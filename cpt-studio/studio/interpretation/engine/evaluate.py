"""The per-code rule of design v2 (docs/gemini-migration/FINAL-V2.md 4.3, 4.4, 4.6, 4.10, 4.11 and Appendix A; step 4a of
8.1; DECISIONS D182, D188, D189, D191, D194, D197; repair r4a: D216, D225's engine half, D226, D229's 4a P2-P4, P8,
P9, and its refutation refute-r4a-r1's F1, F4, F7; repair r4a of round w7r: D232's row 7, D240's site fit, and its
refutation's P1 - a digital examination never makes a session non-act-only - and P5; repair r4a of round w8r: D253, a
digital examination is never the session's done examination either, and, after its refutation refute-r4a-r1, never
supports an examination code - P1; repair r4a of round w9r: D265, a digital examination never words, binds or changes
an item, and D267's conflict key; step f3w of AMENDMENT-2's build round: D280.1, row 7 reads no examination established
as a digital examination, and D287, every conflict key names facts.established_kind): one proposed code against the
settled, text-free FactSet - its
candidates, its supporting acts (E*), every unresolved or failed requirement of every positive candidate, the binding of
each held group, and its exclusion. Forked from v1's events.py and ercp.py with their readers deleted (5.5): the rules
read results, ids and integer spans only, through engine/facts.py's predicates and engine/pairing.py's relations.

**decide(code, kept, R)** is 4.4's outcome function (``decide``):
- route (d) (no link, or a link naming no act) is held, never READY (C-6): one item, performed_status at rank 4, an
  explanation (coding_rule:unprofiled, or not_linked for a code of another family); D80's recognised-only codes
  (99152, 99153) likewise (coding_rule:recognised_only). Neither reads a group.
- For each requirement group (catalogue.requirements): the CANDIDATES are the events possibly of a kind covering the
  group (facts.possibly, the candidate arm of 4.2: the claimed value, the readings, the control's sibling; an umbrella
  covers its members, a tattoo and an injection are one act; a clip or an injection read through catalogue.catalogue_kind
  by possibly - the bleeding control it may be when its purpose is possibly hemostasis, silent included: D157's doubt
  arm, kept by 4.13, step 1e's hand-off R5; itself unless its purpose is supported hemostasis, which makes it a bleeding
  control only) whose status is not denied performed. 4.4 reads no session family here: an act of the code's kind in
  another family's session is a candidate, failing row 6. A candidate SUPPORTS the code when every row of
  SUPPORT below is T (and, for 43264, its YIELD: 4.3's "no support from that act"). When some candidate supports, the
  group is met and E* gains every supporting one. Otherwise the POSITIVE candidates (possibly performed or attempted -
  a doubted status and one pass 2 did not establish included [R:HO-1] - and not established as of another date or
  performer) each record EVERY witness (held fact) of every non-T row [R:HO-8], and questions.choose binds the group
  (4.8; its "fewest non-T requirements" counted over requirements_of(code): ``unmet``) - never on a digital examination
  of an examination group (D265: FINAL 5.6 E13; ``_digital_candidate``), which stays a positive candidate holding the
  code (repair r4a-2's DV1) while its witnesses never word the item: with only digital examinations positive, the
  group's item is 4.6's own (the item the document gets without them; never an exclusion: ``_unbound_item``). With no
  positive candidate,
  the exclusion (4.6) decides: EXCLUDED (reinstatable), or a statement_scope question, or not documented (7.6:
  performed_status, rank 4). Round r3 (DESIGN-v2 f.1, f.2(3)): 4.6 reads R_base, and - DECISIONS D324 (6) - it runs for
  a group only when R_base's own 4.4 decision of the group reaches it, read by the same code path (``_read_group``: no
  supporting act, no pending candidate, no found or pending XCHG pair); otherwise the group is held, not documented.
- Then the code-specific rows (4.4's ``code_requirements``) over EVERY supporting act, each non-T row's witnesses added
  to ``held_facts``: there is no early return before them (Q2), and an act that fails one stays in E* while it holds the
  code (the design's literal outcome function; v1's R4 filtered such an act out of E* instead - recorded as a
  question). The one exception is D240's (D29's installed reading, "A verified target outside the class does not
  support"): for a code with a SITE row, beside a supporting act established within its site class an act
  established outside it is no supporting act - it leaves E* and none of the code's rows reads it (``_site_fit``).
  "The distal esophageal stricture was dilated with a balloon. The duodenal bulb stricture was dilated with a
  balloon." gives 43249 on the esophageal act and 43245 on the duodenal one. An act whose site is not established
  stays in E* and is read (its SITE row asks which structure was dilated), and with no act established within the
  class every supporting act stays, as before (the misfit explanation, or the site question) - the step's NOTES,
  question QB, names the installed reading's other half.
- Route (b) (46221) is never READY (Appendix A; D197): after its groups, one item, performed_status at rank 4, cause
  coding_rule:route_b. Its row 6 is its places in the code's regions; exclusion, base and competition read its acts.
- 3.2.6 rule 2 (``on_evidence``): a code whose kept evidence overlaps the unit of a kept unlisted entry (an act, a denial
  or a doubt) is held - performed_status at RANK 2 ("an unlisted unit on its evidence", h2), cause unlisted, quoting the
  unit - and none of its groups is excluded (a citation beside it is asked). No 8.1 row names its owner; built here
  fail-closed, a question for the integration owner (the refutation's D1; the step's NOTES).

**SUPPORT(E, C, g)** (4.3 rows 1-8, each T, U or F with its witnesses):
1. kind: supported and covering g; a positive umbrella (removal, intervention) never supports a method-specific code -
   every catalogue code is one - and asks act_method (rank 9, h5); a clip or an injection supports a bleeding-control
   group only with its purpose supported hemostasis, and its own (injection) group only when its purpose neither is
   supported hemostasis nor claims it unestablished. An unestablished kind or purpose asks performed_status at rank 4
   (step 1f's reading R9(c)). A digital examination (FINAL 5.6 E13: its device claims manual) never supports an
   examination group - it is no session's examination (D253; refute-r4a-r1 P1 of round w8r): its device established,
   the not-documented question (rank 4), else the device's own question - witnesses that never word the item (D265).
2. status: supported performed; also attempted_not_completed for a code with the ATT tag (step 1f's hand-off R9(a): the
   tag, never catalogue.examination_code, which also answers the office E/M codes). Attempted on any other code is an
   explanation at rank 4 (C-9: coding_rule:attempted; the 52/53 consideration is assess's). A doubt pass 1 reported on
   status asks rank 2, any other status not established rank 4.
3. the effective date relation supported on_date_of_service (event_time, rank 6).
4. the effective performer supported documenting_team (event_performer, rank 7).
5. the entry supported documenting_clinician (event_entry, rank 5): another owner supported is an explanation.
6. route (a): the session supported, its kind supported the code's family (procedure, rank 8); route (b): every place of
   the act established, its supported places in the code's regions, at least one (act_target, rank 11).
7. the session is done: every event that may be its examination (``examinations``, by its own kind and session facts -
   step 1f's hand-off R9(d) - in a session whose family admits one, the established tie included: refute-4a-r2 P3)
   passes rows 2-5 (an examination begun counts as done, as v1's done does), except that beside the session's own done
   examination - never a digital one (FINAL 5.6 E13, D253: as ``act_only`` and D227's session_done read it) - an event
   established as of another occasion (a plan, another date, another performer) adds nothing; a session with none is
   the act's own (T). An examination ESTABLISHED as a digital examination (pairing.established_digital: kind supported
   examination, device supported manual - E13's established reading, D227, D253) is read by no part of row 7: it is
   neither the session's done examination nor one whose rows 2-5 must pass (DECISIONS D280.1), so it never words, binds
   or changes an item; one whose device only claims manual is read as before and keeps QD2's hold (D280.3, D271),
   worded by engine/questions (DIGITAL_SCOPE). Another act's own facts never touch it (K2). A synthetic examination act
   of
   the session (D216: a kept unlisted act or doubt that may be its examination) is one that is never done: its doubt
   holds - in an act-only session only (D232: no event established as the session's examination, a digital examination
   excepted as combination.session_done's act-only arm excepts it - FINAL 5.6 E13, D227, refute-r4a-r1 P1; beside an
   examination established as the session's, done or not, a synthetic one adds nothing).
8. no CONTRADICTION, DOUBT or UNRESOLVED relation from any paired statement (engine/pairing.py, 4.5) - each its rank-1,
   rank-2 or row's item - and no unlisted denial or doubt pairing with it (statement_scope, cause unlisted). A
   contradicted fact among rows 1-7 asks rank 1 (conflict:<kind>) on its own row, a doubt on status rank 2; an act
   whose kind is not supported is conflict:other (D267, D287: facts.established_kind's Kind.OTHER, its item's one
   label, which questions.act_kind, coverage's and classes' keys read too).
E/M (the EM templates): the visit's session encounter supported this_encounter (event_time, rank 6).

**An established failure with no explanation.** 4.8 makes an F an explanation; where neither 4.3 nor
requirements.RULES names one (rows 3, 4 and 6 - the date relation, the performer or the session's family established
otherwise -, route (b)'s place outside its regions, the examination of row 7 established not done, the E/M encounter
established separate, ROUTE's other routes, LIMITED's full reach for 43231 and 43232, XCHG's possible exchange), the
witness is the requirement's question (kind question, cause coding_rule:<rule>): held either way, and every held fact has
a sentence (the step's NOTES, question Q4).

**The code-specific rows** (4.3's second table; Appendix A's tags), each over every supporting act (or its session):
TECH (technique.device in the code's class: another class an explanation, an unestablished or classless device a
question); SITE (D29: every place of the act and its supported lesion established, its supported
places within the class, at least one; every supported place outside the class, none surgically made or unplaced, is
the "another site" explanation; the lesion is its FINDING - every entry a same_as member in any state may join to it,
an entry without established places or an id the FactSet does not hold leaving the row open: DECISIONS D297 ENGB-1);
STRUCT:pfc (43240: structure supported pancreatic_fluid_collection, no supported place biliary or hepatic: D120, D136,
D145); ROUTE (43253: route supported eus_transmural; submucosal is the wall
injection's explanation); TRACT (the session's tract, D171(2); an EUS filed pancreatobiliary fits the upper codes:
D226); STATIONS (43242, 43259: the three upper stations supported examined and a reach at or beyond the duodenum, or an
empty list with the completeness claim supported and that reach [R:SC-B]; a station negated is the class explanation;
only the members that may name an upper station are read: refute-4a-r2 P4); LIMITED (43231, 43232: reached short of the
duodenum; 43237, 43238 - the codes whose profile includes the EGD, step 1f's hand-off #7 - a station negated or
reached short; all three examined is the class explanation; the upper stations only, as STATIONS); LOWER (D43: the
class reach, the stoma codes also an anatomy entry of type stoma supported and the approach through_stoma, and -
DECISIONS D325 (2) - a colonic route, ``_lower_colonic`` (DECISIONS D327 (1): never where the anatomy may leave the
colon gone, ``whole_colon_absent_possible``), else the class's route hold; the stoma
class's approach is asked at RANK row 8, procedure - another approach supported its explanation naming it, an approach
or a stoma entry not established its question - and through_stoma denied the class explanation: D225, P5; the reach
and the approach each recorded when not T: refute-r4a-r1 F7; DECISIONS D328 (1): the class's route is the lower-GI
route table's, per anus for the sigmoidoscopic and colonoscopic classes, ``_anus_route``); YIELD
(43264: yield supported stones, stone fragments, sludge or debris; negated is "documented as retrieving nothing";
contradicted conflict:stone_extraction; a filter of SUPPORT, 4.3's "no support from that act");
CAUSE (purpose supported hemostasis and cause supported pre_existing_lesion, spontaneous or earlier_procedure; cause
act_of_this_session or purpose prophylaxis is bundled, rank 18); XCHG (43274, 43275: no possibly-performed counterpart,
filed or kept unlisted - an act or a doubt (D216) - in the same or an unknown duct - the duct question names the act
whose duct is not established, in the two-act form (D225, P6); beside a filed counterpart in the same duct, whether
the two were one exchange, about the counterpart when its status is not established; 43276: a stent exchange
supporting, or a stent removal and a stent placement each supporting in one duct, both ducts supported and equal; a
positive filed part beside a kept unlisted other part is a pair candidate too (D216)). Every witness rests on the fact
that is not T under that fact's own attribute (a contradicted purpose, reach or target lesion is never witnessed as
the cause, the stations or the act's places: D225 P7, refute-r4a-r1 F4). R6 and COLFULL, ENT, C3+SEP, ADDON, bundling,
combination, R7 and R9 are the steps 4b, 4c, 4d and 5a rows that assess appends (4.4). THE LOWER-GI ROUTE TABLE
(DECISIONS D328 (1); catalogue.LOWER_ROUTES): every lower-GI endoscopy code's route row - a code is READY only when the
record establishes its route and nothing filed contradicts the anatomy it needs, read fail-closed (``_row_lower_route``,
under a colonoscopy code's COLFULL row, a sigmoidoscopy's and an enteroscopy's under Requirement.ROUTE_TABLE; a lower
EUS code's in its LOWER row; the section comment at the table). THE LOWER-GI PATH GUARD (DECISIONS D330 (1); catalogue.
HARMLESS): after every arm of those rows, a lower-GI code is held with the table's own hold unless every anatomy entry
of the document is the entry its route itself uses or a match for a row of the ruled harmless set for its route
family, and a per-anus code's own approach and through do not contradict the route - fail-closed by construction: a
shape the set omits holds (``path_guard``, ``_guarded``; the section comment before ``_row_lower_route``).

**Exclusion** (4.6): with no supporting act and no positive candidate, a statement D excludes the code only when (1) D's
kind is supported and covers the group, its session supported of the code's family (route (b): its places in the code's
regions) - never a digital examination's examination kind (D265: as a statement it denies no session's examination
either, ``_concerns``, ``possibly_here``); (2) its deciding fact is established - status negated performed, or supported
planned; the date relation supported earlier_date or later_date; the performer supported other_clinician or
other_facility - an attempted status never decides (C-9); (3) a current denial's breadth is supported and not exceptive
(a statement of another date or performer, or a plan, carries none: K1); (4) the code covers D by citation (C-10,
``cover``); (5) nothing doubts the code's kinds (no event possibly of them - its kind read with its session's family,
4.2 - possibly done today by the documenting team; no DOUBT relation; no unlisted denial, doubt or act of them: 3.2.6
rule 3's synthetic doubted act, an unlisted clip or injection a possible bleeding control, two unlisted acts or doubts a
possible stent exchange (D216); and no unlisted unit on the code's kept evidence, rule 2). A partial cover, a citation
beside a doubt, a broad current denial (4.10) the code does not cite, and a denial of the code's kinds whose session or
date relation is not established (its session possibly of the code's family) all ask statement_scope (rank 3, C-7) - a
broad denial is never dropped; otherwise not documented.

**C-10, kept as geometry over offsets** (``cover``; v1's coverage_of and within_words, ported over DECISIONS D188's
text-free view): CITATION when a kept span overlaps D's anchor units and every kept span lies within the union of D's
kind words and status words (its Anchor) and the ``at`` spans of the ``statement`` sources of D's target lesion, target
places and date relation (Fact.cited). PARTIAL when a kept span overlaps and one reaches past that union; NONE
otherwise. v1 read each letter or digit of a kept span; the engine holds no text, so the caller may pass ``kept_words``,
the letter-or-digit runs of the kept spans computed at R1 by an allowlisted character-class function, and without them
every offset of every kept span must lie inside the union (fail-closed: a gap of a space or a stop makes the cover
partial, a statement_scope question, never an exclusion). A source citing its whole units (no located words) adds
nothing (fail-closed).

**The item** (``item``): the one clarification of a held code (questions.item over the evaluation's held facts and any
the caller appends - R6, the class and code checks, the combination - with the groups' positive candidates recomputed,
and questions.Raised: what the item needs of the holds this module raised beside the FactSet - 3.2.6 rule 2's entries,
XCHG's two acts, the synthetic acts - D225).

**The absence conditions** (D216: every rule whose condition is the ABSENCE of a possibly performed act reads 3.2.6
rule 3's synthetic doubted act - a kept unlisted ACT - as possibly performed, and a kept unlisted DOUBT too: a doubt
about whether an act was done leaves it possibly performed, 4.2 [R:HO-1], so the weaker statement never releases what
the stated act holds - refute-r4a-r1 F1; ``synthetic_possible``; a DENIAL is a statement only, the step's NOTES,
question Q1. ``synthetic_kinds``: every kind when it names none, else what its kind covers; ``synthetic_in``: its card,
or any session when it names none or one the FactSet does not hold). Every one in this module, and whether it reads it:
- XCHG's counterparts of 43274 and 43275 (``counterparts``, ``unlisted_counterparts``): reads it (the duct question
  about the unlisted act or doubt, which has no duct);
- 43276's pair candidates (``_pairs``): reads it (a positive filed part beside a synthetic other part);
- 4.6 condition 5 (``doubted``): reads it (any nature, as before; now also an unlisted clip or injection as a possible
  bleeding control, and two synthetic parts as a possible exchange, ``_exchange_doubted``);
- row 7's possible examinations (``synthetic_examinations``): reads it in an act-only session that admits an
  examination (``act_only``; D232, which rules the earlier NOTES' question Q2: beside an examination established as
  the session's, a synthetic one adds nothing, and the session's base code keeps 3.2.6 rule 3's base_included hold,
  step 4d's; an unlisted doubt keeps 3.2.6 rule 4's pairing, row 8);
- "no positive candidate" before 4.6 (``_decide``): through condition 5 - never EXCLUDED beside one; never READY (an
  unlisted entry never supports); the not-documented item names no unlisted act (the step's NOTES, question Q3).
The other conditions are about facts, places, statements or relations, not the absence of an act: route (b)'s
regions; TRACT, STATIONS, LIMITED, LOWER (session facts); row 8's pairing and 3.2.6 rule 4 (a statement's presence);
rule 2 (``on_evidence``: an entry's presence); 4.6's last paragraph (``possibly_here``) and 4.10 (``broad``): denials.

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, facts, pairing, questions, requirements, requirements_table and types
only - no retired v1 module (5.0), none of contract's text modules, not wording - holds no word, phrase or marker list
(every module-level collection holds enumeration members), reads no text and returns no document string. ``mypy
--strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum, unique
from types import MappingProxyType
from typing import Protocol

from studio.interpretation.contract.types import (AnastomosisSubtype, AnatomyType, Approach, Attribute, Breadth, Cause,
                                                  DateRelation, Device, EncounterRelation, Extent, Kind, Landmark, Link,
                                                  Material, Owner, Performer, Purpose, Reason, Result, Route,
                                                  SessionKind, Status, Structure, Tract, UnlistedWhat)
from studio.interpretation.engine import anatomy, catalogue, classes, pairing, questions
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import CODES, Tag, Template
from studio.interpretation.engine.types import (Cover, Evaluation, Exclusion, Fact, FactSet, HeldFact, Id, IdFamily,
                                                ItemKind, Span, UnlistedStatement)

_A = Attribute
_Q, _E = ItemKind.QUESTION, ItemKind.EXPLANATION
_Rule = questions.Rule


@unique
class Truth(Enum):
    """The truth of a requirement (FINAL-V2 4.2, B's Kleene view): T when its facts hold the needed values, F when a fact
    is established against them, U otherwise (9.1's trace writes it)."""
    T = 'T'
    U = 'U'
    F = 'F'


# --- the items RANK gives each row (4.3, 4.8; engine/requirements.RULES) ------------------------------------------------

_STATUS = rq.Item(rq.Rank.STATUS, rq.FactKey.PERFORMED_STATUS)
_DOUBT = rq.Item(rq.Rank.DOUBT, rq.FactKey.PERFORMED_STATUS)
_ENTRY = rq.Item(rq.Rank.ENTRY, rq.FactKey.EVENT_ENTRY)
_TIME = rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME)
_PERFORMER = rq.Item(rq.Rank.PERFORMER, rq.FactKey.EVENT_PERFORMER)
_PROCEDURE = rq.Item(rq.Rank.PROCEDURE, rq.FactKey.PROCEDURE)
_METHOD = rq.Item(rq.Rank.METHOD, rq.FactKey.ACT_METHOD)
_TECHNIQUE = rq.Item(rq.Rank.TECHNIQUE, rq.FactKey.TECHNIQUE)
_ACT_TARGET = rq.Item(rq.Rank.ACT_TARGET, rq.FactKey.ACT_TARGET)
_TARGET = rq.Item(rq.Rank.TARGET, rq.FactKey.TARGET)
_STATIONS = rq.Item(rq.Rank.EXAM_STATIONS, rq.FactKey.EXAM_STATIONS)
_EXTENT = rq.Item(rq.Rank.EXTENT, rq.FactKey.EXTENT)
_YIELD = rq.Item(rq.Rank.YIELD, rq.FactKey.ACT_YIELD)
_CAUSE = rq.Item(rq.Rank.BUNDLING, rq.FactKey.ACT_CAUSE)
_BUNDLED = rq.Item(rq.Rank.BUNDLED, rq.FactKey.PERFORMED_STATUS)
_SCOPE = rq.Item(rq.Rank.STATEMENT_SCOPE, rq.FactKey.STATEMENT_SCOPE)

# The kinds the rules name (catalogue's tables, as enumeration members).
_POSITIVE: frozenset[Status] = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})
_OTHER_DATES: frozenset[DateRelation] = frozenset({DateRelation.EARLIER_DATE, DateRelation.LATER_DATE})
_OTHER_PERFORMERS: frozenset[Performer] = frozenset({Performer.OTHER_CLINICIAN, Performer.OTHER_FACILITY})
_DOUBTS: frozenset[Reason] = frozenset({Reason.DOUBT_STATED, Reason.DOUBT_UNCLEAR})
_RETRIEVED: frozenset[Material] = frozenset({Material.STONES, Material.STONE_FRAGMENTS, Material.SLUDGE, Material.DEBRIS})
_BLEEDING_CAUSES: frozenset[Cause] = frozenset({Cause.PRE_EXISTING_LESION, Cause.SPONTANEOUS,
                                                Cause.EARLIER_PROCEDURE})
_UNPLACED: frozenset[Landmark] = anatomy.ALTERED | anatomy.UNPLACED
# XCHG (D105, D127): each stent act's counterparts, which make a possible exchange beside it.
_COUNTERPARTS: Mapping[Kind, frozenset[Kind]] = MappingProxyType({
    Kind.STENT: frozenset({Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE}),
    Kind.STENT_REMOVAL: frozenset({Kind.STENT, Kind.STENT_EXCHANGE})})
_EXCHANGE_PARTS: tuple[tuple[Kind, ...], tuple[Kind, ...]] = ((Kind.STENT_REMOVAL,), (Kind.STENT,))
_STENT_KINDS: frozenset[Kind] = frozenset({Kind.STENT, Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE})
# The natures of a kept unlisted entry every absence condition reads as a possibly performed act (D216; refute-r4a-r1
# F1): an act (3.2.6 rule 3's synthetic doubted act) and a doubt (4.2 [R:HO-1]); never a denial
# (``synthetic_possible``).
_POSSIBLY_PERFORMED: frozenset[UnlistedWhat] = frozenset({UnlistedWhat.ACT, UnlistedWhat.DOUBT})
# The row each pairing row's UNRESOLVED relation is about (its witness's attribute).
_ROW_ATTRIBUTE: Mapping[pairing.Row, Attribute] = MappingProxyType({
    pairing.Row.SESSION: _A.SESSION, pairing.Row.TIMING: _A.DATE_RELATION, pairing.Row.PERFORMER: _A.PERFORMER,
    pairing.Row.BREADTH: _A.SCOPE_BREADTH, pairing.Row.TARGET: _A.TARGET_PLACES,
    pairing.Row.TECHNIQUE: _A.TECHNIQUE_DEVICE})
# C-10's statement-linked target and timing facts whose ``at`` spans join the cover (4.6 condition 4; D188): those the
# statement's pairing reads (requirements.RULES' SUP.8), v1's COVERING less the kind and status (the Anchor's words).
_COVERING: tuple[Attribute, ...] = (_A.TARGET_LESION, _A.TARGET_PLACES, _A.DATE_RELATION)


# --- records ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Row:
    """One requirement of one candidate (4.3): which (a requirements.Requirement or a code-specific Tag), its Truth, and
    its witnesses (empty for T)."""
    requirement: rq.Requirement | Tag
    truth: Truth
    witnesses: tuple[HeldFact, ...] = ()


@dataclass(frozen=True, slots=True)
class Support:
    """SUPPORT(E, C, g) with the code's per-act rows: every row's truth and witnesses, in 4.3's order. ``partner``: for
    43276's pair (XCHG), the stent placement beside the removal ``event``."""
    event: Id
    rows: tuple[Row, ...]
    partner: Id | None = None

    @property
    def met(self) -> bool:
        """Every row T: the act supports the code."""
        return all(row.truth is Truth.T for row in self.rows)

    @property
    def witnesses(self) -> tuple[HeldFact, ...]:
        """Every witness of every non-T row, each once, in row order."""
        return tuple(dict.fromkeys(held for row in self.rows for held in row.witnesses))

    @property
    def unmet(self) -> int:
        """How many rows are not T (4.8 binding rule (3))."""
        return sum(1 for row in self.rows if row.truth is not Truth.T)


class PairsReader(Protocol):
    """What row 8 reads through a caller's per-FactSet reader (engine/coverage.Reader: its pairs and unlisted pairs,
    each computed once per Reader): the FactSet it reads, and an act's pairs."""
    R: FactSet

    def pairs(self, event: Id) -> tuple[pairing.Pair, ...]: ...

    def unlisted_pairs(self, event: Id) -> tuple[pairing.UnlistedPair, ...]: ...


@dataclass(frozen=True, slots=True)
class _Code:
    """The proposal's code with its link and its requirement spec (engine/requirements.spec). ``reader``: DECISIONS D324
    (8) (round r3's integration int5, the ask lane's Q1 (b)) - the caller's reader of the FactSet ``support`` reads, when
    it passed one (the planner's what-if worlds and its FactSet: one coverage.Reader each), through which row 8 reads an
    act's pairs once per Reader instead of once per code."""
    code: str
    link: catalogue.CodeLink
    spec: rq.Spec
    reader: PairsReader | None = None

    @property
    def template(self) -> Template:
        return self.spec.template

    def has(self, tag: Tag) -> bool:
        return tag in self.spec.tags


def _code(code: str) -> _Code:
    return _Code(code, catalogue.code_link(code), rq.spec(code))


# --- reading facts ------------------------------------------------------------------------------------------------------


def _fact(R: FactSet, subject: Id | None, attribute: Attribute) -> Fact:
    return facts_.fact(R, subject, attribute)


def _members(R: FactSet, subject: Id | None, attribute: Attribute) -> tuple[Fact, ...]:
    return facts_.members(R, subject, attribute)


def _id(found: Fact) -> Id | None:
    """The supported id a fact names; None unless supported."""
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def _doubted(found: Fact) -> bool:
    """A doubt pass 1 reported (3.3 row 2: unknown with doubt_stated or doubt_unclear)."""
    return found.result is Result.UNKNOWN and any(reason in _DOUBTS for reason in found.reasons)


def _anchor(R: FactSet, event: Id | None) -> tuple[Span, ...]:
    return questions.anchor_units(R, event)


def _quoted(found: Fact | None, R: FactSet, event: Id | None) -> tuple[Span, ...]:
    """What a witness quotes: the fact's own spans, else the event's anchor."""
    if found is not None and found.spans:
        return tuple(sorted(set(found.spans)))
    return _anchor(R, event)


def _session(R: FactSet, event: Id) -> Id | None:
    return _id(_fact(R, event, _A.SESSION))


def other_date(R: FactSet, event: Id) -> bool:
    """4.4's established_other_date: the effective date relation supported earlier_date or later_date."""
    found = _fact(R, event, _A.DATE_RELATION)
    return found.result is Result.SUPPORTED and isinstance(found.value, DateRelation) and found.value in _OTHER_DATES


def other_performer(R: FactSet, event: Id) -> bool:
    """4.4's established_other_performer: the effective performer supported other_clinician or other_facility."""
    found = _fact(R, event, _A.PERFORMER)
    return (found.result is Result.SUPPORTED and isinstance(found.value, Performer)
            and found.value in _OTHER_PERFORMERS)


def positive(R: FactSet, event: Id) -> bool:
    """4.4's positive candidate - possibly today's act, in doubt: possibly performed or possibly attempted_not_completed
    (a status not established leaves every status possible: a doubted act is positive [R:HO-1]), and neither of another
    date nor of another performer established. The same-day rule (4.7, step 4d) reads it."""
    status = _fact(R, event, _A.STATUS)
    return (any(facts_.possibly(status, value) for value in _POSITIVE)
            and not other_date(R, event) and not other_performer(R, event))


def _covers_group(kind: Kind, group: Sequence[Kind]) -> bool:
    return any(catalogue.covers(kind, wanted) for wanted in group)


def _bleeding_group(group: Sequence[Kind]) -> bool:
    return _covers_group(Kind.BLEEDING_CONTROL, group)


def _claims_hemostasis(purpose: Fact) -> bool:
    """A purpose fact that claims hemostasis without establishing it: not established, hemostasis its claimed value or
    one of its options (a doubt's reading, a contradicted side, an unrejected control). DECISIONS D324 (1) (round r3's
    integration int5, the fold lane's Q-F3): never a purpose an established answer ruled hemostasis out of
    (facts.ruled_out: "This act was not done for hemostasis.") - the answer removes that value, and only it."""
    return (not facts_.established(purpose) and Purpose.HEMOSTASIS not in facts_.ruled_out(purpose)
            and (purpose.value is Purpose.HEMOSTASIS or Purpose.HEMOSTASIS in purpose.options))


def candidate_kinds(R: FactSet, group: Sequence[Kind], event: Id) -> frozenset[Kind]:
    """The kinds through which ``event`` is a candidate of ``group`` (4.4): each kind it may be (facts.possibly, the
    candidate arm of 4.2) that covers a kind of the group - a clip or an injection read through catalogue.catalogue_kind
    by possibly (D157's doubt arm, step 1e's hand-off R5): the bleeding control it may be when its purpose is possibly
    hemostasis (silent included) and the group holds the bleeding control; itself, unless its purpose is supported
    hemostasis, which makes it a bleeding control only (v1's catalogue kind)."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    purpose = _fact(R, event, _A.PURPOSE)
    found: set[Kind] = set()
    for kind in kinds:
        if kind in catalogue.HEMOSTASIS_KINDS:
            if _bleeding_group(group) and facts_.possibly(purpose, Purpose.HEMOSTASIS):
                found.add(Kind.BLEEDING_CONTROL)
            if not facts_.holds(purpose, Purpose.HEMOSTASIS) and _covers_group(kind, group):
                found.add(kind)
        elif _covers_group(kind, group):
            found.add(kind)
    return frozenset(found)


def is_candidate(R: FactSet, group: Sequence[Kind], event: Id) -> bool:
    """4.4's candidate: possibly of a kind of the group (candidate_kinds) and not denied performed."""
    return (not facts_.denied(_fact(R, event, _A.STATUS), Status.PERFORMED)
            and bool(candidate_kinds(R, group, event)))


def candidates(R: FactSet, group: Sequence[Kind]) -> tuple[Id, ...]:
    """Every candidate of ``group`` in pass 1's order."""
    return tuple(event for event in R.events if is_candidate(R, group, event))


# --- 3.2.6 rule 3's synthetic doubted acts (DECISIONS D216) -------------------------------------------------------------


def synthetic_acts(R: FactSet) -> tuple[UnlistedStatement, ...]:
    """Every kept unlisted ACT, in FactSet.unlisted's order: 3.2.6 rule 3's synthetic doubted act, which D216 makes a
    possibly performed act of its kind in its session for every rule whose condition is the absence of one (it never
    supports, excludes or releases anything: 3.2.6). An unlisted denial or doubt is no act (condition 5 and rule 4 read
    those); the absence conditions read the synthetic acts and the unlisted doubts alike (``synthetic_possible``)."""
    # round r3 (DESIGN-v2 b.7; PROTOTYPE): an entry a Q-ABSORB answer absorbed re-tells a described act - no synthetic act
    return tuple(entry for index, entry in enumerate(R.unlisted) if entry.what is UnlistedWhat.ACT
                 and index not in R.absorbed)


def synthetic_possible(R: FactSet) -> tuple[UnlistedStatement, ...]:
    """Every kept unlisted entry an absence condition reads as a possibly performed act (D216; refute-r4a-r1 F1), in
    FactSet.unlisted's order: an ACT (3.2.6 rule 3's synthetic doubted act) and a DOUBT - a doubt about whether an act
    was done leaves the act possibly performed (4.2 [R:HO-1]: a doubt is never an absence), so the weaker statement
    never releases what the stated act holds ("It is unclear whether the old biliary stent was removed." beside the
    filed placement holds 43274, as "The existing biliary stent was removed." does). A DENIAL is a statement that the
    act was not done: 3.2.6 rule 4 pairs it, and condition 5 reads it; no absence condition reads it as an act (the
    step's NOTES, question Q1)."""
    # round r3 (DESIGN-v2 b.7; PROTOTYPE): an absorbed entry is no possibly performed act (its rule-4 pairs stay)
    return tuple(entry for index, entry in enumerate(R.unlisted) if entry.what in _POSSIBLY_PERFORMED
                 and index not in R.absorbed)


def synthetic_kinds(entry: UnlistedStatement) -> frozenset[Kind]:
    """The kinds a synthetic act may be (D216, fail-closed): every kind when the entry names none (an unknown kind
    leaves every kind possible, 4.2), else every kind its kind covers (catalogue.covers: itself, an umbrella's members, a
    tattoo and an injection as one act) - as condition 5 and 3.2.6 rule 4 read an unlisted entry's kind."""
    if entry.kind is None:
        return frozenset(Kind)
    named = entry.kind
    return frozenset(kind for kind in Kind if catalogue.covers(named, kind))


def synthetic_in(R: FactSet, entry: UnlistedStatement, session: Id | None) -> bool:
    """Whether the synthetic act ``entry`` may be in ``session`` (D216: "in its session"): its session card is
    ``session``, or it names none (3.2.6 rule 4's "with no session, of every session"), or it names one the FactSet does
    not hold (4.11: a missing identifier manufactures neither a match nor a non-match); and in any session when
    ``session`` is None (the act it is read beside has no supported session)."""
    return (session is None or entry.session is None or entry.session == session
            or entry.session not in R.sessions)


def _synthetic_doubt(entry: UnlistedStatement, subject: Id | None) -> HeldFact:
    """A synthetic act's witness (3.2.6 rule 3, D216): a doubt about an act no card describes - performed_status at RANK 2
    (4.8: a doubt), a question, cause unlisted, about no single fact (D189: attribute and result None), quoting its own
    units; ``subject`` is the session the rule read it in (None when that is not known) - the shape step 4c's synthetic
    examination act takes (classes._unlisted_doubt)."""
    return _held(rq.fact_key(_DOUBT.fact), _DOUBT.rank, _Q, None, subject, None, questions.UNLISTED,
                 tuple(sorted(set(entry.units))))


# --- witnesses (4.4 HeldFact, D189) ------------------------------------------------------------------------------------


def _held(fact: str, rank: rq.Rank | None, kind: ItemKind, attribute: Attribute | None, subject: Id | None,
          found: Fact | None, cause: str, spans: tuple[Span, ...]) -> HeldFact:
    """A held fact: its result is the fact's (D189; None for a hold about no single fact), its reason the fact's first
    when the fact is not established."""
    result = found.result if found is not None else None
    reason = found.reasons[0] if found is not None and found.reasons and not facts_.established(found) else None
    return HeldFact(fact=fact, attribute=attribute, subject=subject, result=result, kind=kind, cause=cause,
                    reason=reason, spans=spans, rank=rank.value if rank is not None else None)


def _conflict_kind(R: FactSet, event: Id | None, group: Sequence[Kind]) -> Kind:
    """The kind a conflict over ``event`` is keyed by (conflict:<kind>): facts.established_kind - the catalogue kind of
    its SUPPORTED kind with its supported purpose; an act whose kind is not SUPPORTED (negated, doubted, unresolved,
    contradicted, silent) or is other is Kind.OTHER, so its conflict is keyed conflict:other, the one label its item names
    it by (DECISIONS D287, build list B9: the one derivation questions.act_kind, coverage's and classes' keys read;
    D267, r4a-2 Q1 QK option (b): "the snare removal" beside "another act" for one act is gone); no act, the code's
    group's first kind (Kind.OTHER for none)."""
    if event is not None:
        return facts_.established_kind(R, event)
    return group[0] if group else Kind.OTHER


def _open(found: Fact, ask: rq.Item, attribute: Attribute, subject: Id, act: Id | None, group: Sequence[Kind],
          R: FactSet, cause: str | None = None) -> HeldFact:
    """The witness of a requirement whose fact is not what it needs (U): a contradicted fact asks rank 1
    (conflict:<the act's kind>; a session's fact is its examination's, which the item names - D225 P7); a doubt pass 1
    reported on a status asks rank 2; any other the row's ``ask`` - its cause the fact's reading
    (questions.cause_of), or ``cause`` for an established fact a coding rule doubts."""
    spans = _quoted(found, R, act)
    if found.result is Result.CONTRADICTED:
        kind = Kind.EXAMINATION if subject.family is IdFamily.SESSION else _conflict_kind(R, act, group)
        return _held(rq.fact_key(rq.FactKey.CONFLICT, kind), rq.Rank.CONFLICT, _Q, attribute, subject, found,
                     questions.cause_of(found), spans)
    if attribute is _A.STATUS and _doubted(found):
        return _held(rq.fact_key(_DOUBT.fact), _DOUBT.rank, _Q, attribute, subject, found, questions.cause_of(found),
                     spans)
    reading = cause if cause is not None and facts_.established(found) else questions.cause_of(found)
    return _held(rq.fact_key(ask.fact), ask.rank, _Q, attribute, subject, found, reading, spans)


def _fails(item: rq.Item, explained: bool, attribute: Attribute | None, subject: Id | None, found: Fact | None,
           rule: questions.Rule, R: FactSet, act: Id | None) -> HeldFact:
    """The witness of an established fact failing a coding rule (F): an EXPLANATION where the rule words one, else the
    row's question (the design gives the row no explanation: the requirement asked again, fail-closed)."""
    return _held(rq.fact_key(item.fact), item.rank, _E if explained else _Q, attribute, subject, found,
                 questions.coding_rule(rule), _quoted(found, R, act))


def _row(requirement: rq.Requirement | Tag, witnesses: Sequence[HeldFact], failed: bool = False) -> Row:
    if not witnesses:
        return Row(requirement, Truth.T)
    return Row(requirement, Truth.F if failed else Truth.U, tuple(witnesses))


# --- SUPPORT, rows 1-8 (4.3) --------------------------------------------------------------------------------------------


def _row_kind(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 1 (module docstring). A digital examination (``_digital``: FINAL 5.6 E13, a device CLAIMING manual) is no
    session's examination, so it never supports an examination group - the group of every code that accounts for the
    session's examination (catalogue.requirements: (examination,)) - whatever its other rows (``_digital_row``;
    refute-r4a-r1 P1 of round w8r)."""
    if Kind.EXAMINATION in group and _digital(R, event):
        return _digital_row(group, R, event)
    found = _fact(R, event, _A.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, Kind):
        kind = found.value
        if kind in catalogue.UMBRELLAS:  # h5: a positive umbrella never supports a method-specific code
            return _row(rq.Requirement.SUP_KIND, [_open(found, _METHOD, _A.KIND, event, event, group, R,
                                                        questions.coding_rule(_Rule.UMBRELLA))])
        purpose = _fact(R, event, _A.PURPOSE)
        if kind in catalogue.HEMOSTASIS_KINDS and _covers_group(kind, group):
            # read as itself (an injection code): a purpose supported hemostasis makes it a bleeding control instead,
            # and one that claims hemostasis without establishing it leaves that open (catalogue.catalogue_kind)
            if facts_.holds(purpose, Purpose.HEMOSTASIS):
                return _row(rq.Requirement.SUP_KIND, [_fails(_STATUS, False, _A.PURPOSE, event, purpose,
                                                             _Rule.NOT_DOCUMENTED, R, event)], failed=True)
            if _claims_hemostasis(purpose):
                return _row(rq.Requirement.SUP_KIND, [_open(purpose, _STATUS, _A.PURPOSE, event, event, group, R)])
            return _row(rq.Requirement.SUP_KIND, [])
        if _covers_group(kind, group):
            return _row(rq.Requirement.SUP_KIND, [])
        if kind in catalogue.HEMOSTASIS_KINDS and _bleeding_group(group):
            if facts_.holds(purpose, Purpose.HEMOSTASIS):
                return _row(rq.Requirement.SUP_KIND, [])
            return _row(rq.Requirement.SUP_KIND, [_open(purpose, _STATUS, _A.PURPOSE, event, event, group, R)],
                        failed=facts_.established(purpose))
        return _row(rq.Requirement.SUP_KIND, [_fails(_STATUS, False, _A.KIND, event, found, _Rule.NOT_DOCUMENTED, R,
                                                     event)], failed=True)
    return _row(rq.Requirement.SUP_KIND, [_open(found, _STATUS, _A.KIND, event, event, group, R)],
                failed=facts_.established(found))


def _digital_row(group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """Row 1 of a digital examination for an examination group (FINAL 5.6 E13; DECISIONS D253: "A fact E13 says never
    counts can never release a code"; v1's events.supports, D100: "a digital rectal examination read as the family's
    examination is no session and supports no base code"): never T, so the digital rectal examination filed as the
    colonoscopy's examination never supports 45378 (nor the flexible sigmoidoscopy's 45330) - the code is held as it is
    without the DRE line (refute-r4a-r1 P1 of round w8r: READY on the DRE alone). Its device established manual is the
    established failure, its witness the not-documented question (performed_status, rank 4, coding_rule:not_documented:
    the code-level sentence the same document without the DRE line gets, as a kind established as another is read);
    a device that claims manual without establishing it (unresolved, doubted, contradicted: QE13 option (a)) is the
    device's own question at the status row (``_open``: a contradicted device its conflict). The event stays a
    candidate, so a positive one holds the code as before and 4.6's exclusion reads exactly what it read (9.4:
    weakening never drops a candidate, never turns a digital examination into another, and so never releases or
    excludes)."""
    device = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if facts_.established(device):
        return _row(rq.Requirement.SUP_KIND, [_fails(_STATUS, False, _A.TECHNIQUE_DEVICE, event, device,
                                                     _Rule.NOT_DOCUMENTED, R, event)], failed=True)
    return _row(rq.Requirement.SUP_KIND, [_open(device, _STATUS, _A.TECHNIQUE_DEVICE, event, event, group, R)])


def _row_status(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 2 with ATT (module docstring)."""
    found = _fact(R, event, _A.STATUS)
    accepted = _POSITIVE if c.has(Tag.ATT) else frozenset({Status.PERFORMED})
    if found.result is Result.SUPPORTED and isinstance(found.value, Status):
        if found.value in accepted:
            return _row(rq.Requirement.SUP_STATUS, [])
        if found.value is Status.ATTEMPTED_NOT_COMPLETED:  # C-9: a hold, the 52/53 consideration (assess)
            return _row(rq.Requirement.SUP_STATUS, [_fails(_STATUS, True, _A.STATUS, event, found, _Rule.ATTEMPTED, R,
                                                           event)], failed=True)
        return _row(rq.Requirement.SUP_STATUS, [_fails(_STATUS, False, _A.STATUS, event, found, _Rule.NOT_DOCUMENTED,
                                                       R, event)], failed=True)
    if found.result is Result.NEGATED:
        return _row(rq.Requirement.SUP_STATUS, [_fails(_STATUS, False, _A.STATUS, event, found, _Rule.NOT_DOCUMENTED,
                                                       R, event)], failed=True)
    return _row(rq.Requirement.SUP_STATUS, [_open(found, _STATUS, _A.STATUS, event, event, group, R)])


def _row_value(requirement: rq.Requirement, attribute: Attribute, wanted: DateRelation | Performer,
               ask: rq.Item, rule: questions.Rule) -> Callable[[_Code, Sequence[Kind], FactSet, Id], Row]:
    """4.3 rows 3 and 4: the act's effective ``attribute`` supported ``wanted``; established otherwise, the row's
    question (no explanation is given for it); not established, its question."""
    def row(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
        found = _fact(R, event, attribute)
        if facts_.holds(found, wanted):
            return _row(requirement, [])
        if facts_.established(found):
            return _row(requirement, [_fails(ask, False, attribute, event, found, rule, R, event)], failed=True)
        return _row(requirement, [_open(found, ask, attribute, event, event, group, R)])
    return row


_row_date = _row_value(rq.Requirement.SUP_DATE, _A.DATE_RELATION, DateRelation.ON_DATE_OF_SERVICE, _TIME,
                       _Rule.TIMING)
_row_performer = _row_value(rq.Requirement.SUP_PERFORMER, _A.PERFORMER, Performer.DOCUMENTING_TEAM, _PERFORMER,
                            _Rule.PERFORMER)


def _row_entry(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 5: the entry supported documenting_clinician; another owner supported is the another-entry explanation."""
    return _row(rq.Requirement.SUP_ENTRY, *_entry(R, event, event, group))


def _entry(R: FactSet, subject: Id, act: Id, group: Sequence[Kind]) -> tuple[list[HeldFact], bool]:
    found = _fact(R, subject, _A.ENTRY)
    if facts_.holds(found, Owner.DOCUMENTING_CLINICIAN):
        return [], False
    if found.result is Result.SUPPORTED and isinstance(found.value, Owner):
        return [_fails(_ENTRY, True, _A.ENTRY, subject, found, _Rule.ENTRY, R, subject)], True
    if found.result is Result.NEGATED:
        return [_fails(_ENTRY, False, _A.ENTRY, subject, found, _Rule.ENTRY, R, subject)], True
    return [_open(found, _ENTRY, _A.ENTRY, subject, act, group, R)], False


def _row_session(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 6: route (a), the session and its kind; route (b), the act's places in the code's regions."""
    if c.link.route is catalogue.LinkRoute.UNRECONCILED:
        return _row(rq.Requirement.SUP_SESSION, *_regions(c, group, R, event))
    found = _fact(R, event, _A.SESSION)
    session = _id(found)
    if session is None:
        return _row(rq.Requirement.SUP_SESSION, [_open(found, _PROCEDURE, _A.SESSION, event, event, group, R)])
    kind = _fact(R, session, _A.KIND)
    if facts_.holds(kind, c.link.family):
        return _row(rq.Requirement.SUP_SESSION, [])
    if facts_.established(kind):
        return _row(rq.Requirement.SUP_SESSION, [_fails(_PROCEDURE, False, _A.KIND, session, kind, _Rule.SESSION, R,
                                                        event)], failed=True)
    return _row(rq.Requirement.SUP_SESSION, [_open(kind, _PROCEDURE, _A.KIND, session, event, group, R)])


def _regions(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> tuple[list[HeldFact], bool]:
    """Route (b)'s row 6: every place of the act established, its supported places in the code's regions, at least
    one."""
    places = _members(R, event, _A.TARGET_PLACES)
    open_ = [member for member in places if not facts_.established(member)]
    if open_:
        return [_open(open_[0], _ACT_TARGET, _A.TARGET_PLACES, event, event, group, R)], False
    supported = [member.value for member in places if member.result is Result.SUPPORTED
                 and isinstance(member.value, Landmark)]
    if supported and all(anatomy.in_regions(place, c.link.regions) for place in supported):
        return [], False
    if supported and any(place not in _UNPLACED and not anatomy.in_regions(place, c.link.regions)
                         for place in supported):
        return [_fails(_ACT_TARGET, False, _A.TARGET_PLACES, event, places[0], _Rule.SESSION, R, event)], True
    return [_open(places[0] if places else facts_.SILENT, _ACT_TARGET, _A.TARGET_PLACES, event, event, group, R)], False


def _may_be_in(R: FactSet, event: Id, session: Id) -> bool:
    """Whether ``event`` may be in ``session`` by its own session fact: facts.possibly's (supported: that session; not
    established: the claimed one, a doubt's readings, a contradiction's sides, an unrejected control's, every one for
    an empty slot; negated: none), and every session when the fact names an id the FactSet does not hold, as its value
    or a reading (4.11: a missing identifier manufactures neither a match nor a non-match; step 4b's
    coverage.sessions_of reads it the same way). Monotone: a weakened fact never leaves fewer sessions open."""
    found = _fact(R, event, _A.SESSION)
    named = (found.value,) if facts_.established(found) else (found.value, *found.options)
    if found.result is not Result.NEGATED and any(isinstance(value, Id) and value not in R.sessions
                                                  for value in named):
        return True
    return facts_.possibly(found, session)


def _admits_examination(R: FactSet, session: Id) -> bool:
    """Whether ``session`` may hold an examination: its kind not established, or a family whose kinds hold the
    examination (FAMILY_KINDS, the table K2 reads: DECISIONS D191). An office visit's session holds none."""
    kind = _fact(R, session, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, SessionKind):
        return True
    return Kind.EXAMINATION in facts_.family_kinds(kind.value)


def is_examination_of(R: FactSet, event: Id, session: Id) -> bool:
    """``event`` established as ``session``'s examination by its own facts: kind supported examination, session
    supported ``session``."""
    return (facts_.holds(_fact(R, event, _A.KIND), Kind.EXAMINATION)
            and facts_.holds(_fact(R, event, _A.SESSION), session))


def another_occasion(R: FactSet, event: Id) -> bool:
    """``event`` established as of another occasion - a plan (status supported planned), another date (4.4's
    established_other_date) or another performer (established_other_performer): the statements K1 and 4.6 condition 3
    read as carrying no breadth. A denial (status negated) is none."""
    return facts_.holds(_fact(R, event, _A.STATUS), Status.PLANNED) or other_date(R, event) or other_performer(R, event)


def examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The events that may be ``session``'s examination (4.3 row 7; step 1f's hand-off R9(d): by their own kind and
    session facts, never session.examination), in pass 1's order, when its family admits an examination
    (``_admits_examination``): every event established as its examination (``is_examination_of``), and every event whose
    kind is possibly the examination and which may be in it (``_may_be_in``: an empty slot included). A session whose
    family holds no examination (an office visit's, a feeding-tube procedure's) has none, whatever an event's tie: the
    established arm is gated by the family too (refute-4a-r2 P3), so weakening a tie never drops an examination the
    established tie read (P-MONO)."""
    if not _admits_examination(R, session):
        return ()
    return tuple(event for event in R.events
                 if is_examination_of(R, event, session)
                 or (facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION) and _may_be_in(R, event, session)))


def synthetic_examinations(R: FactSet, session: Id) -> tuple[UnlistedStatement, ...]:
    """Row 7's synthetic examination acts of ``session`` (D216; 3.2.6 rule 3), in FactSet.unlisted's order, when its
    family admits an examination: every kept unlisted act or doubt (``synthetic_possible``: refute-r4a-r1 F1) that may
    be an examination (``synthetic_kinds``: its kind examination, or none named) and may be in it (``synthetic_in``).
    Each is a possibly performed examination of the session that is never established done (its status is the doubt,
    and it has no date, performer or entry), so it holds the session's codes as a filed examination in doubt does."""
    if not _admits_examination(R, session):
        return ()
    return tuple(entry for entry in synthetic_possible(R)
                 if Kind.EXAMINATION in synthetic_kinds(entry) and synthetic_in(R, entry, session))


def _digital(R: FactSet, event: Id) -> bool:
    """FINAL 5.6 E13's digital examination (DECISIONS D69; D227: combination.session_done, the reference derivation of
    "a session is done", excepts it - "a digital examination ... is no session"; D253, QE13 option (a)): an event whose
    device CLAIMS manual - supported manual, or, not established, manual its claimed value or one of its readings
    (facts.possibly_written over a device that is not silent) - questions.digital_examination, the one derivation the
    item's examination words read too. Read so that 9.4's weakenings never turn a digital examination into the session's
    own (each keeps the claimed value: an established manual device weakened still claims it), so the session it was
    told in stays act-only and its digital examination never its done one (P-MONO; refute-r4a-r1 P1, refute-r4a-r2 A2).
    A silent device (the endoscopic examination's usual filing: "The colonoscope was advanced to the cecum."), one
    established as another device, and manual negated claim none."""
    return questions.digital_examination(R, event)


def act_only(R: FactSet, session: Id) -> bool:
    """4.3 row 7's act-only session ("its examination, when it has one, passes 2-5 (an act-only session: the act
    itself)"): no event is established as ``session``'s examination (``is_examination_of``: kind supported
    examination, session supported ``session``), a digital examination (``_digital``: FINAL 5.6 E13) excepted - the
    reading of combination.session_done's act-only arm (DECISIONS D227's one derivation, whose ``_examinations`` except
    the digital examination; refute-r4a-r1 P1: a colonoscopy told through its snare beside a digital rectal examination
    filed as its examination has no examination, so pass 2's unlisted examination holds 45385, never READY); row 7's
    ``done`` excepts it the same way (D253). Row 7 reads a synthetic examination act only here (D232). Read per
    session: another session's examination never makes
    this one non-act-only (refute-r4a-r1 P5). Monotone under 9.4: weakening a fact never establishes an examination
    and never drops a device's manual claim, so a weakened FactSet is act-only wherever the stronger one was."""
    return not any(is_examination_of(R, event, session) and not _digital(R, event) for event in R.events)


def _done_rows(R: FactSet, exam: Id, exam_group: Sequence[Kind]) -> tuple[list[HeldFact], bool]:
    """Rows 2-5 on an examination (4.3 row 7): the witnesses of every row that is not T (an examination begun counts as
    done, v1's done), and whether one is an established failure."""
    witnesses: list[HeldFact] = []
    failed = False
    status = _fact(R, exam, _A.STATUS)
    if not (status.result is Result.SUPPORTED and isinstance(status.value, Status) and status.value in _POSITIVE):
        if facts_.established(status):
            witnesses.append(_fails(_STATUS, False, _A.STATUS, exam, status, _Rule.EXAMINATION, R, exam))
            failed = True
        else:
            witnesses.append(_open(status, _STATUS, _A.STATUS, exam, exam, exam_group, R))
    for attribute, wanted, ask in ((_A.DATE_RELATION, DateRelation.ON_DATE_OF_SERVICE, _TIME),
                                   (_A.PERFORMER, Performer.DOCUMENTING_TEAM, _PERFORMER)):
        value = _fact(R, exam, attribute)
        if facts_.holds(value, wanted):
            continue
        if facts_.established(value):
            witnesses.append(_fails(ask, False, attribute, exam, value, _Rule.EXAMINATION, R, exam))
            failed = True
        else:
            witnesses.append(_open(value, ask, attribute, exam, exam, exam_group, R))
    held, entry_failed = _entry(R, exam, exam, exam_group)
    witnesses.extend(held)
    return witnesses, failed or entry_failed


def _row_done(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 7: every event that may be the session's examination (``examinations``) passes rows 2-5 (an examination
    begun counts as done); a session with none is the act's own. The examination's facts alone are read (K2).
    - An event that passes rows 2-5 never makes a session not done, whichever session it is: it adds nothing.
    - When an event established as the session's examination passes rows 2-5 (the session's own done examination), an
      event established as of another occasion (``another_occasion``: a plan, another date, another performer) is no
      examination done on the date of service beside it, whatever its tie: it adds nothing. "Repeat colonoscopy in 3
      years." and "Colonoscopy in 2019 was normal.", each filed as an examination with its session slot empty, no
      longer hold every code of every session (the refutation's F1; 4.9 retires D31's "anything unresolved holds
      everything"). Read whatever the tie, so that weakening the tie never releases (P-MONO); without the session's
      own done examination such an event may be its only one, and holds. A digital examination (``_digital``: FINAL
      5.6 E13) is never the session's own done examination (DECISIONS D253, refute-r4a-r2 A2): beside a digital rectal
      examination filed as the colonoscopy's examination, "Colonoscopy in 2019 was normal." (or a planned repeat) filed
      in the session holds 45385 exactly as without the DRE line - so row 7's two readings of the session's examination,
      ``done`` and ``act_only``, agree with D227's session_done, and a fact E13 says never counts releases nothing.
    - An examination ESTABLISHED as a digital examination (pairing.established_digital: kind supported examination,
      device supported manual) is read by no part of row 7 (DECISIONS D280.1, build list B1): it is neither the
      session's done examination nor one whose rows 2-5 must pass, so "The digital rectal examination was deferred."
      filed as the colonoscopy's examination beside the colonoscope's done examination leaves 45385 READY, as the
      document without the DRE line. One whose device only CLAIMS manual (unresolved, doubted, contradicted, an
      overfilled slot) is read below and keeps QD2's hold (D280.3, D271); a 9.4 weakening never creates a supported
      device, so this never releases under a weakening.
    - Otherwise each event's witnesses are recorded: F when it is established as the session's examination and an
      established fact fails rows 2-5, else U, with the witnesses of its kind and session when not established.
    - In an act-only session (``act_only``: no event established as its examination, a digital examination excepted:
      FINAL 5.6 E13, refute-r4a-r1 P1), each synthetic examination act of the session (``synthetic_examinations``;
      D216: a kept unlisted act or doubt that may be its examination, read as a possibly performed one) holds it, its
      doubt the witness (``_synthetic_doubt``, its subject the session): it is never done. Beside an examination established as the session's - done or not - a synthetic one adds nothing
      (D232: "row 7 reads it only in an act-only session"; one kept unlisted doubt of kind examination, carded to the
      colonoscopy or to no session, no longer holds 45385 beside the colonoscopy's done examination, nor 43239 beside
      the EGD's). The session's base code keeps 3.2.6 rule 3's base_included hold (step 4d's), and an unlisted doubt
      keeps 3.2.6 rule 4's pairing with the examination (row 8)."""
    found = _fact(R, event, _A.SESSION)
    session = _id(found)
    if session is None:
        return _row(rq.Requirement.SUP_SESSION_DONE, [_open(found, _PROCEDURE, _A.SESSION, event, event, group, R)])
    witnesses: list[HeldFact] = []
    failed = False
    exam_group = (Kind.EXAMINATION,)
    exams = examinations(R, session)
    rows = {exam: _done_rows(R, exam, exam_group) for exam in exams}
    # D253: the session's own done examination never a digital one (E13), as act_only reads it and D227's session_done
    done = any(is_examination_of(R, exam, session) and not rows[exam][0] and not _digital(R, exam) for exam in exams)
    for exam in exams:
        held, exam_failed = rows[exam]
        if not held or (done and another_occasion(R, exam)) or pairing.established_digital(R, exam):  # D280.1
            continue
        if is_examination_of(R, exam, session):
            failed = failed or exam_failed
        else:
            kind = _fact(R, exam, _A.KIND)
            if not facts_.holds(kind, Kind.EXAMINATION):
                witnesses.append(_open(kind, _STATUS, _A.KIND, exam, exam, exam_group, R))
            tied = _fact(R, exam, _A.SESSION)
            if not facts_.holds(tied, session):
                witnesses.append(_open(tied, _STATUS, _A.SESSION, exam, exam, exam_group, R))
        witnesses.extend(held)
    if act_only(R, session):  # D232: never beside an examination established as the session's
        witnesses.extend(_synthetic_doubt(entry, session) for entry in synthetic_examinations(R, session))
    return _row(rq.Requirement.SUP_SESSION_DONE, witnesses, failed)


def _row_clean(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3 row 8: every relation of a paired statement that is not INDEPENDENT (engine/pairing.py, 4.5) - its item at
    its rank, its cause relation:<type>; a CONTRADICTION keyed conflict:<the act's kind>, conflict:other for an act
    whose kind is not supported (DECISIONS D267: the act's one label), else the first kind through which the statement
    concerns it - and every unlisted denial or doubt pairing with the act (statement_scope, cause unlisted)."""
    witnesses: list[HeldFact] = []
    own = _conflict_kind(R, event, group)
    # DECISIONS D324 (8) (int5): the caller's reader of R, when it passed one - the same pairs, read once per Reader
    reader = c.reader if c.reader is not None and c.reader.R is R else None
    for pair in (reader.pairs(event) if reader is not None else pairing.pairs_of(R, event)):
        found = pairing.item(pair)
        cause = pairing.cause(pair)
        if found is None or cause is None:
            continue
        if found.fact is rq.FactKey.CONFLICT:  # D267: a conflict over an act no kind names is conflict:other
            named = own is Kind.OTHER or own in pair.kinds
            kind = own if named else min(pair.kinds, key=list(Kind).index, default=own)
            key = rq.fact_key(rq.FactKey.CONFLICT, kind)
        else:
            key = rq.fact_key(found.fact)
        attribute = _ROW_ATTRIBUTE[pair.row] if pair.relation is pairing.Relation.UNRESOLVED and pair.row else _A.STATUS
        witnesses.append(_held(key, found.rank, _Q, attribute, event, None, cause, pair.spans))
    for unlisted in (reader.unlisted_pairs(event) if reader is not None  # what it asks is the pairing table's
                     else pairing.unlisted_pairs(R, event)):  # (pairing.item; D228 DQ3)
        asked = pairing.item(unlisted) or _SCOPE
        witnesses.append(_held(rq.fact_key(asked.fact), asked.rank, _Q, None, event, None, questions.UNLISTED,
                               unlisted.spans))
    return _row(rq.Requirement.SUP_CLEAN, witnesses)


def _row_encounter(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """4.3's E/M row: the visit's session encounter supported this_encounter (event_time)."""
    found = _fact(R, event, _A.SESSION)
    session = _id(found)
    if session is None:
        return _row(rq.Requirement.V_THIS_ENCOUNTER, [_open(found, _TIME, _A.SESSION, event, event, group, R)])
    encounter = _fact(R, session, _A.ENCOUNTER)
    if facts_.holds(encounter, EncounterRelation.THIS_ENCOUNTER):
        return _row(rq.Requirement.V_THIS_ENCOUNTER, [])
    if facts_.established(encounter):
        return _row(rq.Requirement.V_THIS_ENCOUNTER, [_fails(_TIME, False, _A.ENCOUNTER, session, encounter,
                                                             _Rule.ENCOUNTER, R, event)], failed=True)
    return _row(rq.Requirement.V_THIS_ENCOUNTER, [_open(encounter, _TIME, _A.ENCOUNTER, session, event, group, R)])


_SUPPORT_ROWS: tuple[Callable[[_Code, Sequence[Kind], FactSet, Id], Row], ...] = (
    _row_kind, _row_status, _row_date, _row_performer, _row_entry, _row_session, _row_done, _row_clean)
_EM_TEMPLATES: frozenset[Template] = frozenset({Template.EM, Template.EM_ADDON})


# --- the code-specific rows (4.3's second table) ------------------------------------------------------------------------


def _row_technique(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """TECH: the act's device supported in the code's technique class; another class is the another-technique
    explanation; a device of no class, a denied one or one not established is the technique question."""
    required = c.spec.row.technique if c.spec.row is not None else None
    found = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if found.result is Result.SUPPORTED and isinstance(found.value, Device):
        named = catalogue.technique_class(found.value)
        if named is required:
            return _row(Tag.TECH, [])
        if named is not None:
            return _row(Tag.TECH, [_fails(_TECHNIQUE, True, _A.TECHNIQUE_DEVICE, event, found, _Rule.TECHNIQUE, R,
                                          event)], failed=True)
    return _row(Tag.TECH, [_open(found, _TECHNIQUE, _A.TECHNIQUE_DEVICE, event, event, group, R,
                                 questions.coding_rule(_Rule.TECHNIQUE))])


# The witness SITE rests on when an entry of the act's target lesion's finding has no established places, or the finding
# holds an id the FactSet does not hold (DECISIONS D297 ENGB-1; facts.finding_places' ``unknown``): nothing established
# says where that part of the lesion lies - unknown (reading_unknown), asked as the lesion's places (_site_attribute).
_FINDING_UNKNOWN = Fact(result=Result.UNKNOWN, value=None, state=None, options=(), reasons=(Reason.SILENT,), spans=())


def _places_of(R: FactSet, event: Id) -> tuple[tuple[Fact, ...], Fact | None]:
    """SITE's places (D29): the act's place facts and its lesion's (when its target lesion is supported) - the places of
    every entry of that lesion's FINDING (DECISIONS D297 ENGB-1, facts.finding_places: every lesion entry a same_as
    member in any state may join to it, directly or through other entries, either direction; the entry the act names
    first); and the first fact among them, or its lesion fact, that is not established (None when every one is) - else
    ``_FINDING_UNKNOWN`` when an entry of the finding has no established places or the finding holds an id the FactSet
    does not hold: the row held and open, never T and never F. A wider finding only adds places or opens the row, so
    same_as only holds here (3.2.3's UNCONTROLLED; requirements' (lesion, same_as) stays on the hold path)."""
    places = list(_members(R, event, _A.TARGET_PLACES))
    lesion = _fact(R, event, _A.TARGET_LESION)
    open_: Fact | None = None if facts_.established(lesion) or facts_.silent(lesion) else lesion
    lesion_id = _id(lesion)
    unknown = False
    if lesion_id is not None:
        found = facts_.finding_places(R, lesion_id)
        places += found.members
        unknown = found.unknown is not None
    for member in places:
        if open_ is None and not facts_.established(member):
            open_ = member
    if open_ is None and unknown:
        open_ = _FINDING_UNKNOWN
    return tuple(places), open_


def _site_attribute(R: FactSet, event: Id, found: Fact) -> Attribute:
    """The attribute a SITE witness rests on, so its held fact names the fact that is actually unknown (D225 P7;
    refute-r4a-r1 F4: a contradicted target lesion is no conflict about where the act was done): the act's target
    lesion, one of the act's own places (target.places; and an empty place list, read as SILENT), or one of its
    lesion's places (places: a member of any entry of the lesion's finding, and ``_FINDING_UNKNOWN``)."""
    if found is _FINDING_UNKNOWN:
        return _A.PLACES
    if found is facts_.SILENT or any(found is member for member in _members(R, event, _A.TARGET_PLACES)):
        return _A.TARGET_PLACES
    if found is _fact(R, event, _A.TARGET_LESION):
        return _A.TARGET_LESION
    return _A.PLACES


def _row_site(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """SITE (D29; module docstring)."""
    site = c.spec.row.site if c.spec.row is not None else None
    if site is None:
        return _row(Tag.SITE, [])
    places, open_ = _places_of(R, event)
    if open_ is not None:
        return _row(Tag.SITE, [_open(open_, _ACT_TARGET, _site_attribute(R, event, open_), event, event, group, R)])
    supported = [member.value for member in places if member.result is Result.SUPPORTED
                 and isinstance(member.value, Landmark)]
    within = catalogue.SITE_CLASSES[site]
    if supported and all(place in within for place in supported):
        return _row(Tag.SITE, [])
    if supported and all(place not in within and place not in _UNPLACED for place in supported):
        return _row(Tag.SITE, [_fails(_ACT_TARGET, True, _site_attribute(R, event, places[0]), event, places[0],
                                      _Rule.SITE, R, event)], failed=True)
    first = places[0] if places else facts_.SILENT
    return _row(Tag.SITE, [_open(first, _ACT_TARGET, _site_attribute(R, event, first), event, event, group, R,
                                 questions.coding_rule(_Rule.SITE))])


def _site_fit(c: _Code, group: Sequence[Kind], R: FactSet, found: Sequence[Id]) -> list[Id]:
    """D240 (D29's installed reading, "A verified target outside the class does not support"): a group's supporting acts
    as the code's rows read them. For a code with a SITE row, when one of them is established within the site class
    (its SITE row T), those established outside it (F: every supported place outside the class, none surgically made
    or unplaced) are no supporting acts - they leave E* and no code row reads them. Every other act stays: one whose
    site is not established (U) is read and asks which structure was dilated (4.3's SITE row; the step's NOTES, question
    QB), and with no act established within the class every act stays, as before - the misfit explanation, or the site
    question. Monotone under 9.4: weakening never establishes a site, so it never drops an act the stronger FactSet
    kept (a T act weakened to U is still read; an F act weakened to U is read again)."""
    site = c.spec.row.site if c.spec.row is not None else None
    if site is None or len(found) < 2:
        return list(found)
    truths = {event: _row_site(c, group, R, event).truth for event in found}
    if not any(truth is Truth.T for truth in truths.values()):
        return list(found)
    return [event for event in found if truths[event] is not Truth.F]


def _row_structure(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """STRUCT:pfc (43240): the structure supported pancreatic_fluid_collection and no supported place biliary or hepatic
    (every place established); another structure, or a place set apart, is the another-structure explanation."""
    found = _fact(R, event, _A.TARGET_STRUCTURE)
    places = _members(R, event, _A.TARGET_PLACES)
    supported = [member.value for member in places if member.result is Result.SUPPORTED
                 and isinstance(member.value, Landmark)]
    apart = any(anatomy.in_regions(place, catalogue.DEFINING_TARGET_APART) for place in supported)
    open_place = next((member for member in places if not facts_.established(member)), None)
    if facts_.holds(found, Structure.PANCREATIC_FLUID_COLLECTION):
        if apart:
            return _row(Tag.STRUCT_PFC, [_fails(_TARGET, True, _A.TARGET_PLACES, event, places[0], _Rule.STRUCTURE, R,
                                                event)], failed=True)
        if open_place is None:
            return _row(Tag.STRUCT_PFC, [])
        return _row(Tag.STRUCT_PFC, [_open(open_place, _TARGET, _A.TARGET_PLACES, event, event, group, R,
                                           questions.coding_rule(_Rule.STRUCTURE))])
    if facts_.established(found):
        return _row(Tag.STRUCT_PFC, [_fails(_TARGET, bool(supported), _A.TARGET_STRUCTURE, event, found,
                                            _Rule.STRUCTURE, R, event)], failed=True)
    return _row(Tag.STRUCT_PFC, [_open(found, _TARGET, _A.TARGET_STRUCTURE, event, event, group, R,
                                       questions.coding_rule(_Rule.STRUCTURE))])


def _row_route(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """ROUTE (43253): the route supported eus_transmural; submucosal is the wall injection's explanation; another
    established route, or none, the route question."""
    found = _fact(R, event, _A.TECHNIQUE_ROUTE)
    if facts_.holds(found, Route.EUS_TRANSMURAL):
        return _row(Tag.ROUTE, [])
    if facts_.holds(found, Route.SUBMUCOSAL):
        return _row(Tag.ROUTE, [_fails(_TECHNIQUE, True, _A.TECHNIQUE_ROUTE, event, found, _Rule.ROUTE, R, event)],
                    failed=True)
    if facts_.established(found):
        return _row(Tag.ROUTE, [_fails(_TECHNIQUE, False, _A.TECHNIQUE_ROUTE, event, found, _Rule.ROUTE, R, event)],
                    failed=True)
    return _row(Tag.ROUTE, [_open(found, _TECHNIQUE, _A.TECHNIQUE_ROUTE, event, event, group, R,
                                  questions.coding_rule(_Rule.ROUTE))])


def _no_session(requirement: Tag, R: FactSet, event: Id, group: Sequence[Kind]) -> Row:
    found = _fact(R, event, _A.SESSION)
    return _row(requirement, [_open(found, _PROCEDURE, _A.SESSION, event, event, group, R)])


def _row_tract(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """TRACT (D171(2)): the session's tract supported the code's; another supported tract is the another-tract
    explanation. D226: an EUS session filed pancreatobiliary (1b's tract definition: an EUS of the pancreas or the bile
    duct from the stomach or the duodenum) fits every upper EUS code - the endoscope's route is the upper tract -
    whenever the session may be an EUS (its kind's own question is SUPPORT row 6's); the lower EUS codes still need
    lower, and STATIONS and LIMITED are unchanged."""
    required = c.spec.row.tract if c.spec.row is not None else None
    session = _session(R, event)
    if session is None or required is None:
        return _no_session(Tag.TRACT, R, event, group)
    found = _fact(R, session, _A.TRACT)
    if facts_.holds(found, required):
        return _row(Tag.TRACT, [])
    if (required is Tract.UPPER and facts_.holds(found, Tract.PANCREATOBILIARY)
            and facts_.possibly(_fact(R, session, _A.KIND), SessionKind.EUS)):
        return _row(Tag.TRACT, [])
    if facts_.established(found):
        explained = found.result is Result.SUPPORTED
        return _row(Tag.TRACT, [_fails(_PROCEDURE, explained, _A.TRACT, session, found, _Rule.TRACT, R, event)],
                    failed=True)
    return _row(Tag.TRACT, [_open(found, _PROCEDURE, _A.TRACT, session, event, group, R)])


def _reached(R: FactSet, session: Id) -> tuple[tuple[Fact, ...], list[Extent]]:
    found = _members(R, session, _A.REACHED)
    return found, [member.value for member in found if member.result is Result.SUPPORTED
                   and isinstance(member.value, Extent)]


def _contradicted(found: Iterable[Fact]) -> Fact | None:
    return next((member for member in found if member.result is Result.CONTRADICTED), None)


def _own(member: Fact, reached: Sequence[Fact]) -> Attribute:
    """The attribute a STATIONS or LIMITED witness rests on: REACHED for one of the session's reached members, STATIONS
    for a station - so a held fact names the fact that is actually unknown (D225 P7; refute-r4a-r1 F4: a contradicted
    reach is no conflict about the stations)."""
    return _A.REACHED if any(member is point for point in reached) else _A.STATIONS


def _upper(member: Fact) -> bool:
    """A station member STATIONS and LIMITED read (4.3: "esophagus, stomach and duodenum"): its claimed value, or one of
    its readings or sides, an upper station. A member that can name no upper station (the jejunum in any state) is no
    station of either class: it holds nothing and decides nothing (refute-4a-r2 P4; the F5 repair's property)."""
    return member.value in catalogue.UPPER_STATIONS or any(option in catalogue.UPPER_STATIONS
                                                           for option in member.options)


def _row_stations(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """STATIONS (43242, 43259; [R:SC-B]): module docstring. Only the members that may name an upper station are read
    (``_upper``): the list's emptiness (the completeness claim's arm) is the whole list's."""
    session = _session(R, event)
    if session is None:
        return _no_session(Tag.STATIONS, R, event, group)
    listed = _members(R, session, _A.STATIONS)
    stations = tuple(member for member in listed if _upper(member))
    reached, points = _reached(R, session)
    conflict = _contradicted((*stations, *reached))
    if conflict is not None:
        return _row(Tag.STATIONS, [_open(conflict, _STATIONS, _own(conflict, reached), session, event, group, R)])
    denied = [member for member in stations if member.result is Result.NEGATED
              and member.value in catalogue.UPPER_STATIONS]
    if denied:
        return _row(Tag.STATIONS, [_fails(_STATIONS, True, _A.STATIONS, session, denied[0], _Rule.STATIONS, R,
                                          event)], failed=True)
    far = any(point in catalogue.FULL_REACH for point in points)
    examined = {member.value for member in stations if member.result is Result.SUPPORTED}
    if not listed:
        complete = R.completeness.get(session) is Result.SUPPORTED
        if complete and far:
            return _row(Tag.STATIONS, [])
    elif all(facts_.established(member) for member in stations) and far and all(
            station in examined for station in catalogue.UPPER_STATIONS):
        return _row(Tag.STATIONS, [])
    first = next((member for member in (*stations, *reached) if not facts_.established(member)), None)
    if first is None:
        return _row(Tag.STATIONS, [_held(rq.fact_key(_STATIONS.fact), _STATIONS.rank, _Q, _A.STATIONS, session,
                                         None, questions.coding_rule(_Rule.STATIONS), _anchor(R, event))])
    return _row(Tag.STATIONS, [_open(first, _STATIONS, _own(first, reached), session, event, group, R)])


def _row_limited(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """LIMITED (D28, D171(3); step 1f's hand-off #7): 43231 and 43232 need a reach short of the duodenum; 43237 and
    43238, whose profile includes the EGD (catalogue.includes_examination), a station negated or a reach short; all
    three stations examined is the class explanation. Only the members that may name an upper station are read
    (``_upper``), as STATIONS reads them."""
    session = _session(R, event)
    if session is None:
        return _no_session(Tag.LIMITED, R, event, group)
    stations = tuple(member for member in _members(R, session, _A.STATIONS) if _upper(member))
    reached, points = _reached(R, session)
    conflict = _contradicted((*stations, *reached))
    if conflict is not None:
        return _row(Tag.LIMITED, [_open(conflict, _STATIONS, _own(conflict, reached), session, event, group, R)])
    short = (bool(points) and all(facts_.established(member) for member in reached)
             and all(point in catalogue.SHORT_OF_DUODENUM for point in points))
    if catalogue.includes_examination(c.code, SessionKind.EGD):
        examined = {member.value for member in stations if member.result is Result.SUPPORTED}
        if all(station in examined for station in catalogue.UPPER_STATIONS):  # the class explanation, whatever else
            # its witness is an examined upper station (D189: the result it rests on), never a station negated
            # elsewhere (the jejunum) that happens to come first
            witness = next(member for member in stations if member.result is Result.SUPPORTED
                           and member.value in catalogue.UPPER_STATIONS)
            return _row(Tag.LIMITED, [_fails(_STATIONS, True, _A.STATIONS, session, witness, _Rule.LIMITED, R,
                                             event)], failed=True)
        if short or any(member.result is Result.NEGATED and member.value in catalogue.UPPER_STATIONS
                        for member in stations):
            return _row(Tag.LIMITED, [])
    else:
        if short:
            return _row(Tag.LIMITED, [])
        if any(point in catalogue.FULL_REACH for point in points):
            return _row(Tag.LIMITED, [_fails(_STATIONS, False, _A.REACHED, session, reached[0], _Rule.LIMITED, R,
                                             event)], failed=True)
    first = next((member for member in (*reached, *stations) if not facts_.established(member)), None)
    if first is None:
        return _row(Tag.LIMITED, [_held(rq.fact_key(_STATIONS.fact), _STATIONS.rank, _Q, _A.STATIONS, session, None,
                                        questions.coding_rule(_Rule.LIMITED), _anchor(R, event))])
    return _row(Tag.LIMITED, [_open(first, _STATIONS, _own(first, reached), session, event, group, R)])


def _row_lower(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """LOWER (D43): every reached point established and in the class reach, at least one; the stoma class also an
    anatomy entry of type stoma supported and the approach supported through_stoma. A supported point outside the
    reach is the misfit, the examination-class explanation (4.3 LOWER: "misfit: held (class)"; 4.8: an established
    failure is an explanation). For the stoma class the approach is asked as the approach (D225, refute-4a-r2 P5: RANK
    row 8, procedure, "approach for a class" - never R6's extent sentence): another approach supported is the class
    explanation naming it (procedure, an explanation); an approach not established, or supported through_stoma with no
    anatomy entry of type stoma supported, the approach question (procedure, a question); through_stoma denied with no
    approach supported - no approach to name - stays the examination-class explanation (extent; the step's NOTES,
    question Q6). The reach and the approach are each recorded whenever they are not T (HO-8: every unresolved fact is
    held; refute-r4a-r1 F7: an unestablished reach no longer hides the approach), so RANK asks the approach (row 8)
    before the extent (row 14) when both are unknown, and the row is F when either fails on an established fact.

    DECISIONS D328 (1) (L6C-1): the class's route is the lower-GI route table's (catalogue.LOWER_ROUTES), read here for
    the lower EUS codes - per anus for the sigmoidoscopic and colonoscopic classes (45341, 45342, 45391, 45392:
    ``_anus_route``, with LOWER's own explanation: an approach established through a stoma, a pouch or - the colonoscopic
    class, a colon to traverse - a colon gone, a stoma that may exist), through a stoma for the stoma class (44406,
    44407: ``_lower_approach``, as above). A session not established is asked as before, beside the table's own hold
    about the act where the anatomy alone contradicts a per-anus row; a lower EUS code the table declares no row for
    holds with the table's own hold."""
    exam_class = c.spec.row.eus_class if c.spec.row is not None else None
    session = _session(R, event)
    found = catalogue.lower_route(c.code)
    if session is None or exam_class is None:
        row = _no_session(Tag.LOWER, R, event, group)
        held: list[HeldFact] = []
        if found is None:
            held = [_table_hold(R, event, event)]
        elif found.route is Approach.TRANSANAL:
            held, _ = _anus_route(found.needs, _Rule.LOWER, group, R, None, event)
        if found is not None and not held and path_guard(found, R, None):  # DECISIONS D330 (1): the path guard
            held = [_table_hold(R, event, event)]
        return _row(Tag.LOWER, [*row.witnesses, *held]) if held else row
    witnesses, failed = _lower_reach(exam_class, group, R, session, event)
    route: list[HeldFact] = []
    route_failed = False
    if found is None:
        route = [_table_hold(R, session, event)]
    elif found.route is Approach.TRANSANAL:
        route, route_failed = _anus_route(found.needs, _Rule.LOWER, group, R, session, event)
    elif found.route is Approach.THROUGH_STOMA:
        route, route_failed = _lower_approach(group, R, session, event)
    if found is not None and not route and path_guard(found, R, session):  # DECISIONS D330 (1): the path guard
        route = [_table_hold(R, session, event)]
    return _row(Tag.LOWER, [*witnesses, *route], failed or route_failed)


def _lower_reach(exam_class: catalogue.EusClass, group: Sequence[Kind], R: FactSet, session: Id,
                 event: Id) -> tuple[list[HeldFact], bool]:
    """LOWER's reach: a contradicted reached point asks rank 1; a supported point outside the class reach is the
    examination-class explanation (F); a point not established, or none, the extent question; else nothing."""
    reached, points = _reached(R, session)
    conflict = _contradicted(reached)
    if conflict is not None:
        return [_open(conflict, _EXTENT, _A.REACHED, session, event, group, R)], False
    reach = catalogue.EUS_CLASS_REACH[exam_class]
    outside = next((member for member in reached if member.result is Result.SUPPORTED
                    and isinstance(member.value, Extent) and member.value not in reach), None)
    if outside is not None:
        return [_fails(_EXTENT, True, _A.REACHED, session, outside, _Rule.LOWER, R, event)], True
    open_ = next((member for member in reached if not facts_.established(member)), None)
    if open_ is not None or not points:
        return [_open(open_ if open_ is not None else facts_.SILENT, _EXTENT, _A.REACHED, session, event, group,
                      R)], False
    return [], False


def _lower_colonic(R: FactSet, session: Id, event: Id) -> list[HeldFact]:
    """DECISIONS D325 (2) (round r3's third repair; the int5 integrator's Q1, D324 (5)'s range): LOWER's stoma class -
    44406 and 44407, the EUS colonoscopy codes through a stoma, inside 44388-44408 - needs an established COLONIC route
    too (``colonic_route``: the anatomy may not leave the colon gone - DECISIONS D327 (1),
    ``whole_colon_absent_possible`` -, and the stoma established in the colon or a reached point at or past the cecum
    supported), beside the approach established through_stoma and a stoma entry established. Met: nothing. Not met
    while the reach is open and may lie at or past the cecum (a reached point not established that may be one of
    AT_OR_PAST_CECUM, or no reach filed) and the anatomy may not leave the colon gone: nothing here - LOWER's own reach
    question (``_lower_reach``) already holds the row, and a true answer that the scope reached the cecum releases it,
    never one that it reached the ileum, the valve or the stoma. Otherwise the class's own hold for its route
    (procedure, RANK row 8, coding_rule:lower, about the session's anatomy: the hold the class gives a stoma route with
    no stoma entry, so its words are the class's, D320 (i)): a reach to the stoma, the small bowel or the ileocecal
    valve alone never completes a through-stoma colonoscopy, nor does any reach where no colon may remain. Every 9.4
    weakening only keeps it held (the route reads supported facts, the absent readings only widen, an open reach is
    LOWER's question)."""
    if colonic_route(R, session):
        return []
    if not whole_colon_absent_possible(R):
        reached = facts_.members(R, session, _A.REACHED)
        if not reached or any(not facts_.established(member)
                              and any(facts_.possibly(member, point) for point in AT_OR_PAST_CECUM)
                              for member in reached):
            return []
    return [_held(rq.fact_key(_PROCEDURE.fact), _PROCEDURE.rank, _Q, _A.TYPE, session, None,
                  questions.coding_rule(_Rule.LOWER), _anchor(R, event))]


def _lower_approach(group: Sequence[Kind], R: FactSet, session: Id, event: Id) -> tuple[list[HeldFact], bool]:
    """The stoma class's approach (D225 P5; module docstring): supported through_stoma beside a supported anatomy entry
    of type stoma is T - DECISIONS D325 (2): once the route is colonic (``_lower_colonic``, else the class's route
    hold); another approach supported is the class explanation naming it (F, RANK row 8); through_stoma denied with no
    approach supported the examination-class explanation (F, extent: question Q6); through_stoma supported with no stoma
    entry, or an approach not established, the approach question (U, RANK row 8)."""
    approach = _fact(R, session, _A.APPROACH)
    if facts_.holds(approach, Approach.THROUGH_STOMA):
        if any(facts_.holds(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) for entry in R.anatomy):
            return _lower_colonic(R, session, event), False
        return [_held(rq.fact_key(_PROCEDURE.fact), _PROCEDURE.rank, _Q, _A.TYPE, session, None,
                      questions.coding_rule(_Rule.LOWER), _anchor(R, event))], False
    if approach.result is Result.SUPPORTED and isinstance(approach.value, Approach):  # misfit: named (P5)
        return [_fails(_PROCEDURE, True, _A.APPROACH, session, approach, _Rule.LOWER, R, event)], True
    if facts_.denied(approach, Approach.THROUGH_STOMA):  # misfit with no approach to name: the class's
        return [_fails(_EXTENT, True, _A.APPROACH, session, approach, _Rule.LOWER, R, event)], True
    return [_open(approach, _PROCEDURE, _A.APPROACH, session, event, group, R,
                  questions.coding_rule(_Rule.LOWER))], False


# --- the lower-GI route table (DECISIONS D328 (1); D310 (1), D225 P5, D312 (5), D324 (5), D325 (2), D327 (1)) ----------
# A billing table (D306 keeps billing tables as code): catalogue.LOWER_ROUTES declares, for EVERY lower-GI endoscopy
# code of the catalogue (catalogue.lower_gi), its route - per anus, through a stoma, through a pouch - and the anatomy
# it needs - a colon to traverse, a rectum and sigmoid, a colonic stoma, an ileal stoma, a pouch -, and a code is READY
# only when the record establishes its route and nothing filed contradicts the anatomy it needs, read fail-closed. The
# rounds before added the route rules family by family (the colonoscopy through a stoma, D310 (1); through the anus,
# D325 (2); each found by another refutation), so D328 (1) rules one table and one reading of it, dispatched on the
# code's row (``_row_lower_route``; the lower EUS codes' own row, ``_row_lower``):
# - per anus (``_anus_route``, every per-anus family alike: the colonoscopy, its EUS codes 45391 and 45392, the
#   sigmoidoscopy and its EUS codes 45341 and 45342): an approach established through a stoma is the class's
#   explanation; an entry that may be an ileal pouch, or an approach established or possible through a pouch, is the
#   table's own hold (``pouch_possible``); for the colonoscopy family an anatomy that may leave no colon is the table's
#   own hold too (``no_colon_possible``: D325 (2), D327 (1) - a small-bowel reach completes a colonoscopy only when a
#   colon remains); a stoma that may exist asks the approach (``stoma_possible``, D312 (5)). There is no rectum-absent
#   arm: a sigmoidoscopy after a low anterior resection stays as int6 decides it.
# - through a stoma: the colonoscopy family needs a colonic stoma - the approach supported through_stoma, a stoma entry
#   established and a colonic route (``colonic_route``: D324 (5), D325 (2), D327 (1); LOWER's stoma class, 44406 and
#   44407, reads the same need through ``_lower_approach`` and ``_lower_colonic``); the ileoscopy through a stoma
#   (44380-44384) needs an ileal stoma, its route the enteroscopy class's own (engine/classes: the approach and the
#   entry passed through), and nothing filed may make that stoma colonic (``colonic_stoma_possible``).
# - through a pouch (44385, 44386): a pouch, which the enteroscopy class's route establishes (the entry passed through
#   established an ileal pouch: engine/classes) - nothing more here.
# A lower-GI code the table declares no row for holds with the table's own hold. Before the table (int2) the two
# colonoscopy ranges' requirement rows were row for row the same, so a through-stoma code went READY on any colonoscopy
# whose act was established (D310: the gap is MAIN's studio/gi too). The colonoscopy family's codes of each route:


def _route_of(code: int) -> Approach | None:
    found = catalogue.LOWER_ROUTES.get(code)
    return found.route if found is not None else None


STOMA_ROUTE_CODES: frozenset[int] = frozenset(
    code for code, row in CODES.items()
    if row.family is SessionKind.COLONOSCOPY and _route_of(code) is Approach.THROUGH_STOMA)
ANUS_ROUTE_CODES: frozenset[int] = frozenset(
    code for code, row in CODES.items()
    if row.family is SessionKind.COLONOSCOPY and _route_of(code) is Approach.TRANSANAL)
# DECISIONS D324 (5) (round r3's repair: L6-2, R2E-STOMA-ORGAN), two more columns of the same billing table, each an
# enumeration of engine/anatomy's own regions and containment (never a list of words):
# - the COLONIC REACH: the reached points of the colon (anatomy.Region.COLON: the colon, its sides and segments, the
#   cecum, the appendiceal orifice and the ileocecal valve, to the rectosigmoid) - never the ileum or the small bowel
#   (an ileal or small-bowel reach alone never completes a through-stoma colonoscopy: through an ileostomy it may never
#   have entered a colon), nor the rectum or the anal canal;
# - the organs of a LOWER-TRACT stoma: every landmark that is, holds or lies within the colon or the ileum
#   (anatomy.compatible: the colon and its segments, the ileum and its terminal parts, the small bowel that holds the
#   ileum) - a colostomy or an ileostomy, the only stomas a colonoscope passes; a stoma of any other placed organ (a
#   gastrostomy, an esophagostomy, a duodenostomy, a jejunostomy) opens no colonoscopy route.
COLONIC_REACH: frozenset[Extent] = frozenset(
    extent for extent in Extent if anatomy.region(extent) is anatomy.Region.COLON)
# DECISIONS D325 (2) (L6B-1, high: a scope through a loop ileostomy's efferent limb to the valve gave 44389 READY): the
# colonic reach THROUGH A STOMA is a point at or past the cecum - every point of the colon but the ileocecal valve. The
# valve is the ileum's own opening into the colon: from an ileal stoma, or one of an organ not established, it is
# reached before any colon, so it never counts alone; it counts only from a stoma established in the colon, where the
# organ arm of ``colonic_route`` already makes the route colonic whatever the reach (``_colonic_organ``).
AT_OR_PAST_CECUM: frozenset[Extent] = frozenset(
    extent for extent in COLONIC_REACH if extent is not Extent.ILEOCECAL_VALVE)
LOWER_STOMA_ORGANS: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark
    if anatomy.compatible(landmark, Landmark.COLON) or anatomy.compatible(landmark, Landmark.ILEUM))
# The landmarks that name no placeable organ (anatomy.UNPLACED, anatomy.ALTERED: other, an anastomosis, a stoma, a
# pouch): an organ filed so leaves every organ open.
_NO_ORGAN: frozenset[Landmark] = anatomy.UNPLACED | anatomy.ALTERED


def settled_narrows(found: Fact) -> bool:
    """DECISIONS D342 (1) (a), THE ONE PREDICATE over settle's outcome (FINAL-V2 3.3's truth table: contract/settle.row
    and decide) for every claim a release decides on - a subtype, an absence's organ, a controlled type, any claim a
    harmless row reads - and for every reader built on ``_may_be``, the guard's and the route rows' hold clauses
    included: whether the settled claim ``found`` may NARROW the reading to what it carries. Exactly two settled states
    do:
    - ESTABLISHED through its control (3.3 row 8: every check passed, pass 2 supported the claim attached and rejected
      its control where it has one - facts.established);
    - UNAPPRAISED (3.3 row 6: pass 2 was never asked, and pass 1 had no doubt, no contradiction and no failed check -
      settle's row-6 outcome, unresolved for its one reason; DECISIONS D340 Q1: such a claim decides as Fable read it).
    Every other settled state is read at its WIDEST, whatever its reason - this is one predicate over the settled result,
    never a list of the states it widens: pass 1's contradiction or doubt (rows 1, 2), a silent slot (3), a failed check
    (4), pass 1's qualifier (5), indistinct cards (7), every pair outcome pass 2 left unestablished (row 9: unclear,
    qualified, detached, incoherent, missing, contradicted with its control rejected or not, the control missing), and any
    fact a later reading leaves unresolved. int8's reading widened only a claim pass 2 contradicted with no option left
    (``rejected_open``), so a claim pass 2 doubted - an honest "unclear" on a subtype pass 1 over-read - still decided
    the guard's release at its claimed value and its sibling's (L4P8-1, L5R8-1, L6R-1, L9-1; the final check's finding
    1). Every 9.4 weakening acts on an established fact and leaves it in a widened state or a claim of the same value,
    so none narrows a reading (P-MONO)."""
    return facts_.established(found) or (found.result is Result.UNRESOLVED
                                         and tuple(found.reasons) == (Reason.UNAPPRAISED,))


def _may_be(found: Fact, value: AnatomyType | Landmark | AnastomosisSubtype | Approach | Extent | Id) -> bool:
    """Whether an anatomy entry's (or a session's) ``found`` may hold ``value``, read fail-closed for a closure that only
    HOLDS (D324 (5)) and for the release reading alike (DECISIONS D342 (1) (a): the same predicate for every reader):
    - where the settled claim may narrow (``settled_narrows``: established, or unappraised), facts.possibly - supported
      at it; unappraised, its claimed value and what it carries;
    - any established negation - it never rules a value out here: it names no value of its own, and the fact pass has no
      negated form for an entry's type and no control for its negated organ (contract/claims.py), so a negation is read
      to hold only, never to release;
    - every other settled state (pass 2 asked and did not establish it, pass 1 doubted or contradicted it, a check failed
      on it, a silent slot): EVERY value of its enumeration - never its claimed value, an unrejected control's value or a
      doubt's readings alone - but a value an established negation answer ruled out (facts.ruled_out: DECISIONS D324
      (1), a negation answer removes only its value).
    So only a fact SUPPORTED at another value, or a claim pass 2 was never asked of another value, rules ``value`` out.
    DECISIONS D336 (1) (b) (L4P-5) widened a claim pass 2 rejected with no control left (int8's ``rejected_open``);
    D342 (1) (a) completes it as one predicate. Every 9.4 weakening only widens it (``settled_narrows``)."""
    return _possibly_settled(found, value) or found.result is Result.NEGATED


def _possibly_settled(found: Fact, value: AnatomyType | Landmark | AnastomosisSubtype | Approach | Extent | Id) -> bool:
    """DECISIONS D342 (1) (a): ``found`` may hold ``value`` by the one predicate alone - facts.possibly where the settled
    claim may narrow (``settled_narrows``: established - an established negation of a claim the contract writes in a
    negated form of its own, a session's reached point, names no value -, or unappraised); every value of its
    enumeration but one an established negation answer ruled out (facts.ruled_out) where it may not. ``_may_be`` adds the
    anatomy entry's rule that an established negation names no value at all and rules none out; a session's reach is
    read by this one (R5R-9's reach clause, ``ileal_stoma_contradicted``), where "the cecum was not reached" established
    rules the cecum out and reaches nothing."""
    return facts_.possibly(found, value) or (not settled_narrows(found) and value not in facts_.ruled_out(found))


def _possible_as_filed(found: Fact, value: AnatomyType | Id) -> bool:
    """``_may_be`` before DECISIONS D336 (1) (b)'s and D342 (1) (a)'s widening of a claim that is neither established nor
    unappraised: facts.possibly or any established negation - read where the guard EXEMPTS an entry (``route_entries``
    while the act's session is not established: an entry that may be the route's own), where a wider reading would
    exempt more and so hold less."""
    return facts_.possibly(found, value) or found.result is Result.NEGATED


def colon_absent_possible(R: FactSet, entry: Id) -> bool:
    """DECISIONS D324 (5): whether anatomy entry ``entry`` may file the colon AS A WHOLE surgically absent - its type
    may be surgically_absent and its organ may be the colon itself (``_may_be``: a type or organ pass 2 never
    established, as a surgically absent organ no reached point names is never claimed, reads its claimed value). A
    segment filed absent (a sigmoid colectomy, a right hemicolectomy: organ supported at the segment, or claimed so) is
    no absent colon, and a type or organ SUPPORTED otherwise rules the entry out; an established negation never does
    (``_may_be``: read to hold only)."""
    return (_may_be(_fact(R, entry, _A.TYPE), AnatomyType.SURGICALLY_ABSENT)
            and _may_be(_fact(R, entry, _A.ORGAN), Landmark.COLON))


# DECISIONS D327 (1) (round r3's repair of int6's residual: the rules lane's Q1, v8, v9 and v10), two more columns of
# the same billing table, each an enumeration of members (never a list of words), read beside D324 (5)'s colon filed
# absent as a whole:
# - the colon's SEGMENTS, the anatomy table's (engine/anatomy's Region.COLON): the cecum and the ascending, transverse,
#   descending and sigmoid colon. The table's other colon landmarks are the colon itself, its four sides (the right,
#   left, proximal and distal colon) and the points within or between segments - the appendiceal orifice and the
#   ileocecal valve in the cecum; the hepatic and splenic flexures and the rectosigmoid, where two segments meet. A side
#   counts as the segments it holds (anatomy.contains: the right colon the cecum and the ascending colon, the left colon
#   the descending and the sigmoid colon, the proximal colon the right colon's and the transverse colon, the distal
#   colon the left colon's), the colon as all five, a point as none. The four kinds split Region.COLON completely (the
#   tests pin it); a colon landmark the table gains is no segment here until it is classified, so it is never needed
#   for the segments to cover the colon - it can only ever add a hold.
# - the ANASTOMOSIS SUBTYPES that join the ileum BELOW the colon: an ileorectal anastomosis (after a total abdominal
#   colectomy) and an ileoanal one (after a proctocolectomy) - beside either no colon remains. The subtypes that leave
#   the colon as before are the ones listed, and ILEUM_BELOW_COLON is the rest, so a subtype the enumeration gains holds
#   until it is classified: those joining a colon that remains (ileocolic, a right hemicolectomy; colocolic, a
#   segmental colectomy; colorectal and coloanal, a sigmoid, Hartmann or anterior resection) and those of the upper
#   tract, the bile duct and the pancreas, with other, which say nothing of the colon.
COLON_SEGMENTS: frozenset[Landmark] = frozenset({
    Landmark.CECUM, Landmark.ASCENDING_COLON, Landmark.TRANSVERSE_COLON, Landmark.DESCENDING_COLON,
    Landmark.SIGMOID_COLON})
# Each place whose absence files a segment absent -> the segments it is or holds (a segment itself; a side, its
# segments; the colon, all five). A place in no such row (a point, an organ outside the colon) files none.
_SEGMENTS_OF: Mapping[Landmark, frozenset[Landmark]] = MappingProxyType({
    place: frozenset(segment for segment in COLON_SEGMENTS if place is segment or anatomy.contains(place, segment))
    for place in Landmark
    if any(place is segment or anatomy.contains(place, segment) for segment in COLON_SEGMENTS)})
_COLON_REMAINS: frozenset[AnastomosisSubtype] = frozenset({
    AnastomosisSubtype.ILEOCOLIC, AnastomosisSubtype.COLOCOLIC, AnastomosisSubtype.COLORECTAL,
    AnastomosisSubtype.COLOANAL})
_NOT_OF_THE_COLON: frozenset[AnastomosisSubtype] = frozenset({
    AnastomosisSubtype.GASTROJEJUNAL, AnastomosisSubtype.GASTRODUODENAL, AnastomosisSubtype.ESOPHAGOJEJUNAL,
    AnastomosisSubtype.ESOPHAGOGASTRIC, AnastomosisSubtype.HEPATICOJEJUNAL, AnastomosisSubtype.CHOLEDOCHODUODENAL,
    AnastomosisSubtype.PANCREATICOJEJUNAL, AnastomosisSubtype.OTHER})
ILEUM_BELOW_COLON: frozenset[AnastomosisSubtype] = frozenset(
    subtype for subtype in AnastomosisSubtype if subtype not in _COLON_REMAINS | _NOT_OF_THE_COLON)
# DECISIONS D328's addendum (rules4 Q2), fail-closed: when both sides of the colon may be absent, the transverse colon may
# be absent too, so the sides cover the colon - the right colon's segments and the left colon's (anatomy.contains: the
# cecum and the ascending colon; the descending and the sigmoid colon), each side filed as the side or as its segments
# (a side counts as its segments: D327 (1)). Every cover of the five segments covers both sides.
_BOTH_SIDES: frozenset[Landmark] = _SEGMENTS_OF[Landmark.RIGHT_COLON] | _SEGMENTS_OF[Landmark.LEFT_COLON]
# DECISIONS D328's addendum (rules4 Q3): an anastomosis's JOINS are read as well as its subtype. The places of the small
# bowel (anatomy.Region.SMALL_BOWEL: the jejunum, the ileum and its terminal parts, the small bowel) and the places below
# the colon (Region.RECTUM and Region.ANUS: the rectum, the anal canal), each with the landmarks that name no placeable
# organ (_NO_ORGAN: other, an anastomosis, a stoma, a pouch - an ileal pouch's own landmark), which may be either: an
# anastomosis joining one to the other leaves no colon between them. Computed from engine/anatomy's regions.
_SMALL_BOWEL_PLACES: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark if anatomy.region(landmark) is anatomy.Region.SMALL_BOWEL) | _NO_ORGAN
_BELOW_COLON_PLACES: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark
    if anatomy.region(landmark) in (anatomy.Region.RECTUM, anatomy.Region.ANUS)) | _NO_ORGAN


# DECISIONS D330 (1) (R5R-6, closed with the guard, by its principle): the two ends each anastomosis subtype names (every
# subtype but OTHER, which names another pair) - the places of the regions its name joins (engine/anatomy's regions;
# the ileum with the landmarks compatible with it, the jejunum alone of the small bowel): a joins member naming no
# placeable organ is read as one of its subtype's own ends.
def _region_places(*regions: anatomy.Region) -> frozenset[Landmark]:
    return frozenset(landmark for landmark in Landmark if anatomy.region(landmark) in regions)


_ILEAL_ENDS: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark if anatomy.compatible(landmark, Landmark.ILEUM))
_COLON_ENDS: frozenset[Landmark] = _region_places(anatomy.Region.COLON)
_JEJUNUM: frozenset[Landmark] = frozenset({Landmark.JEJUNUM})
SUBTYPE_ENDS: Mapping[AnastomosisSubtype, frozenset[Landmark]] = MappingProxyType({
    AnastomosisSubtype.ILEOCOLIC: _ILEAL_ENDS | _COLON_ENDS,
    AnastomosisSubtype.COLOCOLIC: _COLON_ENDS,
    AnastomosisSubtype.COLORECTAL: _COLON_ENDS | _region_places(anatomy.Region.RECTUM),
    AnastomosisSubtype.COLOANAL: _COLON_ENDS | _region_places(anatomy.Region.ANUS),
    AnastomosisSubtype.ILEORECTAL: _ILEAL_ENDS | _region_places(anatomy.Region.RECTUM),
    AnastomosisSubtype.ILEOANAL: _ILEAL_ENDS | _region_places(anatomy.Region.ANUS),
    AnastomosisSubtype.GASTROJEJUNAL: _region_places(anatomy.Region.STOMACH) | _JEJUNUM,
    AnastomosisSubtype.GASTRODUODENAL: _region_places(anatomy.Region.STOMACH, anatomy.Region.DUODENUM),
    AnastomosisSubtype.ESOPHAGOJEJUNAL: _region_places(anatomy.Region.ESOPHAGUS) | _JEJUNUM,
    AnastomosisSubtype.ESOPHAGOGASTRIC: _region_places(anatomy.Region.ESOPHAGUS, anatomy.Region.STOMACH),
    AnastomosisSubtype.HEPATICOJEJUNAL: _region_places(anatomy.Region.BILIARY, anatomy.Region.LIVER) | _JEJUNUM,
    AnastomosisSubtype.CHOLEDOCHODUODENAL: _region_places(anatomy.Region.BILIARY, anatomy.Region.DUODENUM),
    AnastomosisSubtype.PANCREATICOJEJUNAL: _region_places(anatomy.Region.PANCREAS) | _JEJUNUM,
})


def _absent_readings(R: FactSet, entry: Id) -> frozenset[frozenset[Landmark]]:
    """DECISIONS D327 (1): each set of colon segments one reading of anatomy entry ``entry`` may file surgically absent
    - only the empty set unless its type may be surgically_absent; else, for every place its organ may be (``_may_be``:
    its supported value; not established, its claimed value, a reading, a side or an unrejected control's value; every
    place for a silent organ, an open denial or an established negation), the segments that place is or holds
    (``_SEGMENTS_OF``), and the empty set when no such place is possible. Read fail-closed as ``colon_absent_possible``
    reads its entry: only a fact SUPPORTED at another value rules a reading out. Every 9.4 weakening only adds
    readings."""
    if not _may_be(_fact(R, entry, _A.TYPE), AnatomyType.SURGICALLY_ABSENT):
        return frozenset({frozenset()})
    organ = _fact(R, entry, _A.ORGAN)
    readings = frozenset(segments for place, segments in _SEGMENTS_OF.items() if _may_be(organ, place))
    return readings or frozenset({frozenset()})


def segments_absent_possible(R: FactSet) -> bool:
    """DECISIONS D327 (1) (v10): whether the anatomy entries that may be surgically absent may together cover every
    segment of the colon - the colon filed absent segment by segment, or side by side: whether ONE reading of all the
    entries together (each entry one of its readings, ``_absent_readings``) files every segment of COLON_SEGMENTS
    absent - or, DECISIONS D328's addendum (rules4 Q2, fail-closed), both sides of the colon (``_BOTH_SIDES``: the right
    colon's segments and the left colon's), beside which the transverse colon may be absent too. Computed over the
    segment sets the entries can reach so far (at most 2 ** 5 of them). So an entry that may be either of two sides
    counts as the one that completes the cover, but never as both at once: beside the transverse colon, an entry
    contradicted between the right and the left colon leaves a colon in every reading, and the code is read as before.
    Four segments of five that keep a segment of a side, a side alone, or a side beside the other side's one segment (the
    right colon and the sigmoid) leave a colon that may remain: False. Every 9.4 weakening only adds readings, so none
    turns it False."""
    reached: frozenset[frozenset[Landmark]] = frozenset({frozenset()})
    for entry in R.anatomy:
        reached = frozenset(so_far | segments for so_far in reached for segments in _absent_readings(R, entry))
    return any(so_far >= _BOTH_SIDES for so_far in reached)


def ileum_below_colon_possible(R: FactSet, entry: Id) -> bool:
    """DECISIONS D327 (1) (v8, v9): whether anatomy entry ``entry``'s subtype may be one that joins the ileum below the
    colon (ILEUM_BELOW_COLON: ileorectal, ileoanal) - ``_may_be`` over a subtype pass 1 claimed: supported at it, its
    claimed value, a reading, a side, an unrejected control's value (the subtype's control names its sibling, and
    ileorectal and ileoanal are each other's), an open denial, or any established negation. Never a SILENT subtype: it
    names no anastomosis. DECISIONS D328's addendum (rules4 Q3): OR its joins may join the ileum to the rectum or the
    anus (``joins_ileum_below_colon_possible``) - so only an anastomosis whose subtype AND joins pass 1 both left silent
    stays as int6 decides it (the addendum's recorded residual; the common right-hemicolectomy filing names an ileocolic
    subtype and joins the ileum to the colon). The entry's type is not read: a subtype or a joins list names an
    anastomosis whatever type was filed. Every 9.4 weakening keeps a claimed subtype claimed (none makes it silent) and
    only widens what it and each member of the joins may be."""
    subtype = _fact(R, entry, _A.SUBTYPE)
    return ((not facts_.silent(subtype) and any(_may_be(subtype, value) for value in ILEUM_BELOW_COLON))
            or joins_ileum_below_colon_possible(R, entry))


def joins_ileum_below_colon_possible(R: FactSet, entry: Id) -> bool:
    """DECISIONS D328's addendum (rules4 Q3): whether anatomy entry ``entry``'s JOINS may join the small bowel - the
    ileum - to the rectum or the anus, read fail-closed over the members pass 1 filed (``_may_be`` over each: its
    supported place; not established, its claimed value, a reading, a side, an unrejected control's value, an open
    denial; any established negation; a claim pass 2 rejected with no control, every place; a landmark naming no
    placeable organ may be either end): one member that may lie in the small bowel (_SMALL_BOWEL_PLACES) beside ANOTHER
    that may lie below the colon (_BELOW_COLON_PLACES). Two members that are each the colon's or the upper tract's (an
    ileocolic anastomosis joins the ileum to the colon; a colorectal one the colon to the rectum) never hold. Every 9.4
    weakening of a member only widens what it may be, and 9.4 deletes no member of this list (test_properties.LISTS),
    so none turns it False.

    DECISIONS D330 (1) (c) (R5R-4): a list of ONE member that may lie below the colon - the rectum, the anal canal, or a
    landmark naming no placeable organ, which may be either end - holds (an LAR's colorectal join filed by its rectum).

    DECISIONS D330 (1) (R5R-6, closed with the guard; its class rule by principle): where the entry's subtype is filed
    and every subtype it may be names its two ends (SUBTYPE_ENDS: every subtype but OTHER), a member naming no placeable
    organ (a colonic J-pouch's pouch, a gastric bypass's pouch) is read as one of those ends - never as the small bowel
    or below the colon unless an end is: a coloanal anastomosis joining the pouch and the anal canal, or a gastrojejunal
    one joining the pouch and the jejunum, joins no ileum below the colon. A silent subtype, or one that may be OTHER,
    reads such a member as before (either end). Every 9.4 weakening of the subtype keeps it filed and only widens what
    it may be, so it only widens the ends a member may be, or turns the reading off.

    DECISIONS D336 (1) (b) (final check 2 and 3; FC3 supersedes D330 (1) (c)'s release of a one-member list): an
    anastomosis has two ends, so for an entry that may be an anastomosis (``_may_be`` over its type) every end its joins
    list does not name - both for an empty list, the second for a list of one member - may be EVERY landmark, or, where
    its subtype is filed and names its ends (the R5R-6 reading above), one of those ends: a silent-joins anastomosis at
    the jejunum may be jejuno-rectal, and a one-member [ileum] may be an ileorectal or an ileoanal join whose other end
    pass 1 did not file - both hold; an ileocolic subtype decides its ends, so its joins left silent join the ileum to
    the colon and hold nothing. Every 9.4 weakening of the type only widens whether it may be an anastomosis, and of the
    subtype only widens (or turns off) its ends, so none turns it False.

    DECISIONS D342 (1) (b) (L9-2, L6R-3: A FILED FIELD NAMES ITS SHAPE): a FILED joins list names an anastomosis whatever
    the entry's uncontrolled type, so a list of one member has an unnamed end - every landmark, or its subtype's own ends
    - beside a surgically absent organ, a Roux limb, another alteration or a silent type as beside an anastomosis; only
    a CONTROLLED type established as another shape (``_own_shape``: a stoma, an ileal or a gastric pouch, read by
    ``settled_narrows``) reads its list otherwise, as its own join (a gastric pouch joined to the jejunum). An EMPTY list
    files nothing: it names its two unnamed ends only for an entry that may be an anastomosis (D336 (1) (b)). Every 9.4
    weakening of the type only widens what it may be, so it only turns a controlled type's own join into an
    anastomosis's (more ends), never the reverse."""
    joins = facts_.members(R, entry, _A.JOINS)
    subtype = _fact(R, entry, _A.SUBTYPE)
    named = [value for value in AnastomosisSubtype if _may_be(subtype, value)]
    ends = (frozenset().union(*(SUBTYPE_ENDS[value] for value in named))
            if not facts_.silent(subtype) and named and all(value in SUBTYPE_ENDS for value in named) else None)
    places = []
    for member in joins:
        found = frozenset(place for place in Landmark if _may_be(member, place))
        places.append((found - _NO_ORGAN) | ends if ends is not None and found & _NO_ORGAN else found)
    if len(places) == 1 and places[0] & _BELOW_COLON_PLACES:  # D330 (1) (c): one member that may lie below the colon
        return True
    type_ = _fact(R, entry, _A.TYPE)
    if ((not places and _may_be(type_, AnatomyType.ANASTOMOSIS))  # D336 (1) (b): an empty list's two unnamed ends
            or (len(places) == 1 and not _own_shape(type_))):  # D342 (1) (b): a filed member's unnamed end
        places += [ends if ends is not None else frozenset(Landmark)] * (2 - len(places))
    small = [bool(found & _SMALL_BOWEL_PLACES) for found in places]
    below = [bool(found & _BELOW_COLON_PLACES) for found in places]
    return any(small[one] and below[other] for one in range(len(places)) for other in range(len(places))
               if one != other)


def _own_shape(type_: Fact) -> bool:
    """DECISIONS D342 (1) (b): whether an entry's type ``type_`` is a CONTROLLED type established as a shape of its own -
    every value it may be (``_may_be``, so ``settled_narrows``: established, or unappraised) one the contract controls
    (catalogue.CONTROLLED_TYPES: a stoma, an ileal pouch, a gastric pouch) - so its filed joins list is read as its own
    join rather than as an anastomosis's. An uncontrolled type (surgically absent, a Roux limb, a bypass, another
    alteration, an anastomosis), a silent type or one in any widened state is no such shape."""
    types = frozenset(value for value in AnatomyType if _may_be(type_, value))
    return bool(types) and types <= catalogue.CONTROLLED_TYPES


def whole_colon_absent_possible(R: FactSet) -> bool:
    """D324 (5) and DECISIONS D327 (1): whether the record's anatomy may leave no colon at all - an entry may file the
    colon as a whole surgically absent (``colon_absent_possible``), the entries that may be surgically absent may cover
    every segment of the colon (``segments_absent_possible``), or an entry's subtype may join the ileum below the colon
    (``ileum_below_colon_possible``). The route table reads it wherever D324 (5) read the first case alone - the
    through-stoma codes' colonic route (``colonic_route``, its witness, LOWER's ``_lower_colonic``) and the anus route's
    colon to traverse (``no_colon_possible``) - so each case holds 44388-44408 and 45378-45398 with the table's own
    hold. A colon that may remain - a right hemicolectomy with an ileocolic anastomosis, a sigmoid or Hartmann
    resection, a segmental colectomy - meets none of them, and the code is read exactly as before. Every 9.4 weakening
    only widens each case, so none turns it False."""
    return (any(colon_absent_possible(R, entry) or ileum_below_colon_possible(R, entry) for entry in R.anatomy)
            or segments_absent_possible(R))


def _colonic_organ(R: FactSet, entry: Id) -> bool:
    """D324 (5)'s first arm for one entry: its type supported stoma and its organ SUPPORTED at a colon place
    (anatomy.Region.COLON) - a colostomy the record establishes. The fact pass never claims a stoma's organ
    (contract/claims.py has only the surgically-absent forms for an organ), so on a fact pass alone this arm reads an
    established organ only where an answer or a later request supplies one; an organ not established never meets it."""
    organ = _fact(R, entry, _A.ORGAN)
    return (facts_.holds(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) and organ.result is Result.SUPPORTED
            and isinstance(organ.value, Landmark) and anatomy.region(organ.value) is anatomy.Region.COLON)


def colonic_route(R: FactSet, session: Id) -> bool:
    """DECISIONS D324 (5) (L6-2, high; also on int3): whether a colonoscopy through a stoma in ``session`` - its
    approach supported through_stoma - has a COLONIC route, which a through-stoma code (44388-44408: DECISIONS D325
    (2), 44406 and 44407 included, ``_lower_colonic``) needs besides the approach and a stoma entry established. Both
    hold:
    - the colon as a whole is not filed surgically absent: no anatomy entry may be a surgically absent colon
      (``colon_absent_possible``, read fail-closed: an entry pass 1 filed so holds whatever pass 2 left open) - and,
      DECISIONS D327 (1), the anatomy may not leave the colon gone otherwise: by its segments or sides, or beside an
      anastomosis joining the ileum below the colon (``whole_colon_absent_possible``);
    - the stoma's organ is a colon segment (every entry that may be a stoma - facts.possibly over its type - a stoma
      established at a colon place: ``_colonic_organ``), or the record establishes a colonic reach through the stoma
      (a reached point of the session SUPPORTED at or past the cecum, AT_OR_PAST_CECUM; the session's approach is
      through the stoma, so its reach is). DECISIONS D325 (2) (L6B-1): the ileocecal valve counts only from a stoma
      established in the colon (the first arm, whatever the reach); from an ileal stoma or one of an organ not
      established only a point at or past the cecum counts - the valve is reached there before any colon.
    An ileal or small-bowel reach alone, or the valve alone, meets neither arm (the class rule: a small-bowel reach
    completes a colonoscopy only when a colon remains and was traversed), so a scope passed through an end ileostomy
    after a proctocolectomy into the ileum, or through a loop ileostomy's efferent limb to the valve, holds the
    through-stoma codes - an ileoscopy through a stoma (44380-44384) - for the coder. Read so, every 9.4 weakening only
    turns it False: the arms read supported facts only, and the absent readings only widen."""
    if whole_colon_absent_possible(R):
        return False
    if any(member.result is Result.SUPPORTED and member.value in AT_OR_PAST_CECUM
           for member in facts_.members(R, session, _A.REACHED)):
        return True
    stomas = [entry for entry in R.anatomy if facts_.possibly(_fact(R, entry, _A.TYPE), AnatomyType.STOMA)]
    return bool(stomas) and all(_colonic_organ(R, entry) for entry in stomas)


def _colonic_route_witness(R: FactSet, session: Id, event: Id, group: Sequence[Kind]) -> HeldFact | None:
    """D324 (5): the route row's witness when ``colonic_route`` is not met (None when it is), as HO-8 holds every fact
    the row rests on and the planner reads each: the route table's own hold (``_route_hold``, the coder's) when an
    entry may file the colon surgically absent - or, DECISIONS D327 (1), the anatomy may leave the colon gone otherwise
    (``whole_colon_absent_possible``): no answer establishes an anatomy entry's type, organ or subtype (the route's
    facts have no question template) - or when the reach is established and holds no colonic point (an ileal or
    small-bowel reach alone, or - DECISIONS D325 (2) - the ileocecal valve alone: no reading of it is colonic through
    the stoma); otherwise the reach the route rests on, asked as COLFULL's extent row asks it (RANK row 14, its reading's
    cause; a contradicted one at RANK 1): a reached point not established that may lie at or past the cecum
    (AT_OR_PAST_CECUM), or an empty reach list - a true answer that the scope reached the cecum through the stoma makes
    the route colonic, so the question it serves can release the code, and a false one never does; an open point that
    may only be the valve is never asked (its true answer would not make the route colonic: L6B-1's question path)."""
    if colonic_route(R, session):
        return None
    if not whole_colon_absent_possible(R):
        reached = facts_.members(R, session, _A.REACHED)
        open_ = next((member for member in reached if not facts_.established(member)
                      and any(facts_.possibly(member, point) for point in AT_OR_PAST_CECUM)), None)
        if open_ is not None or not reached:
            return _open(open_ if open_ is not None else facts_.SILENT, _EXTENT, _A.REACHED, session, event, group, R)
    return _route_hold(R, session, event)


def lower_stoma_possible(R: FactSet, entry: Id) -> bool:
    """DECISIONS D324 (5) (R2E-STOMA-ORGAN): whether anatomy entry ``entry``'s organ leaves it possibly a stoma of the
    lower tract - a colon or an ileum stoma, the only kind a colonoscope may pass. Only an organ SUPPORTED at a placed
    landmark outside LOWER_STOMA_ORGANS rules that out (a gastrostomy's stomach). An organ not established (unresolved -
    the fact pass never claims a stoma's organ -, contradicted, unknown, silent) leaves it open, as does an established
    negation (it names no organ, so the others stay possible) and an organ filed as no placeable landmark (_NO_ORGAN).
    Every 9.4 weakening only opens it."""
    organ = _fact(R, entry, _A.ORGAN)
    if organ.result is not Result.SUPPORTED or not isinstance(organ.value, Landmark) or organ.value in _NO_ORGAN:
        return True
    return organ.value in LOWER_STOMA_ORGANS


def stoma_possible(R: FactSet, session: Id) -> bool:
    """D310 (1)'s "possible" for a colonoscopy through the anus, closed by DECISIONS D312 (5) with F.11 (3) as one rule
    (round r3's build): a stoma route is possible unless the session's approach is ESTABLISHED as another route
    (``_route_closed``: supported at another approach, or through_stoma itself denied), and then exactly when a stoma
    is possible - an anatomy entry's type supported or possible as a stoma (facts.possibly: supported, its claimed
    value or a reading of it, unresolved, contradicted with it a side, an open denial, silent), OR the approach's own
    through_stoma reading possible (``_stoma_reading``: pass 1's claim, a doubt's reading, a contradiction's side or an
    unrejected control's value names it, an open denial leaves every route open, or an established denial of another
    route leaves it among the others). A stoma route needs a stoma or a reading of one, so a silent approach on a
    document whose anatomy names no entry that may be a stoma leaves 45378-45398 as int2 read them (D114).

    The checker's finding (5) (D312): an established stoma entry beside an approach only unresolved as transanal let
    45378-45398 go READY - the reading before read the approach by facts.possibly, which keeps an unresolved fact's
    claimed value and so ruled the stoma route out on a fact pass 2 never established. Read so, every 9.4 weakening
    only opens a closed route (an established approach made unresolved, a doubt added) or keeps what a member names, so
    no weakening turns it False (P-MONO); only an established approach closes it.

    DECISIONS D324 (5) (R2E-STOMA-ORGAN): the entry clause opens a route only for an entry that may be a stoma of the
    lower tract (``lower_stoma_possible``: a colon or ileum stoma, or one whose organ is not established) - a gastrostomy
    established at the stomach beside a colonoscopy no longer holds 45378-45398. Its organ weakened opens it again."""
    approach = _fact(R, session, _A.APPROACH)
    if _route_closed(approach):
        return False
    if _stoma_reading(approach):
        return True
    return any(facts_.possibly(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) and lower_stoma_possible(R, entry)
               for entry in R.anatomy)


def _route_closed(approach: Fact) -> bool:
    """DECISIONS D312 (5): the approach ESTABLISHED as a route that is not through a stoma - supported at another
    approach, or through_stoma denied. Anything not established (unresolved, contradicted, unknown, an open denial,
    silent) leaves the route open, and an established denial of another approach (the scope did not enter through the
    anus) names no route at all, so it leaves it open too."""
    if approach.result is Result.SUPPORTED:
        return approach.value is not Approach.THROUGH_STOMA
    return approach.result is Result.NEGATED and approach.value is Approach.THROUGH_STOMA


def _stoma_reading(approach: Fact) -> bool:
    """DECISIONS D312 (5): the approach's own through_stoma reading is possible - facts.possibly over the approach (its
    supported value; not established, its claimed value, a reading, a side, an unrejected control's value, or an open
    denial, which leaves every value open) for any approach pass 1 claimed (never a silent slot: it names no route, and
    a stoma route needs a stoma), or an established denial of another approach, which leaves through_stoma among the
    other approaches (an established negation reads as every other value of its enumeration)."""
    if approach.result is Result.NEGATED:
        return approach.value is not Approach.THROUGH_STOMA
    return not facts_.silent(approach) and facts_.possibly(approach, Approach.THROUGH_STOMA)


def ileal_pouch_possible(R: FactSet, entry: Id) -> bool:
    """DECISIONS D325 (2) (L6B-2, high): whether anatomy entry ``entry`` may be an ileal pouch (``_may_be`` over its
    type: supported, claimed, a reading, a side, an unrejected control's value, an open denial, silent, or any
    established negation - read to hold only). An ileal pouch is the ileum made into a reservoir once the colon is
    gone, so beside one no colon may remain for a scope through the anus to traverse (a pouch endoscopy is 44385/44386).
    A gastric pouch or a Roux limb is another type (AnatomyType: catalogue.ENTEROSCOPY_CLASS_ANATOMY's distinction,
    D141), so it is never read here."""
    return _may_be(_fact(R, entry, _A.TYPE), AnatomyType.ILEAL_POUCH)


def pouch_route_possible(R: FactSet, session: Id) -> bool:
    """DECISIONS D325 (2): whether the approach of ``session`` is established, or possible, through a pouch - the
    record names the pouch route: facts.possibly over the approach (supported through_pouch; not established, pass 1's
    claim, a doubt's reading, a contradiction's side or an unrejected control's value names it, or an open denial,
    which leaves every route open) for any approach pass 1 claimed. Never a silent approach (it names no route, and
    every colonoscopy's approach may be silent), and never an ESTABLISHED negation: one of through_pouch rules the
    route out, and one of another approach (through the stoma, per anus) names no pouch - the stoma route's reading of
    it (``_stoma_reading``) is not this route's, as a pouch route needs a pouch named. Every 9.4 weakening keeps the
    value it reads (as claimed, or among the options) and turns an established negation into an open denial, so none
    turns it False."""
    approach = _fact(R, session, _A.APPROACH)
    return not facts_.silent(approach) and facts_.possibly(approach, Approach.THROUGH_POUCH)


def no_colon_possible(R: FactSet, session: Id | None) -> bool:
    """DECISIONS D325 (2) (L6B-2, high: an ileal pouch after a proctocolectomy reached per anus into the ileum gave 45380
    READY): whether a colon may NOT remain for a colonoscopy through the anus in ``session`` - a colonoscopy code needs a
    colon to traverse, and a small-bowel reach completes a colonoscopy only when a colon remains. True in the ruling's
    three cases, each read fail-closed: an anatomy entry may file the whole colon surgically absent
    (``colon_absent_possible``) - and, DECISIONS D327 (1), the anatomy may leave the colon gone otherwise: the entries
    that may be surgically absent may cover every segment, or an entry's subtype may be ileorectal or ileoanal
    (``whole_colon_absent_possible``, v8, v9 and v10); an entry may be an ileal pouch (``ileal_pouch_possible``); the
    session's approach is established or possible through a pouch (``pouch_route_possible``). With ``session`` None (the
    act's session not established) only the anatomy cases are read: they hold whatever the session, so no answer about
    it can release the code (D312 checker S3's principle); the approach is read once the session is known. Every 9.4
    weakening only widens each case (they read possibilities, never a value's absence), so none turns it False.
    DECISIONS D328 (1): the table's colon arm of the colonoscopy family (``_anatomy_contradicts``) - the anatomy cases
    beside its pouch arm, ``pouch_possible``, which every per-anus code reads."""
    return whole_colon_absent_possible(R) or pouch_possible(R, session)


def pouch_possible(R: FactSet, session: Id | None) -> bool:
    """DECISIONS D328 (1) (D325 (2)'s two pouch cases, read for every per-anus code of the route table): whether an
    anatomy entry may be an ileal pouch (``ileal_pouch_possible``) or - ``session`` known - the session's approach is
    established or possible through a pouch (``pouch_route_possible``). An ileal pouch is the ileum made into a reservoir
    once the colon and the rectum are gone, so beside one no colon, rectum or sigmoid may remain for a scope through the
    anus (a pouch endoscopy is 44385/44386). With ``session`` None only the anatomy is read: it holds whatever the
    session, so no answer about the session can release it. Every 9.4 weakening only widens each case."""
    if any(ileal_pouch_possible(R, entry) for entry in R.anatomy):
        return True
    return session is not None and pouch_route_possible(R, session)


# The landmarks of the colon (anatomy.Region.COLON): a stoma whose organ may be one of them may be a colostomy, which an
# ileoscopy through a stoma does not pass (DECISIONS D328 (1): it needs an ileal stoma).
_COLON_PLACES: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark if anatomy.region(landmark) is anatomy.Region.COLON)


def _stomas_passed(R: FactSet, session: Id | None) -> tuple[Id, ...]:
    """The stomas ``session``'s endoscope may have entered the bowel through: every anatomy entry whose type may be a
    stoma (facts.possibly) - only the one the session's through names when that is SUPPORTED naming an anatomy entry
    (none when that entry cannot be a stoma: the enteroscopy class's route part then holds the code itself)."""
    stomas = tuple(entry for entry in R.anatomy if facts_.possibly(_fact(R, entry, _A.TYPE), AnatomyType.STOMA))
    if session is not None:
        through = _fact(R, session, _A.THROUGH)
        if (through.result is Result.SUPPORTED and isinstance(through.value, Id)
                and through.value.family is IdFamily.ANATOMY):
            return tuple(entry for entry in stomas if entry == through.value)
    return stomas


def colonic_stoma_possible(R: FactSet, session: Id | None) -> bool:
    """DECISIONS D328 (1): whether a stoma ``session``'s endoscope may have passed through (``_stomas_passed``) may be a
    COLONIC stoma by what pass 1 filed - the route table's ileoscopy through a stoma (44380-44384) needs an ileal stoma.
    True when such an entry's organ is filed (not silent) and may be a colon place or a landmark naming no placeable
    organ (``_may_be`` over _COLON_PLACES and _NO_ORGAN: its supported place; not established, its claimed value, a
    reading, a side, an unrejected control's value, an open denial; any established negation). A silent organ files
    nothing against an ileal stoma - the fact pass never claims a stoma's organ, and an ileostomy whose organ pass 1 left
    empty stays as the enteroscopy class decides it. Every 9.4 weakening of an organ or of the through only widens it
    (an established through weakened reads every entry that may be a stoma)."""
    for entry in _stomas_passed(R, session):
        organ = _fact(R, entry, _A.ORGAN)
        if not facts_.silent(organ) and any(_may_be(organ, place) for place in _COLON_PLACES | _NO_ORGAN):
            return True
    return False


# DECISIONS D330 (1) (R5R-9): the landmarks an ileal stoma's organ may be - the ileum, its parts, and the small bowel
# that holds it (anatomy.compatible with the ileum).
ILEAL_PLACES: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark if anatomy.compatible(landmark, Landmark.ILEUM))


def ileal_stoma_contradicted(R: FactSet, session: Id | None) -> bool:
    """DECISIONS D328 (1) and D330 (1) (R5R-9): whether what is filed contradicts the ileal stoma an ileoscopy through a
    stoma (44380-44384) needs, read fail-closed - its route's own entry, which the path guard leaves to this rule:
    - a stoma the endoscope may have passed through may be colonic by what pass 1 filed (``colonic_stoma_possible``);
    - such a stoma's organ is FILED (not silent) and MAY lie outside the ileum (ILEAL_PLACES: a jejunostomy's, a
      gastrostomy's organ) - read in the hold direction only, as pass 1 filed it; a silent organ files nothing (Q6);
    - the session's reach MAY be a colon point at or past the cecum (AT_OR_PAST_CECUM; facts.possibly, as
      ``_colonic_route_witness`` and classes._reach read an open reach): the colon may have been traversed through the
      stoma, so the examination may be a colonoscopy through a stoma (44388/44389) - the mirror of D325 (2), held
      whatever the organ (with ``session`` None the reach is read once the session is known).
    DECISIONS D336 (1) (c) (L4P-3, L4P-4: P-MONO for every hold clause): each clause reads every value a member may be
    (``_may_be``), never only a supported value - an organ held only while it could lie NOWHERE in the ileum, and a reach
    held only on a SUPPORTED colonic point, each let one 9.4 weakening (an added ileal reading; a cecum made unresolved
    or doubted) release 44382. Read so, every 9.4 weakening only widens an organ, a reached point or the stomas passed
    (never makes an organ silent), so none turns it False; deleting the established colonic point leaves the reach the
    record would have had without it (SC-B's list-completeness residual). DECISIONS D342 (1) (a) (L4P8-3): the reach
    clause reads each reached member by the one predicate too (``_possibly_settled``), so a member pass 2 left
    unestablished (rejected, unclear, ...), pass 1 doubted or a failed check left open may be every point, the cecum
    among them; an established member reads its value (a reached point, or - established denied - none)."""
    if colonic_stoma_possible(R, session):
        return True
    for entry in _stomas_passed(R, session):
        organ = _fact(R, entry, _A.ORGAN)
        if not facts_.silent(organ) and any(_may_be(organ, place) for place in Landmark if place not in ILEAL_PLACES):
            return True
    return session is not None and any(_possibly_settled(member, point)  # D342 (1) (a): the one predicate (L4P8-3)
                                       for member in facts_.members(R, session, _A.REACHED) for point in AT_OR_PAST_CECUM)


def _stoma_entry(R: FactSet, session: Id, event: Id, group: Sequence[Kind]) -> HeldFact:
    """The through-stoma codes' anatomy requirement not met (no entry's type established stoma): the question on the
    first entry whose type leaves stoma possible (its reading's cause: a reading Fable may be asked - no question
    template in the probe, so the planner blocks it); with none, the table's own hold - no anatomy entry may be a stoma
    (a question about the session's anatomy, coding_rule:stoma_route, as LOWER's stoma class holds a missing entry): the
    document names no stoma, which no answer can supply (the coder's)."""
    for entry in R.anatomy:
        found = _fact(R, entry, _A.TYPE)
        if facts_.possibly(found, AnatomyType.STOMA):
            return _open(found, _PROCEDURE, _A.TYPE, entry, event, group, R, questions.coding_rule(_Rule.STOMA_ROUTE))
    return _route_hold(R, session, event)


def _table_hold(R: FactSet, subject: Id, event: Id) -> HeldFact:
    """The route table's own hold (``_route_hold``) about ``subject``: the session, or the act itself where its session
    is not established - the anatomy holds the code whatever the session, so no answer about the session can release it
    (D312 checker S3's principle)."""
    return _held(rq.fact_key(_PROCEDURE.fact), _PROCEDURE.rank, _Q, _A.TYPE, subject, None,
                 questions.coding_rule(_Rule.STOMA_ROUTE), _anchor(R, event))


def _route_hold(R: FactSet, session: Id, event: Id) -> HeldFact:
    """The route table's own hold: a question about the session's anatomy (procedure at RANK row 8, about no fact,
    coding_rule:stoma_route) that no answer can meet - the planner reads it ABSENT (asking's census: the route table's
    anatomy hold with no fact), so it reaches the coder. It holds a through-stoma code when the document names no entry
    that may be a stoma (``_stoma_entry``), and where DECISIONS D324 (5)'s colonic route is not met on facts no answer
    can change (``_colonic_route_witness``); and - DECISIONS D325 (2) - a colonoscopy code through the anus where a colon
    may not remain (``no_colon_possible``): the same hold and so the same words, as D320 (i) keeps the customer surface
    unchanged. DECISIONS D327 (1)'s cases (``whole_colon_absent_possible``) hold both ranges with it too, and DECISIONS
    D328 (1) every lower-GI code whose row the record contradicts (``_anus_route``, ``colonic_stoma_possible``) or that
    has no row."""
    return _table_hold(R, session, event)


def _anatomy_contradicts(needs: catalogue.RouteAnatomy, R: FactSet, session: Id | None) -> bool:
    """DECISIONS D328 (1): whether what the record files may contradict the anatomy a per-anus code needs, read
    fail-closed - for every per-anus code a pouch (``pouch_possible``: an entry that may be an ileal pouch, or an
    approach established or possible through one); for the colonoscopy family (a colon to traverse) an anatomy that may
    leave no colon too (``no_colon_possible``: D325 (2), D327 (1)). A rectum and sigmoid has no rectum-absent arm and no
    colon arm (D328 (1)): a sigmoidoscopy after a low anterior resection, or of the rectum an ileorectal anastomosis
    leaves, stays as before."""
    if needs is catalogue.RouteAnatomy.COLON:
        return no_colon_possible(R, session)
    return pouch_possible(R, session)


def _anus_route(needs: catalogue.RouteAnatomy, rule: questions.Rule, group: Sequence[Kind], R: FactSet,
                session: Id | None, event: Id) -> tuple[list[HeldFact], bool]:
    """DECISIONS D328 (1): a per-anus code's route (the route table's Approach.TRANSANAL rows) - its witnesses, and
    whether an established fact fails it. The record establishes the route through the anus unless the record may
    contradict it, read fail-closed in the ruling's order:
    - the session's approach established (supported) through a stoma: the class's explanation naming it (procedure,
      RANK row 8, ``rule``: coding_rule:stoma_route for the colonoscopy and sigmoidoscopy families, LOWER's own for its
      sigmoidoscopic and colonoscopic EUS classes) - F;
    - what is filed may contradict the anatomy the code needs (``_anatomy_contradicts``: a pouch for every per-anus
      code, a colon gone for the colonoscopy family): the table's own hold (``_route_hold``, the coder's);
    - a stoma that may exist (``stoma_possible``, D312 (5)): the approach's question (its reading's cause; ``rule``'s
      for an approach established otherwise, an established denial);
    otherwise nothing (the route holds). With ``session`` None (the act's session not established: SUPPORT row 6 asks
    it) only the anatomy is read, and it holds the code whatever the session (the table's hold about the act). Every 9.4
    weakening only keeps it held: each case reads possibilities, never a value's absence."""
    if session is None:
        return ([_table_hold(R, event, event)] if _anatomy_contradicts(needs, R, None) else []), False
    approach = _fact(R, session, _A.APPROACH)
    if facts_.holds(approach, Approach.THROUGH_STOMA):
        return [_fails(_PROCEDURE, True, _A.APPROACH, session, approach, rule, R, event)], True
    if _anatomy_contradicts(needs, R, session):
        return [_route_hold(R, session, event)], False
    if stoma_possible(R, session):
        return [_open(approach, _PROCEDURE, _A.APPROACH, session, event, group, R, questions.coding_rule(rule))], False
    return [], False


def _through_stoma_route(label: rq.Requirement | Tag, group: Sequence[Kind], R: FactSet, session: Id | None,
                         event: Id) -> Row:
    """The colonoscopy through a stoma (the route table's colonic-stoma rows of the colonoscopy family: DECISIONS D310
    (1), D324 (5), D325 (2), D327 (1)). T only when the session's approach is supported through_stoma, an anatomy
    entry's type is supported stoma and the route is colonic (``colonic_route``: no entry may file the colon surgically
    absent, nor may the anatomy leave it gone otherwise, and the stoma's organ is a colon segment or a colonic reach
    through it is established; else its witness, ``_colonic_route_witness``: the table's own hold, the coder's, or the
    open reach it rests on); another approach established, or through_stoma denied, is the explanation naming the
    approach (procedure, RANK row 8, coding_rule:stoma_route); an approach not established is the approach question (its
    reading's cause), beside the anatomy requirement when no entry is a stoma (``_stoma_entry``). A session not
    established is SUPPORT row 6's question (T here) - except on a document whose anatomy names no entry that may be a
    stoma, or may leave the colon gone (``whole_colon_absent_possible``): there no session the act may be in gives a
    colonic route, so the table's own hold about the act holds it whatever the session (the planner reads it ABSENT)."""
    if session is None:
        if (not any(facts_.possibly(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) for entry in R.anatomy)
                or whole_colon_absent_possible(R)):
            return _row(label, [_table_hold(R, event, event)])
        return _row(label, [])
    approach = _fact(R, session, _A.APPROACH)
    stoma = any(facts_.holds(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) for entry in R.anatomy)
    if facts_.holds(approach, Approach.THROUGH_STOMA):
        if not stoma:
            return _row(label, [_stoma_entry(R, session, event, group)])
        witness = _colonic_route_witness(R, session, event, group)
        return _row(label, [] if witness is None else [witness])
    if (approach.result is Result.SUPPORTED and isinstance(approach.value, Approach)) or facts_.denied(
            approach, Approach.THROUGH_STOMA):
        return _row(label, [_fails(_PROCEDURE, True, _A.APPROACH, session, approach, _Rule.STOMA_ROUTE, R, event)],
                    failed=True)
    witnesses = [_open(approach, _PROCEDURE, _A.APPROACH, session, event, group, R,
                       questions.coding_rule(_Rule.STOMA_ROUTE))]
    if not stoma:
        witnesses.append(_stoma_entry(R, session, event, group))
    return _row(label, witnesses)


# --- the lower-GI path guard (DECISIONS D330 (1)): fail-closed by construction ---------------------------------------
# Four rounds each found the next post-surgical lower-GI shape a listed arm missed, so D330 (1) inverts the default: an
# unknown shape costs a hold, never a false READY. After every arm of a route row (``_row_lower_route``, ``_row_lower``),
# a lower-GI code - every row of catalogue.LOWER_ROUTES - is held with the table's own hold (``_table_hold``, an
# existing reason: D320 (i)) unless EVERY anatomy entry of the document is, for that code's route, (i) the entry the
# route itself uses (``route_entries``) or (ii) a match for a row of the ONE finite typed RULED HARMLESS SET for its
# route family (catalogue.HARMLESS: ``harmless``); and a per-anus code's own route is the guard's too (R5R-7, R5R-8:
# ``_anus_route_contradicted``). It only holds: it runs where the arms left the route met (or only the open reach the
# colonic route rests on), never releases what an arm held, and reads only pass 1's anatomy entries, the session's
# approach and through and the colon's cover - none of them askable (asking.FACT_ATTRIBUTES), so no answer lifts it
# (D324 (4)).


@dataclass(frozen=True, slots=True)
class ReleaseReading:
    """What a release may rest on for one anatomy entry (DECISIONS D336 (1) (b); ``release_reading``): the ONE claim the
    contract controls that decides the entry's shape - ``decided_by`` (Attribute.TYPE: a type in catalogue.
    CONTROLLED_TYPES; Attribute.ORGAN: the organ claim of an entry filed surgically absent, the absence form; Attribute.
    SUBTYPE: a subtype in catalogue.CONTROLLED_SUBTYPES, which names an anastomosis) and ``values``, every value that
    claim may be (``_may_be``) - with what the other fields may be, read only to HOLD: ``organs`` (each possible value of
    a filed organ; None for a silent one) and ``joins`` (each member's possible values)."""
    decided_by: Attribute
    values: frozenset[AnatomyType | AnastomosisSubtype | Landmark]
    organs: frozenset[Landmark] | None
    joins: tuple[frozenset[Landmark], ...]


def release_reading(R: FactSet, entry: Id) -> ReleaseReading | None:
    """DECISIONS D336 (1) (b), the release direction's reading of anatomy entry ``entry``: every attribute is read by its
    widest possible value unless the contract CONTROLS it, so an entry's shape is decided only by a controlled claim, and
    None - the widest reading, which no row of the harmless set holds - when no controlled claim decides it, or when its
    filing contradicts the claim that would (D336 (1) (e): no attribute decides alone against another one that
    contradicts it). Each field is read by ``_may_be`` - DECISIONS D342 (1) (a): a claim narrows only when established
    through its control or unappraised; in every other settled state (pass 2 asked and did not establish it, pass 1
    doubted or contradicted it, a check failed) it is every value, so it decides nothing:
    - a FILED subtype names an anastomosis: it decides the shape (Attribute.SUBTYPE) when every subtype it may be is one
      the contract controls (catalogue.CONTROLLED_SUBTYPES - OTHER has no sibling) and the entry's type may only be an
      anastomosis (catalogue.SUBTYPE_TYPE: a type filed otherwise, silent, contradicted or rejected contradicts it, as an
      uncontrolled type is never its own release); any other filed subtype - beside an absence, a stoma, a pouch, or a
      subtype that may be OTHER - leaves the entry undecided;
    - else an entry whose type may only be surgically absent (catalogue.ABSENCE_TYPE) is decided by its organ claim, the
      absence form (Attribute.ORGAN: "The <organ> is surgically absent", controlled by its negation; the type has no
      control of its own): every place its FILED organ may be - a silent organ decides nothing;
    - else a type that may only be a type the contract controls (catalogue.CONTROLLED_TYPES: a stoma, an ileal pouch, a
      gastric pouch) decides it (Attribute.TYPE).
    A type with no control of its own (an anastomosis without a controlled subtype; a Roux limb, a bypass, another
    alteration), a joins list (no control: read only to hold) and a silent field never decide a release. Every 9.4
    weakening only widens what a field may be, so it turns a decided reading into a wider one or into None, never the
    reverse."""
    type_, subtype, organ = (_fact(R, entry, attribute) for attribute in (_A.TYPE, _A.SUBTYPE, _A.ORGAN))
    types = frozenset(value for value in AnatomyType if _may_be(type_, value))
    subtypes = (frozenset() if facts_.silent(subtype)
                else frozenset(value for value in AnastomosisSubtype if _may_be(subtype, value)))
    organs = None if facts_.silent(organ) else frozenset(value for value in Landmark if _may_be(organ, value))
    joins = tuple(frozenset(value for value in Landmark if _may_be(member, value))
                  for member in facts_.members(R, entry, _A.JOINS))
    if not types or (organs is not None and not organs):
        return None
    if not facts_.silent(subtype):
        if subtypes and subtypes <= catalogue.CONTROLLED_SUBTYPES and types == {catalogue.SUBTYPE_TYPE}:
            return ReleaseReading(_A.SUBTYPE, frozenset(subtypes), organs, joins)
        return None
    if types == {catalogue.ABSENCE_TYPE}:
        return ReleaseReading(_A.ORGAN, frozenset(organs), organs, joins) if organs is not None else None
    if types <= catalogue.CONTROLLED_TYPES:
        return ReleaseReading(_A.TYPE, frozenset(types), organs, joins)
    return None


def subtype_ends_contradicted(reading: ReleaseReading) -> bool:
    """DECISIONS D336 (1) (e) (an impossible join; L6O-3, final check 5): whether an entry decided by its subtype files an
    organ or a joins member the subtype cannot join - for EVERY subtype it may be (a reading of each must hold), some
    possible place of its filed organ or of a joins member that names a placeable organ lies outside that subtype's own
    ends (SUBTYPE_ENDS; a landmark naming no placeable organ - a colonic J-pouch's pouch - names one of its ends). An
    upper subtype at the rectum, or a duodenum joined to the rectum under any subtype, contradicts it; an ileocolic
    anastomosis joining the ileum and the colon does not. Read only to HOLD; every 9.4 weakening widens a place or the
    subtypes read, so none turns it False."""
    if reading.decided_by is not _A.SUBTYPE:
        return False
    fields = [*reading.joins, *([reading.organs] if reading.organs is not None else [])]
    for subtype in reading.values:
        ends = SUBTYPE_ENDS.get(subtype) if isinstance(subtype, AnastomosisSubtype) else None
        if ends is None or any(place not in ends and place not in _NO_ORGAN for found in fields for place in found):
            return True
    return False


def harmless_row(reading: ReleaseReading, row: catalogue.Harmless) -> bool:
    """DECISIONS D330 (1), D336 (1): whether an entry read so (``release_reading``) matches ``row`` of the ruled harmless
    set - the row releases on the claim that decides it (``decided_by``) and every value that claim may be lies within
    the row's ``values``; read only to hold, a filed organ's every possible value lies within ``organs`` and every
    possible place of each joins member within ``joins``. Every 9.4 weakening only widens what a field may be (none makes
    a filed field silent or deletes a joins member), so none turns a mismatch into a match."""
    if reading.decided_by is not row.decided_by or not reading.values <= row.values:
        return False
    if reading.organs is not None and not reading.organs <= row.organs:
        return False
    return all(member <= row.joins for member in reading.joins)


def harmless(R: FactSet, entry: Id, needs: catalogue.RouteAnatomy) -> bool:
    """DECISIONS D330 (1), completed by D336 (1): whether anatomy entry ``entry`` is harmless for the route family
    ``needs`` - EVERY reading it may have lies within a row of catalogue.HARMLESS[needs]: a controlled claim decides its
    shape (``release_reading``: every uncontrolled attribute at its widest), its subtype's own ends hold what it files
    (``subtype_ends_contradicted``), it matches a row (``harmless_row``), and, for every family but those of
    catalogue.HARMLESS_ILEUM_BELOW (the pouch's), it may not join the ileum below the colon
    (``ileum_below_colon_possible``: its subtype, or its joins with the ends they do not name)."""
    if needs not in catalogue.HARMLESS_ILEUM_BELOW and ileum_below_colon_possible(R, entry):
        return False
    reading = release_reading(R, entry)
    if reading is None or subtype_ends_contradicted(reading):
        return False
    return any(harmless_row(reading, row) for row in catalogue.HARMLESS[needs])


# The anatomy type of the entry each route itself passes (D330 (1) (i)): a stoma, an ileal pouch. A per-anus route
# passes none.
_ROUTE_ENTRY_TYPE: Mapping[Approach, AnatomyType] = MappingProxyType({
    Approach.THROUGH_STOMA: AnatomyType.STOMA, Approach.THROUGH_POUCH: AnatomyType.ILEAL_POUCH})


def route_entries(found: catalogue.LowerRoute, R: FactSet, session: Id | None) -> frozenset[Id]:
    """DECISIONS D330 (1) (i): the anatomy entry the route of ``found`` itself uses - for a through-stoma or a pouch row,
    the stoma or the pouch the session ESTABLISHED it entered through: the entry the session's through names when it is
    SUPPORTED, else the one entry that may be of the route's type (``_possible_as_filed``) and that the through may name
    (a silent through may name any) - each only when its type is SUPPORTED the route's type (a type the contract
    controls: catalogue.CONTROLLED_TYPES); none when that is not one entry (two stomas and a through not established:
    neither is exempt). With ``session`` None (the act's session not established) every entry that may be of the route's
    type, since any of them may be the route's own once the session is known (the guard then holds only what holds
    whatever the session). A per-anus route uses none. Every 9.4 weakening of the through or of a type only widens what
    may be named, so an entry exempt on the weakened FactSet was exempt before or the set is no longer one entry.
    DECISIONS D336 (1) (b): an exemption is the release direction, so it reads an entry's type as filed - a claim pass 2
    rejected is never read wider here, where a wider reading would exempt more."""
    wanted = _ROUTE_ENTRY_TYPE.get(found.route)
    if wanted is None:
        return frozenset()
    possible = [entry for entry in R.anatomy if _possible_as_filed(_fact(R, entry, _A.TYPE), wanted)]
    if session is None:
        return frozenset(possible)
    through = _fact(R, session, _A.THROUGH)
    if (through.result is Result.SUPPORTED and isinstance(through.value, Id)
            and through.value.family is IdFamily.ANATOMY):
        named = [through.value]
    else:
        named = [entry for entry in possible if facts_.possibly(through, entry)]
    if len(named) == 1 and facts_.holds(_fact(R, named[0], _A.TYPE), wanted):
        return frozenset(named)
    return frozenset()


def _named_by(R: FactSet, through: Fact) -> tuple[Id, ...]:
    """The anatomy entries a session's ``through`` may name (``_may_be``: its supported entry; not established, its
    claimed entry, a reading, a side; every entry for an open denial or an established negation), an entry the FactSet
    does not hold among them (its type reads as silent: it may be anything). A silent through names none."""
    if facts_.silent(through):
        return ()
    ids = [*R.anatomy, *(value for value in (through.value, *through.options)
                         if isinstance(value, Id) and value.family is IdFamily.ANATOMY and value not in R.anatomy)]
    return tuple(entry for entry in ids if _may_be(through, entry))


def _stoma_or_pouch_possible(R: FactSet, entry: Id) -> bool:
    """Whether anatomy entry ``entry`` may be a stoma or a pouch (D330 (1), R5R-8): its type may be a stoma, an ileal
    pouch or a gastric pouch (``_may_be``: a silent type may be anything), or its organ is filed at a landmark naming a
    stoma or a pouch (an S-pouch filed as another alteration)."""
    found = _fact(R, entry, _A.TYPE)
    organ = _fact(R, entry, _A.ORGAN)
    return (any(_may_be(found, value) for value in (AnatomyType.STOMA, AnatomyType.ILEAL_POUCH,
                                                    AnatomyType.GASTRIC_POUCH))
            or (not facts_.silent(organ) and any(_may_be(organ, value) for value in (Landmark.STOMA, Landmark.POUCH))))


def _anus_route_contradicted(R: FactSet, session: Id) -> bool:
    """DECISIONS D330 (1): the route's own entry belongs to the guard too - whether the record contradicts a per-anus
    route in ``session``: its approach is filed or supported as anything but per anus (R5R-7: ``_may_be`` over every
    other approach - supported, claimed, a reading, a side, an open denial, an established negation or a claim pass 2
    rejected names one); or its through may name an entry that may be a stoma or a pouch (R5R-8:
    ``_stoma_or_pouch_possible``).

    DECISIONS D336 (1) (b) and (e) (final check 4): a per-anus approach is never ESTABLISHED through a control - the
    contract gives per anus no contrary (catalogue.CONTROLLED_APPROACHES: oral, through a stoma, through a pouch) - so a
    supported per-anus approach is a single verdict, read at its widest, as a silent one is: it reads per anus only when
    no entry may be a stoma of the lower tract or an ileal pouch, and the approach may not be through a pouch (int6's
    reading of a silent approach: ``lower_stoma_possible`` over every entry whose type may be a stoma, ``pouch_possible``).
    So beside a stoma, its organ never established (D330 (d)), no per-anus code is released on the approach alone. Every
    9.4 weakening only widens what the approach, a type or the through may be, so none turns it False."""
    approach = _fact(R, session, _A.APPROACH)
    if not facts_.silent(approach) and any(_may_be(approach, value) for value in Approach
                                           if value is not Approach.TRANSANAL):
        return True
    if not (approach.result is Result.SUPPORTED and approach.value in catalogue.CONTROLLED_APPROACHES):
        if (any(_may_be(_fact(R, entry, _A.TYPE), AnatomyType.STOMA) and lower_stoma_possible(R, entry)
                for entry in R.anatomy) or pouch_possible(R, session)):
            return True
    return any(_stoma_or_pouch_possible(R, entry) for entry in _named_by(R, _fact(R, session, _A.THROUGH)))


def colonic_route_stoma_contradicted(R: FactSet, session: Id | None) -> bool:
    """DECISIONS D336 (1) (e) (L6O-4: a route the filing contradicts; R5R-9's closure for the colonoscopy through a stoma,
    44388-44408): whether a stoma the endoscope may have passed through (``_stomas_passed``) files an organ that MAY lie
    outside the lower tract's stoma organs (LOWER_STOMA_ORGANS: the colon's and the ileum's places; a landmark naming no
    placeable organ may lie anywhere) - no colonoscope passes a gastrostomy, a duodenostomy or a jejunostomy, whatever
    reach is filed through it. Read in the hold direction only, as pass 1 filed it (``_may_be``: every value it may be;
    P-MONO), so an unverified organ may hold but never release (D330 (d)); a silent organ files nothing. With
    ``session`` None (the act's session not established) it holds only what holds whatever the session (D312 checker
    S3's principle, as ``route_entries`` exempts every stoma the session may enter through): every such stoma files
    one - the code is held then by SUPPORT row 6's session question whatever this reads, so it decides only whether that
    question may release it. With the session known, every 9.4 weakening only widens an organ or the stomas passed (a
    weakened through reads every entry that may be a stoma), so none turns it False."""
    def outside(entry: Id) -> bool:
        organ = _fact(R, entry, _A.ORGAN)
        return not facts_.silent(organ) and any(_may_be(organ, place) for place in Landmark
                                                if place not in LOWER_STOMA_ORGANS)

    stomas = _stomas_passed(R, session)
    if session is None:
        return bool(stomas) and all(outside(entry) for entry in stomas)
    return any(outside(entry) for entry in stomas)


def _route_may_use(found: catalogue.LowerRoute, R: FactSet, session: Id | None) -> tuple[Id, ...]:
    """DECISIONS D342 (1) (c): the anatomy entries that may be the route's OWN entry - for a through-stoma or a pouch row
    (catalogue.ROUTE_OWN), every entry whose type may be the route's type (``_may_be``: the one predicate) and that the
    session's through may name (``_may_be``; a silent through may name any) - only the entry the through names when it is
    SUPPORTED naming an anatomy entry. With ``session`` None every entry whose type may be the route's type. A per-anus
    route uses none."""
    own = catalogue.ROUTE_OWN.get(found.needs)
    if found.route is Approach.TRANSANAL or own is None:
        return ()
    entries = tuple(entry for entry in R.anatomy if _may_be(_fact(R, entry, _A.TYPE), own.type))
    if session is None:
        return entries
    through = _fact(R, session, _A.THROUGH)
    if (through.result is Result.SUPPORTED and isinstance(through.value, Id)
            and through.value.family is IdFamily.ANATOMY):
        return tuple(entry for entry in entries if entry == through.value)
    return tuple(entry for entry in entries if _may_be(through, entry))


def own_entry_outside(R: FactSet, entry: Id, own: catalogue.OwnAnatomy) -> bool:
    """DECISIONS D342 (1) (c) (D336 (1) (e)'s unbuilt part: L4P8-2, L9-3, the final check's finding 2): whether anatomy
    entry ``entry``, read as the route's own entry, files a field that may lie outside its type's own anatomy
    (``own``: catalogue.ROUTE_OWN) - read by (a) and (b), in the hold direction like every other entry:
    - a FILED organ some value of which (``_may_be``) lies outside ``own.organs`` (a silent organ files nothing);
    - a FILED subtype some value of which lies outside ``own.subtypes`` (a stoma joins nothing: every filed subtype; an
      ileal pouch, its own ileorectal or ileoanal join);
    - a joins member some place of which lies outside ``own.joins`` - the own entry's type is a controlled type
      established as its own shape (its route requires it), so its list is read as filed, as its own join (D342 (1) (b)).
    Every 9.4 weakening only widens what a field may be, so none turns it False."""
    organ, subtype = _fact(R, entry, _A.ORGAN), _fact(R, entry, _A.SUBTYPE)
    if not facts_.silent(organ) and any(_may_be(organ, place) for place in Landmark if place not in own.organs):
        return True
    if not facts_.silent(subtype) and any(_may_be(subtype, value) for value in AnastomosisSubtype
                                          if value not in own.subtypes):
        return True
    return any(_may_be(member, place) for member in facts_.members(R, entry, _A.JOINS) for place in Landmark
               if place not in own.joins)


def route_own_entry_contradicted(found: catalogue.LowerRoute, R: FactSet, session: Id | None) -> bool:
    """DECISIONS D342 (1) (c), THE ROUTE'S OWN ENTRY: whether the entry the route of ``found`` itself uses is not
    certain - its established type gives the route, and its organ, subtype and joins must lie within that type's own
    anatomy (``own_entry_outside``); read in the hold direction, every entry that may be the route's own
    (``_route_may_use``) is read so, and one that files a field outside its type's anatomy holds. With ``session`` None
    (the act's session not established) it holds only what holds whatever the session (D312 checker S3's principle, as
    ``colonic_route_stoma_contradicted`` reads its stomas): every such entry files one. A per-anus route has no own
    entry."""
    own = catalogue.ROUTE_OWN.get(found.needs)
    if found.route is Approach.TRANSANAL or own is None:
        return False
    entries = _route_may_use(found, R, session)
    if session is None:
        return bool(entries) and all(own_entry_outside(R, entry, own) for entry in entries)
    return any(own_entry_outside(R, entry, own) for entry in entries)


def _accepted_approaches(found: catalogue.LowerRoute) -> frozenset[Approach]:
    """The approaches the code's own row or class accepts (DECISIONS D336 (1) (a)): its route's, and, for a route that
    passes an entry of a type, the approaches that enter an entry of that type directly (classes.ENTRY_APPROACHES - D219:
    per anus, the faithful filing of a pouchoscopy, for an ileal pouch). Another approach supported fails the code's own
    row or class (an established failure, the code held anyway)."""
    own = _ROUTE_ENTRY_TYPE.get(found.route)
    entering = classes.ENTRY_APPROACHES.get(own, frozenset()) if own is not None else frozenset()
    return frozenset({found.route}) | entering


def path_guard(found: catalogue.LowerRoute, R: FactSet, session: Id | None) -> bool:
    """DECISIONS D330 (1), THE LOWER-GI PATH GUARD, completed by D336 (1): whether the route row of a lower-GI code whose
    route table row is ``found`` holds with the table's own hold - unless EVERY anatomy entry of the document is, for the
    row's route, (i) the entry the route itself uses (``route_entries``) or (ii) harmless for its route family
    (``harmless``: every reading it may have within a row of catalogue.HARMLESS[found.needs], its shape decided by a
    controlled claim); for a family beside which the colon may not be gone as a whole (not in
    catalogue.HARMLESS_WHOLE_COLON), the entries that may be surgically absent may not cover the colon either
    (``segments_absent_possible``: D327 (1), a side counts as its segments); a per-anus route may not be contradicted by
    its own approach or through (``_anus_route_contradicted``, ``session`` known); and a colonoscopy through a stoma's
    stoma may not file an organ outside the lower tract (``colonic_route_stoma_contradicted``, D336 (1) (e)).
    Fail-closed by construction: a shape the harmless set omits holds.

    DECISIONS D336 (1) (a) (L4P-1; final check 1): no early return - the guard reads every anatomy entry whatever the
    session's approach. The only exemption is an established FAILURE of the code's own row or class on the established
    approach: a through-stoma or pouch row whose session's approach is SUPPORTED at one neither its row nor its class
    accepts (``_accepted_approaches``) adds nothing - the code is held by that explanation anyway (the enteroscopy
    class's, the colonoscopy through a stoma's own row, LOWER's stoma class's), so its item stays it. Per anus, which the
    pouch class accepts (D219), is no such failure: a pouchoscopy per anus reads every entry. Every 9.4 weakening only
    widens what each field may be (a weakened approach no longer establishes another route), so none turns it False.

    DECISIONS D342 (1): every field it reads is read by the one predicate (``settled_narrows``, through ``_may_be``); a
    filed joins list names an anastomosis whatever the entry's uncontrolled type (``joins_ileum_below_colon_possible``);
    and the route's own entry - exempt from the harmless set (``route_entries``) - is read in the hold direction too: its
    organ, subtype and joins within its type's own anatomy (``route_own_entry_contradicted``)."""
    if found.route is not Approach.TRANSANAL and session is not None:
        approach = _fact(R, session, _A.APPROACH)
        if approach.result is Result.SUPPORTED and approach.value not in _accepted_approaches(found):
            return False  # an approach the code's own row or class fails on is established: held by it anyway
    own = route_entries(found, R, session)
    if any(entry not in own and not harmless(R, entry, found.needs) for entry in R.anatomy):
        return True
    if found.needs not in catalogue.HARMLESS_WHOLE_COLON and segments_absent_possible(R):
        return True
    if found.needs is catalogue.RouteAnatomy.COLONIC_STOMA and colonic_route_stoma_contradicted(R, session):
        return True
    if route_own_entry_contradicted(found, R, session):  # DECISIONS D342 (1) (c): the route's own entry
        return True
    return found.route is Approach.TRANSANAL and session is not None and _anus_route_contradicted(R, session)


def _guarded(row: Row, found: catalogue.LowerRoute, R: FactSet, session: Id | None, event: Id) -> Row:
    """``row`` (a route row its arms decided) with the path guard (``path_guard``) after every arm: where the arms left
    the route met - no witness, or only the open reach the colonic route rests on (a question whose true answer an
    unknown shape could still hold: the guard's hold beside it blocks the candidate, asking.plan's releasable filter) -
    the table's own hold about the session (about the act while its session is not established) is added when the guard
    holds. A row an arm held otherwise (an established failure, a hold, another question) is returned as it was: the
    guard never releases and never re-words an arm's hold."""
    if row.truth is Truth.F or any(held.attribute is not _A.REACHED for held in row.witnesses):
        return row
    if not path_guard(found, R, session):
        return row
    hold = _table_hold(R, session if session is not None else event, event)
    return _row(row.requirement, [*row.witnesses, hold]) if hold not in row.witnesses else row


def _row_lower_route(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """DECISIONS D328 (1): the lower-GI route table's row (catalogue.LOWER_ROUTES) over one supporting act of a lower-GI
    endoscopy code (catalogue.lower_gi) other than the lower EUS codes (LOWER's own row reads theirs, ``_row_lower``): a
    colonoscopy code's under its COLFULL row (the colonoscopy route table of D310 (1), whose rows these are), a
    sigmoidoscopy's and an enteroscopy's (through a stoma or a pouch) under the table's own id (Requirement.ROUTE_TABLE).
    Dispatched on the code's row:
    - per anus: ``_anus_route`` (the colonoscopy family a colon to traverse, the sigmoidoscopy family a rectum and
      sigmoid);
    - through a stoma, a colonic stoma: ``_through_stoma_route`` (the colonoscopy family);
    - through a stoma, an ileal stoma (the ileoscopy, whose route the enteroscopy class establishes: engine/classes): the
      table's own hold when a stoma the endoscope may have passed through may be colonic by what is filed
      (``colonic_stoma_possible``), whatever the session;
    - through a pouch: nothing (the enteroscopy class's route establishes the pouch).
    A lower-GI code the table declares no row for holds with the table's own hold (the completeness test fails first).

    DECISIONS D330 (1): the ileoscopy's ileal stoma reads its own stoma's filed organ and the reach through it too
    (``ileal_stoma_contradicted``, R5R-9), and after every arm the lower-GI path guard (``_guarded``, ``path_guard``)
    holds the row with the table's own hold unless every anatomy entry is the route's own or harmless for its family."""
    label: rq.Requirement | Tag = Tag.COLFULL if c.has(Tag.COLFULL) else rq.Requirement.ROUTE_TABLE
    found = catalogue.lower_route(c.code)
    session = _session(R, event)
    if found is None:
        return _row(label, [_table_hold(R, session if session is not None else event, event)])
    return _guarded(_route_arms(label, found, group, R, session, event), found, R, session, event)


def _route_arms(label: rq.Requirement | Tag, found: catalogue.LowerRoute, group: Sequence[Kind], R: FactSet,
                session: Id | None, event: Id) -> Row:
    """``_row_lower_route``'s arms, dispatched on the code's row ``found`` (its docstring), before the path guard."""
    if found.route is Approach.TRANSANAL:
        witnesses, failed = _anus_route(found.needs, _Rule.STOMA_ROUTE, group, R, session, event)
        return _row(label, witnesses, failed)
    if found.needs is catalogue.RouteAnatomy.COLONIC_STOMA:
        return _through_stoma_route(label, group, R, session, event)
    if found.needs is catalogue.RouteAnatomy.ILEAL_STOMA and ileal_stoma_contradicted(R, session):
        return _row(label, [_table_hold(R, session if session is not None else event, event)])
    return _row(label, [])


# The route row's name the earlier rounds' tests read (D310 (1)'s colonoscopy route table: its rows are the table's now).
_row_colon_route = _row_lower_route


def _row_yield(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """YIELD (43264; D106): module docstring."""
    found = _fact(R, event, _A.YIELD)
    if found.result is Result.CONTRADICTED:
        return _row(Tag.YIELD, [_held(rq.fact_key(rq.FactKey.CONFLICT, Kind.STONE_EXTRACTION), rq.Rank.CONFLICT, _Q,
                                      _A.YIELD, event, found, questions.cause_of(found), _quoted(found, R, event))])
    if found.result is Result.SUPPORTED and isinstance(found.value, Material) and found.value in _RETRIEVED:
        return _row(Tag.YIELD, [])
    if found.result is Result.NEGATED:
        return _row(Tag.YIELD, [_fails(_YIELD, True, _A.YIELD, event, found, _Rule.YIELD, R, event)], failed=True)
    return _row(Tag.YIELD, [_open(found, _YIELD, _A.YIELD, event, event, group, R,
                                  questions.coding_rule(_Rule.YIELD))])


def _row_cause(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """CAUSE (every code covering the bleeding control): module docstring."""
    purpose = _fact(R, event, _A.PURPOSE)
    cause = _fact(R, event, _A.CAUSE)
    conflict = _contradicted((purpose, cause))
    if conflict is not None:  # its own attribute: a contradicted purpose is no conflict about the cause (F4)
        return _row(Tag.CAUSE, [_open(conflict, _CAUSE, _A.PURPOSE if conflict is purpose else _A.CAUSE, event, event,
                                      group, R)])
    if facts_.holds(purpose, Purpose.PROPHYLAXIS):
        return _row(Tag.CAUSE, [_fails(_BUNDLED, True, _A.PURPOSE, event, purpose, _Rule.CAUSE, R, event)],
                    failed=True)
    if not facts_.holds(purpose, Purpose.HEMOSTASIS):
        return _row(Tag.CAUSE, [_open(purpose, _CAUSE, _A.PURPOSE, event, event, group, R,
                                      questions.coding_rule(_Rule.CAUSE))], failed=facts_.established(purpose))
    if facts_.holds(cause, Cause.ACT_OF_THIS_SESSION):
        return _row(Tag.CAUSE, [_fails(_BUNDLED, True, _A.CAUSE, event, cause, _Rule.CAUSE, R, event)], failed=True)
    if cause.result is Result.SUPPORTED and isinstance(cause.value, Cause) and cause.value in _BLEEDING_CAUSES:
        return _row(Tag.CAUSE, [])
    return _row(Tag.CAUSE, [_open(cause, _CAUSE, _A.CAUSE, event, event, group, R,
                                  questions.coding_rule(_Rule.CAUSE))])


def _wanted(R: FactSet, event: Id) -> frozenset[Kind]:
    """The counterpart kinds of a stent act (XCHG; _COUNTERPARTS) over every kind it may be as a candidate."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    return frozenset(kind for own in kinds for kind in _COUNTERPARTS.get(own, frozenset()))


def counterparts(R: FactSet, event: Id) -> tuple[Id, ...]:
    """XCHG (D105, D127): the filed possibly-performed counterparts of a stent act - a stent removal or exchange beside a
    placement, a placement or exchange beside a removal - that nothing sets apart: positive (4.4), possibly of a
    counterpart kind, and neither both ducts supported and different nor both sessions supported and different. Its
    kept unlisted counterparts: ``unlisted_counterparts``."""
    wanted = _wanted(R, event)
    if not wanted:
        return ()
    duct, session = _fact(R, event, _A.TARGET_DUCT), _session(R, event)
    out: list[Id] = []
    for other in R.events:
        if other == event or not positive(R, other):
            continue
        if not facts_.possible_kinds(R, other, of_family=False) & wanted:
            continue
        theirs = _fact(R, other, _A.TARGET_DUCT)
        if (duct.result is Result.SUPPORTED and theirs.result is Result.SUPPORTED and duct.value != theirs.value):
            continue
        other_session = _session(R, other)
        if session is not None and other_session is not None and session != other_session:
            continue
        out.append(other)
    return tuple(out)


def unlisted_counterparts(R: FactSet, event: Id) -> tuple[UnlistedStatement, ...]:
    """XCHG's synthetic counterparts of a stent act (D216, XCHG's "no possibly-performed counterpart" first; refute-4a-r2
    P1): every kept unlisted act (3.2.6 rule 3's synthetic doubted act, possibly performed) or doubt (possibly performed
    too: refute-r4a-r1 F1; ``synthetic_possible``) that may be of a counterpart kind (``synthetic_kinds``) and may be
    in the act's session (``synthetic_in``), in FactSet.unlisted's order. An unlisted entry has no duct, so nothing sets
    it apart by duct: "The existing biliary stent was removed. A new 10 Fr plastic stent was placed." with only the
    placement filed and the removal kept as an unlisted act holds 43274, as the same removal filed in doubt or with its
    duct unknown does - and as "It is unclear whether the old biliary stent was removed." kept as an unlisted doubt
    does."""
    wanted = _wanted(R, event)
    if not wanted:
        return ()
    session = _session(R, event)
    return tuple(entry for entry in synthetic_possible(R)
                 if synthetic_kinds(entry) & wanted and synthetic_in(R, entry, session))


def _same_duct(R: FactSet, one: Id, other: Id) -> bool:
    first, second = _fact(R, one, _A.TARGET_DUCT), _fact(R, other, _A.TARGET_DUCT)
    return (first.result is Result.SUPPORTED and second.result is Result.SUPPORTED and first.value is not None
            and first.value == second.value)


def _stent_name(claimed: Kind | None, possible: frozenset[Kind], wanted: frozenset[Kind]) -> Kind:
    """The stent kind an exchange question names an act by: its claimed (or stated) kind when that is one of ``wanted``,
    else the first of ``wanted``, in Kind's order, that it may be (it is read as a counterpart only because it may be
    one), else the first of ``wanted`` (the step's NOTES, question Q4)."""
    if claimed is not None and claimed in wanted:
        return claimed
    ordered = [kind for kind in Kind if kind in wanted]
    return next((kind for kind in ordered if kind in possible), ordered[0])


def _filed_side(R: FactSet, event: Id, wanted: frozenset[Kind]) -> questions.Side:
    """A filed act as an exchange question names it: its stent kind (``_stent_name``), its anchor, its id."""
    kind = _stent_name(questions.act_kind(R, event, ()), facts_.possible_kinds(R, event, of_family=False), wanted)
    return questions.Side(kind, _anchor(R, event), event)


def _unlisted_side(entry: UnlistedStatement, wanted: frozenset[Kind]) -> questions.Side:
    """A kept unlisted act as an exchange question names it: its stated stent kind (``_stent_name``), its own units, no
    id."""
    return questions.Side(_stent_name(entry.kind, synthetic_kinds(entry), wanted), tuple(sorted(set(entry.units))))


def _wanted_of(kind: Kind) -> frozenset[Kind]:
    """The kinds an exchange question may name a stent act's counterpart by: _COUNTERPARTS', else the other stent
    kinds."""
    return _COUNTERPARTS.get(kind, _STENT_KINDS - {kind})


def _duct_hold(unknown: questions.Side, known: questions.Side, R: FactSet) -> tuple[HeldFact, questions.Exchange]:
    """XCHG's duct question (act_target, rank 11; D225, refute-4a-r2 P6): about the act whose duct is NOT established
    (``unknown``: its subject and its duct fact's result; no subject and no result for a kept unlisted act, which has
    no duct), quoting both acts, with the Exchange the item's two-act form (wording's same_duct) names."""
    spans = tuple(sorted(set(unknown.spans) | set(known.spans)))
    duct = _fact(R, unknown.event, _A.TARGET_DUCT) if unknown.event is not None else None
    held = _held(rq.fact_key(_ACT_TARGET.fact), _ACT_TARGET.rank, _Q, _A.TARGET_DUCT, unknown.event, duct,
                 questions.coding_rule(_Rule.EXCHANGE), spans)
    return held, questions.Exchange(unknown, known)


def _filed_exchange(R: FactSet, event: Id, own: frozenset[Kind], other: Id,
                    theirs: frozenset[Kind] | None = None) -> tuple[HeldFact, questions.Exchange | None]:
    """XCHG's hold of a stent act ``event`` (named within ``own``) beside a filed counterpart ``other`` (within
    ``theirs``, by default the counterparts of ``event``'s name): the duct question about the act whose duct is not
    supported - ``event``'s own when neither is - while the two ducts are not both supported and equal; else whether the
    two were one exchange (performed_status, rank 4; no Exchange: the first patch's question Q4, carried), about the
    counterpart when its status is not established (D225: the act whose performance is unknown is named, its status
    fact the witness's result - never the code's own act, whose status is supported), else about ``event`` (both acts
    established: no id words "the two are one exchange", the step's NOTES, question Q7)."""
    if _same_duct(R, event, other):
        spans = tuple(sorted(set(_anchor(R, event)) | set(_anchor(R, other))))
        status = _fact(R, other, _A.STATUS)
        about, found = (event, None) if facts_.established(status) else (other, status)
        return (_held(rq.fact_key(_STATUS.fact), _STATUS.rank, _Q, _A.STATUS, about, found,
                      questions.coding_rule(_Rule.EXCHANGE), spans), None)
    mine = _filed_side(R, event, own)
    yours = _filed_side(R, other, theirs if theirs is not None else _wanted_of(mine.kind))
    if _fact(R, event, _A.TARGET_DUCT).result is Result.SUPPORTED:
        return _duct_hold(yours, mine, R)
    return _duct_hold(mine, yours, R)


def _unlisted_exchange(R: FactSet, event: Id, own: frozenset[Kind], entry: UnlistedStatement,
                       theirs: frozenset[Kind] | None = None) -> tuple[HeldFact, questions.Exchange]:
    """XCHG's hold of a stent act ``event`` beside a synthetic counterpart ``entry`` (D216): the duct question about the
    unlisted act, which has no duct (P6: the act whose duct is unknown is named, the filed act its counterpart)."""
    mine = _filed_side(R, event, own)
    return _duct_hold(_unlisted_side(entry, theirs if theirs is not None else _wanted_of(mine.kind)), mine, R)


def exchange_holds(R: FactSet, event: Id, group: Sequence[Kind]) -> tuple[tuple[HeldFact, questions.Exchange | None],
                                                                            ...]:
    """XCHG for 43274 and 43275 on a supporting act (43276 reads its pairs in ``decide``): one hold per filed counterpart
    (``counterparts``) and per synthetic one (``unlisted_counterparts``), each with the Exchange its item names."""
    if Kind.STENT_EXCHANGE in group:
        return ()
    own = frozenset(group) & _STENT_KINDS or _STENT_KINDS  # 43275's group holds the foreign body too: never named
    found = [_filed_exchange(R, event, own, other) for other in counterparts(R, event)]
    return (*found, *(_unlisted_exchange(R, event, own, entry) for entry in unlisted_counterparts(R, event)))


def _row_exchange(c: _Code, group: Sequence[Kind], R: FactSet, event: Id) -> Row:
    """XCHG for 43274 and 43275: no possibly-performed counterpart, filed or kept unlisted (D216), in the same or an
    unknown duct (``exchange_holds``)."""
    return _row(Tag.XCHG, [held for held, _ in exchange_holds(R, event, group)])


# The code-specific rows 4.4's code_requirements evaluates over every supporting act; YIELD, a row of SUPPORT itself (4.3:
# "no support from that act"). The others are steps 4b-5a's, which assess appends (4.4).
_TAG_ROWS: Mapping[Tag, Callable[[_Code, Sequence[Kind], FactSet, Id], Row]] = MappingProxyType({
    Tag.TECH: _row_technique, Tag.SITE: _row_site, Tag.STRUCT_PFC: _row_structure, Tag.ROUTE: _row_route,
    Tag.TRACT: _row_tract, Tag.STATIONS: _row_stations, Tag.LIMITED: _row_limited, Tag.LOWER: _row_lower,
    Tag.CAUSE: _row_cause, Tag.XCHG: _row_exchange})
_FILTER_ROWS: Mapping[Tag, Callable[[_Code, Sequence[Kind], FactSet, Id], Row]] = MappingProxyType({
    Tag.YIELD: _row_yield})
EVALUATED_TAGS: frozenset[Tag] = frozenset(_TAG_ROWS) | frozenset(_FILTER_ROWS)


def support(code: str, group: Sequence[Kind], R: FactSet, event: Id, reader: PairsReader | None = None) -> Support:
    """SUPPORT(E, C, g) (module docstring): every row's truth and witnesses, in 4.3's order - rows 1-8, the E/M encounter
    for an E/M code, and 43264's YIELD. ``reader``: the caller's per-FactSet reader of ``R`` (engine/coverage.Reader),
    read by row 8 only when it is ``R``'s own (DECISIONS D324 (8), int5): the outcome is the same with or without it."""
    c = _code(code)
    return _support(replace(c, reader=reader) if reader is not None and reader.R is R else c, tuple(group), R, event)


def _support(c: _Code, group: tuple[Kind, ...], R: FactSet, event: Id) -> Support:
    rows = [row(c, group, R, event) for row in _SUPPORT_ROWS]
    if c.template in _EM_TEMPLATES:
        rows.append(_row_encounter(c, group, R, event))
    rows += [_FILTER_ROWS[tag](c, group, R, event) for tag in c.spec.tags if tag in _FILTER_ROWS]
    return Support(event, tuple(rows))


def code_rows(code: str, group: Sequence[Kind], R: FactSet, event: Id) -> tuple[Row, ...]:
    """4.4's code_requirements on one supporting act: the code-specific rows this step evaluates (module docstring), in
    Appendix A's tag order."""
    return _code_rows(_code(code), tuple(group), R, event)


def _code_rows(c: _Code, group: tuple[Kind, ...], R: FactSet, event: Id) -> tuple[Row, ...]:
    rows = tuple(_TAG_ROWS[tag](c, group, R, event) for tag in c.spec.tags if tag in _TAG_ROWS)
    # DECISIONS D328 (1): every lower-GI endoscopy code's route row (round r3's probe prototype built the colonoscopy's,
    # D310 (1)); the lower EUS codes' is LOWER's own row (``_row_lower``)
    if catalogue.lower_gi(c.code) and not c.has(Tag.LOWER):
        rows += (_row_lower_route(c, group, R, event),)
    return rows


# --- 43276's pairs (XCHG) -----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Paired:
    """43276's pairs: those found (each supporting), the positive ones pending (each a candidate), the Exchange of every
    duct question among the pending ones' witnesses, and the kept unlisted act each synthetic part's doubt is about."""
    found: tuple[tuple[Id, Id], ...]
    pending: tuple[Support, ...]
    exchanges: tuple[tuple[HeldFact, questions.Exchange], ...]
    synthetic: tuple[tuple[HeldFact, UnlistedStatement], ...] = ()


def _pairs(c: _Code, R: FactSet) -> _Paired:
    """43276's other way of being supported (4.3 XCHG): every stent removal and stent placement that each support the
    code (rows 1-8 over their own kinds) in one duct, both ducts supported and equal - the pairs found; and, for every
    positive removal and positive placement nothing sets apart, the pair as a positive candidate, its witnesses both
    acts' and the duct's (bound by its removal). D216: a kept unlisted act or doubt (``synthetic_possible``) that may be
    the other part, in the filed part's session, makes a pair with a positive filed part too - a candidate bound by the
    filed part, its witnesses the filed part's, the synthetic act's doubt (3.2.6 rule 3) and the duct question about
    the synthetic act (it has no duct) - so 43276 is never excluded, nor its item "not documented", beside a possible
    exchange one of whose parts only pass 2 reported. Two synthetic parts make no candidate (neither has an id):
    condition 5 reads them (``_exchange_doubted``)."""
    removal_kinds, placement_kinds = frozenset(_EXCHANGE_PARTS[0]), frozenset(_EXCHANGE_PARTS[1])
    removals = candidates(R, _EXCHANGE_PARTS[0])
    placements = candidates(R, _EXCHANGE_PARTS[1])
    found: list[tuple[Id, Id]] = []
    pending: list[Support] = []
    exchanges: list[tuple[HeldFact, questions.Exchange]] = []
    synthetic: list[tuple[HeldFact, UnlistedStatement]] = []
    for removal in removals:
        for placement in placements:
            if removal == placement or placement not in counterparts(R, removal):
                continue
            first = _support(c, _EXCHANGE_PARTS[0], R, removal)
            second = _support(c, _EXCHANGE_PARTS[1], R, placement)
            same = _same_duct(R, removal, placement)
            if first.met and second.met and same:
                found.append((removal, placement))
                continue
            if positive(R, removal) and positive(R, placement):
                duct: tuple[Row, ...] = ()
                if not same:
                    held, exchange = _filed_exchange(R, removal, removal_kinds, placement, placement_kinds)
                    duct = (Row(Tag.XCHG, Truth.U, (held,)),)
                    if exchange is not None:
                        exchanges.append((held, exchange))
                pending.append(Support(removal, first.rows + second.rows + duct, partner=placement))
    for part, own, theirs in ((_EXCHANGE_PARTS[0], removal_kinds, placement_kinds),
                              (_EXCHANGE_PARTS[1], placement_kinds, removal_kinds)):
        for event in (removals if part is _EXCHANGE_PARTS[0] else placements):
            if not positive(R, event):
                continue
            session = _session(R, event)
            for entry in synthetic_possible(R):
                if not synthetic_kinds(entry) & theirs or not synthetic_in(R, entry, session):
                    continue
                rows = _support(c, part, R, event).rows
                doubt = _synthetic_doubt(entry, session if session is not None else entry.session)
                held, exchange = _unlisted_exchange(R, event, own, entry, theirs)
                exchanges.append((held, exchange))
                synthetic.append((doubt, entry))
                pending.append(Support(event, rows + (Row(rq.Requirement.SUP_STATUS, Truth.U, (doubt,)),
                                                      Row(Tag.XCHG, Truth.U, (held,)))))
    return _Paired(tuple(found), tuple(pending), tuple(exchanges), tuple(synthetic))


def _exchange_doubted(R: FactSet) -> bool:
    """Whether two kept unlisted acts or doubts (``synthetic_possible``) may be a stent removal and a stent placement of
    one session (D216: each a possibly performed act; 4.6 condition 5 for 43276, whose kinds a removal and a placement
    in one duct make): a possible exchange neither of whose parts has an id, so no candidate - it doubts 43276, which
    is then never excluded."""
    acts = synthetic_possible(R)
    for index, removal in enumerate(acts):
        if Kind.STENT_REMOVAL not in synthetic_kinds(removal):
            continue
        for other, placement in enumerate(acts):
            if other == index or Kind.STENT not in synthetic_kinds(placement):
                continue
            if (removal.session is None or placement.session is None or removal.session == placement.session
                    or removal.session not in R.sessions or placement.session not in R.sessions):
                return True
    return False


# --- exclusion (4.6) ----------------------------------------------------------------------------------------------------


@unique
class Covered(Enum):
    """How a code's kept spans cover a statement (C-10, 4.6 condition 4): by CITATION (overlapping its anchor, every
    kept span within its covering words), PARTIAL (overlapping, one reaching past them), or NONE (no overlap)."""
    CITATION = 'citation'
    PARTIAL = 'partial'
    NONE = 'none'


def _overlaps(one: Span, other: Span) -> bool:
    return one.start < other.end and other.start < one.end


def covering(R: FactSet, statement: Id) -> tuple[Span, ...]:
    """C-10's covering words of a statement (4.6 condition 4; D188): its anchor's kind and status words, and the ``at``
    spans of the ``statement`` sources of its target lesion, target places and date relation, each once, in order. A
    source citing its whole units (no located words) adds nothing."""
    anchor = R.anchors.get(statement)
    spans: list[Span] = []
    if anchor is not None:
        spans += [found for found in (anchor.kind_words, anchor.status_words) if found is not None]
    for attribute in _COVERING:
        domain = facts_.DOMAINS[(IdFamily.EVENT, attribute)]
        found = _members(R, statement, attribute) if domain.many else (_fact(R, statement, attribute),)
        for member in found:
            spans += [cited.at for cited in member.cited if cited.link is Link.STATEMENT and cited.at is not None]
    return tuple(sorted(set(spans)))


def within(span: Span, words: Sequence[Span]) -> bool:
    """C-10 over offsets: every offset of ``span`` lies inside the union of ``words`` (an empty span always does)."""
    position = span.start
    for part in sorted(words):
        if part.start > position:
            break
        position = max(position, part.end)
        if position >= span.end:
            return True
    return position >= span.end


def cover(R: FactSet, statement: Id, kept: Sequence[Span], kept_words: Sequence[Span] | None = None) -> Covered:
    """C-10 (module docstring): CITATION, PARTIAL or NONE. ``kept_words``: the letter-or-digit runs of the kept spans
    (R1's result); without them each kept span counts whole (fail-closed)."""
    anchor = R.anchors.get(statement)
    if anchor is None or not any(_overlaps(span, unit) for span in kept for unit in anchor.units):
        return Covered.NONE
    words = covering(R, statement)
    read = kept if kept_words is None else kept_words
    return Covered.CITATION if all(within(span, words) for span in read) else Covered.PARTIAL


def _in_family(c: _Code, R: FactSet, statement: Id) -> bool:
    """4.6 condition 1's place: route (a), the statement's session supported and its kind the code's family; route (b),
    every place of the statement established, its supported places in the code's regions, at least one."""
    if c.link.route is catalogue.LinkRoute.UNRECONCILED:
        places = _members(R, statement, _A.TARGET_PLACES)
        supported = [member.value for member in places if member.result is Result.SUPPORTED]
        return (bool(supported) and all(facts_.established(member) for member in places)
                and all(isinstance(place, Landmark) and anatomy.in_regions(place, c.link.regions)
                        for place in supported))
    session = _session(R, statement)
    return session is not None and facts_.holds(_fact(R, session, _A.KIND), c.link.family)


def concerns(code: str, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.6 condition 1: the statement's kind supported and covering the group; its session supported and of the code's
    family (route (b): its places in the code's regions)."""
    c = _code(code)
    return _concerns(c, group, R, statement)


def _concerns(c: _Code, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.6 condition 1 (``concerns``). A digital examination (FINAL 5.6 E13, ``_digital``) is no session's examination,
    so as a statement its examination kind concerns no group (DECISIONS D265: "No digital rectal examination was
    performed." never excludes 45378, nor asks its scope, as the same document without the DRE line)."""
    kind = _fact(R, statement, _A.KIND)
    if kind.value is Kind.EXAMINATION and _digital(R, statement):
        return False
    return (kind.result is Result.SUPPORTED and isinstance(kind.value, Kind) and _covers_group(kind.value, group)
            and _in_family(c, R, statement))


def deciding(R: FactSet, statement: Id) -> Attribute | None:
    """4.6 condition 2: the statement's first established deciding fact - status negated performed or supported planned;
    the date relation supported earlier_date or later_date; the performer supported other_clinician or other_facility.
    None when none is established; an attempted status never decides (C-9)."""
    status = _fact(R, statement, _A.STATUS)
    if facts_.denied(status, Status.PERFORMED) or facts_.holds(status, Status.PLANNED):
        return _A.STATUS
    if other_date(R, statement):
        return _A.DATE_RELATION
    if other_performer(R, statement):
        return _A.PERFORMER
    return None


def not_exceptive(R: FactSet, statement: Id) -> bool:
    """4.6 condition 3: a statement of another date or performer, or a plan, carries no breadth (K1); any other (a
    current denial) needs its breadth supported and not exceptive (C-7)."""
    if other_date(R, statement) or other_performer(R, statement) or facts_.holds(_fact(R, statement, _A.STATUS),
                                                                                 Status.PLANNED):
        return True
    breadth = _fact(R, statement, _A.SCOPE_BREADTH)
    return (breadth.result is Result.SUPPORTED and isinstance(breadth.value, Breadth)
            and breadth.value is not Breadth.EXCEPTIVE)


def _possible_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """The kinds an event may be when an exclusion asks whether anything doubts a code's kinds (4.2's widened arm), with
    the bleeding control a clip or an injection may be (D157(2))."""
    kinds = facts_.possible_kinds(R, event, of_family=True)
    if kinds & catalogue.HEMOSTASIS_KINDS and facts_.possibly(_fact(R, event, _A.PURPOSE), Purpose.HEMOSTASIS):
        return kinds | {Kind.BLEEDING_CONTROL}
    return kinds


def doubted(R: FactSet, group: Sequence[Kind]) -> bool:
    """4.6 condition 5 fails: an event possibly of the code's kinds (widened by its session's family) is possibly done
    today by the documenting team; or a DOUBT relation touches the kinds; or an unlisted entry is of them (or of no
    kind) - a denial or a doubt (4.6), and an act too: 3.2.6 rule 3 makes an unlisted act a synthetic doubted act, of
    no date and no performer pass 1 filed, so possibly today's act by the documenting team (the refutation's D2, read
    fail-closed; D216 rules it: every absence condition reads the synthetic act). An unlisted clip or injection, whose
    purpose no card states, is possibly a bleeding control (D157(2)), as a filed one with a purpose not established is;
    and a stent exchange's group is doubted by a possible exchange two synthetic acts or doubts make
    (``_exchange_doubted``)."""
    for event in R.events:
        if not any(_covers_group(kind, group) for kind in _possible_kinds(R, event)):
            continue
        status = _fact(R, event, _A.STATUS)
        if (any(facts_.possibly(status, value) for value in _POSITIVE)
                and facts_.possibly(_fact(R, event, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE)
                and facts_.possibly(_fact(R, event, _A.PERFORMER), Performer.DOCUMENTING_TEAM)):
            return True
    for pair in pairing.pairs(R):
        if pair.relation is pairing.Relation.DOUBT and any(_covers_group(kind, group) for kind in pair.kinds):
            return True
    if any(_unlisted_of(entry, group) for entry in R.unlisted):
        return True
    return Kind.STENT_EXCHANGE in group and _exchange_doubted(R)


def _unlisted_of(entry: UnlistedStatement, group: Sequence[Kind]) -> bool:
    """Whether a kept unlisted entry (any nature) may be of ``group``'s kinds (condition 5): it names no kind, or a kind
    covering one of the group's, or a clip or an injection beside a bleeding-control group (its purpose unstated)."""
    if entry.kind is None or _covers_group(entry.kind, group):
        return True
    return entry.kind in catalogue.HEMOSTASIS_KINDS and _bleeding_group(group)


def broad(c: _Code, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.10's broad denial: status negated performed, breadth supported all_of_kind, its session supported (of the
    code's family: it concerns the code), its date relation supported on_date_of_service."""
    return (_concerns(c, group, R, statement)
            and facts_.denied(_fact(R, statement, _A.STATUS), Status.PERFORMED)
            and facts_.holds(_fact(R, statement, _A.SCOPE_BREADTH), Breadth.ALL_OF_KIND)
            and facts_.holds(_fact(R, statement, _A.DATE_RELATION), DateRelation.ON_DATE_OF_SERVICE))


def possibly_this_session(c: _Code, R: FactSet, statement: Id) -> bool:
    """4.6's "possibly this session" (its last paragraph: a statement whose session or date relation is not established
    is possibly this session, possibly today) - DECISIONS D301 RF-A2-2: the ONE reader 4.6's question
    (``possibly_here``) and RD-2's count (``may_exclude``: condition 1's place, ``_may_place``, and the question's own
    term in ``_may_exclude_by``) read, so a statement 4.6 asks a statement_scope question of is never one the ADDON row
    reads as in no session of the code's family. Route (a): a statement whose session is not supported - negated,
    unresolved, doubted, contradicted, an overfilled view, silent, or naming an id the FactSet does not hold (pass 2
    established it in no one session) - is possibly this session, of the code's family; one whose session is supported
    is when that session's kind is possibly the code's family. Route (b) (no family; condition 1 reads its places in the
    code's regions) reads every statement as possibly its session. As built before D301, may_exclude read a session that
    is not supported through facts.possibly (``_may_be_in``), so a denial whose session is negated, or claimed only in
    an EGD beside the ERCP, was asked its scope by 4.6 while the ADDON row counted the primary it held. Monotone: a 9.4
    weakening never makes a session supported and only widens what a session's kind may be, so it never turns this
    False."""
    if c.link.route is catalogue.LinkRoute.UNRECONCILED:
        return True
    held = _id(_fact(R, statement, _A.SESSION))
    return held is None or facts_.possibly(_fact(R, held, _A.KIND), c.link.family)


def possibly_here(c: _Code, group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.6's last paragraph: a denial of the code's kinds (its kind possibly one of them, 4.2's widened arm) whose
    session or date relation is not established - possibly this session (``possibly_this_session``: a session not
    supported, or one possibly of the code's family; DECISIONS D301 RF-A2-2's one reader), possibly today - so a broad
    denial is never dropped. A digital examination's denial (FINAL 5.6 E13) denies no session's examination: its
    examination kind is not read (DECISIONS D265), any other it may be is."""
    if not facts_.denied(_fact(R, statement, _A.STATUS), Status.PERFORMED):
        return False
    kinds = _possible_kinds(R, statement)
    if _digital(R, statement):  # D265: a digital examination's denial is no denial of the session's examination
        kinds -= {Kind.EXAMINATION}
    if not any(_covers_group(kind, group) for kind in kinds):
        return False
    session, timing = _fact(R, statement, _A.SESSION), _fact(R, statement, _A.DATE_RELATION)
    unplaced = not facts_.established(session) or not facts_.established(timing)
    return (unplaced and possibly_this_session(c, R, statement)
            and facts_.possibly(timing, DateRelation.ON_DATE_OF_SERVICE))


@dataclass(frozen=True, slots=True)
class Excluded:
    """The exclusion's answer for one group (4.6): the Exclusion that excludes the code, else the item that holds it (a
    statement_scope question, or None for 7.6's not documented)."""
    exclusion: Exclusion | None
    item: HeldFact | None


def _scope(R: FactSet, statement: Id, kept: Sequence[Span]) -> HeldFact:
    spans = tuple(sorted(set(_anchor(R, statement)) | set(kept)))
    return _held(rq.fact_key(_SCOPE.fact), _SCOPE.rank, _Q, _A.SCOPE_BREADTH, statement, None,
                 questions.coding_rule(_Rule.STATEMENT_SCOPE), spans)


def _exclusion(c: _Code, group: Sequence[Kind], kept: Sequence[Span], R: FactSet,
               kept_words: Sequence[Span] | None, evidence_doubted: bool = False) -> Excluded:
    """4.6 (module docstring), over every statement in pass 1's order: the first that meets conditions 1-5 excludes.
    ``evidence_doubted``: an unlisted unit lies on the code's kept evidence (3.2.6 rule 2, ``on_evidence``), which holds
    the code - so a citation is asked, never decided, as beside any doubt (unlisted entries never exclude: 3.2.6)."""
    in_doubt = evidence_doubted or doubted(R, group)
    scope: HeldFact | None = None
    for statement in R.events:
        if _concerns(c, group, R, statement):
            decided = deciding(R, statement)
            covered = cover(R, statement, kept, kept_words)
            if decided is not None and not_exceptive(R, statement):
                if covered is Covered.CITATION and not in_doubt:
                    anchor = R.anchors.get(statement)
                    return Excluded(Exclusion(event=statement, fact=decided, cover=Cover.CITATION,
                                              anchor=tuple(sorted(set(anchor.units))) if anchor is not None else ()),
                                    None)
                if covered is not Covered.NONE and scope is None:
                    scope = _scope(R, statement, kept)
            if covered is Covered.NONE and broad(c, group, R, statement) and scope is None:
                scope = _scope(R, statement, kept)
        if scope is None and possibly_here(c, group, R, statement):
            scope = _scope(R, statement, kept)
    return Excluded(None, scope)


def exclusion(code: str, group: Sequence[Kind], kept: Sequence[Span], R: FactSet,
              kept_words: Sequence[Span] | None = None) -> Excluded:
    """4.6 for ``code``'s ``group`` (module docstring), with 3.2.6 rule 2's doubt on the kept evidence."""
    return _exclusion(_code(code), group, kept, R, kept_words, bool(on_evidence(kept, R)))


# --- an exclusion that is possible (DECISIONS D294 RD-2: the ADDON row's primary) --------------------------------------


def _surely_positive(R: FactSet, group: Sequence[Kind], event: Id) -> bool:
    """``event`` a positive candidate of ``group`` (4.4) under every reading of the facts that are not established: its
    kind supported and a candidate of the group by it (``candidate_kinds``; a clip's or an injection's purpose
    established, which decides whether it is a bleeding control), its status supported performed or begun, and neither
    another date nor another performer possible for it (facts.possibly over its effective date relation and performer).
    Such an act stays a positive candidate however the rest is resolved, so 4.6 (a code with no supporting act and no
    positive candidate) never excludes its group.

    DECISIONS D297 ENGA-F2: a digital examination of an examination group (``_digital_candidate``: FINAL 5.6 E13, its
    device claiming manual or established manual) is never such an act, whatever its facts. Its group is read as the
    same document without its lines (D265: ``_decide`` never binds it, and 4.6's own item is asked instead - a
    statement 4.6 would exclude by is asked its scope, a statement_scope question), so the premise is read as
    ``_decide`` reads the group: a primary held only by that question may be excluded, and an established digital
    rectal examination line never makes the ADDON row count it (D253: a fact E13 says never counts can never release
    a code). Monotone: the claimed-manual reading only grows under a 9.4 weakening, so this only narrows what is
    surely positive."""
    if _digital_candidate(group, R, event):
        return False
    kind, status = _fact(R, event, _A.KIND), _fact(R, event, _A.STATUS)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, Kind):
        return False
    if kind.value in catalogue.HEMOSTASIS_KINDS and not facts_.established(_fact(R, event, _A.PURPOSE)):
        return False
    if not candidate_kinds(R, group, event):
        return False
    if status.result is not Result.SUPPORTED or status.value not in _POSITIVE:
        return False
    date, performer = _fact(R, event, _A.DATE_RELATION), _fact(R, event, _A.PERFORMER)
    return (not any(facts_.possibly(date, value) for value in _OTHER_DATES)
            and not any(facts_.possibly(performer, value) for value in _OTHER_PERFORMERS))


def _may_be_of(group: Sequence[Kind], R: FactSet, statement: Id) -> bool:
    """4.6 condition 1's kind (``_concerns``) read with the possibility readers: the statement's kind possibly one
    covering the group (4.2's statement arm, ``_possible_kinds``), the examination kind of a digital examination
    ESTABLISHED as one never (DECISIONS D265).

    DECISIONS D297 ENGA-F1: E13's digital exception is read ESTABLISHED here (pairing.established_digital: kind
    supported examination, device supported manual; D280.1/.2), never the claimed-manual reading (``_digital``) that
    ``_concerns`` and ``possibly_here`` read. Subtracted from what a statement may be, a claimed reading would turn this
    reader False exactly when a 9.4 weakening (an established device to unresolved, a doubt, pass 1's contradiction, an
    overfilled view, a doubt reading manual) makes the device claim manual - so a weakened examination statement would
    stop excluding and release the add-on. A 9.4 weakening never creates a supported device or kind, so the established
    reading only narrows under one: this reader only widens, and stays wider than the kinds ``_concerns`` and
    ``possibly_here`` read (every statement of a group's kinds for them is one for it)."""
    kinds = _possible_kinds(R, statement)
    if pairing.established_digital(R, statement):
        kinds -= {Kind.EXAMINATION}
    return any(_covers_group(kind, group) for kind in kinds)


def _may_place(c: _Code, R: FactSet, statement: Id) -> bool:
    """4.6 condition 1's place (``_in_family``) read with the possibility readers: route (a), possibly this session
    (``possibly_this_session``, DECISIONS D301 RF-A2-2's one reader, the one 4.6's question reads: its session supported
    and that session's kind possibly the code's family, or not supported - any session of the family); route (b), no
    supported place of it outside the code's regions."""
    if c.link.route is catalogue.LinkRoute.UNRECONCILED:
        return not any(member.result is Result.SUPPORTED and isinstance(member.value, Landmark)
                       and not anatomy.in_regions(member.value, c.link.regions)
                       for member in _members(R, statement, _A.TARGET_PLACES))
    return possibly_this_session(c, R, statement)


def _may_exclude_by(c: _Code, group: Sequence[Kind], kept: Sequence[Span], R: FactSet,
                    kept_words: Sequence[Span] | None, statement: Id) -> bool:
    """Whether ``statement`` may exclude ``c``'s ``group`` - 4.6's conditions 1-4 read with the possibility readers,
    condition 5 never read (a citation a doubt blocks still may exclude), its kind possibly one of the group's
    (``_may_be_of``) - by one of the statement_scope questions or exclusions 4.6 reads:

    - 4.6's last paragraph (``possibly_here``), whatever the code's cover (DECISIONS D301 RF-A2-1): a denial (status
      negated performed, or not established) possibly of the date of service whose session or date relation is not
      established, possibly this session (``possibly_this_session``, the ONE reader 4.6's question reads: RF-A2-2) - any
      breadth. As built before D301 only the uncited arm read it, so the same statement held the add-on when the code
      did not cite it and released it when the code cited it or covered it partly;
    - otherwise the statement possibly of the code's family (``_may_place``; with ``_may_be_of``, 4.6 condition 1 read
      with the possibility readers, wider than ``_concerns``) and, the code covering it by citation or partly (an
      exclusion, a citation blocked only by doubt, or a partial cover's statement_scope question), a deciding fact
      possibly established - a plan, another date or another performer, which carries no breadth (K1), or a denial whose
      breadth is possibly not exceptive; or, the code not covering it, 4.10's broad denial possible: a denial possibly
      of the date of service whose breadth may be all_of_kind.

    The cited arm is never narrower than the uncited arm for one statement: every term the uncited arm reads the cited
    arm reads (a breadth possibly all_of_kind is possibly not exceptive). A fact not established is read as each value
    it may take (facts.possibly), so a statement whose deciding fact, breadth, session or date is not established but
    would exclude if it were may exclude; each term only widens under a 9.4 weakening, and the cover reads the anchor
    and kept spans, which no weakening moves."""
    if not _may_be_of(group, R, statement):
        return False
    status, date = _fact(R, statement, _A.STATUS), _fact(R, statement, _A.DATE_RELATION)
    breadth, performer = _fact(R, statement, _A.SCOPE_BREADTH), _fact(R, statement, _A.PERFORMER)
    denial = facts_.denied(status, Status.PERFORMED) or not facts_.established(status)
    today = facts_.possibly(date, DateRelation.ON_DATE_OF_SERVICE)
    unplaced = not facts_.established(_fact(R, statement, _A.SESSION)) or not facts_.established(date)
    if denial and today and unplaced and possibly_this_session(c, R, statement):
        return True  # 4.6's last paragraph read with the possibility readers, whatever the cover (D301 RF-A2-1)
    if not _may_place(c, R, statement):  # with _may_be_of above: condition 1
        return False
    unbroad = (facts_.holds(status, Status.PLANNED) or not facts_.established(status)
               or any(facts_.possibly(date, value) for value in _OTHER_DATES)
               or any(facts_.possibly(performer, value) for value in _OTHER_PERFORMERS))
    if cover(R, statement, kept, kept_words) is not Covered.NONE:
        return unbroad or (denial and any(facts_.possibly(breadth, value) for value in Breadth
                                          if value is not Breadth.EXCEPTIVE))
    return denial and today and facts_.possibly(breadth, Breadth.ALL_OF_KIND)


def _same_session(R: FactSet, one: Id, other: Id) -> bool:
    """Both events' sessions supported and the same (``_same_duct``'s reading of the session: XCHG's counterparts set
    two acts apart only by two supported sessions that differ, so two supported and equal can never be set apart)."""
    first = _session(R, one)
    return first is not None and first == _session(R, other)


def _exchange_paired(c: _Code, group: Sequence[Kind], R: FactSet) -> bool:
    """DECISIONS D301 RF-A2-3: 43276's group (XCHG, its stent_exchange group) supported or held under every reading by
    its other way of being supported (4.3 XCHG, ``_pairs``): a stent removal and a stent placement, two events, each
    surely positive for its part (``_surely_positive`` over _EXCHANGE_PARTS: kind supported, status supported performed
    or begun, no other date or performer possible), the placement one of the removal's counterparts (``counterparts``,
    as ``_pairs`` pairs them), that nothing can set apart - their ducts both supported and the same (``_same_duct``) and
    their sessions both supported and the same (``_same_session``): XCHG's counterparts set two acts apart only by two
    supported ducts or sessions that differ, and a supported fact is never resolved otherwise. ``_decide`` then finds
    the pair (both supporting) or holds it pending (both positive, the placement one of the removal's counterparts)
    whatever is resolved, and never reaches 4.6 for the group - as for a surely positive candidate (4.6's premise: no
    supporting act and no positive candidate). A pair whose duct or session is not established may be set apart by a
    reading, so its group is read as any other (fail-closed). Monotone: each term only narrows under a 9.4 weakening, so
    a weakening never turns this on."""
    if Kind.STENT_EXCHANGE not in group or not c.has(Tag.XCHG):
        return False
    removals = [event for event in candidates(R, _EXCHANGE_PARTS[0])
                if _surely_positive(R, _EXCHANGE_PARTS[0], event)]
    placements = [event for event in candidates(R, _EXCHANGE_PARTS[1])
                  if _surely_positive(R, _EXCHANGE_PARTS[1], event)]
    return any(removal != placement and _same_duct(R, removal, placement) and _same_session(R, removal, placement)
               and placement in counterparts(R, removal) for removal in removals for placement in placements)


def may_exclude(code: str, kept: Sequence[Span], R: FactSet, *, kept_words: Sequence[Span] | None = None) -> bool:
    """DECISIONS D294 RD-2: whether some statement MAY exclude ``code`` with its kept spans ``kept`` - 4.6 read with the
    possibility readers. A group 4.4 supports or holds under every reading - some act a positive candidate whatever is
    resolved (``_surely_positive``), or 43276's removal and placement pair each surely positive and never set apart
    (``_exchange_paired``, DECISIONS D301 RF-A2-3) - is never excluded and never asked 4.6's question (4.6's premise:
    ``_decide`` never reaches it); any other group may be, by a statement that may meet 4.6's conditions
    (``_may_exclude_by``): a citation blocked only by doubt, a statement_scope question 4.6 asks (a partial cover, a
    broad denial the code does not cite, 4.6's last paragraph whatever the cover: D301 RF-A2-1), or a statement whose
    deciding fact, breadth, session or date is not established but would exclude if it were. What holds the code is
    never read (its hold cause is never the test), and an excluded code may be excluded. Every fact it reads it reads
    through facts.possibly, which only widens under a 9.4 weakening, a session that is not supported as possibly this
    session (``possibly_this_session``, the one reader 4.6's question reads: D301 RF-A2-2), and FINAL 5.6 E13's digital
    examination in the direction that widens it too (DECISIONS D297): ESTABLISHED where it removes what a statement may
    be (``_may_be_of``, ENGA-F1), CLAIMED where it removes an act from the premise (``_surely_positive``, ENGA-F2) - so
    a weakening never turns it False: the ADDON row (engine/assess) counts no primary for which it is True, and so a
    weakened exclusion never releases an add-on."""
    c = _code(code)
    groups_ = catalogue.requirements(c.link)
    if not c.link.linked or not groups_ or catalogue.recognised_only(c.link):
        return False
    for group in groups_:
        if any(_surely_positive(R, group, event) for event in candidates(R, group)):
            continue
        if _exchange_paired(c, group, R):
            continue
        if any(_may_exclude_by(c, group, kept, R, kept_words, statement) for statement in R.events):
            return True
    return False


# --- the never-READY holds and not documented ---------------------------------------------------------------------------


def _code_level(rule: questions.Rule, kind: ItemKind, kept: Sequence[Span]) -> HeldFact:
    """A hold about no single fact (D189: attribute, subject and result None): performed_status at the status row."""
    return _held(rq.fact_key(_STATUS.fact), _STATUS.rank, kind, None, None, None, questions.coding_rule(rule),
                 tuple(sorted(set(kept))))


def on_evidence(kept: Sequence[Span], R: FactSet) -> tuple[UnlistedStatement, ...]:
    """3.2.6 rule 2: every kept unlisted entry - an act, a denial or a doubt - one of whose units one of the code's kept
    spans overlaps, in FactSet.unlisted's order. 3.2.6's own case: "The existing biliary stent was removed and replaced
    with a new plastic stent." with only the placement filed and pass 2's unlisted removal kept; 43274, citing that
    sentence, is held - never READY for what may be an exchange (the refutation's D1)."""
    return tuple(entry for entry in R.unlisted
                 if any(_overlaps(span, unit) for span in kept for unit in entry.units))


def _evidence_hold(entry: UnlistedStatement, R: FactSet, supporting: Sequence[Id]) -> HeldFact:
    """3.2.6 rule 2's hold: performed_status at RANK 2 ("an unlisted unit on its evidence", h2), a question quoting the
    unlisted unit, cause unlisted; about no single fact (D189: attribute and result None). Its subject, the act its item
    names: the first supporting act whose anchor shares a unit with the entry, else None (the item then names the
    group's bound act, else the first supporting act, else the code's own kind)."""
    units = tuple(sorted(set(entry.units)))
    subject = next((event for event in supporting
                    if any(_overlaps(unit, own) for unit in units for own in _anchor(R, event))), None)
    return _held(rq.fact_key(_DOUBT.fact), _DOUBT.rank, _Q, None, subject, None, questions.UNLISTED, units)


# --- decide (4.4) -------------------------------------------------------------------------------------------------------


def unmet(code: str, group: Sequence[Kind], R: FactSet, candidate: Support) -> int:
    """4.8 binding rule (3), "the fewest non-T requirements", counted over requirements_of(code) (step 1f's hand-off
    R9(e); refute-4a-r2 P2): the candidate's rows that are not T (SUPPORT's, the E/M encounter's, YIELD's; for 43276's
    pair both acts' and the duct's) and the code-specific rows this step evaluates on it (``code_rows``: TECH, SITE,
    STRUCT:pfc, ROUTE, TRACT, STATIONS, LIMITED, LOWER, CAUSE, XCHG) that are not T. R6, bundling, the combination and
    R7/R9 are evaluated by steps 4b, 4d and 5a after the binding, and are not counted (the step's NOTES, deviation 3)."""
    return _unmet(_code(code), tuple(group), R, candidate)


def _unmet(c: _Code, group: tuple[Kind, ...], R: FactSet, candidate: Support) -> int:
    required = frozenset(rq.requirements_of(c.code))
    rows = (*candidate.rows, *_code_rows(c, group, R, candidate.event))
    return sum(1 for row in rows if row.truth is not Truth.T and row.requirement in required)


@dataclass(frozen=True, slots=True)
class _Group:
    kinds: tuple[Kind, ...]
    supports: tuple[Support, ...]
    supporting: tuple[Id, ...]
    positive: tuple[questions.Candidate, ...]


@dataclass(frozen=True, slots=True)
class _Decided:
    evaluation: Evaluation
    groups: tuple[_Group, ...]
    raised: questions.Raised = questions.Raised()


def _synthetic_witnesses(R: FactSet, held: Sequence[HeldFact], paired: Sequence[tuple[HeldFact, UnlistedStatement]]
                         ) -> dict[HeldFact, UnlistedStatement]:
    """The synthetic acts' doubts among ``held``, each with the kept unlisted act it is about, so the item names that
    act's own kind and quotes its own units: 43276's pair parts as ``_pairs`` recorded them, then row 7's synthetic
    examinations of each session (``synthetic_examinations``: an examination, or an act of no kind) - never another
    kept act that happens to share the units (a sentence telling two acts: "advanced ... and removed")."""
    present = frozenset(held)
    found: dict[HeldFact, UnlistedStatement] = {}
    for witness, entry in paired:
        if witness in present:
            found.setdefault(witness, entry)
    for session in R.sessions:
        for entry in synthetic_examinations(R, session):
            witness = _synthetic_doubt(entry, session)
            if witness in present:
                found.setdefault(witness, entry)
    return found


def _digital_candidate(group: Sequence[Kind], R: FactSet, event: Id) -> bool:
    """A candidate of an examination group that is a digital examination (FINAL 5.6 E13: ``_digital``, its device
    claiming manual; row 1's ``_digital_row``): DECISIONS D265 - it never takes the binding and its witnesses never
    word the item. It stays a candidate (repair r4a-2 of round w8r's DV1: a positive one holds the code and 4.6 reads
    what it read, so 9.4's weakening of a device into a manual claim never releases or excludes)."""
    return Kind.EXAMINATION in group and _digital(R, event)


def _unbound_item(c: _Code, group: Sequence[Kind], kept: Sequence[Span], R: FactSet,
                  kept_words: Sequence[Span] | None, evidence_doubted: bool) -> HeldFact:
    """The held fact a group gets when its only positive candidates are digital examinations (DECISIONS D265: every item
    of a code is the item the same document gets without the digital examination's lines and the relations that pair
    it): 4.6's own item - the statement_scope question of a partial cover, a citation beside a doubt or a broad denial
    the code does not cite, else 7.6's not documented (a code-level hold naming no act). Never an exclusion: a positive
    digital examination holds the code (repair r4a-2's DV1, P-MONO), so a statement 4.6 would exclude by is asked its
    scope instead - the citation beside a doubt (the step's NOTES, question Q-R4A-EXCL). A digital examination statement
    concerns no group (``_concerns``), as without its line."""
    base = R.excluding  # round r3 (DESIGN-v2 f.1; PROTOTYPE): 4.6 reads R_base, never an answer
    excluded = _exclusion(c, group, kept, base, kept_words, evidence_doubted)
    if excluded.exclusion is not None:
        return _scope(base, excluded.exclusion.event, kept)
    return excluded.item if excluded.item is not None else _code_level(_Rule.NOT_DOCUMENTED, _Q, kept)


@dataclass(frozen=True, slots=True)
class _Read:
    """4.4's reading of one requirement group on one FactSet (``_read_group``): every candidate's SUPPORT, the
    supporting acts (``found``), the positive candidates that support nothing (``pending``) and, for 43276's
    stent_exchange group with no supporting act, its pairs (``paired``: XCHG's other way of being supported, filed or
    D216 synthetic - each found pair's two acts joined to ``found``, each pending pair to ``pending``)."""
    supports: tuple[Support, ...]
    found: tuple[Id, ...]
    pending: tuple[Support, ...]
    paired: _Paired | None

    @property
    def reaches_exclusion(self) -> bool:
        """4.4's decision reaches 4.6 for the group: no supporting act and no pending candidate - a found or pending
        XCHG pair, filed or synthetic, among them (DECISIONS D324 (6))."""
        return not self.found and not self.pending


def _read_group(c: _Code, group: tuple[Kind, ...], R: FactSet) -> _Read:
    """4.4 over one requirement group on ``R`` (module docstring): the ONE code path ``_decide`` reads a group by - on
    R_q for its outcome, and on R_base for the premise of 4.6 (DECISIONS D324 (6), the rule below in ``_decide``)."""
    supports = tuple(_support(c, group, R, event) for event in candidates(R, group))
    found = [entry.event for entry in supports if entry.met]
    pending = [entry for entry in supports if not entry.met and positive(R, entry.event)]
    paired: _Paired | None = None
    if Kind.STENT_EXCHANGE in group and c.has(Tag.XCHG) and not found:
        paired = _pairs(c, R)
        found += [event for pair in paired.found for event in pair]
        pending += paired.pending
    return _Read(supports, tuple(found), tuple(pending), paired)


def _decide(code: str, kept: Sequence[Span], R: FactSet, kept_words: Sequence[Span] | None) -> _Decided:
    c = _code(code)
    link = c.link
    groups_ = catalogue.requirements(link)
    if not link.linked or not groups_:
        rule = (_Rule.NOT_LINKED if link.reason is catalogue.NoRouteReason.FAMILY_MISMATCH else _Rule.UNPROFILED)
        return _Decided(Evaluation((), (_code_level(rule, _E, kept),), {}), ())
    if catalogue.recognised_only(link):
        return _Decided(Evaluation((), (_code_level(_Rule.RECOGNISED_ONLY, _E, kept),), {}), ())
    supporting: list[Id] = []
    held: list[HeldFact] = []
    bindings: dict[tuple[Kind, ...], Id] = {}
    decided: list[_Group] = []
    acts: list[tuple[tuple[Kind, ...], Id]] = []
    exchanges: dict[HeldFact, questions.Exchange] = {}
    paired_synthetic: list[tuple[HeldFact, UnlistedStatement]] = []
    evidence = on_evidence(kept, R)  # 3.2.6 rule 2: an unlisted unit on the kept evidence holds the code
    for group in groups_:
        read = _read_group(c, group, R)
        supports, found, pending = read.supports, list(read.found), list(read.pending)
        if read.paired is not None:
            for witness, exchange in read.paired.exchanges:
                exchanges.setdefault(witness, exchange)
            paired_synthetic += read.paired.synthetic
        if found:
            found = _site_fit(c, group, R, found)  # D240: an act established outside the site class does not support
            supporting += [event for event in found if event not in supporting]
            acts += [(group, event) for event in found]
            decided.append(_Group(group, supports, tuple(found), ()))
            continue
        if pending:
            ranked = tuple(questions.Candidate(entry.event, entry.witnesses, _unmet(c, group, R, entry))
                           for entry in pending)
            for entry in pending:
                held.extend(entry.witnesses)
            bindable = tuple(candidate for candidate in ranked if not _digital_candidate(group, R, candidate.event))
            if bindable:  # D265: a digital examination never takes the binding
                bindings[group] = questions.choose(kept, bindable, R)
            else:  # D265: only digital examinations hold the group - its item is the document's without them
                held.append(_unbound_item(c, group, kept, R, kept_words, bool(evidence)))
            decided.append(_Group(group, supports, (), ranked))
            continue
        # round r3 (DESIGN-v2 f.1, f.2(3); PROTOTYPE): 4.6's exclusion reads R_base, the row without any answer - an
        # answer releases and never excludes. DECISIONS D324 (6) (L2-3): 4.6 runs for the group only when R_base's OWN
        # 4.4 decision reaches it, read by the one code path this function reads the group by (``_read_group``: no
        # supporting act, no pending candidate, and no found or pending XCHG pair, filed or synthetic) - never a partial
        # re-check (the build re-checked candidate positivity alone, so an answer that set 43276's pair apart on R_q,
        # asked for another code, sent it to 4.6 on R_base, where a cited denial excluded it). Otherwise the group is
        # held, not documented, never excluded
        base = R.excluding
        if base is not R and not _read_group(c, group, base).reaches_exclusion:
            held.append(_code_level(_Rule.NOT_DOCUMENTED, _Q, kept))
            decided.append(_Group(group, supports, (), ()))
            continue
        excluded = _exclusion(c, group, kept, base, kept_words, bool(on_evidence(kept, base)))
        if excluded.exclusion is not None:
            return _Decided(Evaluation((), (), {}, exclusion=excluded.exclusion), ())
        held.append(excluded.item if excluded.item is not None else _code_level(_Rule.NOT_DOCUMENTED, _Q, kept))
        decided.append(_Group(group, supports, (), ()))
    for group, event in acts:  # 4.4's code_requirements over every supporting act: no early return before them (Q2)
        held.extend(witness for row in _code_rows(c, group, R, event) for witness in row.witnesses)
        if c.has(Tag.XCHG):
            for witness, named in exchange_holds(R, event, group):
                if named is not None:
                    exchanges.setdefault(witness, named)
    rule_2 = {_evidence_hold(entry, R, supporting): entry for entry in reversed(evidence)}
    held.extend(_evidence_hold(entry, R, supporting) for entry in evidence)
    if c.template is Template.ROUTE_B:  # D197: route (b) is never READY; its one item
        held.append(_code_level(_Rule.ROUTE_B, _E, kept))
    found_held = tuple(dict.fromkeys(held))
    raised = questions.Raised(evidence=MappingProxyType(rule_2), exchanges=MappingProxyType(exchanges),
                              synthetic=MappingProxyType(_synthetic_witnesses(R, found_held, paired_synthetic)))
    return _Decided(Evaluation(tuple(supporting), found_held, bindings), tuple(decided), raised)


def decide(code: str, kept: Sequence[Span], R: FactSet, *, kept_words: Sequence[Span] | None = None) -> Evaluation:
    """4.4's outcome function for ``code`` with its kept evidence spans ``kept`` (R1 already passed) over the settled
    FactSet ``R`` (facts.effective's, L1 re-judged): Evaluation(supporting, held_facts, bindings, exclusion) - module
    docstring. ``kept_words``: the letter-or-digit runs of the kept spans for C-10 (``cover``), None for the
    fail-closed reading. Pure: identical inputs give an identical Evaluation."""
    return _decide(code, kept, R, kept_words).evaluation


def code_facts(code: str, group: Sequence[Kind] = ()) -> questions.CodeFacts:
    """What an item names of ``code`` (questions.CodeFacts): its family, the group's kinds (by default the kinds the
    code accounts for, catalogue.accounted - called, never forked: step 1e's hand-off #5) and its row's technique, site,
    EUS class and tract."""
    c = _code(code)
    kinds = tuple(group) or catalogue.accounted(c.link)
    row = c.spec.row
    return questions.CodeFacts(code=code, family=c.link.family, group=kinds,
                               technique=row.technique if row is not None else None,
                               site=row.site if row is not None else None,
                               exam_class=row.eus_class if row is not None else None,
                               tract=row.tract if row is not None else None)


def groups(code: str, kept: Sequence[Span], R: FactSet, evaluation: Evaluation,
           kept_words: Sequence[Span] | None = None) -> tuple[questions.Group, ...]:
    """Each held group of ``evaluation`` as the item reads it (questions.Group): its positive candidates with their
    witnesses, recomputed (decide is pure), and its binding."""
    return _groups(_decide(code, kept, R, kept_words), evaluation)


def _groups(decided: _Decided, evaluation: Evaluation) -> tuple[questions.Group, ...]:
    return tuple(questions.Group(group.kinds, group.positive, evaluation.bindings.get(group.kinds))
                 for group in decided.groups if group.positive)


def item(code: str, kept: Sequence[Span], R: FactSet, evaluation: Evaluation, extra: Sequence[HeldFact] = (),
         kept_words: Sequence[Span] | None = None) -> questions.Item | None:
    """The ONE item of a held code (4.8, D182): questions.item over ``evaluation``'s held facts and ``extra`` (the R6
    facts, the class and code checks, the combination holds assess appends, 4.4), with the groups' bindings. None when
    nothing is held (an excluded or a READY code). What the item needs of the holds this module raised beside the
    FactSet (questions.Raised: 3.2.6 rule 2's entries, XCHG's two acts, the synthetic acts) is recomputed with the
    groups (decide is pure)."""
    decided = _decide(code, kept, R, kept_words)
    held = tuple(dict.fromkeys((*evaluation.held_facts, *extra)))
    return questions.item(held, _groups(decided, evaluation), code_facts(code), R, evaluation.supporting,
                          raised=decided.raised)
