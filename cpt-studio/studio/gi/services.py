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
import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Optional, Sequence

from studio.gi import context as gi_context
from studio.types import Span

INVENTORY_VERSION = 'gi-services@1'

FLAGS = re.A | re.I

# Bounds (reading stops and says so; nothing is silently truncated).
MAX_SENTENCES = 6000
MAX_ACTS = 2000
MAX_LESIONS_PER_SERVICE = 60
MAX_SERVICES = 40
SENTENCE_READ_CHARS = 1200  # a longer sentence is read in its first part for acts, and the rest is a problem

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
                                 r'(?:manometry|motility\s+(?:study|testing))\b|\bmanometry\b'),
    ('gi.feeding_tube', 'feeding_tube', r'\bPEG(?:-J)?\b|\bpercutaneous\s+endoscopic\s+(?:gastrostomy|jejunostomy)\b'
                                        r'|\bgastrostomy\s+tube\b|\bG-?tube\b|\bjejunostomy\s+tube\b|\bJ-?tube\b'
                                        r'|\bgastrostomy\s+(?:button|tube)\s+(?:replacement|change|exchange)\b'),
    ('gi.enteroscopy', 'enteroscopy', r'\b(?:push\s+|small[- ]bowel\s+|deep\s+|spiral\s+|(?:double|single)[- ]balloon\s+'
                                      r'|balloon[- ]assisted\s+|device[- ]assisted\s+)?enteroscop(?:y|ies|e)\b'),
    ('gi.egd', 'egd', r'\bEGD\b|\besophagogastroduodenoscop(?:y|ies)\b|\bupper\s+(?:GI\s+|gastrointestinal\s+)?'
                      r'endoscop(?:y|ies)\b(?!\s+ultraso)|\bgastroscop(?:y|ies)\b|\bupper[- ]endoscopy\b'),
    ('gi.egd', 'esophagoscopy', r'\b(?:transnasal\s+)?esophagoscop(?:y|ies)\b|\bTNE\b'),
    ('gi.egd', 'poem', r'\bper-?oral\s+endoscopic\s+myotomy\b|\bPOEM\b'),
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
    ('esd', r'\bendoscopic\s+submucosal\s+dissection\b|\bESD\b'),
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
    ('band_ligation', r'\b(?:band(?:ed|ing)?\s+ligation|variceal\s+band(?:ing)?|bands?\s+(?:were|was)\s+(?:placed|applied)'
                      r'|banded)\b'),
    ('dilation', r'\bdilat(?:ion|ation|ed|ing)\b|\bbougie\w*\b|\bSavary\b|\bMaloney\b'),
    ('stent', r'\bstents?\b'),
    ('foreign_body', r'\bforeign\s+bod(?:y|ies)\b|\bfood\s+(?:bolus|impaction)\b'),
    ('sphincterotomy', r'\b(?:biliary\s+|pancreatic\s+)?(?:sphincterotomy|papillotomy)\b'),
    ('stone_extraction', r'\bstones?\b|\bcalcul(?:us|i)\b|\bsludge\b|\bballoon\s+(?:sweep|extraction)\b|\bbasket\b'),
    ('lithotripsy', r'\blithotrips(?:y|ies)\b'),
    ('cholangioscopy', r'\bcholangioscop(?:y|ic|e)\b|\bSpyGlass\b'),
    ('cannulation', r'\bcannulat(?:ion|ed)\b'),
    ('peg', r'\bPEG(?:-J)?\b|\bpercutaneous\s+endoscopic\s+gastrostomy\b|\bgastrostomy\s+tube\s+(?:was\s+)?placed\b'),
    ('tube_replacement', r'\b(?:gastrostomy|G-?tube|PEG|J-?tube|jejunostomy)\b[^.;]{0,30}\b(?:replace(?:d|ment)|'
                         r'exchang(?:ed|e)|changed)\b|\breplace(?:d|ment)\s+of\s+(?:the\s+)?(?:gastrostomy|G-?tube)\b'),
    ('myotomy', r'\bmyotom(?:y|ies)\b'),
    ('decompression', r'\bdecompress(?:ion|ed)\b'),
    ('fundoplication', r'\btransoral\s+(?:incisionless\s+)?fundoplication\b|\bTIF\b'),
    ('capsule_study', r'\bcapsule\b'),
    ('manometry', r'\bmanometr(?:y|ic)\b|\bmotility\s+study\b|\bHRM\b'),
    ('ph_monitoring', r'\bpH\b|\bimpedance\b|\bBravo\b'),
    ('rectal_sensation', r'\brectal\s+(?:sensation|compliance|tone)\b|\bballoon\s+expulsion\b'),
    ('moderate_sedation', r'\bmoderate\s+sedation\b|\bconscious\s+sedation\b'),
))
ACT_KINDS = tuple(kind for kind, _ in ACTS)
# Kinds whose mere naming in a sentence is not an act (they name a thing): they are acts only with an act predicate.
NOUN_KINDS = frozenset(('stone_extraction', 'stent', 'clip', 'capsule_study', 'ph_monitoring', 'manometry', 'biopsy',
                        'injection', 'foreign_body', 'cannulation', 'tattoo', 'rectal_sensation'))

# --- vocabulary: reading words ---------------------------------------------------------------------------------
ACT_VERB = _rx(r'\b(?:was|were|been|is|are)\s+(?:then\s+|also\s+|successfully\s+|subsequently\s+|completely\s+|each\s+)?'
               r'(?:performed|done|obtained|taken|removed|resected|retrieved|excised|placed|deployed|inserted|applied|'
               r'achieved|injected|tattooed|ablated|treated|dilated|banded|clipped|cleared|extracted|swept|sampled|'
               r'biopsied|snared|cannulated|completed|carried\s+out|accomplished|made|used|passed|advanced|'
               r'introduced|reached|intubated|replaced|exchanged|ingested|recorded|positioned|attached|delivered|'
               r'fragmented|crushed|cut|sent|submitted|marked)\b'
               r'|\b(?:we|I)\s+(?:then\s+)?(?:performed|obtained|took|removed|resected|placed|deployed|injected|ablated|'
               r'dilated|banded|clipped|extracted|biopsied|snared|sampled|cannulated|passed|advanced|replaced)\b'
               r'|\bunderwent\b|\bunderwent\s+successful\b')
# A participle naming the act with no auxiliary ("polyps removed by cold snare", "biopsies taken").
BARE_PARTICIPLE = _rx(r'\b(?:performed|obtained|taken|removed|resected|retrieved|placed|deployed|injected|ablated|treated|'
                      r'dilated|banded|clipped|extracted|sampled|biopsied|snared|achieved|done|completed|sent)\b')
NEG_LEAD = _rx(r'^(?:[\s\-*•(]*(?:[A-Z]{1,3}\d{1,2}|\d{1,2}[.)])?\s*)*(?:no|neither|none|nor|without|there\s+was\s+no'
               r'|there\s+were\s+no)\b')
NEG_OTHER = _rx(r'^(?:[\s\-*•(]*(?:[A-Z]{1,3}\d{1,2}|\d{1,2}[.)])?\s*)*(?:no|neither|none|nor|there\s+(?:was|were)\s+no)'
                r'\s+(?:other|further|additional|more|another|separate|repeat)\b')
NOT_VERB = _rx(r"\b(?:was|were|is|are|been|has|have|had|did|does|could|would|can)\s+(?:not|never|n't)\b(?:\s+be)?"
               r"|\bnot\s+(?:performed|done|obtained|taken|removed|resected|treated|sampled|biopsied|placed|injected|"
               r"attempted|repeated|undertaken|carried\s+out|reached|completed|required|needed|indicated)\b"
               r"|\b(?:wasn't|weren't|didn't)\b")
WITHOUT = _rx(r'\b(?:without|w/o)\b')
CANCEL_WORDS = _rx(r'\b(?:cancel(?:l)?ed|declined|refused|deferred|postponed|aborted\s+before|not\s+attempted)\b')
HISTORY_WORDS = _rx(r'\b(?:prior|previous(?:ly)?|history\s+of|historical|in\s+the\s+past|ago|earlier|remote|old|formerly'
                    r'|last\s+(?:year|month|week|time|visit|seen)|had\s+(?:a|an|undergone|been|had)|status\s+post|s/p'
                    r'|prior-record|mentioned\s+in\s+the\s+preprocedure\s+history)\b')
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
                  r'|presumed|presumably|suspected|apparently|attempt(?:ed)?)\b')
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
PROCEDURE_FIELD = _rx(r'^[\s\-*#]*(?:procedures?(?:\s+performed(?:\s+today)?)?|operation|interventions?)\s*[:\-–]\s*'
                      r'(?P<value>\S[^\n]*)$')
ROLE_HEADINGS = (('nursing', _rx(r'^[\s\-*#]*(?:nursing|nurse|RN|recovery\s+nurse|procedure\s+checklist|nursing\s+'
                                 r'checklist|pre-?procedure\s+nursing|intra-?procedure\s+nursing)\b[^\n]{0,60}$')),
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
GENERIC_HEADING = _rx(r'^[\s\-*#]*[A-Z][A-Za-z /&,()\-]{1,60}:?\s*$')
OTHER_PROVIDER = (
    ('anesthesia', _rx(r'\b(?:monitored\s+anesthesia\s+care|MAC|general\s+anesthesia|propofol\s+sedation|deep\s+sedation|'
                       r'anesthesia|anaesthesia)\b[^.;]{0,120}\b(?:by|from|supplied|provided|administered|managed)\b[^.;]{0,80}'
                       r'\b(?:anesthesia|anaesthesia|anesthesiologist|CRNA|separate|another)\b'
                       r'|\b(?:anesthesia|anaesthesia)\s+(?:professional|service|team|provider)\s+(?:managed|provided|'
                       r'administered|supplied|gave)\b')),
    ('pathology', _rx(r'\bpathology\s+(?:interpretation|service|department|review)\b[^.;]{0,120}\b(?:separate|by\s+the|'
                      r'will\s+be|reported\s+separately|performed\s+by)\b|\b(?:specimen\s+processing|histology)\b[^.;]{0,80}'
                      r'\bseparate\s+pathology\b|\bseparate\s+pathology\s+service\b')),
    ('radiology', _rx(r'\bradiology\s+interpretation\s+is\s+reported\s+separately\b|\bradiologist\b[^.;]{0,60}\bseparately\b'
                      r'|\bradiology\s+services\s+are\s+billed\s+separately\b')),
    ('facility', _rx(r'\bfacility\s+(?:services|charges|fees|claim)\b[^.;]{0,120}\b(?:separately|by\s+the|respective|'
                     r'billed|documented)\b|\bfacility\s+and\s+(?:radiology|anesthesia)\s+services\s+are\s+billed\s+'
                     r'separately\b')),
)
SEDATION_BY_ENDOSCOPIST_DENIED = _rx(r'\b(?:endoscopist|performing\s+physician|proceduralist)\s+(?:did\s+not|was\s+not|'
                                     r'never)\s+(?:administer|provide|give|supervise)\w*\b[^.;]{0,60}\bsedation\b'
                                     r'|\bendoscopist\s+did\s+not\s+provide\s+a\s+separately\s+documented\s+'
                                     r'moderate[- ]sedation\b')
BOX_ROW = _rx(r'(?P<subject>[A-Za-z][^\[\]\n]{2,80}?)\s*[:\-]?\s*\[(?P<a>[ xX✓✔])\]\s*(?P<la>performed|yes|done)'
              r'\s*\[(?P<b>[ xX✓✔])\]\s*(?P<lb>not\s+performed|no|not\s+done)\b')
PAGE_HEADER = _rx(r'^[^\n]{0,120}\|\s*[^\n]{0,120}\|\s*[^\n]{0,120}$')
# E/M: an evaluation documented as such, a note's own structure, and routine procedure-related work.
EM_EVALUATED = _rx(r'\b(?:evaluated|seen|examined|assessed|reviewed\s+in\s+clinic)\s+(?:today\s+)?(?:for|in|with)\b'
                   r'|\bpresents?\s+(?:today\s+)?(?:for|with)\b|\bfollow(?:s|ed)?[- ]?up\s+(?:visit|appointment)\b'
                   r'|\b(?:office|clinic|outpatient)\s+(?:visit|encounter|consultation)\b|\bhistory\s+of\s+present\s+illness\b'
                   r'|\bHPI\b|\bchief\s+complaint\b|\bnew\s+patient\s+(?:visit|evaluation)\b')
NOTE_STRUCTURE = re.compile(r'^[ \t]*(?:impression|assessment|plan|exam(?:ination)?|physical\s+exam(?:ination)?|history|'
                            r'HPI|chief\s+complaint|ROS|review\s+of\s+systems|medications|allergies)\b[^\n]{0,40}?[:\-]',
                            re.A | re.I | re.M)
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
    kind: str  # report | history | plan | other


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
PLAN_HEADING = _rx(r'^[\s\-*#]*(?:plan|plans|recommendations?|assessment\s+and\s+plan|disposition\s+and\s+plan'
                   r'|follow-?up\s+plan)\s*:?\s*$')


def parts(text: str) -> tuple[_Part, ...]:
    """The document cut into report parts (a part about one service, from its title to the next title), role parts
    (a nursing, anesthesia, pathology or radiology entry, to the next heading) and other text."""
    cuts: list[tuple[int, str, str, Optional[Span], str]] = [(0, '', 'physician', None, 'other')]
    family, kind_now = '', 'other'
    for ls, le in _lines(text):
        line = text[ls:le]
        stripped = line.strip()
        if not stripped or len(stripped) > 100:
            continue
        if PAGE_HEADER.match(stripped) and stripped.count('|') >= 2:
            continue
        role = next((r for r, p in ROLE_HEADINGS if p.match(line)), None)
        if role:
            cuts.append((ls, family, role, Span(ls + line.index(stripped), ls + line.index(stripped) + len(stripped),
                                                stripped), 'role'))
            continue
        m = REPORT_TITLE.match(line)
        named, _ = _family_named(line) if m else ('', '')
        field_m = PROCEDURE_FIELD.match(line)
        if m and named and not PLAN_WORDS.search(line) and not HISTORY_WORDS.search(line):
            family = named
            s = ls + line.index(stripped)
            cuts.append((ls, family, 'physician', Span(s, s + len(stripped), stripped), 'report'))
            kind_now = 'report'
            continue
        if not m and GENERIC_HEADING.match(line) and not PLAN_WORDS.search(line) and not HISTORY_WORDS.search(line) \
                and not HISTORY_HEADING.match(line) and not PLAN_HEADING.match(line):
            heading_families = {f for f, _, p in SERVICES if p.search(line)}
            if len(heading_families) == 1 and len(stripped) <= 60:
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
    return tuple(out)


def _part_at(plist: Sequence[_Part], starts: Sequence[int], pos: int) -> _Part:
    i = bisect.bisect_right(starts, pos) - 1
    return plist[max(i, 0)]


def _sentences(text: str) -> list[tuple[int, int]]:
    """Sentences: split at a full stop, question or exclamation mark followed by space and a capital or digit or a
    list label, at a line that starts a numbered or labelled item, and at blank lines. Line wraps inside a sentence
    are kept (PDF text wraps mid-sentence)."""
    out: list[tuple[int, int]] = []
    start = 0
    n = len(text)
    i = 0
    abbreviations = ('Dr', 'Mr', 'Mrs', 'Ms', 'vs', 'approx', 'e.g', 'i.e', 'St', 'No', 'Fig')
    while i < n:
        ch = text[i]
        cut = None
        if ch in '.!?':
            j = i + 1
            while j < n and text[j] in ' \t':
                j += 1
            if j >= n or text[j] == '\n' or text[j].isupper() or text[j].isdigit() or text[j] in '"(“[':
                word = re.search(r'([A-Za-z.]{1,6})$', text[start:i])
                if not (word and word.group(1).rstrip('.') in abbreviations and ch == '.'):
                    if not (ch == '.' and i > 0 and text[i - 1].isdigit() and j < n and text[j].isdigit()):
                        cut = i + 1
        elif ch == '\n':
            nxt = text[i + 1:i + 40]
            prev_line_text = text[text.rfind('\n', 0, i) + 1:i]
            if re.match(r'[ \t]*[A-Z][A-Za-z /&()\-]{1,40}:[ \t]+\S', nxt) \
                    or re.match(r'[ \t]*[A-Z][A-Za-z /&()\-]{1,40}:[ \t]+\S', prev_line_text):
                cut = i  # a "Label: value" field line is a sentence of its own
            elif re.match(r'\s*\n', nxt) or re.match(r'[ \t]*(?:[A-Z]{1,3}\d{1,2}\s|\d{1,2}[.)]\s|[-*•]\s)', nxt) \
                    or (re.match(r'[ \t]*[A-Z][A-Za-z /&,()\-]{1,60}:?[ \t]*(?:\n|$)', text[i + 1:i + 80])
                        and not text[start:i].rstrip().endswith(',')):
                cut = i
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

_CLAUSE_CUT = _rx(r';|\s+but\s+|\s+whereas\s+|\s+although\s+|,\s+while\s+|\s+and\s+(?=(?:was|were|is|are)\s+(?:not|never)\b)'
                  r'|\s+and\s+(?=(?:the|a|an|this|that|it|she|he|they|we|I|one|two|three|\d+)\b[^.;]{0,60}\b(?:was|were|'
                  r'is|are|has|have|had|did)\b)|,\s+(?=(?:and\s+)?(?:the|this|that|it|she|he|they|we|I)\s+[^.;,]{0,40}'
                  r'\b(?:was|were|is|are)\b)')


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


def read_clause(text: str, clause: tuple[int, int], pos: int, end: int, *, service_date: Optional[date], dates,
                part: _Part, in_today_report: bool) -> Reading:
    """The status a clause gives the thing named at [pos, end) in it."""
    cs, ce = clause
    before = text[cs:pos]
    after = text[end:ce]
    whole = text[cs:ce]
    cues: list[str] = []
    # Check boxes on the row: "[X] Performed [ ] Not performed".
    for m in BOX_ROW.finditer(text, max(cs, pos - 90), min(len(text), ce + 60)):
        a, b = m.group('a').strip(), m.group('b').strip()
        if a and not b:
            return Reading('performed', ('box: performed checked',))
        if b and not a:
            return Reading('negated', ('box: not performed checked',))
        return Reading('uncertain', ('box: both or neither option checked',))
    # Negation.
    if NEG_OTHER.match(whole):
        return Reading('uncertain', ('no other/further: denies only acts beyond the documented ones',))
    if NEG_LEAD.match(whole):
        return Reading('negated', ('negated: the clause opens with a negation that covers its list',))
    head = before[-60:]
    if re.search(r'\b(?:no|without|w/o|nor|neither)\s+(?:\w+[\s,-]+){0,6}$', head, FLAGS) \
            and not re.search(r'\b(?:no|without)\s+(?:immediate\s+)?(?:complications?|bleeding|perforation)\b', head, FLAGS):
        if not re.search(r'\b(?:was|were|is|are|been)\b', head[head.lower().rfind('no'):] if 'no' in head.lower() else head, FLAGS):
            cues.append('negated: a negation before it in its clause')
            return Reading('negated', tuple(cues))
    not_verb = NOT_VERB.search(whole)
    if not_verb:
        # "was complete and was not discontinued": the negated word is the completion word, not this act.
        neg_target = text[cs + not_verb.end(): min(ce, cs + not_verb.end() + 40)]
        if not re.match(r'\s*(?:\w+\s+){0,2}(?:discontinu|interrupt|terminat|abort|incomplet|stopped)', neg_target, FLAGS):
            return Reading('negated', ('negated: "not" on its predicate',))
    if WITHOUT.search(before[-40:]):
        return Reading('negated', ('negated: "without" before it',))
    if CANCEL_WORDS.search(whole):
        return Reading('cancelled', ('cancelled: ' + CANCEL_WORDS.search(whole).group(0).lower(),))
    # Time: a date in the clause.
    for d in _dates_in(dates, cs, ce):
        if service_date is None:
            if d.precision == 'year' and HISTORY_WORDS.search(whole):
                return Reading('historical', (f'historical: {text[d.start:d.end]} with a history word',))
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
    hedge = HEDGE_WORDS.search(whole)
    if hedge:
        return Reading('uncertain', ('uncertain: ' + hedge.group(0).lower(),))
    if part.kind == 'history' and not TODAY_WORDS.search(whole):
        return Reading('historical', ('historical: in a history section',))
    if part.kind == 'plan' and not TODAY_WORDS.search(whole):
        return Reading('planned', ('planned: in a plan section',))
    if ACT_VERB.search(whole) or BARE_PARTICIPLE.search(after) or BARE_PARTICIPLE.search(before[-40:]) \
            or BARE_PARTICIPLE.fullmatch(text[pos:end].strip()):
        if in_today_report or TODAY_WORDS.search(whole) or part.kind == 'report':
            return Reading('performed', ('performed: an act predicate in a current report',))
        return Reading('performed', ('performed: an act predicate',))
    if in_today_report:
        return Reading('uncertain', ('uncertain: named without an act predicate',))
    return Reading('uncertain', ('uncertain: no performance statement',))


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


def _family_for_act(kind: str, region: str, part_family: str, present: Sequence[str]) -> str:
    """Which service an act belongs to: the report part's own service, else by anatomy where one service fits. An
    act whose anatomy cannot be reached by the part's service (a duodenal biopsy in a colonoscopy part) goes to the
    present service whose anatomy it is."""
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


DILATION_ACT = _rx(r'\b(?:balloon|bougie\w*|Savary|Maloney|dilator|CRE|pneumatic|wire-guided|through-the-scope|TTS)\b'
                   r'|\b(?:we|I)\s+dilated\b|\bdilat(?:ion|ation)\s+(?:was|were)\s+(?:performed|done|carried\s+out)\b'
                   r'|\b(?:was|were)\s+dilated\s+(?:with|using|by)\b|\bdilated\s+(?:with|using)\s+(?:a|an)\b'
                   r'|\b(?:no|without)\s+dilat(?:ion|ation)\b|\bdilat(?:ion|ation)\s+was\s+not\b')
OBSERVED = _rx(r'\b(?:was|were|is|are)\s+(?:seen|noted|found|identified|visualized|visualised|observed|present|detected|'
               r'appreciated|evident|demonstrated)\b')


def build(text: str, *, service_date: Optional[date], routing=None, context_facts=None) -> ServiceInventory:
    """The documented services of ``text`` for the effective ``service_date``. ``routing`` (a RoutingResult) supplies
    routing's family readings, kept beside each service and used, fail-closed, where the two readings disagree."""
    problems: list[str] = []
    dates = gi_context.find_dates(text)
    plist = parts(text)
    starts = [p.start for p in plist]
    sentences = _sentences(text)
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
    encounter_intents: list[str] = []
    routine_em: list[Span] = []
    # Pass 1: services named, other providers' services, encounter-wide statements.
    named: list[tuple[str, str, int, int, int, int]] = []
    for ss, se in sentences:
        part = _part_at(plist, starts, ss)
        for family, kind, pattern in SERVICES:
            for m in pattern.finditer(text, ss, min(se, ss + SENTENCE_READ_CHARS)):
                if any(a < m.end() and m.start() < b for _, _, a, b, _, _ in named):
                    continue
                named.append((family, kind, m.start(), m.end(), ss, se))
        for role, pattern in OTHER_PROVIDER:
            if pattern.search(text, ss, se):
                attributions.append(Attribution(role, (_span(text, ss, se),)))
        if SEDATION_BY_ENDOSCOPIST_DENIED.search(text, ss, se):
            sedation_denied = 'denied'
        if part.kind not in ('history', 'plan'):
            for name, pattern in INTENT_WORDS:
                m = pattern.search(text, ss, se)
                if m:
                    lead = text[max(ss, m.start() - 20):m.start()].lower()
                    encounter_intents.append(('not ' if re.search(r'\bnot\s+(?:a\s+|an\s+)?$', lead) else '') + name)
        if EM_ROUTINE.search(text, ss, se):
            routine_em.append(_span(text, ss, se))
    try:
        for family, kind, ms, me, ss, se in sorted(named, key=lambda x: x[2]):
            part = _part_at(plist, starts, ss)
            cls = clauses(text, ss, se)
            clause = _clause_for(cls, ms)
            title = part.title is not None and part.title.start <= ms < part.title.end and part.family == family
            in_report = part.kind == 'report' and part.family == family
            if title:
                reading = Reading('performed', (f'section: report title "{part.title.text}"',))
            else:
                reading = read_clause(text, clause, ms, me, service_date=service_date, dates=dates, part=part,
                                      in_today_report=in_report)
                if reading.status == 'uncertain' and in_report and not HEDGE_WORDS.search(text, *clause):
                    reading = Reading('performed', reading.cues + ('performed: named inside its own current report',))
                line_start = text.rfind('\n', 0, ms) + 1
                line_end = text.find('\n', ms)
                if reading.status == 'uncertain' and PROCEDURE_FIELD.match(text[line_start:line_end if line_end >= 0
                                                                                  else len(text)]):
                    reading = Reading('performed', reading.cues + ('performed: listed on the procedure line',))
            d = draft(family, kind)
            if part.kind == 'report' and part.family == family:
                d.scopes.append((part.start, part.end))
            if title and d.report_title is None:
                d.report_title = part.title
            d.statuses.append((reading.status, reading.cues, _span(text, *clause)))
            if reading.status == 'performed':
                d.evidence.append(_span(text, *clause))
            if family not in present_families and reading.status in ('performed', 'uncertain'):
                present_families.append(family)
        # Instruments name their service ("The colonoscope was advanced to the cecum").
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            for m in INSTRUMENTS.finditer(text, ss, se):
                word = m.group(0).lower()
                family = next((f for name, f in INSTRUMENT_FAMILY if name in word), part.family)
                if not family:
                    continue
                clause = _clause_for(clauses(text, ss, se), m.start())
                reading = read_clause(text, clause, m.start(), m.end(), service_date=service_date, dates=dates,
                                      part=part, in_today_report=part.kind == 'report' and part.family == family)
                if family not in drafts:
                    if reading.status != 'performed':
                        continue
                    # "The colonoscope was passed to the cecum" under "Lower Endoscopy Report": the instrument names it
                    draft(family, FAMILY_KINDS.get(family, family.split('.')[-1]))
                    if family not in present_families:
                        present_families.append(family)
                d = drafts[family]
                d.statuses.append((reading.status, reading.cues, _span(text, *clause)))
                if reading.status == 'performed':
                    d.evidence.append(_span(text, *clause))
        # Pass 2: completion and extent, read in each service's own report part (or a sentence naming only it).
        procedural = [f for f in drafts if f != 'gi.office_em']
        for ss, se in sentences:
            part = _part_at(plist, starts, ss)
            fam = part.family if part.family in drafts and part.kind == 'report' else ''
            if not fam:
                named_here = sorted({f for f, _, _, _, s2, _ in named if s2 == ss and f in drafts}
                                    | _instrument_families(text, ss, se, drafts))
                fam = named_here[0] if len(named_here) == 1 else ''
            if not fam and len(procedural) == 1 and part.kind not in ('history', 'plan'):
                fam = procedural[0]  # one procedure documented: an untitled report's sentences are its own
            if not fam or part.kind in ('history', 'plan'):
                continue
            d = drafts[fam]
            for cs, ce in clauses(text, ss, se):
                clause_text = text[cs:ce]
                if HISTORY_WORDS.search(clause_text) or re.search(r'\b(?:if|unless|whether)\b', clause_text, FLAGS):
                    continue
                if COMPLETE_POS.search(clause_text) and not re.search(r'\bnot\s+(?:reached|intubated|complete)',
                                                                        clause_text, FLAGS):
                    d.completion_pos.append(_span(text, cs, ce))
                for m in INCOMPLETE_WORDS.finditer(text, cs, ce):
                    lead = text[max(cs, m.start() - 60):m.start()].lower()
                    if re.search(r'\b(?:not|never|no|without)\s+(?:\w+\s+)?$', lead) or re.search(
                            r'\b(?:not|never|without)\s+(?:(?!was\b|were\b|is\b|are\b|but\b|however\b)[\w-]+,?\s+){0,5}$',
                            lead):
                        continue  # "was not discontinued", "not terminated early or interrupted"
                    if PLAN_WORDS.search(clause_text):
                        continue
                    if re.search(r'\b(?:lesion|polyp|mass|it)\b[^.;]{0,40}\bnot\s+removed\b', clause_text, FLAGS):
                        continue
                    d.completion_neg.append(_span(text, cs, ce))
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
            cls = clauses(text, ss, se)
            anatomy_all = _anatomy_in(text, ss, se)
            regions = {region for _, region, _, _ in anatomy_all}
            part_family = part.family if part.family in drafts and part.kind == 'report' else ''
            named_here = sorted({f for f, _, _, _, s2, _ in named if s2 == ss and f in drafts}
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
                fam = _family_for_act('biopsy', region_one, part_family, present_families)
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
                                    evidence=(_span(text, ss, se),))
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
                fam = _family_for_act(kind, region, part_family, present_families)
                if not fam or fam not in drafts:
                    continue
                if kind == 'snare' and re.match(r'\s*site\b', text[me:me + 8], FLAGS):
                    continue
                if kind == 'dilation' and not DILATION_ACT.search(text, clause[0], clause[1]):
                    continue  # "a common bile duct dilated to 11 mm", "upstream duct dilation": a finding
                reading = read_clause(text, clause, ms, me, service_date=service_date, dates=dates, part=part,
                                      in_today_report=part.kind == 'report')
                clause_text = text[clause[0]:clause[1]]
                has_act_verb = bool(ACT_VERB.search(clause_text) or BARE_PARTICIPLE.search(clause_text)
                                    or BOX_ROW.search(text, max(0, ms - 90), min(len(text), clause[1] + 60)))
                if reading.status == 'negated' and not has_act_verb:
                    continue  # a denied finding ("without food impaction", "no stones"), not a denied act
                if reading.status == 'negated' and OBSERVED.search(clause_text) and not ACT_VERB.search(clause_text):
                    continue  # "No stricture or ring was seen"
                if kind in NOUN_KINDS and not has_act_verb and not _on_procedure_line(text, ms, part):
                    continue
                if reading.status == 'uncertain' and not has_act_verb and not _on_procedure_line(text, ms, part):
                    continue
                if reading.status == 'uncertain' and _on_procedure_line(text, ms, part):
                    reading = Reading('performed', reading.cues + ('performed: listed on the procedure line',))
                d = drafts[fam]
                d.scopes.append((part.start, part.end) if part.kind == 'report' and part.family == fam else (ss, se))
                lesion = _lesion_for(sentence_lesions, ms)
                role = part.role
                labelled = next((r for r, pattern in ROLE_LABEL if pattern.match(text[ss:se])), None)
                if labelled:
                    role = labelled
                elif role == 'physician':
                    for sig_role, sig in ROLE_SIGNATURE:
                        if sig.search(text, ss, se):
                            role = sig_role
                act_count += 1
                if act_count > MAX_ACTS:
                    raise _Capped(f'More than {MAX_ACTS:,} acts are documented; the rest were not inventoried.')
                d.acts.append(Act(id=f'{d.id}-A{len(d.acts) + 1}', service=d.id, kind=kind, status=reading.status,
                                  role=role, anatomy=tuple(dict.fromkeys(a[0] for a in anat)), region=region,
                                  technique=_technique(text, *clause, near=ms), lesion=lesion.id if lesion else '',
                                  evidence=(_span(text, *clause),), cues=reading.cues,
                                  detail=_detail(text, *clause, kind)))
            if sentence_lesions:
                lesion = sentence_lesions[-1]
                for f, d in drafts.items():
                    if d.id == lesion.service:
                        last_lesion[f] = lesion
    except _Capped as exc:
        problems.append(str(exc))
    services = [_finish(d, text, routing, context_facts, encounter_intents) for d in drafts.values()]
    services = [s for s in services if s is not None]
    em = _em_service(text, routing, context_facts, services, routine_em, sentences, len(services) + 1)
    if em is not None:
        services.append(em)
    services = tuple(services)
    conflicts = _conflicts(services)
    return ServiceInventory(version=INVENTORY_VERSION, services=services, conflicts=conflicts,
                            attributions=_dedupe_attributions(attributions), problems=tuple(dict.fromkeys(problems)),
                            sedation_by_endoscopist=sedation_denied)


def _instrument_families(text: str, start: int, end: int, drafts) -> set:
    found = set()
    for m in INSTRUMENTS.finditer(text, start, end):
        word = m.group(0).lower()
        family = next((f for name, f in INSTRUMENT_FAMILY if name in word), '')
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
    elif negative:
        status = 'cancelled' if any(s[0] == 'cancelled' for s in negative) else 'negated'
        cues.extend(negative[0][1])
    elif timed:
        status = timed[0][0]
        cues.extend(timed[0][1])
    elif hedged:
        status = 'uncertain'
        cues.extend(hedged[0][1])
    else:
        return None
    completion = 'unknown'
    if status == 'performed':
        if d.completion_neg:
            completion = 'incomplete'
            status = 'incomplete'
            cues.append('incomplete: ' + d.completion_neg[0].text[:120])
        elif d.completion_pos:
            completion = 'complete'
    finding = routing.finding(d.family) if routing is not None and hasattr(routing, 'finding') else None
    routing_status = finding.status if finding is not None else ''
    if routing_status:
        doubting = [m for m in finding.mentions if m.status == 'uncertain'
                    and not any(c.startswith('uncertain: no performance evidence') for c in m.cues)]
        if status in POSITIVE and routing_status in ('planned', 'historical', 'cancelled', 'negated'):
            cues.append(f'uncertain: routing reads the family as {routing_status}')
            status = 'uncertain'
        elif status in POSITIVE and routing_status == 'uncertain' and doubting:
            # routing's own doubt about today's service (a hedge, an ambiguous box row, a plan label) holds it
            cues.append('uncertain: routing holds the family: ' + (doubting[0].cues[0] if doubting[0].cues else 'doubt'))
            status = 'uncertain'
        elif status in ('planned', 'historical', 'cancelled', 'negated') and routing_status in POSITIVE:
            cues.append(f'uncertain: routing reads the family as {routing_status}')
            status = 'uncertain'
        elif status == 'performed' and routing_status == 'incomplete' and completion != 'complete':
            status, completion = 'incomplete', 'incomplete'
            cues.append('incomplete: routing reads the examination as incomplete')
    extent = ''
    if finding is not None:
        fact = next((f for f in finding.facts if f.name == 'extent' and f.value), None)
        extent = fact.value if fact else ''
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
    completion_evidence = tuple(_dedupe_spans(d.completion_neg if completion == 'incomplete' else d.completion_pos))[:4]
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


def _same_subject(done: Act, denied: Act, service_acts: Sequence[Act]) -> bool:
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
        elsewhere = [a for a in service_acts if a.status == 'performed' and a.kind == done.kind and a is not done
                     and ((a.lesion and a.lesion != denied.lesion) or (not a.lesion and a.anatomy))]
        return not elsewhere
    return True


RELATED_KINDS = {'tattoo': ('tattoo', 'injection'), 'injection': ('injection', 'tattoo')}


def _conflicts(services: Sequence[DocumentedService]) -> tuple[Conflict, ...]:
    """Acts of one service that the document states both as done and as not done today. A difference of time
    (historical vs today) is not a conflict, nor a denial of further acts beyond the documented ones; a statement about
    one lesion never conflicts with one about another lesion or another site."""
    out: list[Conflict] = []
    for service in services:
        done = [a for a in service.acts if a.status == 'performed']
        denied = [a for a in service.acts if a.status in ('negated', 'cancelled')]
        for d_act in done:
            kinds = RELATED_KINDS.get(d_act.kind, (d_act.kind,))
            against = [n for n in denied if n.kind in kinds and _same_subject(d_act, n, service.acts)]
            if not against:
                continue
            subject = 'tattoo' if 'tattoo' in kinds else d_act.kind
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
