"""The catalogue's vocabulary tables of design v2 (docs/gemini-migration/FINAL-V2.md, step 1e of 8.1): how a proposed
code links to acts, the kinds a code needs, the umbrellas and what covers what, the defining kinds, the technique, site,
EUS, enteroscopy and colonoscopy class tables, and the family maps - pure tables over the contract's enumeration values,
with the lookups v1 read over them. The engine's forked rules (steps 4a-4d) read them, and step 1f depends on them;
FINAL-V2 4.4 calls catalogue.code_link, catalogue.requirements and catalogue.recognised_only by name.

**Ported from v1, proved equal to v1's by value** (FINAL-V2 5.0; tests/v2/test_catalogue_parity.py computes v1's
values in the test, for all 163 codes of the catalogue and for every five-digit code), from studio/interpretation/
mapping.py, classes.py, lexicon.py and assess.py's colonoscopy reach (D38, D44), and the gi reference tables they read
(studio.gi.catalogue's CODES, entries, NOT_REPORTED, UNSUPPORTED_ACTS, READ_UNDER, UNRECONCILED_ACTS and _REGIONS;
studio.gi.profiles' routing ranges, carve-outs and flags), with two tables the arbiter's rulings add: the Kind-valued
parts of each catalogue entry's bundled and unsupported_acts (BUNDLED_KINDS, UNSUPPORTED_KINDS; DECISIONS D191), and
studio.gi.services.FAMILY_REGIONS as K3's reach (FAMILY_REACH; DECISIONS D192). This module imports none of them: the
tables are copied here. Round r3's lower-GI route table (DECISIONS D328 (1): RouteAnatomy, LowerRoute, LOWER_ROUTES,
lower_gi, lower_route) is a billing table of CPT Studio's own, with no v1 value: every lower-GI endoscopy code's route
and the anatomy it needs, which engine/evaluate reads.

**How v1's strings are written here.** A family is its SessionKind (v1's slug 'gi.<value>'; gi.other is OTHER_GI and
gi.unsupported NOT_GI, lexicon.FAMILY_OF). A kind is a Kind; v1's catalogue kind 'eus_exam' is Kind.EXAMINATION in the
EUS family (ADJUDICATION C-1: the examination is the session, and the session kind tells the EUS one apart), and v1's ''
(kind 'other', listed and never reconciled) is None. A code is its number (int) in every code-keyed table, so no
module-level collection holds a string (5.7 measure 4, NoWordLists); the lookups take the proposal's code string and
read a table only for the canonical decimal form of a number (number()), which is exactly v1's dict-key match. Routing a
code to its family (family_for_code) keeps gi.profiles' own rule - a str of five characters for which str.isdigit holds,
compared as a string with each range's bounds - so it routes every string as v1 does. CPT Studio's own coding names
(route, reason, support level, technique, site, EUS and enteroscopy classes) are the Enums below, whose values are v1's
strings; none is ever compared with document text.

**Left out, and why** (each a surface form, a display string, a rule name, or an input of a retired reader; DECISIONS
D207 records the list as 1e's "tables left out", and D191 brought in the kinds FamilyEntry.bundled and unsupported_acts
name):
- surface-form and word lists, never ported (the new path forbids them, FINAL-V2 5.7 measure 4; Gemini's facts
  replace them, 5.1): mapping's BLEEDING_STATED, BLEEDING_NEGATORS, NOT_BLEEDING_NOW, HEMOSTASIS_WORDS,
  PANCREATIC_FLUID_COLLECTION (DEFINING_TARGETS' phrases), SUBMUCOSAL_WORDS, INK_WORDS, INJECTION_OWN_WORDS; classes'
  ROUTE_WORDS, ROUTE_INTO, ROUTE_NOUNS, ROUTE_FORMS, ROUTE_BREAKS, PLACE_PREFIXES, PHRASE_REACH, INTESTINAL_POUCH_WORDS,
  GASTRIC_POUCH_WORDS, ROUTE_STATED, ROUTE_READ; lexicon's LANDMARK_FORMS, DEVICE_WORDS, PROCEDURE_NAMES and every other
  word list. Where a table mixed enumeration values with words, its enumeration-valued part is here: classes.ROUTES and
  CLASS_ROUTE as ENTEROSCOPY_CLASS_ANATOMY and ENTEROSCOPY_CLASS_APPROACH, catalogue.READ_UNDER's family and regions,
  mapping.DEFINING_TARGET_APART;
- display strings (wording's, step 3c): mapping.SERVICE_KIND (service names for labels; v2 reads a code's included
  examination by SessionKind, CodeLink.includes), READ_UNDER's two labels, classes.CLASS_WORDS, ROUTE_PHRASES, CHECK,
  ELSEWHERE_CHECK, EXTENT_QUESTION, BASE_QUESTION, IN_DOUBT, and every FamilyEntry field but its support level, its
  acts and the kinds its bundled and unsupported_acts name (label, kinds, documentation, bundled and unsupported_acts'
  sentences, questions, evidence, rules, notes);
- FamilyEntry.bundled's items that name a rule, not a kind: COMMON_BUNDLED's biopsy_of_removed_lesion, lift_injection
  and resection_technique (4.7's bundling rules, each read from its own facts) and the office visit's em_routine (the
  same-day E/M rule, 4.7). BUNDLED_KINDS holds only the items that are Kind values (D191);
- enumeration-valued tables whose only reader is a retired reader (FINAL-V2 5.1) or a persisted word-derived field:
  mapping.WALL_REGIONS (wall_place, row 19; ROUTE reads technique.route), POSSIBLE_BLEEDING_CONTROL (D115's word-derived
  kind, dropped by D180), lexicon.UNCHECKED_DEVICES (verify's device check), mapping.role, key and map_events (the
  per-event key v1 persisted and no rule read; v2 persists nothing word-derived, 5.5).

**The two landmarks LANDMARKS2 adds** (third_portion_duodenum, fourth_portion_duodenum; FINAL-V2 1.4) have no v1 value.
DECISIONS D204 rules where they stand: in every class table here exactly where v1's duodenal landmarks stand
(duodenum and second_portion_duodenum, which agree in every table; v1's second_portion_duodenum took "third portion"
words), in the EUS full reach and the gastric-and-duodenal dilation site, in no other. So a reach or a dilation v1 coded
from "third portion" words is coded alike, and a third-portion reach still fits no enteroscopy class, as in v1
(fail-closed: D108's descriptor reading, which would make them jejunal, needs a coding rule recorded on evidence).
stated_depth (EXTENTS) is in no class table. The test pins both rules.

**The text-free boundary** (FINAL-V2 4.1, 5.7 measure 4): this module imports the standard library, contract/types.py
and engine/anatomy.py only - no retired v1 module (5.0), nothing of studio.gi, none of contract's text modules - holds no
word, phrase or surface-form list, and reads no document text: its only string input is a proposed code.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import (AnastomosisSubtype, AnatomyType, Approach, Attribute, Device,
                                                  Extent, Kind, Landmark, Purpose, SessionKind, Station, Tract)
from studio.interpretation.engine.anatomy import (ALTERED, ANASTOMOSIS_PLACE, UNPLACED, Place, Region, compatible,
                                                contains, in_regions, region)


@unique
class LinkRoute(Enum):
    """How a proposed code links to acts (mapping.ROUTES; FINAL C7 as ADJUDICATION C-6 amends it): (a) the catalogue,
    (b) an unreconciled act, (d) none. There is no route (c)."""
    CATALOGUE = 'catalogue'
    UNRECONCILED = 'unreconciled'
    NONE = 'none'


@unique
class NoRouteReason(Enum):
    """Why a code has no route (mapping.NO_ROUTE_REASONS): no catalogue profile, or a profile of another family than
    the code routes to."""
    UNPROFILED = 'unprofiled'
    FAMILY_MISMATCH = 'family_mismatch'


@unique
class SupportLevel(Enum):
    """A family's catalogue support level (studio.gi.catalogue: SUPPORTED, RECOGNISED, UNSUPPORTED)."""
    SUPPORTED = 'supported'
    RECOGNISED = 'recognised'
    UNSUPPORTED = 'unsupported'


@unique
class TechniqueClass(Enum):
    """The technique class a code can depend on (CodeProfile.technique, mapping.TECHNIQUE_CLASS): a transendoscopic
    balloon, dilators over a guide wire, or the unguided bougie (no code depends on the last; it is a class all the
    same, so such a dilation is another technique to a balloon or wire-guided code)."""
    BALLOON = 'balloon'
    WIRE_BOUGIE = 'wire_bougie'
    BOUGIE = 'bougie'


@unique
class SiteClass(Enum):
    """The site class of a site-specific dilation code (DECISIONS D29, mapping.SITE_CLASSES)."""
    ESOPHAGEAL = 'esophageal'
    GASTRIC_DUODENAL = 'gastric_duodenal'


@unique
class EusClass(Enum):
    """The EUS examination class (DECISIONS D28: the catalogue's full and limited; D43: the lower-tract EUS codes'
    sigmoidoscopic, colonoscopic and stoma classes; mapping.examination_class)."""
    FULL = 'full'
    LIMITED = 'limited'
    SIGMOIDOSCOPIC = 'sigmoidoscopic'
    COLONOSCOPIC = 'colonoscopic'
    STOMA = 'stoma'


@unique
class EnteroscopyClass(Enum):
    """The class of a small-bowel enteroscopy code (DECISIONS D108, classes.CLASSES)."""
    JEJUNAL = 'jejunal'
    ILEAL = 'ileal'
    STOMA = 'stoma'
    POUCH = 'pouch'


# --- the families (studio.gi.profiles; lexicon's family tables; mapping.ENDOSCOPIC_FAMILIES) ---------------------------

_OFFICE_EM, _EGD, _ENT, _EUS, _ERCP, _COLON, _SIG = (
    SessionKind.OFFICE_EM, SessionKind.EGD, SessionKind.ENTEROSCOPY, SessionKind.EUS, SessionKind.ERCP,
    SessionKind.COLONOSCOPY, SessionKind.FLEX_SIG)
_CAPSULE, _MOTILITY, _REFLUX, _ANORECTAL, _FEEDING, _SEDATION = (
    SessionKind.CAPSULE, SessionKind.MOTILITY, SessionKind.REFLUX, SessionKind.ANORECTAL, SessionKind.FEEDING_TUBE,
    SessionKind.SEDATION)

# gi.profiles.FAMILY_ORDER (= lexicon.FAMILY_ORDER): the order every family list is written in, and routing's order.
FAMILY_ORDER: tuple[SessionKind, ...] = (
    _OFFICE_EM, _EGD, _ENT, _EUS, _ERCP, _COLON, _SIG, _CAPSULE, _MOTILITY, _REFLUX, _ANORECTAL, _FEEDING, _SEDATION,
    SessionKind.EM_OTHER, SessionKind.OTHER_GI, SessionKind.NOT_GI)

# gi.profiles: the EUS codes carved out of the other ranges, and the codes in the colonoscopy range that are none.
_EUS_CODES = (43231, 43232, 43237, 43238, 43240, 43242, 43253, 43259, 44406, 44407, 45341, 45342, 45391, 45392, 76975)
_NOT_COLONOSCOPY = (45395, 45397, 45399)

# Each family's inclusive routing ranges (gi.profiles' code_ranges, as numbers), in FAMILY_ORDER. Used only to route a
# code to a family; they are not a CPT reference.
CODE_RANGES: Mapping[SessionKind, tuple[tuple[int, int], ...]] = MappingProxyType({
    _OFFICE_EM: ((99202, 99205), (99211, 99215), (99242, 99245), (99417, 99417)),
    _EGD: ((43180, 43233), (43235, 43270), (43210, 43210), (43497, 43497)),
    _ENT: ((44360, 44386),),
    _EUS: tuple((code, code) for code in _EUS_CODES),
    _ERCP: ((43260, 43265), (43273, 43278), (74328, 74330)),
    _COLON: ((45378, 45399), (44388, 44408)),
    _SIG: ((45330, 45350),),
    _CAPSULE: ((91110, 91113),),
    _MOTILITY: ((91010, 91022), (91040, 91040), (91117, 91117)),
    _REFLUX: ((91030, 91038),),
    _ANORECTAL: ((91120, 91122),),
    _FEEDING: ((43762, 43763), (49440, 49452)),
    _SEDATION: ((99151, 99157),),
    SessionKind.EM_OTHER: ((99221, 99239), (99281, 99288), (99291, 99292), (99252, 99255)),
    SessionKind.OTHER_GI: ((43450, 43453), (43752, 43761), (45300, 45327), (46600, 46615), (46221, 46250),
                           (91065, 91065), (91200, 91299), (47000, 47001), (49082, 49084)),
    SessionKind.NOT_GI: (),
})
# The codes each family's ranges carve out and route on (gi.profiles' excluded_codes).
EXCLUDED_CODES: Mapping[SessionKind, frozenset[int]] = MappingProxyType({
    family: frozenset(codes) for family, codes in (
        (_EGD, _EUS_CODES + tuple(code for code in range(43260, 43271) if code not in (43266, 43270))),
        (_COLON, _EUS_CODES + _NOT_COLONOSCOPY),
        (_SIG, _EUS_CODES))})
# The families gi.profiles marks supported, and those it marks procedural (= lexicon.PROCEDURAL_FAMILIES: an endoscopic
# or procedural family, as against E/M).
PROFILE_SUPPORTED: frozenset[SessionKind] = frozenset({
    _OFFICE_EM, _EGD, _ENT, _EUS, _ERCP, _COLON, _SIG, _CAPSULE, _MOTILITY, _REFLUX, _ANORECTAL, _FEEDING})
PROCEDURAL_FAMILIES: frozenset[SessionKind] = frozenset({
    _EGD, _ENT, _EUS, _ERCP, _COLON, _SIG, _CAPSULE, _MOTILITY, _REFLUX, _ANORECTAL, _FEEDING})
# The families an endoscope examines in a session (mapping.ENDOSCOPIC_FAMILIES): their examination is the session every
# act of the family belongs to (FINAL 7.8), and a base or EUS code's examination kind.
ENDOSCOPIC_FAMILIES: frozenset[SessionKind] = frozenset({_EGD, _ENT, _COLON, _SIG, _EUS, _ERCP})
# The E/M families (lexicon.EM_PROCEDURES) and the E/M kinds (lexicon.EM_KINDS).
EM_FAMILIES: frozenset[SessionKind] = frozenset({_OFFICE_EM, SessionKind.EM_OTHER})
EM_KINDS: frozenset[Kind] = frozenset({Kind.EM_VISIT, Kind.EM_PROLONGED})

# Each catalogue entry's support level (FamilyEntry.support); a family with no entry (em_other, not_gi) has none.
FAMILY_SUPPORT: Mapping[SessionKind, SupportLevel] = MappingProxyType({
    **{family: SupportLevel.SUPPORTED for family in (
        _OFFICE_EM, _EGD, _ENT, _COLON, _SIG, _EUS, _ERCP, _CAPSULE, _MOTILITY, _REFLUX, _ANORECTAL, _FEEDING)},
    _SEDATION: SupportLevel.RECOGNISED, SessionKind.OTHER_GI: SupportLevel.RECOGNISED,
})
# The act kinds each catalogue entry reconciles with codes (FamilyEntry.acts), in its order; the EUS's 'eus_exam' is its
# examination (Kind.EXAMINATION).
_ENDOSCOPIC_ACTS = (Kind.BIOPSY, Kind.HOT_BIOPSY, Kind.SNARE, Kind.EMR, Kind.ABLATION, Kind.BLEEDING_CONTROL,
                    Kind.INJECTION, Kind.TATTOO, Kind.BAND_LIGATION, Kind.DILATION, Kind.STENT, Kind.FOREIGN_BODY,
                    Kind.DECOMPRESSION)
FAMILY_ACTS: Mapping[SessionKind, tuple[Kind, ...]] = MappingProxyType({
    _OFFICE_EM: (Kind.EM_VISIT,),
    _EGD: _ENDOSCOPIC_ACTS + (Kind.PEG, Kind.TUBE_PLACEMENT, Kind.MYOTOMY, Kind.FUNDOPLICATION),
    _ENT: (Kind.BIOPSY, Kind.HOT_BIOPSY, Kind.SNARE, Kind.ABLATION, Kind.BLEEDING_CONTROL, Kind.STENT,
           Kind.FOREIGN_BODY, Kind.DILATION, Kind.TUBE_PLACEMENT, Kind.PEG, Kind.TUBE_REPLACEMENT),
    _COLON: _ENDOSCOPIC_ACTS,
    _SIG: _ENDOSCOPIC_ACTS,
    _EUS: (Kind.EXAMINATION, Kind.FNA, Kind.INJECTION, Kind.DRAINAGE),
    _ERCP: (Kind.BIOPSY, Kind.SPHINCTEROTOMY, Kind.STONE_EXTRACTION, Kind.LITHOTRIPSY, Kind.CHOLANGIOSCOPY, Kind.STENT,
            Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE, Kind.DILATION, Kind.ABLATION, Kind.PRESSURE_MEASUREMENT),
    _CAPSULE: (Kind.CAPSULE_STUDY,),
    _MOTILITY: (Kind.MANOMETRY,),
    _REFLUX: (Kind.PH_MONITORING,),
    _ANORECTAL: (Kind.MANOMETRY, Kind.RECTAL_SENSATION),
    _FEEDING: (Kind.PEG, Kind.TUBE_PLACEMENT, Kind.TUBE_REPLACEMENT),
    _SEDATION: (Kind.MODERATE_SEDATION,),
    SessionKind.OTHER_GI: (),
})
# The kinds each catalogue entry names as not separately reported in its family (FamilyEntry.bundled: COMMON_BUNDLED's
# clip and cannulation in the four endoscopies, the EUS's forceps biopsy, the ERCP's cannulation, contrast injection and
# clip, the reflux study's pH capsule), and as having no code profile in it (FamilyEntry.unsupported_acts: the ESD of an
# EGD or a colonoscopy, the EUS's drainage other than of a pseudocyst, the anorectal balloon expulsion): the Kind-valued
# parts of both, by value (DECISIONS D191). 4.7's bundling reads "a family's bundled kinds" here, and
# requirements_table.FAMILY_KINDS, the kinds of a session family that K2 and possibly's kind arm read, unions both with
# FAMILY_ACTS. Keyed as FAMILY_ACTS is (an entry that names none has the empty set). The items that name a rule are not
# kinds and are not here (module docstring), nor any sentence.
_NO_KINDS: frozenset[Kind] = frozenset()
_COMMON_BUNDLED_KINDS = frozenset({Kind.CLIP, Kind.CANNULATION})
BUNDLED_KINDS: Mapping[SessionKind, frozenset[Kind]] = MappingProxyType({
    **{family: _NO_KINDS for family in FAMILY_ACTS},
    _EGD: _COMMON_BUNDLED_KINDS, _ENT: _COMMON_BUNDLED_KINDS, _COLON: _COMMON_BUNDLED_KINDS,
    _SIG: _COMMON_BUNDLED_KINDS, _EUS: frozenset({Kind.BIOPSY}),
    _ERCP: frozenset({Kind.CANNULATION, Kind.INJECTION, Kind.CLIP}), _REFLUX: frozenset({Kind.CAPSULE_STUDY}),
})
UNSUPPORTED_KINDS: Mapping[SessionKind, frozenset[Kind]] = MappingProxyType({
    **{family: _NO_KINDS for family in FAMILY_ACTS},
    _EGD: frozenset({Kind.ESD}), _COLON: frozenset({Kind.ESD}), _EUS: frozenset({Kind.DRAINAGE}),
    _ANORECTAL: frozenset({Kind.BALLOON_EXPULSION}),
})

# The families whose examination reaches each place an anastomosis can take (mapping.ANASTOMOSIS_FAMILIES, D34): an
# upper endoscopy the esophagus and the stomach side, a colonoscopy or a sigmoidoscopy the right colon side and the rectum.
_UPPER_FAMILIES = frozenset({_EGD, _EUS, _ERCP, _ENT})
_LOWER_FAMILIES = frozenset({_COLON, _SIG})
ANASTOMOSIS_FAMILIES: Mapping[Landmark, frozenset[SessionKind]] = MappingProxyType({
    Landmark.ESOPHAGUS: _UPPER_FAMILIES, Landmark.STOMACH: _UPPER_FAMILIES, Landmark.RIGHT_COLON: _LOWER_FAMILIES,
    Landmark.RECTUM: _LOWER_FAMILIES})

# A profile rule that reads an act under another family (catalogue.READ_UNDER): (family, kind) -> (that family, the
# regions where it reads such an act). An EUS forceps biopsy at an upper GI place is read under the EGD.
READ_UNDER: Mapping[tuple[SessionKind, Kind], tuple[SessionKind, frozenset[Region]]] = MappingProxyType({
    (_EUS, Kind.BIOPSY): (_EGD, frozenset({Region.ESOPHAGUS, Region.STOMACH, Region.DUODENUM}))})

# K3's reach (FINAL-V2 3.1 K3; DECISIONS D192): the regions a session of each family can reach, v1's
# studio.gi.services.FAMILY_REGIONS by value - an upper endoscopy the upper tract (the esophagus, the stomach, the
# duodenum), a colonoscopy the lower tract (the colon, the rectum, the anus) and the small bowel beyond its valve, a
# sigmoidoscopy the lower tract, an enteroscopy the small bowel. A family that is not here (the EUS, the ERCP, every
# family that is no endoscopy) is not judged. K3 only demotes and never moves an act; its known over-holds are
# fail-closed residuals that D192 records (an EGD biopsy at the ampulla, which REGION_OF puts in the biliary region; a
# push enteroscopy's gastric act), and a change to this table needs a DECISIONS entry on development evidence.
_UPPER_TRACT = frozenset({Region.ESOPHAGUS, Region.STOMACH, Region.DUODENUM})
_LOWER_TRACT = frozenset({Region.COLON, Region.RECTUM, Region.ANUS})
FAMILY_REACH: Mapping[SessionKind, frozenset[Region]] = MappingProxyType({
    _EGD: _UPPER_TRACT, _COLON: _LOWER_TRACT | frozenset({Region.SMALL_BOWEL}), _SIG: _LOWER_TRACT,
    _ENT: frozenset({Region.SMALL_BOWEL})})

# Acts that never need a code of their own, whatever the family (catalogue.NOT_REPORTED), and acts no profile reconciles
# (catalogue.UNSUPPORTED_ACTS). The per-family tables are BUNDLED_KINDS and UNSUPPORTED_KINDS above.
NOT_REPORTED: frozenset[Kind] = frozenset({Kind.CLIP, Kind.CANNULATION})
UNSUPPORTED_ACTS: frozenset[Kind] = frozenset({Kind.ESD})


def number(code: object) -> int | None:
    """The number ``code`` names when it is a str in canonical decimal form (no sign, space, separator, leading zero or
    other digits than 0-9): the key of every code-keyed table here. None otherwise. A code string matches a table's
    number exactly when it equals that number's canonical form, as v1's string keys match."""
    if not isinstance(code, str):
        return None
    try:
        value = int(code)
    except ValueError:
        return None
    return value if str(value) == code else None


# The routing carve-outs as the strings routing compares (computed from the numbers above).
_EXCLUDED_FORMS: Mapping[SessionKind, frozenset[str]] = MappingProxyType({
    family: frozenset(str(code) for code in codes) for family, codes in EXCLUDED_CODES.items()})


def family_for_code(code: object) -> SessionKind:
    """gi.profiles.family_for_code: route a provider code to a family by number only; NOT_GI (gi.unsupported) when none
    applies. Never raises. gi.profiles' own rule, kept exactly: a str of five characters for which str.isdigit holds,
    compared as a string with each range's bounds, families in FAMILY_ORDER, carve-outs skipped."""
    if not (isinstance(code, str) and len(code) == 5 and code.isdigit()):
        return SessionKind.NOT_GI
    for family in FAMILY_ORDER:
        if code in _EXCLUDED_FORMS.get(family, frozenset()):
            continue
        for low, high in CODE_RANGES[family]:
            if str(low) <= code <= str(high):
                return family
    return SessionKind.NOT_GI


# --- the code profiles (studio.gi.catalogue.CODES) ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Profile:
    """A code's catalogue profile (catalogue.CodeProfile): its family; covers, the act kinds it accounts for; base, the
    family's examination without an intervention; exam, an EUS examination class where the catalogue gives one; addon;
    includes, the families whose examination it includes (an EGD-with-EUS code includes the upper endoscopy that is the
    EUS's endoscopic portion); technique, the one dilation technique it accounts for, None for any."""
    family: SessionKind
    covers: tuple[Kind, ...] = ()
    base: bool = False
    exam: EusClass | None = None
    addon: bool = False
    includes: tuple[SessionKind, ...] = ()
    technique: TechniqueClass | None = None


def _c(family: SessionKind, covers: tuple[Kind, ...] = (), *, base: bool = False, exam: EusClass | None = None,
       addon: bool = False, includes: tuple[SessionKind, ...] = (), technique: TechniqueClass | None = None) -> Profile:
    return Profile(family, covers, base, exam, addon, includes, technique)


# Every catalogue code (the 163 of studio.gi.catalogue.CODES, in its order) -> its profile. An INTERNAL engineering
# profile used only to reconcile proposals with documented acts: not a CPT reference, no descriptor.
CODES: Mapping[int, Profile] = MappingProxyType({
    **{code: _c(_OFFICE_EM, (Kind.EM_VISIT,), base=True) for code in (
        99202, 99203, 99204, 99205, 99211, 99212, 99213, 99214, 99215, 99242, 99243, 99244, 99245)},
    99417: _c(_OFFICE_EM, (Kind.EM_PROLONGED,), addon=True),
    # EGD
    43235: _c(_EGD, base=True), 43236: _c(_EGD, (Kind.INJECTION,)), 43239: _c(_EGD, (Kind.BIOPSY,)),
    43241: _c(_EGD, (Kind.TUBE_PLACEMENT,)), 43243: _c(_EGD, (Kind.INJECTION,)), 43244: _c(_EGD, (Kind.BAND_LIGATION,)),
    43245: _c(_EGD, (Kind.DILATION,)), 43246: _c(_EGD, (Kind.PEG,)), 43247: _c(_EGD, (Kind.FOREIGN_BODY,)),
    43248: _c(_EGD, (Kind.DILATION,), technique=TechniqueClass.WIRE_BOUGIE),
    43249: _c(_EGD, (Kind.DILATION,), technique=TechniqueClass.BALLOON),
    43233: _c(_EGD, (Kind.DILATION,), technique=TechniqueClass.BALLOON), 43250: _c(_EGD, (Kind.HOT_BIOPSY,)),
    43251: _c(_EGD, (Kind.SNARE,)), 43254: _c(_EGD, (Kind.EMR,)), 43255: _c(_EGD, (Kind.BLEEDING_CONTROL,)),
    43257: _c(_EGD, (Kind.ABLATION,)), 43266: _c(_EGD, (Kind.STENT,)), 43270: _c(_EGD, (Kind.ABLATION,)),
    43210: _c(_EGD, (Kind.FUNDOPLICATION,)), 43497: _c(_EGD, (Kind.MYOTOMY,)),
    # esophagoscopy (flexible transoral and transnasal), in the upper GI family
    43200: _c(_EGD, base=True), 43201: _c(_EGD, (Kind.INJECTION,)), 43202: _c(_EGD, (Kind.BIOPSY,)),
    43204: _c(_EGD, (Kind.INJECTION,)), 43205: _c(_EGD, (Kind.BAND_LIGATION,)), 43211: _c(_EGD, (Kind.EMR,)),
    43212: _c(_EGD, (Kind.STENT,)), 43213: _c(_EGD, (Kind.DILATION,)),
    43214: _c(_EGD, (Kind.DILATION,), technique=TechniqueClass.BALLOON), 43215: _c(_EGD, (Kind.FOREIGN_BODY,)),
    43216: _c(_EGD, (Kind.HOT_BIOPSY,)), 43217: _c(_EGD, (Kind.SNARE,)),
    43220: _c(_EGD, (Kind.DILATION,), technique=TechniqueClass.BALLOON),
    43226: _c(_EGD, (Kind.DILATION,), technique=TechniqueClass.WIRE_BOUGIE), 43227: _c(_EGD, (Kind.BLEEDING_CONTROL,)),
    43229: _c(_EGD, (Kind.ABLATION,)), 43197: _c(_EGD, base=True), 43198: _c(_EGD, (Kind.BIOPSY,)),
    # small-bowel enteroscopy, ileoscopy and pouchoscopy through a stoma
    44360: _c(_ENT, base=True), 44361: _c(_ENT, (Kind.BIOPSY,)), 44363: _c(_ENT, (Kind.FOREIGN_BODY,)),
    44364: _c(_ENT, (Kind.SNARE,)), 44365: _c(_ENT, (Kind.HOT_BIOPSY, Kind.ABLATION)),
    44366: _c(_ENT, (Kind.BLEEDING_CONTROL,)), 44369: _c(_ENT, (Kind.ABLATION,)), 44370: _c(_ENT, (Kind.STENT,)),
    44372: _c(_ENT, (Kind.TUBE_PLACEMENT, Kind.PEG)), 44373: _c(_ENT, (Kind.TUBE_REPLACEMENT,)),
    44376: _c(_ENT, base=True), 44377: _c(_ENT, (Kind.BIOPSY,)), 44378: _c(_ENT, (Kind.BLEEDING_CONTROL,)),
    44379: _c(_ENT, (Kind.STENT,)), 44380: _c(_ENT, base=True),
    44381: _c(_ENT, (Kind.DILATION,), technique=TechniqueClass.BALLOON), 44382: _c(_ENT, (Kind.BIOPSY,)),
    44384: _c(_ENT, (Kind.STENT,)), 44385: _c(_ENT, base=True), 44386: _c(_ENT, (Kind.BIOPSY,)),
    # colonoscopy (and through a stoma)
    45378: _c(_COLON, base=True), 45379: _c(_COLON, (Kind.FOREIGN_BODY,)), 45380: _c(_COLON, (Kind.BIOPSY,)),
    45381: _c(_COLON, (Kind.INJECTION, Kind.TATTOO)), 45382: _c(_COLON, (Kind.BLEEDING_CONTROL,)),
    45384: _c(_COLON, (Kind.HOT_BIOPSY,)), 45385: _c(_COLON, (Kind.SNARE,)),
    45386: _c(_COLON, (Kind.DILATION,), technique=TechniqueClass.BALLOON), 45388: _c(_COLON, (Kind.ABLATION,)),
    45389: _c(_COLON, (Kind.STENT,)), 45390: _c(_COLON, (Kind.EMR,)), 45393: _c(_COLON, (Kind.DECOMPRESSION,)),
    45398: _c(_COLON, (Kind.BAND_LIGATION,)), 44388: _c(_COLON, base=True), 44389: _c(_COLON, (Kind.BIOPSY,)),
    44390: _c(_COLON, (Kind.FOREIGN_BODY,)), 44391: _c(_COLON, (Kind.BLEEDING_CONTROL,)),
    44392: _c(_COLON, (Kind.HOT_BIOPSY,)), 44394: _c(_COLON, (Kind.SNARE,)), 44401: _c(_COLON, (Kind.ABLATION,)),
    44402: _c(_COLON, (Kind.STENT,)), 44403: _c(_COLON, (Kind.EMR,)), 44404: _c(_COLON, (Kind.INJECTION, Kind.TATTOO)),
    44405: _c(_COLON, (Kind.DILATION,), technique=TechniqueClass.BALLOON), 44408: _c(_COLON, (Kind.DECOMPRESSION,)),
    # flexible sigmoidoscopy
    45330: _c(_SIG, base=True), 45331: _c(_SIG, (Kind.BIOPSY,)), 45332: _c(_SIG, (Kind.FOREIGN_BODY,)),
    45333: _c(_SIG, (Kind.HOT_BIOPSY,)), 45334: _c(_SIG, (Kind.BLEEDING_CONTROL,)),
    45335: _c(_SIG, (Kind.INJECTION, Kind.TATTOO)), 45337: _c(_SIG, (Kind.DECOMPRESSION,)),
    45338: _c(_SIG, (Kind.SNARE,)), 45340: _c(_SIG, (Kind.DILATION,), technique=TechniqueClass.BALLOON),
    45346: _c(_SIG, (Kind.ABLATION,)), 45347: _c(_SIG, (Kind.STENT,)), 45349: _c(_SIG, (Kind.EMR,)),
    45350: _c(_SIG, (Kind.BAND_LIGATION,)),
    # endoscopic ultrasound: only the codes of an EGD with EUS include an upper endoscopy's examination
    43231: _c(_EUS, (Kind.EXAMINATION,), exam=EusClass.LIMITED),
    43232: _c(_EUS, (Kind.EXAMINATION, Kind.FNA), exam=EusClass.LIMITED),
    43237: _c(_EUS, (Kind.EXAMINATION,), exam=EusClass.LIMITED, includes=(_EGD,)),
    43238: _c(_EUS, (Kind.EXAMINATION, Kind.FNA), exam=EusClass.LIMITED, includes=(_EGD,)),
    43242: _c(_EUS, (Kind.EXAMINATION, Kind.FNA), exam=EusClass.FULL, includes=(_EGD,)),
    43259: _c(_EUS, (Kind.EXAMINATION,), exam=EusClass.FULL, includes=(_EGD,)),
    43253: _c(_EUS, (Kind.EXAMINATION, Kind.INJECTION), includes=(_EGD,)),
    43240: _c(_EUS, (Kind.EXAMINATION, Kind.DRAINAGE), includes=(_EGD,)),
    45341: _c(_EUS, (Kind.EXAMINATION,)), 45342: _c(_EUS, (Kind.EXAMINATION, Kind.FNA)),
    45391: _c(_EUS, (Kind.EXAMINATION,)), 45392: _c(_EUS, (Kind.EXAMINATION, Kind.FNA)),
    44406: _c(_EUS, (Kind.EXAMINATION,)), 44407: _c(_EUS, (Kind.EXAMINATION, Kind.FNA)),
    # ERCP
    43260: _c(_ERCP, base=True), 43261: _c(_ERCP, (Kind.BIOPSY,)), 43262: _c(_ERCP, (Kind.SPHINCTEROTOMY,)),
    43263: _c(_ERCP, (Kind.PRESSURE_MEASUREMENT,)), 43264: _c(_ERCP, (Kind.STONE_EXTRACTION,)),
    43265: _c(_ERCP, (Kind.LITHOTRIPSY, Kind.STONE_EXTRACTION)), 43273: _c(_ERCP, (Kind.CHOLANGIOSCOPY,), addon=True),
    43274: _c(_ERCP, (Kind.STENT,)), 43275: _c(_ERCP, (Kind.STENT_REMOVAL, Kind.FOREIGN_BODY)),
    43276: _c(_ERCP, (Kind.STENT_EXCHANGE,)), 43277: _c(_ERCP, (Kind.DILATION,), technique=TechniqueClass.BALLOON),
    43278: _c(_ERCP, (Kind.ABLATION,)),
    # capsule endoscopy
    91110: _c(_CAPSULE, (Kind.CAPSULE_STUDY,)), 91111: _c(_CAPSULE, (Kind.CAPSULE_STUDY,)),
    91113: _c(_CAPSULE, (Kind.CAPSULE_STUDY,)),
    # motility and manometry
    91010: _c(_MOTILITY, (Kind.MANOMETRY,)), 91013: _c(_MOTILITY, (Kind.MANOMETRY,), addon=True),
    91020: _c(_MOTILITY, (Kind.MANOMETRY,)), 91022: _c(_MOTILITY, (Kind.MANOMETRY,)),
    91117: _c(_MOTILITY, (Kind.MANOMETRY,)), 91040: _c(_MOTILITY, (Kind.MANOMETRY,)),
    # pH and impedance
    91034: _c(_REFLUX, (Kind.PH_MONITORING,)), 91035: _c(_REFLUX, (Kind.PH_MONITORING,)),
    91037: _c(_REFLUX, (Kind.PH_MONITORING,)), 91038: _c(_REFLUX, (Kind.PH_MONITORING,)),
    91030: _c(_REFLUX, (Kind.PH_MONITORING,)),
    # anorectal testing
    91120: _c(_ANORECTAL, (Kind.RECTAL_SENSATION,)), 91122: _c(_ANORECTAL, (Kind.MANOMETRY,)),
    # feeding tubes outside an endoscopy
    43762: _c(_FEEDING, (Kind.TUBE_REPLACEMENT,)), 43763: _c(_FEEDING, (Kind.TUBE_REPLACEMENT,)),
    49440: _c(_FEEDING, (Kind.PEG, Kind.TUBE_PLACEMENT)), 49441: _c(_FEEDING, (Kind.TUBE_PLACEMENT,)),
    49446: _c(_FEEDING, (Kind.TUBE_PLACEMENT,)), 49450: _c(_FEEDING, (Kind.TUBE_REPLACEMENT,)),
    49451: _c(_FEEDING, (Kind.TUBE_REPLACEMENT,)), 49452: _c(_FEEDING, (Kind.TUBE_REPLACEMENT,)),
    # moderate sedation by the performing physician
    99152: _c(_SEDATION, (Kind.MODERATE_SEDATION,)), 99153: _c(_SEDATION, (Kind.MODERATE_SEDATION,), addon=True),
})

# The act a code of a family the catalogue does not reconcile accounts for (catalogue.UNRECONCILED_ACTS, route (b):
# 46221, a hemorrhoid band ligation), and where that act is done (catalogue.UNRECONCILED_REGIONS).
UNRECONCILED_ACTS: Mapping[int, tuple[Kind, ...]] = MappingProxyType({46221: (Kind.BAND_LIGATION,)})
UNRECONCILED_REGIONS: Mapping[int, tuple[Region, ...]] = MappingProxyType({46221: (Region.RECTUM, Region.ANUS)})


def code_profile(code: object) -> Profile | None:
    """catalogue.code_profile: the profile of ``code`` (its canonical number's), None when it has none."""
    found = number(code)
    return CODES.get(found) if found is not None else None


def includes_examination(code: object, family: SessionKind) -> bool:
    """catalogue.includes_examination: whether ``code`` includes the examination of a session of ``family`` of another
    family (an EGD-with-EUS code includes the upper endoscopy that is the EUS's endoscopic portion). A code with no
    profile includes none."""
    profile = code_profile(code)
    return profile is not None and family in profile.includes


def family_codes_act(family: SessionKind, kind: Kind) -> bool:
    """catalogue.family_codes_act: whether a code of ``family`` accounts for an act of ``kind`` (a tattoo and an
    injection are one act for coding). The examination is the session (C-1): Kind.EXAMINATION answers as v1's catalogue
    kind of the family's examination did - True only for the EUS, whose codes cover their examination. This is not the
    set of kinds a session of the family can hold: K2 and possibly's kind arm read requirements_table.FAMILY_KINDS
    (DECISIONS D191), which adds the family's acts, BUNDLED_KINDS, UNSUPPORTED_KINDS and the rest to these kinds (an
    ERCP cannulation is no kind an ERCP code accounts for, and it is one an ERCP session holds)."""
    covers = _FAMILY_COVERS.get(family, frozenset())
    return kind in covers or (kind in ONE_ACT and bool(covers & ONE_ACT))


# --- the defining kinds of a code (DECISIONS D27; FINAL 7.3) ------------------------------------------------------------


def _defining(code: int, profile: Profile, codes: Mapping[int, Profile]) -> tuple[Kind, ...]:
    """mapping._defining: D(C), the kinds of C's covers that no other code of C's family covers ALONE (as its one covered
    kind), in covers order; () unless that set is non-empty and smaller than C's covers."""
    alone = {other.covers[0] for other_code, other in codes.items()
             if other_code != code and other.family is profile.family and len(other.covers) == 1}
    kinds = tuple(kind for kind in profile.covers if kind not in alone)
    return kinds if kinds and set(kinds) < set(profile.covers) else ()


# code -> D(C), for every catalogue code D27 narrows (computed from CODES: 43265 lithotripsy, the EUS sampling, drainage
# and injection codes their act, 44365 hot_biopsy, 49440 peg).
DEFINING: Mapping[int, tuple[Kind, ...]] = MappingProxyType({
    code: kinds for code, kinds in ((code, _defining(code, profile, CODES)) for code, profile in CODES.items()) if kinds})


def defining(code: object) -> tuple[Kind, ...]:
    """D27: the defining kinds of ``code``, () where D27 does not narrow it."""
    found = number(code)
    return DEFINING.get(found, ()) if found is not None else ()


# --- the umbrellas and what covers what (contract 6.4-6.5) -------------------------------------------------------------

# The removal umbrella's methods (reconcile.REMOVAL_KINDS), and the intervention umbrella's members: every act kind but
# the examination, the visit, prolonged visit time, moderate sedation, the umbrella itself and other, in Kind's order (a
# positive removal, method not stated, is an intervention too).
REMOVAL_MEMBERS: tuple[Kind, ...] = (Kind.SNARE, Kind.EMR, Kind.HOT_BIOPSY, Kind.ESD)
_NOT_INTERVENTIONS = frozenset({Kind.EXAMINATION, Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION,
                                Kind.INTERVENTION, Kind.OTHER})
INTERVENTION_MEMBERS: tuple[Kind, ...] = tuple(kind for kind in Kind if kind not in _NOT_INTERVENTIONS)
UMBRELLAS: Mapping[Kind, tuple[Kind, ...]] = MappingProxyType({Kind.REMOVAL: REMOVAL_MEMBERS,
                                                               Kind.INTERVENTION: INTERVENTION_MEMBERS})
# A tattoo and an injection are one act for coding (catalogue.family_codes_act).
ONE_ACT: frozenset[Kind] = frozenset({Kind.TATTOO, Kind.INJECTION})
# The kinds a clip or an injection whose purpose is supported hemostasis is read as (COMMON_BUNDLED's clip rule).
HEMOSTASIS_KINDS: frozenset[Kind] = frozenset({Kind.CLIP, Kind.INJECTION})

# Each family's covered kinds (family_codes_act), from CODES.
_FAMILY_COVERS: Mapping[SessionKind, frozenset[Kind]] = MappingProxyType({
    family: frozenset(kind for profile in CODES.values() if profile.family is family for kind in profile.covers)
    for family in FAMILY_ORDER})


def catalogue_kind(kind: Kind, purpose: Purpose | None = None) -> Kind | None:
    """The catalogue kind of an act of ``kind`` whose SUPPORTED purpose is ``purpose`` (None when its purpose is not
    supported): mapping.catalogue_kind's enumeration arm. A clip or an injection whose purpose is hemostasis is a
    bleeding control (COMMON_BUNDLED's clip rule); other is no catalogue kind (listed for the reviewer, never
    reconciled); every other kind is itself. An examination is Kind.EXAMINATION in every family (its session kind tells
    the EUS one apart, C-1). The cause never changes the kind: CAUSE is a requirement of the codes covering a bleeding
    control (FINAL-V2 4.3). v1's word arms (D115, D142, D149 and D157's bleeding words and adjective key) are dropped
    (D180); D157's doubt - a clip or an injection whose purpose or cause is not established may be a bleeding control -
    is the caller's, read by possibly (FINAL-V2 4.2, 4.6 condition 5)."""
    if kind is Kind.OTHER:
        return None
    if kind in HEMOSTASIS_KINDS and purpose is Purpose.HEMOSTASIS:
        return Kind.BLEEDING_CONTROL
    return kind


def covers(statement: Kind | None, act: Kind | None) -> bool:
    """mapping.covers: whether a statement of catalogue kind ``statement`` concerns an act of catalogue kind ``act``
    (contract 6.4-6.5): the same kind, a tattoo and an injection as one act, or an umbrella covering its members. Never
    for None or other (no catalogue kind)."""
    if statement is None or act is None or statement is Kind.OTHER or act is Kind.OTHER:
        return False
    if statement is act or (statement in ONE_ACT and act in ONE_ACT):
        return True
    return act in UMBRELLAS.get(statement, ())


# --- technique classes (CodeProfile.technique; mapping.TECHNIQUE_CLASS) -------------------------------------------------

# The devices that name a technique class a code can depend on; every other device is evidence only.
TECHNIQUE_CLASS: Mapping[Device, TechniqueClass] = MappingProxyType({
    Device.BALLOON: TechniqueClass.BALLOON, Device.WIRE_BOUGIE: TechniqueClass.WIRE_BOUGIE,
    Device.BOUGIE: TechniqueClass.BOUGIE})


def technique_class(device: Device | None) -> TechniqueClass | None:
    """mapping.code_technique over a SUPPORTED device: its technique class, None when it names none (or when the device
    is not supported, which the caller passes as None)."""
    return TECHNIQUE_CLASS.get(device) if device is not None else None


def technique_dependent(family: SessionKind | None, kind: Kind) -> bool:
    """mapping.technique_dependent: whether a code of ``family`` that accounts for ``kind`` depends on the technique (a
    profile with a technique: the dilation codes). With no family, any family's profile counts (fail toward asking)."""
    return any(profile.technique is not None and kind in profile.covers
               and (family is None or profile.family is family) for profile in CODES.values())


# --- the site of a dilation (DECISIONS D29; FINAL 7.2 R4) ----------------------------------------------------------------

# Each site class's landmarks, exactly as D29 lists them (no containment is read: the GE junction is esophageal; the
# ampulla, the jejunum and every surgically made place are in neither class), with LANDMARKS2's third and fourth duodenal
# portions where the duodenum stands (module docstring; DECISIONS D204).
SITE_CLASSES: Mapping[SiteClass, frozenset[Landmark]] = MappingProxyType({
    SiteClass.ESOPHAGEAL: frozenset({Landmark.ESOPHAGUS, Landmark.PROXIMAL_ESOPHAGUS, Landmark.MID_ESOPHAGUS,
                                     Landmark.DISTAL_ESOPHAGUS, Landmark.GASTROESOPHAGEAL_JUNCTION}),
    SiteClass.GASTRIC_DUODENAL: frozenset({Landmark.STOMACH, Landmark.GASTRIC_CARDIA, Landmark.GASTRIC_FUNDUS,
                                           Landmark.GASTRIC_BODY, Landmark.GASTRIC_ANTRUM, Landmark.PYLORUS,
                                           Landmark.DUODENUM, Landmark.DUODENAL_BULB, Landmark.SECOND_PORTION_DUODENUM,
                                           Landmark.THIRD_PORTION_DUODENUM, Landmark.FOURTH_PORTION_DUODENUM}),
})
# The site-specific dilation codes and their site class, by the structure their descriptors name (mapping.DILATION_SITES;
# cited there for the engineer). Every other dilation code is not here.
DILATION_SITES: Mapping[int, SiteClass] = MappingProxyType({
    43213: SiteClass.ESOPHAGEAL, 43214: SiteClass.ESOPHAGEAL, 43220: SiteClass.ESOPHAGEAL, 43226: SiteClass.ESOPHAGEAL,
    43233: SiteClass.ESOPHAGEAL, 43248: SiteClass.ESOPHAGEAL, 43249: SiteClass.ESOPHAGEAL,
    43245: SiteClass.GASTRIC_DUODENAL})


def site_class(code: object) -> SiteClass | None:
    """D29: the site class of a site-specific dilation code, None for any other code."""
    found = number(code)
    return DILATION_SITES.get(found) if found is not None else None


# --- the EUS examination class and tract (DECISIONS D28, D43, D171; mapping's EUS tables) -------------------------------

EXAMINATION_CLASSES: tuple[EusClass, ...] = (EusClass.FULL, EusClass.LIMITED)  # catalogue.CodeProfile.exam
# The reach of the session's EUS examination each class needs, over EXTENTS (the values a session's reached holds). D28:
# a FULL examination at or beyond the duodenum (the duodenum, its bulb, its portions, the ampulla, the jejunum); a LIMITED
# one short of the duodenum (the esophagus's and the stomach's landmarks). D43: a flexible sigmoidoscopy's reach, a
# colonoscopy's (beyond the splenic flexure, to the cecum), and a colonoscopy's through a stoma (either, the colon or the
# stoma). A reach anywhere else (the small bowel named as such, an anastomosis, an organ beside the tract, a stated depth)
# fits none of them.
FULL_REACH: frozenset[Extent] = frozenset({
    Extent.DUODENUM, Extent.DUODENAL_BULB, Extent.SECOND_PORTION_DUODENUM, Extent.THIRD_PORTION_DUODENUM,
    Extent.FOURTH_PORTION_DUODENUM, Extent.AMPULLA, Extent.JEJUNUM})
SHORT_OF_DUODENUM: frozenset[Extent] = frozenset({
    Extent.ESOPHAGUS, Extent.PROXIMAL_ESOPHAGUS, Extent.MID_ESOPHAGUS, Extent.DISTAL_ESOPHAGUS,
    Extent.GASTROESOPHAGEAL_JUNCTION, Extent.STOMACH, Extent.GASTRIC_CARDIA, Extent.GASTRIC_FUNDUS, Extent.GASTRIC_BODY,
    Extent.GASTRIC_ANTRUM, Extent.PYLORUS})
SIGMOIDOSCOPIC_REACH: frozenset[Extent] = frozenset({
    Extent.RECTUM, Extent.RECTOSIGMOID, Extent.SIGMOID_COLON, Extent.DESCENDING_COLON, Extent.LEFT_COLON,
    Extent.DISTAL_COLON})
COLONOSCOPIC_REACH: frozenset[Extent] = frozenset({
    Extent.TRANSVERSE_COLON, Extent.HEPATIC_FLEXURE, Extent.ASCENDING_COLON, Extent.RIGHT_COLON, Extent.PROXIMAL_COLON,
    Extent.CECUM, Extent.APPENDICEAL_ORIFICE, Extent.ILEOCECAL_VALVE, Extent.TERMINAL_ILEUM, Extent.ILEUM,
    Extent.NEO_TERMINAL_ILEUM})
STOMA_REACH: frozenset[Extent] = SIGMOIDOSCOPIC_REACH | COLONOSCOPIC_REACH | frozenset({Extent.COLON, Extent.STOMA})
EUS_CLASS_REACH: Mapping[EusClass, frozenset[Extent]] = MappingProxyType({
    EusClass.FULL: FULL_REACH, EusClass.LIMITED: SHORT_OF_DUODENUM, EusClass.SIGMOIDOSCOPIC: SIGMOIDOSCOPIC_REACH,
    EusClass.COLONOSCOPIC: COLONOSCOPIC_REACH, EusClass.STOMA: STOMA_REACH})
# D43: the lower-tract EUS codes, to which the catalogue gives no class, take the class of the lower endoscopy they are
# done through.
LOWER_EUS_CLASS: Mapping[int, EusClass] = MappingProxyType({
    45341: EusClass.SIGMOIDOSCOPIC, 45342: EusClass.SIGMOIDOSCOPIC, 45391: EusClass.COLONOSCOPIC,
    45392: EusClass.COLONOSCOPIC, 44406: EusClass.STOMA, 44407: EusClass.STOMA})
# D171 (2): the EUS codes of an upper endoscopy (an esophagoscopy's and an EGD's, transoral), which need an upper-tract
# EUS session; D171 (3): the EGD's limited EUS codes (an examination limited to the esophagus, stomach or duodenum).
UPPER_EUS_CODES: frozenset[int] = frozenset({43231, 43232, 43237, 43238, 43240, 43242, 43253, 43259})
EGD_LIMITED_EUS_CODES: frozenset[int] = frozenset({43237, 43238})
# The upper tract's EUS stations in the order an upper EUS passes them (FINAL-V2 4.3 STATIONS: each supported examined),
# and every region an upper endoscopy's EUS examines or samples from them (the stations' regions, and the pancreas, the
# biliary tree and the liver beside them).
UPPER_STATIONS: tuple[Station, ...] = (Station.ESOPHAGUS, Station.STOMACH, Station.DUODENUM)
UPPER_TRACT_REGIONS: frozenset[Region] = frozenset({Region.ESOPHAGUS, Region.STOMACH, Region.DUODENUM, Region.PANCREAS,
                                                    Region.BILIARY, Region.LIVER})
# D171 (4): the EUS-guided TRANSMURAL injection code (FINAL-V2 4.3 ROUTE: technique.route eus_transmural).
TRANSMURAL_INJECTION_CODES: frozenset[int] = frozenset({43253})
# D120: the regions where a supported place of 43240's drainage sets it apart from a pancreatic fluid collection's
# drainage (FINAL-V2 4.3 STRUCT:pfc: no supported place biliary or hepatic). DEFINING_TARGETS' phrases are not ported.
DEFINING_TARGET_APART: frozenset[Region] = frozenset({Region.BILIARY, Region.LIVER})


def examination_class(code: object) -> EusClass | None:
    """mapping.examination_class: the EUS examination class of ``code`` - the catalogue's (full | limited), or D43's
    lower-tract class (sigmoidoscopic | colonoscopic | stoma); None for a code with none."""
    profile = code_profile(code)
    if profile is not None and profile.exam in EXAMINATION_CLASSES:
        return profile.exam
    found = number(code)
    return LOWER_EUS_CLASS.get(found) if found is not None else None


def eus_tract(code: object) -> Tract | None:
    """mapping.eus_tract (D171 (2)): UPPER for an upper endoscopy's EUS code, LOWER for D43's lower-tract EUS codes,
    None for any other code."""
    found = number(code)
    if found in UPPER_EUS_CODES:
        return Tract.UPPER
    return Tract.LOWER if found in LOWER_EUS_CLASS else None


# --- the enteroscopy classes (DECISIONS D108, D114, D141; classes.py's tables; FINAL-V2 4.3 ENT) -------------------------

# (first code, last code, class): the descriptors' ranges, every catalogue code of the family in exactly one.
ENTEROSCOPY_RANGES: tuple[tuple[int, int, EnteroscopyClass], ...] = (
    (44360, 44373, EnteroscopyClass.JEJUNAL), (44376, 44379, EnteroscopyClass.ILEAL),
    (44380, 44384, EnteroscopyClass.STOMA), (44385, 44386, EnteroscopyClass.POUCH))
# The reach each class needs, over EXTENTS: the jejunum (beyond the second portion, not the ileum); an ileal reach; an
# ileal reach through a stoma; an ileal reach or the pouch. A reach at the duodenum, its bulb or any of its portions, the
# ampulla, the small bowel named only as such, an anastomosis, a stated depth, or anywhere before the duodenum or beyond
# the ileum fits no class (the third and fourth portions too, as v1's "third portion" reach: DECISIONS D204).
ILEAL_REACH: frozenset[Extent] = frozenset({Extent.ILEUM, Extent.TERMINAL_ILEUM, Extent.NEO_TERMINAL_ILEUM})
ENTEROSCOPY_CLASS_REACH: Mapping[EnteroscopyClass, frozenset[Extent]] = MappingProxyType({
    EnteroscopyClass.JEJUNAL: frozenset({Extent.JEJUNUM}), EnteroscopyClass.ILEAL: ILEAL_REACH,
    EnteroscopyClass.STOMA: ILEAL_REACH, EnteroscopyClass.POUCH: ILEAL_REACH | frozenset({Extent.POUCH})})
# The classes that never fit an examination stated incomplete (D43, D56, D72; FINAL-V2 4.3 ENT: "for the deeper
# classes, completion not incomplete").
ENTEROSCOPY_DEEPER: frozenset[EnteroscopyClass] = frozenset({EnteroscopyClass.ILEAL})
# The approach each class needs (FINAL-V2 4.3 ENT: oral for jejunal and ileal, through_stoma, through_pouch): classes.
# CLASS_ROUTE's routes as Approach values (ILEAL oral, STOMA through the stoma, POUCH through the pouch), and the oral
# approach 4.3 asks of the jejunal class too, for which v1's table named no route (v1 read its reach only).
ENTEROSCOPY_CLASS_APPROACH: Mapping[EnteroscopyClass, Approach] = MappingProxyType({
    EnteroscopyClass.JEJUNAL: Approach.ORAL, EnteroscopyClass.ILEAL: Approach.ORAL,
    EnteroscopyClass.STOMA: Approach.THROUGH_STOMA, EnteroscopyClass.POUCH: Approach.THROUGH_POUCH})
# The anatomy entry each route's class needs (classes.ROUTES: the encounter's stoma, and its pouch - D141: the
# SMALL-INTESTINAL pouch, never a gastric pouch or a Roux limb, which 4.3 ENT names as an ileal_pouch entry).
ENTEROSCOPY_CLASS_ANATOMY: Mapping[EnteroscopyClass, AnatomyType] = MappingProxyType({
    EnteroscopyClass.STOMA: AnatomyType.STOMA, EnteroscopyClass.POUCH: AnatomyType.ILEAL_POUCH})


def code_class(code: object) -> EnteroscopyClass | None:
    """classes.code_class: the class of a catalogue code of the enteroscopy family, None for any other code."""
    found = number(code)
    profile = CODES.get(found) if found is not None else None
    if found is None or profile is None or profile.family is not _ENT:
        return None
    return next((name for first, last, name in ENTEROSCOPY_RANGES if first <= found <= last), None)


# --- the colonoscopy's full reach (DECISIONS D38, D44, D57, D63; assess.py; FINAL-V2 4.3 COLFULL) ------------------------

# D38: a colonoscopy examines the entire colon, to the cecum, and may include the terminal ileum or the small intestine
# proximal to an anastomosis: the reach that establishes its extent, over EXTENTS. D44: a reach to an anastomosis
# completes it only where the colon proximal to it is gone - an anastomosis placed on the right colon side (D34); in v2,
# reached_anatomy supported with that subtype (4.3 COLFULL: ileocolic), derived from anatomy.ANASTOMOSIS_PLACE.
COLONOSCOPY_FULL_REACH: frozenset[Extent] = frozenset({
    Extent.CECUM, Extent.APPENDICEAL_ORIFICE, Extent.ILEOCECAL_VALVE, Extent.TERMINAL_ILEUM, Extent.ILEUM,
    Extent.NEO_TERMINAL_ILEUM, Extent.SMALL_BOWEL})
COLONOSCOPY_FULL_ANASTOMOSIS: frozenset[Landmark] = frozenset({Landmark.RIGHT_COLON})
COLONOSCOPY_FULL_SUBTYPES: frozenset[AnastomosisSubtype] = frozenset(
    subtype for subtype, place in ANASTOMOSIS_PLACE.items() if place in COLONOSCOPY_FULL_ANASTOMOSIS)


# --- the lower-GI route table (DECISIONS D328 (1); D310 (1), D312 (5), D324 (5), D325 (2), D327 (1)) -------------------
#
# A billing table (DECISIONS D306 keeps billing tables as code), and the one place a lower-GI endoscopy code's route is
# declared. The rounds before it added the route rules family by family - the colonoscopy through a stoma, then through
# the anus, then the EUS and sigmoidoscopy families, each found by another refutation - so DECISIONS D328 (1) rules the
# table by principle, with an exhaustive check (D324 (2)'s lesson): EVERY lower-GI endoscopy code of the catalogue
# (``lower_gi``, computed from the catalogue's own tables, never from this one) declares two things in one typed row -
# its ROUTE (the approach its endoscope enters by: per anus, through a stoma, through a pouch) and the ANATOMY IT NEEDS
# - and tests/v2/test_r3f_rules.py's completeness test fails for a code with none, which engine/evaluate holds at run
# time. engine/evaluate reads the row: a code is READY only when the record establishes its route and nothing filed
# contradicts the anatomy it needs, read fail-closed (its route rows' docstrings).


@unique
class RouteAnatomy(Enum):
    """The anatomy a lower-GI endoscopy code needs (DECISIONS D328 (1)): a colon to traverse (a colonoscopy through the
    anus); a rectum and sigmoid (a sigmoidoscopy, a proctosigmoidoscopy); a colonic stoma (a colonoscopy through a stoma:
    a colon reached through it); an ileal stoma (an ileoscopy through a stoma); a pouch (an endoscopy of an ileal
    pouch)."""
    COLON = 'colon'
    RECTUM_AND_SIGMOID = 'rectum_and_sigmoid'
    COLONIC_STOMA = 'colonic_stoma'
    ILEAL_STOMA = 'ileal_stoma'
    POUCH = 'pouch'


@dataclass(frozen=True, slots=True)
class LowerRoute:
    """One row of the lower-GI route table (DECISIONS D328 (1)): ``route``, the approach the code's endoscope enters by
    (Approach.TRANSANAL - per anus -, THROUGH_STOMA or THROUGH_POUCH), and ``needs``, the anatomy the code needs."""
    route: Approach
    needs: RouteAnatomy


# The families as DECISIONS D328 (1) names them, each an inclusive range of code numbers with its row; no two overlap,
# and each holds the EUS codes of its family (the colonoscopy's 45391 and 45392, the sigmoidoscopy's 45341 and 45342,
# the colonoscopy through a stoma's 44406 and 44407): the colonoscopy 45378-45398, per anus, a colon to traverse; the
# sigmoidoscopy 45330-45350 and the proctosigmoidoscopy 45300-45327, per anus, a rectum and sigmoid; the colonoscopy
# through a stoma 44388-44408, a colonic stoma; the ileoscopy through a stoma 44380-44384, an ileal stoma; the
# endoscopy of a pouch 44385-44386, through it, a pouch. A range holds every number in it, those the catalogue gives no
# profile included (they are held as unprofiled, route (d), before any row is read).
LOWER_ROUTE_RANGES: tuple[tuple[int, int, LowerRoute], ...] = (
    (45378, 45398, LowerRoute(Approach.TRANSANAL, RouteAnatomy.COLON)),
    (45330, 45350, LowerRoute(Approach.TRANSANAL, RouteAnatomy.RECTUM_AND_SIGMOID)),
    (45300, 45327, LowerRoute(Approach.TRANSANAL, RouteAnatomy.RECTUM_AND_SIGMOID)),
    (44388, 44408, LowerRoute(Approach.THROUGH_STOMA, RouteAnatomy.COLONIC_STOMA)),
    (44380, 44384, LowerRoute(Approach.THROUGH_STOMA, RouteAnatomy.ILEAL_STOMA)),
    (44385, 44386, LowerRoute(Approach.THROUGH_POUCH, RouteAnatomy.POUCH)))
# The table, per code number (computed from the ranges).
LOWER_ROUTES: Mapping[int, LowerRoute] = MappingProxyType({
    code: row for first, last, row in LOWER_ROUTE_RANGES for code in range(first, last + 1)})
# The families whose every code is a lower-GI endoscopy (with LOWER_EUS_CLASS's EUS codes and the enteroscopy classes
# passed through a stoma or a pouch, ENTEROSCOPY_CLASS_ANATOMY's: ``lower_gi``).
LOWER_GI_FAMILIES: frozenset[SessionKind] = frozenset({_COLON, _SIG})


def lower_gi(code: object) -> bool:
    """DECISIONS D328 (1): whether ``code`` is a lower-GI endoscopy code of the catalogue, by principle - a catalogue
    code (CODES) of the colonoscopy or the sigmoidoscopy family, a lower-tract EUS code (LOWER_EUS_CLASS: D43's
    sigmoidoscopic, colonoscopic and stoma classes), or an enteroscopy code whose class passes through a stoma or a
    pouch (ENTEROSCOPY_CLASS_ANATOMY). Computed from the catalogue's own tables, never from LOWER_ROUTES: a lower-GI code
    the catalogue gains needs a row there - the completeness test fails without one, and engine/evaluate holds it with
    the table's own hold. A number with no profile is no catalogue code (route (d) holds it before any row is read)."""
    found = number(code)
    profile = CODES.get(found) if found is not None else None
    if found is None or profile is None:
        return False
    return (profile.family in LOWER_GI_FAMILIES or found in LOWER_EUS_CLASS
            or code_class(code) in ENTEROSCOPY_CLASS_ANATOMY)


def lower_route(code: object) -> LowerRoute | None:
    """DECISIONS D328 (1): the route table's row of ``code`` (its canonical number's), None when it declares none."""
    found = number(code)
    return LOWER_ROUTES.get(found) if found is not None else None


# --- the ruled harmless set: the lower-GI path guard's release set (DECISIONS D330 (1), completed by D336 (1)) -------
#
# Four rounds each found the next post-surgical lower-GI shape a listed arm missed - the enumeration failure in the
# release direction - so DECISIONS D330 (1) inverts the default: after every arm of a route row (engine/evaluate,
# ``path_guard``), a lower-GI code - every row of LOWER_ROUTES - is held with the table's own hold unless EVERY anatomy
# entry of the document is, for that code's route, (i) the entry the route itself uses (the stoma or the pouch the
# session established it entered through) or (ii) a match for a row of this ONE finite typed table for that route family
# (the row's ``needs``). The table is the RELEASE set: a shape it omits costs a hold, never a false READY. Every set below
# is an enumeration of members computed from engine/anatomy's regions and containment (never a word list); each row's
# one-line anatomical reason is in its comment here and in the NOTES (r3h/rules6; r3i/int8 for D336).
#
# DECISIONS D336 (1) completes the construction rule in the release direction: an entry is harmless for a family only
# if EVERY reading it may have lies within a row, where every attribute is read by its widest possible value unless the
# contract CONTROLS it (b). So each row RELEASES ON ONE CONTROLLED CLAIM - ``decided_by``: an anatomy type the contract
# controls (CONTROLLED_TYPES: 3.2.3's type siblings), the organ claim of an entry filed surgically absent (the absence
# form: its claim states that the organ is surgically absent, controlled by its own negation), or a subtype the contract
# controls (CONTROLLED_SUBTYPES: 3.2.3's subtype siblings; a subtype names an anastomosis). A type the contract does not
# control (an anastomosis, a Roux limb, a bypass, another alteration; an absence but by its organ claim) and every member
# of a joins list (no control: an attribute read only to HOLD) never decide a release; a row reads them only to hold: a
# filed organ must lie within ``organs`` and every possible place of each joins member within ``joins``, or the entry is
# no match (engine/evaluate ``harmless_row``). No row releases on joins, so the rows that did (an anastomosis its joins
# name, D330 (1)'s row 7, and the pouch family's row 9) and the row that took any type wholly outside the lower GI tract
# (row 4: it released on an uncontrolled type, and on an empty joins list read as naming nothing) are gone.


@unique
class EntryShape(Enum):
    """The entry shapes of the ruled harmless set (DECISIONS D330 (1), D336 (1)), each released on one controlled claim:
    an organ filed surgically absent (its organ claim, the absence form); an anastomosis of a colon-keeping subtype, of
    the upper tract, or - beside a pouch code - the pouch's own ileoanal or ileorectal join (its subtype); a gastric
    pouch (its type: an alteration of the upper tract, DECISIONS D141); a stoma beside a route established otherwise (its
    type; DECISIONS D310 (1): the route is the established fact)."""
    ABSENT = 'absent'
    ANASTOMOSIS_COLON = 'anastomosis_colon'
    ANASTOMOSIS_UPPER = 'anastomosis_upper'
    ANASTOMOSIS_POUCH = 'anastomosis_pouch'
    UPPER_ALTERATION = 'upper_alteration'
    STOMA = 'stoma'


@dataclass(frozen=True, slots=True)
class Harmless:
    """One row of the ruled harmless set (DECISIONS D330 (1), D336 (1)): ``needs``, the route family (the route table's
    anatomy need: catalogue.LowerRoute.needs); ``shape``; ``decided_by``, the controlled claim the row releases on
    (Attribute.TYPE: a type the contract controls; Attribute.ORGAN: the organ claim of an entry filed surgically absent;
    Attribute.SUBTYPE: a subtype the contract controls) and ``values``, the values of that claim it releases on - every
    value the claim may be must lie within them; and, read only to HOLD, ``organs`` (where a filed organ may lie: each
    possible value; a silent organ files nothing) and ``joins`` (where each possible place of every joins member may
    lie)."""
    needs: RouteAnatomy
    shape: EntryShape
    decided_by: Attribute
    values: frozenset[AnatomyType | AnastomosisSubtype | Landmark]
    organs: frozenset[Landmark]
    joins: frozenset[Landmark]


# What the contract CONTROLS (DECISIONS D336 (1) (b): contract/claims.py's CONTROLS with its sibling tables, 3.2.3), as
# enumerations of members - the engine imports no contract module, so tests/v2/test_r3i_guard.py's P-CONTROLLED census
# pins each equal to the contract's own tables:
# - CONTROLLED_TYPES: the anatomy types whose claim has a contrary control (3.2.3: "ileal_pouch, gastric_pouch, stoma ...
#   the sibling type"); every other type is decided by a single verdict, so it is read only to hold;
# - CONTROLLED_SUBTYPES: the anastomosis subtypes with a sibling control (every pair 3.2.3 lists, both ways) - OTHER and
#   pancreaticojejunal have none (3.2.3 pairs no sibling with them), so they are decided by a single verdict;
# - CONTROLLED_APPROACHES: the approaches with a contrary control (the approach table: oral against a stoma or a pouch)
#   - per anus has none, so the per-anus route is never established through a control (engine/evaluate,
#   ``_anus_route_contradicted``);
# - ABSENCE_TYPE: the type whose organ claim states the absence (the organ's only claim form, controlled by its negation);
# - SUBTYPE_TYPE: the type a subtype names (its claim's form, "This anastomosis is ...").
CONTROLLED_TYPES: frozenset[AnatomyType] = frozenset({AnatomyType.ILEAL_POUCH, AnatomyType.GASTRIC_POUCH,
                                                       AnatomyType.STOMA})
CONTROLLED_SUBTYPES: frozenset[AnastomosisSubtype] = frozenset({
    AnastomosisSubtype.ILEOCOLIC, AnastomosisSubtype.COLOCOLIC, AnastomosisSubtype.COLORECTAL, AnastomosisSubtype.COLOANAL,
    AnastomosisSubtype.ILEORECTAL, AnastomosisSubtype.ILEOANAL, AnastomosisSubtype.GASTROJEJUNAL,
    AnastomosisSubtype.GASTRODUODENAL, AnastomosisSubtype.ESOPHAGOJEJUNAL, AnastomosisSubtype.ESOPHAGOGASTRIC,
    AnastomosisSubtype.HEPATICOJEJUNAL, AnastomosisSubtype.CHOLEDOCHODUODENAL})
CONTROLLED_APPROACHES: frozenset[Approach] = frozenset({Approach.ORAL, Approach.THROUGH_STOMA, Approach.THROUGH_POUCH})
ABSENCE_TYPE: AnatomyType = AnatomyType.SURGICALLY_ABSENT
SUBTYPE_TYPE: AnatomyType = AnatomyType.ANASTOMOSIS
# DECISIONS D345 (1) (L6M-1): A FILED FIELD NAMES ITS SHAPE IN EVERY FIELD AND EVERY READER - the MADE places (the
# surgically made landmarks that are a shape of their own; anatomy.ALTERED less the anastomosis, which a subtype names)
# and the shape each names: an entry whose organ or a joins member may be the stoma may be a stoma, one that may be the
# pouch may be an ileal pouch (the lower tract's pouch). The one exception - a subtype established that itself defines
# the place - is engine/evaluate's (``SUBTYPE_MADE_PLACES``, read from each subtype's own ends).
MADE_PLACE_SHAPES: Mapping[Landmark, AnatomyType] = MappingProxyType({
    Landmark.STOMA: AnatomyType.STOMA, Landmark.POUCH: AnatomyType.ILEAL_POUCH})


# The places, from engine/anatomy's regions and containment:
# - the LOWER GI TRACT's anchors (D330 (1): the anal canal, the rectum, the colon - its cecum, appendiceal orifice and
#   ileocecal valve among its points - and the ileum), and the landmarks naming no placeable organ (UNPLACED, ALTERED:
#   other - which may be the appendix, which has no landmark -, an anastomosis, a stoma, a pouch);
# - OUTSIDE_LOWER_GI: every landmark compatible with none of the anchors (neither one of them, inside one, nor holding
#   one) and naming a placeable organ - the esophagus, the stomach, the duodenum and the ampulla, the jejunum, the bile
#   ducts and the gallbladder, the pancreas, the liver, a lymph node. The small bowel as a whole holds the ileum, so it
#   is not outside; the jejunum is. A landmark the table gains is outside only when it is placed and compatible with no
#   anchor; any other is no member here until classified, so it can only add a hold.
_LOWER_ANCHORS: tuple[Landmark, ...] = (Landmark.ANAL_CANAL, Landmark.RECTUM, Landmark.COLON, Landmark.ILEUM)
NO_PLACED_ORGAN: frozenset[Landmark] = UNPLACED | ALTERED
OUTSIDE_LOWER_GI: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark
    if landmark not in NO_PLACED_ORGAN and not any(compatible(landmark, anchor) for anchor in _LOWER_ANCHORS))
COLON_LANDMARKS: frozenset[Landmark] = frozenset(landmark for landmark in Landmark if region(landmark) is Region.COLON)
# the colon's parts: every colon landmark but the colon as a whole (a segment, a side, a point within or between them)
COLON_PARTS: frozenset[Landmark] = COLON_LANDMARKS - frozenset({Landmark.COLON})
RECTUM_LANDMARKS: frozenset[Landmark] = frozenset(landmark for landmark in Landmark if region(landmark) is Region.RECTUM)
ANUS_LANDMARKS: frozenset[Landmark] = frozenset(landmark for landmark in Landmark if region(landmark) is Region.ANUS)
SMALL_BOWEL_LANDMARKS: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark if region(landmark) is Region.SMALL_BOWEL)
# the parts of the ileum (its terminal and neo-terminal ileum): an absence of one leaves an ileum for a stoma or a pouch
ILEAL_PARTS: frozenset[Landmark] = frozenset(landmark for landmark in Landmark if contains(Landmark.ILEUM, landmark))
# The anastomosis subtypes by what they join (enumerations of members, each pinned to partition AnastomosisSubtype with
# ILEUM_BELOW_SUBTYPES and OTHER): those that keep a colon (ileocolic, colocolic, colorectal, coloanal); those of the
# upper tract, the bile duct and the pancreas; those that join the ileum below the colon (ileorectal, ileoanal), the
# pouch's own join (an ileal pouch is the ileum joined to the anus or the rectum); OTHER joins another pair, so it is in
# no subtype row (and the contract gives it no control). A subtype the enumeration gains is in no row until classified.
COLON_KEEPING_SUBTYPES: frozenset[AnastomosisSubtype] = frozenset({
    AnastomosisSubtype.ILEOCOLIC, AnastomosisSubtype.COLOCOLIC, AnastomosisSubtype.COLORECTAL,
    AnastomosisSubtype.COLOANAL})
UPPER_SUBTYPES: frozenset[AnastomosisSubtype] = frozenset({
    AnastomosisSubtype.GASTROJEJUNAL, AnastomosisSubtype.GASTRODUODENAL, AnastomosisSubtype.ESOPHAGOJEJUNAL,
    AnastomosisSubtype.ESOPHAGOGASTRIC, AnastomosisSubtype.HEPATICOJEJUNAL, AnastomosisSubtype.CHOLEDOCHODUODENAL,
    AnastomosisSubtype.PANCREATICOJEJUNAL})
ILEUM_BELOW_SUBTYPES: frozenset[AnastomosisSubtype] = frozenset({
    AnastomosisSubtype.ILEORECTAL, AnastomosisSubtype.ILEOANAL})
_LANDMARKS: frozenset[Landmark] = frozenset(Landmark)
# Where each joins member of a matching entry may lie (read only to HOLD - no row releases on joins): an anastomosis that
# keeps a colon the small bowel (an ileocolic join), the colon, the rectum, the anal canal or a pouch - a colonic
# J-pouch, its subtype filed colon-keeping (R5R-6); the pouch's own join the small bowel, the rectum, the anal canal or
# the pouch; an upper anastomosis or a gastric pouch an organ outside the lower GI tract or a pouch (a gastric pouch's
# own end). engine/evaluate reads each member of a subtype's row within that subtype's own ends too (SUBTYPE_ENDS).
_COLON_JOINS: frozenset[Landmark] = (SMALL_BOWEL_LANDMARKS | COLON_LANDMARKS | RECTUM_LANDMARKS | ANUS_LANDMARKS
                                     | frozenset({Landmark.POUCH}))
_POUCH_JOINS: frozenset[Landmark] = (SMALL_BOWEL_LANDMARKS | RECTUM_LANDMARKS | ANUS_LANDMARKS
                                     | frozenset({Landmark.POUCH}))
_UPPER_JOINS: frozenset[Landmark] = OUTSIDE_LOWER_GI | frozenset({Landmark.POUCH})
# The organs each route family's ABSENT row releases (the reasons: NOTES, r3h/rules6): every family an organ outside the
# lower GI tract, an organ the table does not name (other: the appendix among them) and the rectum (D328 (1): there is
# no rectum-absent arm); a colon to traverse and a rectum and sigmoid a part of the colon (a segment, a side, a point:
# the colon as a whole, or the entries together covering it, is no part - DECISIONS D327 (1)) and the small bowel; a
# colonic stoma those and the anal canal (after an abdominoperineal resection the colostomy is the route); an ileal
# stoma and a pouch the whole colon (their own anatomy after a colectomy) and the ileum's parts, the ileal stoma the anal
# canal too. Never the anal canal for a per-anus code (R5R-2) or a pouch, never the ileum as a whole beside an ileal
# stoma or a pouch.
_ABSENT_ORGANS: Mapping[RouteAnatomy, frozenset[Landmark]] = MappingProxyType({
    RouteAnatomy.COLON: OUTSIDE_LOWER_GI | UNPLACED | COLON_PARTS | RECTUM_LANDMARKS | SMALL_BOWEL_LANDMARKS,
    RouteAnatomy.RECTUM_AND_SIGMOID: OUTSIDE_LOWER_GI | UNPLACED | COLON_PARTS | RECTUM_LANDMARKS | SMALL_BOWEL_LANDMARKS,
    RouteAnatomy.COLONIC_STOMA: (OUTSIDE_LOWER_GI | UNPLACED | COLON_PARTS | RECTUM_LANDMARKS | SMALL_BOWEL_LANDMARKS
                                 | ANUS_LANDMARKS),
    RouteAnatomy.ILEAL_STOMA: (OUTSIDE_LOWER_GI | UNPLACED | COLON_LANDMARKS | RECTUM_LANDMARKS | ANUS_LANDMARKS
                               | ILEAL_PARTS),
    RouteAnatomy.POUCH: OUTSIDE_LOWER_GI | UNPLACED | COLON_LANDMARKS | RECTUM_LANDMARKS | ILEAL_PARTS,
})


def _harmless_rows(needs: RouteAnatomy) -> tuple[Harmless, ...]:
    """The rows of one route family (DECISIONS D330 (1), D336 (1); each row's reason in its comment and the NOTES)."""
    _S = EntryShape
    _TYPE, _ORGAN, _SUBTYPE = Attribute.TYPE, Attribute.ORGAN, Attribute.SUBTYPE
    absent = _ABSENT_ORGANS[needs]
    rows = (
        # an organ filed surgically absent that the family's route and need do not pass, released on its organ claim
        # (the absence form: "The <organ> is surgically absent", controlled by its negation) - its subtype silent (a
        # subtype names an anastomosis: a filed one contradicts the absence) and, DECISIONS D342 (1) (b), its joins list
        # empty: a filed joins list names an anastomosis, about which the absence's organ claim decides nothing (L9-2,
        # L6R-3: int8 read a list filed on an absence as places of the absence, within the same organs)
        Harmless(needs, _S.ABSENT, _ORGAN, absent, absent, frozenset()),
        # an anastomosis of the upper tract or the bile duct (its subtype, controlled): it joins no lower-GI organ - the
        # pancreaticojejunal subtype has no control (3.2.3 pairs it with no sibling), so it never decides a release
        Harmless(needs, _S.ANASTOMOSIS_UPPER, _SUBTYPE, UPPER_SUBTYPES & CONTROLLED_SUBTYPES, _LANDMARKS, _UPPER_JOINS),
        # a gastric pouch: an alteration of the upper tract by its type (controlled: its sibling is the ileal pouch;
        # DECISIONS D141), a filed organ outside the lower GI tract (an upper-tract type at a lower-GI organ, or at a
        # landmark naming no placed organ, is a contradictory filing: D336 (1) (e)). A Roux limb's type has no control,
        # so it never decides a release
        Harmless(needs, _S.UPPER_ALTERATION, _TYPE, frozenset({AnatomyType.GASTRIC_POUCH}), OUTSIDE_LOWER_GI,
                 _UPPER_JOINS),
        # a stoma (its type, controlled) beside the route its code's row establishes otherwise: through a stoma the
        # stoma the route uses (route_entries) or the colonic or ileal route its arms read, through a pouch the pouch -
        # DECISIONS D310 (1): the route is the established fact, and a diverting stoma is no part of it. Per anus the
        # route is never established through a control (the contract gives per anus no contrary, D336 (1) (b)), so the
        # guard's own per-anus clause holds any entry that may be a stoma (engine/evaluate ``_anus_route_contradicted``).
        # Its organ is never read here: a stoma's organ is never claimed or askable (D330 (d))
        Harmless(needs, _S.STOMA, _TYPE, frozenset({AnatomyType.STOMA}), _LANDMARKS, _LANDMARKS),
    )
    if needs is RouteAnatomy.POUCH:
        return rows + (
            # the pouch's own join (its subtype, controlled): an ileal pouch is the ileum joined to the anus or the rectum
            Harmless(needs, _S.ANASTOMOSIS_POUCH, _SUBTYPE, ILEUM_BELOW_SUBTYPES, _LANDMARKS, _POUCH_JOINS),
        )
    return rows + (
        # an anastomosis that keeps a colon (its subtype, controlled: a right hemicolectomy's ileocolic join, a
        # segmental colectomy's colocolic, an anterior resection's colorectal or coloanal, a colonic J-pouch's)
        Harmless(needs, _S.ANASTOMOSIS_COLON, _SUBTYPE, COLON_KEEPING_SUBTYPES, _LANDMARKS, _COLON_JOINS),
    )


# THE TABLE: the route families (the route table's needs) -> their rows, in RouteAnatomy's order. One finite typed table;
# tests/v2/test_r3g_rules.py's and tests/v2/test_r3i_guard.py's census and completeness tests pin it.
HARMLESS: Mapping[RouteAnatomy, tuple[Harmless, ...]] = MappingProxyType({
    needs: _harmless_rows(needs) for needs in RouteAnatomy})
# DECISIONS D342 (1) (c), THE ROUTE'S OWN ENTRY (D336 (1) (e)'s unbuilt part: L4P8-2, L9-3, the final check's finding
# 2): the entry a through-stoma or a pouch row's route itself uses is exempt from the harmless set (engine/evaluate
# ``route_entries``), and is read in the hold direction like every other entry instead - its established type gives the
# route, and its organ, subtype and joins must lie within that type's own anatomy, or the route is not certain
# (``route_own_entry_contradicted``). One row per through family, from engine/anatomy's regions and containment:
# - a colonic stoma's (the colonoscopy through a stoma): a stoma of the lower tract - the colon's and the ileum's places
#   (every landmark compatible with the colon or the ileum: evaluate.LOWER_STOMA_ORGANS, which colonic_route_stoma_
#   contradicted reads), its joins the same; no subtype (a stoma names no join);
# - an ileal stoma's (the ileoscopy through a stoma): the ileum's places (compatible with the ileum: evaluate.
#   ILEAL_PLACES, which ileal_stoma_contradicted reads), its joins the same; no subtype;
# - an ileal pouch's (the endoscopy of a pouch): the ileum's places and the pouch's own landmark; its own join, the
#   ileum joined to the rectum or the anus (ILEUM_BELOW_SUBTYPES); its joins the pouch family's own (the small bowel, the
#   rectum, the anal canal, the pouch).
# A landmark naming no placed organ (other, an anastomosis, a stoma) is none of a stoma's places, so a stoma filed at one
# holds, as colonic_route_stoma_contradicted holds it; tests/v2/test_r3m_guard.py pins each row.
@dataclass(frozen=True, slots=True)
class OwnAnatomy:
    """THE ROUTE'S OWN ENTRY's anatomy for one through family (DECISIONS D342 (1) (c)): ``needs``, the route family;
    ``type``, the controlled type the route passes (a stoma, an ileal pouch); and where the entry's filed fields may lie -
    ``organs``, ``subtypes`` (every value a filed subtype may be), ``joins`` (every place of each member)."""
    needs: RouteAnatomy
    type: AnatomyType
    organs: frozenset[Landmark]
    subtypes: frozenset[AnastomosisSubtype]
    joins: frozenset[Landmark]


LOWER_STOMA_PLACES: frozenset[Landmark] = frozenset(
    landmark for landmark in Landmark if compatible(landmark, Landmark.COLON) or compatible(landmark, Landmark.ILEUM))
ILEAL_PLACES: frozenset[Landmark] = frozenset(landmark for landmark in Landmark if compatible(landmark, Landmark.ILEUM))
ROUTE_OWN: Mapping[RouteAnatomy, OwnAnatomy] = MappingProxyType({
    RouteAnatomy.COLONIC_STOMA: OwnAnatomy(RouteAnatomy.COLONIC_STOMA, AnatomyType.STOMA, LOWER_STOMA_PLACES,
                                           frozenset(), LOWER_STOMA_PLACES),
    RouteAnatomy.ILEAL_STOMA: OwnAnatomy(RouteAnatomy.ILEAL_STOMA, AnatomyType.STOMA, ILEAL_PLACES, frozenset(),
                                         ILEAL_PLACES),
    RouteAnatomy.POUCH: OwnAnatomy(RouteAnatomy.POUCH, AnatomyType.ILEAL_POUCH, ILEAL_PLACES | {Landmark.POUCH},
                                   ILEUM_BELOW_SUBTYPES, _POUCH_JOINS),
})
# The family rules beside the rows, each an enumeration of route families:
# - HARMLESS_WHOLE_COLON: the families beside which the colon may be gone as a whole - an ileal stoma's and a pouch's
#   own anatomy after a colectomy. For every other family the colon filed absent as a whole is no harmless shape, nor are
#   the entries that may together cover it (DECISIONS D327 (1): a side counts as its segments), and an anastomosis that
#   may join the ileum below the colon leaves no colon;
# - HARMLESS_ILEUM_BELOW: the families beside which an entry that may join the ileum below the colon (its subtype or its
#   joins: evaluate.ileum_below_colon_possible) is harmless - the pouch's, whose own join it is. For every other family
#   it matches no row: no colon to traverse, no rectum and sigmoid, and beside an ileal stoma a pouch its efferent limb
#   may reach.
HARMLESS_WHOLE_COLON: frozenset[RouteAnatomy] = frozenset({RouteAnatomy.ILEAL_STOMA, RouteAnatomy.POUCH})
HARMLESS_ILEUM_BELOW: frozenset[RouteAnatomy] = frozenset({RouteAnatomy.POUCH})


# --- how a proposed code links to acts (FINAL C7 as ADJUDICATION C-6 amends it; FINAL-V2 4.4) ---------------------------


@dataclass(frozen=True, slots=True)
class CodeLink:
    """How a proposed code links to acts (mapping.CodeLink; FINAL C7, C-1, C-6). ``code``: the proposal's code.
    ``route``: (a) catalogue, (b) unreconciled, (d) none. ``family``: the family the code routes to. ``kinds``: K(C), the
    catalogue kinds of its candidates (its covers; the examination for a base code with none). ``session``: the
    examination kind of the session it belongs to (Kind.EXAMINATION in an endoscopic family, else None). ``acts``: the
    kinds besides the examination, each needing a supporting act of its own (C-1). ``regions``: route (b)'s regions. On
    route none every tuple is empty and ``reason`` says why. ``supported``: the routed family's gi.profiles flag;
    ``support``: its catalogue support level (None with no entry). ``defining``: D(C) (D27), the only kinds that match
    the code where D27 narrows it, () otherwise."""
    code: str
    route: LinkRoute
    family: SessionKind
    kinds: tuple[Kind, ...] = ()
    session: Kind | None = None
    acts: tuple[Kind, ...] = ()
    base: bool = False
    addon: bool = False
    technique: TechniqueClass | None = None
    includes: tuple[SessionKind, ...] = ()
    regions: tuple[Region, ...] = ()
    supported: bool = False
    support: SupportLevel | None = None
    reason: NoRouteReason | None = None
    defining: tuple[Kind, ...] = ()

    @property
    def linked(self) -> bool:
        return self.route is not LinkRoute.NONE


def _link(code: str, codes: Mapping[int, Profile]) -> CodeLink:
    """mapping.code_link over the profile table ``codes``: (a) the catalogue, (b) an unreconciled act, or (d) none."""
    routed = family_for_code(code)
    supported, support = routed in PROFILE_SUPPORTED, FAMILY_SUPPORT.get(routed)
    found = number(code)
    profile = codes.get(found) if found is not None else None
    if found is not None and profile is not None:
        if profile.family is not routed:
            return CodeLink(code, LinkRoute.NONE, routed, supported=supported, support=support,
                            reason=NoRouteReason.FAMILY_MISMATCH)
        session = Kind.EXAMINATION if routed in ENDOSCOPIC_FAMILIES else None
        kinds = profile.covers or ((session,) if profile.base and session is not None else ())
        return CodeLink(code, LinkRoute.CATALOGUE, routed, kinds=kinds, session=session,
                        acts=tuple(kind for kind in kinds if kind is not Kind.EXAMINATION), base=profile.base,
                        addon=profile.addon, technique=profile.technique, includes=profile.includes,
                        supported=supported, support=support, defining=DEFINING.get(found, ()))
    acts = UNRECONCILED_ACTS.get(found, ()) if found is not None else ()
    if acts and found is not None:
        return CodeLink(code, LinkRoute.UNRECONCILED, routed, kinds=acts, acts=acts,
                        regions=UNRECONCILED_REGIONS.get(found, ()), supported=supported, support=support)
    return CodeLink(code, LinkRoute.NONE, routed, supported=supported, support=support,
                    reason=NoRouteReason.UNPROFILED)


# code_link as a pure table: every catalogue code's link, and route (b)'s.
CODE_LINKS: Mapping[int, CodeLink] = MappingProxyType({
    code: _link(str(code), CODES) for code in (*CODES, *UNRECONCILED_ACTS)})


def code_link(code: str) -> CodeLink:
    """mapping.code_link: the link of ``code`` - CODE_LINKS' for a catalogue or route (b) code, else route none
    (unprofiled: "outside CPT Studio's coding profiles; review required", never READY, C-6)."""
    found = number(code)
    link = CODE_LINKS.get(found) if found is not None else None
    return link if link is not None else _link(code, CODES)


def requirements(link: CodeLink) -> tuple[tuple[Kind, ...], ...]:
    """events.requirements: the code's requirement groups, each needing a supporting act of one of its kinds (C-1): on
    route (b) its kinds; for a code whose kinds hold the examination besides acts (an EUS code), one group per act (the
    examination is the session); otherwise one group, its defining kinds where D27 narrows it, else its kinds. () on
    route none."""
    if not link.linked:
        return ()
    if link.route is LinkRoute.UNRECONCILED:
        return (link.kinds,)
    if link.acts and Kind.EXAMINATION in link.kinds:
        return tuple((kind,) for kind in link.acts)
    kinds = link.defining or link.kinds
    return (kinds,) if kinds else ()


def accounted(link: CodeLink) -> tuple[Kind, ...]:
    """events.accounted: the kinds a code accounts for - its defining kinds where D27 narrows it, else the acts besides
    the examination, else its kinds."""
    return link.defining or link.acts or link.kinds


def examination_code(link: CodeLink) -> bool:
    """events.examination_code: whether the code accounts for the examination itself (a base code, an examination-only
    EUS code), so an examination begun and not completed supports it, with the 52/53 consideration (FINAL-V2 4.3 row 2,
    ATT)."""
    return link.base or (bool(link.kinds) and all(kind is Kind.EXAMINATION for kind in link.kinds))


def recognised_only(link: CodeLink) -> bool:
    """mapping.recognised_only (DECISIONS D80): whether ``link`` is a code on route (a) of a family CPT Studio
    recognises and lists for review but does not assess - its catalogue support level is not supported, or gi.profiles
    marks the family not supported (either one marks it: fail-closed). Today exactly gi.sedation's 99152 and 99153."""
    return link.route is LinkRoute.CATALOGUE and not (link.supported and link.support is SupportLevel.SUPPORTED)


def read_under(family: SessionKind, kind: Kind, place: Place | None) -> SessionKind | None:
    """mapping.read_under (catalogue.READ_UNDER): the family an act of ``kind`` of ``family`` at ``place`` is read under,
    None when no rule applies or the place lies in none of the rule's regions."""
    rule = READ_UNDER.get((family, kind))
    if rule is None or not in_regions(place, rule[1]):
        return None
    return rule[0]
