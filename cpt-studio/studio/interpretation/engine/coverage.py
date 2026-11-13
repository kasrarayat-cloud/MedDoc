"""Coverage and completeness over the settled facts (docs/gemini-migration/FINAL-V2.md 4.7, 4.8, 4.9, 4.10, 3.2.6 and
4.3's bundling row; step 4b of 8.1; cpt-studio-events@2): v1's studio/interpretation/coverage.py (FINAL 7.7 and 7.8 as
ADJUDICATION C-2, C-4 and C-5 amend them) forked into engine/, its readers deleted and its inputs rewired to the typed,
text-free FactSet (engine/facts.py, step 2d) and the pairing table (engine/pairing.py, step 3d). Nothing here reads text:
every input is an enumeration member, an id, a result or an integer span.

**Bundling** (4.7's bundling row, 4.3's bundling row, DECISIONS D191's hand-off 1e:R3: catalogue.BUNDLED_KINDS here,
UNSUPPORTED_KINDS in reconcile, ``unsupported_kinds``). Each rule is v1's, judged in Kleene's three values (4.2: T
when its facts hold the needed values, F when one is established against them, U otherwise) over one PART (the act that
may be included) and, for the rules that include it in another act, one WHOLE - an event other than the part, read by
``possibly`` (4.3: "the whole's status and timing read by possibly"): of the rule's whole kinds, possibly performed (or
begun, D79 and D177), possibly on the date of service, possibly in the part's session (both established and different
sets them apart; with fewer than two sessions nothing can, as in 4.5's session row). The rules, in v1's order (Rule):
- CLIP and CANNULATION (NOT_REPORTED): the part's catalogue kind is clip (a clip whose purpose is established as not
  hemostasis; one whose purpose may be hemostasis may be a bleeding control: U, D157's doubt) or cannulation.
- FAMILY_BUNDLED (a family's bundled kinds): the part's catalogue kind is one of BUNDLED_KINDS of its session's family,
  less NOT_REPORTED and the EUS's forceps biopsy (read under the upper endoscopy, never bundled: v1's ``kind !=
  'biopsy'``): the ERCP's contrast injection and the reflux study's pH capsule.
- LIFT_INJECTION: an injection (or a tattoo, by its part_of only: ONE_ACT, v1's arm) whose part_of names an EMR or ESD;
  or an injection whose purpose is lift_for_resection, of the same lesion as one.
- RESECTION_TECHNIQUE: a snare or hot-forceps removal whose part_of names an EMR or ESD, or of the same lesion as one.
- STENT_INCLUDED (D45): a sphincterotomy or a dilation of an ERCP session beside a stent placement or exchange of the
  same duct - both ducts established; established apart (biliary or cystic against pancreatic) sets them apart, and
  anything else is asked, never READY alone.
- PROCEDURAL_ADJUNCT (D30, D79): a bleeding control, ablation, clip or injection whose part_of names an act (never the
  examination: the session, C-1), or whose cause is act_of_this_session and whose cause_event names an event of the
  session (the examination included: control of bleeding the procedure itself caused). The whole may be performed or
  begun. D41's lexical identity and D58/D77's place adjacency are gone (4.7, 4.13): causality is part_of and cause.
  v1's same-lesion arm (D30: "by its verified part_of or the removal's lesion"), a FACT arm 4.7's "gone" column does
  not retire and its v2 inputs do not list, is built FAIL-CLOSED and never decides (the step's NOTES, question DQ1):
  an ablation or a bleeding control (v1's adjunct kinds, by catalogue kind) with a lesion stated, beside a removal
  performed or begun with a lesion stated, is possibly that removal's adjunct - U, asked (act_part), never T - unless
  the lesions are established apart or its own established part_of or cause says otherwise.
- BIOPSY_OF_REMOVED_LESION (C-2): a biopsy of the same lesion as a removal (snare, EMR, hot biopsy, ESD, or the removal
  umbrella, each of whose methods is one), where that lesion is single or the two anchors share a unit; an established
  group in separate units un-bundles it (DECISIONS D196: lesion.multiplicity is read on the READY path).
- DRAINAGE_STEP (G3, D171, D177): a fine-needle aspiration whose part_of names a drainage, or of the same lesion as one;
  the drainage may be performed or begun.

**What a fact leaves open.** An enumeration fact holds its value when supported; when negated it leaves every other value
open (pairing's reading); when not established, ``facts.possibly``'s values (its claimed value, its options, a doubt's
readings, an unrejected control's value; every value for an empty slot). A status that is not established leaves every
status open (4.2's status arm); a status established negated says the act was not done. The SAME LESION is T when both
lesions are supported and equal or joined by a supported same_as; F only when facts.apart_by_lesion (distinct_from and
the lesion pair controls, never while a same_as may join them) or facts.apart_by_place (established disjoint places and
their pair controls) sets the two acts apart; U otherwise - an unknown identity never sets two acts apart and never
makes one (4.11, the 2026-11-09 checklist). A part_of or a cause the document does not state (an EMPTY slot that no
doubt names) relates nothing: P16 and P15 ask pass 1 for them only where the document states them, and 3.2.3 leaves
part_of, part_relation and cause_event UNCONTROLLED because "a yes-bias can only hold"; a part_of or cause_event that is
claimed, doubted or contradicted relates the acts it may name (U). Any part_relation counts: an act part_of the whole
is not a separate service whatever the relation (the step's NOTES record this reading, question Q2).

**One verdict per act** (``verdict``; 4.3's bundling row): F (bundled) when some bundle is T, its witnesses the T
bundles' EXPLANATIONS alone (naming the whole: performed_status at rank 18, cause ``coding_rule:<rule>``) - the bundling
is an OR over its bundles, so a question about another possible whole could never release it; U (QUESTIONS) when none is
T and some is U; T (its own act) otherwise. A U bundle's witnesses rest on the facts it is not established on: a
contradicted one asks rank 1 (``conflict:<kind>``), a doubted status rank 2 (performed_status), any other a rank-17 fact
- ``act_part`` for a part_of, a whole's kind, status, timing or session; ``act_cause`` for a cause or cause_event;
``act_target`` for a lesion, a place or a duct (4.8's bundling row). **A contradicted act is never bundled out of its
question** (D3; S4's failure class D3, FINAL-V2 4.8 rank 1 and Appendix C): an act whose own kind, status, date
relation, performer, entry or session is contradicted, or that a statement contradicts (pairing.Relation.CONTRADICTION),
is never F - its verdict is U, its rank-1 conflict witnesses first, its T bundles explaining nothing - so neither the
code-level ``bundling`` nor the listing ever explains it away as part of another act, and reconcile lists it in doubt
with its conflict question. The same principle on the whole's side ("contradictions ... are never resolved by
bundling", S4): a whole a statement contradicts may not have been done, so a bundling into it is U, the whole's
conflict its first witness (the step's NOTES, question Q7).

**bundling(code, supporting, R)** (4.4's decide: ``held_facts += bundling(code, supporting, R)``): () when one of the
supporting acts is its own (v1: a code with an own act proceeds on it); otherwise every supporting act's witnesses -
each one's questions or explanations, every candidate's (HO-8), a question (it may release the code) ranking before an
explanation. Every catalogue code has at most one requirement group (catalogue.requirements; tested), so this is per
group.

**Sessions** (4.7: "from the sessions table"; S3 6.2): one Session per session of the FactSet, in pass 1's order. Its
members are the events whose session fact claims it (any state but negated: v1's family, the one session reconcile
lists an act under); its POSSIBLE members (``possible_members``) every event that may be in it (``sessions_of``: its
claimed session, an empty slot, a doubt's readings, a contradiction's sides, a negation of another session, or an id
naming no session of the FactSet - 4.2: a doubt is never an absence); its examinations the members that are
done (4.3 rows 2-5 supported: reading.done), their kind supported examination and their session supported; its POSSIBLE
examinations (D62, D87) the events, not done, whose kind may be the examination, whose session may be it and each of
whose rows 2-5 may hold. ``event`` is its one examination (exactly one done, no possible one); ``unresolved`` two or
more done or possible; ``done`` a member whose session fact is supported as this session, done, with its kind supported
(a claimed membership that is not established makes no session done: the act is listed in doubt instead);
``incomplete`` every done examination established attempted_not_completed. ``part_of`` (C3) is the session its
part_of_session names when supported (of another kind, or a kind not established), else (C-4, structural over supported
session kinds and tracts: 4.7's base_within row) the done EUS session whose tract is supported upper, for a done EGD
session with one done examination (v1's ``own``);
``possibly_part_of`` (D70) the session it may be part of otherwise - a part_of_session not established, or a session
that may be an EUS (its kind supported EUS, or not established with EUS among what it leaves open: 4.7's
"possibly_part_of by possibly") and may be upper (its tract not established, or pancreatobiliary) and may be done.
coding_family's region moves (D114, D141, D148, D153), eus_places and every C-4 word arm are gone (5.4): an act's
session is its own fact.

**Reportable and doubted** (v1's shapes). Reportable: done (rows 2-5 supported), status supported performed, kind
supported and its catalogue kind one of its session's family's reportable kinds (the catalogue acts but the examination,
the umbrellas and NOT_REPORTED, v1's NOT_ACT_KINDS; D116's stent removal and exchange where the family lists the stent),
session and its kind supported, and not bundled (verdict not F); event_coding drops the E/M kinds from its lists (the
session's own service is never an act beside itself), as v1 did. Doubted (4.7 [R:HO-1]): an act that may be of a
reportable kind of a family it may be in - every family when its own session fact is not established (4.2; settle's K2
demotes the session of an act its family cannot hold) - (D117's positive removal umbrella and D115's possible bleeding
control - from purpose, never words - included), possibly performed or begun, neither its date relation nor its
performer established as another, and in doubt: a required fact (4.3 rows 1-6) not supported, a statement paired with it
in any relation but INDEPENDENT, an unlisted denial or doubt paired with it (3.2.6 rule 4), or a bundling in doubt (U).
``doubted_in`` reads the same in ONE session: the act possibly in it, of a reportable kind of a family that session may
be of. An UNLISTED ACT with a session (3.2.6 rule 3) is a synthetic doubted act of that session. D137/D145's EUS acts of
a CATALOGUE kind the EUS entry does not list (v1's eus_unprofiled_entries read catalogue_kind: a hemostatic clip or
injection is a bleeding control; kind other is v1's '') are recorded as reportable when that kind is established and the
act done and performed, and doubted when begun or in doubt (D156 (3): never both).

**reconcile, completeness, event_coding, the service questions** (S3 6.3; "unchanged shapes, cpt-studio-events@2"): v1's
rules over these readings, with typed records in place of v1's sentences (the wording - an item's label, a service
question's sentence - is step 3c's, from the item's fact key, subject and spans; FINAL-V2 4.8): reconcile's unresolved
items (no_proposal, not_covered, coverage_unknown, unsupported, in_doubt; one per session and act kind), bundled acts,
covered sessions, sessions not listed and the unestablished count; completeness's fixed sentences (v1's, pinned equal;
an unlisted statement makes it incomplete, 3.2.6 rule 1); event_coding@2 (ids and enumeration values only; a session's
doubted entries hold every act possibly in it and doubted there, so a weakening never drops an act from the records
base_included reads). What a weakening may not release, reconcile keeps listed (P-MONO at the records): a done session
whose kind is not established is read as every supported family it may be of, whatever one reading lists listed with its
family None and only the codes covering it under every reading covering it (v1 grouped it by pass 1's claimed family);
an act filed under no session of the FactSet (an empty slot, a contradicted or doubted one, an id naming none) is listed
in doubt with its session None; D142's class (a kind its family's acts do not list, another's do) in doubt is listed in
doubt; a session not done counts as unestablished by its possible members (an examination whose session fact is in doubt
is possibly its own); an act of a kind its family has no profile for (``unsupported_kinds``: UNSUPPORTED_ACTS and the
family's UNSUPPORTED_KINDS, hand-off 1e:R3) is listed unsupported. One service question per (session, fact) for an act
in doubt no counted code reads, the act chosen by 4.8's binding (one a code's question names last, D149; then the fewest
witnesses; then document order) and none a code's item already asks (D89); and D125's extent question per done session
whose extent no code asks.

**The text-free boundary** (P1; FINAL-V2 4.1, 5.7 measure 4): this module imports the standard library, the package's
labels, contract/types.py and engine's catalogue, facts, pairing, reading, requirements and types only - no retired v1
module (5.0), none of contract's text modules, not wording - holds no word, phrase or marker list (every module-level
collection holds enumeration members), and reads no text. Its only sentences are completeness's fixed ones (v1's); every
other record carries CPT Studio's codes, ids and integer spans. ``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, unique
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation import ENGINE_VERSION_V2
from studio.interpretation.contract.types import (Attribute, Cause, DateRelation, Duct, Kind, Landmark, Multiplicity,
                                                  Owner, Performer, Purpose, Qualifier2, Reason, Result, SessionKind,
                                                  Status, Tract, UnlistedWhat, VerdictValue)
from studio.interpretation.engine import anatomy, catalogue, pairing, reading
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span, UnlistedStatement

_T = TypeVar('_T', bound=Enum)
_A = Attribute

# The completeness record's second-review bound (v1's coverage.SECOND_REVIEW_CHECKED = engine.SECOND_REVIEW_CHECKED).
SECOND_REVIEW_CHECKED = 64
# event_coding's version: the read-time overlay (step 5c) reads @2 only (FINAL-V2 6.5).
CODING_VERSION = ENGINE_VERSION_V2


# --- the vocabulary ----------------------------------------------------------------------------------------------------


@unique
class Truth(Enum):
    """The truth of a requirement or of one of its conjuncts (FINAL-V2 4.2, B's Kleene view): T when its facts hold the
    needed values, F when a fact is established against them, U otherwise."""
    T = 'T'
    U = 'U'
    F = 'F'


@unique
class Rule(Enum):
    """The bundling rules (4.7, COMMON_BUNDLED; the module docstring), in v1's order. The values are v1's reasons, and
    those step 3c's wording.Bundling names (clip, cannulation and the six that can ask); FAMILY_BUNDLED is a family's
    own bundled kind (v1's FamilyEntry.bundled sentence)."""
    CLIP = 'clip'
    CANNULATION = 'cannulation'
    FAMILY_BUNDLED = 'family_bundled'
    LIFT_INJECTION = 'lift_injection'
    RESECTION_TECHNIQUE = 'resection_technique'
    STENT_INCLUDED = 'stent_included'
    PROCEDURAL_ADJUNCT = 'procedural_adjunct'
    BIOPSY_OF_REMOVED_LESION = 'biopsy_of_removed_lesion'
    DRAINAGE_STEP = 'drainage_step'


# The causes a witness carries (FINAL-V2 4.4), operator data that names no vendor.
READING_UNKNOWN = 'reading_unknown'
# The coding rule an act's own witness names when it rests on an established fact (4.3 rows 1-6 read for no code).
ACT_SUPPORT = 'act_support'
READING_CONTRADICTED = 'reading_contradicted'
UNESTABLISHED = 'unestablished'
UNLISTED = 'unlisted'
RELATION_CONTRADICTION = f'relation:{pairing.Relation.CONTRADICTION.value}'


@unique
class Coherence(Enum):
    """The appraisal outcomes of 3.2.3's coherence table that are no verdict, as a cause names them (4.4:
    appraisal:<verdict or coherence>)."""
    INCOHERENT = 'control_incoherent'
    DETACHED = 'detached'
    MISSING = 'missing'


# Each appraisal reason of 3.3 row 9 -> the verdict or coherence its cause names (as engine/classes.py, step 4c).
APPRAISAL_CAUSES: Mapping[Reason, VerdictValue | Coherence] = MappingProxyType({
    Reason.APPRAISAL_CONTRADICTS: VerdictValue.CONTRADICTS, Reason.APPRAISAL_UNCLEAR: VerdictValue.UNCLEAR,
    Reason.APPRAISAL_QUALIFIED: VerdictValue.QUALIFIED, Reason.CONTROL_INCOHERENT: Coherence.INCOHERENT,
    Reason.APPRAISAL_DETACHED: Coherence.DETACHED, Reason.APPRAISAL_MISSING: Coherence.MISSING,
    **{Reason(f'appraisal_qualified:{qualifier.value}'): VerdictValue.QUALIFIED for qualifier in Qualifier2},
})
# The reasons settle gives a fact a doubt names (3.3 row 2).
DOUBT_REASONS: frozenset[Reason] = frozenset({Reason.DOUBT_STATED, Reason.DOUBT_UNCLEAR})

# --- the tables (every one over enumeration members) -------------------------------------------------------------------

_PERFORMED: frozenset[Status] = frozenset({Status.PERFORMED})
_POSITIVE: frozenset[Status] = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})  # D79, D177: or begun
_TODAY: frozenset[DateRelation] = frozenset({DateRelation.ON_DATE_OF_SERVICE})
_RESECTIONS: frozenset[Kind] = frozenset({Kind.EMR, Kind.ESD})
_LIFTS: frozenset[Kind] = frozenset({Kind.INJECTION})
_LIFTS_BY_PART: frozenset[Kind] = catalogue.ONE_ACT  # an injection or a tattoo, by its part_of (v1's ONE_ACT arm)
_TECHNIQUES: frozenset[Kind] = frozenset({Kind.SNARE, Kind.HOT_BIOPSY})
_STENT_PARTS: frozenset[Kind] = frozenset({Kind.SPHINCTEROTOMY, Kind.DILATION})
_STENTS: frozenset[Kind] = frozenset({Kind.STENT, Kind.STENT_EXCHANGE})
_ADJUNCTS: frozenset[Kind] = frozenset({Kind.BLEEDING_CONTROL, Kind.ABLATION, Kind.CLIP, Kind.INJECTION})
# v1's adjunct kinds (relations.PROCEDURAL_ADJUNCTS, catalogue kinds), the only ones its same-lesion arm read (DQ1).
_LESION_ADJUNCTS: frozenset[Kind] = frozenset({Kind.ABLATION, Kind.BLEEDING_CONTROL})
_BIOPSIES: frozenset[Kind] = frozenset({Kind.BIOPSY})
_OTHER: frozenset[Kind] = frozenset({Kind.OTHER})  # no catalogue kind (v1's ''), which D137's class reads too
_REMOVALS: frozenset[Kind] = frozenset(catalogue.REMOVAL_MEMBERS)
_ASPIRATIONS: frozenset[Kind] = frozenset({Kind.FNA})
_DRAINAGES: frozenset[Kind] = frozenset({Kind.DRAINAGE})
_ERCP: frozenset[SessionKind] = frozenset({SessionKind.ERCP})
# The acts an adjunct's part_of can name: every kind but the examination (the session, ADJUDICATION C-1).
_ACT_WHOLES: frozenset[Kind] = frozenset(kind for kind in Kind if kind is not Kind.EXAMINATION)
# D45: the ducts that set a stent and a sphincterotomy or dilation apart (the cystic duct lies on the biliary side).
_DUCTS_APART: frozenset[frozenset[Duct]] = frozenset({frozenset({Duct.BILIARY, Duct.PANCREATIC}),
                                                      frozenset({Duct.CYSTIC, Duct.PANCREATIC})})
# A family's own bundled kinds (4.7: "a family's bundled kinds"; D191's BUNDLED_KINDS), less NOT_REPORTED (their own
# rules) and the EUS's forceps biopsy (read under the upper endoscopy, never bundled: v1's ``kind != 'biopsy'``).
FAMILY_OWN_BUNDLED: Mapping[SessionKind, frozenset[Kind]] = MappingProxyType({
    family: frozenset(kind for kind in kinds if kind not in catalogue.NOT_REPORTED
                      and not (family is SessionKind.EUS and kind is Kind.BIOPSY))
    for family, kinds in catalogue.BUNDLED_KINDS.items()})
_OWN_BUNDLED_ANY: frozenset[Kind] = frozenset(kind for kinds in FAMILY_OWN_BUNDLED.values() for kind in kinds)
# D116: the stent's own acts besides its placement, reportable in a family whose catalogue acts hold the stent.
STENT_ACTS: frozenset[Kind] = frozenset({Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE})
# What is never an act beside its session (v1's NOT_ACT_KINDS): the examination (the session) and the umbrellas.
# event_coding drops the E/M kinds from its lists besides (v1's: the session's own service is never an act beside
# itself), and reconcile lists a doubted visit as v1 did.
_NOT_ACTS: frozenset[Kind] = frozenset({Kind.EXAMINATION, *catalogue.UMBRELLAS})
# 4.3 rows 1-6, an act's own required facts (the conflict a contradicted one raises; the doubt of ``doubted``).
_OWN_FACTS: tuple[Attribute, ...] = (_A.KIND, _A.STATUS, _A.DATE_RELATION, _A.PERFORMER, _A.ENTRY, _A.SESSION)


def reportable_kinds(family: SessionKind) -> frozenset[Kind]:
    """v1's reportable_kind for ``family``: its catalogue acts but the examination, the umbrellas and NOT_REPORTED, and
    (D116) the stent removal and exchange where its acts hold the stent placement."""
    acts = frozenset(catalogue.FAMILY_ACTS.get(family, ()))
    return frozenset(kind for kind in acts if kind not in _NOT_ACTS and kind not in catalogue.NOT_REPORTED) | (
        STENT_ACTS if Kind.STENT in acts else frozenset())


def eus_unlisted_kind(kind: Kind) -> bool:
    """D137, D145: a CATALOGUE kind of an EUS act (catalogue_kinds; v1's catalogue_kind) the EUS's catalogue entry does
    not list among its acts - a lumen-apposing stent, an ablation, a tattoo, a bleeding control (a hemostatic clip or
    injection), an act of kind other - and that is no examination, umbrella, E/M kind or NOT_REPORTED kind."""
    return (kind not in catalogue.FAMILY_ACTS[SessionKind.EUS] and kind not in _NOT_ACTS
            and kind not in catalogue.EM_KINDS and kind not in catalogue.NOT_REPORTED)


def unsupported_kinds(family: SessionKind) -> frozenset[Kind]:
    """The kinds no code profile of ``family`` reconciles (hand-off 1e:R3; DECISIONS D191): v1's UNSUPPORTED_ACTS (the
    ESD, whatever the family) and the family's own UNSUPPORTED_KINDS that its catalogue acts do not list - the anorectal
    balloon expulsion, which the catalogue entry says "is listed for the reviewer". A kind the family's acts also list
    (the EUS's drainage: 43240 covers a pseudocyst's, and UNSUPPORTED_KINDS names the others) is the family's act, read
    as one: its code's own rows decide it (4.3's STRUCT:pfc), never its kind alone."""
    own = catalogue.UNSUPPORTED_KINDS.get(family, frozenset()) - frozenset(catalogue.FAMILY_ACTS.get(family, ()))
    return catalogue.UNSUPPORTED_ACTS | own


# --- judging one conjunct ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Doubt:
    """One fact a bundling's truth rests on while it is not established: ``subject``'s ``attribute`` (``fact`` its
    Fact), asked as ``key`` (act_part, act_cause or act_target) unless it is contradicted or a doubted status, and
    ``kind``, the kind of the act it belongs to (conflict:<kind>)."""
    subject: Id
    attribute: Attribute
    fact: Fact
    key: rq.FactKey
    kind: Kind


@dataclass(frozen=True, slots=True)
class Judged:
    """A conjunct's truth; for U, the facts it rests on (Doubt) and any ready witness (``conflicts``: a whole a
    statement contradicts, D3); for T, the attribute that decided it (None for a conjunct no single fact decides)."""
    truth: Truth
    doubts: tuple[Doubt, ...] = ()
    attribute: Attribute | None = None
    conflicts: tuple[HeldFact, ...] = ()


_FALSE = Judged(Truth.F)
_TRUE = Judged(Truth.T)


def _decided(attribute: Attribute) -> Judged:
    return Judged(Truth.T, (), attribute)


def _both(*judged: Judged) -> Judged:
    """Kleene conjunction: F when one is F; U, with every U's doubts, when one is U; else T (the first deciding
    attribute)."""
    if any(item.truth is Truth.F for item in judged):
        return _FALSE
    open_ = [item for item in judged if item.truth is Truth.U]
    if open_:
        return Judged(Truth.U, tuple(doubt for item in open_ for doubt in item.doubts), None,
                      tuple(found for item in open_ for found in item.conflicts))
    return Judged(Truth.T, (), next((item.attribute for item in judged if item.attribute is not None), None))


def _either(*judged: Judged) -> Judged:
    """Kleene disjunction: the first T; else U, with every U's doubts; else F."""
    for item in judged:
        if item.truth is Truth.T:
            return item
    open_ = [item for item in judged if item.truth is Truth.U]
    if open_:
        return Judged(Truth.U, tuple(doubt for item in open_ for doubt in item.doubts), None,
                      tuple(found for item in open_ for found in item.conflicts))
    return _FALSE


def _pure_silent(found: Fact) -> bool:
    """An empty slot no doubt names (3.3 row 3): pass 1 stated nothing and nothing doubts it."""
    return (found.state is None and not found.options and found.result is Result.UNKNOWN
            and all(reason is Reason.SILENT for reason in found.reasons))


def _doubted(found: Fact) -> bool:
    """A fact a doubt names (3.3 row 2): unknown, with a doubt's reason."""
    return found.result is Result.UNKNOWN and any(reason in DOUBT_REASONS for reason in found.reasons)


def _kind_of(R: FactSet, event: Id) -> Kind:
    """The kind an item about ``event`` names (conflict:<kind>): its claimed kind, else its first possible side, else
    other."""
    found = facts_.fact(R, event, _A.KIND)
    if isinstance(found.value, Kind):
        return found.value
    return next((option for option in found.options if isinstance(option, Kind)), Kind.OTHER)


class _Asker:
    """Who a conjunct's doubts are about and how they are asked: the FactSet, the part and its kind, and the Reader
    whose pairs a whole's contradictions are read from (None outside one: no whole is judged then)."""

    __slots__ = ('R', 'part', 'kind', 'reader')

    def __init__(self, R: FactSet, part: Id, reader: Reader | None = None) -> None:
        self.R = R
        self.part = part
        self.kind = _kind_of(R, part)
        self.reader = reader

    def doubt(self, subject: Id, attribute: Attribute, found: Fact, key: rq.FactKey) -> Judged:
        kind = self.kind if subject == self.part or subject.family is not IdFamily.EVENT else _kind_of(self.R, subject)
        return Judged(Truth.U, (Doubt(subject, attribute, found, key, kind),))


def _enum_in(ask: _Asker, subject: Id, attribute: Attribute, wanted: frozenset[_T], domain: type[_T],
             key: rq.FactKey) -> Judged:
    """Whether ``subject``'s single-valued ``attribute`` holds one of ``wanted`` (module docstring: supported, its
    value; negated, every other value; not established, facts.possibly's)."""
    found = facts_.fact(ask.R, subject, attribute)
    if found.result is Result.SUPPORTED:
        return _decided(attribute) if found.value in wanted else _FALSE
    if found.result is Result.NEGATED:
        rest = frozenset(member for member in domain if member != found.value)
        return ask.doubt(subject, attribute, found, key) if rest & wanted else _FALSE
    if any(facts_.possibly(found, value) for value in wanted):
        return ask.doubt(subject, attribute, found, key)
    return _FALSE


def _status_in(ask: _Asker, subject: Id, wanted: frozenset[Status], key: rq.FactKey) -> Judged:
    """Whether ``subject``'s status is one of ``wanted``: supported, its value; negated, no (the act was not done);
    not established, every status (4.2's status arm)."""
    found = facts_.fact(ask.R, subject, _A.STATUS)
    if found.result is Result.SUPPORTED:
        return _decided(_A.STATUS) if found.value in wanted else _FALSE
    if found.result is Result.NEGATED:
        return _FALSE
    return ask.doubt(subject, _A.STATUS, found, key)


def may_be(found: Fact) -> frozenset[Kind]:
    """The kinds an event whose kind fact is ``found`` may be, an umbrella read as each of its members (it is one of
    them, method not stated): supported, its value; negated, every other kind; not established, facts.possibly's."""
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        kinds: frozenset[Kind] = frozenset({found.value})
    elif found.result is Result.NEGATED:
        kinds = frozenset(kind for kind in Kind if kind != found.value)
    else:
        kinds = frozenset(kind for kind in Kind if facts_.possibly(found, kind))
    return frozenset(member for kind in kinds for member in catalogue.UMBRELLAS.get(kind, (kind,)))


def _kind_in(ask: _Asker, subject: Id, wanted: frozenset[Kind], key: rq.FactKey) -> Judged:
    """Whether ``subject`` is of one of ``wanted``: T when its kind is supported and everything it may be is wanted (an
    umbrella whose members all are), F when nothing it may be is, U otherwise."""
    found = facts_.fact(ask.R, subject, _A.KIND)
    kinds = may_be(found)
    if not kinds & wanted:
        return _FALSE
    if found.result is Result.SUPPORTED and kinds <= wanted:
        return _decided(_A.KIND)
    return ask.doubt(subject, _A.KIND, found, key)


def catalogue_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """The catalogue kinds ``event`` may be (catalogue.catalogue_kind over facts): a clip or an injection whose purpose
    is supported hemostasis is a bleeding control; one whose purpose may be hemostasis may be either (D157's doubt);
    kind other is no catalogue kind."""
    purpose = facts_.fact(R, event, _A.PURPOSE)
    out: set[Kind] = set()
    for kind in may_be(facts_.fact(R, event, _A.KIND)):
        if kind is Kind.OTHER:
            continue
        if kind in catalogue.HEMOSTASIS_KINDS and facts_.holds(purpose, Purpose.HEMOSTASIS):
            out.add(Kind.BLEEDING_CONTROL)
        elif kind in catalogue.HEMOSTASIS_KINDS and _purpose_may_be_hemostasis(purpose):
            out |= {kind, Kind.BLEEDING_CONTROL}
        else:
            out.add(kind)
    return frozenset(out)


def _purpose_may_be_hemostasis(purpose: Fact) -> bool:
    """A purpose that leaves hemostasis open: not established (facts.possibly), or negated as another purpose."""
    if purpose.result is Result.NEGATED:
        return purpose.value is not Purpose.HEMOSTASIS
    return not facts_.established(purpose) and facts_.possibly(purpose, Purpose.HEMOSTASIS)


def _ckind_in(ask: _Asker, subject: Id, wanted: frozenset[Kind], key: rq.FactKey) -> Judged:
    """Whether ``subject``'s catalogue kind is one of ``wanted`` (catalogue_kinds): T when its kind is supported and every
    catalogue kind it may be is wanted (a clip whose purpose cannot be hemostasis is a clip); F when none is; U
    otherwise, resting on the kind when it is not supported and on the purpose that leaves a bleeding control open."""
    kinds = catalogue_kinds(ask.R, subject)
    if not kinds & wanted:
        return _FALSE
    kind, purpose = facts_.fact(ask.R, subject, _A.KIND), facts_.fact(ask.R, subject, _A.PURPOSE)
    if kind.result is Result.SUPPORTED and kinds <= wanted:
        return _decided(_A.KIND)
    doubts: list[Judged] = []
    if kind.result is not Result.SUPPORTED:
        doubts.append(ask.doubt(subject, _A.KIND, kind, key))
    if may_be(kind) & catalogue.HEMOSTASIS_KINDS and Kind.BLEEDING_CONTROL in kinds and \
            purpose.result is not Result.SUPPORTED:
        doubts.append(ask.doubt(subject, _A.PURPOSE, purpose, key))
    return _both(*doubts) if doubts else ask.doubt(subject, _A.KIND, kind, key)


def sessions_of(R: FactSet, event: Id) -> frozenset[Id]:
    """The sessions of the FactSet ``event`` may be in: its supported session; every other session when its session is
    negated; facts.possibly's sessions otherwise (every session for an empty slot). A session fact that names a session
    the FactSet does not hold (a dangling id: settle's I4 keeps the claimed value, unresolved, FINAL-V2 1.8), as its
    value or as one of its readings, leaves every session open: a missing identifier manufactures neither a match nor a
    non-match (4.11), and a doubt is never an absence (4.2)."""
    found = facts_.fact(R, event, _A.SESSION)
    every = frozenset(R.sessions)
    if found.result is Result.NEGATED:
        return frozenset(session for session in every if session != found.value)
    named = (found.value, *found.options) if found.result is not Result.SUPPORTED else (found.value,)
    if any(isinstance(value, Id) and value not in every for value in named):
        return every
    if found.result is Result.SUPPORTED and isinstance(found.value, Id):
        return frozenset({found.value})
    return frozenset(session for session in every if facts_.possibly(found, session))


def _established_sessions(R: FactSet, found: Fact) -> frozenset[Id] | None:
    """The sessions an ESTABLISHED session fact leaves open (supported: its session; negated: every other one); None
    for one that is not established."""
    if found.result is Result.SUPPORTED and isinstance(found.value, Id):
        return frozenset({found.value})
    if found.result is Result.NEGATED:
        return frozenset(session for session in R.sessions if session != found.value)
    return None


def _same_session(ask: _Asker, part: Id, whole: Id) -> Judged:
    """The part and the whole in one session (4.5's session row as bundling reads it): both supported, equal or not;
    apart only when both are established and leave no session in common (an unknown session never sets two acts
    apart); with fewer than two sessions nothing can; U otherwise, resting on the session facts not established."""
    one, other = facts_.fact(ask.R, part, _A.SESSION), facts_.fact(ask.R, whole, _A.SESSION)
    if one.result is Result.SUPPORTED and other.result is Result.SUPPORTED:
        return _decided(_A.SESSION) if one.value == other.value else _FALSE
    first, second = _established_sessions(ask.R, one), _established_sessions(ask.R, other)
    if first is not None and second is not None and not first & second:
        return _FALSE
    if len(ask.R.sessions) < 2:
        return _TRUE
    doubts = [ask.doubt(subject, _A.SESSION, found, rq.FactKey.ACT_PART)
              for subject, found in ((part, one), (whole, other)) if found.result is not Result.SUPPORTED]
    return _both(*doubts)


def _whole(ask: _Asker, part: Id, whole: Id, kinds: frozenset[Kind] | None, statuses: frozenset[Status]) -> Judged:
    """The whole as 4.3's bundling row reads it (by possibly): of ``kinds`` (None: any kind), its status one of
    ``statuses``, on the date of service, in the part's session."""
    kind = _TRUE if kinds is None else _kind_in(ask, whole, kinds, rq.FactKey.ACT_PART)
    return _both(kind, _status_in(ask, whole, statuses, rq.FactKey.ACT_PART),
                 _enum_in(ask, whole, _A.DATE_RELATION, _TODAY, DateRelation, rq.FactKey.ACT_PART),
                 _same_session(ask, part, whole), _unchallenged(ask, whole))


def _unchallenged(ask: _Asker, whole: Id) -> Judged:
    """D3's principle on the whole's side (S4: "contradictions ... are never resolved by bundling"): a whole a
    statement contradicts (pairing's CONTRADICTION) may not have been done, so a bundling into it is asked - its
    conflict first (rank 1) - and never explained away. T when no statement contradicts it."""
    if ask.reader is None:
        return _TRUE
    found = tuple(item for item in ask.reader.conflicts(whole) if item.cause == RELATION_CONTRADICTION)
    return Judged(Truth.U, (), None, found) if found else _TRUE


def _part_of(ask: _Asker, part: Id, whole: Id) -> Judged:
    """The part's part_of names the whole (any part_relation): supported, its value; negated or an empty slot no doubt
    names, no (module docstring); otherwise, facts.possibly's."""
    found = facts_.fact(ask.R, part, _A.PART_OF)
    if found.result is Result.SUPPORTED:
        return _decided(_A.PART_OF) if found.value == whole else _FALSE
    if found.result is Result.NEGATED or _pure_silent(found):
        return _FALSE
    return ask.doubt(part, _A.PART_OF, found, rq.FactKey.ACT_PART) if facts_.possibly(found, whole) else _FALSE


def _caused_by(ask: _Asker, part: Id, whole: Id) -> Judged:
    """The part treats bleeding the whole caused (D30, D79: cause act_of_this_session with cause_event): the cause,
    unless an empty slot no doubt names; and the cause_event naming the whole - supported, its value; negated, not that
    act; an empty slot, any act of the session; otherwise facts.possibly's."""
    cause = facts_.fact(ask.R, part, _A.CAUSE)
    if _pure_silent(cause):
        return _FALSE
    by_act = _enum_in(ask, part, _A.CAUSE, frozenset({Cause.ACT_OF_THIS_SESSION}), Cause, rq.FactKey.ACT_CAUSE)
    if by_act.truth is Truth.F:
        return _FALSE
    event = facts_.fact(ask.R, part, _A.CAUSE_EVENT)
    if event.result is Result.SUPPORTED:
        named = _decided(_A.CAUSE_EVENT) if event.value == whole else _FALSE
    elif event.result is Result.NEGATED:
        named = _FALSE if event.value == whole else ask.doubt(part, _A.CAUSE_EVENT, event, rq.FactKey.ACT_CAUSE)
    elif _pure_silent(event) or facts_.possibly(event, whole):
        named = ask.doubt(part, _A.CAUSE_EVENT, event, rq.FactKey.ACT_CAUSE)
    else:
        named = _FALSE
    return _both(by_act, named)


def _supported_id(found: Fact) -> Id | None:
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def _joined(R: FactSet, one: Id, other: Id, *, possibly: bool) -> bool:
    """Two lesions one (same_as in either list): supported, or (``possibly``) possibly so (facts.possibly)."""
    test = facts_.possibly if possibly else facts_.holds
    return one == other or any(test(member, other) for member in facts_.members(R, one, _A.SAME_AS)) or any(
        test(member, one) for member in facts_.members(R, other, _A.SAME_AS))


def _apart(R: FactSet, part: Id, whole: Id) -> bool:
    """The two acts' targets established apart (4.2 [R:SC-B]): by lesion (facts.apart_by_lesion: distinct_from and the
    lesion pair controls, never while a same_as may join the two lesions) or by place (facts.apart_by_place: disjoint
    established places and their pair controls)."""
    one = _supported_id(facts_.fact(R, part, _A.TARGET_LESION))
    other = _supported_id(facts_.fact(R, whole, _A.TARGET_LESION))
    by_lesion = (facts_.apart_by_lesion(R, part, whole) and one is not None and other is not None
                 and not _joined(R, one, other, possibly=True))
    return by_lesion or facts_.apart_by_place(R, part, whole)


def _same_lesion(ask: _Asker, part: Id, whole: Id) -> Judged:
    """One lesion (module docstring): T when both are supported and equal or joined by a supported same_as; F when the
    two acts' targets are established apart; U otherwise, resting on the lesion facts not established (on the part's,
    when both are supported and nothing joins or sets them apart)."""
    one, other = facts_.fact(ask.R, part, _A.TARGET_LESION), facts_.fact(ask.R, whole, _A.TARGET_LESION)
    first, second = _supported_id(one), _supported_id(other)
    if first is not None and second is not None and _joined(ask.R, first, second, possibly=False):
        return _decided(_A.TARGET_LESION)
    if _apart(ask.R, part, whole):
        return _FALSE
    doubts = [ask.doubt(subject, _A.TARGET_LESION, found, rq.FactKey.ACT_TARGET)
              for subject, found in ((part, one), (whole, other)) if found.result is not Result.SUPPORTED]
    return _both(*doubts) if doubts else ask.doubt(part, _A.TARGET_LESION, one, rq.FactKey.ACT_TARGET)


def _shared_unit(R: FactSet, one: Id, other: Id) -> bool:
    """The two events' anchors share a unit (C-2's passage in common, as a unit span)."""
    first, second = R.anchors.get(one), R.anchors.get(other)
    return first is not None and second is not None and bool(set(first.units) & set(second.units))


def _single_or_shared(ask: _Asker, part: Id, whole: Id) -> Judged:
    """C-2 (DECISIONS D196): the two anchors share a unit, or the lesion is supported single; an established group (or
    single negated) sets them apart; U otherwise, resting on the multiplicity."""
    if _shared_unit(ask.R, part, whole):
        return _TRUE
    lesion = (_supported_id(facts_.fact(ask.R, part, _A.TARGET_LESION))
              or _supported_id(facts_.fact(ask.R, whole, _A.TARGET_LESION)))
    if lesion is None:
        return Judged(Truth.U)
    return _enum_in(ask, lesion, _A.MULTIPLICITY, frozenset({Multiplicity.SINGLE}), Multiplicity,
                    rq.FactKey.ACT_TARGET)


def _ducts(found: Fact) -> frozenset[Duct]:
    if found.result is Result.SUPPORTED and isinstance(found.value, Duct):
        return frozenset({found.value})
    if found.result is Result.NEGATED:
        return frozenset(duct for duct in Duct if duct != found.value)
    return frozenset(duct for duct in Duct if facts_.possibly(found, duct))


def duct(R: FactSet, event: Id) -> Duct | None:
    """The duct an ERCP act is established in (v1's duct_side): its supported target.duct, None otherwise."""
    found = facts_.fact(R, event, _A.TARGET_DUCT)
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Duct) else None


def _same_duct(ask: _Asker, part: Id, whole: Id) -> Judged:
    """D45: both ducts supported and equal; both ESTABLISHED and every duct one leaves open set apart from every duct
    the other leaves open (_DUCTS_APART), no; U otherwise - a duct established on neither act, or on one only, never
    sets them apart (4.11)."""
    one, other = facts_.fact(ask.R, part, _A.TARGET_DUCT), facts_.fact(ask.R, whole, _A.TARGET_DUCT)
    first, second = duct(ask.R, part), duct(ask.R, whole)
    if first is not None and first is second:
        return _decided(_A.TARGET_DUCT)
    left, right = _ducts(one), _ducts(other)
    if facts_.established(one) and facts_.established(other) and left and right and all(
            frozenset({x, y}) in _DUCTS_APART for x in left for y in right):
        return _FALSE
    doubts = [ask.doubt(subject, _A.TARGET_DUCT, found, rq.FactKey.ACT_TARGET)
              for subject, found in ((part, one), (whole, other)) if found.result is not Result.SUPPORTED]
    return _both(*doubts) if doubts else ask.doubt(part, _A.TARGET_DUCT, one, rq.FactKey.ACT_TARGET)


def _family_in(ask: _Asker, subject: Id, families: frozenset[SessionKind]) -> Judged:
    """The event's session is of one of ``families``: T when its session and that session's kind are supported and the
    kind is one of them; F when no session it may be in may be of them; U otherwise, resting on its session fact and on
    the kinds of the sessions it may be in that are not established."""
    family = facts_.session_family(ask.R, subject)
    if family is not None:
        return _decided(_A.SESSION) if family in families else _FALSE
    session = facts_.fact(ask.R, subject, _A.SESSION)
    candidates = sessions_of(ask.R, subject)
    may = [candidate for candidate in candidates
           if any(_session_kind_may_be(facts_.fact(ask.R, candidate, _A.KIND), wanted) for wanted in families)]
    if ask.R.sessions and not may:
        return _FALSE
    doubts: list[Judged] = []
    if session.result is not Result.SUPPORTED:
        doubts.append(ask.doubt(subject, _A.SESSION, session, rq.FactKey.ACT_PART))
    for candidate in may:
        kind = facts_.fact(ask.R, candidate, _A.KIND)
        if kind.result is not Result.SUPPORTED:
            doubts.append(ask.doubt(candidate, _A.KIND, kind, rq.FactKey.ACT_PART))
    return _both(*doubts) if doubts else ask.doubt(subject, _A.SESSION, session, rq.FactKey.ACT_PART)


def _session_kind_may_be(found: Fact, wanted: SessionKind) -> bool:
    if found.result is Result.SUPPORTED:
        return found.value is wanted
    if found.result is Result.NEGATED:
        return found.value is not wanted
    return facts_.possibly(found, wanted)


# --- the bundling rules (module docstring) -----------------------------------------------------------------------------


def _rule_clip(ask: _Asker) -> Judged:
    return _ckind_in(ask, ask.part, frozenset({Kind.CLIP}), rq.FactKey.ACT_PART)


def _rule_cannulation(ask: _Asker) -> Judged:
    return _kind_in(ask, ask.part, frozenset({Kind.CANNULATION}), rq.FactKey.ACT_PART)


def _rule_family(ask: _Asker) -> Judged:
    """FAMILY_BUNDLED: the part's catalogue kind is one of its session family's own bundled kinds."""
    kinds = catalogue_kinds(ask.R, ask.part)
    if not kinds & _OWN_BUNDLED_ANY:
        return _FALSE
    family = facts_.session_family(ask.R, ask.part)
    if family is not None:
        own = FAMILY_OWN_BUNDLED.get(family, frozenset())
        return _ckind_in(ask, ask.part, own, rq.FactKey.ACT_PART) if own else _FALSE
    families = frozenset(found for found, own in FAMILY_OWN_BUNDLED.items() if own & kinds)
    return _both(_ckind_in(ask, ask.part, _OWN_BUNDLED_ANY, rq.FactKey.ACT_PART), _family_in(ask, ask.part, families))


def _lift(ask: _Asker, whole: Id) -> Judged:
    """LIFT_INJECTION: an injection or a tattoo whose part_of names an EMR or ESD; or an injection whose purpose is
    lift_for_resection, of the same lesion as one. The relation comes first, so a T names its deciding fact."""
    by_part = _both(_part_of(ask, ask.part, whole), _kind_in(ask, ask.part, _LIFTS_BY_PART, rq.FactKey.ACT_PART))
    by_purpose = _both(_same_lesion(ask, ask.part, whole), _kind_in(ask, ask.part, _LIFTS, rq.FactKey.ACT_PART),
                       _enum_in(ask, ask.part, _A.PURPOSE, frozenset({Purpose.LIFT_FOR_RESECTION}), Purpose,
                                rq.FactKey.ACT_PART))
    return _both(_either(by_part, by_purpose), _whole(ask, ask.part, whole, _RESECTIONS, _PERFORMED))


def _technique(ask: _Asker, whole: Id) -> Judged:
    """RESECTION_TECHNIQUE: a snare or hot-forceps removal whose part_of names an EMR or ESD, or of its lesion."""
    return _both(_either(_part_of(ask, ask.part, whole), _same_lesion(ask, ask.part, whole)),
                 _kind_in(ask, ask.part, _TECHNIQUES, rq.FactKey.ACT_PART),
                 _whole(ask, ask.part, whole, _RESECTIONS, _PERFORMED))


def _stent(ask: _Asker, whole: Id) -> Judged:
    """STENT_INCLUDED (D45): an ERCP sphincterotomy or dilation beside a stent placement or exchange of its duct."""
    return _both(_same_duct(ask, ask.part, whole), _kind_in(ask, ask.part, _STENT_PARTS, rq.FactKey.ACT_PART),
                 _family_in(ask, ask.part, _ERCP), _whole(ask, ask.part, whole, _STENTS, _PERFORMED))


def _adjunct(ask: _Asker, whole: Id) -> Judged:
    """PROCEDURAL_ADJUNCT (D30, D79): a bleeding control, ablation, clip or injection whose part_of names an act, or
    that treats bleeding the whole (any event of the session) caused; the whole performed or begun. v1's same-lesion
    arm is possible only (_lesion_adjunct)."""
    by_part = _both(_part_of(ask, ask.part, whole), _whole(ask, ask.part, whole, _ACT_WHOLES, _POSITIVE))
    by_cause = _both(_caused_by(ask, ask.part, whole), _whole(ask, ask.part, whole, None, _POSITIVE))
    return _both(_either(by_part, by_cause, _lesion_adjunct(ask, whole)),
                 _kind_in(ask, ask.part, _ADJUNCTS, rq.FactKey.ACT_PART))


def _lesion_adjunct(ask: _Asker, whole: Id) -> Judged:
    """v1's D30 same-lesion arm ("by its verified part_of or the removal's lesion"), built fail-closed (the module
    docstring; the step's NOTES, question DQ1): a part of v1's adjunct kinds (a catalogue kind ablation or bleeding
    control, relations.PROCEDURAL_ADJUNCTS; a clip or an injection whose purpose may be hemostasis included) with a
    lesion stated, beside a removal performed or begun (today, in its session) with a lesion stated, is POSSIBLY that
    removal's adjunct unless the two lesions are established apart or its own facts establish otherwise (_not_adjunct):
    U, asked as its part_of (act_part, rank 17) - never T, since whether one lesion alone bundles it is the design's to
    say, and a part_of or cause_event naming the removal bundles it by those arms. A lesion stated on neither act, or on
    one only, relates nothing here (P13: a target the document does not state is left empty). Monotone under 9.4's
    weakenings: none makes a stated lesion silent, and every exit to F reads an established fact."""
    if any(_pure_silent(facts_.fact(ask.R, subject, _A.TARGET_LESION)) for subject in (ask.part, whole)) or \
            _not_adjunct(ask.R, ask.part, whole):
        return _FALSE
    found = _both(_ckind_in(ask, ask.part, _LESION_ADJUNCTS, rq.FactKey.ACT_PART), _same_lesion(ask, ask.part, whole),
                  _whole(ask, ask.part, whole, _REMOVALS, _POSITIVE))
    if found.truth is Truth.F:
        return _FALSE
    asked = ask.doubt(ask.part, _A.PART_OF, facts_.fact(ask.R, ask.part, _A.PART_OF), rq.FactKey.ACT_PART)
    return Judged(Truth.U, asked.doubts + found.doubts, None, found.conflicts)


def _not_adjunct(R: FactSet, part: Id, whole: Id) -> bool:
    """The part's own ESTABLISHED facts say it is not the whole's adjunct: its part_of negated naming the whole; its
    cause established as no act of this session (supported pre_existing_lesion, spontaneous, earlier_procedure or
    other; or act_of_this_session negated: 4.3's CAUSE row decides such a bleeding control); or caused by an act of
    this session established as another event (cause_event supported naming another)."""
    part_of, cause = facts_.fact(R, part, _A.PART_OF), facts_.fact(R, part, _A.CAUSE)
    if part_of.result is Result.NEGATED and part_of.value == whole:
        return True
    if cause.result is Result.NEGATED:
        return cause.value is Cause.ACT_OF_THIS_SESSION
    if cause.result is not Result.SUPPORTED:
        return False
    if cause.value is not Cause.ACT_OF_THIS_SESSION:
        return True
    event = facts_.fact(R, part, _A.CAUSE_EVENT)
    return event.result is Result.SUPPORTED and event.value != whole


def _biopsy(ask: _Asker, whole: Id) -> Judged:
    """BIOPSY_OF_REMOVED_LESION (C-2, D196): a biopsy of the lesion a removal removed, single or in a shared unit."""
    return _both(_same_lesion(ask, ask.part, whole), _kind_in(ask, ask.part, _BIOPSIES, rq.FactKey.ACT_PART),
                 _whole(ask, ask.part, whole, _REMOVALS, _PERFORMED), _single_or_shared(ask, ask.part, whole))


def _drainage(ask: _Asker, whole: Id) -> Judged:
    """DRAINAGE_STEP (G3, D171, D177): a fine-needle aspiration whose part_of names a drainage, or of its lesion; the
    drainage performed or begun."""
    return _both(_either(_part_of(ask, ask.part, whole), _same_lesion(ask, ask.part, whole)),
                 _kind_in(ask, ask.part, _ASPIRATIONS, rq.FactKey.ACT_PART),
                 _whole(ask, ask.part, whole, _DRAINAGES, _POSITIVE))


_PART_RULES: tuple[tuple[Rule, Callable[[_Asker], Judged]], ...] = (
    (Rule.CLIP, _rule_clip), (Rule.CANNULATION, _rule_cannulation), (Rule.FAMILY_BUNDLED, _rule_family))
_WHOLE_RULES: tuple[tuple[Rule, Callable[[_Asker, Id], Judged]], ...] = (
    (Rule.LIFT_INJECTION, _lift), (Rule.RESECTION_TECHNIQUE, _technique), (Rule.STENT_INCLUDED, _stent),
    (Rule.PROCEDURAL_ADJUNCT, _adjunct), (Rule.BIOPSY_OF_REMOVED_LESION, _biopsy), (Rule.DRAINAGE_STEP, _drainage))
# The part kinds each whole rule can apply to (a quick skip; the rule itself judges the kind).
_RULE_PARTS: Mapping[Rule, frozenset[Kind]] = MappingProxyType({
    Rule.LIFT_INJECTION: _LIFTS_BY_PART, Rule.RESECTION_TECHNIQUE: _TECHNIQUES, Rule.STENT_INCLUDED: _STENT_PARTS,
    Rule.PROCEDURAL_ADJUNCT: _ADJUNCTS, Rule.BIOPSY_OF_REMOVED_LESION: _BIOPSIES,
    Rule.DRAINAGE_STEP: _ASPIRATIONS})


@dataclass(frozen=True, slots=True)
class Bundle:
    """One bundling of ``part`` (module docstring): into ``whole`` (None for a rule that needs none: the examination's
    or the family's own) by ``rule``; ``truth`` T (established) or U (possible, never F); ``attribute`` the fact that
    decided a T; ``doubts`` the facts a U rests on."""
    part: Id
    whole: Id | None
    rule: Rule
    truth: Truth
    attribute: Attribute | None
    doubts: tuple[Doubt, ...]
    conflicts: tuple[HeldFact, ...] = ()


@dataclass(frozen=True, slots=True)
class Verdict:
    """An act's bundling (4.3's bundling row): ``truth`` T (its own act), U (its bundling in doubt) or F (bundled);
    ``bundles`` every T or U bundle; ``held`` the witnesses a code supported only by it carries (module docstring);
    ``contradicted`` whether a contradiction keeps it from ever being bundled (D3)."""
    truth: Truth
    bundles: tuple[Bundle, ...]
    held: tuple[HeldFact, ...]
    contradicted: bool


def _ordered(spans: Iterable[Span]) -> tuple[Span, ...]:
    return tuple(sorted(set(spans)))


def _anchor_units(R: FactSet, event: Id | None) -> tuple[Span, ...]:
    if event is None:
        return ()
    anchor = R.anchors.get(event)
    return anchor.units if anchor is not None else ()


def _cause(found: Fact, rule: str) -> str:
    """The cause of a witness resting on ``found`` (FINAL-V2 4.4): reading_unknown (silent or doubted),
    reading_contradicted, appraisal:<verdict or coherence>, unestablished:<reason>; ``coding_rule:<rule>`` when the fact
    is established (the doubt is the rule's own)."""
    if found.result is Result.UNKNOWN:
        return READING_UNKNOWN
    if found.result is Result.CONTRADICTED:
        return READING_CONTRADICTED
    if found.result is not Result.UNRESOLVED:
        return f'coding_rule:{rule}'
    reason = found.reasons[0] if found.reasons else None
    if reason is None:
        return UNESTABLISHED
    appraisal = APPRAISAL_CAUSES.get(reason)
    if appraisal is not None:
        return f'appraisal:{appraisal.value}'
    return f'{UNESTABLISHED}:{reason.value}'


def _reason(found: Fact) -> Reason | None:
    return found.reasons[0] if found.reasons and not facts_.established(found) else None


def witness(found: Fact, attribute: Attribute | None, subject: Id | None, key: rq.FactKey, kind: Kind,
            spans: tuple[Span, ...], rule: str) -> HeldFact:
    """A QUESTION resting on ``found`` (4.8): rank 1 ``conflict:<kind>`` when it is contradicted; rank 2
    performed_status when it is a doubted status; else ``key`` at its RANK row."""
    if found.result is Result.CONTRADICTED:
        item = rq.Item(rq.Rank.CONFLICT, rq.FactKey.CONFLICT)
        name = rq.fact_key(rq.FactKey.CONFLICT, kind)
    elif attribute is _A.STATUS and _doubted(found):
        item = rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS)
        name = rq.fact_key(item.fact)
    else:
        item = _ITEM_OF[key]
        name = rq.fact_key(item.fact)
    assert item.rank is not None
    return HeldFact(fact=name, attribute=attribute, subject=subject, result=found.result, kind=ItemKind.QUESTION,
                    cause=_cause(found, rule), reason=_reason(found), spans=spans, rank=item.rank.value)


# The RANK row each key a rule raises is asked at (4.8).
_ITEM_OF: Mapping[rq.FactKey, rq.Item] = MappingProxyType({
    rq.FactKey.ACT_PART: rq.Item(rq.Rank.BUNDLING, rq.FactKey.ACT_PART),
    rq.FactKey.ACT_CAUSE: rq.Item(rq.Rank.BUNDLING, rq.FactKey.ACT_CAUSE),
    rq.FactKey.ACT_TARGET: rq.Item(rq.Rank.BUNDLING, rq.FactKey.ACT_TARGET),
    rq.FactKey.PERFORMED_STATUS: rq.Item(rq.Rank.STATUS, rq.FactKey.PERFORMED_STATUS),
    rq.FactKey.EVENT_ENTRY: rq.Item(rq.Rank.ENTRY, rq.FactKey.EVENT_ENTRY),
    rq.FactKey.EVENT_TIME: rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME),
    rq.FactKey.EVENT_PERFORMER: rq.Item(rq.Rank.PERFORMER, rq.FactKey.EVENT_PERFORMER),
    rq.FactKey.PROCEDURE: rq.Item(rq.Rank.PROCEDURE, rq.FactKey.PROCEDURE),
    rq.FactKey.ACT_METHOD: rq.Item(rq.Rank.METHOD, rq.FactKey.ACT_METHOD),
})
_BUNDLED_ITEM = rq.Item(rq.Rank.BUNDLED, rq.FactKey.PERFORMED_STATUS)


# --- the reader: one FactSet's per-event readings, each computed once -------------------------------------------------


class Reader:
    """One FactSet's per-event readings for the functions below (the pairs of 4.5, the bundles, the verdicts, the
    witnesses), each computed once per Reader. Read-only: the FactSet is frozen, and nothing here changes it. Make one
    per FactSet and pass it where a function takes ``reader``; never share one across FactSets."""

    __slots__ = ('R', 'order', '_pairs', '_unlisted', '_bundles', '_verdicts', '_conflicts')

    def __init__(self, R: FactSet) -> None:
        self.R = R
        self.order: Mapping[Id, int] = MappingProxyType({event: index for index, event in enumerate(R.events)})
        self._pairs: dict[Id, tuple[pairing.Pair, ...]] = {}
        self._unlisted: dict[Id, tuple[pairing.UnlistedPair, ...]] = {}
        self._bundles: dict[Id, tuple[Bundle, ...]] = {}
        self._verdicts: dict[Id, Verdict] = {}
        self._conflicts: dict[Id, tuple[HeldFact, ...]] = {}

    @classmethod
    def of(cls, value: Reader | FactSet) -> Reader:
        return value if isinstance(value, Reader) else cls(value)

    def pairs(self, event: Id) -> tuple[pairing.Pair, ...]:
        """pairing.pairs_of: every statement paired with ``event``, with its relation."""
        if event not in self._pairs:
            self._pairs[event] = pairing.pairs_of(self.R, event)
        return self._pairs[event]

    def unlisted_pairs(self, event: Id) -> tuple[pairing.UnlistedPair, ...]:
        """pairing.unlisted_pairs: every unlisted denial or doubt paired with ``event`` (3.2.6 rule 4)."""
        if event not in self._unlisted:
            self._unlisted[event] = pairing.unlisted_pairs(self.R, event)
        return self._unlisted[event]

    def conflicts(self, event: Id) -> tuple[HeldFact, ...]:
        """The rank-1 conflicts on ``event`` (4.8 rank 1): each of its own required facts that is contradicted (4.3
        rows 1-6), and each statement that contradicts it (pairing's CONTRADICTION), quoting both."""
        if event not in self._conflicts:
            R, out = self.R, []
            kind = _kind_of(R, event)
            own = _anchor_units(R, event)
            for attribute in _OWN_FACTS:
                found = facts_.fact(R, event, attribute)
                if found.result is Result.CONTRADICTED:
                    out.append(witness(found, attribute, event, rq.FactKey.PERFORMED_STATUS, kind,
                                       _ordered(own + found.spans), 'conflict'))
            for pair in self.pairs(event):
                if pair.relation is pairing.Relation.CONTRADICTION:
                    named = kind if kind in pair.kinds else min(pair.kinds, key=list(Kind).index, default=kind)
                    status = facts_.fact(R, event, _A.STATUS)
                    out.append(HeldFact(fact=rq.fact_key(rq.FactKey.CONFLICT, named), attribute=_A.STATUS,
                                        subject=event, result=status.result, kind=ItemKind.QUESTION,
                                        cause=RELATION_CONTRADICTION, reason=None, spans=pair.spans,
                                        rank=rq.Rank.CONFLICT.value))
            self._conflicts[event] = tuple(out)
        return self._conflicts[event]

    def bundles(self, event: Id) -> tuple[Bundle, ...]:
        """Every T or U bundle of ``event`` (module docstring), in Rule's order, then the wholes' order. An event that
        cannot be an act today (its status established as not performed and not begun) is part of nothing."""
        if event not in self._bundles:
            self._bundles[event] = self._compute_bundles(event)
        return self._bundles[event]

    def _compute_bundles(self, event: Id) -> tuple[Bundle, ...]:
        R = self.R
        ask = _Asker(R, event, self)
        if _status_in(ask, event, _POSITIVE, rq.FactKey.ACT_PART).truth is Truth.F:
            return ()
        out: list[Bundle] = []
        for rule, judge in _PART_RULES:
            found = judge(ask)
            if found.truth is not Truth.F:
                out.append(Bundle(event, None, rule, found.truth, found.attribute, found.doubts, found.conflicts))
        kinds = may_be(facts_.fact(R, event, _A.KIND))
        for rule, judge_whole in _WHOLE_RULES:
            if not kinds & _RULE_PARTS[rule]:
                continue
            for whole in R.events:
                if whole == event:
                    continue
                found = judge_whole(ask, whole)
                if found.truth is not Truth.F:
                    out.append(Bundle(event, whole, rule, found.truth, found.attribute, found.doubts,
                                      found.conflicts))
        return tuple(out)

    def verdict(self, event: Id) -> Verdict:
        """The act's bundling verdict (module docstring; D3: a contradicted act is never F)."""
        if event not in self._verdicts:
            self._verdicts[event] = self._compute_verdict(event)
        return self._verdicts[event]

    def _compute_verdict(self, event: Id) -> Verdict:
        """The verdict and its witnesses (module docstring). F (some bundle T): the T bundles' explanations only - a
        question about ANOTHER possible whole could never release an act already established as part of one (the
        bundling is an OR over its bundles; refute-4c-r1 B's shape). U: every U bundle's witnesses, a contradicted
        act's conflicts first (D3: its T bundles explain nothing)."""
        R = self.R
        bundles = self.bundles(event)
        conflicts = self.conflicts(event)
        if not bundles:  # a contradicted act with nothing to bundle into has nothing to hide either
            return Verdict(Truth.T, (), (), bool(conflicts))
        established = [bundle for bundle in bundles if bundle.truth is Truth.T]
        if established and not conflicts:
            return Verdict(Truth.F, bundles, tuple(dict.fromkeys(
                self._explanation(bundle, self._spans(event, bundle)) for bundle in established)), False)
        held: list[HeldFact] = list(conflicts)
        for bundle in bundles:
            if bundle.truth is Truth.U:
                spans = self._spans(event, bundle)
                held += list(bundle.conflicts)
                held += [witness(doubt.fact, doubt.attribute, doubt.subject, doubt.key, doubt.kind, spans,
                                 bundle.rule.value) for doubt in bundle.doubts]
        return Verdict(Truth.U, bundles, tuple(dict.fromkeys(held)), bool(conflicts))

    def _spans(self, event: Id, bundle: Bundle) -> tuple[Span, ...]:
        """What a bundle's item quotes: the part's anchor and the whole's (4.3: "naming the whole")."""
        return _ordered(_anchor_units(self.R, event) + _anchor_units(self.R, bundle.whole))

    def _explanation(self, bundle: Bundle, spans: tuple[Span, ...]) -> HeldFact:
        """A T bundle's EXPLANATION (4.3: "bundled: held (explanation naming the whole)"; 4.8 rank 18)."""
        found = facts_.fact(self.R, bundle.part, bundle.attribute) if bundle.attribute is not None and \
            bundle.attribute in _SINGLE_EVENT_FACTS else None
        return HeldFact(fact=rq.fact_key(_BUNDLED_ITEM.fact), attribute=bundle.attribute, subject=bundle.part,
                        result=found.result if found is not None else Result.SUPPORTED, kind=ItemKind.EXPLANATION,
                        cause=f'coding_rule:{bundle.rule.value}', reason=None, spans=spans,
                        rank=rq.Rank.BUNDLED.value)


# The single-valued event facts an explanation can rest on (its deciding attribute).
_SINGLE_EVENT_FACTS: frozenset[Attribute] = frozenset({_A.KIND, _A.PART_OF, _A.CAUSE, _A.CAUSE_EVENT,
                                                       _A.TARGET_LESION, _A.TARGET_DUCT, _A.SESSION, _A.STATUS,
                                                       _A.PURPOSE, _A.DATE_RELATION})


def possibly_today(R: FactSet, event: Id) -> bool:
    """v1's possibly_current (D62, D68, D98) over facts: whether ``event`` may be of the date of service - its effective
    date relation not established as another date (supported earlier_date or later_date, or on_date_of_service
    negated), and on_date_of_service among what it leaves open."""
    ask = _Asker(R, event)
    return _enum_in(ask, event, _A.DATE_RELATION, _TODAY, DateRelation, rq.FactKey.EVENT_TIME).truth is not Truth.F


def bundles(R: FactSet | Reader, event: Id) -> tuple[Bundle, ...]:
    """Every T or U bundle of ``event`` (module docstring)."""
    return Reader.of(R).bundles(event)


def verdict(R: FactSet | Reader, event: Id) -> Verdict:
    """``event``'s bundling verdict (module docstring)."""
    return Reader.of(R).verdict(event)


def bundled(R: FactSet | Reader, event: Id) -> Bundle | None:
    """v1's bundled_reason over facts: the first established (T) bundle of ``event`` - None when it has none, and
    always None for a contradicted act (D3: never bundled out of its question)."""
    found = Reader.of(R).verdict(event)
    if found.truth is not Truth.F:
        return None
    return next(bundle for bundle in found.bundles if bundle.truth is Truth.T)


def bundling_doubts(R: FactSet | Reader, event: Id) -> tuple[Bundle, ...]:
    """v1's bundling_doubt over facts: the U bundles of ``event`` - its bundling in doubt, asked (act_part, act_cause,
    act_target), never READY."""
    return tuple(bundle for bundle in Reader.of(R).bundles(event) if bundle.truth is Truth.U)


def drainage_step(R: FactSet | Reader, event: Id) -> Bundle | None:
    """v1's drainage_step (D171 (1), D177 (3)) over facts: the first bundle of ``event`` into a drainage it may be the
    step of (T: established; U: possible), None when it is the step of none. engine/assess.py's EUS code checks read
    it (step 5a)."""
    return next((bundle for bundle in Reader.of(R).bundles(event) if bundle.rule is Rule.DRAINAGE_STEP), None)


def bundling(code: str, supporting: Sequence[Id], R: FactSet | Reader) -> tuple[HeldFact, ...]:
    """4.3's bundling row for ``code`` (4.4's ``held_facts += bundling(code, supporting, R)``): () when a supporting act
    is its own (verdict T), or none is given; else every supporting act's witnesses (module docstring). The bundling
    of an act does not depend on the code reading it (v1's bundled_reason took none); ``code`` is 4.4's interface."""
    reader = Reader.of(R)
    verdicts = [reader.verdict(event) for event in dict.fromkeys(supporting)]
    if not verdicts or any(found.truth is Truth.T for found in verdicts):
        return ()
    return tuple(dict.fromkeys(item for found in verdicts for item in found.held))


# --- sessions (4.7: from the sessions table; S3 6.2) ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Session:
    """One session of the FactSet as coverage reads it (module docstring): ``kind`` its family when established;
    ``events`` its members in pass 1's order; ``examinations`` its done examinations; ``possible`` its possible ones
    (D62, D87: doubts, never facts); ``event`` its one examination; ``unresolved``, ``done``, ``incomplete``; ``part_of``
    the session it is the included portion of (C3, C-4); ``possibly_part_of`` the session it may be (D70)."""
    id: Id
    kind: SessionKind | None
    events: tuple[Id, ...] = ()
    examinations: tuple[Id, ...] = ()
    possible: tuple[Id, ...] = ()
    event: Id | None = None
    unresolved: bool = False
    done: bool = False
    incomplete: bool = False
    part_of: Id | None = None
    possibly_part_of: Id | None = None


def filed(R: FactSet, event: Id) -> Id | None:
    """The session ``event`` is filed under: its session fact's claimed id in any state but negated (v1's family, the
    one session event_coding lists it in); None for an empty slot or a negated one."""
    found = facts_.fact(R, event, _A.SESSION)
    return found.value if isinstance(found.value, Id) and found.result is not Result.NEGATED else None


def possible_members(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The events that may be in ``session``, in pass 1's order (sessions_of): its members, and every event whose
    session fact leaves it open - an empty slot (P12: "Leave it empty when the document does not say which"), a doubt's
    reading, a contradiction's side, a negation of another session, an id naming no session (4.2: a doubt is never an
    absence). What event_coding's doubted entries, the unestablished count and D70 read."""
    return tuple(event for event in R.events if session in sessions_of(R, event))


def _done(R: FactSet, event: Id) -> bool:
    """4.3 rows 2-5 supported (reading.done: "done = 4.3 rows 2-5", 4.7) and the kind supported: a done event."""
    return reading.done(reading.Reading(R), event) and facts_.fact(R, event, _A.KIND).result is Result.SUPPORTED


def _possibly_done(R: FactSet, event: Id) -> bool:
    """Each of 4.3 rows 2-5 may hold (by possibly): status performed or begun, the date of service, the documenting
    team, the documenting clinician's entry."""
    status = facts_.fact(R, event, _A.STATUS)
    return ((facts_.possibly(status, Status.PERFORMED) or facts_.possibly(status, Status.ATTEMPTED_NOT_COMPLETED))
            and possibly_today(R, event)
            and _may_hold(facts_.fact(R, event, _A.PERFORMER), Performer.DOCUMENTING_TEAM)
            and _may_hold(facts_.fact(R, event, _A.ENTRY), Owner.DOCUMENTING_CLINICIAN))


def _may_hold(found: Fact, wanted: Enum) -> bool:
    """Whether ``found`` leaves ``wanted`` open (module docstring's reading of a fact): supported, its value; negated,
    every other value; not established, facts.possibly's."""
    if found.result is Result.SUPPORTED:
        return found.value == wanted
    if found.result is Result.NEGATED:
        return found.value != wanted
    return facts_.possibly(found, wanted)


def done_examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The session's done examinations (D69-D71 over facts), in pass 1's order: kind supported examination, session
    supported, done (rows 2-5 supported). Never D62's possible ones."""
    return tuple(event for event in R.events
                 if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(facts_.fact(R, event, _A.SESSION), session) and _done(R, event))


def possible_examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """D62, D87: the events that may be the session's examination and are not done: kind possibly the examination,
    session possibly this one, each of rows 2-5 possibly holding."""
    done = set(done_examinations(R, session))
    return tuple(event for event in R.events if event not in done
                 and _may_hold(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and session in sessions_of(R, event) and _possibly_done(R, event))


def _session_kind(R: FactSet, session: Id) -> SessionKind | None:
    found = facts_.fact(R, session, _A.KIND)
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, SessionKind) else None


def _tract_upper(R: FactSet, session: Id) -> Truth:
    """C-4's upper EUS: the session's tract supported upper (T); supported lower (F); otherwise (pancreatobiliary,
    negated or not established) possibly an upper one (U)."""
    found = facts_.fact(R, session, _A.TRACT)
    if found.result is Result.SUPPORTED:
        return Truth.T if found.value is Tract.UPPER else Truth.F if found.value is Tract.LOWER else Truth.U
    if found.result is Result.NEGATED and found.value is Tract.UPPER:
        return Truth.F
    return Truth.U


def sessions(R: FactSet) -> dict[Id, Session]:
    """{session id: Session} of every session of the FactSet, in pass 1's order (module docstring)."""
    found: dict[Id, Session] = {}
    for session in R.sessions:
        members = tuple(event for event in R.events if filed(R, event) == session)
        exams = done_examinations(R, session)
        possible = possible_examinations(R, session)
        established = [event for event in members if facts_.holds(facts_.fact(R, event, _A.SESSION), session)]
        found[session] = Session(
            id=session, kind=_session_kind(R, session), events=members, examinations=exams, possible=possible,
            event=exams[0] if len(exams) == 1 and not possible else None,
            unresolved=len(exams) + len(possible) >= 2,
            done=any(_done(R, event) for event in established),
            incomplete=bool(exams) and all(facts_.holds(facts_.fact(R, event, _A.STATUS),
                                                        Status.ATTEMPTED_NOT_COMPLETED) for event in exams))
    for session, record in list(found.items()):
        part_of, possibly = _part_of_session(R, found, record)
        if part_of is not None or possibly is not None:
            found[session] = _replace(record, part_of, possibly)
    return found


def _replace(record: Session, part_of: Id | None, possibly: Id | None) -> Session:
    return Session(id=record.id, kind=record.kind, events=record.events, examinations=record.examinations,
                   possible=record.possible, event=record.event, unresolved=record.unresolved, done=record.done,
                   incomplete=record.incomplete, part_of=part_of, possibly_part_of=None if part_of else possibly)


def _part_of_session(R: FactSet, found: Mapping[Id, Session], record: Session) -> tuple[Id | None, Id | None]:
    """(part_of, possibly_part_of) of ``record`` (module docstring): C3 by its part_of_session, C-4 and D70 structurally
    for a done EGD beside an EUS session."""
    stated = facts_.fact(R, record.id, _A.PART_OF_SESSION)
    whole = _supported_id(stated)
    if whole is not None and whole != record.id and whole in found and not (
            record.kind is not None and found[whole].kind is record.kind):
        return whole, None
    possibly: Id | None = None
    if not facts_.established(stated) and not _pure_silent(stated):
        possibly = next((other for other in found if other != record.id and facts_.possibly(stated, other)), None)
    if record.kind is SessionKind.EGD and record.done and len(record.examinations) == 1:  # v1's ``own``
        for other in found.values():
            # C-4 reads the EUS's kind established; D70 by possibly (4.7): a kind not established that leaves the EUS
            # open makes the EGD possibly its endoscopic portion, never part of nothing
            if other.id == record.id or not _session_kind_may_be(facts_.fact(R, other.id, _A.KIND), SessionKind.EUS):
                continue
            upper = _tract_upper(R, other.id)
            if other.kind is SessionKind.EUS and other.done and upper is Truth.T:
                return other.id, None
            if upper is not Truth.F and (other.done or other.possible or any(
                    _possibly_done(R, event) for event in possible_members(R, other.id))):
                possibly = possibly or other.id
    return None, possibly


def session_of(sessions_: Mapping[Id, Session], family: SessionKind, events: Iterable[Id] = ()) -> Id | None:
    """v1's session_of: the session a code of ``family`` is matched to - the done session of that family holding its
    ``events`` (its supporting acts) when one does, else the first done session of the family; None when none."""
    done = [session for session in sessions_.values() if session.kind is family and session.done]
    wanted = set(events)
    holding = [session for session in done if wanted & set(session.events)]
    chosen = holding or done
    return chosen[0].id if chosen else None


# --- reportable and doubted (v1's shapes; 4.7) -----------------------------------------------------------------------


def session_families(R: FactSet, session: Id) -> frozenset[SessionKind]:
    """The families ``session`` may be of: its kind when supported; every other kind when negated; facts.possibly's
    otherwise (every kind for an empty slot)."""
    found = facts_.fact(R, session, _A.KIND)
    return frozenset(wanted for wanted in SessionKind if _session_kind_may_be(found, wanted))


def _families(R: FactSet, event: Id) -> frozenset[SessionKind]:
    """The families ``event`` may be of: its session's when established; when its session is established and that
    session's kind is not, the kinds that session may be; when its own session fact is not established, EVERY family
    (4.2: "every kind, when the session is not established either" - its claimed session may be the wrong one: settle's
    K2 demotes the session of an act its family cannot hold, D191, as a PEG filed under a colonoscopy, which no reading
    of that session would ever list); the kinds of the sessions a negated session leaves otherwise."""
    family = facts_.session_family(R, event)
    if family is not None:
        return frozenset({family})
    if not facts_.established(facts_.fact(R, event, _A.SESSION)):
        return frozenset(SessionKind)
    out: set[SessionKind] = set()
    for session in sessions_of(R, event):
        out |= session_families(R, session)
    return frozenset(out) if out else frozenset(SessionKind)


def reportable(R: FactSet | Reader, event: Id) -> bool:
    """7.8's reportable over facts: done (4.3 rows 2-5 supported), status supported performed, kind supported, session
    and its kind supported, its catalogue kind (with its supported purpose: a hemostatic clip is a bleeding control)
    one of that family's reportable kinds (reportable_kinds), and not bundled."""
    reader = Reader.of(R)
    R_ = reader.R
    kind = _claimed_catalogue_kind(R_, event)
    family = facts_.session_family(R_, event)
    return (family is not None and kind is not None and _done(R_, event)
            and facts_.holds(facts_.fact(R_, event, _A.STATUS), Status.PERFORMED)
            and kind in reportable_kinds(family) and reader.verdict(event).truth is not Truth.F)


def _positive_here(R: FactSet, event: Id) -> bool:
    """Possibly performed or begun (pairing.positive), and neither its date relation nor its performer established as
    another (doubted's frame, v1's _stated_here)."""
    return pairing.positive(R, event) and not pairing.other_date(R, event) and not pairing.other_performer(R, event)


def _may_be_reportable(R: FactSet, event: Id, families: frozenset[SessionKind]) -> bool:
    """Whether ``event`` may be of a reportable kind of one of ``families`` (the families it may be of, or one
    session's), or is D117's removal umbrella or D115's possible bleeding control there, or (D145) an EUS act of a
    catalogue kind the EUS entry does not list (eus_kinds)."""
    kinds = catalogue_kinds(R, event)
    for family in families:
        acts = catalogue.FAMILY_ACTS.get(family, ())
        if kinds & reportable_kinds(family):
            return True
        if Kind.REMOVAL in _claimed_kinds(R, event) and any(member in acts for member in catalogue.REMOVAL_MEMBERS):
            return True  # D117
        if family is SessionKind.EUS and any(eus_unlisted_kind(kind) for kind in eus_kinds(R, event)):
            return True  # D145
    return False


def eus_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """The kinds D137's class reads (v1's eus_unprofiled_entries read catalogue_kind, '' for an act of no catalogue
    kind): the catalogue kinds ``event`` may be (catalogue_kinds: a clip or an injection whose purpose is supported
    hemostasis is a bleeding control, one whose purpose may be hemostasis may be either) and other."""
    return catalogue_kinds(R, event) | (may_be(facts_.fact(R, event, _A.KIND)) & _OTHER)


def _claimed_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """The kinds ``event`` may be WITHOUT expanding an umbrella (D117 reads the umbrella itself)."""
    found = facts_.fact(R, event, _A.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        return frozenset({found.value})
    return frozenset(kind for kind in Kind if facts_.possibly(found, kind))


def _required_supported(R: FactSet, event: Id) -> bool:
    """4.3 rows 1-6 over one act: kind supported (no umbrella), status supported performed or begun, the date of
    service, the documenting team, the documenting clinician's entry, the session and its kind supported."""
    kind = facts_.fact(R, event, _A.KIND)
    return (kind.result is Result.SUPPORTED and isinstance(kind.value, Kind) and kind.value not in catalogue.UMBRELLAS
            and reading.done(reading.Reading.of(R), event) and facts_.session_family(R, event) is not None)


def doubted(R: FactSet | Reader, event: Id) -> bool:
    """4.7's doubted (module docstring): a possibly-positive act of a reportable kind of a family it may be of, in
    doubt."""
    reader = Reader.of(R)
    return _doubted_among(reader, event, _families(reader.R, event))


def doubted_in(R: FactSet | Reader, event: Id, session: Id) -> bool:
    """``doubted`` read in ONE session (event_coding's doubted entries; step 4d's SessionActs: "an act possibly in the
    session included"): ``session`` among those ``event`` may be in (sessions_of), and the act doubted as one of a
    reportable kind of a family that session may be of (its own session's family when established). An act whose
    session fact leaves two sessions open is doubted in each, so a weakening of that fact never drops it from the
    session it was reportable or doubted in (9.4 P-MONO at the records base_included reads)."""
    reader = Reader.of(R)
    R_ = reader.R
    if session not in sessions_of(R_, event):
        return False
    family = facts_.session_family(R_, event)
    return _doubted_among(reader, event, frozenset({family}) if family is not None else session_families(R_, session))


def _doubted_among(reader: Reader, event: Id, families: frozenset[SessionKind]) -> bool:
    """The body of ``doubted`` over ``families`` (module docstring)."""
    R_ = reader.R
    kind = facts_.fact(R_, event, _A.KIND)
    if (kind.result is Result.SUPPORTED and kind.value in _NOT_ACTS and kind.value is not Kind.REMOVAL) or \
            not _positive_here(R_, event) or not _may_be_reportable(R_, event, families):
        return False
    if Kind.REMOVAL in _claimed_kinds(R_, event):
        return True  # D117: a removal whose method is not stated may be any of them
    if _bleeding_control_in_doubt(reader, event, families):
        return True  # D115, from purpose (never words)
    if not _required_supported(R_, event):
        return True
    if any(pair.relation is not pairing.Relation.INDEPENDENT for pair in reader.pairs(event)):
        return True
    if reader.unlisted_pairs(event):
        return True
    return reader.verdict(event).truth is Truth.U


def _bleeding_control_in_doubt(reader: Reader, event: Id, families: frozenset[SessionKind]) -> bool:
    """D115 over facts: a clip or an injection whose purpose may be hemostasis and is not established, of one of
    ``families`` whose catalogue acts hold the bleeding control - unless, read as one, it is an established procedural
    adjunct."""
    R = reader.R
    purpose = facts_.fact(R, event, _A.PURPOSE)
    raw = may_be(facts_.fact(R, event, _A.KIND))
    if not raw & catalogue.HEMOSTASIS_KINDS or Kind.BLEEDING_CONTROL not in catalogue_kinds(R, event) or \
            purpose.result is Result.SUPPORTED:
        return False
    if not any(Kind.BLEEDING_CONTROL in catalogue.FAMILY_ACTS.get(family, ()) for family in families):
        return False
    return not any(bundle.truth is Truth.T and bundle.rule is Rule.PROCEDURAL_ADJUNCT
                   for bundle in reader.bundles(event))


def eus_unlisted(R: FactSet | Reader, event: Id) -> tuple[bool, bool]:
    """D137 and D145 over facts: (reportable, doubted) for an act of the EUS session (its session and that session's
    kind supported) that may be of a CATALOGUE kind the EUS entry does not list (eus_kinds; v1's
    eus_unprofiled_entries: a hemostatic clip or injection is a bleeding control, which the EUS lists not) - reportable
    when that kind is established (its kind supported, its catalogue kind one: a clip or an injection with its purpose
    established) and the act done, performed and not bundled; doubted when begun, or in doubt (``doubted``: a kind or a
    purpose not established, a relation, a bundling in doubt) and not reportable (D156 (3): never both). (False,
    False) for any other event: an act only possibly in an EUS session is doubted there by ``doubted_in`` (D145's arm
    of _may_be_reportable)."""
    reader = Reader.of(R)
    R_ = reader.R
    kinds = eus_kinds(R_, event)
    if facts_.session_family(R_, event) is not SessionKind.EUS or not any(eus_unlisted_kind(kind) for kind in kinds):
        return False, False
    one = facts_.fact(R_, event, _A.KIND).result is Result.SUPPORTED and len(kinds) == 1
    status = facts_.fact(R_, event, _A.STATUS)
    done = one and _done(R_, event) and reader.verdict(event).truth is not Truth.F
    listed = done and facts_.holds(status, Status.PERFORMED)
    begun = done and facts_.holds(status, Status.ATTEMPTED_NOT_COMPLETED)
    return listed, not listed and (begun or doubted(reader, event))


def unlisted_acts(R: FactSet, session: Id | None = None) -> tuple[tuple[int, UnlistedStatement], ...]:
    """3.2.6 rule 3: (index, entry) of each kept unlisted ACT that names a session - of ``session`` when given - each a
    synthetic doubted act of that session."""
    return tuple((index, entry) for index, entry in enumerate(R.unlisted)
                 if entry.what is UnlistedWhat.ACT and entry.session is not None
                 and (session is None or entry.session == session))


# --- coverage and the unresolved items (v1's reconcile over sessions) --------------------------------------------------


@dataclass(frozen=True, slots=True)
class Counted:
    """A counted, decidable code as coverage reads it: its key, code, family and the events its decision read (its
    supporting events, then the candidates its item is about)."""
    key: str
    code: str
    family: SessionKind
    supporting: tuple[Id, ...] = ()
    read: tuple[Id, ...] = ()


@unique
class ItemReason(Enum):
    """An unresolved item's reason (v1's: completeness['unresolved_items'][].reason)."""
    NO_PROPOSAL = 'no_proposal'
    NOT_COVERED = 'not_covered'
    COVERAGE_UNKNOWN = 'coverage_unknown'
    UNSUPPORTED = 'unsupported'
    IN_DOUBT = 'in_doubt'


@unique
class Detail(Enum):
    """Which of v1's item sentences an item is (step 3c words it): a session with no proposal, documented as performed
    or as incomplete; an act no profile accounts for, done, or attempted or in doubt; an act of a kind no code of its
    service accounts for; read under another service, not placed at its site or with no such service; an act not
    covered; an act CPT Studio could not confirm as done at this encounter."""
    SESSION_PERFORMED = 'session_performed'
    SESSION_INCOMPLETE = 'session_incomplete'
    NO_PROFILE = 'no_profile'
    ATTEMPTED_OR_IN_DOUBT = 'attempted_or_in_doubt'
    NO_CODE_OF_SERVICE = 'no_code_of_service'
    READ_UNDER_NOT_PLACED = 'read_under_not_placed'
    READ_UNDER_NO_SERVICE = 'read_under_no_service'
    NOT_COVERED = 'not_covered'
    IN_DOUBT = 'in_doubt'


@dataclass(frozen=True, slots=True)
class Item:
    """One unresolved item (v1's _item, text-free): the session (None for an event filed under none) and its family,
    the act kind (None for a session's own item), the reason and which sentence (Detail), the events and the unlisted
    statements (their index in FactSet.unlisted) it lists, and the evidence spans (at most two, v1's)."""
    session: Id | None
    family: SessionKind | None
    act: Kind | None
    reason: ItemReason
    detail: Detail
    events: tuple[Id, ...]
    evidence: tuple[Span, ...]
    unlisted: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class BundledAct:
    """An act listed as part of another (v1's completeness['bundled'] entry): its session, the act, its kind, the rule
    (None when it is read under another service: READ_UNDER) and the whole it is part of (None for a rule that names
    none)."""
    session: Id | None
    event: Id
    act: Kind
    rule: Rule | None
    whole: Id | None


@dataclass(frozen=True, slots=True)
class InDoubt:
    """What an in_doubt item's service question is about: an event, or a kept unlisted act (its index)."""
    event: Id | None = None
    unlisted: int | None = None


@dataclass
class Coverage:
    """reconcile's result (v1's Coverage): the unresolved items, the bundled acts, the counted codes by session, the
    sessions done with no proposal and not listed, the unestablished count, each in_doubt item with what its question
    is about, and the count of kept unlisted statements (3.2.6 rule 1)."""
    unresolved: list[Item] = field(default_factory=list)
    bundled: list[BundledAct] = field(default_factory=list)
    covered: dict[Id, list[str]] = field(default_factory=dict)
    not_listed: list[Session] = field(default_factory=list)
    unestablished: int = 0
    in_doubt: list[tuple[Item, InDoubt]] = field(default_factory=list)
    unlisted: int = 0


def inclusion_asks_no_code(sessions_: Mapping[Id, Session], session: Session, counted: Sequence[Counted]) -> bool:
    """v1's inclusion_asks_no_code over sessions: a session read as included in another asks for no code of its own
    while that other session has no counted code, or when one of its counted codes includes the examination."""
    including = sessions_.get(session.part_of) if session.part_of is not None else None
    if including is None or including.kind is None or session.kind is None:
        return False
    codes = [item.code for item in counted if item.family is including.kind]
    return not codes or any(catalogue.includes_examination(code, session.kind) for code in codes)


def _evidence(R: FactSet, events: Iterable[Id]) -> tuple[Span, ...]:
    return _ordered(span for event in events for span in _anchor_units(R, event))[:2]


def _claimed_catalogue_kind(R: FactSet, event: Id) -> Kind | None:
    """The catalogue kind of ``event``'s claimed kind in any state with its SUPPORTED purpose (v1's catalogue_kind);
    None for no kind or kind other."""
    kind = facts_.fact(R, event, _A.KIND).value
    if not isinstance(kind, Kind):
        return None
    purpose = facts_.fact(R, event, _A.PURPOSE)
    return catalogue.catalogue_kind(kind, purpose.value if purpose.result is Result.SUPPORTED and isinstance(
        purpose.value, Purpose) else None)


def _codes_of(session: Session, counted: Sequence[Counted], sessions_: Mapping[Id, Session]) -> list[Counted]:
    """The counted codes a session's coverage reads: those of its family whose events it holds, or (none of their
    events in a session of the family) the first done session of the family."""
    if session.kind is None:
        return []
    out = []
    for item in counted:
        if item.family is not session.kind:
            continue
        events = set(item.supporting) | set(item.read)
        holders = [other.id for other in sessions_.values() if other.kind is item.family and events & set(other.events)]
        if session.id in holders or (not holders and session_of(sessions_, item.family) == session.id):
            out.append(item)
    return out


def reconcile(R: FactSet | Reader, counted: Sequence[Counted], *, procedure_day: bool,
              sessions_: Mapping[Id, Session] | None = None) -> Coverage:
    """The unresolved items, bundled acts and covered sessions for the counted codes (v1's reconcile over facts; the
    module docstring). ``procedure_day``: a procedure done on the date of service (combination's, step 4d)."""
    reader = Reader.of(R)
    R_ = reader.R
    sessions_ = sessions_ if sessions_ is not None else sessions(R_)
    out = Coverage(unlisted=len(R_.unlisted))
    read_by: dict[Id, list[Counted]] = {}
    for item in counted:
        for event in tuple(item.supporting) + tuple(item.read):
            read_by.setdefault(event, []).append(item)
    any_done = {session.id for session in sessions_.values() if session.done}
    for session in sessions_.values():
        family = session.kind
        if family is None:  # its kind not established: read as every family it may be of
            _kind_unestablished(reader, sessions_, session, counted, read_by, procedure_day, any_done, out)
        elif session.done and catalogue.FAMILY_SUPPORT.get(family) is catalogue.SupportLevel.SUPPORTED:
            out.covered[session.id] = _reconcile_session(reader, sessions_, session, family, counted, read_by,
                                                         procedure_day, any_done, out)
    for session in sessions_.values():
        _in_doubt(reader, session, read_by, out)
    # the events filed under no session of the FactSet (an empty slot, a contradicted or doubted one, an id naming none):
    # a doubt is never an absence
    _in_doubt(reader, None, read_by, out, frozenset(sessions_))
    _merge(out)
    listed = {item.session for item in out.unresolved}
    for session in sessions_.values():  # v1's uncounted: a session done with no proposal, not listed or included
        if session.id in out.covered and not out.covered[session.id] and session.part_of is None \
                and session.id not in listed:
            out.not_listed.append(session)
    for session in sessions_.values():  # unestablished: a family stated, none of it done, read by no code
        if not session.done and _unestablished(R_, session, counted):
            out.unestablished += 1
    return out


def _reconcile_session(reader: Reader, sessions_: Mapping[Id, Session], session: Session, family: SessionKind,
                       counted: Sequence[Counted], read_by: Mapping[Id, list[Counted]], procedure_day: bool,
                       any_done: set[Id], out: Coverage) -> list[str]:
    """One done session read as ``family`` (v1's reconcile loop): its items and bundled acts appended to ``out``; the
    counted codes that cover it returned (none: no_proposal, or D134's office visit beside a procedure day, which
    reconcile lists as not listed)."""
    R_ = reader.R
    codes = _codes_of(session, counted, sessions_)
    anchor = session.event or next((event for event in session.events if _done(R_, event)), None)
    evidence = _evidence(R_, (anchor,) if anchor is not None else ())
    if not codes and inclusion_asks_no_code(sessions_, session, counted):
        pass  # the including session's code covers the examination; its own acts still count
    elif not codes:
        # D134: never an office visit beside a procedure done on the date of service (listed as not_listed)
        if family is SessionKind.OFFICE_EM and (procedure_day or any_done - {session.id}):
            return []
        done_ids = tuple(event for event in session.events if _done(R_, event))
        out.unresolved.append(Item(session.id, family, None, ItemReason.NO_PROPOSAL,
                                   Detail.SESSION_INCOMPLETE if session.incomplete else Detail.SESSION_PERFORMED,
                                   done_ids, evidence))
        for event in session.events:  # its done acts of a kind no profile of the family reconciles (1e:R3; v1's
            kind = _claimed_catalogue_kind(R_, event)  # reportable_kind condition, which listed none, dropped)
            if kind is not None and kind in unsupported_kinds(family) and _done(R_, event):
                out.unresolved.append(Item(session.id, family, kind, ItemReason.UNSUPPORTED, Detail.NO_PROFILE,
                                           (event,), _evidence(R_, (event,))))
        return []
    unknown = any(catalogue.code_link(item.code).route is not catalogue.LinkRoute.CATALOGUE for item in codes)
    for event in session.events:
        _member(reader, sessions_, session, family, event, read_by, unknown, out)
    return [item.code for item in codes]


def _kind_unestablished(reader: Reader, sessions_: Mapping[Id, Session], session: Session, counted: Sequence[Counted],
                        read_by: Mapping[Id, list[Counted]], procedure_day: bool, any_done: set[Id],
                        out: Coverage) -> None:
    """A done session whose kind is not established (v1 grouped it by pass 1's claimed family and listed it), read as
    EVERY supported family it may be of (session_families): whatever one reading lists is listed - its family None,
    since none is established - and the codes that cover it are those covering it under every reading. So a weakening
    of the session's kind (its family one of those it may be of) never releases what the established family listed,
    and a done session no reading covers is listed no_proposal, never 'complete'. A session that may be of no
    supported family is not read, as v1 read none."""
    families = [family for family in session_families(reader.R, session.id)
                if catalogue.FAMILY_SUPPORT.get(family) is catalogue.SupportLevel.SUPPORTED]
    if not session.done or not families:
        return
    found = Coverage()
    covered: list[str] | None = None
    for family in sorted(families, key=list(SessionKind).index):
        reading = _with_kind(session, family)
        codes = _reconcile_session(reader, {**sessions_, session.id: reading}, reading, family, counted, read_by,
                                   procedure_day, any_done, found)
        covered = codes if covered is None else [code for code in covered if code in codes]
    out.covered[session.id] = covered or []
    out.unresolved += [Item(item.session, None, item.act, item.reason, item.detail, item.events, item.evidence,
                            item.unlisted) for item in found.unresolved]
    seen = {act.event for act in out.bundled}
    for act in found.bundled:
        if act.event not in seen:
            seen.add(act.event)
            out.bundled.append(act)


def _with_kind(record: Session, kind: SessionKind) -> Session:
    return Session(id=record.id, kind=kind, events=record.events, examinations=record.examinations,
                   possible=record.possible, event=record.event, unresolved=record.unresolved, done=record.done,
                   incomplete=record.incomplete, part_of=record.part_of, possibly_part_of=record.possibly_part_of)


def _unestablished(R: FactSet, session: Session, counted: Sequence[Counted]) -> bool:
    """v1's unestablished count over one session that is not done: a family stated (its kind, or for a kind not
    established each family it may be of, with a catalogue entry), read by no counted code (v1: no code of its family;
    for a kind not established, not every family it may be of has one), and an event possibly in it
    (possible_members) possibly positive here - an examination whose own session fact is in doubt is possibly this
    session's. Monotone: a weakening only adds families and possible members, so it never empties the count."""
    families = frozenset({session.kind}) if session.kind is not None else session_families(R, session.id)
    stated = [family for family in families if catalogue.FAMILY_SUPPORT.get(family) is not None]
    if not stated or all(any(item.family is family for item in counted) for family in stated):
        return False
    return any(_positive_here(R, event) for event in possible_members(R, session.id))


def _member(reader: Reader, sessions_: Mapping[Id, Session], session: Session, family: SessionKind, event: Id,
            read_by: Mapping[Id, list[Counted]], unknown: bool, out: Coverage) -> None:
    """One member act of a session with counted codes (v1's reconcile loop, in its order: a bundled act is read before
    its kind is)."""
    R = reader.R
    kind = _claimed_catalogue_kind(R, event)
    if kind is None or kind in _NOT_ACTS:
        return
    acts = catalogue.FAMILY_ACTS.get(family, ())
    why = bundled(reader, event)
    status = facts_.fact(R, event, _A.STATUS)
    if not (_done(R, event) and facts_.holds(status, Status.PERFORMED)):
        # an act no code of the family accounts for is listed whatever its outcome (reconcile, compl-1)
        attempted = status.value is Status.ATTEMPTED_NOT_COMPLETED or not facts_.established(status)
        if (attempted and why is None and kind in acts and kind not in unsupported_kinds(family)
                and not pairing.other_date(R, event) and not pairing.other_performer(R, event)
                and not catalogue.family_codes_act(family, kind)):
            out.unresolved.append(Item(session.id, family, kind, ItemReason.UNSUPPORTED, Detail.ATTEMPTED_OR_IN_DOUBT,
                                       (event,), _evidence(R, (event,))))
        return
    if kind in unsupported_kinds(family):  # 1e:R3: the ESD, the anorectal balloon expulsion
        out.unresolved.append(Item(session.id, family, kind, ItemReason.UNSUPPORTED, Detail.NO_PROFILE, (event,),
                                   _evidence(R, (event,))))
        return
    under = _read_under(R, sessions_, family, kind, event)
    if under is not None:
        if under is Detail.NOT_COVERED:
            out.bundled.append(BundledAct(session.id, event, kind, None, None))
        else:
            out.unresolved.append(Item(session.id, family, kind, ItemReason.UNSUPPORTED, under, (event,),
                                       _evidence(R, (event,))))
        return
    if why is not None:
        out.bundled.append(BundledAct(session.id, event, kind, why.rule, why.whole))
        return
    if kind not in acts:
        # D142: a done act of a kind its family does not list, reportable elsewhere and read by no code
        if (event not in read_by and kind not in catalogue.EM_KINDS
                and facts_.fact(R, event, _A.KIND).result is Result.SUPPORTED
                and facts_.holds(facts_.fact(R, event, _A.SESSION), session.id) and any(
                    kind in catalogue.FAMILY_ACTS.get(other, ()) for other, level in catalogue.FAMILY_SUPPORT.items()
                    if level is catalogue.SupportLevel.SUPPORTED)):
            out.unresolved.append(Item(session.id, family, kind,
                                       ItemReason.COVERAGE_UNKNOWN if unknown else ItemReason.NOT_COVERED,
                                       Detail.NOT_COVERED, (event,), _evidence(R, (event,))))
        return
    if reader.verdict(event).truth is Truth.U and event in read_by:
        return  # a code depends on its bundling and asks it
    if not catalogue.family_codes_act(family, kind):
        out.unresolved.append(Item(session.id, family, kind, ItemReason.UNSUPPORTED, Detail.NO_CODE_OF_SERVICE,
                                   (event,), _evidence(R, (event,))))
        return
    if any(item.family is family for item in read_by.get(event, ())):
        return
    out.unresolved.append(Item(session.id, family, kind,
                               ItemReason.COVERAGE_UNKNOWN if unknown else ItemReason.NOT_COVERED, Detail.NOT_COVERED,
                               (event,), _evidence(R, (event,))))


def _read_under(R: FactSet, sessions_: Mapping[Id, Session], family: SessionKind, kind: Kind,
                event: Id) -> Detail | None:
    """v1's _read_under over facts (catalogue.READ_UNDER: an EUS forceps biopsy read under the upper endoscopy):
    Detail.NOT_COVERED as "read under" when the rule holds - every supported place of the act in the rule's regions
    (its places established) and a done session of that family has a done performed act of the kind - else why
    nothing reads it; None for any other act."""
    rule = catalogue.READ_UNDER.get((family, kind))
    if rule is None:
        return None
    other_family, regions = rule
    places = facts_.members(R, event, _A.TARGET_PLACES)
    known = [member.value for member in places if member.result is Result.SUPPORTED]
    if not places or not all(facts_.established(member) for member in places) or not known or not all(
            isinstance(place, Landmark) and anatomy.in_regions(place, regions) for place in known):
        return Detail.READ_UNDER_NOT_PLACED
    reads = any(other.kind is other_family and other.done and any(
        _claimed_catalogue_kind(R, member) is kind and _done(R, member)
        and facts_.holds(facts_.fact(R, member, _A.STATUS), Status.PERFORMED) for member in other.events)
        for other in sessions_.values())
    return Detail.NOT_COVERED if reads else Detail.READ_UNDER_NO_SERVICE


def _in_doubt(reader: Reader, session: Session | None, read_by: Mapping[Id, list[Counted]], out: Coverage,
              known: frozenset[Id] = frozenset()) -> None:
    """The in_doubt items of one session (``session`` None: of the events filed under none of the ``known`` sessions -
    an empty, contradicted or doubted slot, or an id naming no session of the FactSet), each listed once: each doubted
    act no counted code reads and not bundled - and D142's class in doubt (_elsewhere_in_doubt) - and each unlisted act
    of the session (3.2.6 rule 3)."""
    R = reader.R
    family = session.kind if session is not None else None
    if family is not None and catalogue.FAMILY_SUPPORT.get(family) is not catalogue.SupportLevel.SUPPORTED:
        return
    members = session.events if session is not None else tuple(event for event in R.events
                                                                if filed(R, event) not in known)
    key = session.id if session is not None else None
    for event in members:
        if event in read_by or bundled(reader, event) is not None:
            continue
        listed, doubt = eus_unlisted(reader, event)
        if listed or not (doubted(reader, event) or doubt or (
                session is not None and family is not None and _elsewhere_in_doubt(R, session.id, family, event))):
            continue
        item = Item(key, family, _claimed_catalogue_kind(R, event), ItemReason.IN_DOUBT, Detail.IN_DOUBT, (event,),
                    _evidence(R, (event,)))
        out.unresolved.append(item)
        out.in_doubt.append((item, InDoubt(event=event)))
    if session is not None:
        for index, entry in unlisted_acts(R, session.id):
            item = Item(key, family, entry.kind, ItemReason.IN_DOUBT, Detail.IN_DOUBT, (), _ordered(entry.units)[:2],
                        (index,))
            out.unresolved.append(item)
            out.in_doubt.append((item, InDoubt(unlisted=index)))


def _elsewhere_in_doubt(R: FactSet, session: Id, family: SessionKind, event: Id) -> bool:
    """D142's class IN DOUBT: an act filed under ``session`` (its session supported) that may be of a kind its
    established ``family`` does not list among its acts while a supported family does (no E/M kind, examination,
    umbrella or never-reported kind) - D142 lists it not covered when it is done, performed and its kind supported -
    possibly positive here and not so established: in doubt, listed (a doubt is never an absence). Reachable past
    settle's K2 for a kind the family's codes account for and its acts do not list (the ERCP's foreign body); v1 listed
    it nowhere (its compl-1 and doubted read the family's acts)."""
    if not facts_.holds(facts_.fact(R, event, _A.SESSION), session) or not _positive_here(R, event) or (
            _done(R, event) and facts_.holds(facts_.fact(R, event, _A.STATUS), Status.PERFORMED)):
        return False
    acts = catalogue.FAMILY_ACTS.get(family, ())
    elsewhere = frozenset(kind for other, level in catalogue.FAMILY_SUPPORT.items()
                          if level is catalogue.SupportLevel.SUPPORTED for kind in catalogue.FAMILY_ACTS.get(other, ()))
    return any(kind not in acts and kind in elsewhere and kind not in catalogue.EM_KINDS and kind not in _NOT_ACTS
               and kind not in catalogue.NOT_REPORTED for kind in catalogue_kinds(R, event))


def _merge(out: Coverage) -> None:
    """One item per (session, act kind): a second site of one service is the same code (v1); every in_doubt event of a
    merged item keeps its question (D89)."""
    merged: dict[tuple[Id | None, Kind | None], Item] = {}
    keys: dict[int, tuple[Id | None, Kind | None]] = {}
    for index, item in enumerate(out.unresolved):
        key = (item.session, item.act)
        keys[index] = key
        if key not in merged:
            merged[key] = item
        else:
            first = merged[key]
            merged[key] = Item(first.session, first.family, first.act, first.reason, first.detail,
                               tuple(dict.fromkeys(first.events + item.events)), first.evidence,
                               tuple(dict.fromkeys(first.unlisted + item.unlisted)))
    # every item is alive in out.unresolved while this runs, so an id names one item only
    lookup = {id(item): keys[index] for index, item in enumerate(out.unresolved)}
    in_doubt = [(merged[lookup[id(item)]], ref) for item, ref in out.in_doubt if id(item) in lookup]
    out.unresolved = list(merged.values())
    out.in_doubt = in_doubt


def unresolved_record(items: Sequence[Item]) -> list[dict[str, object]]:
    """completeness['unresolved_items'] (v1's, text-free): each item as ids, enumeration values and integer spans, with
    its second-review mark (FINAL 7.8, D10): True on a no_proposal or not_covered item with an index below
    SECOND_REVIEW_CHECKED. Its label is step 3c's, from the record."""
    return [{'service': None if item.session is None else str(item.session),
             'family': None if item.family is None else item.family.value,
             'act': None if item.act is None else item.act.value, 'reason': item.reason.value,
             'detail': item.detail.value, 'events': [str(event) for event in item.events],
             'unlisted': list(item.unlisted), 'evidence': [[span.start, span.end] for span in item.evidence],
             'second_review': index < SECOND_REVIEW_CHECKED and item.reason in _MARKED}
            for index, item in enumerate(items)]


_MARKED: frozenset[ItemReason] = frozenset({ItemReason.NO_PROPOSAL, ItemReason.NOT_COVERED})


def bundled_record(acts: Sequence[BundledAct]) -> list[dict[str, object]]:
    """completeness['bundled'] (v1's, text-free): each bundled act's session, event, kind, rule (None: read under
    another service) and whole."""
    return [{'service': None if act.session is None else str(act.session), 'event': str(act.event),
             'act': act.act.value, 'rule': None if act.rule is None else act.rule.value,
             'whole': None if act.whole is None else str(act.whole)} for act in acts]


# --- the service questions (4.8; v1's in_doubt_questions and service_extent_questions) ---------------------------------


@dataclass(frozen=True, slots=True)
class ServiceItem:
    """One service-scope item (4.8: "they hold nothing"): its session and family, the item (a HeldFact: fact key,
    subject, result, cause, spans, rank) and what it names - an event, an unlisted act (its index), or the session."""
    session: Id | None
    family: SessionKind | None
    item: HeldFact
    event: Id | None = None
    unlisted: int | None = None


def _item_order(item: HeldFact) -> tuple[int, int]:
    """4.8's order of an act's items: its rank, then a question before an explanation at an equal rank."""
    return (item.rank if item.rank is not None else 99, 0 if item.kind is ItemKind.QUESTION else 1)


def act_witnesses(R: FactSet | Reader, event: Id) -> tuple[HeldFact, ...]:
    """Every witness of one act read for no code (4.3 rows 1-8 over the act, and its bundling; the service question's
    reading of v1's focus_question h1-h5): its conflicts (rank 1); each statement paired with it in a relation that is
    not INDEPENDENT (pairing.item at its rank) and each unlisted denial or doubt (statement_scope); its status (rank 2
    when doubted, else 4), kind (4; a positive umbrella act_method, 9) and - for a clip or an injection - purpose (4);
    its entry (5: an explanation when established as another role), date relation (6), performer (7), session and its
    kind (8); its bundling in doubt (rank 17). Ordered by rank (4.8)."""
    reader = Reader.of(R)
    R_ = reader.R
    own = _anchor_units(R_, event)
    kind = _kind_of(R_, event)
    out: list[HeldFact] = list(reader.conflicts(event))
    for pair in reader.pairs(event):
        item = pairing.item(pair)
        if item is None or pair.relation is pairing.Relation.CONTRADICTION or item.rank is None:
            continue
        out.append(HeldFact(fact=rq.fact_key(item.fact), attribute=None, subject=event, result=None,
                            kind=ItemKind.QUESTION, cause=pairing.cause(pair) or UNESTABLISHED, reason=None,
                            spans=pair.spans, rank=item.rank.value))
    for unlisted_pair in reader.unlisted_pairs(event):
        out.append(HeldFact(fact=rq.fact_key(rq.FactKey.STATEMENT_SCOPE), attribute=None, subject=event, result=None,
                            kind=ItemKind.QUESTION, cause=UNLISTED, reason=None, spans=unlisted_pair.spans,
                            rank=rq.Rank.STATEMENT_SCOPE.value))
    for attribute in _OWN_FACTS:
        found = facts_.fact(R_, event, attribute)
        if found.result is Result.CONTRADICTED:
            continue  # among the conflicts
        spans = _ordered(own + found.spans)
        if attribute is _A.KIND:  # row 1: a positive umbrella asks its method (9); a kind not established, rank 4
            if found.result is not Result.SUPPORTED:
                out.append(witness(found, attribute, event, rq.FactKey.PERFORMED_STATUS, kind, spans, ACT_SUPPORT))
            elif found.value in catalogue.UMBRELLAS:
                out.append(witness(found, attribute, event, rq.FactKey.ACT_METHOD, kind, spans, ACT_SUPPORT))
        elif attribute is _A.STATUS:  # row 2: a status not established (rank 2 when doubted, else 4)
            if not facts_.established(found):
                out.append(witness(found, attribute, event, rq.FactKey.PERFORMED_STATUS, kind, spans, ACT_SUPPORT))
        elif attribute is _A.SESSION:  # row 6: the session, then its kind (rank 8)
            session = _supported_id(found)
            if session is None:
                out.append(witness(found, attribute, event, rq.FactKey.PROCEDURE, kind, spans, ACT_SUPPORT))
            elif facts_.fact(R_, session, _A.KIND).result is not Result.SUPPORTED:
                out.append(witness(facts_.fact(R_, session, _A.KIND), _A.KIND, session, rq.FactKey.PROCEDURE, kind,
                                   own, ACT_SUPPORT))
        else:  # rows 3-5: an established other value is an explanation (4.8's F), else a question
            key, wanted = _ACT_ROWS[attribute]
            if facts_.holds(found, wanted):
                continue
            if facts_.established(found):
                rank = _ITEM_OF[key].rank
                out.append(HeldFact(fact=rq.fact_key(key), attribute=attribute, subject=event, result=found.result,
                                    kind=ItemKind.EXPLANATION, cause=f'coding_rule:{ACT_SUPPORT}', reason=None,
                                    spans=spans,
                                    rank=rank.value if rank is not None else None))
            else:
                out.append(witness(found, attribute, event, key, kind, spans, ACT_SUPPORT))
    purpose = facts_.fact(R_, event, _A.PURPOSE)  # row 1 for a clip or an injection: its purpose (D157's doubt)
    if may_be(facts_.fact(R_, event, _A.KIND)) & catalogue.HEMOSTASIS_KINDS and \
            purpose.result is not Result.SUPPORTED and _purpose_may_be_hemostasis(purpose):
        out.append(witness(purpose, _A.PURPOSE, event, rq.FactKey.PERFORMED_STATUS, kind,
                           _ordered(own + purpose.spans), ACT_SUPPORT))
    verdict_ = reader.verdict(event)
    if verdict_.truth is Truth.U:
        out += [item for item in verdict_.held if item.kind is ItemKind.QUESTION]
    unique = tuple(dict.fromkeys(out))
    return tuple(sorted(unique, key=_item_order))


# 4.3 rows 3-5 over one act: the attribute -> (the key a failure asks, the value the row needs).
_ACT_ROWS: Mapping[Attribute, tuple[rq.FactKey, Enum]] = MappingProxyType({
    _A.DATE_RELATION: (rq.FactKey.EVENT_TIME, DateRelation.ON_DATE_OF_SERVICE),
    _A.PERFORMER: (rq.FactKey.EVENT_PERFORMER, Performer.DOCUMENTING_TEAM),
    _A.ENTRY: (rq.FactKey.EVENT_ENTRY, Owner.DOCUMENTING_CLINICIAN)})


def act_item(R: FactSet | Reader, event: Id) -> HeldFact | None:
    """The act's one item (4.8: its highest-ranked witness, a question before an explanation at an equal rank); None
    when nothing about it is in doubt."""
    found = act_witnesses(R, event)
    return found[0] if found else None


def _unlisted_item(entry: UnlistedStatement, session: Id | None) -> HeldFact:
    """An unlisted act's item (3.2.6 rules 2 and 3): performed_status at the doubt row, quoting its units."""
    return HeldFact(fact=rq.fact_key(rq.FactKey.PERFORMED_STATUS), attribute=None, subject=session, result=None,
                    kind=ItemKind.QUESTION, cause=UNLISTED, reason=None, spans=_ordered(entry.units),
                    rank=rq.Rank.DOUBT.value)


def in_doubt_questions(R: FactSet | Reader, coverage: Coverage, asked: Iterable[tuple[Id | None, str]] = (),
                       holding: Iterable[Id] = ()) -> list[ServiceItem]:
    """One service item per (session, fact) for the in_doubt items (4.8; v1's in_doubt_questions): each act in doubt
    no counted code reads, with its own item (act_item; an unlisted act's, _unlisted_item). ``asked``: the (subject,
    fact key) of the codes' items - a service item naming one is dropped (D89, by act and fact). ``holding``: the acts
    the codes' items name - such an act takes its (session, fact) slot only when no other act in doubt does (D149, D157
    (3)); then the act with the fewest witnesses (4.8's binding), then document order. Every fact is asked once per
    session; which act it names never drops a fact."""
    reader = Reader.of(R)
    R_ = reader.R
    codes_asked = set(asked)
    held = set(holding)
    groups: dict[tuple[Id | None, str], list[tuple[tuple[int, int, int], ServiceItem]]] = {}
    for item, ref in coverage.in_doubt:
        if ref.event is not None:
            found = act_witnesses(reader, ref.event)
            if not found:
                continue
            top = found[0]
            service = ServiceItem(item.session, item.family, top, event=ref.event)
            rank = (1 if ref.event in held else 0, len(found), reader.order.get(ref.event, 0))
            subject: Id | None = ref.event
        elif ref.unlisted is not None:
            entry = R_.unlisted[ref.unlisted]
            top = _unlisted_item(entry, item.session)
            service = ServiceItem(item.session, item.family, top, unlisted=ref.unlisted)
            rank = (0, 1, len(R_.events) + ref.unlisted)
            subject = item.session
        else:
            continue
        if (subject, top.fact) in codes_asked:
            continue
        groups.setdefault((item.session, top.fact), []).append((rank, service))
    return [min(members, key=lambda pair: pair[0])[1] for members in groups.values()]


# D125: the families whose done sessions get the extent question (c2e53f8e reconcile.py:961-962).
_EXTENT_FAMILIES: frozenset[SessionKind] = frozenset({SessionKind.EGD, SessionKind.COLONOSCOPY, SessionKind.FLEX_SIG,
                                                      SessionKind.ENTEROSCOPY})


def service_extent_questions(R: FactSet | Reader, sessions_: Mapping[Id, Session],
                             asked: Iterable[tuple[Id | None, str]] = ()) -> list[ServiceItem]:
    """D125's extent item (v1's service_extent_questions over facts): for each done session of an upper endoscopy, a
    colonoscopy, a sigmoidoscopy or an enteroscopy that states neither a reach (a reached point supported) nor a
    completion (supported), and whose extent no code's item asks (``asked``: (subject, fact key); the session or one of
    its examinations as subject), one extent item (rank 14), naming the session. A reach or a completion that is not
    established is a doubt, never a fact (D87): the item is asked. A question only: no code's status changes."""
    R_ = Reader.of(R).R
    codes_asked = set(asked)
    extent = rq.fact_key(rq.FactKey.EXTENT)
    out = []
    for session in sessions_.values():
        if session.kind not in _EXTENT_FAMILIES or not session.done:
            continue
        if any((subject, extent) in codes_asked for subject in (session.id, *session.examinations)):
            continue
        reached = facts_.members(R_, session.id, _A.REACHED)
        completion = facts_.fact(R_, session.id, _A.COMPLETION)
        if any(member.result is Result.SUPPORTED for member in reached) or completion.result is Result.SUPPORTED:
            continue
        resting = next((found for found in (*reached, completion) if not _pure_silent(found)), completion)
        spans = _ordered(span for event in (session.event,) if event is not None
                         for span in _anchor_units(R_, event)) or _ordered(
            span for event in session.examinations for span in _anchor_units(R_, event))
        out.append(ServiceItem(session.id, session.kind, HeldFact(
            fact=extent, attribute=_A.REACHED, subject=session.id, result=resting.result, kind=ItemKind.QUESTION,
            cause=_cause(resting, 'extent'), reason=_reason(resting), spans=spans, rank=rq.Rank.EXTENT.value)))
    return out


# --- completeness (v1's coverage.completeness, its sentences copied and pinned equal) -----------------------------------

UNVERIFIED_REASON = "CPT Studio's reading left {count} attribute{s} unverified that a decision read"


def _plural(count: int) -> str:
    return '' if count == 1 else 's'


def completeness(coverage: Coverage, sessions_: Mapping[Id, Session], *, open_questions: int, provider_ok: bool,
                 conflicts: int, label: Callable[[Session], str], unverified: int = 0) -> dict[str, object]:
    """The encounter's coding completeness at assessment time, worded as v1's coverage.completeness words it (pinned
    equal by test), plus 3.2.6 rule 1: kept unlisted statements make it incomplete (``coverage.unlisted``). ``label``
    names a session not listed (v1's uncounted_label; step 3c's wording, injected by the caller, as derive.py's quote
    is)."""
    reasons = []
    unresolved = coverage.unresolved
    not_listed = coverage.not_listed
    if not provider_ok:
        reasons.append('the provider response was not available')
    if unresolved:
        reasons.append(f'{len(unresolved)} documented service{_plural(len(unresolved))} or act'
                       f'{_plural(len(unresolved))} without a supported proposal')
    if coverage.unestablished:
        reasons.append(f'{coverage.unestablished} documented service{_plural(coverage.unestablished)} not '
                       'established as performed and read by no proposal')
    if not_listed:
        reasons.append(f'{len(not_listed)} documented service{_plural(len(not_listed))} without a supported '
                       'proposal and not listed as unresolved: ' + ', '.join(label(session) for session in not_listed))
    if conflicts:
        reasons.append(f'{conflicts} conflict{_plural(conflicts)} in the record')
    if open_questions:
        reasons.append(f'{open_questions} open question{_plural(open_questions)}')
    if unverified:
        reasons.append(UNVERIFIED_REASON.format(count=unverified, s=_plural(unverified)))
    if coverage.unlisted:
        reasons.append(f'{coverage.unlisted} statement{_plural(coverage.unlisted)} of the document that the reading '
                       'did not list')
    performed = [session for session in sessions_.values() if session.done]
    return {
        'state': 'incomplete' if reasons else 'complete_pending_review',
        'reasons': reasons,
        'services': len(performed),
        'unresolved': len(unresolved),
        'conflicts': conflicts,
        'statement': ('Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.') if reasons else (
            'Every documented service has a proposal to review. This is not verified coding: code-set membership '
            'and NCCI edits are not verified, and each proposal still needs a reviewer.'),
    }


def included_by(sessions_: Mapping[Id, Session], covered: Mapping[Id, Sequence[str]]) -> dict[Id, list[str]]:
    """v1's included_by over sessions: {session id: the counted codes of the session it is read as part of that include
    its examination} for every done session read as part of another."""
    out: dict[Id, list[str]] = {}
    for session in sessions_.values():
        if session.done and session.part_of is not None and session.kind is not None:
            kind = session.kind
            out[session.id] = [code for code in covered.get(session.part_of, ())
                               if catalogue.includes_examination(code, kind)]
    return out


# --- event_coding@2 (what the overlay, the reports and the customer API read; FINAL-V2 6.5) ---------------------------


def _entry(R: FactSet, event: Id) -> dict[str, object]:
    kind = _claimed_catalogue_kind(R, event)
    lesion = _supported_id(facts_.fact(R, event, _A.TARGET_LESION))
    return {'event': str(event), 'kind': None if kind is None else kind.value,
            'lesion': None if lesion is None else str(lesion), 'unlisted': None}


def _ids(values: Iterable[Id]) -> list[str]:
    return [str(value) for value in values]


def event_coding(R: FactSet | Reader, sessions_: Mapping[Id, Session],
                 codes: Mapping[str, tuple[Id | None, Sequence[Id]]]) -> dict[str, object]:
    """{version, sessions, codes, lesions} (v1's event_coding, text-free; cpt-studio-events@2). ``codes``: {proposal
    key: (session id, E* event ids)} of the decidable proposals. A session's ``reportable`` and ``doubted`` entries are
    the acts base_included and the overlay read (step 4d, 5c), in pass 1's order: its reportable acts and D137's EUS
    acts (their session established as it); its doubted acts - every act POSSIBLY in it (possible_members: filed under
    it, or its session fact leaving it open) and doubted there (doubted_in), and D145's EUS acts begun or in doubt,
    never both (D156 (3)); never the visit; and each unlisted act of the session (3.2.6 rule 3). An act whose session
    is not established is so in every session it may be in: a weakening never drops it from these records (P-MONO)."""
    reader = Reader.of(R)
    R_ = reader.R
    coded_sessions: dict[str, object] = {}
    for session in sessions_.values():
        reportable_entries: list[dict[str, object]] = []
        doubted_entries: list[dict[str, object]] = []
        members = set(session.events) | set(possible_members(R_, session.id))
        for event in (event for event in R_.events if event in members):
            if facts_.fact(R_, event, _A.KIND).value in catalogue.EM_KINDS:
                continue  # the session's own service is never an act beside itself (v1)
            listed, doubt = eus_unlisted(reader, event)
            if reportable(reader, event) or listed:
                reportable_entries.append(_entry(R_, event))
            if not listed and (doubted_in(reader, event, session.id) or doubt):
                doubted_entries.append(_entry(R_, event))
        for index, entry in unlisted_acts(R_, session.id):
            doubted_entries.append({'event': None, 'kind': None if entry.kind is None else entry.kind.value,
                                    'lesion': None, 'unlisted': index})
        kind = None if session.kind is None else session.kind.value
        coded_sessions[str(session.id)] = {
            'family': kind, 'kind': kind, 'event': None if session.event is None else str(session.event),
            'part_of': None if session.part_of is None else str(session.part_of),
            'possibly_part_of': None if session.possibly_part_of is None else str(session.possibly_part_of),
            'unresolved': session.unresolved, 'done': session.done, 'incomplete': session.incomplete,
            'examinations': _ids(session.examinations), 'possible': _ids(session.possible),
            'events': _ids(session.events), 'reportable': reportable_entries, 'doubted': doubted_entries}
    coded_codes: dict[str, object] = {}
    for key, (session_id, supporting) in codes.items():
        lesions = sorted({lesion for lesion in (_supported_id(facts_.fact(R_, event, _A.TARGET_LESION))
                                                for event in supporting) if lesion is not None},
                         key=lambda lesion: lesion.number)
        coded_codes[key] = {'session': None if session_id is None else str(session_id),
                            'events': _ids(supporting), 'lesions': _ids(lesions)}
    coded_lesions: dict[str, object] = {}
    for lesion in R_.lesions:
        multiplicity = facts_.fact(R_, lesion, _A.MULTIPLICITY)
        coded_lesions[str(lesion)] = {
            'places': [member.value.value for member in facts_.members(R_, lesion, _A.PLACES)
                       if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)],
            'multiplicity': multiplicity.value.value if multiplicity.result is Result.SUPPORTED and isinstance(
                multiplicity.value, Multiplicity) else None,
            'distinct_from': _ids(member.value for member in facts_.members(R_, lesion, _A.DISTINCT_FROM)
                                  if member.result is Result.SUPPORTED and isinstance(member.value, Id)),
            'same_as': _ids(member.value for member in facts_.members(R_, lesion, _A.SAME_AS)
                            if member.result is Result.SUPPORTED and isinstance(member.value, Id))}
    return {'version': CODING_VERSION, 'sessions': coded_sessions, 'codes': coded_codes, 'lesions': coded_lesions}
