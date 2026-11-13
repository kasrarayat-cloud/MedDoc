"""The contract's shared types (docs/gemini-migration/FINAL-V2.md, step 0b of 8.1): every enumeration of FINAL-V2
1.3-1.7, 2.4 and 3.2-3.3 as an Enum, and the records the contract passes between its modules - a unit (1.2), pass 1's
source, fact and doubt (1.3), pass 2's claim, card, verdict and unlisted statement (2.4, 3.2), and the settled fact the
EventInventory row stores (1.7).

**Every enumeration is a plain Enum** whose values are the design's strings, in the design's order. Three hold values
the design does not write as strings: CheckStatus's failed and Attribute's dotted 1.4 paths (readings DECISIONS D207
records), and CardType's type names (2.4 gives each type only its id letter, which CardType.letter holds). It is never
a StrEnum: a member is not a str, so a string operation on a value is a type error (FINAL-V2 5.7 measure 5) and a member
never compares equal to a raw string. Each is @unique, so a repeated value fails at import instead of silently making an
alias. Where the design derives a list from v1's (KINDS, DEVICES2, LANDMARKS2, EXTENTS, SESSION_KINDS, MULTIPLICITY,
DATE_ROLES, DATE_STATES), the values are written out here and tests/v2/test_types.py proves them equal to v1's tuples by
value, so this module executes no v1 code (5.7).

**The records are frozen dataclasses with slots**, holding exactly the fields the design names; each docstring gives
them. The pass-1 and pass-2 records keep the wire form - ids and values as the answers write them - because they are
read and checked here, in the contract; the engine never sees them (engine/types.py holds its typed, text-free view).

This module imports nothing but the standard library. It holds no word list: each Enum is the closed list of values the
design names (NoWordLists, FINAL-V2 5.7 measure 4, admits the values of a contract enumeration), and nothing here
compares a value with document text.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique

# --- pass 1's fact and doubt (FINAL-V2 1.3) ---------------------------------------------------------------------------


@unique
class FactState(Enum):
    """FACT_STATES of FINAL-V2 1.3: supported (the document states the value for this object); negated (it explicitly
    states the value does not hold for it); contradicted (it states incompatible values of one attribute of one object).
    A silent attribute has no state: its slot is empty."""
    SUPPORTED = 'supported'
    NEGATED = 'negated'
    CONTRADICTED = 'contradicted'


@unique
class Link(Enum):
    """LINKS of FINAL-V2 1.3: what a cited unit is for the object it is cited for. Each has a deterministic geometry
    (3.1 G1): statement, the object's own statement; section, the start or closing signature of the containing section;
    frame, a framing sentence inside that section; placing, a sentence anywhere that says when or by whom this act or
    the acts of a part were done [R:CO-2]; document_frame, a unit of N0 that is a source of an encounter fact;
    antecedent, the earlier statement an anaphoric frame refers to; other_statement, another statement about the same
    object."""
    STATEMENT = 'statement'
    SECTION = 'section'
    FRAME = 'frame'
    PLACING = 'placing'
    DOCUMENT_FRAME = 'document_frame'
    ANTECEDENT = 'antecedent'
    OTHER_STATEMENT = 'other_statement'


@unique
class Qualifier(Enum):
    """QUALIFIERS of FINAL-V2 1.3: what a statement says about itself. Any qualifier but approximate makes the fact
    unresolved (3.1 Q1); approximate is recorded and never lowers. Plans, attempts and denials are statuses, never
    qualifiers."""
    HEDGED = 'hedged'
    CONDITIONAL = 'conditional'
    REPORTED = 'reported'
    PARTIAL = 'partial'
    NAMED_ONLY = 'named_only'
    RESTATEMENT_ONLY = 'restatement_only'
    REFERENCE_ONLY = 'reference_only'
    APPROXIMATE = 'approximate'


@unique
class DoubtBasis(Enum):
    """DOUBT_BASES of FINAL-V2 1.3: why pass 1 doubts a fact. stated: the document itself states doubt; conflict:
    another statement cannot be true together with the fact; unclear: the words admit two or more readings. 3.3 rows 1
    and 2 give what settle does with each."""
    STATED = 'stated'
    CONFLICT = 'conflict'
    UNCLEAR = 'unclear'


@unique
class DoubtAbout(Enum):
    """DOUBT_ABOUT of FINAL-V2 1.4 [R:CO-1]: the attribute a doubt names. whole names every claimed fact of the doubt's
    objects."""
    STATUS = 'status'
    KIND = 'kind'
    SESSION = 'session'
    DATE_RELATION = 'date_relation'
    PERFORMER = 'performer'
    ENTRY = 'entry'
    TARGET = 'target'
    TECHNIQUE = 'technique'
    PURPOSE = 'purpose'
    CAUSE = 'cause'
    PART_OF = 'part_of'
    YIELD = 'yield'
    ACCESS_OUTCOME = 'access_outcome'
    EXTENT = 'extent'
    STATIONS = 'stations'
    COMPLETION = 'completion'
    APPROACH = 'approach'
    ANATOMY = 'anatomy'
    IDENTITY = 'identity'
    DATE_OF_SERVICE = 'date_of_service'
    VISIT = 'visit'
    WHOLE = 'whole'


# --- pass 1's value enumerations (FINAL-V2 1.4) -----------------------------------------------------------------------


@unique
class Kind(Enum):
    """KINDS of FINAL-V2 1.4: v1's 42 act kinds (schema.KINDS), unchanged; removal and intervention stay umbrellas."""
    EXAMINATION = 'examination'
    EM_VISIT = 'em_visit'
    EM_PROLONGED = 'em_prolonged'
    BIOPSY = 'biopsy'
    HOT_BIOPSY = 'hot_biopsy'
    SNARE = 'snare'
    EMR = 'emr'
    ESD = 'esd'
    REMOVAL = 'removal'
    ABLATION = 'ablation'
    BLEEDING_CONTROL = 'bleeding_control'
    CLIP = 'clip'
    TATTOO = 'tattoo'
    INJECTION = 'injection'
    BAND_LIGATION = 'band_ligation'
    DILATION = 'dilation'
    STENT = 'stent'
    STENT_REMOVAL = 'stent_removal'
    STENT_EXCHANGE = 'stent_exchange'
    FOREIGN_BODY = 'foreign_body'
    DECOMPRESSION = 'decompression'
    TUBE_PLACEMENT = 'tube_placement'
    TUBE_REPLACEMENT = 'tube_replacement'
    PEG = 'peg'
    MYOTOMY = 'myotomy'
    FUNDOPLICATION = 'fundoplication'
    FNA = 'fna'
    DRAINAGE = 'drainage'
    CANNULATION = 'cannulation'
    SPHINCTEROTOMY = 'sphincterotomy'
    STONE_EXTRACTION = 'stone_extraction'
    LITHOTRIPSY = 'lithotripsy'
    CHOLANGIOSCOPY = 'cholangioscopy'
    PRESSURE_MEASUREMENT = 'pressure_measurement'
    CAPSULE_STUDY = 'capsule_study'
    MANOMETRY = 'manometry'
    PH_MONITORING = 'ph_monitoring'
    RECTAL_SENSATION = 'rectal_sensation'
    BALLOON_EXPULSION = 'balloon_expulsion'
    MODERATE_SEDATION = 'moderate_sedation'
    INTERVENTION = 'intervention'
    OTHER = 'other'


@unique
class DateRole(Enum):
    """DATE_ROLES of FINAL-V2 1.4: v1's roles of a date the document gives besides the date of service."""
    THIS_ENCOUNTER = 'this_encounter'
    BIRTH = 'birth'
    OTHER_OCCURRENCE = 'other_occurrence'
    OTHER_DOCUMENT = 'other_document'
    REPORT_TIME = 'report_time'
    UNCLEAR = 'unclear'


@unique
class DateState(Enum):
    """DATE_STATES of FINAL-V2 1.4: v1's states of the encounter's date of service (1.4 ENCOUNTER.date_of_service)."""
    STATED = 'stated'
    SEVERAL = 'several'
    NOT_STATED = 'not_stated'


@unique
class Multiplicity(Enum):
    """MULTIPLICITY of FINAL-V2 1.4: v1's, less unknown (a silent multiplicity is an empty slot)."""
    SINGLE = 'single'
    GROUP = 'group'


@unique
class Device(Enum):
    """DEVICES2 of FINAL-V2 1.4: v1's DEVICES less not_stated (29); an unstated device is an empty slot."""
    ENDOSCOPE = 'endoscope'
    COLD_SNARE = 'cold_snare'
    HOT_SNARE = 'hot_snare'
    SNARE = 'snare'
    COLD_FORCEPS = 'cold_forceps'
    HOT_FORCEPS = 'hot_forceps'
    FORCEPS = 'forceps'
    NEEDLE = 'needle'
    INJECTION = 'injection'
    BALLOON = 'balloon'
    WIRE_BOUGIE = 'wire_bougie'
    BOUGIE = 'bougie'
    CLIP = 'clip'
    BAND = 'band'
    ARGON_PLASMA = 'argon_plasma'
    RADIOFREQUENCY = 'radiofrequency'
    CRYOTHERAPY = 'cryotherapy'
    THERMAL_PROBE = 'thermal_probe'
    ELECTROCAUTERY = 'electrocautery'
    STENT = 'stent'
    BASKET = 'basket'
    EXTRACTION_BALLOON = 'extraction_balloon'
    SPHINCTEROTOME = 'sphincterotome'
    LITHOTRIPTER = 'lithotripter'
    CHOLANGIOSCOPE = 'cholangioscope'
    CAPSULE = 'capsule'
    CATHETER = 'catheter'
    MANUAL = 'manual'
    OTHER = 'other'


@unique
class Landmark(Enum):
    """LANDMARKS2 of FINAL-V2 1.4: v1's LANDMARKS less not_stated, plus third_portion_duodenum and
    fourth_portion_duodenum (contained in duodenum). The design does not place the two new values; they follow
    second_portion_duodenum here, so the duodenal portions read in order, and every v1 value keeps its v1 order."""
    ESOPHAGUS = 'esophagus'
    PROXIMAL_ESOPHAGUS = 'proximal_esophagus'
    MID_ESOPHAGUS = 'mid_esophagus'
    DISTAL_ESOPHAGUS = 'distal_esophagus'
    GASTROESOPHAGEAL_JUNCTION = 'gastroesophageal_junction'
    STOMACH = 'stomach'
    GASTRIC_CARDIA = 'gastric_cardia'
    GASTRIC_FUNDUS = 'gastric_fundus'
    GASTRIC_BODY = 'gastric_body'
    GASTRIC_ANTRUM = 'gastric_antrum'
    PYLORUS = 'pylorus'
    DUODENUM = 'duodenum'
    DUODENAL_BULB = 'duodenal_bulb'
    SECOND_PORTION_DUODENUM = 'second_portion_duodenum'
    THIRD_PORTION_DUODENUM = 'third_portion_duodenum'
    FOURTH_PORTION_DUODENUM = 'fourth_portion_duodenum'
    AMPULLA = 'ampulla'
    JEJUNUM = 'jejunum'
    ILEUM = 'ileum'
    TERMINAL_ILEUM = 'terminal_ileum'
    NEO_TERMINAL_ILEUM = 'neo_terminal_ileum'
    SMALL_BOWEL = 'small_bowel'
    COLON = 'colon'
    RIGHT_COLON = 'right_colon'
    LEFT_COLON = 'left_colon'
    PROXIMAL_COLON = 'proximal_colon'
    DISTAL_COLON = 'distal_colon'
    CECUM = 'cecum'
    APPENDICEAL_ORIFICE = 'appendiceal_orifice'
    ILEOCECAL_VALVE = 'ileocecal_valve'
    ASCENDING_COLON = 'ascending_colon'
    HEPATIC_FLEXURE = 'hepatic_flexure'
    TRANSVERSE_COLON = 'transverse_colon'
    SPLENIC_FLEXURE = 'splenic_flexure'
    DESCENDING_COLON = 'descending_colon'
    SIGMOID_COLON = 'sigmoid_colon'
    RECTOSIGMOID = 'rectosigmoid'
    RECTUM = 'rectum'
    ANAL_CANAL = 'anal_canal'
    ANASTOMOSIS = 'anastomosis'
    STOMA = 'stoma'
    POUCH = 'pouch'
    COMMON_BILE_DUCT = 'common_bile_duct'
    BILE_DUCT = 'bile_duct'
    PANCREATIC_DUCT = 'pancreatic_duct'
    PANCREAS = 'pancreas'
    GALLBLADDER = 'gallbladder'
    LIVER = 'liver'
    LYMPH_NODE = 'lymph_node'
    OTHER = 'other'


@unique
class Extent(Enum):
    """EXTENTS of FINAL-V2 1.4: LANDMARKS2's values, in its order, plus stated_depth (an extent stated without a
    landmark, "to 40 cm"). Written out because an Enum cannot extend another with members."""
    ESOPHAGUS = 'esophagus'
    PROXIMAL_ESOPHAGUS = 'proximal_esophagus'
    MID_ESOPHAGUS = 'mid_esophagus'
    DISTAL_ESOPHAGUS = 'distal_esophagus'
    GASTROESOPHAGEAL_JUNCTION = 'gastroesophageal_junction'
    STOMACH = 'stomach'
    GASTRIC_CARDIA = 'gastric_cardia'
    GASTRIC_FUNDUS = 'gastric_fundus'
    GASTRIC_BODY = 'gastric_body'
    GASTRIC_ANTRUM = 'gastric_antrum'
    PYLORUS = 'pylorus'
    DUODENUM = 'duodenum'
    DUODENAL_BULB = 'duodenal_bulb'
    SECOND_PORTION_DUODENUM = 'second_portion_duodenum'
    THIRD_PORTION_DUODENUM = 'third_portion_duodenum'
    FOURTH_PORTION_DUODENUM = 'fourth_portion_duodenum'
    AMPULLA = 'ampulla'
    JEJUNUM = 'jejunum'
    ILEUM = 'ileum'
    TERMINAL_ILEUM = 'terminal_ileum'
    NEO_TERMINAL_ILEUM = 'neo_terminal_ileum'
    SMALL_BOWEL = 'small_bowel'
    COLON = 'colon'
    RIGHT_COLON = 'right_colon'
    LEFT_COLON = 'left_colon'
    PROXIMAL_COLON = 'proximal_colon'
    DISTAL_COLON = 'distal_colon'
    CECUM = 'cecum'
    APPENDICEAL_ORIFICE = 'appendiceal_orifice'
    ILEOCECAL_VALVE = 'ileocecal_valve'
    ASCENDING_COLON = 'ascending_colon'
    HEPATIC_FLEXURE = 'hepatic_flexure'
    TRANSVERSE_COLON = 'transverse_colon'
    SPLENIC_FLEXURE = 'splenic_flexure'
    DESCENDING_COLON = 'descending_colon'
    SIGMOID_COLON = 'sigmoid_colon'
    RECTOSIGMOID = 'rectosigmoid'
    RECTUM = 'rectum'
    ANAL_CANAL = 'anal_canal'
    ANASTOMOSIS = 'anastomosis'
    STOMA = 'stoma'
    POUCH = 'pouch'
    COMMON_BILE_DUCT = 'common_bile_duct'
    BILE_DUCT = 'bile_duct'
    PANCREATIC_DUCT = 'pancreatic_duct'
    PANCREAS = 'pancreas'
    GALLBLADDER = 'gallbladder'
    LIVER = 'liver'
    LYMPH_NODE = 'lymph_node'
    OTHER = 'other'
    STATED_DEPTH = 'stated_depth'


@unique
class Status(Enum):
    """STATUSES of FINAL-V2 1.4. An act not done is its status performed, negated; a status in doubt is a doubt."""
    PERFORMED = 'performed'
    ATTEMPTED_NOT_COMPLETED = 'attempted_not_completed'
    PLANNED = 'planned'


@unique
class DateRelation(Enum):
    """DATE_RELATIONS of FINAL-V2 1.4: when an act was done (or the acts told in a part), relative to the date of
    service."""
    ON_DATE_OF_SERVICE = 'on_date_of_service'
    EARLIER_DATE = 'earlier_date'
    LATER_DATE = 'later_date'


@unique
class EncounterRelation(Enum):
    """ENCOUNTER_RELATIONS of FINAL-V2 1.4: whether a session is this document's encounter or a separate one."""
    THIS_ENCOUNTER = 'this_encounter'
    SEPARATE_ENCOUNTER = 'separate_encounter'


@unique
class Performer(Enum):
    """PERFORMERS of FINAL-V2 1.4: who did an act (or the acts told in a part)."""
    DOCUMENTING_TEAM = 'documenting_team'
    OTHER_CLINICIAN = 'other_clinician'
    OTHER_FACILITY = 'other_facility'


@unique
class Owner(Enum):
    """OWNERS of FINAL-V2 1.4: whose entry a part of the document is."""
    DOCUMENTING_CLINICIAN = 'documenting_clinician'
    NURSING = 'nursing'
    ANESTHESIA = 'anesthesia'
    PATHOLOGY = 'pathology'
    RADIOLOGY = 'radiology'
    OTHER_CLINICIAN = 'other_clinician'
    OUTSIDE_RECORD = 'outside_record'
    PATIENT_REPORTED = 'patient_reported'
    ADMINISTRATIVE = 'administrative'


@unique
class SectionRole(Enum):
    """SECTION_ROLES of FINAL-V2 1.4: what a part of the document is."""
    HEADER = 'header'
    INDICATION = 'indication'
    HISTORY = 'history'
    MEDICATIONS = 'medications'
    SEDATION = 'sedation'
    PROCEDURE = 'procedure'
    FINDINGS = 'findings'
    IMPRESSION = 'impression'
    COMPLICATIONS = 'complications'
    SPECIMENS = 'specimens'
    PLAN = 'plan'
    PATHOLOGY_RESULT = 'pathology_result'
    NURSING_NOTE = 'nursing_note'
    ANESTHESIA_RECORD = 'anesthesia_record'
    ADDENDUM = 'addendum'
    SIGNATURE = 'signature'
    OTHER = 'other'


@unique
class PersonRole(Enum):
    """PERSON_ROLES of FINAL-V2 1.4: a named person's role."""
    DOCUMENTING_CLINICIAN = 'documenting_clinician'
    TRAINEE = 'trainee'
    ASSISTANT = 'assistant'
    NURSE = 'nurse'
    ANESTHESIA = 'anesthesia'
    PATHOLOGIST = 'pathologist'
    RADIOLOGIST = 'radiologist'
    REFERRING = 'referring'
    OTHER = 'other'


@unique
class OtherClass(Enum):
    """OTHER_CLASSES of FINAL-V2 1.4: the class of an act of kind other (G5, T4)."""
    PROCEDURE = 'procedure'
    TEST = 'test'
    ORDER = 'order'
    IMAGING = 'imaging'
    LABORATORY = 'laboratory'
    COUNSELING = 'counseling'
    EVALUATION = 'evaluation'
    MEDICATION = 'medication'
    OTHER = 'other'


@unique
class SessionKind(Enum):
    """SESSION_KINDS of FINAL-V2 1.4: v1's PROCEDURES less unknown (16), the family slugs of gi.profiles (the family
    table is unchanged)."""
    OFFICE_EM = 'office_em'
    EGD = 'egd'
    ENTEROSCOPY = 'enteroscopy'
    COLONOSCOPY = 'colonoscopy'
    FLEX_SIG = 'flex_sig'
    EUS = 'eus'
    ERCP = 'ercp'
    CAPSULE = 'capsule'
    MOTILITY = 'motility'
    REFLUX = 'reflux'
    ANORECTAL = 'anorectal'
    FEEDING_TUBE = 'feeding_tube'
    SEDATION = 'sedation'
    EM_OTHER = 'em_other'
    OTHER_GI = 'other_gi'
    NOT_GI = 'not_gi'


@unique
class Tract(Enum):
    """TRACTS of FINAL-V2 1.4: the tract a session examined."""
    UPPER = 'upper'
    LOWER = 'lower'
    PANCREATOBILIARY = 'pancreatobiliary'


@unique
class Approach(Enum):
    """APPROACHES of FINAL-V2 1.4: how the scope entered."""
    ORAL = 'oral'
    TRANSNASAL = 'transnasal'
    TRANSANAL = 'transanal'
    THROUGH_STOMA = 'through_stoma'
    THROUGH_POUCH = 'through_pouch'
    THROUGH_GASTROSTOMY = 'through_gastrostomy'
    PERCUTANEOUS = 'percutaneous'


@unique
class Completion(Enum):
    """COMPLETIONS of FINAL-V2 1.4 [R:CO-8], against the examination's own intended extent as the document states it:
    complete (it reached that extent), incomplete (it stopped short of it), terminated (it stopped early for a stated
    reason)."""
    COMPLETE = 'complete'
    INCOMPLETE = 'incomplete'
    TERMINATED = 'terminated'


@unique
class Station(Enum):
    """STATIONS of FINAL-V2 1.4: the parts a session examined (supported) or did not examine (negated)."""
    ESOPHAGUS = 'esophagus'
    STOMACH = 'stomach'
    DUODENUM = 'duodenum'
    JEJUNUM = 'jejunum'
    ILEUM = 'ileum'
    COLON = 'colon'
    RECTUM = 'rectum'


@unique
class Structure(Enum):
    """STRUCTURES of FINAL-V2 1.4: what an act was done to."""
    LESION = 'lesion'
    STRICTURE = 'stricture'
    ULCER = 'ulcer'
    BLEEDING_SITE = 'bleeding_site'
    VESSEL = 'vessel'
    VARIX = 'varix'
    STONE = 'stone'
    STENT = 'stent'
    DUCT = 'duct'
    PANCREATIC_FLUID_COLLECTION = 'pancreatic_fluid_collection'
    GALLBLADDER = 'gallbladder'
    LIVER = 'liver'
    LYMPH_NODE = 'lymph_node'
    MASS = 'mass'
    WALL = 'wall'
    LUMEN = 'lumen'
    FOREIGN_BODY = 'foreign_body'
    MUCOSA = 'mucosa'
    ANASTOMOSIS = 'anastomosis'
    OTHER = 'other'


@unique
class Duct(Enum):
    """DUCTS of FINAL-V2 1.4."""
    BILIARY = 'biliary'
    PANCREATIC = 'pancreatic'
    CYSTIC = 'cystic'


@unique
class Route(Enum):
    """ROUTES of FINAL-V2 1.4: how an act's agent reached the tissue (G1)."""
    SUBMUCOSAL = 'submucosal'
    EUS_TRANSMURAL = 'eus_transmural'
    EUS_FINE_NEEDLE = 'eus_fine_needle'
    INTRALUMINAL = 'intraluminal'
    INTRADUCTAL = 'intraductal'
    PERCUTANEOUS = 'percutaneous'
    TOPICAL = 'topical'


@unique
class Purpose(Enum):
    """PURPOSES of FINAL-V2 1.4. hemostasis: bleeding present at this encounter, treated; prophylaxis: prevention."""
    DIAGNOSTIC = 'diagnostic'
    REMOVAL = 'removal'
    LIFT_FOR_RESECTION = 'lift_for_resection'
    MARKING = 'marking'
    HEMOSTASIS = 'hemostasis'
    PROPHYLAXIS = 'prophylaxis'
    TREATMENT = 'treatment'
    ACCESS = 'access'
    SAMPLING = 'sampling'
    DRAINAGE = 'drainage'
    DECOMPRESSION = 'decompression'
    OTHER = 'other'


@unique
class Cause(Enum):
    """CAUSES of FINAL-V2 1.4: what caused the bleeding a hemostasis act treated."""
    ACT_OF_THIS_SESSION = 'act_of_this_session'
    PRE_EXISTING_LESION = 'pre_existing_lesion'
    SPONTANEOUS = 'spontaneous'
    EARLIER_PROCEDURE = 'earlier_procedure'
    OTHER = 'other'


@unique
class PartRelation(Enum):
    """PART_RELATIONS of FINAL-V2 1.4: how an act is part of another."""
    STEP_OF = 'step_of'
    LIFT_FOR = 'lift_for'
    ACCESS_FOR = 'access_for'
    ADJUNCT_OF = 'adjunct_of'
    COMPONENT_OF = 'component_of'


@unique
class Material(Enum):
    """MATERIALS of FINAL-V2 1.4: what an extraction act retrieved; anything negated means nothing was retrieved."""
    STONES = 'stones'
    STONE_FRAGMENTS = 'stone_fragments'
    SLUDGE = 'sludge'
    DEBRIS = 'debris'
    STENT = 'stent'
    FOREIGN_BODY = 'foreign_body'
    TISSUE = 'tissue'
    ANYTHING = 'anything'


@unique
class AccessOutcome(Enum):
    """ACCESS_OUTCOMES of FINAL-V2 1.4: the outcome of a cannulation act."""
    ACHIEVED = 'achieved'
    FAILED = 'failed'
    ACHIEVED_AFTER_FAILED_ATTEMPTS = 'achieved_after_failed_attempts'


@unique
class Breadth(Enum):
    """BREADTHS of FINAL-V2 1.4: what a statement (a denial) covers."""
    SINGLE_TARGET = 'single_target'
    LISTED_TARGETS = 'listed_targets'
    ALL_OF_KIND = 'all_of_kind'
    EXCEPTIVE = 'exceptive'
    SEGMENT = 'segment'


@unique
class AnatomyType(Enum):
    """ANATOMY_TYPES of FINAL-V2 1.4: an anatomy entry's alteration or absence."""
    SURGICALLY_ABSENT = 'surgically_absent'
    ANASTOMOSIS = 'anastomosis'
    STOMA = 'stoma'
    ILEAL_POUCH = 'ileal_pouch'
    GASTRIC_POUCH = 'gastric_pouch'
    ROUX_LIMB = 'roux_limb'
    BYPASS = 'bypass'
    OTHER_ALTERATION = 'other_alteration'


@unique
class AnastomosisSubtype(Enum):
    """ANASTOMOSIS_SUBTYPES of FINAL-V2 1.4."""
    ILEOCOLIC = 'ileocolic'
    COLOCOLIC = 'colocolic'
    COLORECTAL = 'colorectal'
    COLOANAL = 'coloanal'
    ILEORECTAL = 'ileorectal'
    ILEOANAL = 'ileoanal'
    GASTROJEJUNAL = 'gastrojejunal'
    GASTRODUODENAL = 'gastroduodenal'
    ESOPHAGOJEJUNAL = 'esophagojejunal'
    ESOPHAGOGASTRIC = 'esophagogastric'
    HEPATICOJEJUNAL = 'hepaticojejunal'
    CHOLEDOCHODUODENAL = 'choledochoduodenal'
    PANCREATICOJEJUNAL = 'pancreaticojejunal'
    OTHER = 'other'


@unique
class RestatementRole(Enum):
    """RESTATEMENT_ROLES of FINAL-V2 1.4. Only restates can move an act's entry, and only when its role is established
    (1.5, [R:SC-D])."""
    RESTATES = 'restates'
    SUMMARIZES = 'summarizes'
    TITLE = 'title'
    NAMES_ONLY = 'names_only'
    REFERS_BACK = 'refers_back'


@unique
class EmBasis(Enum):
    """EM_BASES of FINAL-V2 1.4: v1's, less not_stated."""
    TOTAL_TIME = 'total_time'
    MEDICAL_DECISION_MAKING = 'medical_decision_making'


@unique
class Separate(Enum):
    """SEPARATE of FINAL-V2 1.4: a visit stated separately identifiable; the denial is that fact negated."""
    STATED = 'stated'


@unique
class Attribute(Enum):
    """The attributes a fact is about: the path of each FACT, SLOT and FACTS field of FINAL-V2 1.4's answer, a nested
    field written ``<field>.<field>`` as 1.6 and 4.3 write it (target.places, technique.device, scope.breadth,
    visit.basis); plus ``entry``, an act's entry (1.5), which is claimed per act though pass 1 never reports it (3.2.2
    act.entry), and ``restatements.role``, the role of a restatement, claimed for a ``restates`` one (3.2.1, [R:SC-D]).
    A path several object families share (kind, performer, role) is one member: the subject's family tells them apart.
    Fields that are sources (a section's start and end, a person's name, a lesion's description, an event's anchor) or
    plain lists are not facts and have no member; scope's targets, segment, covers and excepts are members because their
    statements are claimed (3.2.1)."""
    # the encounter
    DATE_OF_SERVICE = 'date_of_service'
    OTHER_DATES_ROLE = 'other_dates.role'
    DOCUMENTING_CLINICIAN = 'documenting_clinician'
    # a person, a section
    ROLE = 'role'
    OWNER = 'owner'
    OCCASION = 'occasion'
    PERFORMER = 'performer'
    PERFORMER_PERSON = 'performer_person'
    # a session
    EXAMINATION = 'examination'
    KIND = 'kind'
    ENCOUNTER = 'encounter'
    TRACT = 'tract'
    APPROACH = 'approach'
    THROUGH = 'through'
    REACHED = 'reached'
    DEVICE_REACHED = 'device_reached'
    REACHED_ANATOMY = 'reached_anatomy'
    COMPLETION = 'completion'
    STATIONS = 'stations'
    PART_OF_SESSION = 'part_of_session'
    # an anatomy entry
    TYPE = 'type'
    ORGAN = 'organ'
    SUBTYPE = 'subtype'
    JOINS = 'joins'
    # a lesion
    MULTIPLICITY = 'multiplicity'
    PLACES = 'places'
    DISTINCT_FROM = 'distinct_from'
    SAME_AS = 'same_as'
    # an event (kind, performer and performer_person above)
    RESTATEMENTS_ROLE = 'restatements.role'
    OTHER_CLASS = 'other_class'
    STATUS = 'status'
    SESSION = 'session'
    DATE_RELATION = 'date_relation'
    DATE = 'date'
    TARGET_LESION = 'target.lesion'
    TARGET_STRUCTURE = 'target.structure'
    TARGET_PLACES = 'target.places'
    TARGET_ANATOMY = 'target.anatomy'
    TARGET_DUCT = 'target.duct'
    TECHNIQUE_DEVICE = 'technique.device'
    TECHNIQUE_ROUTE = 'technique.route'
    PURPOSE = 'purpose'
    CAUSE = 'cause'
    CAUSE_EVENT = 'cause_event'
    PART_OF = 'part_of'
    PART_RELATION = 'part_relation'
    YIELD = 'yield'
    ACCESS_OUTCOME = 'access_outcome'
    SCOPE_BREADTH = 'scope.breadth'
    SCOPE_TARGETS = 'scope.targets'
    SCOPE_SEGMENT = 'scope.segment'
    SCOPE_COVERS = 'scope.covers'
    SCOPE_EXCEPTS = 'scope.excepts'
    VISIT_BASIS = 'visit.basis'
    VISIT_SEPARATELY_IDENTIFIABLE = 'visit.separately_identifiable'
    ENTRY = 'entry'


# --- the settled fact (FINAL-V2 1.7, 3.3) -----------------------------------------------------------------------------


@unique
class Result(Enum):
    """The result settle gives each fact (FINAL-V2 1.7, 3.3): supported and negated are established; contradicted,
    unknown (silent, or doubted with its value kept) and unresolved are not."""
    SUPPORTED = 'supported'
    NEGATED = 'negated'
    CONTRADICTED = 'contradicted'
    UNKNOWN = 'unknown'
    UNRESOLVED = 'unresolved'


@unique
class CheckStatus(Enum):
    """The outcome of one deterministic check of a fact or source (FINAL-V2 1.7 checks, sources[].geometry). The design
    names "ok"; "failed" is its only complement, and a failure's detail is in the fact's reasons (Reason)."""
    OK = 'ok'
    FAILED = 'failed'


@unique
class Precision(Enum):
    """The precision of a date literal or date value (FINAL-V2 1.7 checks.literals; 3.1 L1: day, month and year), as
    v1's literals name them."""
    DAY = 'day'
    MONTH = 'month'
    YEAR = 'year'


@unique
class Reason(Enum):
    """Why a fact settled as it did: the closed list settle.REASONS is drawn from and store.load checks (FINAL-V2 1.7,
    3.3). In 3.3's row order: a contradiction (row 1), a doubt (row 2), silence (row 3), each check's reasons (row 4:
    3.1's S2, I1-I4, G1-G5, K1's structure_<rule> - one per rule of 3.1 K1, with consistency.Structure's values
    (DECISIONS D186) - K2-K7 and L1, then the cross-object anchor rule), a qualifier (row 5: qualified:<q> for every
    Qualifier but approximate), a fact outside CLAIMED (row 6), indistinct cards (row 7), and the appraisal (row 9:
    3.2.3's coherence table, appraisal_qualified:<q> for every Qualifier2, then appraisal_qualified, a qualified verdict
    that names no qualifier, D186). G6 ignores a restatement and K8 settles as row 1, so neither has a reason of its
    own; the cross-object rules of 3.1 add none either, since an inherited fact carries its section fact's reasons
    (D186)."""
    CONTRADICTED_BY_PASS1 = 'contradicted_by_pass1'
    DOUBT_STATED = 'doubt_stated'
    DOUBT_UNCLEAR = 'doubt_unclear'
    SILENT = 'silent'
    SHAPE_INCONSISTENT = 'shape_inconsistent'
    UNIT_UNKNOWN = 'unit_unknown'
    WORDS_NOT_IN_UNITS = 'words_not_in_units'
    WORDS_NOT_BOUNDED = 'words_not_bounded'
    UNITS_NOT_CONSECUTIVE = 'units_not_consecutive'
    SOURCE_TOO_LONG = 'source_too_long'
    ANCHOR_WORDS = 'anchor_words'
    REFERENCE_INVALID = 'reference_invalid'
    GEOMETRY_STATEMENT = 'geometry_statement'
    GEOMETRY_SECTION = 'geometry_section'
    GEOMETRY_FRAME = 'geometry_frame'
    GEOMETRY_PLACING = 'geometry_placing'
    GEOMETRY_DOCUMENT_FRAME = 'geometry_document_frame'
    GEOMETRY_ANTECEDENT = 'geometry_antecedent'
    GEOMETRY_OTHER_STATEMENT = 'geometry_other_statement'
    SECTION_ORDER = 'section_order'
    SECTION_START_UNLOCATED = 'section_start_unlocated'
    TARGET_DETACHED = 'target_detached'
    INHERIT_UNATTACHED = 'inherit_unattached'
    EXTENT_INFERRED = 'extent_inferred'
    STRUCTURE_SCOPE = 'structure_scope'
    STRUCTURE_YIELD = 'structure_yield'
    STRUCTURE_ACCESS_OUTCOME = 'structure_access_outcome'
    STRUCTURE_CAUSE = 'structure_cause'
    STRUCTURE_PART_OF = 'structure_part_of'
    STRUCTURE_ENDOSCOPIC = 'structure_endoscopic'
    STRUCTURE_VISIT = 'structure_visit'
    STRUCTURE_OTHER_CLASS = 'structure_other_class'
    STRUCTURE_STATUS_TIME = 'structure_status_time'
    STRUCTURE_EXCEPTIVE = 'structure_exceptive'
    STRUCTURE_LISTED_TARGETS = 'structure_listed_targets'
    STRUCTURE_SINGLE_TARGET = 'structure_single_target'
    STRUCTURE_SEGMENT = 'structure_segment'
    STRUCTURE_UMBRELLA = 'structure_umbrella'
    SESSION_INCONSISTENT = 'session_inconsistent'
    SESSION_CONFLICT = 'session_conflict'
    SESSION_UNREACHABLE = 'session_unreachable'
    ANATOMY_CONFLICT = 'anatomy_conflict'
    PERSON_CONFLICT = 'person_conflict'
    INSTRUMENT_CONFLICT = 'instrument_conflict'
    FRAME_ROLE = 'frame_role'
    LITERAL_MISMATCH = 'literal_mismatch'
    LITERAL_UNCHECKED = 'literal_unchecked'
    ANCHOR_INVALID = 'anchor_invalid'
    QUALIFIED_HEDGED = 'qualified:hedged'
    QUALIFIED_CONDITIONAL = 'qualified:conditional'
    QUALIFIED_REPORTED = 'qualified:reported'
    QUALIFIED_PARTIAL = 'qualified:partial'
    QUALIFIED_NAMED_ONLY = 'qualified:named_only'
    QUALIFIED_RESTATEMENT_ONLY = 'qualified:restatement_only'
    QUALIFIED_REFERENCE_ONLY = 'qualified:reference_only'
    UNAPPRAISED = 'unappraised'
    CARDS_INDISTINCT = 'cards_indistinct'
    CONTROL_INCOHERENT = 'control_incoherent'
    APPRAISAL_CONTRADICTS = 'appraisal_contradicts'
    APPRAISAL_QUALIFIED_HEDGED = 'appraisal_qualified:hedged'
    APPRAISAL_QUALIFIED_CONDITIONAL = 'appraisal_qualified:conditional'
    APPRAISAL_QUALIFIED_REPORTED = 'appraisal_qualified:reported'
    APPRAISAL_QUALIFIED_PARTIAL = 'appraisal_qualified:partial'
    APPRAISAL_QUALIFIED_NAMED_ONLY = 'appraisal_qualified:named_only'
    APPRAISAL_QUALIFIED_RESTATEMENT_ONLY = 'appraisal_qualified:restatement_only'
    APPRAISAL_QUALIFIED_REFERENCE_ONLY = 'appraisal_qualified:reference_only'
    APPRAISAL_QUALIFIED_APPROXIMATE = 'appraisal_qualified:approximate'
    APPRAISAL_QUALIFIED_NEGATED_CONTEXT = 'appraisal_qualified:negated_context'
    APPRAISAL_QUALIFIED_OTHER_OCCASION = 'appraisal_qualified:other_occasion'
    APPRAISAL_QUALIFIED_OTHER_PERFORMER = 'appraisal_qualified:other_performer'
    APPRAISAL_QUALIFIED_OTHER_ENTRY = 'appraisal_qualified:other_entry'
    APPRAISAL_QUALIFIED_OTHER_TARGET = 'appraisal_qualified:other_target'
    APPRAISAL_QUALIFIED_OTHER_ACT = 'appraisal_qualified:other_act'
    APPRAISAL_QUALIFIED_SCOPE_LIMITED = 'appraisal_qualified:scope_limited'
    APPRAISAL_QUALIFIED_PLANNED_ONLY = 'appraisal_qualified:planned_only'
    APPRAISAL_QUALIFIED_HISTORY_ONLY = 'appraisal_qualified:history_only'
    APPRAISAL_QUALIFIED = 'appraisal_qualified'
    APPRAISAL_UNCLEAR = 'appraisal_unclear'
    APPRAISAL_DETACHED = 'appraisal_detached'
    APPRAISAL_MISSING = 'appraisal_missing'


# --- pass 2's vocabulary (FINAL-V2 2.4, 3.2) --------------------------------------------------------------------------


@unique
class VerdictValue(Enum):
    """VERDICTS of FINAL-V2 2.4 (A3): pass 2's judgment of one claim, the ``verdict`` of a Verdict. A claim phrased
    about a statement asks what the statement concerns, not whether an act was done [R:HO-2]."""
    SUPPORTS = 'supports'
    CONTRADICTS = 'contradicts'
    QUALIFIED = 'qualified'
    UNCLEAR = 'unclear'


@unique
class Attached(Enum):
    """ATTACHED of FINAL-V2 2.4 (A4): whether the cited units, read in their place, are about the object the claim
    names."""
    YES = 'yes'
    NO = 'no'
    UNCLEAR = 'unclear'


@unique
class Qualifier2(Enum):
    """QUALIFIERS_2 of FINAL-V2 2.4: QUALIFIERS' values, in their order, then the nine pass 2 adds. A qualified verdict
    leaves its fact unresolved (3.2.3: appraisal_qualified:<q>)."""
    HEDGED = 'hedged'
    CONDITIONAL = 'conditional'
    REPORTED = 'reported'
    PARTIAL = 'partial'
    NAMED_ONLY = 'named_only'
    RESTATEMENT_ONLY = 'restatement_only'
    REFERENCE_ONLY = 'reference_only'
    APPROXIMATE = 'approximate'
    NEGATED_CONTEXT = 'negated_context'
    OTHER_OCCASION = 'other_occasion'
    OTHER_PERFORMER = 'other_performer'
    OTHER_ENTRY = 'other_entry'
    OTHER_TARGET = 'other_target'
    OTHER_ACT = 'other_act'
    SCOPE_LIMITED = 'scope_limited'
    PLANNED_ONLY = 'planned_only'
    HISTORY_ONLY = 'history_only'


@unique
class UnlistedWhat(Enum):
    """What an unlisted statement is (FINAL-V2 2.4 A6, APPRAISAL.unlisted ``what``; 3.2.6): an act, a denial of an act,
    or a doubt about an act."""
    ACT = 'act'
    DENIAL = 'denial'
    DOUBT = 'doubt'


@unique
class CardType(Enum):
    """The object type a card names (FINAL-V2 2.4): acts and statements about acts alike (so a card never tells a denial
    from an act), sessions, sections, lesions, anatomy entries. Its value is the type's name; ``letter`` is the letter
    its cards' ids are renumbered with (2.4: A1.., X1.., N0.., L1.., Y1..)."""
    ACT = 'act'
    SESSION = 'session'
    SECTION = 'section'
    LESION = 'lesion'
    ANATOMY = 'anatomy'

    @property
    def letter(self) -> str:
        """The letter of this type's card ids (FINAL-V2 2.4): A acts and statements about acts, X sessions, N sections,
        L lesions, Y anatomy entries. An id format, compared with no document text."""
        return {CardType.ACT: 'A', CardType.SESSION: 'X', CardType.SECTION: 'N', CardType.LESION: 'L',
                CardType.ANATOMY: 'Y'}[self]


# --- the records ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """An integer span [start, end) of the revision text (FINAL-V2 1.7, 4.1: "ids and integer spans"). It holds no text,
    so the engine reads it (engine/types.py re-exports it under the name the design gives it there); wording.quote(span)
    slices the revision after the decision. Ordered by (start, end): document order. ValueError unless 0 <= start <=
    end, both int."""
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start <= self.end:
            raise ValueError(f'A span runs from 0 <= start <= end; got ({self.start!r}, {self.end!r}).')


@dataclass(frozen=True, slots=True)
class Unit:
    """One unit of the revision, meant to be a sentence, as contract/segment.py cuts it (FINAL-V2 1.2 rule 5). Geometry
    only: a unit is its offsets and holds no text.

    id: 'S<k>', numbered in document order. start, end: offsets in the revision text, trimmed of surrounding whitespace,
    so the unit is text[start:end]. line, paragraph, page: the unit's (first) line, its paragraph and its page, as
    segment numbers them; a unit never crosses a page. forced: True when the unit was split at the last space before 600
    characters (rule 4)."""
    id: str
    start: int
    end: int
    line: int
    paragraph: int
    page: int
    forced: bool


@dataclass(frozen=True, slots=True)
class Source:
    """A citation in pass 1's answer (FINAL-V2 1.3 SOURCE).

    units: the cited unit ids, consecutive within one paragraph (at most 12, an item-level bound: 1.8, 3.1 I3). words:
    the exact words inside the cited units, which may run over them (1.2 rule 7), or '' to cite the whole of the units.
    link: what the cited units are for the object (Link; its geometry is 3.1 G1)."""
    units: tuple[str, ...]
    words: str
    link: Link


@dataclass(frozen=True, slots=True)
class Option:
    """One side of a contradicted fact (FINAL-V2 1.3 FACT.options): the value that side states, and its own sources."""
    value: str
    sources: tuple[Source, ...]


@dataclass(frozen=True, slots=True)
class Fact:
    """One judgment in pass 1's answer (FINAL-V2 1.3 FACT; the table there gives each state's value, sources and
    options).

    state: supported | negated | contradicted (FactState). value: an enumeration value, an id or an ISO date at its
    precision, as pass 1 wrote it; '' exactly when contradicted. qualifiers: what the statement says about itself
    (Qualifier). sources: at least one; for a contradicted fact, the union of both sides. options: empty unless
    contradicted, then at least two, one per side (Option). A silent attribute is an empty slot, never a Fact (1.3
    SLOT), and a doubt is kept beside the fact (Doubt), never in it.

    The encounter's date of service is written with v1's DATE_STATES instead (1.4; extract_read.DateOfService), and
    settle maps it onto these states, so it is one settled fact like any other (DECISIONS D187): stated is supported,
    with its value and sources; several is contradicted, value '' and each candidate date an option with its own
    sources (3.3 row 1); not_stated is silent, an empty slot (3.3 row 3)."""
    state: FactState
    value: str
    qualifiers: tuple[Qualifier, ...]
    sources: tuple[Source, ...]
    options: tuple[Option, ...]


@dataclass(frozen=True, slots=True)
class Doubt:
    """A doubt in pass 1's answer (FINAL-V2 1.3 DOUBT; answer level, like v1's open questions) [R:HO-1][R:CO-1].

    about: the attribute it doubts (DoubtAbout; whole names every claimed fact of its objects). objects: the ids of the
    objects it names. units: the unit ids that raise it. basis: stated | conflict | unclear (DoubtBasis). readings: the
    values of that attribute it leaves open. A doubt can only demote: it never creates, sets or changes a value (3.3
    rows 1-2)."""
    about: DoubtAbout
    objects: tuple[str, ...]
    units: tuple[str, ...]
    basis: DoubtBasis
    readings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Claim:
    """One claim in pass 2's request (FINAL-V2 3.2.2-3.2.4): CPT Studio's fixed sentence about one object, rendered by
    contract/claims.py (step 2c) from its template, subject and value, citing units. A control (3.2.3) is a Claim like
    any other; nothing in it marks it.

    id: 'K<k>', its place in the seeded order. template: the id of its template in claims.TEMPLATES or
    STATEMENT_TEMPLATES. subject: the id of the object the claim is about, as pass 1's answer names it. value: the value
    claimed, as pass 1's answer writes it. units: the unit ids it cites (the anchor's sentence closure, or the governing
    source's units for an inherited or placed fact, 3.2.5). content: its content key, the sha256 claims.py computes over
    (template, subject, value, units); every verdict is stored with it, so a verdict is never read against a different
    claim (3.2.4, [R:MO-5])."""
    id: str
    template: str
    subject: str
    value: str
    units: tuple[str, ...]
    content: str


@dataclass(frozen=True, slots=True)
class Card:
    """One card in pass 2's request (FINAL-V2 2.4). It names only an object's type and units, never a label of pass 1's
    values, so no control can be rejected by comparing it with a card [R:SC-C].

    id: renumbered by type: A1.. acts and statements about acts, X1.. sessions, N0.. sections, L1.. lesions, Y1..
    anatomy. type: CardType. units: the unit ids of the anchor's sentence closure (1.2 rule 6), or of a lesion's or
    anatomy entry's description. kind_words, status_words: the spans of the event's own anchor words (its kind words and
    status words: document text, never a value), quoted on the card only when another event shares an anchor unit, so
    the two cards differ [R:CO-7]; None otherwise. Spans, not text: claims.py copies no text (5.6), and the request
    quotes the revision's own slice."""
    id: str
    type: CardType
    units: tuple[str, ...]
    kind_words: Span | None
    status_words: Span | None


@dataclass(frozen=True, slots=True)
class Verdict:
    """Pass 2's answer to one claim (FINAL-V2 2.4 APPRAISAL.verdicts; A3-A5).

    claim: the claim's id. verdict: supports | contradicts | qualified | unclear (VerdictValue). attached: yes | no |
    unclear (Attached). qualifiers: those a qualified verdict names (Qualifier2). evidence: the unit ids relied on, no
    words (at most 8, 1.8); for contradicts and qualified, the units that contradict or qualify, kept as counter sources
    (3.2.5)."""
    claim: str
    verdict: VerdictValue
    attached: Attached
    qualifiers: tuple[Qualifier2, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Unlisted:
    """A statement pass 2 reports that no card's claims describe (FINAL-V2 2.4 A6, APPRAISAL.unlisted; 3.2.6), stored as
    events.unlisted when kept.

    units: its unit ids. what: act | denial | doubt (UnlistedWhat). kind: the Kind the document names, None when it
    names none (pass 2 writes ''). session: the id of the session card it belongs to, None when the document does not
    say (pass 2 writes '')."""
    units: tuple[str, ...]
    what: UnlistedWhat
    kind: Kind | None
    session: str | None


@dataclass(frozen=True, slots=True)
class LocatedWords:
    """A source's words located in the revision (FINAL-V2 1.7 sources[].words): start and end are offsets in the
    revision text, and text is the revision's own slice text[start:end], which store.row proves before a row is written
    (P9: no model string is stored)."""
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class SettledSource:
    """A source as the settled row stores it (FINAL-V2 1.7 sources[]).

    units: its unit ids. link: Link. words: its words located (LocatedWords); None when the source cites its whole units
    (pass 1's words ''). geometry: whether its link geometry (3.1 G1) passed (CheckStatus)."""
    units: tuple[str, ...]
    link: Link
    words: LocatedWords | None
    geometry: CheckStatus


@dataclass(frozen=True, slots=True)
class SettledOption:
    """One side of a contradicted fact as the settled row stores it (FINAL-V2 1.3 options, stored as 1.7 stores
    sources): the value that side states, and its sources."""
    value: str
    sources: tuple[SettledSource, ...]


@dataclass(frozen=True, slots=True)
class SettledClaim:
    """Pass 1's claim as the settled row stores it (FINAL-V2 1.7 claim).

    state: FactState; None for a silent slot. value: as pass 1 wrote it ('' when contradicted or silent). qualifiers:
    Qualifier. options: a contradicted fact's sides (SettledOption). inherited_from: the id of the section an inherited
    fact was taken from (an effective date relation or performer, or an act's entry, 1.5), None for the object's own
    fact."""
    state: FactState | None
    value: str
    qualifiers: tuple[Qualifier, ...]
    options: tuple[SettledOption, ...]
    inherited_from: str | None


@dataclass(frozen=True, slots=True)
class StoredLiteral:
    """A date literal L1 read in a fact's own words (FINAL-V2 1.7 checks.literals[]; 3.1 L1): value, the ISO date at its
    precision; precision: day | month | year. Stored so that assess and read time re-judge it with no text (4.2
    effective)."""
    value: str
    precision: Precision


@dataclass(frozen=True, slots=True)
class Checks:
    """The deterministic checks of one fact (FINAL-V2 1.7 checks; 3.1).

    integrity (S2, I1-I4), geometry (G1-G6), literal (L1) and consistency (K1-K8): each ok or failed (CheckStatus; the
    fact's reasons say why). literals: the date literals L1 read (StoredLiteral). qualified: True when a qualifier other
    than approximate was reported (Q1)."""
    integrity: CheckStatus
    geometry: CheckStatus
    literal: CheckStatus
    literals: tuple[StoredLiteral, ...]
    consistency: CheckStatus
    qualified: bool


@dataclass(frozen=True, slots=True)
class ControlVerdict:
    """An appraised claim's contrary control and pass 2's verdict on it (FINAL-V2 1.7 appraisal.control; 3.2.3): claim,
    the control's claim id; verdict, VerdictValue, None when pass 2 gave none."""
    claim: str
    verdict: VerdictValue | None


@dataclass(frozen=True, slots=True)
class Appraisal:
    """Pass 2's verdict on a fact's claim, as the settled row stores it (FINAL-V2 1.7 appraisal; 3.2.3-3.2.5).

    claim: the claim's id. content: its content key (Claim.content), which binds the verdict to the claim [R:MO-5].
    verdict, attached: pass 2's, None when it gave no verdict (appraisal_missing). qualifiers: Qualifier2. evidence: the
    unit ids pass 2 relied on. control: the control and its verdict (ControlVerdict), None for an attribute decided by a
    single verdict (UNCONTROLLED, 3.2.3)."""
    claim: str
    content: str
    verdict: VerdictValue | None
    attached: Attached | None
    qualifiers: tuple[Qualifier2, ...]
    evidence: tuple[str, ...]
    control: ControlVerdict | None


@dataclass(frozen=True, slots=True)
class SettledFact:
    """One fact of the settled inventory, as contract/settle.py writes it into the EventInventory row (FINAL-V2 1.7; 3.3
    is the table that sets result and reasons). An inherited fact is stored once per act.

    claim: pass 1's claim (SettledClaim). sources: its sources, located (SettledSource). checks: its deterministic
    checks (Checks). appraisal: pass 2's verdict (Appraisal); None for a fact never claimed (silent, doubted,
    contradicted, failed, or outside CLAIMED). result: Result. reasons: why, from the closed list (Reason)."""
    claim: SettledClaim
    sources: tuple[SettledSource, ...]
    checks: Checks
    appraisal: Appraisal | None
    result: Result
    reasons: tuple[Reason, ...]
