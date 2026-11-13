"""The one-question policy (docs/gemini-migration/FINAL-V2.md 4.8, 4.4; DECISIONS D182, D189; step 4a of 8.1): RANK
applied to a held code's witnesses, the binding (which act the item names), the ONE item - a question or an explanation -
and its message id, over the HeldFacts engine/evaluate.py records. Text-free: it reads ranks, kinds, ids and integer
spans, and the item names a message id and the text-free slots CPT Studio's fixed sentence is built from; the revision
text is sliced by the caller (wording.build) after the decision, never here.

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
is asked only when no kept span selects the other act.

**Causes** (4.4 [R:MO-2]; ``cause_of``): reading_unknown (silent or doubted), reading_contradicted,
appraisal:<verdict or coherence> for an appraisal reason (3.3 row 9), unestablished:<reason> for any other reason of an
unresolved fact (unestablished when it carries none), coding_rule:<id> for an established fact failing a coding rule
(``coding_rule``), relation:<type> (engine/pairing.py's), unlisted, context_missing, date_unknown. Operator data: no
vendor is named, and no customer string carries one. step 4c asked for this one derivation (its request R2).

**Message ids** (``MessageId``; step 3c's wording.Message, mirrored value for value): the engine cannot import
studio/interpretation/wording.py - it imports studio.gi and is no ``mypy --strict`` module (5.7 measure 5) - so the ids
are restated here as an Enum whose every member equals wording.Message's by name and value (tests/v2/test_questions.py
pins it, and pins each id's fact key, kind and rank against wording.MESSAGES), and ``Fill`` mirrors wording.Slots field
for field. The caller builds the sentence: ``wording.build(wording.Message(item.message.value), slots, revision_text)``
with ``slots = wording.Slots(**{name: getattr(item.fill, name) for each Fill field})``, its ``bundling`` turned into
wording.Bundling by value (never dataclasses.asdict, which would turn the Span records into dicts; tests/v2/
test_questions.slots does it).

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, facts, pairing, requirements and types only - no retired v1 module,
none of contract's text modules, not wording - holds no word, phrase or marker list (every module-level collection holds
enumeration members, or is computed from them), reads no text and returns no document string (a cause and a fact key are
CPT Studio's codes). ``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import (Approach, Attribute, Device, Extent, Kind, Landmark, Owner, Purpose,
                                                  Qualifier2, Reason, Result, SessionKind, Station, Tract, VerdictValue)
from studio.interpretation.engine import catalogue, pairing
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span

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


def message_of(held: HeldFact, code: CodeFacts) -> MessageId:
    """The message id that words ``held`` (4.8; step 3c's MESSAGES): chosen by its fact key, its kind and, where one
    fact has several sentences, by the coding rule its cause names - a relation's conflict quotes both statements, a
    contradicted fact its sides; a rank-2 performed_status is a doubt, a rank-4 one a status question, not-documented,
    or the explanation of C-9, route (d), D80 or route (b); the technique by the code's class (TECH), the act's statement
    of a device (the pairing's technique row) or the EUS route (ROUTE); act_target by the site class (SITE), the duct
    (XCHG) or the act's place (route (b)); target by 43240's structure; procedure's explanation by the tract (TRACT).
    Every id it returns has the held fact's fact key, kind and rank in wording.MESSAGES (tested)."""
    key, _ = fact_of(held)
    rule = _rule_of(held)
    relation = held.cause in RELATION_CAUSES
    if key is rq.FactKey.CONFLICT:
        return MessageId.CONFLICT if relation else MessageId.CONFLICT_FACT
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
    """The kind an item names an act by: the catalogue kind of its claimed kind with its supported purpose (a clip or an
    injection for hemostasis is a bleeding control, catalogue.catalogue_kind), else its claimed kind; for no act, or an
    act whose kind names nothing (silent, contradicted, other), the first kind of the code's group."""
    if event is not None:
        claimed = facts_.fact(R, event, _A.KIND).value
        if isinstance(claimed, Kind):
            purpose = _supported(facts_.fact(R, event, _A.PURPOSE))
            named = catalogue.catalogue_kind(claimed, purpose if isinstance(purpose, Purpose) else None)
            if named is not None:
                return named
    return group[0] if group else None


def _event(subject: Id | None) -> Id | None:
    return subject if subject is not None and subject.family is IdFamily.EVENT else None


def _unlisted_units(held: HeldFact, R: FactSet, act: Id | None) -> tuple[Span, ...]:
    """The units of the unlisted entry an unlisted hold quotes: the entry of the act's unlisted pair whose spans the
    held fact records (3.2.6 rule 4: the entry's units and the act's anchor), else the held fact's spans that are not
    the act's anchor, else every span it records (3.2.6 rule 2's hold records the entry's units alone). An entry found
    in the act's own sentence is quoted too: the act's anchor is then the entry's unit (the refutation's F2)."""
    if act is not None:
        for pair in pairing.unlisted_pairs(R, act):
            if pair.spans == held.spans:
                return tuple(sorted(set(pair.statement.units)))
    own = anchor_units(R, act)
    return tuple(span for span in held.spans if span not in own) or held.spans


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
         acts: Sequence[Id] = ()) -> Fill:
    """The Fill of ``held``'s item (module docstring): the code and its row's parameters; the act the hold names (its
    kind as the item names it, its supported device, its first supported place, its anchor as its words; the code's
    group for a code-level hold); the statements it quotes; and, for the explanations that name an established value,
    that value (the entry's owner, the session's tract and stations, the act's technique class, the outside place)."""
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
    return Fill(code=code.code, act=act_kind(R, event, code.group), reached=reached,
                bundling=_bundling(R, event, _rule_of(held)),
                device=device if isinstance(device, Device) else None, place=place, words=words,
                statements=named.statements, group=code.group, family=code.family, technique=code.technique,
                stated=stated, site=code.site, exam_class=code.exam_class,
                owner=owner if isinstance(owner, Owner) else None, stations=stations, denied=denied,
                tract=tract if isinstance(tract, Tract) else None, required_tract=code.tract)


def item(held_facts: Sequence[HeldFact], groups: Sequence[Group], code: CodeFacts, R: FactSet,
         acts: Sequence[Id] = ()) -> Item | None:
    """The ONE item of a held code (4.8, D182): ``select``'s held fact, its message id and its Fill (``acts``: the code's
    supporting acts, which name a hold about their session). None when nothing is held. A contradicted fact whose sides
    cannot be told apart (fewer than two statements) is worded in the relation's conflict form, which quotes one."""
    held = select(held_facts, groups, R)
    if held is None:
        return None
    message = message_of(held, code)
    filled = fill(held, groups, code, R, message, acts)
    if message is MessageId.CONFLICT_FACT and len(filled.statements) < 2:
        message = MessageId.CONFLICT
        if not filled.statements:
            filled = replace(filled, statements=(held.spans,) if held.spans else ())
    return Item(held=held, message=message, fill=filled)
