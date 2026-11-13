"""The enteroscopy classes of design v2 (docs/gemini-migration/FINAL-V2.md 4.3 ENT, 4.7 and 5.5; step 4c of 8.1): v1's
studio/interpretation/classes.py (DECISIONS D108, D114, D141, D148, D153, D160) forked into engine/, its readers deleted
and its inputs rewired to settled facts - a session's kind, approach, through, reached and completion, the type of the
anatomy entry it went through, its examination's kind, session and status, and an act's own session fact. Nothing here
reads text: every input is an enumeration member, an id, a result or a span of the FactSet (engine/facts.py, step 2d).

**The class of a code** (code_class; D108): the descriptors' ranges, catalogue.ENTEROSCOPY_RANGES (step 1e) - 44360-44373
JEJUNAL, 44376-44379 ILEAL, 44380-44384 STOMA, 44385-44386 POUCH; no other code has one.

**What a fact leaves open** (FINAL-V2 4.2's possibly, read in any state, P3, P6: a doubt is never an absence). A
single-valued enumeration fact (_open) leaves open its value when supported; every other value when negated; and, when
it is not established, every value for an EMPTY slot - silent, or named by a doubt whose readings settle kept beside it
(3.3 rows 2 and 3; 4.2: a silent fact leaves every value possible) - and for a denial (state negated: the denial may be
wrong, and so may any other value), else its claimed value and its options (a contradicted fact's sides, a doubt's
readings, an unrejected control's value). A status that is not established leaves every status open (4.2's status
arm). An id-valued fact (_named: through, an event's session) names its id when supported; nothing when negated (a
denial names no object as the one it is) or silent (a session that states no entry passed through names none: D114's
problem 4); and, when it is not established, its claimed id and its options - for an empty slot a doubt names, the
doubt's readings. A reached member (_may_reach) may say its own point was reached unless it is established negated.

**The class fit** (class_fit; FINAL-V2 4.3 ENT: "approach supported (oral for jejunal and ileal; through_stoma with a
stoma entry; through_pouch with an ileal_pouch entry, never a gastric pouch or a Roux limb) and reached in the class
reach; for the deeper classes, completion not incomplete"), over ONE session, part by part. Each part is T, U or F (4.2,
the truth of a requirement) and each part that is not T gives its own witness; the class is T only when every part is.
- FAMILY: the session's kind supported enteroscopy (4.3 row 6, read again so that a class is never judged on another
  family's session). procedure (rank 8).
- APPROACH: the session's approach supported as the class's (catalogue.ENTEROSCOPY_CLASS_APPROACH: oral for JEJUNAL and
  ILEAL - for JEJUNAL as 4.3 writes it, D207's accepted 1e:dev4 -, through_stoma for STOMA, through_pouch for POUCH). F
  when it is established as another (supported with another value, or negated as the class's); U otherwise. procedure.
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
  U, a question, as v1's class and extent questions were. The jejunal class is "not including ileum": a point BEYOND it
  (BEYOND: the deeper class's reach, the ileal points) supported among the reached points is F - the examination is
  established to have included the ileum - and a reached point that may lie beyond it (one only possible, or a point
  containing an ileal one, as the small bowel named as such may be the ileum: D28) is U, whatever the jejunal points
  say (the fail-closed reading of refute-4c-r1 DQ2, v1's furthest landmark; NOTES.md Q2 records its one cost: P-MONO's
  deleted member). device_reached is never read (K6, P19), nor reached_anatomy (no class rule's read-set has it).
  extent (rank 14).
- COMPLETION (ILEAL, the deeper class: catalogue.ENTEROSCOPY_DEEPER; D43, D56): T only when the completion leaves no
  stopping short open (incomplete or terminated, CO-8) - supported complete; F when established so (supported incomplete
  or terminated, negated complete); U otherwise, a silent slot and a slot a doubt names included (the fail-closed
  reading of refute-4c-r1 DQ4 and its critical finding A: 4.2 leaves every value of a silent or doubted slot possible,
  P3; NOTES.md Q4). extent.
- EXAMINATION (ILEAL; D72): an examination of the session - an event whose kind leaves examination open and whose
  session fact may name the session, in any state (4.9's EXAMINATION role, found by its own session and kind facts; the
  session's own examination slot is no claim, 3.2.1) - whose status leaves attempted_not_completed open never fits; F
  only when that status is established attempted_not_completed and the examination is established as this session's
  (its kind supported examination, its session supported), U otherwise: a question resting on the status when it is
  not established, else on the examination's tie to the session that is not (refute-4c-r1 F). extent.

A part that is not T gives a witness (engine/types.HeldFact, 4.4): a QUESTION for U, whose cause comes from the fact's
own result and first reason (reading_unknown, reading_contradicted, appraisal:<verdict or coherence>,
unestablished:<reason>; CLASS_CAUSE for a doubt this rule raises over established facts), and an EXPLANATION for F
(CLASS_CAUSE). Every witness is kept (4.4: a hold carries all its unresolved facts); which one is asked is RANK's choice
(4.8), and D89's "one item naming both doubts" is the wording's, over held_facts (step 3c). misfit_form gives v1's
question form (class_hold's CLASS, INCOMPLETE, EXTENT or ROUTE) over the same parts, for that wording; its INCOMPLETE
form ("is stated to be incomplete") needs the stopping short STATED by a deeper part's own claim (PartFit.stated).

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
Nothing moves (5.4: coverage.coding_family retires; K3 can only unresolve a session fact), so no region, place or reach
is read. v1's second arm (the enteroscopy's examination code held beside a moved act) has no counterpart here: with no
move, an act Gemini places in another session is not the enteroscopy's, and one whose session is in doubt holds the
examination code through base_included's possible acts (4.7, step 4d), never through this module. It never makes a code
READY or EXCLUDED.

**enteroscopy_hold** (v1's name; D89): every witness of an enteroscopy code - the class fit of each session its
supporting acts (E*, 4.4's code_requirements) are in, and its elsewhere acts. A supporting act whose session fact is
not supported cannot be placed, and gives a procedure question rather than being skipped.

**What it reads** (P-READSET, P-INDEP, 9.4): only attributes the enteroscopy codes' requirement closure reads
(engine/requirements.dependencies): a session's kind, approach, through, reached and completion; an anatomy entry's
type; an event's kind, session and status (EXAMINATION role) and, for an act of a requirement group, its kind, purpose
(a clip or an injection, for a code covering bleeding control), status, date relation, performer, entry and session,
and its session's kind (SUPPORT rows 1-6). tests/v2/test_classes.py records the reads and pins them inside the closure.

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
                                                  Result, SessionKind, Status, VerdictValue)
from studio.interpretation.engine import anatomy, catalogue
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine.catalogue import EnteroscopyClass
from studio.interpretation.engine.requirements import FactKey, Rank, fact_key
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span

_E = TypeVar('_E', bound=Enum)
_A = Attribute
_SESSION, _ANATOMY = IdFamily.SESSION, IdFamily.ANATOMY

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
# The points beyond an oral class that its code's descriptor excludes: the jejunal class is "not including ileum", so
# the reach of the deeper oral class (catalogue.ENTEROSCOPY_DEEPER: the ileal points) lies beyond it (module docstring,
# REACH). Derived from catalogue's tables; the deeper class itself has nothing beyond it.
BEYOND: Mapping[EnteroscopyClass, frozenset[Extent]] = MappingProxyType({
    exam_class: frozenset(point for deeper in CLASSES if deeper in catalogue.ENTEROSCOPY_DEEPER & ORAL_CLASSES
                          for point in catalogue.ENTEROSCOPY_CLASS_REACH[deeper])
    for exam_class in CLASSES if exam_class in ORAL_CLASSES - catalogue.ENTEROSCOPY_DEEPER})
# The completions that keep the deeper class from fitting (D43, D56; CO-8's terminated with incomplete, as R6:extent and
# the 52/53 consideration read them: an examination that stopped short of the extent it set out to reach).
STOPPED_SHORT: frozenset[Completion] = frozenset({Completion.INCOMPLETE, Completion.TERMINATED})

# The witnesses' causes (FINAL-V2 4.4), operator data that names no vendor: an established fact failing the class
# (an explanation), or a doubt the class rule raises over established facts; an act documented in another family's
# session; a fact read as unknown or contradicted; an unresolved fact's own reason or appraisal.
CLASS_CAUSE = 'coding_rule:enteroscopy_class'
ELSEWHERE_CAUSE = 'coding_rule:act_elsewhere'
READING_UNKNOWN = 'reading_unknown'
READING_CONTRADICTED = 'reading_contradicted'
UNESTABLISHED = 'unestablished'


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
    left unrejected, a silent slot, an examination only possibly of the session) and for every other part."""
    part: Part
    truth: Truth
    witness: HeldFact | None
    stated: bool = False


@dataclass(frozen=True, slots=True)
class ClassFit:
    """The class fit of ``exam_class`` on ``session``: each part's truth and witness, in the order the module docstring
    lists them (the deeper parts only for ILEAL: one EXAMINATION part per examination of the session that may be
    attempted_not_completed, else a single EXAMINATION part that is T)."""
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
    ``domain`` (never in a FactSet facts.py built) leaves every value open. Weakening a fact (FINAL-V2 9.4 P-MONO) can
    only widen what it leaves open."""
    if found.result is Result.SUPPORTED:
        return frozenset({found.value}) if isinstance(found.value, domain) else frozenset(domain)
    if found.result is Result.NEGATED:
        return frozenset(member for member in domain if member != found.value)
    if found.state is None or found.state is FactState.NEGATED:
        return frozenset(domain)
    return frozenset(value for value in (found.value, *found.options) if isinstance(value, domain))


def _open_status(found: Fact) -> frozenset[Status]:
    """The statuses ``found`` leaves open: every status when it is not established (4.2's status arm [R:HO-1][R:HO-3]:
    a doubt about whether an act was done is a doubt about every status), else _open's."""
    return _open(found, Status) if facts_.established(found) else frozenset(Status)


def _named(found: Fact, family: IdFamily) -> tuple[Id, ...]:
    """The ids of ``family`` an id-valued ``found`` may name, in order (module docstring): its value when supported;
    none when negated or silent; when it is not established, its claimed value and its options (for an empty slot a
    doubt names, the doubt's readings: 3.3 row 2)."""
    if found.result is Result.NEGATED:
        return ()
    values = (found.value,) if found.result is Result.SUPPORTED else (found.value, *found.options)
    return tuple(dict.fromkeys(value for value in values if isinstance(value, Id) and value.family is family))


def _may_reach(member: Fact) -> frozenset[Extent]:
    """The points a reached member may say the endoscope reached: its point when supported; none when it is established
    negated ("X was not reached" says nothing about another point); when it is not established, its claimed point (a
    denial not established may be wrong) and its options."""
    if member.result is Result.NEGATED:
        return frozenset()
    values = (member.value,) if member.result is Result.SUPPORTED else (member.value, *member.options)
    return frozenset(value for value in values if isinstance(value, Extent))


def _claims(found: Fact, value: object) -> bool:
    """Whether pass 1's own claim of ``found`` states ``value``, whatever settle made of it: claimed supported as it, or
    contradicted with it a side."""
    return ((found.state is FactState.SUPPORTED and found.value == value)
            or (found.state is FactState.CONTRADICTED and value in found.options))


def _one(found: Fact, wanted: Enum) -> Truth:
    """T when ``found`` is supported as ``wanted``; F when it is established against it (supported with another value,
    or negated as ``wanted``); U otherwise (not established, or negated as another value, which leaves ``wanted``
    open)."""
    if facts_.holds(found, wanted):
        return Truth.T
    if found.result is Result.SUPPORTED or facts_.denied(found, wanted):
        return Truth.F
    return Truth.U


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


def _ordered(spans: Iterable[Span]) -> tuple[Span, ...]:
    return tuple(sorted(set(spans)))


def _reach_spans(session: Id, R: FactSet) -> tuple[Span, ...]:
    """The spans of the session's reached points, each once, in document order: what a class question quotes when its
    own fact cites nothing."""
    return _ordered(span for member in facts_.members(R, session, _A.REACHED) for span in member.spans)


def _witness(question: bool, key: FactKey, rank: Rank, attribute: Attribute, subject: Id, found: Fact,
             spans: tuple[Span, ...]) -> HeldFact:
    """A witness resting on ``found``: a QUESTION (U: its cause from the fact, and the fact's first reason when it is
    not established) or an EXPLANATION (F: CLASS_CAUSE, no reason, as an established fact fails the class)."""
    reason = found.reasons[0] if question and found.reasons and not facts_.established(found) else None
    return HeldFact(fact=fact_key(key), attribute=attribute, subject=subject, result=found.result,
                    kind=ItemKind.QUESTION if question else ItemKind.EXPLANATION,
                    cause=_cause(found) if question else CLASS_CAUSE, reason=reason, spans=spans, rank=rank.value)


def _part(part: Part, truth: Truth, key: FactKey, rank: Rank, attribute: Attribute, subject: Id, found: Fact,
          spans: tuple[Span, ...], stated: bool = False) -> PartFit:
    """A part's truth and its witness: none for T; a question for U; an explanation for F (_witness)."""
    if truth is Truth.T:
        return PartFit(part, truth, None)
    return PartFit(part, truth, _witness(truth is Truth.U, key, rank, attribute, subject, found, spans), stated)


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
                 kind.spans or _reach_spans(session, R))


def _approach(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> PartFit:
    found = facts_.fact(R, session, _A.APPROACH)
    truth = _one(found, catalogue.ENTEROSCOPY_CLASS_APPROACH[exam_class])
    return _part(Part.APPROACH, truth, FactKey.PROCEDURE, Rank.PROCEDURE, _A.APPROACH, session, found,
                 found.spans or _reach_spans(session, R))


def _route(exam_class: EnteroscopyClass, session: Id, R: FactSet) -> PartFit:
    through = facts_.fact(R, session, _A.THROUGH)
    spans = through.spans or _reach_spans(session, R)
    if exam_class in ROUTE_CLASSES:
        needed = catalogue.ENTEROSCOPY_CLASS_ANATOMY[exam_class]
        entry = through.value if through.result is Result.SUPPORTED and isinstance(through.value, Id) else None
        if entry is None or entry.family is not _ANATOMY:
            return _part(Part.ROUTE, Truth.U, FactKey.PROCEDURE, Rank.PROCEDURE, _A.THROUGH, session, through, spans)
        kind = facts_.fact(R, entry, _A.TYPE)
        return _part(Part.ROUTE, _one(kind, needed), FactKey.PROCEDURE, Rank.PROCEDURE, _A.TYPE, entry, kind,
                     kind.spans or spans)
    approach = facts_.fact(R, session, _A.APPROACH)
    if _one(approach, catalogue.ENTEROSCOPY_CLASS_APPROACH[exam_class]) is Truth.F:
        return PartFit(Part.ROUTE, Truth.T, None)  # the approach, established as another route, explains the hold
    if not routes(session, R) | doubted_routes(session, R):
        return PartFit(Part.ROUTE, Truth.T, None)
    return _part(Part.ROUTE, Truth.U, FactKey.PROCEDURE, Rank.PROCEDURE, _A.THROUGH, session, through, spans)


def _beyond(points: Iterable[Extent], beyond: frozenset[Extent]) -> bool:
    """Whether a point of ``points`` may lie beyond the class: a point of ``beyond``, or one containing such a point (the
    small bowel named as such may be the ileum, as D28 reads it)."""
    return any(point in beyond or any(anatomy.contains(point, deeper) for deeper in beyond) for point in points)


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
        return _part(Part.REACH, Truth.F, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session, past, spans)
    if any(member.result is Result.SUPPORTED and member.value in wanted for member in points):
        maybe_past = next((member for member in points if _beyond(_may_reach(member), beyond)), None)
        if maybe_past is None:
            return PartFit(Part.REACH, Truth.T, None)
        return _part(Part.REACH, Truth.U, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session, maybe_past, spans)
    denials = tuple(member for member in points if member.result is Result.NEGATED)
    if wanted and all(any(_denies(denial, point) for denial in denials) for point in wanted):
        denial = next(denial for denial in denials if any(_denies(denial, point) for point in wanted))
        return _part(Part.REACH, Truth.F, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session, denial, spans)
    open_point = next((member for member in points if not facts_.established(member)
                       and _may_reach(member) & (wanted | beyond)), None)
    return _part(Part.REACH, Truth.U, FactKey.EXTENT, Rank.EXTENT, _A.REACHED, session,
                 open_point if open_point is not None else facts_.SILENT, spans)


def _completion(session: Id, R: FactSet) -> PartFit:
    found = facts_.fact(R, session, _A.COMPLETION)
    left = _open(found, Completion)
    if not left & STOPPED_SHORT:
        return PartFit(Part.COMPLETION, Truth.T, None)
    truth = Truth.F if facts_.established(found) and left <= STOPPED_SHORT else Truth.U
    stated = any(_claims(found, value) for value in STOPPED_SHORT) or (
        found.state is FactState.NEGATED and found.value is Completion.COMPLETE)
    return _part(Part.COMPLETION, truth, FactKey.EXTENT, Rank.EXTENT, _A.COMPLETION, session, found,
                 found.spans or _reach_spans(session, R), stated)


def examinations(session: Id, R: FactSet) -> tuple[Id, ...]:
    """The examinations ``session`` may have, in pass 1's order: the events whose kind fact leaves examination open and
    whose session fact may name ``session``, each in any state (4.9's EXAMINATION role, found by its own session and
    kind facts; module docstring: _open, _named)."""
    return tuple(event for event in R.events
                 if Kind.EXAMINATION in _open(facts_.fact(R, event, _A.KIND), Kind)
                 and session in _named(facts_.fact(R, event, _A.SESSION), _SESSION))


def _examination(session: Id, R: FactSet) -> tuple[PartFit, ...]:
    out: list[PartFit] = []
    for event in examinations(session, R):
        status = facts_.fact(R, event, _A.STATUS)
        left = _open_status(status)
        if Status.ATTEMPTED_NOT_COMPLETED not in left:
            continue
        kind, placed = facts_.fact(R, event, _A.KIND), facts_.fact(R, event, _A.SESSION)
        tied = facts_.holds(kind, Kind.EXAMINATION) and facts_.holds(placed, session)
        truth = (Truth.F if tied and facts_.established(status) and left == {Status.ATTEMPTED_NOT_COMPLETED}
                 else Truth.U)
        stated = (_claims(status, Status.ATTEMPTED_NOT_COMPLETED) and _claims(kind, Kind.EXAMINATION)
                  and _claims(placed, session))
        # the witness rests on the fact that is not established: the status, else the examination's tie to the session
        attribute, found = ((_A.STATUS, status) if tied or not facts_.established(status)
                            else (_A.SESSION, placed) if not facts_.holds(placed, session) else (_A.KIND, kind))
        out.append(_part(Part.EXAMINATION, truth, FactKey.EXTENT, Rank.EXTENT, attribute, event, found,
                         found.spans or status.spans or _reach_spans(session, R), stated))
    return tuple(out) or (PartFit(Part.EXAMINATION, Truth.T, None),)


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


def _may_be_of_group(R: FactSet, event: Id, group: Sequence[Kind]) -> bool:
    """4.4's candidate test on the kind: a kind ``event``'s kind fact leaves possible as a candidate's (facts.
    possible_kinds: its claimed value, its readings and its control's sibling; every kind when silent) covers a kind of
    ``group`` (catalogue.covers, an umbrella included) - a clip or an injection read as a bleeding control too where the
    group names one and its purpose may be hemostasis (D157's doubt, read by possibly)."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    hemostatic = False
    if Kind.BLEEDING_CONTROL in group and kinds & catalogue.HEMOSTASIS_KINDS:
        hemostatic = facts_.possibly(facts_.fact(R, event, _A.PURPOSE), Purpose.HEMOSTASIS)
    for kind in kinds:
        named = [catalogue.catalogue_kind(kind)]
        if hemostatic:
            named.append(catalogue.catalogue_kind(kind, Purpose.HEMOSTASIS))
        if any(item is not None and catalogue.covers(item, wanted) for item in named for wanted in group):
            return True
    return False


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
    enteroscopy act code, when it has positive candidates (4.4) and every one of them is done (rows 1-5) and placed in a
    session of another family, each of them, in pass 1's order. () for a code of no class, for an examination code (the
    examination is the session, and never moves), for a group with no positive candidate, and for one with a positive
    candidate in doubt on rows 1-5, in its own family's session, or whose session is not established."""
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
        if not placed or any(holder is None for _event, holder in placed):
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
    is not supported (its class cannot be judged, so it is asked, never skipped); then its elsewhere acts
    (act_elsewhere). () for a code of no class, and for a code whose class fits every such session and which has no
    elsewhere act. It returns witnesses only: never READY, never an exclusion."""
    exam_class = code_class(code)
    if exam_class is None:
        return ()
    held: list[HeldFact] = []
    for session in sessions_of(supporting, R):
        held.extend(class_fit(exam_class, session, R).witnesses)
    for event in supporting:
        if not sessions_of((event,), R):
            found = facts_.fact(R, event, _A.SESSION)
            held.append(_witness(True, FactKey.PROCEDURE, Rank.PROCEDURE, _A.SESSION, event, found, found.spans))
    held.extend(elsewhere_hold(found, R) for found in act_elsewhere(code, R))
    return tuple(held)
