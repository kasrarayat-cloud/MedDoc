"""The closed lists evidence binding reads (design/contract.md 5.3 and appendix B; design/FINAL.md 5.5 as
design/ADJUDICATION.md EB1-EB3 and C-15 amend them), versioned by INVENTORY_VERSION: landmarks with their containment,
devices, procedure names, negators, quantifiers, the C1 markers, the visit labels, the reach guard's instrument words,
the words a person name is not, and the reference and function words the identity rules read (contract 6.2).

Every entry is matched in ``fold``ed text - Unicode NFKC, case folded, hyphens and dashes as spaces, curly quotes
straight, whitespace collapsed - and word-bounded: an entry never matches inside a longer word ("not" is not read in
"another", "colon" not in "colonoscopy"). A landmark is read as the longest name that covers its words, so "hepatic
flexure" names the flexure and never the liver as well.

What a list is for (EB1): a check reads ONLY the cited words of the attribute it verifies, and these lists confirm the
literal content of those words - a landmark, a device, a procedure's name, a negator, a quantifier, a duration's unit,
a visit label, (EB3) a C1 marker on a value that could decide an exclusion, and (DECISIONS D35) a marker of another
occasion in the words of a time stated current, which leaves that time unverified. No list reads a passage, a heading or
the document, no list produces a value, and a word missing from a list leaves its attribute unverified: a focused
question, never an exclusion and never READY - except D35's, the one list a word must be ABSENT from: a marker of
another occasion it holds leaves the current time unverified, whatever else the words say. Words given for a current
time must also be made only of whole present-encounter frames (DECISIONS D54, CURRENT_FRAMES) or carry a date at day
precision; a frame missing there leaves the time unverified. A list is widened only under a new INVENTORY_VERSION, by
re-normalizing the stored answers with no new request (contract 1).

Pure: imports nothing from studio.gi (FINAL 3.1). PROCEDURAL_FAMILIES and FAMILY_OF are this module's own copies of
the families gi.profiles marks procedural and of the family slugs, pinned equal to gi.profiles by a test.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from types import MappingProxyType
from typing import Iterable

from studio.interpretation import schema

# --- folding -----------------------------------------------------------------------------------------------------------

DASHES = frozenset('-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d')
SOFT_HYPHEN = '\u00ad'  # invisible: removed, never a space
SINGLE_QUOTES = frozenset('\u2018\u2019\u201a\u201b\u2032')
DOUBLE_QUOTES = frozenset('\u201c\u201d\u201e\u201f\u2033')


def fold_char(char: str) -> str:
    """One character as the normalized tier reads it (FINAL C2): NFKC, case folded, a hyphen or dash as a space, a curly
    quote straight, whitespace as a space. It may give no character (a soft hyphen) or several (NFKC's "fi")."""
    out = []
    for piece in unicodedata.normalize('NFKC', char).casefold():
        if piece == SOFT_HYPHEN:
            continue
        if piece in DASHES or piece.isspace():
            out.append(' ')
        elif piece in SINGLE_QUOTES:
            out.append("'")
        elif piece in DOUBLE_QUOTES:
            out.append('"')
        else:
            out.append(piece)
    return ''.join(out)


def fold(text: str) -> str:
    """``text`` as every list here is read: each character folded (fold_char), whitespace runs collapsed, stripped."""
    return ' '.join(''.join(fold_char(char) for char in text).split())


def _alternation(phrases: Iterable[str]) -> str:
    """The folded phrases as one alternation, longest first (so the longest phrase at a place wins)."""
    folded = sorted({fold(phrase) for phrase in phrases if fold(phrase)}, key=lambda value: (-len(value), value))
    return '|'.join(re.escape(value) for value in folded)


@lru_cache(maxsize=None)
def _compiled(phrases: tuple) -> re.Pattern:
    return re.compile(r'(?<!\w)(?:' + _alternation(phrases) + r')(?!\w)')


def found(text: str, phrases: Iterable[str]) -> tuple[str, ...]:
    """The entries of ``phrases`` that ``text`` holds, folded, word-bounded and non-overlapping (the longest at each
    place), in the order they first occur, each once. ``text`` is folded here."""
    pattern = _compiled(tuple(sorted(set(phrases))))
    seen = []
    for match in pattern.finditer(fold(text)):
        if match.group(0) not in seen:
            seen.append(match.group(0))
    return tuple(seen)


def holds(text: str, phrases: Iterable[str]) -> bool:
    return bool(found(text, phrases))


# --- the procedure families (gi.profiles' slugs; contract 3.1 and 9.1) ------------------------------------------------

# PROCEDURES value -> family slug ('' for unknown). other_gi is gi.other and not_gi is gi.unsupported.
FAMILY_OF = MappingProxyType({
    **{value: f'gi.{value}' for value in schema.PROCEDURES if value not in ('other_gi', 'not_gi', 'unknown')},
    'other_gi': 'gi.other', 'not_gi': 'gi.unsupported', 'unknown': '',
})
# The families gi.profiles marks procedure=True (an endoscopic or procedural family, as against E/M): the frame of the
# procedure default (contract 5.3) and of derived.procedure_day (8.3).
PROCEDURAL_FAMILIES = frozenset({'gi.egd', 'gi.enteroscopy', 'gi.colonoscopy', 'gi.flex_sig', 'gi.eus', 'gi.ercp',
                                 'gi.capsule', 'gi.motility', 'gi.reflux', 'gi.anorectal', 'gi.feeding_tube'})
# gi.profiles.FAMILY_ORDER, the order every family list here is written in.
FAMILY_ORDER = ('gi.office_em', 'gi.egd', 'gi.enteroscopy', 'gi.eus', 'gi.ercp', 'gi.colonoscopy', 'gi.flex_sig',
                'gi.capsule', 'gi.motility', 'gi.reflux', 'gi.anorectal', 'gi.feeding_tube', 'gi.sedation',
                'gi.em_other', 'gi.other', 'gi.unsupported')
EM_PROCEDURES = frozenset({'office_em', 'em_other'})  # an E/M visit event takes its family from its kind (5.3)
EM_KINDS = frozenset({'em_visit', 'em_prolonged'})


def family_of(procedure: str) -> str:
    """The family slug of a PROCEDURES value, '' for unknown or anything else."""
    return FAMILY_OF.get(procedure, '')


# --- landmarks (contract appendix B; services.ANATOMY's names, ported; ADJUDICATION C-15) -------------------------------

LANDMARK_FORMS = MappingProxyType({
    'esophagus': ('esophagus', 'esophageal', 'oesophagus', 'oesophageal'),
    'proximal_esophagus': ('proximal esophagus', 'upper esophagus', 'proximal third of the esophagus',
                           'upper third of the esophagus', 'proximal esophageal', 'upper esophageal',
                           'proximal oesophagus', 'upper oesophagus'),
    'mid_esophagus': ('mid esophagus', 'middle esophagus', 'middle third of the esophagus', 'mid third of the esophagus',
                      'mid esophageal', 'midesophagus', 'midesophageal', 'mid oesophagus'),
    'distal_esophagus': ('distal esophagus', 'lower esophagus', 'distal third of the esophagus',
                         'lower third of the esophagus', 'distal esophageal', 'lower esophageal', 'distal oesophagus',
                         'lower oesophagus'),
    'gastroesophageal_junction': ('gastroesophageal junction', 'gastro esophageal junction',
                                  'gastro oesophageal junction', 'gastrooesophageal junction', 'ge junction', 'gej',
                                  'egj', 'esophagogastric junction', 'z line', 'squamocolumnar junction'),
    'stomach': ('stomach', 'gastric'),
    'gastric_cardia': ('cardia', 'gastric cardia'),
    'gastric_fundus': ('fundus', 'gastric fundus', 'fundic'),
    'gastric_body': ('gastric body', 'body of the stomach', 'corpus', 'gastric corpus'),
    'gastric_antrum': ('antrum', 'antral', 'gastric antrum'),
    'pylorus': ('pylorus', 'pyloric', 'pyloric channel'),
    'duodenum': ('duodenum', 'duodenal'),
    'duodenal_bulb': ('duodenal bulb', 'bulb of the duodenum', 'bulb', 'bulbar duodenum'),
    'second_portion_duodenum': ('second portion of the duodenum', 'second part of the duodenum', 'second portion',
                                '2nd portion of the duodenum', '2nd part of the duodenum',
                                'third portion of the duodenum', 'third part of the duodenum',
                                '3rd portion of the duodenum', 'd2', 'post bulbar duodenum', 'postbulbar duodenum',
                                'descending duodenum'),
    'ampulla': ('ampulla', 'ampullary', 'papilla', 'major papilla', 'ampulla of vater', 'papilla of vater',
                'major duodenal papilla'),
    'jejunum': ('jejunum', 'jejunal'),
    'ileum': ('ileum', 'ileal'),
    'terminal_ileum': ('terminal ileum', 'terminal ileal', 'ti'),
    'neo_terminal_ileum': ('neo terminal ileum', 'neoterminal ileum', 'neo ti', 'neo terminal ileal'),
    'small_bowel': ('small bowel', 'small intestine', 'small intestinal'),
    'colon': ('colon', 'colonic', 'large bowel', 'large intestine'),
    'right_colon': ('right colon', 'right sided colon', 'right side of the colon', 'right hemicolon'),
    'left_colon': ('left colon', 'left sided colon', 'left side of the colon', 'left hemicolon'),
    'proximal_colon': ('proximal colon',),
    'distal_colon': ('distal colon',),
    'cecum': ('cecum', 'caecum', 'cecal', 'caecal'),
    'appendiceal_orifice': ('appendiceal orifice', 'appendiceal opening', 'appendix orifice', 'appendiceal os',
                            'orifice of the appendix'),
    'ileocecal_valve': ('ileocecal valve', 'ileocaecal valve', 'ic valve', 'icv'),
    'ascending_colon': ('ascending colon',),
    'hepatic_flexure': ('hepatic flexure',),
    'transverse_colon': ('transverse colon',),
    'splenic_flexure': ('splenic flexure',),
    'descending_colon': ('descending colon',),
    'sigmoid_colon': ('sigmoid colon', 'sigmoid'),
    'rectosigmoid': ('rectosigmoid', 'recto sigmoid', 'rectosigmoid junction', 'rectosigmoid colon'),
    'rectum': ('rectum', 'rectal'),
    'anal_canal': ('anal canal', 'anus', 'anal verge', 'perianal', 'anal'),
    'anastomosis': ('anastomosis', 'anastomoses', 'anastomotic'),
    'stoma': ('stoma', 'stomal', 'ostomy', 'colostomy', 'ileostomy'),
    'pouch': ('pouch', 'pouches', 'j pouch', 'ileal pouch'),
    'common_bile_duct': ('common bile duct', 'cbd', 'common duct', 'choledochus'),
    'bile_duct': ('bile duct', 'bile ducts', 'biliary', 'biliary tree', 'biliary duct', 'hepatic duct',
                  'common hepatic duct', 'cystic duct', 'intrahepatic ducts', 'choledochal'),
    'pancreatic_duct': ('pancreatic duct', 'main pancreatic duct', 'duct of wirsung'),
    'pancreas': ('pancreas', 'pancreatic', 'pancreatic head', 'head of the pancreas', 'uncinate', 'uncinate process',
                 'pancreatic body', 'body of the pancreas', 'pancreatic tail', 'tail of the pancreas',
                 'pancreatic neck', 'neck of the pancreas'),
    'gallbladder': ('gallbladder', 'gall bladder'),
    'liver': ('liver', 'hepatic'),
    'lymph_node': ('lymph node', 'lymph nodes', 'node', 'nodes', 'nodal', 'lymphadenopathy'),
})
# Landmarks with no surface form: their placement is not established by any word (``other``), or they are not a value.
UNPLACED_LANDMARKS = frozenset({'not_stated', 'other'})
# Surgically made places whose position in the tract this vocabulary cannot tell (an anastomosis may be in any segment):
# never disjoint from anything, so a difference of site is never manufactured from them (contract 6.3).
ALTERED_LANDMARKS = frozenset({'anastomosis', 'stoma', 'pouch'})
# DECISIONS D34: an anastomosis's TYPE, named by a literal place word directly before its noun ("ileocolonic
# anastomosis", "colorectal anastomotic stricture"), and the place that type gives it - the side of the tract it joins:
# an ileocolonic or ileocolic one the right colon side; a colorectal, coloanal or ileorectal one the rectum; a
# gastrojejunal one the stomach side (D29's gastric class); an esophagojejunal or esophagogastric one the esophagus side.
# A closed list: any other type ("colocolonic", "ileoanal", a gastroduodenal or Roux limb) names no place, and a type
# word that does not qualify the noun ("for colorectal cancer") names none either. Read only in an anatomy entry's own
# words (mapping.anastomosis_place); a word missing here keeps the anastomosis unplaced, as before.
ANASTOMOSIS_TYPES = MappingProxyType({
    'right_colon': ('ileocolonic', 'ileocolic', 'ileo colonic', 'ileo colic'),
    'rectum': ('colorectal', 'coloanal', 'ileorectal', 'colo rectal', 'colo anal', 'ileo rectal'),
    'stomach': ('gastrojejunal', 'gastro jejunal'),
    'esophagus': ('esophagojejunal', 'esophagogastric', 'oesophagojejunal', 'oesophagogastric', 'esophago jejunal',
                  'esophago gastric', 'oesophago jejunal', 'oesophago gastric'),
})

# What each landmark contains (contract appendix B; C-15's colon regions). Generous on purpose: a containment missing
# here would make two places "disjoint" and so manufacture a difference (6.3), and would fail a correct landmark.
_CONTAINS = {
    'esophagus': ('proximal_esophagus', 'mid_esophagus', 'distal_esophagus', 'gastroesophageal_junction'),
    'distal_esophagus': ('gastroesophageal_junction',),
    'stomach': ('gastric_cardia', 'gastric_fundus', 'gastric_body', 'gastric_antrum', 'pylorus',
                'gastroesophageal_junction'),
    'small_bowel': ('duodenum', 'jejunum', 'ileum'),
    'duodenum': ('duodenal_bulb', 'second_portion_duodenum', 'ampulla'),
    'second_portion_duodenum': ('ampulla',),
    'ileum': ('terminal_ileum', 'neo_terminal_ileum'),
    'colon': ('right_colon', 'left_colon', 'proximal_colon', 'distal_colon', 'cecum', 'appendiceal_orifice',
              'ileocecal_valve', 'ascending_colon', 'hepatic_flexure', 'transverse_colon', 'splenic_flexure',
              'descending_colon', 'sigmoid_colon', 'rectosigmoid'),
    'right_colon': ('cecum', 'appendiceal_orifice', 'ileocecal_valve', 'ascending_colon', 'hepatic_flexure'),
    'left_colon': ('splenic_flexure', 'descending_colon', 'sigmoid_colon', 'rectosigmoid'),
    'proximal_colon': ('right_colon', 'cecum', 'appendiceal_orifice', 'ileocecal_valve', 'ascending_colon',
                       'hepatic_flexure', 'transverse_colon'),
    'distal_colon': ('left_colon', 'splenic_flexure', 'descending_colon', 'sigmoid_colon', 'rectosigmoid'),
    'cecum': ('appendiceal_orifice', 'ileocecal_valve'),
    'bile_duct': ('common_bile_duct',),
    'pancreas': ('pancreatic_duct',),
}


def _closure(table: dict) -> dict:
    closed = {}

    def inside(name: str, path: tuple) -> frozenset:
        if name in closed:
            return closed[name]
        if name in path:
            raise ValueError(f'The landmark containment has a cycle through {name}.')
        found_ = set()
        for child in table.get(name, ()):
            found_.add(child)
            found_ |= inside(child, path + (name,))
        closed[name] = frozenset(found_)
        return closed[name]

    for landmark in schema.LANDMARKS:
        inside(landmark, ())
    return closed


CONTAINS = MappingProxyType(_closure(_CONTAINS))  # every landmark -> every landmark it contains (transitively)
_LANDMARK_OF_FORM = {fold(form): landmark for landmark, forms in LANDMARK_FORMS.items() for form in forms}
_LANDMARK_PATTERN = re.compile(r'(?<!\w)(?:' + _alternation(_LANDMARK_OF_FORM) + r')(?!\w)')


def contains(outer: str, inner: str) -> bool:
    """Whether landmark ``outer`` contains landmark ``inner`` (strictly)."""
    return inner in CONTAINS.get(outer, frozenset())


def compatible(first: str, second: str) -> bool:
    """Whether two landmarks are one place or one contains the other."""
    return first == second or contains(first, second) or contains(second, first)


def disjoint(first: str, second: str) -> bool:
    """Whether two landmarks are established as different places (contract 6.3): both placed by this vocabulary,
    neither containing the other, and nothing contained by both. Never for an unplaced or altered landmark."""
    unknown = UNPLACED_LANDMARKS | ALTERED_LANDMARKS
    if first in unknown or second in unknown or compatible(first, second):
        return False
    return not (CONTAINS.get(first, frozenset()) & CONTAINS.get(second, frozenset()))


def landmarks_named(text: str) -> tuple[str, ...]:
    """The landmarks ``text`` names, each by its longest form at a place ("transverse colon" names only the transverse
    colon, never the colon as well), in the order they occur, each once."""
    named = []
    for match in _LANDMARK_PATTERN.finditer(fold(text)):
        landmark = _LANDMARK_OF_FORM[match.group(0)]
        if landmark not in named:
            named.append(landmark)
    return tuple(named)


# D34: every anastomosis type word, folded, and the place it gives; and each type word directly before an anastomosis
# noun (LANDMARK_FORMS['anastomosis']).
_ANASTOMOSIS_TYPE_WORDS = MappingProxyType({fold(form): place for place, forms in ANASTOMOSIS_TYPES.items()
                                            for form in forms})
_ANASTOMOSIS_TYPE_OF_FORM = MappingProxyType({f'{form} {fold(noun)}': place
                                              for form, place in _ANASTOMOSIS_TYPE_WORDS.items()
                                              for noun in LANDMARK_FORMS['anastomosis']})
# More than one anastomosis named in one record's words (D34: several anastomoses keep the ambiguity).
ANASTOMOSES = ('anastomoses',)


def anastomosis_places(text: str) -> tuple[str, ...]:
    """DECISIONS D34: the places of the anastomosis types ``text`` names - a type word of ANASTOMOSIS_TYPES directly
    before an anastomosis noun ("stapled ileocolonic anastomosis", "colorectal anastomotic stricture") - in the order
    they occur, each once. A type word that qualifies no anastomosis noun names nothing here."""
    return tuple(dict.fromkeys(_ANASTOMOSIS_TYPE_OF_FORM[form] for form in found(text, _ANASTOMOSIS_TYPE_OF_FORM)))


def anastomosis_type_places(text: str) -> tuple[str, ...]:
    """D34: the places of EVERY anastomosis type word ``text`` holds, wherever it stands ("for colorectal cancer"
    too), in the order they occur, each once: what a record's words could say against one type."""
    return tuple(dict.fromkeys(_ANASTOMOSIS_TYPE_WORDS[form] for form in found(text, _ANASTOMOSIS_TYPE_WORDS)))


# --- devices (contract 5.3, technique row; catalogue BALLOON / WIRE_BOUGIE and the unguided bougie) -------------------

SCOPE_NOUNS = ('colonoscope', 'endoscope', 'gastroscope', 'sigmoidoscope', 'enteroscope', 'duodenoscope',
               'echoendoscope', 'scope', 'instrument', 'colonoscopes', 'endoscopes', 'upper endoscope',
               'pediatric colonoscope', 'adult colonoscope', 'ultrathin endoscope')
# The examinations an endoscope is by definition: their names are the endoscope device's words too.
ENDOSCOPIC_EXAMINATIONS = ('colonoscopy', 'ileocolonoscopy', 'egd', 'esophagogastroduodenoscopy', 'upper endoscopy',
                           'upper gi endoscopy', 'endoscopy', 'gastroscopy', 'esophagoscopy', 'sigmoidoscopy',
                           'flexible sigmoidoscopy', 'enteroscopy', 'eus', 'endoscopic ultrasound', 'ercp',
                           'endoscopically', 'endoscopic')
SNARE = ('snare', 'snares', 'snared', 'snaring')
FORCEPS = ('forceps',)
BALLOON = ('balloon', 'balloons', 'cre', 'tts', 'through the scope', 'pneumatic', 'hydrostatic',
           'controlled radial expansion')
WIRE_GUIDED = ('savary', 'savary gilliard', 'american dilator', 'american dilators', 'wire guided', 'over the wire')
GUIDEWIRE = ('guidewire', 'guidewires', 'guide wire', 'guide wires', 'wire')
DILATOR = ('dilator', 'dilators', 'bougie', 'bougies')
UNGUIDED_BOUGIE = ('bougie', 'bougies', 'maloney', 'hurst')
DEVICE_WORDS = MappingProxyType({
    'endoscope': SCOPE_NOUNS + ENDOSCOPIC_EXAMINATIONS,
    'snare': SNARE,
    'forceps': FORCEPS + ('biopsy forceps', 'jumbo forceps'),
    'needle': ('needle', 'needles', 'gauge', 'fna', 'fnb', 'fine needle'),
    # an injected agent names the injection, as epinephrine does: a marking tattoo (India ink, carbon particles) and a
    # saline lift are placed only by submucosal injection (S16 census: "tattoo", "carbon-particle tattoo", "tattooed
    # with India ink", "tattooed", "lifted with saline", "saline lift")
    'injection': ('inject', 'injected', 'injecting', 'injection', 'injections', 'epinephrine', 'adrenaline', 'tattoo',
                  'tattooed', 'tattooing', 'india ink', 'carbon particle', 'saline lift', 'lifted with saline'),
    'balloon': BALLOON,
    'clip': ('clip', 'clips', 'clipped', 'clipping', 'hemoclip', 'hemoclips', 'endoclip', 'endoclips'),
    'band': ('band', 'bands', 'banded', 'banding'),
    'argon_plasma': ('argon plasma', 'argon', 'apc'),
    'radiofrequency': ('radiofrequency', 'radio frequency', 'rfa'),
    'cryotherapy': ('cryotherapy', 'cryo', 'cryoablation', 'cryospray', 'cryoballoon'),
    'thermal_probe': ('heater probe', 'bipolar', 'multipolar', 'bicap', 'gold probe', 'thermal probe',
                      'coagulation probe', 'thermal'),
    'electrocautery': ('electrocautery', 'cautery', 'cauterized', 'cauterised', 'cauterization', 'electrosurgical',
                       'electrocoagulation'),
    'stent': ('stent', 'stents'),
    'basket': ('basket', 'baskets'),
    'sphincterotome': ('sphincterotome', 'papillotome', 'needle knife'),
    'lithotripter': ('lithotripter', 'lithotripsy', 'electrohydraulic', 'ehl', 'laser'),
    'cholangioscope': ('cholangioscope', 'cholangioscopy', 'spyglass'),
    'capsule': ('capsule', 'pillcam'),
    'catheter': ('catheter', 'catheters'),
    'manual': ('digital', 'manual', 'manually', 'finger'),
})
COLD, HOT = ('cold',), ('hot',)
# Electrocautery delivered through the snare's tip, or named by its generator's mode (S16 census: "contact coagulation
# using the snare tip", "low-power snare-tip soft coagulation", "snare-tip soft coagulation", "coagulation using the
# snare tip", "blended current"). Coagulation alone is not enough: a heater probe coagulates too (thermal_probe).
SNARE_TIP = ('snare tip', 'tip of the snare')
# A snare named by its current is a hot snare (S16 census: "15 mm electrocautery snare", "electrosurgical snare", "EMR
# electrosurgical snare") - never in words that also say "cold" ("a cold snare, without electrocautery").
HOT_CURRENT = ('hot', 'electrocautery', 'electrosurgical')
COAGULATION = ('coagulation', 'coagulated', 'coagulate', 'coagulating')
CURRENT_MODES = ('soft coagulation', 'blended current', 'blend current')
EXTRACTION = ('extraction', 'sweep', 'sweeps', 'swept', 'occlusion', 'retrieval')
UNCHECKED_DEVICES = frozenset({'not_stated', 'other'})  # no surface form: not stated, or a device outside the list


def device_named(device: str, text: str) -> bool:
    """Whether ``text`` holds a surface form of the DEVICES class ``device`` (contract 5.3, technique row): balloon by
    any balloon word; wire_bougie by a wire-guided dilator's name, or a bougie or dilator with a guide wire; bougie by
    an unguided bougie's name, or a dilator with no balloon and no wire named; cold_snare by "cold" and a snare;
    extraction_balloon by a balloon and an extraction word. False for a device with no surface form."""
    if device == 'electrocautery' and (holds(text, CURRENT_MODES)
                                       or (holds(text, SNARE_TIP) and holds(text, COAGULATION))):
        return True
    if device == 'cold_snare':
        return holds(text, COLD) and holds(text, SNARE)
    if device == 'hot_snare':
        return holds(text, HOT_CURRENT) and holds(text, SNARE) and not holds(text, COLD)
    if device in ('cold_forceps', 'hot_forceps'):
        temperature = COLD if device == 'cold_forceps' else HOT
        return holds(text, temperature) and holds(text, FORCEPS + ('biopsy',))
    if device == 'wire_bougie':
        return holds(text, WIRE_GUIDED) or (holds(text, DILATOR) and holds(text, GUIDEWIRE))
    if device == 'bougie':
        return holds(text, UNGUIDED_BOUGIE) or (holds(text, ('dilator', 'dilators')) and not holds(text, BALLOON)
                                                 and not holds(text, GUIDEWIRE))
    if device == 'extraction_balloon':
        return holds(text, ('balloon', 'balloons')) and holds(text, EXTRACTION)
    words = DEVICE_WORDS.get(device)
    return bool(words) and holds(text, words)


# The reach guard (contract 5.3, reach row; applied to the reach's own words, EB1): a non-scope device named in the
# words of a reach, with no scope named there, means the point is a device's, not the endoscope's. The through-the-scope
# device names are removed first ("a TTS balloon" is passed through the scope).
NON_SCOPE_DEVICES = ('guidewire', 'guide wire', 'guidewires', 'wire', 'catheter', 'balloon', 'capsule', 'probe',
                     'dilator', 'bougie', 'stent', 'basket')
THROUGH_THE_SCOPE = ('through the scope', 'tts')
REACH_SCOPES = ('colonoscope', 'endoscope', 'gastroscope', 'sigmoidoscope', 'enteroscope', 'duodenoscope',
                'echoendoscope', 'scope', 'instrument')


def _without_through_the_scope(text: str) -> str:
    return _compiled(tuple(sorted(THROUGH_THE_SCOPE))).sub(' ', fold(text))


def device_reach(text: str) -> bool:
    """Whether the reach words ``text`` name a non-scope device and no scope, the through-the-scope names removed."""
    folded = _without_through_the_scope(text)
    return holds(folded, NON_SCOPE_DEVICES) and not holds(folded, REACH_SCOPES)


def scope_named(text: str) -> bool:
    """Whether ``text`` names a scope (the reach rule's "not_stated with a scope named", contract 5.4), the
    through-the-scope names removed first as the guard removes them: "through the scope" names a device's route, and
    never by itself the examination's instrument."""
    return holds(_without_through_the_scope(text), REACH_SCOPES)


# --- procedure names (contract 5.3, procedure row; services.SERVICES' names, ported) ----------------------------------

PROCEDURE_NAMES = MappingProxyType({
    'office_em': ('visit', 'office visit', 'clinic visit', 'consultation', 'consult', 'evaluation', 'follow up visit',
                  'new patient', 'established patient', 'e/m', 'evaluation and management'),
    'egd': ('egd', 'upper endoscopy', 'upper gi endoscopy', 'upper gastrointestinal endoscopy',
            'esophagogastroduodenoscopy', 'gastroscopy', 'gastroscope', 'upper endoscope', 'esophagoscopy',
            'esophagoscope', 'transnasal endoscopy', 'tne', 'poem', 'peroral endoscopic myotomy',
            'per oral endoscopic myotomy'),
    'enteroscopy': ('enteroscopy', 'enteroscope', 'push enteroscopy', 'balloon enteroscopy', 'deep enteroscopy',
                    'double balloon enteroscopy', 'single balloon enteroscopy', 'spiral enteroscopy'),
    'colonoscopy': ('colonoscopy', 'colonoscope', 'ileocolonoscopy', 'colonoscopic'),
    'flex_sig': ('sigmoidoscopy', 'flexible sigmoidoscopy', 'sigmoidoscope', 'flex sig'),
    'eus': ('eus', 'endoscopic ultrasound', 'endoscopic ultrasonography', 'endosonography', 'endosonographic',
            'echoendoscope', 'echoendoscopy'),
    'ercp': ('ercp', 'endoscopic retrograde cholangiopancreatography', 'duodenoscope'),
    'capsule': ('capsule endoscopy', 'video capsule', 'wireless capsule', 'capsule', 'pillcam'),
    'motility': ('manometry', 'motility', 'esophageal manometry', 'high resolution manometry', 'hrm'),
    'reflux': ('ph monitoring', 'ph study', 'ph impedance', 'impedance', 'bravo', 'reflux monitoring', 'ph'),
    'anorectal': ('anorectal manometry', 'anorectal', 'balloon expulsion', 'rectal sensation', 'arm'),
    'feeding_tube': ('gastrostomy', 'peg', 'feeding tube', 'g tube', 'jejunostomy', 'pej', 'gj tube'),
    'sedation': ('sedation', 'moderate sedation', 'conscious sedation'),
    'em_other': ('inpatient consultation', 'hospital visit', 'emergency department', 'consult', 'consultation',
                 'inpatient', 'hospital follow up'),
})


def procedure_named(procedure: str, text: str) -> bool:
    """Whether ``text`` holds a name of the PROCEDURES value ``procedure`` (other_gi, not_gi and unknown have none)."""
    names = PROCEDURE_NAMES.get(procedure)
    return bool(names) and holds(text, names)


# --- negation, quantifiers, the visit (contract 5.3) ------------------------------------------------------------------

NEGATORS = ('no', 'not', "n't", 'none', 'nothing', 'neither', 'nor', 'never', 'without')
NON_PERFORMANCE = ('declined', 'deferred', 'cancelled', 'canceled', 'omitted', 'withheld', 'refused', 'postponed',
                   'abandoned', 'aborted', 'skipped', 'left in situ', 'left in place', 'left untreated')
_NEGATOR = re.compile(r"(?<!\w)(?:" + _alternation(entry for entry in NEGATORS if entry != "n't")
                      + r")(?!\w)|(?<=\w)n't(?!\w)")
QUANTIFIERS = ('no', 'none', 'nothing', 'neither', 'nor', 'any', 'all', 'every', 'no other', 'no further',
               'no additional')
DURATION_UNITS = ('min', 'mins', 'minute', 'minutes', 'hour', 'hours', 'hr', 'hrs')
DECISION_LABELS = ('decision making', 'mdm')


def negation(text: str) -> tuple[str, ...]:
    """The negators and non-performance words ``text`` holds (contract 5.3, status not_performed row), in order."""
    folded = fold(text)
    seen = []
    for match in _NEGATOR.finditer(folded):
        if match.group(0) not in seen:
            seen.append(match.group(0))
    for entry in found(folded, NON_PERFORMANCE):
        if entry not in seen:
            seen.append(entry)
    return tuple(seen)


# --- the C1 markers (FINAL 5.5; EB3: read only in the words of a value that could decide an exclusion) ---------------

PLANNING_MARKERS = ('plan', 'plans', 'planned', 'planning', 'will', 'to be', 'scheduled', 'schedule', 'recommend',
                    'recommends', 'recommended', 'recommendation', 'repeat', 'return', 'follow up', 'follow-up',
                    'consider', 'consideration', 'refer', 'referral', 'pending', 'next', 'upcoming')
FAILURE_MARKERS = ('unable', 'could not', "couldn't", 'cannot', 'can not', 'failed', 'fail', 'failure', 'unsuccessful',
                   'not successful', 'aborted', 'abandoned', 'terminated', 'stopped', 'incomplete', 'not completed',
                   'not achieved', 'not possible', 'not able')
EARLIER_MARKERS = ('previous', 'previously', 'prior', 'earlier', 'ago', 'last', 'history', 'historical', 'past',
                   'formerly', 'before this', 'at that time', 'status post', 's/p', 'in the past', 'already')
FUTURE_MARKERS = ('will', 'to be', 'planned', 'plan', 'scheduled', 'next', 'upcoming', 'later', 'repeat', 'return',
                  'follow up', 'follow-up', 'future')  # 'future': S16 census ("A future intervention ... is planned")
FACILITY_MARKERS = ('hospital', 'facility', 'center', 'centre', 'clinic', 'institution', 'practice', 'outside',
                    'elsewhere', 'another', 'referring')
NUMBER_WORDS = ('one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
                'fifteen', 'eighteen', 'twenty', 'twenty four', 'thirty', 'sixty', 'ninety')
# The future marker "in N day(s), week(s), month(s), year(s)", N a numeral or a number word - or a range of two, "in 4 to
# 6 weeks", "in two or three months" (S16 census: "in 4 to 6 weeks").
_NUMBER = r'(?:\d+|' + _alternation(NUMBER_WORDS) + r')'
_IN_PERIOD = re.compile(r'(?<!\w)in ' + _NUMBER + r'(?: (?:to|or) ' + _NUMBER + r')? (?:day|week|month|year)s?(?!\w)')


def markers(kind: str, text: str) -> tuple[str, ...]:
    """The C1 markers of ``kind`` (planning, failure, earlier, future, facility) that ``text`` holds, in order."""
    lists = {'planning': PLANNING_MARKERS, 'failure': FAILURE_MARKERS, 'earlier': EARLIER_MARKERS,
             'future': FUTURE_MARKERS, 'facility': FACILITY_MARKERS}
    found_ = list(found(text, lists[kind]))
    if kind == 'future':
        found_ += [match.group(0) for match in _IN_PERIOD.finditer(fold(text)) if match.group(0) not in found_]
    return tuple(found_)


# DECISIONS D35: the words of a time Gemini calls current_encounter must not name another occasion - a C1 earlier or
# future marker, or "original" ("At the original procedure": the occasion a reproduced report narrates, FRESH-2
# aside-of-twins-023). Read only in that time's own words (verify.time_words), never in a passage. "original" is NOT an
# earlier marker: an earlier time its words alone carry still lacks one, so no exclusion changes (EB3).
OTHER_OCCASION = ('original',)


def other_occasion(text: str) -> tuple[str, ...]:
    """D35: the markers of another occasion ``text`` holds - the earlier markers, the future markers (with "in N
    weeks"), then OTHER_OCCASION - each once, in that order."""
    found_ = []
    for entry in markers('earlier', text) + markers('future', text) + found(text, OTHER_OCCASION):
        if entry not in found_:
            found_.append(entry)
    return tuple(found_)


# DECISIONS D42 (the S17 refutation of D35, finding 7) inverted D35's default for a current time's own words: SAFE only
# where they anchor the time to THIS encounter. DECISIONS D54 (the round-2 refutation of D42, findings 0, 7 and 8): D42
# read an anchor WORD anywhere in the words, so "These were the findings at her index colonoscopy", "At her index
# colonoscopy this spring", "At her first colonoscopy the same" and "At the index procedure, on withdrawal" verified an
# act of another occasion as current - "these", "this", "same" or a procedure's phase names no occasion by itself. D54
# reads the words WHOLE: they anchor the time only when they are made of whole present-encounter frames and nothing
# else (current_frame); a date literal at day precision is read by its own check (verify.time_words). Anything else - an
# anchor word inside other words, a period ("this spring", "this year"), a bare sequence word ("initially", "then"), a
# heading ("findings") - leaves the time unverified (current_unanchored): a time question, never an exclusion and never
# READY. A frame missing here asks; it never releases (an inclusion list that decides safety names what is safe).
# CURRENT_FRAMES is the census of every current time FRESH-1 and FRESH-2 recorded - the frozen answers, 1,099 + 1,079
# current times, 136 + 219 with words; their normalized inventories, 991 + 1,079 and 119 + 219 (FRESH-1's four refused
# answers have none); 18 + 20 distinct worded texts, 24 in all - each present-encounter wording exactly, then the
# obvious exact frames of the present encounter; never a wording that names another occasion, a period or a bare
# sequence word. The census's other wordings stay unanchored as under D42 ("Those were the findings at her index
# colonoscopy.", "Over the summer", "initially", "then", "FINDINGS"), carry a date at day precision, or are D35's. D35's
# markers stay, and stand alone where found.
CURRENT_FRAMES = (
    # the census (FRESH-1 and FRESH-2), folded
    'today', 'during the present encounter', 'during the single date of service stated at the top of this report',
    'occurred during the single date of service stated at the top of this report', 'this examination',
    'at this examination', 'this time', 'this time as well', 'on this occasion', 'same session', 'on withdrawal',
    # the obvious exact frames of the present encounter
    'this procedure', 'at this procedure', 'during this procedure', 'during this examination',
    'at the present encounter', 'on the date of service', 'this morning', 'this afternoon',
)
_CURRENT_FRAMES = frozenset(fold(frame) for frame in CURRENT_FRAMES)
_FRAME_EDGES = re.compile(r'^[\W_]+|[\W_]+$')  # leading and trailing punctuation and whitespace
_FRAME_JOINS = re.compile(r'[,;]| and ')  # a comma, a semicolon, a standalone "and" (folded text: single spaces)


def current_frame(text: str) -> bool:
    """D54: whether ``text`` is made only of whole present-encounter frames. Folded, its leading and trailing
    punctuation and whitespace stripped, split at commas, semicolons and a standalone " and ", each part stripped: True
    only when there is a part and EVERY non-empty part equals a CURRENT_FRAMES entry. "Today", "This time as well." and
    "Today, on withdrawal" are; "At the index procedure, on withdrawal", "these were the findings at her index
    colonoscopy", "this spring", "this" and "," are not."""
    parts = [part.strip() for part in _FRAME_JOINS.split(_FRAME_EDGES.sub('', fold(text)))]
    parts = [part for part in parts if part]
    return bool(parts) and all(part in _CURRENT_FRAMES for part in parts)


# DECISIONS D64 (D54's review): the words that may introduce a same-day date in a current time's words ("on November 8,
# 2026"), and nothing else - read by dated_frame only.
DATE_CONNECTORS = ('on', 'dated', 'of', 'as of', 'date', 'date of service', 'the date of service', 'service date')


def dated_frame(rest: str) -> bool:
    """D64: whether what is left of a current time's words once its day-precision date literals are cut out - ``rest``
    - names nothing but that date: split as current_frame splits, every part empty, a DATE_CONNECTORS entry or a whole
    CURRENT_FRAMES entry. "on November 8, 2026" and "today, 11/09/2026" are; "At her index colonoscopy on 11/09/2026"
    and "faxed to us on 11/09/2026" are not - a same-day date beside other words dates the act only where those words
    are this encounter's own."""
    parts = [part.strip() for part in _FRAME_JOINS.split(_FRAME_EDGES.sub('', fold(rest)))]
    return all(not part or part in DATE_CONNECTORS or part in _CURRENT_FRAMES for part in parts)


# DECISIONS D109 (the round-4 refutation, finding 14): the frames that place an act on the date of service itself - read
# by facts.day_of only, in a time's OWN words (EB1), and only as WHOLE frames, as D54 reads CURRENT_FRAMES: the words,
# folded, their edges stripped and split at commas, semicolons and a standalone "and", must be made of these and nothing
# else. "Earlier in the day", "Earlier that day" and "Earlier in the morning" are ON the date even where Gemini gives
# the time earlier_encounter (an act of its own encounter earlier on the same date, ADJUDICATION C-3); "earlier in the
# day, before her visit" is not made of frames and is read as before. facts.SAME_DAY_WORDS ("today", "this morning",
# ...) stays as it was, read anywhere in the words; these frames only ADD the same-date phrasings that carry none of
# those words. Never a bare "that day", "that morning" or "in the morning": they name no day by themselves.
SAME_DAY_FRAMES = (
    'today', 'earlier today', 'later today', 'tonight', 'this morning', 'this afternoon', 'this evening',
    'earlier this morning', 'earlier this afternoon', 'earlier this evening', 'later this morning',
    'later this afternoon', 'later this evening',
    'earlier in the day', 'later in the day', 'earlier that day', 'later that day', 'earlier that same day',
    'later that same day', 'earlier the same day', 'later the same day', 'earlier on the same day',
    'later on the same day', 'earlier in the morning', 'later in the morning', 'earlier in the afternoon',
    'later in the afternoon', 'earlier in the evening', 'later in the evening', 'earlier that morning',
    'earlier that afternoon', 'later that morning', 'later that afternoon', 'later that evening',
    'same day', 'the same day', 'on the same day', 'that same day', 'same date', 'the same date', 'on the same date',
    'on the date of service', 'on the same date of service',
)


# --- the words a person name is not (contract 5.3: names tokenized without titles, credentials and role words) --------

TITLES = ('dr', 'doctor', 'prof', 'professor', 'mr', 'mrs', 'ms', 'miss', 'mx')
CREDENTIALS = ('md', 'do', 'mbbs', 'mbchb', 'phd', 'np', 'pa', 'pa c', 'rn', 'bsn', 'msn', 'crna', 'facg', 'facp',
               'fasge', 'agaf', 'frcp', 'frcpc', 'mph', 'dnp', 'aprn', 'cnp', 'fnp', 'lpn', 'dds', 'mrcp', 'facs',
               'faasld', 'mbbch', 'fellow')
ROLE_WORDS = ('endoscopist', 'endoscopists', 'gastroenterologist', 'gastroenterologists', 'gastroenterology',
              'hepatologist', 'hepatology', 'gi', 'attending', 'fellow', 'fellows', 'resident', 'residents',
              'physician', 'physicians', 'surgeon', 'surgeons', 'surgery', 'surgical', 'nurse', 'nurses', 'nursing',
              'anesthesiologist', 'anesthetist', 'anesthesia', 'anaesthesia', 'anaesthetist', 'assistant',
              'assistants', 'trainee', 'trainees', 'technician', 'tech', 'staff', 'team', 'provider', 'providers',
              'clinician', 'clinicians', 'consultant', 'radiologist', 'pathologist', 'oncologist', 'hospitalist',
              'intern', 'student', 'practitioner', 'primary', 'care', 'pcp', 'performing', 'performed', 'operator',
              'proceduralist', 'author', 'signed', 'electronically', 'attestation', 'supervising', 'supervision',
              'supervised', 'department', 'service', 'unit', 'division', 'endoscopy', 'medical', 'health',
              'university', 'mac', 'egd', 'eus', 'ercp', 'emr', 'esd', 'apc', 'procedure', 'report', 'note',
              'scrub', 'circulating', 'referring', 'outside', 'consulting', 'covering', 'on call')
FUNCTION_WORDS = ('the', 'a', 'an', 'and', 'or', 'with', 'by', 'of', 'at', 'in', 'on', 'for', 'from', 'to', 'under',
                  'as', 'per', 'via', 'our', 'his', 'her', 'their', 'its', 'this', 'that', 'these', 'those', 'i', 'we',
                  'me', 'us', 'myself', 'same', 'other', 'another', 'who', 'was', 'were', 'is', 'are', 'be', 'been',
                  'also', 'then', 'plus', 'both', 'all')
NOT_NAMES = frozenset(fold(word) for word in TITLES + CREDENTIALS + ROLE_WORDS + FUNCTION_WORDS + FACILITY_MARKERS)

# --- the identity rules' words (contract 6.2; read by identity.py) ----------------------------------------------------

REFERENCE_WORDS = ('it', 'its', 'this', 'these', 'that', 'those', 'them', 'lesion', 'lesions', 'polyp', 'polyps',
                   'mass', 'area', 'the lesion', 'the lesions', 'the polyp', 'the polyps', 'the mass', 'the area')
# Removed before two descriptions are compared for a shared content word (6.2, lexical tie).
TIE_FUNCTION_WORDS = frozenset({'the', 'and', 'with', 'from', 'was', 'were', 'are', 'for', 'this', 'that', 'these',
                                'those', 'which', 'into', 'onto', 'its', 'their', 'there', 'then', 'than', 'also',
                                'been', 'being', 'has', 'had', 'have', 'not', 'any', 'all', 'one', 'two', 'three',
                                'four', 'five', 'six', 'about', 'approximately', 'measuring', 'measured', 'noted',
                                'seen', 'found', 'identified', 'located', 'appeared', 'small', 'large', 'site'})
