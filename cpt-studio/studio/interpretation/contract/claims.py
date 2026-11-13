"""The claims pass 2 judges (gemini-appraisal@1; docs/gemini-migration/FINAL-V2.md 2.4, 3.2.1-3.2.6, 3.6 and 1.8; step 2c of
8.1): which of pass 1's facts are claimed, CPT Studio's fixed sentence for each, the contrary control generated for every
READY- or exclusion-deciding one, the pair controls, the completeness claim, the cards, the content keys, the per-request
bound and the seeded order. ``build(basis, seed)`` gives the ClaimSet; contract/appraise_prompt.py renders it into the
request, contract/appraise_read.py reads pass 2's answer against it, and contract/settle.py (step 3a) settles each fact
from it.

**Which facts are claimed** (3.2.1). engine/requirements.CLAIMED (step 1f, pinned by sha) lists, per object class, the
attributes some coding rule reads and the condition under which each is claimed. An event is an ACT, or a STATEMENT when
its claimed status is negated; either is claimed only when its claimed kind is codable (requirements.CODABLE_KINDS) and
its anchor is a valid run with a sentence closure. Every supported or negated fact CLAIMED lists whose condition holds
becomes one claim, and only when it passed its checks: a contradicted, doubted, silent, qualified (any qualifier but
approximate) or failed fact is never claimed (3.1, 3.3 rows 1-5). "Passed its checks" is the reader's own findings
(extract_read: S2, I1, I3's bound, I4) and the ``findings`` the caller gives for the checks settle orchestrates
(geometry's I2, I3, G1-G6; consistency's K1-K8 and L1; the cross-object rules): this module runs no check of its own and
reads no text. A doubt names facts as extract_read.ReadDoubt.named says (a malformed doubt names every attribute of its
objects).

**Inherited facts are claimed per act** (1.5). An act's effective date relation and performer (and performer_person) are
its own slot when that is not empty, else its containing section's - the section the caller attached its anchor to (G4)
- and the act's entry is that section's owner. Such a claim is about THE ACT and cites the governing section fact's
sources. A doubt or finding naming the act's own attribute applies to its effective fact; one naming the section's
fact applies to every act inheriting it.

**The sentence** of a claim is a template of TEMPLATES (act-phrased, and the object forms) or STATEMENT_TEMPLATES (every
attribute claimed for an event whose status is negated is statement-phrased [R:HO-2]), filled from the label tables. A
sentence that names a statement's kind is rendered only when that kind is itself claimed, and a sentence that names
another fact (the relation of a part_of, a breadth's session, excepted acts or targets, an anastomosis's type) only
when that fact is claimed too: a doubted, contradicted or failed value is never shown inside another claim. A claim
cites units: for each of the fact's sources, the object's own statement run (an act's anchor, a lesion's description, a
session's examination anchor) when the source's link is ``statement``, else the source's own units, every run widened
to its sentence closure (1.2 rule 6); so an inherited or placed fact cites its governing source (3.2.5). Objects in a
sentence are named by their card ids; units by their ids. part_of and part_relation, a breadth and its excepted acts,
and a segment's two places, are each told by one sentence and so share one claim.

**Cards** (2.4 [R:SC-C][R:CO-7]) name only an object's type and units: an act or a statement about one (A1..), a session
(X1..), a part of the document (N0..), a lesion (L1..), an anatomy entry (Y1..), numbered in document order. Never a
kind, family, owner or any other label of pass 1's values. When two events share an anchor unit, each card carries that
event's own kind-words and status-words spans (document text, quoted by the request), so the two cards differ.

**Controls** (3.2.3 [R:SC-C]; DECISIONS D194-D196) are generated from CONTROLS, a table over (object class, attribute,
state, values, kinds): each rule says which contrary - a sibling or contrary table's value, a fixed value, the other
polarity, a contrast place, or another object of the document - is asserted about the same object, citing the same
units, in the real-claim form of its contrary. A performed act's control is the statement-phrased "This statement says
that {kind} was not done." (D196), a real claim's form on an event card; the restatement's summary form, the
statement's "was done" form and the completeness claim's limitation form are the three own forms 3.2.3 prescribes. A
contrast place is the first of the place's CONTRAST_PLACES candidates (a segment: its first place's nearest, then its
last place's, then the far ones) compatible with no place of the object - none of its places, of any state, and
nothing of a segment's whole range, read in the tract's order (TRACT_ORDER) - and every list ends with far places of
six regions (CONTRAST_FALLBACK); a place whose candidates the object's places all use up is not claimed (D196: every
place a READY or exclusion path reads is controlled). Another object is never one of the object's own values. No control
asserts what one of the same object's real claims asserts (D196): where pass 1 gives a value and its contrary, neither
is claimed, and the build asserts it. A control that exists in the document but cannot be written without a fact that
is not claimable leaves its fact unclaimed (fail-closed), and the facts sharing its claim with it. UNCONTROLLED names
each attribute decided by a single verdict, with its reason. Pair controls (3.2.3 [R:SC-B]; D196) ask each object about
the other's place or lesion - never one of its own - wherever a statement with a single, listed or segment target
meets an act of a compatible or sibling kind of its session, and for every pair of acts of one session whose kinds a
place-identity rule reads (D118's one stricture; bundling identity by place: the kinds are read from the requirement
table's read-sets), in both directions; their number grows with the square of such acts in one session, and a set
over CLAIM_BOUND is never sent. The completeness claim (3.2.2 [R:SC-B]) is made for an upper EUS session whose station
list is empty, its kind and tract claimable. Nothing in a control's wording marks it, and the seeded order interleaves
it with the claims.

**Content keys and the order.** Each claim's content key is the sha256 of (template, subject, value, units, and every
other parameter its sentence renders, as pass 1's ids, values and unit ids): a verdict is stored with it and never read
against a different claim [R:MO-5]. Two claims with one key are one claim. The claims are ordered by sha256 of (seed,
content key) - a seed the caller derives from the request's inputs - and numbered K1.. in that order, so the order is a
pure function of the inputs and tells nothing about which claim is a control or what pass 1 listed first. A claim set
over CLAIM_BOUND (1.8: 640 claims per request) is never sent (7.4 door 0).

**What this module never does** (5.6, 5.7 measure 4; P1): it copies no text - cards and claims carry unit ids and
spans, and the document reaches pass 2 through the framing - reads no word of the document, compares no value with
text, and imports neither re nor a text module (segment, geometry, fold, date_literals) nor any retired v1 module. Its
string tables are pinned OUTPUT tables (TEMPLATES, STATEMENT_TEMPLATES and the label tables KIND_LABELS, LABELS,
PLACE_LABELS, STATEMENT_DATE_PHRASES and CARD_PHRASES, with the card and claim line formats), rendered into the request
and compared with nothing, their sha in TEMPLATES_SHA256 and STATEMENT_TEMPLATES_SHA256; every other table holds
enumeration members, and every string test is an equality of values (WordsNeverDecide binds this module). A card's id
letter is contract/types' CardType.letter.

**The pins** (2.5) this module's objects take: templates_document() (TEMPLATES_SHA256: the templates, the label tables,
the formats and which template renders each fact), statement_templates_document() (STATEMENT_TEMPLATES_SHA256),
controls_document() (CONTROLS_SHA256: CONTROLS, its tables, the contrast and other-object rules, the pair-control
selection with the kind pairs and read kinds it admits, the completeness rule, UNCONTROLLED and the seed rule) and
claim_bound_document() (CLAIM_BOUND_SHA256); contract/appraise_prompt.py checks them, with CLAIMED's, before a request
is built. The integration owner writes them after the wave's last repair; until the first recording under the label a
changed object needs only its pin recomputed, after it a new APPRAISAL_VERSION (DECISIONS D202).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, unique
from types import MappingProxyType
from typing import cast

from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import jsonschema
from studio.interpretation.contract.extract_read import (Cited, DateOfService, FactKey, ReadAnswer, ReadCitation,
                                                         ReadFact, ReadMember)
from studio.interpretation.contract.types import (AccessOutcome, AnastomosisSubtype, AnatomyType, Approach, Attribute,
                                                  Breadth, Card, CardType, Cause, Claim, Completion, DateRelation,
                                                  DateState, Device, Duct, EmBasis, EncounterRelation, Extent, Fact,
                                                  FactState, Kind, Landmark, Link, Material, Multiplicity, OtherClass,
                                                  Owner, PartRelation, Performer, Purpose, Qualifier, Reason,
                                                  RestatementRole, Route, SessionKind, Source, Span, Station, Status,
                                                  Structure, Tract, Unit)
from studio.interpretation.engine import anatomy, catalogue
from studio.interpretation.engine import requirements as rq

Family = xs.Family
ObjectClass = rq.ObjectClass
_A = Attribute

# --- the per-request bound (FINAL-V2 1.8 [R:MO-3]) ---------------------------------------------------------------------

# At most this many claims (controls, pair controls and the completeness claim included) in one request: the bound times
# the output per verdict (about 24 tokens) plus the largest thinking measured on FRESH-2 (16,776 tokens) stays under the
# 32,768-token cap. Recomputed from D2's measured output per verdict and pinned (CLAIM_BOUND_SHA256).
CLAIM_BOUND = 640


def claim_bound_document() -> dict[str, object]:
    """The per-request bound's canonical form, whose sha256 the integration owner pins (CLAIM_BOUND_SHA256)."""
    return {'claims_per_request': CLAIM_BOUND}


# --- the templates (FINAL-V2 3.2.2) ------------------------------------------------------------------------------------


@unique
class TemplateId(Enum):
    """Every claim template, by id. The ACT_, VISIT_, SESSION_, ANATOMY_, LESION_ and ENCOUNTER_ templates and the
    statement's breadth and covers forms are TEMPLATES (3.2.2's first table writes statement.breadth and
    statement.covers there); the other STMT_ templates are STATEMENT_TEMPLATES (3.2.2's statement-phrased table, with
    DECISIONS D195's statement person). Three serve only as a control's form (3.2.3's own forms): ACT_RESTATES_SUMMARY,
    STMT_DONE and SESSION_SOME_STATIONS. ACT_STATUS_NEGATED is 3.2.2's form of an act's negated status, which no claim
    takes: an event whose status is negated is a statement (3.2.1), and a performed act's control is the
    statement-phrased STMT_NOT_DONE (D196)."""
    ACT_KIND = 'act.kind'
    ACT_OTHER_CLASS = 'act.other_class'
    ACT_STATUS = 'act.status'
    ACT_STATUS_NEGATED = 'act.status.negated'
    ACT_DATE_RELATION = 'act.date_relation'
    ACT_DATE = 'act.date'
    ACT_PERFORMER = 'act.performer'
    ACT_PERFORMER_NEGATED = 'act.performer.negated'
    ACT_PERFORMER_PERSON = 'act.performer_person'
    ACT_ENTRY = 'act.entry'
    ACT_SESSION = 'act.session'
    ACT_TARGET_LESION = 'act.target.lesion'
    ACT_TARGET_PLACE = 'act.target.places'
    ACT_TARGET_PLACE_NEGATED = 'act.target.places.negated'
    ACT_TARGET_STRUCTURE = 'act.target.structure'
    ACT_TARGET_ANATOMY = 'act.target.anatomy'
    ACT_TARGET_DUCT = 'act.target.duct'
    ACT_DEVICE = 'act.technique.device'
    ACT_DEVICE_NEGATED = 'act.technique.device.negated'
    ACT_ROUTE = 'act.technique.route'
    ACT_PURPOSE = 'act.purpose'
    ACT_CAUSE = 'act.cause'
    ACT_CAUSE_EVENT = 'act.cause_event'
    ACT_CAUSE_NEGATED = 'act.cause.negated'
    ACT_PART_OF = 'act.part_of'
    ACT_PART_OF_NEGATED = 'act.part_of.negated'
    ACT_YIELD = 'act.yield'
    ACT_YIELD_NEGATED = 'act.yield.negated'
    ACT_ACCESS = 'act.access_outcome'
    ACT_RESTATES = 'act.restatements.role'
    ACT_RESTATES_SUMMARY = 'act.restatements.role.summary'
    VISIT_BASIS = 'visit.basis'
    VISIT_SEPARATE = 'visit.separately_identifiable'
    VISIT_SEPARATE_NEGATED = 'visit.separately_identifiable.negated'
    SESSION_KIND = 'session.kind'
    SESSION_ENCOUNTER = 'session.encounter'
    SESSION_TRACT = 'session.tract'
    SESSION_APPROACH = 'session.approach'
    SESSION_THROUGH = 'session.through'
    SESSION_REACHED = 'session.reached'
    SESSION_REACHED_NEGATED = 'session.reached.negated'
    SESSION_REACHED_ANATOMY = 'session.reached_anatomy'
    SESSION_COMPLETION = 'session.completion'
    SESSION_STATION = 'session.stations'
    SESSION_STATION_NEGATED = 'session.stations.negated'
    SESSION_PART_OF_SESSION = 'session.part_of_session'
    SESSION_ALL_STATIONS = 'session.stations.completeness'
    SESSION_SOME_STATIONS = 'session.stations.limitation'
    ANATOMY_TYPE = 'anatomy.type'
    ANATOMY_ORGAN_ABSENT = 'anatomy.organ'
    ANATOMY_ORGAN_NOT_ABSENT = 'anatomy.organ.negated'
    ANATOMY_SUBTYPE = 'anatomy.subtype'
    ANATOMY_JOINS = 'anatomy.joins'
    LESION_MULTIPLICITY = 'lesion.multiplicity'
    LESION_DISTINCT = 'lesion.distinct_from'
    LESION_SAME = 'lesion.same_as'
    ENCOUNTER_DATE = 'encounter.date_of_service'
    STMT_BREADTH_ALL = 'statement.scope.breadth.all_of_kind'
    STMT_BREADTH_EXCEPTIVE = 'statement.scope.breadth.exceptive'
    STMT_BREADTH_TARGETED = 'statement.scope.breadth.targeted'
    STMT_COVERS = 'statement.scope.covers'
    STMT_KIND = 'statement.kind'
    STMT_NOT_DONE = 'statement.status.negated'
    STMT_DONE = 'statement.status.done'
    STMT_DATE_RELATION = 'statement.date_relation'
    STMT_SESSION = 'statement.session'
    STMT_PERFORMER = 'statement.performer'
    STMT_PERFORMER_PERSON = 'statement.performer_person'
    STMT_TARGET_LESION = 'statement.target.lesion'
    STMT_TARGET_PLACE = 'statement.target.places'
    STMT_TARGET_SEGMENT = 'statement.scope.segment'
    STMT_TARGET_ANATOMY = 'statement.target.anatomy'
    STMT_TARGET_DUCT = 'statement.target.duct'
    STMT_DEVICE = 'statement.technique.device'


@unique
class Slot(Enum):
    """The fields a template fills, each written {<value>} in its sentence."""
    KIND = 'kind'  # a kind, bare
    KIND_A = 'kind_a'  # a kind with its article
    KINDS = 'kinds'  # a kind, plural
    OTHER_CLASS = 'other_class'
    STATUS = 'status'
    DATE_RELATION = 'date_relation'
    DATE = 'date'
    PERFORMER = 'performer'
    PERSON = 'person'
    START = 'start'
    OWNER = 'owner'
    SESSION = 'session'
    OTHER = 'other'
    LESION = 'lesion'
    PLACE = 'place'
    POINT = 'point'
    STATION = 'station'
    ORGAN = 'organ'
    STRUCTURE = 'structure'
    ANATOMY = 'anatomy'
    DUCT = 'duct'
    DEVICE = 'device'
    ROUTE = 'route'
    PURPOSE = 'purpose'
    CAUSE = 'cause'
    ACT = 'act'
    ACTS = 'acts'
    RELATION = 'relation'
    MATERIAL = 'material'
    ACCESS = 'access'
    BASIS = 'basis'
    FAMILY = 'family'
    ENCOUNTER = 'encounter'
    TRACT = 'tract'
    APPROACH = 'approach'
    COMPLETION = 'completion'
    TYPE = 'type'
    SUBTYPE = 'subtype'
    MULTIPLICITY = 'multiplicity'
    UNITS = 'units'
    FIRST = 'first'
    LAST = 'last'
    TARGET = 'target'


T = TemplateId

# 3.2.2's first table, sentence for sentence; each {field} is a Slot, filled from the label tables, card ids and unit
# ids. A pinned OUTPUT table (5.7 NoWordLists): rendered into the request, never compared with document text.
TEMPLATES: Mapping[TemplateId, str] = MappingProxyType({
    T.ACT_KIND: 'This act is {kind_a}.',
    T.ACT_OTHER_CLASS: 'This act is {other_class}.',
    T.ACT_STATUS: 'This act {status}.',
    T.ACT_STATUS_NEGATED: 'The document states that this act was not carried out.',
    T.ACT_DATE_RELATION: 'This act {date_relation}.',
    T.ACT_DATE: 'This act was done on {date}.',
    T.ACT_PERFORMER: 'This act was done by {performer}.',
    T.ACT_PERFORMER_NEGATED: 'The document states this act was not done by {performer}.',
    T.ACT_PERFORMER_PERSON: 'This act was done by the person named at {person}.',
    T.ACT_ENTRY: 'This act is told in the part of the document that begins at {start}, written by {owner}.',
    T.ACT_SESSION: 'This act was done during session {session}.',
    T.ACT_TARGET_LESION: 'This act was done to lesion {lesion}.',
    T.ACT_TARGET_PLACE: 'This act was done in the {place}.',
    T.ACT_TARGET_PLACE_NEGATED: 'The document states this act was not done in the {place}.',
    T.ACT_TARGET_STRUCTURE: 'This act was done to {structure}.',
    T.ACT_TARGET_ANATOMY: 'This act was done at anatomy {anatomy}.',
    T.ACT_TARGET_DUCT: 'This act was done in the {duct} duct.',
    T.ACT_DEVICE: 'This act used {device}.',
    T.ACT_DEVICE_NEGATED: 'The document states that {device} was not used for this act.',
    T.ACT_ROUTE: 'This act was {route}.',
    T.ACT_PURPOSE: 'This act was done for {purpose}.',
    T.ACT_CAUSE: 'The bleeding this act treated was {cause}.',
    T.ACT_CAUSE_EVENT: 'The bleeding this act treated was caused by act {act}.',
    T.ACT_CAUSE_NEGATED: 'The bleeding this act treated was not caused by another act of this procedure.',
    T.ACT_PART_OF: 'This act was {relation} act {act}.',
    T.ACT_PART_OF_NEGATED: 'The document states this act was separate from act {act}.',
    T.ACT_YIELD: 'This act retrieved {material}.',
    T.ACT_YIELD_NEGATED: 'The document states that this act retrieved nothing.',
    T.ACT_ACCESS: 'The cannulation {access}.',
    T.ACT_RESTATES: ('The part of the document beginning at {units} tells this act in full, in its own words, not only '
                     'as a summary, a title or a reference to another part.'),
    T.ACT_RESTATES_SUMMARY: ('The part of the document beginning at {units} only summarizes this act, names it, or '
                             'refers to where it is told.'),
    T.VISIT_BASIS: "The visit's level is based on {basis}.",
    T.VISIT_SEPARATE: ('The document states the visit was significant and separately identifiable from any '
                       'procedure.'),
    T.VISIT_SEPARATE_NEGATED: 'The document states the visit was not separately identifiable.',
    T.SESSION_KIND: 'Session {session} is {family}.',
    T.SESSION_ENCOUNTER: 'Session {session} {encounter}.',
    T.SESSION_TRACT: 'Session {session} examined the {tract}.',
    T.SESSION_APPROACH: 'In session {session} the scope was passed {approach}.',
    T.SESSION_THROUGH: 'In session {session} the scope passed through anatomy {anatomy}.',
    T.SESSION_REACHED: 'In session {session} the endoscope itself reached the {point}.',
    T.SESSION_REACHED_NEGATED: 'In session {session} the endoscope did not reach the {point}.',
    T.SESSION_REACHED_ANATOMY: 'The furthest point in session {session} was at anatomy {anatomy}.',
    T.SESSION_COMPLETION: 'Session {session} was {completion}.',
    T.SESSION_STATION: 'In session {session} the {station} was examined.',
    T.SESSION_STATION_NEGATED: 'In session {session} the {station} was not examined.',
    T.SESSION_PART_OF_SESSION: 'Session {session} was the endoscopic portion of session {other}.',
    T.SESSION_ALL_STATIONS: ('The document does not say that the ultrasound examination of session {session} covered '
                             'only some of the esophagus, the stomach and the duodenum.'),
    T.SESSION_SOME_STATIONS: ('The document says that the ultrasound examination of session {session} covered only '
                              'some of the esophagus, the stomach and the duodenum.'),
    T.ANATOMY_TYPE: 'The patient has {type} (described at {units}).',
    T.ANATOMY_ORGAN_ABSENT: 'The {organ} is surgically absent.',
    T.ANATOMY_ORGAN_NOT_ABSENT: 'The document states the {organ} is not surgically absent.',
    T.ANATOMY_SUBTYPE: 'This anastomosis is {subtype}.',
    T.ANATOMY_JOINS: 'This anastomosis joins the {place}.',
    T.LESION_MULTIPLICITY: 'Lesion {lesion} is {multiplicity}.',
    T.LESION_DISTINCT: 'Lesions {lesion} and {other} are different lesions.',
    T.LESION_SAME: 'Lesions {lesion} and {other} are the same lesion.',
    T.ENCOUNTER_DATE: 'The date of service of this document is {date}.',
    T.STMT_BREADTH_ALL: 'This statement says no {kind} at all was done in session {session}.',
    T.STMT_BREADTH_EXCEPTIVE: 'This statement denies only {kinds} other than acts {acts}.',
    T.STMT_BREADTH_TARGETED: 'This statement denies {kind} of {target}.',
    T.STMT_COVERS: 'This statement applies to act {act}.',
})

# 3.2.2's statement-phrased table [R:HO-2]: every attribute claimed for an event whose claimed status is negated, with
# DECISIONS D195's statement person ("This statement is about {kind label}s by the person named at {units}."; the units
# fill {person}, as the act's form fills them). A pinned OUTPUT table.
STATEMENT_TEMPLATES: Mapping[TemplateId, str] = MappingProxyType({
    T.STMT_KIND: 'This statement is about {kinds}.',
    T.STMT_NOT_DONE: 'This statement says that {kind} was not done.',
    T.STMT_DONE: 'This statement says that {kind} was done.',
    T.STMT_DATE_RELATION: 'This statement is about {kinds} {date_relation}.',
    T.STMT_SESSION: 'This statement is about session {session}.',
    T.STMT_PERFORMER: 'This statement is about {kinds} by {performer}.',
    T.STMT_PERFORMER_PERSON: 'This statement is about {kinds} by the person named at {person}.',
    T.STMT_TARGET_LESION: 'This statement is about {kinds} of lesion {lesion}.',
    T.STMT_TARGET_PLACE: 'This statement is about {kinds} in the {place}.',
    T.STMT_TARGET_SEGMENT: 'This statement is about {kinds} from the {first} to the {last}.',
    T.STMT_TARGET_ANATOMY: 'This statement is about {kinds} at anatomy {anatomy}.',
    T.STMT_TARGET_DUCT: 'This statement is about {kinds} in the {duct} duct.',
    T.STMT_DEVICE: 'This statement is about {kinds} with {device}.',
})

# The templates whose sentence names the statement's kind: rendered only when that kind is claimed.
NAMES_THE_KIND: frozenset[TemplateId] = frozenset({
    T.STMT_NOT_DONE, T.STMT_DONE, T.STMT_DATE_RELATION, T.STMT_PERFORMER, T.STMT_PERFORMER_PERSON,
    T.STMT_TARGET_LESION, T.STMT_TARGET_PLACE, T.STMT_TARGET_SEGMENT, T.STMT_TARGET_ANATOMY, T.STMT_TARGET_DUCT,
    T.STMT_DEVICE, T.STMT_BREADTH_ALL, T.STMT_BREADTH_EXCEPTIVE, T.STMT_BREADTH_TARGETED})


def template(template_id: TemplateId) -> str:
    """The sentence of ``template_id``, from TEMPLATES or STATEMENT_TEMPLATES."""
    found = TEMPLATES.get(template_id)
    return found if found is not None else STATEMENT_TEMPLATES[template_id]


# --- the label tables (3.2.2: "labels come from fixed tables"): pinned OUTPUT tables -----------------------------------

# A kind's three forms: (bare, with its article, plural), as the templates use them ({kind}, {kind_a}, {kinds}). Each
# names the meaning 1.4's definition gives, never a surface form of a document.
KIND_LABELS: Mapping[Kind, tuple[str, str, str]] = MappingProxyType({
    Kind.EXAMINATION: ('examination as a whole', 'the examination itself, not an act done during it',
                       'examinations as a whole'),
    Kind.EM_VISIT: ('evaluation and management visit', 'an evaluation and management visit',
                    'evaluation and management visits'),
    Kind.EM_PROLONGED: ('prolonged visit time', 'prolonged visit time stated as such', 'prolonged visit time'),
    Kind.BIOPSY: ('tissue sampling with forceps', 'a tissue sampling with forceps', 'tissue samplings with forceps'),
    Kind.HOT_BIOPSY: ('removal or sampling with hot forceps', 'a removal or sampling with hot forceps',
                      'removals or samplings with hot forceps'),
    Kind.SNARE: ('removal with a snare', 'a removal with a snare', 'removals with a snare'),
    Kind.EMR: ('endoscopic mucosal resection', 'an endoscopic mucosal resection', 'endoscopic mucosal resections'),
    Kind.ESD: ('endoscopic submucosal dissection', 'an endoscopic submucosal dissection',
               'endoscopic submucosal dissections'),
    Kind.REMOVAL: ('removal by any method', 'a removal by a method the document does not give',
                   'removals by any method'),
    Kind.ABLATION: ('ablation of tissue', 'an ablation of tissue', 'ablations of tissue'),
    Kind.BLEEDING_CONTROL: ('treatment of bleeding', 'a treatment of bleeding', 'treatments of bleeding'),
    Kind.CLIP: ('clip placement', 'a clip placement', 'clip placements'),
    Kind.TATTOO: ('injection that marks a site', 'an injection that marks a site', 'injections that mark a site'),
    Kind.INJECTION: ('injection that does not mark a site', 'an injection that does not mark a site',
                     'injections that do not mark a site'),
    Kind.BAND_LIGATION: ('band ligation', 'a band ligation', 'band ligations'),
    Kind.DILATION: ('dilation of a narrowing', 'a dilation of a narrowing', 'dilations of a narrowing'),
    Kind.STENT: ('stent placement', 'a stent placement', 'stent placements'),
    Kind.STENT_REMOVAL: ('stent removal', 'a stent removal', 'stent removals'),
    Kind.STENT_EXCHANGE: ('stent exchange', 'a stent exchange', 'stent exchanges'),
    Kind.FOREIGN_BODY: ('foreign body removal', 'a foreign body removal', 'foreign body removals'),
    Kind.DECOMPRESSION: ('decompression', 'a decompression', 'decompressions'),
    Kind.TUBE_PLACEMENT: ('tube placement other than a gastrostomy', 'a tube placement other than a gastrostomy',
                          'tube placements other than a gastrostomy'),
    Kind.TUBE_REPLACEMENT: ('feeding tube replacement', 'a feeding tube replacement', 'feeding tube replacements'),
    Kind.PEG: ('percutaneous endoscopic gastrostomy placement', 'a percutaneous endoscopic gastrostomy placement',
               'percutaneous endoscopic gastrostomy placements'),
    Kind.MYOTOMY: ('myotomy', 'a myotomy', 'myotomies'),
    Kind.FUNDOPLICATION: ('fundoplication', 'a fundoplication', 'fundoplications'),
    Kind.FNA: ('fine-needle aspiration or biopsy', 'a fine-needle aspiration or biopsy',
               'fine-needle aspirations or biopsies'),
    Kind.DRAINAGE: ('drainage', 'a drainage', 'drainages'),
    Kind.CANNULATION: ('cannulation of a duct', 'a cannulation of a duct', 'cannulations of a duct'),
    Kind.SPHINCTEROTOMY: ('sphincterotomy', 'a sphincterotomy', 'sphincterotomies'),
    Kind.STONE_EXTRACTION: ('extraction of stones', 'an extraction of stones', 'extractions of stones'),
    Kind.LITHOTRIPSY: ('lithotripsy', 'a lithotripsy', 'lithotripsies'),
    Kind.CHOLANGIOSCOPY: ('cholangioscopy', 'a cholangioscopy', 'cholangioscopies'),
    Kind.PRESSURE_MEASUREMENT: ('pressure measurement', 'a pressure measurement', 'pressure measurements'),
    Kind.CAPSULE_STUDY: ('capsule study', 'a capsule study', 'capsule studies'),
    Kind.MANOMETRY: ('manometry', 'a manometry study', 'manometry studies'),
    Kind.PH_MONITORING: ('pH monitoring', 'a pH monitoring study', 'pH monitoring studies'),
    Kind.RECTAL_SENSATION: ('rectal sensation, tone or compliance testing',
                            'a rectal sensation, tone or compliance test', 'rectal sensation, tone or compliance tests'),
    Kind.BALLOON_EXPULSION: ('balloon expulsion testing', 'a balloon expulsion test', 'balloon expulsion tests'),
    Kind.MODERATE_SEDATION: ('moderate sedation', 'moderate sedation', 'moderate sedation'),
    Kind.INTERVENTION: ('intervention of any kind', 'an intervention of any kind', 'interventions of any kind'),
    Kind.OTHER: ('act of another kind', 'an act of another kind', 'acts of another kind'),
})

# Every other value a template renders, one label per member of each enumeration a template names. Keyed by
# enumeration members (the members of two enumerations never compare equal). A card's id letter is CardType.letter
# (contract/types, 2.4), never a label here.
LABELS: Mapping[Enum, str] = MappingProxyType({
    # "This act is {other_class}."
    OtherClass.PROCEDURE: 'a procedure', OtherClass.TEST: 'a test', OtherClass.ORDER: 'an order',
    OtherClass.IMAGING: 'an imaging study', OtherClass.LABORATORY: 'a laboratory test',
    OtherClass.COUNSELING: 'counseling', OtherClass.EVALUATION: 'an evaluation', OtherClass.MEDICATION: 'a medication',
    OtherClass.OTHER: 'an act of another class',
    # "This act {status}."
    Status.PERFORMED: 'was carried out (not only planned, attempted or denied)',
    Status.ATTEMPTED_NOT_COMPLETED: 'was begun but not completed',
    Status.PLANNED: 'is planned or recommended, not done',
    # "This act {date_relation}."
    DateRelation.ON_DATE_OF_SERVICE: 'was done on the date of service',
    DateRelation.EARLIER_DATE: 'was done on a date before the date of service',
    DateRelation.LATER_DATE: 'is to be done, or was done, after the date of service',
    # "This act was done by {performer}." and the statement's "... by {performer}."
    Performer.DOCUMENTING_TEAM: 'the documenting clinician or a member of their team',
    Performer.OTHER_CLINICIAN: 'a clinician other than the documenting clinician and their team',
    Performer.OTHER_FACILITY: 'another facility',
    # "..., written by {owner}."
    Owner.DOCUMENTING_CLINICIAN: 'the documenting clinician', Owner.NURSING: 'nursing staff',
    Owner.ANESTHESIA: 'anesthesia staff', Owner.PATHOLOGY: 'pathology', Owner.RADIOLOGY: 'radiology',
    Owner.OTHER_CLINICIAN: 'a clinician other than the documenting clinician',
    Owner.OUTSIDE_RECORD: 'another clinician or facility, as a record copied in',
    Owner.PATIENT_REPORTED: 'no clinician, as what the patient reports', Owner.ADMINISTRATIVE: 'administrative staff',
    # "This act was done to {structure}."
    Structure.LESION: 'a lesion', Structure.STRICTURE: 'a stricture', Structure.ULCER: 'an ulcer',
    Structure.BLEEDING_SITE: 'a bleeding site', Structure.VESSEL: 'a vessel', Structure.VARIX: 'a varix',
    Structure.STONE: 'a stone', Structure.STENT: 'a stent', Structure.DUCT: 'a duct',
    Structure.PANCREATIC_FLUID_COLLECTION: 'a pancreatic fluid collection', Structure.GALLBLADDER: 'the gallbladder',
    Structure.LIVER: 'the liver', Structure.LYMPH_NODE: 'a lymph node', Structure.MASS: 'a mass',
    Structure.WALL: 'the wall', Structure.LUMEN: 'the lumen', Structure.FOREIGN_BODY: 'a foreign body',
    Structure.MUCOSA: 'the mucosa', Structure.ANASTOMOSIS: 'an anastomosis', Structure.OTHER: 'another structure',
    # "... in the {duct} duct."
    Duct.BILIARY: 'bile', Duct.PANCREATIC: 'pancreatic', Duct.CYSTIC: 'cystic',
    # "This act used {device}." and its negated and statement forms
    Device.ENDOSCOPE: 'an endoscope', Device.COLD_SNARE: 'a cold snare', Device.HOT_SNARE: 'a hot snare',
    Device.SNARE: 'a snare the document does not call cold or hot', Device.COLD_FORCEPS: 'cold forceps',
    Device.HOT_FORCEPS: 'hot forceps', Device.FORCEPS: 'forceps the document does not call cold or hot',
    Device.NEEDLE: 'a needle', Device.INJECTION: 'an injection device', Device.BALLOON: 'a dilating balloon',
    Device.WIRE_BOUGIE: 'dilators passed over a guide wire', Device.BOUGIE: 'a bougie passed without a guide wire',
    Device.CLIP: 'a clip', Device.BAND: 'a band', Device.ARGON_PLASMA: 'argon plasma coagulation',
    Device.RADIOFREQUENCY: 'radiofrequency energy', Device.CRYOTHERAPY: 'cryotherapy',
    Device.THERMAL_PROBE: 'a thermal probe', Device.ELECTROCAUTERY: 'electrocautery', Device.STENT: 'a stent',
    Device.BASKET: 'a basket', Device.EXTRACTION_BALLOON: 'an extraction balloon',
    Device.SPHINCTEROTOME: 'a sphincterotome', Device.LITHOTRIPTER: 'a lithotripter',
    Device.CHOLANGIOSCOPE: 'a cholangioscope', Device.CAPSULE: 'a capsule', Device.CATHETER: 'a catheter',
    Device.MANUAL: 'manual pressure or handling, without a device', Device.OTHER: 'a device of another kind',
    # "This act was {route}."
    Route.SUBMUCOSAL: 'a submucosal injection',
    Route.EUS_TRANSMURAL: 'done across the wall, guided by endoscopic ultrasound',
    Route.EUS_FINE_NEEDLE: 'done by a fine needle, guided by endoscopic ultrasound',
    Route.INTRALUMINAL: 'done within the lumen', Route.INTRADUCTAL: 'done within a duct',
    Route.PERCUTANEOUS: 'done through the skin', Route.TOPICAL: 'applied to the surface',
    # "This act was done for {purpose}."
    Purpose.DIAGNOSTIC: 'diagnosis', Purpose.REMOVAL: 'removal',
    Purpose.LIFT_FOR_RESECTION: 'lifting tissue for a resection', Purpose.MARKING: 'marking a site',
    Purpose.HEMOSTASIS: 'treatment of bleeding present at this encounter', Purpose.PROPHYLAXIS: 'prevention of bleeding',
    Purpose.TREATMENT: 'treatment', Purpose.ACCESS: 'gaining access', Purpose.SAMPLING: 'sampling',
    Purpose.DRAINAGE: 'drainage', Purpose.DECOMPRESSION: 'decompression', Purpose.OTHER: 'a purpose of another kind',
    # "The bleeding this act treated was {cause}."
    Cause.ACT_OF_THIS_SESSION: 'caused by another act of the same session',
    Cause.PRE_EXISTING_LESION: 'from a lesion present before the session', Cause.SPONTANEOUS: 'spontaneous',
    Cause.EARLIER_PROCEDURE: 'caused by an earlier procedure', Cause.OTHER: 'from a cause of another kind',
    # "This act was {relation} act {act}."
    PartRelation.STEP_OF: 'a step of', PartRelation.LIFT_FOR: 'a lift done to enable',
    PartRelation.ACCESS_FOR: 'access gained to enable', PartRelation.ADJUNCT_OF: 'an adjunct done with',
    PartRelation.COMPONENT_OF: 'one part of',
    # "This act retrieved {material}."
    Material.STONES: 'stones', Material.STONE_FRAGMENTS: 'stone fragments', Material.SLUDGE: 'sludge',
    Material.DEBRIS: 'debris', Material.STENT: 'a stent', Material.FOREIGN_BODY: 'a foreign body',
    Material.TISSUE: 'tissue', Material.ANYTHING: 'material of some kind',
    # "The cannulation {access}."
    AccessOutcome.ACHIEVED: 'was achieved', AccessOutcome.FAILED: 'failed',
    AccessOutcome.ACHIEVED_AFTER_FAILED_ATTEMPTS: 'was achieved after failed attempts',
    # "The visit's level is based on {basis}."
    EmBasis.TOTAL_TIME: 'the total time spent', EmBasis.MEDICAL_DECISION_MAKING: 'medical decision making',
    # "Session {session} is {family}."
    SessionKind.OFFICE_EM: 'an office or outpatient evaluation and management visit',
    SessionKind.EGD: 'an upper endoscopy', SessionKind.ENTEROSCOPY: 'a small-bowel enteroscopy',
    SessionKind.COLONOSCOPY: 'a colonoscopy', SessionKind.FLEX_SIG: 'a flexible sigmoidoscopy',
    SessionKind.EUS: 'an endoscopic ultrasound examination',
    SessionKind.ERCP: 'an endoscopic retrograde cholangiopancreatography', SessionKind.CAPSULE: 'a capsule endoscopy',
    # motility names its family's studies (91010-91022, 91040, 91117) and sets them apart from anorectal testing, so the
    # control DECISIONS D196 gives an anorectal session (its sibling, motility) is false of an anorectal manometry
    SessionKind.MOTILITY: ('a motility or manometry study of the esophagus, the stomach, the small bowel or the colon, '
                           'not an anorectal test'),
    SessionKind.REFLUX: 'a pH or impedance monitoring study',
    SessionKind.ANORECTAL: 'an anorectal test', SessionKind.FEEDING_TUBE: 'a feeding-tube procedure',
    SessionKind.SEDATION: 'moderate sedation by the clinician who performs the procedure',
    SessionKind.EM_OTHER: 'an evaluation and management service in another setting',
    SessionKind.OTHER_GI: 'a gastrointestinal service of another kind',
    SessionKind.NOT_GI: 'a service outside gastroenterology',
    # "Session {session} {encounter}."
    EncounterRelation.THIS_ENCOUNTER: 'is the encounter this document records',
    EncounterRelation.SEPARATE_ENCOUNTER: ('was a separate encounter on the date of service, not the one this '
                                           'document records'),
    # "Session {session} examined the {tract}."
    Tract.UPPER: 'upper digestive tract', Tract.LOWER: 'lower digestive tract',
    Tract.PANCREATOBILIARY: 'bile and pancreatic ducts',
    # "In session {session} the scope was passed {approach}."
    Approach.ORAL: 'through the mouth', Approach.TRANSNASAL: 'through the nose', Approach.TRANSANAL: 'through the anus',
    Approach.THROUGH_STOMA: 'through a stoma', Approach.THROUGH_POUCH: 'through a pouch',
    Approach.THROUGH_GASTROSTOMY: 'through a gastrostomy', Approach.PERCUTANEOUS: 'through the skin',
    # "Session {session} was {completion}."
    Completion.COMPLETE: 'complete, reaching the extent it set out to reach',
    Completion.INCOMPLETE: 'incomplete, stopping short of the extent it set out to reach',
    Completion.TERMINATED: 'terminated early, for a reason the document states',
    # "The patient has {type} (described at {units})."
    AnatomyType.SURGICALLY_ABSENT: 'an organ or part removed by surgery',
    AnatomyType.ANASTOMOSIS: 'a surgical joining of two organs', AnatomyType.STOMA: 'a surgical opening (a stoma)',
    AnatomyType.ILEAL_POUCH: 'a pouch made from the ileum', AnatomyType.GASTRIC_POUCH: 'a pouch made from the stomach',
    AnatomyType.ROUX_LIMB: 'a Roux limb', AnatomyType.BYPASS: 'a surgical bypass',
    AnatomyType.OTHER_ALTERATION: 'a surgical alteration of another kind',
    # "This anastomosis is {subtype}."
    AnastomosisSubtype.ILEOCOLIC: 'one joining ileum and colon',
    AnastomosisSubtype.COLOCOLIC: 'one joining two parts of the colon',
    AnastomosisSubtype.COLORECTAL: 'one joining colon and rectum',
    AnastomosisSubtype.COLOANAL: 'one joining colon and anus',
    AnastomosisSubtype.ILEORECTAL: 'one joining ileum and rectum',
    AnastomosisSubtype.ILEOANAL: 'one joining ileum and anus',
    AnastomosisSubtype.GASTROJEJUNAL: 'one joining stomach and jejunum',
    AnastomosisSubtype.GASTRODUODENAL: 'one joining stomach and duodenum',
    AnastomosisSubtype.ESOPHAGOJEJUNAL: 'one joining esophagus and jejunum',
    AnastomosisSubtype.ESOPHAGOGASTRIC: 'one joining esophagus and stomach',
    AnastomosisSubtype.HEPATICOJEJUNAL: 'one joining bile duct and jejunum',
    AnastomosisSubtype.CHOLEDOCHODUODENAL: 'one joining common bile duct and duodenum',
    AnastomosisSubtype.PANCREATICOJEJUNAL: 'one joining pancreas and jejunum',
    AnastomosisSubtype.OTHER: 'one joining organs of another pair',
    # "Lesion {lesion} is {multiplicity}."
    Multiplicity.SINGLE: 'a single lesion', Multiplicity.GROUP: 'a group of lesions described only together',
    # "In session {session} the {station} was examined."
    Station.ESOPHAGUS: 'esophagus', Station.STOMACH: 'stomach', Station.DUODENUM: 'duodenum',
    Station.JEJUNUM: 'jejunum', Station.ILEUM: 'ileum', Station.COLON: 'colon', Station.RECTUM: 'rectum',
})

# Places: "in the {place}", "reached the {point}", "The {organ} is surgically absent", "joins the {place}", over
# LANDMARKS2. An EXTENTS value renders as the landmark of its value, and stated_depth as PLACE_LABEL_DEPTH.
PLACE_LABELS: Mapping[Landmark, str] = MappingProxyType({
    Landmark.ESOPHAGUS: 'esophagus', Landmark.PROXIMAL_ESOPHAGUS: 'proximal esophagus',
    Landmark.MID_ESOPHAGUS: 'middle esophagus', Landmark.DISTAL_ESOPHAGUS: 'distal esophagus',
    Landmark.GASTROESOPHAGEAL_JUNCTION: 'gastroesophageal junction', Landmark.STOMACH: 'stomach',
    Landmark.GASTRIC_CARDIA: 'cardia of the stomach', Landmark.GASTRIC_FUNDUS: 'fundus of the stomach',
    Landmark.GASTRIC_BODY: 'body of the stomach', Landmark.GASTRIC_ANTRUM: 'antrum of the stomach',
    Landmark.PYLORUS: 'pylorus', Landmark.DUODENUM: 'duodenum', Landmark.DUODENAL_BULB: 'bulb of the duodenum',
    Landmark.SECOND_PORTION_DUODENUM: 'duodenum (its second portion)',
    Landmark.THIRD_PORTION_DUODENUM: 'duodenum (its third portion)',
    Landmark.FOURTH_PORTION_DUODENUM: 'duodenum (its fourth portion)', Landmark.AMPULLA: 'ampulla',
    Landmark.JEJUNUM: 'jejunum', Landmark.ILEUM: 'ileum', Landmark.TERMINAL_ILEUM: 'terminal ileum',
    Landmark.NEO_TERMINAL_ILEUM: 'ileum next to an ileocolic joining (neo-terminal ileum)',
    Landmark.SMALL_BOWEL: 'small bowel', Landmark.COLON: 'colon', Landmark.RIGHT_COLON: 'right colon',
    Landmark.LEFT_COLON: 'left colon', Landmark.PROXIMAL_COLON: 'proximal colon', Landmark.DISTAL_COLON: 'distal colon',
    Landmark.CECUM: 'cecum', Landmark.APPENDICEAL_ORIFICE: 'opening of the appendix',
    Landmark.ILEOCECAL_VALVE: 'ileocecal valve', Landmark.ASCENDING_COLON: 'ascending colon',
    Landmark.HEPATIC_FLEXURE: 'hepatic flexure', Landmark.TRANSVERSE_COLON: 'transverse colon',
    Landmark.SPLENIC_FLEXURE: 'splenic flexure', Landmark.DESCENDING_COLON: 'descending colon',
    Landmark.SIGMOID_COLON: 'sigmoid colon', Landmark.RECTOSIGMOID: 'junction of the sigmoid colon and the rectum',
    Landmark.RECTUM: 'rectum', Landmark.ANAL_CANAL: 'anal canal', Landmark.ANASTOMOSIS: 'surgical joining',
    Landmark.STOMA: 'stoma', Landmark.POUCH: 'pouch', Landmark.COMMON_BILE_DUCT: 'common bile duct',
    Landmark.BILE_DUCT: 'bile duct', Landmark.PANCREATIC_DUCT: 'pancreatic duct', Landmark.PANCREAS: 'pancreas',
    Landmark.GALLBLADDER: 'gallbladder', Landmark.LIVER: 'liver', Landmark.LYMPH_NODE: 'lymph node',
    Landmark.OTHER: 'place the document names that none of these names',
})
PLACE_LABEL_DEPTH = 'depth the document states'  # EXTENTS' stated_depth: "reached the {point}"

# "This statement is about {kinds} {date_relation}." (the act's form is LABELS').
STATEMENT_DATE_PHRASES: Mapping[DateRelation, str] = MappingProxyType({
    DateRelation.ON_DATE_OF_SERVICE: 'on the date of service',
    DateRelation.EARLIER_DATE: 'on a date before the date of service',
    DateRelation.LATER_DATE: 'after the date of service',
})


# How the request writes the cards and the claims after the document (contract/appraise_prompt.py renders them, 2.4):
# a card names its object's type and units, nothing else (the words of two acts told in one sentence are quoted:
# document text); a claim names its card - or the document, for a claim about the encounter - and the units it cites,
# then its sentence. A pinned OUTPUT table and five formats, pinned with TEMPLATES.
CARD_PHRASES: Mapping[CardType, str] = MappingProxyType({
    CardType.ACT: 'an act, or a statement about an act, told at {units}',
    CardType.SESSION: 'a session, told at {units}',
    CardType.SECTION: 'a part of the document, beginning at {units}',
    CardType.LESION: 'a lesion, described at {units}',
    CardType.ANATOMY: 'an anatomy entry, described at {units}',
})
CARDS_HEADING = 'CARDS'
CLAIMS_HEADING = 'CLAIMS'
CARD_LINE = '{card}: {phrase}{words}.'
CARD_WORDS = ', in its own words {quotes}'
CLAIM_LINE = '{claim} (about {card}; cites {units}): {sentence}'
DOCUMENT_CARD = 'the document'


def label(member: Enum) -> str:
    """The label a template renders for an enumeration value: KIND_LABELS' form with its article, PLACE_LABELS for a
    place (an extent as the landmark of its value, stated_depth as PLACE_LABEL_DEPTH), LABELS for every other."""
    if isinstance(member, Kind):
        return KIND_LABELS[member][1]
    if isinstance(member, Landmark):
        return PLACE_LABELS[member]
    if isinstance(member, Extent):
        return PLACE_LABEL_DEPTH if member is Extent.STATED_DEPTH else PLACE_LABELS[Landmark(member.value)]
    return LABELS[member]


# --- which template renders a claimed fact ------------------------------------------------------------------------------

_S, _N = FactState.SUPPORTED, FactState.NEGATED
_ACT, _STMT, _SESSION_C = ObjectClass.ACT, ObjectClass.STATEMENT, ObjectClass.SESSION
_ANAT_C, _LES_C, _ENC_C = ObjectClass.ANATOMY, ObjectClass.LESION, ObjectClass.ENCOUNTER
# (object class, attribute, state) -> the template of its real claim. A pair absent here has no form - 3.2.2's dashes -
# so a fact of that state is not claimed (Unclaimable.NO_TEMPLATE). FORMS_BY_VALUE and NEGATED_VALUES refine four rows.
FORMS: Mapping[tuple[ObjectClass, Attribute, FactState], TemplateId] = MappingProxyType({
    (_ACT, _A.KIND, _S): T.ACT_KIND, (_ACT, _A.OTHER_CLASS, _S): T.ACT_OTHER_CLASS, (_ACT, _A.STATUS, _S): T.ACT_STATUS,
    (_ACT, _A.STATUS, _N): T.ACT_STATUS_NEGATED, (_ACT, _A.DATE_RELATION, _S): T.ACT_DATE_RELATION,
    (_ACT, _A.DATE, _S): T.ACT_DATE, (_ACT, _A.PERFORMER, _S): T.ACT_PERFORMER,
    (_ACT, _A.PERFORMER, _N): T.ACT_PERFORMER_NEGATED, (_ACT, _A.PERFORMER_PERSON, _S): T.ACT_PERFORMER_PERSON,
    (_ACT, _A.ENTRY, _S): T.ACT_ENTRY, (_ACT, _A.SESSION, _S): T.ACT_SESSION,
    (_ACT, _A.TARGET_LESION, _S): T.ACT_TARGET_LESION, (_ACT, _A.TARGET_PLACES, _S): T.ACT_TARGET_PLACE,
    (_ACT, _A.TARGET_PLACES, _N): T.ACT_TARGET_PLACE_NEGATED, (_ACT, _A.TARGET_STRUCTURE, _S): T.ACT_TARGET_STRUCTURE,
    (_ACT, _A.TARGET_ANATOMY, _S): T.ACT_TARGET_ANATOMY, (_ACT, _A.TARGET_DUCT, _S): T.ACT_TARGET_DUCT,
    (_ACT, _A.TECHNIQUE_DEVICE, _S): T.ACT_DEVICE, (_ACT, _A.TECHNIQUE_DEVICE, _N): T.ACT_DEVICE_NEGATED,
    (_ACT, _A.TECHNIQUE_ROUTE, _S): T.ACT_ROUTE, (_ACT, _A.PURPOSE, _S): T.ACT_PURPOSE,
    (_ACT, _A.CAUSE, _S): T.ACT_CAUSE, (_ACT, _A.CAUSE, _N): T.ACT_CAUSE_NEGATED,
    (_ACT, _A.CAUSE_EVENT, _S): T.ACT_CAUSE_EVENT, (_ACT, _A.CAUSE_EVENT, _N): T.ACT_CAUSE_NEGATED,
    (_ACT, _A.PART_OF, _S): T.ACT_PART_OF, (_ACT, _A.PART_OF, _N): T.ACT_PART_OF_NEGATED,
    (_ACT, _A.PART_RELATION, _S): T.ACT_PART_OF, (_ACT, _A.YIELD, _S): T.ACT_YIELD,
    (_ACT, _A.YIELD, _N): T.ACT_YIELD_NEGATED, (_ACT, _A.ACCESS_OUTCOME, _S): T.ACT_ACCESS,
    (_ACT, _A.VISIT_BASIS, _S): T.VISIT_BASIS, (_ACT, _A.VISIT_SEPARATELY_IDENTIFIABLE, _S): T.VISIT_SEPARATE,
    (_ACT, _A.VISIT_SEPARATELY_IDENTIFIABLE, _N): T.VISIT_SEPARATE_NEGATED,
    (_ACT, _A.RESTATEMENTS_ROLE, _S): T.ACT_RESTATES,
    (_STMT, _A.KIND, _S): T.STMT_KIND, (_STMT, _A.STATUS, _N): T.STMT_NOT_DONE, (_STMT, _A.SESSION, _S): T.STMT_SESSION,
    (_STMT, _A.DATE_RELATION, _S): T.STMT_DATE_RELATION, (_STMT, _A.PERFORMER, _S): T.STMT_PERFORMER,
    (_STMT, _A.PERFORMER_PERSON, _S): T.STMT_PERFORMER_PERSON,
    (_STMT, _A.SCOPE_BREADTH, _S): T.STMT_BREADTH_TARGETED, (_STMT, _A.SCOPE_COVERS, _S): T.STMT_COVERS,
    (_STMT, _A.SCOPE_EXCEPTS, _S): T.STMT_BREADTH_EXCEPTIVE, (_STMT, _A.TARGET_LESION, _S): T.STMT_TARGET_LESION,
    (_STMT, _A.TARGET_PLACES, _S): T.STMT_TARGET_PLACE, (_STMT, _A.TARGET_ANATOMY, _S): T.STMT_TARGET_ANATOMY,
    (_STMT, _A.TARGET_DUCT, _S): T.STMT_TARGET_DUCT, (_STMT, _A.SCOPE_TARGETS, _S): T.STMT_TARGET_LESION,
    (_STMT, _A.SCOPE_SEGMENT, _S): T.STMT_TARGET_SEGMENT, (_STMT, _A.TECHNIQUE_DEVICE, _S): T.STMT_DEVICE,
    (_SESSION_C, _A.KIND, _S): T.SESSION_KIND, (_SESSION_C, _A.ENCOUNTER, _S): T.SESSION_ENCOUNTER,
    (_SESSION_C, _A.TRACT, _S): T.SESSION_TRACT, (_SESSION_C, _A.APPROACH, _S): T.SESSION_APPROACH,
    (_SESSION_C, _A.THROUGH, _S): T.SESSION_THROUGH, (_SESSION_C, _A.REACHED, _S): T.SESSION_REACHED,
    (_SESSION_C, _A.REACHED, _N): T.SESSION_REACHED_NEGATED,
    (_SESSION_C, _A.REACHED_ANATOMY, _S): T.SESSION_REACHED_ANATOMY,
    (_SESSION_C, _A.COMPLETION, _S): T.SESSION_COMPLETION, (_SESSION_C, _A.STATIONS, _S): T.SESSION_STATION,
    (_SESSION_C, _A.STATIONS, _N): T.SESSION_STATION_NEGATED,
    (_SESSION_C, _A.PART_OF_SESSION, _S): T.SESSION_PART_OF_SESSION,
    (_ANAT_C, _A.TYPE, _S): T.ANATOMY_TYPE, (_ANAT_C, _A.ORGAN, _S): T.ANATOMY_ORGAN_ABSENT,
    (_ANAT_C, _A.ORGAN, _N): T.ANATOMY_ORGAN_NOT_ABSENT, (_ANAT_C, _A.SUBTYPE, _S): T.ANATOMY_SUBTYPE,
    (_ANAT_C, _A.JOINS, _S): T.ANATOMY_JOINS,
    (_LES_C, _A.MULTIPLICITY, _S): T.LESION_MULTIPLICITY, (_LES_C, _A.DISTINCT_FROM, _S): T.LESION_DISTINCT,
    (_LES_C, _A.SAME_AS, _S): T.LESION_SAME,
    (_ENC_C, _A.DATE_OF_SERVICE, _S): T.ENCOUNTER_DATE,
})
# The rows whose template the value chooses: a statement's breadth.
FORMS_BY_VALUE: Mapping[tuple[ObjectClass, Attribute, FactState, Enum], TemplateId] = MappingProxyType({
    (_STMT, _A.SCOPE_BREADTH, _S, Breadth.ALL_OF_KIND): T.STMT_BREADTH_ALL,
    (_STMT, _A.SCOPE_BREADTH, _S, Breadth.EXCEPTIVE): T.STMT_BREADTH_EXCEPTIVE,
    (_STMT, _A.SCOPE_BREADTH, _S, Breadth.SINGLE_TARGET): T.STMT_BREADTH_TARGETED,
    (_STMT, _A.SCOPE_BREADTH, _S, Breadth.LISTED_TARGETS): T.STMT_BREADTH_TARGETED,
    (_STMT, _A.SCOPE_BREADTH, _S, Breadth.SEGMENT): T.STMT_BREADTH_TARGETED,
})
# A negated fact of these attributes has a form only for these values (3.2.2): the negated status is "not carried out"
# or "not done" for the performed status, the negated cause "not caused by another act of this procedure" for
# act_of_this_session.
NEGATED_VALUES: Mapping[tuple[ObjectClass, Attribute], frozenset[Enum]] = MappingProxyType({
    (_ACT, _A.STATUS): frozenset({Status.PERFORMED}),
    (_STMT, _A.STATUS): frozenset({Status.PERFORMED}),
    (_ACT, _A.CAUSE): frozenset({Cause.ACT_OF_THIS_SESSION}),
})


# --- the controls (FINAL-V2 3.2.3 [R:SC-C]) ------------------------------------------------------------------------------


@unique
class Contrary(Enum):
    """How a control's contrary value is chosen. SAME: the claim's own value (the contrary is the other polarity, or the
    rule's own form); TABLE: the value the rule's table gives (no entry: no control); FIXED: the rule's fixed value;
    ANOTHER_SESSION, ANOTHER_LESION, ANOTHER_PERSON, ANOTHER_ANATOMY: the first other object of the document, in
    document order, that a card can show and that is none of the object's own values of the attribute;
    ANOTHER_LESION_OF_SESSION: the first other lesion an act of the same session is done to; ANOTHER_POSITIVE_ACT: the
    first other act of the same session claimed performed, other than the act's own cause_event; REPORTED_ACTS: the acts
    of a kind the statement covers, claimed performed (their kind and status claimable); ANATOMY_POINT: the place an
    anatomy entry of the claimed type is (an anastomosis, a stoma or a pouch); CONTRAST: the first CONTRAST_PLACES
    candidate of the place compatible with no place of the object (DECISIONS D196); FIRST_CONTRAST: the same for a
    segment, from its first place's candidates and then its last place's, compatible with nothing of its whole range.
    Where no other object, reported act or anatomy point exists in the document, the fact has no control there (the
    claim alone decides, as 3.2.3's rows say). A contrast has no such condition: a place whose candidates are all
    compatible with the object's places is not claimed (Unclaimable.CONTROL)."""
    SAME = 'same'
    TABLE = 'table'
    FIXED = 'fixed'
    ANOTHER_SESSION = 'another_session'
    ANOTHER_LESION_OF_SESSION = 'another_lesion_of_session'
    ANOTHER_LESION = 'another_lesion'
    ANOTHER_PERSON = 'another_person'
    ANOTHER_ANATOMY = 'another_anatomy'
    ANOTHER_POSITIVE_ACT = 'another_positive_act'
    REPORTED_ACTS = 'reported_acts'
    ANATOMY_POINT = 'anatomy_point'
    CONTRAST = 'contrast'
    FIRST_CONTRAST = 'first_contrast'


@unique
class Table(Enum):
    """The control tables, each pinned with CONTROLS (2.5)."""
    KIND_SIBLINGS = 'kind_siblings'
    SESSION_SIBLINGS = 'session_siblings'
    CONTRAST_PLACES = 'contrast_places'
    DEVICE_SIBLINGS = 'device_siblings'
    TYPE_SIBLINGS = 'type_siblings'
    SUBTYPE_SIBLINGS = 'subtype_siblings'
    DATE_CONTRARY = 'date_contrary'
    PERFORMER_CONTRARY = 'performer_contrary'
    OWNER_CONTRARY = 'owner_contrary'
    OTHER_CLASS_CONTRARY = 'other_class_contrary'
    DUCT_CONTRARY = 'duct_contrary'
    ACCESS_CONTRARY = 'access_contrary'
    BASIS_CONTRARY = 'basis_contrary'
    ENCOUNTER_CONTRARY = 'encounter_contrary'
    TRACT_CONTRARY = 'tract_contrary'
    APPROACH_CONTRARY = 'approach_contrary'
    COMPLETION_CONTRARY = 'completion_contrary'
    MULTIPLICITY_CONTRARY = 'multiplicity_contrary'


# KIND_SIBLINGS: the sibling a kind claim's control asserts (an act's and a statement's alike), 3.2.3's list and the
# three DECISIONS D194 adds, each chosen outside the kind so a faithful second reading rejects it: removal/biopsy,
# intervention/examination, em_prolonged/em_visit (99417 has a READY path). The examination and the visit are decided
# through session.kind and the visit facts (3.2.3), which are controlled; moderate sedation and kind other get none, as
# no READY or exclusion path reads their kind (D194: engine/requirements reads it on the hold path only).
KIND_SIBLINGS: Mapping[Kind, Kind] = MappingProxyType({
    Kind.SNARE: Kind.EMR, Kind.EMR: Kind.SNARE, Kind.ESD: Kind.EMR, Kind.HOT_BIOPSY: Kind.BIOPSY,
    Kind.BIOPSY: Kind.HOT_BIOPSY, Kind.CLIP: Kind.INJECTION, Kind.INJECTION: Kind.CLIP, Kind.TATTOO: Kind.INJECTION,
    Kind.BLEEDING_CONTROL: Kind.CLIP, Kind.ABLATION: Kind.BLEEDING_CONTROL, Kind.DILATION: Kind.STENT,
    Kind.STENT: Kind.DILATION, Kind.BAND_LIGATION: Kind.INJECTION, Kind.STONE_EXTRACTION: Kind.LITHOTRIPSY,
    Kind.LITHOTRIPSY: Kind.STONE_EXTRACTION, Kind.STENT_REMOVAL: Kind.STENT, Kind.STENT_EXCHANGE: Kind.STENT_REMOVAL,
    Kind.SPHINCTEROTOMY: Kind.DILATION, Kind.CANNULATION: Kind.SPHINCTEROTOMY, Kind.CHOLANGIOSCOPY: Kind.CANNULATION,
    Kind.FOREIGN_BODY: Kind.STONE_EXTRACTION, Kind.PEG: Kind.TUBE_PLACEMENT, Kind.TUBE_PLACEMENT: Kind.PEG,
    Kind.TUBE_REPLACEMENT: Kind.TUBE_PLACEMENT, Kind.DECOMPRESSION: Kind.STENT, Kind.MYOTOMY: Kind.DILATION,
    Kind.FUNDOPLICATION: Kind.MYOTOMY, Kind.FNA: Kind.BIOPSY, Kind.DRAINAGE: Kind.FNA,
    Kind.CAPSULE_STUDY: Kind.EXAMINATION, Kind.MANOMETRY: Kind.PRESSURE_MEASUREMENT,
    Kind.PRESSURE_MEASUREMENT: Kind.MANOMETRY, Kind.PH_MONITORING: Kind.MANOMETRY,
    Kind.RECTAL_SENSATION: Kind.BALLOON_EXPULSION, Kind.BALLOON_EXPULSION: Kind.RECTAL_SENSATION,
    Kind.REMOVAL: Kind.BIOPSY, Kind.INTERVENTION: Kind.EXAMINATION, Kind.EM_PROLONGED: Kind.EM_VISIT,
})
# SESSION_SIBLINGS: 3.2.3's list and the five DECISIONS D196 adds (office_em/em_other, motility/reflux, reflux/motility,
# anorectal/motility, feeding_tube/egd). With them every family a code of which can be READY has a sibling; sedation's
# two codes are recognised only (D80) and em_other, other_gi and not_gi have none.
SESSION_SIBLINGS: Mapping[SessionKind, SessionKind] = MappingProxyType({
    SessionKind.COLONOSCOPY: SessionKind.FLEX_SIG, SessionKind.FLEX_SIG: SessionKind.COLONOSCOPY,
    SessionKind.EGD: SessionKind.EUS, SessionKind.EUS: SessionKind.EGD, SessionKind.ERCP: SessionKind.EGD,
    SessionKind.ENTEROSCOPY: SessionKind.EGD, SessionKind.CAPSULE: SessionKind.EGD,
    SessionKind.OFFICE_EM: SessionKind.EM_OTHER, SessionKind.MOTILITY: SessionKind.REFLUX,
    SessionKind.REFLUX: SessionKind.MOTILITY, SessionKind.ANORECTAL: SessionKind.MOTILITY,
    SessionKind.FEEDING_TUBE: SessionKind.EGD,
})
_L = Landmark
# CONTRAST_PLACES (DECISIONS D196): for each place, an ordered list of candidates, the nearest first, each a place the
# key neither is, contains nor lies in (3.2.3's "disjoint": it writes esophagus/stomach, stomach/duodenum and sigmoid
# colon/rectum, and those three pairs come first here). A place's control asserts the first candidate compatible with
# no place of the object and with nothing of a segment's whole range (Contrary.CONTRAST, FIRST_CONTRAST): a control
# naming the object's own other place, or a place inside its segment, was true by construction. A surgically made
# place and other have none: engine/anatomy.py sets them apart from nothing and puts them in no region, so no contrast
# of them is a contrary. _NEAREST holds the nearest candidates; every list then ends with CONTRAST_FALLBACK's places.
_NEAREST: Mapping[Landmark, tuple[Landmark, ...]] = MappingProxyType({
    _L.ESOPHAGUS: (_L.STOMACH, _L.GASTRIC_BODY, _L.DUODENUM, _L.JEJUNUM, _L.COLON),
    _L.PROXIMAL_ESOPHAGUS: (_L.MID_ESOPHAGUS, _L.DISTAL_ESOPHAGUS, _L.GASTRIC_BODY, _L.DUODENUM),
    _L.MID_ESOPHAGUS: (_L.DISTAL_ESOPHAGUS, _L.PROXIMAL_ESOPHAGUS, _L.GASTRIC_BODY, _L.DUODENUM),
    _L.DISTAL_ESOPHAGUS: (_L.MID_ESOPHAGUS, _L.PROXIMAL_ESOPHAGUS, _L.GASTRIC_BODY, _L.DUODENUM),
    _L.GASTROESOPHAGEAL_JUNCTION: (_L.GASTRIC_CARDIA, _L.MID_ESOPHAGUS, _L.GASTRIC_BODY, _L.DUODENUM),
    _L.STOMACH: (_L.DUODENUM, _L.MID_ESOPHAGUS, _L.JEJUNUM, _L.COLON),
    _L.GASTRIC_CARDIA: (_L.GASTRIC_FUNDUS, _L.GASTRIC_BODY, _L.MID_ESOPHAGUS, _L.GASTRIC_ANTRUM, _L.DUODENUM),
    _L.GASTRIC_FUNDUS: (_L.GASTRIC_BODY, _L.GASTRIC_CARDIA, _L.GASTRIC_ANTRUM, _L.MID_ESOPHAGUS, _L.DUODENUM),
    _L.GASTRIC_BODY: (_L.GASTRIC_ANTRUM, _L.GASTRIC_FUNDUS, _L.GASTRIC_CARDIA, _L.DUODENUM, _L.MID_ESOPHAGUS),
    _L.GASTRIC_ANTRUM: (_L.GASTRIC_BODY, _L.DUODENAL_BULB, _L.GASTRIC_FUNDUS, _L.SECOND_PORTION_DUODENUM,
                        _L.MID_ESOPHAGUS),
    _L.PYLORUS: (_L.DUODENAL_BULB, _L.GASTRIC_BODY, _L.SECOND_PORTION_DUODENUM, _L.MID_ESOPHAGUS),
    _L.DUODENUM: (_L.STOMACH, _L.JEJUNUM, _L.MID_ESOPHAGUS, _L.COLON),
    _L.DUODENAL_BULB: (_L.SECOND_PORTION_DUODENUM, _L.GASTRIC_ANTRUM, _L.THIRD_PORTION_DUODENUM, _L.GASTRIC_BODY,
                       _L.JEJUNUM),
    _L.SECOND_PORTION_DUODENUM: (_L.DUODENAL_BULB, _L.THIRD_PORTION_DUODENUM, _L.GASTRIC_ANTRUM, _L.JEJUNUM),
    _L.THIRD_PORTION_DUODENUM: (_L.SECOND_PORTION_DUODENUM, _L.FOURTH_PORTION_DUODENUM, _L.DUODENAL_BULB, _L.JEJUNUM,
                                _L.GASTRIC_BODY),
    _L.FOURTH_PORTION_DUODENUM: (_L.THIRD_PORTION_DUODENUM, _L.JEJUNUM, _L.SECOND_PORTION_DUODENUM, _L.ILEUM,
                                 _L.GASTRIC_BODY),
    _L.AMPULLA: (_L.DUODENAL_BULB, _L.THIRD_PORTION_DUODENUM, _L.GASTRIC_ANTRUM, _L.JEJUNUM),
    _L.JEJUNUM: (_L.ILEUM, _L.DUODENUM, _L.COLON, _L.STOMACH),
    _L.ILEUM: (_L.JEJUNUM, _L.CECUM, _L.ASCENDING_COLON, _L.DUODENUM, _L.STOMACH),
    _L.TERMINAL_ILEUM: (_L.CECUM, _L.JEJUNUM, _L.ASCENDING_COLON, _L.TRANSVERSE_COLON, _L.DUODENUM),
    _L.NEO_TERMINAL_ILEUM: (_L.ASCENDING_COLON, _L.JEJUNUM, _L.TRANSVERSE_COLON, _L.DUODENUM),
    _L.SMALL_BOWEL: (_L.COLON, _L.STOMACH, _L.MID_ESOPHAGUS),
    _L.COLON: (_L.RECTUM, _L.ILEUM, _L.ANAL_CANAL, _L.STOMACH),
    _L.RIGHT_COLON: (_L.TRANSVERSE_COLON, _L.TERMINAL_ILEUM, _L.DESCENDING_COLON, _L.SIGMOID_COLON, _L.RECTUM),
    _L.LEFT_COLON: (_L.TRANSVERSE_COLON, _L.RECTUM, _L.HEPATIC_FLEXURE, _L.ASCENDING_COLON, _L.CECUM),
    _L.PROXIMAL_COLON: (_L.DISTAL_COLON, _L.TERMINAL_ILEUM, _L.RECTUM, _L.STOMACH),
    _L.DISTAL_COLON: (_L.PROXIMAL_COLON, _L.RECTUM, _L.TERMINAL_ILEUM, _L.STOMACH),
    _L.CECUM: (_L.ASCENDING_COLON, _L.TERMINAL_ILEUM, _L.HEPATIC_FLEXURE, _L.TRANSVERSE_COLON, _L.RECTUM),
    # the opening of the appendix and the ileocecal valve lie side by side in the cecum, not one after the other along
    # the tract: a segment ending at either reaches the cecum around the other, so neither is the other's candidate
    _L.APPENDICEAL_ORIFICE: (_L.ASCENDING_COLON, _L.TERMINAL_ILEUM, _L.TRANSVERSE_COLON, _L.RECTUM),
    _L.ILEOCECAL_VALVE: (_L.ASCENDING_COLON, _L.TERMINAL_ILEUM, _L.HEPATIC_FLEXURE, _L.TRANSVERSE_COLON, _L.RECTUM),
    _L.ASCENDING_COLON: (_L.HEPATIC_FLEXURE, _L.CECUM, _L.TRANSVERSE_COLON, _L.TERMINAL_ILEUM, _L.DESCENDING_COLON,
                         _L.RECTUM),
    _L.HEPATIC_FLEXURE: (_L.TRANSVERSE_COLON, _L.ASCENDING_COLON, _L.SPLENIC_FLEXURE, _L.CECUM, _L.RECTUM),
    _L.TRANSVERSE_COLON: (_L.SPLENIC_FLEXURE, _L.HEPATIC_FLEXURE, _L.DESCENDING_COLON, _L.ASCENDING_COLON, _L.RECTUM,
                          _L.CECUM),
    _L.SPLENIC_FLEXURE: (_L.DESCENDING_COLON, _L.TRANSVERSE_COLON, _L.SIGMOID_COLON, _L.HEPATIC_FLEXURE, _L.RECTUM,
                         _L.CECUM),
    _L.DESCENDING_COLON: (_L.SIGMOID_COLON, _L.SPLENIC_FLEXURE, _L.TRANSVERSE_COLON, _L.RECTUM, _L.HEPATIC_FLEXURE,
                          _L.CECUM),
    _L.SIGMOID_COLON: (_L.RECTUM, _L.DESCENDING_COLON, _L.SPLENIC_FLEXURE, _L.ANAL_CANAL, _L.TRANSVERSE_COLON,
                       _L.CECUM),
    _L.RECTOSIGMOID: (_L.RECTUM, _L.DESCENDING_COLON, _L.ANAL_CANAL, _L.TRANSVERSE_COLON, _L.CECUM),
    _L.RECTUM: (_L.SIGMOID_COLON, _L.ANAL_CANAL, _L.DESCENDING_COLON, _L.TRANSVERSE_COLON, _L.CECUM),
    _L.ANAL_CANAL: (_L.RECTUM, _L.SIGMOID_COLON, _L.DESCENDING_COLON, _L.TRANSVERSE_COLON, _L.CECUM),
    _L.COMMON_BILE_DUCT: (_L.PANCREATIC_DUCT, _L.GALLBLADDER, _L.PANCREAS, _L.LIVER),
    _L.BILE_DUCT: (_L.PANCREATIC_DUCT, _L.GALLBLADDER, _L.PANCREAS, _L.LIVER),
    _L.PANCREATIC_DUCT: (_L.BILE_DUCT, _L.GALLBLADDER, _L.LIVER, _L.LYMPH_NODE),
    _L.PANCREAS: (_L.LIVER, _L.GALLBLADDER, _L.BILE_DUCT, _L.LYMPH_NODE),
    _L.GALLBLADDER: (_L.LIVER, _L.PANCREAS, _L.PANCREATIC_DUCT, _L.LYMPH_NODE),
    _L.LIVER: (_L.GALLBLADDER, _L.PANCREAS, _L.LYMPH_NODE, _L.STOMACH),
    _L.LYMPH_NODE: (_L.PANCREAS, _L.LIVER, _L.GALLBLADDER, _L.STOMACH),
})
# The places every candidate list ends with (DECISIONS D196: every place a READY or exclusion path reads is
# controlled): one in each of six regions apart from one another - the stomach, the rectum, the esophagus, the small
# bowel, the colon's first part and the liver - so an object uses up its list only when its own places reach all six,
# besides its nearest candidates. A place set of an act or a statement does so only by naming nearly the whole tract;
# such a place is then not claimed (Unclaimable.CONTROL: fail-closed), never claimed with no control.
CONTRAST_FALLBACK: tuple[Landmark, ...] = (_L.STOMACH, _L.RECTUM, _L.MID_ESOPHAGUS, _L.JEJUNUM, _L.CECUM, _L.LIVER)
CONTRAST_PLACES: Mapping[Landmark, tuple[Landmark, ...]] = MappingProxyType({
    place: nearest + tuple(far for far in CONTRAST_FALLBACK
                           if far not in nearest and not anatomy.compatible(place, far))
    for place, nearest in _NEAREST.items()})
del _L


def _tract_order() -> tuple[Landmark, ...]:
    """LANDMARKS2's places in the order a segment's whole range is read in (DECISIONS D196): a walk of engine/anatomy's
    containment, each place right after the narrowest place that holds it, the places one place holds in LANDMARKS2's
    order (contract/types: v1's order, the tract's). A place LANDMARKS2 lists apart from the place holding it is read
    where that place stands: the ampulla, listed after the fourth portion of the duodenum, inside the second portion
    that holds it (engine/anatomy.CONTAINS), so a segment of the duodenum never leaves the second portion out."""
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


# The tract's order (_tract_order), and a place's position in it.
TRACT_ORDER: tuple[Landmark, ...] = _tract_order()
_PLACE_ORDER: Mapping[Landmark, int] = MappingProxyType({place: position for position, place in enumerate(TRACT_ORDER)})
# 3.2.3's statement.device: "the sibling device of its class (cold_snare/hot_snare, cold_forceps/hot_forceps,
# balloon/wire_bougie)".
DEVICE_SIBLINGS: Mapping[Device, Device] = MappingProxyType({
    Device.COLD_SNARE: Device.HOT_SNARE, Device.HOT_SNARE: Device.COLD_SNARE, Device.COLD_FORCEPS: Device.HOT_FORCEPS,
    Device.HOT_FORCEPS: Device.COLD_FORCEPS, Device.BALLOON: Device.WIRE_BOUGIE, Device.WIRE_BOUGIE: Device.BALLOON,
})
# 3.2.3's anatomy.type: "ileal_pouch, gastric_pouch, stoma ... the sibling type (ileal_pouch/gastric_pouch,
# stoma/anastomosis)".
TYPE_SIBLINGS: Mapping[AnatomyType, AnatomyType] = MappingProxyType({
    AnatomyType.ILEAL_POUCH: AnatomyType.GASTRIC_POUCH, AnatomyType.GASTRIC_POUCH: AnatomyType.ILEAL_POUCH,
    AnatomyType.STOMA: AnatomyType.ANASTOMOSIS,
})
# 3.2.3's anatomy.subtype: each pair it lists, both ways.
SUBTYPE_SIBLINGS: Mapping[AnastomosisSubtype, AnastomosisSubtype] = MappingProxyType({
    AnastomosisSubtype.ILEOCOLIC: AnastomosisSubtype.COLOCOLIC,
    AnastomosisSubtype.COLOCOLIC: AnastomosisSubtype.ILEOCOLIC,
    AnastomosisSubtype.COLORECTAL: AnastomosisSubtype.COLOANAL,
    AnastomosisSubtype.COLOANAL: AnastomosisSubtype.COLORECTAL,
    AnastomosisSubtype.ILEORECTAL: AnastomosisSubtype.ILEOANAL,
    AnastomosisSubtype.ILEOANAL: AnastomosisSubtype.ILEORECTAL,
    AnastomosisSubtype.GASTROJEJUNAL: AnastomosisSubtype.GASTRODUODENAL,
    AnastomosisSubtype.GASTRODUODENAL: AnastomosisSubtype.GASTROJEJUNAL,
    AnastomosisSubtype.ESOPHAGOJEJUNAL: AnastomosisSubtype.ESOPHAGOGASTRIC,
    AnastomosisSubtype.ESOPHAGOGASTRIC: AnastomosisSubtype.ESOPHAGOJEJUNAL,
    AnastomosisSubtype.HEPATICOJEJUNAL: AnastomosisSubtype.CHOLEDOCHODUODENAL,
    AnastomosisSubtype.CHOLEDOCHODUODENAL: AnastomosisSubtype.HEPATICOJEJUNAL,
})
# The contrary values 3.2.3 writes for the other controlled attributes.
CONTRARY: Mapping[Table, Mapping[Enum, Enum]] = MappingProxyType({
    Table.DATE_CONTRARY: MappingProxyType({  # on_date_of_service / earlier or later
        DateRelation.ON_DATE_OF_SERVICE: DateRelation.EARLIER_DATE,
        DateRelation.EARLIER_DATE: DateRelation.ON_DATE_OF_SERVICE,
        DateRelation.LATER_DATE: DateRelation.ON_DATE_OF_SERVICE}),
    Table.PERFORMER_CONTRARY: MappingProxyType({  # documenting_team / other_*
        Performer.DOCUMENTING_TEAM: Performer.OTHER_CLINICIAN, Performer.OTHER_CLINICIAN: Performer.DOCUMENTING_TEAM,
        Performer.OTHER_FACILITY: Performer.DOCUMENTING_TEAM}),
    Table.OWNER_CONTRARY: MappingProxyType({  # nursing for the documenting clinician; the documenting clinician otherwise
        Owner.DOCUMENTING_CLINICIAN: Owner.NURSING,
        **{owner: Owner.DOCUMENTING_CLINICIAN for owner in Owner if owner is not Owner.DOCUMENTING_CLINICIAN}}),
    Table.OTHER_CLASS_CONTRARY: MappingProxyType({  # procedure against evaluation; every other class against procedure
        OtherClass.PROCEDURE: OtherClass.EVALUATION,
        **{other: OtherClass.PROCEDURE for other in OtherClass if other is not OtherClass.PROCEDURE}}),
    Table.DUCT_CONTRARY: MappingProxyType({  # DECISIONS D196: biliary/pancreatic, pancreatic/biliary, cystic/pancreatic
        Duct.BILIARY: Duct.PANCREATIC, Duct.PANCREATIC: Duct.BILIARY, Duct.CYSTIC: Duct.PANCREATIC}),
    Table.ACCESS_CONTRARY: MappingProxyType({  # achieved / failed: the failed form / the achieved form; D196:
        # achieved_after_failed_attempts takes the failed form
        AccessOutcome.ACHIEVED: AccessOutcome.FAILED, AccessOutcome.FAILED: AccessOutcome.ACHIEVED,
        AccessOutcome.ACHIEVED_AFTER_FAILED_ATTEMPTS: AccessOutcome.FAILED}),
    Table.BASIS_CONTRARY: MappingProxyType({  # the other basis
        EmBasis.TOTAL_TIME: EmBasis.MEDICAL_DECISION_MAKING, EmBasis.MEDICAL_DECISION_MAKING: EmBasis.TOTAL_TIME}),
    Table.ENCOUNTER_CONTRARY: MappingProxyType({  # the opposite value
        EncounterRelation.THIS_ENCOUNTER: EncounterRelation.SEPARATE_ENCOUNTER,
        EncounterRelation.SEPARATE_ENCOUNTER: EncounterRelation.THIS_ENCOUNTER}),
    Table.TRACT_CONTRARY: MappingProxyType({Tract.UPPER: Tract.LOWER, Tract.LOWER: Tract.UPPER}),  # upper against lower
    Table.APPROACH_CONTRARY: MappingProxyType({  # oral against through_stoma or through_pouch
        Approach.ORAL: Approach.THROUGH_STOMA, Approach.THROUGH_STOMA: Approach.ORAL,
        Approach.THROUGH_POUCH: Approach.ORAL}),
    Table.COMPLETION_CONTRARY: MappingProxyType({  # complete against incomplete or terminated
        Completion.COMPLETE: Completion.INCOMPLETE, Completion.INCOMPLETE: Completion.COMPLETE,
        Completion.TERMINATED: Completion.COMPLETE}),
    Table.MULTIPLICITY_CONTRARY: MappingProxyType({  # the other value
        Multiplicity.SINGLE: Multiplicity.GROUP, Multiplicity.GROUP: Multiplicity.SINGLE}),
})


def table(name: Table) -> Mapping[Enum, Enum]:
    """The value-to-value control table ``name``: a sibling table, or one of CONTRARY's. CONTRAST_PLACES, whose values
    are lists of candidates, is read by ``contrast_candidates``; KeyError for it here."""
    siblings: dict[Table, Mapping[Enum, Enum]] = {
        Table.KIND_SIBLINGS: cast(Mapping[Enum, Enum], KIND_SIBLINGS),
        Table.SESSION_SIBLINGS: cast(Mapping[Enum, Enum], SESSION_SIBLINGS),
        Table.DEVICE_SIBLINGS: cast(Mapping[Enum, Enum], DEVICE_SIBLINGS),
        Table.TYPE_SIBLINGS: cast(Mapping[Enum, Enum], TYPE_SIBLINGS),
        Table.SUBTYPE_SIBLINGS: cast(Mapping[Enum, Enum], SUBTYPE_SIBLINGS)}
    return siblings[name] if name in siblings else CONTRARY[name]


def segment_range(first: Landmark, last: Landmark) -> tuple[Landmark, ...]:
    """A segment's whole range (DECISIONS D196), in TRACT_ORDER, whichever end the segment names first: its two places,
    and every place between them all of whose places (engine/anatomy.CONTAINS) are between them too - the second
    portion of the duodenum with the ampulla it holds. A place between them that holds one beyond an end (the duodenum
    in a segment ending at its third portion, the colon in one from the ileum to the cecum) reaches outside the segment,
    so it is left out: a candidate it holds may lie outside the segment, and one holding it holds a place of the range
    too, so it is rejected through that place."""
    one, other = sorted((_PLACE_ORDER[first], _PLACE_ORDER[last]))

    def between(place: Landmark) -> bool:
        return one <= _PLACE_ORDER[place] <= other

    return tuple(place for place in TRACT_ORDER if between(place) and (
        place is first or place is last or all(between(inner) for inner in anatomy.CONTAINS[place])))


def contrast_candidates(places: Sequence[Landmark]) -> tuple[Landmark, ...]:
    """The CONTRAST_PLACES candidates of ``places`` (a place's control: its own list; a segment's: its first place's
    nearest candidates, then its last place's, then the fallback places their lists end with), each once, in order."""
    found: list[Landmark] = []
    for place in places:
        found += [candidate for candidate in _NEAREST.get(place, ()) if candidate not in found]
    for place in places:
        found += [candidate for candidate in CONTRAST_PLACES.get(place, ()) if candidate not in found]
    return tuple(found)


def contrast(candidates: Iterable[Landmark], avoid: Iterable[Landmark]) -> Landmark | None:
    """The first of ``candidates`` compatible (engine/anatomy.compatible: the same place, or one containing the other)
    with none of ``avoid`` - every place of the object, and a segment's whole range (DECISIONS D196); None when every
    candidate is (the builder then leaves the place unclaimed: Unclaimable.CONTROL)."""
    avoided = tuple(avoid)
    return next((candidate for candidate in candidates
                 if not any(anatomy.compatible(candidate, place) for place in avoided)), None)


@dataclass(frozen=True, slots=True)
class ControlRule:
    """One row of CONTROLS (3.2.3): a claimed fact of ``object_class``'s ``attribute`` in ``state`` - of one of
    ``values`` (None: any) and, for an event, of one of ``kinds`` (None: any) - is controlled by the real-claim form of
    (``as_attribute``, ``as_state``, the contrary value ``contrary`` chooses), each defaulting to the fact's own, or by
    ``form`` where the control has a form of its own (3.2.3's three) or another class's real-claim form (a performed
    act's statement form, DECISIONS D196). ``table`` and ``fixed`` parameterise TABLE, FIXED, CONTRAST and
    FIRST_CONTRAST."""
    object_class: ObjectClass
    attribute: Attribute
    state: FactState
    contrary: Contrary
    values: frozenset[Enum] | None = None
    kinds: frozenset[Kind] | None = None
    as_attribute: Attribute | None = None
    as_state: FactState | None = None
    table: Table | None = None
    fixed: Enum | None = None
    form: TemplateId | None = None


_CR = ControlRule
# 3.2.3's table, row for row, as DECISIONS D194-D196 complete it: a performed act's control in the statement form; the
# places of every kind (the contrast rule); the duct; the statement's person (D195); session.through; the access
# outcome's third value (ACCESS_CONTRARY); the session siblings (SESSION_SIBLINGS).
CONTROLS: tuple[ControlRule, ...] = (
    _CR(_ACT, _A.STATUS, _S, Contrary.SAME, frozenset({Status.PERFORMED}), as_state=_N, form=T.STMT_NOT_DONE),
    _CR(_ACT, _A.STATUS, _S, Contrary.FIXED, frozenset({Status.ATTEMPTED_NOT_COMPLETED, Status.PLANNED}),
        fixed=Status.PERFORMED),
    _CR(_ACT, _A.DATE_RELATION, _S, Contrary.TABLE, table=Table.DATE_CONTRARY),
    _CR(_ACT, _A.PERFORMER, _S, Contrary.TABLE, table=Table.PERFORMER_CONTRARY),
    _CR(_ACT, _A.PERFORMER_PERSON, _S, Contrary.ANOTHER_PERSON),
    _CR(_ACT, _A.ENTRY, _S, Contrary.TABLE, table=Table.OWNER_CONTRARY),
    _CR(_ACT, _A.RESTATEMENTS_ROLE, _S, Contrary.SAME, frozenset({RestatementRole.RESTATES}),
        form=T.ACT_RESTATES_SUMMARY),
    _CR(_ACT, _A.SESSION, _S, Contrary.ANOTHER_SESSION),
    _CR(_ACT, _A.KIND, _S, Contrary.TABLE, table=Table.KIND_SIBLINGS),
    _CR(_ACT, _A.OTHER_CLASS, _S, Contrary.TABLE, table=Table.OTHER_CLASS_CONTRARY),
    _CR(_ACT, _A.TARGET_PLACES, _S, Contrary.CONTRAST, table=Table.CONTRAST_PLACES),
    _CR(_ACT, _A.TARGET_LESION, _S, Contrary.ANOTHER_LESION_OF_SESSION),
    _CR(_ACT, _A.TARGET_DUCT, _S, Contrary.TABLE, table=Table.DUCT_CONTRARY),
    _CR(_ACT, _A.TECHNIQUE_DEVICE, _S, Contrary.SAME, frozenset(catalogue.TECHNIQUE_CLASS), as_state=_N),
    _CR(_ACT, _A.TECHNIQUE_ROUTE, _S, Contrary.FIXED, frozenset({Route.EUS_TRANSMURAL}), fixed=Route.SUBMUCOSAL),
    _CR(_ACT, _A.TARGET_STRUCTURE, _S, Contrary.FIXED, frozenset({Structure.PANCREATIC_FLUID_COLLECTION}),
        fixed=Structure.WALL),
    _CR(_ACT, _A.PURPOSE, _S, Contrary.FIXED, frozenset({Purpose.HEMOSTASIS}), fixed=Purpose.PROPHYLAXIS),
    _CR(_ACT, _A.CAUSE, _S, Contrary.ANOTHER_POSITIVE_ACT,
        frozenset(cause for cause in Cause if cause is not Cause.ACT_OF_THIS_SESSION), as_attribute=_A.CAUSE_EVENT),
    _CR(_ACT, _A.YIELD, _S, Contrary.SAME, as_state=_N),
    _CR(_ACT, _A.YIELD, _N, Contrary.FIXED, as_state=_S, fixed=Material.STONES),
    _CR(_ACT, _A.ACCESS_OUTCOME, _S, Contrary.TABLE, table=Table.ACCESS_CONTRARY),
    _CR(_ACT, _A.VISIT_BASIS, _S, Contrary.TABLE, table=Table.BASIS_CONTRARY),
    _CR(_ACT, _A.VISIT_SEPARATELY_IDENTIFIABLE, _S, Contrary.SAME, as_state=_N),
    _CR(_ACT, _A.VISIT_SEPARATELY_IDENTIFIABLE, _N, Contrary.SAME, as_state=_S),
    _CR(_STMT, _A.STATUS, _N, Contrary.SAME, frozenset({Status.PERFORMED}), form=T.STMT_DONE),
    _CR(_STMT, _A.KIND, _S, Contrary.TABLE, table=Table.KIND_SIBLINGS),
    _CR(_STMT, _A.DATE_RELATION, _S, Contrary.TABLE, table=Table.DATE_CONTRARY),
    _CR(_STMT, _A.SESSION, _S, Contrary.ANOTHER_SESSION),
    _CR(_STMT, _A.PERFORMER, _S, Contrary.TABLE, table=Table.PERFORMER_CONTRARY),
    _CR(_STMT, _A.PERFORMER_PERSON, _S, Contrary.ANOTHER_PERSON),
    _CR(_STMT, _A.TARGET_PLACES, _S, Contrary.CONTRAST, table=Table.CONTRAST_PLACES),
    _CR(_STMT, _A.SCOPE_SEGMENT, _S, Contrary.FIRST_CONTRAST, as_attribute=_A.TARGET_PLACES,
        table=Table.CONTRAST_PLACES),
    _CR(_STMT, _A.TARGET_LESION, _S, Contrary.ANOTHER_LESION),
    _CR(_STMT, _A.SCOPE_TARGETS, _S, Contrary.ANOTHER_LESION, as_attribute=_A.TARGET_LESION),
    _CR(_STMT, _A.SCOPE_BREADTH, _S, Contrary.FIXED, frozenset({Breadth.EXCEPTIVE}), fixed=Breadth.ALL_OF_KIND),
    _CR(_STMT, _A.SCOPE_BREADTH, _S, Contrary.REPORTED_ACTS, frozenset({Breadth.ALL_OF_KIND})),
    _CR(_STMT, _A.SCOPE_EXCEPTS, _S, Contrary.SAME, as_attribute=_A.SCOPE_COVERS),
    _CR(_STMT, _A.TECHNIQUE_DEVICE, _S, Contrary.TABLE, table=Table.DEVICE_SIBLINGS),
    _CR(_SESSION_C, _A.KIND, _S, Contrary.TABLE, table=Table.SESSION_SIBLINGS),
    _CR(_SESSION_C, _A.ENCOUNTER, _S, Contrary.TABLE, table=Table.ENCOUNTER_CONTRARY),
    _CR(_SESSION_C, _A.TRACT, _S, Contrary.TABLE, table=Table.TRACT_CONTRARY),
    _CR(_SESSION_C, _A.APPROACH, _S, Contrary.TABLE, table=Table.APPROACH_CONTRARY),
    _CR(_SESSION_C, _A.THROUGH, _S, Contrary.ANOTHER_ANATOMY),
    _CR(_SESSION_C, _A.REACHED, _S, Contrary.SAME, as_state=_N),
    _CR(_SESSION_C, _A.REACHED, _N, Contrary.SAME, as_state=_S),
    _CR(_SESSION_C, _A.REACHED_ANATOMY, _S, Contrary.ANATOMY_POINT, as_attribute=_A.REACHED, as_state=_N),
    _CR(_SESSION_C, _A.COMPLETION, _S, Contrary.TABLE, table=Table.COMPLETION_CONTRARY),
    _CR(_SESSION_C, _A.STATIONS, _S, Contrary.SAME, as_state=_N),
    _CR(_SESSION_C, _A.STATIONS, _N, Contrary.SAME, as_state=_S),
    _CR(_ANAT_C, _A.TYPE, _S, Contrary.TABLE,
        frozenset({AnatomyType.ILEAL_POUCH, AnatomyType.GASTRIC_POUCH, AnatomyType.STOMA}), table=Table.TYPE_SIBLINGS),
    _CR(_ANAT_C, _A.ORGAN, _S, Contrary.SAME, as_state=_N),
    _CR(_ANAT_C, _A.SUBTYPE, _S, Contrary.TABLE, table=Table.SUBTYPE_SIBLINGS),
    _CR(_LES_C, _A.MULTIPLICITY, _S, Contrary.TABLE, table=Table.MULTIPLICITY_CONTRARY),
    _CR(_LES_C, _A.DISTINCT_FROM, _S, Contrary.SAME, as_attribute=_A.SAME_AS),
)
del _CR


@unique
class Why(Enum):
    """Why an attribute is decided by a single verdict (UNCONTROLLED, 3.2.3; R7 and 3.6(3) cite the list)."""
    LITERAL_CHECKED = 'literal_checked'  # L1 checks it against its own literal; only the controlled relation decides
    NO_SINGLE_CONTRARY = 'no_single_contrary'  # L1 and the member date's precedence check it; no natural contrary
    ONLY_HOLDS = 'only_holds'  # it only bundles or explains, so a yes-bias can only hold
    ONLY_UNRESOLVES = 'only_unresolves'  # it can only turn INDEPENDENT into UNRESOLVED
    ONLY_JOINS = 'only_joins'  # it only joins, and joining bundles or holds
    # DECISIONS D196: session.through with a single anatomy entry, no other entry to name; the class fit also needs the
    # approach and the entry's type, both controlled. With another entry its control names it (ANOTHER_ANATOMY).
    ONE_ANATOMY_ENTRY = 'one_anatomy_entry'


@dataclass(frozen=True, slots=True)
class Uncontrolled:
    """One UNCONTROLLED entry: ``attribute`` of ``object_class``, for ``values`` (None: every value), and why a single
    verdict there can only hold."""
    object_class: ObjectClass
    attribute: Attribute
    why: Why
    values: frozenset[Enum] | None = None


# 3.2.3's UNCONTROLLED, closed (P-CONTROLLED keeps it so): each attribute decided by a single verdict, with its reason.
# DECISIONS D196 adds session.through with a single anatomy entry, and session.part_of_session (it only bundles,
# base_within, and its absence is read by possibly: engine/requirements reads it on the hold path).
UNCONTROLLED: tuple[Uncontrolled, ...] = (
    Uncontrolled(_ACT, _A.DATE, Why.LITERAL_CHECKED),
    Uncontrolled(_ENC_C, _A.DATE_OF_SERVICE, Why.NO_SINGLE_CONTRARY),
    Uncontrolled(_ACT, _A.PART_OF, Why.ONLY_HOLDS),
    Uncontrolled(_ACT, _A.PART_RELATION, Why.ONLY_HOLDS),
    Uncontrolled(_ACT, _A.PURPOSE, Why.ONLY_HOLDS,
                 frozenset(purpose for purpose in Purpose if purpose is not Purpose.HEMOSTASIS)),
    Uncontrolled(_STMT, _A.SCOPE_COVERS, Why.ONLY_UNRESOLVES),
    Uncontrolled(_LES_C, _A.SAME_AS, Why.ONLY_JOINS),
    Uncontrolled(_SESSION_C, _A.THROUGH, Why.ONE_ANATOMY_ENTRY),
    Uncontrolled(_SESSION_C, _A.PART_OF_SESSION, Why.ONLY_HOLDS),
)


def control_rule(object_class: ObjectClass, attribute: Attribute, state: FactState, value: Enum | None,
                 kind: Kind | None = None) -> ControlRule | None:
    """The CONTROLS row for a claimed fact, None when the fact has none. A row whose contrary another object of the
    document gives (ANOTHER_*, REPORTED_ACTS) still yields no control where the document has no such object; a row
    may also be on UNCONTROLLED for that case (session.through with one anatomy entry, D196)."""
    for rule in CONTROLS:
        if (rule.object_class is object_class and rule.attribute is attribute and rule.state is state
                and (rule.values is None or value in rule.values)
                and (rule.kinds is None or kind in rule.kinds)):
            return rule
    return None


def uncontrolled(object_class: ObjectClass, attribute: Attribute, value: Enum | None = None) -> Uncontrolled | None:
    """The UNCONTROLLED entry for an attribute (and, for an entry listing values, a value it lists), None when it is
    not on the list."""
    for entry in UNCONTROLLED:
        if (entry.object_class is object_class and entry.attribute is attribute
                and (entry.values is None or value is None or value in entry.values)):
            return entry
    return None


# --- what the claims are built from ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Basis:
    """What ``build`` reads: pass 1's answer and the geometry the caller computed from the revision with contract/
    segment.py and contract/geometry.py (this module touches no text).

    answer: pass 1's answer, read (contract/extract_read.read). units: the revision's units (segment.units), ids and
    offsets only. findings: every check finding on a fact beyond the reader's own (geometry's I2, I3, G1-G6;
    consistency's K1-K8 and L1; the cross-object rules), by the fact's key (for an act's inherited fact, the act's key
    of that attribute); a fact with any finding is never claimed. closures: the sentence closure (1.2 rule 6) of each
    run of units the answer cites, by the run; a run with none (it fails I1 or I3) is never cited. sections: each
    event's containing section, by event id, when its anchor is attached to it (1.5, G4); an event absent here inherits
    nothing. restatement_sections: the section each restatement lies in, by (event id, its index), when attached.
    anchor_words: each event's located kind words and status words, by event id (None for words '' or not located)."""
    answer: ReadAnswer
    units: tuple[Unit, ...]
    findings: Mapping[FactKey, tuple[Reason, ...]] = field(default_factory=dict)
    closures: Mapping[tuple[str, ...], tuple[str, ...]] = field(default_factory=dict)
    sections: Mapping[str, str] = field(default_factory=dict)
    restatement_sections: Mapping[tuple[str, int], str] = field(default_factory=dict)
    anchor_words: Mapping[str, tuple[Span | None, Span | None]] = field(default_factory=dict)


# --- what build gives ---------------------------------------------------------------------------------------------------


@unique
class Unclaimable(Enum):
    """Why a fact CLAIMED lists, that passed its checks, still got no claim; settle reads it as unappraised (3.3 row
    6). NO_TEMPLATE: 3.2.2 gives its state or value no form (a dash). KIND: its statement-phrased sentence names the
    statement's kind, which is not itself claimed. PARTNER: its sentence needs another fact that is not claimed
    (part_of and part_relation; a breadth's session, excepted acts, targets or segment; an anastomosis's type). UNITS: a
    run it must cite has no sentence closure. REFERENCE: an object its sentence names has no card. CONTROL: its control
    (3.2.3) exists in the document but cannot be written without a fact that is not claimable - a performed act's
    statement-form control names its kind, an all_of_kind breadth's names the reported acts of its kind (their kind and
    status), an exceptive breadth's names its session - or, for a place, every contrast candidate is compatible with
    one of the object's places: the claim would stand uncontrolled, so it is not made (fail-closed), and the facts
    sharing its claim go with it (PARTNER). CONTRARY: its control would assert what another claim about the same object
    asserts, or its claim is what another fact's control asserts (pass 1 gives a value and its contrary): neither is
    claimed (DECISIONS D196)."""
    NO_TEMPLATE = 'no_template'
    KIND = 'kind'
    PARTNER = 'partner'
    UNITS = 'units'
    REFERENCE = 'reference'
    CONTROL = 'control'
    CONTRARY = 'contrary'


@dataclass(frozen=True, slots=True)
class Appraised:
    """A fact of pass 1 and the claims that appraise it: key, where the fact is (for an act's inherited fact, the act's
    key of that attribute; a scope list's member, its key); inherited_from, the section it was taken from (an effective
    date relation, performer or performer_person, or the act's entry), None for the object's own fact; state and value,
    the fact's; claim, the id of its claim; control, the id of its contrary control, None for an attribute on
    UNCONTROLLED or when no contrary exists in this document (the claim alone decides: 3.2.3's coherence table)."""
    key: FactKey
    inherited_from: str | None
    state: FactState
    value: str
    claim: str
    control: str | None


@dataclass(frozen=True, slots=True)
class PairControl:
    """A pair control (3.2.3 [R:SC-B]): claim, its id; subject, the object it asks about (family, id); other, the
    object whose place or lesion it asks; attribute, TARGET_PLACES or TARGET_LESION; value, the place or the lesion id.
    A difference of place or lesion between the two counts only when every such control on each side was rejected."""
    claim: str
    subject: tuple[xs.Family, str]
    other: tuple[xs.Family, str]
    attribute: Attribute
    value: str


@dataclass(frozen=True, slots=True)
class Completeness:
    """The completeness claim of an upper EUS session whose station list is empty (3.2.2 [R:SC-B]): session, its id;
    claim and control, the two claims' ids."""
    session: str
    claim: str
    control: str


@dataclass(frozen=True, slots=True)
class Unclaimed:
    """A fact CLAIMED lists that passed its checks and got no claim, and why."""
    key: FactKey
    inherited_from: str | None
    why: Unclaimable


@dataclass(frozen=True)
class ClaimSet:
    """The claims of one request (2.4): cards, in card order; claims, in the seeded order (K1..); sentences and about,
    each claim's sentence and the card it is about (a claim about the encounter names none: ''); appraised,
    pair_controls and completeness, which claim appraises what (settle's input); unclaimed; objects, each card's object
    (family, id); controls, the ids of the claims that serve as a control - a contrary control, a pair control or a
    completeness control - never the id of a real claim (DECISIONS D196: a control never asserts what a real claim
    about the same object asserts, and build() asserts it); seed, the order's seed."""
    cards: tuple[Card, ...]
    claims: tuple[Claim, ...]
    sentences: Mapping[str, str]
    about: Mapping[str, str]
    appraised: tuple[Appraised, ...]
    pair_controls: tuple[PairControl, ...]
    completeness: tuple[Completeness, ...]
    unclaimed: tuple[Unclaimed, ...]
    objects: Mapping[str, tuple[xs.Family, str]]
    controls: frozenset[str]
    seed: str

    def claim(self, claim_id: str) -> Claim | None:
        """The claim of that id, None when the set has none."""
        return next((item for item in self.claims if item.id == claim_id), None)

    def card(self, card_id: str) -> Card | None:
        """The card of that id, None when the set has none."""
        return next((item for item in self.cards if item.id == card_id), None)

    def canonical(self) -> list[list[object]]:
        """The claim list's canonical form: [id, template, subject, value, units, content] per claim, in order."""
        return [[item.id, item.template, item.subject, item.value, list(item.units), item.content]
                for item in self.claims]

    def sha256(self) -> str:
        """The claim list's sha256 (1.7: among the EventInventory row's bindings [R:MO-5])."""
        return jsonschema.sha256_of(self.canonical())


def over_bound(claim_set: ClaimSet) -> bool:
    """Whether ``claim_set`` holds more claims than CLAIM_BOUND (1.8): such a set is never sent (7.4 door 0, 7.5)."""
    return len(claim_set.claims) > CLAIM_BOUND


# --- building ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ref:
    """An object a sentence names: rendered as its card's id."""
    family: xs.Family
    object: str


@dataclass(frozen=True, slots=True)
class _Named:
    """A breadth's target as its sentence names it: a noun (lesion, lesions) and the lesions' cards."""
    noun: str
    refs: tuple[Ref, ...]


_Value = str | Ref | tuple[Ref, ...] | _Named


@dataclass(frozen=True, slots=True)
class _Spec:
    """A claim before it is numbered: its template, the object it is about, the value it claims, the units it cites,
    every other parameter its sentence renders (pass 1's ids, values and unit ids) and its slots' values."""
    template: TemplateId
    subject: Ref
    value: str
    units: tuple[str, ...]
    params: tuple[str, ...]
    slots: tuple[tuple[Slot, _Value], ...]

    def content(self) -> str:
        """The content key (3.2.4 [R:MO-5])."""
        return jsonschema.sha256_of([self.template.value, self.subject.family.value, self.subject.object, self.value,
                                     list(self.units), list(self.params)])

    def assertion(self) -> tuple[TemplateId, Ref, tuple[tuple[Slot, _Value], ...]]:
        """What the spec asserts, whatever units it cites: its template, the object it is about and its filled slots -
        two specs with one assertion render one sentence about one card (DECISIONS D196: a control never asserts
        what a real claim about the same object asserts)."""
        return (self.template, self.subject, self.slots)

    def refs(self) -> tuple[Ref, ...]:
        """The subject and every object the sentence names."""
        found = [self.subject]
        for _slot, value in self.slots:
            if isinstance(value, Ref):
                found.append(value)
            elif isinstance(value, tuple):
                found += value
            elif isinstance(value, _Named):
                found += value.refs
        return tuple(found)


@dataclass(frozen=True, slots=True)
class _Fact:
    """One claimable fact (own, inherited or a scope member): where it is, its state, value and sources."""
    key: FactKey
    state: FactState
    value: str
    sources: tuple[Source, ...]
    inherited_from: str | None = None


_CARD_TYPE: Mapping[xs.Family, CardType] = MappingProxyType({
    Family.EVENT: CardType.ACT, Family.SESSION: CardType.SESSION, Family.SECTION: CardType.SECTION,
    Family.LESION: CardType.LESION, Family.ANATOMY: CardType.ANATOMY})
_CARD_ORDER = (CardType.ACT, CardType.SESSION, CardType.SECTION, CardType.LESION, CardType.ANATOMY)
_INHERITED_FROM: Mapping[Attribute, Attribute] = MappingProxyType({
    _A.DATE_RELATION: _A.OCCASION, _A.PERFORMER: _A.PERFORMER, _A.PERFORMER_PERSON: _A.PERFORMER_PERSON})
_FAMILY_OF: Mapping[ObjectClass, xs.Family] = MappingProxyType({
    _ACT: Family.EVENT, _STMT: Family.EVENT, _SESSION_C: Family.SESSION, _ANAT_C: Family.ANATOMY,
    _LES_C: Family.LESION, _ENC_C: Family.ENCOUNTER})
_ENUM_OF: Mapping[tuple[xs.Family, Attribute], type[Enum]] = MappingProxyType({
    (family, item.attribute): item.values for family in Family for item in xs.ATTRIBUTES[family]
    if item.values is not None})
# The single-label templates: the slot each fills with its value's label.
_LABEL_SLOT: Mapping[TemplateId, Slot] = MappingProxyType({
    T.ACT_KIND: Slot.KIND_A, T.ACT_OTHER_CLASS: Slot.OTHER_CLASS, T.ACT_STATUS: Slot.STATUS,
    T.ACT_DATE_RELATION: Slot.DATE_RELATION, T.STMT_DATE_RELATION: Slot.DATE_RELATION, T.ACT_PERFORMER: Slot.PERFORMER, T.ACT_PERFORMER_NEGATED: Slot.PERFORMER,
    T.ACT_TARGET_STRUCTURE: Slot.STRUCTURE, T.ACT_DEVICE: Slot.DEVICE, T.ACT_DEVICE_NEGATED: Slot.DEVICE,
    T.ACT_ROUTE: Slot.ROUTE, T.ACT_PURPOSE: Slot.PURPOSE, T.ACT_CAUSE: Slot.CAUSE, T.ACT_YIELD: Slot.MATERIAL,
    T.ACT_ACCESS: Slot.ACCESS, T.VISIT_BASIS: Slot.BASIS, T.SESSION_KIND: Slot.FAMILY,
    T.SESSION_ENCOUNTER: Slot.ENCOUNTER, T.SESSION_TRACT: Slot.TRACT, T.SESSION_APPROACH: Slot.APPROACH,
    T.SESSION_COMPLETION: Slot.COMPLETION, T.ANATOMY_SUBTYPE: Slot.SUBTYPE, T.LESION_MULTIPLICITY: Slot.MULTIPLICITY,
    T.STMT_PERFORMER: Slot.PERFORMER, T.STMT_DEVICE: Slot.DEVICE, T.ACT_TARGET_PLACE: Slot.PLACE,
    T.ACT_TARGET_PLACE_NEGATED: Slot.PLACE, T.STMT_TARGET_PLACE: Slot.PLACE, T.ANATOMY_JOINS: Slot.PLACE,
    T.SESSION_REACHED: Slot.POINT, T.SESSION_REACHED_NEGATED: Slot.POINT, T.SESSION_STATION: Slot.STATION,
    T.SESSION_STATION_NEGATED: Slot.STATION, T.ANATOMY_ORGAN_ABSENT: Slot.ORGAN, T.ANATOMY_ORGAN_NOT_ABSENT: Slot.ORGAN,
    T.ACT_TARGET_DUCT: Slot.DUCT, T.STMT_TARGET_DUCT: Slot.DUCT, T.ANATOMY_TYPE: Slot.TYPE})
# The templates naming one object, the slot it fills, and the object's family.
_REF_SLOT: Mapping[TemplateId, tuple[Slot, xs.Family]] = MappingProxyType({
    T.ACT_SESSION: (Slot.SESSION, Family.SESSION), T.STMT_SESSION: (Slot.SESSION, Family.SESSION),
    T.ACT_TARGET_LESION: (Slot.LESION, Family.LESION), T.STMT_TARGET_LESION: (Slot.LESION, Family.LESION),
    T.ACT_TARGET_ANATOMY: (Slot.ANATOMY, Family.ANATOMY), T.STMT_TARGET_ANATOMY: (Slot.ANATOMY, Family.ANATOMY),
    T.SESSION_THROUGH: (Slot.ANATOMY, Family.ANATOMY), T.SESSION_REACHED_ANATOMY: (Slot.ANATOMY, Family.ANATOMY),
    T.SESSION_PART_OF_SESSION: (Slot.OTHER, Family.SESSION), T.ACT_CAUSE_EVENT: (Slot.ACT, Family.EVENT),
    T.STMT_COVERS: (Slot.ACT, Family.EVENT), T.ACT_PART_OF_NEGATED: (Slot.ACT, Family.EVENT),
    T.LESION_DISTINCT: (Slot.OTHER, Family.LESION), T.LESION_SAME: (Slot.OTHER, Family.LESION)})
# The anatomy entries' forms that say what kind of anatomy entry it is, so its type must be claimed with them.
_TYPED_FORMS: frozenset[TemplateId] = frozenset({T.ANATOMY_ORGAN_ABSENT, T.ANATOMY_ORGAN_NOT_ABSENT,
                                                 T.ANATOMY_SUBTYPE, T.ANATOMY_JOINS})
# REACHED_ANATOMY's control: the place an anatomy entry of each type is (3.2.3 "the {point at anatomy Y}").
ANATOMY_POINT: Mapping[AnatomyType, Extent] = MappingProxyType({
    AnatomyType.ANASTOMOSIS: Extent.ANASTOMOSIS, AnatomyType.STOMA: Extent.STOMA, AnatomyType.ILEAL_POUCH: Extent.POUCH,
    AnatomyType.GASTRIC_POUCH: Extent.POUCH})
_TARGETED = frozenset({Breadth.SINGLE_TARGET, Breadth.LISTED_TARGETS, Breadth.SEGMENT})


def build(basis: Basis, seed: str) -> ClaimSet:
    """The claims of one request from pass 1's answer and its geometry (``basis``), ordered by ``seed`` (the module's
    docstring). Pure: equal arguments give an equal ClaimSet in every process (no set or hash order is read)."""
    return _Builder(basis, seed).run()


class _Builder:
    """One build: the answer's indexes, the specs gathered, and their numbering."""

    def __init__(self, basis: Basis, seed: str) -> None:
        self.basis = basis
        self.seed = seed
        answer = basis.answer
        self.position = {unit.id: index for index, unit in enumerate(basis.units)}
        self.facts: dict[tuple[xs.Family, str, Attribute], list[ReadFact]] = {}
        for item in answer.facts:
            self.facts.setdefault((item.key.family, item.key.object, item.key.attribute), []).append(item)
        self.members: dict[tuple[str, Attribute], list[ReadMember]] = {}
        for member in answer.members:
            self.members.setdefault((member.key.object, member.key.attribute), []).append(member)
        self.citations: dict[tuple[xs.Family, str, Cited], list[ReadCitation]] = {}
        for citation in answer.citations:
            self.citations.setdefault((citation.family, citation.object, citation.cited), []).append(citation)
        self.doubted: set[tuple[xs.Family, str, Attribute]] = set()
        for doubt in answer.doubts:
            for family, name in doubt.objects:
                for attribute in doubt.named(family):
                    self.doubted.add((family, name, attribute))
        self.ids: dict[xs.Family, tuple[str, ...]] = {
            family: tuple(item['id'] for item in answer.answer[family.value]) for family in Family
            if family is not Family.ENCOUNTER}
        self.roles = {item['id']: tuple(node['role'] for node in item['restatements'])
                      for item in answer.answer['events']}
        self.appraised: list[tuple[_Fact, _Spec, _Spec | None]] = []
        self.pairs: list[tuple[_Spec, tuple[xs.Family, str], tuple[xs.Family, str], Attribute, str]] = []
        self.complete: list[tuple[str, _Spec, _Spec]] = []
        self.unclaimed: list[Unclaimed] = []
        # the claims of facts left unclaimed because their control cannot be written (Unclaimable.CONTROL)
        self.withdrawn: list[_Spec] = []

    # -- reading the answer --

    def slot(self, family: xs.Family, name: str, attribute: Attribute) -> list[ReadFact]:
        return self.facts.get((family, name, attribute), [])

    def supported(self, family: xs.Family, name: str, attribute: Attribute) -> str | None:
        """The value of a slot's one fact when it is supported, whatever its checks; else None."""
        items = self.slot(family, name, attribute)
        if len(items) == 1 and isinstance(items[0].fact, Fact) and items[0].fact.state is FactState.SUPPORTED:
            return items[0].fact.value
        return None

    def is_doubted(self, family: xs.Family, name: str, attribute: Attribute) -> bool:
        """Whether a doubt names this fact (extract_read.ReadDoubt.named)."""
        return (family, name, attribute) in self.doubted

    def usable(self, item: ReadFact) -> bool:
        """Whether a fact may be claimed: supported or negated, no finding of the reader or the caller, no qualifier but
        approximate, and no doubt naming it (3.1, 3.3 rows 1-5)."""
        fact = item.fact
        key = item.key
        return (isinstance(fact, Fact) and fact.state is not FactState.CONTRADICTED and not item.reasons
                and not self.basis.findings.get(key)
                and all(qualifier is Qualifier.APPROXIMATE for qualifier in fact.qualifiers)
                and not self.is_doubted(key.family, key.object, key.attribute))

    def claimed_value(self, family: xs.Family, name: str, attribute: Attribute) -> str | None:
        """The value of a slot's one supported fact when it is itself claimable."""
        items = self.slot(family, name, attribute)
        if len(items) == 1 and self.usable(items[0]) and isinstance(items[0].fact, Fact) \
                and items[0].fact.state is FactState.SUPPORTED:
            return items[0].fact.value
        return None

    def member_usable(self, member: ReadMember) -> bool:
        """Whether a scope list's member may be claimed: no finding of the reader or the caller, and no doubt naming its
        list (a doubt about ``whole``, or a malformed one, names every attribute of its objects: 3.1 S2, 3.3)."""
        key = member.key
        return (not member.reasons and not self.basis.findings.get(key)
                and not self.is_doubted(key.family, key.object, key.attribute))

    def usable_members(self, event: str, attribute: Attribute) -> list[ReadMember] | None:
        """A scope list's members when every one is claimable, else None (an empty list is [])."""
        found = self.members.get((event, attribute), [])
        return found if all(self.member_usable(member) for member in found) else None

    def own_facts(self, family: xs.Family, name: str, attribute: Attribute) -> list[_Fact]:
        return [_Fact(item.key, item.fact.state, item.fact.value, item.fact.sources)
                for item in self.slot(family, name, attribute) if self.usable(item) and isinstance(item.fact, Fact)]

    def citation(self, family: xs.Family, name: str, cited: Cited, index: int = 0) -> ReadCitation | None:
        return next((item for item in self.citations.get((family, name, cited), []) if item.index == index), None)

    def closure(self, run: Sequence[str] | None) -> tuple[str, ...] | None:
        return None if not run else self.basis.closures.get(tuple(run))

    def ordered(self, units: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted(set(units), key=lambda unit: (self.position.get(unit, len(self.position)), unit)))

    def at(self, run: Sequence[str] | None) -> int:
        """Where a run stands in the document: its first unit's index (after every unit for none)."""
        return min((self.position.get(unit, len(self.position)) for unit in run or ()), default=len(self.position) + 1)

    def cited_run(self, family: xs.Family, name: str, cited: Cited) -> tuple[str, ...] | None:
        found = self.citation(family, name, cited)
        if found is None or found.reasons or not found.units or self.closure(found.units) is None:
            return None
        return found.units

    def anchor(self, event: str) -> tuple[str, ...] | None:
        """An event's anchor run, when it is a valid run with a closure."""
        return self.cited_run(Family.EVENT, event, Cited.ANCHOR)

    def statement_run(self, family: xs.Family, name: str) -> tuple[str, ...] | None:
        """The object's own statement (G1's ``statement``): an event's anchor; a lesion's description; a session's
        examination's anchor; a person's name. None for a section, an anatomy entry and the encounter."""
        if family is Family.EVENT:
            return self.anchor(name)
        if family is Family.LESION:
            return self.cited_run(family, name, Cited.DESCRIPTION)
        if family is Family.PERSON:
            return self.cited_run(family, name, Cited.NAME)
        if family is Family.SESSION:
            examination = self.supported(Family.SESSION, name, _A.EXAMINATION)
            return None if examination is None else self.anchor(examination)
        return None

    def cited(self, sources: Sequence[Source], statement: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """The units a claim cites for a fact with these sources (the module's docstring), None when a run has no
        closure."""
        units: list[str] = []
        for source in sources:
            run = statement if (source.link is Link.STATEMENT and statement is not None) else source.units
            found = self.closure(run)
            if found is None:
                return None
            units += found
        return self.ordered(units) if units else None

    def kind_of(self, event: str) -> Kind | None:
        value = self.supported(Family.EVENT, event, _A.KIND)
        return Kind(value) if value is not None else None

    def values_of(self, family: xs.Family, name: str, attribute: Attribute) -> list[str]:
        """Every value pass 1 gives an object's attribute, whatever its state, checks or doubts: each fact's value and
        each option's of a contradicted one, and each member of a scope list. A control never asserts one of them for
        a contrary (DECISIONS D196)."""
        found: list[str] = []
        for item in self.slot(family, name, attribute):
            if isinstance(item.fact, Fact):
                found += [value for value in (item.fact.value, *(option.value for option in item.fact.options))
                          if value != '']
        return found + [member.value for member in self.members.get((name, attribute), [])]

    def asserted_values(self, family: xs.Family, name: str, attribute: Attribute) -> list[str]:
        """The values pass 1 asserts hold of an object's attribute, whatever their checks or doubts: each supported
        fact's value, and each option of a contradicted one (a negated fact asserts that its value does not hold)."""
        found: list[str] = []
        for item in self.slot(family, name, attribute):
            if isinstance(item.fact, Fact) and item.fact.state is FactState.SUPPORTED:
                found.append(item.fact.value)
            elif isinstance(item.fact, Fact) and item.fact.state is FactState.CONTRADICTED:
                found += [option.value for option in item.fact.options]
        return [value for value in found if value != '']

    def own_places(self, event: str) -> list[Landmark]:
        """Every place of an event (DECISIONS D196: a contrast is compatible with none of them): each value of its
        target.places, and its segment's whole range (segment_range) - or its places, when the segment is not two."""
        found = [Landmark(value) for value in self.values_of(Family.EVENT, event, _A.TARGET_PLACES)]
        segment = [Landmark(value) for value in self.values_of(Family.EVENT, event, _A.SCOPE_SEGMENT)]
        return found + list(segment_range(segment[0], segment[1]) if len(segment) == 2 else segment)

    def own_lesions(self, event: str) -> list[str]:
        """Every lesion an event names: its target.lesion's values and its listed targets."""
        return (self.values_of(Family.EVENT, event, _A.TARGET_LESION)
                + self.values_of(Family.EVENT, event, _A.SCOPE_TARGETS))

    def object_class(self, event: str) -> ObjectClass:
        """ACT, or STATEMENT for an event whose claimed status is negated (3.2.1)."""
        items = self.slot(Family.EVENT, event, _A.STATUS)
        negated = len(items) == 1 and isinstance(items[0].fact, Fact) and items[0].fact.state is FactState.NEGATED
        return _STMT if negated else _ACT

    def claimable_event(self, event: str) -> bool:
        """An event of a codable kind with a valid anchor: its facts are claimed (3.2.1)."""
        return self.kind_of(event) in rq.CODABLE_KINDS and self.anchor(event) is not None

    def section_start(self, section: str) -> tuple[str, ...] | None:
        """The units a section begins at: its start's units; for the opening part, whose start cites none, the text's
        first unit (G2: N0 begins at the text start)."""
        found = self.citation(Family.SECTION, section, Cited.START)
        if found is None or found.reasons:
            return None
        if found.units:
            return found.units
        if self.ids[Family.SECTION][:1] == (section,) and self.basis.units:
            return (self.basis.units[0].id,)
        return None

    def anatomy_units(self, name: str) -> tuple[str, ...] | None:
        """An anatomy entry's description (2.4): the units of its type fact's sources, widened to their closures."""
        items = self.slot(Family.ANATOMY, name, _A.TYPE)
        if len(items) != 1 or not isinstance(items[0].fact, Fact):
            return None
        return self.cited(items[0].fact.sources, None)

    def card_units(self, family: xs.Family, name: str) -> tuple[str, ...]:
        """The units a card shows (2.4): an act's anchor closure; a session's examination's anchor closure, else its
        kind fact's cited units; a section's start; a lesion's description closure; an anatomy entry's description; a
        person's name closure (people get no card: it only orders them)."""
        if family is Family.SECTION:
            return self.section_start(name) or ()
        if family is Family.ANATOMY:
            return self.anatomy_units(name) or ()
        run = self.statement_run(family, name)
        if run is not None:
            return self.closure(run) or ()
        if family is Family.SESSION:
            items = self.slot(Family.SESSION, name, _A.KIND)
            if len(items) == 1 and isinstance(items[0].fact, Fact):
                return self.cited(items[0].fact.sources, None) or ()
        return ()

    # -- rendering one claim --

    def render(self, object_class: ObjectClass, attribute: Attribute, state: FactState, value: str, subject: Ref,
               units: tuple[str, ...], form: TemplateId | None = None) -> _Spec | Unclaimable:
        """The real-claim form of (attribute, state, value) about ``subject`` (3.2.2), or ``form`` where a control has
        a form of its own; Unclaimable when 3.2.2 gives none, or a fact its sentence names is not claimable."""
        enum = _ENUM_OF.get((_FAMILY_OF[object_class], attribute))
        member = enum(value) if enum is not None and value != '' else None
        if form is None:
            form = FORMS.get((object_class, attribute, state))
            if member is not None:
                form = FORMS_BY_VALUE.get((object_class, attribute, state, member), form)
                allowed = NEGATED_VALUES.get((object_class, attribute))
                if state is FactState.NEGATED and allowed is not None and member not in allowed:
                    return Unclaimable.NO_TEMPLATE
            if form is None:
                return Unclaimable.NO_TEMPLATE
        slots: list[tuple[Slot, _Value]] = []
        params: list[str] = []
        if form in NAMES_THE_KIND or form is T.STMT_KIND:
            kind = Kind(value) if form is T.STMT_KIND else self.statement_kind(subject.object)
            if kind is None:
                return Unclaimable.KIND
            bare, _article, plural = KIND_LABELS[kind]
            slots += [(Slot.KIND, bare), (Slot.KINDS, plural)]
            if form is not T.STMT_KIND:
                params.append(kind.value)
        why = self.fill(form, attribute, value, member, subject, slots, params)
        if why is not None:
            return why
        return _Spec(form, subject, value, units, tuple(params), tuple(slots))

    def statement_kind(self, event: str) -> Kind | None:
        """A statement's kind when its kind fact is itself claimable (a statement-phrased sentence names it)."""
        value = self.claimed_value(Family.EVENT, event, _A.KIND)
        return Kind(value) if value is not None else None

    def fill(self, form: TemplateId, attribute: Attribute, value: str, member: Enum | None, subject: Ref,
             slots: list[tuple[Slot, _Value]], params: list[str]) -> Unclaimable | None:
        """The slots of ``form`` for one value, and the parameters its sentence renders beyond it."""
        if subject.family is Family.SESSION:
            slots.append((Slot.SESSION, subject))
        if form in (T.LESION_MULTIPLICITY, T.LESION_DISTINCT, T.LESION_SAME):
            slots.append((Slot.LESION, subject))
        if form in _LABEL_SLOT:
            if form is T.ANATOMY_TYPE:
                described = self.anatomy_units(subject.object)
                if described is None:
                    return Unclaimable.UNITS
                slots.append((Slot.UNITS, units_phrase(described)))
                params.extend(described)
            if form in _TYPED_FORMS:
                anatomy_type = self.claimed_value(Family.ANATOMY, subject.object, _A.TYPE)
                if anatomy_type is None:
                    return Unclaimable.PARTNER
                organ_form = form is T.ANATOMY_ORGAN_ABSENT or form is T.ANATOMY_ORGAN_NOT_ABSENT
                if organ_form and anatomy_type != AnatomyType.SURGICALLY_ABSENT.value:
                    return Unclaimable.NO_TEMPLATE
            if form is T.ACT_DATE_RELATION or form is T.STMT_DATE_RELATION:
                relation = DateRelation(value)
                slots.append((Slot.DATE_RELATION,
                              label(relation) if form is T.ACT_DATE_RELATION else STATEMENT_DATE_PHRASES[relation]))
                return None
            if member is None:
                return Unclaimable.NO_TEMPLATE
            slots.append((_LABEL_SLOT[form], label(member)))
            return None
        if form in _REF_SLOT:
            slot, family = _REF_SLOT[form]
            slots.append((slot, Ref(family, value)))
            return None
        if form is T.ACT_DATE or form is T.ENCOUNTER_DATE:
            slots.append((Slot.DATE, value))
            return None
        if form is T.ACT_PERFORMER_PERSON or form is T.STMT_PERFORMER_PERSON:
            name_run = self.statement_run(Family.PERSON, value)
            if name_run is None:
                return Unclaimable.REFERENCE
            slots.append((Slot.PERSON, units_phrase(self.ordered(name_run))))
            params.extend(name_run)
            return None
        if form is T.ACT_PART_OF:
            return self.part_of_slots(subject.object, attribute, value, slots, params)
        if form in (T.STMT_BREADTH_ALL, T.STMT_BREADTH_EXCEPTIVE, T.STMT_BREADTH_TARGETED, T.STMT_TARGET_SEGMENT):
            return self.breadth_slots(form, subject.object, slots, params)
        if form in (T.ACT_ENTRY, T.ACT_RESTATES, T.ACT_RESTATES_SUMMARY):
            return None  # filled by claim_entry and claim_restatements, which know the section and the restatement
        if form in (T.ACT_STATUS_NEGATED, T.ACT_CAUSE_NEGATED, T.ACT_YIELD_NEGATED, T.VISIT_SEPARATE,
                    T.VISIT_SEPARATE_NEGATED, T.STMT_NOT_DONE, T.STMT_DONE, T.STMT_KIND, T.SESSION_ALL_STATIONS,
                    T.SESSION_SOME_STATIONS):
            return None  # the sentence names nothing beyond its subject and the statement's kind
        raise RuntimeError(f'No slots for {form}.')  # pragma: no cover - every template is an arm above (a test pins it)

    def part_of_slots(self, event: str, attribute: Attribute, value: str, slots: list[tuple[Slot, _Value]],
                      params: list[str]) -> Unclaimable | None:
        """part_of and part_relation are told by one sentence: both must be claimable, and both facts share it."""
        partner = self.claimed_value(Family.EVENT, event, _A.PART_RELATION if attribute is _A.PART_OF else _A.PART_OF)
        if partner is None:
            return Unclaimable.PARTNER
        part_of, relation = (value, partner) if attribute is _A.PART_OF else (partner, value)
        slots += [(Slot.RELATION, label(PartRelation(relation))), (Slot.ACT, Ref(Family.EVENT, part_of))]
        params.append(relation)
        return None

    def breadth_slots(self, form: TemplateId, statement: str, slots: list[tuple[Slot, _Value]],
                      params: list[str]) -> Unclaimable | None:
        """The breadth forms' slots: the statement's session (all_of_kind); its excepted acts (exceptive); its target -
        one lesion or place, the listed lesions, or the segment's two places (single, listed or segment); and the
        segment claim's two places. Every fact they name must be claimable."""
        if form is T.STMT_BREADTH_ALL:
            session = self.claimed_value(Family.EVENT, statement, _A.SESSION)
            if session is None:
                return Unclaimable.PARTNER
            slots.append((Slot.SESSION, Ref(Family.SESSION, session)))
            params.append(session)
            return None
        if form is T.STMT_BREADTH_EXCEPTIVE:
            excepts = self.usable_members(statement, _A.SCOPE_EXCEPTS)
            if not excepts:
                return Unclaimable.PARTNER
            slots.append((Slot.ACTS, tuple(Ref(Family.EVENT, member.value) for member in excepts)))
            params.extend(member.value for member in excepts)
            return None
        segment = self.usable_members(statement, _A.SCOPE_SEGMENT)
        if form is T.STMT_TARGET_SEGMENT:
            if segment is None or len(segment) != 2:
                return Unclaimable.PARTNER
            slots += [(Slot.FIRST, label(Landmark(segment[0].value))), (Slot.LAST, label(Landmark(segment[1].value)))]
            params.extend(member.value for member in segment)
            return None
        breadth = self.claimed_value(Family.EVENT, statement, _A.SCOPE_BREADTH)
        lesion = self.claimed_value(Family.EVENT, statement, _A.TARGET_LESION)
        places = [fact for fact in self.own_facts(Family.EVENT, statement, _A.TARGET_PLACES)
                  if fact.state is FactState.SUPPORTED]
        targets = self.usable_members(statement, _A.SCOPE_TARGETS)
        if breadth == Breadth.SINGLE_TARGET.value and lesion is not None:
            slots.append((Slot.TARGET, _Named('lesion', (Ref(Family.LESION, lesion),))))
            params.append(lesion)
        elif breadth == Breadth.SINGLE_TARGET.value and len(places) == 1:
            slots.append((Slot.TARGET, f'the {label(Landmark(places[0].value))}'))
            params.append(places[0].value)
        elif breadth == Breadth.LISTED_TARGETS.value and targets is not None and len(targets) >= 2:
            slots.append((Slot.TARGET, _Named('lesions', tuple(Ref(Family.LESION, item.value) for item in targets))))
            params.extend(item.value for item in targets)
        elif breadth == Breadth.SEGMENT.value and segment is not None and len(segment) == 2:
            slots.append((Slot.TARGET, f'the {label(Landmark(segment[0].value))} to the '
                                       f'{label(Landmark(segment[1].value))}'))
            params.extend(member.value for member in segment)
        else:
            return Unclaimable.PARTNER
        return None

    # -- one fact's claim, and its control --

    def claim(self, object_class: ObjectClass, fact: _Fact, subject: Ref, units: tuple[str, ...],
              render_as: tuple[Attribute, str] | None = None, made: _Spec | None = None) -> None:
        """The claim of one claimable fact (rendered as ``render_as`` when its sentence is another fact's: an excepted
        act's is its breadth's, a segment place's the segment's), and its control (CONTROLS), recorded as appraised;
        Unclaimed when it cannot be rendered."""
        if made is None:
            attribute, value = render_as if render_as is not None else (fact.key.attribute, fact.value)
            rendered = self.render(object_class, attribute, fact.state, value, subject, units)
            if isinstance(rendered, Unclaimable):
                self.unclaimed.append(Unclaimed(fact.key, fact.inherited_from, rendered))
                return
            made = rendered
        control = self.control(object_class, fact, subject, units, made)
        if isinstance(control, Unclaimable):
            # a control the document calls for but that cannot be written: the claim would stand uncontrolled, and the
            # facts sharing it go too (shared_claims)
            self.unclaimed.append(Unclaimed(fact.key, fact.inherited_from, control))
            self.withdrawn.append(made)
            return
        self.appraised.append((fact, made, control))

    def control(self, object_class: ObjectClass, fact: _Fact, subject: Ref, units: tuple[str, ...],
                made: _Spec) -> _Spec | Unclaimable | None:
        """The contrary control of a claimed fact (3.2.3): None when its attribute has no rule for this value, or no
        contrary exists in this document (the claim alone decides); Unclaimable.CONTROL when a contrary exists but its
        sentence needs a fact that is not claimable (the fact is then not claimed: fail-closed)."""
        attribute = fact.key.attribute
        enum = _ENUM_OF.get((_FAMILY_OF[object_class], attribute))
        member = enum(fact.value) if enum is not None and fact.value != '' else None
        kind = self.kind_of(subject.object) if subject.family is Family.EVENT else None
        rule = control_rule(object_class, attribute, fact.state, member, kind)
        if rule is None:
            return None
        if rule.contrary is Contrary.REPORTED_ACTS:
            return self.reported_acts_control(subject, units)
        value = self.contrary(rule, member, fact, subject)
        if value is None or isinstance(value, Unclaimable):
            return value
        rendered = self.render(object_class, rule.as_attribute or attribute, rule.as_state or fact.state, value,
                               subject, units, rule.form)
        if isinstance(rendered, Unclaimable):
            return Unclaimable.CONTROL
        if made.template is T.ACT_ENTRY or made.template is T.ACT_RESTATES:
            # the same section start, or the same restatement units, as the claim it controls
            slots: tuple[tuple[Slot, _Value], ...] = tuple(
                (slot, item) for slot, item in made.slots if slot is not Slot.OWNER)
            if made.template is T.ACT_ENTRY:
                slots += ((Slot.OWNER, label(Owner(value))),)
            return _Spec(rendered.template, subject, value, units, made.params, slots)
        return rendered

    def contrary(self, rule: ControlRule, member: Enum | None, fact: _Fact, subject: Ref) -> str | Unclaimable | None:
        """The contrary value a control asserts, or None (no contrary in this document). A contrast place is compatible
        with no place of the object, and another object is none of the object's own values (DECISIONS D196). A place
        whose every candidate is compatible with a place of the object has a contrary the control cannot name:
        Unclaimable.CONTROL (D196 controls every place a READY or exclusion path reads; a place a single verdict
        decides is never claimed)."""
        how = rule.contrary
        if how is Contrary.SAME:
            return fact.value
        if how is Contrary.FIXED:
            return None if rule.fixed is None else str(rule.fixed.value)
        if how is Contrary.TABLE:
            found = table(rule.table).get(member) if rule.table is not None and member is not None else None
            return None if found is None else str(found.value)
        if how is Contrary.CONTRAST or how is Contrary.FIRST_CONTRAST:
            if how is Contrary.CONTRAST:
                places = [Landmark(fact.value)]
            else:
                places = [Landmark(value) for value in self.values_of(Family.EVENT, subject.object, _A.SCOPE_SEGMENT)]
                if len(places) != 2:
                    return None
            candidates = contrast_candidates(places)
            if not candidates:
                return None  # a surgically made place, or other: engine/anatomy sets it apart from nothing
            found_place = contrast(candidates, self.own_places(subject.object))
            return Unclaimable.CONTROL if found_place is None else found_place.value
        if how is Contrary.ANOTHER_SESSION:
            own = [fact.value, *self.values_of(subject.family, subject.object, _A.SESSION)]
            return self.first_other(Family.SESSION, own, lambda name: True)
        if how is Contrary.ANOTHER_LESION:
            own = [fact.value, *self.own_lesions(subject.object)]
            return self.first_other(Family.LESION, own, lambda name: True)
        if how is Contrary.ANOTHER_PERSON:
            # an inherited person is the section's: the fact's own value is excluded with the act's own slot's
            own = [fact.value, *self.values_of(subject.family, subject.object, _A.PERFORMER_PERSON)]
            return self.first_other(Family.PERSON, own, lambda name: True)
        if how is Contrary.ANOTHER_ANATOMY:
            own = [fact.value, *self.values_of(subject.family, subject.object, _A.THROUGH)]
            return self.first_other(Family.ANATOMY, own, lambda name: True)
        if how is Contrary.ANATOMY_POINT:
            anatomy_type = self.supported(Family.ANATOMY, fact.value, _A.TYPE)
            point = ANATOMY_POINT.get(AnatomyType(anatomy_type)) if anatomy_type is not None else None
            return None if point is None else point.value
        session = self.supported(Family.EVENT, subject.object, _A.SESSION)
        if session is None:
            return None
        if how is Contrary.ANOTHER_LESION_OF_SESSION:
            of_session = {self.supported(Family.EVENT, event, _A.TARGET_LESION) for event in self.ids[Family.EVENT]
                          if event != subject.object and self.supported(Family.EVENT, event, _A.SESSION) == session}
            own = [fact.value, *self.own_lesions(subject.object)]
            return self.first_other(Family.LESION, own, lambda name: name in of_session)
        if how is Contrary.ANOTHER_POSITIVE_ACT:
            own = [subject.object, *self.values_of(Family.EVENT, subject.object, _A.CAUSE_EVENT)]
            return self.first_other(Family.EVENT, own, lambda name: (
                self.supported(Family.EVENT, name, _A.SESSION) == session
                and self.supported(Family.EVENT, name, _A.STATUS) == Status.PERFORMED.value))
        raise RuntimeError(f'Unknown contrary {how}.')  # pragma: no cover

    def first_other(self, family: xs.Family, own: Sequence[str], keep: Callable[[str], bool]) -> str | None:
        """The first object of ``family`` in document order that is none of ``own`` (the object's own values, and the
        object itself where it is of the family), that ``keep`` admits and that a card can show; None when there is
        none."""
        found = [(self.at(self.card_units(family, name)), name) for name in self.ids[family]
                 if name not in own and keep(name) and self.card_units(family, name)]
        return min(found)[1] if found else None

    def reported_acts_control(self, subject: Ref, units: tuple[str, ...]) -> _Spec | Unclaimable | None:
        """all_of_kind's control: the exceptive form listing the reported acts of a kind the statement covers (3.2.3:
        "only when reported acts of the kind exist"; None when none does). An act is reported when pass 1 asserts of
        it, whatever the checks or doubts (asserted_values: a contradicted fact's options included), the performed
        status and a kind the statement's covers - so weakening an act's status or kind from doubted to contradicted
        never takes the control away. The control lists only acts whose kind and status are claimable and whose card
        can be shown, so it never shows a doubted, contradicted or failed value; when no reported act is such, the
        breadth is not claimed (Unclaimable.CONTROL: it settles unappraised, fail-closed)."""
        kind = self.statement_kind(subject.object)
        if kind is None:
            return None
        reported = [name for name in self.ids[Family.EVENT]
                    if name != subject.object and self.object_class(name) is _ACT
                    and any(value == Status.PERFORMED.value
                            for value in self.asserted_values(Family.EVENT, name, _A.STATUS))
                    and any(catalogue.covers(kind, Kind(value))
                            for value in self.asserted_values(Family.EVENT, name, _A.KIND))]
        if not reported:
            return None
        acts = sorted((self.at(self.anchor(name)), name) for name in reported
                      if self.claimable_event(name)
                      and self.claimed_value(Family.EVENT, name, _A.STATUS) == Status.PERFORMED.value
                      and self.claimed_value(Family.EVENT, name, _A.KIND) is not None)
        if not acts:
            return Unclaimable.CONTROL
        bare, _article, plural = KIND_LABELS[kind]
        slots: tuple[tuple[Slot, _Value], ...] = (
            (Slot.KIND, bare), (Slot.KINDS, plural), (Slot.ACTS, tuple(Ref(Family.EVENT, name) for _at, name in acts)))
        return _Spec(T.STMT_BREADTH_EXCEPTIVE, subject, Breadth.EXCEPTIVE.value, units,
                     (kind.value, *(name for _at, name in acts)), slots)

    # -- the objects --

    def run(self) -> ClaimSet:
        self.claim_events()
        self.claim_sessions()
        self.claim_anatomy()
        self.claim_lesions()
        self.claim_encounter()
        self.shared_claims()
        self.no_control_is_a_claim()
        self.pair_controls()
        self.completeness()
        return self.finish()

    def shared_claims(self) -> None:
        """A claim several facts share names each of them - an excepted act's claim is its breadth's exceptive sentence,
        a segment's two places share one - so when one of them is not claimed because its control cannot be written
        (Unclaimable.CONTROL: an exceptive breadth whose session is not claimable), the facts sharing its claim are
        not claimed either (Unclaimable.PARTNER): no sentence names a fact that is not claimed."""
        withdrawn = {made.assertion() for made in self.withdrawn}
        sharing = {index for index, (_fact, made, _control) in enumerate(self.appraised)
                   if made.assertion() in withdrawn}
        for index in sorted(sharing):
            fact = self.appraised[index][0]
            self.unclaimed.append(Unclaimed(fact.key, fact.inherited_from, Unclaimable.PARTNER))
        self.appraised = [entry for index, entry in enumerate(self.appraised) if index not in sharing]

    def no_control_is_a_claim(self) -> None:
        """DECISIONS D196 (the arbiter's 2c#3): a control never asserts what one of the same object's real claims
        asserts - such a control is true whenever the claim is, so it can only make the pair incoherent. The contrast
        and other-object rules choose around the object's own values; what is left can only be pass 1 giving a value
        and its contrary (a lesion both distinct from and the same as another; an excepted act it also covers): neither
        fact is claimed (Unclaimable.CONTRARY), so neither is decided by the other's verdict. A claim several facts share
        names each of them (an excepted act's is its breadth's exceptive sentence), so the facts sharing it go too
        (Unclaimable.PARTNER): no sentence names a fact that is not claimed."""
        claimed: dict[tuple[TemplateId, Ref, tuple[tuple[Slot, _Value], ...]], list[int]] = {}
        for index, (_fact, made, _control) in enumerate(self.appraised):
            claimed.setdefault(made.assertion(), []).append(index)
        contrary: set[int] = set()
        for index, (_fact, _made, control) in enumerate(self.appraised):
            if control is not None and control.assertion() in claimed:
                contrary |= {index, *claimed[control.assertion()]}
        sharing = {other for index in contrary for other in claimed[self.appraised[index][1].assertion()]} - contrary
        for index in sorted(contrary | sharing):
            fact = self.appraised[index][0]
            why = Unclaimable.CONTRARY if index in contrary else Unclaimable.PARTNER
            self.unclaimed.append(Unclaimed(fact.key, fact.inherited_from, why))
        self.appraised = [entry for index, entry in enumerate(self.appraised) if index not in contrary | sharing]

    def claim_events(self) -> None:
        for event in self.ids[Family.EVENT]:
            kind = self.kind_of(event)
            anchor = self.anchor(event)
            if kind is None or kind not in rq.CODABLE_KINDS or anchor is None:
                continue
            object_class = self.object_class(event)
            subject = Ref(Family.EVENT, event)
            for item in xs.ATTRIBUTES[Family.EVENT]:
                for condition in rq.claimed(object_class, item.attribute, kind):
                    self.claim_attribute(event, object_class, item, condition, subject, anchor)

    def claim_attribute(self, event: str, object_class: ObjectClass, item: xs.Field, condition: rq.Condition,
                        subject: Ref, anchor: tuple[str, ...]) -> None:
        attribute = item.attribute
        if attribute is _A.ENTRY:
            self.claim_entry(event, subject)
            return
        if attribute is _A.RESTATEMENTS_ROLE:
            self.claim_restatements(event, subject)
            return
        if item.arity is xs.Arity.LIST:
            self.claim_members(event, object_class, attribute, subject, anchor)
            return
        if attribute is _A.PART_RELATION:
            self.claim_part_relation(event, subject, anchor)
            return
        if condition is rq.Condition.EUS_SESSION:
            session = self.supported(Family.EVENT, event, _A.SESSION)
            if session is None or self.supported(Family.SESSION, session, _A.KIND) != SessionKind.EUS.value:
                return
        if condition is rq.Condition.OTHER_CLINICIAN and \
                self.effective_value(event, _A.PERFORMER) != Performer.OTHER_CLINICIAN.value:
            return
        if condition in (rq.Condition.EFFECTIVE, rq.Condition.OTHER_CLINICIAN) and \
                not self.slot(Family.EVENT, event, attribute):
            self.claim_inherited(event, object_class, attribute, subject)
            return
        for fact in self.own_facts(Family.EVENT, event, attribute):
            units = self.cited(fact.sources, anchor)
            if units is None:
                self.unclaimed.append(Unclaimed(fact.key, None, Unclaimable.UNITS))
                continue
            self.claim(object_class, fact, subject, units)

    def effective_value(self, event: str, attribute: Attribute) -> str | None:
        """The supported value of an act's effective attribute: its own slot's, else its section's (1.5)."""
        if self.slot(Family.EVENT, event, attribute):
            return self.supported(Family.EVENT, event, attribute)
        section = self.basis.sections.get(event)
        return None if section is None else self.supported(Family.SECTION, section, _INHERITED_FROM[attribute])

    def claim_inherited(self, event: str, object_class: ObjectClass, attribute: Attribute, subject: Ref) -> None:
        """An act's effective fact taken from its containing section (1.5): claimed about the act, citing the section
        fact's sources, unless a doubt or finding names the act's own attribute."""
        section = self.basis.sections.get(event)
        key = FactKey(Family.EVENT, event, attribute, 0)
        if section is None or self.is_doubted(Family.EVENT, event, attribute) or self.basis.findings.get(key):
            return
        for own in self.own_facts(Family.SECTION, section, _INHERITED_FROM[attribute]):
            fact = _Fact(key, own.state, own.value, own.sources, section)
            units = self.cited(own.sources, None)
            if units is None:
                self.unclaimed.append(Unclaimed(key, section, Unclaimable.UNITS))
                continue
            self.claim(object_class, fact, subject, units)

    def claim_entry(self, event: str, subject: Ref) -> None:
        """The act's entry (1.5): its containing section's owner, claimed about the act, citing the owner's sources."""
        section = self.basis.sections.get(event)
        key = FactKey(Family.EVENT, event, _A.ENTRY, 0)
        if section is None or self.is_doubted(Family.EVENT, event, _A.ENTRY) or self.basis.findings.get(key):
            return
        start = self.section_start(section)
        for own in self.own_facts(Family.SECTION, section, _A.OWNER):
            fact = _Fact(key, own.state, own.value, own.sources, section)
            units = self.cited(own.sources, None)
            if own.state is not FactState.SUPPORTED:
                self.unclaimed.append(Unclaimed(key, section, Unclaimable.NO_TEMPLATE))
            elif units is None or start is None:
                self.unclaimed.append(Unclaimed(key, section, Unclaimable.UNITS))
            else:
                slots: tuple[tuple[Slot, _Value], ...] = (
                    (Slot.START, units_phrase(self.ordered(start))), (Slot.OWNER, label(Owner(own.value))))
                made = _Spec(T.ACT_ENTRY, subject, own.value, units, (section, *start), slots)
                self.claim(_ACT, fact, subject, units, made=made)

    def claim_restatements(self, event: str, subject: Ref) -> None:
        """The role of a restates restatement that lies in a section the documenting clinician owns (1.5 [R:SC-D])."""
        for index, role in enumerate(self.roles[event]):
            if role != RestatementRole.RESTATES.value:
                continue
            section = self.basis.restatement_sections.get((event, index))
            key = FactKey(Family.EVENT, event, _A.RESTATEMENTS_ROLE, index)
            if (section is None
                    or self.supported(Family.SECTION, section, _A.OWNER) != Owner.DOCUMENTING_CLINICIAN.value
                    or self.is_doubted(Family.EVENT, event, _A.RESTATEMENTS_ROLE) or self.basis.findings.get(key)):
                continue
            found = self.citation(Family.EVENT, event, Cited.RESTATEMENT, index)
            units = None if found is None or found.reasons else self.closure(found.units)
            if found is None or units is None:
                self.unclaimed.append(Unclaimed(key, None, Unclaimable.UNITS))
                continue
            fact = _Fact(key, FactState.SUPPORTED, role, ())
            slots: tuple[tuple[Slot, _Value], ...] = ((Slot.UNITS, units_phrase(self.ordered(found.units))),)
            made = _Spec(T.ACT_RESTATES, subject, role, units, tuple(found.units), slots)
            self.claim(_ACT, fact, subject, units, made=made)

    def claim_members(self, event: str, object_class: ObjectClass, attribute: Attribute, subject: Ref,
                      anchor: tuple[str, ...]) -> None:
        """A statement's scope list: each covered act and each listed target its own claim; the excepted acts share
        their breadth's exceptive claim (cited as the breadth is); the segment's two places share one claim."""
        units = self.closure(anchor) or ()
        render_as: tuple[Attribute, str] | None = None
        if attribute is _A.SCOPE_EXCEPTS:
            breadth = [fact for fact in self.own_facts(Family.EVENT, event, _A.SCOPE_BREADTH)
                       if fact.state is FactState.SUPPORTED and fact.value == Breadth.EXCEPTIVE.value]
            breadth_units = self.cited(breadth[0].sources, anchor) if breadth else None
            if breadth_units is None:
                for member in self.members.get((event, attribute), []):
                    if self.member_usable(member):
                        self.unclaimed.append(Unclaimed(member.key, None, Unclaimable.PARTNER))
                return
            units, render_as = breadth_units, (_A.SCOPE_BREADTH, Breadth.EXCEPTIVE.value)
        segment = self.members.get((event, _A.SCOPE_SEGMENT), [])
        for member in self.members.get((event, attribute), []):
            if not self.member_usable(member):
                continue
            fact = _Fact(member.key, FactState.SUPPORTED, member.value, ())
            if attribute is _A.SCOPE_SEGMENT:
                render_as = (_A.SCOPE_SEGMENT, segment[0].value)
            self.claim(object_class, fact, subject, units, render_as)

    def claim_part_relation(self, event: str, subject: Ref, anchor: tuple[str, ...]) -> None:
        """part_relation shares part_of's claim: rendered as part_of's fact, citing part_of's units."""
        part_of = [fact for fact in self.own_facts(Family.EVENT, event, _A.PART_OF) if fact.state is FactState.SUPPORTED]
        for fact in self.own_facts(Family.EVENT, event, _A.PART_RELATION):
            units = self.cited(part_of[0].sources, anchor) if part_of else None
            if units is None or fact.state is not FactState.SUPPORTED:
                self.unclaimed.append(Unclaimed(fact.key, None, Unclaimable.PARTNER))
                continue
            self.claim(_ACT, fact, subject, units, (_A.PART_OF, part_of[0].value))

    def claim_sessions(self) -> None:
        visits = {self.supported(Family.EVENT, event, _A.SESSION) for event in self.ids[Family.EVENT]
                  if self.supported(Family.EVENT, event, _A.KIND) == Kind.EM_VISIT.value}
        for session in self.ids[Family.SESSION]:
            subject = Ref(Family.SESSION, session)
            statement = self.statement_run(Family.SESSION, session)
            for entry in rq.CLAIMED[_SESSION_C]:
                if entry.condition is rq.Condition.COMPLETENESS:
                    continue  # completeness()
                if entry.condition is rq.Condition.HOLDS_VISIT and session not in visits:
                    continue
                for fact in self.own_facts(Family.SESSION, session, entry.attribute):
                    units = self.cited(fact.sources, statement)
                    if units is None:
                        self.unclaimed.append(Unclaimed(fact.key, None, Unclaimable.UNITS))
                        continue
                    self.claim(_SESSION_C, fact, subject, units)

    def anatomy_read(self) -> list[str]:
        """The anatomy entries a rule reads (3.2.1; requirements.Condition.READ_BY_A_RULE): those a session's through or
        reached_anatomy, or an act's target.anatomy, names; those of a type a class rule reads; a surgically absent one
        only when a reached point or a station names its organ (the organ or a place inside it)."""
        named = {self.supported(Family.SESSION, session, attribute) for session in self.ids[Family.SESSION]
                 for attribute in (_A.THROUGH, _A.REACHED_ANATOMY)}
        named |= {self.supported(Family.EVENT, event, _A.TARGET_ANATOMY) for event in self.ids[Family.EVENT]}
        points: list[anatomy.Place] = []
        for session in self.ids[Family.SESSION]:
            points += [Extent(item.fact.value) for item in self.slot(Family.SESSION, session, _A.REACHED)
                       if isinstance(item.fact, Fact) and item.fact.state is FactState.SUPPORTED]
            points += [Station(item.fact.value) for item in self.slot(Family.SESSION, session, _A.STATIONS)
                       if isinstance(item.fact, Fact) and item.fact.state is FactState.SUPPORTED]
        found = []
        for name in self.ids[Family.ANATOMY]:
            value = self.supported(Family.ANATOMY, name, _A.TYPE)
            if value == AnatomyType.SURGICALLY_ABSENT.value:
                organ = self.supported(Family.ANATOMY, name, _A.ORGAN)
                read = organ is not None and any(anatomy.landmark_of(point) is Landmark(organ)
                                                 or anatomy.contains(Landmark(organ), point) for point in points)
            else:
                read = value is not None and AnatomyType(value) in rq.ANATOMY_READ_TYPES
            if name in named or read:
                found.append(name)
        return found

    def claim_anatomy(self) -> None:
        for name in self.anatomy_read():
            subject = Ref(Family.ANATOMY, name)
            for entry in rq.CLAIMED[_ANAT_C]:
                for fact in self.own_facts(Family.ANATOMY, name, entry.attribute):
                    units = self.cited(fact.sources, None)
                    if units is None:
                        self.unclaimed.append(Unclaimed(fact.key, None, Unclaimable.UNITS))
                        continue
                    self.claim(_ANAT_C, fact, subject, units)

    def claim_lesions(self) -> None:
        """The lesions of claimed acts (3.2.1): each lesion a claimable event is done to or a statement lists."""
        of_claimed: set[str] = set()
        for event in self.ids[Family.EVENT]:
            if not self.claimable_event(event):
                continue
            of_claimed |= {fact.value for fact in self.own_facts(Family.EVENT, event, _A.TARGET_LESION)}
            of_claimed |= {member.value for member in self.members.get((event, _A.SCOPE_TARGETS), [])}
        for name in self.ids[Family.LESION]:
            if name not in of_claimed:
                continue
            subject = Ref(Family.LESION, name)
            statement = self.statement_run(Family.LESION, name)
            for entry in rq.CLAIMED[_LES_C]:
                for fact in self.own_facts(Family.LESION, name, entry.attribute):
                    units = self.cited(fact.sources, statement)
                    if units is None:
                        self.unclaimed.append(Unclaimed(fact.key, None, Unclaimable.UNITS))
                        continue
                    self.claim(_LES_C, fact, subject, units)

    def claim_encounter(self) -> None:
        """The date of service, when stated, passed its checks and is not doubted (3.2.1). UNCONTROLLED."""
        key = FactKey(Family.ENCOUNTER, '', _A.DATE_OF_SERVICE, 0)
        items = self.slot(Family.ENCOUNTER, '', _A.DATE_OF_SERVICE)
        if len(items) != 1 or not isinstance(items[0].fact, DateOfService):
            return
        item, when = items[0], items[0].fact
        if (when.state is not DateState.STATED or item.reasons or self.basis.findings.get(key)
                or self.is_doubted(Family.ENCOUNTER, '', _A.DATE_OF_SERVICE)):
            return
        units = self.cited(when.sources, None)
        if units is None:
            self.unclaimed.append(Unclaimed(key, None, Unclaimable.UNITS))
            return
        fact = _Fact(key, FactState.SUPPORTED, when.value, when.sources)
        made = _Spec(T.ENCOUNTER_DATE, Ref(Family.ENCOUNTER, ''), when.value, units, (), ((Slot.DATE, when.value),))
        self.appraised.append((fact, made, None))

    # -- pair controls and the completeness claim --

    def places(self, event: str) -> list[Landmark]:
        """An event's claimable places: its supported target places, and its segment's two places."""
        found = [Landmark(fact.value) for fact in self.own_facts(Family.EVENT, event, _A.TARGET_PLACES)
                 if fact.state is FactState.SUPPORTED]
        segment = self.usable_members(event, _A.SCOPE_SEGMENT)
        return found + [Landmark(member.value) for member in segment or ()]

    def lesions(self, event: str) -> list[str]:
        """An event's claimable lesions: its supported target lesion, and each listed target that may be claimed - each
        member on its own, as claim_members claims them (an invalid or failed member leaves the others claimed), so a
        pair control never asks an object about a lesion one of its own claims names."""
        found = [fact.value for fact in self.own_facts(Family.EVENT, event, _A.TARGET_LESION)
                 if fact.state is FactState.SUPPORTED]
        return found + [member.value for member in self.members.get((event, _A.SCOPE_TARGETS), [])
                        if self.member_usable(member)]

    def pair_controls(self) -> None:
        """3.2.3 [R:SC-B]: each statement with a single, listed or segment target, against every act of a compatible
        or sibling kind in its session (in any session when its session is not claimable); and every pair of acts whose
        kinds a rule of identity by place reads together (_place_identity_pair: D118's one stricture, and bundling
        identity by place, DECISIONS D196), not established in different sessions. Each object is asked about every
        place of the other that none of its own places is compatible with, and about the other's lesions when their
        lesions differ."""
        events = [event for event in self.ids[Family.EVENT] if self.claimable_event(event)]
        acts = [event for event in events if self.object_class(event) is _ACT]
        for statement in events:
            breadth = self.claimed_value(Family.EVENT, statement, _A.SCOPE_BREADTH)
            if self.object_class(statement) is not _STMT or breadth is None or Breadth(breadth) not in _TARGETED:
                continue
            kind = self.kind_of(statement)
            session = self.claimed_value(Family.EVENT, statement, _A.SESSION)
            for act in acts:
                act_kind = self.kind_of(act)
                act_session = self.supported(Family.EVENT, act, _A.SESSION)
                if kind is None or act_kind is None or not _compatible(kind, act_kind):
                    continue
                if session is not None and act_session is not None and act_session != session:
                    continue
                self.pair(statement, act)
        for index, first in enumerate(acts):
            for second in acts[index + 1:]:
                one = self.claimed_value(Family.EVENT, first, _A.SESSION)
                other = self.claimed_value(Family.EVENT, second, _A.SESSION)
                if (one is None or other is None or one == other) and \
                        _place_identity_pair(self.kind_of(first), self.kind_of(second)):
                    self.pair(first, second)

    def pair(self, first: str, second: str) -> None:
        """Both directions of the pair controls between two events."""
        for asked, other in ((first, second), (second, first)):
            asked_places, other_places = self.places(asked), self.places(other)
            if asked_places and other_places:
                for place in _distinct(other_places):
                    if not any(anatomy.compatible(place, own) for own in asked_places):
                        self.pair_spec(asked, other, _A.TARGET_PLACES, place.value)
            asked_lesions, other_lesions = self.lesions(asked), self.lesions(other)
            if asked_lesions and other_lesions and set(asked_lesions) != set(other_lesions):
                for lesion in sorted(set(other_lesions) - set(asked_lesions)):
                    self.pair_spec(asked, other, _A.TARGET_LESION, lesion)

    def pair_spec(self, asked: str, other: str, attribute: Attribute, value: str) -> None:
        """One pair control: ``asked`` is asked about ``other``'s place or lesion, citing its own anchor's closure."""
        units = self.closure(self.anchor(asked))
        if units is None:
            return
        made = self.render(self.object_class(asked), attribute, FactState.SUPPORTED, value, Ref(Family.EVENT, asked),
                           self.ordered(units))
        if not isinstance(made, Unclaimable):
            self.pairs.append((made, (Family.EVENT, asked), (Family.EVENT, other), attribute, value))

    def completeness(self) -> None:
        """The completeness claim (3.2.2 [R:SC-B]) for every upper EUS session whose station list is empty, cited at its
        examination's sentence closure, with its limitation-form control. The claim renders the session's kind and
        tract and its empty list, so it is made only when they are claimable, as every claim's facts are: the kind and
        the tract supported, passing their checks and named by no doubt, and the list named by no doubt or finding.
        Otherwise there is none, and STATIONS stays unmet (fail-closed; the arbiter's 2c#6)."""
        for session in self.ids[Family.SESSION]:
            if (self.claimed_value(Family.SESSION, session, _A.KIND) != SessionKind.EUS.value
                    or self.claimed_value(Family.SESSION, session, _A.TRACT) != Tract.UPPER.value
                    or self.slot(Family.SESSION, session, _A.STATIONS)
                    or self.is_doubted(Family.SESSION, session, _A.STATIONS)
                    or self.basis.findings.get(FactKey(Family.SESSION, session, _A.STATIONS, 0))):
                continue
            units = self.closure(self.statement_run(Family.SESSION, session))
            if units is None:
                continue
            subject = Ref(Family.SESSION, session)
            slots: tuple[tuple[Slot, _Value], ...] = ((Slot.SESSION, subject),)
            claim = _Spec(T.SESSION_ALL_STATIONS, subject, '', self.ordered(units), (), slots)
            control = _Spec(T.SESSION_SOME_STATIONS, subject, '', self.ordered(units), (), slots)
            self.complete.append((session, claim, control))

    # -- cards, numbering and the order --

    def finish(self) -> ClaimSet:
        specs: list[_Spec] = []
        for _fact, made, control in self.appraised:
            specs += [made] if control is None else [made, control]
        specs += [made for made, *_rest in self.pairs]
        for _session, claim, control in self.complete:
            specs += [claim, control]
        cards, card_of = self.cards([ref for made in specs for ref in made.refs()])

        def shown(made: _Spec | None) -> bool:
            return made is not None and all(
                ref.family is Family.ENCOUNTER or (ref.family, ref.object) in card_of for ref in made.refs())

        by_key: dict[str, _Spec] = {}
        for made in specs:
            if shown(made):
                by_key.setdefault(made.content(), made)
        ordered = sorted(by_key, key=lambda content: jsonschema.sha256_of([self.seed, content]))
        claim_id = {content: f'K{index}' for index, content in enumerate(ordered, start=1)}
        claims: list[Claim] = []
        sentences: dict[str, str] = {}
        about: dict[str, str] = {}
        for content in ordered:
            made = by_key[content]
            identifier = claim_id[content]
            claims.append(Claim(identifier, made.template.value, made.subject.object, made.value, made.units, content))
            sentences[identifier] = _sentence(made, card_of)
            about[identifier] = card_of.get((made.subject.family, made.subject.object), '')
        appraised: list[Appraised] = []
        unclaimed = list(self.unclaimed)
        controls: set[str] = set()
        for fact, made, control in self.appraised:
            if not shown(made):
                unclaimed.append(Unclaimed(fact.key, fact.inherited_from, Unclaimable.REFERENCE))
                continue
            control_id = claim_id[control.content()] if control is not None and shown(control) else None
            if control_id is not None:
                controls.add(control_id)
            appraised.append(Appraised(fact.key, fact.inherited_from, fact.state, fact.value,
                                       claim_id[made.content()], control_id))
        pairs: list[PairControl] = []
        for made, subject, other, attribute, value in self.pairs:
            pair = PairControl(claim_id[made.content()], subject, other, attribute, value) if shown(made) else None
            if pair is not None and pair not in pairs:
                pairs.append(pair)
                controls.add(pair.claim)
        complete: list[Completeness] = []
        for session, claim, control in self.complete:
            if shown(claim) and shown(control):
                complete.append(Completeness(session, claim_id[claim.content()], claim_id[control.content()]))
                controls.add(claim_id[control.content()])
        # DECISIONS D196: no control asserts what a real claim about the same object asserts, whatever units each
        # cites (no_control_is_a_claim leaves none); one that did would be a defect, and no claim set is built
        real = {made.assertion() for _fact, made, _control in self.appraised if shown(made)}
        written = [control for _fact, _made, control in self.appraised if control is not None]
        written += [made for made, *_rest in self.pairs] + [control for _session, _claim, control in self.complete]
        if controls & {item.claim for item in appraised} or any(
                shown(control) and control.assertion() in real for control in written):
            raise RuntimeError('A control asserts what a real claim about the same object asserts (DECISIONS D196); '
                               'no claim set is built.')
        return ClaimSet(
            cards=tuple(cards), claims=tuple(claims), sentences=MappingProxyType(sentences),
            about=MappingProxyType(about), appraised=tuple(appraised), pair_controls=tuple(pairs),
            completeness=tuple(complete), unclaimed=tuple(unclaimed),
            objects=MappingProxyType({card_id: object_ for object_, card_id in card_of.items()}),
            controls=frozenset(controls), seed=self.seed)

    def cards(self, refs: list[Ref]) -> tuple[list[Card], dict[tuple[xs.Family, str], str]]:
        """One card per object named, numbered by type in document order (sections from N0, the others from 1); an
        object with no units gets none. Two events sharing an anchor unit carry their own anchor words (2.4
        [R:CO-7])."""
        wanted = sorted({(ref.family.value, ref.object) for ref in refs if ref.family is not Family.ENCOUNTER})
        objects = [(Family(family), name) for family, name in wanted]
        units_of = {item: self.card_units(*item) for item in objects}
        objects = [item for item in objects if units_of[item]]
        anchors = {name: frozenset(self.anchor(name) or ()) for family, name in objects if family is Family.EVENT}
        shared = {name for name, units in anchors.items()
                  if any(other != name and units & other_units for other, other_units in anchors.items())}
        cards: list[Card] = []
        card_of: dict[tuple[xs.Family, str], str] = {}
        for card_type in _CARD_ORDER:
            mine = sorted((item for item in objects if _CARD_TYPE[item[0]] is card_type),
                          key=lambda item: (self.at(units_of[item]), self.words_at(item), item[1]))
            for number, (family, name) in enumerate(mine, start=0 if card_type is CardType.SECTION else 1):
                identifier = f'{card_type.letter}{number}'
                kind_words, status_words = (self.basis.anchor_words.get(name, (None, None))
                                            if family is Family.EVENT and name in shared else (None, None))
                cards.append(Card(identifier, card_type, self.ordered(units_of[(family, name)]), kind_words,
                                  status_words))
                card_of[(family, name)] = identifier
        return cards, card_of

    def words_at(self, item: tuple[xs.Family, str]) -> tuple[int, int]:
        """Events sharing an anchor are numbered by where their own words stand."""
        family, name = item
        spans = self.basis.anchor_words.get(name, (None, None)) if family is Family.EVENT else (None, None)
        starts = [span.start for span in spans if span is not None]
        return (min(starts), max(starts)) if starts else (0, 0)


def _compatible(statement: Kind, act: Kind) -> bool:
    """3.2.3's "compatible or sibling kind": the statement's kind covers the act's (catalogue.covers: the same kind, a
    tattoo and an injection, an umbrella and its members), or either is the other's KIND_SIBLINGS sibling."""
    return (catalogue.covers(statement, act) or KIND_SIBLINGS.get(statement) is act
            or KIND_SIBLINGS.get(act) is statement)


_DECIDING = frozenset({rq.Path.READY, rq.Path.EXCLUSION})


def _place_read_kinds(requirement: rq.Requirement, role: rq.Role) -> frozenset[Kind]:
    """The act kinds whose places ``requirement`` reads in ``role`` on a READY or exclusion path, from the requirement
    table's read-sets (a read made for every kind: the codable kinds)."""
    found: set[Kind] = set()
    for read in rq.RULES[requirement].every_read():
        if read.role is role and read.attribute is _A.TARGET_PLACES and read.paths & _DECIDING:
            found |= read.kinds if read.kinds is not None else rq.CODABLE_KINDS
    return frozenset(found)


# The rules of identity by place whose pairs get pair controls (3.2.3 [R:SC-B]; DECISIONS D196), each read from the
# requirement table: D118's one stricture (4.7 competing: two acts whose places the competition reads, both of these
# kinds), and bundling identity by place (4.7 bundling: an act of the first kinds beside a whole of the second).
STRICTURE_PAIR_KINDS: frozenset[Kind] = _place_read_kinds(rq.Requirement.COMBINATION, rq.Role.ACT)
BUNDLING_PAIR_KINDS: tuple[frozenset[Kind], frozenset[Kind]] = (
    _place_read_kinds(rq.Requirement.BUNDLING, rq.Role.ACT), _place_read_kinds(rq.Requirement.BUNDLING, rq.Role.WHOLE))


def _place_identity_pair(one: Kind | None, other: Kind | None) -> bool:
    """Whether two acts' kinds are read together by a rule of identity by place: both of STRICTURE_PAIR_KINDS, or one
    of BUNDLING_PAIR_KINDS' act kinds and the other of its whole kinds (either way round)."""
    if one is None or other is None:
        return False
    acts, wholes = BUNDLING_PAIR_KINDS
    return ((one in STRICTURE_PAIR_KINDS and other in STRICTURE_PAIR_KINDS)
            or (one in acts and other in wholes) or (other in acts and one in wholes))


def _distinct(places: list[Landmark]) -> list[Landmark]:
    """Each place once, in LANDMARKS2's order."""
    return [place for place in Landmark if place in places]


def units_phrase(units: Sequence[str]) -> str:
    """Unit ids as a sentence names them: S5; S5 and S6; S5, S6 and S7."""
    return joined(list(units))


def joined(items: list[str]) -> str:
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def _sentence(made: _Spec, card_of: Mapping[tuple[xs.Family, str], str]) -> str:
    """A spec's sentence: its template filled, every object named by its card's id."""
    def card(ref: Ref) -> str:
        return card_of[(ref.family, ref.object)]

    rendered: dict[str, str] = {}
    for slot, value in made.slots:
        if isinstance(value, Ref):
            rendered[slot.value] = card(value)
        elif isinstance(value, _Named):
            rendered[slot.value] = f'{value.noun} {joined([card(item) for item in value.refs])}'
        elif isinstance(value, tuple):
            rendered[slot.value] = joined([card(item) for item in value])
        else:
            rendered[slot.value] = value
    return template(made.template).format_map(rendered)


# --- the pins (FINAL-V2 2.5) ---------------------------------------------------------------------------------------------


def _members(values: Iterable[Enum]) -> list[str]:
    return sorted(str(member.value) for member in values)


def templates_document() -> dict[str, object]:
    """TEMPLATES' canonical form, whose sha256 the integration owner pins (TEMPLATES_SHA256): the templates, every label
    table, and which template renders each (class, attribute, state) and value."""
    return {
        'templates': {key.value: sentence for key, sentence in TEMPLATES.items()},
        'names_the_kind': _members(NAMES_THE_KIND),
        'kind_labels': {kind.value: list(forms) for kind, forms in KIND_LABELS.items()},
        'labels': [[type(member).__name__, str(member.value), text] for member, text in LABELS.items()],
        'place_labels': {place.value: text for place, text in PLACE_LABELS.items()},
        'place_label_depth': PLACE_LABEL_DEPTH,
        'statement_date_phrases': {relation.value: text for relation, text in STATEMENT_DATE_PHRASES.items()},
        'card_phrases': {card_type.value: text for card_type, text in CARD_PHRASES.items()},
        'format': {'cards_heading': CARDS_HEADING, 'claims_heading': CLAIMS_HEADING, 'card_line': CARD_LINE,
                   'card_words': CARD_WORDS, 'claim_line': CLAIM_LINE, 'document_card': DOCUMENT_CARD},
        'forms': [[object_class.value, attribute.value, state.value, form.value]
                  for (object_class, attribute, state), form in FORMS.items()],
        'forms_by_value': [[object_class.value, attribute.value, state.value, str(member.value), form.value]
                           for (object_class, attribute, state, member), form in FORMS_BY_VALUE.items()],
        'negated_values': [[object_class.value, attribute.value, _members(values)]
                           for (object_class, attribute), values in NEGATED_VALUES.items()],
    }


def statement_templates_document() -> dict[str, str]:
    """STATEMENT_TEMPLATES' canonical form (STATEMENT_TEMPLATES_SHA256)."""
    return {key.value: sentence for key, sentence in STATEMENT_TEMPLATES.items()}


def controls_document() -> dict[str, object]:
    """The CONTROLS generator's canonical form (CONTROLS_SHA256): its rules, its tables (KIND_SIBLINGS,
    SESSION_SIBLINGS, CONTRAST_PLACES with each place's candidates in order, DEVICE_SIBLINGS, TYPE_SIBLINGS,
    SUBTYPE_SIBLINGS and the contrary tables), the anatomy points, the contrast rule with the tract order a segment's
    range is read in and the fallback places, the other-object and reported-acts rules, the pair-control
    selection - with every (statement kind, act kind) pair it admits and the kinds the place-identity rules read, so a
    changed selection moves the pin (the arbiter's 2c#8) - the completeness rule, the rule that no control is a real
    claim, UNCONTROLLED, and the seed rule."""
    def rule(item: ControlRule) -> list[object]:
        return [item.object_class.value, item.attribute.value, item.state.value, item.contrary.value,
                None if item.values is None else _members(item.values),
                None if item.kinds is None else _members(item.kinds),
                None if item.as_attribute is None else item.as_attribute.value,
                None if item.as_state is None else item.as_state.value,
                None if item.table is None else item.table.value,
                None if item.fixed is None else str(item.fixed.value),
                None if item.form is None else item.form.value]

    def rows(name: Table) -> list[list[object]]:
        if name is Table.CONTRAST_PLACES:
            return [[place.value, [candidate.value for candidate in candidates]]
                    for place, candidates in CONTRAST_PLACES.items()]
        return [[str(key.value), str(value.value)] for key, value in table(name).items()]

    acts, wholes = BUNDLING_PAIR_KINDS
    return {
        'rules': [rule(item) for item in CONTROLS],
        'tables': {name.value: rows(name) for name in Table},
        'anatomy_point': [[key.value, value.value] for key, value in ANATOMY_POINT.items()],
        'contrast': ("the first candidate of the place (a segment: its first place's nearest candidates, then its last "
                     "place's, then the fallback places) that "
                     'engine/anatomy.compatible finds compatible with no place of the object - each value of its '
                     "target.places, of any state, its options included, and its segment's whole range: its two "
                     'places and every place between them in the tract order all of whose places are between them '
                     'too; every list ends with the fallback places; when every candidate is compatible with a place '
                     'of the object, the place is not claimed (control); a place with no candidates has no control'),
        'tract_order': [place.value for place in TRACT_ORDER],
        'contrast_fallback': [place.value for place in CONTRAST_FALLBACK],
        'another': ('the first object of its family in document order that a card can show and that is none of the '
                    "object's own values of the attribute (an inherited value included)"),
        'no_control_is_a_claim': 'a control never asserts what a real claim about the same object asserts '
                                 '(template, subject and filled slots); where pass 1 gives a value and its contrary, '
                                 'neither fact is claimed (contrary), nor any fact sharing either claim (partner)',
        'unwritable_control': 'a control the document calls for whose sentence needs a fact that is not claimable '
                              'leaves its fact unclaimed (control), and every fact sharing its claim (partner)',
        'reported_acts': 'acts pass 1 asserts performed, of a kind the statement covers (a contradicted '
                         "fact's options included); listed when their kind and status are claimable",
        'pair_controls': {
            'statements': _members(_TARGETED),
            'pair_kinds': [[statement.value, act.value] for statement in Kind for act in Kind
                           if _compatible(statement, act)],
            'acts': ("of a pair kind; the same session, or any session when the statement's session is not "
                     "claimable or the act's is not supported"),
            'stricture_kinds': _members(STRICTURE_PAIR_KINDS),
            'bundling_kinds': {'act': _members(acts), 'whole': _members(wholes)},
            'place_identity_pairs': 'two acts both of the stricture kinds, or one of the bundling act kinds and the '
                                    'other of the bundling whole kinds',
            'pairs_unless': 'both sessions claimable and different',
            'asks': 'each place of the other that none of its own places is compatible with (engine/anatomy); each '
                    'lesion of the other when the two lesion sets differ, never one of its own (its target lesion '
                    'and each listed target that may be claimed, member by member)',
            'both_directions': True,
        },
        'completeness': {'session_kind': SessionKind.EUS.value, 'tract': Tract.UPPER.value, 'stations': 'empty',
                         'claimable': 'the kind and the tract claimed; the list named by no doubt or finding',
                         'claim': T.SESSION_ALL_STATIONS.value, 'control': T.SESSION_SOME_STATIONS.value},
        'uncontrolled': [[entry.object_class.value, entry.attribute.value, entry.why.value,
                          None if entry.values is None else _members(entry.values)] for entry in UNCONTROLLED],
        'seed_rule': 'claims sorted by sha256_of([seed, content key]) and numbered K1..; the content key is sha256_of('
                     '[template, subject family, subject, value, units, params])',
    }
