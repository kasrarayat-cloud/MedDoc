"""The requirement table of design v2 (docs/gemini-migration/FINAL-V2.md 4.3, 4.8, 4.9, 3.2.1 and Appendix A; step 1f of
8.1; labelled REQUIREMENTS_VERSION, cpt-requirements@1): what each code requires, what each requirement reads and what
it raises, the fixed RANK of a held code's items, the CLAIMED table pass 2's claims are selected from, and each code's
requirement closure, dependencies(code).

**Two modules, one table** (P2: "Each code's required facts are data; the claims of pass 2, the question rank and the
acceptance trace derive from it"). engine/requirements_table.py is GENERATED from the worktree's catalogue tables by
scripts/gen_requirements.py: each catalogue code's template, requirement groups and code-specific tags (Appendix A),
the kinds each family's catalogue entry names (NAMED_KINDS: 3.2.1's ERCP kinds, DECISIONS D207) and the kinds of each
session family (FAMILY_KINDS, DECISIONS D191).
This module is written by hand from the design: the requirements every template carries (4.3's SUPPORT, the E/M
encounter, bundling, combination, R7 and R9), what each requirement and tag reads and raises (RULES), RANK (4.8),
CLAIMED (3.2.1) and dependencies (4.9). Nothing here evaluates a requirement: the forked rules (steps 4a-4d) do, and
they read these tables.

- **Requirements** (Requirement, and the table's Tag): 4.3's SUPPORT rows 1-8 (SUP.1 ... SUP.8, the ids 9.1's trace
  writes), B's V.this_encounter (4.3's E/M row), and 4.3's code-specific rows. requirements_of(code) lists a code's,
  in 4.3's order: SUPPORT (the examination's for BASE and EUS_EXAM, the visit's for EM), the E/M encounter, its tags,
  then route (b) or route (d), bundling, combination, R7 and R9 as its template carries them. Route (b) is never READY
  and its one item is a ROUTE_B row's (DECISIONS D197).
- **RULES** give each requirement's reads - (role, attribute, paths, kinds): the object it reads, the attribute, whether
  a READY or an exclusion path reads it or only a hold can follow from it, and the act kinds read when narrower than
  the role's - and the items it raises: ``asks`` for an unresolved requirement (U: 4.3's "unmet -> fact"), ``explains``
  for an established failure (F: 4.3's "established otherwise ->"), each at RANK's row. A contradicted fact of any
  requirement asks rank 1 (conflict:<kind>) and a doubt on status rank 2, whatever the requirement: RANK says so once.
  The paths are what 3.2.3's control generator reads (claims.CONTROLS, step 2c): lesion.multiplicity is read on the
  READY path and session.part_of_session on the hold path (DECISIONS D196), and the kind of an act of moderate sedation
  or of kind other, which has no sibling, only on the hold path (D194). The kinds are what CLAIMED must cover (D195,
  P-READSET per kind): a code-specific row reads the code's supporting act, never an umbrella act (4.3 row 1), and
  4.5's target row the lesion and places of an act whose kind has a target.
- **RANK** is 4.8's table, exactly its 23 ranks, pinned (tests/v2/test_requirements.py); service_date stays unranked.
- **CLAIMED** is 3.2.1's table, per object class: the attributes claimed, the act kinds each is claimed for, and the
  condition under which it is, as DECISIONS D194 (the umbrellas are codable) and D195 (every attribute a rule reads is
  claimed, per kind) complete it. claimed_sha256() is its pin (2.5; APPRAISAL_VERSION names it; D202: recomputed, with
  no version bump, until the first recording).
- **dependencies(code)** is the code's requirement closure (4.9) at the level a code alone determines: the roles its
  outcome reads, the attributes read on each, the kinds whose acts fill its candidate role and the kinds whose
  statements pair with them or with the counterparts XCHG reads. Which objects fill each role in a given FactSet is
  the rules' own reading (Role's docstring); P-INDEP (9.4, step 6a) perturbs facts outside the closure so resolved.

**The text-free boundary** (FINAL-V2 4.1, 5.7 measure 4): this module imports the standard library, contract/types.py,
contract/jsonschema.py (sha256_of, for the pins), engine/catalogue.py and engine/requirements_table.py - no retired v1
module and none of contract's text modules - holds no word, phrase or marker list (every module-level collection holds
enumeration members), and reads no text: its only string input is a proposed code, read as a number.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.jsonschema import sha256_of
from studio.interpretation.contract.types import AnatomyType, Attribute, Kind, Purpose, SessionKind
from studio.interpretation.engine import catalogue
from studio.interpretation.engine.requirements_table import (CATALOGUE_KINDS, CODES, NAMED_KINDS, CodeRow, Tag,
                                                             Template)

# --- RANK (FINAL-V2 4.8; DECISIONS D182) ------------------------------------------------------------------------------


@unique
class FactKey(Enum):
    """The questions.FORM fact keys RANK names (FINAL-V2 4.8): what a held code's item is about. CONFLICT is written
    conflict:<kind> (fact_key). The five new facts (event_entry, exam_stations, act_yield, act_cause, act_part) join
    wording.NEW_FACTS (D181, step 3c)."""
    CONFLICT = 'conflict'
    PERFORMED_STATUS = 'performed_status'
    STATEMENT_SCOPE = 'statement_scope'
    EVENT_ENTRY = 'event_entry'
    EVENT_TIME = 'event_time'
    EVENT_PERFORMER = 'event_performer'
    PROCEDURE = 'procedure'
    ACT_METHOD = 'act_method'
    TECHNIQUE = 'technique'
    ACT_TARGET = 'act_target'
    TARGET = 'target'
    EXAM_STATIONS = 'exam_stations'
    EXTENT = 'extent'
    ACT_YIELD = 'act_yield'
    CANNULATION = 'cannulation'
    ACT_PART = 'act_part'
    ACT_CAUSE = 'act_cause'
    EM_BASIS = 'em_basis'
    SEPARATE_EM = 'separate_em'
    BASE_INCLUDED = 'base_included'
    COMPETING_CODES = 'competing_codes'
    SETTING = 'setting'
    PATIENT_STATUS = 'patient_status'
    SERVICE_DATE = 'service_date'


@unique
class Rank(Enum):
    """The 23 ranks of FINAL-V2 4.8's RANK, in its order; a member's value is its rank (1 is asked first). The first
    four keep v1's h1-h4 order. A row's fact keys are RANK's."""
    CONFLICT = 1  # conflict:<kind>: a contradicted required fact (a conflict doubt, a K8 pair), a CONTRADICTION (h1)
    DOUBT = 2  # performed_status: a doubt - a DOUBT relation, pass 1's doubt on status, an unlisted statement (h2)
    STATEMENT_SCOPE = 3  # statement_scope: an UNRESOLVED relation on breadth, target or covers; an uncited denial (h3)
    STATUS = 4  # performed_status: status not established; attempted on a non-examination code (C-9); not documented
    ENTRY = 5  # event_entry: whose entry the act is told in, another role (F) or not established (U)
    TIME = 6  # event_time: the date relation not established; an undatable act beside an E/M
    PERFORMER = 7  # event_performer
    PROCEDURE = 8  # procedure: the session not established; tract or approach for a class
    METHOD = 9  # act_method: a positive umbrella beside a method-specific code (h5)
    TECHNIQUE = 10  # technique: technique class; EUS route
    ACT_TARGET = 11  # act_target: site class, region (route b), duct
    TARGET = 12  # target: the EUS target (R6); 43240's structure
    EXAM_STATIONS = 13  # exam_stations: full and limited EUS stations
    EXTENT = 14  # extent: R6 extent, the colonoscopy reach, the class reach, completion
    YIELD = 15  # act_yield: 43264
    CANNULATION = 16  # cannulation: R6 ERCP access
    BUNDLING = 17  # act_part, act_cause, act_target (bundling identity): a bundling on an unresolved fact
    BUNDLED = 18  # performed_status (bundled): an explanation naming the whole act
    EM_BASIS = 19  # em_basis
    SEPARATE_EM = 20  # separate_em (key-bound)
    BASE_INCLUDED = 21  # base_included (key-bound)
    COMPETING = 22  # competing_codes
    MEMBER_CONTEXT = 23  # setting, patient_status: member context (D3)


# Each rank's fact keys, as 4.8 writes them.
RANK: Mapping[Rank, tuple[FactKey, ...]] = MappingProxyType({
    Rank.CONFLICT: (FactKey.CONFLICT,),
    Rank.DOUBT: (FactKey.PERFORMED_STATUS,),
    Rank.STATEMENT_SCOPE: (FactKey.STATEMENT_SCOPE,),
    Rank.STATUS: (FactKey.PERFORMED_STATUS,),
    Rank.ENTRY: (FactKey.EVENT_ENTRY,),
    Rank.TIME: (FactKey.EVENT_TIME,),
    Rank.PERFORMER: (FactKey.EVENT_PERFORMER,),
    Rank.PROCEDURE: (FactKey.PROCEDURE,),
    Rank.METHOD: (FactKey.ACT_METHOD,),
    Rank.TECHNIQUE: (FactKey.TECHNIQUE,),
    Rank.ACT_TARGET: (FactKey.ACT_TARGET,),
    Rank.TARGET: (FactKey.TARGET,),
    Rank.EXAM_STATIONS: (FactKey.EXAM_STATIONS,),
    Rank.EXTENT: (FactKey.EXTENT,),
    Rank.YIELD: (FactKey.ACT_YIELD,),
    Rank.CANNULATION: (FactKey.CANNULATION,),
    Rank.BUNDLING: (FactKey.ACT_PART, FactKey.ACT_CAUSE, FactKey.ACT_TARGET),
    Rank.BUNDLED: (FactKey.PERFORMED_STATUS,),
    Rank.EM_BASIS: (FactKey.EM_BASIS,),
    Rank.SEPARATE_EM: (FactKey.SEPARATE_EM,),
    Rank.BASE_INCLUDED: (FactKey.BASE_INCLUDED,),
    Rank.COMPETING: (FactKey.COMPETING_CODES,),
    Rank.MEMBER_CONTEXT: (FactKey.SETTING, FactKey.PATIENT_STATUS),
})
# 4.8's "-" row: the encounter-scope date question, which blocks the reviewed report and ranks no code's item.
UNRANKED: tuple[FactKey, ...] = (FactKey.SERVICE_DATE,)
# The key-bound facts (questions.KEY_BOUND_FACTS): a pre-v2 member answer still binds to them by key (4.8).
KEY_BOUND: frozenset[FactKey] = frozenset({FactKey.SEPARATE_EM, FactKey.BASE_INCLUDED})


def fact_key(fact: FactKey, kind: Kind | None = None) -> str:
    """The questions.FORM key a HeldFact carries for ``fact`` (engine/types.HeldFact.fact): conflict:<kind> for
    FactKey.CONFLICT, which needs the contradicted act's kind; the key itself for any other fact, which takes none.
    ValueError otherwise."""
    if fact is FactKey.CONFLICT:
        if kind is None:
            raise ValueError('conflict:<kind> names the kind of the contradicted act.')
        return f'{fact.value}:{kind.value}'
    if kind is not None:
        raise ValueError(f'{fact.value} takes no kind.')
    return str(fact.value)


@dataclass(frozen=True, slots=True)
class Item:
    """An item a requirement raises (4.3's "unmet -> fact" and "established otherwise ->" columns) at its RANK row:
    rank (None for the unranked service_date) and fact, one of that row's fact keys."""
    rank: Rank | None
    fact: FactKey

    def __post_init__(self) -> None:
        facts = RANK[self.rank] if self.rank is not None else UNRANKED
        if self.fact not in facts:
            raise ValueError(f'{self.fact.value} is not a fact key of rank {self.rank}.')


# --- what a requirement reads (FINAL-V2 4.3-4.9) ----------------------------------------------------------------------


@unique
class Requirement(Enum):
    """The requirements that are not code-specific tags (FINAL-V2 4.3): SUPPORT's eight rows - SUPPORT(E, C, g), act E
    supports requirement group g of code C when each holds - the E/M encounter row, and the four rows of 4.3's second
    table that the table's Tag does not carry. The values are the ids 9.1's trace writes ("SUP.3")."""
    SUP_KIND = 'SUP.1'  # kind covers g; a positive umbrella never supports a method-specific code; examination: session
    SUP_STATUS = 'SUP.2'  # status performed; for a base or exam-only code also attempted_not_completed (C-9)
    SUP_DATE = 'SUP.3'  # effective date_relation on_date_of_service
    SUP_PERFORMER = 'SUP.4'  # effective performer documenting_team
    SUP_ENTRY = 'SUP.5'  # entry(E) documenting_clinician (1.5)
    SUP_SESSION = 'SUP.6'  # session X with X.kind the code's family; route (b): places in the code's regions
    SUP_SESSION_DONE = 'SUP.7'  # the session is done: its examination passes rows 2-5 (an act-only session: the act)
    SUP_CLEAN = 'SUP.8'  # no CONTRADICTION, DOUBT or UNRESOLVED relation (4.5), no unlisted statement, no contradiction
    V_THIS_ENCOUNTER = 'V.this_encounter'  # an E/M code: the visit's session encounter supported this_encounter
    ROUTE_B = 'route (b)'  # a code off the catalogue with an unreconciled act (46221): never READY (D197)
    ROUTE_D = 'route (d)'  # unprofiled codes, another family: never READY (C-6)
    BUNDLING = 'bundling'  # every code (4.7): part_of, cause, lesion identity, duct; the whole read by possibly
    COMBINATION = 'combination'  # as v1 (4.7): base, base-within, competing over facts
    R7_R9 = 'R7, R9'  # every code: the date of service known; the references are records


@unique
class Role(Enum):
    """What object a requirement reads, relative to the code (FINAL-V2 4.9's closure, item by item). Each role names
    the objects that fill it in a FactSet:
    - ACT: a candidate of the code (an act possibly of a kind of one of its requirement groups, not denied: 4.4) and
      every act of E*;
    - EXAMINATION: the examination of an ACT's or a COUNTERPART's session (4.3 row 7), found by its own session and
      kind facts;
    - SESSION: an ACT's or a COUNTERPART's session, and the session a same-day act or a session act is in;
    - VISIT: the em_visit event of an E/M code's session (R6:em_basis, C3+SEP; 99417 reads its visit's basis);
    - SESSION_ACT: any other act of an ACT's session (R6:cannulation's cannulation; base_included's acts);
    - COUNTERPART: XCHG's stent removal, placement and exchange acts, the sides of a possible exchange (D105, D127).
      43276 is met by a removal and a placement EACH SUPPORTING it, and 43274 and 43275 by no possibly performed
      counterpart (4.3's XCHG row), so a counterpart is read as SUPPORT reads an act: its own facts, and its session,
      that session's examination, the statements paired with it, its lesion and the unlisted statements touching it,
      each in the role an ACT's fill;
    - WHOLE: an act an ACT may be part of, caused by, or bundled into (4.7's bundling rules);
    - STATEMENT: a statement paired with an ACT or a COUNTERPART (4.5: an established denial, or a possible statement
      - an event whose status is not established - or one of another date or performer);
    - SAME_DAY_ACT: any act the same-day rule reads for an E/M code (4.7: a procedural act of the encounter);
    - ANATOMY: an anatomy entry a class rule reads (a session's through or reached_anatomy, a stoma or a pouch);
    - LESION: the lesion of an ACT, a COUNTERPART or a STATEMENT, and a lesion it is distinct from or the same as;
    - ENCOUNTER: the encounter (the date of service);
    - UNLISTED: an unlisted statement touching an ACT or a COUNTERPART (3.2.6), never a fact;
    - MEMBER: member context (setting, patient status, the member date; D3), never a fact;
    - COUNTED: the counted code set (an add-on's primary, a base code's rivals, competing codes)."""
    ACT = 'act'
    EXAMINATION = 'examination'
    SESSION = 'session'
    VISIT = 'visit'
    SESSION_ACT = 'session_act'
    COUNTERPART = 'counterpart'
    WHOLE = 'whole'
    STATEMENT = 'statement'
    SAME_DAY_ACT = 'same_day_act'
    ANATOMY = 'anatomy'
    LESION = 'lesion'
    ENCOUNTER = 'encounter'
    UNLISTED = 'unlisted'
    MEMBER = 'member'
    COUNTED = 'counted'


@unique
class Path(Enum):
    """Where a read can lead (FINAL-V2 3.2.3: controls are generated for every attribute "a rule reads on a READY or
    exclusion path"): READY, a T of the requirement needs it; EXCLUSION, 4.6 reads it to exclude; HOLD, nothing but a
    hold or a consideration can follow from it (UNCONTROLLED's reason)."""
    READY = 'ready'
    EXCLUSION = 'exclusion'
    HOLD = 'hold'


@dataclass(frozen=True, slots=True)
class Read:
    """One input of a requirement: ``attribute`` of the ``role``'s objects (None for a role that holds no fact:
    UNLISTED, MEMBER, COUNTED), on ``paths``. ``kinds`` narrows the act kinds it is read for; None reads it for every
    act the role names (for ACT, the code's candidates)."""
    role: Role
    attribute: Attribute | None
    paths: frozenset[Path]
    kinds: frozenset[Kind] | None = None


@dataclass(frozen=True, slots=True)
class Rule:
    """A requirement's reads, and the items it raises: ``asks`` when it is unresolved (U, a question) and ``explains``
    when an established fact fails it (F, an explanation). ``arms`` are reads made only for the codes of some
    templates (route (b)'s regions; the combination row's base arm), each (templates, reads)."""
    reads: tuple[Read, ...]
    asks: tuple[Item, ...] = ()
    explains: tuple[Item, ...] = ()
    arms: tuple[tuple[frozenset[Template], tuple[Read, ...]], ...] = ()

    def every_read(self) -> tuple[Read, ...]:
        """Every read the rule can make, its arms' included: what CLAIMED and the control generator answer to."""
        return self.reads + tuple(read for _templates, reads in self.arms for read in reads)

    def reads_for(self, template: Template) -> tuple[Read, ...]:
        """The reads the rule makes for a code of ``template``: its own, and every arm of that template."""
        return self.reads + tuple(read for templates, reads in self.arms if template in templates for read in reads)


_READY = frozenset({Path.READY})
_BOTH = frozenset({Path.READY, Path.EXCLUSION})
_HOLD = frozenset({Path.HOLD})
_ACT, _EXAM, _SESSION, _VISIT, _SESSION_ACT = Role.ACT, Role.EXAMINATION, Role.SESSION, Role.VISIT, Role.SESSION_ACT
_COUNTERPART, _WHOLE, _STATEMENT, _SAME_DAY = Role.COUNTERPART, Role.WHOLE, Role.STATEMENT, Role.SAME_DAY_ACT
_A = Attribute

# The kinds a rule names. A clip or an injection whose purpose is hemostasis is a bleeding control (catalogue_kind).
_HEMOSTASIS_KINDS = catalogue.HEMOSTASIS_KINDS
_EXAMINATION = frozenset({Kind.EXAMINATION})
_VISIT_KINDS = frozenset({Kind.EM_VISIT})
_CANNULATION = frozenset({Kind.CANNULATION})
_STENT_KINDS = frozenset({Kind.STENT, Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE})  # XCHG (D105): v1's ercp sides
# 4.7's bundling rules, by the act each reads: lift_injection (an injection beside an EMR or ESD),
# resection_technique (a snare or hot-forceps removal beside one), biopsy_of_removed_lesion (a biopsy of a removed
# lesion), drainage_step (an FNA beside a drainage), the procedural adjunct (a bleeding control, ablation, clip or
# injection caused by an act of the session), stent_included (D45: a sphincterotomy or dilation beside a stent in the
# same duct).
_SAME_LESION_KINDS = frozenset({Kind.INJECTION, Kind.SNARE, Kind.HOT_BIOPSY, Kind.BIOPSY, Kind.FNA})
_ADJUNCT_KINDS = frozenset({Kind.BLEEDING_CONTROL, Kind.ABLATION, Kind.CLIP, Kind.INJECTION})
_DUCT_KINDS = frozenset({Kind.SPHINCTEROTOMY, Kind.DILATION})
_WHOLE_LESION_KINDS = frozenset({*catalogue.REMOVAL_MEMBERS, Kind.DRAINAGE})
_STRICTURE_KINDS = frozenset({Kind.DILATION})  # D118: one stricture, by same lesion or places not disjoint
# DECISIONS D194: moderate sedation and kind other get no sibling (claims.KIND_SIBLINGS, step 2c), so the kind of an act
# of either is read on the hold path only; a rule that reads any act's kind reads every other kind where it reads it.
_NO_SIBLING_KINDS = frozenset({Kind.MODERATE_SEDATION, Kind.OTHER})
_SIBLING_KINDS = frozenset(kind for kind in Kind if kind not in _NO_SIBLING_KINDS)
# The kinds of an act that can support a code: a positive umbrella (removal, intervention) never supports a
# method-specific code (4.3 row 1), and every catalogue code is one. So a code-specific row (a Tag), met on the code's
# supporting act (4.4: code_requirements over the supporting acts), reads no umbrella act; SUPPORT reads every
# candidate, the umbrellas included (row 1 raises act_method on a positive one).
_SUPPORTING_KINDS = frozenset(kind for kind in Kind if kind not in catalogue.UMBRELLAS)
# The kinds of an act that has a target (DECISIONS D195: every kind but the visit, prolonged visit time, moderate
# sedation and other): 4.5's target row reads the paired act's lesion and places only when it has them. CLAIMED's
# TARGET_KINDS are these. An act of another kind has no claimed lesion or places, so they are always unknown
# (unresolved(unappraised), 3.3 row 6): the row answers as for an unknown target (4.5, 4.11: never INDEPENDENT, and
# UNRESOLVED wherever an unknown target is), reading no fact of that act (step 3d: never skipped).
_NO_TARGET_KINDS = frozenset({Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION, Kind.OTHER})
_TARGET_KINDS = frozenset(kind for kind in Kind if kind not in _NO_TARGET_KINDS)


def _r(role: Role, attribute: Attribute | None, paths: frozenset[Path] = _READY,
       kinds: frozenset[Kind] | None = None) -> Read:
    return Read(role, attribute, paths, kinds)


def _e(attribute: Attribute, paths: frozenset[Path] = _READY) -> Read:
    """A code-specific row's read of the code's supporting act (E*): an ACT read of the kinds that can support."""
    return Read(Role.ACT, attribute, paths, _SUPPORTING_KINDS)


# The combination row's two arms (4.7): base_included and base_within read a BASE or EUS_EXAM code's session and its
# other acts; the competition reads every code's candidates and the counted set (D163, D167: claims by possibly; D118).
# part_of_session only bundles (base_within) and its absence is read by possibly: the hold path (DECISIONS D196).
_BASE_ARM = (
    _r(_SESSION_ACT, _A.KIND, kinds=_SIBLING_KINDS), _r(_SESSION_ACT, _A.KIND, _HOLD, _NO_SIBLING_KINDS),
    _r(_SESSION_ACT, _A.STATUS), _r(_SESSION_ACT, _A.SESSION),
    _r(_SESSION_ACT, _A.DATE_RELATION), _r(_SESSION_ACT, _A.PERFORMER), _r(_SESSION_ACT, _A.ENTRY),
    _r(_SESSION_ACT, _A.PART_OF, _HOLD), _r(_SESSION, _A.PART_OF_SESSION, _HOLD), _r(_SESSION, _A.TRACT),
    _r(_SESSION, _A.KIND), _r(Role.COUNTED, None))
_COMPETING_ARM = (
    _r(_ACT, _A.KIND), _r(_ACT, _A.STATUS), _r(_ACT, _A.SESSION), _r(_ACT, _A.DATE_RELATION),
    _r(_ACT, _A.TARGET_LESION, kinds=_STRICTURE_KINDS), _r(_ACT, _A.TARGET_PLACES, kinds=_STRICTURE_KINDS),
    _r(Role.COUNTED, None))
# The templates whose code is held beside its session's other acts (4.7 base_included, base_within).
BASE_ARM_TEMPLATES: frozenset[Template] = frozenset({Template.BASE, Template.EUS_EXAM})

_DOUBT, _STATUS = Item(Rank.DOUBT, FactKey.PERFORMED_STATUS), Item(Rank.STATUS, FactKey.PERFORMED_STATUS)
_ENTRY, _TIME = Item(Rank.ENTRY, FactKey.EVENT_ENTRY), Item(Rank.TIME, FactKey.EVENT_TIME)
_PERFORMER, _PROCEDURE = Item(Rank.PERFORMER, FactKey.EVENT_PERFORMER), Item(Rank.PROCEDURE, FactKey.PROCEDURE)
_TECHNIQUE, _ACT_TARGET = Item(Rank.TECHNIQUE, FactKey.TECHNIQUE), Item(Rank.ACT_TARGET, FactKey.ACT_TARGET)
_TARGET, _STATIONS = Item(Rank.TARGET, FactKey.TARGET), Item(Rank.EXAM_STATIONS, FactKey.EXAM_STATIONS)
_EXTENT, _BUNDLED = Item(Rank.EXTENT, FactKey.EXTENT), Item(Rank.BUNDLED, FactKey.PERFORMED_STATUS)
_SEPARATE = Item(Rank.SEPARATE_EM, FactKey.SEPARATE_EM)
_BASE = Item(Rank.BASE_INCLUDED, FactKey.BASE_INCLUDED)

# Every requirement and tag: what it reads and raises (FINAL-V2 4.3's rows; the items at 4.8's ranks).
RULES: Mapping[Requirement | Tag, Rule] = MappingProxyType({
    # 4.3 row 1; 4.4's candidate; 4.6 condition 5 (a possible bleeding control, D157): a clip or an injection is read
    # with its purpose. U: a positive umbrella asks act_method (rank 9); a kind not established asks performed_status
    # at rank 4 (4.8 names no other rank for it; B's A.exists, "not documented").
    Requirement.SUP_KIND: Rule((_r(_ACT, _A.KIND, _BOTH), _r(_ACT, _A.PURPOSE, _BOTH, _HEMOSTASIS_KINDS)),
                               asks=(Item(Rank.METHOD, FactKey.ACT_METHOD), _STATUS)),
    # 4.3 row 2. F: attempted on a code that is not an examination's (C-9), rank 4.
    Requirement.SUP_STATUS: Rule((_r(_ACT, _A.STATUS, _BOTH),), asks=(_DOUBT, _STATUS), explains=(_STATUS,)),
    # 4.3 row 3 (1.5: effective, own or inherited); the act's date is L1's literal, re-judged at assess (4.2 effective)
    Requirement.SUP_DATE: Rule((_r(_ACT, _A.DATE_RELATION, _BOTH), _r(_ACT, _A.DATE, _HOLD)), asks=(_TIME,)),
    # 4.3 row 4 (effective)
    Requirement.SUP_PERFORMER: Rule((_r(_ACT, _A.PERFORMER, _BOTH),), asks=(_PERFORMER,)),
    # 4.3 row 5 (1.5: the containing section's owner; a restates restatement moves it, its role established: SC-D)
    Requirement.SUP_ENTRY: Rule((_r(_ACT, _A.ENTRY), _r(_ACT, _A.RESTATEMENTS_ROLE)), asks=(_ENTRY,),
                                explains=(_ENTRY,)),
    # 4.3 row 6; route (b): the act's places in the code's regions (rank 11's "region (route b)"; 4.6 condition 1)
    Requirement.SUP_SESSION: Rule((_r(_ACT, _A.SESSION, _BOTH), _r(_SESSION, _A.KIND, _BOTH)),
                                  asks=(_PROCEDURE, _ACT_TARGET),
                                  arms=((frozenset({Template.ROUTE_B}), (_r(_ACT, _A.TARGET_PLACES, _BOTH),)),)),
    # 4.3 row 7: rows 2-5 on the session's examination; K2 never touches it from another act (HO-7)
    Requirement.SUP_SESSION_DONE: Rule((
        _r(_EXAM, _A.KIND, kinds=_EXAMINATION), _r(_EXAM, _A.SESSION, kinds=_EXAMINATION),
        _r(_EXAM, _A.STATUS, kinds=_EXAMINATION), _r(_EXAM, _A.DATE_RELATION, kinds=_EXAMINATION),
        _r(_EXAM, _A.DATE, _HOLD, _EXAMINATION), _r(_EXAM, _A.PERFORMER, kinds=_EXAMINATION),
        _r(_EXAM, _A.ENTRY, kinds=_EXAMINATION), _r(_EXAM, _A.RESTATEMENTS_ROLE, kinds=_EXAMINATION)),
        asks=(_DOUBT, _STATUS, _ENTRY, _TIME, _PERFORMER), explains=(_STATUS, _ENTRY)),
    # 4.3 row 8: the pairing table (4.5) over every paired statement, both sides read; 4.6 conditions 1-3 read the
    # statement; an unlisted denial or doubt pairs UNRESOLVED (3.2.6 rule 4). A CONTRADICTION asks rank 1, a DOUBT
    # rank 2, an UNRESOLVED(attribute) that attribute (session, timing, performer, technique) or statement_scope. The
    # target row reads the act's lesion and places when its kind has a target (D195): never a visit's.
    Requirement.SUP_CLEAN: Rule((
        _r(_STATEMENT, _A.KIND, _BOTH), _r(_STATEMENT, _A.STATUS, _BOTH), _r(_STATEMENT, _A.SESSION, _BOTH),
        _r(_STATEMENT, _A.DATE_RELATION, _BOTH), _r(_STATEMENT, _A.PERFORMER, _BOTH),
        _r(_STATEMENT, _A.PERFORMER_PERSON), _r(_STATEMENT, _A.SCOPE_BREADTH, _BOTH),
        _r(_STATEMENT, _A.SCOPE_EXCEPTS, _BOTH), _r(_STATEMENT, _A.SCOPE_COVERS, _HOLD),
        _r(_STATEMENT, _A.SCOPE_TARGETS), _r(_STATEMENT, _A.SCOPE_SEGMENT), _r(_STATEMENT, _A.TARGET_LESION),
        _r(_STATEMENT, _A.TARGET_PLACES), _r(_STATEMENT, _A.TECHNIQUE_DEVICE),
        _r(_ACT, _A.KIND), _r(_ACT, _A.STATUS), _r(_ACT, _A.SESSION), _r(_ACT, _A.DATE_RELATION),
        _r(_ACT, _A.PERFORMER), _r(_ACT, _A.PERFORMER_PERSON), _r(_ACT, _A.TARGET_LESION, kinds=_TARGET_KINDS),
        _r(_ACT, _A.TARGET_PLACES, kinds=_TARGET_KINDS), _r(_ACT, _A.TECHNIQUE_DEVICE),
        _r(Role.LESION, _A.DISTINCT_FROM),
        _r(_SESSION, _A.KIND), _r(Role.UNLISTED, None, _HOLD)),
        asks=(Item(Rank.CONFLICT, FactKey.CONFLICT), _DOUBT, Item(Rank.STATEMENT_SCOPE, FactKey.STATEMENT_SCOPE),
              _PROCEDURE, _TIME, _PERFORMER, _TECHNIQUE)),
    # 4.3: "For an E/M code, the visit's session must also have encounter supported this_encounter (unmet: event_time)"
    Requirement.V_THIS_ENCOUNTER: Rule((_r(_SESSION, _A.ENCOUNTER),), asks=(_TIME,)),
    # Appendix A: route (b) (46221) is held, never READY (DECISIONS D197); 4.3 row 6's route (b) arm still decides which
    # acts support it, and exclusion, base and competition read those acts. The hold's one item (4.8) is this row's:
    # performed_status at the status row, its cause coding_rule:route_b (HeldFact.cause, written by step 4a).
    Requirement.ROUTE_B: Rule((), explains=(_STATUS,)),
    # 4.3 route (d): never READY (C-6), performed_status (unprofiled); 4.8 ranks it at the status row
    Requirement.ROUTE_D: Rule((), explains=(_STATUS,)),
    # 4.3 bundling, 4.7's rules: the act's part_of, cause and lesion identity, the whole read by possibly. part_of,
    # part_relation, cause_event and same_as only bundle (UNCONTROLLED: a yes-bias can only hold); a difference of
    # lesion, place or duct sets the act apart, so it is read on the READY path, and so is the lesion's multiplicity:
    # an established group un-bundles a biopsy of a removed lesion (4.7, C-2; DECISIONS D196).
    Requirement.BUNDLING: Rule((
        _r(_ACT, _A.PART_OF, _HOLD), _r(_ACT, _A.PART_RELATION, _HOLD), _r(_ACT, _A.CAUSE, _HOLD, _ADJUNCT_KINDS),
        _r(_ACT, _A.CAUSE_EVENT, _HOLD, _ADJUNCT_KINDS), _r(_ACT, _A.PURPOSE, _HOLD, frozenset({Kind.INJECTION})),
        _r(_ACT, _A.TARGET_LESION, kinds=_SAME_LESION_KINDS), _r(_ACT, _A.TARGET_PLACES, kinds=_SAME_LESION_KINDS),
        _r(_ACT, _A.TARGET_DUCT, kinds=_DUCT_KINDS), _r(Role.LESION, _A.SAME_AS, _HOLD),
        _r(Role.LESION, _A.DISTINCT_FROM), _r(Role.LESION, _A.MULTIPLICITY),
        _r(_WHOLE, _A.KIND, _HOLD), _r(_WHOLE, _A.STATUS, _HOLD), _r(_WHOLE, _A.DATE_RELATION, _HOLD),
        _r(_WHOLE, _A.SESSION, _HOLD), _r(_WHOLE, _A.TARGET_LESION, kinds=_WHOLE_LESION_KINDS),
        _r(_WHOLE, _A.TARGET_PLACES, kinds=_WHOLE_LESION_KINDS), _r(_WHOLE, _A.TARGET_DUCT, kinds=_STENT_KINDS)),
        asks=(Item(Rank.BUNDLING, FactKey.ACT_PART), Item(Rank.BUNDLING, FactKey.ACT_TARGET)),
        explains=(_BUNDLED,)),
    # 4.3 combination, 4.7: the competition (every code), and base_included and base_within (BASE_ARM_TEMPLATES)
    Requirement.COMBINATION: Rule(_COMPETING_ARM, asks=(_BASE, Item(Rank.COMPETING, FactKey.COMPETING_CODES)),
                                  explains=(_BASE,), arms=((BASE_ARM_TEMPLATES, _BASE_ARM),)),
    # 4.3 R7, R9: the date of service known (document or member); the encounter-scope date question
    Requirement.R7_R9: Rule((_r(Role.ENCOUNTER, _A.DATE_OF_SERVICE), _r(Role.MEMBER, None)),
                            asks=(Item(None, FactKey.SERVICE_DATE),)),
    # --- the code-specific rows (the table's tags) ---
    # ATT: attempted_not_completed accepted for the examination; F (incomplete) is the 52/53 consideration, no item
    Tag.ATT: Rule((_e(_A.STATUS),)),
    Tag.R6_EXTENT: Rule((_r(_SESSION, _A.REACHED), _r(_SESSION, _A.COMPLETION)), asks=(_EXTENT,)),
    # COLFULL: a FULL_REACH point, or reached_anatomy with an ileocolic subtype; completion incomplete is 52/53
    Tag.COLFULL: Rule((_r(_SESSION, _A.REACHED), _r(_SESSION, _A.REACHED_ANATOMY), _r(Role.ANATOMY, _A.SUBTYPE),
                       _r(_SESSION, _A.COMPLETION)), asks=(_EXTENT,)),
    Tag.R6_TARGET: Rule((_e(_A.TARGET_PLACES), _r(_EXAM, _A.TARGET_PLACES, kinds=_EXAMINATION)),
                        asks=(_TARGET,)),
    Tag.R6_CANNULATION: Rule((
        _r(_SESSION_ACT, _A.KIND, kinds=_CANNULATION), _r(_SESSION_ACT, _A.SESSION, kinds=_CANNULATION),
        _r(_SESSION_ACT, _A.STATUS, kinds=_CANNULATION), _r(_SESSION_ACT, _A.ACCESS_OUTCOME, kinds=_CANNULATION),
        _r(_SESSION_ACT, _A.TARGET_DUCT, kinds=_CANNULATION)), asks=(Item(Rank.CANNULATION, FactKey.CANNULATION),)),
    Tag.R6_EM_BASIS: Rule((_r(_VISIT, _A.VISIT_BASIS, kinds=_VISIT_KINDS),),
                          asks=(Item(Rank.EM_BASIS, FactKey.EM_BASIS),)),
    # R6:context: member-entered setting and patient status (D3: never read from the document)
    Tag.R6_CONTEXT: Rule((_r(Role.MEMBER, None),), asks=(Item(Rank.MEMBER_CONTEXT, FactKey.SETTING),
                                                         Item(Rank.MEMBER_CONTEXT, FactKey.PATIENT_STATUS))),
    # DEF: a supporting act of the defining kind; unmet "as SUPPORT"
    Tag.DEF: Rule((_e(_A.KIND, _BOTH),)),
    Tag.TECH: Rule((_e(_A.TECHNIQUE_DEVICE),), asks=(_TECHNIQUE,), explains=(_TECHNIQUE,)),
    # SITE: every supported place of the act and of its supported lesion within the class
    Tag.SITE: Rule((_e(_A.TARGET_PLACES), _e(_A.TARGET_LESION), _r(Role.LESION, _A.PLACES)),
                   asks=(_ACT_TARGET,), explains=(_ACT_TARGET,)),
    Tag.STRUCT_PFC: Rule((_e(_A.TARGET_STRUCTURE), _e(_A.TARGET_PLACES)), asks=(_TARGET,),
                         explains=(_TARGET,)),
    Tag.ROUTE: Rule((_e(_A.TECHNIQUE_ROUTE),), asks=(_TECHNIQUE,), explains=(_TECHNIQUE,)),
    Tag.TRACT: Rule((_r(_SESSION, _A.TRACT),), asks=(_PROCEDURE,), explains=(_PROCEDURE,)),
    # STATIONS: each station, or the empty list with its completeness claim established (SC-B), and the reach
    Tag.STATIONS: Rule((_r(_SESSION, _A.STATIONS), _r(_SESSION, _A.REACHED)), asks=(_STATIONS,),
                       explains=(_STATIONS,)),
    Tag.LIMITED: Rule((_r(_SESSION, _A.REACHED), _r(_SESSION, _A.STATIONS)), asks=(_STATIONS,), explains=(_STATIONS,)),
    Tag.LOWER: Rule((_r(_SESSION, _A.REACHED), _r(_SESSION, _A.APPROACH), _r(Role.ANATOMY, _A.TYPE)),
                    asks=(_EXTENT,), explains=(_EXTENT,)),
    Tag.ENT: Rule((_r(_SESSION, _A.APPROACH), _r(_SESSION, _A.THROUGH), _r(_SESSION, _A.REACHED),
                   _r(_SESSION, _A.COMPLETION), _r(Role.ANATOMY, _A.TYPE)),
                  asks=(_PROCEDURE, _EXTENT), explains=(_PROCEDURE, _EXTENT)),
    # YIELD: F (negated: "documented as retrieving nothing"); contradicted: conflict:stone_extraction (rank 1)
    Tag.YIELD: Rule((_e(_A.YIELD),), asks=(Item(Rank.YIELD, FactKey.ACT_YIELD),),
                    explains=(Item(Rank.YIELD, FactKey.ACT_YIELD),)),
    # XCHG (D105, D127): 43276 is met by a stent removal and a stent placement EACH SUPPORTING it, in one duct, and
    # 43274 and 43275 by no possibly performed counterpart in the same or an unknown duct (v1's _stent_side: kind,
    # status, date relation, performer). So a counterpart is read as SUPPORT reads an act - rows 1-6 and row 8's
    # pairing: kind, status, date relation (its date's literal on the hold path, as SUP.3), performer and person, entry
    # and its restatement's role, session, lesion, places, device - with its duct; its session, examination and the
    # statements paired with it fill those roles (Role's docstring; dependencies).
    Tag.XCHG: Rule((_e(_A.KIND), _e(_A.STATUS), _e(_A.TARGET_DUCT),
                    _r(_COUNTERPART, _A.KIND, kinds=_STENT_KINDS), _r(_COUNTERPART, _A.STATUS, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.DATE_RELATION, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.DATE, _HOLD, _STENT_KINDS),
                    _r(_COUNTERPART, _A.PERFORMER, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.PERFORMER_PERSON, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.ENTRY, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.RESTATEMENTS_ROLE, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.SESSION, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.TARGET_LESION, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.TARGET_PLACES, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.TARGET_DUCT, kinds=_STENT_KINDS),
                    _r(_COUNTERPART, _A.TECHNIQUE_DEVICE, kinds=_STENT_KINDS)), asks=(_ACT_TARGET, _STATUS)),
    # CAUSE: F (cause act_of_this_session) is bundled as a procedural adjunct, the explanation naming the whole
    Tag.CAUSE: Rule((_e(_A.PURPOSE), _e(_A.CAUSE), _e(_A.CAUSE_EVENT, _HOLD)),
                    asks=(Item(Rank.BUNDLING, FactKey.ACT_CAUSE),), explains=(_BUNDLED,)),
    # C3+SEP (4.7 same-day E/M): any procedural act possibly positive with its date relation, the performer not read;
    # the kind of an act of moderate sedation or of kind other on the hold path (D194)
    Tag.C3_SEP: Rule((
        _r(_SAME_DAY, _A.KIND, kinds=_SIBLING_KINDS), _r(_SAME_DAY, _A.KIND, _HOLD, _NO_SIBLING_KINDS),
        _r(_SAME_DAY, _A.OTHER_CLASS), _r(_SAME_DAY, _A.STATUS), _r(_SAME_DAY, _A.SESSION),
        _r(_SAME_DAY, _A.DATE_RELATION), _r(_SAME_DAY, _A.DATE, _HOLD), _r(_SESSION, _A.KIND),
        _r(_VISIT, _A.VISIT_SEPARATELY_IDENTIFIABLE, kinds=_VISIT_KINDS), _r(Role.UNLISTED, None, _HOLD)),
        asks=(_TIME, _SEPARATE), explains=(_SEPARATE,)),
    # ADDON: its primary counted; the fact "as today" (4.3 names none)
    Tag.ADDON: Rule((_r(Role.COUNTED, None),)),
    # D80: never READY, performed_status (recognised_only), at the status row
    Tag.D80: Rule((), explains=(_STATUS,)),
})

# --- the templates (B-requirements.md 4.4; FINAL-V2 Appendix A) -------------------------------------------------------

_SUPPORT = (Requirement.SUP_KIND, Requirement.SUP_STATUS, Requirement.SUP_DATE, Requirement.SUP_PERFORMER,
            Requirement.SUP_ENTRY, Requirement.SUP_SESSION, Requirement.SUP_SESSION_DONE, Requirement.SUP_CLEAN)
_EVALUATED_TAIL = (Requirement.BUNDLING, Requirement.COMBINATION, Requirement.R7_R9)
# What each template carries before its code's tags (SUPPORT, and the E/M encounter) and after them. A RECOGNISED code
# (D80) and an UNPROFILED one (route (d)) are held before any group is read (4.4's decide), so they carry no SUPPORT.
TEMPLATE_HEAD: Mapping[Template, tuple[Requirement, ...]] = MappingProxyType({
    **{template: _SUPPORT for template in (Template.BASE, Template.ACT, Template.EUS_EXAM, Template.EUS_ACT,
                                           Template.ADDON_ACT, Template.FEEDING, Template.TEST, Template.ROUTE_B)},
    Template.EM: _SUPPORT + (Requirement.V_THIS_ENCOUNTER,),
    Template.EM_ADDON: _SUPPORT + (Requirement.V_THIS_ENCOUNTER,),
    Template.RECOGNISED: (),
    Template.UNPROFILED: (),
})
TEMPLATE_TAIL: Mapping[Template, tuple[Requirement, ...]] = MappingProxyType({
    **{template: _EVALUATED_TAIL for template in Template if template not in (Template.RECOGNISED,
                                                                                Template.UNPROFILED)},
    Template.ROUTE_B: (Requirement.ROUTE_B, *_EVALUATED_TAIL),
    Template.RECOGNISED: (Requirement.R7_R9,),
    Template.UNPROFILED: (Requirement.ROUTE_D, Requirement.R7_R9),
})
# The templates whose SUPPORT is the examination's, with ATT (Appendix A), and those whose codes are never READY:
# D80's recognised-only codes, route (b) and route (d) (Appendix A: "held, never READY"). Each such code carries exactly
# one requirement that reads nothing and explains performed_status at the status row - D80, ROUTE_B (DECISIONS D197) or
# ROUTE_D - so its hold has its one item (4.8).
EXAMINATION_TEMPLATES: frozenset[Template] = frozenset({Template.BASE, Template.EUS_EXAM})
NEVER_READY: frozenset[Template] = frozenset({Template.RECOGNISED, Template.ROUTE_B, Template.UNPROFILED})


@dataclass(frozen=True, slots=True)
class Spec:
    """A code's requirements: its template, family and requirement groups, its tags, and the generated row (None for a
    code off the catalogue: route (b) or route (d))."""
    code: str
    template: Template
    family: SessionKind
    groups: tuple[tuple[Kind, ...], ...]
    tags: tuple[Tag, ...]
    row: CodeRow | None


def spec(code: str) -> Spec:
    """The requirements of the proposed ``code``: the table's row for a catalogue code (its canonical number's); route
    (b)'s link for a code with an unreconciled act (46221); route (d) for every other string."""
    number = catalogue.number(code)
    row = CODES.get(number) if number is not None else None
    if row is not None:
        return Spec(code, row.template, row.family, row.groups, row.tags, row)
    link = catalogue.code_link(code)
    if link.route is catalogue.LinkRoute.UNRECONCILED:
        return Spec(code, Template.ROUTE_B, link.family, catalogue.requirements(link), (), None)
    return Spec(code, Template.UNPROFILED, link.family, (), (), None)


def requirements_of(code: str) -> tuple[Requirement | Tag, ...]:
    """The requirements of ``code`` in 4.3's order: its template's head (SUPPORT, the E/M encounter), its tags, then its
    template's tail (route (b) or route (d), bundling, combination, R7 and R9). What 9.1's trace lists and gate 6 cases
    on."""
    found = spec(code)
    return (*TEMPLATE_HEAD[found.template], *found.tags, *TEMPLATE_TAIL[found.template])


def candidate_kinds(groups: tuple[tuple[Kind, ...], ...]) -> frozenset[Kind]:
    """The kinds whose acts can be candidates for requirement groups ``groups`` (4.4's candidate): a kind of a group,
    the kind a tattoo and an injection share (ONE_ACT), an umbrella covering one (catalogue.covers), and a clip or an
    injection, a bleeding control when its purpose is hemostasis (catalogue.catalogue_kind)."""
    wanted = frozenset(kind for group in groups for kind in group)
    return frozenset(kind for kind in Kind if any(catalogue.covers(kind, item) for item in wanted)
                     or catalogue.catalogue_kind(kind, Purpose.HEMOSTASIS) in wanted)


def statement_kinds(kinds: frozenset[Kind]) -> frozenset[Kind]:
    """The kinds of the statements that pair with acts of ``kinds`` (4.5: possibly equal, a tattoo with an injection, an
    umbrella covering it). A statement whose kind is not established pairs as every kind of its session's family
    [R:HO-5], whatever these are."""
    return frozenset(kind for kind in Kind if any(catalogue.covers(kind, item) for item in kinds))


def reads_of(code: str) -> tuple[Read, ...]:
    """Every read of ``code``'s requirements, in their order, each rule's arms only for the code's template (Rule)."""
    template = spec(code).template
    return tuple(read for requirement in requirements_of(code) for read in RULES[requirement].reads_for(template))


@dataclass(frozen=True, slots=True)
class Dependencies:
    """A code's requirement closure (FINAL-V2 4.9) at the level the code alone determines. ``reads``: each role its
    requirements read, with the attributes read on it (an empty set for a role that holds no fact). ``kinds``: the
    kinds whose acts fill its ACT role (candidate_kinds of its groups). ``statement_kinds``: the kinds whose statements
    fill its STATEMENT role - those pairing with its candidates and with the counterparts its rules read (XCHG's stent
    removal, placement and exchange: statement_kinds) - and any statement whose kind is not established. Each is empty
    when the code reads no such role (a RECOGNISED or UNPROFILED code). ``member``: whether member context is read.
    ``template``: its template (a NEVER_READY template's codes are held whatever these facts say)."""
    code: str
    template: Template
    kinds: frozenset[Kind]
    statement_kinds: frozenset[Kind]
    reads: Mapping[Role, frozenset[Attribute]]
    member: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, 'reads', MappingProxyType(dict(self.reads)))


def dependencies(code: str) -> Dependencies:
    """``code``'s requirement closure (FINAL-V2 4.9; module docstring): every role and attribute its requirements read
    (reads_of), and the kinds that fill its candidate and statement roles. Nothing outside it can change its status,
    its item or its held facts (P-INDEP, 9.4)."""
    found = spec(code)
    candidates = candidate_kinds(found.groups)
    roles: dict[Role, set[Attribute]] = {}
    counterparts: set[Kind] = set()
    for read in reads_of(code):
        if read.role is Role.ACT and read.kinds is not None and not read.kinds & candidates:
            continue  # a read of act kinds none of the code's candidates can be
        if read.role is Role.COUNTERPART and read.kinds is not None:
            counterparts |= read.kinds  # XCHG: each must support, so the statements paired with it count (4.3 row 8)
        attributes = roles.setdefault(read.role, set())
        if read.attribute is not None:
            attributes.add(read.attribute)
    kinds = candidates if Role.ACT in roles else frozenset()
    paired = statement_kinds(kinds | frozenset(counterparts)) if Role.STATEMENT in roles else frozenset()
    return Dependencies(code, found.template, kinds, paired,
                        {role: frozenset(attributes) for role, attributes in roles.items()}, Role.MEMBER in roles)


# --- CLAIMED (FINAL-V2 3.2.1) -----------------------------------------------------------------------------------------


@unique
class ObjectClass(Enum):
    """CLAIMED's object classes (3.2.1): an act of a codable kind; a statement (an event whose claimed status is
    negated) of a codable kind; a session; an anatomy entry; a lesion; the encounter."""
    ACT = 'act'
    STATEMENT = 'statement'
    SESSION = 'session'
    ANATOMY = 'anatomy'
    LESION = 'lesion'
    ENCOUNTER = 'encounter'


@unique
class Condition(Enum):
    """When a CLAIMED attribute is claimed (3.2.1): a supported or negated fact that passed its checks is claimed when
    its condition holds (a silent, doubted, contradicted or failed fact never is)."""
    ALWAYS = 'always'
    EFFECTIVE = 'effective'  # an act's effective date_relation or performer: its own, or its section's (1.5)
    OTHER_CLINICIAN = 'other_clinician'  # an act's performer_person: when its performer is other_clinician
    EUS_SESSION = 'eus_session'  # an injection's structure: in an EUS session
    WHEN_PRESENT = 'when_present'  # part_of and part_relation: when pass 1 reports them
    RESTATES_IN_OWN_SECTION = 'restates_in_own_section'  # a restates restatement in the documenting clinician's part
    OWN_WHEN_NAMED = 'own_when_named'  # a statement's performer and person: its own, when it names one (not inherited)
    WHEN_NAMED = 'when_named'  # a statement's device: when it names one
    HOLDS_VISIT = 'holds_visit'  # a session's encounter: a session holding a visit
    COMPLETENESS = 'completeness'  # the completeness claim: an upper EUS session whose station list is empty (SC-B)
    READ_BY_A_RULE = 'read_by_a_rule'  # an anatomy entry a session's through or reached_anatomy, an act's
    # target.anatomy, or a class rule reads (ANATOMY_READ_TYPES; a surgically absent organ a reach or station names)
    OF_A_CLAIMED_ACT = 'of_a_claimed_act'  # a lesion: one of a claimed act


@dataclass(frozen=True, slots=True)
class Claimed:
    """One CLAIMED entry: ``attribute`` is claimed under ``condition``, for an act or a statement of one of ``kinds``
    (None: every codable kind; and for the other classes, which have no kind)."""
    attribute: Attribute
    condition: Condition
    kinds: frozenset[Kind] | None = None


# 3.2.1: "an act of a codable kind (a kind some family's catalogue lists, an examination, an em_visit, or kind other)":
# every act kind the catalogue names (the generated CATALOGUE_KINDS), with those three, and the umbrellas removal and
# intervention, which DECISIONS D194 makes codable: an umbrella act's and an umbrella statement's facts are claimed like
# any other's, so 4.10's broad denial ("No polyp was removed today.") can exclude and contradict, and a positive
# umbrella's status can raise rank 9's act_method. Every Kind is codable; an event whose kind is not established is not.
CODABLE_KINDS: frozenset[Kind] = CATALOGUE_KINDS | frozenset({Kind.EXAMINATION, Kind.EM_VISIT, Kind.OTHER, Kind.REMOVAL,
                                                              Kind.INTERVENTION})
# The act kinds whose places and lesion are claimed (DECISIONS D195): every codable kind that has a target - all but
# the visit, prolonged visit time, moderate sedation and other - the examination included (R6:target reads its places;
# 4.5's target row, the paired act's). 3.2.1 named the fifteen lesion-bearing kinds, snare to drainage.
TARGET_KINDS: frozenset[Kind] = CODABLE_KINDS - frozenset({Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION,
                                                           Kind.OTHER})
# 3.2.1's kind lists, as it writes them. ROUTE_KINDS: "injection, tattoo, fiducial, drainage, fna" (fiducial is no
# Kind: a fiducial placement is filed as an injection; DECISIONS D207). The extraction kinds of yield are design A's
# (X8, the source of K1's "yield only on extraction kinds"; D194 keeps removal). The ERCP kinds are the fifteen the
# ERCP catalogue entry names (requirements_table.NAMED_KINDS), cannulation included (R6:cannulation reads its duct):
# the builder's reading DECISIONS D207 records. They are not the ERCP session family's kinds (FAMILY_KINDS, D191),
# which add the examination, intervention, moderate sedation and other: no rule reads their duct, and P2 rules out a
# claim no rule needs. Eight of the fifteen are read by no rule either: kind-level claims D195 keeps as 3.2.1 lists
# them.
ROUTE_KINDS: frozenset[Kind] = frozenset({Kind.INJECTION, Kind.TATTOO, Kind.DRAINAGE, Kind.FNA})
CAUSE_KINDS: frozenset[Kind] = frozenset({Kind.CLIP, Kind.INJECTION, Kind.BLEEDING_CONTROL, Kind.ABLATION})
EXTRACTION_KINDS: frozenset[Kind] = frozenset({Kind.STONE_EXTRACTION, Kind.FOREIGN_BODY, Kind.REMOVAL,
                                               Kind.STENT_REMOVAL})
ERCP_KINDS: frozenset[Kind] = NAMED_KINDS[SessionKind.ERCP]
# The anatomy types a class rule reads (3.2.1: "stoma, pouch, limb, bypass, a surgically absent organ a reach or
# station names").
ANATOMY_READ_TYPES: frozenset[AnatomyType] = frozenset({
    AnatomyType.STOMA, AnatomyType.ILEAL_POUCH, AnatomyType.GASTRIC_POUCH, AnatomyType.ROUX_LIMB, AnatomyType.BYPASS,
    AnatomyType.SURGICALLY_ABSENT})

_C, _ALWAYS = Condition, Condition.ALWAYS
CLAIMED: Mapping[ObjectClass, tuple[Claimed, ...]] = MappingProxyType({
    ObjectClass.ACT: (
        Claimed(_A.KIND, _ALWAYS), Claimed(_A.OTHER_CLASS, _ALWAYS), Claimed(_A.STATUS, _ALWAYS),
        Claimed(_A.SESSION, _ALWAYS), Claimed(_A.DATE_RELATION, _C.EFFECTIVE), Claimed(_A.DATE, _ALWAYS),
        Claimed(_A.PERFORMER, _C.EFFECTIVE), Claimed(_A.PERFORMER_PERSON, _C.OTHER_CLINICIAN),
        Claimed(_A.ENTRY, _ALWAYS), Claimed(_A.TECHNIQUE_DEVICE, _ALWAYS),
        Claimed(_A.TECHNIQUE_ROUTE, _ALWAYS, ROUTE_KINDS),
        Claimed(_A.TARGET_STRUCTURE, _ALWAYS, frozenset({Kind.DRAINAGE})),
        Claimed(_A.TARGET_STRUCTURE, _C.EUS_SESSION, frozenset({Kind.INJECTION})),
        Claimed(_A.TARGET_DUCT, _ALWAYS, ERCP_KINDS),
        Claimed(_A.TARGET_PLACES, _ALWAYS, TARGET_KINDS),
        Claimed(_A.TARGET_LESION, _ALWAYS, TARGET_KINDS),
        Claimed(_A.PURPOSE, _ALWAYS, CAUSE_KINDS), Claimed(_A.CAUSE, _ALWAYS, CAUSE_KINDS),
        Claimed(_A.CAUSE_EVENT, _ALWAYS, CAUSE_KINDS),
        Claimed(_A.PART_OF, _C.WHEN_PRESENT), Claimed(_A.PART_RELATION, _C.WHEN_PRESENT),
        Claimed(_A.YIELD, _ALWAYS, EXTRACTION_KINDS),
        Claimed(_A.ACCESS_OUTCOME, _ALWAYS, frozenset({Kind.CANNULATION})),
        Claimed(_A.VISIT_BASIS, _ALWAYS, frozenset({Kind.EM_VISIT})),
        Claimed(_A.VISIT_SEPARATELY_IDENTIFIABLE, _ALWAYS, frozenset({Kind.EM_VISIT})),
        Claimed(_A.RESTATEMENTS_ROLE, _C.RESTATES_IN_OWN_SECTION)),
    # "targets or segment": the statement's target facts (lesion, places, anatomy, duct: 3.2.2's statement.target
    # forms) and its scope's targets and segment; its own named person (4.5's performer row; DECISIONS D195)
    ObjectClass.STATEMENT: (
        Claimed(_A.KIND, _ALWAYS), Claimed(_A.STATUS, _ALWAYS), Claimed(_A.SESSION, _ALWAYS),
        Claimed(_A.DATE_RELATION, _C.EFFECTIVE), Claimed(_A.PERFORMER, _C.OWN_WHEN_NAMED),
        Claimed(_A.PERFORMER_PERSON, _C.OWN_WHEN_NAMED), Claimed(_A.SCOPE_BREADTH, _ALWAYS),
        Claimed(_A.SCOPE_COVERS, _ALWAYS), Claimed(_A.SCOPE_EXCEPTS, _ALWAYS),
        Claimed(_A.TARGET_LESION, _ALWAYS), Claimed(_A.TARGET_PLACES, _ALWAYS), Claimed(_A.TARGET_ANATOMY, _ALWAYS),
        Claimed(_A.TARGET_DUCT, _ALWAYS), Claimed(_A.SCOPE_TARGETS, _ALWAYS), Claimed(_A.SCOPE_SEGMENT, _ALWAYS),
        Claimed(_A.TECHNIQUE_DEVICE, _C.WHEN_NAMED)),
    ObjectClass.SESSION: (
        Claimed(_A.KIND, _ALWAYS), Claimed(_A.ENCOUNTER, _C.HOLDS_VISIT), Claimed(_A.TRACT, _ALWAYS),
        Claimed(_A.APPROACH, _ALWAYS), Claimed(_A.THROUGH, _ALWAYS), Claimed(_A.REACHED, _ALWAYS),
        Claimed(_A.REACHED_ANATOMY, _ALWAYS), Claimed(_A.COMPLETION, _ALWAYS), Claimed(_A.STATIONS, _ALWAYS),
        Claimed(_A.PART_OF_SESSION, _ALWAYS), Claimed(_A.STATIONS, _C.COMPLETENESS)),
    ObjectClass.ANATOMY: (
        Claimed(_A.TYPE, _C.READ_BY_A_RULE), Claimed(_A.ORGAN, _C.READ_BY_A_RULE),
        Claimed(_A.SUBTYPE, _C.READ_BY_A_RULE), Claimed(_A.JOINS, _C.READ_BY_A_RULE)),
    # a lesion's places: SITE's lesion arm (DECISIONS D195), in the lesion's own attribute order (1.4)
    ObjectClass.LESION: (
        Claimed(_A.MULTIPLICITY, _C.OF_A_CLAIMED_ACT), Claimed(_A.PLACES, _C.OF_A_CLAIMED_ACT),
        Claimed(_A.DISTINCT_FROM, _C.OF_A_CLAIMED_ACT), Claimed(_A.SAME_AS, _C.OF_A_CLAIMED_ACT)),
    ObjectClass.ENCOUNTER: (Claimed(_A.DATE_OF_SERVICE, _ALWAYS),),
})
# The object class each role's objects are claimed as: an event read in an ACT role is claimed as an act (an act-filed
# possible statement included), one in the STATEMENT role as a statement; UNLISTED, MEMBER and COUNTED hold no fact.
ROLE_CLASS: Mapping[Role, ObjectClass | None] = MappingProxyType({
    Role.ACT: ObjectClass.ACT, Role.EXAMINATION: ObjectClass.ACT, Role.SESSION: ObjectClass.SESSION,
    Role.VISIT: ObjectClass.ACT, Role.SESSION_ACT: ObjectClass.ACT, Role.COUNTERPART: ObjectClass.ACT,
    Role.WHOLE: ObjectClass.ACT, Role.STATEMENT: ObjectClass.STATEMENT, Role.SAME_DAY_ACT: ObjectClass.ACT,
    Role.ANATOMY: ObjectClass.ANATOMY, Role.LESION: ObjectClass.LESION, Role.ENCOUNTER: ObjectClass.ENCOUNTER,
    Role.UNLISTED: None, Role.MEMBER: None, Role.COUNTED: None})
_EVENT_CLASSES = frozenset({ObjectClass.ACT, ObjectClass.STATEMENT})


def claimed(object_class: ObjectClass, attribute: Attribute, kind: Kind | None = None) -> tuple[Condition, ...]:
    """The conditions under which ``attribute`` of an object of ``object_class`` is claimed (3.2.1) - for an act or a
    statement, one of ``kind``, which must be codable - in CLAIMED's order; () when it never is. The caller (claims.py,
    step 2c; settle's row 6, step 3a) decides whether a condition holds for the object at hand."""
    if object_class in _EVENT_CLASSES and (kind is None or kind not in CODABLE_KINDS):
        return ()
    return tuple(entry.condition for entry in CLAIMED[object_class] if entry.attribute is attribute
                 and (entry.kinds is None or kind in entry.kinds))


def _members(values: frozenset[Kind] | frozenset[AnatomyType]) -> list[str]:
    order = list(Kind) if all(isinstance(value, Kind) for value in values) else list(AnatomyType)
    return [member.value for member in order if member in values]


def claimed_canonical() -> dict[str, object]:
    """CLAIMED's canonical form, the bytes its pin hashes: the codable kinds, the anatomy types a class rule reads, and
    every class's entries in order (attribute, condition, kinds or null)."""
    return {
        'codable_kinds': _members(CODABLE_KINDS),
        'anatomy_read_types': _members(ANATOMY_READ_TYPES),
        'classes': [[object_class.value, [[entry.attribute.value, entry.condition.value,
                                           None if entry.kinds is None else _members(entry.kinds)]
                                          for entry in CLAIMED[object_class]]] for object_class in ObjectClass],
    }


def claimed_sha256() -> str:
    """The sha256 of CLAIMED's canonical bytes (contract/jsonschema.sha256_of): the CLAIMED pin of 2.5, which
    APPRAISAL_VERSION names ("the CLAIMED selection (by sha)"). A changed CLAIMED needs gemini-appraisal@2."""
    return sha256_of(claimed_canonical())


def rank_canonical() -> dict[str, object]:
    """RANK's canonical form: each rank with its fact keys in 4.8's order, the unranked and the key-bound facts."""
    return {'ranks': [[rank.value, [fact.value for fact in RANK[rank]]] for rank in Rank],
            'unranked': [fact.value for fact in UNRANKED],
            'key_bound': [fact.value for fact in FactKey if fact in KEY_BOUND]}


def rules_canonical() -> dict[str, object]:
    """The read-sets' canonical form: every requirement's reads, asks and explains, the templates' head and tail."""
    def kinds(read: Read) -> list[str] | None:
        return None if read.kinds is None else _members(read.kinds)

    def items(found: tuple[Item, ...]) -> list[list[object]]:
        return [[None if item.rank is None else item.rank.value, item.fact.value] for item in found]

    def reads(found: tuple[Read, ...]) -> list[list[object]]:
        return [[read.role.value, None if read.attribute is None else read.attribute.value,
                 [path.value for path in Path if path in read.paths], kinds(read)] for read in found]

    return {
        'rules': [[requirement.value,
                   reads(rule.reads), items(rule.asks), items(rule.explains),
                   [[[template.value for template in Template if template in templates], reads(arm)]
                    for templates, arm in rule.arms]] for requirement, rule in RULES.items()],
        'head': [[template.value, [item.value for item in TEMPLATE_HEAD[template]]] for template in Template],
        'tail': [[template.value, [item.value for item in TEMPLATE_TAIL[template]]] for template in Template],
    }


def table_canonical() -> list[list[object]]:
    """The generated table's canonical form: each row's fields as values."""
    def value(member: Enum | None) -> object:
        return None if member is None else member.value

    return [[row.code, row.family.value, row.template.value, [[kind.value for kind in group] for group in row.groups],
             [tag.value for tag in row.tags], [kind.value for kind in row.defining], value(row.technique),
             value(row.site), value(row.tract), value(row.eus_class), value(row.enteroscopy_class)]
            for row in CODES.values()]
