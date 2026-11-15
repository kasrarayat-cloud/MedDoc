"""The one-question policy (docs/gemini-migration/FINAL-V2.md 4.8, 4.4; DECISIONS D182, D189, D225, D232, D246, D253,
D254, D257, D258, D265, D266, D267; step 4a of 8.1, repaired as r4a of round w7r and, after its refutation, r4a-2, as
r4a of round w8r and, after its refutation refute-r4a-r1, r4a-2, and as r4a of round w9r): RANK applied to a held code's
witnesses, the binding (which act the
item names), the ONE item - a question or an explanation - and its message id, over the HeldFacts engine/evaluate.py
records. Text-free: it reads ranks, kinds, ids and integer spans, and the item names a message id and the text-free
slots CPT Studio's fixed sentence is built from; the revision text is sliced by the caller (wording.build) after the
decision, never here.

**Each held code carries exactly ONE clarification** (4.8; D182): the item of its highest-ranked non-T requirement on its
chosen binding - a QUESTION when that requirement is unresolved (U), an EXPLANATION when an established fact fails it
(F). The other non-T requirements stay in ``held_facts`` (the Evaluation's), each with its cause, over every positive
candidate [R:HO-8]; they are never asked as separate questions.

**RANK** is engine/requirements.Rank (4.8's 23 rows, pinned by step 1f): a witness's ``rank`` is its row's value, 1 asked
first. ``order`` sorts held facts as 4.8 asks: by rank (the unranked encounter-scope service_date last), at an equal rank
a question before an explanation (an explanation can never become T), then document order (the first span), then the
subject's place in pass 1's order.

**The binding** (``choose``; 4.8 [C][A][B][R:HO-8]): among a group's positive candidates, (1) those whose anchor the
code's kept spans overlap, when any does; (2) then the candidate whose top item ranks highest (a contradiction on any of
them is asked before anything else); (3) then the fewest non-T requirements (closest to READY; counted over the
requirements of ``requirements_of(code)`` the per-code rule evaluates on a candidate: step 1f's hand-off R9(e)); (4) at an
equal rank, a question before an explanation; (5) then document order. Never simply the first act in reading order (Q1).

**The item** (``select``): the first, in ``order``, of the held facts ON the binding - every held fact but the witnesses
of a positive candidate that is not its group's bound one (a witness the bound candidate shares, such as its session's,
stays on it). So a contradiction on a candidate the item does not name stays in ``held_facts`` (HO-8's first case) and
is asked only when no kept span selects the other act. ``item`` takes ``select``'s choice but in one case: an
enteroscopy class item whose session has no supported reached point names no reach truly, and the reach's own question
is the item instead (v1's installed reading; ``item``).

**Every sentence true for its state** (D225, refute-4a-r2 P5, P6, P7, P10, P11; repair r3c's six ids): the item names
the act and the fact that is actually unknown. ``Raised`` carries what engine/evaluate.py knows of the holds it raised
beside the FactSet: 3.2.6 rule 2's hold is worded as its unlisted entry (UNLISTED_EVIDENCE: the entry's nature and kind,
its own unit - never the code's act said to be in doubt); XCHG's duct question names the act whose duct is not
established beside its counterpart (SAME_DUCT); a synthetic act's doubt (D216; an unlisted act or doubt, each read as
possibly performed: refute-r4a-r1 F1) names the unlisted entry by its own kind (an act of no kind as an act) with its
own units - a kept unlisted ACT in SYNTHETIC_ACT's words ("The document documents ..., which CPT Studio's reading of
the document does not account for": D246, r4a R4 (a); never "left in doubt", untrue of an act the document states),
a kept unlisted DOUBT in DOUBT's. Without them (a caller passing none)
the item is the one every other hold gets. A contradicted attribute other than the status, and a status whose sides
cannot be told apart, is a conflict about that attribute (CONFLICT_ATTRIBUTE; a session's fact names its examination);
the stoma EUS class's approach is asked or explained as the approach (EXAMINATION_ROUTE, EXAMINATION_APPROACH, RANK row
8); STRUCT:pfc's explanation names the place it read (STRUCTURE_PLACE).

**An unlisted doubt never names a session's examination as left in doubt unless its card names that session** (D232):
a synthetic examination doubt names the examination by its session's service only when its card names the session it
holds; otherwise it is "the examination" its own unit speaks of. 3.2.6 rule 4's pair of an unlisted doubt with a
session's examination (row 8; asked at RANK row 2, D228) is worded the same way: by the examination's service when the
doubt's card names the session the examination is established in, else as the doubt's own examination - its kind, its
own unit, no session - never "The document leaves the upper endoscopy in doubt" for a sentence about another
examination.

**A statement that names no session is asked about the held session's performance, never about the statement**
(D258): a kept unlisted doubt or denial with no card, or a card naming a session the FactSet does not hold, held
against a session's examination - 3.2.6 rule 4's pair with an act whose own kind is the examination, or a synthetic
examination act's doubt (row 7's, step 4c's) of kind examination - is UNLISTED_SCOPE (``_scope_entry``): the held
session's examination by its service and its own words, whether it is documented as done on the date of service, the
statement quoted as one that names no procedure session; the held fact unchanged (performed_status, RANK row 2, cause
unlisted), so a member's "not documented" excludes as before. An act (SYNTHETIC_ACT), an entry carded to a session the
FactSet holds (DOUBT, D232), a pair with an act of another kind and an entry of no kind read as a synthetic act keep
their items.

**A digital examination never words an item, and an item quotes only what it asks about** (D265, D266; repair r4a of
round w9r): a digital examination (FINAL 5.6 E13: its device claiming manual, ``digital_examination``) never takes a
binding (engine/evaluate.py), and where a hold rests on its own facts - its rows 2-5 read on another act's row 7, r4a
QD2, kept as built by D271 - the item names the session's examination by its service, never the DRE's sentence or device
(``fill``, ``_session_named``). UNLISTED_SCOPE and the carded DOUBT quote an examination statement only when that
examination is possibly done on the date of service - not of another date, not planned, not by another performer, not
negated (``_quotable``, ``_quoted_examination``) - else they name the examination by its service with no quote; and
every DOUBT of a kept unlisted entry carries the entry's nature (``unlisted_what``), carded or not, so a denial is
worded as a statement that the act was not done (step r3c's form). An act whose kind is not SUPPORTED (negated,
doubted, unresolved, contradicted, silent) or is other is Kind.OTHER, "another act", in ``act_kind`` - the one label the
Fill, overlay's slots and engine/evaluate's conflict key (conflict:other) read (D267). A route the anatomy only
possibly opens is marked in ``possible_approaches`` (step r3c's marker: never "the documented stoma"), and ENT's
approach part whose only unknown is the route is ENTEROSCOPY_ROUTE, never PROCEDURE (D267, r4a QA).

**Every item 4a makes is worded** (D246; the lead's L1): the fill gives every slot wording asks of the bundling items -
PART and BUNDLING_TARGET name the part and its whole (``whole_words``, the whole's anchor units) and the bundling rule,
BUNDLED its rule, each from the coverage bundle that raised the hold (``_bundle_of``) - and of the enteroscopy class
items (``enteroscopy_class``, the code's class; the reach the class rule read and its own words, refute-r4a-r1 P3; the
session's supported approach and its words for ENTEROSCOPY_APPROACH; the documented stoma or pouch of the route
question, P11; the incomplete form where classes.misfit_form gives it; an approach not supported none, so wording
names no route, D254 rule 3, refute-r4a-r2 A1); ENT's route part whose only unknown is the anatomy passed through is
the route's own question, never PROCEDURE (D253 QX (ii)) - ENTEROSCOPY_THROUGH for the stoma and pouch classes,
ENTEROSCOPY_ROUTE for the oral classes' two-route doubt (refute-r4a-r1 P2 of round w8r); a base-within hold is
BASE_WITHIN (5c's R8), its whole named by its own family and stated as only possibly done when the hold is a question (D257:
``whole_family``, ``whole_possible``). An act no kind names - its kind other, silent or contradicted - is Kind.OTHER in
every act slot, "another act", never the code's group's kind (D254 rule 2: ``_act_slot``; a code-level hold, which
names no act, keeps the group).

**Causes** (4.4 [R:MO-2]; ``cause_of``): reading_unknown (silent or doubted), reading_contradicted,
appraisal:<verdict or coherence> for an appraisal reason (3.3 row 9), unestablished:<reason> for any other reason of an
unresolved fact (unestablished when it carries none), coding_rule:<id> for an established fact failing a coding rule
(``coding_rule``), relation:<type> (engine/pairing.py's), unlisted, context_missing, date_unknown. Operator data: no
vendor is named, and no customer string carries one. step 4c asked for this one derivation (its request R2).

**Message ids** (``MessageId``; step 3c's wording.Message, mirrored value for value - repair r3c's six D225 ids, three
Slots fields and D246's SYNTHETIC_ACT included, and round w8r's UNLISTED_SCOPE and ENTEROSCOPY_THROUGH with the Slots
fields whole_family and whole_possible; and round w9r's Slots field possible_approaches): the engine cannot import
studio/interpretation/wording.py - it imports studio.gi and is no ``mypy --strict`` module (5.7 measure 5) - so the ids
are restated here as an Enum whose every member equals wording.Message's by name and value (tests/v2/test_questions.py
pins it, and pins each id's fact key, kind and rank against wording.MESSAGES), and ``Fill`` mirrors wording.Slots field
for field. The caller builds the sentence: ``wording.build(wording.Message(item.message.value), slots, revision_text)``
with ``slots = wording.Slots(**{name: getattr(item.fill, name) for each Fill field})``, its ``bundling`` turned into
wording.Bundling by value (never dataclasses.asdict, which would turn the Span records into dicts; tests/v2/
test_questions.slots does it).

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, classes, combination, coverage, facts, pairing, requirements and
types only (classes, combination and coverage read for the items they raise: D246) - no retired v1 module,
none of contract's text modules, not wording - holds no word, phrase or marker list (every module-level collection holds
enumeration members, or is computed from them), reads no text and returns no document string (a cause and a fact key are
CPT Studio's codes). ``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import (AnatomyType, Approach, Attribute, DateRelation, Device, Extent, Kind,
                                                  Landmark, Owner, Performer, Purpose, Qualifier2, Reason, Result,
                                                  SessionKind, Station, Status, Tract, UnlistedWhat, VerdictValue)
from studio.interpretation.engine import anatomy, catalogue, classes, combination, coverage, pairing
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import (Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span,
                                                UnlistedStatement)

_A = Attribute
_Q, _E = ItemKind.QUESTION, ItemKind.EXPLANATION

# --- causes (FINAL-V2 4.4 [R:MO-2]) ------------------------------------------------------------------------------------

READING_UNKNOWN = 'reading_unknown'
READING_CONTRADICTED = 'reading_contradicted'
UNESTABLISHED = 'unestablished'
UNLISTED = 'unlisted'
CONTEXT_MISSING = 'context_missing'
DATE_UNKNOWN = 'date_unknown'


@unique
class Coherence(Enum):
    """The appraisal outcomes 3.2.3's coherence table names that are no verdict, as a cause names them (4.4:
    appraisal:<verdict or coherence>); the same values step 4c's classes.py writes (its request R2)."""
    INCOHERENT = 'control_incoherent'
    DETACHED = 'detached'
    MISSING = 'missing'


# Each appraisal reason of 3.3 row 9 -> the verdict or coherence its cause names (appraisal_qualified:<q> is a
# qualified verdict).
APPRAISAL_CAUSES: Mapping[Reason, VerdictValue | Coherence] = MappingProxyType({
    Reason.APPRAISAL_CONTRADICTS: VerdictValue.CONTRADICTS, Reason.APPRAISAL_UNCLEAR: VerdictValue.UNCLEAR,
    Reason.APPRAISAL_QUALIFIED: VerdictValue.QUALIFIED, Reason.CONTROL_INCOHERENT: Coherence.INCOHERENT,
    Reason.APPRAISAL_DETACHED: Coherence.DETACHED, Reason.APPRAISAL_MISSING: Coherence.MISSING,
    **{Reason(f'appraisal_qualified:{qualifier.value}'): VerdictValue.QUALIFIED for qualifier in Qualifier2},
})


@unique
class Rule(Enum):
    """The coding rules whose established failure (or own doubt) holds a code, as ``coding_rule:<id>`` names them in a
    cause (4.4): each a row of 4.3 or a decision of 4.4 and 4.6."""
    ATTEMPTED = 'attempted'  # C-9: begun and not completed on a code that does not account for the examination
    UNPROFILED = 'unprofiled'  # route (d), no profile (C-6)
    NOT_LINKED = 'not_linked'  # route (d), another family (C-6)
    RECOGNISED_ONLY = 'recognised_only'  # D80
    ROUTE_B = 'route_b'  # D197: route (b) is never READY
    NOT_DOCUMENTED = 'not_documented'  # 7.6: no act of the code's kind documented as done
    STATEMENT_SCOPE = 'statement_scope'  # 4.6: a partial cover (C-10), a broad denial not cited (C-7)
    UMBRELLA = 'umbrella'  # 4.3 row 1: a positive umbrella never supports a method-specific code (h5)
    TIMING = 'timing'  # 4.3 row 3: the effective date relation established otherwise (on_date_of_service negated)
    PERFORMER = 'performer'  # 4.3 row 4: the effective performer established otherwise (documenting_team negated)
    ENTRY = 'entry'  # 4.3 row 5: the act told in another role's entry
    SESSION = 'session'  # 4.3 row 6: the act's session of another family; route (b): a place outside its regions
    EXAMINATION = 'examination'  # 4.3 row 7: the session's examination not done
    ENCOUNTER = 'encounter'  # 4.3 E/M row: the visit's session is another encounter
    TECHNIQUE = 'technique'  # TECH
    SITE = 'site'  # SITE (D29)
    STRUCTURE = 'structure'  # STRUCT:pfc (D120, D136, D145)
    ROUTE = 'route'  # ROUTE (43253; D171(4), D177(2))
    TRACT = 'tract'  # TRACT (D171(2))
    STATIONS = 'stations'  # STATIONS (43242, 43259)
    LIMITED = 'limited'  # LIMITED (43231, 43232, 43237, 43238; D28, D171(3))
    LOWER = 'lower'  # LOWER (D43)
    YIELD = 'yield'  # YIELD (43264; D106)
    EXCHANGE = 'exchange'  # XCHG (43274, 43275, 43276; D105, D127)
    CAUSE = 'cause'  # CAUSE (every code covering bleeding_control)
    ENTEROSCOPY_CLASS = 'enteroscopy_class'  # ENT (step 4c's engine/classes.py: its class explanations)
    ACT_ELSEWHERE = 'act_elsewhere'  # ENT (step 4c's: an act held by another family's session)


def coding_rule(rule: Rule) -> str:
    """The cause of a hold a coding rule raises: coding_rule:<id> (4.4)."""
    return f'coding_rule:{rule.value}'


def cause_of(found: Fact) -> str:
    """The cause of a hold resting on ``found`` (4.4): reading_unknown for an unknown fact (silent, or doubted with its
    value kept), reading_contradicted for a contradicted one, appraisal:<verdict or coherence> when an unresolved fact's
    first reason is an appraisal reason (3.3 row 9), unestablished:<reason> for any other first reason
    (``unestablished`` when it has none). An established fact has no reading cause: its failure is a coding rule's, and
    the caller names that rule (``coding_rule``)."""
    if found.result is Result.UNKNOWN:
        return READING_UNKNOWN
    if found.result is Result.CONTRADICTED:
        return READING_CONTRADICTED
    reason = found.reasons[0] if found.reasons else None
    if reason is None:
        return UNESTABLISHED
    appraisal = APPRAISAL_CAUSES.get(reason)
    if appraisal is not None:
        return f'appraisal:{appraisal.value}'
    return f'{UNESTABLISHED}:{reason.value}'


# The causes engine/pairing.py gives a relation's hold (4.4's relation:<type>; pairing.cause).
POSSIBLE_STATEMENT = 'relation:possible_statement'
RELATION_CAUSES: frozenset[str] = frozenset(
    [f'relation:{relation.value}' for relation in pairing.Relation if relation is not pairing.Relation.INDEPENDENT]
    + [POSSIBLE_STATEMENT])


# --- RANK applied (FINAL-V2 4.8) ---------------------------------------------------------------------------------------

_UNRANKED = len(rq.Rank) + 1  # service_date, which RANK does not rank: after every ranked item


def _kind_order(kind: ItemKind) -> int:
    return 0 if kind is ItemKind.QUESTION else 1


def _subject_order(R: FactSet, subject: Id | None) -> int:
    if subject is None:
        return -1
    for position, event in enumerate(R.events):
        if event == subject:
            return position
    for position, other in enumerate((*R.sessions, *R.lesions, *R.sections, *R.anatomy, *R.people)):
        if other == subject:
            return len(R.events) + position
    return len(R.events) + len(R.sessions) + len(R.lesions) + len(R.sections) + len(R.anatomy) + len(R.people)


def order(held: HeldFact, R: FactSet) -> tuple[int, int, int, int, int]:
    """4.8's order of a held fact: its rank (unranked last), a question before an explanation at an equal rank, then
    document order (its first span; a fact quoting nothing after every quoting one), then its subject's place in pass
    1's order."""
    first = min(held.spans) if held.spans else None
    start = first.start if first is not None else -1
    return (held.rank if held.rank is not None else _UNRANKED, _kind_order(held.kind), 0 if first is not None else 1,
            start, _subject_order(R, held.subject))


def ranked(held_facts: Iterable[HeldFact], R: FactSet) -> tuple[HeldFact, ...]:
    """``held_facts`` in 4.8's order (``order``), each once (the first of equal records kept)."""
    unique_facts = tuple(dict.fromkeys(held_facts))
    return tuple(sorted(unique_facts, key=lambda held: order(held, R)))


# --- the binding (FINAL-V2 4.8 [R:HO-8]) --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Candidate:
    """A positive candidate of one requirement group (4.4): its event, its witnesses (the held facts SUPPORT and the
    code's per-act rows record for it, every one kept, [R:HO-8]) and ``unmet``, how many of the requirements the
    per-code rule evaluates on it are not T (4.8's "fewest non-T requirements")."""
    event: Id
    witnesses: tuple[HeldFact, ...]
    unmet: int

    def top(self, R: FactSet) -> HeldFact | None:
        """The candidate's own top item: its first witness in 4.8's order."""
        found = ranked(self.witnesses, R)
        return found[0] if found else None


def _overlaps(one: Span, other: Span) -> bool:
    return one.start < other.end and other.start < one.end


def _anchor_start(R: FactSet, event: Id) -> int:
    anchor = R.anchors.get(event)
    return min(unit.start for unit in anchor.units) if anchor is not None and anchor.units else -1


def _event_order(R: FactSet, event: Id) -> tuple[int, int]:
    """Document order of an event: its anchor's first unit (an event with none before every placed one), then pass 1's
    order."""
    return (_anchor_start(R, event), _subject_order(R, event))


def kept_overlap(kept: Sequence[Span], R: FactSet, event: Id) -> bool:
    """Whether one of the code's kept spans overlaps ``event``'s anchor units (4.8 binding rule (1))."""
    anchor = R.anchors.get(event)
    return anchor is not None and any(_overlaps(span, unit) for span in kept for unit in anchor.units)


def choose(kept: Sequence[Span], candidates: Sequence[Candidate], R: FactSet) -> Id:
    """4.8's binding over a group's positive candidates (module docstring): (1) kept-span overlap, when any candidate's
    anchor is overlapped; (2) the top item's rank; (3) the fewest non-T requirements; (4) at an equal rank a question
    before an explanation; (5) document order. ValueError for no candidate."""
    if not candidates:
        raise ValueError('A binding is chosen among positive candidates, and there are none.')
    overlapped = [candidate for candidate in candidates if kept_overlap(kept, R, candidate.event)]
    pool = overlapped or list(candidates)

    def key(candidate: Candidate) -> tuple[int, int, int, tuple[int, int]]:
        top = candidate.top(R)
        rank = (top.rank if top.rank is not None else _UNRANKED) if top is not None else _UNRANKED + 1
        kind = _kind_order(top.kind) if top is not None else 1
        return (rank, candidate.unmet, kind, _event_order(R, candidate.event))

    return min(pool, key=key).event


# --- the item (FINAL-V2 4.8; D182) -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Group:
    """One requirement group of a held code as the item reads it: its kinds, its positive candidates (with their
    witnesses) and the bound one (None for a group no positive candidate holds: its held fact is code-level)."""
    kinds: tuple[Kind, ...]
    candidates: tuple[Candidate, ...]
    bound: Id | None


def on_binding(held_facts: Sequence[HeldFact], groups: Sequence[Group]) -> tuple[HeldFact, ...]:
    """The held facts ON the chosen bindings (module docstring): every held fact but a witness of a positive candidate
    that is not its group's bound one, unless the bound candidate shares it."""
    off: set[HeldFact] = set()
    kept_on: set[HeldFact] = set()
    for group in groups:
        for candidate in group.candidates:
            target = kept_on if candidate.event == group.bound else off
            target.update(candidate.witnesses)
    return tuple(held for held in held_facts if held not in off or held in kept_on)


def select(held_facts: Sequence[HeldFact], groups: Sequence[Group], R: FactSet) -> HeldFact | None:
    """The ONE item of a held code (4.8, D182): the first held fact ON the binding in 4.8's order; None when nothing is
    held."""
    found = ranked(on_binding(held_facts, groups), R)
    return found[0] if found else None


# --- message ids (step 3c's wording.Message, mirrored; module docstring) ------------------------------------------------


@unique
class MessageId(Enum):
    """wording.Message, member for member (tests/v2/test_questions.py pins the two equal by name and value): the id of a
    held code's one item, naming one fixed question and reason that wording.build builds from the item's Fill and the
    revision text."""
    CONFLICT = 'conflict'
    CONFLICT_FACT = 'conflict_fact'
    DOUBT = 'doubt'
    STATEMENT_SCOPE = 'statement_scope'
    STATUS = 'status'
    NOT_DOCUMENTED = 'not_documented'
    ATTEMPTED = 'attempted'
    UNPROFILED = 'unprofiled'
    NOT_LINKED = 'not_linked'
    RECOGNISED_ONLY = 'recognised_only'
    UNRECONCILED = 'unreconciled'
    ENTRY = 'entry'
    ANOTHER_ENTRY = 'another_entry'
    TIME = 'time'
    TIME_BESIDE_VISIT = 'time_beside_visit'
    PERFORMER = 'performer'
    PROCEDURE = 'procedure'
    ANOTHER_TRACT = 'another_tract'
    ENTEROSCOPY_ROUTE = 'enteroscopy_route'
    ENTEROSCOPY_APPROACH = 'enteroscopy_approach'
    METHOD = 'method'
    TECHNIQUE = 'technique'
    STATED_TECHNIQUE = 'stated_technique'
    ANOTHER_TECHNIQUE = 'another_technique'
    ROUTE = 'route'
    WALL_INJECTION = 'wall_injection'
    ACT_TARGET = 'act_target'
    SITE = 'site'
    ANOTHER_SITE = 'another_site'
    DUCT = 'duct'
    TARGET = 'target'
    STRUCTURE = 'structure'
    ANOTHER_STRUCTURE = 'another_structure'
    STATIONS = 'stations'
    STATION_CLASS = 'station_class'
    EXTENT = 'extent'
    EXAMINATION_CLASS = 'examination_class'
    ENTEROSCOPY_CLASS = 'enteroscopy_class'
    YIELD = 'yield'
    NOTHING_RETRIEVED = 'nothing_retrieved'
    CANNULATION = 'cannulation'
    PART = 'part'
    BUNDLING_TARGET = 'bundling_target'
    CAUSE = 'cause'
    BUNDLED = 'bundled'
    EM_BASIS = 'em_basis'
    SEPARATE_EM = 'separate_em'
    SEPARATE_EM_DENIED = 'separate_em_denied'
    BASE_INCLUDED = 'base_included'
    BASE_EXPLAINED = 'base_explained'
    BASE_WITHIN = 'base_within'
    COMPETING = 'competing'
    SETTING = 'setting'
    PATIENT_STATUS = 'patient_status'
    SERVICE_DATE = 'service_date'
    # D225 (repair r3c's ids, mirrored)
    CONFLICT_ATTRIBUTE = 'conflict_attribute'
    UNLISTED_EVIDENCE = 'unlisted_evidence'
    EXAMINATION_ROUTE = 'examination_route'
    EXAMINATION_APPROACH = 'examination_approach'
    SAME_DUCT = 'same_duct'
    STRUCTURE_PLACE = 'structure_place'
    # D246 (repair r3c's id, mirrored; r4a R4 (a)): 3.2.6 rule 3's synthetic act
    SYNTHETIC_ACT = 'synthetic_act'
    # D258 and D253 QX (ii) (repair r3c of round w8r's ids, mirrored): a statement that names no procedure session, the
    # held session's examination asked; ENT's route part whose only unknown is the anatomy passed through
    UNLISTED_SCOPE = 'unlisted_scope'
    ENTEROSCOPY_THROUGH = 'enteroscopy_through'


@unique
class Bundling(Enum):
    """wording.Bundling, member for member (pinned equal by tests/v2/test_questions.py): the bundling rule an item about
    a part names."""
    BIOPSY_OF_REMOVED_LESION = 'biopsy_of_removed_lesion'
    RESECTION_TECHNIQUE = 'resection_technique'
    LIFT_INJECTION = 'lift_injection'
    PROCEDURAL_ADJUNCT = 'procedural_adjunct'
    DRAINAGE_STEP = 'drainage_step'
    STENT_INCLUDED = 'stent_included'
    CLIP = 'clip'
    CANNULATION = 'cannulation'


@dataclass(frozen=True, slots=True)
class Fill:
    """wording.Slots, field for field (names, types and defaults pinned equal by tests/v2/test_questions.py; ``bundling``
    holds this module's Bundling, which the caller turns into wording.Bundling by value): what an item's sentence names,
    text-free - enumeration members, codes and integer spans. The engine writes it; the caller slices the revision for
    its spans after the decision."""
    code: str = ''
    act: Kind | None = None
    device: Device | None = None
    lesion: tuple[Span, ...] = ()
    place: Landmark | None = None
    words: tuple[Span, ...] = ()
    statements: tuple[tuple[Span, ...], ...] = ()
    whole: Kind | None = None
    whole_words: tuple[Span, ...] = ()
    group: tuple[Kind, ...] = ()
    family: SessionKind | None = None
    technique: catalogue.TechniqueClass | None = None
    stated: catalogue.TechniqueClass | None = None
    site: catalogue.SiteClass | None = None
    exam_class: catalogue.EusClass | None = None
    enteroscopy_class: catalogue.EnteroscopyClass | None = None
    reached: Extent | None = None
    incomplete: bool = False
    owner: Owner | None = None
    stations: tuple[Station, ...] = ()
    denied: tuple[Station, ...] = ()
    tract: Tract | None = None
    required_tract: Tract | None = None
    approach: Approach | None = None
    approach_words: tuple[Span, ...] = ()
    approaches: tuple[Approach, ...] = ()
    bundling: Bundling | None = None
    listed: tuple[Kind, ...] = ()
    possible: tuple[Kind, ...] = ()
    codes: tuple[str, ...] = ()
    both: bool = False
    attribute: Attribute | None = None
    unlisted_what: UnlistedWhat | None = None
    unlisted_kind: Kind | None = None
    whole_family: SessionKind | None = None
    whole_possible: bool = False
    possible_approaches: tuple[Approach, ...] = ()


@dataclass(frozen=True, slots=True)
class CodeFacts:
    """What an item names of the code itself (the proposal's code and its catalogue row; engine/evaluate.py fills it):
    code, family, the requirement group's kinds, and the parameters of its code-specific rows."""
    code: str
    family: SessionKind
    group: tuple[Kind, ...]
    technique: catalogue.TechniqueClass | None = None
    site: catalogue.SiteClass | None = None
    exam_class: catalogue.EusClass | None = None
    tract: Tract | None = None


@dataclass(frozen=True, slots=True)
class Item:
    """A held code's one clarification (4.8, D182): the held fact it rests on (its fact key, kind, cause, subject, rank
    and spans), the message id that words it, and the Fill its sentence is built from. ``kind`` is the held fact's:
    question or explanation."""
    held: HeldFact
    message: MessageId
    fill: Fill

    @property
    def kind(self) -> ItemKind:
        return self.held.kind


@dataclass(frozen=True, slots=True)
class Side:
    """One act an exchange question names (text-free): its stent kind, its spans (its anchor, or a kept unlisted act's
    own units: the words its sentence quotes) and its event (None for a kept unlisted act - 3.2.6 rule 3's synthetic
    act, D216 - which has no id)."""
    kind: Kind
    spans: tuple[Span, ...]
    event: Id | None = None


@dataclass(frozen=True, slots=True)
class Exchange:
    """XCHG's duct question (D225, refute-4a-r2 P6): the act whose duct is not established (``unknown``, the act it
    names) and its counterpart (``known``, the "whole" of wording's two-act same_duct form)."""
    unknown: Side
    known: Side


# The natures of a kept unlisted entry a synthetic act's doubt may be about (engine/evaluate.py's synthetic_possible:
# refute-r4a-r1 F1); ``synthetic_entry`` takes them in FactSet.unlisted's order, as evaluate.py records them.
_POSSIBLY_PERFORMED: frozenset[UnlistedWhat] = frozenset({UnlistedWhat.ACT, UnlistedWhat.DOUBT})
# Each coverage bundling rule the bundling items name, as this module's Bundling (wording.Bundling's mirror) - computed
# from the two enumerations by value (D246): every rule but the family's own bundled kind, which no Bundling names.
_BUNDLING_OF: Mapping[coverage.Rule, Bundling] = MappingProxyType({
    rule: member for rule in coverage.Rule for member in Bundling if member.value == rule.value})
# The bundling items (D246): the part's question about its whole (PART, BUNDLING_TARGET) and its explanation (BUNDLED).
_BUNDLING_ITEMS: frozenset[MessageId] = frozenset({MessageId.PART, MessageId.BUNDLING_TARGET, MessageId.BUNDLED})
# The enteroscopy class items (D246; step 4c's classes.py raises their holds) - those whose class sentence a reach
# not supported leaves with no true form (``item``'s exception) - and every item ``_enteroscopy_fill`` fills: those and
# the route part whose only unknown is the anatomy passed through (D253 QX (ii)), whose item ``select`` chooses as it
# chose its PROCEDURE question before.
_ENTEROSCOPY_ITEMS: frozenset[MessageId] = frozenset({MessageId.ENTEROSCOPY_APPROACH, MessageId.ENTEROSCOPY_CLASS,
                                                      MessageId.ENTEROSCOPY_ROUTE})
_ENTEROSCOPY_FILLED: frozenset[MessageId] = _ENTEROSCOPY_ITEMS | {MessageId.ENTEROSCOPY_THROUGH}


def _no_holds() -> Mapping[HeldFact, UnlistedStatement]:
    return MappingProxyType({})


def _no_exchanges() -> Mapping[HeldFact, Exchange]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class Raised:
    """What engine/evaluate.py knows of holds it raised that the item needs beside the FactSet (D225), each by its held
    fact: 3.2.6 rule 2's holds by the kept unlisted entry on the code's evidence each quotes (``evidence``: worded as
    that entry, its own kind and unit - P11); XCHG's duct questions by their two acts (``exchanges``: P6); the synthetic
    acts' doubts (D216) by their kept unlisted act (``synthetic``). Empty by default: a caller with none (assess's
    fallback) gets the item every other hold gets."""
    evidence: Mapping[HeldFact, UnlistedStatement] = field(default_factory=_no_holds)
    exchanges: Mapping[HeldFact, Exchange] = field(default_factory=_no_exchanges)
    synthetic: Mapping[HeldFact, UnlistedStatement] = field(default_factory=_no_holds)


# Each fact key's message by kind, where one id serves every rule (the rest are chosen by cause in ``message_of``).
_BY_FACT: Mapping[tuple[rq.FactKey, ItemKind], MessageId] = MappingProxyType({
    (rq.FactKey.STATEMENT_SCOPE, _Q): MessageId.STATEMENT_SCOPE,
    (rq.FactKey.EVENT_ENTRY, _Q): MessageId.ENTRY, (rq.FactKey.EVENT_ENTRY, _E): MessageId.ANOTHER_ENTRY,
    (rq.FactKey.EVENT_TIME, _Q): MessageId.TIME, (rq.FactKey.EVENT_PERFORMER, _Q): MessageId.PERFORMER,
    (rq.FactKey.PROCEDURE, _Q): MessageId.PROCEDURE, (rq.FactKey.ACT_METHOD, _Q): MessageId.METHOD,
    (rq.FactKey.EXAM_STATIONS, _Q): MessageId.STATIONS, (rq.FactKey.EXAM_STATIONS, _E): MessageId.STATION_CLASS,
    (rq.FactKey.EXTENT, _Q): MessageId.EXTENT, (rq.FactKey.EXTENT, _E): MessageId.EXAMINATION_CLASS,
    (rq.FactKey.ACT_YIELD, _Q): MessageId.YIELD, (rq.FactKey.ACT_YIELD, _E): MessageId.NOTHING_RETRIEVED,
    (rq.FactKey.CANNULATION, _Q): MessageId.CANNULATION, (rq.FactKey.ACT_PART, _Q): MessageId.PART,
    (rq.FactKey.ACT_CAUSE, _Q): MessageId.CAUSE, (rq.FactKey.EM_BASIS, _Q): MessageId.EM_BASIS,
    (rq.FactKey.SEPARATE_EM, _Q): MessageId.SEPARATE_EM, (rq.FactKey.SEPARATE_EM, _E): MessageId.SEPARATE_EM_DENIED,
    (rq.FactKey.BASE_INCLUDED, _Q): MessageId.BASE_INCLUDED, (rq.FactKey.BASE_INCLUDED, _E): MessageId.BASE_EXPLAINED,
    (rq.FactKey.COMPETING_CODES, _Q): MessageId.COMPETING, (rq.FactKey.SETTING, _Q): MessageId.SETTING,
    (rq.FactKey.PATIENT_STATUS, _Q): MessageId.PATIENT_STATUS, (rq.FactKey.SERVICE_DATE, _Q): MessageId.SERVICE_DATE,
    (rq.FactKey.TARGET, _Q): MessageId.TARGET, (rq.FactKey.TARGET, _E): MessageId.ANOTHER_STRUCTURE,
    (rq.FactKey.TECHNIQUE, _E): MessageId.ANOTHER_TECHNIQUE, (rq.FactKey.ACT_TARGET, _E): MessageId.ANOTHER_SITE,
})
# The coding rules whose established failure at rank 4 is its own explanation (4.3, 4.4, D80, D197).
_STATUS_EXPLANATIONS: Mapping[Rule, MessageId] = MappingProxyType({
    Rule.ATTEMPTED: MessageId.ATTEMPTED, Rule.UNPROFILED: MessageId.UNPROFILED, Rule.NOT_LINKED: MessageId.NOT_LINKED,
    Rule.RECOGNISED_ONLY: MessageId.RECOGNISED_ONLY, Rule.ROUTE_B: MessageId.UNRECONCILED})


def fact_of(held: HeldFact) -> tuple[rq.FactKey, Kind | None]:
    """The RANK fact key a held fact carries, and the kind its conflict names (conflict:<kind>; None for any other key).
    ValueError for a key RANK does not name."""
    for key in rq.FactKey:
        if key is not rq.FactKey.CONFLICT and held.fact == rq.fact_key(key):
            return key, None
    for kind in Kind:
        if held.fact == rq.fact_key(rq.FactKey.CONFLICT, kind):
            return rq.FactKey.CONFLICT, kind
    raise ValueError('A held fact names a fact key RANK gives (engine/requirements.FactKey).')


def _rule_of(held: HeldFact) -> Rule | None:
    for rule in Rule:
        if held.cause == coding_rule(rule):
            return rule
    return None


def _stoma_route(held: HeldFact, code: CodeFacts, rule: Rule | None) -> bool:
    """Whether a procedure hold is LOWER's approach for the stoma EUS class (4.3 LOWER; RANK row 8's "approach for a
    class"): the code's EUS class the stoma class, and the hold about the session's approach or the stoma anatomy entry
    (an approach question carries its reading's cause, an explanation coding_rule:lower)."""
    return (code.exam_class is catalogue.EusClass.STOMA and held.attribute in (_A.APPROACH, _A.TYPE)
            and rule in (Rule.LOWER, None))


# The facts step 4c's ENT route part rests on (classes._route), each with the family of its subject: the session's
# through, and the type of the anatomy entry its supported through names.
_ROUTE_FACTS: Mapping[Attribute, IdFamily] = MappingProxyType({_A.THROUGH: IdFamily.SESSION,
                                                              _A.TYPE: IdFamily.ANATOMY})


def _through_unknown(held: HeldFact, code: CodeFacts, rule: Rule | None) -> bool:
    """Whether a procedure question is ENT's route part whose only unknown is the anatomy passed through (DECISIONS D253
    QX (ii)): step 4c's classes._route U for a class that passes through an anatomy entry (classes.ROUTE_CLASSES: the
    stoma and pouch classes) - the session's through not supported, or its entry's type not established - a question
    carrying its fact's reading cause, never coding_rule:enteroscopy_class (whose route question is
    ENTEROSCOPY_ROUTE's); the held fact about the session's through or the type of an anatomy entry. The oral classes'
    two-route doubt is not one (``_two_routes``: its unknown is the route itself, the mouth or the documented stoma -
    refute-r4a-r1 P2 of round w8r: "passed through the mouth; ... the altered anatomy it was passed through" stated
    the oral route and presupposed the altered anatomy in doubt). No other rule raises a procedure question on those
    facts for an enteroscopy code (LOWER's stoma entry is the EUS stoma class's: ``_stoma_route``)."""
    return (catalogue.code_class(code.code) in classes.ROUTE_CLASSES and rule is None and held.attribute is not None
            and held.subject is not None and _ROUTE_FACTS.get(held.attribute) is held.subject.family)


def _two_routes(held: HeldFact, code: CodeFacts, rule: Rule | None) -> bool:
    """Whether a procedure question is the oral classes' two-route doubt (step 4c's classes._route U for a class that
    needs the oral route, classes.ORAL_CLASSES: the anatomy the session went through may open a stoma's or a pouch's
    route) over a through that is not established - a question carrying the through's reading cause on the session.
    D253 QX (ii) asks it by the route's own question, ENTEROSCOPY_ROUTE ("whether it was passed through the mouth or
    through the documented stoma"), as the class rule's own doubt over an established through is asked - never
    PROCEDURE, and never ENTEROSCOPY_THROUGH (refute-r4a-r1 P2 of round w8r)."""
    return (catalogue.code_class(code.code) in classes.ORAL_CLASSES and rule is None and held.attribute is _A.THROUGH
            and held.subject is not None and held.subject.family is IdFamily.SESSION)


def _approach_unknown(held: HeldFact, code: CodeFacts, rule: Rule | None) -> bool:
    """Whether a procedure question is ENT's approach part whose only unknown is the route (DECISIONS D267, r4a QA
    option (b); D253 QX (ii)): step 4c's classes._approach U for any enteroscopy class - the session's approach not
    established - a question carrying its fact's reading cause (never coding_rule:enteroscopy_class, the class rule's
    own doubt, which ENTEROSCOPY_ROUTE already words), the held fact about a session's approach. 44376 reaching the ileum
    with the approach silent asks the route ("whether it was passed through the mouth or ..."), never "In which
    procedure was the enteroscopy done?" - the procedure is known. No other rule raises a procedure question on a
    session's approach for an enteroscopy code (LOWER's approach is the EUS stoma class's: ``_stoma_route``)."""
    return (catalogue.code_class(code.code) is not None and rule is None and held.attribute is _A.APPROACH
            and held.subject is not None and held.subject.family is IdFamily.SESSION)


def message_of(held: HeldFact, code: CodeFacts) -> MessageId:
    """The message id that words ``held`` (4.8; step 3c's MESSAGES): chosen by its fact key, its kind and, where one
    fact has several sentences, by the coding rule its cause names - a relation's conflict quotes both statements, a
    contradicted fact its sides; a rank-2 performed_status is a doubt, a rank-4 one a status question, not-documented,
    or the explanation of C-9, route (d), D80 or route (b); the technique by the code's class (TECH), the act's statement
    of a device (the pairing's technique row) or the EUS route (ROUTE); act_target by the site class (SITE), the duct
    (XCHG) or the act's place (route (b)); target by 43240's structure, its explanation by what the rule read (the
    structure, or a place set apart: STRUCTURE_PLACE, refute-4a-r2 P10); procedure's explanation by the tract (TRACT);
    for the stoma EUS class (LOWER), procedure by the approach (EXAMINATION_ROUTE, EXAMINATION_APPROACH: P5); ENT's
    route part whose only unknown is the anatomy passed through - for the stoma and pouch classes, a question with its
    fact's reading cause on the session's through or an entry's type - by ENTEROSCOPY_THROUGH (D253 QX (ii),
    ``_through_unknown``), and the oral classes' two-route doubt over a through not established by ENTEROSCOPY_ROUTE
    (``_two_routes``: refute-r4a-r1 P2 of round w8r), never PROCEDURE; ENT's approach part whose only unknown is the
    route - a question with its fact's reading cause on a session's approach, any enteroscopy class - by
    ENTEROSCOPY_ROUTE too (``_approach_unknown``: DECISIONS D267, r4a QA option (b)); a contradicted attribute other
    than the status by
    that attribute (CONFLICT_ATTRIBUTE: P7); a base-within
    hold (step 4d's combination.base_within_hold, cause coding_rule:base_within) by BASE_WITHIN (D246, 5c's R8).
    ``item`` refines it where the FactSet or the holds evaluate.py raised decide (``_refined``: SYNTHETIC_ACT,
    UNLISTED_SCOPE). Every id it returns has the held fact's fact key and rank in wording.MESSAGES, and its kind too -
    but for BASE_WITHIN, an explanation in wording, which a base-within hold of a possible whole (a question) is mapped
    to by the ruling's letter (r4a's QW; D257 words the possible whole) (tested)."""
    key, _ = fact_of(held)
    if key is rq.FactKey.BASE_INCLUDED and held.cause == combination.WITHIN_CAUSE:  # D246 (5c's R8)
        return MessageId.BASE_WITHIN
    rule = _rule_of(held)
    relation = held.cause in RELATION_CAUSES
    if key is rq.FactKey.CONFLICT:
        if relation:
            return MessageId.CONFLICT
        if held.attribute is not None and held.attribute is not _A.STATUS:  # D225 P7: about that attribute
            return MessageId.CONFLICT_ATTRIBUTE
        return MessageId.CONFLICT_FACT
    if key is rq.FactKey.PERFORMED_STATUS:
        if held.rank == rq.Rank.DOUBT.value:
            return MessageId.DOUBT
        if held.rank == rq.Rank.BUNDLED.value:
            return MessageId.BUNDLED
        if held.kind is _E and rule is not None and rule in _STATUS_EXPLANATIONS:
            return _STATUS_EXPLANATIONS[rule]
        return MessageId.NOT_DOCUMENTED if rule is Rule.NOT_DOCUMENTED else MessageId.STATUS
    if key is rq.FactKey.TECHNIQUE and held.kind is _Q:
        if rule is Rule.ROUTE:
            return MessageId.ROUTE
        return MessageId.TECHNIQUE if rule is Rule.TECHNIQUE and code.technique is not None else \
            MessageId.STATED_TECHNIQUE
    if key is rq.FactKey.TECHNIQUE and rule is Rule.ROUTE:
        return MessageId.WALL_INJECTION
    if key is rq.FactKey.ACT_TARGET and held.kind is _Q:
        if held.rank == rq.Rank.BUNDLING.value:
            return MessageId.BUNDLING_TARGET
        if rule is Rule.SITE and code.site is not None:
            return MessageId.SITE
        return MessageId.DUCT if rule is Rule.EXCHANGE else MessageId.ACT_TARGET
    if key is rq.FactKey.TARGET and held.kind is _Q and rule is Rule.STRUCTURE:
        return MessageId.STRUCTURE
    if key is rq.FactKey.TARGET and held.kind is _E and rule is Rule.STRUCTURE and held.attribute is _A.TARGET_PLACES:
        return MessageId.STRUCTURE_PLACE  # D225 P10: the place STRUCT:pfc sets apart, named
    if key is rq.FactKey.PROCEDURE and _stoma_route(held, code, rule):  # D225 P5: the approach asked as the approach
        return MessageId.EXAMINATION_APPROACH if held.kind is _E else MessageId.EXAMINATION_ROUTE
    if key is rq.FactKey.PROCEDURE and held.kind is _Q and _through_unknown(held, code, rule):  # D253 QX (ii)
        return MessageId.ENTEROSCOPY_THROUGH
    if key is rq.FactKey.PROCEDURE and held.kind is _Q and _two_routes(held, code, rule):  # D253 QX (ii); P2
        return MessageId.ENTEROSCOPY_ROUTE
    if key is rq.FactKey.PROCEDURE and held.kind is _Q and _approach_unknown(held, code, rule):  # D267, r4a QA (b)
        return MessageId.ENTEROSCOPY_ROUTE
    if key is rq.FactKey.PROCEDURE and rule is Rule.ENTEROSCOPY_CLASS:
        return MessageId.ENTEROSCOPY_APPROACH if held.kind is _E else MessageId.ENTEROSCOPY_ROUTE
    if key is rq.FactKey.EXTENT and held.kind is _E and rule is Rule.ENTEROSCOPY_CLASS:
        return MessageId.ENTEROSCOPY_CLASS
    if key is rq.FactKey.PROCEDURE and held.kind is _E:
        return MessageId.ANOTHER_TRACT
    found = _BY_FACT.get((key, held.kind))
    if found is None:
        raise ValueError(f'No message words a {held.kind.value} about {held.fact}.')
    return found


# --- the fill (what the item's sentence names, text-free) ---------------------------------------------------------------


def _supported(found: Fact) -> object:
    return found.value if found.result is Result.SUPPORTED else None


def _first_place(R: FactSet, subject: Id, attribute: Attribute) -> Landmark | None:
    for member in facts_.members(R, subject, attribute):
        if member.result is Result.SUPPORTED and isinstance(member.value, Landmark):
            return member.value
    return None


def anchor_units(R: FactSet, event: Id | None) -> tuple[Span, ...]:
    """An event's own statement: its anchor's unit spans, each once, in document order; () for none."""
    anchor = R.anchors.get(event) if event is not None else None
    return tuple(sorted(set(anchor.units))) if anchor is not None else ()


def act_kind(R: FactSet, event: Id | None, group: Sequence[Kind]) -> Kind | None:
    """The kind an item names an act by: the catalogue kind of its SUPPORTED kind with its supported purpose (a clip or
    an injection for hemostasis is a bleeding control, catalogue.catalogue_kind); an act whose kind is not supported -
    negated, doubted, unresolved, contradicted or silent - or is other is Kind.OTHER, "another act" (DECISIONS D267:
    D254 rule 2 reaches every kind that is not SUPPORTED, refute-5c-r1 P2's four inputs; the one label overlay's slots,
    the Fill and evaluate's conflict key read - a negated snare is never "the snare removal", the kind the document
    denies). For no act (a code-level hold), the first kind of the code's group (None for none)."""
    if event is None:
        return group[0] if group else None
    found = facts_.fact(R, event, _A.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        purpose = _supported(facts_.fact(R, event, _A.PURPOSE))
        named = catalogue.catalogue_kind(found.value, purpose if isinstance(purpose, Purpose) else None)
        if named is not None:
            return named
    return Kind.OTHER


def _act_slot(R: FactSet, event: Id | None, group: Sequence[Kind]) -> Kind | None:
    """The kind a Fill's act slot names an act by (DECISIONS D254 rule 2, D267): ``act_kind`` - an act no kind names
    (its kind other, or not supported: negated, doubted, unresolved, contradicted, silent) is Kind.OTHER, "another act",
    the one label wording gives it everywhere and the kind 5c's item_slots names it by; never the code's group's kind,
    which is no fact of that act. For no act (a code-level hold: the code's group is what the item names) the first
    kind of the group."""
    return act_kind(R, event, group)


def _event(subject: Id | None) -> Id | None:
    return subject if subject is not None and subject.family is IdFamily.EVENT else None


def _unlisted_units(held: HeldFact, R: FactSet, act: Id | None) -> tuple[Span, ...]:
    """The units of the unlisted entry an unlisted hold quotes: the entry of the act's unlisted pair whose spans the
    held fact records (3.2.6 rule 4: the entry's units and the act's anchor), else the held fact's spans that are not
    the act's anchor, else every span it records (3.2.6 rule 2's hold records the entry's units alone). An entry found
    in the act's own sentence is quoted too: the act's anchor is then the entry's unit (the refutation's F2)."""
    pair = _unlisted_pair(held, R, act)
    if pair is not None:
        return tuple(sorted(set(pair.statement.units)))
    own = anchor_units(R, act)
    return tuple(span for span in held.spans if span not in own) or held.spans


def _unlisted_pair(held: HeldFact, R: FactSet, act: Id | None) -> pairing.UnlistedPair | None:
    """3.2.6 rule 4's pair an unlisted hold about ``act`` records (row 8): the act's unlisted pair whose spans the held
    fact records - the entry's units and the act's anchor - and whose cause it carries (pairing.cause, as
    ``_statement_of`` reads a relation's), else None (3.2.6 rule 2's hold, a synthetic act's, or another rule's hold
    that happens to quote the same units)."""
    if act is None:
        return None
    return next((pair for pair in pairing.unlisted_pairs(R, act)
                 if pair.spans == held.spans and pairing.cause(pair) == held.cause), None)


def _statement_of(held: HeldFact, R: FactSet) -> Id | None:
    """The statement a relation's hold quotes beside its act (engine/pairing.py): the paired statement whose pair the
    held fact records (the same act, both anchors as its spans, the same cause)."""
    act = _event(held.subject)
    if act is None or held.cause not in RELATION_CAUSES:
        return None
    for pair in pairing.pairs_of(R, act):
        if pair.spans == held.spans and pairing.cause(pair) == held.cause:
            return pair.statement
    return None


@dataclass(frozen=True, slots=True)
class _Named:
    """What an item is about: the act it names (None for a code-level hold that names the code's group instead) and the
    statements it quotes, each its spans."""
    act: Id | None
    statements: tuple[tuple[Span, ...], ...]


# The holds that name the code itself, never an act (4.4's held('unprofiled'), held('recognised_only'), 7.6, D197).
_CODE_LEVEL: frozenset[Rule] = frozenset({Rule.UNPROFILED, Rule.NOT_LINKED, Rule.RECOGNISED_ONLY, Rule.ROUTE_B,
                                          Rule.NOT_DOCUMENTED})


def _named(held: HeldFact, groups: Sequence[Group], R: FactSet, acts: Sequence[Id]) -> _Named:
    """The act ``held`` names and the statements it quotes, by where the hold comes from: a relation (the act and its
    paired statement); an unlisted statement (the act, and the unlisted entry's units - ``_unlisted_units`` - even
    where they are the act's own sentence; 3.2.6 rule 2's hold on the kept evidence names its subject, the supporting
    act sharing the unit, else the bound or first supporting act, else none - its words then the unit); an exclusion's
    statement_scope (no act: the code's group, and the statement); not documented and the never-ready holds (no act);
    any other witness (its own event - an act, or a session's examination - else the group's bound act, else the
    first of the code's supporting ``acts`` in the session it is about; a contradicted fact's sides, each span its own
    statement)."""
    rule = _rule_of(held)
    if rule is Rule.STATEMENT_SCOPE:
        return _Named(None, (anchor_units(R, _event(held.subject)) or held.spans,))
    if rule is not None and rule in _CODE_LEVEL:
        return _Named(None, ())
    act = _event(held.subject)
    if act is None:
        act = next((group.bound for group in groups if group.bound is not None), None)
    if act is None:
        act = next((event for event in acts if facts_.holds(facts_.fact(R, event, _A.SESSION), held.subject)),
                   acts[0] if acts else None) if held.subject is not None else (acts[0] if acts else None)
    statement = _statement_of(held, R)
    if statement is not None:
        return _Named(act, (anchor_units(R, statement),))
    own = anchor_units(R, act)
    others = tuple(span for span in held.spans if span not in own)
    if held.cause == UNLISTED:
        units = _unlisted_units(held, R, act)
        return _Named(act, (units,) if units else ())
    if held.result is Result.CONTRADICTED:
        sides = tuple(dict.fromkeys(others + held.spans))
        return _Named(act, tuple((span,) for span in sides))
    return _Named(act, ())


def _site_places(R: FactSet, event: Id) -> list[Landmark]:
    """SITE's supported places (D29), as engine/evaluate.py's SITE row reads them: the act's, then its supported
    lesion's."""
    places = [member.value for member in facts_.members(R, event, _A.TARGET_PLACES)
              if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)]
    lesion = facts_.fact(R, event, _A.TARGET_LESION)
    if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id):
        places += [member.value for member in facts_.members(R, lesion.value, _A.PLACES)
                   if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)]
    return places


def _outside_place(R: FactSet, event: Id, site: catalogue.SiteClass) -> Landmark | None:
    """The place another-site's explanation names: the first of SITE's supported places outside the class - the act's
    own, else its lesion's, which SITE reads too (an act whose place is told only on its lesion: the refutation's
    F3)."""
    return next((place for place in _site_places(R, event) if place not in catalogue.SITE_CLASSES[site]), None)


def _stations(R: FactSet, session: Id, result: Result) -> tuple[Station, ...]:
    return tuple(member.value for member in facts_.members(R, session, _A.STATIONS)
                 if member.result is result and isinstance(member.value, Station))


def _denied_stations(R: FactSet, session: Id, held: HeldFact) -> tuple[Station, ...]:
    """The stations a station-class explanation names as not examined: the negated upper stations (the esophagus, the
    stomach, the duodenum: the only ones STATIONS and LIMITED read), in pass 1's order; none for LIMITED's explanation,
    which is the limited class's (all three examined) - a negated station outside the upper tract (the jejunum) is
    never named as the full class's misfit (the refutation's F5)."""
    if held.kind is _E and _rule_of(held) is Rule.LIMITED:
        return ()
    return tuple(station for station in _stations(R, session, Result.NEGATED) if station in catalogue.UPPER_STATIONS)


def _reached(R: FactSet, session: Id, code: CodeFacts) -> Extent | None:
    """The reach an examination-class explanation names: the session's first supported reached point outside the
    code's class reach, else its first supported one."""
    points = [member.value for member in facts_.members(R, session, _A.REACHED)
              if member.result is Result.SUPPORTED and isinstance(member.value, Extent)]
    reach = catalogue.EUS_CLASS_REACH.get(code.exam_class) if code.exam_class is not None else None
    outside = [point for point in points if reach is not None and point not in reach]
    found = outside or points
    return found[0] if found else None


def _bundling(R: FactSet, event: Id | None, rule: Rule | None) -> Bundling | None:
    """The bundling rule CAUSE's explanation names (4.3: purpose prophylaxis is the clip rule, cause
    act_of_this_session the procedural adjunct); None for any other hold."""
    if rule is not Rule.CAUSE or event is None:
        return None
    if facts_.holds(facts_.fact(R, event, _A.PURPOSE), Purpose.PROPHYLAXIS):
        return Bundling.CLIP
    return Bundling.PROCEDURAL_ADJUNCT


def fill(held: HeldFact, groups: Sequence[Group], code: CodeFacts, R: FactSet, message: MessageId,
         acts: Sequence[Id] = (), raised: Raised | None = None) -> Fill:
    """The Fill of ``held``'s item (module docstring): the code and its row's parameters; the act the hold names (its
    kind as the item names it, its supported device, its first supported place, its anchor as its words; the code's
    group for a code-level hold); the statements it quotes; and, for the explanations that name an established value,
    that value (the entry's owner, the session's tract and stations, the act's technique class, the outside place).
    Then what D225's and D246's ids name (``_specific``): the unlisted entry on the evidence, XCHG's two acts, a
    synthetic act, an unlisted doubt's pair with a session's examination (D232), the contradicted attribute, the stoma
    class's approach, the place STRUCT:pfc sets apart, the bundling items' part, whole and rule, the enteroscopy class
    items' class, approach and form. A digital examination the hold names as the session's examination (its rows 2-5,
    read on another act's row 7: r4a QD2, kept as built by DECISIONS D271) is never quoted or named as it: the
    session's examination that may be quoted, by its service, and no device (``_session_named``: D265, "the DRE's
    sentence is never quoted as 'the colonoscopy'")."""
    named = _named(held, groups, R, acts)
    event = named.act
    words = anchor_units(R, event)
    if not words and held.cause == UNLISTED:  # 3.2.6 rule 2 with no act: the unlisted unit on the code's evidence
        words = held.spans
    device = _supported(facts_.fact(R, event, _A.TECHNIQUE_DEVICE)) if event is not None else None
    owner = _supported(facts_.fact(R, event, _A.ENTRY)) if event is not None else None
    session = _supported(facts_.fact(R, event, _A.SESSION)) if event is not None else None
    tract = _supported(facts_.fact(R, session, _A.TRACT)) if isinstance(session, Id) else None
    stated = catalogue.technique_class(device) if isinstance(device, Device) else None
    place = _first_place(R, event, _A.TARGET_PLACES) if event is not None else None
    if message is MessageId.ANOTHER_SITE and code.site is not None and event is not None:
        place = _outside_place(R, event, code.site) or place
    stations = _stations(R, session, Result.SUPPORTED) if isinstance(session, Id) else ()
    denied = _denied_stations(R, session, held) if isinstance(session, Id) else ()
    reached = _reached(R, session, code) if isinstance(session, Id) else None
    base = Fill(code=code.code, act=_act_slot(R, event, code.group), reached=reached,
                bundling=_bundling(R, event, _rule_of(held)),
                device=device if isinstance(device, Device) else None, place=place, words=words,
                statements=named.statements, group=code.group, family=code.family, technique=code.technique,
                stated=stated, site=code.site, exam_class=code.exam_class,
                owner=owner if isinstance(owner, Owner) else None, stations=stations, denied=denied,
                tract=tract if isinstance(tract, Tract) else None, required_tract=code.tract)
    where = session if isinstance(session, Id) else None
    if event is not None and base.act is Kind.EXAMINATION and digital_examination(R, event):
        base = _session_named(base, R, event, where)  # D265: never the digital examination as the session's
    return _specific(base, held, code, R, message, event, where, raised if raised is not None else Raised(), acts)


# --- what D225's ids name (refute-4a-r2 P5, P6, P7, P10, P11; repair r3c's ids) -----------------------------------------


def _family_of(R: FactSet, session: Id | None, code: CodeFacts) -> SessionKind:
    """The family an examination is named by: its session's supported kind, else the code's family."""
    kind = _supported(facts_.fact(R, session, _A.KIND)) if session is not None else None
    return kind if isinstance(kind, SessionKind) else code.family


def _session_of(held: HeldFact) -> Id | None:
    return held.subject if held.subject is not None and held.subject.family is IdFamily.SESSION else None


def synthetic_entry(held: HeldFact, R: FactSet, raised: Raised) -> UnlistedStatement | None:
    """The kept unlisted act or doubt a synthetic act's doubt is about (D216; 3.2.6 rule 3; an unlisted doubt is a
    possibly performed act too: refute-r4a-r1 F1): the one evaluate.py recorded (``raised.synthetic``); else, for a
    doubt about no event raised elsewhere or worded with no Raised (step 4c's synthetic examination act, and read time:
    performed_status at rank 2, cause unlisted, its subject a session or none), the first kept unlisted act or doubt,
    in FactSet.unlisted's order, whose own units are its spans - for a session's, one that may be that session's
    synthetic examination first (``_may_be_examination_of``) - the entry evaluate.py records first (refute-r4a-r1
    P10). None for any other hold (3.2.6 rule 2's is its own: ``raised.evidence``)."""
    if held in raised.evidence:
        return None
    found = raised.synthetic.get(held)
    if found is not None:
        return found
    if held.cause != UNLISTED or held.rank != rq.Rank.DOUBT.value or _event(held.subject) is not None:
        return None
    entries = [entry for entry in R.unlisted
               if entry.what in _POSSIBLY_PERFORMED and tuple(sorted(set(entry.units))) == held.spans]
    session = _session_of(held)
    # evaluate.py's own order (refute-r4a-r1 P10: read time, which passes no Raised, words the hold as assess does):
    # FactSet.unlisted's - the order row 7 records a witness in - a session's own synthetic examination first; the sort
    # is stable, so an act never jumps a doubt told before it on the same unit
    entries.sort(key=lambda entry: 0 if session is None or _may_be_examination_of(entry, session, R) else 1)
    return entries[0] if entries else None


def _may_be_examination_of(entry: UnlistedStatement, session: Id, R: FactSet) -> bool:
    """Whether a kept unlisted entry may be ``session``'s synthetic examination, as engine/evaluate.py's
    synthetic_examinations reads it (D216): its kind examination (or one covering it), or none named; its card that
    session, none, or a session the FactSet does not hold (4.11)."""
    return ((entry.kind is None or catalogue.covers(entry.kind, Kind.EXAMINATION))
            and (entry.session is None or entry.session == session or entry.session not in R.sessions))


def _conflict_kind(held: HeldFact, base: Fill) -> Kind | None:
    """The kind a conflict's sentence names its act by: the kind its fact key names (conflict:<kind>), so the item's
    sentence and its key name one act; the base Fill's when the key names none."""
    _, kind = fact_of(held)
    return kind if kind is not None else base.act


def _apart_place(R: FactSet, event: Id | None) -> Landmark | None:
    """The place STRUCT:pfc read that sets the act apart from a pancreatic fluid collection's drainage (D120, D136,
    D145): the act's first supported place in a biliary or hepatic region (catalogue.DEFINING_TARGET_APART)."""
    if event is None:
        return None
    return next((member.value for member in facts_.members(R, event, _A.TARGET_PLACES)
                 if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)
                 and anatomy.in_regions(member.value, catalogue.DEFINING_TARGET_APART)), None)


def _names_session(entry: UnlistedStatement, session: Id | None, R: FactSet) -> bool:
    """Whether a kept unlisted entry's session card names ``session`` (D232): the card is that session, and the FactSet
    holds it. No card, or a card naming a session the FactSet does not hold (4.11: it may be any session's), names
    none."""
    return session is not None and entry.session == session and session in R.sessions


def _names_sessions_examination(entry: UnlistedStatement, act: Id, R: FactSet) -> bool:
    """Whether a kept unlisted entry's card names the session the examination ``act`` is established in (D232): the
    act's session fact supported, naming the card's session."""
    return entry.session is not None and facts_.holds(facts_.fact(R, act, _A.SESSION), entry.session)


def _own_entry(base: Fill, entry: UnlistedStatement) -> Fill:
    """A kept unlisted entry named by itself (D216, D232): its own kind (an entry of no kind named as an act), its own
    units, nothing of the code's act, and no session's service - "the examination" its own unit speaks of."""
    return replace(base, act=entry.kind if entry.kind is not None else Kind.OTHER,
                   words=tuple(sorted(set(entry.units))), statements=(), device=None, place=None, lesion=(),
                   family=None)


def _names_no_held_session(entry: UnlistedStatement, R: FactSet) -> bool:
    """A kept unlisted entry whose card names no session the FactSet holds: none, or one it does not hold (4.11)."""
    return entry.session is None or entry.session not in R.sessions


def _scope_entry(held: HeldFact, R: FactSet, raised: Raised) -> UnlistedStatement | None:
    """The statement a rank-2 unlisted hold is asked by UNLISTED_SCOPE for (DECISIONS D258: "A statement that names no
    session is asked about the held session's performance, never about the statement"): a kept unlisted doubt or denial
    whose card names no procedure session the FactSet holds - none, or one it does not hold (4.11) - held against a
    session's examination:
    - 3.2.6 rule 4's pair (row 8, RANK row 2) of such a statement with an act whose own kind is the examination (QP2's
      no-card doubt, QD's no-card denial; p41);
    - a synthetic examination act's doubt (D216; row 7's in an act-only session, step 4c's examination part: r4c Q1)
      about a session, the entry a DOUBT of kind examination.
    None for every other hold: a synthetic ACT (SYNTHETIC_ACT: the document states it, whatever its card); an entry
    carded to a session the FactSet holds - the held one (DOUBT, its service named: D232) or another (DOUBT, the
    examination its own unit speaks of: D232); a pair with an act of another kind, or of no kind (DOUBT, the act's own
    sentence); an entry of no kind read as a synthetic act, which may be another rule's possible act (XCHG's
    counterpart, 43276's part) - asking the session's examination there would answer another question. The held fact
    is unchanged: performed_status at rank 2, cause unlisted (D228)."""
    if held.rank != rq.Rank.DOUBT.value or held in raised.evidence:  # the cause: synthetic_entry's, the pair's
        return None
    synthetic = synthetic_entry(held, R, raised)
    if synthetic is not None:
        if (synthetic.what is UnlistedWhat.DOUBT and synthetic.kind is Kind.EXAMINATION
                and _session_of(held) is not None and _names_no_held_session(synthetic, R)):
            return synthetic
        return None
    event = _event(held.subject)
    if event is None or act_kind(R, event, ()) is not Kind.EXAMINATION:
        return None
    pair = _unlisted_pair(held, R, event)
    return pair.statement if pair is not None and _names_no_held_session(pair.statement, R) else None


# The statuses an examination may be quoted under as possibly done on the date of service (D266): done, or begun - an
# examination begun counts as done (4.3 row 7, v1's done).
_DONE: frozenset[Status] = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})


def _possibly_done_today(R: FactSet, event: Id) -> bool:
    """An examination possibly done on the date of service (DECISIONS D266): its status possibly performed or begun -
    never negated, never established planned -, its effective date relation possibly the date of service - never of
    another date - and its effective performer possibly the documenting team - never another performer: 4.6 condition
    5's "possibly done today by the documenting team" (engine/evaluate.doubted reads the same three facts)."""
    status = facts_.fact(R, event, _A.STATUS)
    return (any(facts_.possibly(status, value) for value in _DONE)
            and facts_.possibly(facts_.fact(R, event, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE)
            and facts_.possibly(facts_.fact(R, event, _A.PERFORMER), Performer.DOCUMENTING_TEAM))


def _quotable(R: FactSet, event: Id | None) -> bool:
    """An examination an item may quote as the held session's examination (DECISIONS D265, D266): never a digital
    examination (FINAL 5.6 E13, ``digital_examination``: the DRE's sentence is never quoted as "the colonoscopy"), and
    only one possibly done on the date of service (``_possibly_done_today``: "Colonoscopy in 2019 was normal.", "Repeat
    colonoscopy in 3 years.", one by another performer or a denial is never quoted as the examination whose performance
    on the date of service is asked - refute-r4a-r2 F2, D258's QP2 mechanism)."""
    return event is not None and not digital_examination(R, event) and _possibly_done_today(R, event)


def _quoted_examination(R: FactSet, event: Id | None, session: Id | None) -> Id | None:
    """The examination UNLISTED_SCOPE and the carded DOUBT quote as the held session's examination (DECISIONS D266;
    D265): the held act when it may be quoted (``_quotable``); else the first event established as the session's
    examination (kind supported examination, session supported ``session``, a session the FactSet holds) that may be;
    else none - the question then names the examination by its service with no quote."""
    if _quotable(R, event):
        return event
    if session is None or session not in R.sessions:
        return None
    return next((other for other in R.events if facts_.holds(facts_.fact(R, other, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(facts_.fact(R, other, _A.SESSION), session) and _quotable(R, other)), None)


def _session_named(base: Fill, R: FactSet, event: Id | None, session: Id | None) -> Fill:
    """An item that names a session's examination by its service with the words of ``event``, the held act (DECISIONS
    D265, D266): those words, device, place and lesion as before when the act may be quoted (``_quotable``); else the
    words of the session's examination that may be (``_quoted_examination``: none in an act-only session, none of
    another occasion) and no device, place or lesion of the act - a digital examination is never named as the session's
    examination ("Was the colonoscopy (manual) (<the DRE's sentence>) done ...": refute-r4a-r2 F1, refute-r4a-r1 P3 of
    round w8r), and an examination of another occasion never as the one done on the date of service (refute-r4a-r2
    F2). The statements the item quotes are unchanged."""
    examination = _quoted_examination(R, event, session)
    if examination is not None and examination == event:
        return base
    return replace(base, words=anchor_units(R, examination), device=None, place=None, lesion=())


def _scope_family(R: FactSet, session: Id | None, code: CodeFacts) -> SessionKind | None:
    """The service UNLISTED_SCOPE names the held session's examination by (D258): its session's supported kind, else the
    code's family (``_family_of``) - none for a session the FactSet does not hold (refute-r4a-r1 P9: it may be any
    session, so no service is named; wording then says "the examination")."""
    if session is not None and session not in R.sessions:
        return None
    return _family_of(R, session, code)


def _scope_fill(base: Fill, held: HeldFact, code: CodeFacts, R: FactSet, event: Id | None, session: Id | None,
                raised: Raised) -> Fill:
    """UNLISTED_SCOPE's slots (D258; repair r3c of round w8r's builder): the held session's examination by its service
    (``family``, ``_scope_family``) and its own words (``words``: the examination the rule-4 pair holds, its anchor, for
    a synthetic examination's doubt the session's own examination - quoted only when it may be: never a digital
    examination, FINAL 5.6 E13, and only one possibly done on the date of service, DECISIONS D266 -, else the
    session's examination that may be, else none: ``_quoted_examination``), the statement quoted (``statements``: the
    entry's own units, none when it has none), its nature (``unlisted_what``, as the carded DOUBT's: D266), and the act
    an examination (no device, place or lesion of the code's act). It never names the statement's nature, and never
    says that the document leaves that examination in doubt or denies it (wording's builder)."""
    entry = _scope_entry(held, R, raised)
    units = tuple(sorted(set(entry.units))) if entry is not None else ()
    if _event(held.subject) is not None:  # 3.2.6 rule 4's pair: the held act is the examination
        where, examination = session, _quoted_examination(R, event, session)
    else:  # a synthetic examination's doubt: the held session
        where = _session_of(held)
        examination = _quoted_examination(R, None, where)
    return replace(base, act=Kind.EXAMINATION, family=_scope_family(R, where, code),
                   words=anchor_units(R, examination), statements=(units,) if units else (), device=None,
                   place=None, lesion=(), unlisted_what=entry.what if entry is not None else None)


def _side_slot(R: FactSet, side: Side) -> Kind:
    """The kind a SAME_DUCT act slot names one act of XCHG's two-act duct question by (DECISIONS D254 rule 2, in every
    Fill act slot: refute-r4a-r1 P4 of round w8r): the stent kind the exchange question reads it as (``side.kind``,
    engine/evaluate.py's naming, unchanged), unless no kind names the act - a filed act whose own kind names nothing
    (``act_kind``'s Kind.OTHER: its kind other, or not supported - D267) or a kept unlisted act or doubt of no kind
    (every entry with the side's own units, of a possibly performed nature, names none: one entry there naming a kind
    names the side by it - refute-r4a-r2 F4's shape, G3-01) - which is Kind.OTHER, "another act": never "the stent
    removal" for an act CPT Studio's reading gives no kind (wording then gives no exchange reason)."""
    if side.event is not None:
        return side.kind if act_kind(R, side.event, ()) is not Kind.OTHER else Kind.OTHER
    entries = [entry for entry in R.unlisted
               if entry.what in _POSSIBLY_PERFORMED and tuple(sorted(set(entry.units))) == side.spans]
    return Kind.OTHER if entries and all(entry.kind is None for entry in entries) else side.kind


def _whole_family(R: FactSet, session: Id | None) -> SessionKind | None:
    """The family BASE_WITHIN names a base-within hold's whole by (D257): the supported kind of the sessions ``session``
    is, or may be, the endoscopic portion of (combination.wholes, whose subset the hold's record keeps) when they are
    one family; None when they are none, of several families, or one of a kind not supported - wording then names
    "another procedure", never a whole it may not be (refute-r4d-r2 P5's "the endoscopic ultrasound" for a
    colonoscopy)."""
    if session is None:
        return None
    kinds = {_supported(facts_.fact(R, whole.session, _A.KIND)) for whole in combination.wholes(R, session)}
    found = next(iter(kinds)) if len(kinds) == 1 else None
    return found if isinstance(found, SessionKind) else None


def _bundling_cause(rule: coverage.Rule) -> str:
    """The cause coverage's explanation of a T bundle carries (coverage.Reader's explanation: coding_rule:<rule>)."""
    return f'coding_rule:{rule.value}'


def _bundle_of(held: HeldFact, R: FactSet, acts: Sequence[Id]) -> coverage.Bundle | None:
    """The coverage bundle (engine/coverage.py, step 4b's 4.7 bundling over the code's supporting acts) that raised a
    bundling hold (D246): for a T bundle, its explanation - subject the part, the bundle's rule as its cause, the part's
    and the whole's anchors as its spans; for a U bundle, one of its doubts' witnesses (coverage.witness, exactly as
    coverage.bundling records it, the part's and the whole's anchors as its spans). The supporting acts are the parts
    (coverage.bundling reads them), each in coverage's own order of its bundles; None when no bundle raised it."""
    reader = coverage.Reader(R)
    for part in dict.fromkeys(acts):
        for bundle in reader.bundles(part):
            spans = tuple(sorted(set(anchor_units(R, part)) | set(anchor_units(R, bundle.whole))))
            if held.spans != spans:
                continue
            if bundle.truth is coverage.Truth.T:
                if held.kind is _E and held.subject == part and held.cause == _bundling_cause(bundle.rule):
                    return bundle
                continue
            if any(coverage.witness(doubt.fact, doubt.attribute, doubt.subject, doubt.key, doubt.kind, spans,
                                    bundle.rule.value) == held for doubt in bundle.doubts):
                return bundle
    return None


def _bundling_fill(base: Fill, held: HeldFact, code: CodeFacts, R: FactSet, message: MessageId,
                   acts: Sequence[Id]) -> Fill:
    """What the bundling items name (D246): the bundle's rule (``bundling``); for PART and BUNDLING_TARGET also the part
    (its kind, device, place and anchor - whichever object the witness rests on: the part, its whole or a lesion) and
    its whole (its kind, ``whole_words`` its anchor units). Unchanged when no bundle raised the hold."""
    bundle = _bundle_of(held, R, acts)
    if bundle is None:
        return base
    rule = _BUNDLING_OF.get(bundle.rule)
    if message is MessageId.BUNDLED:
        return replace(base, bundling=rule)
    part, whole = bundle.part, bundle.whole
    device = _supported(facts_.fact(R, part, _A.TECHNIQUE_DEVICE))
    return replace(base, act=_act_slot(R, part, code.group), words=anchor_units(R, part),
                   device=device if isinstance(device, Device) else None,
                   place=_first_place(R, part, _A.TARGET_PLACES), lesion=(), statements=(),
                   whole=_act_slot(R, whole, ()) if whole is not None else None, whole_words=anchor_units(R, whole),
                   bundling=rule)


def _enteroscopy_session(held: HeldFact, R: FactSet, session: Id | None) -> Id | None:
    """The session an enteroscopy class item is about: the hold's own session; for a hold about the anatomy entry the
    session went through, the session whose supported ``through`` names it; else the session of the act the item
    names."""
    own = _session_of(held)
    if own is not None:
        return own
    if held.subject is not None and held.subject.family is IdFamily.ANATOMY:
        named = next((found for found in R.sessions if facts_.holds(facts_.fact(R, found, _A.THROUGH), held.subject)),
                     None)
        if named is not None:
            return named
    return session


def _class_reach(R: FactSet, session: Id,
                 exam_class: catalogue.EnteroscopyClass) -> tuple[Extent, tuple[Span, ...]] | None:
    """The reached point an enteroscopy class item names (refute-r4a-r1 P3: the reach the class rule read, never merely
    the session's first): a supported point beyond the class (classes.BEYOND: the point past the jejunal class that
    makes its REACH part F - "reached the ileum" for 44360 beside [jejunum, ileum]), else a supported point in the
    class's own reach (catalogue.ENTEROSCOPY_CLASS_REACH: the reach that fits, beside another part's misfit), else the
    first supported point (one another class's reach, or no class's, holds) - each in pass 1's order: its value and
    its own spans. None when no reached point is supported: no class sentence can then be true (``item``)."""
    points = [(member.value, tuple(sorted(set(member.spans)))) for member in facts_.members(R, session, _A.REACHED)
              if member.result is Result.SUPPORTED and isinstance(member.value, Extent)]
    beyond = classes.BEYOND.get(exam_class, frozenset())
    within = catalogue.ENTEROSCOPY_CLASS_REACH.get(exam_class, frozenset())
    for wanted in (beyond, within):
        found = next((point for point in points if point[0] in wanted), None)
        if found is not None:
            return found
    return points[0] if points else None


def digital_examination(R: FactSet, event: Id) -> bool:
    """FINAL 5.6 E13's digital examination (DECISIONS D69; D227: combination.session_done excepts it - "a digital
    examination ... is no session"; D253, QE13 option (a)): an event whose device CLAIMS manual - supported manual, or,
    not established, manual its claimed value or one of its readings (facts.possibly over a device that is not silent).
    Read so that 9.4's weakenings never turn a digital examination into the session's own (each keeps the claimed value:
    an established manual device weakened still claims it; refute-r4a-r1 P1). A silent device (the endoscopic
    examination's usual filing: "The colonoscope was advanced to the cecum."), one established as another device, and
    manual negated claim none. The one derivation, engine/pairing.digital_examination (the module lowest in the engine's
    imports; DECISIONS D265: an examination statement never pairs with it as with the session's examination):
    engine/evaluate.py's rows 1 and 7 (``_digital_row``, ``act_only`` and ``done``) and its binding read it, and so do
    the examination an item quotes (``_session_examination``, ``_quotable``) and the item that would name it
    (``fill``, ``_session_named``)."""
    return pairing.digital_examination(R, event)


def _session_examination(R: FactSet, session: Id) -> Id | None:
    """A session's own examination, as an item quotes it: the first event established as its examination (kind supported
    examination, session supported ``session``), a digital examination excepted (``digital_examination``: E13's is no
    session's examination, D253); None for none (an act-only session)."""
    return next((event for event in R.events if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(facts_.fact(R, event, _A.SESSION), session)
                 and not digital_examination(R, event)), None)


def _examination_words(R: FactSet, session: Id) -> tuple[Span, ...]:
    """The enteroscopy's own statement, quoted where a fact an enteroscopy class item names cites no words of its own:
    the anchor units of the session's own examination (``_session_examination``: the first event established as its
    examination, never a digital one); () for none. A settled supported fact always carries its sources' units
    (engine/facts.py builds its spans from the stored claim's sources, and settle demotes a source whose units are
    unknown: 3.1 I1), so this is read only for hand-built FactSets - never the anchor of the act the item names (an act
    code's own sentence is no statement of the enteroscopy's reach or route: refute-r4a-r1 P3)."""
    return anchor_units(R, _session_examination(R, session))


def _enteroscopy_fill(base: Fill, held: HeldFact, code: CodeFacts, R: FactSet, message: MessageId,
                      session: Id | None) -> Fill:
    """What the enteroscopy class items name (D246; step 4c's classes.py raises their holds): the code's class
    (``enteroscopy_class``, catalogue.code_class), the reach the class rule read (``_class_reach``: refute-r4a-r1 P3)
    and that reach's own words (v1's class_hold quoted the extent's words; the enteroscopy's own statement when the
    reach cites none, ``_examination_words``); ENTEROSCOPY_APPROACH the session's supported approach and its words (its
    own sources, else the enteroscopy's own statement: refute-r4a-r1 P4) - an approach not supported (denied, or not
    established: refute-r4a-r2 A1) none, so wording gives the class form naming no route (D254 rule 3) -, and
    ENTEROSCOPY_THROUGH (the route part whose only unknown is the anatomy passed through, D253 QX (ii)) the same;
    ENTEROSCOPY_CLASS the incomplete form when
    classes.misfit_form gives it (only a deeper part keeps the class from fitting, its own claim stating the stopping
    short: v1's "stated to be incomplete"); ENTEROSCOPY_ROUTE the incomplete form when a deeper part states it, the
    routes the anatomy the session went through establishes (``approaches``: classes.routes, v1's "through the
    documented stoma", refute-r4a-r1 P11), and those it only possibly opens (``possible_approaches``: classes.
    doubted_routes - a doubted or unresolved through, or an entry whose type is not established - repair r3c of round
    w9r's possible-route marker, worded as possible, never "the documented pouch" or "the documented stoma": DECISIONS
    D267, refute-r4a-r2 F5). With no reached point supported, ``reached`` stays None."""
    exam_class = catalogue.code_class(code.code)
    where = _enteroscopy_session(held, R, session)
    if exam_class is None or where is None:
        return replace(base, enteroscopy_class=exam_class)
    point = _class_reach(R, where, exam_class)
    statement = _examination_words(R, where)
    found = replace(base, enteroscopy_class=exam_class, reached=point[0] if point is not None else None,
                    words=(point[1] if point is not None else ()) or statement)
    if message in (MessageId.ENTEROSCOPY_APPROACH, MessageId.ENTEROSCOPY_THROUGH):
        approach = facts_.fact(R, where, _A.APPROACH)
        value = approach.value if approach.result is Result.SUPPORTED and isinstance(approach.value, Approach) \
            else None
        words = (tuple(sorted(set(approach.spans))) or statement) if value is not None else ()
        return replace(found, approach=value, approach_words=words)
    if message is MessageId.ENTEROSCOPY_CLASS:
        return replace(found, incomplete=classes.misfit_form(code.code, where, R) is classes.ClassForm.INCOMPLETE)
    stated = any(part.part in classes.DEEPER_PARTS and part.truth is not classes.Truth.T and part.stated
                 for part in classes.class_fit(exam_class, where, R).parts)
    opened, possible = classes.routes(where, R), classes.doubted_routes(where, R)
    return replace(found, incomplete=stated, approaches=tuple(way for way in Approach if way in opened),
                   possible_approaches=tuple(way for way in Approach if way in possible))


def _specific(base: Fill, held: HeldFact, code: CodeFacts, R: FactSet, message: MessageId, event: Id | None,
              session: Id | None, raised: Raised, acts: Sequence[Id] = ()) -> Fill:
    """The slots D225's and D246's ids need (wording's builders refuse slots that contradict them), set on the base Fill:
    - UNLISTED_EVIDENCE (P11): the entry's nature and kind, its own units the one statement - never the code's act;
    - SAME_DUCT (P6): the act whose duct is not established and its counterpart, each its words (a kept unlisted act
      its own units, and no device or place) and its kind, an act no kind names as Kind.OTHER (D254 rule 2,
      ``_side_slot``);
    - a synthetic act's DOUBT or SYNTHETIC_ACT (D216, D246): the unlisted act's or doubt's own kind (an entry of no kind
      named as an act), its own units, nothing of the code's act; an examination by its session's service only when the
      entry's card names the session the hold is about (D232), else "the examination";
    - DOUBT for 3.2.6 rule 4's pair of an unlisted doubt or denial with an act, carded or not: the entry's nature
      (``unlisted_what``: D266, so a denial is worded as a statement that the act was not done, never "leaves ... in
      doubt"; a synthetic act's doubt likewise); with a session's examination (D232) the examination by its service
      when the entry's card names the session it is established in - quoting its words only when it may be quoted, a
      digital examination never and one of another occasion never (``_session_named``: D265, D266) -; else (a doubt
      carded to another session the FactSet holds) the doubt named by itself (its own kind, its own unit, no session),
      never that examination "left in doubt";
    - UNLISTED_SCOPE (D258): a statement that names no procedure session - a doubt or a denial with no card, or one
      naming a session the FactSet does not hold - held against a session's examination (``_scope_entry``): that
      examination by its session's service, its own words, and the statement quoted (``_scope_fill``);
    - CONFLICT_ATTRIBUTE (P7): the attribute; a session's fact names its examination;
    - EXAMINATION_ROUTE and EXAMINATION_APPROACH (P5): the session's supported approach and its words, and through a
      stoma when an anatomy entry of type stoma is supported;
    - STRUCTURE_PLACE (P10): the place the rule read;
    - PART, BUNDLING_TARGET and BUNDLED (D246): the bundle's part, whole and rule (``_bundling_fill``);
    - ENTEROSCOPY_APPROACH, ENTEROSCOPY_CLASS, ENTEROSCOPY_ROUTE (D246) and ENTEROSCOPY_THROUGH (D253 QX (ii)): the
      code's class, the session's approach and the incomplete form (``_enteroscopy_fill``);
    - BASE_WITHIN (D257): the whole's own family and whether it is only possibly done (``_whole_family``).
    Every act slot names an act no kind names as Kind.OTHER (D254 rule 2): the act and the whole (``_act_slot``), the
    unlisted entry's kind, a synthetic entry's (``_own_entry``), XCHG's two acts (``_side_slot``)."""
    if message is MessageId.UNLISTED_EVIDENCE:
        entry = raised.evidence[held]
        kind = entry.kind if entry.kind is not None else Kind.OTHER  # D254 rule 2
        return replace(base, unlisted_what=entry.what, unlisted_kind=kind,
                       statements=(tuple(sorted(set(entry.units))),))
    if message is MessageId.UNLISTED_SCOPE:
        return _scope_fill(base, held, code, R, event, session, raised)
    if message is MessageId.BASE_WITHIN:  # D257: the whole by its own family; a question's whole only possibly done
        return replace(base, whole_family=_whole_family(R, _session_of(held)), whole_possible=held.kind is _Q)
    if message is MessageId.SAME_DUCT:
        exchange = raised.exchanges[held]
        unknown = exchange.unknown.event
        device = _supported(facts_.fact(R, unknown, _A.TECHNIQUE_DEVICE)) if unknown is not None else None
        return replace(base, act=_side_slot(R, exchange.unknown), words=exchange.unknown.spans,
                       whole=_side_slot(R, exchange.known),
                       whole_words=exchange.known.spans, device=device if isinstance(device, Device) else None,
                       place=_first_place(R, unknown, _A.TARGET_PLACES) if unknown is not None else None,
                       statements=())
    synthetic = synthetic_entry(held, R, raised) if message in (MessageId.DOUBT, MessageId.SYNTHETIC_ACT) else None
    if synthetic is not None:
        where = _session_of(held) or synthetic.session
        named = _own_entry(base, synthetic)
        if message is MessageId.DOUBT:  # D266: the entry's nature, as for every unlisted entry DOUBT words
            named = replace(named, unlisted_what=synthetic.what)
        if synthetic.kind is Kind.EXAMINATION and _names_session(synthetic, where, R):  # D232: its card names it
            return replace(named, family=_family_of(R, where, code))
        return named
    pair = _unlisted_pair(held, R, event) if message is MessageId.DOUBT and held.cause == UNLISTED else None
    if pair is not None and event is not None:  # 3.2.6 rule 4's pair (row 8): its entry's nature, carded or not (D266)
        what = pair.statement.what
        if base.act is Kind.EXAMINATION:  # with a session's examination
            if what is UnlistedWhat.DOUBT and not _names_sessions_examination(pair.statement, event, R):
                return replace(_own_entry(base, pair.statement), unlisted_what=what)  # D232: never "left in doubt"
            return replace(_session_named(base, R, event, session), unlisted_what=what)  # D265, D266: quoted only
        return replace(base, unlisted_what=what)
    if message in _BUNDLING_ITEMS:
        return _bundling_fill(base, held, code, R, message, acts)
    if message in _ENTEROSCOPY_FILLED:
        return _enteroscopy_fill(base, held, code, R, message, session)
    if message is MessageId.CONFLICT_ATTRIBUTE:
        about = _session_of(held)
        if about is not None:
            return replace(base, attribute=held.attribute, act=Kind.EXAMINATION, family=_family_of(R, about, code),
                           device=None, place=None)
        return replace(base, attribute=held.attribute, act=_conflict_kind(held, base))
    if message in (MessageId.CONFLICT, MessageId.CONFLICT_FACT):
        return replace(base, act=_conflict_kind(held, base))
    if message in (MessageId.EXAMINATION_ROUTE, MessageId.EXAMINATION_APPROACH):
        where = _session_of(held) or session
        approach = facts_.fact(R, where, _A.APPROACH) if where is not None else facts_.SILENT
        value = approach.value if approach.result is Result.SUPPORTED and isinstance(approach.value, Approach) \
            else None
        stoma = any(facts_.holds(facts_.fact(R, entry, _A.TYPE), AnatomyType.STOMA) for entry in R.anatomy)
        return replace(base, approach=value, approach_words=tuple(sorted(set(approach.spans))) if value else (),
                       approaches=(Approach.THROUGH_STOMA,) if stoma else ())
    if message is MessageId.STRUCTURE_PLACE:
        return replace(base, place=_apart_place(R, event) or base.place)
    return base


def _refined(held: HeldFact, message: MessageId, raised: Raised, R: FactSet) -> MessageId:
    """message_of's id, refined by what evaluate.py raised (D225, D246): 3.2.6 rule 2's hold is worded as its unlisted
    entry (UNLISTED_EVIDENCE, P11); XCHG's duct question in the two-act form naming the act whose duct is unknown
    (SAME_DUCT, P6); a synthetic act's doubt about a kept unlisted ACT - 3.2.6 rule 3's synthetic act, an act the
    document states that CPT Studio's reading does not account for - as SYNTHETIC_ACT (D246, r4a R4 (a): DOUBT's
    "leaves ... in doubt" is untrue of it), the same fact key, kind and rank as DOUBT's; a statement that names no
    procedure session - a doubt or a denial with no card, or a card naming a session the FactSet does not hold - held
    against a session's examination as UNLISTED_SCOPE (D258, ``_scope_entry``: the held session's examination asked,
    never the statement), the same fact key, kind and rank again; any other kept unlisted DOUBT stays DOUBT, whose
    sentence is true of it."""
    if held in raised.evidence:
        return MessageId.UNLISTED_EVIDENCE
    if message is MessageId.DUCT and held in raised.exchanges:
        return MessageId.SAME_DUCT
    if message is MessageId.DOUBT:
        entry = synthetic_entry(held, R, raised)
        if entry is not None and entry.what is UnlistedWhat.ACT:
            return MessageId.SYNTHETIC_ACT
        if _scope_entry(held, R, raised) is not None:
            return MessageId.UNLISTED_SCOPE
    return message


def _unnamed_reach(message: MessageId, filled: Fill) -> bool:
    """An enteroscopy class item whose session has no supported reached point (``_enteroscopy_fill``: ``reached``
    None): ENTEROSCOPY_APPROACH, ENTEROSCOPY_CLASS or ENTEROSCOPY_ROUTE with no reach to name. Repair r3c of round w8r
    words those forms with no reach (r4a's R4), so the item is worded either way; ``item`` keeps the installed reading
    there (the reach's own question first, DECISIONS D253 A3)."""
    return message in _ENTEROSCOPY_ITEMS and filled.reached is None


def item(held_facts: Sequence[HeldFact], groups: Sequence[Group], code: CodeFacts, R: FactSet,
         acts: Sequence[Id] = (), raised: Raised | None = None) -> Item | None:
    """The ONE item of a held code (4.8, D182): ``select``'s held fact, its message id and its Fill (``acts``: the code's
    supporting acts, which name a hold about their session; ``raised``: what evaluate.py knows of the holds it raised).
    None when nothing is held. A contradicted fact whose sides cannot be told apart (fewer than two statements) is
    worded as a conflict about its attribute (CONFLICT_ATTRIBUTE, P7: one sentence quoted once, never "performed and
    not performed"); with no attribute named, in the relation's conflict form, which quotes one.

    One exception to ``select``'s choice (the installed reading, D216's order): an enteroscopy class item whose session
    has no supported reached point (``_unnamed_reach``) - an approach established as another route beside a reach not
    established, "Enteroscopy through the ileostomy; the extent could not be determined." for 44360 - names no reach.
    The item is then the next held fact on the binding in 4.8's order - the reach's own question (classes' REACH part
    when it is U, or R6's extent question) - as v1's class_misfit gave no class hold while the reach was not verified
    and R6 asked the missing extent. The class hold stays in ``held_facts``; the code is held either way. When every
    held fact on the binding is such an item - the class reach denied whole with no reached point supported and R6 met
    by a completion stated incomplete ("The ileum was not reached; the examination was incomplete." for 44376; and a
    pouchoscopy whose route and approach explanations, PROCEDURE-keyed, rank before it: refute-r4a-r2 A3, D253) - the
    item is classes' REACH part's explanation worded as the extent question (MessageId.EXTENT, its question kind beside
    the explanation it rests on): v1's class_hold EXTENT form, which classes.misfit_form gives there ("a reach no
    class's reach fits": R6's extent question). r4a-2's NOTES, question QR and deviation DV2; repair r3c of round w8r
    words the class forms with no reach named (r4a's R4), so the exception is the installed reading, no longer a
    refusal's guard."""
    raised = raised if raised is not None else Raised()
    found = ranked(on_binding(held_facts, groups), R)
    if not found:
        return None
    tried: list[tuple[HeldFact, MessageId, Fill]] = []
    for held in found:
        message = _refined(held, message_of(held, code), raised, R)
        filled = fill(held, groups, code, R, message, acts, raised)
        tried.append((held, message, filled))
        if not _unnamed_reach(message, filled):
            break
    else:  # every held fact an enteroscopy class item with no reach (QR's residual): the reach's own (v1's EXTENT form)
        reach = next((entry for entry in tried if fact_of(entry[0])[0] is rq.FactKey.EXTENT), tried[0])
        held, message, filled = reach
        if fact_of(held)[0] is rq.FactKey.EXTENT:
            message = MessageId.EXTENT
            filled = fill(held, groups, code, R, message, acts, raised)
    if message is MessageId.CONFLICT_FACT and len(filled.statements) < 2:
        if held.attribute is not None:
            message = MessageId.CONFLICT_ATTRIBUTE
            filled = fill(held, groups, code, R, message, acts, raised)
        else:
            message = MessageId.CONFLICT
            if not filled.statements:
                filled = replace(filled, statements=(held.spans,) if held.spans else ())
    return Item(held=held, message=message, fill=filled)
