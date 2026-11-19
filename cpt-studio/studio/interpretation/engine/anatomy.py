"""The anatomy chain of design v2 (docs/gemini-migration/FINAL-V2.md, step 1e of 8.1): where a place lies and how two
places relate - containment, regions, compatible and disjoint - over the contract's enumeration values, and the place an
anastomosis of each type takes. Pure tables and the functions v1 read over them, nothing else.

**Ported from v1, proved equal to v1's by value** (FINAL-V2 5.0: "the catalogue's vocabulary tables over enumeration
values, each proved equal to v1's by value"; tests/v2/test_catalogue_parity.py computes v1's values in the test):
- lexicon._CONTAINS and its transitive closure lexicon.CONTAINS ("generous on purpose: a containment missing here would
  make two places disjoint and so manufacture a difference", contract 6.3), and lexicon.contains, compatible and
  disjoint over them, with lexicon.UNPLACED_LANDMARKS (less not_stated, which LANDMARKS2 drops) and
  lexicon.ALTERED_LANDMARKS (the surgically made places, never disjoint from anything);
- mapping.REGION_OF (C8: studio.gi.services.REGION_OF's regions, keyed by the landmarks) with mapping.region and
  mapping.in_regions; a region is a Region member here, and "no region" (v1's '') is None;
- the enumeration-valued part of lexicon.ANASTOMOSIS_TYPES (DECISIONS D34: the side of the tract an anastomosis of a
  type joins): the place of each AnastomosisSubtype whose value is one of v1's type words. The table's other type words
  are spellings of those same types (ileocolonic, ileo colic, colo rectal, oesophagogastric, ...): surface forms, which
  the new path never reads (FINAL-V2 5.1 rows 50-52: D34's place rule over anatomy.subtype), so they are not here.

**The two values LANDMARKS2 adds** (FINAL-V2 1.4), third_portion_duodenum and fourth_portion_duodenum, have no v1 value
to equal. Containment places them under duodenum, as 1.4 states (and so under small_bowel); neither contains anything.
Their region is the duodenum's, as every duodenal landmark's but the ampulla's is (v1's second_portion_duodenum, which
took "third portion" words in v1's lexicon, is in the duodenum region too). DECISIONS D204 rules this placement (and
engine/catalogue.py's class tables follow it). The test pins both.

**A place** is a Landmark (an act's or a lesion's places, an anatomy entry's organ and joins: LANDMARKS2), an Extent (a
session's reached and device_reached points: EXTENTS) or a Station (a session's stations): every function here takes
any of the three and reads an Extent or a Station as the Landmark of the same value. stated_depth ("to 40 cm", an
extent stated without a landmark) is no landmark: it lies in no region, contains and is contained by nothing, is never
disjoint from anything, and is compatible only with itself. Tables are keyed by Landmark; a caller never compares an
Extent with a Landmark directly (plain Enums: Extent.CECUM != Landmark.CECUM), it asks a function here.

**The text-free boundary** (FINAL-V2 4.1, 5.7 measure 4): this module imports the standard library and contract/types.py
only - no retired v1 module (5.0), none of contract's text modules - holds no word, phrase or surface-form list (every
module-level collection holds enumeration members), and reads no text: no value here is ever compared with a document.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import AnastomosisSubtype, Extent, Landmark, Station


@unique
class Region(Enum):
    """The regions a landmark lies in (mapping.REGION_OF's values, v1's copy of studio.gi.services.REGION_OF's): the
    luminal tract's segments, and the organs and nodes beside it. CPT Studio's coding vocabulary, read by the catalogue's
    region rules (route (b)'s regions, READ_UNDER, the EUS tract, 43240's apart regions, K3's FAMILY_REACH: DECISIONS
    D192); never a word of a document."""
    ESOPHAGUS = 'esophagus'
    STOMACH = 'stomach'
    DUODENUM = 'duodenum'
    BILIARY = 'biliary'
    SMALL_BOWEL = 'small_bowel'
    COLON = 'colon'
    RECTUM = 'rectum'
    ANUS = 'anus'
    PANCREAS = 'pancreas'
    LIVER = 'liver'
    NODE = 'node'


# A place, as the functions below take it (module docstring).
Place = Landmark | Extent | Station

# --- regions (mapping.REGION_OF, C8) ----------------------------------------------------------------------------------

# Every landmark -> its region, None where v1 places it in no region (v1's ''): other, and the surgically made places
# whose position in the tract cannot be told (an anastomosis, a stoma, a pouch). In Landmark's order; the two new
# duodenal portions in the duodenum (module docstring).
REGION_OF: Mapping[Landmark, Region | None] = MappingProxyType({
    Landmark.ESOPHAGUS: Region.ESOPHAGUS, Landmark.PROXIMAL_ESOPHAGUS: Region.ESOPHAGUS,
    Landmark.MID_ESOPHAGUS: Region.ESOPHAGUS, Landmark.DISTAL_ESOPHAGUS: Region.ESOPHAGUS,
    Landmark.GASTROESOPHAGEAL_JUNCTION: Region.ESOPHAGUS,
    Landmark.STOMACH: Region.STOMACH, Landmark.GASTRIC_CARDIA: Region.STOMACH, Landmark.GASTRIC_FUNDUS: Region.STOMACH,
    Landmark.GASTRIC_BODY: Region.STOMACH, Landmark.GASTRIC_ANTRUM: Region.STOMACH, Landmark.PYLORUS: Region.STOMACH,
    Landmark.DUODENUM: Region.DUODENUM, Landmark.DUODENAL_BULB: Region.DUODENUM,
    Landmark.SECOND_PORTION_DUODENUM: Region.DUODENUM, Landmark.THIRD_PORTION_DUODENUM: Region.DUODENUM,
    Landmark.FOURTH_PORTION_DUODENUM: Region.DUODENUM,
    Landmark.AMPULLA: Region.BILIARY,
    Landmark.JEJUNUM: Region.SMALL_BOWEL, Landmark.ILEUM: Region.SMALL_BOWEL, Landmark.TERMINAL_ILEUM: Region.SMALL_BOWEL,
    Landmark.NEO_TERMINAL_ILEUM: Region.SMALL_BOWEL, Landmark.SMALL_BOWEL: Region.SMALL_BOWEL,
    Landmark.COLON: Region.COLON, Landmark.RIGHT_COLON: Region.COLON, Landmark.LEFT_COLON: Region.COLON,
    Landmark.PROXIMAL_COLON: Region.COLON, Landmark.DISTAL_COLON: Region.COLON, Landmark.CECUM: Region.COLON,
    Landmark.APPENDICEAL_ORIFICE: Region.COLON, Landmark.ILEOCECAL_VALVE: Region.COLON,
    Landmark.ASCENDING_COLON: Region.COLON, Landmark.HEPATIC_FLEXURE: Region.COLON,
    Landmark.TRANSVERSE_COLON: Region.COLON, Landmark.SPLENIC_FLEXURE: Region.COLON,
    Landmark.DESCENDING_COLON: Region.COLON, Landmark.SIGMOID_COLON: Region.COLON, Landmark.RECTOSIGMOID: Region.COLON,
    Landmark.RECTUM: Region.RECTUM, Landmark.ANAL_CANAL: Region.ANUS,
    Landmark.ANASTOMOSIS: None, Landmark.STOMA: None, Landmark.POUCH: None,
    Landmark.COMMON_BILE_DUCT: Region.BILIARY, Landmark.BILE_DUCT: Region.BILIARY,
    Landmark.PANCREATIC_DUCT: Region.PANCREAS, Landmark.PANCREAS: Region.PANCREAS,
    Landmark.GALLBLADDER: Region.BILIARY, Landmark.LIVER: Region.LIVER, Landmark.LYMPH_NODE: Region.NODE,
    Landmark.OTHER: None,
})

# --- containment (lexicon._CONTAINS and CONTAINS; contract appendix B, ADJUDICATION C-15) -----------------------------

# What each landmark contains directly; CONTAINS closes it transitively. v1's table, with LANDMARKS2's two duodenal
# portions under the duodenum (FINAL-V2 1.4; DECISIONS D204).
_CONTAINS: Mapping[Landmark, tuple[Landmark, ...]] = MappingProxyType({
    Landmark.ESOPHAGUS: (Landmark.PROXIMAL_ESOPHAGUS, Landmark.MID_ESOPHAGUS, Landmark.DISTAL_ESOPHAGUS,
                         Landmark.GASTROESOPHAGEAL_JUNCTION),
    Landmark.DISTAL_ESOPHAGUS: (Landmark.GASTROESOPHAGEAL_JUNCTION,),
    Landmark.STOMACH: (Landmark.GASTRIC_CARDIA, Landmark.GASTRIC_FUNDUS, Landmark.GASTRIC_BODY, Landmark.GASTRIC_ANTRUM,
                       Landmark.PYLORUS, Landmark.GASTROESOPHAGEAL_JUNCTION),
    Landmark.SMALL_BOWEL: (Landmark.DUODENUM, Landmark.JEJUNUM, Landmark.ILEUM),
    Landmark.DUODENUM: (Landmark.DUODENAL_BULB, Landmark.SECOND_PORTION_DUODENUM, Landmark.THIRD_PORTION_DUODENUM,
                        Landmark.FOURTH_PORTION_DUODENUM, Landmark.AMPULLA),
    Landmark.SECOND_PORTION_DUODENUM: (Landmark.AMPULLA,),
    Landmark.ILEUM: (Landmark.TERMINAL_ILEUM, Landmark.NEO_TERMINAL_ILEUM),
    Landmark.COLON: (Landmark.RIGHT_COLON, Landmark.LEFT_COLON, Landmark.PROXIMAL_COLON, Landmark.DISTAL_COLON,
                     Landmark.CECUM, Landmark.APPENDICEAL_ORIFICE, Landmark.ILEOCECAL_VALVE, Landmark.ASCENDING_COLON,
                     Landmark.HEPATIC_FLEXURE, Landmark.TRANSVERSE_COLON, Landmark.SPLENIC_FLEXURE,
                     Landmark.DESCENDING_COLON, Landmark.SIGMOID_COLON, Landmark.RECTOSIGMOID),
    Landmark.RIGHT_COLON: (Landmark.CECUM, Landmark.APPENDICEAL_ORIFICE, Landmark.ILEOCECAL_VALVE,
                           Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE),
    Landmark.LEFT_COLON: (Landmark.SPLENIC_FLEXURE, Landmark.DESCENDING_COLON, Landmark.SIGMOID_COLON,
                          Landmark.RECTOSIGMOID),
    Landmark.PROXIMAL_COLON: (Landmark.RIGHT_COLON, Landmark.CECUM, Landmark.APPENDICEAL_ORIFICE,
                              Landmark.ILEOCECAL_VALVE, Landmark.ASCENDING_COLON, Landmark.HEPATIC_FLEXURE,
                              Landmark.TRANSVERSE_COLON),
    Landmark.DISTAL_COLON: (Landmark.LEFT_COLON, Landmark.SPLENIC_FLEXURE, Landmark.DESCENDING_COLON,
                            Landmark.SIGMOID_COLON, Landmark.RECTOSIGMOID),
    Landmark.CECUM: (Landmark.APPENDICEAL_ORIFICE, Landmark.ILEOCECAL_VALVE),
    Landmark.BILE_DUCT: (Landmark.COMMON_BILE_DUCT,),
    Landmark.PANCREAS: (Landmark.PANCREATIC_DUCT,),
})


def _closure(table: Mapping[Landmark, tuple[Landmark, ...]]) -> dict[Landmark, frozenset[Landmark]]:
    """lexicon._closure over Landmark: every landmark -> every landmark it contains, transitively. ValueError on a cycle."""
    closed: dict[Landmark, frozenset[Landmark]] = {}

    def inside(name: Landmark, path: tuple[Landmark, ...]) -> frozenset[Landmark]:
        if name in closed:
            return closed[name]
        if name in path:
            raise ValueError(f'The landmark containment has a cycle through {name}.')
        found: set[Landmark] = set()
        for child in table.get(name, ()):
            found.add(child)
            found |= inside(child, path + (name,))
        closed[name] = frozenset(found)
        return closed[name]

    for landmark in Landmark:
        inside(landmark, ())
    return closed


CONTAINS: Mapping[Landmark, frozenset[Landmark]] = MappingProxyType(_closure(_CONTAINS))

# Places with no placement of their own: 'other' (lexicon.UNPLACED_LANDMARKS less not_stated, which LANDMARKS2 drops).
UNPLACED: frozenset[Landmark] = frozenset({Landmark.OTHER})
# Surgically made places whose position in the tract cannot be told (lexicon.ALTERED_LANDMARKS): never disjoint from
# anything, so a difference of site is never manufactured from them (contract 6.3).
ALTERED: frozenset[Landmark] = frozenset({Landmark.ANASTOMOSIS, Landmark.STOMA, Landmark.POUCH})

# --- a place of any of the three enumerations, read as its landmark ---------------------------------------------------

# Every Landmark, Extent and Station member -> the Landmark of the same value; stated_depth has none (module docstring).
_LANDMARK_OF: Mapping[Place, Landmark] = MappingProxyType({
    **{landmark: landmark for landmark in Landmark},
    **{extent: Landmark(extent.value) for extent in Extent if extent is not Extent.STATED_DEPTH},
    **{station: Landmark(station.value) for station in Station},
})


def landmark_of(place: Place | None) -> Landmark | None:
    """The Landmark ``place`` is: itself, or the Landmark of an Extent's or a Station's value; None for stated_depth, for
    None and for anything that is no place."""
    return _LANDMARK_OF.get(place) if place is not None else None


def region(place: Place | None) -> Region | None:
    """mapping.region: the region of ``place`` (None for none: other, a surgically made place, stated_depth, None)."""
    landmark = landmark_of(place)
    return REGION_OF[landmark] if landmark is not None else None


def in_regions(place: Place | None, regions: Iterable[Region]) -> bool:
    """mapping.in_regions: whether ``place`` lies in one of ``regions`` (route (b)'s regions, READ_UNDER's regions)."""
    found = region(place)
    return found is not None and found in frozenset(regions)


def contains(outer: Place | None, inner: Place | None) -> bool:
    """lexicon.contains: whether ``outer`` contains ``inner`` (strictly; transitively)."""
    first, second = landmark_of(outer), landmark_of(inner)
    return first is not None and second is not None and second in CONTAINS[first]


def compatible(first: Place, second: Place) -> bool:
    """lexicon.compatible: whether two places are one place or one contains the other. stated_depth is compatible only
    with itself."""
    one, other = landmark_of(first), landmark_of(second)
    if one is None or other is None:
        return first is second
    return one is other or _nested(one, other)


def _nested(one: Landmark, other: Landmark) -> bool:
    """Whether either of two landmarks contains the other (compatible's containment arm)."""
    return other in CONTAINS[one] or one in CONTAINS[other]


def disjoint(first: Place, second: Place) -> bool:
    """lexicon.disjoint: whether two places are established as different places (contract 6.3): both placed (neither
    other, a surgically made place nor stated_depth), neither containing the other, and nothing contained by both."""
    one, other = landmark_of(first), landmark_of(second)
    unknown = UNPLACED | ALTERED
    if one is None or other is None or one in unknown or other in unknown or one is other or _nested(one, other):
        return False
    return not (CONTAINS[one] & CONTAINS[other])


# --- the place an anastomosis of a type takes (DECISIONS D34; lexicon.ANASTOMOSIS_TYPES' enumeration-valued part) ------

# AnastomosisSubtype -> the side of the tract it joins, for the subtypes whose value is one of v1's type words: an
# ileocolic one the right colon side; a colorectal, coloanal or ileorectal one the rectum; a gastrojejunal one the
# stomach side; an esophagojejunal or esophagogastric one the esophagus side. Every other subtype (colocolic, ileoanal,
# gastroduodenal, hepaticojejunal, choledochoduodenal, pancreaticojejunal, other) names no place, as in v1.
ANASTOMOSIS_PLACE: Mapping[AnastomosisSubtype, Landmark] = MappingProxyType({
    AnastomosisSubtype.ILEOCOLIC: Landmark.RIGHT_COLON,
    AnastomosisSubtype.COLORECTAL: Landmark.RECTUM,
    AnastomosisSubtype.COLOANAL: Landmark.RECTUM,
    AnastomosisSubtype.ILEORECTAL: Landmark.RECTUM,
    AnastomosisSubtype.GASTROJEJUNAL: Landmark.STOMACH,
    AnastomosisSubtype.ESOPHAGOJEJUNAL: Landmark.ESOPHAGUS,
    AnastomosisSubtype.ESOPHAGOGASTRIC: Landmark.ESOPHAGUS,
})


def anastomosis_place(subtype: AnastomosisSubtype | None) -> Landmark | None:
    """D34: the place an anastomosis of ``subtype`` takes (ANASTOMOSIS_PLACE), None for a subtype that names none."""
    return ANASTOMOSIS_PLACE.get(subtype) if subtype is not None else None
