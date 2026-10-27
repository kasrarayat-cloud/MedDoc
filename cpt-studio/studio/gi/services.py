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
ACT_VERB = _rx(r'\b(?:was|were|been|is|are)\s+(?:then\s+|also\s+|successfully\s+|subsequently\s+|completely\s+|each\s+)?'
               r'(?:performed|done|obtained|taken|removed|resected|retrieved|excised|placed|deployed|inserted|applied|'
               r'achieved|injected|tattooed|ablated|treated|dilated|banded|clipped|cleared|extracted|swept|sampled|'
               r'biopsied|snared|cannulated|completed|carried\s+out|accomplished|made|used|passed|advanced|'
               r'introduced|reached|intubated|replaced|exchanged|ingested|recorded|positioned|attached|delivered|'
               r'fragmented|crushed|cut|sent|submitted|marked|administered|given|provided|supervised|closed)\b'
               r'|\b(?:we|I)\s+(?:then\s+)?(?:performed|obtained|took|removed|resected|placed|deployed|injected|ablated|'
               r'dilated|banded|clipped|extracted|biopsied|snared|sampled|cannulated|passed|advanced|replaced|'
               r'administered|gave|provided|supervised)\b'
               r'|\bunderwent\b|\bunderwent\s+successful\b')
# A participle naming the act with no auxiliary ("polyps removed by cold snare", "biopsies taken").
BARE_PARTICIPLE = _rx(r'\b(?:performed|obtained|taken|removed|resected|retrieved|placed|deployed|injected|ablated|treated|'
                      r'dilated|banded|clipped|extracted|sampled|biopsied|snared|achieved|done|completed|sent|replaced|'
                      r'exchanged|reinserted|ligated|administered|decompressed|disrupted|inflated|left\s+in\s+(?:place|situ))\b')
NEG_LEAD = _rx(r'^(?:[\s\-*•(]*(?:[A-Z]{1,3}\d{1,2}|\d{1,2}[.)])?\s*)*(?:no|neither|none|nor|without|there\s+was\s+no'
               r'|there\s+were\s+no)\b')
NEG_OTHER = _rx(r'^(?:[\s\-*•(]*(?:[A-Z]{1,3}\d{1,2}|\d{1,2}[.)])?\s*)*(?:no|neither|none|nor|there\s+(?:was|were)\s+no)'
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
# Reviewing earlier records is today's work: "review of prior records" never makes its clause historical.
REVIEW_OF_RECORDS = _rx(r'\breview(?:ed|ing)?\s+(?:of\s+)?(?:the\s+)?(?:prior|previous|old|outside|earlier)\s+'
                        r'(?:records?|notes?|results?|reports?|imaging|studies|labs?|pathology|colonoscopy|endoscopy|'
                        r'charts?)\b')
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


def _family_named(line: str) -> tuple[str, str]:
    for family, kind, pattern in SERVICES:
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
# reviewed (03/2023)")
_DATE_COMPANIONS = (r'(?:[ \t,:\-–—(/]+|\b(?:' + HEADING_EARLIER + r'|' + HEADING_LATER
                    + r'|facility|hospital|center|centre|institution|clinic|elsewhere|reviewed|dated|on|of|from|in|at|'
                      r'an?|the)\b)')
_ALONE_AFTER = r'(?:[ \t]+(?:facility|hospital|center|centre|institution|clinic|elsewhere))?[ \t]*(?:[),:]|\Z)'
HEADING_EARLIER_NAMED = _rx(r'\b' + HEADING_EARLIER + r'\b(?:[ \t]+[\w-]+){0,2}?[ \t]+' + _NAMED
                            + r'|' + _NAMED + r'[ \t]+(?:history|hx)\b'
                            + r'|' + _NAMED + r'[ \t,(\-\u2013]+' + HEADING_EARLIER + _ALONE_AFTER + r'|\bsince\b')
HEADING_LATER_NAMED = _rx(r'\b' + HEADING_LATER + r'\b(?:[ \t]+[\w-]+){0,2}?[ \t]+' + _NAMED
                          + r'|' + _NAMED + r'[ \t,(\-\u2013]+' + HEADING_LATER + _ALONE_AFTER)
HEADING_DATE_BEFORE = _rx(_NAMED + _DATE_COMPANIONS + r'*\Z')  # the label up to a date: the date dates what it names
HEADING_DATE_AFTER = _rx(r'(?:[ \t,:\-–—)]+|\b(?:an?|the)\b)*' + _NAMED)  # a date that leads the name
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
    that ends the block, where the part resumes (routing reads both the same way: gi/sections layout)."""
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
    return _time_parts(text, out)


def _time_parts(text: str, plist: Sequence[_Part]) -> tuple[_Part, ...]:
    """The parts with their history and plan sections where routing's section layout (studio.gi.sections, the structure
    the refutation rounds hardened: inline and wrapped labels, field labels, held lines) puts them, from where such a
    section opens to where it ends. "Prior colonoscopies:", "Past history:", "Impression and Recommendations:",
    "Procedures to be done:" and "Plan: Dr. Smith recommended" open one; the next section the layout opens ("Findings:")
    ends it, as it ends a history or plan part this module's own headings opened. A heading the layout adds whose own
    line already carries a complete statement ("History: an outside EUS-guided biopsy showed adenocarcinoma.") speaks
    for that line only, as a field does. A part keeps its family, role and title; a role part keeps its reading, and a
    plan section inside a titled report stays that report's (its title owns its subsections, as PLAN_HEADING has it)."""
    lay = _sections.layout(text)
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


def _sentences(text: str) -> list[tuple[int, int]]:
    """Sentences: split at a full stop, question or exclamation mark followed by space and a capital or digit or a
    list label, at a line that starts a numbered or labelled item, after a line that ends in an answer of its own
    (_answered_line), and at blank lines. Line wraps inside a sentence are kept (PDF text wraps mid-sentence)."""
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

_CLAUSE_CUT = _rx(r';|\s+but\s+|\s+whereas\s+|\s+although\s+|,\s+while\s+'
                  r'|\s+and\s+(?=(?:was|were|is|are)(?:\s+(?:not|never)|' + NEG_CONTRACTION + r')\b)'
                  # "Biopsies were obtained and dilation was not performed": a coordinated subject with its own negated
                  # predicate opens a clause of its own, so its "not" never reaches the first act
                  r'|\s+and\s+(?=(?:[\w-]+\s+){1,3}(?:was|were|is|are|could|did|had)(?:\s+(?:not|never)|'
                  + NEG_CONTRACTION + r')\b)'
                  r'|(?<![\d.])\s+and\s+(?=(?:the|a|an|this|that|it|she|he|they|we|I|one|two|three|\d+)\b[^.;]{0,60}\b(?:was|were|'
                  r'is|are|has|have|had|did)(?:' + NEG_CONTRACTION + r')?\b)|,\s+(?=(?:and\s+)?(?:the|this|that|it|she|he|they|'
                  r'we|I)\s+[^.;,]{0,40}\b(?:was|were|is|are)(?:' + NEG_CONTRACTION + r')?\b)')


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


def clauses(text: str, start: int, end: int) -> list[tuple[int, int]]:
    out, pos = [], start
    for m in _CLAUSE_CUT.finditer(text, start, end):
        seg = _trim(text, pos, m.start())
        if seg:
            out.append(seg)
        pos = m.end()
    seg = _trim(text, pos, end)
    if seg:
        out.append(seg)
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
        checked = re.search(_box_symbols.BOX_ON_PATTERN, text[line_start:line_end])
        if status == 'negated' and not checked and any('unchecked' in cue for cue in box_cues):
            # no option on the row is marked: an unselected option alone says nothing (the box contract)
            return Reading('uncertain', ('box: an unselected option alone says nothing',))
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
        if not auxiliaries or own or negated_again:
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
        if not auxiliaries or (len(auxiliaries) == 1
                               and re.search(r'\b(?:was|were|is|are|been)\s+(?:[\w-]+ly\s+)?$', tail, FLAGS)):
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
    if any(not WITHOUT_COMPLICATION.match(near, w.start()) for w in WITHOUT.finditer(near)):
        return Reading('negated', ('negated: "without" before it',))
    if REPLACED.search(before[-80:]):
        return Reading('negated', (REPLACED_CUE,))
    if CANCEL_WORDS.search(whole):
        return Reading('cancelled', ('cancelled: ' + CANCEL_WORDS.search(whole).group(0).lower(),))
    # Time: a date in the clause.
    for d in _dates_in(dates, cs, ce):
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
    hist = next((h for h in HISTORY_WORDS.finditer(whole) if not REVIEW_OF_RECORDS.search(
        whole, max(0, h.start() - 30), min(len(whole), h.end() + 40))), None)
    if hist and not TODAY_WORDS.search(whole):
        return Reading('historical', ('historical: ' + hist.group(0).lower(),))
    plan = PLAN_WORDS.search(whole)
    if plan and not (TODAY_WORDS.search(whole) and ACT_VERB.search(whole)):
        return Reading('planned', ('planned: ' + plan.group(0).lower(),))
    # A history or plan section dates what it names before a hedge in the clause is read: a hedged item of a plan is
    # still planned ("1. Dysphagia, likely peptic stricture - upper endoscopy with dilation at the hospital"), never a
    # doubt about a service done today.
    if part.kind == 'history' and not TODAY_WORDS.search(whole):
        return Reading('historical', ('historical: in a history section',))
    if part.kind == 'plan' and not TODAY_WORDS.search(whole):
        return Reading('planned', ('planned: in a plan section',))
    hedge = HEDGE_WORDS.search(whole)
    if hedge:
        return Reading('uncertain', ('uncertain: ' + hedge.group(0).lower(),))
    hypothetical = _hypothetical(text, cs, ce, pos, end, report=in_today_report or part.kind in ('report', 'section'))
    if hypothetical:
        return Reading('uncertain', (HYPOTHETICAL_CUE + hypothetical,))
    if part.kind == 'indication' and not TODAY_WORDS.search(whole):
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
        if in_today_report or TODAY_WORDS.search(whole) or part.kind == 'report':
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


def _own_question(text: str, start: int, end: int) -> bool:
    """Whether the field label [start, end) is an item's own question: every word of it outside the acts and services
    it names is a word of that question (routing's _BOX_ITEM_WORDS: "Biopsy taken", "Was a biopsy performed"), as
    routing's _box_label_kind reads an 'item' label; a time, an attribute or a count ("Biopsy (Y/N)", "Flexible
    sigmoidoscopy in the last 10 years") makes it another question."""
    from studio.gi import detect  # local: detect imports context, which this module also imports
    names = [(a, b) for _, a, b in _acts_in(text, start, end)]
    names += [(m.start(), m.end()) for _, _, pattern in SERVICES for m in pattern.finditer(text, start, end)]
    return all(w.group(0).lower() in detect._BOX_ITEM_WORDS for w in detect._BOX_LABEL_WORD.finditer(text, start, end)
               if not any(a <= w.start() < b for a, b in names))


# A typed field whose label and answer a spaced dash separates ("Biopsy taken - No", "Tattoo placed \u2013 none"): read as a
# field, but a denial it gives only holds (a dash also joins prose), never excludes.
FIELD_DASH = re.compile(r'[ \t]+[-\u2013\u2014][ \t]+')
DASH_FIELD_CUE = 'field: its label and answer are separated by a dash, so its denial holds, never excludes'


def _field_answer(text: str, pos: int, end: int, service_date: Optional[date]) -> Optional[Reading]:
    """_field_answer_read, with a dash-separated field's denial held (FIELD_DASH)."""
    reading = _field_answer_read(text, pos, end, service_date)
    if reading is not None and reading.status == 'negated':
        ls = text.rfind('\n', 0, pos) + 1
        le = text.find('\n', end)
        le = len(text) if le < 0 else le
        if text.find(':', ls, le) < 0:
            return Reading('uncertain', reading.cues + (DASH_FIELD_CUE,))
    return reading


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
    dash = FIELD_DASH.search(text, end, le) if colon < 0 else None
    if dash is not None:
        colon = dash.start()
    if colon < end or ls > pos:
        return None  # no label, or the mention is in the answer ("Findings: biopsies were taken")
    from studio.gi import detect  # local: detect imports context, which this module also imports
    line = text[ls:le] if dash is None else text[ls:colon] + ':' + text[dash.end():le]
    label_end = colon - ls
    value = (text[colon + 1:le] if dash is None else text[dash.end():le]).strip()
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
        return Reading('uncertain', (f'field: the answer \u201c{value}\u201d is not read as done or not done',))
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


def _family_for_act_in(kind: str, region: str, part_family: str, present: Sequence[str]) -> str:
    if kind in KIND_FAMILIES:
        options = [f for f in KIND_FAMILIES[kind] if f in present]
        if kind == 'manometry' and len(options) > 1:
            options = ['gi.anorectal'] if region in ('rectum', 'anus') else ['gi.motility']
        if len(options) == 1:
            return options[0]
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


def build(text: str, *, service_date: Optional[date], routing=None, context_facts=None) -> ServiceInventory:
    """The documented services of ``text`` for the effective ``service_date``. ``routing`` (a RoutingResult) supplies
    routing's family readings, kept beside each service and used, fail-closed, where the two readings disagree.

    The reader reads a same-length view of the text in which a line break inside a sentence (a PDF or scan wrapping
    its line) is a space (``reflow``); every offset is the text's own, and every passage it returns is the text's."""
    flow = reflow(text)
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
_TERMINAL = re.compile(r'[.:;!?]["\')\]]*[ \t]*$')


def reflow(text: str) -> str:
    """``text`` with each soft line break - a wrap inside a sentence - replaced by a space, one character for one.

    A break is soft only when the line before it is a long run of prose (25+ characters and 4+ words) that does not
    end a sentence or a label and does not end in an answer of its own (_answered_line, the rule _sentences cuts at),
    and the next line continues it in lower case, or after a word that cannot end a line (_DANGLING), a comma, or
    before a line opening with a parenthesis; never around a
    check-box or option row, a table row, a list item or a labelled field, and never inside an extraction block.
    Headings, labels, fields and short lines keep their breaks."""
    if '\n' not in text:
        return text
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
        ne = text.find('\n', i + 1)
        nxt = text[i + 1:ne if ne >= 0 else n]
        stripped = prev.strip()
        in_block = bool(_sections.FORM_BLOCK.fullmatch(stripped)) or (in_block and bool(stripped))
        if in_block:
            continue  # an extraction block's lines are each a field, never one wrapped sentence
        if len(stripped) < 25 or len(stripped.split()) < 4 or _TERMINAL.search(prev):
            continue
        if _LIST_ITEM.match(nxt) or _NEXT_ITEM.match(nxt):
            continue
        if not _SOFT_NEXT.match(nxt) and not ((_DANGLING.search(prev) or prev.rstrip().endswith(',')
                                               or nxt.lstrip().startswith('(')) and nxt.strip()
                                              and not GENERIC_HEADING.match(nxt.strip())):
            continue
        if '|' in prev or '|' in nxt or '\t' in prev or '\t' in nxt:
            continue
        if BOX_MARK.search(prev) or BOX_MARK.search(nxt):
            continue
        if _answered_line(text, ls, i, i + 1):
            continue  # "... and said no" / "Hiatal hernia - no": the answer ends its line
        out[i] = ' '
    return ''.join(out)


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
    # A sentence (or its first SENTENCE_READ_CHARS) is cut into clauses once, and every mention read in it shares the
    # cut (refutation r1, cost-6: each named service and each instrument cut its whole sentence again - 299 names at
    # the head of one 196,000-character sentence took 13 s).
    cuts: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def clauses_of(start: int, end: int) -> list[tuple[int, int]]:
        if (start, end) not in cuts:
            cuts[(start, end)] = clauses(text, start, end)
        return cuts[(start, end)]

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
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            for m in INSTRUMENTS.finditer(text, ss, se):
                word = m.group(0).lower()
                family = next((f for name, f in INSTRUMENT_FAMILY if name in word), part.family) \
                    or (_upper_only(text, ss, se) if word == 'endoscope' else '')
                if not family:
                    continue
                clause = _clause_for(clauses_of(ss, se), m.start())
                reading = read_clause(text, clause, m.start(), m.end(), service_date=service_date, dates=dates,
                                      part=part, in_today_report=part.kind == 'report' and part.family == family)
                reading = held_under_denial(text, m.start(), reading, service_date)
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
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            read_end = min(se, ss + SENTENCE_READ_CHARS)
            if se > read_end:
                problems.append(f'A sentence of {se - ss:,} characters at offset {ss} was read for acts only in its '
                                f'first {SENTENCE_READ_CHARS:,} characters.')
            mentions = _acts_in(text, ss, read_end)
            lesion_matches = list(LESION.finditer(text, ss, read_end))
            if not mentions and not lesion_matches:
                continue
            cls = clauses_of(ss, read_end)
            anatomy_all = _anatomy_in(text, ss, read_end)
            regions = {region for _, region, _, _ in anatomy_all}
            part_family = part.family if part.family in drafts and part.kind == 'report' else ''
            named_here = sorted({f for f in named_in.get(ss, ()) if f in drafts}
                                | _instrument_families(text, ss, se, drafts))
            if not part_family and len(named_here) == 1:
                part_family = named_here[0]
            if not part_family and len(procedural) == 1 and part.kind not in ('history', 'plan'):
                part_family = procedural[0]
            sentence_text = text[ss:se]
            denies_further = bool(NEG_OTHER.match(sentence_text))
            # Lesions in this sentence (never from a denial or a "no other" statement).
            sentence_lesions: list[Lesion] = []
            for lm in lesion_matches:
                lead = (lm.group('lead') or '').strip().lower()
                tail = text[lm.end():lm.end() + 14].lower()
                if re.match(r'\s+(?:treatment|resection|removal|site|bed|base|margin)', tail):
                    continue
                region_one = next(iter(regions)) if len(regions) == 1 else ''
                fam = _family_for_act('biopsy', region_one, part_family, present_families, performed_families)
                if not fam or fam not in drafts or denies_further:
                    continue
                d = drafts[fam]
                clause = _clause_for(cls, lm.start())
                reading = read_clause(text, clause, lm.start(), lm.end(), service_date=service_date, dates=dates,
                                      part=part, in_today_report=part.kind == 'report')
                if reading.status in ('historical', 'planned', 'negated'):
                    if not (lead in ('this', 'that', 'the') or not lm.group('size')):
                        continue
                anat = [a for a in anatomy_all if clause[0] <= a[2] < clause[1]] or anatomy_all
                specimen = SPECIMEN.search(text, ss, se)
                size = re.sub(r'\s+', ' ', (lm.group('size') or '').strip())
                existing = None
                if lead in ('this', 'that', 'the', 'it') or not (size or lead):
                    existing = _match_lesion(d.lesions, size, anat[0][0] if anat else '')
                creatable = (size or lead in ('a', 'an', 'one', 'two', 'three', 'four', 'five', 'six', 'several',
                                              'multiple', 'a separate', 'another') or lead.isdigit())
                if existing is None and creatable and anat and reading.status not in ('negated', 'historical',
                                                                                       'planned'):
                    if lm.group('noun').lower().rstrip('s') in ('stricture', 'ring', 'erosion') and not size:
                        continue
                    if len(d.lesions) >= MAX_LESIONS_PER_SERVICE:
                        problems.append(f'More than {MAX_LESIONS_PER_SERVICE} lesions are documented for one service; '
                                        'the rest were not inventoried.')
                        continue
                    lesion = Lesion(id=f'{d.id}-L{len(d.lesions) + 1}', service=d.id, noun=lm.group('noun').lower(),
                                    size=size, morphology=re.sub(r'[\s,]+', ' ', lm.group('morph') or '').strip(),
                                    anatomy=anat[0][0], region=anat[0][1],
                                    specimen=(specimen.group('label') or specimen.group('label2')) if specimen else '',
                                    evidence=(_span(text, ss, read_end),))
                    d.lesions.append(lesion)
                    sentence_lesions.append(lesion)
                elif existing is not None:
                    sentence_lesions.append(existing)
            if not sentence_lesions and ANAPHORA.match(text, ss, se):
                fam = part_family
                if fam and fam in last_lesion:
                    sentence_lesions.append(last_lesion[fam])
            if denies_further:
                continue  # "No other colon biopsy or lesion treatment was performed": nothing beyond the documented acts
            # Acts in this sentence.
            for kind, ms, me in mentions:
                clause = _clause_for(cls, ms)
                anat = [a for a in anatomy_all if clause[0] <= a[2] < clause[1]] or anatomy_all
                region = anat[0][1] if anat else ''
                fam = _family_for_act(kind, region, part_family, present_families, performed_families)
                if not fam or fam not in drafts:
                    continue
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
                d = drafts[fam]
                d.scopes.append((part.start, part.end) if part.kind == 'report' and part.family == fam else (ss, se))
                lesion = _lesion_for(sentence_lesions, ms)
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
                d.acts.append(Act(id=f'{d.id}-A{len(d.acts) + 1}', service=d.id, kind=kind, status=reading.status,
                                  role=role, anatomy=tuple(dict.fromkeys(a[0] for a in anat)), region=region,
                                  technique=_technique(text, *bc, near=ms), lesion=lesion.id if lesion else '',
                                  evidence=(_span(text, *bc),), cues=reading.cues,
                                  detail=_detail(text, *bc, kind)))
            if sentence_lesions:
                lesion = sentence_lesions[-1]
                for f, d in drafts.items():
                    if d.id == lesion.service:
                        last_lesion[f] = lesion
    except _Capped as exc:
        problems.append(str(exc))
    services = [_finish(d, text, routing, context_facts, encounter_intents) for d in drafts.values()]
    services = _included([s for s in services if s is not None])
    em = _em_service(text, routing, context_facts, services, routine_em, sentences, len(services) + 1)
    if em is not None:
        services.append(em)
    services = tuple(services)
    conflicts = _conflicts(services)
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


def _included(services: list) -> list:
    """An upper endoscopy performed with an EUS in the same session is the EUS's endoscopic portion: the EUS code
    includes the examination (EGD with EUS), so the EGD is kept, marked included, and asks for no code of its own. How
    far the ultrasound went never makes the endoscopic examination incomplete. Its own acts are still reconciled."""
    eus = next((s for s in services if s.family == 'gi.eus' and s.status in POSITIVE_STATUSES), None)
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
    found = set()
    for m in INSTRUMENTS.finditer(text, start, end):
        word = m.group(0).lower()
        family = next((f for name, f in INSTRUMENT_FAMILY if name in word), '') \
            or (_upper_only(text, start, end) if word == 'endoscope' else '')
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


class _DoneIndex:
    """The performed acts of one service, counted by kind for _same_subject: by lesion, and those with anatomy and no
    lesion. Built once per service, so a pair of statements is compared in constant time (refutation r1, cost: the scan
    of every act for every pair of statements was cubic and took the assess stage past its limit)."""

    def __init__(self, acts: Sequence[Act]):
        self.by_lesion: dict[str, dict[str, int]] = {}
        self.lesioned: dict[str, int] = {}
        self.sited: dict[str, int] = {}
        for a in acts:
            if a.status != 'performed':
                continue
            if a.lesion:
                kinds = self.by_lesion.setdefault(a.kind, {})
                kinds[a.lesion] = kinds.get(a.lesion, 0) + 1
                self.lesioned[a.kind] = self.lesioned.get(a.kind, 0) + 1
            elif a.anatomy:
                self.sited[a.kind] = self.sited.get(a.kind, 0) + 1

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
      site, which would be what the summary speaks of."""
    if done.lesion and denied.lesion:
        return done.lesion == denied.lesion
    if done.anatomy and denied.anatomy and not set(done.anatomy) & set(denied.anatomy):
        return False
    if denied.lesion and not done.lesion:
        return not index.elsewhere(done, denied)
    return True


RELATED_KINDS = {'tattoo': ('tattoo', 'injection'), 'injection': ('injection', 'tattoo'), 'specimen': ('biopsy',)}
# Acts that take tissue: a specimen recorded beside any of them is accounted for.
TISSUE_KINDS = frozenset(('biopsy', 'hot_biopsy', 'snare', 'emr', 'esd', 'fna', 'foreign_body'))


def _conflicts(services: Sequence[DocumentedService]) -> tuple[Conflict, ...]:
    """Acts of one service that the document states both as done and as not done today. A difference of time
    (historical vs today) is not a conflict, nor a denial of further acts beyond the documented ones; a statement about
    one lesion never conflicts with one about another lesion or another site."""
    out: list[Conflict] = []
    for service in services:
        # an act never reported on its own (catalogue.NOT_REPORTED: clips, cannulation) changes no code, so its done and
        # denied statements are not a coding conflict ("Deep biliary cannulation was achieved" beside "The pancreatic
        # duct was neither cannulated nor injected")
        from studio.gi import catalogue  # local: catalogue reads this module's vocabulary
        done = [a for a in service.acts if a.status == 'performed' and a.kind not in catalogue.NOT_REPORTED]
        denied = [a for a in service.acts if a.status in ('negated', 'cancelled')]
        index = _DoneIndex(service.acts)
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
