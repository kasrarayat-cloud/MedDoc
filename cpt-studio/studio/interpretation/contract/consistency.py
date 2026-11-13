"""Whether pass 1's own values can hold together (docs/gemini-migration/FINAL-V2.md 3.1 rows K1-K8, L1 and Q1, as
REFUTATIONS-V2 revised them [R:HO-7][R:HO-9][R:MO-5]; step 2b of 8.1): the consistency of values (K1-K8), the date
literal in a date's or a timing fact's own words (L1), and the qualifiers pass 1 reported (Q1). ``check`` runs them
all over one answer read by contract/extract_read.py (step 1b); ``rejudge`` re-judges L1's stored literals at assess
and read time.

**What a finding does, and never does** (3.1 "What a failure does", 3.4). Every finding names one fact of pass 1's
answer (by extract_read.FactKey: a fact, or a member of a statement's scope list) and a closed-list reason (a
types.Reason, K1's included: DECISIONS D186); settle (step 3a) makes that fact UNRESOLVED (3.3 row 4 for K1-K7 and L1,
row 5 for Q1). The one key that names no fact of the answer is L1's per-event date rule's: an event's own date_relation
slot, left silent by pass 1, under which settle keeps the relation the event inherits from its section (1.5; D193).
Nothing here sets, changes or removes a value, creates a fact, an exclusion, a support or a contradiction, or makes
anything READY: ``check`` reads its answer and returns findings, which hold keys, reasons and the date literals L1 read,
and no value at all. K8 is the one rule that is not a demotion: a supported and a negated fact of one value (or of a
value inside the negated one) on one object's reached, stations or act places are two facts of pass 1 that settle as the
ONE contradicted fact pass 1 reported (3.3 row 1), so K8 returns which facts join (``Joined``) and creates nothing.

**The rules, as read here** (each reading of an underspecified clause is recorded in DECISIONS D207, the builders'
readings of waves 1 and 2, or in the ruling named beside it):
- An ACT is an event whose status pass 1 did not state negated, and whose kind is not the examination: 3.2.1 calls an
  event whose claimed status is negated a statement, and ADJUDICATION C-1 makes the examination the session, never an
  act. K1's own "statements" are wider, as K1 writes them: negated, or with a well-formed doubt of basis stated on the
  status (1.3).
- K1, values allowed together: a finding demotes the value the rule allows only together with another - the scope, the
  yield, the access outcome, the cause and its event, the part link, the session's reach, stations and completion, the
  visit facts, the other class, the umbrella kind - and never the value it is checked against (kind, status, purpose,
  the session's kind), as v1's structural rules did (normalize._structure); status against timing demotes both, as v1's
  inconsistent_status_time did. The exceptive, listed, single-target and segment rules demote the breadth (3.8 probe
  (c)). A negated part_of (a separate act, 1.6) needs no part_relation.
- K2, session consistency, demotes the act's session fact and the session's examination link only; it never touches
  the examination event's facts, and has no performer arm [R:HO-7]. Its kind arm asks whether the act's session family
  can hold its kind (``family_admits``, the family-kinds table: DECISIONS D191), never whether a code of the family
  accounts for it, so an ERCP's cannulation or a colonoscopy's clip keeps its session and a colonoscopy's PEG does not.
  Its date arm compares the act's OWN date relation with its session examination's claimed one: the examination's own,
  else the occasion of the section its anchor lies in (``containing``, from geometry's G4 edge; 1.5's effective value).
- K3 demotes an act's session fact when a supported place lies in a region its session's family cannot reach (the reach
  is v1's FAMILY_REGIONS by value, DECISIONS D192; a family it does not list is not judged); K4 demotes an anatomy
  entry's surgically_absent type and its organ, and every supported reach, station or act place at or inside that organ
  [A: E17]; K5 demotes a performer and its performer_person when the person's role, or the encounter's documenting
  clinician, disagrees with the performer; K6 the reached point a device also reached; K7 a section's occasion or
  performer framed from outside its role.
- K8's act places are the places of the events in CLAIMED's act class (3.2.1: every event whose status pass 1 did not
  state negated, the examination included); a statement's places are never joined.
- Checks read each object's OWN facts. An act's inherited date relation or performer is checked as the section's fact
  it is (3.3: "steps 1-5 on the section's fact, shared by its acts"), with one exception, L1's per-event date rule
  below (DECISIONS D193). The inherited values read are the examination's date relation K2's date arm compares an act's
  own with, and the occasion an event without a date relation of its own inherits, which L1 judges its own date
  against. Every read across objects is one DECISIONS D201 lists for P-INDEP-SETTLE (step 6a).
- L1 reads, with contract/date_literals.py's copied v1 parsers, only the located words of a fact's own sources (the
  revision's own slice, or the cited units for words ''; ``Words``), never a unit around them. The date of service, an
  other date and an act's ``date`` must equal the literal in their words (v1's verify.date_words: full dates for a day
  value, every literal for a month or a year, each of that precision and equal). A supported timing fact needs every
  literal read in its words to hold it against the reference date at the literal's own precision
  (``date_literals.compare``; DECISIONS D193, with 3.8 probe (b) and v1's D54): on_date_of_service, a day equal to it,
  or a month or a year containing it; earlier_date, a literal that ends before it; later_date, one that starts after
  it. The timing facts are a section's occasion, an event's own date_relation (read with the words of its own ``date``
  too), and the EFFECTIVE date relation of an event that has none of its own but has a supported ``date`` (1.5: the
  occasion of the section its anchor lies in, through ``containing``), read with the occasion's words and the event's
  own date's. That finding is keyed on the event's own date_relation slot, never on the section's fact (D193). Only a
  SUPPORTED ``date`` is read into a relation: a negated date is no evidence of when the act was done. At claim time the
  reference is the document's own date of service, pass 1's stated value when its own literal passes, never a member
  value, and a literal that meets no document date stops nothing [R:MO-5]. ``rejudge`` re-judges the stored literals at
  assess and read time against the effective date (member precedence is dates.py's), with no text, and can only add
  reasons.
- Q1: every qualifier but approximate is a ``qualified:<q>`` reason.

**The tables K1-K4 and K8 read are the caller's** (``Vocabulary``), over enumeration members: containment and regions
(engine/anatomy.py, step 1e), the session families' kinds (engine/requirements_table.FAMILY_KINDS, step 1f: DECISIONS
D191), the umbrellas' coverage, the endoscopic families and the regions each family's session can reach (engine/
catalogue.py, step 1e; FAMILY_REACH: DECISIONS D192), and the extraction kinds (engine/requirements.py, step 1f, design
A's X8). Step 2b depends on 1b and 1c only (DECISIONS D207 accepts this seam), so this module imports no engine module
at run time: settle passes the tables, and only the type checker reads engine/anatomy.py's Region. Nothing here compares
a value with document text.

**K1's reasons** are types.Reason's ``structure_<rule>`` members, one per rule of 3.1 K1 (DECISIONS D186): ``Structure``
keeps the rules' names, each mapped to the Reason of its value when the module is imported, and Findings.structure
holds Reason members, which settle stores as they are.

**Why this is not a reader** (5.6, 5.7 measure 4, WordsNeverDecide and NoWordLists): the checks read enumeration
values, ids, states, links and the doubts' attributes. The one text this module touches is a date's or a timing fact's
own located words, which only contract/date_literals.py's parsers read (the one text module WordsNeverDecide lets
consistency import); it calls no string method, holds no word, phrase, marker or frame list (every module-level
collection holds enumeration members), and imports no regular-expression module itself. Versions: the checks belong to
INVENTORY_VERSION_V2 (gemini-inventory@2): a changed rule re-settles stored pass-1 bytes (1.1, 2.5).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum, unique
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeVar

from studio.interpretation.contract import date_literals
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.extract_read import DateOfService, FactKey, ReadAnswer
from studio.interpretation.contract.types import (AnatomyType, Attribute, Breadth, DateRelation, DateState, DoubtBasis,
                                                  Extent, Fact, FactState, Kind, Landmark, Link, Owner, Performer,
                                                  PersonRole, Precision, Purpose, Qualifier, Reason, SectionRole,
                                                  SessionKind, Source, Station, Status, StoredLiteral)

if TYPE_CHECKING:  # K3's regions, for the type checker only: settle passes the tables (module docstring; D192)
    from studio.interpretation.engine.anatomy import Region

Family = xs.Family
A = Attribute
_E = TypeVar('_E', bound=Enum)

# A place, as the vocabulary's containment and regions take it (engine/anatomy.py's Place): a Landmark (an act's
# places, an anatomy entry's organ), an Extent (a session's reached points) or a Station (a session's stations).
Place = Landmark | Extent | Station

# How L1 reads a source: the text of its located words (geometry.locate's words, the revision's own slice), or of its
# whole cited units for words ''; None when the source does not locate (I1-I3 failed, so nothing is read).
Words = Callable[[Source], str | None]


@unique
class Structure(Enum):
    """K1's rules (3.1 K1, "values allowed together"), in 3.1's order, each named by the value of the Reason its finding
    gives: types.Reason's ``structure_<rule>`` member (DECISIONS D186; ``_STRUCTURE_REASONS``). Each demotes the facts
    named in the module docstring."""
    SCOPE = 'structure_scope'  # scope only on negated or stated-doubt statements
    YIELD = 'structure_yield'  # yield only on extraction kinds
    ACCESS_OUTCOME = 'structure_access_outcome'  # access_outcome only on cannulation
    CAUSE = 'structure_cause'  # cause and cause_event only with purpose hemostasis
    PART_OF = 'structure_part_of'  # part_of and part_relation together
    ENDOSCOPIC = 'structure_endoscopic'  # reached, stations and completion only on endoscopic sessions
    VISIT = 'structure_visit'  # visit facts only on em_visit
    OTHER_CLASS = 'structure_other_class'  # other_class only on kind other
    STATUS_TIME = 'structure_status_time'  # performed or attempted with later_date, planned with earlier_date
    EXCEPTIVE = 'structure_exceptive'  # exceptive needs excepts: existing, of a covered kind, asserted positive
    LISTED_TARGETS = 'structure_listed_targets'  # listed_targets needs 2 or more targets
    SINGLE_TARGET = 'structure_single_target'  # single_target a lesion or a place
    SEGMENT = 'structure_segment'  # segment two landmarks
    UMBRELLA = 'structure_umbrella'  # the umbrella intervention only on statements


# Each K1 rule's Reason (DECISIONS D186): the member of its value, looked up once, so a rule whose reason types.Reason
# does not hold fails the import rather than a check.
_STRUCTURE_REASONS: Mapping[Structure, Reason] = MappingProxyType({rule: Reason(rule.value) for rule in Structure})


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """The tables K1-K4 and K8 read, over enumeration members only. Settle (step 3a) builds it from:

    contains: engine/anatomy.contains(outer, inner), strictly and transitively (K4, K8). region: engine/anatomy.region
    (REGION_OF), None for a place in no region (K3). reach: engine/catalogue.FAMILY_REACH, the regions a session of
    each family can reach, v1's FAMILY_REGIONS by value (K3; DECISIONS D192); a family absent from it is not judged.
    family_admits: whether a session of the family can hold an act of the kind, the kind's membership in
    engine/requirements_table.FAMILY_KINDS[family] (K2's kind arm; DECISIONS D191). covers: engine/catalogue.covers,
    whether a statement of one kind concerns an act of another (K1's exceptive rule). endoscopic:
    engine/catalogue.ENDOSCOPIC_FAMILIES (K1). extraction: engine/requirements.EXTRACTION_KINDS, design A's extraction
    kinds (K1).

    region is typed over Landmark and Region, and reach over SessionKind and Region (D192); region returns None for the
    landmarks REGION_OF places in no region (other, and an anastomosis, a stoma or a pouch), as engine/anatomy.region
    does, so K3 judges no act at them."""
    contains: Callable[[Place, Place], bool]
    region: Callable[[Landmark], Region | None]
    reach: Mapping[SessionKind, frozenset[Region]]
    family_admits: Callable[[SessionKind, Kind], bool]
    covers: Callable[[Kind, Kind], bool]
    endoscopic: frozenset[SessionKind]
    extraction: frozenset[Kind]


@dataclass(frozen=True, slots=True)
class Joined:
    """K8: facts of one object's list - its family, id and attribute - that settle as ONE contradicted fact of pass 1
    (3.3 row 1), each side's sources kept: supported, the facts stating a value; negated, those denying it or a place
    that holds it. Nothing is created: both sides are pass 1's own facts."""
    family: xs.Family
    object: str
    attribute: Attribute
    supported: tuple[FactKey, ...]
    negated: tuple[FactKey, ...]


@dataclass(frozen=True, slots=True)
class Findings:
    """What ``check`` found, by fact (each mapping holds only the facts it names, in the answer's order; an event's
    silent date_relation slot, L1's per-event key, after them in the events' order).

    structure: K1's reasons (types.Reason's structure_<rule> members, DECISIONS D186). consistency: K2-K7's reasons
    (session_inconsistent, session_conflict, session_unreachable, anatomy_conflict, person_conflict,
    instrument_conflict, frame_role). literal: L1's reasons at claim time (literal_mismatch). literals: the date
    literals L1 read in each date and timing fact's words, stored so that assess and read time re-judge them with no
    text (``rejudge``; types.Checks.literals); for an event with no date relation of its own and a supported date, its
    section's occasion literals and its own date's, under its own date_relation key (DECISIONS D193). qualified: Q1's
    reasons. joined: K8's groups. document_date: the claim-time reference date, pass 1's stated date of service when
    its own literal passed, else None."""
    structure: Mapping[FactKey, tuple[Reason, ...]]
    consistency: Mapping[FactKey, tuple[Reason, ...]]
    literal: Mapping[FactKey, tuple[Reason, ...]]
    literals: Mapping[FactKey, tuple[StoredLiteral, ...]]
    qualified: Mapping[FactKey, tuple[Reason, ...]]
    joined: tuple[Joined, ...]
    document_date: date | None

    def reasons(self, key: FactKey) -> tuple[Reason, ...]:
        """Every reason found on the fact at ``key``: K1's, then K2-K7's, L1's and Q1's."""
        return (self.structure.get(key, ()) + self.consistency.get(key, ()) + self.literal.get(key, ())
                + self.qualified.get(key, ()))


# --- the tables of the rules (enumeration members only) -----------------------------------------------------------------

_POSITIVE = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})  # an act done or begun (v1's POSITIVE)
_OTHER_PERFORMERS = frozenset({Performer.OTHER_CLINICIAN, Performer.OTHER_FACILITY})
# K5: the person roles of the documenting team, which 1.4 defines as "the clinician who documents this encounter, or the
# team working with that clinician"; any other role named for a documenting_team performer is "another role".
_TEAM_ROLES = frozenset({PersonRole.DOCUMENTING_CLINICIAN, PersonRole.TRAINEE, PersonRole.ASSISTANT, PersonRole.NURSE,
                         PersonRole.ANESTHESIA})
# K7: the roles whose occasion and performer the document frame never governs, and the owner likewise.
_FRAMED_ROLES = frozenset({SectionRole.HISTORY, SectionRole.INDICATION, SectionRole.MEDICATIONS, SectionRole.PLAN})
_SCOPE_LISTS = (A.SCOPE_TARGETS, A.SCOPE_SEGMENT, A.SCOPE_COVERS, A.SCOPE_EXCEPTS)
_SESSION_FACETS = (A.REACHED, A.STATIONS, A.COMPLETION)  # K1: only on endoscopic sessions
_VISIT_FACTS = (A.VISIT_BASIS, A.VISIT_SEPARATELY_IDENTIFIABLE)
# K8's lists: (family, attribute, the enumeration of its values)
_POLARITY_LISTS: tuple[tuple[xs.Family, Attribute, type[Enum]], ...] = (
    (Family.SESSION, A.REACHED, Extent), (Family.SESSION, A.STATIONS, Station), (Family.EVENT, A.TARGET_PLACES, Landmark))
# Q1: each qualifier that makes a fact unresolved, and its reason; approximate is recorded and never lowers.
_QUALIFIED: Mapping[Qualifier, Reason] = MappingProxyType({
    Qualifier.HEDGED: Reason.QUALIFIED_HEDGED, Qualifier.CONDITIONAL: Reason.QUALIFIED_CONDITIONAL,
    Qualifier.REPORTED: Reason.QUALIFIED_REPORTED, Qualifier.PARTIAL: Reason.QUALIFIED_PARTIAL,
    Qualifier.NAMED_ONLY: Reason.QUALIFIED_NAMED_ONLY, Qualifier.RESTATEMENT_ONLY: Reason.QUALIFIED_RESTATEMENT_ONLY,
    Qualifier.REFERENCE_ONLY: Reason.QUALIFIED_REFERENCE_ONLY,
})
# The precision an ISO value is written at, by its length (3.1 S1 admits YYYY-MM-DD, YYYY-MM and YYYY).
_PRECISION_OF_LENGTH: Mapping[int, Precision] = MappingProxyType({10: Precision.DAY, 7: Precision.MONTH,
                                                                   4: Precision.YEAR})

Found = tuple[FactKey, Fact]


# --- the answer, indexed ----------------------------------------------------------------------------------------------


class _Answer:
    """The read answer's facts and members by (family, object, attribute), its object ids by family, its date of
    service, and each key's place in the answer's order."""

    def __init__(self, answer: ReadAnswer) -> None:
        self.read = answer
        self.ids: dict[xs.Family, tuple[str, ...]] = {
            family: tuple(str(item['id']) for item in answer.answer[family.value])
            for family in Family if family is not Family.ENCOUNTER}
        self.dos: tuple[FactKey, DateOfService] | None = None
        self._facts: dict[tuple[xs.Family, str, Attribute], list[Found]] = {}
        self._members: dict[tuple[xs.Family, str, Attribute], list[tuple[FactKey, str]]] = {}
        self.order: dict[FactKey, int] = {}
        for item in answer.facts:
            self.order[item.key] = len(self.order)
            if isinstance(item.fact, DateOfService):
                self.dos = (item.key, item.fact)
            else:
                self._facts.setdefault((item.key.family, item.key.object, item.key.attribute), []).append(
                    (item.key, item.fact))
        for member in answer.members:
            self.order[member.key] = len(self.order)
            self._members.setdefault((member.key.family, member.key.object, member.key.attribute), []).append(
                (member.key, member.value))

    def facts(self, family: xs.Family, object_id: str, attribute: Attribute) -> list[Found]:
        """Every fact of that object's attribute (a FACT or a slot: at most one; a list: in its order)."""
        return self._facts.get((family, object_id, attribute), [])

    def one(self, family: xs.Family, object_id: str, attribute: Attribute) -> Found | None:
        """The fact of a FACT or a slot, None when the slot is silent."""
        found = self.facts(family, object_id, attribute)
        return found[0] if found else None

    def members(self, family: xs.Family, object_id: str, attribute: Attribute) -> list[tuple[FactKey, str]]:
        """The members of a statement's scope list, with their keys."""
        return self._members.get((family, object_id, attribute), [])

    def inherited(self, event_id: str) -> FactKey:
        """The key of an event's own date_relation slot, which pass 1 left silent: where settle keeps the relation the
        event inherits from its section (1.5) and where L1's per-event date rule puts its finding (DECISIONS D193). No
        fact of the answer has it; it is ordered after the answer's facts and members, in the order it is asked for."""
        key = FactKey(Family.EVENT, event_id, A.DATE_RELATION, 0)
        self.order.setdefault(key, len(self.order))
        return key


def _member(enumeration: type[_E], value: str) -> _E | None:
    """The member of ``enumeration`` whose value is ``value``, None for '' or any other string."""
    for item in enumeration:
        if item.value == value:
            return item
    return None


def _value(found: Found | None, enumeration: type[_E]) -> _E | None:
    """The member a SUPPORTED fact holds, None for a silent slot or any other state."""
    if found is None or found[1].state is not FactState.SUPPORTED:
        return None
    return _member(enumeration, found[1].value)


def _id(found: Found | None) -> str | None:
    """The id a SUPPORTED fact names, None otherwise."""
    if found is None or found[1].state is not FactState.SUPPORTED or found[1].value == '':
        return None
    return found[1].value


def _states_or_offers(found: Found | None, enumeration: type[_E], members: frozenset[_E]) -> bool:
    """Whether a fact states one of ``members`` (supported) or offers one as a side of a contradiction."""
    if found is None:
        return False
    fact = found[1]
    if fact.state is FactState.SUPPORTED:
        return _member(enumeration, fact.value) in members
    if fact.state is FactState.CONTRADICTED:
        return any(_member(enumeration, option.value) in members for option in fact.options)
    return False


def _statement(answer: _Answer, event_id: str) -> bool:
    """K1's statement: an event whose status pass 1 stated negated, or which a well-formed doubt of basis stated names
    for its status (1.3: "the document itself states doubt")."""
    status = answer.one(Family.EVENT, event_id, A.STATUS)
    if status is not None and status[1].state is FactState.NEGATED:
        return True
    return any(not doubt.malformed and doubt.doubt.basis is DoubtBasis.STATED
               and (Family.EVENT, event_id) in doubt.objects and A.STATUS in doubt.named(Family.EVENT)
               for doubt in answer.read.doubts)


def _act_class(answer: _Answer, event_id: str) -> bool:
    """CLAIMED's act class (3.2.1): an event whose status pass 1 did not state negated, the examination included; an
    event whose status it stated negated is a statement."""
    status = answer.one(Family.EVENT, event_id, A.STATUS)
    return status is None or status[1].state is not FactState.NEGATED


def _act(answer: _Answer, event_id: str) -> bool:
    """An act (3.2.1, ADJUDICATION C-1): an event of the act class whose kind is not the examination, which is the
    session."""
    return (_act_class(answer, event_id)
            and _value(answer.one(Family.EVENT, event_id, A.KIND), Kind) is not Kind.EXAMINATION)


class _Out:
    """The findings while they are gathered."""

    def __init__(self) -> None:
        self.structure: dict[FactKey, set[Reason]] = {}
        self.consistency: dict[FactKey, set[Reason]] = {}
        self.literal: dict[FactKey, set[Reason]] = {}
        self.literals: dict[FactKey, tuple[StoredLiteral, ...]] = {}
        self.qualified: dict[FactKey, set[Reason]] = {}
        self.joined: list[Joined] = []

    def rule(self, keys: Iterable[FactKey], rule: Structure) -> None:
        """K1's finding: the rule's Reason on each fact (DECISIONS D186)."""
        for key in keys:
            self.structure.setdefault(key, set()).add(_STRUCTURE_REASONS[rule])

    def reason(self, keys: Iterable[FactKey], reason: Reason) -> None:
        for key in keys:
            self.consistency.setdefault(key, set()).add(reason)


# --- the entry point --------------------------------------------------------------------------------------------------


def check(answer: ReadAnswer, vocabulary: Vocabulary, words: Words,
          containing: Mapping[str, str] | None = None) -> Findings:
    """K1-K8, L1 and Q1 over one read answer. ``vocabulary`` holds the catalogue and anatomy tables (Vocabulary);
    ``words`` gives the text of a source's located words (Words), which L1 alone reads; ``containing`` maps an event id
    to the id of the section its anchor lies in when G4's edge holds (geometry.Sections.attached): K2's date arm reads
    it to find an examination's inherited date relation, and L1 to find the occasion an event with no date relation of
    its own inherits (DECISIONS D193). The answer is read, never changed, and no member value is read: the findings
    depend on the revision and pass 1's bytes alone."""
    indexed = _Answer(answer)
    out = _Out()
    sections = containing or {}
    _k1(indexed, vocabulary, out)
    _k2(indexed, vocabulary, sections, out)
    _k3(indexed, vocabulary, out)
    _k4(indexed, vocabulary, out)
    _k5(indexed, out)
    _k6(indexed, out)
    _k7(indexed, out)
    _k8(indexed, vocabulary, out)
    reference = _l1(indexed, words, sections, out)
    _q1(indexed, out)
    order = indexed.order
    return Findings(
        structure=_frozen(out.structure, order, _ordered),
        consistency=_frozen(out.consistency, order, _ordered),
        literal=_frozen(out.literal, order, _ordered),
        literals=MappingProxyType({key: out.literals[key] for key in sorted(out.literals, key=order.__getitem__)}),
        qualified=_frozen(out.qualified, order, _ordered),
        joined=tuple(out.joined),
        document_date=reference)


def _frozen(found: Mapping[FactKey, set[_E]], order: Mapping[FactKey, int],
            ordered: Callable[[set[_E]], tuple[_E, ...]]) -> Mapping[FactKey, tuple[_E, ...]]:
    return MappingProxyType({key: ordered(found[key]) for key in sorted(found, key=order.__getitem__)})


def _ordered(found: Iterable[Reason]) -> tuple[Reason, ...]:
    """``found`` once each, in the closed list's order (types.Reason)."""
    reasons = set(found)
    return tuple(reason for reason in Reason if reason in reasons)


# --- K1: values allowed together ----------------------------------------------------------------------------------------


def _k1(answer: _Answer, vocabulary: Vocabulary, out: _Out) -> None:
    for event_id in answer.ids[Family.EVENT]:
        _k1_event(answer, vocabulary, event_id, out)
    for session_id in answer.ids[Family.SESSION]:
        facets = [key for attribute in _SESSION_FACETS for key, _ in answer.facts(Family.SESSION, session_id, attribute)]
        if facets and _value(answer.one(Family.SESSION, session_id, A.KIND), SessionKind) not in vocabulary.endoscopic:
            out.rule(facets, Structure.ENDOSCOPIC)


def _k1_event(answer: _Answer, vocabulary: Vocabulary, event_id: str, out: _Out) -> None:
    def keys(*attributes: Attribute) -> list[FactKey]:
        return [key for attribute in attributes for key, _ in answer.facts(Family.EVENT, event_id, attribute)]

    statement = _statement(answer, event_id)
    kind_found = answer.one(Family.EVENT, event_id, A.KIND)
    kind = _value(kind_found, Kind)
    status_found = answer.one(Family.EVENT, event_id, A.STATUS)
    status = _value(status_found, Status)
    breadth_found = answer.one(Family.EVENT, event_id, A.SCOPE_BREADTH)
    scope = keys(A.SCOPE_BREADTH) + [key for attribute in _SCOPE_LISTS
                                     for key, _ in answer.members(Family.EVENT, event_id, attribute)]
    if scope and not statement:
        out.rule(scope, Structure.SCOPE)
    if keys(A.YIELD) and kind not in vocabulary.extraction:
        out.rule(keys(A.YIELD), Structure.YIELD)
    if keys(A.ACCESS_OUTCOME) and kind is not Kind.CANNULATION:
        out.rule(keys(A.ACCESS_OUTCOME), Structure.ACCESS_OUTCOME)
    if keys(A.CAUSE, A.CAUSE_EVENT) and _value(answer.one(Family.EVENT, event_id, A.PURPOSE),
                                                Purpose) is not Purpose.HEMOSTASIS:
        out.rule(keys(A.CAUSE, A.CAUSE_EVENT), Structure.CAUSE)
    part_of, relation = answer.one(Family.EVENT, event_id, A.PART_OF), keys(A.PART_RELATION)
    if part_of is not None and not relation and part_of[1].state is not FactState.NEGATED:
        out.rule([part_of[0]], Structure.PART_OF)  # a negated part_of is a separate act (1.6): no relation needed
    if relation and part_of is None:
        out.rule(relation, Structure.PART_OF)
    if keys(*_VISIT_FACTS) and kind is not Kind.EM_VISIT:
        out.rule(keys(*_VISIT_FACTS), Structure.VISIT)
    if keys(A.OTHER_CLASS) and kind is not Kind.OTHER:
        out.rule(keys(A.OTHER_CLASS), Structure.OTHER_CLASS)
    timing = answer.one(Family.EVENT, event_id, A.DATE_RELATION)
    relation_value = _value(timing, DateRelation)
    if timing is not None and status_found is not None and (
            (status in _POSITIVE and relation_value is DateRelation.LATER_DATE)
            or (status is Status.PLANNED and relation_value is DateRelation.EARLIER_DATE)):
        out.rule([status_found[0], timing[0]], Structure.STATUS_TIME)
    breadth = _value(breadth_found, Breadth)
    if breadth_found is not None and breadth is not None:
        rule = _breadth_rule(answer, vocabulary, event_id, kind, breadth)
        if rule is not None:
            out.rule([breadth_found[0]], rule)
    if kind_found is not None and kind is Kind.INTERVENTION and not statement:
        out.rule([kind_found[0]], Structure.UMBRELLA)


def _breadth_rule(answer: _Answer, vocabulary: Vocabulary, event_id: str, kind: Kind | None,
                  breadth: Breadth) -> Structure | None:
    """The K1 rule a supported breadth breaks, None when it keeps them: exceptive, listed_targets, single_target and
    segment each need their lists (3.1 K1); all_of_kind needs nothing here."""
    lesions = frozenset(answer.ids[Family.LESION])
    targets = {value for _, value in answer.members(Family.EVENT, event_id, A.SCOPE_TARGETS) if value in lesions}
    if breadth is Breadth.EXCEPTIVE:
        excepts = [value for _, value in answer.members(Family.EVENT, event_id, A.SCOPE_EXCEPTS)]
        events = frozenset(answer.ids[Family.EVENT])
        if not excepts or any(
                value not in events or kind is None
                or not _covered(vocabulary, kind, _value(answer.one(Family.EVENT, value, A.KIND), Kind))
                or _value(answer.one(Family.EVENT, value, A.STATUS), Status) not in _POSITIVE
                for value in excepts):
            return Structure.EXCEPTIVE
    elif breadth is Breadth.LISTED_TARGETS:
        if len(targets) < 2:
            return Structure.LISTED_TARGETS
    elif breadth is Breadth.SINGLE_TARGET:
        lesion = _id(answer.one(Family.EVENT, event_id, A.TARGET_LESION))
        places = [fact for _, fact in answer.facts(Family.EVENT, event_id, A.TARGET_PLACES)
                  if fact.state is FactState.SUPPORTED]
        if lesion not in lesions and not places and not targets:
            return Structure.SINGLE_TARGET
    elif breadth is Breadth.SEGMENT:
        segment = {value for _, value in answer.members(Family.EVENT, event_id, A.SCOPE_SEGMENT)}
        if len(segment) != 2 or len(answer.members(Family.EVENT, event_id, A.SCOPE_SEGMENT)) != 2:
            return Structure.SEGMENT
    return None


def _covered(vocabulary: Vocabulary, statement: Kind, act: Kind | None) -> bool:
    return act is not None and vocabulary.covers(statement, act)


# --- K2: session consistency [R:HO-7] -------------------------------------------------------------------------------------


def _k2(answer: _Answer, vocabulary: Vocabulary, containing: Mapping[str, str], out: _Out) -> None:
    sessions = frozenset(answer.ids[Family.SESSION])
    events = frozenset(answer.ids[Family.EVENT])
    for event_id in answer.ids[Family.EVENT]:  # an event's session exists
        found = answer.one(Family.EVENT, event_id, A.SESSION)
        if found is not None and any(name not in sessions for name in _named(found[1])):
            out.reason([found[0]], Reason.SESSION_INCONSISTENT)
    for session_id in answer.ids[Family.SESSION]:  # a session's examination names it
        link = answer.one(Family.SESSION, session_id, A.EXAMINATION)
        examination = _id(link)
        if link is None or examination is None or examination not in events:
            continue
        theirs = answer.one(Family.EVENT, examination, A.SESSION)
        if theirs is not None and not _names(theirs[1], session_id):
            out.reason([link[0]], Reason.SESSION_INCONSISTENT)
    for event_id in answer.ids[Family.EVENT]:
        found = answer.one(Family.EVENT, event_id, A.SESSION)
        session = _id(found)
        if found is None or session is None or session not in sessions or not _act(answer, event_id):
            continue
        kind = _value(answer.one(Family.EVENT, event_id, A.KIND), Kind)
        family = _value(answer.one(Family.SESSION, session, A.KIND), SessionKind)
        if kind is not None and family is not None and not vocabulary.family_admits(family, kind):
            out.reason([found[0]], Reason.SESSION_INCONSISTENT)  # an act's session kind admits its kind (D191)
        own = answer.one(Family.EVENT, event_id, A.DATE_RELATION)
        examination = _id(answer.one(Family.SESSION, session, A.EXAMINATION))
        if own is None or examination is None or examination == event_id or examination not in events:
            continue
        theirs = answer.one(Family.EVENT, examination, A.DATE_RELATION)
        if theirs is None and examination in containing:
            theirs = answer.one(Family.SECTION, containing[examination], A.OCCASION)
        if theirs is not None and _incompatible(own[1], theirs[1]):
            out.reason([found[0]], Reason.SESSION_CONFLICT)  # the act's own other date: its session fact only


def _named(fact: Fact) -> list[str]:
    """The ids a fact names: its value, or each side's value when contradicted ('' names nothing)."""
    names = [option.value for option in fact.options] if fact.state is FactState.CONTRADICTED else [fact.value]
    return [name for name in names if name != '']


def _names(fact: Fact, object_id: str) -> bool:
    """Whether a fact states ``object_id`` (supported), or offers it as a side of a contradiction."""
    if fact.state is FactState.SUPPORTED:
        return fact.value == object_id
    return fact.state is FactState.CONTRADICTED and any(option.value == object_id for option in fact.options)


def _incompatible(first: Fact, second: Fact) -> bool:
    """Whether two date relations cannot both hold: both stated with different values, or one stated and the other
    denying that same value. A contradicted one states no value; two denials never conflict."""
    states = {first.state, second.state}
    if FactState.CONTRADICTED in states or first.value == '' or second.value == '':
        return False
    if first.state is FactState.SUPPORTED and second.state is FactState.SUPPORTED:
        return first.value != second.value
    return states == {FactState.SUPPORTED, FactState.NEGATED} and first.value == second.value


# --- K3: place against session; K4: anatomy against places ------------------------------------------------------------


def _k3(answer: _Answer, vocabulary: Vocabulary, out: _Out) -> None:
    sessions = frozenset(answer.ids[Family.SESSION])
    for event_id in answer.ids[Family.EVENT]:
        found = answer.one(Family.EVENT, event_id, A.SESSION)
        session_id = _id(found)
        if found is None or session_id is None or session_id not in sessions or not _act(answer, event_id):
            continue
        family = _value(answer.one(Family.SESSION, session_id, A.KIND), SessionKind)
        reach = vocabulary.reach.get(family) if family is not None else None
        if reach is None:
            continue
        for _, fact in answer.facts(Family.EVENT, event_id, A.TARGET_PLACES):
            place = _member(Landmark, fact.value) if fact.state is FactState.SUPPORTED else None
            region = vocabulary.region(place) if place is not None else None
            if region is not None and region not in reach:
                out.reason([found[0]], Reason.SESSION_UNREACHABLE)  # nothing is ever moved
                break


def _k4(answer: _Answer, vocabulary: Vocabulary, out: _Out) -> None:
    places: list[tuple[FactKey, Place]] = []
    for session_id in answer.ids[Family.SESSION]:
        for attribute, enumeration in ((A.REACHED, Extent), (A.STATIONS, Station)):
            places += _supported_places(answer.facts(Family.SESSION, session_id, attribute), enumeration)
    for event_id in answer.ids[Family.EVENT]:
        if _act(answer, event_id):
            places += _supported_places(answer.facts(Family.EVENT, event_id, A.TARGET_PLACES), Landmark)
    for anatomy_id in answer.ids[Family.ANATOMY]:
        absent = answer.one(Family.ANATOMY, anatomy_id, A.TYPE)
        organ_found = answer.one(Family.ANATOMY, anatomy_id, A.ORGAN)
        organ = _value(organ_found, Landmark)
        if (absent is None or organ_found is None or organ is None
                or _value(absent, AnatomyType) is not AnatomyType.SURGICALLY_ABSENT):
            continue
        hits = [key for key, place in places if place.value == organ.value or vocabulary.contains(organ, place)]
        if hits:
            out.reason([absent[0], organ_found[0], *hits], Reason.ANATOMY_CONFLICT)


def _supported_places(found: Sequence[Found], enumeration: type[Enum]) -> list[tuple[FactKey, Place]]:
    return _places(found, enumeration, FactState.SUPPORTED)


# --- K5: person against performer; K6: instrument; K7: frame by role --------------------------------------------------


def _k5(answer: _Answer, out: _Out) -> None:
    roles = {person_id: _value(answer.one(Family.PERSON, person_id, A.ROLE), PersonRole)
             for person_id in answer.ids[Family.PERSON]}
    documenting = _id(answer.one(Family.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN))
    for family in (Family.EVENT, Family.SECTION):
        for object_id in answer.ids[family]:
            performer_found = answer.one(family, object_id, A.PERFORMER)
            person_found = answer.one(family, object_id, A.PERFORMER_PERSON)
            performer, person = _value(performer_found, Performer), _id(person_found)
            if performer_found is None or person_found is None or performer is None or person is None:
                continue
            role = roles.get(person)
            if ((performer is Performer.DOCUMENTING_TEAM and role is not None and role not in _TEAM_ROLES)
                    or (performer in _OTHER_PERFORMERS
                        and (role is PersonRole.DOCUMENTING_CLINICIAN or person == documenting))):
                out.reason([performer_found[0], person_found[0]], Reason.PERSON_CONFLICT)


def _k6(answer: _Answer, out: _Out) -> None:
    for session_id in answer.ids[Family.SESSION]:
        device = {fact.value for _, fact in answer.facts(Family.SESSION, session_id, A.DEVICE_REACHED)
                  if fact.state is FactState.SUPPORTED}
        out.reason([key for key, fact in answer.facts(Family.SESSION, session_id, A.REACHED)
                    if fact.state is FactState.SUPPORTED and fact.value in device], Reason.INSTRUMENT_CONFLICT)


def _k7(answer: _Answer, out: _Out) -> None:
    for section_id in answer.ids[Family.SECTION]:
        if not (_states_or_offers(answer.one(Family.SECTION, section_id, A.ROLE), SectionRole, _FRAMED_ROLES)
                or _states_or_offers(answer.one(Family.SECTION, section_id, A.OWNER), Owner,
                                     frozenset({Owner.OUTSIDE_RECORD}))):
            continue
        for attribute, governed in ((A.OCCASION, DateRelation.ON_DATE_OF_SERVICE.value),
                                    (A.PERFORMER, Performer.DOCUMENTING_TEAM.value)):
            for key, fact in answer.facts(Family.SECTION, section_id, attribute):
                framed = any(source.link is Link.DOCUMENT_FRAME for source in fact.sources)
                placed = (fact.state is FactState.SUPPORTED and fact.value == governed
                          and any(source.link is Link.PLACING for source in fact.sources))
                if framed or placed:
                    out.reason([key], Reason.FRAME_ROLE)


# --- K8: both polarities [R:HO-9] -------------------------------------------------------------------------------------


def _k8(answer: _Answer, vocabulary: Vocabulary, out: _Out) -> None:
    """A supported fact whose value is a negated fact's value, or lies inside it, on one object's list: pass 1 stated
    both sides (reaching the cecum and not reaching the colon), so the two join. A supported value that only holds the
    negated one (reached the colon, not the cecum: an incomplete colonoscopy) is no contradiction and joins nothing.
    The places joined are ACT places (3.1 K8): those of the events of CLAIMED's act class, the examination included. A
    statement's places are never joined: its negated place has no statement-phrased template, so it stays unestablished
    and 4.5's target row still holds (fail-closed; the arbiter triage's repair 2b#3)."""
    for family, attribute, enumeration in _POLARITY_LISTS:
        for object_id in answer.ids[family]:
            if family is Family.EVENT and not _act_class(answer, object_id):
                continue
            found = answer.facts(family, object_id, attribute)
            stated = _places(found, enumeration, FactState.SUPPORTED)
            denied = _places(found, enumeration, FactState.NEGATED)
            edges = [(left, right) for left, inner in stated for right, outer in denied
                     if inner.value == outer.value or vocabulary.contains(outer, inner)]
            for group in _components(edges):
                out.joined.append(Joined(family, object_id, attribute,
                                         supported=tuple(key for key, _ in stated if key in group),
                                         negated=tuple(key for key, _ in denied if key in group)))


def _places(found: Sequence[Found], enumeration: type[Enum], state: FactState) -> list[tuple[FactKey, Place]]:
    """The places of a list's facts in ``state``, as members of the list's enumeration, in the list's order."""
    out: list[tuple[FactKey, Place]] = []
    for key, fact in found:
        place = _member(enumeration, fact.value) if fact.state is state else None
        if isinstance(place, (Landmark, Extent, Station)):
            out.append((key, place))
    return out


def _components(edges: Sequence[tuple[FactKey, FactKey]]) -> list[set[FactKey]]:
    """The connected groups of facts the edges join, ordered by their first fact in the list."""
    groups: list[set[FactKey]] = []
    for left, right in edges:
        touching = [group for group in groups if left in group or right in group]
        merged = {left, right}.union(*touching)
        groups = [group for group in groups if group not in touching]
        groups.append(merged)
    return sorted(groups, key=lambda group: min(key.index for key in group))


# --- L1: date literals [R:MO-5] ---------------------------------------------------------------------------------------


def _l1(answer: _Answer, words: Words, containing: Mapping[str, str], out: _Out) -> date | None:
    """L1 at claim time. The date of service first: its value against the full dates in its words; the reference date
    is that value when its literal passes. Then each other date, each event's date, each event's effective date relation
    and each section's occasion. Returns the reference date.

    An event's effective date relation (1.5) is its own, read with the words of its own date; when pass 1 left its own
    slot silent and the event has a supported date, it is the occasion of the section its anchor lies in
    (``containing``), read with the occasion's words and the event's own date's, and judged and stored under the
    event's own date_relation key (``_Answer.inherited``), never the section's (DECISIONS D193). Only a supported date's
    words are read into a relation: a negated date is no evidence of when the act was done, and a contradicted one
    states no date (D193; the arbiter triage's repair 2b#5)."""
    reference: date | None = None
    if answer.dos is not None:
        key, when = answer.dos
        sides = ([(when.value, when.sources)] if when.state is DateState.STATED
                 else [(option.value, option.sources) for option in when.options])
        if sides:
            passed = _transcription(key, sides, words, out)
            if passed and when.state is DateState.STATED and _precision(when.value) is Precision.DAY:
                reference = date.fromisoformat(when.value)
    encounter: Mapping[str, Any] = answer.read.answer[Family.ENCOUNTER.value]
    for key, fact in answer.facts(Family.ENCOUNTER, '', A.OTHER_DATES_ROLE):
        other = str(encounter['other_dates'][key.index]['value'])  # the date the role fact's words state
        _transcription(key, [(other, fact.sources)], words, out)
    for event_id in answer.ids[Family.EVENT]:
        dated = answer.one(Family.EVENT, event_id, A.DATE)
        if dated is not None:
            fact = dated[1]
            sides = ([(option.value, option.sources) for option in fact.options]
                     if fact.state is FactState.CONTRADICTED else [(fact.value, fact.sources)])
            _transcription(dated[0], sides, words, out)
        supported = dated is not None and dated[1].state is FactState.SUPPORTED
        date_sources = dated[1].sources if dated is not None and supported else ()
        own = answer.one(Family.EVENT, event_id, A.DATE_RELATION)
        if own is not None:
            _timing(own, date_sources, words, reference, out)
        elif supported and event_id in containing:
            occasion = answer.one(Family.SECTION, containing[event_id], A.OCCASION)
            if occasion is not None:
                _timing((answer.inherited(event_id), occasion[1]), date_sources, words, reference, out)
    for section_id in answer.ids[Family.SECTION]:
        occasion = answer.one(Family.SECTION, section_id, A.OCCASION)
        if occasion is not None:
            _timing(occasion, (), words, reference, out)
    return reference


def _precision(value: str) -> Precision | None:
    return _PRECISION_OF_LENGTH.get(len(value))


def _transcription(key: FactKey, sides: Sequence[tuple[str, Sequence[Source]]], words: Words, out: _Out) -> bool:
    """L1 on a date's value (the date of service, an other date, an act's date; each side of a contradicted one): the
    literals in its sources' words - the full dates for a day value, every literal for a month or a year - are at least
    one, each of the value's precision and equal to it (v1's verify.date_words over every source). Stores what was read;
    literal_mismatch otherwise."""
    passed, read = True, []
    for value, sources in sides:
        precision = _precision(value)
        literals = _read(sources, words, day_only=precision is Precision.DAY)
        read += literals
        if precision is None or not literals or not all(
                literal.precision == precision.value and literal.iso == value for literal in literals):
            passed = False
    out.literals[key] = _stored(read)
    if not passed:
        out.literal.setdefault(key, set()).add(Reason.LITERAL_MISMATCH)
    return passed


def _timing(found: Found, date_sources: Sequence[Source], words: Words, reference: date | None, out: _Out) -> None:
    """L1 on a timing fact at ``found``'s key (an event's effective date relation, with the words of its own supported
    date; a section's occasion): every literal read is stored; a supported relation is judged against the claim-time
    reference date, and a literal that meets no document date stops nothing."""
    key, fact = found
    literals = _read([*fact.sources, *date_sources], words, day_only=False)
    out.literals[key] = _stored(literals)
    relation = _member(DateRelation, fact.value) if fact.state is FactState.SUPPORTED else None
    if relation is None or reference is None:
        return
    if not all(_holds(relation, literal.value, literal.precision, reference) for literal in literals):
        out.literal.setdefault(key, set()).add(Reason.LITERAL_MISMATCH)


def _read(sources: Iterable[Source], words: Words, *, day_only: bool) -> list[date_literals.DateLiteral]:
    """The date literals in the located words of each source, in order: full dates only, or every literal."""
    found: list[date_literals.DateLiteral] = []
    for source in sources:
        text = words(source)
        if text is not None:
            found += date_literals.full_dates(text) if day_only else date_literals.dates(text)
    return found


def _stored(literals: Sequence[date_literals.DateLiteral]) -> tuple[StoredLiteral, ...]:
    return tuple(StoredLiteral(literal.iso, Precision(literal.precision)) for literal in literals)


def _holds(relation: DateRelation, when: date, precision: str, reference: date) -> bool:
    """Whether a literal (``when`` at ``precision``) agrees with ``relation`` against ``reference``, at the literal's
    own precision (date_literals.compare; DECISIONS D193): on_date_of_service, a literal that holds it - a day equal to
    it, a month or a year containing it (3.8 probe (b): a date 2023 fails it); earlier_date, a literal that ends before
    it; later_date, one that starts after it."""
    order = date_literals.compare(when, precision, reference)
    if relation is DateRelation.ON_DATE_OF_SERVICE:
        return order == 0
    if relation is DateRelation.EARLIER_DATE:
        return order < 0
    return order > 0


def rejudge(relation: DateRelation, literals: Sequence[StoredLiteral], effective: date | None,
            stored: Iterable[Reason] = ()) -> tuple[Reason, ...]:
    """L1 re-judged at assess and at read time (3.1 L1; 4.2 effective), with no text: a supported timing fact of
    ``relation`` whose stored ``literals`` are judged against ``effective``, the effective date of service (member
    precedence is dates.py's), with ``stored`` its reasons so far. It can only demote: the result is ``stored`` plus
    literal_mismatch when a literal disagrees with the effective date at its own precision (a day, a month or a year:
    DECISIONS D193; or cannot be read back), or literal_unchecked when a day literal meets no effective date (D193 keeps
    that one day-only). An event's inherited date relation is re-judged from the literals stored under its own key,
    its section's occasion's and its own date's (D193)."""
    reasons = set(stored)
    if effective is None:
        if any(literal.precision is Precision.DAY for literal in literals):
            reasons.add(Reason.LITERAL_UNCHECKED)
        return _ordered(reasons)
    for literal in literals:
        when = date_literals.stored_date(literal.value, literal.precision.value)
        if when is None or not _holds(relation, when, literal.precision.value, effective):
            reasons.add(Reason.LITERAL_MISMATCH)
    return _ordered(reasons)


# --- Q1: qualifiers -----------------------------------------------------------------------------------------------------


def _q1(answer: _Answer, out: _Out) -> None:
    for item in answer.read.facts:
        if isinstance(item.fact, Fact):
            found = {_QUALIFIED[qualifier] for qualifier in item.fact.qualifiers if qualifier in _QUALIFIED}
            if found:
                out.qualified[item.key] = found
