"""The enteroscopy classes of design v2 (docs/gemini-migration/FINAL-V2.md 4.3 ENT, 4.7 and 5.5; step 4c of 8.1, repaired as
r4c for DECISIONS D216-D219, and for D231's classes half): v1's studio/interpretation/classes.py (DECISIONS D108, D114,
D141, D148, D153, D160) forked into engine/, its readers deleted and its inputs rewired to settled facts - a session's
kind, approach, through, reached and completion, the type of the anatomy entry it went through, its examinations' kind,
session and status, an act's own session fact, and the kept unlisted acts and doubts (3.2.6; D231). Nothing here reads
text: every input is an enumeration member, an id, a result or a span of the FactSet (engine/facts.py, step 2d).

**The class of a code** (code_class; D108): the descriptors' ranges, catalogue.ENTEROSCOPY_RANGES (step 1e) - 44360-44373
JEJUNAL, 44376-44379 ILEAL, 44380-44384 STOMA, 44385-44386 POUCH; no other code has one.

**What a fact leaves open** (FINAL-V2 4.2's possibly, read in any state, P3, P6: a doubt is never an absence). A
single-valued enumeration fact (_open) leaves open its value when supported; every other value when negated; and, when
it is not established, every value for an EMPTY slot - silent, or named by a doubt whose readings settle kept beside it
(3.3 rows 2 and 3; 4.2: a silent fact leaves every value possible) - and for a denial (state negated: the denial may be
wrong, and so may any other value), else its claimed value and its options (a contradicted fact's sides, a doubt's
readings, an unrejected control's value). A status that is not established leaves every status open (4.2's status
arm). The entry a session went through (_named) names its id when supported; nothing when negated (a denial names no
object as the one it is) or silent (a session that states no entry passed through names none: D114's problem 4); and,
when it is not established, its claimed id and its options - for an empty slot a doubt names, the doubt's readings. An
event's session (_may_name, D217's SILENT-EXAM) may name a session as _open reads an enumeration: the session it names
when supported; every other session when negated; every session for an empty slot (silent, or named by a doubt) and for
a denial not established; else its claimed session and its options - and every session, in any state but negated, when
its value or a reading names a session the FactSet does not hold (_unheld; 4.11: a missing identifier manufactures
neither a match nor a non-match; DECISIONS D227's 4d R2-2), as evaluate.py's membership reads it. A reached member
(_may_reach) may say its own point was reached unless it is established negated.

**The class fit** (class_fit; FINAL-V2 4.3 ENT: "approach supported (oral for jejunal and ileal; through_stoma with a
stoma entry; through_pouch with an ileal_pouch entry, never a gastric pouch or a Roux limb) and reached in the class
reach; for the deeper classes, completion not incomplete"), over ONE session, part by part. Each part is T, U or F (4.2,
the truth of a requirement) and each part that is not T gives its own witness; the class is T only when every part is.
- FAMILY: the session's kind supported enteroscopy (4.3 row 6, read again so that a class is never judged on another
  family's session). procedure (rank 8).
- APPROACH: the session's approach supported as one the class accepts (CLASS_APPROACHES: catalogue.
  ENTEROSCOPY_CLASS_APPROACH's oral for JEJUNAL and ILEAL - for JEJUNAL as 4.3 writes it, D207's accepted 1e:dev4 -,
  through_stoma for STOMA, through_pouch for POUCH; and, D219, transanal for POUCH: 1b's approach definition makes
  transanal a faithful filing of a pouchoscopy, and the pouch class then fits only when its through names an
  established ileal_pouch entry, which is the ROUTE part's own T, so a transanal approach never fits a gastric pouch or
  a Roux limb either). F when it is established as none of them (supported with another value, or a denial that leaves
  none of them open); U otherwise - a denial of one accepted approach leaves the other open. procedure.
- ROUTE: for STOMA and POUCH, the session's through supported, naming an anatomy entry whose type is supported as the
  class's (catalogue.ENTEROSCOPY_CLASS_ANATOMY: stoma; ileal_pouch). F when that entry's type is established as another,
  so a gastric pouch, a Roux limb or any other alteration never makes the pouch class (D141, D148: an entry is typed by
  its own type fact alone); U otherwise (through not supported, or the entry's type not established). D153's and D160's
  two pouches are told apart by the appraised through, whose control names the other entry (D196), never by words:
  route phrases, pouch words and gastric_beside are gone (4.7). For JEJUNAL and ILEAL, D114's two-route doubt: those
  classes need the oral route, so a through that may name an entry whose type leaves a stoma or an ileal pouch open
  leaves the route not verified (U, as v1 held a route named two ways); a through naming a gastric pouch, a Roux limb, a
  bypass or an anastomosis (an oral enteroscopy after a gastric bypass, D141's problem 0) doubts nothing. An approach
  established as another route already explains the hold, so beside it the route raises no doubt (T): a question there
  could never release the code (refute-4c-r1 B). procedure.
- REACH: a point of the session's reached SUPPORTED in the class's reach (catalogue.ENTEROSCOPY_CLASS_REACH: the
  jejunum; an ileal reach; an ileal reach through a stoma; an ileal reach or the pouch). F when every point of the
  class's reach is established as not reached (negated itself, or inside a negated point: "the ileum was not reached");
  U otherwise. A reach list is never read as complete (P3, SC-B): a supported point outside the class's reach (the
  jejunum for ILEAL; the duodenum, its bulb or any of its portions for every class - D204: the third and fourth portions
  stand where v1's duodenum stands, in no enteroscopy class) leaves the class's own reach unknown, so the requirement is
  U, a question, as v1's class and extent questions were. The jejunal class is "not including ileum" (D218): a point
  BEYOND it is every point the oral route reaches only through the ileum - the ileum's points (the deeper class's
  reach) and every point of the large bowel (PAST_THE_ILEUM: the colon's points, the ileocecal valve, the cecum and the
  appendiceal orifice among them, and the rectum's and the anal canal's, NOTES.md Q1). A beyond point supported among
  the reached points is F (the installed release's furthest landmark fits no jejunal class there); a reached point that
  may be a beyond point (one only possible: its value or an option beyond, not established negated) is U, whatever the
  jejunal points say. A member that names only a region containing both the jejunal reach and the ileum - the small
  bowel - is no beyond point (D218): [small_bowel, jejunum] fits the jejunal class (4.3's literal row; the installed
  extent is the jejunum), and the small bowel alone fits no class, as installed. No other point contains a beyond point
  without being one (engine/anatomy.py's containment; tests/v2/test_classes.py pins it). device_reached is never read
  (K6, P19), nor reached_anatomy (no class rule's read-set has it). extent (rank 14).
  **The one release this reading allows** (D218; named here and in NOTES.md for 6a's P-MONO, 4c's request R6): 9.4's
  deleted-member weakening releases a jejunal code (44360-44373) when the deleted reached member was the beyond point -
  supported, or one that may be beyond. It is accepted: the final report lists it as a residual. Requiring a stated
  non-reach instead would hold every push enteroscopy (D218).
- COMPLETION (ILEAL, the deeper class: catalogue.ENTEROSCOPY_DEEPER; D43, D56; D217: the completion is a
  disqualifier): T when it is established complete, or SILENT - no claim, no doubt naming the slot and nothing left
  possible beside it (_silent: result unknown, state None, no option, silence its only reason) - for silence states no
  incompleteness (D108, D56; the installed reading). F when it is established incomplete or terminated (supported
  incomplete or terminated, or denied complete; CO-8 groups terminated with incomplete), in the incomplete form. U
  otherwise, with ONE completion question: unresolved in any form (hedged, reported, detached by pass 2, a control left
  unrejected), doubted (a doubt naming the completion or its empty slot, whatever its readings), contradicted (whatever
  value the claim keeps - asked at rank 1), and every other denial (not complete is established only by denying
  complete). extent.
- EXAMINATION (ILEAL; D72 as D217 reads it): the session's examinations - the events whose kind leaves examination open
  and whose session fact may name the session (_may_name: a silent, doubted, unresolved or contradicted slot with this
  session possible, D217's SILENT-EXAM, and a slot naming a session the FactSet does not hold, 4.11 and D227's 4d R2-2,
  so a dangling session id is a question on that examination's session, never a fit; 4.9's EXAMINATION role, found by
  its own session and kind facts - the session's
  own examination slot is no claim, 3.2.1) - and its synthetic examination acts (D216, D231: a kept unlisted act or
  doubt whose kind is examination or none named, whose card names this session, none, or a session the FactSet does
  not hold - 4.11 -, 3.2.6 rule 3's synthetic doubted act; a doubt about whether an act was done leaves it possibly
  performed, refute-r4a-r1 F1, so an unlisted doubt gives the outcome the unlisted act and the filed doubted
  examination give). T when an examination of the session is established performed (kind supported examination,
  session supported this one, status supported performed): an attempt beside it does not count against the class -
  pass 1's filing of a failed attempt followed by success - and the completion decides. T when no examination of the
  session may be attempted and there is no synthetic examination act. F only when an examination of the session is
  established attempted_not_completed (its status, kind and session each supported) and no examination of the session
  may be performed, filed or synthetic: every examination of the session is established attempted (one established
  neither performed nor attempted, a planned one, never makes it fit: NOTES.md Q2). U otherwise: one question per
  examination of the session whose doubt decides - resting on its status when that is not established, else on its tie
  to the session that is not (its session, else its kind), else on the status (an established status the class rule
  doubts) - and one per synthetic act (a doubt about an act no card describes: performed_status, rank 2, cause
  unlisted, quoting its own units, none when it has none - never the session's reach). extent.

**The witnesses** (engine/types.HeldFact, 4.4). A part that is not T gives one: a QUESTION for U, an EXPLANATION for F
(cause CLASS_CAUSE, no reason). A question's cause comes from the fact's own result and first reason (reading_unknown,
reading_contradicted, appraisal:<verdict or coherence>, unestablished:<reason>; CLASS_CAUSE for a doubt this rule raises
over established facts), and its fact key and rank are RANK's for what it rests on (4.8; requirements.py: "A
contradicted fact of any requirement asks rank 1 (conflict:<kind>) and a doubt on status rank 2, whatever the
requirement"): a contradicted fact asks conflict:<kind> at rank 1 (D217) - the kind is the session's examination for a
session's or an anatomy entry's fact, an event's one label (facts.established_kind: DECISIONS D287, its supported
catalogue kind, else other) for an event's -; a status a doubt names asks performed_status at rank 2; any other the
part's own row: procedure (rank 8) for the family, approach and route parts and a supporting act's session, extent (rank
14) for the reach, the completion and the examinations. Every witness is kept (4.4: a hold carries all its unresolved
facts); which one is asked is RANK's choice (4.8), and D89's "one item naming both doubts" is the wording's, over
held_facts (step 3c).
misfit_form gives v1's question form (class_hold's CLASS, INCOMPLETE, EXTENT or ROUTE) over the same parts, for that
wording; its INCOMPLETE form ("is stated to be incomplete") needs the stopping short STATED by a deeper part's own claim
(PartFit.stated).

**act_elsewhere** (D114, as FINAL-V2 4.7 and 4.13 rewire it: "act_elsewhere becomes the act's own session fact"; "the
region moves of D114, D141, D148 and D153: the act's own session fact"): a code of an act whose every POSITIVE candidate
of one of its requirement groups (4.4: its kind may cover the group, its status is not denied performed and may be
performed or attempted, and neither its date relation nor its performer is established as another) is done - kind
supported and covering the group (never an umbrella), status supported performed, effective date relation supported on
the date of service, effective performer supported the documenting team, entry supported the documenting clinician
(4.3 rows 1-5) - and has its own session fact supported naming a session whose kind is supported as another family (an
upper endoscopy's, say), is held: elsewhere_hold's EXPLANATION, performed_status at the status row (rank 4), cause
ELSEWHERE_CAUSE, one per such act (every candidate's witness, 4.4). A positive candidate in doubt on any of rows 1-5, or
in its own family's session, or whose session is not established, keeps its group out of the rule: its own question
(4.4's SUPPORT rows) is then the code's, which an explanation that can never become T must not outrank (refute-4c-r1 C).
So does a kept unlisted act or doubt whose kind may cover the group - every kind when it names none; a clip or an
injection, whose purpose no card states, read as a bleeding control too where the group names one - in any session
(D216: 3.2.6 rule 3's synthetic doubted act is a possibly performed act wherever a rule's condition is the absence of
one; D231: so is an unlisted doubt, as the same doubt filed as a positive candidate in doubt is). Nothing moves (5.4:
coverage.coding_family retires; K3 can only unresolve a session fact), so no region, place or reach is read.
v1's second arm (the enteroscopy's examination code held beside a moved act) has no counterpart here: with no move, an
act Gemini places in another session is not the enteroscopy's, and one whose session is in doubt holds the examination
code through base_included's possible acts (4.7, step 4d), never through this module. It never makes a code READY or
EXCLUDED.

**The absence conditions** (D216, D231; NOTES.md lists each): act_elsewhere's (no positive candidate in doubt, in its
own family's session or unplaced) and the examination part's F (no examination of the session that may be performed)
read the synthetic act as a possibly performed act of its kind; the examination part's T (no examination of the session
that may be attempted) reads it as one that may be attempted (4.2's status arm: a doubted act's status is open). The
synthetic act is a kept unlisted ACT or DOUBT, never a DENIAL (POSSIBLY_PERFORMED, synthetic_possible: evaluate.py's
set, which D231 gives coverage.py and combination.py too, so that the four modules read one set - O17), so each of the
three conditions gives an unlisted doubt the outcome it gives an unlisted act and the same doubt filed as an event whose
status is doubted. The other conditions here read no act: the beyond points, the two-route doubt, a class reach denied
whole and a silent completion.

**enteroscopy_hold** (v1's name; D89): every witness of an enteroscopy code - the class fit of each session its
supporting acts (E*, 4.4's code_requirements) are in, and its elsewhere acts. A supporting act whose session fact is
not supported cannot be placed, and gives a procedure question rather than being skipped.

**What it reads** (P-READSET, P-INDEP, 9.4): only attributes the enteroscopy codes' requirement closure reads
(engine/requirements.dependencies): a session's kind, approach, through, reached and completion; an anatomy entry's
type; an event's kind, session and status (EXAMINATION role) and, for an act of a requirement group, its kind, purpose
(a clip or an injection, for a code covering bleeding control), status, date relation, performer, entry and session,
and its session's kind (SUPPORT rows 1-6); and the kept unlisted statements (3.2.6: what, kind, session and units),
with the FactSet's session ids for a card or an event's session fact that names a session it does not hold (4.11).
tests/v2/test_classes.py records the reads and pins them inside the closure.

**The text-free boundary** (P1; FINAL-V2 4.1, 5.7 measure 4): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, facts, requirements and types only - no retired v1 module, none of
contract's text modules - holds no word, phrase or marker list (every module-level collection holds enumeration
members), and returns no document text: a witness's fact and cause are CPT Studio's own codes, and its spans are integer
spans for wording.quote after the decision.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation.contract.types import (AnatomyType, Approach, Attribute, Completion, DateRelation, Extent,
                                                  FactState, Kind, Owner, Performer, Purpose, Qualifier2, Reason,
                                                  Result, SessionKind, Status, UnlistedWhat, VerdictValue)
from studio.interpretation.engine import anatomy, catalogue
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine.catalogue import EnteroscopyClass
from studio.interpretation.engine.requirements import FactKey, Rank, fact_key
from studio.interpretation.engine.types import (Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span,
                                                UnlistedStatement)

_E = TypeVar('_E', bound=Enum)
_A = Attribute
_SESSION, _ANATOMY, _EVENT = IdFamily.SESSION, IdFamily.ANATOMY, IdFamily.EVENT

# The family whose codes have a class (D108), and the classes in catalogue order.
FAMILY: SessionKind = SessionKind.ENTEROSCOPY
CLASSES: tuple[EnteroscopyClass, ...] = tuple(EnteroscopyClass)
# The classes that pass through an anatomy entry (STOMA, POUCH) and those that need the oral route (JEJUNAL, ILEAL), and
# the anatomy type each such route needs (classes.ROUTES as Approach -> AnatomyType: through_stoma a stoma,
# through_pouch an ileal pouch), all derived from catalogue's tables (step 1e) so that one table decides each.
ROUTE_CLASSES: frozenset[EnteroscopyClass] = frozenset(catalogue.ENTEROSCOPY_CLASS_ANATOMY)
ORAL_CLASSES: frozenset[EnteroscopyClass] = frozenset(
    exam_class for exam_class in CLASSES if catalogue.ENTEROSCOPY_CLASS_APPROACH[exam_class] is Approach.ORAL)
ROUTE_ANATOMY: Mapping[Approach, AnatomyType] = MappingProxyType({
    catalogue.ENTEROSCOPY_CLASS_APPROACH[exam_class]: catalogue.ENTEROSCOPY_CLASS_ANATOMY[exam_class]
    for exam_class in CLASSES if exam_class in ROUTE_CLASSES})
# The approaches that enter an anatomy entry of a type directly (D219: 1b's approach definition makes transanal a
# faithful filing of a pouchoscopy), accepted for the class that passes through an entry of that type: the class then
# fits only when its through names an established entry of that type, which its ROUTE part asks (module docstring).
ENTRY_APPROACHES: Mapping[AnatomyType, frozenset[Approach]] = MappingProxyType({
    AnatomyType.ILEAL_POUCH: frozenset({Approach.TRANSANAL})})


def _class_approaches(exam_class: EnteroscopyClass) -> frozenset[Approach]:
    own = frozenset({catalogue.ENTEROSCOPY_CLASS_APPROACH[exam_class]})
    if exam_class not in ROUTE_CLASSES:
        return own
    return own | ENTRY_APPROACHES.get(catalogue.ENTEROSCOPY_CLASS_ANATOMY[exam_class], frozenset())


# The approaches each class accepts (module docstring, APPROACH): the catalogue's, and D219's transanal for POUCH.
CLASS_APPROACHES: Mapping[EnteroscopyClass, frozenset[Approach]] = MappingProxyType({
    exam_class: _class_approaches(exam_class) for exam_class in CLASSES})
# The regions the oral route reaches only through the ileum, past it (D218): the large bowel's - the colon (whose points
# include the ileocecal valve, the cecum and the appendiceal orifice), the rectum and the anal canal (anatomy.REGION_OF).
PAST_THE_ILEUM_REGIONS: frozenset[anatomy.Region] = frozenset({
    anatomy.Region.COLON, anatomy.Region.RECTUM, anatomy.Region.ANUS})
PAST_THE_ILEUM: frozenset[Extent] = frozenset(
    point for point in Extent if anatomy.region(point) in PAST_THE_ILEUM_REGIONS)
# The points beyond an oral class that its code's descriptor excludes (D218): the jejunal class is "not including
# ileum", so every point the oral route reaches only through the ileum lies beyond it - the deeper oral class's reach
# (catalogue.ENTEROSCOPY_DEEPER: the ileal points) and every point past the ileum (module docstring, REACH). Derived from
# catalogue's and anatomy's tables; the deeper class itself has nothing beyond it.
BEYOND: Mapping[EnteroscopyClass, frozenset[Extent]] = MappingProxyType({
    exam_class: frozenset(point for deeper in CLASSES if deeper in catalogue.ENTEROSCOPY_DEEPER & ORAL_CLASSES
                          for point in catalogue.ENTEROSCOPY_CLASS_REACH[deeper]) | PAST_THE_ILEUM
    for exam_class in CLASSES if exam_class in ORAL_CLASSES - catalogue.ENTEROSCOPY_DEEPER})
# The completions that keep the deeper class from fitting (D43, D56; CO-8's terminated with incomplete, as R6:extent and
# the 52/53 consideration read them: an examination that stopped short of the extent it set out to reach; D217, Q5 as
# built).
STOPPED_SHORT: frozenset[Completion] = frozenset({Completion.INCOMPLETE, Completion.TERMINATED})
# The reasons of a fact a doubt names (3.3 row 2): its status, so named, asks rank 2 (4.8).
DOUBT_REASONS: frozenset[Reason] = frozenset({Reason.DOUBT_STATED, Reason.DOUBT_UNCLEAR})
# The kind a conflict on a session's or an anatomy entry's fact names (conflict:<kind>): the session's examination.
SESSION_CONFLICT_KIND: Kind = Kind.EXAMINATION
# The natures of a kept unlisted entry the absence conditions read as a possibly performed act (D216; DECISIONS D231,
# refute-r4a-r1 F1): an ACT (3.2.6 rule 3's synthetic doubted act) and a DOUBT (4.2 [R:HO-1]: a doubt about whether an
# act was done leaves it possibly performed); never a DENIAL, a statement that it was not done (3.2.6 rule 4 pairs it).
# The set evaluate.synthetic_possible reads; D231 gives it to coverage and combination too, so the four read one (O17).
POSSIBLY_PERFORMED: frozenset[UnlistedWhat] = frozenset({UnlistedWhat.ACT, UnlistedWhat.DOUBT})

# The witnesses' causes (FINAL-V2 4.4), operator data that names no vendor: an established fact failing the class
# (an explanation), or a doubt the class rule raises over established facts; an act documented in another family's
# session; a fact read as unknown or contradicted; an unresolved fact's own reason or appraisal; an unlisted act.
CLASS_CAUSE = 'coding_rule:enteroscopy_class'
ELSEWHERE_CAUSE = 'coding_rule:act_elsewhere'
READING_UNKNOWN = 'reading_unknown'
READING_CONTRADICTED = 'reading_contradicted'
UNESTABLISHED = 'unestablished'
UNLISTED = 'unlisted'


@unique
class Coherence(Enum):
    """The appraisal outcomes 3.2.3's coherence table names that are no verdict, as a cause names them (4.4:
    appraisal:<verdict or coherence>)."""
    INCOHERENT = 'control_incoherent'
    DETACHED = 'detached'
    MISSING = 'missing'


# Each appraisal reason of 3.3 row 9 -> the verdict or coherence its cause names.
APPRAISAL_CAUSES: Mapping[Reason, VerdictValue | Coherence] = MappingProxyType({
    Reason.APPRAISAL_CONTRADICTS: VerdictValue.CONTRADICTS, Reason.APPRAISAL_UNCLEAR: VerdictValue.UNCLEAR,
    Reason.APPRAISAL_QUALIFIED: VerdictValue.QUALIFIED, Reason.CONTROL_INCOHERENT: Coherence.INCOHERENT,
    Reason.APPRAISAL_DETACHED: Coherence.DETACHED, Reason.APPRAISAL_MISSING: Coherence.MISSING,
    **{Reason(f'appraisal_qualified:{qualifier.value}'): VerdictValue.QUALIFIED for qualifier in Qualifier2},
})


@unique
class Truth(Enum):
    """The truth of a requirement (FINAL-V2 4.2, B's Kleene view): T when its facts hold the needed values, F when a fact
    is established against them, U otherwise (9.1's trace writes it)."""
    T = 'T'
    U = 'U'
    F = 'F'


@unique
class Part(Enum):
    """The parts of the ENT requirement (module docstring), each judged on its own facts."""
    FAMILY = 'family'
    APPROACH = 'approach'
    ROUTE = 'route'
    REACH = 'reach'
    COMPLETION = 'completion'
    EXAMINATION = 'examination'


# The parts that decide the route (the approach, and the anatomy entry it passes through or the two-route doubt) and
# those that keep only the deeper class from fitting (misfit_form reads them as v1's route and incomplete forms).
ROUTE_PARTS: frozenset[Part] = frozenset({Part.APPROACH, Part.ROUTE})
DEEPER_PARTS: frozenset[Part] = frozenset({Part.COMPLETION, Part.EXAMINATION})


@unique
class ClassForm(Enum):
    """v1's form of a class hold (classes.class_hold's CLASS_FORM, INCOMPLETE_FORM, EXTENT_FORM and ROUTE_FORM, D43,
    D108, D114), for the wording of step 3c: the class question (the reach fits the code's own class or another class),
    its incomplete form (only a STATED incompleteness keeps the code's own class from fitting: v1's sentence "is stated
    to be incomplete"), R6's extent question (a reach no class fits) and the route question (the reach fits and only the
    route is not verified)."""
    CLASS = 'class'
    INCOMPLETE = 'incomplete'
    EXTENT = 'extent'
    ROUTE = 'route'


@dataclass(frozen=True, slots=True)
class PartFit:
    """One part's truth, and its witness (None when it is T). ``stated``, for a deeper part that is not T: its own
    claims state the stopping short (a completion claimed incomplete or terminated, or denied complete, in any result; an
    examination claimed attempted_not_completed whose kind and session claims name an examination of this session), so
    v1's incomplete form is true of it; False when the stopping short is only possible (a doubt's reading, a control
    left unrejected, a doubted empty slot, an examination only possibly of the session, a synthetic act) and for every
    other part."""
    part: Part
    truth: Truth
    witness: HeldFact | None
    stated: bool = False


@dataclass(frozen=True, slots=True)
class ClassFit:
    """The class fit of ``exam_class`` on ``session``: each part's truth and witness, in the order the module docstring
    lists them (the deeper parts only for ILEAL: a single EXAMINATION part that is T, or one per examination of the
    session whose established attempt makes the class F, or one per examination and synthetic act whose doubt makes it
    U)."""
    exam_class: EnteroscopyClass
    session: Id
    parts: tuple[PartFit, ...]

    @property
    def truth(self) -> Truth:
        """F when a part is F, else U when a part is U, else T (Kleene conjunction)."""
        truths = {part.truth for part in self.parts}
        return Truth.F if Truth.F in truths else Truth.U if Truth.U in truths else Truth.T

    @property
    def witnesses(self) -> tuple[HeldFact, ...]:
        """Every part's witness, in part order: () exactly when the class fits."""
        return tuple(part.witness for part in self.parts if part.witness is not None)


@dataclass(frozen=True, slots=True)
class Elsewhere:
    """An act of a code's requirement group placed, by its own session fact, in a session of another family (module
    docstring): the act, that session, its family, and the group."""
    event: Id
    holder: Id
    family: SessionKind
    group: tuple[Kind, ...]


# --- reading facts ---------------------------------------------------------------------------------------------------


def code_class(code: str) -> EnteroscopyClass | None:
    """classes.code_class: the class of an enteroscopy code (catalogue.code_class, D108), None for any other code."""
    return catalogue.code_class(code)


def _open(found: Fact, domain: type[_E]) -> frozenset[_E]:
    """The values of ``domain`` a single-valued ``found`` leaves open, in any state (module docstring): its value when
    supported; every other value when negated; when it is not established, every value for an empty slot (silent, or
    named by a doubt: 4.2) and for a denial (state negated), else its claimed value and its options. A value outside
    ``domain`` (never in a FactSet facts.py built) leaves every value open. An overfilled slot's merged view
    (AMENDMENT-2 4.3.3 a, facts.overfilled) leaves every value open, as a written denial read alone would - every view,
    since it cannot tell whether a written fact denied a value (facts.open_denial: the fail-closed reading, the step's
    NOTES question Q1R). Weakening a fact (FINAL-V2 9.4 P-MONO) can only widen what it leaves open."""
    if found.result is Result.SUPPORTED:
        return frozenset({found.value}) if isinstance(found.value, domain) else frozenset(domain)
    if found.result is Result.NEGATED:
        return frozenset(member for member in domain if member != found.value)
    if found.state is None or facts_.open_denial(found):
        return frozenset(domain)
    return frozenset(value for value in (found.value, *found.options) if isinstance(value, domain))


def _open_status(found: Fact) -> frozenset[Status]:
    """The statuses ``found`` leaves open: every status when it is not established (4.2's status arm [R:HO-1][R:HO-3]:
    a doubt about whether an act was done is a doubt about every status), else _open's."""
    return _open(found, Status) if facts_.established(found) else frozenset(Status)


def _named(found: Fact, family: IdFamily) -> tuple[Id, ...]:
    """The ids of ``family`` the entry a session went through (its ``through``) may name, in order (module docstring):
    its value when supported; none when negated or silent (D114's problem 4); when it is not established, its claimed
    value and its options (for an empty slot a doubt names, the doubt's readings: 3.3 row 2)."""
    if found.result is Result.NEGATED:
        return ()
    values = (found.value,) if found.result is Result.SUPPORTED else (found.value, *found.options)
    return tuple(dict.fromkeys(value for value in values if isinstance(value, Id) and value.family is family))


def _unheld(found: Fact, R: FactSet) -> bool:
    """Whether a session fact ``found`` that is not negated names a session the FactSet does not hold - its value, and
    when it is not established also a reading (an option): a dangling id, which settle keeps as the claimed value,
    unresolved (pass 1's I4 reference_invalid; coverage.sessions_of). 4.11: a missing identifier manufactures neither a
    match nor a non-match, and DECISIONS D227's 4d R2-2: a session id the FactSet does not hold reads as possibly any
    session for membership - as evaluate._may_be_in reads it. A negated fact (a denial of that id) is _may_name's own
    arm."""
    if found.result is Result.NEGATED:
        return False
    named = (found.value,) if facts_.established(found) else (found.value, *found.options)
    return any(isinstance(value, Id) and value not in R.sessions for value in named)


def _may_name(found: Fact, subject: Id, R: FactSet) -> bool:
    """Whether an event's session fact ``found`` leaves ``subject`` possible, in any state (D217's SILENT-EXAM; module
    docstring), as _open reads an enumeration: supported, when it names it; negated, when it names another (a denial of
    one session leaves every other); when it is not established, always for an empty slot (silent, or named by a doubt:
    4.2) and for a denial (the denial may be wrong), else when it is its claimed value or an option. And always when it
    names a session the FactSet does not hold (_unheld: 4.11, D227's 4d R2-2), in any state but negated - so an
    examination established begun whose session is a dangling id makes the deeper class U with a question on its
    session, never T. An overfilled session slot's merged view (AMENDMENT-2 4.3.3 a) leaves every session possible, as
    a written denial read alone would - every view, since it cannot tell whether a written fact denied a session
    (facts.open_denial; the step's NOTES question Q1R). Weakening the fact can only turn False into True."""
    if _unheld(found, R):
        return True
    if found.result is Result.SUPPORTED:
        return found.value == subject
    if found.result is Result.NEGATED:
        return found.value != subject
    if found.state is None or facts_.open_denial(found):
        return True
    return found.value == subject or subject in found.options


def _may_reach(member: Fact) -> frozenset[Extent]:
    """The points a reached member may say the endoscope reached: its point when supported; none when it is established
    negated ("X was not reached" says nothing about another point); when it is not established, its claimed point (a
    denial not established may be wrong) and its options."""
    if member.result is Result.NEGATED:
        return frozenset()
    values = (member.value,) if member.result is Result.SUPPORTED else (member.value, *member.options)
    return frozenset(value for value in values if isinstance(value, Extent))


def _silent(found: Fact) -> bool:
    """A SILENT slot (D217): nothing stated - no claim (state None), result unknown - no doubt naming it, and nothing
    left possible beside it (no option, silence its only reason). A doubted empty slot (a doubt's reason, or its readings
    kept as options), a contradicted one and one a check failed on are not silent."""
    return (found.state is None and found.result is Result.UNKNOWN and not found.options and bool(found.reasons)
            and all(reason is Reason.SILENT for reason in found.reasons))


def _doubted(found: Fact) -> bool:
    """A fact a doubt names (3.3 row 2): unknown, with a doubt's reason."""
    return found.result is Result.UNKNOWN and any(reason in DOUBT_REASONS for reason in found.reasons)


def _claims(found: Fact, value: object) -> bool:
    """Whether pass 1's own claim of ``found`` states ``value``, whatever settle made of it: claimed supported as it, or
    contradicted with it a side - never for an overfilled slot's merged view (AMENDMENT-2 4.3.3 b [R:truth-T5]: a denied
    or unwritten value is never worded as stated, and the view's options cannot tell a written value from a doubt's
    reading, nor a value one written fact states from one another denies; so a view states nothing here, and its class
    hold takes the class form, never "is stated to be incomplete" - the fail-closed wording, the step's NOTES question
    Q-STATED)."""
    if facts_.overfilled(found):
        return False
    return ((found.state is FactState.SUPPORTED and found.value == value)
            or (found.state is FactState.CONTRADICTED and value in found.options))


def _one_of(found: Fact, wanted: frozenset[_E]) -> Truth:
    """T when ``found`` is supported as a value of ``wanted``; F when it is established against them all (supported with
    another value, or negated as the only value wanted); U otherwise (not established, or a denial that leaves a wanted
    value open)."""
    if found.result is Result.SUPPORTED:
        return Truth.T if found.value in wanted else Truth.F
    if found.result is Result.NEGATED and wanted <= {found.value}:
        return Truth.F
    return Truth.U


def _one(found: Fact, wanted: _E) -> Truth:
    """_one_of over the one value ``wanted``."""
    return _one_of(found, frozenset({wanted}))


def _cause(found: Fact) -> str:
    """The cause of a question resting on ``found`` (FINAL-V2 4.4): reading_unknown (silent or doubted),
    reading_contradicted, appraisal:<verdict or coherence> for an appraisal reason, unestablished:<reason> for any other
    reason of an unresolved fact; CLASS_CAUSE when the fact is established (the doubt is the class rule's own)."""
    if found.result is Result.UNKNOWN:
        return READING_UNKNOWN
    if found.result is Result.CONTRADICTED:
        return READING_CONTRADICTED
    if found.result is not Result.UNRESOLVED:
        return CLASS_CAUSE
    reason = found.reasons[0] if found.reasons else None
    if reason is None:
        return UNESTABLISHED
    appraisal = APPRAISAL_CAUSES.get(reason)
    if appraisal is not None:
        return f'appraisal:{appraisal.value}'
    return f'{UNESTABLISHED}:{reason.value}'


def _conflict_kind(subject: Id, R: FactSet) -> Kind:
    """The kind conflict:<kind> names (4.8 rank 1): for an event, its one label (facts.established_kind: the catalogue
    kind of its supported kind with its supported purpose, else Kind.OTHER - DECISIONS D287, D267's heading: every fact
    key that names an act names that kind, as evaluate's, coverage's and questions.act_kind do); for a session's or an
    anatomy entry's fact, the session's examination (SESSION_CONFLICT_KIND)."""
    if subject.family is not _EVENT:
        return SESSION_CONFLICT_KIND
    return facts_.established_kind(R, subject)


def _ordered(spans: Iterable[Span]) -> tuple[Span, ...]:
    return tuple(sorted(set(spans)))


def _reach_spans(session: Id, R: FactSet) -> tuple[Span, ...]:
    """The spans of the session's reached points, each once, in document order: what a class question quotes when its
    own fact cites nothing."""
    return _ordered(span for member in facts_.members(R, session, _A.REACHED) for span in member.spans)


def _witness(question: bool, key: FactKey, rank: Rank, attribute: Attribute, subject: Id, found: Fact,
             spans: tuple[Span, ...], R: FactSet) -> HeldFact:
    """A witness resting on ``found`` (module docstring, the witnesses): a QUESTION (U: its cause from the fact, the
    fact's first reason when it is not established; its fact key and rank RANK's - conflict:<kind> at rank 1 for a
    contradicted fact, performed_status at rank 2 for a status a doubt names, else ``key`` at ``rank``) or an
    EXPLANATION (F: CLASS_CAUSE, no reason, ``key`` at ``rank``, as an established fact fails the class)."""
    reason = found.reasons[0] if question and found.reasons and not facts_.established(found) else None
    fact, at = fact_key(key), rank
    if question and found.result is Result.CONTRADICTED:
        fact, at = fact_key(FactKey.CONFLICT, _conflict_kind(subject, R)), Rank.CONFLICT
    elif question and attribute is _A.STATUS and _doubted(found):
        fact, at = fact_key(FactKey.PERFORMED_STATUS), Rank.DOUBT
    return HeldFact(fact=fact, attribute=attribute, subject=subject, result=found.result,
                    kind=ItemKind.QUESTION if question else ItemKind.EXPLANATION,
                    cause=_cause(found) if question else CLASS_CAUSE, reason=reason, spans=spans, rank=at.value)


def _part(part: Part, truth: Truth, key: FactKey, rank: Rank, attribute: Attribute, subject: Id, found: Fact,
          spans: tuple[Span, ...], R: FactSet, stated: bool = False) -> PartFit:
    """A part's truth and its witness: none for T; a question for U; an explanation for F (_witness)."""
    if truth is Truth.T:
        return PartFit(part, truth, None)
    return PartFit(part, truth, _witness(truth is Truth.U, key, rank, attribute, subject, found, spans, R), stated)


# --- the routes an anatomy entry opens (classes.routes, doubted_routes, over the session's through) ---------------------


def routes(session: Id, R: FactSet) -> frozenset[Approach]:
    """The routes the session's anatomy establishes (v1's classes.routes, D141, D148): through_stoma when its through is
    supported naming an anatomy entry whose type is supported stoma; through_pouch when that type is supported
    ileal_pouch - never a gastric pouch or a Roux limb. Only the entry the session went through is read: no other
    anatomy entry types it (D148), and none opens a route by being there (D114: an anatomy that has a stoma never says
    the examination went through it)."""
    through = facts_.fact(R, session, _A.THROUGH)
    if through.result is not Result.SUPPORTED or not isinstance(through.value, Id) or through.value.family is not _ANATOMY:
        return frozenset()
    kind = facts_.fact(R, through.value, _A.TYPE)
    return frozenset(approach for approach, needed in ROUTE_ANATOMY.items() if facts_.holds(kind, needed))


def doubted_routes(session: Id, R: FactSet) -> frozenset[Approach]:
    """The routes the session's anatomy may open and does not establish (v1's classes.doubted_routes, D141, D148): those
    whose anatomy type an entry its through may name (_named) leaves open (_open: a type that is silent, doubted or
    denied without being established leaves every type open). A pouch of no established type is such a doubt; it opens
    no class."""
    through = facts_.fact(R, session, _A.THROUGH)
    found: set[Approach] = set()
    for entry in _named(through, _ANATOMY):
        left = _open(facts_.fact(R, entry, _A.TYPE), AnatomyType)
        found.update(approach for approach, needed in ROUTE_ANATOMY.items() if needed in left)
    return frozenset(found) - routes(session, R)


# --- the parts of the class fit ----------------------------------------------------------------------------------------


def _family(session: Id, R: FactSet) -> PartFit:
    kind = facts_.fact(R, session, _A.KIND)
    return _part(Part.FAMILY, _one(kind, FAMILY), FactKey.PROCEDURE, Rank.PROCEDURE, _A.KIND, session, kind,
                 kind.spans or _reach_spans(session, R), R)


def _approach(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> PartFit:
    found = facts_.fact(R, session, _A.APPROACH)
    truth = _one_of(found, CLASS_APPROACHES[exam_class])
    return _part(Part.APPROACH, truth, FactKey.PROCEDURE, Rank.PROCEDURE, _A.APPROACH, session, found,
                 found.spans or _reach_spans(session, R), R)


def _route(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> PartFit:
    through = facts_.fact(R, session, _A.THROUGH)
    spans = through.spans or _reach_spans(session, R)
    if exam_class in ROUTE_CLASSES:
        needed = catalogue.ENTEROSCOPY_CLASS_ANATOMY[exam_class]
        entry = through.value if through.result is Result.SUPPORTED and isinstance(through.value, Id) else None
        if entry is None or entry.family is not _ANATOMY:
            return _part(Part.ROUTE, Truth.U, FactKey.PROCEDURE, Rank.PROCEDURE, _A.THROUGH, session, through, spans, R)
        kind = facts_.fact(R, entry, _A.TYPE)
        return _part(Part.ROUTE, _one(kind, needed), FactKey.PROCEDURE, Rank.PROCEDURE, _A.TYPE, entry, kind,
                     kind.spans or spans, R)
    approach = facts_.fact(R, session, _A.APPROACH)
    if _one_of(approach, CLASS_APPROACHES[exam_class]) is Truth.F:
        return PartFit(Part.ROUTE, Truth.T, None)  # the approach, established as another route, explains the hold
    if not routes(session, R) | doubted_routes(session, R):
        return PartFit(Part.ROUTE, Truth.T, None)
    return _part(Part.ROUTE, Truth.U, FactKey.PROCEDURE, Rank.PROCEDURE, _A.THROUGH, session, through, spans, R)


def _denies(denial: Fact, point: Extent) -> bool:
    """Whether a negated reached point says ``point`` was not reached: the same point, or a point containing it."""
    return isinstance(denial.value, Extent) and (denial.value is point or anatomy.contains(denial.value, point))


def _reach(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> PartFit:
    wanted = catalogue.ENTEROSCOPY_CLASS_REACH[exam_class]
    beyond = BEYOND.get(exam_class, frozenset())
    points = facts_.members(R, session, _A.REACHED)
    spans = _reach_spans(session, R)
    past = next((member for member in points if member.result is Result.SUPPORTED and member.value in beyond), None)
    if past is not None:
        return _part(Part.REACH, Truth.F, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session, past, spans, R)
    if any(member.result is Result.SUPPORTED and member.value in wanted for member in points):
        maybe_past = next((member for member in points if _may_reach(member) & beyond), None)
        if maybe_past is None:
            return PartFit(Part.REACH, Truth.T, None)
        return _part(Part.REACH, Truth.U, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session, maybe_past, spans, R)
    denials = tuple(member for member in points if member.result is Result.NEGATED)
    if wanted and all(any(_denies(denial, point) for denial in denials) for point in wanted):
        denial = next(denial for denial in denials if any(_denies(denial, point) for point in wanted))
        return _part(Part.REACH, Truth.F, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session, denial, spans, R)
    open_point = next((member for member in points if not facts_.established(member)
                       and _may_reach(member) & (wanted | beyond)), None)
    return _part(Part.REACH, Truth.U, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session,
                 open_point if open_point is not None else facts_.SILENT, spans, R)


def _completion(session: Id, R: FactSet) -> PartFit:
    found = facts_.fact(R, session, _A.COMPLETION)
    if facts_.holds(found, Completion.COMPLETE) or _silent(found):
        return PartFit(Part.COMPLETION, Truth.T, None)
    truth = Truth.F if facts_.established(found) and _open(found, Completion) <= STOPPED_SHORT else Truth.U
    stated = any(_claims(found, value) for value in STOPPED_SHORT) or (
        found.state is FactState.NEGATED and found.value is Completion.COMPLETE)
    return _part(Part.COMPLETION, truth, FactKey.EXTENT, Rank.EXTENT, _A.COMPLETION, session, found,
                 found.spans or _reach_spans(session, R), R, stated)


def examinations(session: Id, R: FactSet) -> tuple[Id, ...]:
    """The examinations ``session`` may have, in pass 1's order: the events whose kind fact leaves examination open and
    whose session fact may name ``session`` (_may_name: a silent session slot included, D217's SILENT-EXAM, and one
    naming a session the FactSet does not hold, 4.11), each in any state (4.9's EXAMINATION role, found by its own
    session and kind facts; module docstring)."""
    return tuple(event for event in R.events
                 if Kind.EXAMINATION in _open(facts_.fact(R, event, _A.KIND), Kind)
                 and _may_name(facts_.fact(R, event, _A.SESSION), session, R))


def synthetic_possible(R: FactSet) -> tuple[UnlistedStatement, ...]:
    """The kept unlisted entries every absence condition here reads as possibly performed acts (D216, D231; module
    docstring, the absence conditions), in the stored order: the ACTS and the DOUBTS (POSSIBLY_PERFORMED) - the set
    evaluate.synthetic_possible reads (O17); never a DENIAL."""
    return tuple(entry for entry in R.unlisted if entry.what in POSSIBLY_PERFORMED)


def _card_may_name(entry: UnlistedStatement, session: Id, R: FactSet) -> bool:
    """Whether the kept unlisted entry ``entry`` may be of ``session`` (D216: "in its session"): its session card names
    it, or names none, or names a session the FactSet does not hold (4.11: a missing identifier manufactures neither a
    match nor a non-match; DECISIONS D227's 4d R2-2) - as evaluate.synthetic_in reads a card."""
    return entry.session is None or entry.session == session or entry.session not in R.sessions


def unlisted_examinations(session: Id, R: FactSet) -> tuple[UnlistedStatement, ...]:
    """The synthetic examination acts of ``session`` (D216, D231; 3.2.6 rule 3), in the stored order: the kept unlisted
    ACTS and DOUBTS (synthetic_possible) whose kind is examination or none named and whose card may name ``session``
    (_card_may_name) - each a possibly performed examination of the session, which may also have been attempted (module
    docstring, the absence conditions). An unlisted doubt is read as the act it doubts would be (D231), so it gives the
    class the outcome an unlisted act gives, and the outcome the same doubt filed as a doubted examination gives."""
    return tuple(entry for entry in synthetic_possible(R)
                 if (entry.kind is None or entry.kind is Kind.EXAMINATION) and _card_may_name(entry, session, R))


def _tied(event: Id, session: Id, R: FactSet) -> bool:
    """Whether ``event`` is established as an examination of ``session``: its kind supported examination and its session
    supported this one."""
    return (facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
            and facts_.holds(facts_.fact(R, event, _A.SESSION), session))


def _examination_doubt(event: Id, session: Id, status: Fact, R: FactSet) -> PartFit:
    """The question an examination of the session whose doubt decides the class raises (module docstring): resting on
    its status when that is not established, else on its tie to the session that is not (its session, else its kind),
    else on its status (established, but doubted by the class rule)."""
    kind, placed = facts_.fact(R, event, _A.KIND), facts_.fact(R, event, _A.SESSION)
    tied = _tied(event, session, R)
    attribute, found = ((_A.STATUS, status) if tied or not facts_.established(status)
                        else (_A.SESSION, placed) if not facts_.holds(placed, session) else (_A.KIND, kind))
    stated = (_claims(status, Status.ATTEMPTED_NOT_COMPLETED) and _claims(kind, Kind.EXAMINATION)
              and _claims(placed, session))
    return _part(Part.EXAMINATION, Truth.U, FactKey.EXTENT, Rank.EXTENT, attribute, event, found,
                 found.spans or status.spans or _reach_spans(session, R), R, stated)


def _unlisted_doubt(session: Id, entry: UnlistedStatement) -> PartFit:
    """The question a synthetic examination act raises (D216, D231: a kept unlisted act or doubt): a doubt about an act
    no card describes - performed_status at rank 2 (4.8: a doubt; DECISIONS D228), cause unlisted, about no single fact,
    its subject the session the rule read it in, quoting its own units and nothing else: none when it has none (an entry
    whose every unit id was unknown is kept with no units, contract/appraise_read.py), never the session's reach, which
    is another statement - the spans evaluate._synthetic_doubt gives the same act. The witness does not depend on the
    entry's nature: questions.synthetic_entry finds the entry (an act before a doubt) by those units, and the wording
    names an act with no units without a quote (DECISIONS D246, step 3c's form)."""
    return PartFit(Part.EXAMINATION, Truth.U, HeldFact(
        fact=fact_key(FactKey.PERFORMED_STATUS), attribute=None, subject=session, result=None,
        kind=ItemKind.QUESTION, cause=UNLISTED, reason=None, spans=_ordered(entry.units), rank=Rank.DOUBT.value))


def _examination(session: Id, R: FactSet) -> tuple[PartFit, ...]:
    """D72 as D217 reads it (module docstring, EXAMINATION)."""
    fits = (PartFit(Part.EXAMINATION, Truth.T, None),)
    exams = examinations(session, R)
    synthetic = unlisted_examinations(session, R)
    status = {event: facts_.fact(R, event, _A.STATUS) for event in exams}
    if any(_tied(event, session, R) and facts_.holds(status[event], Status.PERFORMED) for event in exams):
        return fits  # an attempt beside an established performed examination does not count: the completion decides
    attempts = [event for event in exams if Status.ATTEMPTED_NOT_COMPLETED in _open_status(status[event])]
    if not attempts and not synthetic:
        return fits
    performers = [event for event in exams if Status.PERFORMED in _open_status(status[event])]
    failed = [event for event in attempts if _tied(event, session, R)
              and facts_.holds(status[event], Status.ATTEMPTED_NOT_COMPLETED)]
    if failed and not performers and not synthetic:
        return tuple(_part(Part.EXAMINATION, Truth.F, FactKey.EXTENT, Rank.EXTENT, _A.STATUS, event, status[event],
                           status[event].spans or _reach_spans(session, R), R, True) for event in failed)
    doubts = [_examination_doubt(event, session, status[event], R) for event in exams
              if event not in failed and (event in attempts or event in performers)]
    return tuple(doubts) + tuple(_unlisted_doubt(session, entry) for entry in synthetic)


def class_fit(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> ClassFit:
    """FINAL-V2 4.3 ENT over ``session`` (module docstring): each part's truth and witness."""
    parts = [_family(session, R), _approach(exam_class, session, R), _route(exam_class, session, R),
             _reach(exam_class, session, R)]
    if exam_class in catalogue.ENTEROSCOPY_DEEPER:
        parts.append(_completion(session, R))
        parts.extend(_examination(session, R))
    return ClassFit(exam_class, session, tuple(parts))


def fits(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> Truth:
    """v1's classes.fits, over facts: the truth of ``exam_class`` on ``session``."""
    return class_fit(exam_class, session, R).truth


def class_misfit(code: str, session: Id, R: FactSet) -> tuple[HeldFact, ...]:
    """v1's classes.class_misfit, over facts: the witnesses of ``code``'s class on ``session`` - () when its class fits
    or the code has none."""
    exam_class = code_class(code)
    return () if exam_class is None else class_fit(exam_class, session, R).witnesses


def misfit_form(code: str, session: Id, R: FactSet) -> ClassForm | None:
    """v1's classes.class_hold form choice (class_misfit's: D43, D108, D114), over the parts: None when the class fits
    or the code has none; INCOMPLETE when only a deeper part keeps it from fitting and a deeper part's own claims state
    the stopping short (PartFit.stated: v1's "stated to be incomplete"); ROUTE when the session is an enteroscopy that
    reaches the class's reach, no route part is F and a route part is U - for STOMA and POUCH the entry passed through
    is the class's and only the approach is not established (v1's verified anatomy beside an unverified route); CLASS
    when the class's own reach is reached (or, for the jejunal class, established to go beyond it), or another class's
    reach is reached on the session; EXTENT otherwise (a reach no class's reach fits)."""
    exam_class = code_class(code)
    if exam_class is None:
        return None
    fit = class_fit(exam_class, session, R)
    if fit.truth is Truth.T:
        return None
    truth: dict[Part, Truth] = {part.part: part.truth for part in fit.parts if part.part is not Part.EXAMINATION}
    deeper = [part for part in fit.parts if part.part in DEEPER_PARTS and part.truth is not Truth.T]
    if all(value is Truth.T for part, value in truth.items() if part not in DEEPER_PARTS) and any(
            part.stated for part in deeper):
        return ClassForm.INCOMPLETE
    route = [truth[part] for part in Part if part in ROUTE_PARTS]
    anatomy_fits = exam_class not in ROUTE_CLASSES or truth[Part.ROUTE] is Truth.T
    if (truth[Part.FAMILY] is Truth.T and truth[Part.REACH] is Truth.T and Truth.F not in route and Truth.U in route
            and anatomy_fits):
        return ClassForm.ROUTE
    beyond = BEYOND.get(exam_class, frozenset())
    past = any(member.result is Result.SUPPORTED and member.value in beyond
               for member in facts_.members(R, session, _A.REACHED))
    if truth[Part.REACH] is Truth.T or past or any(_reach(other, session, R).truth is Truth.T for other in CLASSES
                                                   if other is not exam_class):
        return ClassForm.CLASS
    return ClassForm.EXTENT


# --- act_elsewhere (D114; FINAL-V2 4.7, 4.13: the act's own session fact) ---------------------------------------------


def _kinds_cover(kinds: Iterable[Kind], group: Sequence[Kind], hemostatic: bool) -> bool:
    """Whether a kind of ``kinds`` covers a kind of ``group`` as a candidate's (catalogue.covers, an umbrella
    included), each read as its catalogue kind and, when ``hemostatic``, as a bleeding control too (a clip or an
    injection whose purpose may be hemostasis)."""
    for kind in kinds:
        named = [catalogue.catalogue_kind(kind)]
        if hemostatic:
            named.append(catalogue.catalogue_kind(kind, Purpose.HEMOSTASIS))
        if any(item is not None and catalogue.covers(item, wanted) for item in named for wanted in group):
            return True
    return False


def _may_be_of_group(R: FactSet, event: Id, group: Sequence[Kind]) -> bool:
    """4.4's candidate test on the kind: a kind ``event``'s kind fact leaves possible as a candidate's (facts.
    possible_kinds: its claimed value, its readings and its control's sibling; every kind when silent) covers a kind of
    ``group`` (catalogue.covers, an umbrella included) - a clip or an injection read as a bleeding control too where the
    group names one and its purpose may be hemostasis (D157's doubt, read by possibly)."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    hemostatic = False
    if Kind.BLEEDING_CONTROL in group and kinds & catalogue.HEMOSTASIS_KINDS:
        hemostatic = facts_.possibly(facts_.fact(R, event, _A.PURPOSE), Purpose.HEMOSTASIS)
    return _kinds_cover(kinds, group, hemostatic)


def unlisted_of_group(R: FactSet, group: Sequence[Kind]) -> tuple[UnlistedStatement, ...]:
    """The kept unlisted acts and doubts that may be acts of ``group`` (D216, D231; module docstring, act_elsewhere), in
    the stored order: an unlisted ACT or DOUBT (synthetic_possible) whose kind covers a kind of the group as a
    candidate's - every kind when it names none, and a clip or an injection, whose purpose no card states, as a
    bleeding control too where the group names one - in any session. An unlisted doubt is read as the act it doubts
    would be (D231): it keeps the group out as an unlisted act does, and as the same doubt filed as an act of the group
    whose status is doubted (a positive candidate in doubt) does."""
    out: list[UnlistedStatement] = []
    for entry in synthetic_possible(R):
        kinds = frozenset(Kind) if entry.kind is None else frozenset({entry.kind})
        hemostatic = Kind.BLEEDING_CONTROL in group and bool(kinds & catalogue.HEMOSTASIS_KINDS)
        if _kinds_cover(kinds, group, hemostatic):
            out.append(entry)
    return tuple(out)


def _established_other(found: Fact, wanted: Enum) -> bool:
    """Whether ``found`` is established as another value than ``wanted``: supported with another, or negated as it."""
    return (found.result is Result.SUPPORTED and found.value != wanted) or facts_.denied(found, wanted)


def _positive(R: FactSet, event: Id) -> bool:
    """4.4's positive candidate, past its kind: its status not denied performed and possibly performed or attempted (a
    status not established leaves every status possible, 4.2), and neither its date relation nor its performer
    established as another (such an act is no candidate of the code's act on the date of service)."""
    status = facts_.fact(R, event, _A.STATUS)
    if facts_.denied(status, Status.PERFORMED) or not (
            facts_.possibly(status, Status.PERFORMED) or facts_.possibly(status, Status.ATTEMPTED_NOT_COMPLETED)):
        return False
    return not (_established_other(facts_.fact(R, event, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE)
                or _established_other(facts_.fact(R, event, _A.PERFORMER), Performer.DOCUMENTING_TEAM))


def _of_group(R: FactSet, event: Id, group: Sequence[Kind]) -> bool:
    """4.3 row 1 for an act: its kind supported and, as its catalogue kind (a clip or an injection read with its
    supported purpose only where the group names a bleeding control: catalogue.catalogue_kind), no umbrella, covering a
    kind of ``group`` (catalogue.covers)."""
    kind = facts_.fact(R, event, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, Kind):
        return False
    purpose: Purpose | None = None
    if kind.value in catalogue.HEMOSTASIS_KINDS and Kind.BLEEDING_CONTROL in group:
        found = facts_.fact(R, event, _A.PURPOSE)
        purpose = found.value if found.result is Result.SUPPORTED and isinstance(found.value, Purpose) else None
    named = catalogue.catalogue_kind(kind.value, purpose)
    return named is not None and named not in catalogue.UMBRELLAS and any(
        catalogue.covers(named, wanted) for wanted in group)


def _done(R: FactSet, event: Id) -> bool:
    """4.3 rows 2-5 for an act of an act code: status supported performed, effective date relation supported on the
    date of service, effective performer supported the documenting team, entry supported the documenting clinician."""
    return (facts_.holds(facts_.fact(R, event, _A.STATUS), Status.PERFORMED)
            and facts_.holds(facts_.fact(R, event, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE)
            and facts_.holds(facts_.fact(R, event, _A.PERFORMER), Performer.DOCUMENTING_TEAM)
            and facts_.holds(facts_.fact(R, event, _A.ENTRY), Owner.DOCUMENTING_CLINICIAN))


def _holder(R: FactSet, event: Id, family: SessionKind) -> tuple[Id, SessionKind] | None:
    """The session and its family when ``event``'s own session fact is supported, naming a session whose kind is
    supported as another family than ``family``; None otherwise (its own family's session, or a session not
    established: a doubt, never an elsewhere act)."""
    session = facts_.fact(R, event, _A.SESSION)
    if session.result is not Result.SUPPORTED or not isinstance(session.value, Id) or session.value.family is not _SESSION:
        return None
    kind = facts_.fact(R, session.value, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, SessionKind) or kind.value is family:
        return None
    return session.value, kind.value


def act_elsewhere(code: str, R: FactSet) -> tuple[Elsewhere, ...]:
    """D114's act_elsewhere over the act's own session fact (module docstring): for each requirement group of an
    enteroscopy act code, when it has positive candidates (4.4), every one of them is done (rows 1-5) and placed in a
    session of another family, and no kept unlisted act or doubt may be an act of the group (D216, D231), each of them,
    in pass 1's order. () for a code of no class, for an examination code (the examination is the session, and never
    moves), for a group with no positive candidate, and for one with a positive candidate in doubt on rows 1-5, in its
    own family's session, or whose session is not established, or beside an unlisted act or doubt that may be of the
    group."""
    if code_class(code) is None:
        return ()
    link = catalogue.code_link(code)
    if not link.linked or catalogue.examination_code(link):
        return ()
    out: list[Elsewhere] = []
    for group in catalogue.requirements(link):
        positive = [event for event in R.events if _may_be_of_group(R, event, group) and _positive(R, event)]
        placed = [(event, _holder(R, event, link.family) if _of_group(R, event, group) and _done(R, event) else None)
                  for event in positive]
        if not placed or any(holder is None for _event, holder in placed) or unlisted_of_group(R, group):
            continue
        out.extend(Elsewhere(event, holder[0], holder[1], tuple(group)) for event, holder in placed
                   if holder is not None)
    return tuple(out)


def elsewhere_hold(found: Elsewhere, R: FactSet) -> HeldFact:
    """D114's elsewhere hold, as a witness (4.4): an EXPLANATION - the act is documented in another family's session, an
    established fact, so the code's act is not documented in its own (customer_api words it "documented in another
    procedure") - at the status row (performed_status, rank 4: "not documented"), cause ELSEWHERE_CAUSE, quoting the
    act's own statement (its anchor units)."""
    anchor = R.anchors.get(found.event)
    spans = _ordered(anchor.units) if anchor is not None else facts_.fact(R, found.event, _A.SESSION).spans
    return HeldFact(fact=fact_key(FactKey.PERFORMED_STATUS), attribute=_A.SESSION, subject=found.event,
                    result=Result.SUPPORTED, kind=ItemKind.EXPLANATION, cause=ELSEWHERE_CAUSE, reason=None,
                    spans=spans, rank=Rank.STATUS.value)


# --- the code's class hold (classes.enteroscopy_hold; D89) --------------------------------------------------------------


def sessions_of(acts: Sequence[Id], R: FactSet) -> tuple[Id, ...]:
    """The sessions ``acts`` are in by their own supported session facts, each once, in the acts' order."""
    found: list[Id] = []
    for event in acts:
        session = facts_.fact(R, event, _A.SESSION)
        if session.result is Result.SUPPORTED and isinstance(session.value, Id) and session.value.family is _SESSION:
            found.append(session.value)
    return tuple(dict.fromkeys(found))


def enteroscopy_hold(code: str, supporting: Sequence[Id], R: FactSet) -> tuple[HeldFact, ...]:
    """Every witness of an enteroscopy code (v1's enteroscopy_hold; D89: both doubts kept, the wording names them): the
    class fit of each session its supporting acts are in; a procedure question for a supporting act whose session fact
    is not supported (its class cannot be judged, so it is asked, never skipped; a contradicted one at rank 1); then its
    elsewhere acts (act_elsewhere). () for a code of no class, and for a code whose class fits every such session and
    which has no elsewhere act. It returns witnesses only: never READY, never an exclusion."""
    exam_class = code_class(code)
    if exam_class is None:
        return ()
    held: list[HeldFact] = []
    for session in sessions_of(supporting, R):
        held.extend(class_fit(exam_class, session, R).witnesses)
    for event in supporting:
        if not sessions_of((event,), R):
            found = facts_.fact(R, event, _A.SESSION)
            held.append(_witness(True, FactKey.PROCEDURE, Rank.PROCEDURE, _A.SESSION, event, found, found.spans, R))
    held.extend(elsewhere_hold(found, R) for found in act_elsewhere(code, R))
    return tuple(held)
