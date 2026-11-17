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
- LIFT_INJECTION (4.7's lift row; refute-4b-r2 F6, DECISIONS D229): an injection (or a tattoo, by its part_of only:
  ONE_ACT, v1's arm) whose part_of names an EMR or ESD with part_relation lift_for or step_of; or an injection whose
  purpose is lift_for_resection, of the same lesion as one - never a hemostatic injection (its purpose supported
  hemostasis: v1's catalogue kind bleeding_control), which a stated adjunct relation bundles as PROCEDURAL_ADJUNCT.
- RESECTION_TECHNIQUE: a snare or hot-forceps removal whose part_of names an EMR or ESD, or of the same lesion as one.
- STENT_INCLUDED (D45): a sphincterotomy or a dilation of an ERCP session beside a stent placement or exchange of the
  same duct - both ducts established; established apart (biliary or cystic against pancreatic) sets them apart, and
  anything else is asked, never READY alone.
- PROCEDURAL_ADJUNCT (D30, D79): a bleeding control, ablation, clip or injection whose part_of names an act (never the
  examination: the session, C-1), or whose cause is act_of_this_session and whose cause_event names an event of the
  session (the examination included: control of bleeding the procedure itself caused). The whole may be performed or
  begun. D41's lexical identity and D58/D77's place adjacency are gone (4.7, 4.13): causality is part_of and cause.
  v1's same-lesion arm (D30: "by its verified part_of or the removal's lesion") asks only where the two acts may name
  the same lesion (DECISIONS D221, refute-4b-r2 F1): an ablation or a bleeding control (v1's adjunct kinds, by
  catalogue kind) with a lesion stated, beside a removal performed or begun with a lesion stated, whose lesion may be
  that removal's (one id; a lesion the other may name; an id naming no lesion of the FactSet, 4.11; a same_as - one
  member or a chain of them through other entries - that may join them; a lesion fact that is not supported, an
  unknown identity: DECISIONS D248 G2, option (b)) is possibly its adjunct - U, asked (the identity's question first:
  an unestablished same_as, one question naming both, or a claim that the two are not one finding; then each lesion
  fact not supported; then act_part), never T - unless its own established part_of or cause says otherwise. Only two
  different SUPPORTED lesion ids no same_as can join are different findings (P5): the arm is F, and the ablation's or
  the bleeding control's code proceeds on its own rows.
- BIOPSY_OF_REMOVED_LESION (C-2): a biopsy of the same lesion as a removal (snare, EMR, hot biopsy, ESD, or the removal
  umbrella, each of whose methods is one), where that lesion is single or the two anchors share a unit; an established
  group in separate units un-bundles it (DECISIONS D196: lesion.multiplicity is read on the READY path). DECISIONS D292
  E1j (HOLDS-ANALYSIS's final fix 1; FINAL-V2 4.7's bundling identity over supported places, 4.11, 5.1 row 10): it is
  F for a biopsy done, at least in part, where no removal was (``_biopsy_elsewhere``) - whenever the biopsy's
  target.lesion is a pure empty slot and its place list is established, and one supported place of it, for EVERY
  removal the rule could pair it with, is disjoint from each of that removal's places (its target.places together with
  the established places of the removed FINDING - every lesion entry a same_as member, in ANY state, may join to its
  target lesion, directly or through other entries: DECISIONS D294 G1, read by facts.finding_places, which SITE and
  D240's site fit read too: D297 ENGB-1), that removal was asked about it by a rejected pair control, and no place pair
  control asked of the biopsy or of those removals is unrejected. A removal whose lesion claim is neither a supported
  lesion whose finding's every entry has established places nor a pure empty slot, a finding holding an id the FactSet
  does not hold, a removal whose places are not established landmarks, and a synthetic removal (no place) leave the
  rule as it was. same_as is read there in the hold direction only (it can only widen the finding, and a wider finding
  can only keep the rule as it was), so it stays a hold-only read of BUNDLING.
- DRAINAGE_STEP (G3, D171, D177): a fine-needle aspiration whose part_of names a drainage, or of the same lesion as one;
  the drainage may be performed or begun.

**What a fact leaves open.** An enumeration fact holds its value when supported; when negated it leaves every other value
open (pairing's reading); when not established, ``facts.possibly``'s values (its claimed value, its options, a doubt's
readings, an unrejected control's value; every value for an empty slot). A status that is not established leaves every
status open (4.2's status arm); a status established negated says the act was not done. same_as is read as the
equivalence it states (P5: one id per distinct finding; a same_as says two entries are one finding): a chain of members
through other entries joins two lesions as one member does (repair r4b, refute-r4b-r1 R1). The SAME LESION (the lift's
purpose arm, the resection technique, the biopsy of a removed lesion, the drainage step) is T when both lesions are
supported and equal or joined by supported same_as members, and no claim between the two entries says they are not one
finding (a negated same_as member in any state, a contradicted one, a distinct_from: DECISIONS D248 G3 - the FactSet
contradicting itself on their identity is asked, never explained, and never released: beside such a claim it is U,
never F by the places or otherwise - repair r4b-2, refute-r4b-r1 F1); F only when facts.apart_by_lesion (distinct_from
and the lesion pair controls, never while a same_as may join them) or facts.apart_by_place (established disjoint places
and their pair controls) sets the two acts apart - the place arm never while the two acts' lesion claims may name one
finding (a common id, by possibly, or a same_as that may join them: DECISIONS D239's reading for bundling, built
fail-closed - refute-r4b-r1 F3, the step's NOTES question QF3 - so weakening the identity of a bundled part, an act's
lesion fact or a same_as member, asks it and never releases it); U otherwise - an unknown identity never sets two acts
apart and never makes one (4.11, the 2026-11-09 checklist). The procedural adjunct's lesion arm reads D221's identity
instead (above). The same_as graph and
what is read off it - each walk, each join, each supported component - are computed once per Reader (D248 G5). A part_of
or a cause the document does not state (an EMPTY slot that no doubt names) relates nothing: P16 and P15 ask pass 1 for
them only where the document states them, and 3.2.3 leaves part_of, part_relation and cause_event UNCONTROLLED because
"a yes-bias can only hold"; a part_of or cause_event that is claimed, doubted or contradicted relates the acts it may
name (U). Any part_relation counts for the procedural adjunct, the resection technique and the drainage step: an act
part_of the whole is not a separate service whatever the relation (the step's NOTES record this reading, question
Q2); the lift reads its relation (lift_for or step_of: 4.7, F6).

**The synthetic act as a possible whole** (DECISIONS D216, D231's coverage half: C1). A whole is every other event and
every synthetic act - 3.2.6 rule 3's synthetic act as D231 reads it: a kept unlisted ACT or DOUBT, with its session card,
or with no card where every session is possible (combination.synthetic, the set the four engine modules read). Each is
read as its filed doubted form (Reader._synthetic_wholes): its kind as the entry names it (an empty slot when it names
none), its status a doubt, its session its card, every other slot empty - so an unlisted act, an unlisted doubt and the
same act filed in doubt give one outcome. A bundling into it is never T (its status is a doubt); its U rests on the
synthetic act's own doubt (performed_status at rank 2, cause unlisted, quoting its units), with the part's own doubts.

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
code-level ``bundling`` nor the listing ever explains it away as part of another act: it is never read under another
service (DECISIONS D227 F3), and reconcile lists it in doubt with its conflict question - also where D137's class
records it reportable (eus_unlisted) - unless a counted code reads it and asks it. The same principle on the whole's
side ("contradictions ... are never resolved by bundling", S4): a whole a statement contradicts may not have been done,
so a bundling into it is U, the whole's conflict its first witness (the step's NOTES, question Q7).

**bundling(code, supporting, R)** (4.4's decide: ``held_facts += bundling(code, supporting, R)``): () when one of the
supporting acts is its own (v1: a code with an own act proceeds on it); otherwise every supporting act's witnesses -
each one's questions or explanations, every candidate's (HO-8), a question (it may release the code) ranking before an
explanation. Every catalogue code has at most one requirement group (catalogue.requirements; tested), so this is per
group.

**Sessions** (4.7: "from the sessions table"; S3 6.2): one Session per session of the FactSet, in pass 1's order. Its
members are the events whose session fact claims it (any state but negated: v1's family, the one session reconcile
lists an act under); its POSSIBLE members (``possible_members``) every event that may be in it (``sessions_of``: its
claimed session, an empty slot, a doubt's readings, a contradiction's sides, a negation of another session, a negation
left open, or an id naming no session of the FactSet - 4.2: a doubt is never an absence). "A session is done" has ONE
derivation (DECISIONS D227; refute-4b-r2 F2): step 4d's combination.session_done, the reference, and 4.3 row 7's "its
examination, when it has one, passes 2-5 (an act-only session: the act itself)", a digital examination (a device
claiming manual: FINAL 5.6 E13, D69; DECISIONS D253 QE13 (a), 4d's _digital) excepted throughout. Its examinations
(``done_examinations``) are its ESTABLISHED
examinations - kind supported examination, session supported, no digital examination - that are done (4.3 rows 2-5
supported: reading.done); its POSSIBLE examinations (``possible_examinations``; D62, D87) the events, not done, that may
be its examination (4d's _may_be_examination_of: kind possibly the examination, session possibly this one by 4d's
membership, possibly positive on the date by the documenting team, no digital examination) - and none at all in a
session whose examination is established, and established not done on the date of service (4d's not_done_today:
planned, or done on another date, and no event the document places in it that may be its examination done today),
whatever an act's date or session slot (DECISIONS D269, Q-P2DATE option (c), 4.3 row 7: an act possibly in such a
session never makes it possibly done - 4d's session_possibly_done; D256 P2's letter excepted only an act whose session
slot is silent and whose date is not established, so a dated act still made a planned EUS possibly done); its synthetic
examinations left open (``possible_unlisted_examinations``; DECISIONS D231 row 1, coverage's C2) the kept unlisted acts
and doubts of kind examination or none that may be in it (4d's combination.synthetic_examinations), read only when it
has no established examination (D232: beside one, a synthetic examination adds nothing); ``done`` is one of its
established examinations done, or, with none, one of its acts (session supported, no digital examination) done and no
possible examination left open, filed or synthetic (tests/v2/test_coverage.py's OneSessionDone asserts all of them
equal 4d's on generated FactSets, kept unlisted entries among them). ``event`` is its one examination (exactly one done,
no possible one); ``unresolved`` two or more done or possible, filed or synthetic; ``incomplete`` every done examination
established attempted_not_completed - so an aborted colonoscopy beside a digital examination is incomplete. A session
whose established examination is not done is not done, whatever its acts: 4.3 row 7 holds every code of it (step 4a),
and reconcile still reads its member acts as a done session's (no no_proposal of its own) when counted codes read the
session - which the unestablished count skips - so a done act no counted code reads is listed whatever step 4a reads of
the session (refute-r4b-r1 R5; the step's NOTES, QR5-1: step 4a reads an examination whose session is established as
another as no examination of that session, step 4d's reference as possibly any session's). ``part_of`` (C3) is the
session its part_of_session names when supported (of another kind, or a kind not established), else (C-4, structural
over supported session kinds and tracts: 4.7's base_within row) the done EUS session whose tract is supported upper,
for a done EGD session with one done examination (v1's ``own``); ``possibly_part_of`` (D70) the session it may be
part of otherwise - a part_of_session not established, naming exactly its claimed value and its options (a
contradiction's sides, a doubt's readings, an empty slot's doubt included: DECISIONS D286, the one set step 4d's wholes
reads; never a session nothing names), or a session that may be an EUS (its kind supported EUS, or not
established with EUS among what it leaves open: 4.7's "possibly_part_of by possibly") and may be upper (its tract not
established, or pancreatobiliary) and may be done: 4d's combination.session_possibly_done, the reference (D227's one
derivation; D231 row 2, coverage's C3: a synthetic act that may be in it makes it possibly done; an entry with no card
that names a kind makes possibly done only a session one of whose possible families holds that kind, DECISIONS D256
P2's K2). DECISIONS D269 (Q-P2DATE option (c); the integration's I4 residual): a session whose examination is
established, and established not done on the date of service (4d's not_done_today), is possibly done by NO act - filed
or kept unlisted, placed, supported, carded or with no card, whatever its date or session slot - and is never a whole:
C3's supported part_of_session and D70's part_of_session not established name no such session (4d's wholes), and the
structural arms read it neither done nor possibly done, so a planned or an earlier EUS is never the whole, established
or possible, of today's EGD. coding_family's region moves (D114, D141, D148, D153), eus_places and every C-4 word arm
are gone (5.4): an act's session is its own fact.

**Reportable and doubted** (v1's shapes). Reportable: done (rows 2-5 supported), status supported performed, kind
supported and its catalogue kind one of its session's family's reportable kinds (the catalogue acts but the examination,
the umbrellas and NOT_REPORTED, v1's NOT_ACT_KINDS; D116's stent removal and exchange where the family lists the stent),
session and its kind supported, and not bundled (verdict not F); event_coding drops the E/M kinds from its lists (the
session's own service is never an act beside itself), as v1 did. Doubted (4.7 [R:HO-1]): an act that may be of a
reportable kind of a family it may be in - for an act whose own session fact is not established, every family unless
the sessions it may be in admit its kind (DECISIONS D227 F8; FAMILY_KINDS, K2's table; ``_families`` reads "admit" so
that no weakening narrows it) - (D117's positive removal umbrella and D115's possible bleeding control - from purpose,
never words - included), possibly performed or begun, neither its date relation nor its
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
doubt, its session or its session's kind not established included; a session not done counts as unestablished by its
possible members (an examination whose session fact is in doubt is possibly its own) and by the synthetic acts that may
be in it (D216) - or, when counted codes read it, its member acts are read as a done session's (refute-r4b-r1 R5).
"Read by a counted code" is read PER SESSION for both (DECISIONS D248 G1): for every family the session is stated as,
a counted code of that family one of whose events may be in it - v1's "a code of its family" meant this session's code
because v1 had one session per family, and a second session of a coded family must stay incomplete. An act of a kind
its family has no profile for (``unsupported_kinds``: UNSUPPORTED_ACTS and the family's UNSUPPORTED_KINDS, hand-off
1e:R3) is listed unsupported. READ_UNDER (DECISIONS D227 F4; P3) reads no list's completeness: an act is read under
another service only when its place list is established complete within the rule's regions (every landmark outside them
its places do not cover excluded by a rejected pair control or a negated member); otherwise it is listed in doubt
(READ_UNDER_NOT_ESTABLISHED), asking a coverage question (InDoubt.witness: act_target, cause coding_rule:read_under)
that holds no code; each read-under listing is an item of its own Detail (refute-r4b-r1 R3, D225), and beside a
session whose kind is not established an act two readings list differently is listed once, in doubt when a reading
lists it so (D248 G4). One service
question per (session, fact) for an act in doubt no counted code reads, the act chosen
by 4.8's binding (one a code's question names last, D149; then the fewest witnesses; then document order) and none a
code's item already asks (D89); and D125's extent question per done session whose extent no code asks.

**The text-free boundary** (P1; FINAL-V2 4.1, 5.7 measure 4): this module imports the standard library, the package's
labels, contract/types.py and engine's anatomy, catalogue, combination (step 4d's reference for "session done",
"possibly done" and "established not done today", D227 and D269, and its synthetic act, D231), facts, pairing,
reading, requirements and types only - no retired v1 module (5.0), none of contract's text modules, not wording - holds
no word, phrase or marker list (every module-level collection holds enumeration members), and reads no text. Its only
sentences are completeness's fixed ones (v1's); every other record carries CPT Studio's codes, ids and integer spans.
``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, unique
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation import ENGINE_VERSION_V3
from studio.interpretation.contract.types import (Attribute, Cause, DateRelation, Duct, FactState, Kind,
                                                  Landmark, Multiplicity, Owner, PartRelation, Performer, Purpose,
                                                  Qualifier2, Reason, Result, SessionKind, Status, Tract, UnlistedWhat,
                                                  VerdictValue)
from studio.interpretation.engine import anatomy, catalogue, combination, pairing, reading
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.types import (Anchor, Fact, FactSet, HeldFact, Id, IdFamily, ItemKind, Span,
                                                UnlistedStatement)

_T = TypeVar('_T', bound=Enum)
_A = Attribute

# The completeness record's second-review bound (v1's coverage.SECOND_REVIEW_CHECKED = engine.SECOND_REVIEW_CHECKED).
SECOND_REVIEW_CHECKED = 64
# event_coding's version: the read-time overlay (step 5c) reads @2 only (FINAL-V2 6.5).
CODING_VERSION = ENGINE_VERSION_V3


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
# 4.7's lift row (DECISIONS D229, refute-4b-r2 F6): the part_relations that make a part_of a lift - lift_for or step_of.
_LIFT_RELATIONS: frozenset[PartRelation] = frozenset({PartRelation.LIFT_FOR, PartRelation.STEP_OF})
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
    """The kind an item about ``event`` names (conflict:<kind>): its one label, facts.established_kind - the catalogue
    kind of its supported kind with its supported purpose, else Kind.OTHER (DECISIONS D287, D267's heading, D254 rule
    2: an act whose kind CPT Studio's reading does not establish is "another act" in every fact key, as evaluate's and
    questions.act_kind's; a clip supported for hemostasis is the bleeding control)."""
    return facts_.established_kind(R, event)


class _Asker:
    """Who a conjunct's doubts are about and how they are asked: the FactSet, the part and its kind, and the Reader
    whose pairs a whole's contradictions are read from (None outside one: no whole is judged then)."""

    __slots__ = ('R', 'part', 'kind', 'reader', '_same', '_elsewhere')

    def __init__(self, R: FactSet, part: Id, reader: Reader | None = None) -> None:
        self.R = R
        self.part = part
        self.kind = _kind_of(R, part)
        self.reader = reader
        self._same: _SameAs | None = None
        self._elsewhere: bool | None = None

    def biopsy_elsewhere(self) -> bool:
        """``_biopsy_elsewhere`` for this part over this asker's FactSet, computed once (it reads no whole of its own:
        the rule asks it per whole, DECISIONS D248 G5's cost)."""
        if self._elsewhere is None:
            self._elsewhere = _biopsy_elsewhere(self)
        return self._elsewhere

    def doubt(self, subject: Id, attribute: Attribute, found: Fact, key: rq.FactKey) -> Judged:
        kind = self.kind if subject == self.part or subject.family is not IdFamily.EVENT else _kind_of(self.R, subject)
        return Judged(Truth.U, (Doubt(subject, attribute, found, key, kind),))

    def same_as(self) -> _SameAs:
        """The FactSet's same_as graph and what is read off it (_SameAs), built once per Reader (once per asker outside
        one): every walk, join and component computed once (DECISIONS D248 G5)."""
        if self.reader is not None:
            return self.reader._same_as()
        if self._same is None:
            self._same = _SameAs(self.R)
        return self._same


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
    them, method not stated): supported, its value; negated, every other kind; not established, facts.possibly's -
    every kind for a denial left open (a kind claim pass 1 wrote negated, not established: DECISIONS D294 RD-3, so a
    weakened denial of a kind never narrows what the act may be to the denied kind)."""
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
    non-match (4.11), and a doubt is never an absence (4.2). So does a fact that is not established and whose claim is
    a negation ("not in X1" left unresolved, doubted or contradicted: facts.possibly would read its claimed value alone,
    so weakening an established negation would narrow every other session to X1, against 9.4 P-MONO), or that names no
    session at all - step 4d's possible_sessions reads both so (repair r4b; DECISIONS D227's one membership) - and an
    overfilled session slot's merged view (AMENDMENT-2 4.3.3 a: never narrower than a written denial read alone; every
    view, since it cannot tell whether a written fact denied a session: facts.open_denial, the step's NOTES question
    Q1R)."""
    found = facts_.fact(R, event, _A.SESSION)
    every = frozenset(R.sessions)
    if found.result is Result.NEGATED:
        return frozenset(session for session in every if session != found.value)
    if found.result is Result.SUPPORTED:
        return frozenset({found.value}) if isinstance(found.value, Id) and found.value in every else every
    named = tuple(value for value in (found.value, *found.options) if isinstance(value, Id))
    if facts_.silent(found) or facts_.open_denial(found) or not named or any(value not in every for value in named):
        return every
    return frozenset(named)


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
    ``statuses``, on the date of service, in the part's session. A whole of none of ``kinds`` is F before anything else
    is read (the same result: Kleene's conjunction is F on any F conjunct; DECISIONS D248 G5's cost)."""
    kind = _TRUE if kinds is None else _kind_in(ask, whole, kinds, rq.FactKey.ACT_PART)
    if kind.truth is Truth.F:
        return _FALSE
    return _both(kind, _status_in(ask, whole, statuses, rq.FactKey.ACT_PART),
                 _enum_in(ask, whole, _A.DATE_RELATION, _TODAY, DateRelation, rq.FactKey.ACT_PART),
                 _same_session(ask, part, whole), _unchallenged(ask, whole))


def _unchallenged(ask: _Asker, whole: Id) -> Judged:
    """D3's principle on the whole's side (S4: "contradictions ... are never resolved by bundling"): a whole a
    statement contradicts (pairing's CONTRADICTION) may not have been done, so a bundling into it is asked - its
    conflict first (rank 1) - and never explained away. T when no statement contradicts it, and for a synthetic act's
    filed doubted form (Reader._synthetic_wholes: no statement pairs with an unlisted act; its own doubt is asked)."""
    if ask.reader is None or whole not in ask.reader.R.events:
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


# One same_as member, where it is read: (the lesion whose same_as list holds it, the member).
_Link = tuple[Id, Fact]
# A claim that two lesion entries are NOT one finding, where it is read (DECISIONS D248 G3): (the lesion whose list holds
# it, same_as or distinct_from, the member).
_Claim = tuple[Id, Attribute, Fact]
# What a walk reaches: each id with the fewest members not supported on a chain to it, and that chain's members.
_Reach = dict[Id, tuple[int, tuple[_Link, ...]]]
# A join's answer (_SameAs.join): None when nothing may join the two sides; else (supported members alone join them, the
# members to ask).
_Joined = tuple[bool, tuple[_Link, ...]] | None


def _member_ids(R: FactSet, member: Fact) -> tuple[Id, ...]:
    """The lesion ids a same_as member may name (facts.possibly): supported, its value; negated ("L1 is not the same as
    L2"), none; not established, its claimed value and its options - every lesion of the FactSet for a silent one."""
    if member.result is Result.NEGATED:
        return ()
    if member.result is Result.SUPPORTED:
        return (member.value,) if isinstance(member.value, Id) else ()
    if facts_.silent(member):
        return tuple(R.lesions)
    return tuple(dict.fromkeys(value for value in (member.value, *member.options) if isinstance(value, Id)))


def _same_as_graph(R: FactSet) -> dict[Id, list[tuple[Id, _Link]]]:
    """same_as as the equivalence it states (P5: one id per distinct finding, and a same_as says two entries are one
    finding), as an undirected graph: each lesion of the FactSet linked, by each member of its same_as list, to every id
    that member may name (_member_ids) - an id the FactSet does not hold included. Built in the FactSet's order, so a
    walk over it is deterministic. (The removed finding E1j reads is facts.finding's: every id a member names in ANY
    state - DECISIONS D294 G1, D297 ENGB-1.) DECISIONS D302 RF2C-L2: a member whose value is empty or unreadable
    (facts.unnamed_member) names an id of its own the FactSet does not hold (facts.free_lesion_number), so it opens its
    holder's component as an unknown id does - the join asks that member, as it asks the member naming an unknown id -
    and facts.possibly_one_finding reads the same."""
    graph: dict[Id, list[tuple[Id, _Link]]] = {}
    fresh = facts_.free_lesion_number(R)
    for holder in R.lesions:
        for member in facts_.members(R, holder, _A.SAME_AS):
            named = list(_member_ids(R, member))
            if facts_.unnamed_member(member):  # D302 RF2C-L2: any one lesion, an id the FactSet does not hold
                named.append(Id(IdFamily.LESION, fresh))
                fresh += 1
            for other in named:
                if other != holder:
                    graph.setdefault(holder, []).append((other, (holder, member)))
                    graph.setdefault(other, []).append((holder, (holder, member)))
    return graph


def _walk(graph: Mapping[Id, Sequence[tuple[Id, _Link]]], start: Iterable[Id]) -> _Reach:
    """Every id ``graph`` reaches from ``start``, each with the fewest members not supported on a chain to it and that
    chain's members, in order from ``start`` (a 0-1 breadth-first walk: a supported member costs nothing, so it is
    queued at the front; one not supported costs one, queued at the back)."""
    best: _Reach = {}
    queue: deque[tuple[int, Id, tuple[_Link, ...]]] = deque(
        (0, node, ()) for node in sorted(frozenset(start), key=_id_order))
    while queue:
        cost, node, chain = queue.popleft()
        if node in best:
            continue
        best[node] = (cost, chain)
        for other, link in graph.get(node, ()):
            if other in best:
                continue
            if link[1].result is Result.SUPPORTED:
                queue.appendleft((cost, other, chain + (link,)))
            else:
                queue.append((cost + 1, other, chain + (link,)))
    return best


def _asked(chain: Sequence[_Link]) -> tuple[_Link, ...]:
    """The members a chain to an id the FactSet does not hold leaves open: those not supported, else the last one (the
    member naming that id, whose identity is unknown)."""
    open_ = tuple(link for link in chain if link[1].result is not Result.SUPPORTED)
    return open_ or tuple(chain[-1:])


def _names(member: Fact) -> tuple[Id, ...]:
    """The ids a list member names in any state: its claimed value and its options (a contradiction's sides, a doubt's
    readings)."""
    return tuple(value for value in (member.value, *member.options) if isinstance(value, Id))


class _SameAs:
    """The FactSet's same_as graph (_same_as_graph) and what the bundling rules read off it, each computed once
    (DECISIONS D248 G5; refute-r4b-r2 G5: the walk ran once per (part, whole) pair, 388 s at FINAL-V2 1.8's bounds): a
    walk per start set, a join per (left, right) pair, the ids supported members join to a lesion (its supported
    component), and _join's third reaches (the components holding two ids the FactSet does not hold); and, for E1j, the
    places of the removed finding of a lesion (``finding_places``: facts.finding_places, DECISIONS D294 G1 and D297
    ENGB-1 - the one reading every rule that reads an act's target lesion's places shares, computed once per
    FactSet). Read-only over a frozen FactSet: one per Reader (per asker outside one), never shared across FactSets."""

    __slots__ = ('R', 'lesions', 'graph', '_walks', '_joins', '_components', '_third')

    def __init__(self, R: FactSet, graph: Mapping[Id, Sequence[tuple[Id, _Link]]] | None = None) -> None:
        self.R = R
        self.lesions: frozenset[Id] = frozenset(R.lesions)
        self.graph: Mapping[Id, Sequence[tuple[Id, _Link]]] = graph if graph is not None else _same_as_graph(R)
        self._walks: dict[frozenset[Id], _Reach] = {}
        self._joins: dict[tuple[frozenset[Id], frozenset[Id]], _Joined] = {}
        self._components: dict[Id, frozenset[Id]] = {}
        self._third: tuple[tuple[Id, tuple[_Link, ...]], ...] | None = None

    def finding_places(self, lesion: Id) -> facts_.FindingPlaces:
        """facts.finding_places for ``lesion`` (DECISIONS D294 G1, D297 ENGB-1)."""
        return facts_.finding_places(self.R, lesion)

    def finding(self, lesion: Id) -> frozenset[Id]:
        """The removed FINDING E1j reads for a removal whose target lesion is ``lesion`` (facts.finding: every id a
        same_as member in ANY state names - facts.any_state_ids: a negation, a member left open and a silent one
        included - joined to it, directly or through other entries and in either direction, ``lesion`` included; an id
        the FactSet does not hold among them leaves E1j as it was). Every state of a member names at least its value,
        so the set never narrows with a member's state: same_as is read in the hold direction only."""
        return frozenset(self.finding_places(lesion).entries)

    def walk(self, start: frozenset[Id]) -> _Reach:
        """_walk from ``start``, once per start set."""
        found = self._walks.get(start)
        if found is None:
            found = self._walks[start] = _walk(self.graph, start)
        return found

    def join(self, left: Iterable[Id], right: Iterable[Id]) -> _Joined:
        """Whether same_as - one member, or a chain of members through other entries (refute-r4b-r1 R1: a same_as states
        that two entries are one finding, an equivalence) - may join a lesion id of ``left`` to one of ``right``: None
        when nothing may; else (by supported members alone, the members to ask) - True when supported members alone join
        them (one finding), and the members not supported on the cheapest joining chain (the fewest members not
        supported: _walk). An id the FactSet does not hold that a member names may be any ONE lesion (4.11: a missing
        identifier manufactures neither a match nor a non-match): in the left's reach or the right's it may be the other
        side's lesion, and a third reach holding two such ids may be both sides' - then the member naming one (or the
        first member not supported before it) is asked (refute-r4b-r1 R2). An id of ``left`` or ``right`` itself naming
        no lesion of the FactSet is the caller's to read (D221's identity: unknown). Once per (left, right) pair."""
        key = (frozenset(left), frozenset(right))
        if key not in self._joins:
            self._joins[key] = self._join(*key)
        return self._joins[key]

    def _join(self, starts: frozenset[Id], ends: frozenset[Id]) -> _Joined:
        found = self.walk(starts)
        reached = sorted((node for node in ends if node in found), key=lambda node: (found[node][0], _id_order(node)))
        if reached:
            chain = found[reached[0]][1]
            open_ = tuple(link for link in chain if link[1].result is not Result.SUPPORTED)
            return not open_, open_
        back = self.walk(ends)
        for reach, origin in ((found, starts), (back, ends)):
            missing = sorted((node for node in reach if node not in self.lesions and node not in origin),
                             key=lambda node: (reach[node][0], _id_order(node)))
            if missing:
                return False, _asked(reach[missing[0]][1])
        for first_missing, asked in self.third():
            if first_missing not in found and first_missing not in back:
                return False, asked
        return None

    def third(self) -> tuple[tuple[Id, tuple[_Link, ...]], ...]:
        """_join's third reaches, once per FactSet: each component of the graph (walked from its first id the FactSet
        does not hold, in id order) that holds a second such id, as (that first id, the members a walk from it asks
        to reach its next such id in id order) - in the order of those first ids. A join returns the first one no
        walk from its two sides reached (those components are read by its own reaches)."""
        if self._third is None:
            out: list[tuple[Id, tuple[_Link, ...]]] = []
            seen: set[Id] = set()
            for node in sorted(self.graph, key=_id_order):
                if node in seen or node in self.lesions:
                    continue
                reach = self.walk(frozenset({node}))
                seen |= set(reach)
                missing = sorted((other for other in reach if other not in self.lesions and other != node),
                                 key=_id_order)
                if missing:
                    out.append((node, _asked(reach[missing[0]][1])))
            self._third = tuple(out)
        return self._third

    def component(self, lesion: Id) -> frozenset[Id]:
        """The ids supported same_as members join to ``lesion``, directly or through other entries, itself included
        (its supported component), once per component."""
        found = self._components.get(lesion)
        if found is None:
            seen = {lesion}
            queue = [lesion]
            while queue:
                node = queue.pop()
                for other, link in self.graph.get(node, ()):
                    if link[1].result is Result.SUPPORTED and other not in seen:
                        seen.add(other)
                        queue.append(other)
            found = frozenset(seen)
            for node in found:
                self._components[node] = found
        return found

    def one_finding(self, one: Id, other: Id) -> bool:
        """Two lesion ids one finding (P5): the same id, or joined by supported same_as members alone, directly or
        through other entries - the same answer as a join's first value (a chain of no member not supported)."""
        return one == other or other in self.component(one)

    def denials(self, one: Id, other: Id) -> tuple[_Claim, ...]:
        """DECISIONS D248 G3 (refute-r4b-r2 G3): the claims that two different lesion entries are NOT one finding,
        between them: in either one's list, a same_as member that is a negation in any state ("L2 is not the same as
        L3" - established, or left open: its claim is still a negation) or a contradicted one with the other among its
        sides, and a distinct_from member that is no negation, naming the other. Read beside supported members that join
        the two, they are the FactSet contradicting itself on the two lesions' identity, which is asked and never
        explained (S4: contradictions are never resolved by bundling; 4.8 rank 1) - and never released either: the
        readers give U on them, never F by the places or otherwise (repair r4b-2, refute-r4b-r1 F1). A contradicted
        member is a claim whatever its other sides name - one whose sides all name the other's finding too is asked,
        its conflict at rank 1, never explained (the step's NOTES, question QF1). Read only between the two acts' own
        lesions, so a weakening never removes one (an established claim weakened keeps its claim), and a supported
        member weakened only breaks the join (the step's NOTES, question QG3)."""
        if one == other:
            return ()
        out: list[_Claim] = []
        for holder, named in ((one, other), (other, one)):
            for member in facts_.members(self.R, holder, _A.SAME_AS):
                if (member.state is FactState.NEGATED or member.result is Result.CONTRADICTED) and \
                        named in _names(member):
                    out.append((holder, _A.SAME_AS, member))
            for member in facts_.members(self.R, holder, _A.DISTINCT_FROM):
                if member.state is not FactState.NEGATED and member.result is not Result.NEGATED and \
                        named in _names(member):
                    out.append((holder, _A.DISTINCT_FROM, member))
        return tuple(out)


def _join(R: FactSet, left: Iterable[Id], right: Iterable[Id],
          graph: Mapping[Id, Sequence[tuple[Id, _Link]]]) -> _Joined:
    """_SameAs.join over ``graph`` (the FactSet's _same_as_graph), with nothing memoized across calls: the Reader's
    _SameAs is the reading the rules use."""
    return _SameAs(R, graph).join(left, right)


def _one_finding(R: FactSet, one: Id, other: Id, graph: Mapping[Id, Sequence[tuple[Id, _Link]]]) -> bool:
    """_SameAs.one_finding over ``graph``: the same id, or joined by supported same_as members alone, directly or
    through other entries."""
    return _SameAs(R, graph).one_finding(one, other)


def _claimed_lesions(found: Fact) -> frozenset[Id]:
    """The lesion ids a target.lesion CLAIM names, read by facts.possibly (4.2; DECISIONS D239's "a lesion claim not
    established whose value or options name the act's lesion"): supported, its value; not established, its claimed value
    and its options - a doubt's readings, a contradiction's sides, the value of a negation left open (possibly that
    lesion after all); an established negation, and an empty slot no doubt names (P13: a lesion the document does not
    state), name none."""
    if found.result is Result.NEGATED:
        return frozenset()
    if found.result is Result.SUPPORTED:
        return frozenset({found.value}) if isinstance(found.value, Id) else frozenset()
    return frozenset(value for value in (found.value, *found.options) if isinstance(value, Id))


def _may_be_one_finding(R: FactSet, part: Id, whole: Id, same: _SameAs) -> bool:
    """Whether the two acts' lesion claims may name one finding (DECISIONS D239's reading, here for bundling: refute-
    r4b-r1 F3, built fail-closed - the step's NOTES, question QF3): both acts state a lesion (_claimed_lesions) and some
    id one may name is one the other may name, or a same_as - one member or a chain of them, supported or not
    (_SameAs.join, a member naming an id the FactSet does not hold included, 4.11) - may join them. Every 9.4 weakening
    keeps a claimed value and a same_as member's edge (an established negation weakened even adds its value), so it
    only widens this: a weakening never turns it False."""
    left = _claimed_lesions(facts_.fact(R, part, _A.TARGET_LESION))
    right = _claimed_lesions(facts_.fact(R, whole, _A.TARGET_LESION))
    return bool(left) and bool(right) and (bool(left & right) or same.join(left, right) is not None)


def _apart(R: FactSet, part: Id, whole: Id, same: _SameAs) -> bool:
    """The two acts' targets established apart (4.2 [R:SC-B]): by lesion (facts.apart_by_lesion: distinct_from - or, by
    DECISIONS D296 and D300 RF-L2, an established lesion pair claim, read as a written distinct_from by
    facts.established_distinct - and the lesion pair controls, never while a same_as - directly or through other
    entries, _SameAs.join - may join the two lesions) or by place (facts.apart_by_place: disjoint established places and their pair controls), never while the
    two acts' lesion claims may name one finding (_may_be_one_finding: DECISIONS D239's reading, which rules pairing's
    analogue - a supported equal lesion, or a lesion possibly equal, is never set apart by place). Read in that order
    and the guard last, only where the places set the acts apart (D248 G5's cost)."""
    one = _supported_id(facts_.fact(R, part, _A.TARGET_LESION))
    other = _supported_id(facts_.fact(R, whole, _A.TARGET_LESION))
    by_lesion = (one is not None and other is not None and facts_.apart_by_lesion(R, part, whole)
                 and same.join((one,), (other,)) is None)
    return by_lesion or (facts_.apart_by_place(R, part, whole) and not _may_be_one_finding(R, part, whole, same))


def _same_lesion(ask: _Asker, part: Id, whole: Id) -> Judged:
    """One lesion (module docstring): T when both are supported and one finding (_SameAs.one_finding: equal, or joined
    by supported same_as members, directly or through other entries) and nothing claims the two entries are not one
    finding (_SameAs.denials, DECISIONS D248 G3); with such a claim, U resting on the claims - never F: one finding by
    supported members is never set apart, by place or by lesion, while the FactSet contradicts itself on it (repair
    r4b-2, refute-r4b-r1 F1: the claim's U fell through to the place exit and released the part, where the same FactSet
    without the claim was bundled). F when the two acts' targets are established apart (_apart: never by place while
    their lesion claims may name one finding); U otherwise, resting on the lesion facts not established (on the part's,
    when both are supported and nothing joins or sets them apart)."""
    one, other = facts_.fact(ask.R, part, _A.TARGET_LESION), facts_.fact(ask.R, whole, _A.TARGET_LESION)
    first, second = _supported_id(one), _supported_id(other)
    same = ask.same_as()
    if first is not None and second is not None and same.one_finding(first, second):
        denials = same.denials(first, second)
        if not denials:
            return _decided(_A.TARGET_LESION)
        return _both(*(ask.doubt(holder, attribute, member, rq.FactKey.ACT_TARGET)
                       for holder, attribute, member in denials))
    if _apart(ask.R, part, whole, same):
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
    """LIFT_INJECTION (4.7's lift row, refute-4b-r2 F6): an injection or a tattoo whose part_of names an EMR or ESD
    with part_relation lift_for or step_of; or an injection whose purpose is lift_for_resection, of the same lesion as
    one - never a hemostatic injection (its purpose supported hemostasis: catalogue kind bleeding_control, which v1's
    lift arm never read as an injection; a stated adjunct of the resection is PROCEDURAL_ADJUNCT's). The relation
    comes first, so a T names its deciding fact. A conjunct is read only where no conjunct beside it is F (the same
    result: Kleene's conjunction is F on any F conjunct; DECISIONS D248 G5's cost) - the whole first."""
    whole_ = _whole(ask, ask.part, whole, _RESECTIONS, _PERFORMED)
    if whole_.truth is Truth.F:
        return _FALSE
    by_part = _both(_part_of(ask, ask.part, whole),
                    _enum_in(ask, ask.part, _A.PART_RELATION, _LIFT_RELATIONS, PartRelation, rq.FactKey.ACT_PART),
                    _kind_in(ask, ask.part, _LIFTS_BY_PART, rq.FactKey.ACT_PART), _not_hemostatic(ask.R, ask.part))
    kind = _kind_in(ask, ask.part, _LIFTS, rq.FactKey.ACT_PART)
    purpose = _enum_in(ask, ask.part, _A.PURPOSE, frozenset({Purpose.LIFT_FOR_RESECTION}), Purpose,
                       rq.FactKey.ACT_PART)
    by_purpose = _FALSE if Truth.F in (kind.truth, purpose.truth) else _both(_same_lesion(ask, ask.part, whole), kind,
                                                                             purpose)
    return _both(_either(by_part, by_purpose), whole_)


def _not_hemostatic(R: FactSet, part: Id) -> Judged:
    """4.7's lift row: never a hemostatic injection - F when the part's purpose is supported hemostasis (v1's
    catalogue_kind, which read the established purpose only: a clip or an injection whose purpose is open is read as
    itself there, D157's doubt being the bleeding control's own row); T otherwise."""
    return _FALSE if facts_.holds(facts_.fact(R, part, _A.PURPOSE), Purpose.HEMOSTASIS) else _TRUE


def _technique(ask: _Asker, whole: Id) -> Judged:
    """RESECTION_TECHNIQUE: a snare or hot-forceps removal whose part_of names an EMR or ESD, or of its lesion. The
    whole and the kind are read first, the identity only where neither is F (the same result; D248 G5's cost)."""
    whole_ = _whole(ask, ask.part, whole, _RESECTIONS, _PERFORMED)
    kind = _kind_in(ask, ask.part, _TECHNIQUES, rq.FactKey.ACT_PART) if whole_.truth is not Truth.F else _FALSE
    if Truth.F in (whole_.truth, kind.truth):
        return _FALSE
    return _both(_either_lazily(lambda: _part_of(ask, ask.part, whole), lambda: _same_lesion(ask, ask.part, whole)),
                 kind, whole_)


def _either_lazily(*judges: Callable[[], Judged]) -> Judged:
    """_either over disjuncts judged in order, stopping at the first T (the same result: _either returns the first T;
    D248 G5's cost)."""
    found: list[Judged] = []
    for judge in judges:
        judged = judge()
        if judged.truth is Truth.T:
            return judged
        found.append(judged)
    return _either(*found)


def _stent(ask: _Asker, whole: Id) -> Judged:
    """STENT_INCLUDED (D45): an ERCP sphincterotomy or dilation beside a stent placement or exchange of its duct."""
    whole_ = _whole(ask, ask.part, whole, _STENTS, _PERFORMED)
    if whole_.truth is Truth.F:
        return _FALSE
    return _both(_same_duct(ask, ask.part, whole), _kind_in(ask, ask.part, _STENT_PARTS, rq.FactKey.ACT_PART),
                 _family_in(ask, ask.part, _ERCP), whole_)


def _adjunct(ask: _Asker, whole: Id) -> Judged:
    """PROCEDURAL_ADJUNCT (D30, D79): a bleeding control, ablation, clip or injection whose part_of names an act, or
    that treats bleeding the whole (any event of the session) caused; the whole performed or begun. v1's same-lesion
    arm is possible only (_lesion_adjunct). An arm's whole is read only where its relation is not F (the same result;
    D248 G5's cost)."""
    kind = _kind_in(ask, ask.part, _ADJUNCTS, rq.FactKey.ACT_PART)
    if kind.truth is Truth.F:
        return _FALSE
    part_of = _part_of(ask, ask.part, whole)
    by_part = _FALSE if part_of.truth is Truth.F else _both(part_of,
                                                             _whole(ask, ask.part, whole, _ACT_WHOLES, _POSITIVE))
    caused = _caused_by(ask, ask.part, whole)
    by_cause = _FALSE if caused.truth is Truth.F else _both(caused, _whole(ask, ask.part, whole, None, _POSITIVE))
    found = _either(by_part, by_cause) if Truth.T in (by_part.truth, by_cause.truth) else _either(
        by_part, by_cause, _lesion_adjunct(ask, whole))
    return _both(found, kind)


def _lesion_adjunct(ask: _Asker, whole: Id) -> Judged:
    """v1's D30 same-lesion arm ("by its verified part_of or the removal's lesion"), as DECISIONS D221 rules it (the
    module docstring; refute-4b-r2 F1): a part of v1's adjunct kinds (a catalogue kind ablation or bleeding control,
    relations.PROCEDURAL_ADJUNCTS; a clip or an injection whose purpose may be hemostasis included) with a lesion
    stated, beside a removal performed or begun (today, in its session) with a lesion stated, ASKS only where the two
    acts may name the same lesion (_adjunct_lesion): U, asked as its part_of (act_part, rank 17), unless its own
    established part_of or cause says otherwise (_not_adjunct) - never T: with the same lesion the arm reads
    part_relation and cause as 4.7 says, so a part_of or cause_event naming the removal bundles it by those arms. Two
    different supported lesion ids no same_as can join are different findings (P5's one id per distinct finding): F,
    and the ablation's or the bleeding control's code proceeds on its own rows (the installed D30 bundled only the
    removal's same verified lesion; 4.7 asks nothing there) - and only those: a lesion fact that is not supported
    (unresolved, contradicted, doubted, negated) is an unknown identity (4.11), so the arm asks its lesion question
    (DECISIONS D248 G2, option (b)). same_as is read as the equivalence it states: a chain of members through other
    entries joins them as one member does (refute-r4b-r1 R1: pass 1 filing three entries for one finding, each linked to
    the first), and a member naming an id the FactSet does not hold may join its chain to any lesion (R2, 4.11). A
    same_as that may join them and is not established gives U, its one question naming both first; a claim that the two
    lesions are not one finding beside supported members joining them is asked first likewise (D248 G3). The identity's
    question - the same_as or that claim, then each lesion fact not supported - comes before the part_of (act_part):
    what the document must settle about the lesions decides whether the part_of matters. A lesion stated on neither act,
    or on one only, relates nothing here (P13: a target the document does not state is left empty). Monotone under 9.4's
    weakenings: none makes a stated lesion silent, a lesion or same_as fact weakened only widens what each act may name
    and what may join them, and every exit to F reads an established fact, an empty slot no doubt names, or two
    supported lesion ids themselves - deleting a same_as member is the one change that can release it, and 9.4 deletes
    members of places, stations and reached only (the step's NOTES, question QR4-1). The kind and the whole are read
    before the identity (the same result: every exit is F on either; D248 G5's cost)."""
    if _pure_silent(facts_.fact(ask.R, whole, _A.TARGET_LESION)):
        return _FALSE
    removal = _whole(ask, ask.part, whole, _REMOVALS, _POSITIVE)
    if removal.truth is Truth.F or _pure_silent(facts_.fact(ask.R, ask.part, _A.TARGET_LESION)) or \
            _not_adjunct(ask.R, ask.part, whole):
        return _FALSE
    found = _both(_ckind_in(ask, ask.part, _LESION_ADJUNCTS, rq.FactKey.ACT_PART), removal)
    if found.truth is Truth.F:
        return _FALSE
    identity = _adjunct_lesion(ask, whole)
    if identity.truth is Truth.F:
        return _FALSE
    asked = ask.doubt(ask.part, _A.PART_OF, facts_.fact(ask.R, ask.part, _A.PART_OF), rq.FactKey.ACT_PART)
    return Judged(Truth.U, identity.doubts + asked.doubts + found.doubts, None, found.conflicts)


def _lesion_values(R: FactSet, found: Fact) -> frozenset[Id]:
    """The lesions a target.lesion fact may name: supported, its value; negated, every other lesion of the FactSet; not
    established, its claimed value and its options (facts.possibly) - every lesion for an empty slot a doubt names, a
    negation left open ("not L2" unresolved) or a value naming no lesion of the FactSet, supported or not (4.11: a
    missing identifier manufactures neither a match nor a non-match); an overfilled target.lesion slot's merged view
    reads as a written denial alone would (AMENDMENT-2 4.3.3 a; every view, since it cannot tell whether a written fact
    denied a lesion: facts.open_denial, the step's NOTES question Q1R)."""
    every = frozenset(R.lesions)
    if found.result is Result.SUPPORTED:
        if not isinstance(found.value, Id):
            return frozenset()
        return frozenset({found.value}) if found.value in every else every | frozenset({found.value})
    if found.result is Result.NEGATED:
        return frozenset(lesion for lesion in every if lesion != found.value)
    named = frozenset(value for value in (found.value, *found.options) if isinstance(value, Id))
    if facts_.silent(found) or facts_.open_denial(found) or not named or any(value not in every for value in named):
        return every | named
    return named


def _adjunct_lesion(ask: _Asker, whole: Id) -> Judged:
    """DECISIONS D221 as D248 G2 reads it: whether the part and the whole may name the same lesion. T when both target
    lesions are supported and one finding (_SameAs.one_finding: one id, or joined by supported same_as members, directly
    or through other entries) and nothing claims the two entries are not one finding (_SameAs.denials, D248 G3; such a
    claim is asked first). F only when BOTH lesion facts are supported, naming two lesions of the FactSet that no
    same_as - one member or a chain of them (_SameAs.join) - may join: two different supported ids are different findings
    (P5; D221's words, and D248 G2's option (b)). U otherwise: a lesion fact that is not supported - unresolved,
    contradicted, doubted or negated - is an unknown identity, which never sets two acts apart in the adjunct rule
    (4.11), whatever the lesions it may name; and a lesion id naming no lesion of the FactSet manufactures neither a
    match nor a non-match (4.11). A U rests on the first member not established on the cheapest chain that may join them
    (act_target, rank 17: one question naming both) when only a same_as may, then on each lesion fact not supported (or
    naming no lesion of the FactSet): the lesion question."""
    R = ask.R
    one, other = facts_.fact(R, ask.part, _A.TARGET_LESION), facts_.fact(R, whole, _A.TARGET_LESION)
    first, second = _supported_id(one), _supported_id(other)
    same = ask.same_as()
    if first is not None and second is not None and same.one_finding(first, second):
        denials = same.denials(first, second)
        if not denials:
            return _decided(_A.TARGET_LESION)
        return _both(*(ask.doubt(holder, attribute, member, rq.FactKey.ACT_TARGET)
                       for holder, attribute, member in denials))
    # a lesion fact not supported - or supported naming no lesion of the FactSet (4.11) - is what a U rests on
    doubts = [ask.doubt(subject, _A.TARGET_LESION, found, rq.FactKey.ACT_TARGET)
              for subject, found in ((ask.part, one), (whole, other))
              if found.result is not Result.SUPPORTED or _supported_id(found) not in R.lesions]
    left, right = _lesion_values(R, one), _lesion_values(R, other)
    if left & right or not (left | right) <= frozenset(R.lesions):
        # a lesion both may name; or an id naming no lesion of the FactSet, which may be any lesion (4.11)
        return _both(*doubts) if doubts else _decided(_A.TARGET_LESION)
    joined = same.join(left, right)
    if joined is None:
        # D248 G2: different findings only when both lesion facts are supported; an unknown identity is asked
        return _both(*doubts) if doubts else _FALSE
    if joined[1]:
        holder, member = joined[1][0]
        doubts.insert(0, ask.doubt(holder, _A.SAME_AS, member, rq.FactKey.ACT_TARGET))
    return Judged(Truth.U, tuple(doubt for item in doubts for doubt in item.doubts))


# A deterministic order of ids (a frozenset's iteration order is not): family, in IdFamily's order, then number.
_FAMILY_ORDER: Mapping[IdFamily, int] = MappingProxyType({family: order for order, family in enumerate(IdFamily)})


def _id_order(value: Id) -> tuple[int, int]:
    return (_FAMILY_ORDER[value.family], value.number)


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
    """BIOPSY_OF_REMOVED_LESION (C-2, D196): a biopsy of the lesion a removal removed, single or in a shared unit; F
    for a biopsy done elsewhere than every removal (DECISIONS D292 E1j: ``_biopsy_elsewhere``). The whole and the kind
    are read first, the identity only where neither is F (the same result; D248 G5's cost)."""
    whole_ = _whole(ask, ask.part, whole, _REMOVALS, _PERFORMED)
    kind = _kind_in(ask, ask.part, _BIOPSIES, rq.FactKey.ACT_PART) if whole_.truth is not Truth.F else _FALSE
    if Truth.F in (whole_.truth, kind.truth):
        return _FALSE
    if ask.biopsy_elsewhere():  # DECISIONS D292 E1j
        return _FALSE
    return _both(_same_lesion(ask, ask.part, whole), kind, whole_, _single_or_shared(ask, ask.part, whole))


def _landmarks(values: tuple[object, ...] | None) -> tuple[Landmark, ...] | None:
    """An established place list read as landmarks: None when it is not established (facts._supported's None) or a
    member is no landmark (a place the anatomy chain cannot compare)."""
    if values is None:
        return None
    found = tuple(value for value in values if isinstance(value, Landmark))
    return found if len(found) == len(values) else None


def _biopsy_elsewhere(ask: _Asker) -> bool:
    """DECISIONS D292 E1j (HOLDS-ANALYSIS.md, THE FINAL FIX LIST item 1; FINAL-V2 4.7's bundling identity over supported
    places, 4.11 - a place difference counts only with its pair controls rejected -, 5.1 row 10 - "target.places and the
    lesion's places" -, D216 rules 2-3): whether the biopsy ``ask.part`` was done, at least in part, where no removal
    was, so it is not wholly a biopsy of a removed lesion. Whenever
    - the biopsy names no lesion (its target.lesion a pure empty slot: no claim and no doubt naming it, P13), and its
      place list is established (facts._supported: every member established, one supported, every one a landmark);
    - for EVERY event the rule could pair it with as a removal (``_whole`` not F for this rule, over the asker's
      FactSet: a synthetic removal, read over its own FactSet, has no place established and keeps the rule as it was),
      that removal's places are established landmarks: its target.places TOGETHER WITH the established places of the
      removed FINDING when its lesion claim is supported - DECISIONS D294 G1: every lesion entry a same_as member in ANY
      state may join to that lesion, directly or through other entries and in either direction (facts.finding_places,
      the one reading every rule that reads an act's target lesion's places shares, DECISIONS D297 ENGB-1: the
      engine's lesion is its same_as component, P5, and a finding filed as two entries is one finding), each entry's
      established places (a lesion claim neither supported nor a pure empty slot, an entry of the finding whose places
      are not established landmarks, and an id of the finding the FactSet does not hold keep the rule as it was: the
      removed lesion may lie anywhere). same_as is read in the hold direction only: whatever a member's state, it
      names at least its value, so no same_as state - and no verdict of pass 2 on one - narrows the finding, and a
      wider finding can only keep the rule as it was; (lesion, same_as) stays a hold-only read of BUNDLING
      (requirements.RULES, 3.2.3's UNCONTROLLED: it only joins) and CLAIMED and every pass-2 request are unchanged;
    - no place pair control asked of the biopsy or of any such removal is unrejected (DECISIONS D220's every-control
      scan, apart_by_place's instrument); and
    - one supported place of the biopsy is disjoint (engine/anatomy) from each place of every such removal, and each
      removal was asked about that place by a pair control pass 2 REJECTED -
    it is True, read existentially on the biopsy's side only (the code needs one specimen elsewhere). Its lesion claim
    names nothing, so D239's guard (_may_be_one_finding) is False there. The named residual (D292): a lesion that
    reaches a junction filed at one segment and sampled on its other side, with pass 2 rejecting the removal-place
    control - two reading errors, accepted under FINAL-V2 4.13, which dropped D58/D77's adjacency. Under 9.4's
    weakenings it moves as apart_by_place does: a place, a lesion or a control weakened, or an added doubt, fails a
    condition that needs an established fact, a pure empty slot or a rejected control; a same_as member weakened keeps
    its value and adds only its options, so it only widens the finding; a deleted removal place could release only
    where a rejected control asked that removal about the very place deleted (D245's Q2 shape), and its control, when
    one exists, stays read. tests/v2/test_properties.py runs P-MONO over it."""
    R, part = ask.R, ask.part
    if not _pure_silent(facts_.fact(R, part, _A.TARGET_LESION)):
        return False
    mine = _landmarks(facts_._supported(R, part, _A.TARGET_PLACES))
    if mine is None:
        return False
    wholes = [other for other in R.events
              if other != part and _whole(ask, part, other, _REMOVALS, _PERFORMED).truth is not Truth.F]
    if not wholes:
        return False
    theirs: dict[Id, tuple[Landmark, ...]] = {}
    for other in wholes:
        places = _landmarks(facts_._supported(R, other, _A.TARGET_PLACES))
        if places is None:
            return False
        lesion = facts_.fact(R, other, _A.TARGET_LESION)
        if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id):
            found = ask.same_as().finding_places(lesion.value)  # DECISIONS D294 G1, D297 ENGB-1: the removed finding
            held = _landmarks(tuple(member.value for member in found.members
                                    if member.result is Result.SUPPORTED and member.value is not None))
            if found.unknown is not None or held is None:
                return False  # an entry without established places, or an id the FactSet does not hold
            places += held  # 5.1 row 10: the removed finding's own places, every entry of it
        elif not _pure_silent(lesion):
            return False
        theirs[other] = places
    asked = frozenset(wholes) | {part}
    if any(not rejected for (subject, about, _value), rejected in R.pair_controls.items()
           if about is _A.TARGET_PLACES and subject in asked):
        return False
    return any(all(all(anatomy.disjoint(place, theirs_place) for theirs_place in theirs[other])
                   and R.pair_controls.get((other, _A.TARGET_PLACES, place)) is True for other in wholes)
               for place in mine)


def _drainage(ask: _Asker, whole: Id) -> Judged:
    """DRAINAGE_STEP (G3, D171, D177): a fine-needle aspiration whose part_of names a drainage, or of its lesion; the
    drainage performed or begun. The whole and the kind are read first (the same result; D248 G5's cost)."""
    whole_ = _whole(ask, ask.part, whole, _DRAINAGES, _POSITIVE)
    kind = _kind_in(ask, ask.part, _ASPIRATIONS, rq.FactKey.ACT_PART) if whole_.truth is not Truth.F else _FALSE
    if Truth.F in (whole_.truth, kind.truth):
        return _FALSE
    return _both(_either_lazily(lambda: _part_of(ask, ask.part, whole), lambda: _same_lesion(ask, ask.part, whole)),
                 kind, whole_)


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
    or the family's own, and for a synthetic act) by ``rule``; ``truth`` T (established) or U (possible, never F);
    ``attribute`` the fact that decided a T; ``doubts`` the facts a U rests on; ``unlisted`` the index in
    FactSet.unlisted of the synthetic act it is a bundling into (3.2.6 rule 3 as DECISIONS D231 reads it: a kept
    unlisted act or doubt, a possible whole read as its filed doubted form - never T, its own doubt asked), None for
    any other."""
    part: Id
    whole: Id | None
    rule: Rule
    truth: Truth
    attribute: Attribute | None
    doubts: tuple[Doubt, ...]
    conflicts: tuple[HeldFact, ...] = ()
    unlisted: int | None = None


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


# --- 3.2.6 rule 3's synthetic act as a possible whole (DECISIONS D216, D231: coverage's C1) ---------------------------

# A synthetic act's status as its filed doubted form holds it: a doubt that it was performed (3.3 row 2).
_DOUBTED_PERFORMED = Fact(result=Result.UNKNOWN, value=Status.PERFORMED, state=FactState.SUPPORTED, options=(),
                          reasons=(Reason.DOUBT_STATED,), spans=())


def _filed_doubted_form(R: FactSet, entry: UnlistedStatement) -> dict[Attribute, tuple[Fact, ...]]:
    """The facts pass 1 would have filed for a synthetic act (a kept unlisted act or doubt, 3.2.6 rule 3 as D231 reads
    it): its kind as the entry names it (an empty slot when it names none: every kind possible), its status a doubt
    that it was performed, its session its card - supported when the FactSet holds that session, unresolved and
    reference_invalid when it does not (settle's I4: a missing identifier manufactures neither a match nor a non-match,
    4.11), an empty slot with no card (every session possible) - and every other slot empty: its date, performer, entry,
    lesion, places, duct, part_of and cause unknown."""
    facts: dict[Attribute, tuple[Fact, ...]] = {_A.STATUS: (_DOUBTED_PERFORMED,)}
    if entry.kind is not None:
        facts[_A.KIND] = (Fact(result=Result.SUPPORTED, value=entry.kind, state=FactState.SUPPORTED, options=(),
                               reasons=(), spans=()),)
    if entry.session is not None:
        known = entry.session in R.sessions
        facts[_A.SESSION] = (Fact(result=Result.SUPPORTED if known else Result.UNRESOLVED, value=entry.session,
                                  state=FactState.SUPPORTED, options=(),
                                  reasons=() if known else (Reason.REFERENCE_INVALID,), spans=()),)
    return facts


def _free_event_number(R: FactSet) -> int:
    """One above every event number the FactSet holds or any of its facts names (a dangling part_of or cause_event
    included) or a pair control asks: a synthetic act's place-holder id is never an event a fact or a control names."""
    numbers = [event.number for event in R.events]
    tables = (R.events, R.sessions, R.sections, R.lesions, R.anatomy, R.people)
    for found in (*(member for table in tables for facts in table.values() for members in facts.values()
                    for member in members),
                  *(member for members in R.encounter.values() for member in members)):
        numbers += [value.number for value in (found.value, *found.options)
                    if isinstance(value, Id) and value.family is IdFamily.EVENT]
    for subject, _attribute, value in R.pair_controls:
        numbers += [item.number for item in (subject, value) if isinstance(item, Id) and item.family is IdFamily.EVENT]
    return max(numbers, default=0) + 1


def _synthetic_item(R: FactSet, index: int) -> HeldFact:
    """A synthetic act's one doubt where a rule read it as a possible whole (D231): an unlisted act's item -
    performed_status at the doubt row (rank 2), cause unlisted, about no single fact, quoting the entry's own units -
    its subject the session its card names when the FactSet holds it, None otherwise (evaluate's _synthetic_doubt and
    classes' synthetic examination take the same shape, which step 4a words: DECISIONS D246)."""
    entry = R.unlisted[index]
    return _unlisted_item(entry, entry.session if entry.session in R.sessions else None)


# --- the reader: one FactSet's per-event readings, each computed once -------------------------------------------------


class Reader:
    """One FactSet's per-event readings for the functions below (the pairs of 4.5, the bundles, the verdicts, the
    witnesses), each computed once per Reader. Read-only: the FactSet is frozen, and nothing here changes it. Make one
    per FactSet and pass it where a function takes ``reader``; never share one across FactSets."""

    __slots__ = ('R', 'order', '_pairs', '_unlisted', '_bundles', '_verdicts', '_conflicts', '_same', '_synthetic')

    def __init__(self, R: FactSet) -> None:
        self.R = R
        self.order: Mapping[Id, int] = MappingProxyType({event: index for index, event in enumerate(R.events)})
        self._pairs: dict[Id, tuple[pairing.Pair, ...]] = {}
        self._unlisted: dict[Id, tuple[pairing.UnlistedPair, ...]] = {}
        self._bundles: dict[Id, tuple[Bundle, ...]] = {}
        self._verdicts: dict[Id, Verdict] = {}
        self._conflicts: dict[Id, tuple[HeldFact, ...]] = {}
        self._same: _SameAs | None = None
        self._synthetic: tuple[FactSet, tuple[tuple[int, Id], ...]] | None = None

    @classmethod
    def of(cls, value: Reader | FactSet) -> Reader:
        return value if isinstance(value, Reader) else cls(value)

    def _same_as(self) -> _SameAs:
        """The FactSet's same_as graph and its memoized walks, joins and components (_SameAs), built once."""
        if self._same is None:
            self._same = _SameAs(self.R)
        return self._same

    def _synthetic_wholes(self) -> tuple[FactSet, tuple[tuple[int, Id], ...]]:
        """3.2.6 rule 3's synthetic acts as possible wholes (DECISIONS D231's coverage half, C1): the FactSet with each
        synthetic act (combination.synthetic: a kept unlisted ACT or DOUBT) added as its filed doubted form under a
        place-holder event id no fact names (_free_event_number), and (its index in FactSet.unlisted, that id) per act,
        in stored order - built once. The filed doubted form (_filed_doubted_form) is what pass 1 would have filed for
        the act: its kind as the entry names it (an empty slot when it names none), its status a doubt, its session its
        card (an empty slot with none; a card the FactSet does not hold unresolved, reference_invalid: settle's I4), and
        every other slot empty; its anchor the entry's units. A bundling rule reads it exactly as it reads a filed act
        in doubt, so an unlisted act, an unlisted doubt and the same act filed in doubt give one outcome."""
        if self._synthetic is None:
            R = self.R
            indices = combination.synthetic(R)
            start = _free_event_number(R)
            virtual = tuple((index, Id(IdFamily.EVENT, start + position)) for position, index in enumerate(indices))
            if not virtual:
                self._synthetic = (R, ())
            else:
                events = dict(R.events)
                anchors = dict(R.anchors)
                for index, whole in virtual:
                    entry = R.unlisted[index]
                    events[whole] = _filed_doubted_form(R, entry)
                    anchors[whole] = Anchor(units=tuple(entry.units), kind_words=None, status_words=None)
                self._synthetic = (FactSet(R.encounter, R.people, R.sections, R.sessions, R.anatomy, R.lesions, events,
                                           anchors, R.unlisted, R.pair_controls, R.completeness), virtual)
        return self._synthetic

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
                    # DECISIONS D287: a relation's conflict over an act whose label is OTHER is conflict:other, as in
                    # evaluate (its _row_clean); else the act's label, or the first kind through which it is concerned
                    named = (kind if kind is Kind.OTHER or kind in pair.kinds
                             else min(pair.kinds, key=list(Kind).index, default=kind))
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
        """Each rule in Rule's order: the part's own rules, then each whole rule over every other event and then every
        synthetic act (DECISIONS D231, C1: a possible whole, read as its filed doubted form - _synthetic_wholes - so a
        bundling into it is U, never T; the doubts that rest on the place-holder's own facts are the synthetic act's one
        doubt, Bundle.unlisted, which the verdict asks)."""
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
        rules = [(rule, judge_whole) for rule, judge_whole in _WHOLE_RULES if kinds & _RULE_PARTS[rule]]
        synthetic, virtual = self._synthetic_wholes() if rules else (R, ())
        asked = _Asker(synthetic, event, self)
        for rule, judge_whole in rules:
            for whole in R.events:
                if whole == event:
                    continue
                found = judge_whole(ask, whole)
                if found.truth is not Truth.F:
                    out.append(Bundle(event, whole, rule, found.truth, found.attribute, found.doubts,
                                      found.conflicts))
            for index, whole in virtual:
                found = judge_whole(asked, whole)
                if found.truth is not Truth.F:
                    out.append(Bundle(event, None, rule, found.truth, None,
                                      tuple(doubt for doubt in found.doubts if doubt.subject != whole),
                                      found.conflicts, index))
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
                if bundle.unlisted is not None:  # the synthetic act's one doubt (D231, C1)
                    held.append(_synthetic_item(self.R, bundle.unlisted))
                held += [witness(doubt.fact, doubt.attribute, doubt.subject, doubt.key, doubt.kind, spans,
                                 bundle.rule.value) for doubt in bundle.doubts]
        return Verdict(Truth.U, bundles, tuple(dict.fromkeys(held)), bool(conflicts))

    def _spans(self, event: Id, bundle: Bundle) -> tuple[Span, ...]:
        """What a bundle's item quotes: the part's anchor and the whole's (4.3: "naming the whole") - a synthetic act's
        own units for a bundling into one."""
        whole = (_anchor_units(self.R, bundle.whole) if bundle.unlisted is None
                 else tuple(self.R.unlisted[bundle.unlisted].units))
        return _ordered(_anchor_units(self.R, event) + whole)

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
    step of (T: established; U: possible - a synthetic drainage among them, its whole None and its entry
    Bundle.unlisted), None when it is the step of none. engine/assess.py's EUS code checks read it (step 5a)."""
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
    the session it is the included portion of (C3, C-4); ``possibly_part_of`` the session it may be (D70);
    ``possible_unlisted`` its synthetic examinations left open (DECISIONS D231's C2: the indices in FactSet.unlisted of
    the kept unlisted acts and doubts that may be its examination, read only in a session with no established
    examination - D232 - each a possible examination as its filed doubted form would be)."""
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
    possible_unlisted: tuple[int, ...] = ()


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


def _manual(R: FactSet, event: Id) -> bool:
    """FINAL 5.6 E13 (DECISIONS D69, D227): a digital examination is no session's examination, and makes no session
    done - read as step 4d's session_done reads it (DECISIONS D253, QE13 option (a): combination._digital, the
    reference, called rather than copied: an event that may be an examination whose device CLAIMS manual - supported
    manual, or, not established, manual its claimed value or a reading)."""
    return combination._digital(R, event)


def _examination_sessions(R: FactSet, event: Id) -> frozenset[Id]:
    """The sessions ``event`` may be the examination of: step 4d's possible_sessions, read for membership (DECISIONS
    D227: 4d's session_done is the one derivation of "a session is done", and its membership is part of it) - those
    sessions_of leaves open, and EVERY session when the session fact is an established negation, which 4d's
    _named_sessions reads as naming no session. sessions_of keeps "every other session" for that negation elsewhere in
    this module (the step's NOTES, question QR4-2)."""
    found = facts_.fact(R, event, _A.SESSION)
    return frozenset(R.sessions) if found.result is Result.NEGATED else sessions_of(R, event)


def _may_be_examination_of(R: FactSet, session: Id, event: Id) -> bool:
    """``event`` may be ``session``'s examination (D62; step 4d's combination._may_be_examination_of, D227's
    reference): its kind possibly the examination (facts.possibly), the session possibly ``session``
    (_examination_sessions), possibly positive on the date by the documenting team (4.4's frame: pairing.positive, its
    date relation and its performer not established as another), and not a digital examination (E13)."""
    return (facts_.possibly(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
            and session in _examination_sessions(R, event) and _positive_here(R, event) and not _manual(R, event))


def _examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The session's ESTABLISHED examinations (step 4d's combination._examinations): kind supported examination,
    session supported ``session``, a digital examination excepted (E13)."""
    return tuple(event for event in R.events
                 if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(facts_.fact(R, event, _A.SESSION), session) and not _manual(R, event))


def done_examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The session's done examinations (D69-D71 over facts, DECISIONS D227), in pass 1's order: its established
    examinations (kind supported examination, session supported, a digital examination excepted: FINAL 5.6 E13) that
    are done (4.3 rows 2-5 supported: reading.done). Never D62's possible ones."""
    view = reading.Reading.of(R)
    return tuple(event for event in _examinations(R, session) if reading.done(view, event))


def possible_examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """D62, D87 (DECISIONS D227: step 4d's reading): the events that may be the session's examination
    (_may_be_examination_of) and are not done (4.3 rows 2-5 not all supported) - the examinations "left open" that keep
    a session told only through its acts from being done. DECISIONS D269 (Q-P2DATE option (c), 4.3 row 7; D227's one
    derivation, step 4d's combination.session_possibly_done the reference): a session whose examination is established,
    and established not done on the date of service (combination.not_done_today: planned, or done on another date, and
    no event the document places in it that may be its examination done today), has NONE - every act possibly in it,
    placed or supported, whatever its date or its session slot, is exempt, so none makes it possibly done (D256 P2's
    letter, which this replaces, excepted only an act whose session slot is silent and whose date is not established:
    the mirror of 4d's _unplaced_undated, gone with it). Such a session has an established examination for coverage
    too, and none of them done (one done today would keep it from not_done_today), so it is not done whatever this
    lists (4.3 row 7; _session_done): the exemption moves no ``done``, only the record's ``possible`` and
    ``unresolved``. A 9.4 weakening only ever undoes not_done_today (4d's docstring), so the exemption is never what a
    weakening adds (r4b's question Q3 of round w8r: under D256 P2's letter, weakening a dated act's date to unresolved
    dropped it from a settled session's list)."""
    if combination.not_done_today(R, session):
        return ()  # DECISIONS D269: no act possibly in a session established not done today is left open there
    view = reading.Reading.of(R)
    return tuple(event for event in R.events
                 if _may_be_examination_of(R, session, event) and not reading.done(view, event))


def possible_unlisted_examinations(R: FactSet, session: Id) -> tuple[int, ...]:
    """DECISIONS D231's coverage half, C2 (its row 1; D232): the synthetic examinations left open in a session told only
    through its acts - step 4d's combination.synthetic_examinations (the kept unlisted acts and doubts of kind
    examination or none that may be in the session: its card, or no card, or a card the FactSet does not hold), read
    only when the session has no established examination: beside one, a synthetic examination adds nothing (D232).
    Each is a possibly performed examination that is never done, as its filed doubted form is (possible_examinations
    would list that form)."""
    return () if _examinations(R, session) else combination.synthetic_examinations(R, session)


def _session_done(R: FactSet, session: Id, exams: Sequence[Id], possible: Sequence[Id],
                  unlisted: Sequence[int]) -> bool:
    """DECISIONS D227: THE derivation of "a session is done" - step 4d's combination.session_done, the reference (4.3
    row 7: "its examination, when it has one, passes 2-5 (an act-only session: the act itself)"): one of its
    established examinations is done (``exams``, done_examinations, read only when it has established ones); with
    none, one of its acts (session supported; a digital examination excepted, E13) is done - a session told only
    through its acts (D121, D135) - and no event that may be its examination is left open (``possible``,
    possible_examinations), nor a synthetic act that may be (``unlisted``, possible_unlisted_examinations: DECISIONS
    D231 row 1, C2). The cross-module test (tests/v2/test_coverage.py, OneSessionDone) asserts it equals 4d's on
    generated FactSets, kept unlisted entries among them."""
    view = reading.Reading.of(R)
    if _examinations(R, session):
        return bool(exams)
    if possible or unlisted:
        return False
    return any(facts_.holds(facts_.fact(R, event, _A.SESSION), session) and reading.done(view, event)
               and not _manual(R, event) for event in R.events)


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
        unlisted = possible_unlisted_examinations(R, session)
        found[session] = Session(
            id=session, kind=_session_kind(R, session), events=members, examinations=exams, possible=possible,
            event=exams[0] if len(exams) == 1 and not possible else None,
            unresolved=len(exams) + len(possible) + len(unlisted) >= 2,
            done=_session_done(R, session, exams, possible, unlisted),
            incomplete=bool(exams) and all(facts_.holds(facts_.fact(R, event, _A.STATUS),
                                                        Status.ATTEMPTED_NOT_COMPLETED) for event in exams),
            possible_unlisted=unlisted)
    for session, record in list(found.items()):
        part_of, possibly = _part_of_session(R, found, record)
        if part_of is not None or possibly is not None:
            found[session] = _replace(record, part_of, possibly)
    return found


def _replace(record: Session, part_of: Id | None, possibly: Id | None) -> Session:
    return Session(id=record.id, kind=record.kind, events=record.events, examinations=record.examinations,
                   possible=record.possible, event=record.event, unresolved=record.unresolved, done=record.done,
                   incomplete=record.incomplete, part_of=part_of, possibly_part_of=None if part_of else possibly,
                   possible_unlisted=record.possible_unlisted)


def _part_of_session(R: FactSet, found: Mapping[Id, Session], record: Session) -> tuple[Id | None, Id | None]:
    """(part_of, possibly_part_of) of ``record`` (module docstring): C3 by its part_of_session, C-4 and D70 structurally
    for a done EGD beside an EUS session. D70's "may be done" is step 4d's combination.session_possibly_done, the
    reference (DECISIONS D227's one derivation; D231 row 2 and coverage's C3: a synthetic act - a kept unlisted act or
    doubt - with card S, or no card, or a card the FactSet does not hold, makes S possibly done, as the same act filed
    in doubt does; an entry with no card that names a kind makes possibly done only a session one of whose possible
    families holds that kind, DECISIONS D256 P2's K2). C-4's established whole reads the EUS done. DECISIONS D269
    (Q-P2DATE option (c); the integration's I4 residual; its coverage half, read as 4d's combination.wholes reads it): a
    session whose examination is established, and established not done on the date of service (planned, or done on
    another date: combination.not_done_today), is never a whole of ``record`` - C3's supported part_of_session naming
    it is no whole, D70's part_of_session not established names it as no possible whole, and the structural arms read
    it not done (C-4) and not possibly done by any act, placed or supported, whatever its date or session slot (D70:
    session_possibly_done reads not_done_today first) - so a planned or an earlier EUS is never the whole of today's
    EGD, and the EGD keeps its own items. D70's part_of_session not established names exactly its claimed value and its
    options - an empty slot a doubt names by its readings, never a session nothing names (DECISIONS D286, G3-14 option
    (a); refute-r4b-r1 V9R4B1-2: facts.possibly over an empty slot named the first session not settled, one nothing
    named) - the one set 4d's combination.wholes and _named_wholes read (D227)."""
    stated = facts_.fact(R, record.id, _A.PART_OF_SESSION)
    whole = _supported_id(stated)
    if (whole is not None and whole != record.id and whole in found
            and not (record.kind is not None and found[whole].kind is record.kind)
            and not combination.not_done_today(R, whole)):  # DECISIONS D269: never a whole
        return whole, None
    possibly: Id | None = None
    if not facts_.established(stated) and not _pure_silent(stated):
        # DECISIONS D286 (G3-14): exactly the claim's value and options - an empty slot's doubt by its readings, never a
        # session nothing names (facts.possibly is True for every session over an empty slot) - step 4d's one set
        # (combination.wholes, _named_wholes), AMENDMENT-2 4.3.3's claimed-value read routed by this step's list
        possibly = next((other for other in found if other != record.id
                         and (other == stated.value or other in stated.options)
                         and not combination.not_done_today(R, other)), None)  # D269
    if record.kind is SessionKind.EGD and record.done and len(record.examinations) == 1:  # v1's ``own``
        for other in found.values():
            # C-4 reads the EUS's kind established; D70 by possibly (4.7): a kind not established that leaves the EUS
            # open makes the EGD possibly its endoscopic portion, never part of nothing
            if other.id == record.id or not _session_kind_may_be(facts_.fact(R, other.id, _A.KIND), SessionKind.EUS):
                continue
            upper = _tract_upper(R, other.id)
            if other.kind is SessionKind.EUS and other.done and upper is Truth.T:
                return other.id, None
            if upper is not Truth.F and combination.session_possibly_done(R, other.id):
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
    """The families ``event`` may be of: its session's when established; otherwise the families of the sessions it may
    be in (sessions_of; for each, its kind when supported, else every kind it may be) - except that, when its own
    session fact is not established, it reads EVERY family (4.2: "every kind, when the session is not established
    either") unless the sessions it may be in admit its kind (DECISIONS D227 F8: the kind's membership in FAMILY_KINDS,
    the table settle's K2 reads, D191 - K2 demotes the session of an act its claimed session cannot hold, as a PEG
    filed under a colonoscopy, which no reading of that session would ever list). An ERCP's contrast injection whose
    session pass 2 left unresolved, the ERCP its only possible session, is read as the ERCP's (refute-4b-r2 F8).

    "Admit" is read so that a weakening never narrows the families (9.4 P-MONO; the step's NOTES, question QR4-3):
    EVERY session the act may be in admits EVERY kind it may be (_raw_kinds) under EVERY family that session may be of.
    D227's words - every family "only when no session it may be in admits its kind" - read with ANY in place of each
    EVERY would let an added reading narrow them: a PEG left in a colonoscopy whose kind gains a cannulation reading
    (which a colonoscopy admits) would be read as a colonoscopy act alone and un-doubted. A session id the FactSet does
    not hold may be of any family (D227 R2-2): every family."""
    family = facts_.session_family(R, event)
    if family is not None:
        return frozenset({family})
    found = facts_.fact(R, event, _A.SESSION)
    possible = sessions_of(R, event)
    if not facts_.established(found):
        named = (found.value, *found.options)
        if any(isinstance(value, Id) and value not in R.sessions for value in named):
            return frozenset(SessionKind)
        kinds = _raw_kinds(R, event)
        if not all(kinds <= facts_.family_kinds(other) for session in possible
                   for other in session_families(R, session)):
            return frozenset(SessionKind)
    out: set[SessionKind] = set()
    for session in possible:
        out |= session_families(R, session)
    return frozenset(out) if out else frozenset(SessionKind)


def _raw_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """The kinds ``event`` may be, as K2's kind arm reads a kind (the kind itself, an umbrella not expanded): supported,
    its value; negated, every other kind; not established, facts.possibly's (every kind for an empty slot)."""
    found = facts_.fact(R, event, _A.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        return frozenset({found.value})
    if found.result is Result.NEGATED:
        return frozenset(kind for kind in Kind if kind != found.value)
    return frozenset(kind for kind in Kind if facts_.possibly(found, kind))


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
    covered; an act CPT Studio could not confirm as done at this encounter. READ_UNDER_NOT_ESTABLISHED (DECISIONS D227
    F4; no v1 sentence, the step's request to 3c): an act another service would read under it whose places are not
    established all within that service's sites - listed in doubt, with a coverage question."""
    SESSION_PERFORMED = 'session_performed'
    SESSION_INCOMPLETE = 'session_incomplete'
    NO_PROFILE = 'no_profile'
    ATTEMPTED_OR_IN_DOUBT = 'attempted_or_in_doubt'
    NO_CODE_OF_SERVICE = 'no_code_of_service'
    READ_UNDER_NOT_PLACED = 'read_under_not_placed'
    READ_UNDER_NO_SERVICE = 'read_under_no_service'
    READ_UNDER_NOT_ESTABLISHED = 'read_under_not_established'
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
    """What an in_doubt item's service question is about: an event, or a kept unlisted act (its index); and
    ``witness``, the coverage question the listing itself asks besides the act's own witnesses (DECISIONS D227 F4: a
    read-under act whose place list is not established complete), None for none."""
    event: Id | None = None
    unlisted: int | None = None
    witness: HeldFact | None = None


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
    while that other session has no counted code, or when one of its counted codes includes the examination - beside a
    DONE whole only (DECISIONS D286 ruling F, G3-13 option (b), refute-r4b-r1 V9R4B1-1: v1's rule presumes a whole that
    reconcile itself lists when it has no code, and reconcile lists only done sessions; beside a C3 whole that is not
    done - weakened, planned, or told by nothing - the part keeps its own no_proposal item and completeness reads
    incomplete). The filter is this rule's alone and never filters D70's possible wholes (D286)."""
    including = sessions_.get(session.part_of) if session.part_of is not None else None
    if including is None or including.kind is None or session.kind is None or not including.done:  # D286 ruling F
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
        elif catalogue.FAMILY_SUPPORT.get(family) is not catalogue.SupportLevel.SUPPORTED:
            continue
        elif session.done:
            out.covered[session.id] = _reconcile_session(reader, sessions_, session, family, counted, read_by,
                                                         procedure_day, any_done, out)
        elif _counted_family(R_, session, counted):  # not done, and the unestablished count skips it
            _reconcile_not_done(reader, sessions_, session, family, counted, read_by, out)
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
    # what the session's items quote: its one examination, else its first done member that is no digital examination
    # (E13: a digital examination is no session)
    anchor = session.event or next((event for event in session.events if _done(R_, event) and not _manual(R_, event)),
                                   None)
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


def _reconcile_not_done(reader: Reader, sessions_: Mapping[Id, Session], session: Session, family: SessionKind,
                        counted: Sequence[Counted], read_by: Mapping[Id, list[Counted]], out: Coverage) -> None:
    """A session that is NOT done (DECISIONS D227's one derivation: its established examination not done, or an event
    that may be its examination left open, filed or synthetic) that counted codes read - per session, D248 G1: for every
    family it is stated as, a code of that family one of whose events may be in it - which the unestablished count
    skips (_counted_family): its member acts are read as a done session's are (_member), its items and bundled acts
    appended to ``out`` - so a done act no counted code reads stays listed whatever step 4a's row 7 reads of the session
    (refute-r4b-r1 R5: step 4a reads an examination whose session is established as another as no examination of it,
    step 4d's reference as possibly any session's, so 4a can propose the session's codes READY while coverage calls it
    not done; the step's NOTES, question QR5-1). No no_proposal item and no covered entry: the session is not
    established as performed."""
    codes = _codes_of(session, counted, sessions_)
    unknown = any(catalogue.code_link(item.code).route is not catalogue.LinkRoute.CATALOGUE for item in codes)
    for event in session.events:
        _member(reader, sessions_, session, family, event, read_by, unknown, out)


def _kind_unestablished(reader: Reader, sessions_: Mapping[Id, Session], session: Session, counted: Sequence[Counted],
                        read_by: Mapping[Id, list[Counted]], procedure_day: bool, any_done: set[Id],
                        out: Coverage) -> None:
    """A done session whose kind is not established (v1 grouped it by pass 1's claimed family and listed it), read as
    EVERY supported family it may be of (session_families): whatever one reading lists is listed - its family None,
    since none is established - and the codes that cover it are those covering it under every reading. So a weakening
    of the session's kind (its family one of those it may be of) never releases what the established family listed,
    and a done session no reading covers is listed no_proposal, never 'complete'. A session that may be of no
    supported family is not read, as v1 read none. One that is not done is read so too, its members only
    (_reconcile_not_done), when the unestablished count skips it (for every family it may be of, a counted code of that
    family whose events may be in it: D248 G1). The readings' items list each act once (_one_entry_per_act, D248 G4)."""
    families = [family for family in session_families(reader.R, session.id)
                if catalogue.FAMILY_SUPPORT.get(family) is catalogue.SupportLevel.SUPPORTED]
    if not families or not (session.done or _counted_family(reader.R, session, counted)):
        return
    found = Coverage()
    covered: list[str] | None = None
    for family in sorted(families, key=list(SessionKind).index):
        reading = _with_kind(session, family)
        view = {**sessions_, session.id: reading}
        if not session.done:
            _reconcile_not_done(reader, view, reading, family, counted, read_by, found)
            continue
        codes = _reconcile_session(reader, view, reading, family, counted, read_by, procedure_day, any_done, found)
        covered = codes if covered is None else [code for code in covered if code in codes]
    if session.done:
        out.covered[session.id] = covered or []
    kept = _one_entry_per_act(found)
    renamed = {id(item): Item(item.session, None, item.act, item.reason, item.detail, item.events, item.evidence,
                              item.unlisted) for item in kept}
    out.unresolved += [renamed[id(item)] for item in kept]
    # the items a reading listed in doubt keep their questions (D227 F3, F4), each act once
    asked: set[Id | None] = {ref.event for _, ref in out.in_doubt if ref.event is not None}
    for item, ref in found.in_doubt:
        if id(item) in renamed and (ref.event is None or ref.event not in asked):
            asked.add(ref.event)
            out.in_doubt.append((renamed[id(item)], ref))
    seen = {act.event for act in out.bundled}
    for act in found.bundled:
        if act.event not in seen:
            seen.add(act.event)
            out.bundled.append(act)


def _one_entry_per_act(found: Coverage) -> list[Item]:
    """DECISIONS D248 G4 (refute-r4b-r2 G4; D225: every customer sentence true for its state): the items the readings of
    a session whose kind is not established listed, each act once. An act two readings list differently - an EUS
    biopsy read under the upper endoscopy with its sites not established under the EUS reading, not covered under the
    upper endoscopy's - is listed by ONE item: the first that lists it in doubt (its question kept: a reading's in-doubt
    listing keeps its question, D227 F3 and F4), else the first that lists it. A session's own item (no act kind) and an
    unlisted act's (no event) are kept as listed; _merge then merges by session and act kind as for any session (the
    step's NOTES, question QG4)."""
    in_doubt = {id(item) for item, _ in found.in_doubt}
    chosen: dict[Id, int] = {}
    for position, item in enumerate(found.unresolved):
        if item.act is None or not item.events:
            continue
        for event in item.events:
            current = chosen.get(event)
            if current is None or (id(item) in in_doubt and id(found.unresolved[current]) not in in_doubt):
                chosen[event] = position
    return [item for position, item in enumerate(found.unresolved)
            if item.act is None or not item.events or any(chosen[event] == position for event in item.events)]


def _with_kind(record: Session, kind: SessionKind) -> Session:
    return Session(id=record.id, kind=kind, events=record.events, examinations=record.examinations,
                   possible=record.possible, event=record.event, unresolved=record.unresolved, done=record.done,
                   incomplete=record.incomplete, part_of=record.part_of, possibly_part_of=record.possibly_part_of,
                   possible_unlisted=record.possible_unlisted)


def _stated_families(R: FactSet, session: Session) -> list[SessionKind]:
    """The families a session is stated as, for the unestablished count: its kind, or for a kind not established each
    family it may be of - each with a catalogue entry."""
    families = frozenset({session.kind}) if session.kind is not None else session_families(R, session.id)
    return [family for family in families if catalogue.FAMILY_SUPPORT.get(family) is not None]


def _reads(R: FactSet, item: Counted, session: Id) -> bool:
    """Whether a counted code's decision read an event possibly in ``session`` (sessions_of): one of its supporting or
    read events."""
    return any(session in sessions_of(R, event) for event in (*item.supporting, *item.read))


def _counted_family(R: FactSet, session: Session, counted: Sequence[Counted]) -> bool:
    """Whether the session is read by counted codes, PER SESSION (DECISIONS D248 G1; refute-r4b-r2 G1): a family stated,
    and for EVERY family the session is stated as, a counted code of that family one of whose events (supporting or
    read) is possibly in this session (_reads). v1's "a code of its family" meant this session's code, because v1 had
    one session per family; v2 reads sessions from the sessions table (4.7), so a second session of a coded family is
    read by no code unless a code's events may be in it. The unestablished count skips such a session that is not done,
    and reconcile reads its members instead (_reconcile_not_done: the R5 gate) - one predicate for both."""
    stated = _stated_families(R, session)
    return bool(stated) and all(any(item.family is family and _reads(R, item, session.id) for item in counted)
                                for family in stated)


def _unestablished(R: FactSet, session: Session, counted: Sequence[Counted]) -> bool:
    """v1's unestablished count over one session that is not done: a family stated (its kind, or for a kind not
    established each family it may be of, with a catalogue entry), read by no counted code per session (D248 G1: not
    every family it is stated as has a counted code whose events may be in it - _counted_family), and an event possibly
    in it (possible_members) possibly positive here - an examination whose own session fact is in doubt is possibly
    this session's - or a synthetic act that may be in it (DECISIONS D216: a kept unlisted act or doubt is a possibly
    performed act of its session for every rule whose release is the absence of one; combination.synthetic_in: its
    card, no card, or a card the FactSet does not hold). A weakening only adds families and possible members; the one
    that can drop a session from the count is a counted code's event whose own session fact it leaves open, so that
    the event may be in this session too (sessions_of widens) - and that code's own session row then holds it (4.3 row
    6: its session not established), an open question of the assessment."""
    if not _stated_families(R, session) or _counted_family(R, session, counted):
        return False
    return any(_positive_here(R, event) for event in possible_members(R, session.id)) or any(
        combination.synthetic_in(R, R.unlisted[index], session.id) for index in combination.synthetic(R))


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
    if catalogue.READ_UNDER.get((family, kind)) is not None and reader.conflicts(event):
        # DECISIONS D227 F3 (D3; 4.8 rank 1): a contradicted act is never read under another service - listed in
        # doubt, its service question its conflict (act_witnesses: the conflicts first); a code that reads it asks it
        if event not in read_by:
            _list_in_doubt(R, session.id, family, kind, event, Detail.IN_DOUBT, out)
        return
    under = _read_under(R, sessions_, family, kind, event)
    if under is not None:
        if under is Detail.NOT_COVERED:
            out.bundled.append(BundledAct(session.id, event, kind, None, None))
        elif under is Detail.READ_UNDER_NOT_ESTABLISHED:
            # D227 F4: its place list's completeness not established - listed, asking a coverage question (it holds no
            # code: a service question, 4.8, for an act no counted code reads)
            if event not in read_by:
                _list_in_doubt(R, session.id, family, kind, event, under, out, _read_under_witness(R, event))
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
    """v1's _read_under over facts (catalogue.READ_UNDER: an EUS forceps biopsy read under the upper endoscopy), with
    DECISIONS D227 F4 (P3: no rule reads a list's completeness except through an established completeness claim or
    rejected pair controls): Detail.NOT_COVERED as "read under" only when a done session of that family has a done
    performed act of the kind and the act's place list is established complete within the rule's regions
    (_places_complete); else why nothing reads it - READ_UNDER_NOT_PLACED when a supported place lies outside them (or
    its places are not established and no such service reads it: v1's reading), READ_UNDER_NO_SERVICE when no such
    service reads it, READ_UNDER_NOT_ESTABLISHED (listed in doubt, with a coverage question) when one would and its
    places do not establish that it may; None for any other act."""
    rule = catalogue.READ_UNDER.get((family, kind))
    if rule is None:
        return None
    other_family, regions = rule
    places = facts_.members(R, event, _A.TARGET_PLACES)
    known = [member.value for member in places if member.result is Result.SUPPORTED]
    outside = any(not (isinstance(place, Landmark) and anatomy.in_regions(place, regions)) for place in known)
    inside = bool(places) and all(facts_.established(member) for member in places) and bool(known) and not outside
    reads = any(other.kind is other_family and other.done and any(
        _claimed_catalogue_kind(R, member) is kind and _done(R, member)
        and facts_.holds(facts_.fact(R, member, _A.STATUS), Status.PERFORMED) for member in other.events)
        for other in sessions_.values())
    if not inside and (outside or not reads):
        return Detail.READ_UNDER_NOT_PLACED
    if not reads:
        return Detail.READ_UNDER_NO_SERVICE
    if not inside or not _places_complete(R, event, regions):
        return Detail.READ_UNDER_NOT_ESTABLISHED
    return Detail.NOT_COVERED


def _places_complete(R: FactSet, event: Id, regions: Iterable[anatomy.Region]) -> bool:
    """D227 F4: whether the act's place list - established, its supported places all within ``regions`` - is
    established COMPLETE there: every landmark outside ``regions`` that none of its places is compatible with (the
    places claims.pair asks an act about) is excluded, by a REJECTED pair control asking the act about it (3.2.3: "This
    act was done in the {place}.") or a negated member of its list. The FactSet holds no completeness claim for an
    act's places (FactSet.completeness: an upper EUS session's stations only), and step 2c generates pair controls only
    for the places other objects of the act's session name, so on a settled FactSet this rarely holds and the act is
    listed (the step's NOTES, question QR4-4). A deleted member only adds landmarks to exclude: monotone."""
    regions = frozenset(regions)
    places = facts_.members(R, event, _A.TARGET_PLACES)
    listed = [member.value for member in places
              if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)]
    denied = frozenset(member.value for member in places if member.result is Result.NEGATED)
    return all(R.pair_controls.get((event, _A.TARGET_PLACES, landmark)) is True or landmark in denied
               for landmark in Landmark
               if not anatomy.in_regions(landmark, regions)
               and not any(anatomy.compatible(landmark, place) for place in listed))


READ_UNDER_RULE = 'read_under'


def _read_under_witness(R: FactSet, event: Id) -> HeldFact:
    """D227 F4's coverage question about a read-under act whose place list is not established complete (4.8 rank 17,
    act_target: whether another service reads it depends on where it was done): resting on its first place not
    established (its first place, or an empty slot, otherwise), cause coding_rule:read_under when that place is
    established (the doubt is the rule's own: the list's completeness), quoting the act and its places."""
    places = facts_.members(R, event, _A.TARGET_PLACES)
    found = next((member for member in places if not facts_.established(member)), places[0] if places else
                 facts_.SILENT)
    spans = _ordered(_anchor_units(R, event) + tuple(span for member in places for span in member.spans))
    return witness(found, _A.TARGET_PLACES, event, rq.FactKey.ACT_TARGET, _kind_of(R, event), spans, READ_UNDER_RULE)


def _list_in_doubt(R: FactSet, session: Id | None, family: SessionKind | None, kind: Kind | None, event: Id,
                   detail: Detail, out: Coverage, asked: HeldFact | None = None) -> None:
    """List ``event`` in doubt with its service question (D227 F3 and F4): an in_doubt item, and its InDoubt (``asked``:
    the coverage question the listing asks besides the act's own witnesses)."""
    item = Item(session, family, kind, ItemReason.IN_DOUBT, detail, (event,), _evidence(R, (event,)))
    out.unresolved.append(item)
    out.in_doubt.append((item, InDoubt(event=event, witness=asked)))


def _in_doubt(reader: Reader, session: Session | None, read_by: Mapping[Id, list[Counted]], out: Coverage,
              known: frozenset[Id] = frozenset()) -> None:
    """The in_doubt items of one session (``session`` None: of the events filed under none of the ``known`` sessions -
    an empty, contradicted or doubted slot, or an id naming no session of the FactSet), each listed once: each doubted
    act no counted code reads and not bundled - and D142's class in doubt (_elsewhere_in_doubt) - and each unlisted act
    of the session (3.2.6 rule 3). A contradicted act (D3; DECISIONS D227 F3) is listed in doubt with its conflict
    question even where D137's class records it reportable (eus_unlisted). An act the member loop already listed in
    doubt (D227 F3, F4) is not listed twice."""
    R = reader.R
    family = session.kind if session is not None else None
    if family is not None and catalogue.FAMILY_SUPPORT.get(family) is not catalogue.SupportLevel.SUPPORTED:
        return
    members = session.events if session is not None else tuple(event for event in R.events
                                                                if filed(R, event) not in known)
    key = session.id if session is not None else None
    already = {ref.event for _, ref in out.in_doubt if ref.event is not None}
    for event in members:
        if event in read_by or event in already or bundled(reader, event) is not None:
            continue
        listed, doubt = eus_unlisted(reader, event)
        if (listed and not reader.conflicts(event)) or not (doubted(reader, event) or doubt or any(
                _elsewhere_in_doubt(R, other, event) for other in ((session.id,) if session is not None
                                                                   else tuple(sorted(sessions_of(R, event),
                                                                                     key=_id_order))))):
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


def _elsewhere_in_doubt(R: FactSet, session: Id, event: Id) -> bool:
    """D142's class IN DOUBT: an act possibly in ``session`` (sessions_of) that may be of a kind a family that session
    may be of (_reading_families: its kind when established; else each supported family it may be of) does not list
    among its acts while a supported family does (no E/M kind, examination, umbrella or never-reported kind) - D142
    lists it not covered when it is done, performed, its kind supported and its session supported - possibly positive
    here and not so established: in doubt, listed (a doubt is never an absence). Reachable past settle's K2 for a kind
    the family's codes account for and its acts do not list (the ERCP's foreign body); v1 listed it nowhere (its
    compl-1 and doubted read the family's acts). Its session not established is a doubt too, and so is its session's
    kind (repair r4b): DECISIONS D227 F8 reads such an act in its possible sessions' families when they admit its kind,
    as the ERCP admits a foreign body, so ``doubted`` no longer reaches it through every family. A kind the family
    bundles as its own (FAMILY_OWN_BUNDLED: the ERCP's contrast injection) is the family's, never this class."""
    if session not in sessions_of(R, event) or not _positive_here(R, event) or (
            _done(R, event) and facts_.holds(facts_.fact(R, event, _A.STATUS), Status.PERFORMED)
            and facts_.holds(facts_.fact(R, event, _A.SESSION), session)):
        return False
    elsewhere = frozenset(kind for other, level in catalogue.FAMILY_SUPPORT.items()
                          if level is catalogue.SupportLevel.SUPPORTED for kind in catalogue.FAMILY_ACTS.get(other, ()))
    kinds = catalogue_kinds(R, event)
    return any(kind not in catalogue.FAMILY_ACTS.get(family, ()) and kind not in FAMILY_OWN_BUNDLED.get(family, ())
               and kind in elsewhere and kind not in catalogue.EM_KINDS and kind not in _NOT_ACTS
               and kind not in catalogue.NOT_REPORTED for family in _reading_families(R, session) for kind in kinds)


def _reading_families(R: FactSet, session: Id) -> frozenset[SessionKind]:
    """The supported families ``session`` is read as: its kind when established, else every family it may be of
    (session_families) - each with a supported catalogue entry (v1 read no other: reconcile, _in_doubt)."""
    kind = _session_kind(R, session)
    families = frozenset({kind}) if kind is not None else session_families(R, session)
    return frozenset(family for family in families
                     if catalogue.FAMILY_SUPPORT.get(family) is catalogue.SupportLevel.SUPPORTED)


# The read-under listings (v1's two and D227 F4's): each a sentence of its own, never merged into another listing of
# the same act kind (refute-r4b-r1 R3; DECISIONS D225: every customer sentence true for its state).
_READ_UNDER_DETAILS: frozenset[Detail] = frozenset({Detail.READ_UNDER_NOT_PLACED, Detail.READ_UNDER_NO_SERVICE,
                                                    Detail.READ_UNDER_NOT_ESTABLISHED})


def _merge(out: Coverage) -> None:
    """One item per (session, act kind): a second site of one service is the same code (v1); every in_doubt event of a
    merged item keeps its question (D89). A read-under listing merges only with listings of its own Detail
    (_READ_UNDER_DETAILS): an EUS biopsy placed outside the upper GI sites and another whose sites are not established
    are two sentences, each true of its own acts."""
    merged: dict[tuple[Id | None, Kind | None, Detail | None], Item] = {}
    keys: dict[int, tuple[Id | None, Kind | None, Detail | None]] = {}
    for index, item in enumerate(out.unresolved):
        key = (item.session, item.act, item.detail if item.detail in _READ_UNDER_DETAILS else None)
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
    not INDEPENDENT (pairing.item at its rank) and each unlisted denial or doubt (pairing.item: performed_status at
    rank 2, DECISIONS D228); its status (rank 2 when doubted, else 4), kind (4; a positive umbrella act_method, 9)
    and - for a clip or an injection - purpose (4); its entry (5: an explanation when established as another role),
    date relation (6), performer (7), session and its kind (8); its bundling in doubt (rank 17). Ordered by rank
    (4.8)."""
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
        asked = pairing.item(unlisted_pair)  # performed_status at RANK row 2 (DECISIONS D228)
        assert asked is not None and asked.rank is not None
        out.append(HeldFact(fact=rq.fact_key(asked.fact), attribute=None, subject=event, result=None,
                            kind=ItemKind.QUESTION, cause=UNLISTED, reason=None, spans=unlisted_pair.spans,
                            rank=asked.rank.value))
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
    no counted code reads, with its own item (act_item, or the listing's own coverage question when it ranks first:
    InDoubt.witness, DECISIONS D227 F4; an unlisted act's, _unlisted_item). ``asked``: the (subject,
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
            if ref.witness is not None:  # the listing's own coverage question (D227 F4), at its rank among them
                found = tuple(sorted(dict.fromkeys((*found, ref.witness)), key=_item_order))
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
