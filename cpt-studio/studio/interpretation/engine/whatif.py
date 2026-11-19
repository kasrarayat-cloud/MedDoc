"""Round r3's what-if (docs/gemini-migration DECISIONS D306-D308, D320; build-v2/a2b/r3/design/DESIGN-v2.md a.3): the
codes a document could be coded with, and for every positive candidate of each, the witnesses it would carry if the
code's own rows were read on it - the question planner's input (engine/asking.py). Built in round r3's build on int3
from the probe prototype (build-v2/a2b/r3/probe, PROBE-v2 section 2).

``candidate_codes(R)``: every catalogue code (engine/catalogue.CODES, plus route (b)'s 46221) with a requirement group
for which some event is a POSITIVE candidate (evaluate.candidates: possibly of a kind of the group, status not denied
performed; evaluate.positive: possibly performed or begun, neither another date nor another performer established),
where the code's family is one the candidate's session may be (any session it may be in, each of any family its kind
fact leaves possible; every family when no session is held) - which includes each possible session's base and
examination-only codes (their group is the examination) and the office E/M codes when a visit exists (their group is
the visit). Ordered by code. Proposals do not exist at question time (APPRAISE runs before PREDICT), so candidate codes
stand for them.

``witnesses(R, code)``: one Candidate per (group, positive candidate E): every witness of SUPPORT on E
(evaluate.support: rows 1-8, the E/M encounter, the filter rows), of the code-specific rows on E (evaluate.code_rows),
of R6 over E alone (assess.r6_rows with no member context: the member's context row is A2, never asked), of the
enteroscopy class (classes.enteroscopy_hold over (E,)) and of the bundling (coverage.bundling over (E,)) - every row,
whether or not decide would read it (decide reads the code rows only over supporting acts, so a candidate a relation
holds never shows them; the what-if shows them, so a released relation is never followed by a hidden row the plan did
not ask). A relation witness carries the pairing Pair behind it (pairing.pairs_of over E: same cause, same spans), an
unlisted witness the UnlistedPair (pairing.unlisted_pairs), so the planner names the statement - both read from the
FactSet's ONE coverage Reader and indexed once per candidate (``_EventPairs``; DECISIONS D324 (8): an act's pairs are
computed once per Reader, never once per witness). Never evaluated here:
the ADDON row and the combination rows (base_included, base_within, competing_codes, same_day_em), which read the
COUNTED set (the proposals); they apply at assess over the real proposals, as today. Text-free and pure.

FINAL-V2 5.7 measure 4 (DECISIONS D323, the port's F3): a held fact's cause is CPT Studio's own label, built by the
engine from its enumerations (engine/questions.cause_of and coding_rule, pairing.cause, coverage, combination); it is
READ here through the typed ``Cause`` (``cause_of``: one lookup in a table built from those same enumerations by the
engine's own builders), never by a word test - no comparison with a string, no prefix or split. A label no row of the
table names reads as ``CauseFamily.OTHER``, which the planner blocks (fail-closed). A witness's row family is the
typed ``WitnessSource``, and the member-context row of R6 is read by its requirement through the Enum
(requirements_table.Tag): ``_tag_of``."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import Attribute, Kind, Reason, Result, SessionKind
from studio.interpretation.engine import catalogue, classes, combination, coverage, evaluate, pairing, questions
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, Span, UnlistedStatement

_A = Attribute
ROUTE_B_CODES: tuple[int, ...] = tuple(sorted(catalogue.UNRECONCILED_ACTS))


# --- the cause a witness carries, read typed (FINAL-V2 4.4; 5.7 measure 4) -----------------------------------------------

@unique
class CauseFamily(Enum):
    """What a held fact's cause names (FINAL-V2 4.4: reading_unknown, reading_contradicted, unestablished[:<reason>],
    appraisal:<verdict or coherence>, relation:<type>, unlisted, coding_rule:<id>, context_missing, date_unknown).
    OTHER: a label no row of the table names - read fail-closed (the planner blocks its witness)."""
    READING_UNKNOWN = 'reading_unknown'
    READING_CONTRADICTED = 'reading_contradicted'
    UNESTABLISHED = 'unestablished'
    APPRAISAL = 'appraisal'
    RELATION = 'relation'
    UNLISTED = 'unlisted'
    CODING_RULE = 'coding_rule'
    CONTEXT_MISSING = 'context_missing'
    DATE_UNKNOWN = 'date_unknown'
    OTHER = 'other'


@dataclass(frozen=True, slots=True)
class Cause:
    """A held fact's cause, typed: ``family``; ``reason`` (an unestablished:<reason> cause's Reason; None for the bare
    ``unestablished``); ``verdict`` (an appraisal cause's verdict or coherence, engine/questions.APPRAISAL_CAUSES'
    value); ``relation`` (a relation:<type> cause's pairing.Relation; None for relation:possible_statement, which sets
    ``possible_statement``); ``rule`` (a coding_rule:<id> cause's member - engine/questions.Rule,
    requirements_table.Tag or coverage.Rule - None for an id that is no member of them) and ``label`` (the coding rule's
    id as the cause writes it, for a census reason's words: never compared)."""
    family: CauseFamily
    reason: Reason | None = None
    verdict: Enum | None = None
    relation: pairing.Relation | None = None
    possible_statement: bool = False
    rule: Enum | None = None
    label: str = ''


def _cause_table() -> Mapping[str, Cause]:
    """Every cause label the engine builds -> its typed Cause, each label made by the engine's OWN builders from its own
    enumerations (questions.cause_of over a fact of every Reason; questions.coding_rule of every Rule and Tag;
    pairing's relation:<type> of every Relation; coverage's and combination's coding rules), so a label and its reading
    cannot drift. A label two rows would read differently is a defect of the tables: RuntimeError at import."""
    table: dict[str, Cause] = {}

    def add(label: str, found: Cause) -> None:
        if table.get(label, found) != found:
            raise RuntimeError(f'the cause label {label!r} reads two ways ({table[label]} / {found})')
        table[label] = found

    add(questions.READING_UNKNOWN, Cause(CauseFamily.READING_UNKNOWN))
    add(questions.READING_CONTRADICTED, Cause(CauseFamily.READING_CONTRADICTED))
    add(questions.UNESTABLISHED, Cause(CauseFamily.UNESTABLISHED))
    add(questions.UNLISTED, Cause(CauseFamily.UNLISTED))
    add(questions.CONTEXT_MISSING, Cause(CauseFamily.CONTEXT_MISSING))
    add(questions.DATE_UNKNOWN, Cause(CauseFamily.DATE_UNKNOWN))
    for reason in Reason:  # every unestablished and appraisal cause, by questions.cause_of itself
        made = questions.cause_of(Fact(result=Result.UNRESOLVED, value=None, state=None, options=(), reasons=(reason,),
                                       spans=()))
        verdict = questions.APPRAISAL_CAUSES.get(reason)
        add(made, Cause(CauseFamily.APPRAISAL, verdict=verdict) if verdict is not None
            else Cause(CauseFamily.UNESTABLISHED, reason=reason))
    add(questions.POSSIBLE_STATEMENT, Cause(CauseFamily.RELATION, possible_statement=True))
    for relation in pairing.Relation:  # pairing.cause's relation:<type> (questions.RELATION_CAUSES names the same)
        add(f'{CauseFamily.RELATION.value}:{relation.value}', Cause(CauseFamily.RELATION, relation=relation))
    rules: list[Enum] = [*questions.Rule, *Tag, *coverage.Rule]
    for rule in rules:  # questions' rules first: a coverage rule whose id one of them has reads as that one
        label = f'{CauseFamily.CODING_RULE.value}:{rule.value}'
        if table.get(label) is None:
            add(label, Cause(CauseFamily.CODING_RULE, rule=rule, label=str(rule.value)))
    # coding rules the engine names by its own constants (no member of the three Enums): coverage's own support and
    # read-under rules, combination's rows, and the fact keys coverage passes as a rule (its extent and conflict rows)
    named = [coverage.ACT_SUPPORT, coverage.READ_UNDER_RULE, *(key.value for key in rq.FactKey)]
    for label in (*(f'{CauseFamily.CODING_RULE.value}:{name}' for name in named), combination.BASE_CAUSE,
                  combination.WITHIN_CAUSE, combination.COMPETING_CAUSE, combination.SAME_DAY_CAUSE,
                  classes.CLASS_CAUSE, classes.ELSEWHERE_CAUSE):
        if table.get(label) is None:
            add(label, Cause(CauseFamily.CODING_RULE, label=label[len(CauseFamily.CODING_RULE.value) + 1:]))
    missing = [label for label in questions.RELATION_CAUSES if table.get(label) is None]
    if missing or table.get(questions.ADDON_CAUSE) is None:
        raise RuntimeError(f'the cause table does not read the engine\'s own causes: {missing}')
    return MappingProxyType(table)


CAUSES: Mapping[str, Cause] = _cause_table()
_OTHER = Cause(CauseFamily.OTHER)


def cause_of(held: HeldFact) -> Cause:
    """``held``'s cause, typed (CAUSES); CauseFamily.OTHER for a label the table does not name."""
    return CAUSES.get(held.cause, _OTHER)


@unique
class WitnessSource(StrEnum):
    """The row family that raised a witness (module docstring): support, a code-specific row, R6, the enteroscopy class,
    the bundling. A StrEnum: its value is the word a record stores."""
    SUPPORT = 'support'
    CODE_ROW = 'code_row'
    R6 = 'r6'
    CLASS = 'class'
    BUNDLING = 'bundling'


@dataclass(frozen=True, slots=True)
class Witness:
    """One witness of a candidate: the HeldFact; ``source`` the row family that raised it (WitnessSource; a plain value
    is read into it); ``pairs`` the pairing Pairs behind a relation witness (each statement against the candidate);
    ``unlisted`` the UnlistedPairs behind an unlisted witness of row 8; ``entries`` the kept unlisted entries a synthetic
    witness or a rule-2 witness rests on."""
    held: HeldFact
    source: WitnessSource
    pairs: tuple[pairing.Pair, ...] = ()
    unlisted: tuple[pairing.UnlistedPair, ...] = ()
    entries: tuple[UnlistedStatement, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, 'source', WitnessSource(self.source))


@dataclass(frozen=True, slots=True)
class Candidate:
    """One positive candidate E of one group of ``code``, with every witness it would carry (module docstring)."""
    code: str
    group: tuple[Kind, ...]
    event: Id
    witnesses: tuple[Witness, ...]


def _families_of(R: FactSet, event: Id) -> frozenset[SessionKind]:
    """The families ``event``'s session may be: for each session it may be in (facts.possibly on its session fact;
    every session when the fact is silent or names one the FactSet does not hold), each family that session's kind
    leaves possible (supported: its value; otherwise facts.possibly's). Every family when the FactSet holds no session."""
    if not R.sessions:
        return frozenset(SessionKind)
    found = facts_.fact(R, event, _A.SESSION)
    sessions = [session for session in R.sessions if facts_.possibly(found, session)]
    if not sessions or facts_.silent(found):
        sessions = list(R.sessions)
    out: set[SessionKind] = set()
    for session in sessions:
        kind = facts_.fact(R, session, _A.KIND)
        if kind.result is Result.SUPPORTED and isinstance(kind.value, SessionKind):
            out.add(kind.value)
        else:
            out.update(family for family in SessionKind if facts_.possibly(kind, family))
    return frozenset(out)


def _positive_candidates(R: FactSet, group: Sequence[Kind]) -> tuple[Id, ...]:
    return tuple(event for event in evaluate.candidates(R, group) if evaluate.positive(R, event))


def candidate_codes(R: FactSet) -> tuple[str, ...]:
    """Every candidate code of ``R`` (module docstring), ordered by code."""
    out: set[int] = set()
    for number in (*catalogue.CODES, *ROUTE_B_CODES):
        link = catalogue.code_link(str(number))
        groups = catalogue.requirements(link)
        if not link.linked or not groups:
            continue
        family = link.family
        for group in groups:
            if any(family is None or family in _families_of(R, event) for event in _positive_candidates(R, group)):
                out.add(number)
                break
    return tuple(str(number) for number in sorted(out))


class _EventPairs:
    """One candidate's pairs (DECISIONS D324 (8), the plan's cost): the pairs behind its relation witnesses read from the
    FactSet's ONE Reader (pairing.pairs_of over the event, computed once per Reader, never once per witness) and indexed
    once by the witness they stand behind - a pair's cause (pairing.cause) and its anchor spans - so a relation
    witness's pairs are a lookup, never a scan of every pair of the act per witness (statements x statements per
    candidate). Each witness's pairs keep the Reader's order: exactly the pairs ``_relation_pairs`` read before."""
    __slots__ = ('reader', 'event', '_by')

    def __init__(self, reader: coverage.Reader, event: Id) -> None:
        self.reader = reader
        self.event = event
        self._by: dict[tuple[str | None, tuple[Span, ...]], tuple[pairing.Pair, ...]] | None = None

    def relation(self, held: HeldFact) -> tuple[pairing.Pair, ...]:
        """The pairs behind a relation witness of the event (its cause relation:<type>): every pair of the act whose
        cause and anchor spans are the witness's."""
        if self._by is None:
            by: dict[tuple[str | None, tuple[Span, ...]], list[pairing.Pair]] = {}
            for pair in self.reader.pairs(self.event):
                by.setdefault((pairing.cause(pair), pair.spans), []).append(pair)
            self._by = {key: tuple(found) for key, found in by.items()}
        return self._by.get((held.cause, held.spans), ())

    def unlisted(self, held: HeldFact) -> tuple[pairing.UnlistedPair, ...]:
        return tuple(pair for pair in self.reader.unlisted_pairs(self.event) if pair.spans == held.spans)


def _entries(R: FactSet, held: HeldFact) -> tuple[UnlistedStatement, ...]:
    """The kept unlisted entries whose units are exactly a synthetic or rule-2 witness's spans."""
    return tuple(entry for entry in R.unlisted if tuple(sorted(set(entry.units))) == tuple(held.spans)
                 or (entry.units and set(entry.units) <= set(held.spans)))


def _witness(pairs: _EventPairs, held: HeldFact, source: WitnessSource) -> Witness:
    family = cause_of(held).family
    if family is CauseFamily.RELATION:
        return Witness(held, source, pairs=pairs.relation(held))
    if family is CauseFamily.UNLISTED:
        found = pairs.unlisted(held) if source is WitnessSource.SUPPORT else ()
        return Witness(held, source, unlisted=found, entries=() if found else _entries(pairs.reader.R, held))
    return Witness(held, source)


def reader_of(R: FactSet, reader: coverage.Reader | None = None) -> coverage.Reader:
    """``reader`` when it is ``R``'s own (coverage.Reader: one per FactSet, never shared across FactSets), else a new
    Reader of ``R`` - so a witness is never read through another FactSet's readings."""
    return reader if reader is not None and reader.R is R else coverage.Reader(R)


def _tag_of(requirement: object) -> Tag | None:
    """A row's requirement read through its Enum (requirements_table.Tag): assess's R6 rows carry the Tag's VALUE
    (assess._Row.requirement is a str: ``Tag.R6_CONTEXT.value``), evaluate's rows a Tag; None for any other
    requirement (DECISIONS D323 L1, read as the rows are built: an identity test of the raw value with the member would
    never hold, so the member-context row would no longer be skipped)."""
    if isinstance(requirement, Tag):
        return requirement
    try:
        return Tag(requirement)
    except ValueError:
        return None


def candidate_witnesses(R: FactSet, code: str, group: Sequence[Kind], event: Id,
                       reader: coverage.Reader | None = None) -> tuple[Witness, ...]:
    """Every witness one positive candidate ``event`` of ``code``'s ``group`` would carry (module docstring)."""
    from studio.interpretation.engine import assess as engine_assess  # r6_rows: assess imports nothing of this module

    reader = reader_of(R, reader)
    pairs = _EventPairs(reader, event)
    member = engine_assess.MemberContext()
    found: list[Witness] = []
    seen: set[HeldFact] = set()

    def add(held: HeldFact, source: WitnessSource) -> None:
        if held not in seen:
            seen.add(held)
            found.append(_witness(pairs, held, source))

    for held in evaluate.support(code, group, R, event, reader).witnesses:  # D324 (8), int5: row 8 reads the Reader
        add(held, WitnessSource.SUPPORT)
    for row in evaluate.code_rows(code, group, R, event):
        for held in row.witnesses:
            add(held, WitnessSource.CODE_ROW)
    for r6 in engine_assess.r6_rows(code, (event,), R, member):
        if _tag_of(r6.requirement) is Tag.R6_CONTEXT:
            continue  # member context (A2): never the document's, never asked
        for held in r6.witnesses:
            add(held, WitnessSource.R6)
    for held in classes.enteroscopy_hold(code, (event,), R):
        add(held, WitnessSource.CLASS)
    for held in coverage.bundling(code, (event,), reader):
        add(held, WitnessSource.BUNDLING)
    return tuple(found)


def witnesses(R: FactSet, code: str, reader: coverage.Reader | None = None) -> tuple[Candidate, ...]:
    """Every positive candidate of every group of ``code`` with the witnesses it would carry (module docstring)."""
    link = catalogue.code_link(code)
    groups = catalogue.requirements(link)
    if not link.linked or not groups:
        return ()
    reader = reader_of(R, reader)
    return tuple(Candidate(code, tuple(group), event, candidate_witnesses(R, code, group, event, reader))
                 for group in groups for event in _positive_candidates(R, group))
