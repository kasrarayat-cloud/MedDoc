"""The combination rules of design v2 (docs/gemini-migration/FINAL-V2.md 4.7, 4.1, 4.8, 4.9 and 4.13; step 4d of 8.1;
DECISIONS D191 and the arbiter triage's hand-off 1e:R3): v1's studio/interpretation/combination.py - base, base-within,
competing, the same-day E/M, the separate statement, the separate-lesion modifier review and the endoscopic rows - and
the competition's claims (v1's assess._claims, _one_stricture, _technique_doubts and _stricture_claims: D55, D74, D104,
D118, D163, D167), forked into engine/ with their readers deleted and their inputs rewired to settled facts. Nothing
here reads text: every input is an enumeration member, an id, a result or a span of the FactSet (engine/facts.py), a
code string read as a number (engine/catalogue.py), or a record another step hands in.

The engine applies these rules over the codes it counts (engine/assess.py, step 5a) and the read-time overlay
(interpretation/overlay.py, step 5c) applies the same functions over a reviewer's counted set: one implementation each,
so the two cannot drift (v1's rule, kept).

**What a member is** (``Member``; v1's ``members`` (code, family, session id) and assess's counted selections): a
counted code - its proposal key, its code, the family it routes to, the session it is matched to (None when its family
has none at this encounter), its E* (the acts supporting it), its origin (kept, never read: D40), whether it is a
procedure (assess._procedural, read from the reference rows) and whether the per-code rule supports it (v1's state
performed or incomplete). Every function here takes members in their order and keys its output by member key.

**base_included** (FINAL 7.9, D119, D177(1); 4.7: "unchanged structure | sessions; reportable and doubted acts"). A
base code (``is_base``: a base profile - an endoscopic family's examination or an office visit code, whose two codes of
one visit hold each other - or an examination-only EUS code, every one of whose covers is the examination) matched to
session S is held, never excluded, beside (a) another counted code of its family matched to S that accounts for an act,
(b) S's reportable acts, or (c) S's doubted acts. The reportable and doubted acts are step 4b's (engine/coverage's
event_coding@2, 4.7's "reportable / doubted | v1's shapes" row), handed in as ``coding`` (SessionActs per session),
never re-derived here: two derivations would drift. DECISIONS D119: an upper endoscopy's base code reads, as (b) and
(c), the PEG acts of every feeding-tube session too (a session whose kind may be the feeding tube's, an act whose kind
may be a PEG, both read by facts.possibly). FINAL-V2 3.2.6 rule 3: an unlisted act whose session card is S is a
synthetic doubted act of S, read here from the FactSet (R.unlisted), so it holds S's base code as a doubt whatever the
coding lists. D177(1): the codes the hold NAMES are those of the base code's own EUS tract (catalogue.eus_tract); with
none, the hold names the acts; with neither, every code beside it (the recorded residual: naming nothing would drop the
hold). The hold is an EXPLANATION (F, 4.8) when the examination is established included - (b), a reportable act - and a
QUESTION (U) when only (a), counted codes beside it (a proposal with no act documented is one), or doubted or unlisted
acts hold it; it never reads another code's support, which rests on facts outside its closure (4.9). ``coding`` must
list every session it is asked about: step 4b's event_coding@2 lists every session of the FactSet, so a session it
does not list is a wiring error, refused (ValueError), never read as a session with no acts (which would release a
base code beside acts nobody listed).

**base_within** (C3, C-4, D70; 4.7: "part_of_session supported (C3); C-4 structural over supported session kinds and
tracts (a done EGD beside a done upper EUS on the date); possibly_part_of by possibly"), from the FactSet:
- C3: the session's part_of_session supported, naming another session - established;
- C-4: the session's kind supported EGD and done, beside another session whose kind is supported EUS, whose tract is
  supported upper and which is done - established (a tract that may be upper or pancreatobiliary - an upper EUS
  examining the pancreas - leaves it possible: v1 read every EUS not placed lower as upper). A session is done (4.3
  row 7: "its examination, when it has one, passes 2-5 (an act-only session: the act itself)") when one of its
  examinations - an event whose kind is supported examination and whose session is supported that session, a digital
  examination (device supported manual: FINAL 5.6 E13) excepted - passes rows 2-5 (engine/reading.done); with no such
  examination, when one of its acts (session supported) passes them and no event that may be its examination is left
  open (a kind possibly the examination, possibly in the session, possibly today's), so an EUS told only through its
  done acts is the session (D121, D135);
- D70, by possibly: the part_of_session claim not established, naming the session (its value or an option); or C-4's
  structure possible on every fact (each kind and the tract possibly so, both sessions possibly done: an event possibly
  in the session that may have been done today, facts.possibly) - a possible whole, the code held as one that is,
  never READY. A tract supported lower, or any fact established against the structure, sets nothing up (v1's lower EUS
  includes no EGD).
A base code whose session is (possibly) the endoscopic portion of a whole W is held beside the counted codes matched to
W that include its family's examination (catalogue.includes_examination), or beside none when W has no counted code;
W's counted codes that include no such examination hold nothing. The hold is an EXPLANATION when an established whole
holds it, a QUESTION when only a possible one does. v1's eus_places and its lower-evidence word reading are gone (4.7).

**The competition's claims** (``claims``; D40, D55, D74, D104, D118, D163, D167 - 4.7: "claims over E* and over acts
read by possibly; D118's one stricture by same lesion or places not disjoint; the D29 site fit"; 4.8: "A hold never
lowers what a code claims: claims read acts by possibly, never a held code's state"; 9.4 P-MONO: "the claims never
shrink"). A code claims, whatever its state:
- OWN: its E*, and every act that may be its act - an act that may be of a kind of one of its requirement groups (a
  kind the act may be by facts.possibly, read as the catalogue reads it: a clip or an injection whose purpose is
  supported hemostasis is a bleeding control only, one whose purpose may be hemostasis is both; a tattoo and an
  injection as one act; never an umbrella act, whose established kind is none of its members by possibly - v1's READY
  codes never claimed one, and an INTERVENTION act would otherwise hold every READY code of its family), possibly
  positive (possibly performed or attempted: a status not established leaves both open), its date relation not
  established as another date and its performer not established as another (4.4's positive-candidate frame), and
  possibly in a session of the code's family (by possibly over its session - every session of the FactSet when its
  session fact names none - and that session's kind; READ_UNDER's rule admits an act of the family it reads under;
  on route (b), of any family) - kept only where the code could account for it: for a technique code (a dilation code
  that names a technique), its device not established as another technique class (R4: "a dilation of another
  technique is no act the code accounts for"). This is D163's "a held code keeps, as claims, the acts it could account
  for", read by possibly: 4.4 records every positive candidate's witnesses in held_facts [R:HO-8], and this set holds
  every such act of the code's family. NO PLACE LIST REMOVES A CLAIM: D29's site fit (a dilation whose listed places
  all lie outside a site code's class), route (b)'s regions and READ_UNDER's regions would set an act apart on its
  listed places alone, and a place list may be short - P6 and 9.4's P-MONO name a deleted member as a weakening that
  never releases a rival, and 3.2.3's pair controls, which make a short list safe, guard two objects' places, never
  an act against a class (a dilation listed at the distal esophagus and the pylorus is claimed by 43249 and 43245;
  read by its listed places, deleting the esophageal one would release 43245). The step's NOTES record the question
  and v1's measured cost (D163's G1);
- D55, D74, D104, D167: a narrowed code (D27: CodeLink.defining) whose family has an act that may be of a defining kind,
  possibly positive and not established at another date (or whose E* is not empty) also claims every act that may be of
  its other covered kinds, possibly positive, not established at another date, possibly of its family - any performer,
  as v1's current performed acts were (only 43265, 44365 and 49440 have such kinds);
- D118: a technique code also claims every act of its family that may be of its kinds (a dilation), possibly positive,
  not established at another date (any performer, any technique), done on ONE stricture with ANOTHER act of its own
  (``one_stricture``: the two lesions possibly the same; else not set apart by facts.apart_by_lesion, nor, when no
  lesion is possibly shared, by facts.apart_by_place - both read the pair controls [R:SC-B]) - never with itself.
Every condition reads facts by possibly or as "not established otherwise", and none reads a place list, so weakening a
fact (to unresolved, an added doubt, a control left unrejected, a deleted member) can only add claims (P-MONO): a hold
is never a lowered input that releases a rival. v1's G4 exception (a technique code held for its site adds no claim)
read the code's hold reason, which 4.8 forbids reading; with no site read here it has no counterpart.

**competition** (P-ADMIT2 as D40 amends it, unchanged): two counted codes with different codes whose claims intersect -
the same documented act - are each held with one competing_codes question naming the others, whoever proposed either.

**The same-day E/M** (C-3; D81, D94, D109, D111, D130, D133, D134; 4.7). ``procedure_day`` reads every event that may
be other than an E/M visit or prolonged time (an event whose every possible kind is an E/M kind is never a procedure;
one whose kind may also be another, a doubt, is read as the other too - fail-closed, so a weakened visit kind can only
add a procedure), possibly positive, and procedural:
- of a procedural family - its session possibly of one of SAME_DAY_FAMILIES (the procedure families and gi.other, D81),
  read over the sessions its session fact may name (every session of the FactSet when it names none);
- or possibly of a SAME_DAY_KIND (every kind a procedural family's catalogue entry lists - its acts, its bundled and its
  unsupported kinds, catalogue.BUNDLED_KINDS and UNSUPPORTED_KINDS (hand-off 1e:R3) - the examination and the
  umbrellas: every kind but the visit's, prolonged time, moderate sedation and other; read from D191's one table of a
  session family's kinds, requirements_table.FAMILY_KINDS, less the moderate sedation and other it adds to every
  procedural family), an examination whose kind is supported examination and whose device is supported manual
  excepted (E13: a digital examination);
- or possibly of kind other with other_class possibly procedure (D130's statement reading, rewired: its head words and
  DONE_STATEMENTS are gone, 4.7).
Its effective date relation (engine/facts.py's stored per-act fact; the caller passes facts.effective's FactSet, so L1
is re-judged) decides: supported on_date_of_service, it makes the procedure day (DONE when its status is supported
performed or attempted and what made it procedural is established - its session's family, or its kind supported, and
for an examination outside a procedural family's session its device established as other than manual, so a digital
examination left open never counts as done - else possible; an act counted by its class alone is only ever possible,
D130); established as another date, it is no procedure day; otherwise it is UNDATABLE (event_time). **The performer is
not read** (legacy parity, S3 hazard 7, 4.13: C-3 counts any performer's same-day procedure). FINAL-V2 3.2.6 rule 5:
every kept unlisted act (what act, of no E/M kind) is an undatable possible procedure. A counted procedural code adds
its family to the done list when the per-code rule supports it and to the possible list otherwise (engine._encounter's
selected procedural codes). ``same_day_holds`` gives an E/M code (catalogue.EM_FAMILIES) its holds, by v1's rule with
its one release that a weakening could reach closed (9.4 P-MONO: "the READY ... sets never grow"; C-3: an undatable
event is "a question and never READY"):
- on a procedure day (done or possible) with no separate statement documented: separate_em (rank 20) - an EXPLANATION
  quoting the denial when the visit's separately_identifiable is negated, a QUESTION otherwise (v1's item);
- otherwise, with an undatable act (or an unlisted one) and no ESTABLISHED procedure day (``ProcedureDay.established``:
  a done procedure act, every fact that made it one established - never a counted code's support alone, which rests on
  that code's own facts, outside the E/M code's closure, 4.9): event_time (rank 6) for each undatable act (every
  witness, 4.4). v1 asked it only with no procedure day at all; a merely possible procedure day beside a
  documented statement released the code, and a weakening (a status, a device, a kind, a class left open) creates a
  possible procedure day - so v1's rule turned a held code READY under a weakening. An established procedure day
  cannot be created by a weakening, and beside one the undatable act's date decides nothing for the E/M code (the day
  is a procedure day whatever it is), so there the documented statement releases it, as v1's did;
- otherwise none.
Every input of the hold therefore moves one way under a weakening: the procedure day and the undatable acts can only
grow, the established procedure day and the documented statement can only shrink. The visit's own session encounter
(4.3's V.this_encounter) is step 4a's requirement and is not repeated. ``visit_basis`` (v1's, 5.5) is the visit's
supported basis, which the support display shows; whether R6:em_basis is met is step 4a's row.

**The separate statement** (D113; 4.7: "visit.separately_identifiable supported = a statement; negated = a denial
(quoted); otherwise none"): read from the code's own visit events, then from every other visit of this encounter (kind
supported em_visit, date relation supported on the date of service, its session's encounter supported this_encounter,
its performer supported documenting_team), never another encounter's. Every condition on another visit is established,
so a weakening can only drop a visit, never add one: v1 admitted a visit whose performer was merely not established as
another's, and weakening such a visit's performer (supported other_clinician to unresolved) added its statement and
released a held E/M code. A supported statement on any of them is the statement - a denial never releases, and neither
silences another visit's statement (FRESH-2 fb10's shape) -; else the first denial; else none.

**The modifier review** (59/XS; consideration only, never a status; 4.7: "target.lesion supported and distinct_from
supported"): a code's own acts (E*) of a distinct-lesion kind (catalogue kind supported in DISTINCT_LESION_KINDS) on
supported lesions, beside another counted code of its session, of another code, whose own such acts' lesions are each
supported distinct (distinct_from supported in either lesion's list) from every one of its own. An unknown identity
never pairs (4.11).

**endoscopic_rows**: code -> PFS row of every (code, PFS row or None) pair that has a row (unchanged).

**What a hold is** (engine/types.HeldFact, 4.4, 4.8): base_included (rank 21; key-bound), competing_codes (rank 22),
separate_em (rank 20; key-bound), event_time (rank 6); each with its cause (coding_rule:<rule>, or for event_time the
date fact's own: reading_unknown, reading_contradicted, appraisal:<verdict or coherence>, unestablished:<reason>;
unlisted for an unlisted act), operator data that names no vendor, and the spans its item quotes (the acts' anchors).
The codes and acts a hold names (BaseIncluded, BaseWithin, the competition's rivals, the ProcedureDay) are returned
beside it, as v1's holds' inputs were: the sentences are step 3c's wording, never built here. ``combine`` applies every
rule to a counted set and gives each member its combination holds (4.1's combine, 4.4's "the combination holds").

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's catalogue, facts, pairing, reading, requirements, requirements_table and types only - no
retired v1 module, none of contract's text modules - holds no word, phrase or marker list (every module-level
collection holds enumeration members or is computed from them), reads no text and returns no document string (a cause
is CPT Studio's own code). ``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import (Attribute, DateRelation, Device, EmBasis, EncounterRelation,
                                                  FactState, Kind, OtherClass, Performer, Purpose, Qualifier2, Reason,
                                                  Result, Separate, SessionKind, Status, Tract, UnlistedWhat,
                                                  VerdictValue)
from studio.interpretation.engine import catalogue, pairing, reading, requirements_table
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.catalogue import TechniqueClass
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, ItemKind, Span

_A = Attribute

# --- the tables (module docstring) ------------------------------------------------------------------------------------

# The E/M families and kinds (lexicon.EM_PROCEDURES' families, lexicon.EM_KINDS): an E/M code gets the same-day rule; an
# act of an E/M kind is never a procedure of the day, nor an act beside its own visit.
EM_FAMILIES: frozenset[SessionKind] = catalogue.EM_FAMILIES
EM_KINDS: frozenset[Kind] = catalogue.EM_KINDS
# DECISIONS D81: the families whose acts make a procedure day - the procedure families and gi.other (another GI
# service). v1's gi.unsupported (D94, NOT_GI) is not here: an act of a non-GI session counts by its kind or, for kind
# other, by its other_class (4.7), never by the family alone.
SAME_DAY_FAMILIES: frozenset[SessionKind] = catalogue.PROCEDURAL_FAMILIES | frozenset({SessionKind.OTHER_GI})
# DECISIONS D109, D111: every kind a procedural family's catalogue entry lists (its acts, bundled and unsupported
# kinds), the examination and the umbrellas - every kind but the visit's, prolonged time, moderate sedation and
# other. Read from THE table of a session family's kinds (requirements_table.FAMILY_KINDS, DECISIONS D191: one table,
# which K2 and possibly's kind arm read too), less moderate sedation and other, which it adds to every procedural
# family; tests/v2/test_combination.py pins it equal to the catalogue entries' kinds (catalogue.FAMILY_ACTS,
# BUNDLED_KINDS and UNSUPPORTED_KINDS: the arbiter's hand-off 1e:R3) with the examination and the umbrellas, and to
# v1's by value.
SAME_DAY_KINDS: frozenset[Kind] = frozenset(
    kind for family in catalogue.PROCEDURAL_FAMILIES
    for kind in requirements_table.FAMILY_KINDS.get(family, frozenset())
    if kind not in (Kind.MODERATE_SEDATION, Kind.OTHER))
# engine.DISTINCT_LESION_KINDS (v1's, by value): the acts a separate-lesion modifier consideration can concern.
DISTINCT_LESION_KINDS: tuple[Kind, ...] = catalogue.REMOVAL_MEMBERS + (Kind.BIOPSY, Kind.ABLATION, Kind.INJECTION,
                                                                       Kind.TATTOO)
# DECISIONS D119: the base rule reads an upper endoscopy's PEG of the encounter's feeding-tube session as its act too.
PEG_FAMILY, PEG_SESSION_KIND = SessionKind.EGD, SessionKind.FEEDING_TUBE
# C-4 (D69, D70, D121): an upper endoscopy within an upper EUS. An EUS whose tract may be pancreatobiliary may be an
# upper EUS examining the pancreas or the biliary tree (v1 read every EUS not placed lower as upper): a possible whole,
# never an established one (the step's NOTES record the question).
WITHIN_FAMILY, WHOLE_FAMILY, WHOLE_TRACT = SessionKind.EGD, SessionKind.EUS, Tract.UPPER
POSSIBLY_UPPER: frozenset[Tract] = frozenset({Tract.UPPER, Tract.PANCREATOBILIARY})
# A status that says the act was done, or begun (v1's verify.POSITIVE; 4.3 row 2).
POSITIVE: frozenset[Status] = reading.POSITIVE
# The date relation of an act done on the date of service (C-3).
ON_DATE: DateRelation = DateRelation.ON_DATE_OF_SERVICE
# The device of a digital examination (FINAL 5.6 E13: no session, no procedure of the day).
DIGITAL: Device = Device.MANUAL
# The performer of another visit whose separate statement the E/M code may read (D113): the documenting team,
# established.
TEAM: Performer = Performer.DOCUMENTING_TEAM
# The family an act counted by its kind or class outside a procedural family is named by (v1: OTHER_GI's label,
# "another GI service"; D109, D130).
OTHER_SERVICE: SessionKind = SessionKind.OTHER_GI


@unique
class Modifier(Enum):
    """checks.DISTINCT_LESION_OPTIONS (v1's, by value): the separate-lesion modifiers a reviewer may choose - none or
    one - offered by the modifier review and never assigned."""
    M59 = '59'
    XS = 'XS'


# The holds' causes (FINAL-V2 4.4), operator data that names no vendor: the coding rule that raises the hold; a fact
# read as unknown or contradicted; an unresolved fact's own appraisal or reason; an unlisted statement.
BASE_CAUSE = 'coding_rule:base_included'
WITHIN_CAUSE = 'coding_rule:base_within'
COMPETING_CAUSE = 'coding_rule:competing_codes'
SAME_DAY_CAUSE = 'coding_rule:same_day_em'
UNLISTED_CAUSE = 'unlisted'
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

# The holds' items at their RANK rows (4.8; engine/requirements.RULES' combination and C3+SEP rows ask exactly these).
BASE_ITEM = rq.Item(rq.Rank.BASE_INCLUDED, rq.FactKey.BASE_INCLUDED)
COMPETING_ITEM = rq.Item(rq.Rank.COMPETING, rq.FactKey.COMPETING_CODES)
SEPARATE_ITEM = rq.Item(rq.Rank.SEPARATE_EM, rq.FactKey.SEPARATE_EM)
TIME_ITEM = rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME)


# --- the records ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Member:
    """One counted code (module docstring): ``key`` its proposal key; ``code`` the code; ``family`` the family it routes
    to; ``session`` the session it is matched to (None: its family has none at this encounter); ``supporting`` its E*;
    ``origin`` who proposed it (kept, never read: D40); ``procedural`` whether it is a procedure (assess._procedural:
    a non-E/M code of a procedure profile, or with a global period other than XXX); ``supported`` whether the per-code
    rule supports it (v1's state performed or incomplete: E* not empty and no held fact)."""
    key: str
    code: str
    family: SessionKind
    session: Id | None = None
    supporting: tuple[Id, ...] = ()
    origin: str = ''
    procedural: bool = False
    supported: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, 'supporting', tuple(self.supporting))


@dataclass(frozen=True, slots=True)
class SessionActs:
    """What the base rule reads of one session from step 4b's event_coding@2 (v1's coding['sessions'][S] 'reportable'
    and 'doubted'; FINAL-V2 4.7's "reportable / doubted | v1's shapes"): ``reportable``, the session's reportable acts
    (done, status performed, kind of the family's catalogue acts, not bundled); ``doubted``, its doubted acts (possibly
    positive with a required fact not supported, or a relation; an act possibly in the session included). Neither holds
    the session's own visit (an E/M kind): the session's own service is never an act beside itself."""
    reportable: tuple[Id, ...] = ()
    doubted: tuple[Id, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, 'reportable', tuple(self.reportable))
        object.__setattr__(self, 'doubted', tuple(self.doubted))


@dataclass(frozen=True, slots=True)
class BaseIncluded:
    """A base code held beside its session's interventions (base_included): ``key``, ``code`` and ``session`` the base
    code's; ``beside`` every other counted code of its family and session that accounts for an act (rule (a));
    ``others`` those of its own EUS tract, the codes the hold names (D177(1)); ``reportable`` and ``doubted`` the acts
    of rules (b) and (c) (with D119's PEG acts), ``unlisted`` the indices in FactSet.unlisted of its session's unlisted
    acts (3.2.6 rule 3)."""
    key: str
    code: str
    session: Id
    beside: tuple[str, ...]
    others: tuple[str, ...]
    reportable: tuple[Id, ...]
    doubted: tuple[Id, ...]
    unlisted: tuple[int, ...]

    @property
    def established(self) -> bool:
        """The examination is established included (an EXPLANATION, 4.8: "an established fact fails" the requirement):
        a reportable act of its session - an intervention established done - holds it (rule (b)). Rule (a) alone, a
        counted code beside it, is no fact: the code may be a proposal with no act documented, whose rejection releases
        the base code (the refutation's F2), so it, like doubted and unlisted acts, holds it as a QUESTION. A code the
        per-code rule supports rests on an established done act, which step 4b lists as reportable, so no fact is lost;
        reading ``Member.supported`` here instead would let the base code's item move with the other code's own facts,
        outside its closure (4.9, P-INDEP)."""
        return bool(self.reportable)

    @property
    def named_codes(self) -> tuple[str, ...]:
        """The codes the hold names (D177(1)): its own tract's codes; with none and no act to name, every code beside it
        (the recorded residual); () when it names acts."""
        if self.others:
            return self.others
        return () if self.reportable or self.doubted or self.unlisted else self.beside


@dataclass(frozen=True, slots=True)
class Whole:
    """A session another session is, or may be, the endoscopic portion of (C3, C-4, D70): ``session`` that whole;
    ``established``, True when C3's part_of_session is supported or C-4's structure established, False when only
    possible (D70: held as one that is, never READY)."""
    session: Id
    established: bool


@dataclass(frozen=True, slots=True)
class BaseWithin:
    """A base code held because its session is (possibly) the endoscopic portion of another (base_within): ``key``,
    ``code`` and ``session`` the base code's; ``wholes`` the sessions it is within; ``within`` the counted codes of
    those sessions that include its family's examination (() when they have no counted code); ``established`` whether an
    established whole holds it."""
    key: str
    code: str
    session: Id
    wholes: tuple[Id, ...]
    within: tuple[str, ...]
    established: bool


@dataclass(frozen=True, slots=True)
class VisitBasis:
    """The documented basis of an E/M visit (v1's combination.visit_basis, contract 9.2's em_basis; FINAL-V2 5.5): the
    visit event whose visit.basis is supported, its value, and the spans of that fact (for wording.quote)."""
    event: Id
    basis: EmBasis
    spans: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class ProceduralCode:
    """A counted code for the procedure day (v1's procedure_day ``codes``): its code and family, whether it is a
    procedure (assess._procedural), and whether the per-code rule supports it."""
    code: str
    family: SessionKind
    procedural: bool
    supported: bool


@dataclass(frozen=True, slots=True)
class ProcedureDay:
    """The procedure day by date of service (C-3; v1's ProcedureDay over ids): ``done`` and ``possible``, the families
    of the procedures documented as done, or possibly done, on the date of service (None for a procedure CPT Studio
    could not identify; OTHER_GI for an act counted by its kind or class outside a procedural family), each once;
    ``done_acts`` and ``possible_acts`` the events that make them; ``undatable`` the procedure events whose date
    relation is not established (an E/M code's event_time, never READY); ``undatable_unlisted`` the indices in
    FactSet.unlisted of the unlisted acts (3.2.6 rule 5). D151 withdrew D144's unidentified, so the reconcile rule reads
    ``done`` alone (D134)."""
    done: tuple[SessionKind | None, ...] = ()
    possible: tuple[SessionKind | None, ...] = ()
    done_acts: tuple[Id, ...] = ()
    possible_acts: tuple[Id, ...] = ()
    undatable: tuple[Id, ...] = ()
    undatable_unlisted: tuple[int, ...] = ()

    @property
    def procedure_day(self) -> bool:
        """A procedure is documented as done, or possibly done, on the date of service."""
        return bool(self.done or self.possible or self.done_acts or self.possible_acts)

    @property
    def established(self) -> bool:
        """A procedure is documented as DONE on the date of service by an act whose every fact that made it a done
        procedure is established (``done_acts``). No weakening can create one (module docstring), which is why it alone
        may moot an undatable act's date for an E/M code. A counted procedural code never establishes the day by itself:
        its support rests on that code's own facts (its reach, its device, its bundling), and the E/M code's hold would
        then move with facts outside its closure (4.9, P-INDEP); a supported code's act is a done act here anyway."""
        return bool(self.done_acts)

    @property
    def undatable_any(self) -> bool:
        """A procedure event, or an unlisted act, whose date CPT Studio could not establish."""
        return bool(self.undatable or self.undatable_unlisted)


@dataclass(frozen=True, slots=True)
class SeparateStatement:
    """The documented statement of a significant, separately identifiable E/M (D113): ``stated`` the visit whose
    separately_identifiable is supported (None: none is); ``denied`` the first visit whose separately_identifiable is
    negated, when none is stated; ``spans`` the spans of the fact that decided (for wording.quote)."""
    stated: Id | None = None
    denied: Id | None = None
    spans: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class Partner:
    """Another counted code of a code's session whose acts lie on lesions each distinct from the code's own: its key,
    code, lesions and acts."""
    key: str
    code: str
    lesions: tuple[Id, ...]
    acts: tuple[Id, ...]


@dataclass(frozen=True, slots=True)
class ModifierReview:
    """The separate-lesion modifier review of one code (review_view._modifier_review's shape, as ids; never assigned):
    its key, code and session; its own lesions and the acts on them; its partners; the modifiers offered."""
    key: str
    code: str
    session: Id
    lesions: tuple[Id, ...]
    acts: tuple[Id, ...]
    partners: tuple[Partner, ...]
    options: tuple[Modifier, ...] = tuple(Modifier)


# --- reading facts ----------------------------------------------------------------------------------------------------


def _fact(R: FactSet, subject: Id | None, attribute: Attribute) -> Fact:
    return facts_.fact(R, subject, attribute)


def _order(R: FactSet) -> Mapping[Id, int]:
    return {event: index for index, event in enumerate(R.events)}


def _ordered(R: FactSet, events: Iterable[Id]) -> tuple[Id, ...]:
    """``events`` each once, in pass 1's order (an id the FactSet does not hold last, in the order given)."""
    order = _order(R)
    found = list(dict.fromkeys(events))
    return tuple(sorted(found, key=lambda event: order.get(event, len(order))))


def _anchor_spans(R: FactSet, events: Iterable[Id]) -> tuple[Span, ...]:
    """The anchor units of ``events``, each once, in document order (what a hold quotes)."""
    return tuple(sorted({span for event in events for span in reading.anchors(reading.Reading.of(R), event)}))


def _unlisted_spans(R: FactSet, indices: Iterable[int]) -> tuple[Span, ...]:
    return tuple(sorted({span for index in indices for span in R.unlisted[index].units}))


def possibly_today(R: FactSet, event: Id) -> bool:
    """4.4's positive-candidate frame: the event is possibly positive (possibly performed or attempted_not_completed),
    its effective date relation is not established as another date and its effective performer is not established as
    another (pairing.positive, other_date, other_performer)."""
    return (pairing.positive(R, event) and not pairing.other_date(R, event)
            and not pairing.other_performer(R, event))


def _possibly_positive_on_date(R: FactSet, event: Id) -> bool:
    """possibly_today without the performer: D55's, D167's and D118's frame (v1's current performed acts were any
    performer's)."""
    return pairing.positive(R, event) and not pairing.other_date(R, event)


def _named_sessions(R: FactSet, event: Id) -> tuple[Id, ...] | None:
    """The sessions ``event``'s session fact may name, by possibly: its supported session; its claimed session and
    options when not established; None (any session) when the slot is silent, negated, or names no id - and when a
    NEGATED claim is not established (its state negated, its result open): "not in X1" left open may be in any
    session, so weakening an established negation never narrows the sessions (9.4 P-MONO; read as its claimed value
    alone, it shrank a code's claims)."""
    found = _fact(R, event, _A.SESSION)
    if found.result is Result.SUPPORTED:
        return (found.value,) if isinstance(found.value, Id) else None
    if facts_.silent(found) or found.result is Result.NEGATED or found.state is FactState.NEGATED:
        return None
    named = tuple(dict.fromkeys(value for value in (found.value, *found.options) if isinstance(value, Id)))
    return named or None


def possible_sessions(R: FactSet, event: Id) -> tuple[Id, ...]:
    """The sessions ``event`` may be in: those its session fact may name; every session of the FactSet when it names
    none (a silent slot). An id the FactSet does not hold is kept: its kind reads as silent, so any family."""
    named = _named_sessions(R, event)
    return tuple(R.sessions) if named is None else named


def _session_may_be(R: FactSet, session: Id, family: SessionKind) -> bool:
    return facts_.possibly(_fact(R, session, _A.KIND), family)


def may_be_of_family(R: FactSet, event: Id, family: SessionKind) -> bool:
    """Whether ``event`` may be in a session of ``family``: a session it may be in (possible_sessions: those its
    session fact may name, every session of the FactSet when it names none) may be of that family; any family when
    the FactSet has no session at all. Not established otherwise: weakening a session or kind fact only widens it."""
    sessions = possible_sessions(R, event)
    if not sessions:
        return True
    return any(_session_may_be(R, session, family) for session in sessions)


def _act_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """Every catalogue kind ``event`` may be for coding (catalogue.catalogue_kind, read by possibly): each kind its
    kind fact makes possible (facts.possibly: its value, its options, its control's sibling); a clip or an injection
    whose purpose is supported hemostasis is a bleeding control only (COMMON_BUNDLED's clip rule: no injection code
    accounts for it, as v1's never did), and one whose purpose may be hemostasis is both (D157's doubt, kept as a rule
    over facts, 4.13)."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    hemostatic = kinds & catalogue.HEMOSTASIS_KINDS
    if not hemostatic:
        return kinds
    purpose = _fact(R, event, _A.PURPOSE)
    if facts_.holds(purpose, Purpose.HEMOSTASIS):
        return (kinds - hemostatic) | frozenset({Kind.BLEEDING_CONTROL})
    if facts_.possibly(purpose, Purpose.HEMOSTASIS):
        return kinds | frozenset({Kind.BLEEDING_CONTROL})
    return kinds


def _may_be_of(R: FactSet, event: Id, wanted: frozenset[Kind]) -> frozenset[Kind]:
    """The kinds of ``wanted`` that ``event`` may be as an act (_act_kinds, read by possibly; a tattoo and an injection
    are one act for coding, catalogue.ONE_ACT). An umbrella act (removal, intervention: its kind established as the
    umbrella) is none of its members by possibly (4.2: an established fact makes possible exactly its value), so no
    code claims it, as v1's READY codes never did; a doubt's reading of a member makes it that member."""
    kinds = _act_kinds(R, event)
    return frozenset(target for target in wanted if target in kinds
                     or (target in catalogue.ONE_ACT and bool(kinds & catalogue.ONE_ACT)))


def _cause(found: Fact) -> str:
    """The cause of a question resting on ``found`` (FINAL-V2 4.4): reading_unknown (silent or doubted),
    reading_contradicted, appraisal:<verdict or coherence> for an appraisal reason, unestablished:<reason> for any other
    reason of an unresolved fact, and SAME_DAY_CAUSE for an established fact (the rule's own doubt)."""
    if found.result is Result.UNKNOWN:
        return READING_UNKNOWN
    if found.result is Result.CONTRADICTED:
        return READING_CONTRADICTED
    if found.result is not Result.UNRESOLVED:
        return SAME_DAY_CAUSE
    reason = found.reasons[0] if found.reasons else None
    if reason is None:
        return UNESTABLISHED
    appraisal = APPRAISAL_CAUSES.get(reason)
    if appraisal is not None:
        return f'appraisal:{appraisal.value}'
    return f'{UNESTABLISHED}:{reason.value}'


def _key(item: rq.Item) -> str:
    return rq.fact_key(item.fact)


def _rank(item: rq.Item) -> int | None:
    return item.rank.value if item.rank is not None else None


# --- the codes --------------------------------------------------------------------------------------------------------


def is_base(code: str) -> bool:
    """v1's _base: a base profile (CodeProfile.base: an endoscopic family's diagnostic examination, or an office visit
    code - two E/M codes of one visit hold each other), or a code whose covers are all the examination (an
    examination-only EUS code: 43231, 43237, 43259, 45341, 45391, 44406). An E/M add-on (99417) is neither."""
    profile = catalogue.code_profile(code)
    if profile is None:
        return False
    return profile.base or (bool(profile.covers) and all(kind is Kind.EXAMINATION for kind in profile.covers))


def accounts_for_an_act(code: str) -> bool:
    """Whether a code's profile covers a kind (v1's base rule (a): "another counted code ... that accounts for an
    act")."""
    profile = catalogue.code_profile(code)
    return profile is not None and bool(profile.covers)


# --- the competition's claims (D40, D55, D74, D104, D118, D163, D167) -------------------------------------------------


def _technique_fits(R: FactSet, technique: TechniqueClass | None, event: Id) -> bool:
    """R4: an act a technique code may account for - its device not established as another technique class (a device
    supported in a class other than the code's; a device of no class, or not established, may be the code's)."""
    if technique is None:
        return True
    device = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if device.result is not Result.SUPPORTED or not isinstance(device.value, Device):
        return True
    found = catalogue.technique_class(device.value)
    return found is None or found is technique


def _read_under(R: FactSet, event: Id, family: SessionKind, kinds: frozenset[Kind]) -> bool:
    """catalogue.READ_UNDER over facts: ``event`` may be in a session of a family whose act of one of ``kinds`` is read
    under ``family``. The rule's regions are not read: a place list may be short, and an act set outside them by its
    listed places alone could lose a claim to a deleted member (P6; module docstring)."""
    return any(under is family and kind in kinds and may_be_of_family(R, event, owner)
               for (owner, kind), (under, _regions) in catalogue.READ_UNDER.items())


def may_account_for(code: str, R: FactSet, event: Id) -> bool:
    """Whether ``code`` may account for ``event`` (the OWN arm of ``claims``; module docstring): a candidate of one of
    its requirement groups, possibly today's (4.4's frame), possibly of its family (route (b): of any family) and of
    its technique class. No place list is read: a site or region difference read from listed places could release a
    rival when a member is deleted (P6)."""
    spec = rq.spec(code)
    wanted = frozenset(kind for group in spec.groups for kind in group)
    if not wanted:
        return False
    kinds = _may_be_of(R, event, wanted)
    if not kinds or not possibly_today(R, event):
        return False
    link = catalogue.code_link(code)
    if link.route is not catalogue.LinkRoute.UNRECONCILED and not (
            may_be_of_family(R, event, spec.family) or _read_under(R, event, spec.family, kinds)):
        return False
    return _technique_fits(R, link.technique, event)


def _possible_lesion_values(found: Fact) -> frozenset[Id]:
    """The lesion ids a target.lesion fact may name: its supported value; its claimed value and options when not
    established; none when silent or negated."""
    if found.result is Result.SUPPORTED:
        return frozenset({found.value}) if isinstance(found.value, Id) else frozenset()
    if facts_.silent(found) or found.result is Result.NEGATED:
        return frozenset()
    return frozenset(value for value in (found.value, *found.options) if isinstance(value, Id))


def one_stricture(R: FactSet, first: Id, second: Id) -> bool:
    """DECISIONS D118 over facts ("one stricture by same lesion or places not disjoint", 4.7), erring toward one: the
    two acts' lesions possibly the same (a lesion both may name); else neither set apart by lesion
    (facts.apart_by_lesion: both supported and different, distinct_from supported, the lesion pair controls rejected)
    nor by place (facts.apart_by_place: established, disjoint, the pair controls rejected). An unknown identity never
    sets two acts apart (4.11)."""
    if _possible_lesion_values(_fact(R, first, _A.TARGET_LESION)) & _possible_lesion_values(
            _fact(R, second, _A.TARGET_LESION)):
        return True
    return not (facts_.apart_by_lesion(R, first, second) or facts_.apart_by_place(R, first, second))


def _defining_extras(code: str, R: FactSet, supporting: Sequence[Id]) -> tuple[Id, ...]:
    """D55, D74, D104, D167 (module docstring): the acts of a narrowed code's other covered kinds, once its family has
    an act that may be of a defining kind, possibly positive and not established at another date, or its E* is not
    empty."""
    link = catalogue.code_link(code)
    if not link.defining:
        return ()
    others = frozenset(link.acts) - frozenset(link.defining)
    if not others:
        return ()
    defining = frozenset(link.defining)

    def of_family(event: Id, kinds: frozenset[Kind]) -> bool:
        return (bool(_may_be_of(R, event, kinds)) and _possibly_positive_on_date(R, event)
                and may_be_of_family(R, event, link.family))

    if not supporting and not any(of_family(event, defining) for event in R.events):
        return ()
    return tuple(event for event in R.events if event not in supporting and of_family(event, others))


def _stricture_claims(code: str, R: FactSet, own: Sequence[Id]) -> tuple[Id, ...]:
    """D118 (module docstring): a technique code's claims on ONE stricture with ANOTHER act of its own - the acts of its
    family that may be of its kinds, possibly positive and not established at another date, any performer and any
    technique."""
    link = catalogue.code_link(code)
    if link.technique is None or not own:
        return ()
    kinds = frozenset(link.acts)
    return tuple(event for event in R.events
                 if _may_be_of(R, event, kinds) and _possibly_positive_on_date(R, event)
                 and may_be_of_family(R, event, link.family)
                 and any(mine != event and one_stricture(R, mine, event) for mine in own))


def claims(code: str, R: FactSet, supporting: Sequence[Id] = ()) -> tuple[Id, ...]:
    """The acts ``code`` claims for the competition (module docstring; v1's assess._claims as FINAL-V2 4.7 and 4.8
    rewire it), whatever the code's state: its E* and every act it may account for (OWN), D55's and D167's acts of a
    narrowed code's other kinds, and D118's acts on one stricture - E* first, in the order given, then pass 1's order.
    An act of E* a technique code cannot account for (its device established as another technique class) is not
    claimed (R4)."""
    link = catalogue.code_link(code)
    given = tuple(dict.fromkeys(event for event in supporting if _technique_fits(R, link.technique, event)))
    own = given + tuple(event for event in R.events if event not in given and may_account_for(code, R, event))
    found = list(own)
    for event in _defining_extras(code, R, supporting) + _stricture_claims(code, R, own):
        if event not in found:
            found.append(event)
    head = [event for event in found if event in given]
    tail = [event for event in found if event not in given]
    return tuple(head) + _ordered(R, tail)


def competition(entries: Sequence[tuple[str, str, str, Sequence[Id]]]) -> dict[str, tuple[str, ...]]:
    """FINAL 7.9 Competing, as the installed engine's completion repair and DECISIONS D40 amend P-ADMIT2 (v1's,
    unchanged): ``entries`` (key, code, origin, claims) of the counted codes; two of them with different codes whose
    claims intersect - the same documented act - are each held with one question naming the others, WHOEVER proposed
    either. ``origin`` is kept in the entry and never read. {key: the rival codes, in entry order, each once} of every
    held code."""
    out: dict[str, tuple[str, ...]] = {}
    for key, code, _origin, supporting in entries:
        mine = frozenset(supporting)
        rivals = [other_code for other_key, other_code, _other_origin, other_events in entries
                  if other_key != key and other_code != code and mine & frozenset(other_events)]
        if rivals:
            out[key] = tuple(dict.fromkeys(rivals))
    return out


def contested(entries: Sequence[tuple[str, str, str, Sequence[Id]]]) -> dict[str, tuple[Id, ...]]:
    """For every code ``competition`` holds, the acts it shares with its rivals, in its claims' order (the acts its
    competing_codes item quotes)."""
    out: dict[str, tuple[Id, ...]] = {}
    for key, code, _origin, supporting in entries:
        shared = [event for event in supporting
                  if any(other_key != key and other_code != code and event in other_events
                         for other_key, other_code, _other_origin, other_events in entries)]
        if shared:
            out[key] = tuple(dict.fromkeys(shared))
    return out


# --- base (engine.base_included; FINAL 7.9, D119, D177(1), 3.2.6 rule 3) ----------------------------------------------


def session_acts(coding: Mapping[Id, SessionActs], session: Id) -> SessionActs:
    """Step 4b's reportable and doubted acts of ``session`` (module docstring). event_coding@2 lists every session of
    the FactSet, so a session ``coding`` does not list is a wiring error: ValueError, never "no acts" (the
    refutation's F5: read as empty, it would release a base code beside acts nobody listed)."""
    found = coding.get(session)
    if found is None:
        raise ValueError(f'coding lists no session {session}: event_coding@2 lists every session of the FactSet.')
    return found


def _peg_acts(R: FactSet, coding: Mapping[Id, SessionActs], session: Id) -> SessionActs:
    """DECISIONS D119: the reportable and the doubted acts of every OTHER session (of the FactSet, and any other
    ``coding`` lists) whose kind may be the feeding tube's, that may be PEG placements - each such session read through
    ``session_acts``, so one missing from ``coding`` is refused, never skipped."""
    reportable: list[Id] = []
    doubted: list[Id] = []
    for other in dict.fromkeys((*R.sessions, *coding)):
        if other == session or not _session_may_be(R, other, PEG_SESSION_KIND):
            continue
        acts = session_acts(coding, other)
        reportable += [event for event in acts.reportable if facts_.possibly(_fact(R, event, _A.KIND), Kind.PEG)]
        doubted += [event for event in acts.doubted if facts_.possibly(_fact(R, event, _A.KIND), Kind.PEG)]
    return SessionActs(tuple(reportable), tuple(doubted))


def _unlisted_acts(R: FactSet, session: Id) -> tuple[int, ...]:
    """FINAL-V2 3.2.6 rule 3: the indices of the kept unlisted acts whose session card is ``session``."""
    return tuple(index for index, entry in enumerate(R.unlisted)
                 if entry.what is UnlistedWhat.ACT and entry.session == session)


def base_included(members: Sequence[Member], coding: Mapping[Id, SessionActs], R: FactSet) -> tuple[BaseIncluded, ...]:
    """A family's base code matched to session S is held, never excluded, beside (a) another counted code of its family
    matched to S that accounts for an act, (b) S's reportable acts, or (c) S's doubted acts and unlisted acts (module
    docstring), in member order. ValueError when ``coding`` does not list S (or, for D119, a session that may be the
    feeding tube's): step 4b lists every session (``session_acts``)."""
    found: list[BaseIncluded] = []
    for index, member in enumerate(members):
        session = member.session
        if session is None or not is_base(member.code):
            continue
        acts = session_acts(coding, session)
        beside = tuple(other.code for position, other in enumerate(members)
                       if position != index and other.family is member.family and other.session == session
                       and accounts_for_an_act(other.code))
        tract = catalogue.eus_tract(member.code)
        others = tuple(code for code in beside if catalogue.eus_tract(code) is tract)  # D177 (1)
        reportable, doubted = acts.reportable, acts.doubted
        if member.family is PEG_FAMILY:  # D119
            pegs = _peg_acts(R, coding, session)
            reportable, doubted = reportable + pegs.reportable, doubted + pegs.doubted
        reportable = _ordered(R, reportable)
        doubted = tuple(event for event in _ordered(R, doubted) if event not in reportable)
        unlisted = _unlisted_acts(R, session)
        if beside or reportable or doubted or unlisted:
            found.append(BaseIncluded(key=member.key, code=member.code, session=session, beside=tuple(
                dict.fromkeys(beside)), others=tuple(dict.fromkeys(others)), reportable=reportable, doubted=doubted,
                unlisted=unlisted))
    return tuple(found)


# --- base-within (C3, C-4, D70) ---------------------------------------------------------------------------------------


def _manual(R: FactSet, event: Id) -> bool:
    """FINAL 5.6 E13: an examination whose device is supported manual (a digital examination) is no session."""
    return (facts_.holds(_fact(R, event, _A.KIND), Kind.EXAMINATION)
            and facts_.holds(_fact(R, event, _A.TECHNIQUE_DEVICE), Device.MANUAL))


def _examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The session's established examinations: kind supported examination, session supported ``session``, a digital
    examination excepted (E13)."""
    return tuple(event for event in R.events
                 if facts_.holds(_fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(_fact(R, event, _A.SESSION), session) and not _manual(R, event))


def _may_be_examination_of(R: FactSet, session: Id, event: Id) -> bool:
    """``event`` may be ``session``'s examination (D62's possible examination): its kind possibly the examination, the
    session possibly ``session``, possibly today's (4.4's frame), not an established digital examination."""
    return (facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION) and session in possible_sessions(R, event)
            and possibly_today(R, event) and not _manual(R, event))


def session_done(R: FactSet, session: Id) -> bool:
    """A session is done (4.3 row 7: "its examination, when it has one, passes 2-5 (an act-only session: the act
    itself)"; 4.7's "done = 4.3 rows 2-5"): one of its established examinations passes rows 2-5 (reading.done); with
    none, one of its acts (session supported) passes them - a session told only through its acts (D121, D135) - and no
    event that may be its examination is left open (the refutation's F3: an examination whose date is not established
    beside a done FNA leaves the EUS only possibly done). A digital examination is excepted throughout (E13)."""
    view = reading.Reading.of(R)
    exams = _examinations(R, session)
    if exams:
        return any(reading.done(view, event) for event in exams)
    if any(_may_be_examination_of(R, session, event) and not reading.done(view, event) for event in R.events):
        return False
    return any(facts_.holds(_fact(R, event, _A.SESSION), session) and reading.done(view, event)
               and not _manual(R, event) for event in R.events)


def session_possibly_done(R: FactSet, session: Id) -> bool:
    """A session may be done: an event its session fact may name it, possibly today's (4.4's frame)."""
    return any(session in possible_sessions(R, event) and possibly_today(R, event) and not _manual(R, event)
               for event in R.events)


def wholes(R: FactSet, session: Id) -> tuple[Whole, ...]:
    """The sessions ``session`` is, or may be, the endoscopic portion of (module docstring: C3, C-4, D70), in the
    FactSet's session order, each once (an established whole before a possible one of the same session)."""
    found: dict[Id, bool] = {}
    part = _fact(R, session, _A.PART_OF_SESSION)
    if part.result is Result.SUPPORTED and isinstance(part.value, Id) and part.value != session:
        found[part.value] = True  # C3
    elif part.result in facts_.OPEN and not facts_.silent(part):
        for value in (part.value, *part.options):
            if isinstance(value, Id) and value != session:
                found.setdefault(value, False)  # D70, by possibly
    kind = _fact(R, session, _A.KIND)
    if facts_.possibly(kind, WITHIN_FAMILY) and session_possibly_done(R, session):
        done = facts_.holds(kind, WITHIN_FAMILY) and session_done(R, session)
        for other in R.sessions:
            if other == session:
                continue
            other_kind, tract = _fact(R, other, _A.KIND), _fact(R, other, _A.TRACT)
            if not (facts_.possibly(other_kind, WHOLE_FAMILY)
                    and any(facts_.possibly(tract, value) for value in POSSIBLY_UPPER)
                    and session_possibly_done(R, other)):
                continue
            established = (done and facts_.holds(other_kind, WHOLE_FAMILY) and facts_.holds(tract, WHOLE_TRACT)
                           and session_done(R, other))
            found[other] = found.get(other, False) or established  # C-4; D70 when only possible
    order = {item: position for position, item in enumerate(R.sessions)}
    return tuple(Whole(item, established) for item, established in
                 sorted(found.items(), key=lambda pair: order.get(pair[0], len(order))))


def base_within(members: Sequence[Member], R: FactSet) -> tuple[BaseWithin, ...]:
    """engine.base_within over facts (module docstring): a base code whose session is (possibly) the endoscopic portion
    of another is held - beside the counted codes of that session that include its family's examination, or beside none
    when that session has no counted code. No entry when the code is no base, its session is (possibly) part of no
    other, or that session's counted codes include no such examination. In member order."""
    found: list[BaseWithin] = []
    for index, member in enumerate(members):
        session = member.session
        if session is None or not is_base(member.code):
            continue
        within: list[str] = []
        held: list[Id] = []
        established = False
        for whole in wholes(R, session):
            including = [other.code for position, other in enumerate(members)
                         if position != index and other.session == whole.session]
            codes = [code for code in including if catalogue.includes_examination(code, member.family)]
            if including and not codes:
                continue
            within += codes
            held.append(whole.session)
            established = established or whole.established
        if held:
            found.append(BaseWithin(key=member.key, code=member.code, session=session, wholes=tuple(held),
                                    within=tuple(dict.fromkeys(within)), established=established))
    return tuple(found)


# --- the same-day E/M (C-3; D81, D94, D109, D111, D130, D133, D134) ---------------------------------------------------


def _procedural_family(R: FactSet, event: Id) -> bool:
    """The event may be in a session of a SAME_DAY_FAMILY (every session of the FactSet when its session fact names
    none)."""
    return any(_session_may_be(R, session, family) for session in possible_sessions(R, event)
               for family in SAME_DAY_FAMILIES)


def _established_family(R: FactSet, event: Id) -> SessionKind | None:
    """The event's session family when its session and that session's kind are both supported."""
    return facts_.session_family(R, event)


def _established_kind(R: FactSet, event: Id) -> Kind | None:
    """The event's kind when it is established a SAME_DAY_KIND and, for an examination, established no digital
    examination (E13: its device supported other than manual, or manual negated); None otherwise. A digital examination
    left open (its device silent or not established) may be no procedure at all, so it is never a DONE procedure by its
    kind: weakening a device supported manual must never create a done procedure (the refutation's F1)."""
    kind = _fact(R, event, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, Kind) or kind.value not in SAME_DAY_KINDS:
        return None
    if kind.value is not Kind.EXAMINATION:
        return kind.value
    device = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if device.result is Result.SUPPORTED and device.value != DIGITAL:
        return kind.value
    if device.result is Result.NEGATED and device.value == DIGITAL:
        return kind.value
    return None


def procedure_day(R: FactSet, codes: Sequence[ProceduralCode] = ()) -> ProcedureDay:
    """The procedure day by DATE OF SERVICE (C-3; module docstring), over the FactSet (the caller passes
    facts.effective's, so every date relation is re-judged against the effective date) and the counted codes."""
    done: list[SessionKind | None] = []
    possible: list[SessionKind | None] = []
    done_acts: list[Id] = []
    possible_acts: list[Id] = []
    undatable: list[Id] = []
    for event in R.events:
        kinds = facts_.possible_kinds(R, event, of_family=False)
        if kinds <= EM_KINDS:
            continue  # the visit, prolonged visit time: never a procedure of the day
        manual = _manual(R, event)
        by_family = _procedural_family(R, event)
        by_kind = bool(kinds & SAME_DAY_KINDS) and not manual
        by_class = Kind.OTHER in kinds and facts_.possibly(_fact(R, event, _A.OTHER_CLASS), OtherClass.PROCEDURE)
        if not (by_family or by_kind or by_class) or not pairing.positive(R, event):
            continue
        date = _fact(R, event, _A.DATE_RELATION)
        if pairing.other_date(R, event):
            continue  # C-3: another date
        if not facts_.holds(date, ON_DATE):
            undatable.append(event)  # UNRESOLVED(time): an E/M code's event_time, never READY
            continue
        family = _established_family(R, event)
        status = _fact(R, event, _A.STATUS)
        family_done = family is not None and family in SAME_DAY_FAMILIES
        kind_done = _established_kind(R, event) is not None
        label = family if family_done else OTHER_SERVICE if (by_kind or by_class) else None
        if (status.result is Result.SUPPORTED and isinstance(status.value, Status) and status.value in POSITIVE
                and (family_done or kind_done)):
            done.append(label)
            done_acts.append(event)
        else:
            possible.append(label)
            possible_acts.append(event)
    for code in codes:
        if not code.procedural:
            continue
        (done if code.supported else possible).append(code.family)
    unlisted = tuple(index for index, entry in enumerate(R.unlisted)
                     if entry.what is UnlistedWhat.ACT and entry.kind not in EM_KINDS)
    families = tuple(dict.fromkeys(done))
    return ProcedureDay(done=families, possible=tuple(item for item in dict.fromkeys(possible) if item not in families),
                        done_acts=tuple(done_acts), possible_acts=tuple(possible_acts), undatable=tuple(undatable),
                        undatable_unlisted=unlisted)


def _today_visit(R: FactSet, event: Id) -> bool:
    """A visit of this encounter (D113's "TODAY's visit"): kind supported em_visit, date relation supported on the date
    of service, its session's encounter supported this_encounter, its performer supported documenting_team. Every
    condition is established, so a weakening never adds a visit (v1's "no performer verified to another" did: the
    module docstring)."""
    if not facts_.holds(_fact(R, event, _A.KIND), Kind.EM_VISIT):
        return False
    if not (facts_.holds(_fact(R, event, _A.DATE_RELATION), ON_DATE)
            and facts_.holds(_fact(R, event, _A.PERFORMER), TEAM)):
        return False
    session = _fact(R, event, _A.SESSION)
    return (session.result is Result.SUPPORTED and isinstance(session.value, Id)
            and facts_.holds(_fact(R, session.value, _A.ENCOUNTER), EncounterRelation.THIS_ENCOUNTER))


def separate_statement(R: FactSet, visit_events: Sequence[Id]) -> SeparateStatement:
    """The documented statement of a significant, separately identifiable E/M (module docstring; D113), read from the
    code's own visit events ``visit_events``, then from every other visit of this encounter: the first supported
    statement; else the first denial; else none."""
    own = [event for event in dict.fromkeys(visit_events) if event in R.events]
    today = [event for event in R.events if event not in own and _today_visit(R, event)]
    visits = own + today
    for event in visits:
        found = _fact(R, event, _A.VISIT_SEPARATELY_IDENTIFIABLE)
        if facts_.holds(found, Separate.STATED):
            return SeparateStatement(stated=event, spans=found.spans)
    for event in visits:
        found = _fact(R, event, _A.VISIT_SEPARATELY_IDENTIFIABLE)
        if facts_.denied(found, Separate.STATED):
            return SeparateStatement(denied=event, spans=found.spans)
    return SeparateStatement()


def visit_basis(R: FactSet, visit_events: Sequence[Id]) -> VisitBasis | None:
    """v1's visit_basis over facts (FINAL-V2 5.5): the first of ``visit_events`` whose visit.basis is supported (v1's
    usable basis; EmBasis holds no not_stated, 1.4), with its value and spans; None when none is. Whether R6:em_basis is
    met is step 4a's row (4.3); this is the value the support display shows (v1's assess._inventory_fact 'em_basis')."""
    for event in dict.fromkeys(visit_events):
        found = _fact(R, event, _A.VISIT_BASIS)
        if found.result is Result.SUPPORTED and isinstance(found.value, EmBasis):
            return VisitBasis(event=event, basis=found.value, spans=found.spans)
    return None


def separate_em_hold(member: Member, R: FactSet, day: ProcedureDay, statement: SeparateStatement) -> HeldFact:
    """The separate_em hold of an E/M code on a procedure day with no separate statement (4.3 C3+SEP): an EXPLANATION
    quoting the denial when the visit's separately_identifiable is negated, a QUESTION otherwise; the spans are the
    denial's and the procedure acts'."""
    subject = statement.denied if statement.denied is not None else next(iter(member.supporting), None)
    found = _fact(R, subject, _A.VISIT_SEPARATELY_IDENTIFIABLE) if subject is not None else None
    denied = statement.denied is not None
    spans = tuple(sorted(set(statement.spans) | set(_anchor_spans(R, day.done_acts + day.possible_acts))))
    return HeldFact(fact=_key(SEPARATE_ITEM), attribute=_A.VISIT_SEPARATELY_IDENTIFIABLE, subject=subject,
                    result=found.result if found is not None else None,
                    kind=ItemKind.EXPLANATION if denied else ItemKind.QUESTION, cause=SAME_DAY_CAUSE,
                    reason=found.reasons[0] if found is not None and found.reasons and not denied else None,
                    spans=spans, rank=_rank(SEPARATE_ITEM))


def event_time_holds(R: FactSet, day: ProcedureDay) -> tuple[HeldFact, ...]:
    """An E/M code's event_time holds with no established procedure day (C-3: UNRESOLVED(time), never READY;
    same_day_holds): one per undatable procedure event, its cause the date relation's own, then one per unlisted act
    (cause unlisted)."""
    out: list[HeldFact] = []
    for event in day.undatable:
        found = _fact(R, event, _A.DATE_RELATION)
        out.append(HeldFact(fact=_key(TIME_ITEM), attribute=_A.DATE_RELATION, subject=event, result=found.result,
                            kind=ItemKind.QUESTION, cause=_cause(found),
                            reason=found.reasons[0] if found.reasons else None, spans=_anchor_spans(R, (event,)),
                            rank=_rank(TIME_ITEM)))
    for index in day.undatable_unlisted:
        out.append(HeldFact(fact=_key(TIME_ITEM), attribute=_A.DATE_RELATION, subject=None, result=None,
                            kind=ItemKind.QUESTION, cause=UNLISTED_CAUSE, reason=None,
                            spans=_unlisted_spans(R, (index,)), rank=_rank(TIME_ITEM)))
    return tuple(out)


def same_day_holds(member: Member, R: FactSet, day: ProcedureDay) -> tuple[HeldFact, ...]:
    """The same-day rule's holds of one counted code (module docstring): () for a code outside the E/M families; on a
    procedure day (done or possible) with no separate statement documented, separate_em; otherwise, with an undatable
    act and no ESTABLISHED procedure day, event_time for each undatable act (C-3: never READY); otherwise none. v1 asked
    event_time only with no procedure day, so a possible procedure day a weakening created released a code held for an
    undatable act (the refutation's F1); here only an established procedure day, which no weakening creates, moots the
    undatable act's date."""
    if member.family not in EM_FAMILIES:
        return ()
    statement = separate_statement(R, member.supporting)
    if day.procedure_day and statement.stated is None:
        return (separate_em_hold(member, R, day, statement),)
    if day.undatable_any and not day.established:
        return event_time_holds(R, day)
    return ()


# --- the separate-lesion modifier review (FINAL 7.9; 4.7) -------------------------------------------------------------


def _distinct_lesion_act(R: FactSet, event: Id) -> Id | None:
    """The supported lesion of an act of a distinct-lesion kind (its kind supported, read as the catalogue kind with its
    supported purpose, in DISTINCT_LESION_KINDS); None otherwise."""
    kind = _fact(R, event, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, Kind):
        return None
    purpose = _fact(R, event, _A.PURPOSE)
    named = catalogue.catalogue_kind(kind.value, purpose.value if purpose.result is Result.SUPPORTED
                                     and isinstance(purpose.value, Purpose) else None)
    if named is None or named not in DISTINCT_LESION_KINDS:
        return None
    lesion = _fact(R, event, _A.TARGET_LESION)
    return lesion.value if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id) else None


def lesions_distinct(R: FactSet, first: Id, second: Id) -> bool:
    """Two supported lesions established distinct: different ids, distinct_from supported in either lesion's list."""
    if first == second:
        return False
    return (any(facts_.holds(member, second) for member in facts_.members(R, first, _A.DISTINCT_FROM))
            or any(facts_.holds(member, first) for member in facts_.members(R, second, _A.DISTINCT_FROM)))


def _lesion_acts(R: FactSet, events: Sequence[Id]) -> tuple[tuple[Id, ...], tuple[Id, ...]]:
    lesions: list[Id] = []
    acts: list[Id] = []
    for event in events:
        lesion = _distinct_lesion_act(R, event)
        if lesion is None:
            continue
        acts.append(event)
        if lesion not in lesions:
            lesions.append(lesion)
    return tuple(lesions), tuple(acts)


def modifier_review(R: FactSet, member: Member, members: Sequence[Member]) -> ModifierReview | None:
    """The separate-lesion modifier review of ``member`` (module docstring): its own acts lie on supported lesions, and
    another counted code of its session, of another code, accounts for acts on lesions every one of which is
    established distinct from every one of its own. None otherwise."""
    session = member.session
    lesions, acts = _lesion_acts(R, member.supporting)
    if session is None or not lesions:
        return None
    partners: list[Partner] = []
    for other in members:
        if other.key == member.key or other.code == member.code or other.session != session:
            continue
        theirs, their_acts = _lesion_acts(R, other.supporting)
        if theirs and all(lesions_distinct(R, one, two) for one in lesions for two in theirs):
            partners.append(Partner(key=other.key, code=other.code, lesions=theirs, acts=their_acts))
    if not partners:
        return None
    return ModifierReview(key=member.key, code=member.code, session=session, lesions=lesions, acts=acts,
                          partners=tuple(partners))


# --- the endoscopic rows ----------------------------------------------------------------------------------------------


def endoscopic_rows(pairs: Iterable[tuple[str, Mapping[str, object] | None]]) -> dict[str, Mapping[str, object]]:
    """engine.endoscopic_rows (v1's, unchanged): code -> PFS row of every (code, PFS row or None) pair that has a
    row."""
    return {code: pfs for code, pfs in pairs if pfs}


# --- the holds --------------------------------------------------------------------------------------------------------


def base_hold(found: BaseIncluded, R: FactSet) -> HeldFact:
    """The base_included hold (rank 21, key-bound): an EXPLANATION when the examination is established included (rules
    (a), (b)), a QUESTION when only doubted or unlisted acts hold it; its subject the session; its spans the acts'."""
    spans = tuple(sorted(set(_anchor_spans(R, found.reportable + found.doubted))
                         | set(_unlisted_spans(R, found.unlisted))))
    return HeldFact(fact=_key(BASE_ITEM), attribute=None, subject=found.session, result=None,
                    kind=ItemKind.EXPLANATION if found.established else ItemKind.QUESTION, cause=BASE_CAUSE,
                    reason=None, spans=spans, rank=_rank(BASE_ITEM))


def _session_spans(R: FactSet, sessions: Iterable[Id]) -> tuple[Span, ...]:
    """The anchors of the examinations of ``sessions``: the events whose kind may be the examination and whose session
    fact names one of them."""
    wanted = frozenset(sessions)
    return _anchor_spans(R, (event for event in R.events
                             if facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION)
                             and any(session in wanted for session in _named_sessions(R, event) or ())))


def base_within_hold(found: BaseWithin, R: FactSet) -> HeldFact:
    """The base_within hold (fact base_included, rank 21): an EXPLANATION when an established whole holds it, a QUESTION
    when only a possible one does; its subject the session; its spans the anchors of the examinations of the code's
    session and its wholes."""
    return HeldFact(fact=_key(BASE_ITEM), attribute=None, subject=found.session, result=None,
                    kind=ItemKind.EXPLANATION if found.established else ItemKind.QUESTION, cause=WITHIN_CAUSE,
                    reason=None, spans=_session_spans(R, (found.session, *found.wholes)), rank=_rank(BASE_ITEM))


def competing_hold(acts: Sequence[Id], R: FactSet) -> HeldFact:
    """The competing_codes hold (rank 22): a QUESTION naming no single fact; its subject the first act it shares with
    its rivals; its spans those acts' anchors."""
    return HeldFact(fact=_key(COMPETING_ITEM), attribute=None, subject=next(iter(acts), None), result=None,
                    kind=ItemKind.QUESTION, cause=COMPETING_CAUSE, reason=None, spans=_anchor_spans(R, acts),
                    rank=_rank(COMPETING_ITEM))


# --- the set level (4.1's combine) ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Combination:
    """What the combination rules give a counted set (4.1's combine): ``claims`` each member's claims; ``bases``,
    ``within`` and ``competes`` (the rival codes) and ``contested`` (the shared acts) for each member they hold;
    ``day`` the procedure day; ``statements`` each E/M member's separate statement; ``reviews`` each member's modifier
    review; ``held`` each member's combination holds - base_included (or base-within when base_included does not hold
    it, v1's order), competing_codes, then the same-day rule's. Every mapping is keyed by member key and frozen."""
    claims: Mapping[str, tuple[Id, ...]]
    bases: Mapping[str, BaseIncluded]
    within: Mapping[str, BaseWithin]
    competes: Mapping[str, tuple[str, ...]]
    contested: Mapping[str, tuple[Id, ...]]
    day: ProcedureDay
    statements: Mapping[str, SeparateStatement]
    reviews: Mapping[str, ModifierReview]
    held: Mapping[str, tuple[HeldFact, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'claims', MappingProxyType(dict(self.claims)))
        object.__setattr__(self, 'bases', MappingProxyType(dict(self.bases)))
        object.__setattr__(self, 'within', MappingProxyType(dict(self.within)))
        object.__setattr__(self, 'competes', MappingProxyType(dict(self.competes)))
        object.__setattr__(self, 'contested', MappingProxyType(dict(self.contested)))
        object.__setattr__(self, 'statements', MappingProxyType(dict(self.statements)))
        object.__setattr__(self, 'reviews', MappingProxyType(dict(self.reviews)))
        object.__setattr__(self, 'held', MappingProxyType(dict(self.held)))


def combine(members: Sequence[Member], coding: Mapping[Id, SessionActs], R: FactSet) -> Combination:
    """Every combination rule over the counted ``members`` (4.1's combine; 4.4's "the combination holds (base,
    base-within, competing, separate_em, event_time)"): ``coding`` is step 4b's reportable and doubted acts per session,
    ``R`` the FactSet as assess reads it (facts.effective's). Pure: identical inputs give identical outputs (P-DET)."""
    claimed = {member.key: claims(member.code, R, member.supporting) for member in members}
    entries = [(member.key, member.code, member.origin, claimed[member.key]) for member in members]
    competes = competition(entries)
    shared = contested(entries)
    bases = {found.key: found for found in base_included(members, coding, R)}
    within = {found.key: found for found in base_within(members, R)}
    day = procedure_day(R, tuple(ProceduralCode(member.code, member.family, member.procedural, member.supported)
                                 for member in members))
    statements = {member.key: separate_statement(R, member.supporting) for member in members
                  if member.family in EM_FAMILIES}
    reviews = {member.key: review for member in members
               if (review := modifier_review(R, member, members)) is not None}
    held: dict[str, tuple[HeldFact, ...]] = {}
    for member in members:
        items: list[HeldFact] = []
        if member.key in bases:
            items.append(base_hold(bases[member.key], R))
        elif member.key in within:
            items.append(base_within_hold(within[member.key], R))
        if member.key in competes:
            items.append(competing_hold(shared.get(member.key, ()), R))
        items += same_day_holds(member, R, day)
        held[member.key] = tuple(items)
    return Combination(claims=claimed, bases=bases, within=within, competes=competes, contested=shared, day=day,
                       statements=statements, reviews=reviews, held=held)
