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
NEGATED_POST = (
    # "Colonoscopy was not performed", "ERCP not indicated", "EUS has never been performed"
    ('was not performed', rx(r'^[\s,]*(?:(?:was|were|is|are|has\s+been|have\s+been|had\s+been|will\s+be|would\s+be|'
                             r'could\s+be|can\s+be|to\s+be)\s+)?(?:not|never)\s+(?:(?:been|be|yet|further|ever|'
                             r'successfully)\s+){0,2}(?!completed\b)(?:' + _NOT_DONE + r')\b')),
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
NEGATED_SPAN = rx(r'\bno\b(?P<body>(?:(?!\b(?:was|were|is|are|has|have|had|which|that|but|and\s+the)\b)[^;.!?]){0,80}?)'
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
                        r'(?:sedation|anesthesia|anaesthesia|propofol|MAC|analgesia|retroflexion|photo(?:graph)?s?|'
                        r'photodocumentation|irrigation|lavage|chromoendoscopy|narrow[- ]band\s+imaging|NBI|'
                        r'contrast|fluoroscopy|intubation\s+of\s+the\s+(?:terminal\s+)?ileum)\b')

# --- history: the service happened before this encounter ------------------------

HISTORICAL_PRE = (
    ('history of', _pre(r'history\s+of|hx\s+of|h/o|s/p|status\s+post|personal\s+history\s+of',
                        _HIST_FILLER, 3)),
    ('prior', _pre(r'prior|previous|previously|last|most\s+recent|recent|recently|remote|earlier|past|index|outside',
                   _HIST_FILLER, 3)),
)
# "had a colonoscopy" is history unless the clause says today.
HAD_PRE = _pre(r'had|has\s+had|have\s+had', _HIST_FILLER, 3)
HISTORICAL_CLAUSE = (
    ('ago', rx(r'\b(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|several|many|few)\s+'
               r'(?:days?|weeks?|months?|years?)\s+ago\b|\bago\b')),
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
# "aborted" after the scope went in is an incomplete procedure, not a cancellation;
# "before sedation" keeps it a cancellation. An abort that says neither is held as
# uncertain (detect._abort_status), never excluded as cancelled.
STARTED = rx(r'\b(?:was|were)\s+(?:then\s+)?(?:advanced|inserted|introduced|passed|intubated|reached)\b'
             r'|\binsertion\b|\bintubation\s+of\b'
             r'|\b(?:scope|colonoscope|endoscope|gastroscope|sigmoidoscope|duodenoscope|echoendoscope|enteroscope|'
             r'instrument)\s+(?:had\s+|was\s+|then\s+)?(?:reached|advanced|passed|entered|traversed|inserted|introduced)\b'
             r'|\bafter\s+(?:reaching|advancing|passing|entering|traversing|intubating|insertion|intubation)\b'
             r'|\b(?:at|to|of)\s+(?:approximately\s+|about\s+|~\s*)?\d{1,3}\s*cm\b')
BEFORE_START = rx(r'\b(?:before|prior\s+to)\s+(?:the\s+)?(?:sedation|insertion|scope\s+insertion|intubation|'
                  r'start(?:ing)?|the\s+procedure\s+(?:began|started)|procedure\s+start|endoscope\s+insertion)\b')

# --- incomplete: started but not completed as intended ---------------------------

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
    ('terminated', rx(r'\b(?:terminated|discontinued|halted)\b')),
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
UNCERTAIN_POST = (
    ('if needed', rx(r'^[\s,]*(?:\?|if\s+(?:needed|necessary|indicated|required|warranted|appropriate|'
                     r'clinically\s+indicated)\b|as\s+needed\b|vs\.?\s|versus\b)')),
    # "ERCP pending insurance approval", "Colonoscopy: pending"
    ('pending', rx(r'^[\s,]*(?:[:=\u2013-]\s*|\(\s*)?(?:is\s+|are\s+|was\s+|remains\s+|still\s+)*pending\b')),
    ('was discussed', rx(r'^[\s,]*(?:was|were|has\s+been|have\s+been)\s+(?:discussed|explained|reviewed\s+with)\b')),
    ('may be needed', rx(r'^[\s,]*(?:may|might|could)\s+(?:be|become)\s+(?:needed|necessary|required|indicated|'
                         r'considered|performed|helpful|warranted)\b')),
)
# Clause-scope doubt words are few on purpose: "possible" and "may" mostly qualify a
# diagnosis ("biopsies for possible celiac disease"), so they are anchored above.
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

# A title line such as "COLONOSCOPY REPORT" opens a procedure section.
PROCEDURE_TITLE = rx(r'^[\w /&+,()-]{0,60}?\b(?:procedure\s+)?(?:report|note)$')

# --- office E/M documentation ----------------------------------------------------

EM_VISIT = rx(r'\b(?:(?:in-person\s+|outpatient\s+|ambulatory\s+)?(?:office|clinic)\s+(?:visit|consultation|consult|'
              r'encounter)|outpatient\s+(?:visit|consultation|consult|encounter)|(?:telehealth|telemedicine|video|'
              r'virtual|audio-video)\s+(?:visit|encounter|consultation)|new[- ]patient\s+(?:visit|evaluation|'
              r'consultation|consult|encounter)|established[- ]patient\s+(?:visit|encounter)|follow[- ]?up\s+'
              r'(?:office\s+|clinic\s+)?visit|progress\s+note|evaluation\s+and\s+management)\b')
EM_TIME = rx(r'\b(?:total\s+(?:\w+\s+){0,2}?time|time\s+spent|(?:i|we)\s+spent|spent\s+a\s+total\s+of)\b[^.;\n]{0,140}?'
             r'\b(?P<minutes>\d{1,3})\s*(?:minutes|mins?)\b')
EM_TIME_LINE = rx(r'^[ \t]*(?:total\s+)?time(?:\s+spent)?[ \t]*[:\-][ \t]*(?P<minutes>\d{1,3})\s*(?:minutes|mins?)\b')
# Times that belong to a procedure, never to an E/M visit.
NOT_EM_TIME = rx(r'\b(?:withdrawal|sedation|procedure\s+time|procedural|intra-?service|fluoroscop\w*|insertion|'
                 r'cecal|anesthesia|recovery|monitoring)\b')
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
    ('stomach', 2, rx(r'\bstomach\b|\bgastric\s+(?:body|antrum|fundus|cardia)\b|\bantrum\b|\bpylorus\b')),
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
CENTIMETERS = rx(r'\b(?:to|at|of)\s+(?:approximately\s+|about\s+|~\s*)?(?P<cm>\d{1,3})\s*cm\b')
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
