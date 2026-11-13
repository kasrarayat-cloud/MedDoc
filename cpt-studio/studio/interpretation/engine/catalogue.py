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
tables are copied here.

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

from studio.interpretation.contract.types import (AnastomosisSubtype, AnatomyType, Approach, Device, Extent, Kind,
                                                  Landmark, Purpose, SessionKind, Station, Tract)
from studio.interpretation.engine.anatomy import ANASTOMOSIS_PLACE, Place, Region, in_regions


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
