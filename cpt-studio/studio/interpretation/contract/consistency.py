"""Whether pass 1's own values can hold together (docs/gemini-migration/FINAL-V2.md 3.1 rows K1-K8, L1 and Q1, as
REFUTATIONS-V2 revised them [R:HO-7][R:HO-9][R:MO-5]; step 2b of 8.1; AMENDMENT-2 4.3.3 [R:truth-T3][R:truth-T9], step
f3s): the consistency of values (K1-K8), the date literal in a date's or a timing fact's own words (L1), and the
qualifiers pass 1 reported (Q1). ``check`` runs them all over one answer read by contract/extract_read.py (step 1b);
``rejudge`` re-judges L1's stored literals at assess and read time.

**Slots are read as a single-valued attribute is read** (AMENDMENT-2 4.3.3): _Answer.one gives extract_read.merged's
view - for a slot holding more than one fact (read under gemini-events@3), ONE contradicted fact whose options are every
written value, never its first written fact - and every K rule and L1 FIRES FOR EACH VALUE a slot's fact states or
offers wherever its firing demotes another fact: its supported value, each side of pass 1's own contradiction, each
value an overfilled slot's written facts that are not negated write, and for a rule reading two slots every combination
(``_offered``; K1's status against timing, K2's arms, K3, K4's type and organ, K5's performer, person, role and
documenting clinician, K7's role, L1's relations; an overfilled date has L1 run on each written date, and an act's date
relation is judged with the words of every date its slot states or offers, ``_dates_read``) - gemini-inventory@3's
reading; gemini-inventory@2 keeps the one it was recorded with (Versions, below). A rule that
fires on an ABSENCE (no established value) reads the established value alone (``_value``), which the merged view never
is - so it fires. K2's examination-link arm, which fires when the examination's session does NOT name the session,
counts a session as named only when every written fact states it (``_names``: never a contradiction, never a denied
value). So the merged view is never weaker than one of its written facts read alone, for any rule (4.4), and offering
more values only demotes more (D178: every check only demotes). A finding on the merged view lands on every written
fact of the slot (ReadFact.keys).

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
  too), and the EFFECTIVE date relation of an event that has none of its own but whose ``date`` slot states or offers
  a date (1.5: the occasion of the section its anchor lies in, through ``containing``), read with the occasion's words
  and the event's own date's. That finding is keyed on the event's own date_relation slot, never on the section's fact
  (D193). Every date the slot states or offers is read into a relation - a supported one, each side of pass 1's own
  contradiction, each written date of an overfilled slot that is not negated (AMENDMENT-2 4.3.3 [R:truth-T3]
  [R:truth-T9]; ``_dates_read``) - so the relation fails when any of them, read with it alone, would; a negated date is
  no evidence of when the act was done, and its words are never read. Under gemini-inventory@2 L1 reads as that label
  was recorded (D193; Versions, below): a supported relation alone is judged, and a supported date alone is read into
  a relation and makes an event with no relation of its own judge the occasion it inherits. At claim time the
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
the inventory version (gemini-inventory@3 since AMENDMENT-2's stated-or-offered reading): a changed rule re-settles
stored pass-1 bytes (1.1, 2.5). ``check`` is given the inventory version the findings are made for (the version the
row they settle into is written at: gemini-inventory@3 on the current path, the default), and a label's rule does not
change after its first recording (D202). So EVERY check AMENDMENT-2 4.3.3 changed reads a slot through the reading
of that version (``_Reading``; DECISIONS D294 F2, D297 R2RX-1, D301 RBRX-1): under gemini-inventory@3 (and every label
but @2) the stated-or-offered reading above; under gemini-inventory@2, recorded before AMENDMENT-2, the reading that
label was recorded with, in each check AMENDMENT-2 4.3.3 widened - K1's status against timing, K2's examination-link,
kind and date arms, K3, K4's type and organ, K5's performer, person, role and documenting clinician, and L1's judgment
of a timing fact: the relation sides it judges, the dates it reads into an act's relation, and the condition on which
an act with no relation of its own judges the occasion it inherits - where a fact states its value only when it is
supported (a contradicted fact, pass 1's own contradiction, states no value: L1 judges a supported relation only, and
only a supported date is read into a relation or makes an act judge its inherited occasion, D193's clause), K2's
examination link is named by a supported session of that value or a contradiction offering it as a side, and two date
relations conflict only when both are stated, or one states the value the other denies (``_RECORDED``). The checks
AMENDMENT-2 changed only through the merged view of an overfilled slot (K1's other rules, K2's existence arm, K6, K7,
K8, and L1's transcription of each written date of an overfilled date slot) read every fact pass 1 wrote alone exactly
as before under both labels, and no answer read under gemini-events@2 holds a merged view (an overfilled slot is
refused whole there, 4.3.1). D293 O3's contradicted-date clause (AMENDMENT-2 4.3.3 superseding D193's) is therefore
gemini-inventory@3's; gemini-inventory@2 keeps D193's, as recorded (D301 RBRX-1).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum, unique
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from studio import interpretation
from studio.interpretation.contract import date_literals
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.extract_read import DateOfService, FactKey, ReadAnswer, ReadFact, merged
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
    text (``rejudge``; types.Checks.literals); for an event with no date relation of its own whose date slot states or
    offers a date, its section's occasion literals and those of every date its slot states or offers, under its own
    date_relation key (DECISIONS D193; AMENDMENT-2 4.3.3). qualified: Q1's
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
        self._read: dict[tuple[xs.Family, str, Attribute], list[ReadFact]] = {}
        self._members: dict[tuple[xs.Family, str, Attribute], list[tuple[FactKey, str]]] = {}
        self.order: dict[FactKey, int] = {}
        for item in answer.facts:
            self.order[item.key] = len(self.order)
            if isinstance(item.fact, DateOfService):
                self.dos = (item.key, item.fact)
            else:
                self._facts.setdefault((item.key.family, item.key.object, item.key.attribute), []).append(
                    (item.key, item.fact))
                self._read.setdefault((item.key.family, item.key.object, item.key.attribute), []).append(item)
        for member in answer.members:
            self.order[member.key] = len(self.order)
            self._members.setdefault((member.key.family, member.key.object, member.key.attribute), []).append(
                (member.key, member.value))

    def facts(self, family: xs.Family, object_id: str, attribute: Attribute) -> list[Found]:
        """Every fact of that object's attribute (a FACT or a slot: at most one; a list: in its order)."""
        return self._facts.get((family, object_id, attribute), [])

    def one(self, family: xs.Family, object_id: str, attribute: Attribute) -> ReadFact | None:
        """The fact of a FACT or a slot as a reader of a single-valued attribute reads it (extract_read.merged,
        AMENDMENT-2 4.3.3): None when the slot is silent; for a slot holding more than one fact, the MERGED VIEW - state
        contradicted, every written value an option, its written facts kept (ReadFact.keys: a finding on it lands on
        every fact of the slot; stated_values and asserted_values: what it states or offers) - never its first written
        fact."""
        return merged(self._read.get((family, object_id, attribute), []))

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


def _fact(found: ReadFact) -> Fact:
    """A read slot's fact (the date of service is never read through _Answer.one: it is _Answer.dos)."""
    if not isinstance(found.fact, Fact):
        raise TypeError('The date of service is read as _Answer.dos, never as a slot.')
    return found.fact


def _value(found: ReadFact | None, enumeration: type[_E]) -> _E | None:
    """The member a SUPPORTED fact holds, None for a silent slot or any other state (the merged view of an overfilled
    slot is contradicted, so it holds none). Read only where a rule fires on an ABSENCE (no established value: the
    reading that fires most) or demotes the fact it reads; a rule whose firing demotes another fact reads _offered."""
    if found is None or _fact(found).state is not FactState.SUPPORTED:
        return None
    return _member(enumeration, _fact(found).value)


def _id(found: ReadFact | None) -> str | None:
    """The id a SUPPORTED fact names, None otherwise (read as _value is)."""
    if found is None or _fact(found).state is not FactState.SUPPORTED or _fact(found).value == '':
        return None
    return _fact(found).value


def _offered(found: ReadFact | None, enumeration: type[_E]) -> tuple[_E, ...]:
    """Each member a fact states or offers, as every K rule and L1 read it wherever their firing demotes another fact
    (AMENDMENT-2 4.3.3 [R:truth-T3]): a supported fact's value, each side of pass 1's own contradiction, each value an
    overfilled slot's supported or contradicted written facts write (ReadFact.asserted_values: a value only negated
    facts write is never stated, and one a written fact states fires the rule even if another denies it - firing only
    demotes); () for a silent slot or a negated fact."""
    if found is None:
        return ()
    members = (_member(enumeration, value) for value in found.asserted_values)
    return tuple(member for member in members if member is not None)


def _offered_ids(found: ReadFact | None) -> tuple[str, ...]:
    """Each id a fact states or offers, read as _offered reads a member."""
    return () if found is None else found.asserted_values


def _states_or_offers(found: ReadFact | None, enumeration: type[_E], members: frozenset[_E]) -> bool:
    """Whether a fact states one of ``members`` (supported), offers one as a side of a contradiction, or - the merged
    view of an overfilled slot - writes one in a fact that is not negated (_offered)."""
    return any(member in members for member in _offered(found, enumeration))


def _supported(found: ReadFact | None, enumeration: type[_E]) -> tuple[_E, ...]:
    """The member a SUPPORTED fact holds, as a tuple of one or none (_value): gemini-inventory@2's read of a slot whose
    value decides a K rule or the relation L1 judges, as that label was recorded - a contradicted fact (pass 1's own
    contradiction) states no value (_RECORDED)."""
    member = _value(found, enumeration)
    return () if member is None else (member,)


def _statement(answer: _Answer, event_id: str) -> bool:
    """K1's statement: an event whose status pass 1 stated negated, or which a well-formed doubt of basis stated names
    for its status (1.3: "the document itself states doubt")."""
    status = answer.one(Family.EVENT, event_id, A.STATUS)
    if status is not None and _fact(status).state is FactState.NEGATED:
        return True
    return any(not doubt.malformed and doubt.doubt.basis is DoubtBasis.STATED
               and (Family.EVENT, event_id) in doubt.objects and A.STATUS in doubt.named(Family.EVENT)
               for doubt in answer.read.doubts)


def _act_class(answer: _Answer, event_id: str) -> bool:
    """CLAIMED's act class (3.2.1): an event whose status pass 1 did not state negated, the examination included; an
    event whose status it stated negated is a statement."""
    status = answer.one(Family.EVENT, event_id, A.STATUS)
    return status is None or _fact(status).state is not FactState.NEGATED


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
          containing: Mapping[str, str] | None = None, *,
          inventory_version: str = interpretation.INVENTORY_VERSION_V3) -> Findings:
    """K1-K8, L1 and Q1 over one read answer. ``vocabulary`` holds the catalogue and anatomy tables (Vocabulary);
    ``words`` gives the text of a source's located words (Words), which L1 alone reads; ``containing`` maps an event id
    to the id of the section its anchor lies in when G4's edge holds (geometry.Sections.attached): K2's date arm reads
    it to find an examination's inherited date relation, and L1 to find the occasion an event with no date relation of
    its own inherits (DECISIONS D193). ``inventory_version``: the inventory version the findings are made for - the one
    the row they settle into is written at - whose rules they apply (gemini-inventory@3, the current path's, by
    default): every K rule and L1 read a slot through that version's reading (``_reading``: under gemini-inventory@2
    the reading it was recorded with; DECISIONS D294 F2, D297 R2RX-1, D301 RBRX-1). The answer is read, never changed,
    and no member value is read: the findings depend on the revision, pass 1's bytes and the label alone."""
    indexed = _Answer(answer)
    out = _Out()
    sections = containing or {}
    reading = _reading(inventory_version)
    _k1(indexed, vocabulary, out, reading)
    _k2(indexed, vocabulary, sections, out, reading)
    _k3(indexed, vocabulary, out, reading)
    _k4(indexed, vocabulary, out, reading)
    _k5(indexed, out, reading)
    _k6(indexed, out)
    _k7(indexed, out)
    _k8(indexed, vocabulary, out)
    reference = _l1(indexed, words, sections, out, reading)
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


def _k1(answer: _Answer, vocabulary: Vocabulary, out: _Out, reading: _Reading) -> None:
    for event_id in answer.ids[Family.EVENT]:
        _k1_event(answer, vocabulary, event_id, out, reading)
    for session_id in answer.ids[Family.SESSION]:
        facets = [key for attribute in _SESSION_FACETS for key, _ in answer.facts(Family.SESSION, session_id, attribute)]
        if facets and _value(answer.one(Family.SESSION, session_id, A.KIND), SessionKind) not in vocabulary.endoscopic:
            out.rule(facets, Structure.ENDOSCOPIC)


def _k1_event(answer: _Answer, vocabulary: Vocabulary, event_id: str, out: _Out, reading: _Reading) -> None:
    def keys(*attributes: Attribute) -> list[FactKey]:
        return [key for attribute in attributes for key, _ in answer.facts(Family.EVENT, event_id, attribute)]

    statement = _statement(answer, event_id)
    kind_found = answer.one(Family.EVENT, event_id, A.KIND)
    kind = _value(kind_found, Kind)
    status_found = answer.one(Family.EVENT, event_id, A.STATUS)
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
    if part_of is not None and not relation and _fact(part_of).state is not FactState.NEGATED:
        out.rule(part_of.keys, Structure.PART_OF)  # a negated part_of is a separate act (1.6): no relation needed
    if relation and part_of is None:
        out.rule(relation, Structure.PART_OF)
    if keys(*_VISIT_FACTS) and kind is not Kind.EM_VISIT:
        out.rule(keys(*_VISIT_FACTS), Structure.VISIT)
    if keys(A.OTHER_CLASS) and kind is not Kind.OTHER:
        out.rule(keys(A.OTHER_CLASS), Structure.OTHER_CLASS)
    timing = answer.one(Family.EVENT, event_id, A.DATE_RELATION)
    # status against timing demotes both, so it fires on every value either states or offers ([R:truth-T3]) - read as
    # the findings' inventory version reads them (_Reading: gemini-inventory@2's supported values only)
    if timing is not None and status_found is not None and any(
            (stated in _POSITIVE and relation is DateRelation.LATER_DATE)
            or (stated is Status.PLANNED and relation is DateRelation.EARLIER_DATE)
            for stated in reading.members(status_found, Status)
            for relation in reading.members(timing, DateRelation)):
        out.rule([*status_found.keys, *timing.keys], Structure.STATUS_TIME)
    breadth = _value(breadth_found, Breadth)
    if breadth_found is not None and breadth is not None:
        rule = _breadth_rule(answer, vocabulary, event_id, kind, breadth)
        if rule is not None:
            out.rule(breadth_found.keys, rule)
    if kind_found is not None and kind is Kind.INTERVENTION and not statement:
        out.rule(kind_found.keys, Structure.UMBRELLA)


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


def _k2(answer: _Answer, vocabulary: Vocabulary, containing: Mapping[str, str], out: _Out, reading: _Reading) -> None:
    """K2. Each read of a slot whose value decides the rule reads it as the findings' inventory version reads it
    (``reading``): under gemini-inventory@3 every value it states or offers (_offered, [R:truth-T3]) - the examination
    link, the act's session, its kind, the session's kind, and the date relations K2's date arm compares, for two slots
    every combination - so a contradicted or overfilled slot fires the rule on each of its values instead of switching
    it off; under gemini-inventory@2 as that label was recorded (_RECORDED; DECISIONS D294 F2, D297 R2RX-1). The
    existence arm reads every id a fact names under both. What K2 demotes is unchanged: the act's session fact and the
    session's examination link, on every fact of an overfilled slot (ReadFact.keys)."""
    sessions = frozenset(answer.ids[Family.SESSION])
    events = frozenset(answer.ids[Family.EVENT])
    for event_id in answer.ids[Family.EVENT]:  # an event's session exists
        found = answer.one(Family.EVENT, event_id, A.SESSION)
        if found is not None and any(name not in sessions for name in _named(found)):
            out.reason(found.keys, Reason.SESSION_INCONSISTENT)
    for session_id in answer.ids[Family.SESSION]:  # a session's examination names it
        link = answer.one(Family.SESSION, session_id, A.EXAMINATION)
        for examination in reading.ids(link):
            theirs = answer.one(Family.EVENT, examination, A.SESSION) if examination in events else None
            if link is not None and theirs is not None and not reading.names(theirs, session_id):
                out.reason(link.keys, Reason.SESSION_INCONSISTENT)
    for event_id in answer.ids[Family.EVENT]:
        found = answer.one(Family.EVENT, event_id, A.SESSION)
        if found is None or not _act(answer, event_id):
            continue
        kinds = reading.members(answer.one(Family.EVENT, event_id, A.KIND), Kind)
        for session in reading.ids(found):
            if session not in sessions:
                continue
            families = reading.members(answer.one(Family.SESSION, session, A.KIND), SessionKind)
            if any(not vocabulary.family_admits(family, kind) for kind in kinds for family in families):
                out.reason(found.keys, Reason.SESSION_INCONSISTENT)  # an act's session kind admits its kind (D191)
        if _date_conflict(answer, event_id, found, sessions, events, containing, reading):
            out.reason(found.keys, Reason.SESSION_CONFLICT)  # the act's own other date: its session fact only


def _date_conflict(answer: _Answer, event_id: str, found: ReadFact, sessions: frozenset[str], events: frozenset[str],
                   containing: Mapping[str, str], reading: _Reading) -> bool:
    """K2's date arm: whether the act's OWN date relation and its session examination's claimed one - the examination's
    own, else the occasion of the section its anchor lies in (``containing``) - cannot both hold, read as ``reading``
    reads them: under gemini-inventory@3 (_OFFERED) every session the act's session fact states or offers, every
    examination that session's link states or offers, and every value each relation states or offers (_incompatible);
    under gemini-inventory@2 (_RECORDED, as that label was recorded) the act's supported session, that session's
    supported examination, and a contradicted relation stating no value (_incompatible_stated). The arm fires once
    whatever the number of conflicts (a finding is a reason on the act's session fact)."""
    own = answer.one(Family.EVENT, event_id, A.DATE_RELATION)
    if own is None:
        return False
    for session in reading.ids(found):
        if session not in sessions:
            continue
        for examination in reading.ids(answer.one(Family.SESSION, session, A.EXAMINATION)):
            if examination == event_id or examination not in events:
                continue
            theirs = answer.one(Family.EVENT, examination, A.DATE_RELATION)
            if theirs is None and examination in containing:
                theirs = answer.one(Family.SECTION, containing[examination], A.OCCASION)
            if theirs is not None and reading.incompatible(own, theirs):
                return True
    return False


def _supported_ids(found: ReadFact | None) -> tuple[str, ...]:
    """The id a SUPPORTED fact names, as a tuple of one or none (_id): gemini-inventory@2's read of an id slot whose
    value decides a K rule, as that label was recorded (_RECORDED)."""
    named = _id(found)
    return () if named is None else (named,)


def _named(found: ReadFact) -> tuple[str, ...]:
    """The ids a fact names, whatever its state: its value, each side's value when contradicted, and for the merged view
    of an overfilled slot every value a written fact writes (K2's existence arm fires on any of them, as it fires on a
    negated fact's value: the merged view is never weaker than one written fact read alone, 4.4; '' names nothing)."""
    fact = _fact(found)
    if found.written or fact.state is FactState.CONTRADICTED:
        return tuple(option.value for option in fact.options if option.value != '')
    return (fact.value,) if fact.value != '' else ()


def _names(found: ReadFact, object_id: str) -> bool:
    """Whether a fact establishes that it names ``object_id``, as K2's examination-link arm reads it - the one negative
    trigger, which demotes the link when the examination's session does NOT name the session: a supported fact of that
    value names it; a contradiction does not, for it offers another side on which the rule fires ([R:truth-T3]: each
    side of pass 1's own contradiction); nor does the merged view of an overfilled slot unless every written fact
    states that value (4.3.3 b, a denied value is never read as stated; 4.4, never stronger than one written fact read
    alone, a negated one included); a negated fact names nothing."""
    return set(found.asserted_values) == {object_id} and not found.negated_values


def _names_recorded(found: ReadFact, object_id: str) -> bool:
    """gemini-inventory@2's read of K2's examination-link arm, as that label was recorded (_RECORDED): the examination's
    session fact names ``object_id`` when it states it (supported) or offers it as a side of pass 1's own
    contradiction; a negated fact names nothing."""
    fact = _fact(found)
    if fact.state is FactState.SUPPORTED:
        return fact.value == object_id
    return fact.state is FactState.CONTRADICTED and any(option.value == object_id for option in fact.options)


def _denied(found: ReadFact) -> tuple[str, ...]:
    """The values a fact denies: a negated fact's value; the merged view's negated_values; none otherwise."""
    if found.written:
        return found.negated_values
    fact = _fact(found)
    return (fact.value,) if fact.state is FactState.NEGATED and fact.value != '' else ()


def _incompatible(first: ReadFact, second: ReadFact) -> bool:
    """Whether two date relations cannot both hold, read on every value each states or offers [R:truth-T3]: a value one
    states or offers differs from a value the other states or offers, or is a value the other denies. Two denials never
    conflict. (Before AMENDMENT-2 a contradicted relation stated no value, so it switched the arm off: that reading is
    gemini-inventory@2's, _incompatible_stated.)"""
    mine, theirs = first.asserted_values, second.asserted_values
    return (any(one != other for one in mine for other in theirs)
            or bool(set(mine) & set(_denied(second))) or bool(set(theirs) & set(_denied(first))))


def _incompatible_stated(first: ReadFact, second: ReadFact) -> bool:
    """gemini-inventory@2's comparison in K2's date arm, as that label was recorded (DECISIONS D294 F2): whether two
    date relations cannot both hold - both stated with different values, or one stated and the other denying that same
    value. A contradicted relation states no value, so the arm is off for it; two denials never conflict."""
    one, other = _fact(first), _fact(second)
    states = {one.state, other.state}
    if FactState.CONTRADICTED in states or one.value == '' or other.value == '':
        return False
    if one.state is FactState.SUPPORTED and other.state is FactState.SUPPORTED:
        return one.value != other.value
    return states == {FactState.SUPPORTED, FactState.NEGATED} and one.value == other.value


# --- K3: place against session; K4: anatomy against places ------------------------------------------------------------


def _k3(answer: _Answer, vocabulary: Vocabulary, out: _Out, reading: _Reading) -> None:
    """K3, on every session the act's session fact gives and every family that session's kind gives, as ``reading``
    reads them (gemini-inventory@3: each it states or offers, [R:truth-T3]; gemini-inventory@2: the supported one, as
    recorded): a supported place in a region the family cannot reach demotes the act's session fact."""
    sessions = frozenset(answer.ids[Family.SESSION])
    for event_id in answer.ids[Family.EVENT]:
        found = answer.one(Family.EVENT, event_id, A.SESSION)
        if found is None or not _act(answer, event_id):
            continue
        regions: list[Region] = []
        for _, fact in answer.facts(Family.EVENT, event_id, A.TARGET_PLACES):
            place = _member(Landmark, fact.value) if fact.state is FactState.SUPPORTED else None
            region = vocabulary.region(place) if place is not None else None
            if region is not None:
                regions.append(region)
        for session_id in reading.ids(found):
            if session_id not in sessions:
                continue
            families = reading.members(answer.one(Family.SESSION, session_id, A.KIND), SessionKind)
            reaches = [vocabulary.reach[family] for family in families if family in vocabulary.reach]
            if any(region not in reach for reach in reaches for region in regions):
                out.reason(found.keys, Reason.SESSION_UNREACHABLE)  # nothing is ever moved


def _k4(answer: _Answer, vocabulary: Vocabulary, out: _Out, reading: _Reading) -> None:
    places: list[tuple[FactKey, Place]] = []
    for session_id in answer.ids[Family.SESSION]:
        for attribute, enumeration in ((A.REACHED, Extent), (A.STATIONS, Station)):
            places += _supported_places(answer.facts(Family.SESSION, session_id, attribute), enumeration)
    for event_id in answer.ids[Family.EVENT]:
        if _act(answer, event_id):
            places += _supported_places(answer.facts(Family.EVENT, event_id, A.TARGET_PLACES), Landmark)
    # the type and the organ as ``reading`` reads them: under gemini-inventory@3 every value each states or offers
    # ([R:truth-T3]) - a contradicted or overfilled organ (several organs written for one entry) fires K4 on each, as a
    # contradicted type offering surgically_absent does; under gemini-inventory@2 the supported ones, as recorded
    for anatomy_id in answer.ids[Family.ANATOMY]:
        absent = answer.one(Family.ANATOMY, anatomy_id, A.TYPE)
        organ_found = answer.one(Family.ANATOMY, anatomy_id, A.ORGAN)
        if (absent is None or organ_found is None
                or AnatomyType.SURGICALLY_ABSENT not in reading.members(absent, AnatomyType)):
            continue
        for organ in reading.members(organ_found, Landmark):
            hits = [key for key, place in places if place.value == organ.value or vocabulary.contains(organ, place)]
            if hits:
                out.reason([*absent.keys, *organ_found.keys, *hits], Reason.ANATOMY_CONFLICT)


def _supported_places(found: Sequence[Found], enumeration: type[Enum]) -> list[tuple[FactKey, Place]]:
    return _places(found, enumeration, FactState.SUPPORTED)


# --- K5: person against performer; K6: instrument; K7: frame by role --------------------------------------------------


def _k5(answer: _Answer, out: _Out, reading: _Reading) -> None:
    """K5, on every combination of the performers, persons, the person's roles and documenting clinicians the facts
    give, as ``reading`` reads them (gemini-inventory@3: each they state or offer, [R:truth-T3]; gemini-inventory@2: the
    supported ones, as recorded): a conflict in any demotes the performer and the person."""
    roles = {person_id: reading.members(answer.one(Family.PERSON, person_id, A.ROLE), PersonRole)
             for person_id in answer.ids[Family.PERSON]}
    documenting = reading.ids(answer.one(Family.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN))
    for family in (Family.EVENT, Family.SECTION):
        for object_id in answer.ids[family]:
            performer_found = answer.one(family, object_id, A.PERFORMER)
            person_found = answer.one(family, object_id, A.PERFORMER_PERSON)
            if performer_found is None or person_found is None:
                continue
            if any((performer is Performer.DOCUMENTING_TEAM
                    and any(role not in _TEAM_ROLES for role in roles.get(person, ())))
                   or (performer in _OTHER_PERFORMERS
                       and (PersonRole.DOCUMENTING_CLINICIAN in roles.get(person, ()) or person in documenting))
                   for performer in reading.members(performer_found, Performer)
                   for person in reading.ids(person_found)):
                out.reason([*performer_found.keys, *person_found.keys], Reason.PERSON_CONFLICT)


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


def _l1(answer: _Answer, words: Words, containing: Mapping[str, str], out: _Out, reading: _Reading) -> date | None:
    """L1 at claim time. The date of service first: its value against the full dates in its words; the reference date
    is that value when its literal passes. Then each other date, each event's date, each event's effective date relation
    and each section's occasion. Returns the reference date. What an act's date slot gives its relation (``reading``'s
    dates) and the relations judged (``reading``'s members) are read as the findings' inventory version reads them: the
    paragraph below is gemini-inventory@3's reading; gemini-inventory@2 reads as recorded (_dates_supported: a supported
    date alone is read into a relation, and alone makes an event with no relation of its own judge its inherited
    occasion; a supported relation alone is judged; DECISIONS D301 RBRX-1).

    An event's effective date relation (1.5) is its own, read with the words of its own date; when pass 1 left its own
    slot silent and the event's date slot states or offers a date, it is the occasion of the section its anchor lies in
    (``containing``), read with the occasion's words and the event's own date's, and judged and stored under the
    event's own date_relation key (``_Answer.inherited``), never the section's (DECISIONS D193). The words read into a
    relation are those of every date the slot states or offers (``_dates_read``; AMENDMENT-2 4.3.3 [R:truth-T3]
    [R:truth-T9], which supersede D193's "a contradicted one states no date": L1 fires for each side of pass 1's own
    contradiction and each written value of an overfilled slot that is not negated), so a relation one of those dates
    contradicts is never left standing; a negated date is no evidence of when the act was done, and its words are never
    read (D193; the arbiter triage's repair 2b#5)."""
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
        # an overfilled date slot: L1 on each written date, each fact's own (its value, or each side), under its own
        # key (AMENDMENT-2 4.3.3 [R:truth-T9]: the written dates are the view's options)
        for item in (dated.written or (dated,)) if dated is not None else ():
            fact = _fact(item)
            sides = ([(option.value, option.sources) for option in fact.options]
                     if fact.state is FactState.CONTRADICTED else [(fact.value, fact.sources)])
            _transcription(item.key, sides, words, out)
        # the act's date relation is judged with the words of EVERY date the slot states or offers (gemini-inventory@3,
        # _dates_read: each side of pass 1's own contradiction, each written fact of an overfilled slot that is not
        # negated), so it fails whenever any one of those dates, read with it alone, would fail it ([R:truth-T3]
        # [R:truth-T9]); under gemini-inventory@2 with the words of a supported date alone, as recorded
        # (_dates_supported)
        dates_stated, date_sources = reading.dates(dated)
        own = answer.one(Family.EVENT, event_id, A.DATE_RELATION)
        if own is not None:
            _timing(own.keys, own, date_sources, words, reference, out, reading)
        elif dates_stated and event_id in containing:
            occasion = answer.one(Family.SECTION, containing[event_id], A.OCCASION)
            if occasion is not None:
                _timing((answer.inherited(event_id),), occasion, date_sources, words, reference, out, reading)
    for section_id in answer.ids[Family.SECTION]:
        occasion = answer.one(Family.SECTION, section_id, A.OCCASION)
        if occasion is not None:
            _timing(occasion.keys, occasion, (), words, reference, out, reading)
    return reference


def _dates_read(dated: ReadFact | None) -> tuple[bool, tuple[Source, ...]]:
    """What an act's date slot gives L1's judgment of the act's date relation (AMENDMENT-2 4.3.3 [R:truth-T3]
    [R:truth-T9]: L1 fires for each date the slot states or offers): whether the slot states or offers any date, and
    the sources of every date it states or offers, each once in written order - a supported fact's sources (as before
    AMENDMENT-2); a contradicted fact's own sources and each side's (pass 1's own contradiction); and for the merged
    view of an overfilled slot those of each written fact that is not negated, read the same way. _timing judges
    every literal they hold on its own, so the relation fails exactly when some date, read with it alone, would fail
    it: the merged view is never weaker than one of its written facts (4.4). A negated date is no evidence of when the
    act was done: its words are never read into a relation (D193)."""
    if dated is None:
        return False, ()
    stated = False
    sources: list[Source] = []
    for item in dated.written or (dated,):
        fact = _fact(item)
        if fact.state is FactState.NEGATED:
            continue
        stated = True
        sources += fact.sources
        if fact.state is FactState.CONTRADICTED:
            sources += [source for option in fact.options for source in option.sources]
    return stated, tuple(dict.fromkeys(sources))


def _dates_supported(dated: ReadFact | None) -> tuple[bool, tuple[Source, ...]]:
    """What an act's date slot gives L1's judgment of the act's date relation under gemini-inventory@2, as that label
    was recorded (_RECORDED; D193's clause, DECISIONS D301 RBRX-1): whether the slot holds a SUPPORTED date, and that
    fact's sources as written. Only a supported date is read into a relation: a contradicted one (pass 1's own
    contradiction) states no date, and a negated one is no evidence of when the act was done, so neither one's words are
    read into the relation and neither makes an event with no relation of its own judge the occasion it inherits. (No
    answer read under gemini-events@2 holds the merged view of an overfilled slot: module docstring, Versions.)"""
    if dated is None or _fact(dated).state is not FactState.SUPPORTED:
        return False, ()
    return True, tuple(_fact(dated).sources)


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


def _timing(keys: Sequence[FactKey], found: ReadFact, date_sources: Sequence[Source], words: Words,
            reference: date | None, out: _Out, reading: _Reading) -> None:
    """L1 on a timing fact (an event's effective date relation, with the words of every date its own date slot gives,
    ``reading``'s dates; a section's occasion), its findings and literals at ``keys`` (every fact of an overfilled
    slot, or an event's inherited key):
    every literal read is stored; each relation ``reading`` reads the fact to state - under gemini-inventory@3 each it
    states or offers ([R:truth-T3]: a supported one, each side of pass 1's own contradiction, each stated value of an
    overfilled slot), under gemini-inventory@2 a supported one alone, as recorded (D301 RBRX-1) - is judged against the
    claim-time reference date, and a literal that meets no document date stops nothing."""
    literals = _read([*_fact(found).sources, *date_sources], words, day_only=False)
    for key in keys:
        out.literals[key] = _stored(literals)
    if reference is None:
        return
    if any(not all(_holds(relation, literal.value, literal.precision, reference) for literal in literals)
           for relation in reading.members(found, DateRelation)):
        for key in keys:
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


# --- the reading of each inventory version (DECISIONS D294 F2, D297 R2RX-1, D301 RBRX-1) ---------------------------


class _Members(Protocol):
    """How a K rule or L1 reads the members a slot gives it (_offered, or _supported)."""

    def __call__(self, found: ReadFact | None, enumeration: type[_E], /) -> tuple[_E, ...]: ...


@dataclass(frozen=True, slots=True)
class _Reading:
    """How every check AMENDMENT-2 4.3.3 widened reads a slot whose value decides it, for the inventory version the
    findings are made for (``_reading``; module docstring, Versions): ``members`` and ``ids`` give the members and ids a
    slot gives a K rule (``members`` also the relations L1 judges on a timing fact), ``names`` whether an examination's
    session fact names a session (K2's examination-link arm, the one negative trigger), ``incompatible`` whether two
    date relations cannot both hold (K2's date arm), and ``dates`` what an act's date slot gives L1's judgment of its
    date relation - whether it gives a date (the condition on which an act with no relation of its own judges the
    occasion it inherits) and the sources of every date read into the relation. _OFFERED is AMENDMENT-2 4.3.3's
    stated-or-offered reading; _RECORDED is gemini-inventory@2's, as that label was recorded (D202)."""
    members: _Members
    ids: Callable[[ReadFact | None], tuple[str, ...]]
    names: Callable[[ReadFact, str], bool]
    incompatible: Callable[[ReadFact, ReadFact], bool]
    dates: Callable[[ReadFact | None], tuple[bool, tuple[Source, ...]]]


_OFFERED = _Reading(members=_offered, ids=_offered_ids, names=_names, incompatible=_incompatible, dates=_dates_read)
_RECORDED = _Reading(members=_supported, ids=_supported_ids, names=_names_recorded, incompatible=_incompatible_stated,
                     dates=_dates_supported)


def _reading(inventory_version: str) -> _Reading:
    """The reading every K rule and L1 apply for findings made for ``inventory_version`` (DECISIONS D294 F2, D297
    R2RX-1, D301 RBRX-1): gemini-inventory@2 - whose first recording (D1) was made before AMENDMENT-2 - keeps the
    reading it was recorded with (_RECORDED), since a label's rule never changes after its first recording (D202);
    every other label reads AMENDMENT-2 4.3.3's stated-or-offered reading (_OFFERED), which only demotes more
    (fail-closed)."""
    return _RECORDED if inventory_version == interpretation.INVENTORY_VERSION_V2 else _OFFERED


# --- Q1: qualifiers -----------------------------------------------------------------------------------------------------


def _q1(answer: _Answer, out: _Out) -> None:
    for item in answer.read.facts:
        if isinstance(item.fact, Fact):
            found = {_QUALIFIED[qualifier] for qualifier in item.fact.qualifiers if qualifier in _QUALIFIED}
            if found:
                out.qualified[item.key] = found
