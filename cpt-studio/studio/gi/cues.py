"""Lexical vocabularies for GI routing: service-status cues, service names,
anatomic landmarks and interventions.

These are this service's own reading aids, not coding rules. Every pattern is
ASCII-only and case-insensitive (``re.A | re.I``): Python's Unicode case
folding would otherwise read U+0130, U+0131, U+017F and U+212A as ASCII
letters.

Status cues come in three scopes:

- ``pre``    must end immediately before the service mention ("no ", "prior ");
- ``post``   must start immediately after it (" was not performed", " if needed");
- ``clause`` anywhere in the clause; attached to the nearest mention group.

A miss is meant to fail closed: a mention with no decisive cue falls back to
its section, and only procedure/findings/technique sections (or explicit
past-tense performance) can make it "performed". Explicit negation patterns
read "negated"; any other negation word in the clause that no anchored
pattern and no narrow exception (a complication, a finding, an intent)
accounts for withholds "performed" (DOUBT_TOKEN, detect._doubt).
"""
from __future__ import annotations

import re
import sys

FLAGS = re.A | re.I


def rx(pattern: str, flags: int = FLAGS) -> re.Pattern:
    return re.compile(pattern, flags)


def _words(*words: str) -> str:
    return '|'.join(sorted(words, key=len, reverse=True))


# Placeholder written over other service mentions before a pre/post pattern
# is applied, so "no EGD or colonoscopy" negates both names.
SERVICE_TOKEN = 'svc'

# Small words allowed between a pre-trigger and the mention it governs.
_NEG_FILLER = _words(
    'a', 'an', 'the', 'any', 'prior', 'previous', 'recent', 'further', 'other', 'additional', 'repeat',
    'interval', 'screening', 'diagnostic', 'surveillance', 'upper', 'lower', 'gi', 'endoscopic', 'outside',
    'urgent', 'emergent', 'elective', 'therapeutic', 'planned', 'scheduled', 'need', 'needs', 'indication',
    'indications', 'plan', 'plans', 'role', 'evidence', 'for', 'of', 'or', 'and', 'nor', 'procedure',
    'procedures', 'complete', 'full', 'follow-up', SERVICE_TOKEN,
    # what an intervention is usually qualified by ("no gastric biopsies", "no plastic stent")
    'gastric', 'duodenal', 'esophageal', 'colonic', 'rectal', 'random', 'mucosal', 'cold', 'hot', 'forceps',
    'snare', 'jumbo', 'biliary', 'pancreatic', 'plastic', 'metal', 'metallic', 'covered', 'uncovered',
    'balloon', 'separate', 'more', 'specimens', 'tissue', 'formal', 'duct', 'bile', 'common', 'contrast')
# After "not" only a determiner may stand before the mention: "but not the colonoscopy",
# never "not a screening colonoscopy" (which denies the intent, not the service).
_NOT_FILLER = _words('a', 'an', 'the', 'any', 'or', 'and', 'nor', SERVICE_TOKEN)
_HIST_FILLER = _words(
    'a', 'an', 'the', 'her', 'his', 'their', 'normal', 'abnormal', 'incomplete', 'complete', 'screening',
    'surveillance', 'diagnostic', 'therapeutic', 'outside', 'upper', 'lower', 'gi', 'unremarkable', 'routine',
    'elective', 'index', 'initial', 'first', 'second', 'and', 'or', SERVICE_TOKEN, r'(?:19|20)\d{2}')


def _pre(trigger: str, filler: str, count: int = 5) -> re.Pattern:
    return rx(r'(?<![\w/-])(?:' + trigger + r')(?:[\s,]+(?:' + filler + r')){0,' + str(count) + r'}[\s,]*$')


# --- negation: the service did not happen --------------------------------------

REFUSAL = 'refusal'  # the NEGATED_PRE label whose trigger never speaks of earlier encounters ("left before")
NEGATED_PRE = (
    ('no / without', _pre(r'no|without|w/o', _NEG_FILLER)),
    ('did not undergo', _pre(r"(?:did|does|has|have|had)\s+not\s+(?:yet\s+|previously\s+|ever\s+)?"
                             r"(?:undergo|undergone|underwent|had|have|receive|received|require|required|need|needed)",
                             _NEG_FILLER, 4)),
    ('never had', _pre(r'(?:never|not)\s+(?:yet\s+|previously\s+)?(?:undergone|underwent|had|received|undergo)',
                       _NEG_FILLER, 4)),
    ('denies', _pre(r'denie[sd](?:\s+(?:any|having|ever\s+having))?', _NEG_FILLER, 4)),
    ('declined', _pre(r'declined|declines|refused|refuses', _NEG_FILLER, 4)),
    ('no history of', _pre(r'no\s+(?:personal\s+)?history\s+of|no\s+hx\s+of|no\s+h/o', _NEG_FILLER, 3)),
    # "Neither EUS nor ERCP", "EUS was not performed, nor was ERCP"
    ('neither / nor', _pre(r'neither|nor(?:\s+(?:was|were|is|are|did|does|had|has|have|could|can))?', _NEG_FILLER)),
    # "but not the colonoscopy", "EGD, not colonoscopy, was performed"
    ('not', _pre(r'not', _NOT_FILLER, 3)),
    # a replacement: "flexible sigmoidoscopy instead of colonoscopy", "EGD rather than EUS"
    ('instead of', _pre(r'instead\s+of|rather\s+than|in\s+lieu\s+of|as\s+opposed\s+to|in\s+place\s+of', _NEG_FILLER, 4)),
    # a refusal or an avoidance written before the service: "chose to forgo colonoscopy", "opted out of EUS",
    # "decided against EGD", "elected not to undergo colonoscopy", "left before the EUS". Always about today.
    (REFUSAL, _pre(r'(?:forgo|forego)(?:es|ing|ne)?|fore?went'
                   r'|opt(?:s|ed|ing)?\s+out\s+of|(?:decid|opt|elect)(?:e|es|ed|ing|s)?\s+against'
                   r'|(?:elect|chose|choose|decid|opt|wish|want)(?:e|es|ed|ing|s)?\s+not\s+to\s+'
                   r'(?:have|undergo|proceed\s+with|pursue)'
                   r'|(?:left|leaves|leaving)\s+(?:before|without|prior\s+to)', _NEG_FILLER, 4)),
)
# What a "no <service> ..." phrase governs when the service name only qualifies the next
# word: "No flexible sigmoidoscopy complications", "no EGD-related bleeding", "no EUS-guided
# sampling". Matched against the masked text right after the mention.
NEGATION_HEAD_AFTER = rx(r'^[\s-]*(?:procedure[\s-]+|procedural\s+)?(?:related|associated|induced|guided|assisted|'
                         r'specific|based)\b'
                         r'|^\s+(?:procedure\s+|procedural\s+|post-?procedure\s+)?(?:complications?|adverse|findings?|'
                         r'reports?|records?|results?|images?|abnormalit(?:y|ies)|bleeding|hemorrhage|perforation|'
                         r'issues?|problems?|difficult(?:y|ies)|events?|injur(?:y|ies)|pathology|specimens?|'
                         r'sequelae)\b')
# Participles a "not" denies when they describe a service or an intervention.
_NOT_DONE = (r'performed|completed|undertaken|carried\s+out|attempted|obtained|taken|done|removed|resected|placed|'
             r'biopsied|sampled|dilated|injected|treated|indicated|needed|required|necessary|recommended|warranted|'
             r'pursued|clipped|tattooed|deployed|inserted|retrieved|used|applied|ligated|banded|cauterized|'
             r'scheduled|ordered')
# gi3 extent (N1): a short prepositional post-modifier of the act may stand between it and its post-negation ("Balloon
# dilation of the channel was not attempted", "Biopsies of the cecum were not obtained", "EGD at the bedside was not
# performed"): a preposition of this closed class, an optional determiner and at most three words, then an auxiliary.
# At 90377ec6f413 such an act read as performed under any procedure, findings or technique heading (h2-04's balloon
# dilation, once its "Procedure and findings" heading is read).
# A word that opens a clause of its own is no part of the post-modifier (a closed class: relative and subordinating
# words), so a denial inside a relative clause never reaches the act ("Biopsy of the polyp that was not removed").
_POST_MODIFIER_WORD = (r'(?!(?:that|which|who|whom|whose|where|when|while|because|since|if|unless|although|though|'
                       r'until)\b)[\w-]+')
_POST_MODIFIER = (r'^(?:\s+(?:of|at|in|on|across|through)\s+(?:(?:the|a|an|this|that|these|those)\s+)?'
                  r'(?:' + _POST_MODIFIER_WORD + r'\s+){0,2}?' + _POST_MODIFIER_WORD
                  + r'(?=\s+(?:was|were|is|are|has|have|had)\s))?')
NEGATED_POST = (
    # "Colonoscopy was not performed", "ERCP not indicated", "EUS has never been performed"
    ('was not performed', rx(_POST_MODIFIER + r'[\s,]*(?:(?:was|were|is|are|has\s+been|have\s+been|had\s+been|will\s+be|'
                             r'would\s+be|could\s+be|can\s+be|to\s+be)\s+)?(?:not|never)\s+(?:(?:been|be|yet|further|'
                             r'ever|successfully)\s+){0,2}(?!completed\b)(?:' + _NOT_DONE + r')\b')),
    ('was declined', rx(r'^[\s,]*(?:(?:was|were|is|are|has\s+been|have\s+been)\s+)?(?:declined|refused)\b')),
    # elliptical: "EGD was performed; EUS was not." / "colonoscopy wasn't"
    ('was not', rx(r"^[\s,]*(?:was|were|is|are|has\s+been|have\s+been|had\s+been|did|does|do|could|can|will)"
                   r"\s*(?:not|n't)\s*(?=[.;,!?)\]]|$)")),
    # listed or key-value: "EUS: not performed", "Colonoscopy - not performed", "(not performed)", a table
    # row "Colonoscopy | Not performed",
    # "Stent: none", "Colonoscopy: N/A", "Colonoscopy: no", "Colonoscopy: patient declined"
    ('listed as not done', rx(r'^\s*(?:[:=\u2013\u2014|-]+|\(|,)\s*(?:(?:was|were|is|are)\s+)?(?:not\s+(?:yet\s+)?(?:'
                              + _NOT_DONE + r')\b(?<!completed)|none\b|nil\b|no\s*(?=[.;,)\]]|$)|n/?a(?![\w/])|not\s+applicable\b'
                              r'|(?:the\s+)?(?:patient|pt)\s+(?:declined|refused)\b|declined\b|refused\b|omitted\b'
                              r'|not\s+done\b)')),
)
# "No X was performed": X must sit between "no" and the verb, with no other
# finite verb or relative clause in between.
NEGATED_SPAN = rx(r'\bno\b(?P<body>(?:(?!\b(?:was|were|is|are|has|have|had|which|that|but|and\s+the)\b)[^;.!?]){0,240}?)'
                  r'\b(?:was|were|has\s+been|had\s+been|have\s+been|is|are|will\s+be|could\s+be)\s+'
                  r'(?:successfully\s+|then\s+|further\s+)?(?:' + _NOT_DONE + r'|planned)\b')
# "<something> was not <done>" with no service or intervention named in it ("The stricture was
# not dilated", "Polypectomy was not performed"): it denies the act its own clause describes.
# Only acts: "was not completed" is an incomplete examination and "was not needed" speaks of
# further work, so neither is here.
NOT_DONE_CLAUSE = rx(r'\b(?:was|were|is|are|has\s+been|have\s+been|had\s+been)\s+(?:not|never)\s+(?:(?:been|yet|further|'
                     r'successfully)\s+){0,2}(?:performed|undertaken|carried\s+out|attempted|obtained|taken|done|'
                     r'removed|resected|placed|biopsied|sampled|dilated|injected|clipped|tattooed|deployed|retrieved|'
                     r'ligated|banded|cauterized|inserted)\b')
# Negations that speak about the past ("no prior", "never had", "no history of")
# rather than about today's service.
NEGATION_ABOUT_PAST = rx(r'\b(?:prior|previous|previously|never|ever|history|before|had|recent)\b')

# --- unresolved negation -----------------------------------------------------------
# Any of these words in a clause withholds "performed" from what it attaches to, unless an
# anchored pattern above, a clause cue, or one of the narrow exceptions below accounts for
# it. An exception list that misses a wording fails safe: the reading becomes uncertain.
DOUBT_TOKEN = rx(r"\b(?:no|not|never|neither|nor|none|without|cannot|unable|declined|declines|refused|refuses|refusal"
                 # the bare verbs of putting a service off ("we decided to defer EUS"): no cue reads them, and the
                 # participles "deferred" / "postponed" are cancellation cues that explain themselves
                 r"|defer|defers|deferring|deferral|postpone|postpones|postponing"
                 r")\b|n't\b|(?<![\w/])(?:w/o|n/a)(?![\w/])"
                 r'|\b(?:instead\s+of|rather\s+than|in\s+lieu\s+of|as\s+opposed\s+to|in\s+place\s+of|substituted\s+for)\b')
# The exceptions are matched against the masked clause (service names read "svc").
# 1. A complication, difficulty or adverse event is what is denied: "without difficulty",
#    "no immediate bleeding after the sphincterotomy", "No EGD-related complications".
_QUALIFIER = (r'(?:immediate|immediately|apparent|evident|obvious|significant|clinically\s+significant|major|minor|'
              r'further|active|ongoing|post-?procedur(?:e|al)|post-?polypectomy|delayed|procedur(?:e|al)|'
              r'intra-?procedur(?:e|al)|peri-?procedur(?:e|al)|other|any|known|visible|unexpected|serious|untoward|'
              r'acute|additional|residual|recurrent|related|associated|induced|' + SERVICE_TOKEN
              + r'|evidence\s+of|signs?\s+of)')
COMPLICATION_NEGATION = rx(r'\b(?:no|without|w/o|none|not\s+any|free\s+of|nor)\s+(?:' + _QUALIFIER + r'[\s,-]+)*'
                           r'(?:complications?|adverse\s+(?:events?|reactions?|effects?|outcomes?)|difficult(?:y|ies)|'
                           r'incidents?|events?|bleeding|hemorrhage|oozing|perforation|resistance|trauma|'
                           r'injur(?:y|ies)|problems?|issues?|desaturation|hypoxi(?:a|c)|hypotension|aspiration|'
                           r'distress|discomfort|pain|sequelae)\b')
# 2. A finding is what is denied: "No polyps were seen", "No esophagitis, Barrett-appearing
#    mucosa or stricture.", "showed no residual filling defects". The denied words name no
#    service, intervention or act; an act word ("No polyps were removed") is never a finding.
_ACT_WORD = (SERVICE_TOKEN + r'|polypectom\w*|biops\w*|snar\w*|forceps|dilat\w*|inject\w*|clip\w*|tattoo\w*|cauter\w*'
             r'|resect\w*|retriev\w*|remov\w*|procedures?|exams?|examinations?|endoscop\w*|\w*scope|sampl\w*|FNA|FNB'
             r'|aspirat\w*|stent\w*|sphincterotom\w*|papillotom\w*|cannulat\w*|ligat\w*|band\w*|ablat\w*|APC'
             r'|hemostasis|interventions?|specimens?|retroflex\w*|intubat\w*|insert\w*|advanc\w*|EMR|PEG|bougie\w*'
             r'|balloon\w*|basket\w*|brush\w*|extract\w*|treat\w*|therap\w*|ultrasound|sonograph\w*|cholangiogra\w*'
             r'|pancreatogra\w*|sweep\w*|swept|marking|performed|done|taken|obtained|placed|attempted|completed'
             r'|required|needed|indicated|planned|scheduled'
             # A denied precondition ("no prep", "no consent") is a reason a procedure may not have
             # happened, never a finding that explains the negation away.
             r'|prep\w*|consent\w*')
_AUX_WORD = r'was|were|is|are|be|been|being|has|have|had|did|does|do|will|would|could|can|should|may|might|must'
_NP_WORD = r'(?!(?:' + _ACT_WORD + r'|' + _AUX_WORD + r')\b)[\w/-]+'
_NP = r'(?:' + _NP_WORD + r'(?:\s*,\s*|\s+)){0,7}?' + _NP_WORD
_OBSERVED = (r'(?:seen|noted|found|identified|present|visualized|observed|detected|appreciated|evident|demonstrated|'
             r'encountered|visible|apparent|discovered|shown)')
# Where a denied finding ends: a comma, semicolon, colon or bracket, or a full stop that ends a
# sentence - not the stop of an abbreviation ("no H. pylori biopsies needed").
_FINDING_END = r'(?=\s*(?:[;:,)\]]|\.(?![\w.])(?!\s+[a-z])|$))'
FINDING_NEGATION = (
    rx(r'\b(?:no|without|not\s+any|nor)\s+' + _NP + r'\s*(?:(?:was|were|is|are|has\s+been|have\s+been)\s+)?'
       + _OBSERVED + r'\b'),
    rx(r'\b(?:no|without|not\s+any)\s+' + _NP + _FINDING_END),
    rx(r'\b(?:showed|shows|revealed|reveals|demonstrated|demonstrates|with|there\s+(?:was|were|is|are))\s+'
       r'(?:no|not\s+any)\s+' + _NP + r'(?:' + _FINDING_END + r'|(?=\s(?:and|or|but|in|on|at|to|from|of)\b))'),
    rx(r'\b(?:was|were|is|are)\s+not\s+' + _OBSERVED + r'\b'),
    rx(r'\bcannot\s+(?:be\s+)?(?:exclude[ds]?|ruled?\s+out)\b'),
)
# 3. An intent or a manner is what is denied: "not a screening colonoscopy", "not only",
#    "was not difficult".
QUALIFIER_NEGATION = rx(r'\bnot\s+(?:a\s+|an\s+|the\s+)?(?:screening|surveillance|diagnostic|therapeutic|routine|'
                        r'average-risk|high-risk)\b|\bnot\s+only\b'
                        r'|\bnot\s+(?:(?:technically|particularly|especially|very)\s+)?(?:difficult|traumatic|painful|'
                        r'complicated|prolonged|challenging)\b')
# 4. A different act or care step is what is denied, outside the passage being read: "no
#    sedation was given", "without retroflexion", "declined sedation". Never the procedure
#    itself (no "procedure", "exam" or service name here).
OTHER_ACT_NEGATION = rx(r'\b(?:no|without|w/o|not|nor|declined|declines|refused|refuses)\s+(?:(?:a|an|the|any|further|'
                        r'additional|other|routine|repeat|formal|separate|conscious|moderate|deep|general|IV)\s+){0,2}'
                        r'(?:sedation|sedated|anesthesia|anaesthesia|anesthetized|anaesthetized|propofol|MAC|analgesia|'
                        r'retroflexion|photo(?:graph)?s?|'
                        r'photodocumentation|irrigation|lavage|chromoendoscopy|narrow[- ]band\s+imaging|NBI|'
                        r'contrast|fluoroscopy|intubation\s+of\s+the\s+(?:terminal\s+)?ileum)\b')
# 5. The same acts and care steps denied after their name, as a line of their own ("Sedation was not needed.",
#    "Retroflexion: not performed", "Images were not saved.", "The patient did not require sedation."). Read only
#    where a short line after a described service line is asked whether it denies the service (detect._denies):
#    the act must stand right before its denial, and only these participles deny it ("was not tolerated" or "was
#    not available" may be why the procedure stopped, so they still hold).
_OTHER_ACT = (r'(?:(?:conscious|moderate|deep|general|IV|intravenous|procedural)\s+)?(?:sedation|anesthesia|anaesthesia|'
              r'propofol|MAC|analgesia|retroflexion|photo(?:graph)?s?|photodocumentation|images?|irrigation|lavage|'
              r'chromoendoscopy|narrow[- ]band\s+imaging|NBI|contrast|fluoroscopy|intubation\s+of\s+the\s+(?:terminal\s+)?'
              r'ileum)')
OTHER_ACT_DENIED = rx(r'\b' + _OTHER_ACT + r"\s*(?:[:=\u2013-]\s*)?(?:(?:was|were|is|are|has\s+been|have\s+been|had\s+been|"
                      r"could|can|did|does|will)\s*)?(?:not|never|n't)\s+(?:be\s+|been\s+)?(?:needed|required|used|given|"
                      r'administered|performed|done|taken|saved|obtained|indicated|necessary|attempted)\b'
                      r'|\b(?:did|does|do|will)\s*(?:not|n\'t)\s+(?:require|need|receive|undergo|get)\s+(?:any\s+)?'
                      + _OTHER_ACT + r'\b')

# --- history: the service happened before this encounter ------------------------

# The words that put a service at an earlier occasion when they stand before its name ("prior colonoscopy"). EARLIER
# reads the same words anywhere: before a reach to a depth in its clause, they put the reach at an earlier occasion
# too ("At the previous attempt the colonoscope was advanced to 60 cm"; detect._depth_reach_today, GI round 2 fix
# round, extent). One string, so the two never drift.
# gi3 extent (R5): "past" with an article after it opens a place, never an earlier occasion: "could not be advanced past
# the hepatic flexure" reaches the flexure, as its synonym "beyond the" already did (h2-02 read the flexure historical and
# no extent). Every time use keeps its reading: "past colonoscopy", "the past year", "in the past" (HISTORICAL_CLAUSE),
# and "past," before a comma.
_EARLIER = (r'prior|previous|previously|last|most\s+recent|recent|recently|remote|earlier|past(?!\s+(?:the|a|an)\b)|'
            r'index|outside')
EARLIER = rx(r'\b(?:' + _EARLIER + r')\b')
HISTORICAL_PRE = (
    ('history of', _pre(r'history\s+of|hx\s+of|h/o|s/p|status\s+post|personal\s+history\s+of',
                        _HIST_FILLER, 3)),
    ('prior', _pre(_EARLIER, _HIST_FILLER, 3)),
)
# Who asked for a service is no history: "requested by her previous gastroenterologist", "ordered by the outside
# physician" (the "elsewhere" history cue is not read after these).
REQUEST_BEFORE = rx(r'\b(?:requested|ordered|recommended|referred|suggested|advised|proposed|arranged|scheduled)\s+$')
# "as scheduled", "as planned", "as previously arranged": the booking a done service kept, not a future.
AS_BOOKED_BEFORE = rx(r'\bas\s+(?:(?:previously|originally|initially|already)\s+)?$')
# "had a colonoscopy" is history unless the clause says today.
HAD_PRE = _pre(r'had|has\s+had|have\s+had', _HIST_FILLER, 3)
# What a relative time ("ago", "last month") right after these dates is a symptom, not the service:
# "bleeding since last month", "pain for the last week", "symptoms that began two weeks ago".
SYMPTOM_TIME_BEFORE = rx(r'(?:\bsince|\b(?:over|for|in|during|within|throughout)\s+the'
                         r'|\b(?:start|began|begun|beginning|onset|noted|noticed|develop|worsen|occur|recur)\w*)\s+'
                         r'(?:(?:about|approximately|roughly|around|nearly)\s+)?$')
HISTORICAL_CLAUSE = (
    ('ago', rx(r'\b(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|several|many|few)\s+'
               r'(?:days?|weeks?|months?|years?)\s+ago\b|\bago\b')),
    # Undated, by relative time or by another provider or place: "performed last month", "earlier this year",
    # "at an outside hospital", "by her previous gastroenterologist", "done elsewhere". "last" is anchored to a
    # time unit ("the last 5 cm" and "at last" are not history).
    ('last month', rx(r'\b(?:last|previous)\s+(?:week|month|year|spring|summer|fall|autumn|winter)\b'
                      r'|\bearlier\s+this\s+(?:week|month|year)\b')),
    ('elsewhere', rx(r'\b(?:at|from|by)\s+(?:an?\s+|the\s+)?(?:outside|another|other)\s+(?:hospital|facility|'
                     r'institution|cent(?:er|re)|clinic|practice|gastroenterologist|physician|provider|endoscopist)\b'
                     r'|\b(?:by|with)\s+(?:her|his|their|the)\s+(?:previous|prior|former|outside|referring|other)\s+'
                     r'(?:gastroenterologist|physician|provider|doctor|endoscopist|surgeon)\b'
                     r'|\b(?:performed|done|completed)\s+elsewhere\b')),
    ('in the past', rx(r'\bin\s+the\s+past\b|\byears?\s+before\b|\bformerly\b')),
    ('records reviewed', rx(r'\b(?:reports?|records?|results?|images?)\s+(?:were\s+|was\s+|have\s+been\s+)?reviewed\b'
                            r'|\breview\s+of\s+(?:the\s+)?(?:outside|prior|previous|old)\s+(?:reports?|records?)\b')),
)

# --- cancellation: the service was called off before it happened ---------------

ABORTED = rx(r'\baborted\b')
CANCELLED_CLAUSE = (
    ('cancelled', rx(r'\bcancel(?:l?ed|lation|s)?\b')),
    ('aborted', ABORTED),
    ('postponed', rx(r'\bpostponed\b')),
    ('deferred', rx(r'\bdeferred\b')),
    ('not done', rx(r'\bnot\s+done\b')),
    ('called off', rx(r'\bcalled\s+off\b')),
    ('not started', rx(r'\bnot\s+(?:started|begun)\b')),
    ('no-show', rx(r'\bno[- ]show(?:ed)?\b|\bdid\s+not\s+(?:show|arrive|present\s+for)\b')),
)
# --- a negation that governs a status word (gi2 negation lens, ho-02 at 2b82889f) -----------------------------------
# A status word says the procedure was called off or cut short ("aborted", "cancelled", "postponed", "terminated").
# A negation written directly before it - only a passive auxiliary between - negates that STATUS, not the service:
# "Examination complete, not aborted." says the examination was not cut short, "The colonoscopy was never cancelled"
# that it was not called off. Routing's readers read such a status word as the service's own denial ("not aborted"
# read with the service-name grammar of NEGATED_PRE, "but not the colonoscopy"), cancellation or incompleteness; the
# documented-service reader already reads a negated negative as positive (ARCHITECTURE 5.9). One predicate, read by
# routing's reference and clause-cue readers and by its reading of a cited passage that opens on the status word
# (detect._negated_status, detect._opens_on_a_negated_status).
STATUS_NEGATION = rx(r"(?:\b(?:not|never|neither|nor|without)|n['\u2019]t)(?:\s+(?:being|been|be))?\s+$")
STATUS_NEGATION_REACH = 40  # the negation and its auxiliary stand within this many characters before the status word


def status_negation(text: str, start: int):
    """The negation that governs the status word starting at ``start`` (STATUS_NEGATION), or None."""
    return STATUS_NEGATION.search(text, max(0, start - STATUS_NEGATION_REACH), start)


# A sentence that is a bare statement that the procedure was not called off or cut short, and nothing more: the
# procedure (or a service name, masked as SERVICE_TOKEN) as its subject or none, an optional completion predicate
# ("complete,", "complete;", "was completed and"), the auxiliaries, the negation (also contracted with a typographic
# apostrophe), its status word(s) and an optional "early" or intensifier (_BARE_TAIL). Read whole (fullmatch on the
# masked sentence, once per sentence): any other word - a hedge, a time, "until", "but", another act, a reason -
# keeps the sentence from being one, and the negated status word is then held as a doubt, never released.
STATUS_WORD = (r'(?:aborted|cancel(?:l)?ed|postponed|deferred|called\s+off|terminated|discontinued|halted|stopped|'
               r'interrupted|abandoned)')
_BARE_SUBJECT = r'(?:(?:the|this)\s+)?(?:procedure|examination|exam|study|endoscopy|' + SERVICE_TOKEN + r'|it)'
# What may follow a status word in a bare statement: "early", and a negative-polarity intensifier, which only
# strengthens the negation ("at any point", "at any time", "at any stage", "at all": a closed class).
_BARE_TAIL = r'(?:\s+(?:early|prematurely|at\s+any\s+(?:point|time|stage)|at\s+all))?'
_BARE_NEGATION = r"(?:not|never|neither|without|(?:was|were|is|had|has)n['\u2019]t)(?:\s+(?:being|been|be))?"
BARE_STATUS_DENIAL = rx(
    r'[\s*\u2022-]*(?:' + _BARE_SUBJECT + r'\s+)?'
    r'(?:(?:was|is)\s+)?(?:complete(?:d|ly)?(?:\s*[,;]\s*|\s+and\s+|\s+))?'
    r'(?:(?:was|were|is|has\s+been|had\s+been)\s+)?'
    + _BARE_NEGATION + r'\s+' + STATUS_WORD + _BARE_TAIL +
    r'(?:\s*(?:,|or|nor|and)\s+(?:(?:not|never)\s+)?' + STATUS_WORD + _BARE_TAIL + r')*'
    r'[\s.!]*')
# A statement that a procedure was not done, was called off, was cut short or is in doubt, whose subject routing never
# resolves (a pronoun, or "the procedure" with a predicate the reference patterns do not read): "It was not performed.",
# "It was cancelled before sedation.", "This was postponed.", "It is unclear whether the procedure was completed." Read
# only to keep a bare negated status word held (detect._bare_negation_hold): beside such a statement the bare sentence
# may be the only words routing reads about whether the procedure happened. Never read to deny or hold anything else.
_UNREAD_SUBJECT = r'(?:it|this|(?:the\s+)?(?:procedure|exam|examination|study|endoscopy))'
UNREAD_SERVICE_DOUBT = rx(
    r'\b' + _UNREAD_SUBJECT + r'\s+(?:was|is|has\s+been|had\s+been|will\s+be|would\s+be)\s+'
    r'(?:(?:not|never)\s+(?:(?:been|be|yet)\s+)?(?:performed|done|started|begun|undertaken|attempted|completed?|possible|'
    r'feasible|carried\s+out)'
    r'|' + STATUS_WORD + r'|incomplete|rescheduled|abbreviated|limited)\b'
    r'|\b' + _UNREAD_SUBJECT + r"\s+(?:did\s+not|didn't|never|could\s+not|couldn't)\s+(?:happen|occur|take\s+place|start|"
    r'begin|proceed|be\s+(?:performed|done|completed))\b'
    r'|\b(?:unclear|uncertain|unknown|not\s+(?:clear|certain|known|documented))\s+(?:whether|if)\b'
    r'|\b' + _UNREAD_SUBJECT + r'\s+(?:was|is)\s+(?:possibly|probably|likely|perhaps|maybe|reportedly|presumably)\b'
    # a modal about the procedure itself ("The procedure may have been incomplete.", "It might not have been completed.")
    r'|\b' + _UNREAD_SUBJECT + r'\s+(?:may|might|could|would|must)\s+(?:not\s+)?(?:have\s+)?(?:been|be)\b'
    # the patient leaving before or without it ("The patient left before the procedure began."), a no-show, a refusal
    # of "it"
    r'|\b(?:left|departed|leaves|leaving)\s+(?:\w+\s+){0,2}?(?:before|without|prior\s+to)\b'
    r"|\bno[- ]show\b|\bdid\s+not\s+(?:show|arrive)\b|\b(?:declined|refused)\s+(?:it|this)\b")
# "aborted" after the scope went in is an incomplete procedure, not a cancellation;
# "before sedation" keeps it a cancellation. An abort that says neither is held as
# uncertain (detect._abort_status), never excluded as cancelled.
# The instrument's course: it went in and was moved on ("was advanced", "the colonoscope reached", "insertion", "after
# reaching"). STARTED adds a depth ("at 30 cm"), which also writes a size ("a polyp of 2 cm"); COURSE is the course
# alone, read where a size would mislead (sections._reporting_heads: a later section that narrates an examination's
# course; GI round 2 fix round, extent). One string, so the two never drift.
_COURSE = (r'\b(?:was|were)\s+(?:then\s+)?(?:advanced|inserted|introduced|passed|intubated|reached)\b'
           r'|\binsertion\b|\bintubation\s+of\b'
           r'|\b(?:scope|colonoscope|endoscope|gastroscope|sigmoidoscope|duodenoscope|echoendoscope|enteroscope|'
           r'instrument)\s+(?:had\s+|was\s+|then\s+)?(?:reached|advanced|passed|entered|traversed|inserted|introduced)\b'
           r'|\bafter\s+(?:reaching|advancing|passing|entering|traversing|intubating|insertion|intubation)\b')
COURSE = rx(_COURSE)
STARTED = rx(_COURSE + r'|\b(?:at|to|of)\s+(?:approximately\s+|about\s+|~\s*)?\d{1,3}\s*cm\b')
BEFORE_START = rx(r'\b(?:before|prior\s+to)\s+(?:the\s+)?(?:sedation|insertion|scope\s+insertion|intubation|'
                  r'start(?:ing)?|the\s+procedure\s+(?:began|started)|procedure\s+start|endoscope\s+insertion)\b')

# --- page furniture: what a page prints at its head or foot, outside the document's flow ---------------------------

FURNITURE_CHARS = 100  # a running header or footer is one short line
PAGE_NUMBER_LINE = rx(r'[^\w\n]*(?:(?:page|pg|p)\.?[ \t]*)?\d{1,4}(?:[ \t]*(?:of|/)[ \t]*\d{1,4})?[^\w\n]*')
_FURNITURE_WORD = rx(r"[a-z][a-z0-9/'-]*")


def page_number_line(line: str) -> bool:
    """Whether ``line`` is a page number and nothing else ("Page 1 of 2", "- 1 -", "2", "p. 3", "1/2")."""
    stripped = line.strip()
    return 0 < len(stripped) <= FURNITURE_CHARS and PAGE_NUMBER_LINE.fullmatch(stripped) is not None


def heading_shaped_line(line: str) -> bool:
    """Whether ``line`` is a short line written as a heading, as a letterhead, a running title or a confidentiality or
    print stamp is ("Confidential", "Printed 10/27/2026 09:14", "SCREENING COLONOSCOPY (continued)"): most of its words
    carry a capital letter, and it ends with no stop, colon, semicolon or comma. Bounded: FURNITURE_CHARS."""
    stripped = line.strip()
    if not stripped or len(stripped) > FURNITURE_CHARS or stripped[-1] in '.!?:;,':
        return False
    words = _FURNITURE_WORD.findall(stripped)
    return bool(words) and 2 * sum(1 for word in words if any(c.isupper() for c in word)) > len(words)


# --- incomplete: started but not completed as intended ---------------------------


class _Undenied:
    """A stop word ("discontinued") read like a compiled pattern (finditer, search), whose match a "not" or "never"
    directly before it withdraws across any run of whitespace, never a fixed count of it (refutation r1, formats-6: a
    look-behind that reached across at most two whitespace characters read a page join - "The procedure was not" at
    the foot of one page, "discontinued; it was completed" atop the next - and a wide gap on one line as a discontinued
    procedure). Only whitespace may stand between the two words, or, where a page join leaves them (_across_furniture),
    the page's running header or footer."""

    _DENIAL = rx(r'\b(?:not|never)$')
    FURNITURE_LINES = 3  # lines of a page's head and foot read across (bounded work per stop word)
    FURNITURE_GAP = 200  # whitespace read across before each of them

    def __init__(self, pattern: str):
        self._words = rx(pattern)
        self.pattern = pattern

    def _denied(self, string: str, start: int) -> bool:
        gap = start
        while gap > 0 and string[gap - 1].isspace():
            gap -= 1
        if gap == start:
            return False
        return self._DENIAL.search(string, max(0, gap - 5), gap) is not None \
            or self._across_furniture(string, gap, start)

    def _across_furniture(self, string: str, gap: int, start: int) -> bool:
        """Whether the negation ends a line and the stop word opens a later one with only a page's furniture between
        them: whole lines that are a page number (page_number_line) or, before a stop word that goes on in lower case,
        written as a heading (heading_shaped_line), where a page join leaves them - a blank line among the whitespace
        (refutation 7c8, formats-6: "The procedure was not" / "Page 1 of 2" / "discontinued; it was completed", and a
        letterhead, "Confidential" or "SCREENING COLONOSCOPY (continued)" there, had read a discontinued procedure).
        Without page spans, routing knows a page join only by the blank line it leaves. Bounded: FURNITURE_LINES lines
        of FURNITURE_CHARS, each after at most FURNITURE_GAP whitespace."""
        run = string[gap:start]
        if '\n' not in run:
            return False  # the stop word does not open its line
        lower = string[start].islower()
        blank = run.count('\n') >= 2
        end = gap
        for _ in range(self.FURNITURE_LINES):
            newline = string.rfind('\n', max(0, end - FURNITURE_CHARS - 1), end)
            if newline < 0:
                return False  # a line longer than furniture, or the text's first line
            line = string[newline + 1:end]
            if not (page_number_line(line) or lower and heading_shaped_line(line)):
                return False
            before = newline
            while before > 0 and string[before - 1].isspace() and newline - before < self.FURNITURE_GAP:
                before -= 1
            blank = blank or string.count('\n', before, newline + 1) >= 2
            if self._DENIAL.search(string, max(0, before - 5), before) is not None:
                return blank
            end = before
        return False

    def finditer(self, string: str, pos: int = 0, endpos: int = sys.maxsize):
        return (m for m in self._words.finditer(string, pos, endpos) if not self._denied(string, m.start()))

    def search(self, string: str, pos: int = 0, endpos: int = sys.maxsize):
        return next(self.finditer(string, pos, endpos), None)



INCOMPLETE_CLAUSE = (
    # Subject-less forms name only scope movement: "unable to complete the preparation"
    # is about the patient, not the procedure.
    ('unable to', rx(r'\bunable\s+to\s+(?:be\s+)?(?:advance|advanced|reach|reached|intubate|intubated|cannulate|'
                     r'cannulated|pass|passed|traverse|traversed|access|enter)\b')),
    ('could not', rx(r'\bcould\s+not\s+(?:be\s+)?(?:advance|advanced|reach|reached|intubate|intubated|cannulate|'
                     r'cannulated|pass|passed|traverse|traversed)\b')),
    ('not reached', rx(r'\b(?:was|were)\s+not\s+(?:reached|intubated|cannulated|traversed|examined|visualized)\b')),
    # "it was not advanced to the cecum", "was never advanced beyond", "did not reach the duodenum"
    ('not advanced', rx(r'\b(?:was|were|is|are|been)\s+(?:not|never)\s+(?:able\s+to\s+be\s+|successfully\s+|further\s+|'
                        r'safely\s+)?(?:advanced|passed|inserted|introduced)\s+(?:\w+\s+){0,3}?(?:to|into|beyond|past|'
                        r'through|as\s+far\s+as)\b'
                        r"|\b(?:did|does|could|can)\s*(?:not|n't)\s+(?:be\s+)?(?:reach|advance|pass|intubate|enter|"
                        r'traverse)\b'
                        r'|\bnever\s+(?:reached|advanced|passed|intubated|entered|traversed)\b'
                        r'|\bfailed\s+to\s+(?:reach|advance|pass|intubate|enter|traverse)\b|\bwithout\s+reaching\b')),
    ('prevented', rx(r'\bprevent(?:ed|s|ing)\s+(?:\w+\s+){0,2}?(?:passage|advancement|intubation|entry|traversal|'
                     r'examination|evaluation|insertion)\b|\bimpassable\b|\bnon-?traversable\b')),
    ('terminated', _Undenied(r'\b(?:terminated|discontinued|halted)\b')),
    ('stopped', rx(r'\bstopped\s+(?:at|short|due|because|before)\b')),
    ('precluded', rx(r'\bprecluded\b')),
    ('failed cannulation', rx(r'\b(?:failed|unsuccessful)\s+(?:attempts?\s+at\s+)?(?:deep\s+|selective\s+|biliary\s+|'
                              r'bile\s+duct\s+|pancreatic\s+)?cannulation\b|\bcannulation\s+(?:\w+\s+){0,5}?'
                              r'(?:was\s+|were\s+)?(?:unsuccessful|not\s+achieved|not\s+possible|failed)\b'
                              r'|\b(?:was|were)\s+unsuccessful\b')),
)
# "terminated"/"discontinued" about a medication is not a procedure outcome.
MEDICATION = rx(r'\b(?:aspirin|clopidogrel|plavix|prasugrel|ticagrelor|warfarin|coumadin|apixaban|eliquis|'
                r'rivaroxaban|xarelto|dabigatran|edoxaban|heparin|enoxaparin|lovenox|anticoagula\w*|'
                r'antiplatelet\w*|medications?|meds|iron|metformin|insulin|semaglutide|tirzepatide|glp-1|'
                r'nsaids?|ppi|omeprazole|pantoprazole|esomeprazole|therapy|treatment|supplements?|diet|drug)\b')

# --- planned: the service is in the future ---------------------------------------

_NUMBER = r'(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a\s+few|several)'
PLANNED_PRE = (
    ('upcoming', _pre(r'upcoming|future|planned|scheduled|proposed|anticipated|next', _HIST_FILLER, 3)),
)
PLANNED_CLAUSE = (
    ('scheduled', rx(r'\b(?:re-?)?scheduled\b')),
    ('will', rx(r'\bwill\b|\bshall\b')),
    ('plan', rx(r'\bplan(?:s|ned|ning)?\b')),
    ('recommend', rx(r'\brecommend(?:s|ed|ing|ation|ations)?\b')),
    ('consider', rx(r'\bconsider(?:s|ed|ing|ation)?\b')),
    ('next', rx(r'\bnext\s+(?:week|month|year|visit|appointment|available|step|steps)\b|\btomorrow\b')),
    ('upcoming', rx(r'\bupcoming\b|\bfuture\b|\bawaiting\b')),
    ('to be done', rx(r'\bto\s+be\s+(?:performed|scheduled|done|arranged|booked|repeated|completed|taken|obtained|'
                      r'placed|removed|resected|sent|considered|discussed)\b')),
    ('referred for', rx(r'\breferr(?:ed|al|ing)\s+(?:for|to)\b')),
    ('ordered', rx(r'(?<!in )\border(?:ed|s)?\b')),
    ('due', rx(r'\bdue\s+(?:for|in|now|at)\b')),
    ('booked', rx(r'\bbook(?:ed|ing)?\b|\barrang(?:e|ed|ing)\b')),
    ('should undergo', rx(r'\bshould\s+(?:undergo|have|be\s+performed)\b')),
    ('in N weeks', rx(r'\b(?:in|within|after)\s+' + _NUMBER + r'(?:\s*(?:-|to)\s*\d+)?\s+(?:days?|weeks?|months?|years?)\b')),
)

# --- another time: a time the listed cues do not read --------------------------------------------------------------
# Read only to HOLD (detect._another_time): an unlisted time attached to a service keeps it from reading performed, and
# never makes it historical or planned (round 3b's hold-only rule: routing:8, routing:10). A weekday, a month or a
# month/day is compared with the date of service (detect._today_compatible). The class is open; this is its common
# vocabulary, and a miss leaves the reading where it was.
_UNIT_ABBR = r'(?:d|days?|wks?|weeks?|mos?|months?|yrs?|years?)'
_FEW = (r'(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a\s+few|few|several|'
        r'(?:a\s+)?couple\s+of)')
_WEEKDAY = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
_MONTH_NAME = (r'(?:january|february|march|april|june|july|august|september|october|november|december'
               r'|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)')
_MONTH_LEAD = r'(?:in|on|during|by|until|early|mid|late|end\s+of|beginning\s+of|this|last|next|past)'
OTHER_TIME = (
    # "next Tuesday", "on Tuesday" (a weekday other than the date of service's)
    ('weekday', rx(r'\b(?:(?P<rel>next|last|this|coming|past|previous)\s+)?' + _WEEKDAY + r's?\b')),
    # "in November", "on November 3", "in early November", "November 3", "in May": a month with no year
    ('month', rx(r'(?:\b' + _MONTH_LEAD + r'[\s-]+(?:(?:early|mid|late)[\s-]+)?(?P<month>' + _MONTH_NAME + r')\.?'
                 r'(?:\s+(?P<mday>\d{1,2})(?:st|nd|rd|th)?)?'
                 # May: the part-of-month leads and the hyphen every other month takes, and its day (round 5
                 # declared:7); 'last' / 'past' only before a capitalised May ("The last may be benign." is the
                 # modal), and never 'this' or 'next', which open the modal "This may represent ..."
                 r'|\b(?:(?:in|on|during|by|until|early|mid|late|end\s+of|beginning\s+of)[\s-]+'
                 r'|(?:last|past)[\s-]+(?=(?-i:May|MAY)\b))(?P<may>may)(?:\s+(?P<mayday>\d{1,2})(?:st|nd|rd|th)?)?'
                 r'|\b(?P<month2>' + _MONTH_NAME + r'|may)\.?\s+(?P<mday2>\d{1,2})(?:st|nd|rd|th)?)\b(?![\s,]*\d{4})')),
    # "on 10/14": a month and a day with no year
    ('month/day', rx(r'\b(?:on|dated|by|until)\s+(?P<m>\d{1,2})/(?P<d>\d{1,2})\b(?!/\d)')),
    ('yesterday', rx(r'\byesterday\b|\bthe\s+(?:day|night|evening)\s+(?:before|prior)\b'
                     r'|\bthe\s+previous\s+(?:day|night|evening|morning|afternoon)\b|\blast\s+(?:night|evening)\b')),
    # "two weeks prior", "3 days earlier", "6 mos later"
    ('interval', rx(r'\b' + _FEW + r'[\s-]*' + _UNIT_ABBR + r'\s+(?:prior|earlier|before|previously|later|afterwards?|'
                    r'after|from\s+now|hence|out)\b')),
    # "in 2 wks", "in the coming weeks", "within the next few months"
    ('in N', rx(r'\b(?:in|within|over|during)\s+(?:the\s+)?(?:next|coming|following|upcoming)\s+(?:' + _FEW + r'\s+)?'
                + _UNIT_ABBR + r'\b|\b(?:in|within|after)\s+' + _FEW + r'\s*(?:d|wks?|mos?|yrs?)\b')),
    # "next Thursday", "at the next session": never "next to", "the next polyp", "Next, the scope ..."
    ('next', rx(r'(?<!\bthe\s)(?<!\ba\s)\bnext\s+(?!(?:to|the|a|an|we|i|she|he|it|this|that|step|steps|one|ones|'
                r'portion|part|segment)\b)[a-z]+')),
    ('convenience', rx(r"\bat\s+(?:her|his|their|the\s+patient'?s|your|our|a|the)\s+(?:earliest\s+)?"
                       r'convenien(?:ce|t\s+time)\b|\bwhen\s+convenient\b')),
    ('holidays', rx(r'\b(?:after|over|before)\s+the\s+holidays?\b')),
    # "at her last visit", "during her recent hospitalization", "on a prior exam", "at her last procedure"
    ('another encounter', rx(r'\b(?:at|during|on)\s+(?:her|his|their|the|a|an)\s+(?:(?:last|previous|prior|recent|most\s+'
                             r'recent|earlier|index)\s+)+(?:office\s+|clinic\s+|hospital\s+)?(?:visits?|appointments?|'
                             r'encounters?|admissions?|hospitali[sz]ations?|stays?|procedures?|exams?|examinations?|'
                             r'stud(?:y|ies)|endoscop(?:y|ies)|scopes?|consult(?:ation)?s?|evaluations?)\b'
                             r'|\bduring\s+(?:her|his|their|a|an)\s+(?:hospitali[sz]ation|admission|(?:hospital\s+)?stay)\b')),
    ('childhood', rx(r'\bas\s+an?\s+(?:child|teen(?:ager)?|adolescent|infant|baby|toddler|young\s+(?:adult|man|woman|girl|'
                     r'boy))\b|\bin\s+(?:her|his|their|early)\s+(?:childhood|youth|teens)\b|\bin\s+childhood\b')),
    # "recently underwent", "previously had", "was performed recently"; never a kept booking ("as previously
    # scheduled") or a participle's own time ("performed on the previously tattooed polyp")
    ('recently', rx(r'\b(?:recently|previously|formerly)\s+(?:underwent|undergone|had|received|completed|performed|done)\b'
                    r'|\b(?:underwent|undergone|performed|done|completed)\s+(?:(?!today\b)\w+\s+){0,3}?'
                    r'(?:recently|previously)\b(?!\s+\w+(?:ed|en)\b)')),
)

# --- incomplete, anchored to a named service or to "the procedure" ----------------

INCOMPLETE_PRE = (
    ('incomplete', _pre(r'incomplete|partial|attempted|failed|unsuccessful'
                        r'|(?:unable\s+to|could\s+not|failed\s+to)\s+complete', _HIST_FILLER, 2)),
)
INCOMPLETE_POST = (
    ('was incomplete', rx(r'^[\s,]*(?:was|is|remained|were)\s+(?:incomplete|terminated|discontinued|halted|'
                          r'unsuccessful|not\s+completed)\b')),
    # "Colonoscopy, attempted", "ERCP (attempted)", "Colonoscopy was attempted", "EGD - partial"
    ('attempted', rx(r'^[\s,]*(?:[-\u2013:]\s*|\(\s*)?(?:was\s+|were\s+|is\s+)?(?:attempted|incomplete|partial|'
                     r'abandoned|unsuccessful|not\s+completed|not\s+finished)\b')),
)
# "The procedure was cancelled" / "No procedure was performed": the service is referred to,
# not named; read for the family the sentence describes.
PROCEDURE_CANCELLED = rx(
    r'\b(?:procedure|exam|examination|study|endoscopy)\s+(?:was\s+|is\s+|has\s+been\s+|had\s+been\s+)?'
    r'(?:cancel(?:l)?ed|postponed|deferred|called\s+off|rescheduled|not\s+(?:started|begun|done))\b'
    r'|\b(?:cancel(?:l)?ed|postponed|deferred|called\s+off)\s+(?:the\s+)?(?:procedure|exam|examination|study)\b')
PROCEDURE_NOT_PERFORMED = rx(
    r'\b(?:procedure|exam|examination|study|endoscopy)\s+(?:was|is|has\s+been|had\s+been)\s+not\s+'
    r'(?:performed|attempted|undertaken)\b|\bno\s+(?:procedures?|endoscop(?:y|ies)|exam(?:ination)?s?)\s+'
    r'(?:was|were|has\s+been|have\s+been)\s+(?:performed|done|undertaken|attempted)\b'
    r'|\b(?:declined|refused)\s+(?:the\s+)?(?:procedure|exam|examination|study)\b'
    r'|\b(?:procedure|exam|examination|study)\s+(?:was\s+)?(?:declined|refused)\b')
# Whole-procedure incompleteness written about "the procedure/exam" rather than a named service.
PROCEDURE_INCOMPLETE = rx(
    r'\bincomplete\s+(?:[\w-]+\s+){0,2}?(?:exam|examination|procedure|study|evaluation|intubation|colonoscopy|egd|'
    r'endoscopy|sigmoidoscopy|ercp|eus|ileocolonoscopy|esophagogastroduodenoscopy)\b'
    r'|\b(?:exam|examination|procedure|study|colonoscopy|egd|endoscopy|sigmoidoscopy|ercp|eus)\s+(?:was\s+|is\s+)?'
    r'(?:incomplete|terminated|discontinued|aborted|stopped|halted|not\s+completed)\b'
    r'|\b(?:unable\s+to|could\s+not)\s+(?:be\s+)?complet(?:e|ed)\s+(?:the\s+)?(?:exam|examination|procedure|study)\b'
    r'|\b(?:terminated|discontinued|aborted|stopped|halted)\s+(?:the\s+)?(?:exam|examination|procedure|study)\b')

# --- uncertain: documentation does not commit either way ------------------------

UNCERTAIN_PRE = (
    ('possible', _pre(r'possible|possibly|potential|probable|questionable|\?|pending'
                      r'|(?:may|might|could)\s+(?:need|require|undergo|benefit\s+from|warrant|consider|have)', _HIST_FILLER, 2)),
    # Consent and discussion describe a service; they do not report it done. Anchored to
    # the service, so "after consent was obtained, the scope was advanced to the cecum"
    # still reads the cecum as reached.
    ('consent for', _pre(r'consent(?:ed)?\s+(?:was\s+obtained\s+)?for|discuss(?:ed|ing)|discussion\s+(?:of|about)'
                         r'|risks?(?:,?\s+benefits?)?(?:,?\s+and\s+alternatives)?\s+of', _NEG_FILLER, 3)),
)
# Hedges right after the name of an act (HEDGED_AFTER): a perfect modal or a hedging adverb, which may also follow a
# short phrase of place or means ("Biopsies may have been taken", "Biopsies of the cecum might have been obtained",
# "were possibly obtained", "EGD with dilation would have been completed had ..."); a future modal straight after the
# name ("EGD would be done if ...", "Biopsies would be obtained at a repeat EGD"; only "would": "should", "may" and
# "might be" are plan wording, and a plan line must keep its planned reading); a hedging adverb before the
# participle ("Biopsies possibly taken"); an attempt with no outcome after it, also after a phrase of place ("Biopsy
# of the lesion was attempted."); and a key-value state that closes its value ("Biopsy: unsure.").
_HEDGE_ACT = (r'(?:performed|done|completed|undertaken|carried\s+out|attempted|obtained|taken|removed|resected|excised|'
              r'placed|biopsied|sampled|dilated|injected|treated|clipped|tattooed|deployed|inserted|retrieved|ligated|'
              r'banded|cauterized|coagulated|ablated|extracted|aspirated|cannulated|reached|advanced|examined|'
              r'visualized|intubated|passed|sent|given|administered|used)')
_HEDGE_ADVERB = (r'(?:possibly|probably|likely|presumably|apparently|perhaps|maybe|reportedly|supposedly|seemingly|'
                 r'allegedly)')
_HEDGE_MODAL = (r'(?:may|might|could|would|should|must)\s+(?:(?:possibly|perhaps|also|well|then)\s+)?(?:have\s+been|have)'
                r'|(?:was|were|is|are|has\s+been|have\s+been|had\s+been)\s+' + _HEDGE_ADVERB
                # the adverb before the auxiliary, and a report or a belief: "probably were taken", "were thought to have
                # been taken", "were reported to have been obtained"
                + r'|' + _HEDGE_ADVERB + r'\s+(?:was|were|has\s+been|have\s+been|had\s+been)'
                r'|(?:was|were|is|are)\s+(?:thought|believed|felt|presumed|assumed|suspected|reported|said)\s+to\s+'
                r'(?:have\s+been|be)')
# A short phrase of place or means: up to four words, none of which opens a new clause or a verb phrase.
_PLACE_WORD = (r'(?!(?:after|before|when|while|once|until|because|since|as|and|or|but|so|then|if|unless|it|its|this|that|'
               r'these|those|which|who|whom|whose|where|was|were|is|are|had|has|have|been|being|be)\b)[\w/-]+')
_PLACE_PHRASE = (r'(?:\s+(?:of|from|in|at|on|to|with|within|along|into|near)\s+(?:' + _PLACE_WORD + r'\s+){0,3}?'
                 + _PLACE_WORD + r')?')
_NO_OUTCOME = (r'(?![^.;:!?\n]{0,60}\b(?:success\w*|achieved|accomplished|completed|obtained|taken|removed|'
               r'performed|done)\b)')
HEDGED_AFTER = rx(r'^' + _PLACE_PHRASE + r'[\s,]*(?:(?:' + _HEDGE_MODAL + r')\s+' + _HEDGE_ACT + r'\b'
                  r'|(?:was|were)\s+attempted\b' + _NO_OUTCOME + r')'
                  r'|^[\s,]*(?:would\s+(?:then\s+|also\s+)?be\s+' + _HEDGE_ACT
                  + r'|(?:possibly|probably|likely|presumably|perhaps|maybe|reportedly)\s+' + _HEDGE_ACT + r')\b'
                  r'|^\s*[:=\u2013\u2014|-]+\s*(?:unsure|unknown|uncertain|unclear|undetermined|unconfirmed|not\s+sure|'
                  r'questionable|possibl[ey]|maybe|\?)(?=\s*(?:[.;,)\]]|$))')
UNCERTAIN_POST = (
    ('if needed', rx(r'^[\s,]*(?:\?|if\s+(?:needed|necessary|indicated|required|warranted|appropriate|'
                     r'clinically\s+indicated)\b|as\s+needed\b|vs\.?\s|versus\b)')),
    # "ERCP pending insurance approval", "Colonoscopy: pending"
    ('pending', rx(r'^[\s,]*(?:[:=\u2013-]\s*|\(\s*)?(?:is\s+|are\s+|was\s+|remains\s+|still\s+)*pending\b')),
    ('was discussed', rx(r'^[\s,]*(?:was|were|has\s+been|have\s+been)\s+(?:discussed|explained|reviewed\s+with)\b')),
    ('may be needed', rx(r'^[\s,]*(?:may|might|could)\s+(?:be|become)\s+(?:needed|necessary|required|indicated|'
                         r'considered|performed|helpful|warranted)\b')),
    # Named "pending" on purpose: like "pending" it leaves the act open, so the reading is a doubt
    # (detect._clause_reading_cues) that contradicts section evidence. A plain hedge here could turn a doubt that
    # holds today's service now (an unresolved negation, or a stop after the name such as "Colonoscopy would be
    # done.") into a hedge that no longer contradicts its section, and so release the family.
    ('pending', HEDGED_AFTER),
)
# Clause-scope doubt words are few on purpose: "possible" and "may" mostly qualify a
# diagnosis ("biopsies for possible celiac disease"), so they are anchored above. One more entry,
# HYPOTHETICAL, is added after the service names (it reads only sentences that name none).
UNCERTAIN_CLAUSE = (
    ('unclear whether', rx(r'\bunclear\s+(?:whether|if)\b|\bundecided\b')),
    ('if needed', rx(r'\bif\s+(?:needed|necessary|indicated|required|warranted|appropriate|clinically\s+indicated|'
                     r'symptoms\s+(?:persist|recur|worsen|continue))\b|\bas\s+needed\b')),
    ('candidate for', rx(r'\bcandidate\s+for\b')),
    ('versus', rx(r'\bvs\.?(?=\s)|\bversus\b')),
    ('question mark', rx(r'\?')),
)

# --- performed: explicit past-tense performance ---------------------------------

PERFORMED_CLAUSE = (
    ('was performed', rx(r'\b(?:was|were|has\s+been|have\s+been|had\s+been)\s+(?:successfully\s+|uneventfully\s+|'
                         r'then\s+|subsequently\s+)?(?:performed|completed|done|carried\s+out|undertaken|'
                         r'accomplished|achieved)\b')),
    ('performed today', rx(r'\b(?:performed|completed|done)\s+(?:today|this\s+(?:morning|afternoon|evening))\b')),
    ('was advanced', rx(r'\b(?:was|were)\s+(?:then\s+|carefully\s+|gently\s+|easily\s+|subsequently\s+)?'
                        r'(?:advanced|inserted|introduced|passed|withdrawn|retroflexed|intubated|cannulated|'
                        r'reached|removed|resected|retrieved|obtained|taken|placed|deployed|dilated|injected|'
                        r'ligated|clipped|sampled|aspirated|examined|visualized|traversed|extracted|cleared|'
                        r'swept)\b')),
    ('underwent', rx(r'\bunderwent\b')),
    ('tolerated', rx(r'\btolerated\s+(?:the\s+)?(?:procedure|exam|examination|study|it|well)\b')),
    ('we performed', rx(r'\b(?:we|i)\s+(?:performed|completed|did)\b')),
)
TODAY = rx(r'\btoday\b|\bthis\s+(?:morning|afternoon|evening)\b|\bon\s+the\s+date\s+of\s+(?:the\s+)?'
           r'(?:encounter|service|visit|procedure)\b')

# --- service names --------------------------------------------------------------
# Instrument words ("colonoscope") are not mentions: a colonoscope can perform a
# sigmoidoscopy. "upper endoscopy" never means colonoscopy, "EUS-guided" belongs
# to EUS, and an ERCP's duodenoscope is not an EGD.

SERVICE_PATTERNS = (
    ('gi.eus', rx(r'\bEUS\b|\bendoscopic\s+ultra(?:sound|sonography|sonographic)\b|\bendosonograph(?:y|ic)\b'
                  r'|\bechoendoscopy\b')),
    ('gi.ercp', rx(r'\bERCP\b|\bendoscopic\s+retrograde\s+cholangio-?pancreatograph(?:y|ies)\b')),
    ('gi.egd', rx(r'\bEGD\b|\besophagogastroduodenoscop(?:y|ies)\b'
                  r'|\bupper\s+(?:GI\s+|gastrointestinal\s+)?endoscop(?:y|ies)\b(?!\s+ultraso)'
                  r'|\besophagoscop(?:y|ies)\b|\bgastroscop(?:y|ies)\b'
                  r'|\b(?:push\s+|small[- ]bowel\s+|(?:double|single)[- ]balloon\s+)?enteroscop(?:y|ies)\b')),
    ('gi.colonoscopy', rx(r'\b(?:ileo)?colonoscop(?:y|ies|ic)\b')),
    ('gi.flex_sig', rx(r'\b(?<!rigid\s)(?:flexible\s+)?sigmoidoscop(?:y|ies|ic)\b|\bflex(?:ible|\.)?\s+sig\b')),
)
# "FS" for flexible sigmoidoscopy only as a standalone capitalised token.
FS_ABBREVIATION = re.compile(r'(?<![\w/.-])FS(?![\w/-])', re.A)

# --- uncertain: a hypothetical or a hedge in a sentence that names no service -----------------------------------
# "Had there been a stricture, it would have been dilated with a balloon.", "A stricture would have been dilated had
# one been found.", "Biopsies of the antrum were possibly obtained.", "Biopsy of the cecal lesion, if feasible.".
# An uncertain clause cue that runs from the start of its sentence, read only where nothing in the sentence names a
# service: so it never attaches to a service mention and never turns a doubt about today's service into a plain
# hedge (after a service name, UNCERTAIN_POST's HEDGED_AFTER reads the hedge as a doubt). Added to UNCERTAIN_CLAUSE
# here because it needs SERVICE_PATTERNS.
_ANY_SERVICE = '|'.join(f'(?:{p.pattern})' for _, p in SERVICE_PATTERNS) + r'|(?<![\w/.-])FS(?![\w/-])'
_NO_SERVICE = r'(?:(?!' + _ANY_SERVICE + r')[^.;:!?\n])'
_SENTENCE_HEDGE = (r'(?:' + _HEDGE_MODAL + r'|(?:would|should|may|might)\s+(?:then\s+|also\s+)?be)\s+' + _HEDGE_ACT + r'\b'
                   r'|\bif\s+(?:feasible|possible|tolerated)\b')
HYPOTHETICAL = rx(r'(?:^|(?<=[.;:!?\n])|(?<=[.;:!?\n][ \t])|(?<=[.;:!?\n][ \t][ \t]))(?=\S)'
                  r'(?=' + _NO_SERVICE + r'{0,240}(?:[.;:!?\n]|$))' + _NO_SERVICE + r'{0,200}?\b'
                  r'(?:' + _SENTENCE_HEDGE + r')', FLAGS | re.M)
# A condition on the performance of a named service that opens its sentence: "If colonoscopy were done today, the
# bleeding risk would be high.", "Were a colonoscopy done today, ...", "Had a colonoscopy been done today, ...",
# "Should EGD be performed, ...". Only in a sentence with no negation word: there an unresolved negation already holds
# the service as a doubt, which a plain hedge would pre-empt (and so could release the family). With the performance
# participle right after the service, no stop after the name can doubt it either.
_SERVICE_RUN = (r'(?:(?:the|a|an)\s+)?(?:' + _ANY_SERVICE + r')(?:\s*(?:,|and|or)\s*(?:(?:the|a|an)\s+)?(?:' + _ANY_SERVICE
                + r')){0,2}')
CONDITIONAL = rx(r'(?:^|(?<=[.;:!?\n])|(?<=[.;:!?\n][ \t])|(?<=[.;:!?\n][ \t][ \t]))(?:if|unless|were|had|should)\s+'
                 + _SERVICE_RUN + r'\s+(?:(?:were|was|is|are|be|been|had\s+been|has\s+been|have\s+been)\s+)?'
                 r"(?:done|performed|completed|undertaken|carried\s+out)\b(?![^.;!?\n]{0,300}?(?:\b(?:no|not|never|neither|"
                 r"nor|none|without|cannot|unable|declined|refused)\b|n't\b))", FLAGS | re.M)
UNCERTAIN_CLAUSE = UNCERTAIN_CLAUSE + (('hypothetical', HYPOTHETICAL), ('if', CONDITIONAL))

# A title line such as "COLONOSCOPY REPORT" opens a procedure section.
PROCEDURE_TITLE = rx(r'^[\w /&+,()-]{0,60}?\b(?:procedure\s+)?(?:report|note)$')

# --- office E/M documentation ----------------------------------------------------

EM_VISIT = rx(r'\b(?:(?:in-person\s+|outpatient\s+|ambulatory\s+)?(?:office|clinic)\s+(?:visit|consultation|consult|'
              r'encounter)|outpatient\s+(?:visit|consultation|consult|encounter)|(?:telehealth|telemedicine|video|'
              r'virtual|audio-video)\s+(?:visit|encounter|consultation)|new[- ]patient\s+(?:visit|evaluation|'
              r'consultation|consult|encounter)|established[- ]patient\s+(?:visit|encounter)|follow[- ]?up\s+'
              r'(?:office\s+|clinic\s+)?visit|progress\s+note|evaluation\s+and\s+management)\b')
# gi3 scope (interpretation 43): the visit's documented time by its subject. Total time, time spent, the visit's or the
# encounter's time and "time on the date of ..." are the visit's by their words. A clinician's time ("Face-to-face time",
# "Physician time", "I personally spent": the ``clinician`` group) is the visit's only where its sentence frames it as
# E/M time is framed (EM_TIME_FRAME), or beside a marker of today's visit outside today's procedure text
# (detect._visit_clinician_times): never a procedure's or an interpretation's time ("Physician time: 25 minutes." in an
# EGD report). A procedure's time is still refused sentence by sentence (NOT_EM_TIME).
EM_TIME = rx(r'\b(?:total\s+(?:\w+\s+){0,2}?time|time\s+spent|(?:i|we)\s+spent|spent\s+a\s+total\s+of'
             r'|(?:visit|encounter)\s+time|time\s+on\s+the\s+(?:date|day)\s+of'
             r'|(?P<clinician>(?:face[- ]to[- ]face|physician|clinician|provider|practitioner)\s+time'
             r'|(?:i|we)\s+personally\s+spent))\b[^.;\n]{0,140}?'
             r'\b(?P<minutes>\d{1,3})\s*(?:minutes|mins?)\b')
# The words that frame a clinician's time as E/M time, AMA's own: the date of the encounter or of service, today, and
# counselling or coordination of care (a closed class). The date words are one string with EM_TIME_DAY (gi3 fix round
# 1), so the two never drift.
_EM_TIME_DAY = (r'today|on\s+the\s+(?:date|day)\s+of|(?:service|encounter|visit)\s+date'
                r'|date\s+of\s+(?:service|the\s+(?:encounter|visit))')
EM_TIME_FRAME = rx(r'\b(?:' + _EM_TIME_DAY + r'|counsel(?:l)?(?:ing|ed)?|coordinat\w*\s+(?:of\s+)?care'
                   r'|care\s+coordination)\b')
EM_TIME_DAY = rx(r'\b(?:' + _EM_TIME_DAY + r')\b')
# gi3 fix round 1 (SCOPE-3, SCOPE-5, SCOPE-7): what gives an E/M time statement to something other than the time spent
# on the date of the encounter - AMA's E/M time, so never the visit's, framed by counselling or not. Read only in the
# statement's own words (detect._em_time_elsewhere: its line before the subject, the words up to its minutes, and the
# phrase right after them), never in the rest of its sentence ("Total time today: 30 minutes, including review of the
# labs since the last visit." is today's).
# Another occasion (a closed class): an earlier or a later visit, appointment, encounter, session, call or consultation
# ("at the previous visit", "at the August visit", "since the last visit", "over two visits"), and a period that is no
# single date - a
# week, a month, a calendar month, a quarter or a year ("this calendar month", "last week", "per month"), a number of
# days before ("the past 30 days", "3 days ago"), and the day before or after. A statement whose own words also say the
# date of the encounter (EM_TIME_DAY) is that date's ("Total time on the date of service, including review of the
# previous visit's notes: 40 minutes").
_EM_MONTH = r'(?:january|february|march|april|may|june|july|august|september|october|november|december)'
_EM_OTHER_VISIT = (r'(?:previous|prior|last|earlier|preceding|recent|most\s+recent|index|next|upcoming|future'
                   r'|following|subsequent|later|' + _EM_MONTH + r'|(?:mon|tues|wednes|thurs|fri|satur|sun)day)\s+'
                   r'(?:(?:office|clinic|telephone|phone|video|telehealth|virtual|in-person|follow[- ]?up|return'
                   r'|new[- ]patient|established[- ]patient)\s+)?(?:visits?|appointments?|encounters?|sessions?|calls?'
                   r'|consult(?:ation)?s?)|(?:two|three|four|both|several|multiple|all|\d{1,2})\s+'
                   r'(?:visits|appointments|encounters|sessions)')
_EM_OTHER_PERIOD = (r'(?:this|last|past|previous|prior|preceding|next|coming|current|each|every|per)\s+'
                    r'(?:calendar\s+)?(?:weeks?|months?|quarters?|years?)|calendar\s+(?:week|month|quarter|year)'
                    r'|(?:past|last|previous|preceding|next)\s+\d{1,3}\s+(?:days|weeks|months)'
                    r'|\d{1,3}\s+(?:days?|weeks?|months?)\s+ago|weekly|monthly|quarterly|yearly|annually|yesterday'
                    r'|tomorrow|last\s+night|since\s+(?:the\s+|her\s+|his\s+|their\s+)?(?:last|previous|prior|'
                    + _EM_MONTH + r')')
EM_TIME_ELSEWHEN = rx(r'\b(?:' + _EM_OTHER_VISIT + r'|' + _EM_OTHER_PERIOD + r')\b')
# ... and right after the minutes only as the phrase that places them ("40 minutes at the previous visit", "45 minutes
# this week coordinating care"), never as an object further on ("40 minutes reviewing the notes of the previous visit")
# nor as an item after a comma ("20 minutes, next visit in 6 months").
EM_TIME_ELSEWHEN_AFTER = rx(r'[ \t]*(?:(?:in[ \t]+)?total[ \t]+)?(?:(?:at|during|in|on|over|for|from|within|throughout'
                            r'|since)[ \t]+)?(?:(?:the|her|his|their|a|an)[ \t]+)?(?:' + _EM_OTHER_VISIT + r'|'
                            + _EM_OTHER_PERIOD + r')\b')
# A booking (a closed class): a time the visit was booked, allotted, expected or planned to take - its qualifier right
# before or after the time noun, or a slot - never time spent ("Expected visit time: 30 minutes.", "Encounter time
# allotted: 30 minutes.", "Visit time: 30 minutes (return visit slot)." in a note started before the visit). "Time spent
# discussing the planned colonoscopy" is time spent.
_EM_BOOKING = r'allotted|allocated|expected|scheduled|booked|estimated|anticipated|reserved|planned|budgeted'
EM_TIME_BOOKED = rx(r'\b(?:(?:' + _EM_BOOKING + r')\s+(?:(?:visit|encounter|appointment)\s+)?(?:time|length|duration)'
                    r'|(?:time|length|duration)\s+(?:' + _EM_BOOKING + r')|slots?|allotment)\b')
# ... and in a parenthesis right after the minutes, any booking word qualifies them ("30 minutes (booked)")
EM_TIME_BOOKING_WORD = rx(r'\b(?:' + _EM_BOOKING + r'|slots?|allotment)\b')
# ... and any time in a note that says it was written before its visit (a closed class of statements about the note
# itself: "Note started in advance of the visit; to be completed on the day.", "Pre-visit planning note", "the visit
# has not yet taken place"): no time can have been spent at a visit still to come, so its "Visit time: 30 minutes." is
# the booked length (the known limit S2 holds such a note, never ready). Never what else was done before the visit
# ("Labs were drawn in advance of the visit.") or a pre-charting credit ("Pre-charted by the medical assistant"), which
# completed notes carry. Read once per document.
EM_PRECHARTED = rx(r'\b(?:note|chart|documentation|record)\s+(?:was\s+|is\s+)?(?:started|opened|begun|prepared|written'
                   r'|created)\s+(?:in\s+advance\s+of|ahead\s+of|before)\s+(?:the|this|today\W?s|her|his)\s+'
                   r'(?:visit|appointment|encounter)\b|\bpre-?visit\s+planning\s+note\b'
                   r'|\bto\s+be\s+completed\s+(?:on|at|after|during)\s+(?:the\s+)?(?:day\s+of\s+the\s+)?'
                   r'(?:visit|appointment|encounter)\b|\bto\s+be\s+completed\s+on\s+the\s+day\b(?!\s+of\b)'
                   r'|\b(?:visit|appointment|encounter)\s+(?:has\s+)?not\s+(?:yet\s+)?(?:occurred|taken\s+place'
                   r'|happened)\b')
# Another service's time: a drug or blood administration's (an infusion, a transfusion, an injection, a hydration, a
# chemotherapy administration), as the time's own subject ("Total infusion time: 120 minutes.", "Time spent on the
# infusion", "Total time for the infliximab administration"), as a procedure's is (NOT_EM_TIME; interpretation 43).
# Time spent discussing an infusion is the visit's.
_EM_ADMINISTRATION = r'infusions?|transfusions?|injections?|hydration|chemotherapy|administrations?'
EM_TIME_ADMINISTERED = rx(r'\b(?:(?:' + _EM_ADMINISTRATION + r')\s+(?:time|duration)|(?:time|duration)\s+(?:spent\s+)?'
                          r'(?:on|for|of|during)\s+(?:(?:the|an?)\s+)?(?:[a-z]+\s+)?(?:' + _EM_ADMINISTRATION + r'))\b')
EM_TIME_LINE = rx(r'^[ \t]*(?:total\s+)?time(?:\s+spent)?[ \t]*[:\-][ \t]*(?P<minutes>\d{1,3})\s*(?:minutes|mins?)\b')
# gi3 scope (interpretation 44): the document's own visit marker on a line of its own - a title naming an office, clinic,
# outpatient, follow-up or return note or visit ("Clinic note - return visit", "Hepatology follow-up note", "GI clinic
# follow-up", "Return visit note"), after a field label too ("Visit type: return visit", "Note type | Clinic note"), or a
# heading naming today's visit ("Purpose of today's visit"; the ``heading`` group). The nouns are a closed class: the
# names of an office or outpatient encounter. detect._em_mentions reads a title only in the document's head and refuses
# one whose words name another occurrence ("Next follow-up visit", "Scheduled visit: return visit").
_EM_TITLE_NOUN = (r'(?:office|clinic|outpatient)[ \t]+(?:follow[- ]?up(?:[ \t]+(?:note|visit))?|note|visit(?:[ \t]+note)?'
                  r'|encounter)'
                  r'|(?:follow[- ]?up|return|revisit)[ \t]+(?:(?:office|clinic)[ \t]+)?(?:note|visit(?:[ \t]+note)?|encounter)'
                  r"|(?P<heading>(?:purpose|reason)[ \t]+(?:of|for)[ \t]+(?:today['\u2019]?s|this)[ \t]+visit)")
EM_TITLE = rx(r'^[ \t]*(?:[A-Za-z][A-Za-z /]{0,30}?[ \t]*[:|\u2013-][ \t]*)?'
              r"(?:[A-Za-z][\w&/,()'\u2019.-]*[ \t]+){0,4}?(?P<title>" + _EM_TITLE_NOUN + r')\b'
              r"(?:[ \t]*[-:\u2013\u2014,|][ \t]*[A-Za-z][\w ,/&()'\u2019-]{0,60})?[ \t]*$", FLAGS | re.M)
# gi3 fix round 1 (SCOPE-1, SCOPE-7): the words that, leading a visit title, make it name no office or outpatient visit
# (closed classes). A communication that is no visit - a telephone, phone or audio-only call, an e-mail, a portal
# message (EM_REMOTE: EM_VISIT names video and telehealth visits, never these; "Telephone follow-up note" over "Called
# the patient two days after her colonoscopy"): anywhere in a title line ("Follow-up note - telephone"), and leading a
# visit statement or as its means ("Telephone follow-up visit", "Office visit via telephone"), it names none. A drug or
# blood administration's own occasion - an infusion, an injection, a transfusion ("Infusion clinic note") - and the
# follow-up of another service - "Post-procedure", "Post-op", "Postoperative", "Post-discharge" (a procedure's own
# follow-up, a call or a visit inside its global period, a transitional care visit): a title they lead names no office
# visit by itself, while a statement that names a visit ("Post-op follow-up visit") is read as before.
_EM_REMOTE = r'\b(?:tele-?phon\w*|phone[sd]?|audio[- ]only|e-?mails?|portal)\b'
EM_REMOTE = rx(_EM_REMOTE)
EM_NOT_OFFICE = rx(_EM_REMOTE + r'|\b(?:infus\w*|inject\w*|transfus\w*)\b'
                   r'|\bpost(?:-[a-z]+|[ \t]*(?:op(?:erative)?|procedur(?:e|al))\b)')
# Times that belong to a procedure, never to an E/M visit. gi3 scope (interpretation 43: an interpretation's time never
# counts): a time whose sentence names an interpretation ("Physician time on the date of service for the interpretation:
# 20 minutes." in a manometry report) is that study's; a visit's time that names one is asked, never read.
NOT_EM_TIME = rx(r'\b(?:withdrawal|sedation|procedure\s+time|procedural|intra-?service|fluoroscop\w*|insertion|'
                 r'cecal|anesthesia|recovery|monitoring|interpret\w*)\b')
_LEVEL = r'straightforward|low|moderate|high'
_LEVEL_END = r'(?=[ \t]*(?:[- ]complexity\b|level\b|[:,.;(]|\n|$))'
MDM_LEVEL = rx(r'\b(?:medical\s+decision[- ]making|MDM)\b[^.;\n]{0,60}?\b(?P<level>' + _LEVEL + r')' + _LEVEL_END
               + r'|\b(?P<level2>' + _LEVEL + r')(?:[- ]complexity)?\s+(?:level\s+(?:of\s+)?)?'
               r'(?:medical\s+decision[- ]making|MDM)\b')
# Applied with .match(text, pos) right after an MDM heading, so no '^' anchor.
MDM_BODY_LEVEL = rx(r'[ \t]*:?\s*(?:(?:level|complexity)[ \t]*[:\-][ \t]*)?(?P<level>' + _LEVEL + r')' + _LEVEL_END)

# --- anatomic landmarks (depth order within each tract) ---------------------------

UPPER_LANDMARKS = (
    ('esophagus', 1, rx(r'\besophagus\b|\b(?:upper|middle|mid|lower|distal|proximal)\s+esophagus\b')),
    # gi3 extent (R7): the pyloric outlet is the stomach's, as the pylorus is (h2-04: "Furthest extent: pyloric channel."
    # named no landmark): the pyloric channel, canal, ring or sphincter, the prepyloric antrum or area, the gastric outlet
    ('stomach', 2, rx(r'\bstomach\b|\bgastric\s+(?:body|antrum|fundus|cardia|outlet)\b|\bantrum\b|\bpylorus\b'
                      r'|\bpyloric\s+(?:channel|canal|ring|sphincter)\b|\bprepyloric(?:\s+(?:antrum|area|region))?\b')),
    ('duodenal bulb', 3, rx(r'\bduodenal\s+bulb\b')),
    ('duodenum', 4, rx(r'\bduodenum\b(?!\s*,?\s*(?:second|third|fourth))')),
    ('second part of duodenum', 5, rx(r'\b(?:second|2nd)\s+(?:part|portion)\s+of\s+the\s+duodenum\b|\bD2\b'
                                      r'|\bdescending\s+duodenum\b|\bpost-?bulbar\s+duodenum\b')),
    ('third part of duodenum', 6, rx(r'\b(?:third|3rd)\s+(?:part|portion)\s+of\s+the\s+duodenum\b|\bD3\b')),
    ('fourth part of duodenum', 7, rx(r'\b(?:fourth|4th)\s+(?:part|portion)\s+of\s+the\s+duodenum\b|\bD4\b'
                                      r'|\bligament\s+of\s+treitz\b')),
    ('jejunum', 8, rx(r'\b(?:proximal\s+|mid\s+)?jejunum\b')),
)
LOWER_LANDMARKS = (
    ('rectum', 1, rx(r'\brectum\b')),
    ('sigmoid colon', 2, rx(r'\bsigmoid\s+colon\b|\brectosigmoid\b|\bsigmoid\b(?!oscop)')),
    ('descending colon', 3, rx(r'\bdescending\s+colon\b')),
    ('splenic flexure', 4, rx(r'\bsplenic\s+flexure\b')),
    ('transverse colon', 5, rx(r'\btransverse\s+colon\b')),
    ('hepatic flexure', 6, rx(r'\bhepatic\s+flexure\b')),
    ('ascending colon', 7, rx(r'\bascending\s+colon\b')),
    ('cecum', 8, rx(r'\bcecum\b|\bcecal\s+(?:base|pole|intubation)\b|\bappendiceal\s+orifice\b|\bileocecal\s+valve\b')),
    ('terminal ileum', 9, rx(r'\bterminal\s+ileum\b|\bneo-?terminal\s+ileum\b|\bTI\b')),
)
CECUM_DEPTH = 8
# How a landmark is reached, or not, in its clause.
REACHED_BEFORE = rx(r'\b(?:advanced|passed|inserted|introduced|intubated|examined|inspected|traversed|reached|'
                    r'visualized)\b[^.;]{0,60}?\b(?:to|into|through|as\s+far\s+as|up\s+to|to\s+the\s+level\s+of|'
                    r'beyond|past|at)\s+(?:the\s+)?(?:[\w-]+\s+){0,3}$|\b(?:reached|intubated|entered)\s+(?:the\s+)?$')
REACHED_AFTER = rx(r'^[\s,]*(?:was|were)\s+(?:then\s+|successfully\s+|easily\s+)?(?:reached|intubated|entered|'
                   r'examined|visualized|inspected|identified|seen|normal|unremarkable|photographed)\b'
                   r'|^[\s,]*(?:appeared|appears|looked)\s+normal\b|^\s*intubation\b|^[\s,]*(?:was|were)\s+'
                   r'(?:identified|visualized)\b'
                   # a findings line about the landmark: "Duodenum: normal", "Stomach - unremarkable"
                   r'|^\s*[:\u2013-]\s*(?:normal|unremarkable|examined|visualized|reached|intubated)\b')
NOT_REACHED_BEFORE = rx(r'\b(?:unable\s+to|could\s+not|cannot|failed\s+to|did\s+not)\s+(?:be\s+)?(?:reach|advance|'
                        r'intubate|enter|visualize|examine|pass)\w*\s+(?:\w+\s+){0,3}?(?:to\s+|into\s+)?(?:the\s+)?$'
                        r'|\bshort\s+of\s+(?:the\s+)?$|\bnot\s+(?:reach|reached|examine|examined)\s+(?:the\s+)?$'
                        # "it was not advanced to the", "was never advanced into the", "was not able to be advanced to the"
                        r'|\b(?:was|were|is|are|been)\s+(?:not|never)\s+(?:able\s+to\s+be\s+|successfully\s+|further\s+|'
                        r'safely\s+)?(?:advanced|passed|inserted|introduced|intubated|reached|entered)\s+'
                        r'(?:\w+\s+){0,3}?(?:to\s+|into\s+|as\s+far\s+as\s+)?(?:the\s+)?$'
                        r'|\bnever\s+(?:reached|advanced|passed|entered|intubated)\s+(?:\w+\s+){0,3}?(?:to\s+|into\s+)?'
                        r'(?:the\s+)?$|\bwithout\s+(?:reaching|entering|intubating)\s+(?:the\s+)?$')
NOT_REACHED_AFTER = rx(r'^[\s,]*(?:was|were|could)\s+not\s+(?:be\s+)?(?:reached|intubated|entered|examined|visualized|'
                       r'seen|evaluated|inspected)\b')
REACHED_BEYOND = rx(r'\b(?:beyond|past)\s+(?:the\s+)?(?:[\w-]+\s+){0,2}$')
# A reach whose object is a depth, then the landmark that depth lies in (session 7c8d38da, GI round 2, extent: ho-03's
# "The pediatric colonoscope was advanced to 28 cm from the anal verge in the sigmoid colon"): the landmark is where the
# instrument got to, so it is reached, exactly as "advanced to the sigmoid colon" is. Only straight after the reach verb
# ("advanced to 28 cm ...", "advanced only to 28 cm ..."), so a depth that locates a finding ("a polyp at 28 cm in the
# sigmoid colon") never reads a reach; and only as the endoscope's own reach: an endoscope of any kind or "the
# instrument" (the vocabulary STARTED and detect._P2_INSTRUMENT read a reach by) is the verb's subject, with only
# auxiliaries, "then" and adverbs between them (a closed class: "was", "could only be", "was then carefully"), or its
# object right after it ("advanced the pediatric colonoscope to 28 cm in the sigmoid colon"); so an accessory's depth
# ("A balloon was advanced to 35 cm in the distal esophagus") or a catheter's never says where the endoscope went.
# REACHED_DEPTH_DENIED is its denial ("could not be advanced to 28 cm in the sigmoid colon"), read first as
# NOT_REACHED_BEFORE is, so a denied reach is blocked, never reached. detect._landmarks reads a reach to a depth only
# where no other reach form reads the landmark, and drops it where a deeper landmark is named after it
# (detect._depth_reach_doubted).
_DEPTH_THEN_LANDMARK = (r'(?:to|up\s+to|as\s+far\s+as)\s+(?:approximately\s+|about\s+|~\s*)?\d{1,3}\s*cm\b'
                        r'(?:\s+from\s+(?:the\s+)?(?:anal\s+verge|anus|incisors|teeth|dentate\s+line))?\s*,?\s+'
                        r'(?:in|into|within|at)\s+(?:the\s+)?(?:level\s+of\s+(?:the\s+)?)?(?:[\w-]+\s+){0,2}$')
_DEPTH_INSTRUMENT = r'(?:\w*scope|instrument)'
# GI round 2 fix round (extent, EXT-R6): an adverb that says the advance failed or fell short of where it was going is
# no auxiliary of the reach: "was unsuccessfully advanced to 30 cm in the sigmoid colon", "was partially advanced to 30
# cm". A closed class: the negated adverbs of success, effect, completeness and sufficiency, the adverbs of a futile
# act, and the adverbs of degree that say an act fell short or almost did not happen. Such a reach is held (no reach is
# read, as before the depth form existed), never read as a denial: "unsuccessfully advanced to 30 cm" does not say
# whether 30 cm was reached. It is excluded both between the instrument and the verb and right before the verb of the
# active form ("we unsuccessfully advanced the colonoscope to 30 cm").
_FALLING_SHORT = ('unsuccessfully', 'ineffectively', 'ineffectually', 'unsatisfactorily', 'fruitlessly', 'futilely',
                  'vainly', 'incompletely', 'inadequately', 'insufficiently', 'imperfectly', 'partially', 'partly',
                  'barely', 'hardly', 'scarcely', 'nearly')
_DEPTH_AUXILIARIES = (r'(?:\s+(?:was|were|is|are|be|been|had|has|have|could|can|would|then|further|again|also|still|'
                      r'(?!(?:' + '|'.join(_FALLING_SHORT) + r')\b)\w+ly))*')
_NO_FALLING_SHORT_BEFORE = ''.join(r'(?<!\b' + word + r'\s)' for word in _FALLING_SHORT)
_DEPTH_VERB = r'(?:advanced|passed|inserted|introduced)'
REACHED_DEPTH = rx(r'\b' + _DEPTH_INSTRUMENT + _DEPTH_AUXILIARIES + r'\s+' + _DEPTH_VERB + r'\s+(?:[\w-]+\s+){0,2}?'
                   + _DEPTH_THEN_LANDMARK
                   + r'|' + _NO_FALLING_SHORT_BEFORE + r'\b' + _DEPTH_VERB + r'\s+(?:(?:the|a|an)\s+)?(?:[\w-]+\s+)?'
                   + _DEPTH_INSTRUMENT + r'\s+' + _DEPTH_THEN_LANDMARK)
REACHED_DEPTH_DENIED = rx(r'\b(?:(?:unable\s+to|could\s+not|cannot|can\s*not|failed\s+to|did\s+not)\s+(?:be\s+)?'
                          r'(?:advance|pass|insert|introduce)\w*|(?:was|were|is|are|been)\s+(?:not|never)\s+'
                          r'(?:able\s+to\s+be\s+|successfully\s+|further\s+|safely\s+)?(?:advanced|passed|inserted|'
                          r'introduced)|never\s+(?:advanced|passed))\s+(?:[\w-]+\s+){0,2}?' + _DEPTH_THEN_LANDMARK)
# The depth an extent label's value may open with, right after its landmark ("Extent reached: sigmoid colon at 28 cm",
# "Extent: descending colon (35 cm)", "Extent: sigmoid colon, 28 cm from the anal verge"; session 7c8d38da, GI round 2,
# extent): it says where in that landmark the examination stopped, so it is part of the value (detect._value_words).
# Only where it opens the value: a depth after any other word ("Extent: cecum and TI at 85 cm", "Extent: transverse colon
# at 60 cm and cecum at 85 cm" past its first depth) is read as before, so it still leaves the label unread.
# The blank runs are possessive: with two plain runs around an optional comma or bracket, a run of blanks before no
# depth was tried at every split, quadratic per label (refutation gi2 ops cost: 1,289 labels padded with blanks routed
# 56.8-57.6 s against the installed 44 s and the analyze stage's 60 s). Every match is the same span.
# gi3 extent (R8): the depth may also say how it was measured: "of insertion" ("hepatic flexure, at about 95 cm of
# insertion"), or from, beyond or past a fixed anatomical anchor, a closed class ("Terminal ileum, about 6 cm beyond the
# ileocecal valve": h2-01's table cell). The runs before the anchor are read once too.
EXTENT_VALUE_DEPTH = rx(r'[ \t]*+[,(\[\u2013\u2014-]?[ \t]*+(?:(?:at|to)\s+)?(?:approximately\s+|about\s+|~\s*)?\d{1,3}\s*cm\b'
                        r'(?:\s++(?:of\s++)?insertion\b|\s++(?:from|beyond|past)\s++(?:the\s++)?(?:anal\s+verge|anus|'
                        r'incisors|teeth|dentate\s+line|ileo-?c(?:a)?ecal\s+valve|pylorus|ligament\s+of\s+treitz)\b)?')
CENTIMETERS = rx(r'\b(?:to|at|of)\s+(?:approximately\s+|about\s+|~\s*)?(?P<cm>\d{1,3})\s*cm\b')
# Shorthand extents: an extent label line ("Extent: cecum", "Extent reached: terminal ileum", "The furthest
# extent reached was the cecum", "Depth of insertion: 30 cm"), and "to (the) <landmark | N cm>" straight after
# the service name ("Colonoscopy to cecum", "EGD to D2", "Flexible sigmoidoscopy to 30 cm").
# gi3 extent (R4): the extent-label words are ONE closed class, read by every extent-label reader (the labels here, a
# table's column headers through EXTENT_HEADER, and sections._S2_REPORT_FIELD): a maximality word and a position noun
# ("Deepest point reached", "Furthest landmark", "Maximal insertion", "Most proximal extent"; h2-02's "Deepest point
# reached:" was no label), a position noun and "reached" ("Point reached", "Level reached"), "Insertion depth", and the
# extent and depth forms as before ("Extent", "Furthest extent reached", "Depth of insertion"). Their separator is a
# colon, "=", a dash, "was" or "is", or a table cell's " | " (a two-cell row "Extent | Cecum"). A bare "Reached" is a
# label only before a colon or a cell separator. A verb phrase ("Advanced to:", "Examined to:") is no label of the class,
# and neither is a time ("Insertion time"). The blank runs around the separator are read once (possessive): read with
# plain runs, one label word before a long run of blanks was tried at every split of the run, quadratic per label (at
# 90377ec6f413, "Depth of insertion", 40,000 blanks and "30 cm" in a flexible sigmoidoscopy report routed in 17 s).
_MAXIMAL = r'(?:furthest|farthest|maximal|maximum|deepest|most\s+(?:proximal|distal))'
_REACHED_OF = r'(?:\s+(?:reached|of\s+(?:the\s+)?(?:exam(?:ination)?|insertion|intubation)))'
EXTENT_LABEL_WORDS = (r'(?:(?:' + _MAXIMAL + r'\s+)?(?:extent|depth)' + _REACHED_OF + r'?'
                      r'|' + _MAXIMAL + r'\s+(?:point|landmark|level|insertion)' + _REACHED_OF + r'?'
                      r'|(?:point|landmark|level)\s+reached|insertion\s+(?:depth|extent))')
_EXTENT_LABEL = (r'(?:\b' + EXTENT_LABEL_WORDS + r'\s*+(?:[:=\u2013\u2014-]\s*+|(?<=[ \t])\|[ \t]++|(?<=\s)(?:was|is)\s++)'
                 r'|(?<![\w-])reached[ \t]*+(?::[ \t]*+|(?<=[ \t])\|[ \t]++))'
                 r'(?:to\s++)?(?:the\s++)?(?:approximately\s++|about\s++)?')
# A table column whose header is an extent label of the class ("Furthest point reached", "Extent", "Depth of insertion";
# sections.Layout.columns): the cell a landmark opens is that row's extent label value (detect._extent_column).
EXTENT_HEADER = re.compile(r'[ \t]*(?:(?:the|actual|final)[ \t]+)?(?:' + EXTENT_LABEL_WORDS + r'|reached)[ \t]*', FLAGS)
EXTENT_LABEL_BEFORE = rx(_EXTENT_LABEL + r'$')
EXTENT_CM = rx(_EXTENT_LABEL + r'(?P<cm>\d{1,3})\s*cm\b')
# What may lead an extent label for it to name the extent reached: nothing (the label opens its clause or follows
# a separator), the service's name ("Colonoscopy extent: cecum") or one of these words. Any other word names an
# aim or a plan ("Intended extent: cecum", "Expected extent", "Target depth of insertion: 60 cm"), so the label is
# then no extent read at all (detect._label_lead_plain): a lead this set does not list holds, never releases.
EXTENT_LEAD = frozenset(('the', 'actual', 'final'))
# The only words that may follow the landmark of an extent label's value for it to state the extent reached
# (round 4 routing:9, release:3: 'Extent: cecum (intended).', 'cecum (intended; not reached)', 'cecum was the
# goal'). A closed list, read up to the value's sentence or line end: any other word leaves the extent unread.
# Round 4c declared:11: with the landmark table's own spellings ("cecum and TI", "terminal ileum (TI)", "neo-terminal
# ileum", "cecal base", "cecal pole").
EXTENT_TAIL = frozenset(('reached', 'intubated', 'entered', 'visualized', 'visualised', 'identified', 'confirmed',
                         'seen', 'photographed', 'photodocumented', 'photodocumentation', 'documented',
                         'documentation', 'photo', 'photos', 'image', 'images', 'successfully', 'easily', 'was',
                         'were', 'by', 'the', 'and', 'with', 'of', 'appendiceal', 'orifice', 'ileocecal', 'valve',
                         'terminal', 'ileum', 'cecum', 'caecum', 'ti', 'neo-terminal', 'neoterminal', 'cecal', 'pole',
                         'base'))
SERVICE_TO_GAP = rx(r'\s*(?:\(\s*[A-Z]{2,6}\s*\)\s*)?(?:to|into|through|up\s+to|as\s+far\s+as)\s+(?:the\s+)?'
                    r'(?:level\s+of\s+the\s+)?')
ADVANCED = rx(r'\b(?:advanced|passed|inserted|introduced|examined|reached)\b')

# --- interventions ----------------------------------------------------------------
# (label, pattern, families). An intervention counts only where status_for_span
# reads its own span as performed.

_LUMINAL = ('gi.egd', 'gi.colonoscopy', 'gi.flex_sig')
# "a dilated bile duct" is a finding; only the act of dilating is an intervention.
# A bare "dilated to 11 mm" describes a size (a finding), so it does not count;
# "was dilated (to ...)" and "dilated with/using <device>" do; "was not dilated" denies it.
_DILATION = (r'\bdilat(?:ion|ation)s?\b|\b(?:was|were)\s+(?:(?!not\b|never\b)\w+\s+)?dilated\b'
             r'|(?<!not\s)(?<!never\s)\bdilated\s+(?:with|using)\b')
# ERCP: "dilation of the duct" is anatomy; only dilating a stricture, the papilla,
# the sphincter or an anastomosis (or a sphincteroplasty) is an intervention.
_ERCP_DILATION = (r'\bsphincteroplasty\b'
                  r'|\bdilat(?:ion|ation)\s+of\s+(?:the\s+)?(?:[\w-]+\s+){0,2}?'
                  r'(?:strictures?|papilla|sphincter|ampulla|anastomosis)\b'
                  r'|\b(?:strictures?|papilla|sphincter|ampulla|anastomosis)\s+(?:was|were)\s+'
                  r'(?:(?!not\b|never\b)\w+\s+)?dilated\b')
_LOWER = ('gi.colonoscopy', 'gi.flex_sig')
INTERVENTIONS = (
    ('biopsy', rx(r'\bbiops(?:y|ies|ied)\b'), _LUMINAL),
    # named without its technique; the technique, when named, supersedes it
    ('polypectomy', rx(r'\bpolypectom(?:y|ies)\b'), _LOWER),
    ('cold snare', rx(r'\bcold[- ]snare\b'), _LUMINAL),
    ('hot snare', rx(r'\bhot[- ]snare\b|\bsnare\s+(?:electro)?cautery\b|\belectrocautery\s+snare\b'), _LUMINAL),
    ('cold forceps', rx(r'\bcold\s+forceps\s+polypectomy\b|\b(?:removed|resected|excised)\s+(?:\w+\s+){0,3}?with\s+'
                        r'(?:a\s+|the\s+)?(?:jumbo\s+)?cold\s+forceps\b'), _LOWER),
    ('EMR', rx(r'\bEMR\b|\bendoscopic\s+mucosal\s+resection\b'), _LOWER),
    ('injection/tattoo', rx(r'\btattoo(?:ed|ing)?\b|\binject(?:ed|ion)\b'), _LOWER),
    ('injection', rx(r'\binject(?:ed|ion)\b'), ('gi.egd',)),
    ('clip', rx(r'\b(?:hemo)?clips?\b|\bclipped\b'), _LUMINAL),
    ('APC/ablation', rx(r'\bAPC\b|\bargon\s+plasma\s+coagulation\b|\bablat(?:ion|ed)\b|\bradiofrequency\b'), ('gi.egd',)),
    ('ablation', rx(r'\bAPC\b|\bargon\s+plasma\s+coagulation\b|\bablat(?:ion|ed)\b|\bradiofrequency\b'), _LOWER),
    ('dilation (balloon)', rx(r'\bballoon\s+dilat(?:ion|ation|ed)\b|\b(?:CRE|TTS|through-the-scope)\s+balloon\b'
                              r'|\bdilat(?:ed|ion|ation)\s+(?:\w+\s+){0,6}?(?:with|using)\s+(?:a\s+|an\s+)?'
                              r'(?:[\w-]+\s+){0,3}?balloon\b'), ('gi.egd',)),
    ('dilation (bougie)', rx(r'\bbougie\w*\b|\bsavary\b|\bmaloney\b'), ('gi.egd',)),
    ('dilation', rx(_DILATION), ('gi.egd', 'gi.colonoscopy', 'gi.flex_sig')),
    ('banding', rx(r'\bband\s+ligation\b|\bbanding\b|\bbands?\s+(?:was|were)\s+placed\b|\bvariceal\s+ligation\b'),
     ('gi.egd',)),
    ('foreign body', rx(r'\bforeign\s+bod(?:y|ies)\b|\bfood\s+(?:bolus|impaction)\b'), ('gi.egd',)),
    ('PEG', rx(r'\bPEG\b|\bpercutaneous\s+endoscopic\s+gastrostomy\b'), ('gi.egd',)),
    ('stent', rx(r'\bstents?\b'), ('gi.egd',)),
    ('hemostasis', rx(r'\bhemostasis\s+(?:was\s+)?(?:achieved|obtained|performed)\b|\bcontrol\s+of\s+(?:the\s+)?'
                      r'(?:bleeding|hemorrhage)\b|\b(?:bleeding|hemorrhage|oozing)\s+(?:\w+\s+){0,4}?(?:was\s+|were\s+)?'
                      r'(?:controlled|treated|stopped)\b|\bbipolar\s+(?:probe|cautery|coagulation)\b'
                      r'|\b(?:heater|gold)\s+probe\b|\bthermal\s+coagulation\b'), _LUMINAL),
    ('sphincterotomy', rx(r'\bsphincterotomy\b|\bpapillotomy\b'), ('gi.ercp',)),
    ('stone extraction (balloon)', rx(r'\bballoon\s+(?:sweeps?|extraction|catheter)\b|\bextraction\s+balloon\b'
                                      r'|\b(?:swept|extracted|cleared)\s+(?:\w+\s+){0,6}?(?:with|using)\s+(?:a\s+|an\s+)?'
                                      r'(?:[\w-]+\s+){0,2}?balloon\b'), ('gi.ercp',)),
    ('stone extraction (basket)', rx(r'\b(?:extraction\s+|dormia\s+|retrieval\s+)?basket\b'), ('gi.ercp',)),
    ('stone extraction', rx(r'\bstones?\s+(?:\w+\s+){0,3}?(?:was|were)\s+(?:removed|extracted|cleared|retrieved|swept)\b'
                            r'|\bstone\s+extraction\b|\b(?:removed|extracted|cleared|retrieved)\s+(?:\w+\s+){0,3}?'
                            r'stones?\b'), ('gi.ercp',)),
    ('stent placement', rx(r'\bstents?\s+(?:\w+\s+){0,4}?(?:was|were)\s+(?:placed|deployed|inserted)\b'
                           r'|\b(?:placed|deployed|inserted|placement\s+of)\s+(?:\w+\s+){0,5}?stents?\b'
                           r'|\bstent\s+placement\b'), ('gi.ercp',)),
    ('stent exchange', rx(r'\bstent\s+exchange\b|\bstents?\s+(?:\w+\s+){0,3}?(?:was|were)\s+exchanged\b'
                          r'|\bexchanged\s+(?:\w+\s+){0,3}?stents?\b'), ('gi.ercp',)),
    ('brushings', rx(r'\bbrush(?:ings?|ed)\b|\bcytology\s+brush\b'), ('gi.ercp',)),
    ('dilation', rx(_ERCP_DILATION), ('gi.ercp',)),
    ('pancreatic duct', rx(r'\bpancreatic\s+(?:duct\s+)?(?:stent|sphincterotomy)\b'
                           r'|\bpancreatic\s+duct\s+(?:was\s+)?stented\b'), ('gi.ercp',)),
)
# Labels that a more specific label of the same family makes redundant.
SUPERSEDED_BY = {
    'polypectomy': ('cold snare', 'hot snare', 'cold forceps', 'EMR'),
    'dilation': ('dilation (balloon)', 'dilation (bougie)'),
    'stone extraction': ('stone extraction (balloon)', 'stone extraction (basket)'),
}

# --- ERCP cannulation, EUS sampling and target ------------------------------------

CANNULATION_SUCCESS = rx(r'\b(?:deep|selective|biliary|bile\s+duct|common\s+bile\s+duct)?\s*cannulation\s+'
                         r'(?:of\s+the\s+(?:[\w-]+\s+){0,4}?)?(?:was\s+)?(?:achieved|successful|obtained|accomplished)\b'
                         r'|\bsuccessful(?:ly)?\s+(?:deep\s+|selective\s+|biliary\s+)*cannulat(?:ion|ed)\b'
                         r'|\b(?:was|were)\s+(?:deeply\s+|selectively\s+|successfully\s+|then\s+)*cannulated\b')
CANNULATION_FAILED = rx(r'\b(?:unable\s+to|could\s+not|failed\s+to)\s+(?:be\s+)?(?:deeply\s+|selectively\s+)?'
                        r'cannulat(?:e|ed)\b|\b(?:failed|unsuccessful)\s+(?:attempts?\s+at\s+)?(?:deep\s+|selective\s+|'
                        r'biliary\s+|bile\s+duct\s+)?cannulation\b|\bcannulation\s+(?:\w+\s+){0,5}?(?:was\s+|were\s+)?'
                        r'(?:unsuccessful|not\s+achieved|not\s+possible|failed)\b|\b(?:was|were)\s+not\s+cannulated\b')
EUS_FNA = rx(r'\bfine[- ]needle\s+aspirat(?:ion|es)\b|\bFNA\b')
EUS_FNB = rx(r'\bfine[- ]needle\s+biops(?:y|ies)\b|\bFNB\b|\bcore\s+(?:needle\s+)?biops(?:y|ies)\b')
EUS_TARGETS = (
    ('pancreatic {0} {1}', rx(r'\bpancreatic\s+(?P<a>head|neck|body|tail|uncinate)\s+(?P<b>mass|cyst|lesion|nodule)\b')),
    ('pancreatic {0}', rx(r'\bpancreatic\s+(?P<a>mass|cyst|lesion|nodule)\b')),
    ('pancreas ({0})', rx(r'\b(?P<a>head|neck|body|tail|uncinate\s+process)\s+of\s+the\s+pancreas\b')),
    ('pancreas', rx(r'\bpancreas\b')),
    ('bile duct', rx(r'\b(?:common\s+)?bile\s+duct\b')),
    ('ampulla', rx(r'\bampulla(?:ry)?\b')),
    ('gallbladder', rx(r'\bgallbladder\b')),
    ('subepithelial lesion', rx(r'\bsubepithelial\s+(?:lesion|mass|nodule)\b')),
    ('lymph node', rx(r'\blymph\s+nodes?\b')),
    ('esophagus', rx(r'\besophageal\s+(?:mass|lesion|wall|cancer|tumor)\b')),
    ('stomach', rx(r'\bgastric\s+(?:mass|lesion|wall|cancer|tumor)\b')),
    ('rectum', rx(r'\brectal\s+(?:mass|lesion|wall|cancer|tumor)\b')),
    ('mediastinum', rx(r'\bmediastin(?:um|al)\b')),
)
EUS_TARGET_PHRASE = rx(r'\b(?:EUS|endoscopic\s+ultrasound|endosonography)\b(?:\s+(?:was\s+)?performed)?\s+'
                       r'(?:of|for|to\s+evaluate|for\s+evaluation\s+of|to\s+assess|for\s+staging\s+of)\b')
SAMPLING_NONE = rx(r'\bno\s+(?:tissue\s+)?(?:sampling|FNA|FNB|fine[- ]needle\s+(?:aspiration|biopsy))\b')

# --- colonoscopy intent, preparation and incompleteness ---------------------------

INTENT = rx(r'\b(?P<intent>screening|surveillance|diagnostic)\b')
COLON_WORDS = rx(r'\b(?:colon|colonic|colorectal|rectal|polyps?|adenomas?|adenomatous|colonoscopy|FIT|fecal|stool|'
                 r'cologuard|hematochezia)\b')
PREP_QUALITY = rx(r'\b(?:bowel\s+)?prep(?:aration)?(?:\s+quality)?\s*(?:was|is|:|-)?\s*(?:rated\s+(?:as\s+)?)?'
                  r'(?P<q>excellent|good|adequate|fair|poor|inadequate)\b'
                  r'|\b(?P<q2>excellent|good|adequate|fair|poor|inadequate)\s+(?:bowel\s+)?prep(?:aration)?\b')
BBPS = rx(r'\b(?:Boston\s+Bowel\s+Preparation\s+Scale|BBPS)\b[^.;\n]{0,30}?\b(?P<score>\d{1,2})\b')
INCOMPLETE_REASONS = (
    ('poor bowel preparation', rx(r'\b(?:poor|inadequate|suboptimal)\s+(?:bowel\s+)?prep(?:aration)?\b'
                                  r'|\bprep(?:aration)?\s+(?:was\s+)?(?:poor|inadequate)\b|\b(?:solid|retained)\s+stool\b')),
    ('patient intolerance', rx(r'\bdiscomfort\b|\bintolerance\b|\bdid\s+not\s+tolerate\b|\bpoorly\s+tolerated\b')),
    ('obstruction', rx(r'\bobstruct(?:ion|ing|ed)\b')),
    ('stricture', rx(r'\bstricture\b|\bnarrowing\b')),
    ('looping/angulation', rx(r'\blooping\b|\bangulat(?:ion|ed)\b|\btortuous\b|\bfixed\s+sigmoid\b')),
    ('clinical instability', rx(r'\binstability\b|\bhypotension\b|\bdesaturation\b|\bhypoxi(?:a|c)\b')),
)
_COUNT = r'\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|a|an|single'
_SIZE = r'(?=\s*(?:mm|cm|millimeters?|centimeters?)\b)'
# A count word, never a size ("12 mm polyp" is one polyp, not twelve).
POLYP_COUNT = rx(r'\b(?P<n>' + _COUNT + r')\b(?!' + _SIZE + r')\s+'
                 r'(?:(?!(?:' + _COUNT + r')(?=\s)(?!' + _SIZE + r'))[\w,.-]+\s+){0,6}?polyps?\b')
POLYP_UNCOUNTED = rx(r'\b(?:multiple|several|numerous|few|many|some|various|scattered|innumerable)\s+'
                     r'(?:[\w,-]+\s+){0,3}?polyps\b|\bpolyps\s+too\s+numerous\b')
NUMBER_WORDS = {'a': 1, 'an': 1, 'single': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
                'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}

# --- which procedure a sentence describes ------------------------------------------

INSTRUMENTS = (
    ('gi.colonoscopy', rx(r'\bcolonoscope\b')),
    ('gi.flex_sig', rx(r'\bsigmoidoscope\b')),
    ('gi.egd', rx(r'\bgastroscope\b|\bupper\s+endoscope\b|\benteroscope\b')),
    ('gi.ercp', rx(r'\bduodenoscope\b|\bside[- ]viewing\b|\bcholangiogra\w*\b|\bpancreatogra\w*\b|\bpapilla\b'
                   r'|\bsphincterotom\w*\b|\bbiliary\b|\bbile\s+duct\b')),
    ('gi.eus', rx(r'\bechoendoscope\b|\bendosonograph\w*\b|\bhypoechoic\b|\banechoic\b|\bFN[AB]\b|\bfine[- ]needle\b')),
)

# Where an upper-GI intervention was done (finer than the extent landmarks).
UPPER_LOCATIONS = (
    ('gastroesophageal junction', rx(r'\bgastroesophageal\s+junction\b|\bGE\s+junction\b|\bGEJ\b|\bZ-line\b')),
    ('esophagus', rx(r'\b(?:(?:upper|middle|mid|lower|distal|proximal)\s+)?esophag(?:us|eal)\b')),
    ('gastric antrum', rx(r'\b(?:gastric\s+)?antrum\b|\bantral\b')),
    ('gastric body', rx(r'\bgastric\s+body\b|\bbody\s+of\s+the\s+stomach\b')),
    ('gastric fundus', rx(r'\b(?:gastric\s+)?fundus\b')),
    ('gastric cardia', rx(r'\b(?:gastric\s+)?cardia\b')),
    ('pylorus', rx(r'\bpylor(?:us|ic)\b')),
    ('stomach', rx(r'\bstomach\b|\bgastric\b')),
    ('duodenal bulb', rx(r'\bduodenal\s+bulb\b')),
    ('duodenum', rx(r'\bduoden(?:um|al)\b|\bD2\b')),
)

# "The pancreatic duct was not cannulated" beside a successful biliary cannulation is
# a deliberate choice (pancreatitis precaution), not a failed ERCP.
PANCREATIC_SUBJECT = rx(r'\b(?:pancreatic\s+duct|main\s+pancreatic|PD|pancreatic)\b')
BILIARY_SUBJECT = rx(r'\b(?:common\s+bile\s+duct|bile\s+duct|biliary|CBD|choledoch\w*)\b')
