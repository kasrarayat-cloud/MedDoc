"""Documented services: a source-based inventory of what the document says was done (ARCHITECTURE 5.9).

The inventory is built from the revision's own text, independently of any provider's proposed code list, so that
proposals can be checked against it and a documented service with no proposal becomes visible. For each service it
keeps the documented family and kind, its status (performed, incomplete, planned, historical, cancelled, negated or
uncertain), its completion and extent, the date, clinician and setting the document gives, its lesions (anatomy, size,
morphology, specimen label, what was done to each) and its acts (biopsy, snare removal, dilation, ...), each with exact
supporting passages, the clause-level reading that decided it, and who documented it (the performing physician, a
nurse, anesthesia, pathology). Statements that disagree about the same act of the same service at the same time are
kept as a conflict with both sides, never resolved silently. Services the document attributes to another provider
(anesthesia, pathology, the facility) are recorded as such, so they are never taken for the endoscopist's.

Reading rules (each decided within the clause and the service it belongs to):
- Negation has a scope: a clause that opens with "No"/"Neither"/"Without" negates every act it lists up to its
  predicate ("No EUS, fine-needle sampling, ERCP ... was performed"); "X was not <done>" negates that act for X and
  the acts it lists after "with" ("It was not treated with a snare, cautery, ablation or mucosal resection"); a
  negated negative is positive ("was complete and was not discontinued"). "No other/further/additional X" denies
  only acts beyond the ones documented, never the documented ones.
- Time belongs to the clause: a date or year in the clause, a history or a plan word in it, or a history or plan
  section outside today's report, makes the act historical or planned. An unrelated historical reference elsewhere
  never changes a current act.
- An unresected lesion does not make a completed examination incomplete: completion is read only from statements
  about the examination's extent and completion.

The reader is bounded (caps below; a cap reached is a recorded problem and holds, never a silent truncation) and its
output is validated (``validate``): every passage must equal the text at its offsets and every value must be in its
vocabulary, and a problem is reported, never discarded. Like routing (5.3) it is advisory: it reads declared wording
and cannot be complete for open prose, so nothing it decides is final without a reviewer.
"""
from __future__ import annotations

import bisect
import contextvars
import dataclasses
import functools
import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Optional, Sequence

from studio.gi import context as gi_context
from studio.gi import cues as _cues
from studio.gi import sections as _sections
from studio.ingest import symbols as _box_symbols
from studio.types import Span

INVENTORY_VERSION = 'gi-services@1'

FLAGS = re.A | re.I

# Bounds (reading stops and says so; nothing is silently truncated).
MAX_SENTENCES = 6000
MAX_ACTS = 2000
MAX_LESIONS_PER_SERVICE = 60
MAX_SERVICES = 40
SENTENCE_READ_CHARS = 1200  # a longer sentence is read in its first part for acts, and the rest is a problem
CLAUSE_REACH = 400  # how far around a mention its clause is read (bounds the work per mention)
ROW_REACH = 300  # how far around a mention its check-box row is read

SERVICE_STATUSES = ('performed', 'incomplete', 'planned', 'historical', 'cancelled', 'negated', 'uncertain')
ACT_STATUSES = ('performed', 'negated', 'planned', 'historical', 'cancelled', 'uncertain')
COMPLETIONS = ('complete', 'incomplete', 'unknown')
ROLES = ('physician', 'nursing', 'anesthesia', 'pathology', 'radiology', 'facility', 'unknown')
POSITIVE = ('performed', 'incomplete')


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, FLAGS)


# --- vocabulary: anatomy ----------------------------------------------------------------------------------------
# (canonical name, region, pattern). Ordered: a more specific name first; matches never overlap (first wins).
ANATOMY: tuple[tuple[str, str, re.Pattern], ...] = tuple((name, region, _rx(pattern)) for name, region, pattern in (
    ('distal esophagus', 'esophagus', r'\b(?:distal|lower)(?:\s+third\s+of\s+the)?\s+esophag(?:us|eal)\b'),
    ('proximal esophagus', 'esophagus', r'\b(?:proximal|upper)(?:\s+third\s+of\s+the)?\s+esophag(?:us|eal)\b'),
    ('mid esophagus', 'esophagus', r'\bmid(?:dle)?(?:\s+third\s+of\s+the)?[\s-]+esophag(?:us|eal)\b'),
    ('gastroesophageal junction', 'esophagus', r'\b(?:gastro-?\s?(?:o)?esophageal\s+junction|GEJ|EGJ|Z[- ]line)\b'),
    ('esophagus', 'esophagus', r'\b(?:o)?esophag(?:us|eal)\b'),
    ('gastric antrum and body', 'stomach', r'\b(?:gastric\s+)?antrum\s+and\s+(?:the\s+)?body\b'),
    ('gastric antrum', 'stomach', r'\b(?:gastric\s+)?antr(?:um|al)\b'),
    ('gastric body', 'stomach', r'\bgastric\s+body\b|\bbody\s+of\s+the\s+stomach\b|(?<=antrum\sand\s)body\b'),
    ('gastric fundus', 'stomach', r'\b(?:gastric\s+)?fund(?:us|ic)\b'),
    ('gastric cardia', 'stomach', r'\b(?:gastric\s+)?cardia\b'),
    ('pylorus', 'stomach', r'\bpylor(?:us|ic)\b'),
    ('stomach', 'stomach', r'\bstomach\b|\bgastric\b'),
    ('duodenal bulb', 'duodenum', r'\bduodenal\s+bulb\b|\bbulb\s+of\s+the\s+duodenum\b'),
    ('second portion of the duodenum', 'duodenum',
     r'\b(?:second|2nd|third|3rd)\s+(?:portion|part)\s+of\s+the\s+duodenum\b|\bD2\b|\bpost-?bulbar\s+duodenum\b'),
    ('duodenum', 'duodenum', r'\bduoden(?:um|al)\b'),
    ('ampulla', 'biliary', r'\b(?:major\s+)?(?:ampulla|papilla)\b'),
    ('jejunum', 'small_bowel', r'\bjejun(?:um|al)\b'),
    ('terminal ileum', 'small_bowel', r'\bterminal\s+ileum\b|\bneo-?terminal\s+ileum\b'),
    ('ileum', 'small_bowel', r'\bile(?:um|al)\b'),
    ('small bowel', 'small_bowel', r'\bsmall\s+(?:bowel|intestine)\b'),
    ('cecum', 'colon', r'\bc(?:a)?ec(?:um|al)\b'),
    ('appendiceal orifice', 'colon', r'\bappendiceal\s+orifice\b'),
    ('ileocecal valve', 'colon', r'\bileo-?c(?:a)?ecal\s+valve\b'),
    ('ascending colon', 'colon', r'\bascending\s+colon\b|\bright\s+colon\b'),
    ('hepatic flexure', 'colon', r'\bhepatic\s+flexure\b'),
    ('transverse colon', 'colon', r'\btransverse\s+colon\b'),
    ('splenic flexure', 'colon', r'\bsplenic\s+flexure\b'),
    ('descending colon', 'colon', r'\bdescending\s+colon\b|\bleft\s+colon\b'),
    ('sigmoid colon', 'colon', r'\bsigmoid(?:\s+colon)?\b(?!\s*oscop)'),
    ('rectosigmoid', 'colon', r'\brecto-?sigmoid\b'),
    ('colon', 'colon', r'\bcolon(?:ic)?\b(?!\s*oscop)|\blarge\s+(?:bowel|intestine)\b'),
    ('rectum', 'rectum', r'\brect(?:um|al)\b'),
    ('anal canal', 'anus', r'\banal\s+canal\b|\banus\b|\banal\s+verge\b|\bperianal\b'),
    ('pancreatic head', 'pancreas', r'\b(?:pancreatic\s+head|head\s+of\s+the\s+pancreas|uncinate(?:\s+process)?)\b'),
    ('pancreatic body', 'pancreas', r'\bpancreatic\s+body\b|\bbody\s+of\s+the\s+pancreas\b'),
    ('pancreatic tail', 'pancreas', r'\bpancreatic\s+tail\b|\btail\s+of\s+the\s+pancreas\b'),
    ('pancreatic duct', 'pancreas', r'\bpancreatic\s+duct\b|\bmain\s+duct\b'),
    ('pancreas', 'pancreas', r'\bpancrea(?:s|tic)\b'),
    ('common bile duct', 'biliary', r'\bcommon\s+bile\s+duct\b|\bCBD\b'),
    ('bile duct', 'biliary', r'\b(?:bile|biliary|hepatic|cystic)\s+ducts?\b|\bbiliary\s+tree\b|\bcholedoch\w*\b'),
    ('gallbladder', 'biliary', r'\bgall\s?bladder\b'),
    ('lymph node', 'node', r'\blymph\s+nodes?\b|\b(?:peri\w+\s+)?nodes?\b(?=[^.]{0,20}\b(?:sampl|biops|aspirat|FN))'),
    ('liver', 'liver', r'\bliver\b|\bhepatic\b(?!\s+(?:flexure|duct))'),
))

UPPER = frozenset(('esophagus', 'stomach', 'duodenum'))
LOWER = frozenset(('colon', 'rectum', 'anus'))
# The anatomy vocabulary by canonical name -> region, and the regions of the GI lumen, where an endoscope's forceps act:
# what an examination's sites are read with (examined_regions) - by a READ_UNDER rule (validation.reconcile) and by the
# inclusion of an upper endoscopy in an endoscopic ultrasound (_included).
REGION_OF = {name: region for name, region, _ in ANATOMY}
LUMEN = UPPER | LOWER | {'small_bowel'}
# What a site may cover, read only to tell whether a denial scoped to sites and a statement of the act are about one
# place (_same_subject; refutation gi2 status-2: the round's scoped denial read the regions as a partition, so "No small
# bowel biopsies were taken" no longer paired with the duodenal biopsies a site-less summary may be about): its own
# region, and the places inside it that this vocabulary keeps in regions of their own. The small bowel holds the
# duodenum, and the duodenum (its second part) the papilla in its wall, which the ampulla's 'biliary' region does not
# say; the large bowel - which the canonical name 'colon' also reads ("large bowel", "large intestine") - holds the
# colon and the rectum. Two sites are different places only when what they cover is disjoint: a denial whose site holds
# the act's site, or lies inside it, is about it. A name's own region stays its region everywhere else (REGION_OF).
SITE_COVERS = {
    'small bowel': frozenset(('small_bowel', 'duodenum', 'papilla')),
    'duodenum': frozenset(('duodenum', 'papilla')),
    'second portion of the duodenum': frozenset(('duodenum', 'papilla')),
    'ampulla': frozenset(('biliary', 'papilla')),
}
LARGE_BOWEL = _rx(r'large\s+(?:bowel|intestine)')  # the 'colon' name written as the large bowel
LARGE_BOWEL_COVERS = frozenset(('colon', 'rectum'))


def site_covers(name: str, written: str = '') -> frozenset:
    """What the site ``name`` (an ANATOMY canonical name), as ``written`` in the document, may cover (SITE_COVERS)."""
    if name == 'colon' and LARGE_BOWEL.fullmatch(written):
        return LARGE_BOWEL_COVERS
    covers = SITE_COVERS.get(name)
    if covers is not None:
        return covers
    region = REGION_OF.get(name, '')
    return frozenset((region,)) if region else frozenset()


# The regions each endoscopic family's examination reaches, as the reader gives an act to a family by its site
# (_family_for_act_in): the upper tract for an upper endoscopy, the lower tract for a colonoscopy (and the small bowel
# beyond its valve) or a sigmoidoscopy, the small bowel for an enteroscopy. Read where an act names no site of its own
# (validation.reconcile.elsewhere); a family not listed reaches no region established here.
FAMILY_REGIONS = {'gi.egd': UPPER, 'gi.colonoscopy': LOWER | {'small_bowel'}, 'gi.flex_sig': LOWER,
                  'gi.enteroscopy': frozenset(('small_bowel',))}

# --- vocabulary: services --------------------------------------------------------------------------------------
# (family, kind, pattern). A family is an internal profile (studio.gi.profiles); kind is the documented service.
SERVICES: tuple[tuple[str, str, re.Pattern], ...] = tuple((family, kind, _rx(pattern)) for family, kind, pattern in (
    ('gi.eus', 'eus', r'\bEUS\b|\bendoscopic\s+ultra(?:sound|sonography|sonographic)\b|\bendosonograph(?:y|ic)\b'
                      r'|\bechoendoscop(?:y|ic)\b|\bendosonographic\s+examination\b'),
    ('gi.ercp', 'ercp', r'\bERCP\b|\bendoscopic\s+retrograde\s+cholangio-?pancreatograph(?:y|ies)\b'),
    ('gi.capsule', 'capsule', r'\b(?:video\s+|wireless\s+)?capsule\s+endoscop(?:y|ies)\b|\bPillCam\b'
                              r'|\b(?:small[- ]bowel|colon|esophageal)\s+capsule\s+(?:study|endoscopy)\b'),
    ('gi.reflux', 'ph_study', r'\b(?:ambulatory\s+)?(?:esophageal\s+)?pH(?:[- ]impedance)?\s+(?:monitoring|study|testing|'
                              r'test|recording)\b|\bimpedance[- ]pH\b|\bBravo\b|\bwireless\s+pH\b'
                              r'|\breflux\s+monitoring\b|\b(?:24|48|96)[- ]hour\s+(?:esophageal\s+)?pH\b'),
    ('gi.anorectal', 'anorectal_testing', r'\banorectal\s+manometry\b|\bARM\b|\bballoon\s+expulsion\s+test\b'
                                          r'|\brectal\s+(?:sensation|compliance)\s+(?:test|testing|study)\b'
                                          r'|\banorectal\s+(?:physiology|function)\s+(?:test|testing|study)\b'),
    ('gi.motility', 'manometry', r'\b(?:high[- ]resolution\s+)?esophageal\s+(?:manometry|motility\s+(?:study|testing))\b'
                                 r'|\bHRM\b|\bantroduodenal\s+manometry\b|\b(?:gastric|duodenal|colonic|colon)\s+'
                                 r'(?:manometry|motility\s+(?:study|testing))\b'),
    # A feeding-tube service of its own: a tube changed, replaced or repositioned, or placed with imaging. A PEG placed
    # during an upper endoscopy is that endoscopy's act (its own EGD code), never a second service.
    ('gi.feeding_tube', 'feeding_tube', r'\b(?:gastrostomy|jejunostomy|gastrojejunostomy|G-?J?|J|PEG)(?:[- ]tube)?\s+'
                                        r'(?:tube\s+|button\s+)?(?:replacement|change|exchange|reinsertion|repositioning)\b'
                                        r'|\breplacement\s+of\s+(?:the\s+|a\s+)?(?:gastrostomy|jejunostomy|G-?tube|J-?tube|'
                                        r'PEG)\b|\b(?:percutaneous\s+)?(?:radiologic(?:al)?|image-guided|fluoroscopic(?:ally)?'
                                        r'(?:[- ]guided)?)\s+(?:gastrostomy|jejunostomy|gastrojejunostomy)\b'),
    ('gi.enteroscopy', 'enteroscopy', r'\b(?:push\s+|small[- ]bowel\s+|deep\s+|spiral\s+|(?:double|single)[- ]balloon\s+'
                                      r'|balloon[- ]assisted\s+|device[- ]assisted\s+)?enteroscop(?:y|ies|e)\b'),
    ('gi.egd', 'egd', r'\bEGD\b|\besophagogastroduodenoscop(?:y|ies)\b|\bupper\s+(?:GI\s+|gastrointestinal\s+)?'
                      r'endoscop(?:y|ies)\b(?!\s+ultraso)|\bgastroscop(?:y|ies)\b|\bupper[- ]endoscopy\b'),
    ('gi.egd', 'esophagoscopy', r'\b(?:transnasal\s+)?esophagoscop(?:y|ies)\b|\bTNE\b'),
    ('gi.egd', 'poem', r'\bper-?oral\s+endoscopic\s+myotomy\b|\bPOEM\b'),
    ('gi.egd', 'peg', r'\bpercutaneous\s+endoscopic\s+gastrostomy\b|\bPEG\b(?![- ]?J\b)(?![- ]tube\s+(?:replacement|change|'
                      r'exchange|reinsertion))'),
    ('gi.colonoscopy', 'colonoscopy', r'\b(?:ileo)?colonoscop(?:y|ies|ic)\b'),
    ('gi.flex_sig', 'flex_sig', r'\b(?<!rigid\s)(?:flexible\s+)?sigmoidoscop(?:y|ies|ic)\b|\bflex(?:ible|\.)?\s+sig\b'),
))
FAMILY_KINDS = {family: kind for family, kind, _ in reversed(SERVICES)}
# Names read only as the title of a service's own report (parts(): a report title naming it, with no plan or history
# word; _build: its own report part, on a line that gives no other time) - never in prose, a field, a heading or a
# procedure line, where SERVICES never read them. The esophageal manometry name with its modifier after the organ
# ("Esophageal High-Resolution Manometry Report", refutation gi2 RC4, ho-08): read in prose it had made the study of an
# earlier occurrence ("achalasia diagnosed on esophageal high-resolution manometry in March 2025") a performed service
# through the one act a clinic note documented, an anoscopic banding, offered it for a second review and lost the office
# visit (refutation gi2 attr-F1). Such a title reads as SERVICES' own title does.
TITLE_SERVICES: tuple[tuple[str, str, re.Pattern], ...] = (
    ('gi.motility', 'manometry',
     _rx(r'\besophageal\s+high[- ]resolution\s+(?:manometry|motility\s+(?:study|testing))\b')),
)
INSTRUMENTS = _rx(r'\b(?:colonoscope|sigmoidoscope|gastroscope|upper\s+endoscope|duodenoscope|echoendoscope|enteroscope'
                  r'|endoscope)\b')
INSTRUMENT_FAMILY = (('colonoscope', 'gi.colonoscopy'), ('sigmoidoscope', 'gi.flex_sig'), ('gastroscope', 'gi.egd'),
                     ('upper endoscope', 'gi.egd'), ('duodenoscope', 'gi.ercp'), ('echoendoscope', 'gi.eus'),
                     ('enteroscope', 'gi.enteroscopy'))

# --- vocabulary: acts ------------------------------------------------------------------------------------------
# (kind, pattern). A kind is what was done, independent of the family it is done in. Ordered: the first matching kind
# claims the text (a hot biopsy is not also a biopsy).
ACTS: tuple[tuple[str, re.Pattern], ...] = tuple((kind, _rx(pattern)) for kind, pattern in (
    ('fna', r'\bfine[- ]needle\s+(?:aspiration|biopsy|biopsies|sampling)\b|\bFN[AB]\b|\b\d{2}[- ]gauge\b[^.;]{0,40}'
            r'\bneedle\b|\bneedle\s+pass(?:es)?\b|\bEUS-guided\s+(?:tissue\s+acquisition|sampling|biops(?:y|ies))\b'),
    ('hot_biopsy', r'\bhot\s+(?:biopsy\s+)?forceps\b'),
    ('emr', r'\bendoscopic\s+mucosal\s+resection\b|\bEMR\b|\bmucosectomy\b|\blift(?:-|\s+and\s+)(?:cut|snare)\b'),
    ('esd', r'\b(?:endoscopic\s+)?submucosal\s+dissection\b|\bESD\b'),
    ('snare', r'\b(?:cold\s+|hot\s+)?snare(?:d|\s+polypectomy|\s+resection|\s+removal)?\b(?!\s+site)|\bpolypectom(?:y|ies)\b'),
    ('biopsy', r'\bbiops(?:y|ies|ied|ying)\b|\bforceps\b|\btissue\s+samples?\b|\bsampled\b'),
    ('ablation', r'\b(?:radiofrequency\s+)?ablat(?:ion|ed|ive)\b|\bargon\s+plasma\s+coagulation\b|\bAPC\b|\bRFA\b'
                 r'|\bcryo(?:therapy|ablation)\b'),
    ('bleeding_control', r'\bhemosta(?:sis|tic)\b|\bcontrol(?:led)?\s+(?:of\s+)?(?:the\s+)?(?:active\s+)?bleed\w*'
                         r'|\bbleed\w*\s+(?:was\s+|were\s+)?(?:controlled|treated|stopped|arrested)\b'
                         r'|\b(?:bipolar|multipolar|heater\s+probe|thermal)\s+(?:coagulation|probe|cautery)\b'),
    ('clip', r'\b(?:hemo|endo)?clips?\b|\bclipp(?:ed|ing)\b'),
    ('tattoo', r'\btattoo(?:ed|ing|s)?\b|\bIndia\s+ink\b|\bcarbon\s+particle\s+suspension\b'),
    ('injection', r'\b(?:submucosal\s+)?inject(?:ion|ions|ed)\b'),
    ('band_ligation', r'\b(?:band(?:ed|ing)?\s+ligation|variceal\s+band(?:ing)?|bands?\s+(?:were|was)\s+(?:placed|applied|'
                      r'deployed|fired)|banded)\b|\b(?:placed|applied|deployed|fired)\s+(?:\w+\s+){0,3}?(?:rubber\s+)?bands\b'
                      r'|\bligated\s+with\s+(?:\w+\s+){0,2}?bands?\b'),
    ('dilation', r'\bdilat(?:ion|ation|ed|ing|ors?)\b|\bbougie\w*\b|\bSavary\b(?![- ]?(?:guide-?)?wire)|\bMaloney\b'
                 r'|\b(?:through-the-scope|TTS|CRE|controlled\s+radial\s+expansion|pneumatic)\s+(?:dilation\s+)?balloon\b'
                 r'|(?<!extraction\s)(?<!occlusion\s)(?<!retrieval\s)\bballoon\s+(?:was\s+)?inflated\s+(?:\w+\s+){0,2}?to\s+'
                 r'\d{1,2}(?:\.\d)?\s*mm\b'),
    ('stent', r'\bstents?\b'),
    ('foreign_body', r'\bforeign\s+bod(?:y|ies)\b|\bfood\s+(?:bolus|impaction)\b'),
    ('sphincterotomy', r'\b(?:biliary\s+|pancreatic\s+)?(?:sphincterotomy|papillotomy)\b'),
    ('stone_extraction', r'\bstones?\b|\bcalcul(?:us|i)\b|\bsludge\b|\bballoon\s+(?:sweep|extraction)\b|\bbasket\b'),
    ('lithotripsy', r'\blithotrips(?:y|ies)\b'),
    ('cholangioscopy', r'\bcholangioscop(?:y|ic|e)\b|\bSpyGlass\b'),
    ('cannulation', r'\bcannulat(?:ion|ed)\b'),
    ('peg', r'\bPEG(?:-J)?\b|\bpercutaneous\s+endoscopic\s+gastrostomy\b|\bgastrostomy\s+tube\s+(?:was\s+)?placed\b'),
    ('tube_replacement', r'\b(?:gastrostomy|G-?tube|PEG|J-?tube|jejunostomy)\b[^.;]{0,30}\b(?:replace(?:d|ment)|'
                         r'exchang(?:ed|e)|changed)\b|\breplace(?:d|ment)\s+of\s+(?:the\s+)?(?:gastrostomy|G-?tube)\b'
                         # a tube passed through the tract that is already there is a replacement, never a new placement
                         r'|\b(?:inserted|placed|passed|reinserted)\s+(?:\w+\s+){0,3}?through\s+(?:the\s+)?(?:(?:existing|mature|'
                         r'established|old|healed|well-healed)\s+){1,3}(?:gastrostomy\s+)?(?:tract|stoma)\b'),
    ('myotomy', r'\bmyotom(?:y|ies)\b'),
    ('tube_placement', r'\b(?:decompression|rectal|colonic)\s+tube\b'),
    ('decompression', r'\bdecompress(?:ion|ed)\b(?!\s+tube)'),
    ('fundoplication', r'\btransoral\s+(?:incisionless\s+)?fundoplication\b|\bTIF\b'),
    ('capsule_study', r'\bcapsule\b'),
    ('manometry', r'\bmanometr(?:y|ic)\b|\bmotility\s+study\b|\bHRM\b'),
    ('ph_monitoring', r'\bpH\b|\bimpedance\b|\bBravo\b'),
    ('rectal_sensation', r'\brectal\s+(?:sensation|compliance|tone)\b|\bballoon\s+expulsion\b'),
    ('moderate_sedation', r'\bmoderate\s+sedation\b|\bconscious\s+sedation\b'),
    # a specimen recorded as collected (a nursing or specimen row): tissue was taken by some act; it is never coded
    ('specimen', r'\bspecimens?\s+(?:were\s+|was\s+)?(?:collected|obtained|taken|sent|submitted|retrieved)\b'),
))
ACT_KINDS = tuple(kind for kind, _ in ACTS)
# Kinds whose mere naming in a sentence is not an act (they name a thing): they are acts only with an act predicate.
NOUN_KINDS = frozenset(('stone_extraction', 'stent', 'clip', 'capsule_study', 'ph_monitoring', 'manometry', 'biopsy',
                        'tube_placement', 'specimen',
                        'injection', 'foreign_body', 'cannulation', 'tattoo', 'rectal_sensation'))
# Acts named by the object they use or leave (a stone, a stent, a clip): a bare object-noun field label answered
# with nothing reports a finding, not the act.
OBJECT_NOUN_KINDS = frozenset(('stone_extraction', 'stent', 'clip', 'capsule_study', 'tube_placement', 'foreign_body',
                               'specimen'))

# --- vocabulary: reading words ---------------------------------------------------------------------------------
# The participles an act predicate states done with (ACT_VERB; a field's note is read with them too, _note_denies).
ACT_PARTICIPLES = (r'(?:performed|done|obtained|taken|removed|resected|retrieved|excised|placed|deployed|inserted|applied|'
                   r'achieved|injected|tattooed|ablated|treated|dilated|banded|clipped|cleared|extracted|swept|sampled|'
                   r'biopsied|snared|cannulated|completed|carried\s+out|accomplished|made|used|passed|advanced|'
                   r'introduced|reached|intubated|replaced|exchanged|ingested|recorded|positioned|attached|delivered|'
                   r'fragmented|crushed|cut|sent|submitted|marked|administered|given|provided|supervised|closed)')
ACT_VERB = _rx(r'\b(?:was|were|been|is|are)\s+(?:then\s+|also\s+|successfully\s+|subsequently\s+|completely\s+|each\s+)?'
               + ACT_PARTICIPLES + r'\b'
               r'|\b(?:we|I)\s+(?:then\s+)?(?:performed|obtained|took|removed|resected|placed|deployed|injected|ablated|'
               r'dilated|banded|clipped|extracted|biopsied|snared|sampled|cannulated|passed|advanced|replaced|'
               r'administered|gave|provided|supervised)\b'
               r'|\bunderwent\b|\bunderwent\s+successful\b')
# A participle naming the act with no auxiliary ("polyps removed by cold snare", "biopsies taken").
BARE_PARTICIPLE = _rx(r'\b(?:performed|obtained|taken|removed|resected|retrieved|placed|deployed|injected|ablated|treated|'
                      r'dilated|banded|clipped|extracted|sampled|biopsied|snared|achieved|done|completed|sent|replaced|'
                      r'exchanged|reinserted|ligated|administered|decompressed|disrupted|inflated|left\s+in\s+(?:place|situ))\b')
# What may open a clause before its negation word - spaces, dashes, bullets, brackets and list labels ("- ", "A1 ", "2) ")
# - read one at a time (refutation r1 cost lens, ec5 cost: as "(?:[\s\-*•(]*(?:<label>)?\s*)*" a run was tried in every
# way of sharing it among the repetitions, so "*" and 16 spaces before "Colonoscopy was performed" took the assess stage
# past its limit). A letter label takes its digits whole, or with a numbered label after them ("A12." is "A1" "2."), as
# the old opening could: the same openings reach the same negation word.
NEG_OPENING = r'^(?:[\s\-*•(]|[A-Z]{1,3}(?:\d{2,4}[.)]|\d{1,2}(?!\d))|\d{1,2}[.)])*'
NEG_LEAD = _rx(NEG_OPENING + r'(?:no|neither|none|nor|without|there\s+was\s+no'
               r'|there\s+were\s+no)\b')
NEG_OTHER = _rx(NEG_OPENING + r'(?:no|neither|none|nor|there\s+(?:was|were)\s+no)'
                r'(?:\s+(?:other|further|additional|more|another|separate|repeat)\b'
                # a limit on acts beyond the documented ones: "No tissue was sampled beyond the three containers"
                r'|\b[^.;\n]{0,80}?\b(?:beyond|other\s+than|except(?:\s+for)?|apart\s+from|besides|in\s+addition\s+to)\s+'
                r'(?:the|those|these|what|that|this|its|their|\w+\s+(?:listed|described|documented|noted))\b)')
# Each auxiliary's contraction is the same negation, in either apostrophe (refutation r1: "Biopsies weren’t taken"
# from Word or PDF text, "Biopsies haven't been obtained" and "A biopsy hasn't been taken" had read as done acts).
NEG_CONTRACTION = r"n['’]t"
NOT_VERB = _rx(r"\b(?:was|were|is|are|been|has|have|had|did|does|could|would|can)\s+(?:not|never|" + NEG_CONTRACTION
               + r")\b(?:\s+be)?"
               r"|\bnot\s+(?:performed|done|obtained|taken|removed|resected|treated|sampled|biopsied|placed|injected|"
               r"attempted|repeated|undertaken|carried\s+out|reached|completed|required|needed|indicated)\b"
               r"|\b(?:was|were|is|are|has|have|had|did|does|could|would|ca)" + NEG_CONTRACTION + r"\b(?:\s+be)?")
WITHOUT = _rx(r'\b(?:without|w/o)\b')
# A negation's list ends where another clause opens after it - a subordinator or a temporal preposition ("No bleeding
# occurred after the biopsies were obtained", "There were no complications after biopsies were taken", "No residual
# bleeding followed once two hemoclips were placed"): an act inside that clause is outside the negated list and reads by
# its own predicate, unless a negation of its own follows the opener ("There was no bleeding because no biopsies were
# taken"). Refutation r1, negtime-6: the opening "No" had excluded 43239 and 43255 as denied.
NEGATION_SCOPE_END = _rx(r'\b(?:after|before|once|when|whenever|while|until|because|since|following|whereupon'
                         r'|as\s+soon\s+as|so\s+that)\b')
NEGATION_WORD = _rx(r'\b(?:no|not|none|nothing|neither|nor|never|without|w/o)\b')
# Where a negation's list breaks (7c8 skeptic, sk:5): a comma, "and", "so", "as", "then" - a clause may open after it
# ("There was no bleeding and biopsies were taken", "No active bleeding, two hemoclips were placed", "No bleeding
# occurred as the biopsies were obtained") - or "or" / "nor", which only ever join the list's own items ("No biopsy,
# polypectomy, or tattoo was performed").
NEGATION_LIST_BREAK = _rx(r'(?P<joiner>\b(?:or|nor)\b)|,|\b(?:and|so|as|then|thus|hence|whereupon)\b')
# From an act's mention to its own predicate's auxiliary, within its noun phrase ("biopsies of the antrum were taken"):
# never across a list joiner ("polypectomy or tattoo was performed" is the list's shared predicate).
TO_OWN_PREDICATE = _rx(r'(?:\s+(?!(?:or|nor|and|but)\b)[\w-]+){0,4}?\s+(?:(?:has|have|had)\s+)?(?=(?:was|were|been|is|are)\b)')


def _outside_negation(phrase: str, after: str = '') -> bool:
    """Whether ``phrase`` - the words from a negation up to an act's mention - opens another clause after the negation
    (NEGATION_SCOPE_END) with no negation of its own after that opener: the act is then outside the negated list. So
    when the list's last break before the mention is a clause break (NEGATION_LIST_BREAK, never "or" / "nor") with no
    negation after it, and the mention is the subject of its own act predicate right after it (``after``, the clause
    after the mention: "... and biopsies were taken"): a new clause, not an item of the list (7c8 skeptic, sk:5)."""
    opener = None
    for m in NEGATION_SCOPE_END.finditer(phrase):
        opener = m
    if opener is not None and not NEGATION_WORD.search(phrase, opener.end()):
        return True
    if not after:
        return False
    brk = None
    for m in NEGATION_LIST_BREAK.finditer(phrase):
        brk = m
    if brk is None or brk.group('joiner') or NEGATION_WORD.search(phrase, brk.end()):
        return False
    lead = TO_OWN_PREDICATE.match(after)
    return lead is not None and ACT_VERB.match(after, lead.end()) is not None
# A "not" after the act that belongs to another predicate: one inside a subordinate clause ("Possible EGD with PEG
# placement if intake does not improve"), or a second predicate coordinated with the act's own participle ("was
# tattooed and not removed"). Every other "not" in the clause still negates the act (fail-closed).
SUBORDINATOR = _rx(r'\b(?:if|unless|until|because|since|when|whenever|once|so\s+that|in\s+case|whether)\b')
COORDINATED_PREDICATE = _rx(r'(?:,\s*)?\s+(?:and|or)\s+$')


def _not_on_another_predicate(text: str, neg: int, end: int) -> bool:
    """Whether the negation at ``neg`` governs a predicate other than the act mention ending at ``end``."""
    if neg < end:
        return False  # the negation precedes or covers the mention ("did not undergo EGD", "not biopsied")
    between = text[end:neg]
    sub = SUBORDINATOR.search(between)
    # a subordinate clause the negation lies inside ("... if intake does not improve"), never one set off by commas
    # that closes before the act's own negated predicate ("Snare polypectomy of the polyp, since it appeared deeply
    # invasive, was not performed": refutation r1, read as a done snare)
    if sub and not (re.search(r'^[^,]*,\s*,?\s*$|,\s*(?:(?:it|this|which)\s+)?$', between[sub.end():])
                    and between[:sub.start()].rstrip().endswith(',')):
        return True
    return bool(COORDINATED_PREDICATE.fullmatch(between)) and bool(re.search(r'ed\Z', text[:end]))
# "without (any) complication(s) (at all)" ending its clause at a stop, a semicolon, a colon or the line's end ("The
# following procedures were performed today without any complication at all:" over the polypectomy line): the "without"
# denies the complication, never the act after it. A phrase that runs on, or a list that goes on after a comma ("without
# bleeding requiring clip placement", "without bleeding, perforation or a clip being placed"), still denies.
WITHOUT_COMPLICATION = _rx(r'\b(?:without|w/o)\s+(?:(?:any|immediate|apparent|obvious|significant|major)\s+){0,2}'
                           r'(?:complications?|bleeding|perforation)(?:\s+(?:at\s+all|whatsoever))?[ \t]*(?:[.;:]|\n)')
# A service or an act named as replaced by another: "an EGD was performed rather than EUS", "flexible sigmoidoscopy
# instead of colonoscopy", "EGD in lieu of EUS", "photographed instead of being removed by cold snare" (routing's
# replacement words, studio.gi.cues). The cue governs its own object only - one noun phrase right after it, never across
# a comma or a second determiner - so the act that replaced it reads by its own predicate (refutation r1: "Instead of a
# hot snare, a cold snare was used" and "Rather than a snare, cold forceps were used" had read the cold snare and the
# forceps as replaced).
REPLACED = _rx(r'(?<![\w/-])(?:instead\s+of|rather\s+than|in\s+lieu\s+of|as\s+opposed\s+to|in\s+place\s+of)'
               r'(?:\s+being(?:\s+[a-z]+(?:ed|en))?(?:\s+(?:with|by|using|via))?'
               r'|\s+[a-z]+ing(?:\s+(?:it|them))?\s+(?:with|to|by|using|via))?(?:\s+(?:a|an|the|any))?'
               r'(?:\s+(?!(?:a|an|the|any|this|that|these|those|its|their|was|were|is|are|be|been|being|has|have|had|of'
               r'|with|by|to|for|in|on|at|from|and|or|but|nor|then)\b)[\w-]+){0,3}[ \t]*$')
REPLACED_CUE = 'negated: named as replaced by another service'
CANCEL_WORDS = _rx(r'\b(?:cancel(?:l)?ed|declined|refused|deferred|postponed|aborted\s+before|not\s+attempted)\b')
HISTORY_WORDS = _rx(r'\b(?:prior|previous(?:ly)?|history\s+of|historical|in\s+the\s+past|ago|earlier|remote|old|formerly'
                    r'|last\s+(?:year|month|week|time|visit|seen)|had\s+(?:a|an|undergone|been|had)|status\s+post|s/p'
                    r'|prior-record|mentioned\s+in\s+the\s+preprocedure\s+history)\b'
                    # another facility's study ("an outside EUS-guided biopsy", "at an outside hospital"), never a margin
                    # ("an incision outside the marks")
                    r'|\b(?:an?|the)\s+outside\s+(?:hospital|facility|institution|center|centre|clinic|records?|report|'
                    r'endoscop\w*|colonoscop\w*|gastroenterolog\w*|EGD|EUS(?:-guided)?|ERCP|procedure|study|biops\w*|'
                    r'imaging|CT|MRI|physician|practice)\b|\bat\s+an\s+outside\b|\bperformed\s+elsewhere\b')
PLAN_WORDS = _rx(r'\b(?:will(?:\s+be)?|plan(?:s|ned)?|schedul(?:e|ed|ing)|future|recommend(?:ed|ation)?|may\s+require'
                 r'|might\s+(?:require|need)|may\s+need|consider(?:ed|ation)?|to\s+be\s+(?:arranged|scheduled|done)'
                 r'|arrange(?:d)?|next|upcoming|pending\s+(?:scheduling|authorization)|repeat\s+(?:in|after)|after\s+'
                 r'pathology\s+review|if\s+(?:needed|necessary|indicated|cholangitis|symptoms)|referr(?:al|ed)\s+for'
                 r'|follow-?up\s+(?:colonoscopy|EGD|endoscopy|EUS|ERCP))\b')
# A manner phrase - "as planned", "as recommended", "as previously discussed", "per the prior plan" - is the booking or
# the agreement an act kept (routing's cues.AS_BOOKED_BEFORE), never its time: its plan or history word never dates the
# act (the class of 7c8 skeptic sk:1 and sk:4 beyond their inputs). "will ... as planned" still has its own "will".
MANNER_PHRASE = _rx(r'\bas\s+(?:(?:previously|originally|initially|already|earlier)\s+)?(?:planned|scheduled|recommended|'
                    r'arranged|discussed|requested|ordered|agreed|intended|booked|indicated|noted|described|documented|'
                    r'outlined|consented)(?:\s+(?:previously|earlier|before))?\b'
                    r'|\bper\s+(?:(?:the|our|her|his|their)\s+)?(?:(?:prior|previous|original|initial|earlier)\s+)?'
                    r'(?:plan|recommendation|protocol|discussion|request|order|schedule|consent)\b')
# Reviewing earlier records is today's work: "review of prior records" never makes its clause historical.
REVIEW_OF_RECORDS = _rx(r'\breview(?:ed|ing)?\s+(?:of\s+)?(?:the\s+)?(?:prior|previous|old|outside|earlier)\s+'
                        r'(?:records?|notes?|results?|reports?|imaging|studies|labs?|pathology|colonoscopy|endoscopy|'
                        r'charts?)\b')
# Whose time a date in an act's clause is (refutation r1, negtime-7: "(DOB 03/04/1961) underwent colonoscopy today", "two
# hemoclips at 2015" and "dilation was performed for the stricture found on barium swallow on 09/22/2026" had dated
# today's act and excluded its code). A birth date (its label: "DOB", "born") or a clock time ("at 2015") is no act's
# time. A date in another clause or event - after a subordinator or a relative word whose clause has a predicate of its
# own ("after apixaban was held on ...", "which was removed on ..."), or after another event's participle ("found",
# "seen", "noted", "held") with nothing closing its phrase - is that event's, unless the mention is inside it: it
# leaves the act's time in doubt (OTHER_TIME_CUE: held, never excluded - engine._select), never dates it.
BIRTH_LABEL = _rx(r'(?:\bDOB|\bD\.O\.B\.?|\bdate\s+of\s+birth|\bbirth\s*date|\bborn(?:\s+(?:on|in))?|\bb\.)'
                  r'(?:[ \t]+(?:is|was))?[ \t]*[:#=-]?[ \t]*$')
# The date that stamps when text was written - the app's own addendum header ("ADDENDUM (revision 2, added 2026-10-27
# 08:15 UTC)", jobs.addendum_block_text), a signature's or a dictation's date - is the document's time, never an act's
# (refutation r1, negtime-10: the stamp had made the act an addendum adds "planned" and excluded its code).
# 7c8 skeptic, sk:6: by its structure, not a closed list of participles - a word naming when the text was written (an
# addendum, a late entry, an entry, an update, a correction, a revision, an edit, a signature, a dictation; the list is
# only that structure's vocabulary), optionally its author ("by Dr. Ramos") and "on" / "at", right before the date or
# the bracket that opens it ("Addendum 10/16/2026:", "(entered 10/16/2026)", "signed by Dr. Ramos on 10/16/2026").
STAMP_LABEL = _rx(r'(?:\badded|\baddendum(?:\s+dated)?|\blate\s+entry(?:\s+dated)?|\b(?:re-?)?entered|\bupdated|\bcorrected|\brevised|\bedited|'
                  r'\bfinali[sz]ed|\bauthenticated|\battested|\b(?:e-?|electronically\s+|co-?)?signed|\bdictated|'
                  r'\btranscribed|\bamended|\baddended|\bfaxed|\bprinted)'
                  r"(?:\s+by\s+(?:[\w.'-]+,?\s+){1,5}?)?(?:\s*(?:on|at))?[ \t]*[:#=(-]?[ \t]*$")
# A clock time: "at 2015", "@ 2015", "at approximately 2015" (7c8 skeptic, sk:3: an approximation had read as a year).
CLOCK_TIME = _rx(r'(?:\bat|@|\btime[ \t]*[:=]?)[ \t]*(?:(?:approximately|approx\.?|about|around|roughly|~)[ \t]*)?$')
# A four-digit number after "by" reads as a clock time as well as a year ("placed on the vessel by 2015").
BY_TIME = _rx(r'\bby[ \t]*$')
# What may stand before a date in a parenthesis that dates the act itself ("(09/03/2026)", "(on 09/03/2026)"); any other
# words there label another item's date ("(barium swallow 09/22/2026)", "(CT 09/22/2026)": 7c8 skeptic, sk:3).
OWN_DATE_LEAD = _rx(r'[ \t]*(?:(?:on|in|at|dated|from|since|until|by|circa)[ \t]+)?')
OTHER_EVENT = _rx(r'\b(?:after|before|when|whenever|once|until|because|since|while|whereas|although|if|unless|which|who|'
                  r'whom|whose|where|whereby)\b|\b(?P<event>found|seen|noted|identified|detected|diagnosed|shown|'
                  r'demonstrated|described|reported|documented|visuali[sz]ed|observed|imaged|confirmed|suspected|'
                  r'admitted|discharged|referred|hospitali[sz]ed|held|stopped|started|resumed|restarted|discontinued|last\s+dose)\b')
OTHER_EVENT_PREDICATE = _rx(r'\b(?:was|were|is|are|been|has|have|had|did|does)\b|\b[a-z]{3,}ed\b')
OTHER_TIME_CUE = 'uncertain: a time in its clause is something else\u2019s: '
OTHER_EVENT_REACH = 80  # characters after a date read for the predicate of the clause another event opens before it
CLAUSE_MARK = re.compile(r'[,;:()\n]')  # a mark that closes the clause or event an opener began
HEDGE_WORDS = _rx(r'\?|\b(?:possibl[ey]|probabl[ey]|questionabl[ey]|likely|unlikely|uncertain|unclear|may\s+have|might\s+have'
                  r'|presumed|presumably|suspected|apparently'
                  r'|(?<!first\s)(?<!second\s)(?<!third\s)(?<!fourth\s)(?<!initial\s)(?<!final\s)attempt(?:ed)?)\b')
# A predicate under a modal states nothing done (routing:18): a perfect modal ("it would have been dilated with a
# balloon", "Biopsies could have been taken but were not needed"), the conditional "would be" ("EGD with biopsy would be
# done if the dysphagia persists") - the hedges routing's HEDGED_AFTER reads - and the modals of a recommendation or a
# possibility ("EGD should be done.", "may be done", "could be done"), which routing reads as no performance at all. A
# plan section or a plan word still dates a clause first (read_clause), so a plan line keeps its planned reading. A
# match spans the modal and the one predicate word it governs, so blanking it leaves a clause's own stated predicates
# ("Biopsies were taken and would be sent ...") readable.
HYPOTHETICAL = _rx(r"\b(?:would|could|should|must|may|might)(?:n't|n\u2019t)?(?:\s+(?:not|never|possibly|perhaps|also|well|"
                   r"then|otherwise|still|[\w-]+ly))?(?:\s+have|['\u2019]ve)\s+(?:been\s+|gotten\s+|got\s+)?"
                   r"(?:(?:then|also|[\w-]+ly)\s+){0,2}[\w-]+"
                   r"|\b(?:would|should|could|may|might|must|can|cannot)(?:n't|n\u2019t)?\s+(?:(?:not|never|then|also|"
                   r"otherwise|still|[\w-]+ly)\s+)?(?:be|get)\s+(?:(?:then|also|[\w-]+ly)\s+){0,2}[\w-]+")
# An ability, not a hypothesis, when today's narrative states it ("The colonoscopy could be performed only to the
# splenic flexure", "Biopsies could be obtained without difficulty"): "could"/"can" with "be", no "have" and no
# condition governing the clause (_ability_realized). Elsewhere ("EGD could be done", in an office note) it stays a
# possibility.
ABILITY = _rx(r"\b(?:could|can)\s+(?:(?:then|also|still|[\w-]+ly)\s+)?(?:be|get)\b")
CONDITION_IN_CLAUSE = _rx(r"\b(?:if|unless|whether|provided|in\s+case|had\s+(?:it|the|a|an|there|he|she|they|we|this|"
                          r"that|prep|preparation)|were\s+(?:it|the|a|an|there|he|she|they|we|this|that))\b"
                          # a time still to come (refutation r1: "can be performed once anticoagulation is held", "could
                          # be biopsied at a repeat colonoscopy" had read as done today)
                          r"|\b(?:once|when|after|until|before|as\s+soon\s+as)\b[^.;\n]{0,60}?\b(?:is|are|has\s+been|"
                          r"have\s+been|returns?|resumes?|stops?|starts?|completes?|becomes?|gets?|can|will)\b"
                          r"|\bat\s+(?:a|the)\s+(?:repeat|future|subsequent|later|next|follow-?up|second)\b"
                          r"|\bat\s+a\s+later\s+(?:date|time|session)\b")
PAST_STATEMENT = _rx(r"\b(?:was|were)\s+(?:then\s+|also\s+|subsequently\s+)?[a-z]+(?:ed|en|ne|wn)\b")
# An opener between an act and a modal predicate after it gives the modal another subject ("Cold snare polypectomy of
# the 8 mm polyp, after which the examination could be completed", "Stent placement, so that the duct could be
# decompressed"): the act is not its subject (_hypothetical step 5, facts_wording skeptic).
OTHER_SUBJECT_OPENER = _rx(r"\b(?:which|that|who|whom|whose|where|when|whereupon|after|before|until|once|so|so\s+that|"
                           r"such\s+that|in\s+order|allowing|enabling|permitting|with\s+which|by\s+which|through\s+"
                           r"which)\b|[;:]|,\s*(?:and|but|then)\b")
# A hypothetical predicate right after the mention, after at most a short phrase of place or means (routing's own
# cues._PLACE_PHRASE): "A biopsy would have been taken had ...", "EGD with biopsy would be done if ...".
HYPOTHETICAL_AFTER = _rx(_cues._PLACE_PHRASE + r'[\s,]*(?P<h>' + HYPOTHETICAL.pattern + r')')
# A condition on the mention's own performance that opens its clause (routing's cues.CONDITIONAL, read for any
# mention): "If colonoscopy were done today, ...", "Were a colonoscopy done today, ...", "Had a colonoscopy been done
# today, ...", "Should EGD be performed, ...". BEFORE is read on the clause up to the mention, AFTER right after it; an
# inverted "Had" holds only with its "been" ("Had EGD performed today" says the patient had one).
CONDITION_BEFORE = _rx(r'^[\s\-*•(]*(?P<w>if|unless|were|had|should)\s+(?:(?:the|a|an|any)\s+)?$')
CONDITION_AFTER = _rx(r'\s+(?:(?:were|was|is|are|be|been|had\s+been|has\s+been|have\s+been)\s+)?' + _cues._HEDGE_ACT
                      + r'\b')
CONDITION_AFTER_HAD = _rx(r'\s+been\s+' + _cues._HEDGE_ACT + r'\b')
HYPOTHETICAL_CUE = 'uncertain: hypothetical: '
# What a consent, an authorization or an approval is for is named, never stated done ("Consent was obtained for biopsy
# and cold snare polypectomy", "Written consent for EGD with dilation was obtained", "Consent obtained for: Biopsy",
# "Prior authorization was obtained for colonoscopy"): its predicate ("obtained", "given") is the consent's. Read in a
# clause only when nothing else in it dates or doubts the item first; held, never excluded (_consent_object).
CONSENT_FOR = _rx(r'\b(?:consent(?:s|ed)?|permission|authori[sz]ation|approval|clearance)\b'
                  r'(?P<predicate>[^.;:,\n]{0,60}?)\b(?:for|to)\b[ \t]*:?')
CONSENT_AFTER = _rx(r'[ \t]+(?:consent|authori[sz]ation|approval)\b')
# A consent that is the subject of the clause's predicate ("Informed consent was obtained after explaining the risks of
# colonoscopy with polypectomy"): that predicate is the consent's, never an act's named after it.
CONSENT_SUBJECT = _rx(r'\b(?:informed\s+|written\s+|verbal\s+|procedural\s+)?(?:consent|permission|authori[sz]ation|'
                      r'approval)\b')
CONSENT_PREDICATE = _rx(r'\b(?:signed|given|documented|reviewed|confirmed|verified|received|discussed)\b')
# A consent governed by the preposition, participle or subordinator that opens its phrase ("After obtaining informed
# consent, ...", "With the patient's consent, ...", "Per the patient's permission to proceed, ...", "Following anesthesia
# clearance for the procedure, ...", "After consent was obtained, ..."): an adverbial, never the subject of the predicate
# the clause goes on to, so that predicate is the item's own (refutation r1: "After obtaining informed consent, we
# performed cold snare polypectomy" read the snare as what the consent was for: no unresolved item, no second review).
CONSENT_GOVERNED = _rx(r'(?:after|with|per|following|upon|on|given|having|once|before|prior\s+to|pending|under)\b')
# The predicate a consent can be the subject of: an auxiliary one ("was obtained", "were signed"), never an active one
# whose subject is the endoscopist ("we performed", "I took").
AUXILIARY_PREDICATE = _rx(r'(?:was|were|been|is|are)\b')
CONSENT_CUE = 'uncertain: named as what a consent or an authorization is for'
# What a referral is for ("tattooed for EMR referral", "for an advanced endoscopy referral"): the item inside the phrase
# is planned, never done today; the rest of the clause keeps its own reading (refutation r1: read as an EMR done).
REFERRAL_FOR = _rx(r'\bfor\s+(?:an?\s+|the\s+)?(?:[\w-]+\s+){0,3}?referral\b')
INDICATION_READING = 'uncertain: stated in an indication, not as done today'
# "placement of a covered stent", "removal of the polyp": a nominal act predicate, read like a verb.
NOMINAL_ACT = _rx(r'\b(?:placement|insertion|deployment|removal|extraction|retrieval|resection|ablation|dilation|dilatation|'
                  r'ligation|injection|closure|decompression)\s+of\b')
TODAY_WORDS = _rx(r'\btoday\b|\bthis\s+(?:session|encounter|procedure|examination|visit)\b|\bduring\s+this\b'
                  r'|\bon\s+the\s+date\s+of\s+(?:the\s+)?(?:encounter|service|visit)\b'
                  r'|\bsame\s+(?:session|procedural\s+encounter|encounter)\b|\bat\s+this\s+(?:session|encounter)\b')
# Completion statements about the examination itself.
COMPLETE_POS = _rx(r'\b(?:examination|exam|procedure|study|colonoscopy|EGD|endoscopy|it)\s+was\s+complete(?:d)?\b'
                   r'|\bcomplete\s+(?:examination|exam|colonoscopy)\b|\bcompleted\s+without\s+interruption\b'
                   r'|\b(?:c(?:a)?ecum|terminal\s+ileum)\s+was\s+(?:reached|intubated|identified)\b'
                   r'|\b(?:advanced|passed)\s+(?:under\s+direct\s+visuali[sz]ation\s+)?to\s+the\s+(?:c(?:a)?ecum|terminal\s+ileum)\b'
                   r'|\bc(?:a)?ecal\s+intubation\s+was\s+(?:confirmed|achieved)\b'
                   r'|\bsingle\s+completed\b'
                   r'|\b(?:advanced|passed|introduced)\s+(?:\w+\s+){0,10}?(?:to|into)\s+the\s+(?:second|third|2nd|3rd)\s+'
                   r'(?:portion|part)\s+of\s+the\s+duodenum\b')
INCOMPLETE_WORDS = _rx(r'\b(?:incomplete(?:ly)?|discontinu(?:ed|e|ation)|terminat(?:ed|ion)|abort(?:ed)?|abandon(?:ed)?'
                       r'|unable\s+to\s+(?:advance|reach|pass|traverse|intubate|complete)|could\s+not\s+be\s+(?:advanced|'
                       r'passed|completed)|not\s+(?:reached|completed|advanced\s+beyond)|stopped\s+at|limited\s+to\s+the'
                       r'|precluded|interrupted)\b')
DEEP_CANNULATION = _rx(r'\b(?:deep(?:ly)?|selective(?:ly)?)\s+(?:\w+\s+){0,2}?cannulat(?:ion|ed)\b|\bcannulat(?:ion|ed)\s+'
                       r'(?:\w+\s+){0,4}?(?:deep(?:ly)?|selective(?:ly)?)\b')
DISCONTINUED = _rx(r'\b(?:discontinu(?:ed|e|ation)|terminat(?:ed|ion)|abort(?:ed)?|abandon(?:ed)?|interrupted|stopped\s+'
                   r'(?:early|prematurely|because|due))\b')
INTENT_WORDS = (('screening', _rx(r'\bscreening\b')), ('surveillance', _rx(r'\bsurveillance\b')),
                ('diagnostic', _rx(r'\bdiagnostic\b|\bsymptom-?driven\b')))
LESION_NOUN = (r'(?:polyps?|lesions?|mass(?:es)?|nodules?|tumou?rs?|ulcers?|adenomas?|stricture|ring|varix|varices|'
               r'angioectas(?:ia|iae)|AVMs?|cysts?|plaques?|erosions?)')
LESION = _rx(r'(?P<lead>\b(?:an?|one|two|three|four|five|six|several|multiple|\d+|the|this|that|a\s+separate|another)\s+)?'
             r'(?P<sep>separate\s+)?(?P<size>(?:\d+(?:\.\d+)?\s*(?:x\s*\d+(?:\.\d+)?\s*)?(?:mm|cm)|\d+[- ](?:mm|cm))'
             r'(?:\s+and\s+\d+(?:\.\d+)?\s*(?:mm|cm))?\s+)?(?P<morph>(?:(?:sessile|pedunculated|flat|depressed|'
             r'raised|pale|nonbleeding|non-bleeding|bleeding|hypoechoic|irregular|ulcerated|clean-based|semi-?pedunculated|'
             r'serrated|small|large|diminutive|lateral\s+spreading|laterally\s+spreading|polypoid|submucosal|'
             r'subepithelial|carpet-?like)[\s,]+){0,3})(?P<noun>' + LESION_NOUN + r')\b')
SPECIMEN = _rx(r'\b(?:specimen|jar|container|bottle|pot)s?\s+(?P<label>[A-Z0-9]{1,2})\b|\((?:jar|specimen|container)\s+'
               r'(?P<label2>[A-Z0-9]{1,2})\)')
ANAPHORA = _rx(r'\W*(?:(?:[A-Z]{1,3}\d{1,2}|\d{1,2}[.)])\s+)?(?:this|that|the|it|its)\b(?:\s+(?:\d+(?:\.\d+)?\s*(?:mm|cm)\s+)?'
               + LESION_NOUN + r'\b)?')
TECHNIQUES = (('cold forceps', _rx(r'\bcold[- ](?:biopsy\s+)?forceps\b')), ('hot forceps', _rx(r'\bhot\s+(?:biopsy\s+)?forceps\b')),
              ('cold snare', _rx(r'\bcold\s+snare\b')), ('hot snare', _rx(r'\bhot\s+snare\b')),
              ('balloon', _rx(r'\bballoon\b')), ('guidewire', _rx(r'\bguide-?wire\b|\bSavary\b|\bbougie\b')),
              ('forceps', _rx(r'\bforceps\b')), ('snare', _rx(r'\bsnare\b')),
              ('needle', _rx(r'\b\d{2}[- ]gauge\b|\bneedle\b')), ('argon plasma', _rx(r'\bargon\s+plasma\b|\bAPC\b')),
              ('radiofrequency', _rx(r'\bradiofrequency\b|\bRFA\b')), ('electrocautery', _rx(r'\bcautery\b|\bblended\s+current\b')),
              ('basket', _rx(r'\bbasket\b')), ('extraction balloon', _rx(r'\bextraction\s+balloon\b|\bballoon\s+sweep\b')))

# --- document parts and roles ----------------------------------------------------------------------------------
REPORT_TITLE = _rx(r'^[\s\-*#]*(?P<title>[^\n:.]{0,80}?\b(?:procedure\s+report|report|procedure\s+note|operative\s+note'
                   r'|note|record))\s*$')
# "SMALL BOWEL CAPSULE ENDOSCOPY: INTERPRETATION AND REPORT", "Colonoscopy - procedure note": a title that names its
# service before a colon and only report words after it.
TITLE_REPORT_WORDS = _rx(r'^[\s\-*#]*(?P<title>[^\n:.]{3,80}?)\s*[:\-\u2013]\s*(?:(?:interpretation|procedure|operative|final|'
                         r'physician|study|and|with)\s+){0,4}(?:report|note|record|interpretation|summary)\s*$')
# "PROCEDURE NOTE: ESOPHAGOGASTRODUODENOSCOPY WITH BAND LIGATION": a report title that names its service after a colon.
TITLE_FIELD = _rx(r'^[\s\-*#]*(?:procedure|operative|endoscopy|endoscopic)\s+(?:note|report)\s*[:\-\u2013]\s*'
                  r'(?P<value>\S[^\n]{0,100})$')
# A numbered part of the document ("PART 2 - ") is read by the line after its number.
PART_NUMBER = re.compile(r'[ \t]*' + _sections.DOCUMENT_PART, re.A)
# The procedure field's labels ("Procedure:", "Interventions:", "Procedures performed today:"); a check-box list
# directly under one lists what was done (_in_a_procedure_list).
PROCEDURE_LABELS = (r'(?:procedures?(?:\s+performed(?:\s+today)?)?|operation|interventions?|stud(?:y|ies)'
                    r'(?:\s+performed)?|tests?\s+performed)')
PROCEDURE_FIELD = _rx(r'^[\s\-*#]*' + PROCEDURE_LABELS + r'\s*[:\-–]\s*'
                      r'(?P<value>\S[^\n]*)$')
PROCEDURE_LIST_LABEL = _rx(r'[\s\-*#]*' + PROCEDURE_LABELS + r'[ \t]*:?[ \t]*')
# A nursing heading names the nursing role's own entry ("Nursing record", "NURSING PROCEDURE RECORD (Delphine Oakes,
# LPN)", "Nurse's notes", "Procedure checklist", "Nursing note: 10/14/2026 08:30"), as the other roles' headings name
# their record, note or report, or it is the role's name alone on its line ("NURSING", "Nursing:"). A staff field that
# names a nurse ("Nurse: Jo Rowe, RN", "RN: Jo Rowe", "Nursing staff: Jo Rowe, RN; Sam Lee, LPN") or a line of prose
# about one ("Nurse present throughout the procedure.") heads no entry: it had opened a nursing part over the rest of
# the physician's report, whose acts reconciliation then skipped (refutation r1, missed-1). Its own line still reads
# through ROLE_LABEL. The lookahead keeps the line's earlier bound, so no line that was no heading becomes one.
_NURSE = r'(?:(?:pre|intra)-?procedure\s+|recovery\s+)?(?:nursing|nurse(?:[\'’]?s)?|RN)'
_NURSING_ENTRY = (r'(?:(?:pre-?|intra-?)?procedure\s+)?(?:record|records|note|notes|checklist|documentation|assessment|'
                  r'flowsheet|flow\s+sheet|entry|entries|report|summary)')
ROLE_HEADINGS = (('nursing', _rx(r'^[\s\-*#]*(?=(?:nursing|nurse|RN|recovery\s+nurse|procedure\s+checklist|nursing\s+'
                                 r'checklist|pre-?procedure\s+nursing|intra-?procedure\s+nursing)\b[^\n]{0,60}$)'
                                 r'(?:' + _NURSE + r'\s+' + _NURSING_ENTRY + r'\b|procedure\s+checklist\b'
                                 r'|' + _NURSE + r'[ \t]*:?[ \t]*$)')),
                 ('anesthesia', _rx(r'^[\s\-*#]*(?:anesthesia|anaesthesia|sedation\s+record)\s+(?:record|note|report)\b[^\n]{0,60}$')),
                 ('pathology', _rx(r'^[\s\-*#]*(?:surgical\s+)?pathology\s+(?:report|result|results|addendum)\b[^\n]{0,60}$')),
                 ('radiology', _rx(r'^[\s\-*#]*(?:radiology|imaging)\s+(?:report|result|results)\b[^\n]{0,60}$')))
ROLE_SIGNATURE = (('nursing', _rx(r'\b(?:recorded|entered|documented|completed|charted)\b[^.\n]{0,60}\bby\s+[^.\n]{0,60}'
                                  r'\b(?:RN|LPN|nurse)\b|\bnursing\s+(?:checklist|entry|note|handoff)\b')),
                  ('anesthesia', _rx(r'\b(?:CRNA|anesthesiologist|anaesthetist)\b[^.\n]{0,40}\b(?:recorded|documented|'
                                     r'charted)\b')))
# A sentence that opens with its author's label speaks for that author whatever part it stands in.
ROLE_LABEL = (('physician', _rx(r'^\W*(?:physician|endoscopist|proceduralist|attending|surgeon|MD)(?:\s+(?:note|statement|'
                                r'attestation|addendum|comment))?\s*:')),
              ('nursing', _rx(r'^\W*(?:nurse|nursing|RN|LPN)(?:\s+(?:note|entry|comment))?\s*:')),
              ('anesthesia', _rx(r'^\W*(?:anesthesia|anaesthesia|CRNA|anesthesiologist)(?:\s+(?:note|record))?\s*:')))
GENERIC_HEADING = _rx(r'^[\s\-*#]*[A-Z0-9][A-Za-z0-9 /&,()\-]{1,60}:?\s*$')
# Another provider's service, stated in its sentence: anesthesia given by an anesthesia professional, specimens sent to
# a pathology or cytology service, a facility's or radiology's own billing. A sentence that denies it attributes nothing.
_ANESTHESIA_WHO = (r'\b(?:anesthesiologist|anaesthetist|anaesthesiologist|CRNA|anesthesiology|anaesthesiology|'
                   r'(?:certified\s+registered\s+)?nurse\s+an(?:a)?esthetist|an(?:a)?esthesia\s+associates|'
                   r'anesthesia\s+(?:team|department|care\s+team|service|services|professional|provider|group|record|staff)|'
                   r'anaesthesia\s+(?:team|department|service|record))\b')
OTHER_PROVIDER = (
    ('anesthesia', _rx(r'\b(?:monitored\s+anesthesia\s+care|MAC|general\s+(?:endotracheal\s+)?an(?:a)?esthesia|propofol'
                       r'|deep\s+sedation|an(?:a)?esthesia)\b[^;\n]{0,160}' + _ANESTHESIA_WHO
                       + r'|' + _ANESTHESIA_WHO + r'[^;\n]{0,120}\b(?:provided|administered|gave|managed|supplied|'
                       r'delivered)\b[^;\n]{0,40}\b(?:MAC|an(?:a)?esthesia|sedation|propofol)\b'
                       r'|\ban(?:a)?esthesia\s+(?:services|charges)\s+(?:are|were|will\s+be)\s+(?:billed|reported|documented)'
                       r'\s+separately\b')),
    ('pathology', _rx(r'\b(?:specimens?|samples?|biops(?:y|ies)|containers?|jars?|brushings?|tissue|polyps?|pieces|'
                      r'aspirates?|slides?|cell\s+blocks?|both|all)\b[^.\n]{0,160}?\b(?:sent|submitted|delivered|forwarded|'
                      r'to)\b[^;\n]{0,80}?\b(?:patholog\w*|cytopatholog\w*|cytology|histolog\w*)\b'
                      r'|\b(?:interpretation|evaluation)\b[^;\n]{0,80}\b(?:reported|performed|provided|made)\s+by\s+'
                      r'(?:the\s+)?(?:\w+\s+){0,3}?(?:patholog\w*|cytopatholog\w*)\b'
                      r'|\bpathology\s+(?:interpretation|service|department|review)\b[^;\n]{0,120}\b(?:separate|by\s+the|'
                      r'will\s+be|reported\s+separately|performed\s+by)\b|\bseparate\s+pathology\s+service\b')),
    ('radiology', _rx(r'\bradiology\s+interpretation\s+is\s+reported\s+separately\b|\bradiologist\b[^;\n]{0,60}\bseparately\b'
                      r'|\bradiology\s+services\s+are\s+billed\s+separately\b'
                      r'|\b(?:supervision\s+and\s+interpretation|interpretation)\b[^;\n]{0,80}\b(?:reported|billed|performed|'
                      r'provided)\s+by\s+(?:the\s+)?radiolog\w*\b'
                      r'|\binterpreted\s+by\b[^;\n]{0,60}\bradiolog(?:y|ist)\b')),
    ('facility', _rx(r'\bfacility\s+(?:services|charges|fees|claim|component|billing)\b[^;\n]{0,120}\b(?:separately|by|'
                     r'respective|billed|documented|submitted|reported)\b|\bfacility\s+and\s+(?:radiology|anesthesia)\s+'
                     r'services\s+are\s+billed\s+separately\b'
                     r'|\b(?:reports?|bills?|billed|submits?|claims?)\s+the\s+technical\s+component\b'
                     r'|\btechnical\s+component\b[^;\n]{0,60}\b(?:reported|billed|submitted|claimed)\s+by\b')),
)
# A sentence that denies another provider's service ("No anesthesia professional was involved", "no specimens were sent").
OTHER_PROVIDER_DENIED = _rx(r'\b(?:no|without|not|never|none)\b[^.;\n]{0,40}\b(?:an(?:a)?esthesi\w+|CRNA|MAC|specimens?|'
                            r'samples?|patholog\w*|radiolog\w*|facility)\b|\b(?:an(?:a)?esthesi\w+|CRNA|specimens?|samples?)\b'
                            r'[^.;\n]{0,40}\b(?:was|were)\s+not\b')
SEDATION_BY_ENDOSCOPIST_DENIED = _rx(r'\b(?:endoscopist|performing\s+physician|proceduralist)\s+(?:did\s+not|was\s+not|'
                                     r'never)\s+(?:administer|provide|give|supervise)\w*\b[^.;]{0,60}\bsedation\b'
                                     r'|\bendoscopist\s+did\s+not\s+provide\s+a\s+separately\s+documented\s+'
                                     r'moderate[- ]sedation\b')
BOX_ROW = _rx(r'(?P<subject>[A-Za-z][^\[\]\n]{2,80}?)\s*[:\-]?\s*\[(?P<a>[ xX✓✔])\]\s*(?P<la>performed|yes|done)'
              r'\s*\[(?P<b>[ xX✓✔])\]\s*(?P<lb>not\s+performed|no|not\s+done)\b')
PAGE_HEADER = _rx(r'^[^\n]{0,120}\|\s*[^\n]{0,120}\|\s*[^\n]{0,120}$')
# Any printed check box or option mark: a row with one is read by routing's hardened box reader (gi/detect.py), never
# by the clause words around it.
BOX_MARK = re.compile('(?:' + _box_symbols.BOX_OFF_PATTERN + '|' + _box_symbols.BOX_ON_PATTERN + '|'
                      + _box_symbols.BOX_UNREAD_PATTERN + ')')
BOX_STATUS = {'performed': 'performed', 'incomplete': 'performed', 'negated': 'negated', 'cancelled': 'cancelled',
              'planned': 'planned', 'historical': 'historical', 'uncertain': 'uncertain'}
# E/M: an evaluation documented as such, a note's own structure, and routine procedure-related work.
EM_EVALUATED = _rx(r'\b(?:evaluated|seen|examined|assessed|reviewed\s+in\s+clinic)\s+(?:today\s+)?(?:for|in|with)\b'
                   r'|\bpresents?\s+(?:today\s+)?(?:for|with)\b|\bfollow(?:s|ed)?[- ]?up\s+(?:visit|appointment)\b'
                   r'|\b(?:office|clinic|outpatient)\s+(?:visit|encounter|consultation)\b|\bhistory\s+of\s+present\s+illness\b'
                   r'|\bHPI\b|\bchief\s+complaint\b|\bnew\s+patient\s+(?:visit|evaluation)\b')
NOTE_STRUCTURE = re.compile(r'^[ \t]*(?:impression|assessment|plan|exam(?:ination)?|physical\s+exam(?:ination)?|history|'
                            r'HPI|chief\s+complaint|ROS|review\s+of\s+systems|medications|allergies)\b[^\n]{0,40}?[:\-]',
                            re.A | re.I | re.M)
from studio.gi.cues import EM_VISIT  # noqa: E402  (routing's own visit-statement words)
EM_ROUTINE = _rx(r'\broutine\s+pre-?procedur(?:e|al)\s+(?:history|assessment|evaluation|H&P|update)'
                 r'|\bno\s+separate\s+(?:problem-oriented\s+)?(?:evaluation|E/M|office[- ]visit)'
                 r'|\bnot\s+a\s+separate(?:ly\s+identifiable)?\s+(?:E/M|evaluation|visit)')


@dataclass(frozen=True)
class Reading:
    """How one clause states one thing: its status and the cues that decided it."""
    status: str  # one of ACT_STATUSES
    cues: tuple[str, ...] = ()


@dataclass(frozen=True)
class Act:
    id: str
    service: str  # the service id it belongs to
    kind: str  # one of ACT_KINDS
    status: str  # one of ACT_STATUSES
    role: str  # who documented it (ROLES)
    anatomy: tuple[str, ...] = ()
    region: str = ''
    technique: str = ''
    lesion: str = ''  # lesion id, '' when not directed at a documented lesion
    evidence: tuple[Span, ...] = ()
    cues: tuple[str, ...] = ()
    detail: str = ''  # e.g. "3 passes", "8 mm"


@dataclass(frozen=True)
class Lesion:
    id: str
    service: str
    noun: str
    size: str = ''
    morphology: str = ''
    anatomy: str = ''
    region: str = ''
    specimen: str = ''
    disposition: str = 'unknown'  # removed | sampled | untreated | scheduled | unknown
    evidence: tuple[Span, ...] = ()


@dataclass(frozen=True)
class ConflictSide:
    status: str
    role: str
    evidence: tuple[Span, ...]


@dataclass(frozen=True)
class Conflict:
    id: str
    service: str
    subject: str  # an act kind, or a context fact name
    lesion: str
    sides: tuple[ConflictSide, ...]
    note: str = ''


@dataclass(frozen=True)
class DocumentedService:
    id: str
    family: str
    kind: str
    status: str  # one of SERVICE_STATUSES
    completion: str = 'unknown'  # one of COMPLETIONS
    extent: str = ''
    intent: str = ''
    service_date: str = ''  # ISO date the document gives this service, '' when none
    clinician: str = ''
    setting: str = ''
    role: str = 'physician'
    evidence: tuple[Span, ...] = ()  # passages that establish the service itself
    completion_evidence: tuple[Span, ...] = ()
    cues: tuple[str, ...] = ()
    lesions: tuple[Lesion, ...] = ()
    acts: tuple[Act, ...] = ()
    uncertainty: tuple[str, ...] = ()
    routing_status: str = ''  # what routing (gi-routing) read for the family, for transparency; '' when none
    separate_em: bool = False  # an E/M: the document states a significant, separately identifiable E/M
    scope_start: int = 0  # the text that documents the service: its report part(s), else its own passages
    scope_end: int = 0
    included_in: str = ''  # another service of this encounter whose code includes this one (an EGD inside an EUS)


@dataclass(frozen=True)
class Attribution:
    """A service the document attributes to another provider or entity: never the performing physician's."""
    role: str  # anesthesia | pathology | radiology | facility
    evidence: tuple[Span, ...]


@dataclass(frozen=True)
class ServiceInventory:
    version: str
    services: tuple[DocumentedService, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    attributions: tuple[Attribution, ...] = ()
    problems: tuple[str, ...] = ()
    sedation_by_endoscopist: str = ''  # 'denied' when the document says the endoscopist provided none, else ''

    def service(self, service_id: str) -> Optional[DocumentedService]:
        return next((s for s in self.services if s.id == service_id), None)

    def for_family(self, family: str) -> tuple[DocumentedService, ...]:
        return tuple(s for s in self.services if s.family == family)


# --- structure ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Part:
    start: int
    end: int
    family: str  # the service a report part is about; '' outside a report
    role: str
    title: Optional[Span]
    kind: str  # report | history | plan | indication | other


def _lines(text: str) -> list[tuple[int, int]]:
    out, pos = [], 0
    for line in text.split('\n'):
        out.append((pos, pos + len(line)))
        pos += len(line) + 1
    return out


def _family_named(line: str, title: bool = True) -> tuple[str, str]:
    """The first service ``line`` names; read as a report title (``title``), a name only a title carries
    (TITLE_SERVICES) too."""
    for family, kind, pattern in SERVICES + (TITLE_SERVICES if title else ()):
        if pattern.search(line):
            return family, kind
    return '', ''


HISTORY_HEADING = _rx(r'^[\s\-*#]*(?:past\s+(?:medical|surgical|gi|procedural)\s+history|history|prior\s+(?:procedures|'
                      r'endoscopy|studies)|historical\s+procedures|previous\s+procedures|procedural\s+history)\b[^\n]{0,40}$')
# A span of earlier time that asks after another occurrence ("Colonoscopy in the last 10 years:", a screening question
# printed on a form): a line carrying one is never a bare service heading, which would read that question as today's
# service performed (a phantom service, listed unresolved and sent for a second review). Read for headings only: in a
# clause it can describe today's indication ("for bleeding over the last 2 weeks").
# The words a bare service heading may carry beside the service's own name ("Colonoscopy", "Colonoscopy report",
# "Upper endoscopy - findings"); any other word makes the line a field or a question ("Colonoscopy within 10 years:",
# "Last colonoscopy:", "Colonoscopy up to date:"), never a heading that opens a report of the service.
HEADING_VOCABULARY = _rx(r'\b(?:report|note|notes|procedure|procedures|findings|technique|impression|details|description|'
                         r'summary|narrative|results?|examination|exam|study|section|part|operative|fictional|synthetic)\b')
# A service's own attributes, which a heading of today's report carries beside its name (refutation r1, cluster S:
# "EGD (diagnostic):", "Screening colonoscopy:", "EGD performed:", "Colonoscopy to the cecum:" had opened no heading, so
# in a report of two services the acts under them were read for neither): its intent (the reader's INTENT_WORDS), its
# performance and its extent (a landmark, routing's own, with the words that lead to it).
HEADING_ATTRIBUTES = _rx(r'\b(?:screening|surveillance|diagnostic|therapeutic|symptom-?driven|performed|done|completed?|'
                         r"today(?:['’]s)?|this|to|into|through|the|of)\b")
LANDMARK_NAMES = tuple(pattern for _, _, pattern in _cues.UPPER_LANDMARKS + _cues.LOWER_LANDMARKS)

# The time a heading gives what it heads (refutation r1, cluster S), read from the heading's label and only where it
# qualifies the service or the record the heading names: a word of another time in front of it ("Prior colonoscopy",
# "Last colonoscopy", "Outside report", "Findings at prior colonoscopy", "Most recent screening EGD") or right after it
# with nothing else ("Colonoscopy due:", "Colonoscopy (prior):", "Colonoscopy history"), a date right after or right
# before it, alone or among such words ("Colonoscopy (2016)", "Colonoscopy report (2023-05-02)", "Outside report
# reviewed (03/2023)", "2016 colonoscopy"), a span of earlier time ("in the last 10 years") or "since". A word that
# qualifies something else on the line ("Colonoscopy at the prior polypectomy site", "Surveillance colonoscopy (adenoma
# removed 05/2023)") times nothing. A span that can run either way ("Colonoscopy within 10 years:", "in 3 years") asks.
_SERVICE_NAMES = '|'.join('(?:' + pattern.pattern + ')' for _, _, pattern in SERVICES)
HEADING_RECORD = (r'(?:reports?|notes?|records?|findings|results?|procedures?|studies|study|examinations?|exams?|summary|'
                  r'endoscop(?:y|ies)|patholog(?:y|ies))')
HEADING_EARLIER = (r'(?:prior(?![ \t]+to\b)|previous(?:ly)?|past|last|most[ \t]+recent|recent(?:ly)?|earlier|remote|index|'
                   r'outside|history[ \t]+of|hx[ \t]+of|h/o|s/p|status[ \t]+post)')
HEADING_LATER = (r'(?:next|planned|scheduled|future|upcoming|repeat|due|follow-?up|proposed|anticipated|tentative|'
                 r'requested|rescheduled)')
_NAMED = r'(?:' + _SERVICE_NAMES + r'|\b' + HEADING_RECORD + r'\b)'
# the words a heading's own date may stand among ("Prior colonoscopy (outside facility, 2023)", "Outside report
# reviewed (03/2023)"), and the spaces and marks between them one at a time (refutation r1 cost lens, ec5 cost: as
# "(?:[ \t,...]+|<word>)*" a run of spaces was tried in every way of sharing it among the repetitions - "Colonoscopy",
# 30 spaces and a word before a heading's date took the assess stage past its limit)
_DATE_COMPANIONS = (r'(?:[ \t,:\-–—(/]|\b(?:' + HEADING_EARLIER + r'|' + HEADING_LATER
                    + r'|facility|hospital|center|centre|institution|clinic|elsewhere|reviewed|dated|on|of|from|in|at|'
                      r'an?|the)\b)')
_ALONE_AFTER = r'(?:[ \t]+(?:facility|hospital|center|centre|institution|clinic|elsewhere))?[ \t]*(?:[),:]|\Z)'
HEADING_EARLIER_NAMED = _rx(r'\b' + HEADING_EARLIER + r'\b(?:[ \t]+[\w-]+){0,2}?[ \t]+' + _NAMED
                            + r'|' + _NAMED + r'[ \t]+(?:history|hx)\b'
                            + r'|' + _NAMED + r'[ \t,(\-\u2013]+' + HEADING_EARLIER + _ALONE_AFTER + r'|\bsince\b')
HEADING_LATER_NAMED = _rx(r'\b' + HEADING_LATER + r'\b(?:[ \t]+[\w-]+){0,2}?[ \t]+' + _NAMED
                          + r'|' + _NAMED + r'[ \t,(\-\u2013]+' + HEADING_LATER + _ALONE_AFTER)
HEADING_DATE_BEFORE = _rx(_NAMED + _DATE_COMPANIONS + r'*\Z')  # the label up to a date: the date dates what it names
HEADING_DATE_AFTER = _rx(r'(?:[ \t,:\-–—)]|\b(?:an?|the)\b)*' + _NAMED)  # a date that leads the name (a mark at a time)
# A heading that asks rather than heads ("Colonoscopy up to date:", "Biopsy?"), doubts, cancels or denies: never a
# heading of today's report.
HEADING_DOUBT = _rx(r'\?|\b(?:ever|overdue|up[ \t-]+to[ \t-]+date|not|no|never|none|without)\b'
                    r'|\b(?:in|within|over|during|after|every)[ \t]+(?:the[ \t]+)?(?:(?:last|past|next|previous|preceding)'
                    r'[ \t]+)?(?:\d{1,3}|a|few|several|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[ \t]+'
                    r'(?:years?|months?|weeks?|days?)\b')


def _heading_time(text: str, ls: int, le: int, service_date: Optional[date], dates, date_starts) -> str:
    """The time the heading on [ls, le) gives what it heads: 'earlier' (before this encounter), 'later', 'unknown' (a
    date of its own that cannot be placed - no service date, or a month or year of the service date's own - or a
    question, a doubt, a cancellation or a denial), 'today' (its own date is the service date) or '' (it names no
    time). Only its first 100 characters are read, and the document's own date mentions (``dates``, sorted by start,
    with their ``date_starts``) are looked up by bisection, so the work per heading is bounded."""
    le = min(le, ls + 100)
    label = text[ls:le]
    if HEADING_EARLIER_NAMED.search(label) or EARLIER_SPAN.search(label):
        return 'earlier'
    if HEADING_LATER_NAMED.search(label):
        return 'later'
    if HEADING_DOUBT.search(label) or HEDGE_WORDS.search(label) or CANCEL_WORDS.search(label):
        return 'unknown'
    found = ''
    for d in dates[bisect.bisect_left(date_starts, ls):]:
        if d.start >= le:
            break
        if not (HEADING_DATE_BEFORE.search(text, ls, d.start) or HEADING_DATE_AFTER.match(text, d.end, le)):
            continue  # a date of something else on the line ("adenoma removed 05/2023")
        if service_date is None or d.precision != 'day' and gi_context.compare_to_service(d, service_date) == 0:
            return 'unknown'
        rel = gi_context.compare_to_service(d, service_date)
        if rel:
            return 'earlier' if rel < 0 else 'later'
        found = 'today'
    return found


def _bare_service_heading(text: str, ls: int, le: int, family: str, *, service_date: Optional[date], dates, date_starts,
                          documented: frozenset) -> bool:
    """Whether a heading-like label line (one that ends in ":" or "?", parts()) naming one service, ``family``, is that
    service's heading in today's report. Never when it gives another time, asks, doubts, cancels or denies
    (_heading_time: triage round 2 skeptic - an office note's screening questions about earlier examinations,
    "Colonoscopy within 10 years:", "Last colonoscopy:", had opened phantom performed services and paid second reviews;
    refutation r1 - "Colonoscopy report (2023-05-02):", "Colonoscopy (2016):"). Otherwise when it carries the service's
    name, its acts, heading vocabulary, the service's own attributes and the service date alone; or, whatever else it
    carries, when the document already lists the service as done on a procedure line or titles its report with it
    (``documented``), so the heading names no service the document does not document today (refutation r1: "EGD
    (diagnostic):", "Colonoscopy (screening):"). A title with no colon keeps its other words ("ERCP (UNSUCCESSFUL)",
    "ESOPHAGEAL MANOMETRY REPORT (HIGH RESOLUTION)"). Bounded: one pass of each pattern over at most 100 characters."""
    if _heading_time(text, ls, le, service_date, dates, date_starts) not in ('', 'today'):
        return False
    rest = text[ls:min(le, ls + 100)]
    for _, _, pattern in SERVICES:
        rest = pattern.sub(' ', rest)
    for _, pattern in ACTS:  # "EGD with biopsy", "Colonoscopy with cold snare polypectomy and tattoo"
        rest = pattern.sub(' ', rest)
    for pattern in LANDMARK_NAMES + (HEADING_VOCABULARY, HEADING_ATTRIBUTES, gi_context.FULL_DATE):
        rest = pattern.sub(' ', rest)  # the date left is the service date (_heading_time)
    rest = re.sub(r'\b(?:with|and|plus|cold|hot|and/or)\b', ' ', rest, flags=re.I)
    return not re.search(r'[A-Za-z]{2,}', rest) or family in documented


EARLIER_SPAN = _rx(r'\b(?:in|within|over|during)\s+the\s+(?:last|past|previous|preceding)\s+'
                   r'(?:\d{1,3}|few|several|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+'
                   r'(?:years?|months?|weeks?|days?)\b')
PLAN_HEADING = _rx(r'^[\s\-*#]*(?:plan|plans|recommendations?|assessment\s+and\s+plan|disposition\s+and\s+plan'
                   r'|follow-?up\s+plan)\s*:?\s*$')


def _documented_today(text: str, lines, service_date: Optional[date], dates, date_starts) -> frozenset:
    """The families the document lists as done on a procedure line ("Procedures: EGD and colonoscopy") or titles its
    report with ("Colonoscopy report"), on a line that gives no other time and outside a plan or history section: a
    heading naming one of them is that service's heading whatever qualifier it carries (_bare_service_heading). One pass
    over the lines of at most 100 characters."""
    lay = _sections.layout(text)
    found = set()
    for ls, le in lines:
        line = text[ls:le]
        if not line.strip() or len(line.strip()) > 100:
            continue
        named = PROCEDURE_FIELD.match(line) or (REPORT_TITLE.match(line) or TITLE_FIELD.match(line)
                                                or TITLE_REPORT_WORDS.match(line))
        if not named or PLAN_WORDS.search(line) or HISTORY_WORDS.search(line) \
                or _heading_time(text, ls, le, service_date, dates, date_starts) not in ('', 'today') \
                or lay.section_at(ls).kind in ('plan', 'history'):
            continue
        found.update(f for f, _, pattern in SERVICES if pattern.search(line))
    return frozenset(found)


def parts(text: str, *, service_date: Optional[date] = None, dates=None) -> tuple[_Part, ...]:
    """The document cut into report parts (a part about one service, from its title to the next title), role parts
    (a nursing, anesthesia, pathology or radiology entry, to the next heading) and other text. A history or plan part
    never runs into today's report: a history part ends at the line routing's sections read as a procedure heading
    when today's report goes on under it ("Procedure: Colonoscopy with cold snare polypectomy." after "History:", then a
    findings, technique or impression heading: _opens_todays_report), and an extraction block ("[PDF form fields on
    page 1]") interrupts a history or plan part as text of no time, its lines opening no part, until the blank line
    that ends the block, where the part resumes (routing reads both the same way: gi/sections layout). A sentence
    whose history words are its own subject ("Prior studies have been inconclusive.") opens a history part only where
    the layout opens a section on its line: it is no heading of what follows (refutation 7c8, formats-5 a)."""
    lay = _sections.layout(text)
    by_start = sorted(lay.sections, key=lambda section: section.start)
    layout_starts = [section.start for section in by_start]
    cuts: list[tuple[int, str, str, Optional[Span], str]] = [(0, '', 'physician', None, 'other')]
    family, kind_now = '', 'other'
    resume_after_block = None  # the history or plan part an extraction block interrupted
    lines = _lines(text)
    dates = gi_context.find_dates(text) if dates is None else dates
    date_starts = [d.start for d in dates]
    documented = _documented_today(text, lines, service_date, dates, date_starts)
    for index, (ls, le) in enumerate(lines):
        line = text[ls:le]
        stripped = line.strip()
        if resume_after_block is not None:
            if not stripped:
                cuts.append((ls, *resume_after_block))
                resume_after_block = None
            continue  # an extraction block's lines open no part of their own
        if not stripped or len(stripped) > 100:
            continue
        if cuts[-1][4] in ('history', 'plan') and _sections.FORM_BLOCK.fullmatch(stripped):
            resume_after_block = (cuts[-1][1], cuts[-1][2], None, cuts[-1][4])
            cuts.append((ls, '', 'physician', None, 'other'))
            continue
        if cuts[-1][4] == 'history' and _opens_todays_report(text, lines, index):
            # today's procedure line ends the history before it ("History:" ... "Procedure: Colonoscopy ...")
            cuts.append((ls, family, 'physician', None, kind_now if family else 'other'))
        if PAGE_HEADER.match(stripped) and stripped.count('|') >= 2:
            continue
        role = next((r for r, p in ROLE_HEADINGS if p.match(line)), None)
        if role:
            cuts.append((ls, family, role, Span(ls + line.index(stripped), ls + line.index(stripped) + len(stripped),
                                                stripped), 'role'))
            continue
        numbered = PART_NUMBER.match(line)
        body = line[numbered.end():] if numbered else line
        m = REPORT_TITLE.match(body) or TITLE_FIELD.match(body) or TITLE_REPORT_WORDS.match(body)
        named, _ = _family_named(line) if m else ('', '')
        field_m = PROCEDURE_FIELD.match(line)
        if m and named and not PLAN_WORDS.search(line) and not HISTORY_WORDS.search(line):
            family = named
            s = ls + line.index(stripped)
            cuts.append((ls, family, 'physician', Span(s, s + len(stripped), stripped), 'report'))
            kind_now = 'report'
            continue
        if not m and GENERIC_HEADING.match(line) and not PLAN_WORDS.search(line) and not HISTORY_WORDS.search(line) \
                and not EARLIER_SPAN.search(line) \
                and not HISTORY_HEADING.match(line) and not PLAN_HEADING.match(line):
            heading_families = {f for f, _, p in SERVICES if p.search(line)}
            if len(heading_families) == 1 and len(stripped) <= 60 \
                    and (not stripped.endswith((':', '?')) or _bare_service_heading(
                        text, ls, le, next(iter(heading_families)), service_date=service_date, dates=dates,
                        date_starts=date_starts, documented=documented)):
                s = ls + line.index(stripped)
                cuts.append((ls, next(iter(heading_families)), 'physician', Span(s, s + len(stripped), stripped),
                             'section'))
                continue
            if cuts[-1][4] == 'section':
                # A bare service heading ("Colonoscopy") owns the lines up to the next heading; the encounter's shared
                # sections after it (Complications, Impression, Plan) belong to no one service.
                cuts.append((ls, family, 'physician', None, kind_now if family else 'other'))
                continue
        if HISTORY_HEADING.match(line):
            if stripped.endswith(('.', '!', '?')) and _sections._own_clause(stripped) \
                    and _inside_a_labelled_section(by_start, layout_starts, ls, le):
                # refutation 7c8, formats-5 (a): the PDF writer's wrap set "Prior studies have been inconclusive." at
                # the start of a line inside an indication, and it opened a history part that dated the pH capsule
                # placed today as history (no unresolved item, coding complete); a complete sentence routing's layout
                # reads inside a labelled section that goes on across it heads nothing
                continue
            cuts.append((ls, family, 'physician', None, 'history'))
            continue
        if PLAN_HEADING.match(line) and not family:
            cuts.append((ls, family, 'physician', None, 'plan'))
            continue
        if GENERIC_HEADING.match(line) and cuts[-1][4] == 'role':
            cuts.append((ls, family, 'physician', None, kind_now if family else 'other'))
        del field_m
    out = []
    for i, (start, fam, role, title, kind) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(text)
        if kind == 'section':
            kind = 'report'
        if end > start:
            out.append(_Part(start, end, fam, role, title, 'report' if kind == 'role' and fam else kind))
    return _time_parts(text, out, lay)


def _inside_a_labelled_section(by_start, starts: Sequence[int], ls: int, le: int) -> bool:
    """Whether routing's layout reads the line [ls, le) inside a section a heading opened above it (an
    "Indication:" paragraph) that goes on across the line, with no section of its own opening on it (one bisection)."""
    at = bisect.bisect_right(starts, le) - 1
    if at < 0:
        return False
    section = by_start[at]
    return section.start < ls and section.end > le and section.heading is not None and section.kind != 'other'


def _time_parts(text: str, plist: Sequence[_Part], lay=None) -> tuple[_Part, ...]:
    """The parts with their history and plan sections where routing's section layout (studio.gi.sections, the structure
    the refutation rounds hardened: inline and wrapped labels, field labels, held lines) puts them, from where such a
    section opens to where it ends. "Prior colonoscopies:", "Past history:", "Impression and Recommendations:",
    "Procedures to be done:" and "Plan: Dr. Smith recommended" open one; the next section the layout opens ("Findings:")
    ends it, as it ends a history or plan part this module's own headings opened. A heading the layout adds whose own
    line already carries a complete statement ("History: an outside EUS-guided biopsy showed adenocarcinoma.") speaks
    for that line only, as a field does. A part keeps its family, role and title; a role part keeps its reading, and a
    plan section inside a titled report stays that report's (its title owns its subsections, as PLAN_HEADING has it)."""
    lay = _sections.layout(text) if lay is None else lay
    timed = [(s.start, _time_end(text, s), s.kind) for s in lay.sections if s.kind in ('history', 'plan')]
    timed += [(s.start, min(_time_end(text, s), _paragraph_end(text, s)), s.kind) for s in lay.sections
              if s.kind == 'indication']
    marks = {m for start, end, _ in timed for m in (start, end)}
    ends = {}
    # Every lookup below is a bisection over sorted starts (refutation r1, cost: scanning every section, mark and timed
    # section for each part and piece was quadratic: 195,000 characters of "History:/Plan:" took 42 s).
    section_starts = [s.start for s in lay.sections]
    for p in plist:
        if p.kind in ('history', 'plan') and p.role == 'physician':
            # this module's own heading opened it: it ends where the layout opens another section
            at = bisect.bisect_right(section_starts, p.start)
            ends[p.start] = section_starts[at] if at < len(section_starts) and section_starts[at] < p.end else p.end
            marks.add(ends[p.start])
    marks = sorted(marks)
    timed_sorted = sorted(timed)
    timed_starts = [start for start, _, _ in timed_sorted]

    def timed_kind(pos: int) -> str:
        """The kind of the timed section holding ``pos`` ('' for none): the layout's sections never overlap."""
        at = bisect.bisect_right(timed_starts, pos) - 1
        while at >= 0:  # sections that start at the same place: the first whose span holds pos, in list order
            start, end, kind = timed_sorted[at]
            if start <= pos < end:
                return kind
            if at == 0 or timed_starts[at - 1] != start:
                return ''
            at -= 1
        return ''

    out: list[_Part] = []
    for p in plist:
        lo, hi = bisect.bisect_right(marks, p.start), bisect.bisect_left(marks, p.end)
        edges = [p.start] + marks[lo:hi] + [p.end]
        pieces: list[_Part] = []
        for a, b in zip(edges, edges[1:]):
            kind = _time_kind(p, a, timed_kind, ends.get(p.start))
            if pieces and pieces[-1].kind == kind:
                pieces[-1] = replace(pieces[-1], end=b)
            else:
                pieces.append(_Part(a, b, p.family, p.role, p.title if a == p.start else None, kind))
        out.extend(pieces)
    return tuple(out)


TODAYS_REPORT_REACH = 12  # non-empty lines after a procedure heading read for today's report going on under it


def _opens_todays_report(text: str, lines: Sequence[tuple[int, int]], index: int) -> bool:
    """Whether line ``index`` is a procedure heading (routing's sections: "Procedure: Colonoscopy with cold snare
    polypectomy.", "PROCEDURE PERFORMED:") under which today's report goes on: within TODAYS_REPORT_REACH non-empty
    lines a findings, technique or impression heading follows, before any history or plan heading or report title. A
    history entry's own procedure field ("Procedure: colonoscopy (outside), polyps removed." before "Upper endoscopy
    report") stays history."""
    heading = _sections._heading(text, *lines[index])
    if heading is None or heading[0] != 'procedure':
        return False
    seen = 0
    for ls, le in lines[index + 1:]:
        line = text[ls:le]
        if not line.strip():
            continue
        seen += 1
        if seen > TODAYS_REPORT_REACH:
            return False
        if REPORT_TITLE.match(line) or TITLE_FIELD.match(line) or TITLE_REPORT_WORDS.match(line) \
                or HISTORY_HEADING.match(line) or PLAN_HEADING.match(line):
            return False
        following = _sections._heading(text, ls, le)
        if following is not None and following[0] in ('history', 'plan'):
            return False
        if following is not None and following[0] in ('findings', 'technique', 'impression'):
            return True
    return False
def _time_end(text: str, section) -> int:
    """Where a history or plan section of the layout stops dating what it holds: its end, or the end of its heading's
    line when that line carries a complete statement after the heading."""
    line_end = text.find('\n', section.start, section.end)
    line_end = section.end if line_end < 0 else line_end
    if section.heading is not None and section.heading.end <= line_end:
        content = text[section.heading.end:line_end].strip()
        if content and content[-1] in '.!?':
            return min(section.end, line_end + 1)
    return section.end


def _paragraph_end(text: str, section) -> int:
    """Where an indication stops: its heading line and the lines after it up to a blank line or a line that reads as
    another heading. The layout runs an indication on over a report's own headings it does not know ("OPERATIVE
    DETAILS", "NARRATIVE"), and what follows them is today's report."""
    nl = text.find('\n', section.start, section.end)
    pos = section.end if nl < 0 else nl + 1
    while pos < section.end:
        nl = text.find('\n', pos, section.end)
        line_end = section.end if nl < 0 else nl
        line = text[pos:line_end]
        if not line.strip() or GENERIC_HEADING.match(line):
            return pos
        pos = line_end + 1
    return section.end


def _time_kind(p: _Part, pos: int, timed_kind, own_end: Optional[int]) -> str:
    if p.role != 'physician' or p.kind == 'role':
        return p.kind
    kind = timed_kind(pos)
    if kind == 'history':
        return 'history'
    if kind == 'plan':
        return p.kind if p.kind == 'report' else 'plan'
    if kind == 'indication' and p.kind == 'other':
        return 'indication'  # why the patient came (never inside a titled report, whose subsections are its own)
    if p.kind in ('history', 'plan') and own_end is not None and pos >= own_end:
        return 'report' if p.family else 'other'  # the history or plan this module's heading opened has ended
    return p.kind


def _part_at(plist: Sequence[_Part], starts: Sequence[int], pos: int) -> _Part:
    i = bisect.bisect_right(starts, pos) - 1
    return plist[max(i, 0)]


def _answered_line(text: str, ls: int, le: int, nxt: int) -> bool:
    """Whether the line [ls, le) ends in an answer of its own, read with routing's own answer readers (gi/sections:
    _answered, _OPTION_ROW, the spoken answer), so the two readers never disagree: a field answered with a lone negation
    or a short value ending in a denial ("Hiatal hernia - no", "Hiatal hernia \u2013 no", "Hiatal hernia? no",
    "Sedation: patient declined"), a column answer ("Hiatal hernia\tno"), an option row ("Biopsy taken [ ] Yes [x] No")
    or a spoken answer before a line that opens a clause of its own ("the patient said no" / "Colonoscopy was then
    performed"). Its "no" is the answer, never a negation of the next line's act (round 3 routing:1, round 4
    structure:1 and structure:3). A next line in lower case still runs on (round 4 structure:2: routing holds that
    negation across the break). The line is read after any heading label on it, as routing reads it, and only its
    last WRAP_TAIL characters (bounded work per line)."""
    heading = _sections._heading(text, ls, le)
    content = heading[2].end if heading and ls <= heading[2].end <= le else ls
    before = text[content:le].rstrip()
    reach = min(len(text), nxt + _sections.OWN_CLAUSE_REACH)
    line_end = text.find('\n', nxt, reach)
    after = text[nxt:line_end if line_end >= 0 else reach].lstrip()
    if not before or not after or after[0].islower():
        return False
    tail = before[-_sections.WRAP_TAIL:]
    if _sections._answered(before if len(before) <= _sections.WRAP_TAIL else tail) or _sections._OPTION_ROW.search(tail):
        return True
    return bool(_sections._SEC_SPOKEN_ANSWER.search(tail) and _sections._own_clause(after))


# A row of a two-column table: the DOCX reader writes one line per table row, its cells joined by " | " (studio/ingest/
# docx.py), and a typed table is written the same way ("Checklist item | Nursing entry" / "Tattoo injected | No"). The
# line has exactly one cell bar with a letter or digit on either side of it (three or more cells are a page header or
# another table's row, read as before), and at most TABLE_ROW_CHARS characters (a longer line is read as prose). Its
# first cell is a label, its second the entry for it (gi2 conflicts, PR2).
TABLE_ROW_CHARS = 400
_CELL_WORD = re.compile(r'[A-Za-z0-9]')


def _table_row_bar(text: str, ls: int, le: int) -> int:
    """The offset of the cell bar of the line [ls, le) when that line is a row of a two-column table, else -1. Bounded:
    at most TABLE_ROW_CHARS characters are read."""
    if le <= ls or le - ls > TABLE_ROW_CHARS:
        return -1
    bar = text.find('|', ls, le)
    if bar < 0 or text.find('|', bar + 1, le) >= 0:
        return -1
    if not _CELL_WORD.search(text, ls, bar) or not _CELL_WORD.search(text, bar + 1, le):
        return -1
    return bar


def _next_line_is_a_table_row(text: str, i: int) -> bool:
    """Whether the line after the newline at ``i`` is a two-column table row (bounded as _table_row_bar)."""
    end = text.find('\n', i + 1, i + 2 + TABLE_ROW_CHARS)
    if end < 0:
        end = len(text) if len(text) - (i + 1) <= TABLE_ROW_CHARS else -1
    return end >= 0 and _table_row_bar(text, i + 1, end) >= 0


def _sentences(text: str) -> list[tuple[int, int]]:
    """Sentences: split at a full stop, question or exclamation mark followed by space and a capital or digit or a
    list label, at a line that starts a numbered or labelled item, after a line that ends in an answer of its own
    (_answered_line), and at blank lines. Line wraps inside a sentence are kept (PDF text wraps mid-sentence). A
    check-box row is a sentence of its own, and so is a two-column table row next to another: what one row's entry says
    never reaches the next row."""
    out: list[tuple[int, int]] = []
    start = 0
    n = len(text)
    i = 0
    in_block = False  # inside an extraction block ("[PDF form fields on page 1]" to the blank line that ends it)
    abbreviations = ('Dr', 'Mr', 'Mrs', 'Ms', 'vs', 'approx', 'e.g', 'i.e', 'St', 'No', 'Fig')
    while i < n:
        ch = text[i]
        cut = None
        if ch in '.!?':
            j = i + 1
            while j < n and text[j] in ' \t':
                j += 1
            if j >= n or text[j] == '\n' or text[j].isupper() or text[j].isdigit() or text[j] in '"(“[':
                # the word before the stop, read from at most its last seven characters (refutation r1, cost: reading
                # the whole sentence at every stop that does not end it - "7.45 7.46 ..." - was quadratic)
                decimal = ch == '.' and i > 0 and text[i - 1].isdigit() and j < n and text[j].isdigit()
                word = None if decimal else re.search(r'([A-Za-z.]{1,6})$', text[max(start, i - 7):i])
                if not decimal and not (word and word.group(1).rstrip('.') in abbreviations and ch == '.'):
                    cut = i + 1
        elif ch == '\n':
            nxt = text[i + 1:i + 40]
            # the line the newline ends, never the sentence before it (refutation r1, cost: after a line longer than
            # 400 characters this was the whole sentence so far, read again at every newline)
            prev_line_text = text[max(text.rfind('\n', 0, i) + 1, start):i]
            ended = text[text.rfind('\n', 0, i) + 1:i].strip()
            in_block = bool(_sections.FORM_BLOCK.fullmatch(ended)) or (in_block and bool(ended))
            if in_block:
                cut = i  # an extraction block's lines are each a sentence, never one field run on into the next
            elif BOX_MARK.search(prev_line_text) or BOX_MARK.search(text, i + 1, min(n, i + 200)) and \
                    BOX_MARK.search(text[i + 1:text.find('\n', i + 1) if text.find('\n', i + 1, i + 400) >= 0
                                         else min(n, i + 400)]):
                cut = i  # a check-box or option row never runs on into the next line, nor another into it
            elif _table_row_bar(text, text.rfind('\n', 0, i) + 1, i) >= 0 and _next_line_is_a_table_row(text, i):
                # one table row never runs on into the next (gi2 conflicts, PR2: in a nursing checklist "Tattoo
                # injected | No" had run on into "Snare polypectomy | Yes", whose snare its "No" then negated - a false
                # snare conflict - while the tattoo itself was read done from "injected"). Only between two rows: a row
                # a PDF writer wrapped goes on in a line of no bar, or of one bar when the row has more cells ("1 |
                # Transverse colon | 12 mm sessile | Resected en bloc with a hot" / "snare | Jar A"), read as before.
                cut = i
            elif re.match(r'[ \t]*[A-Z][A-Za-z /&()\-]{1,40}:[ \t]+\S', nxt) \
                    or (re.match(r'[ \t]*[A-Z][A-Za-z /&()\-]{1,40}:[ \t]+\S', prev_line_text)
                        and not re.match(r'[ \t]*[a-z(]', nxt)):
                # a "Label: value" field line is a sentence of its own, unless its value wraps onto a line that
                # continues it ("Rectum: a separate 4 mm lesion ... biopsy for" / "histology (jar B).")
                cut = i
            elif re.match(r'\s*\n', nxt) or re.match(r'[ \t]*(?:[A-Z]{1,3}\d{1,2}\s|\d{1,2}[.)]\s|[-*•]\s)', nxt) \
                    or (re.match(r'[ \t]*[A-Z][A-Za-z /&,()\-]{1,60}:?[ \t]*(?:\n|$)', text[i + 1:i + 80])
                        and not text[start:i].rstrip().endswith(',')):
                cut = i
            elif _answered_line(text, text.rfind('\n', 0, i) + 1, i, i + 1):
                cut = i  # "Hiatal hernia \u2013 no" / "Biopsies were taken ...": the answer ends its line's sentence
            elif _opens_a_sentence(text, i):
                cut = i  # "No polyps; no masses" / "Biopsies were taken.": a paragraph with no blank line before it
            else:
                prev_line = text[text.rfind('\n', 0, i) + 1:i].strip()
                if prev_line and (prev_line.endswith(':') or GENERIC_HEADING.match(prev_line)) \
                        and len(prev_line) < 70 and not prev_line.endswith(','):
                    cut = i
        if cut is not None:
            seg = _trim(text, start, cut)
            if seg:
                out.append(seg)
            start = cut
        i += 1
    seg = _trim(text, start, n)
    if seg:
        out.append(seg)
    return out


def _trim(text: str, start: int, end: int) -> Optional[tuple[int, int]]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _span(text: str, start: int, end: int) -> Span:
    return Span(start, end, text[start:end])


# --- clause reading -------------------------------------------------------------------------------------------------

# What a coordinated, relative or absolute predicate with a time of its own is made of (_CLAUSE_CUT's own_time, 7c8
# skeptic sk:2): its opener, one word of it (an abbreviation's period allowed: "H. pylori"; possessive, so a long word is
# read once), a plan or cancel participle, never one after "as" ("as planned" is the booking an act kept, cues.
# AS_BOOKED_BEFORE), and the predicate itself.
_OWN_TIME_OPENER = r'(?:\s++and\s++|,\s*+(?:and\s++)?(?:(?:which|that|where)\s++)?|\s++(?:which|that|where)\s++)'
_OWN_TIME_WORD = r"[\w'/-]++\.?\s++"
_OWN_TIME_NOT_AS = r'(?!as\b)'
_OWN_TIME_PLAN = r'(?:cancel(?:l)?ed|declined|refused|deferred|postponed|planned|scheduled|recommended|arranged)'
_OWN_TIME_PREDICATE = (r'(?:' + _OWN_TIME_WORD + r'){0,4}?(?:will|shall|should|may|might|must)\b'
                       r'|(?:' + _OWN_TIME_WORD + r'){0,4}?(?:was|were|is|are|has\s+been|have\s+been)\s+(?:[\w-]+ly\s+)?'
                       + _OWN_TIME_PLAN + r'\b'
                       r'|(?:' + _OWN_TIME_NOT_AS + _OWN_TIME_WORD + r'){1,3}?' + _OWN_TIME_PLAN + r'\b'
                       r'|(?:we|I|they)\s+(?:plan|plans|intend|intends|recommend|recommends)\b')
_CLAUSE_CUT = _rx(r';|\s+but\s+|\s+whereas\s+|\s+although\s+|,\s+while\s+'
                  r'|\s+and\s+(?=(?:was|were|is|are)(?:\s+(?:not|never)|' + NEG_CONTRACTION + r')\b)'
                  # "Biopsies were obtained and dilation was not performed": a coordinated subject with its own negated
                  # predicate opens a clause of its own, so its "not" never reaches the first act
                  r'|\s+and\s+(?=(?:[\w-]+\s+){1,3}(?:was|were|is|are|could|did|had)(?:\s+(?:not|never)|'
                  + NEG_CONTRACTION + r')\b)'
                  r'|(?<![\d.])\s+and\s+(?=(?:the|a|an|this|that|it|she|he|they|we|I|one|two|three|\d+)\b[^.;]{0,60}\b(?:was|were|'
                  r'is|are|has|have|had|did)(?:' + NEG_CONTRACTION + r')?\b)|,\s+(?=(?:and\s+)?(?:the|this|that|it|she|he|they|'
                  r'we|I)\s+[^.;,]{0,40}\b(?:was|were|is|are)(?:' + NEG_CONTRACTION + r')?\b)'
                  # refutation r1, negtime-4: a coordinated predicate with a time or a cancellation of its own - a future
                  # ("and will be sent to pathology", "and we will follow up") or its own subject's plan or cancel
                  # predicate ("and dilation was deferred", "and repeat EGD is planned") - opens a clause of its own, so
                  # its word never dates the act the first predicate states done ("Cold forceps biopsies were obtained
                  # from the antrum and will be sent to pathology" had excluded 43239 as planned). Only after an act
                  # predicate stated before it (clauses()): "Biopsy and polypectomy will be performed" stays one clause.
                  # 7c8 skeptic, sk:2: by its structure, not two wordings - opened by "and", a comma, a relative word or
                  # an absolute "with" (_OWN_TIME_OPENER), it is a modal of its own ("and results should be available
                  # next week", ", which will be sent", "and H. pylori treatment will depend"), an auxiliary and a plan
                  # or cancel participle ("and are scheduled"), a participle with its own subject and no auxiliary ("and
                  # dilation deferred", "with repeat colonoscopy recommended") or a pronoun's plan ("and we plan").
                  r'|(?P<own_time>' + _OWN_TIME_OPENER + r'(?=' + _OWN_TIME_PREDICATE + r')'
                  r'|\s++with\s++(?=(?:' + _OWN_TIME_NOT_AS + _OWN_TIME_WORD + r'){1,3}?' + _OWN_TIME_PLAN + r'\b))')


def _bounded_clause(text: str, clause: tuple[int, int], pos: int, end: int) -> tuple[int, int]:
    """The part of a clause within CLAUSE_REACH characters of the mention, cut at whitespace."""
    cs, ce = clause
    lo, hi = max(cs, pos - CLAUSE_REACH), min(ce, end + CLAUSE_REACH)
    if lo > cs:
        space = text.find(' ', lo, pos)
        lo = space + 1 if space >= 0 else pos
    if hi < ce:
        space = text.rfind(' ', end, hi)
        hi = space if space >= 0 else end
    return lo, hi


# Where a cut can begin: every _CLAUSE_CUT alternative opens with a semicolon, a comma or a run of whitespace.
_CUT_START = re.compile(r'[;,]|\s+', re.A)


class _Clause(tuple):
    """A clause (start, end) that an own_time cut (_CLAUSE_CUT) joins to coordinated predicates of its sentence, with
    ``joined``: the span of those joined clauses together. The cut gives each predicate its own time, plan and cancel
    words, never the sentence's TODAY word: whether the sentence says today is read over the joined span (read_clause;
    7c8 skeptic, sk:1: "Biopsies were taken as recommended and will be sent to pathology today" had lost "today" to the
    cut, so "as recommended" dated the biopsy and 43239 was newly excluded)."""

    joined: Optional[tuple[int, int]] = None


def _join(out: list, first: int) -> None:
    """Mark the clauses out[first:] as one own_time-joined run (_Clause.joined), when there are two or more."""
    if len(out) - first < 2:
        return
    span = (out[first][0], out[-1][1])
    for i in range(first, len(out)):
        out[i] = _Clause(out[i])
        out[i].joined = span


def clauses(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """[start, end) cut at _CLAUSE_CUT into trimmed clauses. A run of whitespace is tried as a cut from its first
    character and its second only (refutation r1, cost-6: tried from each of its characters, every try read the run to
    its end again - one counted mention and a run of 60,000 spaces in its sentence took the assess stage to 94 s, and
    120,000 past its limit). From any later character of the run a cut reads as from its second: the character before
    it is whitespace (the lookbehind's "not after a digit" holds) and the run's end and the words after it are the same.
    So the cuts are the ones a try from every character found."""
    out, pos, at = [], start, start
    # A coordinated predicate with its own time (_CLAUSE_CUT's own_time) is cut only after an act predicate stated
    # since the last cut; the search for it resumes where it stopped (a 60-character overlap keeps a predicate that
    # straddles the stop), so a long sentence of such coordinations is read once, never again from its start.
    stated, scanned = False, start
    joined = None  # the index in ``out`` of the first clause of a run an own_time cut joins (_Clause)
    while True:
        lead = _CUT_START.search(text, at, end)
        if lead is None:
            break
        m = _CLAUSE_CUT.match(text, lead.start(), end)
        if m is None and lead.end() - lead.start() > 1:
            m = _CLAUSE_CUT.match(text, lead.start() + 1, end)  # "at 30  and the polyp was": after a digit
        if m is None:
            at = lead.end()
            continue
        if m.lastgroup == 'own_time':
            if not stated:
                lo = max(pos, scanned - 60)
                stated = bool(ACT_VERB.search(text, lo, m.start()) or BARE_PARTICIPLE.search(text, lo, m.start()))
                scanned = m.start()
            if not stated:
                at = m.end()  # not a cut: the search resumes after it, as finditer's did
                continue
        seg = _trim(text, pos, m.start())
        if seg:
            out.append(seg)
        if m.lastgroup == 'own_time':
            if joined is None and seg:
                joined = len(out) - 1
        elif joined is not None:
            _join(out, joined)
            joined = None
        pos = at = m.end()
        stated, scanned = False, pos
    seg = _trim(text, pos, end)
    if seg:
        out.append(seg)
    if joined is not None:
        _join(out, joined)
    return out or [(start, end)]


def _clause_for(cls: Sequence[tuple[int, int]], pos: int) -> tuple[int, int]:
    for c in cls:
        if c[0] <= pos < c[1]:
            return c
    return cls[-1] if cls else (pos, pos)


def _dates_in(dates, start: int, end: int):
    lo = bisect.bisect_left([d.start for d in dates], start)
    out = []
    for d in dates[lo:]:
        if d.start >= end:
            break
        out.append(d)
    return out


def _verbal_predicate(text: str, whole: str, before: str, after: str, pos: int, end: int) -> bool:
    """Whether a clause states an act through a verb (read_clause's performed test, without its nominal form: a
    nominal act - "Balloon dilation of the stricture would have been performed" - takes the tense of its verb)."""
    return bool(ACT_VERB.search(whole) or BARE_PARTICIPLE.search(after) or BARE_PARTICIPLE.search(before[-40:])
                or BARE_PARTICIPLE.fullmatch(text[pos:end].strip()))


def _ability_realized(text: str, a: int, b: int, cs: int, ce: int, report: bool) -> bool:
    """Whether the modal predicate at [a, b) of the clause [cs, ce) states an ability today's narrative realized: a
    "could"/"can be" form (ABILITY), no condition governing the clause, and the clause is in today's report, in a
    procedure, findings, technique or impression section (routing's layout, as _nominal_act reads it), or states
    something else done in the past tense ("... and was then terminated")."""
    if not ABILITY.match(text, a, b) or CONDITION_IN_CLAUSE.search(text, cs, ce):
        return False
    if report or PAST_STATEMENT.search(text[cs:a] + ' ' + text[b:ce]):
        return True
    return _sections.layout(text).section_at(a).kind in ('impression', 'findings', 'technique', 'procedure')


def _hypothetical_spans(text: str, cs: int, ce: int, report: bool = False) -> list[tuple[int, int]]:
    """The hypothetical predicates of the clause [cs, ce), less the abilities its narrative realized."""
    return [(m.start(), m.end()) for m in HYPOTHETICAL.finditer(text, cs, ce)
            if not _ability_realized(text, m.start(), m.end(), cs, ce, report)]


def unhypothetical(text: str, start: int, end: int, report: bool = False) -> str:
    """text[start:end] with every hypothetical predicate (_hypothetical_spans) blanked, same length."""
    piece = list(text[start:end])
    for a, b in _hypothetical_spans(text, start, end, report):
        piece[a - start:b - start] = ' ' * (b - a)
    return ''.join(piece)


def _hypothetical(text: str, cs: int, ce: int, pos: int, end: int, report: bool = False) -> str:
    """The hypothetical wording that keeps the mention at [pos, end) of the bounded clause [cs, ce) from reading as done,
    or '': a condition on its own performance opens the clause ("If colonoscopy were done today, ..."); the mention
    lies in a hypothetical predicate ("it would have been dilated"); or, when no act verb of the clause's own is left
    once the hypothetical predicates are blanked (one that is - "Biopsies were taken and would be sent for H. pylori
    testing" - still decides, as before), a hypothetical act predicate follows the mention after at most a short phrase
    of place or means ("A biopsy would have been taken had ...", "EGD with biopsy would be done if ...") or the clause
    has act verbs and all are hypothetical ("The stricture would have been treated with balloon dilation had it been
    tight")."""
    def phrase(a: int, b: int) -> str:
        return ' '.join(text[a:b].split()).lower()[:80]

    condition = CONDITION_BEFORE.search(text[cs:pos]) if pos > cs else None
    if condition:
        held = (CONDITION_AFTER_HAD if condition.group('w').lower() == 'had' else CONDITION_AFTER).match(text, end, ce)
        if held:
            return phrase(cs, held.end())
    spans = _hypothetical_spans(text, cs, ce, report)
    if not spans:
        return ''
    for a, b in spans:
        if a <= pos < b:
            return phrase(a, b)
    masked = unhypothetical(text, cs, ce, report)
    if _verbal_predicate(text, masked, masked[:pos - cs], masked[end - cs:], pos, end):
        return ''  # a predicate the clause states for itself decides, as before ("..., which was done")
    following = HYPOTHETICAL_AFTER.match(text, end, ce)
    if following and (following.start('h'), following.end('h')) in spans:
        word = following.group('h').split()[-1]
        if ACT_VERB.match('was ' + word) or BARE_PARTICIPLE.fullmatch(word):  # its own act predicate, not "difficult"
            return phrase(following.start('h'), following.end('h'))
    # Every act verb of the clause is hypothetical: the mention is hypothetical only when such a predicate governs it -
    # the mention lies in its complement ("would have been treated with balloon dilation"), or the predicate follows it
    # with no opener that gives the predicate another subject ("..., after which the examination could be completed").
    governing = [(a, b) for a, b in spans
                 if (b <= pos and not OTHER_SUBJECT_OPENER.search(text, b, pos))
                 or (a >= end and not OTHER_SUBJECT_OPENER.search(text, end, a))]
    if governing and _verbal_predicate(text, text[cs:ce], text[cs:pos], text[end:ce], pos, end):
        return phrase(*governing[0])
    return ''  # no act predicate at all: the mention's reading is decided as before (silent or not)


def hypothetical_reading(reading: Reading) -> bool:
    """A reading decided by hypothetical wording: never promoted to performed by a listing or a report it is in."""
    return any(cue.startswith(HYPOTHETICAL_CUE) for cue in reading.cues)


def _consent_governed(text: str, cs: int, at: int) -> bool:
    """Whether the consent noun at ``at`` of the clause starting at ``cs`` is governed by the word that opens its phrase
    (CONSENT_GOVERNED), read from the last comma, colon, semicolon, stop or bracket before it ("Technique: After
    obtaining informed consent"). Bounded: the phrase's last 80 characters."""
    head = text[max(cs, at - 80):at]
    cut = max(head.rfind(c) for c in ',;:.(\n')
    return CONSENT_GOVERNED.match(head[cut + 1:].strip()) is not None


def _consent_object(text: str, cs: int, ce: int, pos: int, end: int) -> bool:
    """Whether the item at [pos, end) of the clause [cs, ce) is what a consent, an authorization or an approval in that
    clause is for (CONSENT_FOR, "Biopsy consent"), with no predicate of its own that states it done: a predicate between
    the consent and the item, or one after the item when the consent has its own ("Consent was obtained for colonoscopy
    and biopsies were taken"), is the item's. A consent is the subject only of an auxiliary predicate, and only when no
    word governs it (_consent_governed): "After obtaining informed consent, we performed cold snare polypectomy" and
    "Informed consent was obtained and we then biopsied ..." state the act done by its own predicate, and after a
    governed consent's phrase closes at a comma, the predicate that follows the item is the item's ("After anesthesia
    clearance for the procedure, hot snare polypectomy ... was performed"). Bounded: one pass over the clause."""
    if CONSENT_AFTER.match(text, end, ce):
        return True
    subject = CONSENT_SUBJECT.search(text, cs, pos)
    predicate_m = ACT_VERB.search(text, subject.end(), pos) \
        if subject and not _consent_governed(text, cs, subject.start()) else None
    if predicate_m is not None and AUXILIARY_PREDICATE.match(predicate_m.group(0)) \
            and predicate_m.start() - subject.end() <= 30 and ',' not in text[subject.end():predicate_m.start()] \
            and not ACT_VERB.search(text, predicate_m.end(), end) and not ACT_VERB.search(text, end, ce) \
            and not BARE_PARTICIPLE.search(text, predicate_m.end(), end) and not BARE_PARTICIPLE.search(text, end, ce):
        return True  # the clause's one predicate is the consent's ("Consent was obtained after explaining ...")
    found = None
    for m in CONSENT_FOR.finditer(text, cs, pos):
        if m.end() <= pos:
            found = m
    if found is None:
        return False
    between = text[found.end():pos]
    if ACT_VERB.search(between) or BARE_PARTICIPLE.search(between) or re.search(r'[.;]', between):
        return False
    tail = text[end:ce]
    stop = re.search(r',|[.;]|\s+(?:and|but|then)\s+(?:a|an|the|two|three|several|multiple|\d+|it|they|this|these)\b',
                     tail, FLAGS)
    tail = tail[:stop.start()] if stop else tail
    own = ACT_VERB.search(tail) or BARE_PARTICIPLE.search(tail)
    if own and ',' in between and _consent_governed(text, cs, found.start()):
        return False  # the governed consent's phrase closed at the comma: the predicate after the item is the item's
    predicate = found.group('predicate')
    consent_said = ACT_VERB.search(predicate) or BARE_PARTICIPLE.search(predicate) or CONSENT_PREDICATE.search(predicate)
    return not (own and consent_said)


# A history or plan word inside a noun phrase that names a site, a lesion or a finding - "the prior polypectomy site",
# "the previous EMR scar", "the previously tattooed polyp", "old blood", "the next polyp" - is the time of what that
# phrase names ("previous EMR", "previously tattooed"), never of an act outside it, whose time it leaves in doubt
# (refutation r1, negtime-5: "Biopsies were obtained from the prior polypectomy site" had excluded 45380 as
# historical). A time word on an occasion ("at the prior colonoscopy", "at the previous EGD") still dates the act.
_ATTRIBUTIVE_HEAD = (r'(?:sites?|scars?|beds?|base|margins?|areas?|anastomos[ie]s|tattoos?|clips?|blood|clots?|'
                     + LESION_NOUN + r')')
ATTRIBUTIVE_TIME = _rx(r'\b(?:the|a|an|this|that|its|their|his|her|with|from|of|on|at|in|into|near|beside|around)\s+'
                       r'(?P<w>prior|previous(?:ly)?|old|earlier|remote|former|next)\s+(?:[\w-]+\s+){0,2}?'
                       + _ATTRIBUTIVE_HEAD + r'\b')
# 7c8 skeptic, sk:4: the same, read by its structure where it had escaped - the "of" phrase of a site ("the site of prior
# polypectomy": the word and the noun after it name what made the site); a clause that opens on a time adverb and the
# participle it qualifies ("Previously tattooed polyp in the ascending colon was removed"; a bare "Prior polyps were
# removed" still dates its act); a date as a noun's attribute ("The 2023 EMR scar": a determiner right before it, a head
# noun within two words after it); and a relative clause or another event's participle describing a noun ("the polyp
# that was previously biopsied", "the ulcer seen on the prior EGD"), from its opener to the predicate after it (a
# relative clause's own predicate first).
ATTRIBUTIVE_OF = _rx(r'\b(?:sites?|scars?|beds?|base|margins?|areas?)\s+(?:of|from)\s+(?:(?:the|a|an)\s+)?'
                     r'(?P<w>prior|previous(?:ly)?|old|earlier|remote|former)\s+[\w-]+'
                     # a time adverb set off with its participle, describing the noun before it ("A polyp, previously
                     # biopsied, was removed")
                     r'|,\s*(?P<w2>previously|recently|formerly)\s+[a-z]+(?:ed|en)\s*,')
ATTRIBUTIVE_LEAD = _rx(r'[^\w\n]*(?P<w>previously|recently|formerly)\s+[a-z]+(?:ed|en)(?:\s+(?:[\w-]+\s+){0,2}?'
                       + _ATTRIBUTIVE_HEAD + r'\b|\s*,)')
ATTRIBUTIVE_DATE_LEAD = _rx(r'\b(?:the|a|an|this|that|its|their|his|her)\s+$')
# A date after the noun it belongs to ("the stricture on barium swallow of 09/22/2026", "the polyp from the CT of
# 09/22/2026", "the EMR scar from 2023"): a site, lesion or finding noun, or another study's, then "of", "from" or
# "dated" right before the date. The act's own occasion ("at the colonoscopy of 09/03/2026") names no such noun.
POSTNOMINAL_DATE = _rx(r'\b(?:' + _ATTRIBUTIVE_HEAD + r'|CT|MRI|MRCP|imaging|scans?|swallow|esophagram|ultrasound|'
                       r'sonogram|x-?rays?|radiographs?|stud(?:y|ies)|exam(?:ination)?s?|labs?)\s+(?:of|from|dated)\s+$')
ATTRIBUTIVE_DATE_HEAD = _rx(r'\s+(?:[\w-]+\s+){0,2}?' + _ATTRIBUTIVE_HEAD + r'\b')
RELATIVE_OR_EVENT = _rx(r'\b(?:(?P<rel>that|which|who|whom|whose)|(?P<event>found|seen|noted|identified|detected|'
                        r'diagnosed|shown|demonstrated|described|reported|documented|visuali[sz]ed|observed|imaged|'
                        r'confirmed|suspected))\b')
PREDICATE_RUN = _rx(r'\b(?:was|were|is|are|be|been|being|has|have|had|will|shall|would|should|can|could|may|might|must|'
                    r'did|does|do)\b(?:\s+(?:was|were|is|are|be|been|being|has|have|had|not|never)\b)*')
_PHRASE_STOP = re.compile(r'[,;:()\n]')


def _described_phrases(text: str, cs: int, ce: int) -> list[tuple[int, int]]:
    """The relative clauses and event phrases of the clause [cs, ce) that describe a noun (RELATIVE_OR_EVENT): each from
    its opener to a comma, a semicolon, a colon, a bracket or the predicate after it - for a relative clause, the one
    after its own (sk:4). Bounded: the clause, once per opener."""
    out = []
    for opener in RELATIVE_OR_EVENT.finditer(text, cs, ce):
        stop = _PHRASE_STOP.search(text, opener.end(), ce)
        limit = stop.start() if stop else ce
        own = 1 if opener.group('rel') else 0
        runs = []
        for run in PREDICATE_RUN.finditer(text, opener.end(), limit):
            runs.append(run)
            if len(runs) > own:
                break
        out.append((opener.start(), runs[own].start() if len(runs) > own else limit))
    return out


def _elsewhere_time_words(text: str, cs: int, ce: int, pos: int) -> dict[int, str]:
    """The time words of the clause [cs, ce) that describe another noun than the mention at ``pos`` (ATTRIBUTIVE_TIME,
    ATTRIBUTIVE_OF, ATTRIBUTIVE_LEAD, or inside a relative clause or event phrase, _described_phrases; the mention outside
    the phrase): their positions, with the phrase each describes."""
    out = {}
    for pattern in (ATTRIBUTIVE_TIME, ATTRIBUTIVE_OF):
        for m in pattern.finditer(text, cs, ce):
            w = m.start('w') if m.group('w') else m.start('w2')
            if not w <= pos < m.end():
                out[w] = ' '.join(text[w:m.end()].strip(' ,').split())
    lead = ATTRIBUTIVE_LEAD.match(text, cs, ce)
    if lead and not lead.start('w') <= pos < lead.end():
        out.setdefault(lead.start('w'), ' '.join(text[lead.start('w'):lead.end()].split()))
    whole = text[cs:ce]
    if not (HISTORY_WORDS.search(whole) or PLAN_WORDS.search(whole)):
        return out
    phrases = [(a, b) for a, b in _described_phrases(text, cs, ce) if not a <= pos < b]
    for words in (HISTORY_WORDS, PLAN_WORDS):
        for m in words.finditer(whole):
            at = cs + m.start()
            phrase = next(((a, b) for a, b in phrases if a <= at < b), None)
            if phrase is not None:
                out.setdefault(at, ' '.join(text[phrase[0]:phrase[1]].split()))
    return out


def _date_owner(text: str, d, cs: int, pos: int, ce: Optional[int] = None) -> str:
    """Whose time the date ``d`` in the clause starting at ``cs`` is, for the mention at ``pos``: '' the clause's own
    (it dates the act), 'none' no act's (a birth date, a documentation stamp, a clock time), 'other' another clause's or
    event's (BIRTH_LABEL, STAMP_LABEL, CLOCK_TIME, OTHER_EVENT). Bounded: the clause up to the date, once."""
    # A label stands right before its date (each pattern is anchored there), so it is read even across a clause or
    # sentence start an abbreviation's period made ("Alex Synthetic (b. 03/04/1961) underwent ...": 7c8 skeptic, sk:3),
    # up to 60 characters back (a stamp's author: "signed by Alex Q. Synthetic, MD on", sk:6).
    head = text[max(0, d.start - 60):d.start]
    if BIRTH_LABEL.search(head) or STAMP_LABEL.search(head) \
            or (d.precision == 'year' and d.bare and CLOCK_TIME.search(head)):
        return 'none'
    if d.precision == 'year' and BY_TIME.search(head):
        return 'other'  # "placed ... by 2015": a clock time or a year, never established as the act's own year
    # A date as the attribute of a site, a lesion or a finding ("The 2023 EMR scar ... was biopsied"), with the mention
    # outside that noun phrase, is that noun's (7c8 skeptic, sk:4).
    lead = ATTRIBUTIVE_DATE_LEAD.search(text, max(cs, d.start - 12), d.start)
    noun = ATTRIBUTIVE_DATE_HEAD.match(text, d.end) if lead else None
    if noun is not None and not lead.start() <= pos < noun.end():
        return 'other'
    of = POSTNOMINAL_DATE.search(text, max(cs, d.start - 40), d.start)
    if of is not None and not of.start() <= pos < d.end:
        return 'other'
    # A date in a parenthesis whose words label another item ("The polyp (CT 09/22/2026) was removed"), with the mention
    # outside it, is that item's (7c8 skeptic, sk:3).
    paren = text.rfind('(', max(0, min(cs, d.start - 80)), d.start)
    if paren >= 0 and ')' not in text[paren:d.start] and not paren < pos < d.start \
            and OWN_DATE_LEAD.fullmatch(text, paren + 1, d.start) is None:
        return 'other'
    # Every other clause or event before the date is asked, the last first: a later word that is no clause of its own
    # ("since") never hides an earlier event whose date it is ("apixaban held since 10/12/2026": 7c8 skeptic, sk:3).
    starts, answer = _other_event_answer(text, cs, d.start, d.end, ce)
    # The loop reads the openers before the date, the last first, and returns '' at the first whose clause or event
    # holds the mention (opener.start() <= pos < d.start): an answer it gives at a later opener stands, any other is ''.
    held = bisect.bisect_right(starts, pos) - 1 if pos < d.start else -1
    if answer is not None and answer[0] > held:
        return answer[1]
    return ''  # no other clause or event owns it, or the mention is inside the one that would: the date is its own


@functools.lru_cache(maxsize=4096)
def _other_event_answer(text: str, cs: int, ds: int, de: int, ce: Optional[int]):
    """For the date [ds, de) of the clause from ``cs`` (to ``ce``): the starts of the other-event openers before it,
    and the first answer _date_owner's opener loop gives wherever the mention stands - (the opener's index, 'other' or
    '') - or None when no opener gives one. Every other clause or event before the date is asked, the last first: a
    later word that is no clause of its own ("since") never hides an earlier event whose date it is ("apixaban held
    since 10/12/2026": 7c8 skeptic, sk:3).

    An opener's phrase runs from it to the date, so the last mark, predicate and word before the date answer for every
    opener's phrase at once, and the answer is read once per date and clause, however many mentions in the clause ask
    (refutation p2, cost2:1: the phrase was sliced and searched again for every earlier opener, times every date and
    every instrument mention read, and a 398,121-character paste took the assess stage past its limit after the request
    was sent)."""
    openers = [(m.start(), m.end(), m.group('event') is not None) for m in OTHER_EVENT.finditer(text, cs, ds)]
    starts = tuple(start for start, _, _ in openers)
    if not openers:
        return starts, None
    reach = openers[0][1]
    last_mark = max((m.start() for m in CLAUSE_MARK.finditer(text, reach, ds)), default=-1)
    last_predicate = max((m.start() for m in OTHER_EVENT_PREDICATE.finditer(text, reach, ds)), default=-1)
    last_word = ds - 1
    while last_word >= reach and text[last_word].isspace():
        last_word -= 1
    after = None  # whether a predicate follows the date in its clause: read once, when an opener first needs it
    for index in range(len(openers) - 1, -1, -1):
        _, end, event = openers[index]
        if last_mark >= end:
            return starts, (index, '')  # that clause or event (and every earlier one) closed before the date
        if event or last_predicate >= end:
            return starts, (index, 'other')
        # A clause the opener begins may set its subject before the date and its predicate after it ("because the
        # polypectomy in 2025 had been incomplete"): the date is then that clause's, never the act's (refutation 7c8,
        # sk:12: "Two polyps were removed with a cold snare today because the polypectomy in 2025 had been incomplete."
        # excluded 45385). Bounded: OTHER_EVENT_REACH after the date, to the clause's end or its next mark.
        if last_word >= end:  # a word of its own between the opener and the date: the clause's subject
            if after is None:
                rest = text[de:min(len(text) if ce is None else ce, de + OTHER_EVENT_REACH)]
                rest = rest[:next((m.start() for m in CLAUSE_MARK.finditer(rest)), len(rest))]
                after = bool(OTHER_EVENT_PREDICATE.search(rest))
            if after:
                return starts, (index, 'other')
        # "since 2019": a phrase, not a clause of its own - an earlier opener may still own the date
    return starts, None


def _in_an_aside(text: str, cs: int, d) -> bool:
    """Whether the date ``d`` stands inside a parenthesis opened before it (in its clause, or just before it)."""
    paren = text.rfind('(', max(0, min(cs, d.start - 80)), d.start)
    return paren >= 0 and ')' not in text[paren:d.start]


def read_clause(text: str, clause: tuple[int, int], pos: int, end: int, *, service_date: Optional[date], dates,
                part: _Part, in_today_report: bool) -> Reading:
    """The status a clause gives the thing named at [pos, end) in it, read within CLAUSE_REACH of the mention."""
    cs, ce = _bounded_clause(text, clause, pos, end)
    if end > pos and any(m.start() <= pos and end <= m.end() for m in REFERRAL_FOR.finditer(text, cs, ce)):
        return Reading('planned', ('planned: what a referral is for',))
    if end > pos and _consent_object(text, cs, ce, pos, end):
        # "Consent was obtained for biopsy and cold snare polypectomy": what the consent is for, never stated done here
        # (a paid second review had been queued for consented acts); held, never excluded.
        return Reading('uncertain', (CONSENT_CUE,))
    before = text[cs:pos]
    after = text[end:ce]
    whole = text[cs:ce]
    cues: list[str] = []
    line_start = max(text.rfind('\n', max(0, pos - ROW_REACH), pos) + 1, pos - ROW_REACH, 0)
    line_end = text.find('\n', end, end + ROW_REACH)
    line_end = min(len(text), end + ROW_REACH) if line_end < 0 else line_end
    has_bracket = '[' in text[line_start:line_end]
    plain = [m for m in BOX_ROW.finditer(text, line_start, line_end)] if has_bracket else []
    if len(plain) == 1 and bool(plain[0].group('a').strip()) != bool(plain[0].group('b').strip()) \
            and plain[0].start() <= pos < plain[0].end():
        # "<act> [X] Performed [ ] Not performed": one row, exactly one of its two options marked
        return Reading('performed' if plain[0].group('a').strip() else 'negated',
                       ('box: performed checked' if plain[0].group('a').strip() else 'box: not performed checked',))
    if end > pos and BOX_MARK.search(text, line_start, line_end):
        # Any other boxed row: routing's box reader, hardened over the refutation rounds, decides (strict rows: an
        # unusual row holds). Its status is the act's.
        from studio.gi import detect  # local: detect imports context, which this module also imports
        status, box_cues = detect.status_for_span(_ORIGINAL.get() or text, pos, end, service_date)
        if status in ('performed', 'incomplete') and _in_a_wrapped_note(text, line_start, line_end, pos, end):
            return Reading('uncertain', (WRAPPED_NOTE_CUE,))
        checked = re.search(_box_symbols.BOX_ON_PATTERN, text[line_start:line_end])
        if status == 'negated' and not checked and any('unchecked' in cue for cue in box_cues):
            # no option on the row is marked: an unselected option alone says nothing (the box contract)
            return Reading('uncertain', (BOX_UNSELECTED,))
        if status in ('performed', 'incomplete') and _under_an_empty_plan_heading(text, line_start):
            return Reading('planned', ('planned: listed under a plan heading',))
        label = _row_label(text, line_start, pos) if status == 'performed' and box_cues \
            and all(cue.startswith('section:') for cue in box_cues) and (_acts_in(text, pos, end) or any(
                pattern.search(text, pos, end) for _, _, pattern in SERVICES)) else None  # an act or a service, never
        # a landmark ("Furthest point reached: [X] Cecum" still completes the examination)
        if label is not None:
            # done only by its section's default, on a row whose own label lists something else ("Risks discussed -
            # \u2612 Biopsy"): strict boxes (2026-10-25) hold it, never read it as done
            return Reading('uncertain', (f'box: the row\u2019s label \u201c{label}\u201d does not list what was done',))
        return Reading(BOX_STATUS.get(status, 'uncertain'), ('box: ' + (box_cues[0] if box_cues else status),)
                       + tuple(box_cues[1:3]))
    # Check boxes on the row, never another line's: "[X] Performed [ ] Not performed".
    for m in BOX_ROW.finditer(text, max(cs, pos - 90, line_start), min(ce + 60, line_end)) if has_bracket else ():
        a, b = m.group('a').strip(), m.group('b').strip()
        if a and not b:
            return Reading('performed', ('box: performed checked',))
        if b and not a:
            return Reading('negated', ('box: not performed checked',))
        return Reading('uncertain', ('box: both or neither option checked',))
    # Negation.
    if NEG_OTHER.match(whole):
        return Reading('uncertain', ('no other/further: denies only acts beyond the documented ones',))
    lead = NEG_LEAD.match(whole)
    if lead:
        # It covers its list and the act's own predicate ("No biopsy, polypectomy or tattoo was performed", "No polyp
        # was snared"), never an item after another predicate ("No bleeding was seen after the polyp was snared", "No
        # polyps were seen, and biopsies were taken": refutation r1 - read as denied acts)
        between = text[cs + lead.end():pos]
        auxiliaries = list(re.finditer(r'\b(?:was|were|is|are|been)\b', between, FLAGS))
        own = len(auxiliaries) == 1 and re.search(r'\b(?:was|were|is|are|been)\s+(?:[\w-]+ly\s+)?$', between, FLAGS)
        # after another predicate, an item stays covered when a negation follows that predicate ("No biopsies were
        # taken, and ... there was nothing to remove with snare or forceps", "... and no tattoo was placed")
        negated_again = auxiliaries and re.search(r'\b(?:no|not|nothing|none|neither|nor|never|without)\b',
                                                  between[auxiliaries[-1].end():], FLAGS)
        if (not auxiliaries or own or negated_again) and not _outside_negation(between, after):
            return Reading('negated', ('negated: the clause opens with a negation that covers its list',))
    head = before[-60:]
    negation = re.search(r'\b(?:no|without|w/o|nor|neither)\s+(?:\w+[\s,-]+){0,6}$', head, FLAGS)
    if negation and not re.search(r'\b(?:no|without)\s+(?:immediate\s+)?(?:complications?|bleeding|perforation)\b', head,
                                  FLAGS):
        # Read from the negation word on (refutation r1, release lens): no auxiliary after it, or only the act's own
        # auxiliary right before the act ("no polyp was snared", "the polyp was neither biopsied"), and the negation is
        # the act's; an auxiliary of another predicate between them ("No bleeding was seen after the polyp was snared")
        # leaves the act to its own predicate.
        tail = head[negation.start():]
        auxiliaries = re.findall(r'\b(?:was|were|is|are|been)\b', tail, FLAGS)
        if (not auxiliaries or (len(auxiliaries) == 1
                                and re.search(r'\b(?:was|were|is|are|been)\s+(?:[\w-]+ly\s+)?$', tail, FLAGS))) \
                and not _outside_negation(tail, after):
            cues.append('negated: a negation before it in its clause')
            return Reading('negated', tuple(cues))
    for not_verb in NOT_VERB.finditer(whole):
        if _not_on_another_predicate(text, cs + not_verb.start(), end):
            continue
        # "was complete and was not discontinued": the negated word is the completion word, not this act.
        neg_target = text[cs + not_verb.end(): min(ce, cs + not_verb.end() + 40)]
        # only when the negated word itself is the completion word, with at most an adverb before it (refutation r1:
        # "Biopsy not obtained given incomplete exam" had read the completion word two words on as the target)
        if not re.match(r'\s*(?:[\w-]+ly\s+)?(?:discontinu|interrupt|terminat|abort|incomplet|stopped)', neg_target, FLAGS):
            return Reading('negated', ('negated: "not" on its predicate',))
    near = before[-40:]
    if any(not WITHOUT_COMPLICATION.match(near, w.start()) and not _outside_negation(near[w.start():], after)
           for w in WITHOUT.finditer(near)):
        return Reading('negated', ('negated: "without" before it',))
    if REPLACED.search(before[-80:]):
        return Reading('negated', (REPLACED_CUE,))
    if CANCEL_WORDS.search(whole):
        return Reading('cancelled', ('cancelled: ' + CANCEL_WORDS.search(whole).group(0).lower(),))
    # Time: a date in the clause - the act's own; a date of something else never dates it (_date_owner).
    # Whether the sentence says today is read over the coordinated predicates an own_time cut joins to this clause
    # (_Clause.joined), as before that cut: the cut moves another predicate's time words, never the sentence's TODAY
    # word (7c8 skeptic, sk:1). Every other time word below is still the clause's own.
    joined = getattr(clause, 'joined', None)
    said = text[slice(*_bounded_clause(text, joined, pos, end))] if joined else whole
    today = bool(TODAY_WORDS.search(said))
    act_said = bool(ACT_VERB.search(said))
    other_time = ''
    for d in _dates_in(dates, cs, ce):
        owner = _date_owner(text, d, cs, pos, ce)
        if not owner and today and ((d.precision == 'year' and d.bare) or _in_an_aside(text, cs, d)):
            # a bare year, or a date in a parenthetical aside ("Alex Synthetic (03/04/1961) underwent colonoscopy
            # today"), never outweighs the clause's "today" (7c8 skeptic, sk:3): held, never dated
            owner = 'other'
        if owner:
            if owner == 'other' and not other_time:
                other_time = f'{text[d.start:d.end]} is dated by another clause or event'
            continue
        if service_date is None:
            if d.precision == 'year' and HISTORY_WORDS.search(whole):
                return Reading('historical', (f'historical: {text[d.start:d.end]} with a history word',))
            if d.precision in ('day', 'month'):
                # A dated statement cannot be placed in time without the service date ("Colonoscopy 2026-09-03: a 6
                # mm polyp was removed" in a note whose date is unknown or in conflict): held, never read as today's.
                return Reading('uncertain', (f'uncertain: dated {text[d.start:d.end]}, and the service date is not '
                                             'known',))
            continue
        rel = gi_context.compare_to_service(d, service_date)
        if rel < 0:
            return Reading('historical', (f'historical: {text[d.start:d.end]} is before the service date',))
        if rel > 0:
            return Reading('planned', (f'planned: {text[d.start:d.end]} is after the service date',))
    # A history or plan word dates the act unless it describes another noun of the clause (ATTRIBUTIVE_TIME): that one
    # leaves the act's time in doubt (refutation r1, negtime-5).
    elsewhere = _elsewhere_time_words(text, cs, ce, pos)
    manner = [m.span() for m in MANNER_PHRASE.finditer(whole)]
    hist = next((h for h in HISTORY_WORDS.finditer(whole) if cs + h.start() not in elsewhere
                 and not any(a <= h.start() < b for a, b in manner)
                 and not REVIEW_OF_RECORDS.search(whole, max(0, h.start() - 30), min(len(whole), h.end() + 40))), None)
    if hist and not today:
        return Reading('historical', ('historical: ' + hist.group(0).lower(),))
    plan = next((m for m in PLAN_WORDS.finditer(whole) if cs + m.start() not in elsewhere
                 and not any(a <= m.start() < b for a, b in manner)), None)
    if plan and not (today and act_said):
        return Reading('planned', ('planned: ' + plan.group(0).lower(),))
    skipped = next((cs + m.start() for words in (HISTORY_WORDS, PLAN_WORDS) for m in words.finditer(whole)
                    if cs + m.start() in elsewhere), None) if elsewhere else None
    if skipped is not None and not other_time:
        other_time = f'it describes \u201c{elsewhere[skipped]}\u201d, not this act'
    # A history or plan section dates what it names before a hedge in the clause is read: a hedged item of a plan is
    # still planned ("1. Dysphagia, likely peptic stricture - upper endoscopy with dilation at the hospital"), never a
    # doubt about a service done today.
    if part.kind == 'history' and not today:
        return Reading('historical', ('historical: in a history section',))
    if part.kind == 'plan' and not today:
        return Reading('planned', ('planned: in a plan section',))
    hedge = HEDGE_WORDS.search(whole)
    if hedge:
        return Reading('uncertain', ('uncertain: ' + hedge.group(0).lower(),))
    hypothetical = _hypothetical(text, cs, ce, pos, end, report=in_today_report or part.kind in ('report', 'section'))
    if hypothetical:
        return Reading('uncertain', (HYPOTHETICAL_CUE + hypothetical,))
    if part.kind == 'indication' and not today:
        # An indication says why the patient came: a performance stated there and not said to be today's is not
        # established as today's ("Indication: Anemia. An EGD was performed last month at an outside hospital; the
        # endoscope was advanced to the duodenum") - held, as routing holds it, never read as done today.
        return Reading('uncertain', (INDICATION_READING,))
    # A form field on its own line ("Biopsy taken: No", "Tattoo placed: None"): once its time is today's (no date,
    # history or plan word, section, hedge or indication said otherwise), its answer - never a participle in its label
    # - states the item.
    answered = _field_answer(text, pos, end, service_date)
    if answered is not None:
        return answered
    if ACT_VERB.search(whole) or BARE_PARTICIPLE.search(after) or BARE_PARTICIPLE.search(before[-40:]) \
            or BARE_PARTICIPLE.fullmatch(text[pos:end].strip()) or _nominal_act(text, before, pos):
        if other_time and not today:
            # stated done, but a time in its clause is something else's: its own time is not established (held)
            return Reading('uncertain', (OTHER_TIME_CUE + other_time,))
        if in_today_report or today or part.kind == 'report':
            return Reading('performed', ('performed: an act predicate in a current report',))
        return Reading('performed', ('performed: an act predicate',))
    if in_today_report:
        return Reading('uncertain', ('uncertain: named without an act predicate',))
    return Reading('uncertain', ('uncertain: no performance statement',))


# Routing's reading of an item no status wording speaks for (detect.SILENT; validation's checks.SILENT_CUE_PREFIX).
ROUTING_SILENT = 'uncertain: no performance evidence'
OWN_BOX_CHECKED = 'box: its own check box is checked, the one marked option of its row'
# What routing's box reader says when no box on the row speaks for or against the item: silence, which a procedure
# line may still list as done. Any other boxed 'uncertain' - an unselected option ("Interventions: \u2610 Hot snare
# \u2610 Biopsy"), an unread mark, boxes that disagree, a row that cannot be paired - is a hold, as is a form field's
# held answer; neither a procedure line nor the service's own report ever makes it a performed act or service.
BOX_SILENT = 'box: ' + ROUTING_SILENT


LIST_REACH = 40  # lines above a check-box line read for the label of the list it is in (bounded work per act)


def _in_a_procedure_list(text: str, pos: int, end: int) -> bool:
    """Whether the check-box line of the item at [pos, end) lists what was done: the label of the list it is in is a
    procedure field's ("Interventions:", "Procedures performed:"). The label is the line's own, before the item
    ("Interventions: \u2612 Cold snare polypectomy"), unless that names an item of its own ("Biopsy: \u2610 ..."); else
    the line directly above the run of check-box lines the item's line belongs to, when that is a label with no answer of
    its own or a heading routing's layout reads. Fail-closed (triage round 2 skeptic: consent, equipment and education
    lists had been read as what was done): any other label ("Consent obtained for:", "Risks discussed:",
    "Instruments:"), a blank line, a line of prose, a field with its own answer or the document's start above the run
    says nothing about what the run lists, so its boxes are not read as done. Bounded: LIST_REACH lines."""
    ls = text.rfind('\n', 0, pos) + 1
    colon = text.find(':', ls, pos)
    if colon >= 0 and not _acts_in(text, ls, colon) \
            and not any(pattern.search(text, ls, colon) for _, _, pattern in SERVICES):
        return PROCEDURE_LIST_LABEL.fullmatch(text, ls, colon + 1) is not None
    line_end = ls - 1
    for _ in range(LIST_REACH):
        if line_end < 0:
            return False  # the document's start: no label says what the run lists
        line_start = text.rfind('\n', 0, line_end) + 1
        line = text[line_start:line_end]
        if not line.strip():
            return False  # a blank line: no label directly over the run
        if BOX_MARK.search(line):
            line_end = line_start - 1
            continue  # another line of the same check-box run
        colon = line.find(':')
        if colon >= 0 and not line[colon + 1:].strip():
            if _acts_in(text, line_start, line_start + colon) \
                    or any(pattern.search(text, line_start, line_start + colon) for _, _, pattern in SERVICES):
                line_end = line_start - 1
                continue  # another item of the list, printed as the label its form field answers ("Biopsy:")
            return PROCEDURE_LIST_LABEL.fullmatch(line, 0, colon + 1) is not None  # the label over the run
        if colon < 0 and _sections._heading(text, line_start, line_end) is not None:
            return PROCEDURE_LIST_LABEL.fullmatch(line) is not None  # a heading over the run
        if colon < 0 and len(line.strip()) <= 80 and not ACT_VERB.search(line) and not BARE_PARTICIPLE.search(line) \
                and not NOT_VERB.search(line) and (_acts_in(text, line_start, line_end) or any(
                    pattern.search(text, line_start, line_end) for _, _, pattern in SERVICES)):
            line_end = line_start - 1
            continue  # another item of the list, printed alone ("Biopsy", "1. Biopsy") for its form field to answer
        return False  # prose or a field with its own answer: what the run lists is unknown
    return False


def _checked_in_a_procedure_list(text: str, pos: int, end: int, service_date: Optional[date]) -> bool:
    """Whether the act at [pos, end) has its own box checked in every reading of its row (routing's reader,
    detect.own_box_checked, on the text as written) and its check-box line lists what was done
    (_in_a_procedure_list)."""
    from studio.gi import detect  # local: detect imports context, which this module also imports
    return detect.own_box_checked(_ORIGINAL.get() or text, pos, end, service_date) \
        and _in_a_procedure_list(text, pos, end)


def _checked_field_in_a_procedure_list(text: str, pos: int, end: int, service_date: Optional[date]) -> bool:
    """Whether the checked form-field line holding the act at [pos, end) names a printed item on its page (routing's
    tie, detect.checked_field_ties) that a procedure list lists (_in_a_procedure_list): "Interventions:" over "Biopsy"
    with "[PDF form fields on page 1] / Biopsy: checked", never a field whose label alone names the act ("Biopsy: Yes"
    under a printed "Biopsy recommended at follow-up?") or a printed consent list."""
    from studio.gi import detect  # local: detect imports context, which this module also imports
    ties = detect.checked_field_ties(_ORIGINAL.get() or text, pos, end, service_date)
    return any(_in_a_procedure_list(text, start, stop) for start, stop in ties)


def _under_an_empty_plan_heading(text: str, line_start: int) -> bool:
    """Whether the check-box run holding the line at ``line_start`` lies under a label with no answer ("Procedure:") that
    sits directly under a plan heading with nothing on its line ("Plan:"): the run lists what is planned (refutation r1:
    "Plan: / Procedure: / [x] Endoscopic mucosal resection / Return in 4 weeks" had read as done today, and paid for a
    second review). Bounded: LIST_REACH lines."""
    line_end = line_start - 1
    for _ in range(LIST_REACH):
        if line_end < 0:
            return False
        start = text.rfind('\n', 0, line_end) + 1
        line = text[start:line_end]
        if BOX_MARK.search(line):
            line_end = start - 1
            continue
        colon = line.find(':')
        if colon < 0 or line[colon + 1:].strip() or start == 0:
            return False
        above_end = start - 1
        above = text[text.rfind('\n', 0, above_end) + 1:above_end]
        return PLAN_HEADING.match(above) is not None
    return False


def _row_label(text: str, line_start: int, pos: int) -> Optional[str]:
    """The label a check-box row gives itself before its first box ("Risks discussed -", "Equipment:"), when that label
    names no item and is no procedure list's ("Interventions:"); else None. Bounded: one line."""
    first = BOX_MARK.search(text, line_start, pos)
    if first is None:
        return None
    head = text[line_start:first.start()].strip()
    if not head or head[-1] not in ':-\u2013\u2014':
        return None
    words = head.rstrip(':-\u2013\u2014 \t')
    if not words or PROCEDURE_LIST_LABEL.fullmatch(words) or _acts_in(text, line_start, first.start()) \
            or any(pattern.search(words) for _, _, pattern in SERVICES):
        return None
    return words


def mention_count(text: str, limit: int) -> int:
    """How many times the text names a service or an act in this reader's own vocabulary (SERVICES, ACTS), counted up to
    just past ``limit``: what the analyze stage bounds besides routing's count (refutation r1, cost: a note naming a
    service only this reader knows - "HRM" 24,000 times - or an act thousands of times passed routing's cap and then
    took the assess stage past its limit). Bounded: one pass of each pattern, stopping once past the limit."""
    count = 0
    for pattern in [p for _, _, p in SERVICES] + [p for _, p in ACTS]:
        for _ in pattern.finditer(text):
            count += 1
            if count > limit:
                return count
    return count


def _row_hold(reading: Reading) -> bool:
    """Whether ``reading`` is a hold its check-box row or its form field's answer makes (see BOX_SILENT)."""
    if reading.status != 'uncertain' or not reading.cues:
        return False
    cue = reading.cues[0]
    return (cue.startswith('box:') and not cue.startswith(BOX_SILENT)) or cue.startswith('field:')


# A form field: one "Label: answer" line, typed in a template or written by extraction for a PDF form's fields. Its
# answer, never a participle in its label, states the item its label names ("Biopsy taken: No" read as a performed
# biopsy, "Tattoo placed: None" as a performed tattoo), in routing's field vocabulary (detect._FIELD_DENIED and
# _BOX_ITEM_WORDS, so the two readers never disagree on a word): a box state ("not checked", "unchecked", "no option
# selected") negates the item, as routing reads it whatever the label; a selected denial ("No", "None", "Not done",
# "Not performed") negates it when the label is the item's own question - the item named with only the words of its
# own question ("Biopsy", "Biopsy taken", "Was a biopsy performed") - and holds it when the label names it among other
# words ("Biopsy (Y/N)", "Flexible sigmoidoscopy complications"); a short answer this reader cannot read ("N", "0",
# "N/A") holds it. A printed question with no answer on its line, or with both options printed and none marked
# ("Biopsy taken:   Yes   No"), is answered by the form field routing ties it to on its page (detect._form_fields: an
# off field negates it, a held one holds it); with no such field an unanswered label is read by its words as before
# ("Biopsies taken:" over the list of sites) and an unmarked pair is held. An affirming answer is no statement here:
# a checked or "Yes" field documents its act through checked_form_field, as before. Any other answer is read by its
# words. A boxed line never reaches this (routing's box reader decides it).
FIELD_REACH = 160  # a field line is short: a longer line is prose, read by its words (bounds the work per mention)
FIELD_BOTH_OPTIONS = re.compile(r'[ \t]*(?:yes|no)(?:[ \t]*[/|,]?[ \t]*(?:yes|no))+[ \t.]*', FLAGS)
FIELD_HOLD_PREFIX = "uncertain: the form field '"  # routing's cues for a field that holds its item or its page
# An answer this reader cannot read as done or not done: a denial or a doubt among other words, or several printed
# options ("None obtained", "zero", "no biopsy", "none needed", "Yes ___ No ___", "Yes / No (circle one)", "Y  N",
# "Yes   No   N/A"). It holds its item, never letting a participle in the label ("taken", "placed") state it done.
ANSWER_DOUBT = _rx(r"\b(?:no|none|never|nil|zero|neither|nor|n/?a|unknown|unsure|unclear|declined|deferred|pending)\b"
                   r"|(?:^|\s)0(?:\s|$)|\?|_{2,}|\(\s*circle|\b(?:yes|y)\b.*\b(?:no|n)\b|\b(?:no|n)\b.*\b(?:yes|y)\b")
# A negated predicate as the answer ("not placed", "not obtained"): read by its words, which deny the item (NOT_VERB).
ANSWER_NEGATED_PREDICATE = _rx(r'(?:was\s+|were\s+)?not\s+\w+')
# An option line an extraction block writes for a printed question: "<question>: <option>: checked|not checked".
FORM_OPTION_STATE = re.compile(r'(?P<option>yes|no|none|n/?a|not\s+done|not\s+performed)[ \t]*:[ \t]*'
                               r'(?P<state>checked|not\s+checked|unchecked)[ \t]*\.?', FLAGS)
FORM_BLOCK_REACH = 200  # lines walked back from a field line to the extraction block marker above it (bounded)


def _in_form_block(text: str, ls: int) -> bool:
    """Whether the line starting at ``ls`` lies inside an extraction block ("[PDF form fields on page 1]" down to the
    blank line that ends it): walked back over non-blank lines, at most FORM_BLOCK_REACH of them."""
    pos = ls
    for _ in range(FORM_BLOCK_REACH):
        if pos <= 0:
            return False
        prev_start = text.rfind('\n', 0, pos - 1) + 1
        line = text[prev_start:pos - 1].strip()
        if not line:
            return False
        if _sections.FORM_BLOCK.fullmatch(line):
            return True
        pos = prev_start
    return False


ALTERNATIVE_WORDS = 3  # words an alternative named with "or" may have ("Tattoo or marking agent injected")
_PLAIN_WORD = re.compile(r"[a-z][a-z'-]*")


def _own_question(text: str, start: int, end: int) -> bool:
    """Whether the field label [start, end) is an item's own question: every word of it outside the acts and services
    it names is a word of that question (routing's _BOX_ITEM_WORDS: "Biopsy taken", "Was a biopsy performed"), as
    routing's _box_label_kind reads an 'item' label; a time, an attribute or a count ("Biopsy (Y/N)", "Flexible
    sigmoidoscopy in the last 10 years") makes it another question.

    One more shape is the item's own question (gi2 conflicts, PR2): the item named with an alternative after "or", the
    question's predicate after both - "Tattoo or marking agent injected", "Biopsy or brushing taken", "Dilation or stent
    placed". A yes/no question about alternatives is answered for each of them, so its "No" denies the item. The
    alternative is at most ALTERNATIVE_WORDS plain words (no digit, no negation) and a name or a word of the question
    must follow it: "Tattoo or marking agent" (nothing after it) and "Tattoo or marking agent recommended" (another
    predicate) stay other questions, as does an "or" after anything but the item's name ("Bleeding or perforation after
    polypectomy")."""
    from studio.gi import detect  # local: detect imports context, which this module also imports
    names = [(a, b) for _, a, b in _acts_in(text, start, end)]
    names += [(m.start(), m.end()) for _, _, pattern in SERVICES for m in pattern.finditer(text, start, end)]
    words = [(w.group(0).lower(), any(a <= w.start() < b for a, b in names))
             for w in detect._BOX_LABEL_WORD.finditer(text, start, end)]
    i = 0
    while i < len(words):
        word, named = words[i]
        if named or word in detect._BOX_ITEM_WORDS:
            i += 1
            continue
        if word == 'or' and i > 0 and words[i - 1][1]:
            j = i + 1
            while j < len(words) and not words[j][1] and words[j][0] not in detect._BOX_ITEM_WORDS:
                if j - i > ALTERNATIVE_WORDS or not _PLAIN_WORD.fullmatch(words[j][0]) \
                        or NEGATION_WORD.fullmatch(words[j][0]):
                    return False
                j += 1
            if j < len(words):
                i = j  # the alternative ends where a name or a word of the question follows it
                continue
        return False
    return True


# A typed field whose label and answer a spaced dash separates ("Biopsy taken - No", "Tattoo placed \u2013 none"): read as a
# field, but a denial it gives only holds (a dash also joins prose), never excludes.
FIELD_DASH = re.compile(r'[ \t]+[-\u2013\u2014][ \t]+')
DASH_FIELD_CUE = 'field: its label and answer are separated by a dash, so its denial holds, never excludes'


# A denying answer with a note after it (gi2 conflicts, PR2): one of the field's own denying answers (routing's
# _FIELD_DENIED: "No", "None", "Not done", "Not performed"), then a dash, a comma, a semicolon or a parenthesis, then
# the note - "No - none used", "No (none used)", "None, see the physician's note". It denies the item as the answer
# alone would, unless the note affirms ("yes"), doubts (a hedge, an unknown), or names an act or a service, or states
# one done, with no negation of its own before it ("No - placed by the fellow", "No - Spot used instead", "No - India
# ink"): such an answer holds its item (ANSWER_DOUBT), as before.
FIELD_DENIAL_NOTE = re.compile(r'(?:no|none|not[ \t]+done|not[ \t]+performed)[ \t]*(?:[-\u2013\u2014,;][ \t]*|\()'
                               r'(?P<note>[^\n]{1,160}?)[ \t)]*\.?', FLAGS)
NOTE_AFFIRMS = _rx(r'\byes\b')
NOTE_UNKNOWN = _rx(r'\b(?:unknown|unsure|unclear|pending|n/?a)\b')  # ANSWER_DOUBT's words that are no negation
NOTE_DONE = _rx(r'\b' + ACT_PARTICIPLES + r'\b')


# Where a clause of a field's note ends, for the scope of a negation in it (refutation gi2 status-3): a mark that ends
# a clause (a comma, a semicolon, a colon, a parenthesis, a full stop, a spaced dash) or "but", the conjunction that
# sets a clause against the one before it. A closed class: the clause-ending punctuation and the adversative conjunction.
NOTE_CLAUSE_BREAK = re.compile(r'[,;:()]|\.(?=\s|$)|[ \t][-\u2013\u2014](?=[ \t])|\bbut\b', FLAGS)


def _note_clause(note: str, start: int, end: int) -> tuple[int, int]:
    """The clause of ``note`` that holds [start, end): from the last NOTE_CLAUSE_BREAK before it to the next after it."""
    clause_start = 0
    for m in NOTE_CLAUSE_BREAK.finditer(note, 0, start):
        clause_start = m.end()
    after = NOTE_CLAUSE_BREAK.search(note, end)
    return clause_start, after.start() if after is not None else len(note)


# What makes a participle state nothing done: the infinitive marker or a modal or future auxiliary before it ("tattoo to
# be placed at surgery", "will be injected"). A closed class: "to" and the auxiliaries.
NOTE_NOT_DONE = _rx(r'\b(?:to|will|would|shall|should|could|can|cannot|may|might|must)\b')


def _note_states_done(note: str, start: int, end: int) -> bool:
    """Whether the clause [start, end) of a note states something done today: a done participle with no infinitive
    marker or auxiliary before it (NOTE_NOT_DONE), and no plan, history or cancel word in the clause outside a manner
    phrase ("as planned" keeps a booking, never dates the act) - "placed by the physician", never "to be placed at
    surgery", "placed at a prior colonoscopy" or "deferred"."""
    manner = [(m.start(), m.end()) for m in MANNER_PHRASE.finditer(note, start, end)]
    for pattern in (PLAN_WORDS, HISTORY_WORDS, CANCEL_WORDS):
        if any(not any(a <= m.start() < b for a, b in manner) for m in pattern.finditer(note, start, end)):
            return False
    return any(not NOTE_NOT_DONE.search(note, start, m.start())
               for pattern in (NOTE_DONE, BARE_PARTICIPLE) for m in pattern.finditer(note, start, end))


def _note_denies(note: str, kinds: frozenset = frozenset()) -> bool:
    """Whether the note after a denying answer leaves the denial standing (FIELD_DENIAL_NOTE): it neither affirms nor
    doubts, and every act, service or done participle it names has a negation of its own before it ("none used").

    A negation governs its own clause (NOTE_CLAUSE_BREAK; refutation gi2 status-3: "No - not by nursing; placed by the
    physician" had read as the nurse's denial of the tattoo the physician documented, a false conflict). A later clause
    with no negation in it that states the item's own act done today (_note_states_done) - naming that act (``kinds``,
    the item's act kinds, or an act RELATED_KINDS ties to them: a tattoo and its injection) or opening with a done
    participle, whose subject is then the item - says the act was done, by whoever did it ("No (not by me) - injected
    by the fellow", "No, not by nursing; tattoo placed by the endoscopist"): the answer is then no denial and holds its
    item, as "No - placed by the fellow" does. A later clause about anything else, or about the act at another time,
    only explains the denial, which stands ("No - none placed; the lesion was completely removed", "No - none used;
    biopsies only", "No - none; tattoo to be placed at surgery", "No - none today; placed at a prior colonoscopy")."""
    if NOTE_AFFIRMS.search(note) or HEDGE_WORDS.search(note) or NOTE_UNKNOWN.search(note):
        return False
    own = {related for kind in kinds for related in (kind, *RELATED_KINDS.get(kind, ()))}
    named: list[tuple[Optional[str], int, int]] = [(kind, m.start(), m.end()) for kind, pattern in ACTS
                                                   for m in pattern.finditer(note)]
    named += [('', m.start(), m.end()) for _, _, pattern in SERVICES for m in pattern.finditer(note)]
    named += [(None, m.start(), m.end()) for pattern in (NOTE_DONE, BARE_PARTICIPLE) for m in pattern.finditer(note)]
    for kind, at, end in named:
        if not NEGATION_WORD.search(note, 0, at):
            return False  # it names or states something with no negation before it
        clause_start, clause_end = _note_clause(note, at, end)
        if NEGATION_WORD.search(note, clause_start, clause_end):
            continue  # its own clause negates it ("none used")
        names_the_act = bool(kind) and kind in own
        opens_with_participle = kind is None and not note[clause_start:at].strip()
        if (names_the_act or opens_with_participle) and _note_states_done(note, clause_start, clause_end):
            return False  # a later clause of its own states the item's act done
    return True


def _field_or_box_line(text: str, pos: int, end: int) -> bool:
    """Whether the line holding the mention at [pos, end) can carry its item's own answer: a field's colon, a two-column
    table row's bar, a dash after the mention (FIELD_DASH) or a check box (read_clause's box readers). Bounded: the line
    within ROW_REACH of the mention."""
    ls = max(text.rfind('\n', max(0, pos - ROW_REACH), pos) + 1, pos - ROW_REACH, 0)
    le = text.find('\n', end, end + ROW_REACH)
    le = min(len(text), end + ROW_REACH) if le < 0 else le
    return (text.find(':', ls, le) >= 0 or text.find('[', ls, le) >= 0 or text.find('|', ls, le) >= 0
            or BOX_MARK.search(text, ls, le) is not None or FIELD_DASH.search(text, end, le) is not None)


def _own_mark_denies(text: str, pos: int, end: int, reading: Reading, service_date: Optional[date]) -> bool:
    """Whether ``reading`` of the item at [pos, end) is a denial its own mark gives it: its check box marks it off, or
    its own field's answer denies it ("Tattoo placed | Not done" - the clause's "not" reads that answer first, the same
    denial). A dash-separated field's denial only holds (_field_answer), so it is none."""
    if reading.status not in ('negated', 'cancelled') or not reading.cues:
        return False
    if reading.cues[0].startswith(('field:', 'box:')):
        return True
    answered = _field_answer(text, pos, end, service_date)
    return answered is not None and answered.status == 'negated'


def _in_a_label_cell(text: str, ls: int, le: int, end: int) -> bool:
    """Whether the line [ls, le) is a two-column table row whose label cell holds the mention ending at ``end``."""
    bar = _table_row_bar(text, ls, le)
    return bar >= 0 and bar >= end


def _field_answer(text: str, pos: int, end: int, service_date: Optional[date]) -> Optional[Reading]:
    """_field_answer_read, with a dash-separated field's denial held (FIELD_DASH). A table row's denial is not held for
    that: its cell bar is the label's end, as a colon is (gi2 conflicts, PR2)."""
    reading = _field_answer_read(text, pos, end, service_date)
    if reading is not None and reading.status == 'negated':
        ls = text.rfind('\n', 0, pos) + 1
        le = text.find('\n', end)
        le = len(text) if le < 0 else le
        if text.find(':', ls, le) < 0 and not _in_a_label_cell(text, ls, le, end):
            return Reading('uncertain', reading.cues + (DASH_FIELD_CUE,))
    return reading


def _denying_answer(text: str, ls: int, colon: int, pos: int, end: int, value: str) -> Reading:
    """The reading a field's denying answer ``value`` gives the item at [pos, end) in its label [ls, colon)."""
    label = text[ls:colon]
    object_kinds = {kind for kind, _, _ in _acts_in(text, pos, end)} & OBJECT_NOUN_KINDS
    if object_kinds and not ACT_VERB.search(label) and not BARE_PARTICIPLE.search(label):
        # "Stones: None", "Stent: None", "Clips: None": a bare object noun answered with nothing is a finding
        # (no stones were found), never a statement that the act was not done (triage round 2 skeptic: an
        # ERCP's "Stones: None" had denied the stone extraction its sweep documented).
        return Reading('uncertain', (SILENT_READINGS[0],))
    if _own_question(text, ls, colon):
        return Reading('negated', (f'field: the answer \u201c{value}\u201d denies it',))
    return Reading('uncertain', (f'field: the answer \u201c{value}\u201d is to a question that names it among '
                                 'other words',))


def _field_answer_read(text: str, pos: int, end: int, service_date: Optional[date]) -> Optional[Reading]:
    """The reading a form field's answer gives the item named at [pos, end) in its label, or None when the mention is
    not in the label of a field line, or the answer says nothing this rule reads (it is then read by its clause's words,
    as before). Its label ends at a colon, or - with no colon on the line - at a spaced dash after the item (FIELD_DASH).
    Bounded by FIELD_REACH; one routing reading (status_for_span) for an unanswered label."""
    ls = text.rfind('\n', max(0, pos - FIELD_REACH), pos) + 1
    if ls == 0 and pos > FIELD_REACH:
        return None
    le = text.find('\n', end, end + FIELD_REACH)
    if le < 0:
        if end + FIELD_REACH < len(text):
            return None
        le = len(text)
    colon = text.find(':', ls, le)
    answer_at = None  # where the answer starts when a dash or a cell bar, not a colon, ends the label
    if colon < 0:
        bar = _table_row_bar(text, ls, le)
        if bar >= end:
            # a two-column table row with the mention in its label cell: the bar ends the label, as a colon does, and
            # the row's entry is the answer ("Tattoo or marking agent injected | No - none used"; gi2 conflicts, PR2)
            colon, answer_at = bar, bar + 1
        else:
            dash = FIELD_DASH.search(text, end, le)
            if dash is not None:
                colon, answer_at = dash.start(), dash.end()
    if colon < end or ls > pos:
        return None  # no label, or the mention is in the answer ("Findings: biopsies were taken")
    from studio.gi import detect  # local: detect imports context, which this module also imports
    line = text[ls:le] if answer_at is None else text[ls:colon] + ':' + text[answer_at:le]
    label_end = colon - ls
    value = (text[colon + 1:le] if answer_at is None else text[answer_at:le]).strip()
    option = FORM_OPTION_STATE.fullmatch(value)
    if option is not None and _in_form_block(text, ls):
        # An extraction block writes each option of a printed question as its own field line ("Biopsy taken: no:
        # checked"): the checked option decides, and a participle in the label is never the item's predicate.
        if not option.group('state').lower().startswith('checked'):
            return Reading('uncertain', (SILENT_READINGS[0],))  # an option not marked says nothing of the item
        word = re.sub(r'\s+', ' ', option.group('option').lower())
        if word in ('no', 'none', 'not done', 'not performed'):
            if _own_question(text, ls, colon):
                return Reading('negated', (f'field: its option \u201c{word}\u201d is checked',))
            return Reading('uncertain', (f'field: its option \u201c{word}\u201d is checked, to a question that names it '
                                         'among other words',))
        if word != 'yes':
            return Reading('uncertain', (f'field: its option \u201c{word}\u201d is checked',))
        return None  # "yes: checked" is read by its words, as before
    denied = detect._FIELD_DENIED.fullmatch(line)
    if denied is not None and denied.end('label') == label_end:
        if denied.group('box'):
            return Reading('negated', (f'field: the answer \u201c{value}\u201d marks it off',))
        if denied.group('answer'):
            return _denying_answer(text, ls, colon, pos, end, value)
        return Reading('uncertain', (f'field: the answer \u201c{value}\u201d is not read as done or not done',))
    noted = FIELD_DENIAL_NOTE.fullmatch(value)
    if noted is not None and _note_denies(noted.group('note'),
                                          frozenset(kind for kind, _, _ in _acts_in(text, pos, end))):
        return _denying_answer(text, ls, colon, pos, end, value)  # "No - none used" (gi2 conflicts, PR2)
    both = FIELD_BOTH_OPTIONS.fullmatch(value) is not None
    if value and not both and ANSWER_DOUBT.search(value) and not ANSWER_NEGATED_PREDICATE.fullmatch(value):
        # triage round 2 skeptic: "Biopsy taken: None obtained" and "Biopsy taken: Yes ___ No ___" read as a done biopsy
        # through the label's participle, which also queued a paid second review
        return Reading('uncertain', (f'field: the answer \u201c{value}\u201d is not read as done or not done',))
    if value and not both:
        return None
    if end > pos:  # a passage read whole (current_statement) names no item to tie
        # A printed question: its answer, if any, is the form field routing ties to it by its label.
        _, cues = detect.status_for_span(_ORIGINAL.get() or text, pos, end, service_date)
        if cues[:1] == (detect.UNCHECKED,):
            return Reading('negated', ('field: its form field marks it off (' + cues[0] + ')',))
        if cues and cues[0].startswith(FIELD_HOLD_PREFIX):
            return Reading('uncertain', ('field: ' + cues[0],))
    if both:
        return Reading('uncertain', (f'field: both options are printed and none is marked (\u201c{value}\u201d)',))
    return None


# A label line that may deny performance ("Procedures not performed:", "Cancelled procedures:"): only beside one is
# routing's denying-label reader asked (bounded work per reading).
DENIAL_LABEL_WORDS = _rx(r'\b(?:not\s+(?:performed|done)|cancell?ed|deferred|declined)\b')
DENIAL_LABEL_LOOKBACK = 2400  # characters above a line in which its label is looked for (LABEL_ITEMS lines in routing)
LISTED_UNDER_DENIAL = 'uncertain: listed under '


def held_under_denial(text: str, pos: int, reading: Reading, service_date: Optional[date]) -> Reading:
    """``reading`` of the mention at ``pos``, held when it reads performed and its line is listed under a label that
    denies performance, read by routing's own reader (detect.denying_label_over, round 4c-2 plan:C): "Procedures not
    performed:" over "Cold snare polypectomy of the 6 mm sigmoid polyp." is never a performed act. Uncertain, never
    negated: the same hold routing makes, so the two readers never disagree."""
    if reading.status != 'performed':
        return reading
    line_start = text.rfind('\n', max(0, pos - DENIAL_LABEL_LOOKBACK), pos) + 1
    above = text[max(0, line_start - DENIAL_LABEL_LOOKBACK):line_start]
    if not any(line.rstrip().endswith(':') and DENIAL_LABEL_WORDS.search(line) for line in above.split('\n')):
        return reading
    from studio.gi import detect  # local: detect imports context, which this module also imports
    label = detect.denying_label_over(text, pos, service_date)
    if label is None:
        return reading
    return Reading('uncertain', (f"{LISTED_UNDER_DENIAL}'{label}', a label that denies performance",) + reading.cues)


# A PDF form-field line the extraction writes for a checked checkbox or a selected "Yes" ("Cold snare polypectomy:
# checked", "Biopsy: Yes", inside "[PDF form fields on page N]"; routing's _FIELD_CHECKED vocabulary): one option,
# marked. Its label names the act; the line states it done, as a marked box row does (the check-box contract: exactly
# one option marked). An unmarked one ("not checked") says nothing here.
FORM_FIELD_CHECKED = re.compile(r'[ \t]*(?P<label>[^:\n]{1,120}?)[ \t]*:[ \t]*(?P<answer>checked|yes)[ \t]*\.?[ \t]*',
                                re.A | re.I)
SILENT_READINGS = ('uncertain: no performance statement', 'uncertain: named without an act predicate')
# An unchecked box this reader leaves to routing's box reader (read_clause; the box contract): it says nothing either way.
BOX_UNSELECTED = 'box: an unselected option alone says nothing'
# What says nothing either way about an item - neither done nor not done (passage_readings' silence).
SAYS_NOTHING = SILENT_READINGS + (BOX_UNSELECTED, BOX_SILENT)


def form_field_blocks(text: str) -> list[tuple[int, int]]:
    """The lines of each PDF form-field block, in order: from the line after its "[PDF form fields on page N]" line to
    the blank line (or the next block's line) that ends it (routing's block, gi/sections). One pass over the lines."""
    out, start, pos = [], None, 0
    for line in text.split('\n'):
        ls, le = pos, pos + len(line)
        pos = le + 1
        stripped = line.strip()
        block = _sections.FORM_BLOCK.fullmatch(stripped) if stripped else None
        if start is not None and (not stripped or block):
            out.append((start, max(start, ls - 1)))
            start = None
        if block and block.group('what') == 'form fields':
            start = min(len(text), le + 1)
    if start is not None:
        out.append((start, len(text)))
    return out


def checked_form_field(text: str, pos: int, blocks: Sequence[tuple[int, int]], starts: Sequence[int]) -> bool:
    """Whether ``pos`` lies in the label of a checked form-field line inside a form-field block (``blocks`` in order,
    ``starts`` their starts)."""
    i = bisect.bisect_right(starts, pos) - 1
    if i < 0 or pos >= blocks[i][1]:
        return False
    line_start = text.rfind('\n', 0, pos) + 1
    line_end = text.find('\n', pos)
    m = FORM_FIELD_CHECKED.fullmatch(text, line_start, line_end if line_end >= 0 else len(text))
    # a label that negates or doubts its act ("Biopsy not done: checked") is no statement that it was done; a "Yes"
    # answers a question, which documents the act only when it is the act's own ("Biopsy: Yes", never "Biopsy in the
    # last 10 years: Yes")
    return m is not None and pos < m.end('label') and not _cues.DOUBT_TOKEN.search(m.group('label')) and (
        m.group('answer').lower() == 'checked' or _own_question(text, m.start('label'), m.end('label')))


# The act's own noun heading its phrase: "En bloc endoscopic submucosal dissection of a 0-IIa lesion", "ligation of
# two varices".
NOMINAL_HEAD = _rx(r'(?:[\w-]+\s+){0,4}?(?:dissection|resection|ligation|dilation|dilatation|ablation|polypectomy|'
                   r'biopsy|biopsies|placement|insertion|extraction|removal|decompression|myotomy|sphincterotomy)\s+of\b')


def _nominal_act(text: str, before: str, pos: int) -> bool:
    """'placement of a covered metal stent' in an impression or a findings or technique section: the nominal form of
    the act's predicate. Never in an indication, a history or a plan, where it names what was asked for or intended."""
    if not NOMINAL_ACT.search(before[-60:]) and not NOMINAL_HEAD.match(text, pos, pos + 120):
        return False
    return _sections.layout(text).section_at(pos).kind in ('impression', 'findings', 'technique', 'procedure')


def _intent_word(text: str, ss: int, se: int, m: re.Match, name: str, *, service_date: Optional[date], dates,
                 part: _Part) -> str:
    """The intent the word at ``m`` of the sentence [ss, se) states for this encounter: ``name``, 'not <name>' for "not
    a screening ..." (read as diagnostic when nothing else is stated), or '' when it states none - a question, a hedge,
    a presumption, a pending confirmation or a doubt in its sentence (routing's own intent vocabularies,
    detect._INTENT_*: "Is this a screening colonoscopy?", "Presumed screening.", "Screening (to be confirmed ...)",
    "Screening per patient, but unclear."), another denial ("non-screening", "no screening"), or a clause its reader
    reads as another time, planned, denied, cancelled or hypothetical ("Screening colonoscopy recommended in 10
    years"). Used only for a family routing does not read (_finish)."""
    from studio.gi import detect  # local: detect imports context, which this module also imports
    if HEDGE_WORDS.search(text, ss, se) or detect._INTENT_PENDING.search(text, ss, se) \
            or detect._INTENT_DOUBTED.search(text, ss, se) \
            or detect._INTENT_PRESUMED.search(text, max(ss, m.start() - 40), m.start()):
        return ''
    if re.search(r'\bnot\s+(?:a\s+|an\s+)?$', text[max(ss, m.start() - 20):m.start()], FLAGS):
        return 'not ' + name
    if detect._INTENT_DENIED.search(text, max(ss, m.start() - 40), m.start()):
        return ''
    reading = read_clause(text, _clause_for(clauses(text, ss, se), m.start()), m.start(), m.end(),
                          service_date=service_date, dates=dates, part=part, in_today_report=False)
    stated = reading.status == 'performed' or (reading.status == 'uncertain' and bool(reading.cues)
                                               and reading.cues[0] in SILENT_READINGS + (INDICATION_READING,))
    return name if stated else ''


def current_statement(text: str, start: int, end: int, service_date: Optional[date]) -> bool:
    """Whether the passage [start, end) states something of the encounter on the date of service: not negated, not
    about another time (a dated or history clause) and not planned."""
    dates = gi_context.find_dates(text)
    part = _Part(0, len(text), '', 'physician', None, 'other')
    reading = read_clause(text, (start, end), start, start, service_date=service_date, dates=dates, part=part,
                          in_today_report=False)
    return reading.status not in ('historical', 'planned', 'negated', 'cancelled')


@functools.lru_cache(maxsize=1)
def _act_frame(text: str, service_date: Optional[date], pages: tuple = ()):
    """The reflowed view of ``text`` with its dates, parts (and their starts) and sentences, as build() reads them -
    page joins included: ``pages`` are the revision's page spans (refutation 7c8, sk:11: without them a sentence
    across a page join read no act done, and 46221 was excluded for bands the document places today): computed once
    per document, date and pages, however many codes ask states_an_act_done of it (one linear pass)."""
    flow = reflow(text, pages)
    dates = gi_context.find_dates(flow)
    plist = parts(flow, service_date=service_date, dates=dates)
    return flow, dates, plist, [p.start for p in plist], _sentences(flow)


# How many things the reader reads in one passage for passage_readings (bounds the work per code); past it the passage
# is not read through, and what it says is not established.
PASSAGE_READS = 64


def done_today(reading: Reading) -> bool:
    """A reading of something done today: performed, or stated done with its time in doubt (OTHER_TIME_CUE)."""
    return reading.status == 'performed' or (reading.status == 'uncertain' and any(
        cue.startswith(OTHER_TIME_CUE) for cue in reading.cues))


def passage_readings(text: str, start: int, end: int, service_date: Optional[date],
                     pages: Sequence = ()) -> Optional[list]:
    """What this reader reads in the passage [start, end), as pass 3 reads acts, on the same reflowed view as build():
    every act mention, service name, procedure-shaped word (routing's own structural form, detect._PROCEDURE_WORD:
    "Anoscopy", "Hemorrhoid banding", "Paracentesis") and act predicate ("was performed", "were placed") in it, each read
    in its own clause and section - [(reading, clause span)], in order, stopping after the first one read as done today
    (done_today). None when the passage holds more than PASSAGE_READS of them (not read through). The engine asks it of
    a code's own deciding passage, so the routing-era reading alone never excludes a code (ec5 and 7c8, cluster EXCL:
    both readers must read the same not-done status; 7c8 skeptic, sk:7 - an act outside the act vocabulary, read by its
    name or its predicate). ``pages`` are the revision's page spans, so a sentence across a page join is read as build()
    reads it (7c8 FORMATS skeptic, sk:11). Bounded: the sentences that meet the passage, PASSAGE_READS reads."""
    from studio.gi import detect  # local: detect imports context, which this module also imports
    flow, dates, plist, starts, sentences = _act_frame(text, service_date, tuple(pages or ()))
    out: list = []
    token = _ORIGINAL.set(text)
    try:
        for ss, se in sentences:
            if se <= start:
                continue
            if ss >= end:
                break
            read_end = min(se, ss + SENTENCE_READ_CHARS)
            lo, hi = max(ss, start), min(read_end, end)
            if lo >= hi:
                continue
            spots = {(ms, me) for _kind, ms, me in _acts_in(flow, lo, hi)}
            for pattern in [p for _, _, p in SERVICES] + [detect._PROCEDURE_WORD, ACT_VERB, BARE_PARTICIPLE]:
                spots.update(m.span() for m in pattern.finditer(flow, lo, hi))
            if not spots:
                continue
            if len(out) + len(spots) > PASSAGE_READS:
                return None
            part = _part_at(plist, starts, ss)
            cls = clauses(flow, ss, read_end)
            for ms, me in sorted(spots):
                clause = _clause_for(cls, ms)
                reading = read_clause(flow, clause, ms, me, service_date=service_date, dates=dates, part=part,
                                      in_today_report=part.kind == 'report')
                reading = held_under_denial(flow, ms, reading, service_date)
                out.append((reading, _span(text, *clause)))
                if done_today(reading):
                    return out
    finally:
        _ORIGINAL.reset(token)
    return out


def report_family_at(text: str, start: int, end: int, service_date: Optional[date], pages: Sequence = (),
                     sections: Sequence[str] = ()) -> str:
    """The family whose report part holds the passage [start, end) as build() cuts the document - a part about one
    service, from its title to the next title, less the history sections in it (parts, _time_parts) - or '' outside a
    report part or across its end. Read on the frame build() reads (_act_frame, computed once per document, date and
    pages): one bisection per passage.

    For a physiology study's own report (REPORTED_STUDIES) read with ``sections`` - the section kinds in which a report
    states what was done, found or concluded - the report speaks for its study only where the document reports that
    study alone and the passage states nothing else (refutation gi2 attr-F3): '' when a report title or a line of those
    sections names another such study, or an act only another study performs (_studies_reported: a combined manometry
    and pH-impedance report, whose results are not read as whose), and when the passage itself states an act its study
    does not perform or names another service ("biopsies of the distal esophagus were taken" after the study) - or is
    longer than the reader reads one sentence for acts (SENTENCE_READ_CHARS: not read through; bounds the work per
    passage)."""
    flow, _dates, plist, starts, _cut = _act_frame(text, service_date, tuple(pages or ()))
    part = _part_at(plist, starts, start)
    if part.kind != 'report' or not (part.start <= start and end <= part.end):
        return ''
    if not sections or part.family not in REPORTED_STUDIES:
        return part.family
    if end - start > SENTENCE_READ_CHARS:
        return ''  # longer than the reader reads one sentence for acts: not read through, so it shows nothing by place
    named, kinds = _studies_reported(text, service_date, tuple(pages or ()), tuple(sections))
    if named - {part.family} or any(part.family not in KIND_FAMILIES[kind] for kind in kinds):
        return ''
    if any(part.family not in KIND_FAMILIES.get(kind, ()) for kind, _, _ in _acts_in(flow, start, end)) \
            or INSTRUMENTS.search(flow, start, end) \
            or any(family != part.family and pattern.search(flow, start, end) for family, _, pattern in SERVICES):
        return ''
    return part.family


# The physiology studies whose own report speaks for them (report_family_at): a manometry, a pH or impedance study, an
# anorectal study, and a capsule endoscopy.
REPORTED_STUDIES = frozenset(('gi.motility', 'gi.reflux', 'gi.anorectal', 'gi.capsule'))


@functools.lru_cache(maxsize=4)
def _studies_reported(text: str, service_date: Optional[date], pages: tuple, sections: tuple) -> tuple:
    """(the physiology studies the document's report titles or ``sections`` lines name, the study act kinds those lines
    state - STUDY_KINDS, as build() reads acts): read once per document, on the frame build() reads. Bounded: one pass of
    each pattern over the titles and the sections' text."""
    flow, _dates, plist, _starts, _cut = _act_frame(text, service_date, pages)
    spans = [(p.title.start, p.title.end) for p in plist if p.title is not None and p.role == 'physician']
    spans += [(s.start, s.end) for s in _sections.layout(text).sections if s.kind in sections]
    named, kinds = set(), set()
    for lo, hi in spans:
        named.update(family for family, _, pattern in SERVICES + TITLE_SERVICES
                     if family in REPORTED_STUDIES and pattern.search(flow, lo, hi))
        kinds.update(kind for kind, pattern in ACTS if kind in STUDY_KINDS and pattern.search(flow, lo, hi))
    return frozenset(named), frozenset(kinds)


def states_an_act_done(text: str, start: int, end: int, service_date: Optional[date],
                       pages: Sequence = ()) -> Optional[Span]:
    """The clause of the first thing passage_readings reads as done today in the passage [start, end), or None."""
    readings = passage_readings(text, start, end, service_date, pages) or []
    return next((clause for reading, clause in readings if done_today(reading)), None)


# --- the reader -----------------------------------------------------------------------------------------------------

@dataclass
class _ServiceDraft:
    id: str
    family: str
    kind: str
    evidence: list = field(default_factory=list)
    completion_pos: list = field(default_factory=list)
    completion_neg: list = field(default_factory=list)
    statuses: list = field(default_factory=list)  # (status, cue, span)
    lesions: list = field(default_factory=list)
    acts: list = field(default_factory=list)
    intents: list = field(default_factory=list)
    extent: str = ''
    report_title: Optional[Span] = None
    scopes: list = field(default_factory=list)  # (start, end) of report parts and passages that document it
    kind_settled: bool = False  # the kind was set by the report title or a performed mention, not a passing one


def _anatomy_in(text: str, start: int, end: int) -> list[tuple[str, str, int, int]]:
    found: list[tuple[str, str, int, int]] = []
    taken: list[tuple[int, int]] = []
    for name, region, pattern in ANATOMY:
        for m in pattern.finditer(text, start, end):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((name, region, m.start(), m.end()))
    return sorted(found, key=lambda x: x[2])


def _technique(text: str, start: int, end: int, near: Optional[int] = None) -> str:
    """The technique named in [start, end); with ``near``, the one closest to that position ("cold snare polypectomy
    and cold forceps biopsy": the snare's technique is the cold snare)."""
    best, distance = '', None
    for name, pattern in TECHNIQUES:
        for m in pattern.finditer(text, start, end):
            if near is None:
                return name
            d = min(abs(m.start() - near), abs(m.end() - near))
            if distance is None or d < distance:
                best, distance = name, d
    return best


def _acts_in(text: str, start: int, end: int) -> list[tuple[str, int, int]]:
    """Act mentions in [start, end): (kind, start, end); a later kind never claims text an earlier one took."""
    found: list[tuple[str, int, int]] = []
    for kind, pattern in ACTS:
        for m in pattern.finditer(text, start, end):
            if any(a < m.end() and m.start() < b for _, a, b in found):
                continue
            found.append((kind, m.start(), m.end()))
    return sorted(found, key=lambda x: x[1])


def _family_for_act(kind: str, region: str, part_family: str, present: Sequence[str],
                    performed: Sequence[str] = ()) -> str:
    """Which service an act belongs to: the report part's own service, else by anatomy where one service fits. An
    act whose anatomy cannot be reached by the part's service (a duodenal biopsy in a colonoscopy part) goes to the
    present service whose anatomy it is. Where several fit, the one service documented as performed takes it (a stent
    in an ERCP report that also cites "the outside EUS")."""
    chosen = _family_for_act_in(kind, region, part_family, present)
    if chosen or not performed:
        return chosen
    narrowed = [f for f in performed if f != 'gi.office_em']
    if len(narrowed) == 1 and _family_for_act_in(kind, region, '', narrowed):
        return narrowed[0]
    return ''


# Acts that only one family performs, whatever part of the document names them.
KIND_FAMILIES = {'ph_monitoring': ('gi.reflux',), 'capsule_study': ('gi.capsule',), 'rectal_sensation': ('gi.anorectal',),
                 'manometry': ('gi.anorectal', 'gi.motility'), 'tube_replacement': ('gi.feeding_tube',)}
# The physiology studies no endoscope performs, and the acts only they perform (manometry, pH or impedance monitoring,
# rectal sensation testing): such an act belongs to a service of its own study family or to none - never to another
# family's service, whether the report part's or the one procedure a document names (refutation gi2 RC4, ho-08: a
# manometry report whose only endoscopy was "An EGD on 2026-09-08 showed ..." in its indication read "Upper GI
# endoscopy - performed (manometry)", asked how far that EGD's instrument was advanced, and listed it as a performed
# service without a proposal). A capsule and a tube change are no such study: an endoscope can place a capsule or change
# a tube.
STUDY_FAMILIES = frozenset(('gi.motility', 'gi.reflux', 'gi.anorectal'))
STUDY_KINDS = frozenset(kind for kind, families in KIND_FAMILIES.items() if set(families) <= STUDY_FAMILIES)


def _family_for_act_in(kind: str, region: str, part_family: str, present: Sequence[str]) -> str:
    if kind in KIND_FAMILIES:
        options = [f for f in KIND_FAMILIES[kind] if f in present]
        if kind == 'manometry' and len(options) > 1:
            options = ['gi.anorectal'] if region in ('rectum', 'anus') else ['gi.motility']
        if len(options) == 1:
            return options[0]
        if kind in STUDY_KINDS:
            # Its own study is documented as performed nowhere: the study its report part, its sentence or the document's
            # one procedure names is still its own, as before, though that study is also named as planned or earlier
            # ("Esophageal manometry in 2024 was normal." under History above today's technique; refutation gi2
            # attr-F2) - and no other service ever performs it.
            return part_family if part_family in KIND_FAMILIES[kind] else ''
    if part_family:
        lower = part_family in ('gi.colonoscopy', 'gi.flex_sig')
        upper = part_family in ('gi.egd',)
        if (lower and region in UPPER and 'gi.egd' in present) or (upper and region in LOWER and any(
                f in present for f in ('gi.colonoscopy', 'gi.flex_sig'))):
            part_family = ''
        else:
            return part_family
    if kind in ('fna',):
        return 'gi.eus' if 'gi.eus' in present else ''
    if kind in ('sphincterotomy', 'stone_extraction', 'lithotripsy', 'cholangioscopy', 'cannulation'):
        return 'gi.ercp' if 'gi.ercp' in present else ''
    if region in UPPER:
        options = [f for f in ('gi.egd',) if f in present]
    elif region in LOWER:
        options = [f for f in ('gi.colonoscopy', 'gi.flex_sig') if f in present]
    elif region == 'small_bowel':
        options = [f for f in ('gi.enteroscopy', 'gi.colonoscopy') if f in present]
    else:
        options = [f for f in present if f not in ('gi.office_em',)]
    return options[0] if len(options) == 1 else ''


# The landmark a family's endpoint is: the duodenum (bulb or beyond) or jejunum for an EGD, the cecum or the terminal
# ileum for a colonoscopy (routing's landmark tables, cues.UPPER_LANDMARKS / LOWER_LANDMARKS).
ENDPOINT_LANDMARKS = {
    'gi.egd': tuple(p for _, depth, p in _cues.UPPER_LANDMARKS if depth >= 3),
    'gi.colonoscopy': tuple(p for _, depth, p in _cues.LOWER_LANDMARKS if depth >= _cues.CECUM_DEPTH),
    'gi.capsule': tuple(p for _, depth, p in _cues.LOWER_LANDMARKS if depth >= _cues.CECUM_DEPTH),
}
NOT_REACHED = _rx(r'\b(?:short\s+of|unable|failed|could\s+not|cannot|can\s*not|precluded|not\s+(?:reached|intubated|'
                  r'visuali[sz]ed|seen|examined|entered|identified|possible)|without\s+reaching|did\s+not)\b')


def _endpoint_seen(text: str, family: str, start: int, end: int, service_date, dates, part) -> Optional[Span]:
    """A clause of today's report that states its endpoint landmark examined: reached ("advanced to the appendiceal
    orifice"), checked ("Extent reached: [X] Cecum") or described as seen ("Duodenum - normal bulb and second portion",
    "1. Cecum - 3 mm polyp"). Never a denial, an earlier or planned examination, or a doubt."""
    clause_text = text[start:end]
    if NOT_REACHED.search(clause_text):
        return None
    for pattern in ENDPOINT_LANDMARKS.get(family, ()):
        m = pattern.search(text, start, end)
        if m is None:
            continue
        reading = read_clause(text, (start, end), m.start(), m.end(), service_date=service_date, dates=dates,
                              part=part, in_today_report=part.kind == 'report')
        if reading.status == 'performed' or (reading.status == 'uncertain' and reading.cues and reading.cues[0] in (
                'uncertain: no performance statement', 'uncertain: named without an act predicate')):
            return _span(text, *_bounded_clause(text, (start, end), m.start(), m.end()))
    return None


# --- GI round 4, package PI: the inventory's own reading of reach, binding and extent -------------------------------
# Every rule below only reads more of what the document states about a service already documented here, and each
# holds wherever its guard is not met (fail-closed: the installed reading stands).

# E1: the endpoint landmarks (routing's own labels and depths, cues.UPPER_LANDMARKS / LOWER_LANDMARKS) a completion
# statement may name for the inventory to read the extent from it - the duodenum (bulb or beyond) for an EGD, the
# cecum or beyond for a colonoscopy. No other family's extent is read here.
_ENDPOINT_TABLE = {'gi.egd': tuple((label, depth, p) for label, depth, p in _cues.UPPER_LANDMARKS if depth >= 3),
                   'gi.colonoscopy': tuple((label, depth, p) for label, depth, p in _cues.LOWER_LANDMARKS
                                           if depth >= _cues.CECUM_DEPTH)}
# A statement carrying an extent word is an extent label routing's own label rules read (and may withhold: round 4c-2
# plan:B, D2); this reader never reads an extent from it.
EXTENT_WORD = _rx(r'\b(?:extent|depth|furthest|farthest|maximal|reach(?:ed)?\s*:)')
PARAGRAPH_BREAK = re.compile(r'\n[ \t]*\n')  # A1: a blank line ends what a paragraph carries
CARRY_REACH = 1500  # A1: characters a paragraph carries its service over (bounded work per act)
# The instrument as the subject of its own reach ("The colonoscope reached the cecum", "The gastroscope went in"): the
# active form of the passive reach ACT_VERB reads ("was advanced", "was passed"). Read right after the instrument word.
_PI_REACH_AFTER = _rx(r'[ \t]+(?:(?:then|easily|successfully|subsequently|readily|smoothly|finally)[ \t]+)?'
                      r'(?:reached|entered|traversed|went[ \t]+(?:in|into|through|down|past|beyond|to))\b')
_PI_REACH_CUE = 'performed: the instrument as the subject of its own reach, in a procedure report'
# W1: an indwelling stent's state ("The existing stent was in position and draining.", "the indwelling stent in good
# position"): a stent noun led by an indwelling word and followed straight away by its state, with no act between.
_PI_INDWELLING_BEFORE = _rx(r'\b(?:existing|indwelling|in-dwelling|previously[ \t]+(?:placed|inserted|deployed)'
                            r'|prior|old|in[ \t-]situ|current)[ \t]+(?:[\w-]+[ \t]+){0,4}$')
_PI_STATE_AFTER = _rx(r'(?:[ \t]+(?:was|were|is|are|remained|remains|appeared|appears|looked|looks|seen|noted))?'
                      r'(?:[ \t]+(?:still|well|again|already))?[ \t]+(?:in[ \t]+(?:(?:good|proper|satisfactory|'
                      r'appropriate|correct|stable|expected|adequate)[ \t]+)?(?:position|place|situ)\b|draining\b'
                      r'|patent\b|functioning\b)')
_PI_E1_SPANS = 64  # E1: completion statements read per service (bounded work; fewer can only read less)


def _pi_own_report(text: str) -> bool:
    """Positive evidence that the document is a procedure's own report (GI round 4, PS helpers): its head carries a
    procedure report's own fields (a sedation or anesthesia line, a field naming who performed it) and its title is no
    note written around a procedure (a booking, a call, a consent, instructions, a handout, a letter, a records
    review)."""
    return _sections.procedure_report_head(text) and not _sections.around_procedure_title(text)


def _pi_reaches(text: str, end: int) -> bool:
    """Whether the instrument word ending at ``end`` is the subject of its own reach (_PI_REACH_AFTER)."""
    return _PI_REACH_AFTER.match(text, end) is not None


def _pi_not_today_place(text: str, pos: int) -> bool:
    """Whether a statement at ``pos`` lies where it cannot speak for today's examination (E1 hardening): in a history
    or plan section of the layout of the text this reader reads or of the document as written, or under another
    occurrence (sections.under_another_occurrence: its own line's lead, or the heading-like line above it)."""
    original = _ORIGINAL.get() or text
    for t in {text, original}:
        if len(t) != len(text):
            continue
        if _sections.layout(t).section_at(pos).kind in ('history', 'plan') \
                or _sections.under_another_occurrence(t, pos):
            return True
    return False


def _endpoint_named(family: str, spans: Sequence[Span], text: str = '') -> str:
    """The deepest endpoint landmark (routing's label) the completion statements ``spans`` name, or '' (GI round 4, E1).
    Never from a statement in a history or plan section or under another occurrence (_pi_not_today_place), never from
    one carrying an extent word - an extent label ("Extent: Cecum | Scope: Olympus": routing's own label rules decide
    those, and where routing withholds such a label this reader adds nothing) or "the furthest point" - and never a
    landmark an earlier-occurrence word leads within the statement ("at the index examination the cecum")."""
    table = _ENDPOINT_TABLE.get(family, ())
    best: Optional[tuple[str, int]] = None
    for span in list(spans)[:_PI_E1_SPANS] if table else ():
        if EXTENT_WORD.search(span.text) or (text and _pi_not_today_place(text, span.start)):
            continue
        for label, depth, pattern in table:
            if best is not None and depth <= best[1]:
                continue
            if any(not _sections.ANOTHER_OCCURRENCE_HEAD.search(span.text, 0, m.start())
                   for m in pattern.finditer(span.text)):
                best = (label, depth)
    return best[0] if best else ''


def _pi_carried(carry, part: _Part, pos: int, regions, performed: Sequence[str], text: str,
                field_row: bool = False) -> str:
    """The family a paragraph carries to an act or lesion at ``pos`` that its part, its sentence and its site leave to
    no family (GI round 4, A1), or '': the family the paragraph last named (``carry``: family, part start, end of the
    sentence that set it), only within the same part and never in a history, plan or indication part, never for a field
    or check-box row, only where more than one family is documented performed and the carried family is one of them,
    within CARRY_REACH characters with no blank line between, and only when every region the statement names is one that
    family reaches (FAMILY_REGIONS: a rectal site never goes to an upper endoscopy)."""
    if carry is None or field_row:
        return ''
    family, part_start, end = carry
    if part_start != part.start or part.kind in ('history', 'plan', 'indication'):
        return ''
    done = [f for f in performed if f != 'gi.office_em']
    if len(done) < 2 or family not in done:
        return ''
    if pos - end > CARRY_REACH or (pos > end and PARAGRAPH_BREAK.search(text, end, pos)):
        return ''
    named = set(regions) - {''}
    if named and not named <= FAMILY_REGIONS.get(family, frozenset()):
        return ''
    return family


def _pi_indwelling_state(text: str, clause_start: int, ms: int, me: int) -> bool:
    """Whether the stent noun at [ms, me) names an indwelling stent's state, not an act (GI round 4, W1): an indwelling
    word leads it within its clause and its state follows straight away ("The existing stent was in position and
    draining.", "the indwelling stent in good position"). A new stent placed beside it is its own noun and still
    counts."""
    return _PI_INDWELLING_BEFORE.search(text, max(clause_start, ms - 120), ms) is not None \
        and _PI_STATE_AFTER.match(text, me) is not None


def _upper_only(text: str, start: int, end: int) -> str:
    """'gi.egd' when a sentence about an unnamed endoscope names only upper GI anatomy, the stomach or duodenum among
    it ("An ultraslim endoscope ... the stomach and duodenum to the second portion were examined")."""
    regions = {region for _, region, _, _ in _anatomy_in(text, start, min(end, start + SENTENCE_READ_CHARS))}
    return 'gi.egd' if regions and regions <= UPPER and regions & {'stomach', 'duodenum'} else ''


DILATION_ACT = _rx(r'\b(?:balloon|bougie\w*|Savary|Maloney|dilators?|CRE|pneumatic|wire-guided|through-the-scope|TTS)\b'
                   r'|\b(?:we|I)\s+dilated\b|\bdilat(?:ion|ation)\s+(?:was|were)\s+(?:performed|done|carried\s+out)\b'
                   r'|\b(?:was|were)\s+dilated\s+(?:with|using|by)\b|\bdilated\s+(?:with|using)\s+(?:a|an)\b'
                   r'|\b(?:no|without)\s+dilat(?:ion|ation)\b|\bdilat(?:ion|ation)\s+was\s+not\b')
# An act noun as the object of a place preposition ("through the newly deployed stent", "across the clips"): the noun
# names a place, and a denial in its clause is about something else.
PLACE_OBJECT = _rx(r'\b(?:through|across|into|beyond|past|within|inside|around|over|alongside|via|adjacent\s+to|next\s+to)'
                   r'\s+(?:the|a|an|this|that|its|their|each)?\s*(?:[\w-]+\s+){0,3}$')
OBSERVED = _rx(r'\b(?:was|were|is|are)\s+(?:seen|noted|found|identified|visualized|visualised|observed|present|detected|'
               r'appreciated|evident|demonstrated)\b')


def build(text: str, *, service_date: Optional[date], routing=None, context_facts=None,
          pages: Sequence = ()) -> ServiceInventory:
    """The documented services of ``text`` for the effective ``service_date``. ``routing`` (a RoutingResult) supplies
    routing's family readings, kept beside each service and used, fail-closed, where the two readings disagree.

    The reader reads a same-length view of the text in which a line break inside a sentence (a PDF or scan wrapping
    its line, or turning its page: ``pages`` are the revision's page spans) is a space (``reflow``); every offset is the
    text's own, and every passage it returns is the text's."""
    flow = reflow(text, pages)
    token = _ORIGINAL.set(text)
    try:
        inventory = _build(flow, service_date=service_date, routing=routing, context_facts=context_facts)
    finally:
        _ORIGINAL.reset(token)
    return _restore_spans(inventory, text) if flow != text else inventory


_ORIGINAL: contextvars.ContextVar = contextvars.ContextVar('services_original_text', default=None)
_SOFT_NEXT = re.compile(r'[ \t]*[a-z]')
# A line ending in a word that cannot end a sentence (an article, a preposition, an auxiliary, a conjunction) is
# continued by the next line whatever its case ("... provided by the" / "Anesthesia team").
_DANGLING = re.compile(r'\b(?:a|an|the|of|to|in|on|at|by|with|from|for|into|onto|and|or|but|nor|was|were|is|are|be|been|'
                       r'being|has|have|had|than|as|per|via|under|over|after|before|during|within|without|including|'
                       r'using|measuring|approximately|about|its|their|his|her|this|that|these|those)[ \t]*$', re.I)
_NEXT_ITEM = re.compile(r'[ \t]*(?:[-*\u2022]|\d{1,2}[.)]\s|[A-Z][A-Za-z /&()\-]{1,40}:(?:\s|$))')
_LIST_ITEM = re.compile(r'[ \t]*(?:[a-z][.)]|[ivx]{1,4}[.)])\s')
# What ends a sentence or a label at the end of a line. A semicolon does not (_sentences never cuts there): a line that
# ends at one and goes on in lower case is a wrap (refutation r1, formats-5: "... candidate for surgery;" / "prior
# studies have been inconclusive." had opened a history part at the wrapped line and dated the study as history).
_TERMINAL = re.compile(r'[.:!?]["\')\]]*[ \t]*$')


def reflow(text: str, pages: Sequence = ()) -> str:
    """``text`` with each soft line break - a wrap inside a sentence - replaced by a space, one character for one.

    A break is soft only when the line before it is a long run of prose (25+ characters and 4+ words) that does not
    end a sentence or a label (a semicolon ends neither) and does not end in an answer of its own (_answered_line, the
    rule _sentences cuts at), and the next line continues it in lower case, or after a word that cannot end a line
    (_DANGLING), a comma, or before a line opening with a parenthesis; never around a table row, a list item or a
    labelled field, never inside an extraction block, around a check-box or option row only where the row itself
    wraps (its option, note or label going on in lower case on the next line, which has no row of its own), never
    either side of a title written as a heading, and never where the join would change the answer a field row gives
    on its own. One title set on two heading lines is one line (_title_wrapped). Headings, labels, fields and short
    lines keep their breaks.

    A page join - the separator the extraction writes between two pages, after the earlier page's own last newline;
    ``pages`` are the text's page spans - is the line break it stands for, never a paragraph break of its own: when the
    last text line of one page and the first text line of the next pass the same test, every newline between them is
    a space, and when the next page's first line only continues in lower case it is one line break, as the same two
    lines read on one page (refutation r1, formats-2, formats-5 and formats-6: "The procedure was not" at the foot of
    a page and "discontinued; it was completed" atop the next, or "a 5 mm adenoma was" and "removed with a cold snare",
    were read as two sentences). Only a recorded page join is one: a blank line the author typed stays a paragraph
    break, and so does a join that ends an extraction block. The page's running footer and the next page's running
    header (_page_joins) are skipped when the join is decided, and a join that is read blanks them, so they are never
    read into the sentence."""
    if '\n' not in text:
        return text
    joins = _page_joins(text, pages)
    out = list(text)
    pos = 0
    n = len(text)
    in_block = False
    while True:
        i = text.find('\n', pos)
        if i < 0 or i + 1 >= n:
            break
        pos = i + 1
        ls = text.rfind('\n', 0, i) + 1
        prev = text[ls:i]
        ns = joins.get(i, i + 1)  # where the next line starts: past the page separator and furniture at a page join
        ne = text.find('\n', ns)
        nxt = text[ns:ne if ne >= 0 else n]
        stripped = prev.strip()
        in_block = bool(_sections.FORM_BLOCK.fullmatch(stripped)) or (in_block and bool(stripped))
        if in_block:
            continue  # an extraction block's lines are each a field, never one wrapped sentence
        if _soft_break(text, ls, i, ns, prev, nxt):
            kept = None
        elif ns > i + 1 and _SOFT_NEXT.match(nxt):
            kept = i  # a page join before a lower-case continuation: one line break, as on one page
        else:
            continue
        for j in range(i, ns):
            if j != kept:
                out[j] = ' '  # the separator, and the page's running footer and header between the two lines
        pos = ns
    return ''.join(out)


def _soft_break(text: str, ls: int, le: int, ns: int, prev: str, nxt: str) -> bool:
    """Whether the break after the line ``prev`` ([ls, le)) is soft before the line ``nxt`` starting at ``ns`` (see
    reflow)."""
    if _row_goes_on(prev, nxt) or _label_answered_below(prev, nxt):
        return True
    stripped = prev.strip()
    if _TERMINAL.search(prev) or _LIST_ITEM.match(nxt) or _NEXT_ITEM.match(nxt):
        return False
    if _title_wrapped(prev, nxt):
        # one title set on two heading lines, however short each is (refutation r1, formats-5; refutation 7c8,
        # formats-5 d: "GASTROSTOMY TUBE" / "REPLACEMENT" had been short of the prose test below, so the replacement
        # it names went unread)
        return True
    if len(stripped) < 25 or len(stripped.split()) < 4:
        return False
    if not _SOFT_NEXT.match(nxt) and not ((_DANGLING.search(prev) or prev.rstrip().endswith(',')
                                           or nxt.lstrip().startswith('(')) and nxt.strip()
                                          and not GENERIC_HEADING.match(nxt.strip())):
        return False
    if '|' in prev or '|' in nxt or '\t' in prev or '\t' in nxt:
        return False
    marked_before, marked_after = BOX_MARK.search(prev), BOX_MARK.search(nxt)
    if (marked_before or marked_after) and (marked_before and marked_after or not _SOFT_NEXT.match(nxt)):
        # refutation r1, formats-0 and formats-1: a check-box or option row is read over its logical extent, so its
        # marked option, its note or its label wrapping onto the next line in lower case is one line with it ("[X] Not"
        # / "performed", "[X] Not taken - not" / "sampled before resection", "... 3 cm distal to the" / "site) [ ]
        # Performed [X] Not performed"); a row never runs on into another row or into a line that does not go on in
        # lower case
        return False
    if _answered_line(text, ls, le, ns):
        return False  # "... and said no" / "Hiatal hernia - no": the answer ends its line
    if _title_line(prev) or _title_line(nxt):
        # refutation r1, formats-4: a title is decided on its own line, before any wrap is joined ("24-HOUR ESOPHAGEAL
        # pH-IMPEDANCE MONITORING REPORT" / "pH sensor positioned ..." had lost its title to a next line in lower case
        # by spelling, and the documented study read uncertain, historical or planned)
        return False
    answer = _field_answer_kind(prev)
    if answer and answer != _field_answer_kind(prev.rstrip() + ' ' + nxt.strip()):
        # refutation r1, formats-3: a field row's own answer ends it ("Biopsies taken from the antrum: N" / "pt on
        # apixaban." had lost its answer, and the label's participle stated the biopsy done): a join never changes the
        # answer a field row gives on its own, so a value that wraps is still one line ("Findings: a 6 mm sessile polyp
        # ... in one piece" / "with a cold snare and retrieved.")
        return False
    return True


# A check-box row's marked option cut after its negation ("[X] Not" / "Performed"), and the separator that sets a note
# off after a row's option ("[X] No - referred to ...", "[X] Not taken: deferred").
_ROW_OPTION_CUT = re.compile(r'[ \t]*(?:not|never)[ \t]*', re.I)
# A note's separator after a row's option. A match starts where a run of spaces does (or at the mark itself): a start
# inside a run is never the first one (the run's own first space matches whatever a later one does), and trying
# every one re-read the run, quadratic in it - 'Biopsy [X]' and 120,000 spaces took the assess stage past its limit
# after the request was sent (refutation p2, cost2:0).
_ROW_NOTE = re.compile(r'(?<![ \t])(?:[ \t]+[-–—][ \t]*|[ \t]*[:;,(][ \t]*)')
# A title an abbreviated name opens: its stop ends no note ("per Dr." / "Okafor"), as _sentences reads it.
_TITLE_STOP = re.compile(r'\b(?:Dr|Mr|Mrs|Ms|Prof|St)\.[ \t]*$')


WRAPPED_NOTE_CUE = ("uncertain: in a check-box row's note that wraps onto a line of its own; that printed line, read "
                    "alone, is no statement that it was done")


def _in_a_wrapped_note(text: str, line_start: int, line_end: int, pos: int, end: int) -> bool:
    """Whether the mention [pos, end), on a row line of the reflowed view (``text``, [line_start, line_end)), stands
    after the row's first mark and is printed on a line of the original text that has no mark of its own: the row's
    note wrapped onto the next line, which reflow reads with its row (_row_goes_on) but routing's box reader reads,
    over the text as printed, as a line of its own (refutation 7c8, formats-1: "[X] Not taken - per Dr." / "Okafor
    (fictional), biopsies are taken only after ..." had read the biopsy done by its section). A reading of that line
    alone never states the act done: it is held. Bounded: ROW_REACH around the mention."""
    original = _ORIGINAL.get()
    if original is None or original is text:
        return False
    first = BOX_MARK.search(text, line_start, line_end)
    if first is None or first.start() >= pos:
        return False  # a row's label, read by its row
    ols = max(original.rfind('\n', max(0, pos - ROW_REACH), pos) + 1, pos - ROW_REACH, 0)
    ole = original.find('\n', end, end + ROW_REACH)
    ole = min(len(original), end + ROW_REACH) if ole < 0 else ole
    return BOX_MARK.search(original, ols, ole) is None


def _row_goes_on(prev: str, nxt: str) -> bool:
    """Whether a check-box row's last option or note, cut where its line ends, goes on in the line ``nxt`` whatever
    its case (refutation 7c8, formats-0 and formats-1: "Tattoo injection [ ] Performed [X] Not" / "Performed" had lost
    the nursing denial, and "[X] No - referred to Halcyon" / "Valley EMR unit (fictional), where the lesion is lifted
    and resected" or "[X] Not taken - per Dr." / "Okafor (fictional), biopsies are taken ..." had read the note's tail
    as free prose): the option is cut after its negation, or the note set off after the option is cut on a word no
    phrase ends on (_DANGLING), a negation, a comma, a semicolon or its separator, on an abbreviated title, or inside a
    name (a capitalised word after a lower-case one) - and ``nxt`` has no mark of its own, is no list item, field,
    table row or extraction block, and opens no clause of its own (sections._own_clause: "Colonoscopy was then
    completed" is a sentence of its own, never the row's). A row whose option or note ends where its line does keeps
    its break; a lower-case continuation is _soft_break's own rule. Bounded: two lines."""
    last = None
    for last in BOX_MARK.finditer(prev):
        pass
    after = nxt.strip()
    if last is None or not after or BOX_MARK.search(nxt) or any(c in prev or c in nxt for c in '|\t') \
            or _LIST_ITEM.match(nxt) or _NEXT_ITEM.match(nxt) or _sections.FORM_BLOCK.fullmatch(after):
        return False
    tail = prev[last.end():]
    if _ROW_OPTION_CUT.fullmatch(tail):
        return not _sections._own_clause(after)
    note = _ROW_NOTE.search(tail)
    if note is None or not tail[:note.start()].strip():
        return False  # the line ends with the row's option, or with no option at all
    words = tail[note.end():].rstrip()
    if not words and ':' in tail[note.start():]:
        return False  # a label ends at its colon ("1. [x] Procedures performed:"): its items follow, never its note
    if not words or _DANGLING.search(words) or _NEGATION_END.search(words) or words.endswith((',', ';')):
        return not _sections._own_clause(after)
    tokens = words.split()
    name = len(tokens) >= 2 and tokens[-1][:1].isupper() and any(t[:1].islower() for t in tokens[:-1])
    if _TITLE_STOP.search(words) or name:
        return after.startswith('(') or (after[:1].isupper() and not _sections._own_clause(after))
    return False


# A short field answer opening a line, in the field readers' own vocabulary (detect._FIELD_DENIED's and _FIELD_CHECKED's
# answers, and the doubt words ANSWER_DOUBT reads), alone or before a comma, a stop, a dash or a parenthesis.
_ANSWER_OPENING = _rx(r'[ \t]*(?:no|none|nil|n|yes|y|n/?a|not[ \t]+(?:done|performed|taken|obtained|checked)|unchecked|'
                      r'checked|declined|deferred)(?=[ \t]*(?:$|[,.;(]|[-\u2013\u2014][ \t]))')


def _label_answered_below(prev: str, nxt: str) -> bool:
    """Whether ``prev`` is a field's label alone - it ends at its one colon, names an act and carries the participle or
    the verb that would state it done ("Biopsies taken from the gastric antrum and the gastric body for Helicobacter
    pylori (CLO):") - and ``nxt`` opens with that field's short answer ("no, pt on apixaban.", "N", "none"): the two are
    one field line, as the text sets it (refutation 7c8, formats-3: a PDF writer wrapped the row right after its colon,
    the label kept its break, and its participle read the biopsy done, 43239 READY where the text holds it). A label
    over a paragraph ("Findings:" / "No polyps were seen.") or over prose that opens with an answer word ("None of the
    three polyps ...") keeps its break. Bounded: one line of FIELD_REACH."""
    stripped = prev.strip()
    if not stripped.endswith(':') or stripped.count(':') != 1 or len(stripped) > FIELD_REACH \
            or BOX_MARK.search(prev) or any(c in prev for c in '|\t'):
        return False
    label = stripped[:-1]
    if not (BARE_PARTICIPLE.search(label) or ACT_VERB.search(label)) or not _acts_in(label, 0, len(label)):
        return False
    return _ANSWER_OPENING.match(nxt) is not None and not _NEXT_ITEM.match(nxt)


def _field_answer_kind(line: str) -> str:
    """The answer a field line ("Label: answer", or "Label - answer" with no colon on it) gives when it is read alone,
    as a whole short answer in the field readers' own vocabulary (_field_answer_read): a box state, a denial or a short
    answer read as neither (detect._FIELD_DENIED), a checked or "yes" answer, both options printed, or a negated
    predicate; '' when the line is no field, or its value is prose (a doubt word among other words is read the same
    on one line as on two). Bounded: one line of FIELD_REACH."""
    line = line.strip()
    if not line or len(line) > FIELD_REACH:
        return ''
    colon = line.find(':')
    if colon >= 0:
        label, value = line[:colon], line[colon + 1:]
    else:
        dash = FIELD_DASH.search(line)
        if dash is None:
            return ''
        label, value = line[:dash.start()], line[dash.end():]
    if not label.strip():
        return ''
    from studio.gi import detect  # local: detect imports context, which this module also imports
    field = label + ':' + value
    denied = detect._FIELD_DENIED.fullmatch(field)
    if denied is not None and denied.end('label') == len(label):
        return denied.lastgroup or 'denied'
    if detect._FIELD_CHECKED.fullmatch(field) is not None:
        return 'checked'
    value = value.strip()
    if FIELD_BOTH_OPTIONS.fullmatch(value):
        return 'both options'
    return 'negated predicate' if ANSWER_NEGATED_PREDICATE.fullmatch(value) else ''


def _opens_a_sentence(text: str, i: int) -> bool:
    """Whether the line after the newline at ``i`` opens a sentence of its own, although the line before it ends with
    no stop: the break is no wrap by routing's own test (sections._soft_wrap: no lower-case continuation, no word a
    sentence cannot end on) and the next line opens with a capital and a clause of its own (sections._own_clause: a
    finite verb or a participle predicate after its first word). A digital PDF's text layer, a scan's OCR and a Word
    document whose paragraphs are spaced carry no blank line between paragraphs (refutation r1, formats-7: "No polyps;
    no masses" / "Biopsies were taken." had been read as one sentence whose "no" denied the biopsy). Bounded: the end
    of the line before (WRAP_TAIL) and the start of the line after (OWN_CLAUSE_REACH).

    A line that opens with a count and the noun it counts, then its predicate ("2 biopsies were taken"), or with its
    own verb before what it acts on ("Biopsied the sigmoid colon at 20 cm"), opens one too (refutation 7c8, formats-7:
    "No polyps; no masses" / "2 biopsies were taken from the sigmoid colon." had denied the biopsy, so with 45378 alone
    it was hidden and 45378 READY); a measure that goes on ("5 mm and was removed") does not."""
    ns = i + 1
    first = re.match(r'[ \t]{0,40}', text[ns:ns + 41]).end() + ns
    if first >= len(text) or not (text[first].isupper() or text[first].isdigit()):
        return False
    ls = max(text.rfind('\n', 0, i) + 1, i - _sections.WRAP_TAIL)
    if not text[ls:i].strip():
        return False
    ne = text.find('\n', ns, ns + _sections.OWN_CLAUSE_REACH)
    ne = min(len(text), ns + _sections.OWN_CLAUSE_REACH) if ne < 0 else ne
    line = text[ns:ne]
    if text[first].isdigit():
        opens = _COUNTED_SUBJECT.match(line) is not None
    else:
        opens = _sections._own_clause(line) or _verb_first(line)
    return opens and not _sections._soft_wrap(text, (ls, i), (ns, ne))


# A count and the noun it counts, then their predicate: "2 biopsies were taken", "3 polyps were removed" (a measure
# that goes on - "5 mm and was removed" - has no predicate of its own before its "and").
_COUNTED_SUBJECT = re.compile(r'[ \t]*\d{1,3}(?:[ \t]+(?!(?:and|or)\b)[A-Za-z][A-Za-z/-]*){1,3}?[ \t]+'
                              r'(?:was|were|is|are|has|have|had)\b', re.A | re.I)


def _verb_first(line: str) -> bool:
    """Whether ``line`` opens with its own verb, capitalised, before what it acts on ("Biopsied the sigmoid colon at
    20 cm.", "Removed a 6 mm polyp with a cold snare."): a past form or participle (sections._own_clause's own test of
    a predicate word) followed by at least two more words. Bounded: OWN_CLAUSE_REACH."""
    words = _sections._CLAUSE_WORD_TOKEN.findall(line, 0, _sections.OWN_CLAUSE_REACH)
    if len(words) < 3 or not words[0][:1].isupper():
        return False
    verb = words[0].lower()
    return (verb.endswith('ed') and len(verb) > 3 and '-' not in verb) or verb in _sections._IRREGULAR_PARTICIPLES


def _title_line(line: str) -> bool:
    """Whether ``line`` is a title written as a heading: on its own it opens a part of the document (a report title,
    _report_title, or a role heading, as parts() reads them), and it is set off by a colon or a dash or written as a
    heading (_heading_shaped: "ESOPHAGEAL pH IMPEDANCE MONITORING REPORT", "Esophageal pH-Impedance Monitoring
    Report"). A prose line that happens to end in "report" ("... summarised in the attached colonoscopy report") is no
    title. A heading that names its service with no report word is one too (_service_heading: "24-HOUR ESOPHAGEAL pH
    MONITORING", "HIGH RESOLUTION ESOPHAGEAL MANOMETRY"; refutation 7c8, formats-4). Bounded: one line of at most 100
    characters, as parts() reads it."""
    titled = _report_title(line)
    if not titled and not any(pattern.match(line) for _, pattern in ROLE_HEADINGS) and not _service_heading(line):
        return False
    return titled == 'set off' or _heading_shaped(line)


def _service_heading(line: str) -> bool:
    """Whether ``line`` names one service as parts() reads a bare service heading: a heading-like line
    (GENERIC_HEADING) of at most 60 characters that names exactly one family and carries no plan, history or earlier
    span word (refutation 7c8, formats-4: "24-HOUR ESOPHAGEAL pH MONITORING" / "pH sensor placed at prior manometry."
    had been joined, as the next line is in lower case by spelling, and the study read historical; coding complete)."""
    stripped = line.strip()
    if not stripped or len(stripped) > 60 or not GENERIC_HEADING.match(line) or PLAN_WORDS.search(line) \
            or HISTORY_WORDS.search(line) or EARLIER_SPAN.search(line) or HISTORY_HEADING.match(line) \
            or PLAN_HEADING.match(line):
        return False
    return len({family for family, _, pattern in SERVICES if pattern.search(line)}) == 1


def _report_title(line: str) -> str:
    """'set off' or 'title' when parts() would open a report part with ``line`` on its own (a report title naming one
    service, with no plan or history word: REPORT_TITLE, or TITLE_FIELD or TITLE_REPORT_WORDS, whose title words a colon
    or a dash sets off); else ''."""
    if not line.strip() or len(line.strip()) > 100:
        return ''
    numbered = PART_NUMBER.match(line)
    body = line[numbered.end():] if numbered else line
    set_off = TITLE_FIELD.match(body) or TITLE_REPORT_WORDS.match(body)
    if not set_off and not REPORT_TITLE.match(body):
        return ''
    if not _family_named(line)[0] or PLAN_WORDS.search(line) or HISTORY_WORDS.search(line):
        return ''
    return 'set off' if set_off else 'title'


def _heading_shaped(line: str) -> bool:
    """Whether ``line`` is written as a heading: most of its words carry a capital letter (upper case, title case, or a
    mixed-case token such as "pH"), and it ends with no stop."""
    stripped = line.strip()
    words = re.findall(r"[A-Za-z][A-Za-z0-9/'-]*", stripped)
    return bool(words) and not stripped.endswith(('.', '!', '?')) \
        and 2 * sum(1 for word in words if any(c.isupper() for c in word)) > len(words)


def _title_wrapped(prev: str, nxt: str) -> bool:
    """Whether one title is set on the two lines ``prev`` and ``nxt`` ("BEDSIDE PROCEDURE NOTE: GASTROSTOMY TUBE" /
    "REPLACEMENT", "SMALL BOWEL CAPSULE ENDOSCOPY: INTERPRETATION AND" / "REPORT"): both are written as headings, the
    second has no label, box or cell of its own, and together - never apart - they are a report title or name a
    service (refutation r1, formats-5: a scan's narrower lines set the title on two lines, and the service it names was
    not read at all, so coding read complete)."""
    if ':' in nxt or any(c in prev or c in nxt for c in '|\t') or BOX_MARK.search(prev) or BOX_MARK.search(nxt) \
            or not _heading_shaped(prev) or not _heading_shaped(nxt):
        return False
    joined = prev.rstrip() + ' ' + nxt.strip()
    if _report_title(joined) and not _report_title(prev) and not _report_title(nxt):
        return True
    return bool(_family_named(joined, title=False)[0]) and not _family_named(prev, title=False)[0] \
        and not _family_named(nxt, title=False)[0]


EDGE_LINES = 3  # lines read at a page's head and foot for its running header or footer (bounded work per page)
EDGE_REACH = 2000  # characters walked from a page's edge for them
_NEGATION_END = re.compile(r'\b(?:not|never)[ \t]*$', re.I)


def _edge_lines(text: str, start: int, end: int, from_top: bool) -> list[tuple[int, int]]:
    """The first (``from_top``) or last EDGE_LINES + 1 non-empty lines of the page [start, end), nearest the edge
    first, as (start, end) of each line. Bounded: EDGE_REACH characters from the edge."""
    out: list[tuple[int, int]] = []
    if from_top:
        pos, limit = start, min(end, start + EDGE_REACH)
        while pos < limit and len(out) <= EDGE_LINES:
            newline = text.find('\n', pos, end)
            le = end if newline < 0 else newline
            if text[pos:le].strip():
                out.append((pos, le))
            if newline < 0:
                break
            pos = newline + 1
    else:
        pos, limit = end, max(start, end - EDGE_REACH)
        while pos > limit and len(out) <= EDGE_LINES:
            ls = max(start, text.rfind('\n', start, pos) + 1)
            if text[ls:pos].strip():
                out.append((ls, pos))
            pos = ls - 1
    return out


def _edge_key(line: str) -> str:
    """A line as a running header or footer repeats it on every page: its words, any page or date number masked."""
    return re.sub(r'\d+', '#', ' '.join(line.split())).lower()


def _page_joins(text: str, pages: Sequence) -> dict:
    """{offset of the newline that ends the last line of a page's body: offset of the first line of the next page's
    body} for each two consecutive pages of ``pages`` (spans with ``start`` and ``end``) that both hold text, with only
    whitespace between them.

    A page's body leaves out its running footer and the next page's running header (refutation 7c8, formats-6, -5 and
    -2: "Page 1 of 2", "Page 2 of 2", a letterhead repeated atop page 2 or "Confidential" stood between "The procedure
    was not" and "discontinued; it was completed", and the join paired the furniture line instead): up to EDGE_LINES
    lines at the page's foot and the next page's head that number the page (cues.page_number_line) or recur at the
    same edge of another page are its furniture; a line written as a heading there (cues.heading_shaped_line) is
    furniture only where the sentence plainly runs across the join - the body's last line ends on a word no sentence
    ends on (_DANGLING) or on a negation, and the next body line continues it (_soft_break, or in lower case). A
    check-box row, a table row or cell and an extraction block's marker are never furniture (a page header of cells,
    PAGE_HEADER, is running, as parts() reads it). Bounded: EDGE_LINES lines within EDGE_REACH of each page edge."""
    spans = sorted((p.start, p.end) for p in pages or ())
    spans = [(s, e) for s, e in spans if 0 <= s <= e <= len(text)]
    tops = [_edge_lines(text, s, e, True) for s, e in spans]
    bottoms = [_edge_lines(text, s, e, False) for s, e in spans]
    seen = {'top': {}, 'bottom': {}}  # edge key -> the pages that print it at that edge
    for index, (top, bottom) in enumerate(zip(tops, bottoms)):
        for edge, lines in (('top', top[:EDGE_LINES]), ('bottom', bottom[:EDGE_LINES])):
            for ls, le in lines:
                seen[edge].setdefault(_edge_key(text[ls:le]), set()).add(index)

    def furniture(edge: str, ls: int, le: int) -> str:
        line = text[ls:le]
        stripped = line.strip()
        if _sections.FORM_BLOCK.fullmatch(stripped) or BOX_MARK.search(line):
            return ''
        if _cues.page_number_line(line) or len(seen[edge].get(_edge_key(line), ())) > 1 \
                or (PAGE_HEADER.match(stripped) and stripped.count('|') >= 2):
            return 'running'
        if '|' in line or '\t' in line:
            return ''
        return 'heading' if _cues.heading_shaped_line(line) else ''

    joins = {}
    for index in range(len(spans) - 1):
        (s1, e1), (s2, e2) = spans[index], spans[index + 1]
        if s2 < e1 or text[e1:s2].strip():
            continue  # overlapping pages, or something between the pages: no join
        bottom, top = bottoms[index], tops[index + 1]
        if not bottom or not top:
            continue  # a page with no text
        foot = [furniture('bottom', *line) for line in bottom[:EDGE_LINES]]
        head = [furniture('top', *line) for line in top[:EDGE_LINES]]
        skip_foot = next((k for k, kind in enumerate(foot) if not kind), len(foot))
        skip_head = next((k for k, kind in enumerate(head) if not kind), len(head))
        if skip_foot >= len(bottom) or skip_head >= len(top):
            skip_foot = skip_head = 0  # nothing left of a page's body: read its lines as written
        if 'heading' in foot[:skip_foot] + head[:skip_head]:
            (ls, le), (ns, ne) = bottom[skip_foot], top[skip_head]
            prev, nxt = text[ls:le], text[ns:ne]
            runs_across = (_DANGLING.search(prev) or _NEGATION_END.search(prev)) and (
                _SOFT_NEXT.match(nxt) or _soft_break(text, ls, le, ns, prev, nxt))
            if not runs_across:  # a line written as a heading is the document's own: only running lines are skipped
                skip_foot = next((k for k, kind in enumerate(foot) if kind != 'running'), len(foot))
                skip_head = next((k for k, kind in enumerate(head) if kind != 'running'), len(head))
        (ls, le), (ns, _ne) = bottom[skip_foot], top[skip_head]
        if le < len(text) and text[le] == '\n' and le < ns:
            joins[le] = ns
    return joins


def _restore_spans(obj, text: str):
    """``obj`` (the inventory) with every passage's text taken from ``text`` at its own offsets."""
    if isinstance(obj, Span):
        return Span(obj.start, obj.end, text[obj.start:obj.end])
    if isinstance(obj, tuple):
        return tuple(_restore_spans(x, text) for x in obj)
    if isinstance(obj, list):
        return [_restore_spans(x, text) for x in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        changes = {f.name: _restore_spans(getattr(obj, f.name), text) for f in dataclasses.fields(obj)
                   if f.init}
        return dataclasses.replace(obj, **changes)
    return obj


def _build(text: str, *, service_date: Optional[date], routing=None, context_facts=None) -> ServiceInventory:
    problems: list[str] = []
    dates = gi_context.find_dates(text)
    date_starts = [d.start for d in dates]
    plist = parts(text, service_date=service_date, dates=dates)
    starts = [p.start for p in plist]
    sentences = _sentences(text)
    blocks = form_field_blocks(text)
    block_starts = [bs for bs, _ in blocks]
    if len(sentences) > MAX_SENTENCES:
        problems.append(f'The document has {len(sentences):,} sentences; only the first {MAX_SENTENCES:,} were read '
                        'for documented services, so services after them are not inventoried.')
        sentences = sentences[:MAX_SENTENCES]
    drafts: dict[str, _ServiceDraft] = {}

    def draft(family: str, kind: str) -> _ServiceDraft:
        if family not in drafts:
            if len(drafts) >= MAX_SERVICES:
                raise _Capped(f'More than {MAX_SERVICES} services are documented; the rest were not inventoried.')
            drafts[family] = _ServiceDraft(f'S{len(drafts) + 1}', family, kind)
        return drafts[family]

    attributions: list[Attribution] = []
    sedation_denied = ''
    present_families: list[str] = []
    performed_families: list[str] = []  # families with a performed reading (a title, a statement, an instrument)
    encounter_intents: list[str] = []
    routine_em: list[Span] = []
    placements = _Placements()  # how each statement of an act is placed, for pairing them (_conflicts)
    # A sentence (or its first SENTENCE_READ_CHARS) is cut into clauses once, and every mention read in it shares the
    # cut (refutation r1, cost-6: each named service and each instrument cut its whole sentence again - 299 names at
    # the head of one 196,000-character sentence took 13 s).
    cuts: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def clauses_of(start: int, end: int) -> list[tuple[int, int]]:
        if (start, end) not in cuts:
            cuts[(start, end)] = clauses(text, start, end)
        return cuts[(start, end)]

    def lesion_status(clause: tuple[int, int], lm: re.Match, part: _Part) -> str:
        return read_clause(text, clause, lm.start(), lm.end(), service_date=service_date, dates=dates, part=part,
                           in_today_report=part.kind == 'report').status

    # Pass 1: services named, other providers' services, encounter-wide statements.
    named: list[tuple[str, str, int, int, int, int]] = []
    for ss, se in sentences:
        part = _part_at(plist, starts, ss)
        # only this sentence's mentions can overlap a mention in it (sentences never overlap): comparing with every
        # mention named so far was quadratic (refutation r1, cost; 10,000 hedged one-line sentences took about 6 s)
        here: list[tuple[int, int]] = []
        for family, kind, pattern in SERVICES:
            for m in pattern.finditer(text, ss, min(se, ss + SENTENCE_READ_CHARS)):
                if any(a < m.end() and m.start() < b for a, b in here):
                    continue
                here.append((m.start(), m.end()))
                named.append((family, kind, m.start(), m.end(), ss, se))
        title = part.title
        lo, hi = (max(ss, title.start), min(se, ss + SENTENCE_READ_CHARS, title.end)) if title is not None else (0, 0)
        if lo < hi and part.kind == 'report' \
                and _heading_time(text, title.start, title.end, service_date, dates, date_starts) in ('', 'today') \
                and all(service_date is not None and d.precision == 'day'
                        and gi_context.compare_to_service(d, service_date) == 0
                        for d in dates[bisect.bisect_left(date_starts, title.start):bisect.bisect_left(date_starts,
                                                                                                        title.end)]):
            # a name only a title carries (TITLE_SERVICES): read as this report part's own title alone, on a line that
            # gives no other time and carries no date but the service date's - never in prose, a field or a heading
            # (refutation gi2 attr-F1)
            for family, kind, pattern in TITLE_SERVICES:
                for m in pattern.finditer(text, lo, hi):
                    if family == part.family and not any(a < m.end() and m.start() < b for a, b in here):
                        here.append((m.start(), m.end()))
                        named.append((family, kind, m.start(), m.end(), ss, se))
        for role, pattern in OTHER_PROVIDER:
            if pattern.search(text, ss, min(se, ss + SENTENCE_READ_CHARS)) \
                    and not OTHER_PROVIDER_DENIED.search(text, ss, min(se, ss + SENTENCE_READ_CHARS)):
                attributions.append(Attribution(role, (_span(text, ss, se),)))
        if SEDATION_BY_ENDOSCOPIST_DENIED.search(text, ss, se):
            sedation_denied = 'denied'
        if part.kind not in ('history', 'plan'):
            for name, pattern in INTENT_WORDS:
                m = pattern.search(text, ss, se)
                stated = _intent_word(text, ss, se, m, name, service_date=service_date, dates=dates, part=part) \
                    if m else ''
                if stated:
                    encounter_intents.append(stated)
        if EM_ROUTINE.search(text, ss, se):
            routine_em.append(_span(text, ss, se))
    try:
        for family, kind, ms, me, ss, se in sorted(named, key=lambda x: x[2]):
            part = _part_at(plist, starts, ss)
            cls = clauses_of(ss, se)
            clause = _clause_for(cls, ms)
            title = part.title is not None and part.title.start <= ms < part.title.end and part.family == family
            in_report = part.kind == 'report' and part.family == family
            if title:
                reading = Reading('performed', (f'section: report title "{part.title.text}"',))
            else:
                reading = read_clause(text, clause, ms, me, service_date=service_date, dates=dates, part=part,
                                      in_today_report=in_report)
                hypothetical = hypothetical_reading(reading)  # a hypothetical is a hedge: never promoted below
                if reading.status == 'uncertain' and in_report and not HEDGE_WORDS.search(text, *clause) \
                        and not hypothetical and not _row_hold(reading):
                    reading = Reading('performed', reading.cues + ('performed: named inside its own current report',))
                line_start = text.rfind('\n', 0, ms) + 1
                line_end = text.find('\n', ms)
                if reading.status == 'uncertain' and not hypothetical and not _row_hold(reading) and PROCEDURE_FIELD.match(
                        text[line_start:line_end if line_end >= 0 else len(text)]):
                    reading = Reading('performed', reading.cues + ('performed: listed on the procedure line',))
                reading = held_under_denial(text, ms, reading, service_date)
            d = draft(family, kind)
            if (title or reading.status == 'performed') and not d.kind_settled:
                d.kind, d.kind_settled = kind, True  # "Prior upper endoscopy ..." never makes a TNE an EGD
            if part.kind == 'report' and part.family == family:
                d.scopes.append((part.start, part.end))
            if title and d.report_title is None:
                d.report_title = part.title
            bounded_span = _span(text, *_bounded_clause(text, clause, ms, me))
            d.statuses.append((reading.status, reading.cues, bounded_span))
            if reading.status == 'performed':
                d.evidence.append(bounded_span)
            if family not in present_families and reading.status in ('performed', 'uncertain'):
                present_families.append(family)
            if family not in performed_families and reading.status == 'performed':
                performed_families.append(family)
        # Instruments name their service ("The colonoscope was advanced to the cecum").
        own_report: list[bool] = []  # GI round 4 (S1): read once, at the first instrument that needs it
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            upper = None  # what the sentence's anatomy makes an unnamed endoscope: read once, at its first one
            for m in INSTRUMENTS.finditer(text, ss, se):
                word = m.group(0).lower()
                family = next((f for name, f in INSTRUMENT_FAMILY if name in word), part.family)
                if not family and word == 'endoscope':
                    upper = _upper_only(text, ss, se) if upper is None else upper
                    family = upper
                if not family:
                    continue
                clause = _clause_for(clauses_of(ss, se), m.start())
                reading = read_clause(text, clause, m.start(), m.end(), service_date=service_date, dates=dates,
                                      part=part, in_today_report=part.kind == 'report' and part.family == family)
                reading = held_under_denial(text, m.start(), reading, service_date)
                if reading.status == 'uncertain' and len(reading.cues) == 1 and reading.cues[0] in SILENT_READINGS \
                        and _pi_reaches(text, m.end()):
                    # GI round 4 (S1): the instrument is the subject of its own reach ("The colonoscope reached the
                    # cecum") and nothing in its clause dates, denies, doubts or plans it - read as performed, as the
                    # passive "was advanced" is, but only with positive evidence that the document is the procedure's
                    # own report (its head, no note written around a procedure), never under another occurrence and
                    # never in a clause carrying a date (whose owner this reader did not weigh); else it stays silent
                    cs, ce = _bounded_clause(text, clause, m.start(), m.end())
                    if not own_report:
                        own_report.append(_pi_own_report(_ORIGINAL.get() or text))
                    if own_report[0] and not _dates_in(dates, cs, ce) \
                            and not _sections.under_another_occurrence(_ORIGINAL.get() or text, m.start()):
                        reading = Reading('performed', reading.cues + (_PI_REACH_CUE,))
                bounded_span = _span(text, *_bounded_clause(text, clause, m.start(), m.end()))
                if reading.status == 'performed' and family in drafts and any(
                        REPLACED_CUE in cue_list for status, cue_list, sp in drafts[family].statuses
                        if status == 'negated' and sp.start < bounded_span.end and bounded_span.start < sp.end):
                    # "Because the echoendoscope was unavailable, an EGD was performed rather than EUS": the clause's act
                    # predicate is the replacing service's; the replaced service's instrument documents no performance.
                    reading = Reading('uncertain', reading.cues + ('uncertain: its service is named as replaced in the '
                                                                   'same clause',))
                if family not in drafts:
                    if reading.status != 'performed':
                        continue
                    # "The colonoscope was passed to the cecum" under "Lower Endoscopy Report": the instrument names it
                    draft(family, FAMILY_KINDS.get(family, family.split('.')[-1]))
                    if family not in present_families:
                        present_families.append(family)
                if reading.status == 'performed' and family not in performed_families:
                    performed_families.append(family)
                d = drafts[family]
                d.statuses.append((reading.status, reading.cues, bounded_span))
                if reading.status == 'performed':
                    d.evidence.append(bounded_span)
        # Pass 2: completion and extent, read in each service's own report part (or a sentence naming only it).
        procedural = [f for f in drafts if f != 'gi.office_em']
        # The families each sentence names, indexed once (refutation r1, cost: passes 2 and 3 scanned every mention
        # named in the document for every sentence).
        named_in: dict[int, set[str]] = {}
        for f, _, _, _, s2, _ in named:
            named_in.setdefault(s2, set()).add(f)
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            fam = part.family if part.family in drafts and part.kind == 'report' else ''
            if not fam:
                named_here = sorted({f for f in named_in.get(ss, ()) if f in drafts}
                                    | _instrument_families(text, ss, se, drafts))
                fam = named_here[0] if len(named_here) == 1 else ''
            if not fam and len(procedural) == 1 and part.kind not in ('history', 'plan'):
                fam = procedural[0]  # one procedure documented: an untitled report's sentences are its own
            if not fam or part.kind in ('history', 'plan'):
                continue
            d = drafts[fam]
            for cs, ce in clauses_of(ss, se):
                clause_text = text[cs:ce]
                if HISTORY_WORDS.search(clause_text) or re.search(r'\b(?:if|unless|whether)\b', clause_text, FLAGS):
                    continue
                # "It would have been passed to the cecum had ...": a hypothetical reach completes nothing (a stop in
                # the clause is still read below, from the clause as written)
                positive_m = COMPLETE_POS.search(unhypothetical(text, cs, ce, part.kind in ('report', 'section')))
                if positive_m and not re.search(r'\bnot\s+(?:reached|intubated|complete)', clause_text, FLAGS):
                    d.completion_pos.append(_span(text, *_bounded_clause(text, (cs, ce), cs + positive_m.start(),
                                                                         cs + positive_m.end())))
                elif not positive_m and has_endpoint(fam, d.kind):
                    reached = _endpoint_seen(text, fam, cs, ce, service_date, dates, part)
                    if reached is not None:
                        d.completion_pos.append(reached)
                for m in INCOMPLETE_WORDS.finditer(text, cs, ce):
                    lead = text[max(cs, m.start() - 60):m.start()].lower()
                    if re.search(r'(?:\b(?:not|never|no|without)|' + NEG_CONTRACTION + r')\s+(?:\w+\s+)?$', lead) \
                            or re.search(r'(?:\b(?:not|never|without)|' + NEG_CONTRACTION + r')\s+(?:(?!was\b|were\b|is\b|'
                                         r'are\b|but\b|however\b)[\w-]+,?\s+){0,5}$', lead):
                        continue  # "was not discontinued", "wasn't discontinued", "not terminated early or interrupted"
                    if PLAN_WORDS.search(clause_text):
                        continue
                    if re.search(r'\b(?:lesion|polyp|mass|it)\b[^.;]{0,40}\bnot\s+removed\b', clause_text, FLAGS):
                        continue
                    d.completion_neg.append(_span(text, *_bounded_clause(text, (cs, ce), m.start(), m.end())))
                    break
        # Pass 3: lesions and acts.
        act_count = 0
        last_lesion: dict[str, Lesion] = {}
        # GI round 4 (A1): with more than one service performed, the only performed family's fallback no longer
        # decides an act or lesion that names no service, instrument or site its family fits; the service its
        # paragraph is about does (_pi_carried) - the one family its last naming sentence named, or gave a lesion or
        # an act by its own part, name or site. A sentence naming two families leaves the paragraph to neither.
        carry: Optional[tuple[str, int, int]] = None  # (family, part start, end of the sentence that set it)
        # a paragraph carries a service only where more than one is performed (_pi_carried): elsewhere every sentence
        # without an act or a lesion is passed over unread, as before (bounded work: no added scan per sentence)
        carrying = len([f for f in performed_families if f != 'gi.office_em']) > 1
        indwelling: list[tuple[str, str]] = []  # (family, act id) read as an indwelling stent's state (W1, below)
        # where each lesion was last named as itself, and where each service's text last named a lesion this reader did
        # not record: "the polyp" after an unrecorded polyp may be that one, not the last one recorded (status-1, below)
        last_named: dict[str, int] = {}
        unrecorded: dict[str, int] = {}
        # the encounter's denials: no service named for them, each with the one service its part's heading names, if any
        # (see below)
        unplaced: list[tuple[Act, str]] = []
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            read_end = min(se, ss + SENTENCE_READ_CHARS)
            if se > read_end:
                problems.append(f'A sentence of {se - ss:,} characters at offset {ss} was read for acts only in its '
                                f'first {SENTENCE_READ_CHARS:,} characters.')
            mentions = _acts_in(text, ss, read_end)
            lesion_matches = list(LESION.finditer(text, ss, read_end))
            if not mentions and not lesion_matches and not carrying:
                continue  # nothing to read here, and no paragraph's service to follow (as before GI round 4)
            named_here = sorted({f for f in named_in.get(ss, ()) if f in drafts}
                                | _instrument_families(text, ss, se, drafts))
            if carrying and len(named_here) == 1:
                carry = (named_here[0], part.start, se)  # GI round 4 (A1): every sentence naming one service sets it
            elif carrying and named_here:
                carry = None  # two services named: the paragraph carries neither
            if not mentions and not lesion_matches:
                continue
            cls = clauses_of(ss, read_end)
            anatomy_all = _anatomy_in(text, ss, read_end)
            regions = {region for _, region, _, _ in anatomy_all}
            part_family = part.family if part.family in drafts and part.kind == 'report' else ''
            if not part_family and len(named_here) == 1:
                part_family = named_here[0]
            if not part_family and len(procedural) == 1 and part.kind not in ('history', 'plan'):
                part_family = procedural[0]
            sentence_text = text[ss:se]
            denies_further = bool(NEG_OTHER.match(sentence_text))
            # Lesions in this sentence (never from a denial or a "no other" statement).
            sentence_lesions: list[Lesion] = []
            # the lesions this sentence names as its own: recorded here, or named by their size, their site or their own
            # noun ("the stricture") with no lesion this reader did not record named since - never one that "the
            # lesion", "the mass" or "it" falls back to, the last recorded whatever it was (refutation gi2 status-1: a
            # rectal mass the lesion reader does not record left "The lesion was tattooed" at the transverse polyp
            # before it, and the rectal tattoo denial was read as another subject)
            own_lesions: set[str] = set()
            for lm in lesion_matches:
                lead = (lm.group('lead') or '').strip().lower()
                tail = text[lm.end():lm.end() + 14].lower()
                if re.match(r'\s+(?:treatment|resection|removal|site|bed|base|margin)', tail):
                    continue
                region_one = next(iter(regions)) if len(regions) == 1 else ''
                fam = _family_for_act('biopsy', region_one, part_family, present_families, performed_families)
                if not fam:
                    # GI round 4 (A1): the service its paragraph is about, where every site the sentence names fits it
                    fam = _pi_carried(carry, part, ss, regions, performed_families, text)
                if not fam or fam not in drafts or denies_further:
                    continue
                d = drafts[fam]
                clause = _clause_for(cls, lm.start())
                # Its clause is read only where its reading decides something: a sized lesion that "this", "that" or
                # "the" does not name (passed over when denied or of another time), and a lesion about to be recorded
                # (refutation r1, cost-2 and cost-4: no count bounds lesion nouns, and reading every one - 99,600 bare
                # "AVM" at the paste limit - took the assess stage to 55 s of its 120 on a quiet host).
                status = None
                if lm.group('size') and lead not in ('this', 'that', 'the'):
                    status = lesion_status(clause, lm, part)
                    if status in ('historical', 'planned', 'negated'):
                        continue
                anat = [a for a in anatomy_all if clause[0] <= a[2] < clause[1]] or anatomy_all
                size = re.sub(r'\s+', ' ', (lm.group('size') or '').strip())
                existing = None
                if lead in ('this', 'that', 'the', 'it') or not (size or lead):
                    existing = _match_lesion(d.lesions, size, anat[0][0] if anat else '')
                creatable = (size or lead in ('a', 'an', 'one', 'two', 'three', 'four', 'five', 'six', 'several',
                                              'multiple', 'a separate', 'another') or lead.isdigit())
                if existing is None and creatable and anat and (status or lesion_status(clause, lm, part)) not in (
                        'negated', 'historical', 'planned'):
                    if lm.group('noun').lower().rstrip('s') in ('stricture', 'ring', 'erosion') and not size:
                        unrecorded[fam] = lm.start()
                        continue
                    if len(d.lesions) >= MAX_LESIONS_PER_SERVICE:
                        problems.append(f'More than {MAX_LESIONS_PER_SERVICE} lesions are documented for one service; '
                                        'the rest were not inventoried.')
                        unrecorded[fam] = lm.start()
                        continue
                    specimen = SPECIMEN.search(text, ss, se)
                    lesion = Lesion(id=f'{d.id}-L{len(d.lesions) + 1}', service=d.id, noun=lm.group('noun').lower(),
                                    size=size, morphology=re.sub(r'[\s,]+', ' ', lm.group('morph') or '').strip(),
                                    anatomy=anat[0][0], region=anat[0][1],
                                    specimen=(specimen.group('label') or specimen.group('label2')) if specimen else '',
                                    evidence=(_span(text, ss, read_end),))
                    d.lesions.append(lesion)
                    sentence_lesions.append(lesion)
                    own_lesions.add(lesion.id)
                    last_named[lesion.id] = lm.start()
                    placements.lesions[lesion.id] = _covers_of(text, anat)  # every site its clause names
                elif existing is not None:
                    sentence_lesions.append(existing)
                    if size or anat or (_noun_key(lm.group('noun')) == _noun_key(existing.noun)
                                        and last_named.get(existing.id, -1) > unrecorded.get(fam, -1)):
                        own_lesions.add(existing.id)
                        last_named[existing.id] = lm.start()
                else:
                    unrecorded[fam] = lm.start()  # a lesion named that this reader does not record
            if not sentence_lesions and ANAPHORA.match(text, ss, se):
                fam = part_family
                if fam and fam in last_lesion:
                    sentence_lesions.append(last_lesion[fam])
            # an act's lesion is at one known place only when every lesion its sentence names is at the same places
            # (_lesion_for picks one of several by position)
            one_place = len({placements.lesions.get(lesion.id) for lesion in sentence_lesions}) == 1
            if denies_further:
                continue  # "No other colon biopsy or lesion treatment was performed": nothing beyond the documented acts
            # Acts in this sentence.
            for kind, ms, me in mentions:
                clause = _clause_for(cls, ms)
                anat = [a for a in anatomy_all if clause[0] <= a[2] < clause[1]] or anatomy_all
                region = anat[0][1] if anat else ''
                fam = _family_for_act(kind, region, part_family, present_families, performed_families)
                if not fam:
                    # GI round 4 (A1): the service its prose paragraph is about (never a field or check-box row)
                    fam = _pi_carried(carry, part, ss, {a[1] for a in anat}, performed_families, text,
                                      field_row=_field_or_box_line(text, ms, me))
                elif fam in drafts:
                    carry = (fam, part.start, se)  # an act its own part, name or site gives a family sets it
                if not fam or fam not in drafts:
                    # Neither its part, its sentence nor its site tells which of the documented services the statement
                    # is about. A checklist item's own field or check box that denies it today is then the encounter's
                    # denial of that act: it is set beside each service that documents the act done once every act is
                    # read (``unplaced``; gi2 conflicts, PR2: a nursing checklist's "Tattoo or marking agent injected |
                    # No - none used" under a report of an upper endoscopy and a colonoscopy had been dropped, and with
                    # it the conflict with the physician's tattoo). Anything else - prose, whose denial may be scoped
                    # to a site or a lesion the reader does not see - stays unattributed, as before, and so does a
                    # history, plan or indication part (another occasion's).
                    if part.kind in ('history', 'plan', 'indication') or not drafts \
                            or not _field_or_box_line(text, ms, me):
                        continue
                    fam = ''
                if kind == 'snare' and re.match(r'[ \t]*site\b', text[me:me + 8], FLAGS):
                    continue  # "the polypectomy site": a place; never the next line's "Site:" field (boxes_pdf skeptic)
                if kind == 'dilation' and not DILATION_ACT.search(text, clause[0], clause[1]):
                    continue  # "a common bile duct dilated to 11 mm", "upstream duct dilation": a finding
                reading = read_clause(text, clause, ms, me, service_date=service_date, dates=dates, part=part,
                                      in_today_report=part.kind == 'report')
                bc = _bounded_clause(text, clause, ms, me)
                clause_text = text[bc[0]:bc[1]]
                row_lo = max(text.rfind('\n', max(0, ms - ROW_REACH), ms) + 1, ms - ROW_REACH, 0)
                row_hi = text.find('\n', me, me + ROW_REACH)
                row_hi = min(len(text), me + ROW_REACH) if row_hi < 0 else row_hi
                boxed = bool(BOX_MARK.search(text, row_lo, row_hi))
                checked = checked_form_field(text, ms, blocks, block_starts)
                # a form field's denying answer is its item's predicate ("Biopsy: No", "Tattoo placed: None")
                fielded = reading.status == 'negated' and reading.cues[:1] != () \
                    and reading.cues[0].startswith('field:')
                has_act_verb = bool(ACT_VERB.search(clause_text) or BARE_PARTICIPLE.search(clause_text) or boxed
                                    or checked or fielded or _nominal_act(text, text[bc[0]:ms], ms))
                if reading.status == 'negated' and not has_act_verb:
                    continue  # a denied finding ("without food impaction", "no stones"), not a denied act
                if reading.status == 'negated' and OBSERVED.search(clause_text) and not ACT_VERB.search(clause_text):
                    continue  # "No stricture or ring was seen"
                if reading.status == 'negated' and kind in NOUN_KINDS and PLACE_OBJECT.search(text, bc[0], ms):
                    continue  # "the scope was not passed through the newly deployed stent": a place, not a denied act
                if kind in NOUN_KINDS and not has_act_verb and not _on_procedure_line(text, ms, part):
                    continue
                if reading.status == 'uncertain' and not has_act_verb and not _on_procedure_line(text, ms, part):
                    continue
                if reading.status == 'uncertain' and not hypothetical_reading(reading) and not _row_hold(reading) \
                        and _on_procedure_line(text, ms, part):
                    reading = Reading('performed', reading.cues + ('performed: listed on the procedure line',))
                if checked and reading.status == 'uncertain' and reading.cues and reading.cues[0] in SILENT_READINGS \
                        and fam in performed_families \
                        and _checked_field_in_a_procedure_list(text, ms, me, service_date):
                    # its checked field names a printed item a procedure list lists, in a service a title, a statement
                    # or an instrument documents: the field states that item done (strict boxes, 2026-10-25)
                    reading = Reading('performed', reading.cues + ('performed: its form field is checked',))
                if reading.status == 'uncertain' and reading.cues and reading.cues[0].startswith(BOX_SILENT) \
                        and all(cue.startswith(ROUTING_SILENT) for cue in reading.cues[1:]) \
                        and part.kind not in ('history', 'plan', 'indication') and fam in performed_families \
                        and _checked_in_a_procedure_list(text, ms, me, service_date):
                    # Routing finds nothing for or against the act (a checked box is no performance statement to it:
                    # its section decides, and this one gives no default), its own box is checked in every reading of
                    # its row, the list it is in lists what was done, and a title, a statement or an instrument already
                    # documents the service: the row's one marked option (5.9) - "(x) Cold snare polypectomy" directly
                    # under "Interventions:", never under "Consent obtained for:", and never the only word that a
                    # service was done (the owner's strict-box decision, 2026-10-25: any other row holds).
                    reading = Reading('performed', reading.cues + (OWN_BOX_CHECKED,))
                reading = held_under_denial(text, ms, reading, service_date)
                if not fam and (not _own_mark_denies(text, ms, me, reading, service_date) or _dates_in(dates, *bc)
                                or HISTORY_WORDS.search(clause_text) or PLAN_WORDS.search(clause_text)):
                    continue  # no service named, and no item's own denial today (a date or time word: another's?)
                if fam:
                    d = drafts[fam]
                    d.scopes.append((part.start, part.end) if part.kind == 'report' and part.family == fam
                                    else (ss, se))
                lesion = _lesion_for(sentence_lesions, ms) if fam else None
                role = part.role
                labelled = next((r for r, pattern in ROLE_LABEL if pattern.match(text[ss:se])), None)
                if labelled:
                    role = labelled
                elif role == 'physician':
                    # A signature speaks for an act only as the label its sentence opens with, closed by a colon before
                    # the act and naming no act itself ("Recorded by Jo Fictional RN: India ink tattoo [X] Performed").
                    # Anywhere else it names who recorded something else - the specimen, the sedation ("..., placed in
                    # formalin and documented by Jo Rowe, RN", "Under propofol sedation given by the CRNA and
                    # documented in the anesthesia record, a polyp was removed") - never who documented the act, which
                    # it had hidden from reconciliation (refutation r1, missed-2).
                    label_end = text.rfind(':', ss, ms)
                    if label_end >= 0 and not any(ss <= other < label_end for _, other, _ in mentions):
                        for sig_role, sig in ROLE_SIGNATURE:
                            if sig.search(text, ss, label_end):
                                role = sig_role
                act_count += 1
                if act_count > MAX_ACTS:
                    raise _Capped(f'More than {MAX_ACTS:,} acts are documented; the rest were not inventoried.')
                act = Act(id='', service='', kind=kind, status=reading.status, role=role,
                          anatomy=tuple(dict.fromkeys(a[0] for a in anat)), region=region,
                          technique=_technique(text, *bc, near=ms), lesion=lesion.id if lesion else '',
                          evidence=(_span(text, *bc),), cues=reading.cues, detail=_detail(text, *bc, kind))
                placements.note(act, _covers_of(text, anat),
                                lesion is not None and lesion.id in own_lesions and one_place)
                if not fam:
                    unplaced.append((act, _heading_service(part, drafts)))
                    continue
                d.acts.append(replace(act, id=f'{d.id}-A{len(d.acts) + 1}', service=d.id))
                if kind == 'stent' and reading.status == 'performed' and _pi_indwelling_state(text, bc[0], ms, me):
                    indwelling.append((fam, d.acts[-1].id))  # GI round 4 (W1): weighed once every act is read
            if sentence_lesions:
                lesion = sentence_lesions[-1]
                for f, d in drafts.items():
                    if d.id == lesion.service:
                        last_lesion[f] = lesion
                        carry = (f, part.start, se)  # GI round 4 (A1): a lesion recorded sets the paragraph's service
        # The encounter's denials (above): each is set beside every service that documents done an act it denies - the
        # two statements are about the same act, and _conflicts keeps them as a conflict there - and beside no other,
        # so a denial of an act no service documents adds nothing, and no service's own scope grows by it. A part whose
        # own heading names one documented service ("Nursing checklist - colonoscopy") is about that service: its
        # denials are set beside that service only (refutation gi2 status-5: such a checklist's "Biopsy taken | No" had
        # been set beside the upper endoscopy's antral biopsies too, a false conflict the heading rules out).
        from studio.gi import catalogue  # local: catalogue reads this module's vocabulary
        done_kinds = {d.id: {a.kind for a in d.acts if a.status == 'performed'} for d in drafts.values()}
        for denial, heading_family in unplaced:
            # an act never reported on its own (clips, cannulation) is no coding conflict (_conflicts)
            contradicted = DENIED_BY.get(denial.kind, frozenset((denial.kind,))) - catalogue.NOT_REPORTED
            for d in ((drafts[heading_family],) if heading_family else drafts.values()):
                if not done_kinds[d.id] & contradicted:
                    continue
                act_count += 1
                if act_count > MAX_ACTS:
                    raise _Capped(f'More than {MAX_ACTS:,} acts are documented; the rest were not inventoried.')
                d.acts.append(replace(denial, id=f'{d.id}-A{len(d.acts) + 1}', service=d.id))
        # GI round 4 (W1): an indwelling stent's state ("The existing stent was in position and draining.") is no
        # performed act. It is dropped only where its service documents another stent performed (a new stent placed
        # beside it still counts), so dropping it never takes away what a code, a base-included hold or an unresolved
        # item reads: hold-only. Elsewhere the installed reading stands. Weighed once every act and every denial is
        # placed, so no act id is assigned after a drop.
        for fam, act_id in indwelling:
            d = drafts[fam]
            phantom = {i for f, i in indwelling if f == fam}
            if any(a.kind == 'stent' and a.status == 'performed' and a.id not in phantom for a in d.acts):
                d.acts = [a for a in d.acts if a.id != act_id]
    except _Capped as exc:
        problems.append(str(exc))
    services = [_finish(d, text, routing, context_facts, encounter_intents) for d in drafts.values()]
    services = _included([s for s in services if s is not None])
    em = _em_service(text, routing, context_facts, services, routine_em, sentences, len(services) + 1)
    if em is not None:
        services.append(em)
    services = tuple(services)
    conflicts = _conflicts(services, placements)
    return ServiceInventory(version=INVENTORY_VERSION, services=services, conflicts=conflicts,
                            attributions=_dedupe_attributions(attributions), problems=tuple(dict.fromkeys(problems)),
                            sedation_by_endoscopist=sedation_denied)


POSITIVE_STATUSES = ('performed', 'incomplete')
# The cues _finish adds when routing's reading of a family makes a service uncertain: a contrary statement in today's
# report (or, for a service the inventory reads as not performed, routing reading it performed), or routing's own doubt
# about today's service.
ROUTING_CONTRARY_CUE = 'uncertain: routing reads the family as '
ROUTING_DOUBT_CUE = 'uncertain: routing holds the family: '


def doubted_by_routing_alone(service) -> bool:
    """Whether ``service`` is uncertain only through routing's reading of its family: the inventory read it as performed
    (or incomplete), and a contrary statement in today's report or routing's own doubt about today's service made it
    uncertain (_finish). A service the inventory itself reads as not performed, or in doubt, is not."""
    return service.status == 'uncertain' and service.routing_status not in POSITIVE_STATUSES and any(
        cue.startswith((ROUTING_CONTRARY_CUE, ROUTING_DOUBT_CUE)) for cue in service.cues)


def act_regions(service, act) -> set:
    """The regions an act names: its anatomy's, and the lesion's it is directed at."""
    lesion = next((les for les in service.lesions if les.id == act.lesion), None) if act.lesion else None
    sites = {REGION_OF.get(name, '') for name in act.anatomy} | {act.region}
    if lesion is not None:
        sites |= {lesion.region, REGION_OF.get(lesion.anatomy, '')}
    return sites - {''}


def examined_regions(service) -> set:
    """The regions a service's own documentation names: its passages, its extent, its lesions and its acts done."""
    texts = [span.text for span in (*service.evidence, *service.completion_evidence)] + [service.extent]
    sites = {region for text in texts if text for _, region, pattern in ANATOMY if pattern.search(text)}
    sites |= {site for lesion in service.lesions for site in (lesion.region, REGION_OF.get(lesion.anatomy, ''))}
    sites |= {site for act in service.acts if act.status == 'performed' for site in act_regions(service, act)}
    return sites - {''}


def _included(services: list) -> list:
    """An upper endoscopy performed with an EUS in the same session is the EUS's endoscopic portion: the EUS code
    includes the examination (EGD with EUS), so the EGD is kept, marked included, and asks for no code of its own. How
    far the ultrasound went never makes the endoscopic examination incomplete. Its own acts are still reconciled.

    Only an EUS of the upper GI tract has an upper endoscopy as its endoscopic portion: an EUS whose own documentation
    names a site of the lower tract (colon, rectum, anus) among its passages, extent, lesions and acts - the reading a
    READ_UNDER rule reads an examination's tract with (examined_regions) - includes none, and the EGD beside it stays a
    service of its own (refutation p2, reports2:0: an EGD beside a rectal EUS was marked included in it, so a
    sigmoidoscopy EUS code was read as accounting for the EGD - "every performed service that routing detected has a
    selected proposal", "every documented service has a proposal to review", "included in S2: that service's code
    includes this examination"). Whether a selected code of the EUS includes the examination is the reconciliation's
    question (catalogue.includes_examination)."""
    eus = next((s for s in services if s.family == 'gi.eus' and s.status in POSITIVE_STATUSES
                and not examined_regions(s) & LOWER), None)
    if eus is None:
        return services
    out = []
    for s in services:
        if s.family == 'gi.egd' and s.kind == 'egd' and s.status in POSITIVE_STATUSES:
            routing_only = s.status == 'incomplete' and any(c == 'incomplete: routing reads the examination as incomplete'
                                                            for c in s.cues)
            s = dataclasses.replace(
                s, included_in=eus.id,
                status='performed' if routing_only else s.status,
                completion='unknown' if routing_only else s.completion,
                cues=tuple(c for c in s.cues if not (routing_only and c.startswith('incomplete:')))
                + (f'included: the endoscopic portion of {eus.id} (EGD with EUS)',))
        out.append(s)
    return out


def _instrument_families(text: str, start: int, end: int, drafts) -> set:
    """The drafted families the instruments of [start, end) name. The anatomy an unnamed endoscope is read by is read
    once (refutation r1, cost-4, the instrument vocabulary: it was read again for each unnamed endoscope - 39,000 in one
    sentence took the assess stage to 56 s of its 120)."""
    found = set()
    upper = None
    for m in INSTRUMENTS.finditer(text, start, end):
        word = m.group(0).lower()
        family = next((f for name, f in INSTRUMENT_FAMILY if name in word), '')
        if not family and word == 'endoscope':
            upper = _upper_only(text, start, end) if upper is None else upper
            family = upper
        if family in drafts:
            found.add(family)
    return found


def _on_procedure_line(text: str, pos: int, part: _Part) -> bool:
    """The act is listed on a procedure line ("Procedure: Colonoscopy with cold snare polypectomy") or in the title or
    the first line under the report's procedure heading."""
    line_start = text.rfind('\n', 0, pos) + 1
    line_end = text.find('\n', pos)
    line = text[line_start:line_end if line_end >= 0 else len(text)]
    if PROCEDURE_FIELD.match(line):
        return True
    if part.title is not None and part.title.start <= pos < part.title.end:
        return True
    prev_end = line_start - 1
    prev_start = text.rfind('\n', 0, max(prev_end, 0)) + 1
    prev = text[prev_start:prev_end].strip().lower() if prev_end > 0 else ''
    return prev in ('procedure', 'procedures', 'procedure performed', 'procedures performed', 'operation',
                    'procedure(s)', 'procedures performed today')


def _em_service(text: str, routing, context_facts, services, routine_em, sentences, number) -> Optional[DocumentedService]:
    """The office/outpatient E/M service the document documents for this date, from routing's E/M reading, or for a
    note routing reads no E/M in, from the note's own evaluation wording (a sparse note still documents a visit)."""
    finding = routing.finding('gi.office_em') if routing is not None and hasattr(routing, 'finding') else None
    procedures_done = [s for s in services if s.status in POSITIVE]
    facts = {f.name: f for f in (finding.facts if finding is not None else ())}
    cues: list[str] = []
    evidence: list[Span] = []
    if finding is not None:
        status = finding.status if finding.status in SERVICE_STATUSES else 'uncertain'
        for m in finding.mentions:
            if m.status == status and len(evidence) < 4:
                evidence.append(m.sentence if m.sentence.text else m.span)
        if status in POSITIVE:
            # What the visit's level rests on (total time, medical decision making) is part of its evidence.
            for name in ('em_basis', 'time_minutes', 'mdm_level', 'separate_em'):
                fact = facts.get(name)
                for span in (fact.evidence if fact is not None else ())[:2]:
                    ss, se = next(((a, b) for a, b in sentences if a <= span.start < b), (span.start, span.end))
                    evidence.append(_span(text, ss, se))
        cues.append(f'routing reads the office E/M as {status}')
        routing_status = finding.status
    else:
        routing_status = ''
        if procedures_done:
            return None
        found = EM_EVALUATED.search(text)
        structure = NOTE_STRUCTURE.findall(text)
        if not found and len(structure) < 2:
            return None
        status = 'performed' if found else 'uncertain'
        if found:
            ss, se = next(((a, b) for a, b in sentences if a <= found.start() < b), (found.start(), found.end()))
            evidence.append(_span(text, ss, se))
            cues.append('performed: the note documents an evaluation ("' + found.group(0) + '")')
        else:
            cues.append('uncertain: a note with a clinical note structure but no evaluation statement')
    if procedures_done and routine_em and 'separate_em' not in facts:
        status = 'negated'
        cues.append('negated: the document calls today\'s history and examination routine procedure-related work and '
                    'documents no separate E/M')
        evidence = list(routine_em[:2])
    elif routine_em and not procedures_done and status == 'historical':
        pass
    if not evidence and status in POSITIVE + ('uncertain',):
        return None if finding is None else DocumentedService(
            id=f'S{number}', family='gi.office_em', kind='office_em', status=status, cues=tuple(cues),
            routing_status=routing_status, setting=_fact_value(facts.get('setting')) or _setting(context_facts))
    return DocumentedService(
        id=f'S{number}', family='gi.office_em', kind='office_em', status=status,
        evidence=tuple(_dedupe_spans(evidence))[:8],
        cues=tuple(cues), routing_status=routing_status,
        setting=_fact_value(facts.get('setting')) or _setting(context_facts),
        service_date=_service_date_value(context_facts), separate_em='separate_em' in facts,
        uncertainty=tuple(name for name in ('setting', 'patient_status', 'em_basis')
                          if not _fact_value(facts.get(name)) and not (name == 'setting' and _setting(context_facts))))


def _fact_value(fact) -> str:
    return fact.value if fact is not None and getattr(fact, 'value', None) else ''


def _service_date_value(context_facts) -> str:
    if not context_facts:
        return ''
    sd = context_facts.get('service_date')
    return sd.value if sd is not None and getattr(sd, 'origin', '') in ('document', 'user') and sd.value else ''


class _Capped(Exception):
    pass


def _detail(text: str, start: int, end: int, kind: str) -> str:
    clause = text[start:end]
    if kind == 'fna':
        m = re.search(r'\b(\w+)\s+pass(?:es)?\b', clause, FLAGS)
        g = re.search(r'\b(\d{2})[- ]gauge\b', clause, FLAGS)
        return ', '.join(x for x in ((f'{g.group(1)}-gauge' if g else ''), (f'{m.group(1)} passes' if m else '')) if x)
    if kind == 'clip' and re.search(r'\bprophylactic(?:ally)?\b|\bto\s+(?:close|prevent)\b', clause, FLAGS):
        return 'prophylactic'
    m = re.search(r'\b(\d+(?:\.\d+)?\s*(?:mm|cm))\b', clause, FLAGS)
    return m.group(1) if m else ''


# Families whose service has a defined endpoint: the cecum for a colonoscopy or a capsule, beyond the pylorus for an
# EGD, deep cannulation for an ERCP, the full examination for an EUS. An esophagoscopy, a POEM, an enteroscopy, a
# flexible sigmoidoscopy, a physiology study or a tube change has none.
ENDPOINT_FAMILIES = ('gi.colonoscopy', 'gi.ercp', 'gi.eus', 'gi.capsule')


def has_endpoint(family: str, kind: str) -> bool:
    return family in ENDPOINT_FAMILIES or (family == 'gi.egd' and kind in ('egd', 'peg'))


def _routing_fact(finding, name: str):
    if finding is None:
        return None
    return next((f for f in finding.facts if f.name == name and f.value), None)


def _match_lesion(lesions: Sequence[Lesion], size: str, anatomy: str) -> Optional[Lesion]:
    for lesion in reversed(lesions):
        if size and lesion.size and size.replace(' ', '') == lesion.size.replace(' ', ''):
            return lesion
        if not size and anatomy and lesion.anatomy == anatomy:
            return lesion
    if not size and not anatomy and lesions:
        return lesions[-1]
    return None


def _noun_key(noun: str) -> str:
    """A lesion noun (LESION_NOUN) in the singular: whether "the stricture" names a recorded stricture (_build)."""
    noun = noun.lower().replace('tumour', 'tumor')
    for plural, singular in (('ices', 'ix'), ('iae', 'ia'), ('sses', 'ss')):
        if noun.endswith(plural):
            return noun[:-len(plural)] + singular
    return noun[:-1] if noun.endswith('s') and not noun.endswith('ss') else noun


def _covers_of(text: str, anatomy: Sequence[tuple[str, str, int, int]]) -> frozenset:
    """What the sites named at ``anatomy`` (_anatomy_in's mentions) may cover, together (site_covers)."""
    out: frozenset = frozenset()
    for name, _, start, end in anatomy:
        out |= site_covers(name, text[start:end])
    return out


def _heading_service(part: _Part, drafts) -> str:
    """The one documented service (a family in ``drafts``) the part's own heading names ("Nursing checklist -
    colonoscopy"), else '' - a heading that names none, or several, says nothing of which service its entries are
    about."""
    if part.title is None:
        return ''
    named = {family for family, _, pattern in SERVICES if pattern.search(part.title.text)}
    return next(iter(named)) if len(named) == 1 and next(iter(named)) in drafts else ''


def _lesion_for(lesions: Sequence[Lesion], pos: int) -> Optional[Lesion]:
    """The lesion an act at ``pos`` is directed at: the only lesion of its sentence, else the last one named before it."""
    if not lesions:
        return None
    if len(lesions) == 1:
        return lesions[0]
    best = None
    for lesion in lesions:
        if any(ev.start <= pos for ev in lesion.evidence):
            best = lesion
    return best or lesions[0]


def _finish(d: _ServiceDraft, text: str, routing, context_facts, encounter_intents) -> Optional[DocumentedService]:
    statuses = d.statuses
    positive = [s for s in statuses if s[0] == 'performed']
    negative = [s for s in statuses if s[0] in ('negated', 'cancelled')]
    timed = [s for s in statuses if s[0] in ('historical', 'planned')]
    hedged = [s for s in statuses if s[0] == 'uncertain']
    performed_acts = [a for a in d.acts if a.status == 'performed']
    cues: list[str] = []
    if d.report_title is not None or positive or performed_acts:
        status = 'performed'
        decisive = positive[0] if positive else None
        if decisive:
            cues.extend(decisive[1])
        elif d.report_title is not None:
            cues.append(f'section: report title "{d.report_title.text}"')
        else:
            cues.append('performed: acts documented as performed')
    elif negative and not any(c.startswith(HYPOTHETICAL_CUE) for s in hedged for c in s[1]):
        status = 'cancelled' if any(s[0] == 'cancelled' for s in negative) else 'negated'
        cues.extend(negative[0][1])
    elif negative:
        # a hypothetical statement of the service beside a denial ("Colonoscopy would have been performed had ..." after
        # "No colonoscopy was performed at the outside hospital"): held, never newly negated (facts_wording skeptic)
        status = 'uncertain'
        cues.extend(next(s[1] for s in hedged if any(c.startswith(HYPOTHETICAL_CUE) for c in s[1])))
    elif timed:
        status = timed[0][0]
        cues.extend(timed[0][1])
    elif hedged:
        status = 'uncertain'
        cues.extend(hedged[0][1])
    else:
        return None
    completion = 'unknown'
    finding = routing.finding(d.family) if routing is not None and hasattr(routing, 'finding') else None
    routing_status = finding.status if finding is not None else ''
    reach = _routing_fact(finding, 'extent')
    stops = [sp for sp in d.completion_neg if DISCONTINUED.search(sp.text)]
    deep_cannulation = [a for a in d.acts if a.kind == 'cannulation' and a.status == 'performed' and a.evidence
                        and DEEP_CANNULATION.search(a.evidence[0].text)]
    completion_spans: list[Span] = []
    if status == 'performed':
        if not has_endpoint(d.family, d.kind):
            # No defined endpoint (an esophagoscopy, a POEM, an enteroscopy, a physiology study, a tube change): how far
            # the instrument went is no completeness; only a documented discontinuation is.
            if stops:
                completion, status = 'incomplete', 'incomplete'
                cues.append('incomplete: ' + stops[0].text[:120])
                completion_spans = stops
        elif finding is not None:
            # A family routing reads: incompleteness is routing's (its reach logic was hardened over the refutation
            # rounds: "not advanced further" beyond a landmark reached is no incomplete examination), and so is the
            # extent it reads (the landmark the family calls for, reached); this reader adds the completeness
            # statements it can show.
            cannulation = _routing_fact(finding, 'cannulation')
            if routing_status == 'incomplete':
                completion, status = 'incomplete', 'incomplete'
                cues.append('incomplete: routing reads the examination as incomplete')
                completion_spans = list(d.completion_neg) + (list(reach.evidence) if reach else [])
            elif d.completion_pos:
                completion, completion_spans = 'complete', list(d.completion_pos)
            elif reach is not None and not reach.value.startswith('incomplete'):
                completion, completion_spans = 'complete', list(reach.evidence)
                cues.append(f'complete: routing reads the extent as {reach.value}')
            elif d.family == 'gi.ercp' and cannulation is not None and cannulation.value == 'successful':
                completion, completion_spans = 'complete', list(cannulation.evidence)
                cues.append('complete: routing reads the cannulation as successful')
            elif d.family == 'gi.ercp' and deep_cannulation:
                completion, completion_spans = 'complete', list(deep_cannulation[0].evidence)
                cues.append('complete: deep cannulation documented as performed')
        elif d.completion_neg:
            completion = 'incomplete'
            status = 'incomplete'
            cues.append('incomplete: ' + d.completion_neg[0].text[:120])
            completion_spans = list(d.completion_neg)
        elif d.completion_pos:
            completion, completion_spans = 'complete', list(d.completion_pos)
    if routing_status:
        doubting = [m for m in finding.mentions if m.status == 'uncertain'
                    and not any(c.startswith('uncertain: no performance evidence') for c in m.cues)]
        # Routing reads a family from its NAME; its summary of a planned repeat, an earlier examination or a "no prior
        # colonoscopy" in the indication is about another occurrence, never a doubt about the acts documented today.
        # A statement in today's own report that the service was not done, or is planned or past, is.
        contrary = [m for m in finding.mentions
                    if (m.status in ('negated', 'cancelled') and m.section not in ('history', 'indication', 'plan'))
                    or (m.status in ('planned', 'historical')
                        and m.section in ('procedure', 'findings', 'technique', 'impression'))]
        if status in POSITIVE and routing_status in ('planned', 'historical', 'cancelled', 'negated') and contrary:
            cues.append(f'{ROUTING_CONTRARY_CUE}{routing_status}: '
                        + (contrary[0].cues[0] if contrary[0].cues else contrary[0].sentence.text[:80]))
            status = 'uncertain'
        elif status in POSITIVE and routing_status == 'uncertain' and doubting:
            # routing's own doubt about today's service (a hedge, an ambiguous box row, a plan label) holds it
            cues.append(ROUTING_DOUBT_CUE + (doubting[0].cues[0] if doubting[0].cues else 'doubt'))
            status = 'uncertain'
        elif status in ('planned', 'historical', 'cancelled', 'negated') and routing_status in POSITIVE:
            cues.append(f'{ROUTING_CONTRARY_CUE}{routing_status}')
            status = 'uncertain'

    extent = reach.value if reach is not None else ''
    if not extent and status == 'performed' and completion == 'complete' and not d.completion_neg \
            and has_endpoint(d.family, d.kind) and routing_status not in POSITIVE:
        # GI round 4 (E1): routing reads no extent at all (no reach, no stop) and does not read the family as done
        # today, where this reader reads the examination complete by its own endpoint statement ("Neoterminal ileum:
        # normal.", "The duodenal bulb and descending duodenum were normal."): the deepest endpoint landmark those
        # statements name is the extent - never one stated in a history or plan section, under another occurrence or as
        # an extent label (_endpoint_named), never a guess. Where routing reads the family done today, its extent
        # reading (a withheld one too) decides, as before.
        named = _endpoint_named(d.family, completion_spans, text)
        if named:
            extent = named
            cues.append(f'complete: this reader reads the endpoint ({named}) in its own completion statement')
    if finding is not None:
        # A family routing reads takes routing's intent, as it takes routing's extent: read per family, for a service
        # done today, from today's indication and procedure text only - never a question, a hedge, a pending
        # confirmation, a direct denial, a plan or a history (detect._intent; routing reads it for a colonoscopy, so
        # another routed family states none, as the routing-era rationale did). Intent words elsewhere in the document
        # are no reading of this service.
        stated = _routing_fact(finding, 'intent') if routing_status in POSITIVE else None
        intent = str(stated.value) if stated is not None and getattr(stated, 'origin', '') == 'document' else ''
    else:
        own_intents = [i for i in d.intents if not i.startswith('not ')]
        all_intents = own_intents or [i for i in encounter_intents if not i.startswith('not ')]
        intent = all_intents[0] if all_intents else ''
        if not intent and any(i == 'not screening' for i in list(d.intents) + list(encounter_intents)):
            intent = 'diagnostic'
    if d.family in ('gi.ercp', 'gi.eus', 'gi.office_em', 'gi.motility', 'gi.reflux', 'gi.anorectal', 'gi.capsule',
                    'gi.feeding_tube'):
        intent = '' if intent in ('screening', 'surveillance') else intent
    lesions = tuple(_disposition(lesion, d.acts) for lesion in d.lesions)
    evidence = tuple(_dedupe_spans(([d.report_title] if d.report_title else []) + [s[2] for s in positive]))[:6]
    completion_evidence = tuple(_dedupe_spans(completion_spans))[:4]
    spans = list(d.scopes) + [(e.start, e.end) for e in evidence]
    scope_start = min((a for a, _ in spans), default=0)
    scope_end = max((b for _, b in spans), default=0)
    return DocumentedService(
        scope_start=scope_start, scope_end=scope_end,
        id=d.id, family=d.family, kind=d.kind, status=status, completion=completion, extent=extent, intent=intent,
        service_date=_service_date_value(context_facts), setting=_setting(context_facts), role='physician',
        evidence=evidence, completion_evidence=completion_evidence, cues=tuple(dict.fromkeys(cues)), lesions=lesions,
        acts=tuple(_merge_acts(d.acts)), routing_status=routing_status)


def _setting(context_facts) -> str:
    fact = (context_facts or {}).get('setting')
    return fact.value if fact is not None and getattr(fact, 'value', None) else ''


def _disposition(lesion: Lesion, acts: Sequence[Act]) -> Lesion:
    mine = [a for a in acts if a.lesion == lesion.id]
    done = {a.kind for a in mine if a.status == 'performed'}
    if done & {'snare', 'emr', 'esd', 'hot_biopsy'} or any('completely removed' in ev.text.lower() for a in mine
                                                           for ev in a.evidence if a.status == 'performed'):
        disposition = 'removed'
    elif 'biopsy' in done:
        disposition = 'sampled'
    elif any(a.status == 'planned' for a in mine):
        disposition = 'scheduled'
    elif any(a.status == 'negated' for a in mine):
        disposition = 'untreated'
    else:
        disposition = lesion.disposition
    return replace(lesion, disposition=disposition)


def _merge_acts(acts: Sequence[Act]) -> list[Act]:
    """One act per (kind, status, lesion, anatomy, role): a restatement in the impression adds its passage."""
    merged: dict[tuple, Act] = {}
    for act in acts:
        key = (act.kind, act.status, act.lesion, act.anatomy if not act.lesion else (), act.role)
        if key in merged:
            prev = merged[key]
            merged[key] = replace(prev, evidence=tuple(_dedupe_spans(prev.evidence + act.evidence))[:6],
                                  technique=prev.technique or act.technique, detail=prev.detail or act.detail)
        else:
            merged[key] = act
    return list(merged.values())


def _dedupe_spans(spans) -> list[Span]:
    seen, out = set(), []
    for s in spans:
        if s is None:
            continue
        key = (s.start, s.end)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _dedupe_attributions(items: Sequence[Attribution]) -> tuple[Attribution, ...]:
    out: dict[str, Attribution] = {}
    for item in items:
        if item.role in out:
            prev = out[item.role]
            out[item.role] = replace(prev, evidence=tuple(_dedupe_spans(prev.evidence + item.evidence))[:4])
        else:
            out[item.role] = item
    return tuple(out.values())


@dataclass
class _Placements:
    """Where the statements of acts are, read while they are read (_build) and used only to pair them (_same_subject):
    for each passage of an act (its span and kind) what its own sites may cover (site_covers) and whether the lesion it
    is at is one its own sentence names (by its size, its site or its own noun), and for each recorded lesion every site
    its clause names. Never part of the inventory (refutation gi2 status-1 and status-2)."""
    acts: dict = field(default_factory=dict)  # (start, end, kind) -> (covers, own lesion)
    lesions: dict = field(default_factory=dict)  # lesion id -> covers

    def note(self, act: Act, covers: frozenset, own_lesion: bool):
        key = (act.evidence[0].start, act.evidence[0].end, act.kind)
        if key in self.acts:  # two mentions of one kind in one passage: either may be the doubtful one
            known, own = self.acts[key]
            covers, own_lesion = known | covers, own and own_lesion
        self.acts[key] = (covers, own_lesion)


class _DoneIndex:
    """The performed acts of one service, counted by kind for _same_subject: by lesion, those with anatomy and no
    lesion, and the places those at a lesion or a site may cover. Built once per service, so a pair of statements is
    compared in constant time (refutation r1, cost: the scan of every act for every pair of statements was cubic and
    took the assess stage past its limit); only_outside is answered once per kind and set of places."""

    def __init__(self, acts: Sequence[Act], lesions: Sequence[Lesion] = (), placements: Optional[_Placements] = None):
        self.by_lesion: dict[str, dict[str, int]] = {}
        self.lesioned: dict[str, int] = {}
        self.sited: dict[str, int] = {}
        self.placements = placements if placements is not None else _Placements()
        self.lesion_covers = {lesion.id: self.placements.lesions.get(lesion.id)
                              or (site_covers(lesion.anatomy) if lesion.anatomy else frozenset((lesion.region,)) - {''})
                              for lesion in lesions}
        self.placed: dict[str, set[frozenset]] = {}  # per kind, what its acts at a lesion or a site may cover
        self._outside: dict[tuple[str, frozenset], bool] = {}
        self._regions: dict[str, frozenset] = {}  # by act id (unique in a service): read once per statement
        for a in acts:
            if a.status != 'performed':
                continue
            if a.lesion:
                kinds = self.by_lesion.setdefault(a.kind, {})
                kinds[a.lesion] = kinds.get(a.lesion, 0) + 1
                self.lesioned[a.kind] = self.lesioned.get(a.kind, 0) + 1
            elif a.anatomy:
                self.sited[a.kind] = self.sited.get(a.kind, 0) + 1
            regions = self.regions(a)
            if regions:
                self.placed.setdefault(a.kind, set()).add(regions)

    def regions(self, act: Act) -> frozenset:
        """The places a statement of an act may be at (site_covers): its own anatomy's, else - naming none - its
        lesion's when every passage of it names that lesion as its own (_Placements). A lesion "the lesion" or "it"
        only fell back to is at no place that can be told, so nothing is read from it (refutation gi2 status-1)."""
        if act.id in self._regions:
            return self._regions[act.id]
        noted = [self.placements.acts.get((span.start, span.end, act.kind)) for span in act.evidence]
        if act.anatomy:
            known = [placed[0] for placed in noted if placed is not None and placed[0]]
            out = frozenset().union(*known) if known else frozenset().union(*(site_covers(name)
                                                                               for name in act.anatomy))
        elif act.lesion and noted and all(placed is not None and placed[1] for placed in noted):
            out = self.lesion_covers.get(act.lesion, frozenset())
        else:
            out = frozenset()
        if act.id:
            self._regions[act.id] = out
        return out

    def only_outside(self, kind: str, regions: frozenset) -> bool:
        """Whether acts of ``kind`` are documented done at lesions or sites, each of them outside all ``regions``."""
        key = (kind, regions)
        if key not in self._outside:
            placed = self.placed.get(kind, ())
            self._outside[key] = bool(placed) and not any(sites & regions for sites in placed)
        return self._outside[key]

    def elsewhere(self, done: Act, denied: Act) -> bool:
        """Whether another act of done's kind is documented at another lesion, or at a site with no lesion."""
        other_lesions = self.lesioned.get(done.kind, 0) - self.by_lesion.get(done.kind, {}).get(denied.lesion, 0) \
            - (1 if done.lesion and done.lesion != denied.lesion else 0)
        other_sites = self.sited.get(done.kind, 0) - (1 if not done.lesion and done.anatomy else 0)
        return other_lesions > 0 or other_sites > 0


def _same_subject(done: Act, denied: Act, index: _DoneIndex) -> bool:
    """Whether a statement that an act was done and one that it was not are about the same act of one service:
    - both about lesions: the same lesion;
    - the denial about the service as a whole ("no tattoo was placed"): any act of that kind done, unless both name
      anatomy and the sites differ ("biopsies from the antrum" beside "the duodenum was not biopsied");
    - the denial about one lesion, the statement of the act about none ("Colonoscopy with cold snare polypectomy"
      beside "This lesion was not removed by snare"): only when no act of that kind is documented at another lesion or
      site, which would be what the summary speaks of;
    - the denial about sites, the statement of the act naming none (gi2 conflicts, PR1). An act at a lesion is at that
      lesion's site: it is another subject when the lesion lies in a region the denial does not name ("No pancreatic
      stent was placed" beside the stent deployed across the bile duct stricture). A summary naming neither a site nor
      a lesion ("EGD with ... cold forceps biopsies") is another subject only when the acts of that kind documented
      done at a lesion or a site all lie outside the denied regions: it lists those ("No gastric or duodenal biopsies
      were taken" beside the esophageal biopsies it lists). Read by region, never by site name: one such act inside a
      denied region ("biopsies were also taken from the antrum" under "no gastric biopsies", which the site names alone
      never pair) keeps the summary paired, so a statement that may be about the denied site still pairs and the doubt
      is kept. Regions are compared by what their sites may cover (site_covers: the small bowel holds the duodenum,
      the large bowel the rectum), so only disjoint places are different subjects; and an act is at its lesion's site
      only when its own sentence names that lesion - one "the lesion" fell back to pairs, as any statement whose place
      cannot be told does (refutation gi2 status-1 and status-2)."""
    if done.lesion and denied.lesion:
        return done.lesion == denied.lesion
    if done.anatomy and denied.anatomy and not set(done.anatomy) & set(denied.anatomy):
        return False
    if denied.lesion and not done.lesion:
        return not index.elsewhere(done, denied)
    if denied.anatomy and not done.anatomy:
        denied_regions = index.regions(denied)
        if denied_regions:
            if done.lesion:
                site = index.regions(done)
                return not site or bool(site & denied_regions)
            return not index.only_outside(done.kind, denied_regions)
    return True


RELATED_KINDS = {'tattoo': ('tattoo', 'injection'), 'injection': ('injection', 'tattoo'), 'specimen': ('biopsy',)}
# The acts done that a denial of each kind is about (RELATED_KINDS read the other way): what an encounter's denial is
# set beside (_build).
DENIED_BY = {kind: frozenset(done for done in ACT_KINDS if kind in RELATED_KINDS.get(done, (done,)))
             for kind in ACT_KINDS}
# Acts that take tissue: a specimen recorded beside any of them is accounted for.
TISSUE_KINDS = frozenset(('biopsy', 'hot_biopsy', 'snare', 'emr', 'esd', 'fna', 'foreign_body'))


def _conflicts(services: Sequence[DocumentedService],
               placements: Optional[_Placements] = None) -> tuple[Conflict, ...]:
    """Acts of one service that the document states both as done and as not done today. A difference of time
    (historical vs today) is not a conflict, nor a denial of further acts beyond the documented ones; a statement about
    one lesion never conflicts with one about another lesion or another site. ``placements`` (read by _build) says
    where each statement is; without it nothing is read from a lesion an act is at."""
    out: list[Conflict] = []
    for service in services:
        # an act never reported on its own (catalogue.NOT_REPORTED: clips, cannulation) changes no code, so its done and
        # denied statements are not a coding conflict ("Deep biliary cannulation was achieved" beside "The pancreatic
        # duct was neither cannulated nor injected")
        from studio.gi import catalogue  # local: catalogue reads this module's vocabulary
        done = [a for a in service.acts if a.status == 'performed' and a.kind not in catalogue.NOT_REPORTED]
        denied = [a for a in service.acts if a.status in ('negated', 'cancelled')]
        index = _DoneIndex(service.acts, service.lesions, placements)
        for d_act in done:
            kinds = RELATED_KINDS.get(d_act.kind, (d_act.kind,))
            if d_act.kind == 'specimen' and any(a.kind in TISSUE_KINDS for a in done):
                continue  # a specimen beside a documented biopsy or removal: that act's specimen
            against = [n for n in denied if n.kind in kinds and _same_subject(d_act, n, index)]
            if not against:
                continue
            subject = 'tattoo' if 'tattoo' in kinds else 'biopsy' if d_act.kind == 'specimen' else d_act.kind
            if any(c.service == service.id and c.subject == subject and c.lesion == d_act.lesion for c in out):
                continue
            sides: list[ConflictSide] = [ConflictSide(d_act.status, d_act.role, d_act.evidence)]
            seen = {tuple((e.start, e.end) for e in d_act.evidence)}
            for n in against:
                key = tuple((e.start, e.end) for e in n.evidence)
                if key not in seen:
                    seen.add(key)
                    sides.append(ConflictSide(n.status, n.role, n.evidence))
            if len(sides) < 2:
                continue
            roles = sorted({side.role for side in sides})
            note = ('The document states this act both as performed and as not performed'
                    + (f' ({" and ".join(roles)} entries).' if len(roles) > 1 else '.'))
            out.append(Conflict(id=f'{service.id}-C{len(out) + 1}', service=service.id, subject=subject,
                                lesion=d_act.lesion, sides=tuple(sides), note=note))
    return tuple(out)


# --- validation -------------------------------------------------------------------------------------------------

def validate(inventory: ServiceInventory, text: str) -> tuple[str, ...]:
    """Problems with the inventory's structure: every passage exact, every value in its vocabulary, every reference
    resolvable. An empty tuple means the inventory is internally consistent (not that it is complete)."""
    problems: list[str] = []
    ids = set()

    def exact(span: Span, where: str):
        if not (0 <= span.start <= span.end <= len(text)) or text[span.start:span.end] != span.text:
            problems.append(f'{where}: a passage does not match the revision text at its offsets.')

    for s in inventory.services:
        if s.id in ids:
            problems.append(f'Service id {s.id} is repeated.')
        ids.add(s.id)
        if s.status not in SERVICE_STATUSES:
            problems.append(f'{s.id}: unknown status {s.status!r}.')
        if s.completion not in COMPLETIONS:
            problems.append(f'{s.id}: unknown completion {s.completion!r}.')
        for span in s.evidence + s.completion_evidence:
            exact(span, s.id)
        lesion_ids = {l.id for l in s.lesions}
        for lesion in s.lesions:
            for span in lesion.evidence:
                exact(span, lesion.id)
        for act in s.acts:
            if act.kind not in ACT_KINDS:
                problems.append(f'{act.id}: unknown act {act.kind!r}.')
            if act.status not in ACT_STATUSES:
                problems.append(f'{act.id}: unknown act status {act.status!r}.')
            if act.role not in ROLES:
                problems.append(f'{act.id}: unknown role {act.role!r}.')
            if act.lesion and act.lesion not in lesion_ids:
                problems.append(f'{act.id}: refers to a lesion that is not documented.')
            if not act.evidence:
                problems.append(f'{act.id}: an act without a passage.')
            for span in act.evidence:
                exact(span, act.id)
    for c in inventory.conflicts:
        if c.service not in ids:
            problems.append(f'{c.id}: refers to a service that is not inventoried.')
        for side in c.sides:
            for span in side.evidence:
                exact(span, c.id)
    for a in inventory.attributions:
        for span in a.evidence:
            exact(span, f'attribution {a.role}')
    return tuple(problems)
