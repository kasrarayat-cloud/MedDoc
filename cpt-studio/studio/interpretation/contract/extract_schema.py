"""The shape pass 1 answers in (gemini-events@2; docs/gemini-migration/FINAL-V2.md 1.3-1.8 and 2.1, step 1b of 8.1): the
enumerations it uses with their one-line definitions, LOCAL_SCHEMA_2 with ``doubts`` and ``device_reached``,
RESPONSE_SCHEMA_2 derived from it mechanically, and BOUNDS_2.

**LOCAL_SCHEMA_2 is the source**, written in v1's LOCAL form (1.4): every object requires every property it declares,
in the design's order, and forbids any other; there is no nullable union; the types are object, array and string (the
answer has no integer). The design's shorthand expands as 1.3 defines it:
- SOURCE ``{units, words, link}``: the cited unit ids, the exact words inside them ('' for all of them), the link.
- FACT(E) ``{state, value, qualifiers, sources, options}``: ``value`` is a value of E, or '' (the value of a
  contradicted fact, 1.3); each option's ``value`` is a value of E, never ''. For an id or a date, both are plain
  strings: an id is resolved by the reader (3.1 I4) and a date's shape is S1's.
- SLOT(E) is a list of FACT(E) holding at most one (1.8; [] is a silent attribute); FACTS(E) is a list of FACT(E).
RESPONSE_SCHEMA_2, what generationConfig.responseSchema carries, is ``jsonschema.gemini_schema(LOCAL_SCHEMA_2)``: one
generator, copied from v1's schema.py by step 0b (contract/jsonschema.py), so the two cannot drift and v2 runs no v1
code. Gemini's form is a hint to the model and never trusted: contract/extract_read.py validates every answer against
LOCAL_SCHEMA_2.

**The tables the reader and settle read**, each over enumeration members only (no word, phrase or marker; 5.7
NoWordLists):
- ATTRIBUTES: every attribute an object of each family has, in the answer's order, with its arity (a FACT, a SLOT, FACTS,
  a plain LIST, or OTHER: the date of service's own shape, a restatement's role, an act's entry), its values (an
  enumeration, an id of a family, or a date) and the bound of 1.8 its list takes.
- DOUBT_ATTRIBUTES: the attributes each DOUBT_ABOUT value names on each family (1.4 DOUBT_ABOUT, 1.6's rows; every row
  confirmed by DECISIONS D200). S2 reads it to tell whether a named object carries the attribute; settle (step 3a)
  reads it to apply a doubt (3.3 rows 1-2).
- BOUNDS_2: 1.8's numbers, keyed by Bound.
- Family.letter: the letter every id of a family opens with (1.4; DECISIONS D185), which the reader's ids stage checks.

**DEFINITIONS** gives each value list the schema uses its one-line definition (1.4: "Each value list carries a one-line
definition in the instruction, pinned with the schema"). It is a pinned OUTPUT table (5.7 NoWordLists names "the
enumeration definitions of extract_schema.py"): it describes meanings and never surface forms (2.3), step 2a renders it
into INSTRUCTIONS_2, and no code compares it with document text. definitions_document() is its canonical form. It has no
pin of its own: 2a renders it verbatim, so INSTRUCTIONS_SHA256_V2 covers it (DECISIONS D202).

Everything here belongs to INTERPRETATION_VERSION_V2 (gemini-events@2): a changed byte of LOCAL_SCHEMA_2,
RESPONSE_SCHEMA_2 or DEFINITIONS changes what is asked. Until the first recording under gemini-events@2 (D1) it needs
only recomputed pins; after it, gemini-events@3 (2.5; DECISIONS D202). BOUNDS_2 is read, never sent.
DOUBT_ATTRIBUTES and ATTRIBUTES' values feed checks and the doubt mapping, which INVENTORY_VERSION_V2 names (1.1): a
change of them alone re-settles stored answers with no send.

Pure: imports only the standard library and the contract's types and jsonschema; touches no document text.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import Any

from studio.interpretation.contract import jsonschema
from studio.interpretation.contract.types import (AccessOutcome, AnastomosisSubtype, AnatomyType, Approach, Attribute,
                                                  Breadth, Cause, Completion, DateRelation, DateRole, DateState, Device,
                                                  DoubtAbout, DoubtBasis, Duct, EmBasis, EncounterRelation, Extent,
                                                  FactState, Kind, Landmark, Link, Material, Multiplicity, OtherClass,
                                                  Owner, PartRelation, Performer, PersonRole, Purpose, Qualifier,
                                                  RestatementRole, Route, SectionRole, Separate, SessionKind, Station,
                                                  Status, Structure, Tract)

# --- the object families, arities and bounds -------------------------------------------------------------------------


@unique
class Family(Enum):
    """The families of objects in pass 1's answer (1.4 ANSWER). Each value is the answer's own key for the family: the
    encounter is one object, every other family a list of objects with an ``id``. Doubts are answer-level (1.3) and are
    not a family: they name objects of the families."""
    ENCOUNTER = 'encounter'
    PERSON = 'people'
    SECTION = 'sections'
    SESSION = 'sessions'
    ANATOMY = 'anatomy'
    LESION = 'lesions'
    EVENT = 'events'

    @property
    def letter(self) -> str:
        """The letter every id of this family opens with (FINAL-V2 1.4; DECISIONS D185): P people, N sections, X
        sessions, Y anatomy entries, L lesions, E events; '' for the encounter, which has no id. An id format (as
        engine/types.IdFamily's letters), compared with no document text."""
        return {Family.ENCOUNTER: '', Family.PERSON: 'P', Family.SECTION: 'N', Family.SESSION: 'X', Family.ANATOMY: 'Y',
                Family.LESION: 'L', Family.EVENT: 'E'}[self]


@unique
class Arity(Enum):
    """How an attribute is given in the answer (1.3). FACT: exactly one FACT, never silent. SLOT: a list holding no FACT
    (silent: unknown) or one. FACTS: a list of FACTs (multi-valued: places, reached points, stations, joins,
    distinct_from, same_as). LIST: a plain list of values, not facts (a statement's scope lists). OTHER: not a FACT of
    the answer - the date of service (its own shape, DATE_STATES), a restatement's role (one value per restatement) and
    an act's entry (the owner of the section its anchor lies in, 1.5)."""
    FACT = 'fact'
    SLOT = 'slot'
    FACTS = 'facts'
    LIST = 'list'
    OTHER = 'other'


@unique
class Bound(Enum):
    """What one number of BOUNDS_2 bounds (1.8). A whole answer outside one of them is refused, named by count, never
    truncated - except SOURCE_UNITS, an ITEM-level bound: a source or an anchor over it fails its own check
    (source_too_long, 3.1 I3) and the answer is read [R:CO-5]. A list 1.8 gives no number of its own takes none: a
    section's closing signatures (1.4 SECTION.end) and the units of a restatement or a doubt refuse an answer only
    through CITED_UNITS."""
    EVENTS = 'events'
    SECTIONS = 'sections'
    SESSIONS = 'sessions'
    PEOPLE = 'people'
    ANATOMY = 'anatomy'
    LESIONS = 'lesions'
    OTHER_DATES = 'other_dates'
    RESTATEMENTS = 'restatements'  # per event
    DOUBTS = 'doubts'
    DOUBT_OBJECTS = 'doubt_objects'  # per doubt
    DOUBT_READINGS = 'doubt_readings'  # per doubt
    SLOT = 'slot'  # FACTs in one slot
    PLACES = 'places'  # per list: places (a lesion's and an act's), reached, device_reached, joins
    STATIONS = 'stations'  # per list
    LESION_LINKS = 'lesion_links'  # per list: distinct_from, same_as
    SOURCES = 'sources'  # per list of sources: a fact's (the date of service's too) and an option's (1.8 "per fact")
    OPTIONS = 'options'  # per fact
    SCOPE_LIST = 'scope_list'  # per list: targets, segment, covers, excepts
    WORDS_CHARS = 'words_chars'  # characters of one words value (a source's words, an anchor's kind or status words)
    CITED_UNITS = 'cited_units'  # unit ids cited in the whole answer, every list of unit ids counted
    SOURCE_UNITS = 'source_units'  # units of one source or anchor: ITEM-level


# 1.8, number for number. A whole answer outside any but SOURCE_UNITS is refused (contract/extract_read.py).
BOUNDS_2: Mapping[Bound, int] = MappingProxyType({
    Bound.EVENTS: 200, Bound.SECTIONS: 48, Bound.SESSIONS: 16, Bound.PEOPLE: 16, Bound.ANATOMY: 16, Bound.LESIONS: 64,
    Bound.OTHER_DATES: 16, Bound.RESTATEMENTS: 16, Bound.DOUBTS: 64, Bound.DOUBT_OBJECTS: 16, Bound.DOUBT_READINGS: 4,
    Bound.SLOT: 1, Bound.PLACES: 8, Bound.STATIONS: 7, Bound.LESION_LINKS: 16, Bound.SOURCES: 8, Bound.OPTIONS: 4,
    Bound.SCOPE_LIST: 32, Bound.WORDS_CHARS: 600, Bound.CITED_UNITS: 4000, Bound.SOURCE_UNITS: 12,
})


# --- the attributes of each family -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Field:
    """One attribute of an object family (1.4, 1.6).

    attribute: the Attribute (its value is the answer's path to it, ``<field>.<field>`` for a nested one). arity: how
    the answer gives it (Arity). values: the enumeration of its values, None for an id or a date. refers_to: the family
    whose id it holds, None for an enumeration or a date; an attribute with neither is a date (ISO at its precision).
    bound: the Bound its list takes (SLOT for a slot, the 1.8 bound of a FACTS or LIST attribute), None otherwise."""
    attribute: Attribute
    arity: Arity
    values: type[Enum] | None = None
    refers_to: Family | None = None
    bound: Bound | None = None

    @property
    def is_date(self) -> bool:
        """Whether its values are dates (ISO at their precision)."""
        return self.values is None and self.refers_to is None

    @property
    def path(self) -> tuple[str, ...]:
        """Its path in the object, from its Attribute's value (target.places: ('target', 'places'))."""
        return tuple(self.attribute.value.split('.'))


def _fact(attribute: Attribute, values: type[Enum] | None = None, refers_to: Family | None = None) -> Field:
    return Field(attribute, Arity.FACT, values, refers_to)


def _slot(attribute: Attribute, values: type[Enum] | None = None, refers_to: Family | None = None) -> Field:
    return Field(attribute, Arity.SLOT, values, refers_to, Bound.SLOT)


def _facts(attribute: Attribute, bound: Bound, values: type[Enum] | None = None,
           refers_to: Family | None = None) -> Field:
    return Field(attribute, Arity.FACTS, values, refers_to, bound)


def _list(attribute: Attribute, values: type[Enum] | None = None, refers_to: Family | None = None) -> Field:
    return Field(attribute, Arity.LIST, values, refers_to, Bound.SCOPE_LIST)


def _other(attribute: Attribute, values: type[Enum] | None = None) -> Field:
    return Field(attribute, Arity.OTHER, values)


A = Attribute
# Every attribute of each family, in the answer's order (1.4), ending with what the answer does not give as a FACT.
ATTRIBUTES: Mapping[Family, tuple[Field, ...]] = MappingProxyType({
    Family.ENCOUNTER: (
        _other(A.DATE_OF_SERVICE),  # {state: DATE_STATES, value, sources, options}: a day, or ''
        _fact(A.OTHER_DATES_ROLE, DateRole),  # one FACT per other date: encounter.other_dates[i].role
        _slot(A.DOCUMENTING_CLINICIAN, refers_to=Family.PERSON),
    ),
    Family.PERSON: (
        _fact(A.ROLE, PersonRole),
    ),
    Family.SECTION: (
        _fact(A.OWNER, Owner),
        _slot(A.ROLE, SectionRole),
        _slot(A.OCCASION, DateRelation),
        _slot(A.PERFORMER, Performer),
        _slot(A.PERFORMER_PERSON, refers_to=Family.PERSON),
    ),
    Family.SESSION: (
        _slot(A.EXAMINATION, refers_to=Family.EVENT),
        _fact(A.KIND, SessionKind),
        _slot(A.ENCOUNTER, EncounterRelation),
        _slot(A.TRACT, Tract),
        _slot(A.APPROACH, Approach),
        _slot(A.THROUGH, refers_to=Family.ANATOMY),
        _facts(A.REACHED, Bound.PLACES, Extent),
        _facts(A.DEVICE_REACHED, Bound.PLACES, Extent),  # [R:CO-8]
        _slot(A.REACHED_ANATOMY, refers_to=Family.ANATOMY),
        _slot(A.COMPLETION, Completion),
        _facts(A.STATIONS, Bound.STATIONS, Station),
        _slot(A.PART_OF_SESSION, refers_to=Family.SESSION),
    ),
    Family.ANATOMY: (
        _fact(A.TYPE, AnatomyType),
        _slot(A.ORGAN, Landmark),
        _slot(A.SUBTYPE, AnastomosisSubtype),
        _facts(A.JOINS, Bound.PLACES, Landmark),
    ),
    Family.LESION: (
        _slot(A.MULTIPLICITY, Multiplicity),
        _facts(A.PLACES, Bound.PLACES, Landmark),
        _facts(A.DISTINCT_FROM, Bound.LESION_LINKS, refers_to=Family.LESION),
        _facts(A.SAME_AS, Bound.LESION_LINKS, refers_to=Family.LESION),
    ),
    Family.EVENT: (
        _other(A.RESTATEMENTS_ROLE, RestatementRole),  # events[i].restatements[j].role, a plain value
        _fact(A.KIND, Kind),
        _slot(A.OTHER_CLASS, OtherClass),
        _fact(A.STATUS, Status),
        _slot(A.SESSION, refers_to=Family.SESSION),
        _slot(A.DATE_RELATION, DateRelation),
        _slot(A.DATE),
        _slot(A.PERFORMER, Performer),
        _slot(A.PERFORMER_PERSON, refers_to=Family.PERSON),
        _slot(A.TARGET_LESION, refers_to=Family.LESION),
        _slot(A.TARGET_STRUCTURE, Structure),
        _facts(A.TARGET_PLACES, Bound.PLACES, Landmark),
        _slot(A.TARGET_ANATOMY, refers_to=Family.ANATOMY),
        _slot(A.TARGET_DUCT, Duct),
        _slot(A.TECHNIQUE_DEVICE, Device),
        _slot(A.TECHNIQUE_ROUTE, Route),
        _slot(A.PURPOSE, Purpose),
        _slot(A.CAUSE, Cause),
        _slot(A.CAUSE_EVENT, refers_to=Family.EVENT),
        _slot(A.PART_OF, refers_to=Family.EVENT),
        _slot(A.PART_RELATION, PartRelation),
        _slot(A.YIELD, Material),
        _slot(A.ACCESS_OUTCOME, AccessOutcome),
        _slot(A.SCOPE_BREADTH, Breadth),
        _list(A.SCOPE_TARGETS, refers_to=Family.LESION),
        _list(A.SCOPE_SEGMENT, Landmark),
        _list(A.SCOPE_COVERS, refers_to=Family.EVENT),
        _list(A.SCOPE_EXCEPTS, refers_to=Family.EVENT),
        _slot(A.VISIT_BASIS, EmBasis),
        _slot(A.VISIT_SEPARATELY_IDENTIFIABLE, Separate),
        _other(A.ENTRY, Owner),  # the owner of the section the anchor lies in (1.5); claimed per act, never reported
    ),
})
del A


def attributes(family: Family) -> tuple[Attribute, ...]:
    """Every attribute an object of ``family`` has, in ATTRIBUTES' order."""
    return tuple(field.attribute for field in ATTRIBUTES[family])


def field(family: Family, attribute: Attribute) -> Field:
    """The Field of ``attribute`` on ``family``. KeyError when the family has no such attribute."""
    for item in ATTRIBUTES[family]:
        if item.attribute is attribute:
            return item
    raise KeyError(f'{family.name} has no attribute {attribute.name}.')


def _named() -> dict[DoubtAbout, Mapping[Family, tuple[Attribute, ...]]]:
    """DOUBT_ATTRIBUTES' rows: the attributes each DOUBT_ABOUT value names, by family, from 1.4's list and 1.6's rows (the
    directive's attributes, located). ``whole`` names every attribute of every family."""
    A, F = Attribute, Family
    rows: dict[DoubtAbout, dict[Family, tuple[Attribute, ...]]] = {
        DoubtAbout.STATUS: {F.EVENT: (A.STATUS,)},
        DoubtAbout.KIND: {F.EVENT: (A.KIND, A.OTHER_CLASS), F.SESSION: (A.KIND,)},
        DoubtAbout.SESSION: {F.EVENT: (A.SESSION,)},
        DoubtAbout.DATE_RELATION: {F.EVENT: (A.DATE_RELATION, A.DATE), F.SECTION: (A.OCCASION,),
                                   F.SESSION: (A.ENCOUNTER,)},
        DoubtAbout.PERFORMER: {F.EVENT: (A.PERFORMER, A.PERFORMER_PERSON),
                               F.SECTION: (A.PERFORMER, A.PERFORMER_PERSON)},
        DoubtAbout.ENTRY: {F.EVENT: (A.ENTRY,), F.SECTION: (A.OWNER,)},
        DoubtAbout.TARGET: {F.EVENT: (A.TARGET_LESION, A.TARGET_STRUCTURE, A.TARGET_PLACES, A.TARGET_ANATOMY,
                                      A.TARGET_DUCT),
                            F.LESION: (A.PLACES,)},
        DoubtAbout.TECHNIQUE: {F.EVENT: (A.TECHNIQUE_DEVICE, A.TECHNIQUE_ROUTE), F.SESSION: (A.APPROACH, A.THROUGH)},
        DoubtAbout.PURPOSE: {F.EVENT: (A.PURPOSE,)},
        DoubtAbout.CAUSE: {F.EVENT: (A.CAUSE, A.CAUSE_EVENT)},
        DoubtAbout.PART_OF: {F.EVENT: (A.PART_OF, A.PART_RELATION), F.SESSION: (A.PART_OF_SESSION,)},
        DoubtAbout.YIELD: {F.EVENT: (A.YIELD,)},
        DoubtAbout.ACCESS_OUTCOME: {F.EVENT: (A.ACCESS_OUTCOME,)},
        DoubtAbout.EXTENT: {F.SESSION: (A.REACHED, A.DEVICE_REACHED, A.REACHED_ANATOMY, A.COMPLETION)},
        DoubtAbout.STATIONS: {F.SESSION: (A.STATIONS,)},
        DoubtAbout.COMPLETION: {F.SESSION: (A.COMPLETION,)},
        DoubtAbout.APPROACH: {F.SESSION: (A.APPROACH, A.THROUGH)},
        DoubtAbout.ANATOMY: {F.ANATOMY: (A.TYPE, A.ORGAN, A.SUBTYPE, A.JOINS)},
        DoubtAbout.IDENTITY: {F.LESION: (A.MULTIPLICITY, A.SAME_AS, A.DISTINCT_FROM)},
        DoubtAbout.DATE_OF_SERVICE: {F.ENCOUNTER: (A.DATE_OF_SERVICE,)},
        DoubtAbout.VISIT: {F.EVENT: (A.VISIT_BASIS, A.VISIT_SEPARATELY_IDENTIFIABLE)},
        DoubtAbout.WHOLE: {family: attributes(family) for family in F},
    }
    return {about: MappingProxyType(rows[about]) for about in DoubtAbout}


# What each DOUBT_ABOUT value names on each family, every row confirmed by DECISIONS D200 (a change to a row is
# gemini-inventory@3 once a v2 row is stored). A family missing from a row does not carry that attribute, so a doubt
# naming one of its objects is malformed (S2) and applies to every claimed fact of its objects (fail-closed, 3.1 S2).
DOUBT_ATTRIBUTES: Mapping[DoubtAbout, Mapping[Family, tuple[Attribute, ...]]] = MappingProxyType(_named())


# --- the value lists and their definitions (1.4: one line each, in the instruction, pinned with the schema) -----------

# Every enumeration LOCAL_SCHEMA_2 uses, in the order the schema first uses it.
ENUMERATIONS: tuple[type[Enum], ...] = (
    DateState, Link, FactState, DateRole, Qualifier, PersonRole, Owner, SectionRole, DateRelation, Performer,
    SessionKind, EncounterRelation, Tract, Approach, Extent, Completion, Station, AnatomyType, Landmark,
    AnastomosisSubtype, Multiplicity, RestatementRole, Kind, OtherClass, Status, Structure, Duct, Device, Route, Purpose,
    Cause, PartRelation, Material, AccessOutcome, Breadth, EmBasis, Separate, DoubtAbout, DoubtBasis,
)

# The pinned OUTPUT table of 5.7 NoWordLists: one line per value list, describing meanings, never surface forms (2.3).
# Step 2a renders it into INSTRUCTIONS_2; nothing compares it with document text.
DEFINITIONS: Mapping[type[Enum], str] = MappingProxyType({
    DateState: 'The date of service: stated (the document gives one date for this encounter), several (it gives more '
               'than one; each is listed as an option with its own sources, and the value is left empty) or not_stated '
               '(it gives none).',
    Link: "What a cited unit is for the object: statement (the object's own statement: an act's anchor, a session's "
          "examination, a lesion's description), section (the start or the closing signature of the part of the "
          'document that contains the object), frame (a sentence inside that part that frames what the part tells), '
          "placing (a sentence anywhere in the document, other than the object's own statement, that says when or by "
          'whom this act, or the acts of a part, were done), document_frame (a unit of the opening part of the '
          'document that is a source of an encounter fact: its title, its date-of-service line or its documenting '
          "clinician's line), antecedent (the earlier statement an anaphoric frame refers to) or other_statement "
          '(another statement about the same object).',
    FactState: 'The state of a fact: supported (the document states this value for this object), negated (the document '
               'explicitly states that this value does not hold for this object) or contradicted (the document states '
               'incompatible values of this attribute for this one object; each is given as an option with its own '
               'sources, and the value is left empty).',
    DateRole: 'The role of another date the document states: this_encounter (a date of this encounter), birth (a date '
              'of birth), other_occurrence (the date of another visit or procedure), other_document (the date of '
              'another report or result), report_time (when this document was written or signed) or unclear (a role '
              'the document does not make clear).',
    Qualifier: 'What a statement says about itself: hedged (it is hedged), conditional (it holds only under a condition '
               'it states), reported (it is reported second-hand), partial (it states only part of the fact), '
               'named_only (the fact is only named, in a title or a heading), restatement_only (the fact is only '
               'restated from elsewhere), reference_only (the fact is only referred to) or approximate (a measure is '
               'stated as approximate).',
    PersonRole: "A named person's role: documenting_clinician (the clinician who documents this encounter), trainee, "
                'assistant, nurse, anesthesia, pathologist, radiologist, referring (the clinician who referred the '
                'patient) or other.',
    Owner: 'Whose entry a part of the document is: documenting_clinician (the clinician who documents this encounter), '
           'nursing, anesthesia, pathology, radiology, other_clinician (another clinician), outside_record (a record '
           'from another clinician or facility, copied in), patient_reported (what the patient reports) or '
           'administrative.',
    SectionRole: 'What a part of the document is: header, indication, history, medications, sedation, procedure, '
                 'findings, impression, complications, specimens, plan, pathology_result, nursing_note, '
                 'anesthesia_record, addendum, signature or other.',
    DateRelation: 'When an act was done, relative to the date of service: on_date_of_service (on the date of service, '
                  'at this encounter or at a separate one the same day), earlier_date (on an earlier date) or '
                  'later_date (on a later date).',
    Performer: 'Who did an act: documenting_team (the clinician who documents this encounter, or the team working with '
               'that clinician), other_clinician (another clinician) or other_facility (another facility).',
    SessionKind: 'What a session is: office_em (an office or outpatient evaluation and management visit), egd (an upper '
                 'endoscopy), enteroscopy (a small-bowel enteroscopy), colonoscopy, flex_sig (a flexible '
                 'sigmoidoscopy), eus (an endoscopic ultrasound), ercp (an endoscopic retrograde '
                 'cholangiopancreatography), capsule (a capsule endoscopy), motility (a motility or manometry study), '
                 'reflux (a pH or impedance monitoring study), anorectal (anorectal testing), feeding_tube (a '
                 'feeding-tube procedure), sedation (moderate sedation by the clinician who performs the procedure), '
                 'em_other (an evaluation and management service other than an office or outpatient visit), other_gi '
                 '(another gastrointestinal service) or not_gi (a service outside gastroenterology).',
    EncounterRelation: "Whether a session is part of this document's encounter: this_encounter or separate_encounter (a "
                       'separate encounter, which may be on the same date).',
    Tract: 'The part of the digestive tract a session examined: upper, lower or pancreatobiliary.',
    Approach: 'How the endoscope entered: oral (through the mouth), transnasal (through the nose), transanal (through '
              'the anus), through_stoma (through a stoma), through_pouch (through a pouch), through_gastrostomy '
              '(through a gastrostomy) or percutaneous (through the skin).',
    Extent: 'A point an examination reached: a value of the places, or stated_depth (an extent stated as a depth or a '
            'distance, without a landmark).',
    Completion: 'Whether an examination reached the extent it set out to reach, as the document states it: complete (it '
                'reached that extent), incomplete (it stopped short of it) or terminated (it stopped early, for a '
                'reason the document states).',
    Station: 'A part of the tract an examination examined (supported) or did not examine (negated): esophagus, stomach, '
             'duodenum, jejunum, ileum, colon or rectum.',
    AnatomyType: 'An alteration or absence of anatomy: surgically_absent (an organ or part removed by surgery), '
                 'anastomosis (a surgical joining of two organs), stoma (a surgical opening), ileal_pouch (a pouch made '
                 'from the ileum), gastric_pouch (a pouch made from the stomach), roux_limb (a Roux limb), bypass (a '
                 'surgical bypass) or other_alteration (another surgical alteration).',
    Landmark: 'A place, by its anatomical name, in the digestive tract or in an organ beside it; anastomosis, stoma and '
              'pouch name a surgically made place, and other a place no other value names.',
    AnastomosisSubtype: 'Which organs an anastomosis joins: ileocolic, colocolic, colorectal, coloanal, ileorectal, '
                        'ileoanal, gastrojejunal, gastroduodenal, esophagojejunal, esophagogastric, hepaticojejunal, '
                        'choledochoduodenal, pancreaticojejunal or other.',
    Multiplicity: 'How many lesions one lesion entry is: single (one lesion) or group (several lesions the document '
                  'describes only together).',
    RestatementRole: 'How another statement of an act relates to it: restates (it tells the act in full, in its own '
                     'words, not only as a summary, a title or a reference), summarizes (it only summarizes the act), '
                     'title (it only names the act in a title or a heading), names_only (it only names the act) or '
                     'refers_back (it only refers to where the act is told).',
    Kind: 'What an act is: examination (the examination itself), em_visit (an evaluation and management visit), '
          'em_prolonged (prolonged visit time, stated as such), biopsy (tissue sampling with forceps), hot_biopsy '
          '(removal or sampling with hot forceps), snare (removal with a snare), emr (endoscopic mucosal resection), '
          'esd (endoscopic submucosal dissection), removal (a removal whose method the document does not state, or a '
          'statement about removal by any method), ablation (destruction of tissue by an ablative method), '
          'bleeding_control (treatment of bleeding by any method), clip (placement of a clip), tattoo (an injection '
          'that marks a site), injection (any other injection into tissue), band_ligation, dilation (dilation of a '
          'narrowing), stent (placement of a stent), stent_removal (removal of a stent), stent_exchange (an exchange '
          'of a stent), foreign_body (removal of a foreign body or a food bolus), decompression, tube_placement (a tube '
          'placed during an examination, other than a gastrostomy), tube_replacement (a feeding tube replaced or '
          'exchanged), peg (a percutaneous endoscopic gastrostomy placed), myotomy, fundoplication, fna (fine-needle '
          'aspiration or biopsy), drainage, cannulation (cannulation of a duct), sphincterotomy, stone_extraction, '
          'lithotripsy, cholangioscopy, pressure_measurement, capsule_study, manometry, ph_monitoring, rectal_sensation '
          '(rectal sensation, tone or compliance testing), balloon_expulsion (a balloon expulsion test), '
          'moderate_sedation, intervention (only for a statement about interventions of every kind) or other (any '
          'other act).',
    OtherClass: 'The class of an act of kind other: procedure, test, order, imaging, laboratory, counseling, evaluation, '
                'medication or other.',
    Status: "An act's status: performed (done), attempted_not_completed (begun and not completed) or planned (planned, "
            'not yet done); an act the document says was not done is status performed, negated.',
    Structure: 'What an act was done to: lesion, stricture, ulcer, bleeding_site, vessel, varix, stone, stent, duct, '
               'pancreatic_fluid_collection, gallbladder, liver, lymph_node, mass, wall, lumen, foreign_body, mucosa, '
               'anastomosis or other.',
    Duct: 'The duct an act was done in: biliary, pancreatic or cystic.',
    Device: 'The device the document names for an act: endoscope, cold_snare, hot_snare, snare (a snare the document '
            'does not call cold or hot), cold_forceps, hot_forceps, forceps (forceps the document does not call '
            'cold or hot), needle, injection, balloon, wire_bougie, bougie, clip, band, argon_plasma, radiofrequency, '
            'cryotherapy, thermal_probe, electrocautery, stent, basket, extraction_balloon, sphincterotome, '
            'lithotripter, cholangioscope, capsule, catheter, manual or other.',
    Route: "How an act's agent reached the tissue: submucosal (into the submucosa), eus_transmural (across the wall, "
           'guided by endoscopic ultrasound), eus_fine_needle (by a fine needle, guided by endoscopic ultrasound), '
           'intraluminal (within the lumen), intraductal (within a duct), percutaneous (through the skin) or topical '
           '(applied to the surface).',
    Purpose: 'Why an act was done: diagnostic, removal, lift_for_resection (to lift tissue for a resection), marking (to '
             'mark a site), hemostasis (to treat bleeding present at this encounter), prophylaxis (to prevent), '
             'treatment, access (to gain access), sampling, drainage, decompression or other.',
    Cause: 'What caused the bleeding a hemostasis act treated: act_of_this_session (an act of this session, named in '
           'cause_event), pre_existing_lesion (a lesion present before this session), spontaneous (spontaneous '
           'bleeding), earlier_procedure (an earlier procedure) or other.',
    PartRelation: 'How an act is part of another act: step_of (a step of it), lift_for (a lift done to enable it), '
                  'access_for (access gained to enable it), adjunct_of (an adjunct done with it) or component_of (one '
                  'part of a composite act told as its parts).',
    Material: 'What an extraction act retrieved: stones, stone_fragments, sludge, debris, stent, foreign_body, tissue or '
              'anything (any material; anything negated means the act retrieved nothing).',
    AccessOutcome: 'The outcome of a cannulation act: achieved, failed or achieved_after_failed_attempts.',
    Breadth: 'What a statement about acts covers: single_target (one target), listed_targets (the targets it lists), '
             'all_of_kind (every act of its kind in its session), exceptive (every act of its kind except the acts '
             'already reported, which it lists in excepts) or segment (every act of its kind in a stretch of the tract, '
             'given by its first and last place).',
    EmBasis: 'The basis of a visit, as the document states it: total_time or medical_decision_making.',
    Separate: 'Whether a visit is separately identifiable: stated (the document states it as significant and '
              'separately identifiable from the procedures; a denial is this value negated).',
    DoubtAbout: "The attribute a doubt is about: status (an act's status), kind (what an act or a session is), session "
                '(which session an act was done in), date_relation (when an act, or the acts a part tells, were done, '
                'or whether a session was this encounter), performer (who did an act, or the acts a part tells), entry '
                '(whose entry an act or a part is), target (what or where an act was done to, or where a lesion is), '
                "technique (an act's device or route, or how a session's endoscope entered), purpose (why an act was "
                'done), cause (what caused the bleeding an act treated), part_of (what an act or a session was part '
                'of), yield (what an extraction act retrieved), access_outcome (the outcome of a cannulation act), '
                "extent (how far a session's endoscope or a device reached, and whether the examination was "
                'complete), stations (which parts a session examined), completion (whether an examination reached the '
                "extent it set out to reach), approach (how a session's endoscope entered), anatomy (an anatomy entry's "
                'type, organ, subtype or joins), identity (whether a lesion entry is one lesion or several, and whether '
                "lesions are the same or distinct), date_of_service (the encounter's date of service), visit (a visit's "
                'basis or its separate identity) or whole (every attribute of the objects the doubt names).',
    DoubtBasis: 'Why a doubt is raised: stated (the document itself states doubt), conflict (another statement of the '
                'document cannot be true together with the value, although it does not give a value of that '
                'attribute) or unclear (the words admit two or more readings).',
})


def definitions_document() -> dict[str, str]:
    """DEFINITIONS in its canonical form, {the enumeration's class name: its line}, in ENUMERATIONS' order. It has no
    pin of its own (DECISIONS D202): step 2a renders every line verbatim into INSTRUCTIONS_2, whose pin covers them."""
    return {enumeration.__name__: DEFINITIONS[enumeration] for enumeration in ENUMERATIONS}


# --- LOCAL_SCHEMA_2 (1.4): the source ---------------------------------------------------------------------------------


def _local_schema() -> dict[str, Any]:
    """LOCAL_SCHEMA_2, built fresh: no node is shared, so the derived schema and every copy are independent."""

    def string() -> dict[str, Any]:
        return {'type': 'string'}

    def strings() -> dict[str, Any]:
        return {'type': 'array', 'items': {'type': 'string'}}

    def enum(values: type[Enum], *, empty: bool = False) -> dict[str, Any]:
        """An enumeration's values in its order; with ``empty``, '' after them (the value of a contradicted fact)."""
        return {'type': 'string', 'enum': [member.value for member in values] + ([''] if empty else [])}

    def array(items: dict[str, Any]) -> dict[str, Any]:
        return {'type': 'array', 'items': items}

    def obj(properties: dict[str, Any]) -> dict[str, Any]:
        """Every field required and nothing else allowed, in the order given."""
        return {'type': 'object', 'additionalProperties': False, 'required': list(properties),
                'properties': properties}

    def source() -> dict[str, Any]:
        return obj({'units': strings(), 'words': string(), 'link': enum(Link)})

    def fact(values: type[Enum] | None = None) -> dict[str, Any]:
        """FACT(values); an id or a date when ``values`` is None."""
        value = enum(values, empty=True) if values is not None else string()
        option = enum(values) if values is not None else string()
        return obj({'state': enum(FactState), 'value': value, 'qualifiers': array(enum(Qualifier)),
                    'sources': array(source()), 'options': array(obj({'value': option, 'sources': array(source())}))})

    def slot(values: type[Enum] | None = None) -> dict[str, Any]:
        return array(fact(values))

    facts = slot  # the same shape; 1.8 bounds a slot at one fact

    encounter = obj({
        'date_of_service': obj({'state': enum(DateState), 'value': string(), 'sources': array(source()),
                                'options': array(obj({'value': string(), 'sources': array(source())}))}),
        'other_dates': array(obj({'value': string(), 'role': fact(DateRole)})),
        'documenting_clinician': slot(),
    })
    person = obj({'id': string(), 'name': source(), 'role': fact(PersonRole)})
    section = obj({
        'id': string(), 'start': source(), 'end': array(source()), 'owner': fact(Owner), 'role': slot(SectionRole),
        'occasion': slot(DateRelation), 'performer': slot(Performer), 'performer_person': slot(),
    })
    session = obj({
        'id': string(), 'examination': slot(), 'kind': fact(SessionKind), 'encounter': slot(EncounterRelation),
        'tract': slot(Tract), 'approach': slot(Approach), 'through': slot(), 'reached': facts(Extent),
        'device_reached': facts(Extent), 'reached_anatomy': slot(), 'completion': slot(Completion),
        'stations': facts(Station), 'part_of_session': slot(),
    })
    anatomy = obj({'id': string(), 'type': fact(AnatomyType), 'organ': slot(Landmark),
                   'subtype': slot(AnastomosisSubtype), 'joins': facts(Landmark)})
    lesion = obj({'id': string(), 'description': source(), 'multiplicity': slot(Multiplicity),
                  'places': facts(Landmark), 'distinct_from': facts(), 'same_as': facts()})
    event = obj({
        'id': string(),
        'anchor': obj({'units': strings(), 'kind_words': string(), 'status_words': string()}),
        'restatements': array(obj({'units': strings(), 'role': enum(RestatementRole)})),
        'kind': fact(Kind), 'other_class': slot(OtherClass), 'status': fact(Status), 'session': slot(),
        'date_relation': slot(DateRelation), 'date': slot(), 'performer': slot(Performer), 'performer_person': slot(),
        'target': obj({'lesion': slot(), 'structure': slot(Structure), 'places': facts(Landmark), 'anatomy': slot(),
                       'duct': slot(Duct)}),
        'technique': obj({'device': slot(Device), 'route': slot(Route)}),
        'purpose': slot(Purpose), 'cause': slot(Cause), 'cause_event': slot(), 'part_of': slot(),
        'part_relation': slot(PartRelation), 'yield': slot(Material), 'access_outcome': slot(AccessOutcome),
        'scope': obj({'breadth': slot(Breadth), 'targets': strings(), 'segment': array(enum(Landmark)),
                      'covers': strings(), 'excepts': strings()}),
        'visit': obj({'basis': slot(EmBasis), 'separately_identifiable': slot(Separate)}),
    })
    doubt = obj({'about': enum(DoubtAbout), 'objects': strings(), 'units': strings(), 'basis': enum(DoubtBasis),
                 'readings': strings()})
    return obj({'encounter': encounter, 'people': array(person), 'sections': array(section),
                'sessions': array(session), 'anatomy': array(anatomy), 'lesions': array(lesion),
                'events': array(event), 'doubts': array(doubt)})


LOCAL_SCHEMA_2: dict[str, Any] = _local_schema()

# --- RESPONSE_SCHEMA_2 (1.4): derived, never written by hand -----------------------------------------------------------

RESPONSE_SCHEMA_2: dict[str, Any] = jsonschema.gemini_schema(LOCAL_SCHEMA_2)
