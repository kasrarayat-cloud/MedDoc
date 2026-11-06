"""Labelled procedure paragraphs: one section fact for routing, the documented-service reader and the admission.

Completion repair, 2026-11-06 (U2, and U12's section fact; HARNESS.md "Completion repair (2026-11-06)"). A procedure
report may write each of its procedures as a paragraph labelled with the service's name, after its Indications line:

    Indications: Food impaction; surveillance after prior adenomas.
    Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. ...
    Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. ...
    Impression: ...

``sections.layout`` opens no section for such a label (a label with text after its colon is content), so the
Indications ran on over both narratives, routing held every performance cue there, read no extent, and the services
reader folded that doubt over its own reading. The layout is the context reader's frozen input for the date of service
(ops/gi4/freeze.py), so it is not changed here. Instead this module computes, once per text, the RELEASED labelled
paragraphs, and from them a derived layout (``clinical_layout``) that every clinical reader reads: routing's analysis,
the checks that read routing's layout, the services reader's section reads, the admission's held-section and
report-section reads. ``sections.layout(text)`` is never changed, and where nothing is released the derived layout IS
``sections.layout(text)`` (the same object), so every other document reads exactly as before.

The earlier attempt (F-SECTIONS L, harness repair 3) changed sections.py itself and was dropped after two refutation
cycles; its counterexamples (tests/fixtures/gi4/completion/corpus.json group A, "F-SECTIONS L" and "F-SECTIONS T")
are the acceptance set of the rules below. A paragraph is released only when ALL of these hold; any doubt keeps the
base reading (the Indications' hold), which is the safe side.

- P1, the document is a procedure report, read from its head (its first lines up to its first section heading with a
  colon; a report title the layout reads as a heading is read here as a title): a title line that is a GI procedure
  report's own title (_PROCEDURE_REPORT_TITLE, an allow-list grammar, so an unknown title word fails closed:
  "Gastroenterology Procedure Report", "Upper Endoscopy Report", "Procedure report (fictional)"), and no head title
  line names another kind of document (a clinic, office, telehealth, consult, anesthesia, pre-operative, orders,
  records, review, copy or draft document: _NOT_A_PROCEDURE_REPORT, with routing's own title-hold words); or, with no
  title line at all, a head made only of fields whose labels are a procedure report's own (_HEAD_FIELDS, an
  allow-list). Either way the document carries no office E/M structure (an E/M heading, an MDM, time or examination
  section, an office, clinic or telehealth visit named: cues.EM_VISIT).
- P2, the label is exactly one GI service's name (sections._service_name_only: "Upper endoscopy", "COLONOSCOPY",
  "Esophagogastroduodenoscopy (EGD)"), the label line starts a sentence of its own (the layout runs it on from no line
  above), and that first sentence narrates the label's scope's own course from the colon on: "[frame,] the|a|an
  [modifier] <instrument> was|were [adverb] introduced|advanced|inserted|passed", the instrument mapped to the label's
  family by the services reader's own mapping (services.INSTRUMENT_FAMILY; a bare "endoscope" names no family). The
  frame and the modifiers are allow-lists of today's procedure steps ("After repositioning,") and instrument kinds
  ("pediatric"): anything else before the instrument ("Previously,", "At the referring hospital,", "(outside)") fails.
- P3, the label's family fits the report: a head title naming families names this one; a procedure line ("Procedure:
  ...", a procedure heading with a colon) naming families names this one, with no other time, place, agent or source on
  it; the family has no second labelled paragraph and no positive section of its own elsewhere (a procedure, findings
  or technique body naming it or its instrument: a second narrative of one family is another occasion); a report with a
  positive section of its own besides the paragraph's declares the family on a procedure line; and the tract fits
  (_tract_misfit): no released paragraph names a site its own family's instrument cannot reach, and no site outside the
  history, plan and indication sections lies beyond every released, declared or titled family ("Upper endoscopy: ..."
  then "Findings: A 9 mm sigmoid colon polyp was removed": nothing in that report is released).
- P4, the containing section is an indication-type section whose heading line carries its own content (an empty heading
  directly introducing the paragraph makes the paragraph that heading's content), or a positive (procedure, findings,
  technique) section, or the paragraph directly follows a paragraph released here in the same section; a paragraph after
  one that is not released is never released.
- N1, no sentence of the paragraph states another time (a date, a year, a month or weekday, a time unit outside a
  future form, a past-time word), another place (outside, referring, a facility noun, a proper name after at/in/from/per),
  another agent (Dr., a person noun, "by" anything but a landmark, per, according to, reportedly) or another source (a
  report, a record, a chart, a copy, documentation); every sentence or clause whose subject is the examination ("This
  examination", "The procedure", a service name; "It" at a sentence's start) says only what an allow-list of today's
  predicates says (normal, complete, well tolerated, performed under sedation, a future form, ...); a later sentence
  naming the examination anywhere else ("The patient had this colonoscopy when she was 50.") holds, unless it says the
  patient tolerated it or that it had no complications; and no other family's service is named in the paragraph outside
  its frame of today's steps (the derived layout would read it as performed too). A future or plan word about a sub-act does not block ("not
  resected today; it will be referred for endoscopic mucosal resection").
- N2, no later sentence that names the paragraph's family, an examination noun or "above" states another time (outside
  a plan section or a future form), place, agent or source ("Note: the colonoscopy above was performed in 2025 and is
  copied for reference."), and the family is named again nowhere after it but in the report's impression, assessment or
  plan sections and other labelled paragraphs ("Note: this colonoscopy belongs to another patient.").
- N3, the containing section's own text before its first labelled paragraph announces nothing (follows, below, as
  follows, attached, copied, a summary ...); names no examination noun or the family with a hold signal; in an
  indication, names no other occasion of the family by routing's own reading (detect.named_as_another_occasion: "She had
  a colonoscopy", "the index colonoscopy", "Her last colonoscopy"; a consent or a discussion of it is none); and does not
  end on a line that introduces what follows (a colon), nor on an unterminated line that may run on into the label (it
  ends on a function word or a determiner's phrase, or states a hold signal: "Surveillance after an outside").

A paragraph runs from its label line to the next line that opens a layout section, another label line ("Word:" with
content: sections._bare_label) or a blank line, whichever comes first (the blank line is stricter than the label rule
alone: a paragraph only ever ends earlier, and what follows it keeps the base reading). The released set is a pure function of the text:
it never reads the service date.

Cost: one pass over the lines; every per-paragraph question is answered by bisection over positions found once per
text (signals, mentions, sentences), so the work is linear in the text whatever the number of labels.
"""
from __future__ import annotations

import bisect
import functools
import re
from dataclasses import dataclass
from typing import Optional

from studio.gi import cues
from studio.gi import sections as gi_sections
from studio.gi.sections import Layout, Section
from studio.types import Span

STRUCTURE_VERSION = 'gi-structure@1'
FLAGS = re.A | re.I

# --- P2: the label line --------------------------------------------------------------------------------------------
LABEL_READ = 100  # a label and its colon lie in a line's first characters (a line is never read further for one)
_LABEL_MARKS = ' \t*_#'


def _label_at(line: str) -> Optional[tuple[str, int, int]]:
    """(the label as written, its start, where the value after its colon starts) when ``line`` opens with a label - at
    most LABEL_READ characters, letters first, emphasis or heading marks around it set aside - a colon and a value of
    its own ("Colonoscopy: The colonoscope ...", "**COLONOSCOPY:** ..."); None otherwise. Read procedurally, so a long
    run of blanks costs its length once."""
    colon = line.find(':', 0, LABEL_READ)
    if colon < 0:
        return None
    lead = len(line) - len(line.lstrip(_LABEL_MARKS))
    label = line[lead:colon].rstrip(_LABEL_MARKS)
    if not label or not label[0].isalpha() or '|' in label:
        return None
    value = colon + 1
    while value < len(line) and line[value] in _LABEL_MARKS:
        value += 1
    if value >= len(line):
        return None
    return label, lead, value
_SERVICE_NAMES = '|'.join(f'(?:{pattern.pattern})' for _, pattern in cues.SERVICE_PATTERNS)
# Today's procedure steps that may open the first sentence before its instrument (an allow-list: anything else fails).
_FRAME = (r'(?:(?:after|following)[ \t\n]++(?:(?:the[ \t\n]++)?(?:patient[ \t\n]++)?repositioning(?:[ \t\n]++(?:of[ \t\n]++)?the[ \t\n]++'
          r'patient)?|(?:completion[ \t\n]++of[ \t\n]++)?(?:the[ \t\n]++)?(?:' + _SERVICE_NAMES + r'))'
          r'|next|then|subsequently|thereafter|afterwards?'
          r'|with[ \t\n]++the[ \t\n]++patient[ \t\n]++in[ \t\n]++the[ \t\n]++(?:left|right)[ \t\n]++lateral(?:[ \t\n]++decubitus)?[ \t\n]++position)'
          r'[ \t\n]*+,[ \t\n]*+')
# Instrument kinds that may stand before the instrument (an allow-list).
_INSTRUMENT_MODIFIER = (r'(?:(?:adult|pediatric|paediatric|standard|slim|ultrathin|ultra-thin|high-definition|hd|'
                        r'variable-stiffness|therapeutic|diagnostic|video|flexible)[ \t\n]++){0,2}')
_COURSE_VERB = r'(?P<verb>introduced|advanced|inserted|passed)'
_COURSE_ADVERB = r'(?:(?:then|carefully|gently|subsequently|easily|successfully|readily)[ \t\n]++)?'

# --- N1, N2, N3: another time, place, agent or source (each a hold signal; any one blocks) ---------------------------
_YEAR = r'\b(?:19|20)\d{2}\b'
_MONTH_NAMES = (r'\b(?:January|February|March|April|June|July|August|September|October|November|December|Jan|Feb|Mar|'
                r'Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b\.?|\bMay\b(?![ \t]++(?:be|have|need|require|also)\b)')
_WEEKDAY = r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b'
_TIME_UNIT = (r'\b(?:days?|weeks?|months?|years?|decades?|fortnights?|visits?|occasions?|sessions?|admissions?|'
              r'encounters?|appointments?|hospitali[sz]ations?|stays?|dates?)\b')
_PAST_WORD = (r'\b(?:previously|previous|prior|earlier|before|beforehand|ago|formerly|former|recently|recent|yesterday|'
              r'last|initially|initial|originally|original|index|remote|historically|historical|already|since|once)\b'
              r'|\b(?:back|by|until|till|since|from)[ \t\n]++then\b|\bthen[ \t]*+[.;!?](?=\s|$)|\bat[ \t\n]++that[ \t\n]++time\b'
              r'|\b(?:at|by)[ \t\n]++(?:the[ \t\n]++)?age[ \t\n]++(?:of[ \t\n]++)?\d{1,3}\b|\b\d{1,3}[ \t\n-]++years?[ \t\n-]++old\b'
              r'|\bas[ \t\n]++an?[ \t\n]++(?:child|teenager|teen|young[ \t\n]++adult|student|baby|infant|adolescent)\b'
              r'|\bwhen[ \t\n]++(?:she|he|they|the[ \t\n]++patient)[ \t\n]++(?:was|were|had|lived|moved|worked|visited|stayed)\b'
              r'|\bin[ \t]++the[ \t]++past\b|\bpast[ \t]++(?:history|procedures?|examinations?|exams?|stud(?:y|ies)|visits?|'
              r'years?|months?|weeks?)\b')
_OTHER_PLACE = (r'\b(?:outside|elsewhere|referring|transferring|sending|outlying|external|offsite|off-site|OSH|abroad|'
                r'overseas)\b'
                r'|\b(?:hospitals?|facilit(?:y|ies)|cent(?:er|re)s?|clinics?|institutions?|institutes?|practices?|'
                r'offices?|departments?|infirmar(?:y|ies)|emergency[ \t]++(?:room|department)|ED|ER)\b')
_AGENT = (r'\b(?:Dr|Drs|Doctor)\b|\bper[ \t]++|\baccording[ \t]++to\b|\breported(?:ly)?\b|\bdocumented[ \t]++by\b'
          r'|\b(?:surgeons?|gastroenterologists?|endoscopists?|physicians?|doctors?|fellows?|residents?|colleagues?|'
          r'providers?|teams?|anesthesiologists?|anaesthetists?|anesthetists?|crnas?|technicians?|nurses?)\b')
_SOURCE = (r'\b(?:reports?|records?|cop(?:y|ies|ied)|pasted|reproduced|duplicat\w*|transcri\w*|scanned|faxed|received|'
           r'attached|enclosed|appended|imported|excerpt\w*|referrals?|summar(?:y|ies|ized|ised)|charts?|files?|'
           r'documented|documentation|examples?|templates?|hypothetical|simulated|illustrative)\b')
# Another place, agent or occasion by its determiner ("at another site", "a different provider", "on another day").
_ANOTHER = (r'\b(?:another|other|different|separate)[ \t\n]++(?:site|location|unit|campus|building|city|state|country|town|'
            r'institution|cent(?:er|re)|hospital|facility|clinic|practice|provider|physician|doctor|surgeon|'
            r'gastroenterologist|endoscopist|team|occasion|day|date|time|visit|encounter|admission|procedure|examination|'
            r'exam|study|patient)s?\b')
_LANDMARK_NAMES = '|'.join(f'(?:{p.pattern})' for _, _, p in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS)
# "by" before a landmark identifies the landmark ("identified by the appendiceal orifice"); any other "by" names an
# agent or a manner, and holds (the safe side).
_BY_AGENT = re.compile(r'\bby[ \t\n]++(?!(?:both[ \t\n]++)?(?:the[ \t\n]++)?(?:' + _LANDMARK_NAMES + r'))', FLAGS)
# A proper name after a place preposition ("At Synthetic Valley Medical Center", "from Mercy"): read with case.
_PROPER_PLACE = re.compile(r'\b(?:[Aa]t|[Ii]n|[Ff]rom|[Pp]er)[ \t\n]++(?:the[ \t\n]++)?[A-Z][a-z]{2,}', re.A)
HOLD_SIGNALS = re.compile('|'.join(f'(?:{p})' for p in (_YEAR, _WEEKDAY, _TIME_UNIT, _PAST_WORD, _OTHER_PLACE,
                                                       _AGENT, _SOURCE, _ANOTHER)), FLAGS)
_MONTH = re.compile(_MONTH_NAMES, re.A)
# The same signals without the time ones (a plan section's or a future form's time is the plan's).
_NOT_TIME_SIGNALS = re.compile('|'.join(f'(?:{p})' for p in (_OTHER_PLACE, _AGENT, _SOURCE, _ANOTHER)), FLAGS)
_TIME_SIGNALS = re.compile('|'.join(f'(?:{p})' for p in (_YEAR, _WEEKDAY, _TIME_UNIT, _PAST_WORD)), FLAGS)
# A time unit in a future form is the plan's ("in 3 years", "repeat in six weeks"), never another occasion's.
_FUTURE_UNIT = re.compile(r'\b(?:in|within|after)[ \t]++(?:about[ \t]++|approximately[ \t]++)?(?:\d{1,3}(?:[ \t]*+-[ \t]*+\d{1,3})?'
                          r'|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a[ \t]++few|few|several)[ \t]++'
                          + _TIME_UNIT, FLAGS)
_FUTURE_CLAUSE = re.compile(r'\b(?:will|shall)\b|\b(?:is|are)[ \t]++(?:to[ \t]++be|planned|scheduled|recommended)\b'
                            r'|\b(?:repeat|return|next|future|follow-?up|surveillance|recommend\w*|plan(?:ned|s)?|'
                            r'schedul\w*)\b', FLAGS)
# N3: how an indication may name a labelled paragraph's family (an allow-list: any other mention holds) - in a sentence
# of consent or discussion ("Risks and benefits of upper endoscopy and colonoscopy were discussed."), qualified by an
# intent ("Screening colonoscopy"), or followed by its reason ("Colonoscopy for anemia", "... to evaluate ...").
_CONSENT_SENTENCE = re.compile(r'\b(?:risks?|benefits?|alternatives?|consent\w*|explained|discussed|informed|agreed)\b',
                               FLAGS)
_INTENT_BEFORE = re.compile(r'\b(?:screening|surveillance|diagnostic|therapeutic|average[ -]risk|high[ -]risk|elective|'
                            r'urgent|emergent|open[ -]access)[ \t\n]*+$', FLAGS)
_REASON_AFTER = re.compile(r'(?:[ \t\n]*+(?:,|and|&|/|plus)[ \t\n]*+(?:(?:an?|the)[ \t\n]++)?(?:' + _SERVICE_NAMES + r'))*'
                           r'[ \t\n]*+(?:,[ \t\n]*+)?(?:for|to[ \t\n]++(?:evaluate|assess|investigate|rule[ \t\n]++out|'
                           r'exclude)|due[ \t\n]++to|because[ \t\n]++of)\b', FLAGS)
_SOURCE_SIGNAL = re.compile(_SOURCE, FLAGS)
# What announces the paragraph that follows as a copy, a summary or another record (N3).
_ANNOUNCE = re.compile(r'\bas[ \t]++follows\b|\bfollows\b|\bbelow\b|\bthe[ \t]++following[ \t]*+:|\bhere(?:after|under|with)\b'
                       r'|\b(?:attached|enclosed|appended|reproduced|copied|pasted|transcribed|excerpted|quoted)\b'
                       r'|\bsummar(?:y|ies|ized|ised)\b', FLAGS)
_DETERMINERS = frozenset(('a', 'an', 'the', 'her', 'his', 'their', 'its', 'this', 'that', 'these', 'those', 'any', 'no',
                          'our', 'my', 'your', 'some', 'each', 'every', 'another'))
# An examination noun: the examination itself, by a generic noun or by any service's name.
_EXAM_NOUN = (r'(?:examinations?|exams?|procedures?|stud(?:y|ies)|tests?|cases?|endoscop(?:y|ies)|' + _SERVICE_NAMES + ')')
_EXAM_SUBJECT = re.compile(r'[ \t\n]*+(?:(?:the|this|that|these|those|today\'?s|said|same|present|current|above|both|each|'
                           r'either|neither|her|his|their|its)[ \t\n]++)?(?:(?:entire|whole|upper|lower|diagnostic|'
                           r'screening|surveillance)[ \t\n]++)?' + _EXAM_NOUN + r'\b(?![ \t\n]*+(?:-|of\b))', FLAGS)
_PRONOUN_SUBJECT = re.compile(r'[ \t\n]*+(?:it|this|that)[ \t\n]++(?=(?:was|were|is|are|had|has|took|occurred|happened|'
                              r'showed|revealed|demonstrated)\b)', FLAGS)
# What an examination subject may say in today's own narrative (an allow-list; any other predicate holds).
_EXAM_PREDICATE_OK = re.compile(
    r'[ \t\n]++(?:(?:was|were|is|are)[ \t\n]++(?:then[ \t\n]++|also[ \t\n]++)?(?:otherwise[ \t\n]++)?(?:normal|unremarkable|'
    r'complete|completed|uncomplicated|well[ -]tolerated|tolerated[ \t\n]++well|successful|satisfactory|adequate|good|fair|'
    r'limited|difficult|technically[ \t\n]++(?:adequate|satisfactory|successful|difficult|challenging)|without[ \t\n]++'
    r'(?:complications?|difficulty|incident))\b'
    r'|(?:was|were)[ \t\n]++(?:then[ \t\n]++)?(?:performed|done|completed)(?:[ \t\n]*+(?:$|[.;,])|[ \t\n]++(?:under[ \t\n]++'
    r'(?:monitored[ \t\n]++anesthesia[ \t\n]++care|mac|moderate[ \t\n]++sedation|conscious[ \t\n]++sedation|deep[ \t\n]++'
    r'sedation|general[ \t\n]++anesthesia|propofol(?:[ \t\n]++sedation)?|sedation)|with[ \t\n]++the[ \t\n]++patient[ \t\n]++'
    r'in[ \t\n]++the[ \t\n]++(?:left|right)[ \t\n]++lateral(?:[ \t\n]++decubitus)?[ \t\n]++position|without[ \t\n]++'
    r'(?:complications?|difficulty|incident))[ \t\n]*+(?:$|[.;]))'
    r'|(?:will|shall)[ \t\n]++be\b|(?:is|are)[ \t\n]++(?:to[ \t\n]++be|planned|scheduled|recommended)\b'
    r'|(?:showed|revealed|demonstrated)\b)', FLAGS)
# An examination named anywhere in a later sentence of the paragraph (its subject, its object): such a sentence may say
# only what the subject allow-list says, or that the patient tolerated it ("The patient tolerated both procedures
# ..."); anything else about the examination ("The patient had this colonoscopy when she was 50.") holds.
_EXAM_MENTION = re.compile(r'\b' + _EXAM_NOUN + r'\b', FLAGS)
_EXAM_TOLERATED = re.compile(r'[ \t\n]*+(?:(?:the[ \t\n]++)?(?:patient|she|he)[ \t\n]++tolerated[ \t\n]++(?:(?:the|both|this|all|each)'
                             r'[ \t\n]++)?' + _EXAM_NOUN + r'\b'
                             r'|there[ \t\n]++(?:were|was)[ \t\n]++no[ \t\n]++(?:(?:immediate|apparent|other)[ \t\n]++)?'
                             r'complications?[ \t\n]++(?:of|from|during|after)[ \t\n]++(?:the|this)[ \t\n]++' + _EXAM_NOUN
                             + r'[ \t\n]*+[.;]?[ \t\n]*+$)', FLAGS)
# A pronoun subject at a sentence's start may also tell the scope's course ("It was advanced to the cecum.").
_PRONOUN_PREDICATE_OK = re.compile(r'(?:was|were)[ \t\n]++(?:then[ \t\n]++)?(?:advanced|withdrawn|passed|introduced|'
                                   r'inserted|reached|intubated|retroflexed)\b', FLAGS)

# --- P1: the document's head ---------------------------------------------------------------------------------------
_TITLE_PREFIX = (r'(?:gastroenterology|gastrointestinal|gi|digestive|endoscopy|endoscopic|outpatient|inpatient|'
                 r'ambulatory|screening|surveillance|diagnostic|therapeutic)')
_TITLE_CORE = (r'(?:procedures?|endoscopy|endoscopic|(?:' + _SERVICE_NAMES + r')(?:[ \t]*+(?:,|and|&|/|with|plus)[ \t]*+(?:'
               + _SERVICE_NAMES + r'))*)')
_PROCEDURE_REPORT_TITLE = re.compile(r'(?:' + _TITLE_PREFIX + r'[ \t]++){0,3}' + _TITLE_CORE
                                     + r'(?:[ \t]++procedures?)?[ \t]++(?:report|note)', FLAGS)
_SAFE_ASIDE = re.compile(r'[ \t]*+\([ \t]*+(?:fictional|synthetic|final)[ \t]*+\)[ \t]*+$', FLAGS)
_NOT_A_PROCEDURE_REPORT = re.compile(
    r'\b(?:clinic|office|telehealth|telemedicine|virtual|video|telephone|phone|consult\w*|an(?:a)?esthe\w*|pre-?op\w*|'
    r'pre-?procedure|post-?op\w*|h[ \t]*+&[ \t]*+p|history|physical|orders?|nursing|nurse|discharge|progress|letters?|'
    r'correspondence|referrals?|records?|outside|external|prior|previous|cop(?:y|ia|ies|ied)|duplicates?|drafts?|'
    r'templates?|addend\w*|requests?|requested|pathology|radiology|imaging|summary|review\w*|education|instructions?|'
    r'consent|booking|scheduling|follow[- ]?up|visit|encounter|admission|emergency|triage|void|error|unsigned|'
    r'preliminary|amended|planned|scheduled|cancel\w*|awaiting|pending)\b', FLAGS)
# The fields a procedure report's head carries (an allow-list: a head with any other field, untitled, fails closed).
_HEAD_FIELDS = frozenset((
    'date of service', 'date of procedure', 'procedure date', 'service date', 'date', 'exam date', 'examination date',
    'patient', 'patient name', 'name', 'mrn', 'medical record number', 'dob', 'date of birth', 'age', 'sex', 'gender',
    'endoscopist', 'proceduralist', 'performing physician', 'performing endoscopist', 'physician', 'attending',
    'attending physician', 'gastroenterologist', 'referring physician', 'referring provider', 'facility', 'location',
    'place of service', 'setting', 'room', 'sedation', 'anesthesia', 'anesthesia type', 'assistant', 'nurse', 'fellow',
    'procedure', 'procedures', 'procedure performed', 'procedures performed'))
_EM_LABELS = frozenset(('chief complaint', 'cc', 'reason for visit', 'history of present illness', 'hpi',
                        'review of systems', 'ros', 'medical decision making', 'medical decision-making', 'mdm',
                        'decision making'))


@dataclass(frozen=True)
class LabelledParagraph:
    """A released labelled procedure paragraph: [start, end) runs from its label line's start to the start of the line
    that ends it; ``label`` is the label as written with its colon; ``family`` the label's routing family."""
    start: int
    end: int
    family: str
    label: Span


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    family: str
    label: Span
    body: int  # where the narrative starts (after the colon)
    section: int  # index of the frozen layout section the label line lies in


def _instrument_family(word: str) -> str:
    from studio.gi import services as gi_services  # local: services is the instrument mapping's owner
    return gi_services._instrument_family(word)


def _instruments_pattern() -> str:
    from studio.gi import services as gi_services
    return gi_services.INSTRUMENTS.pattern


@functools.lru_cache(maxsize=1)
def _course_start() -> re.Pattern:
    """P2's first-sentence shape (built once: the instrument names are the services reader's own)."""
    return re.compile(r'(?P<frame>' + _FRAME + r')?(?:the|a|an)[ \t\n]++' + _INSTRUMENT_MODIFIER + r'(?P<instrument>'
                      + _instruments_pattern() + r')[ \t\n]++(?:was|were)[ \t\n]++' + _COURSE_ADVERB + _COURSE_VERB
                      + r'\b', FLAGS)


def _signals(text: str, start: int, end: int, time: bool = True) -> bool:
    """Whether [start, end) states another time (``time``), place, agent or source (the hold signals above); a time
    unit in a future form, or any time in a future clause, is the plan's and does not count."""
    if _NOT_TIME_SIGNALS.search(text, start, end) or _BY_AGENT.search(text, start, end) \
            or _PROPER_PLACE.search(text, start, end):
        return True
    if not time:
        return False
    from studio.gi import context as gi_context  # local: the date reader's own date mentions (read only)
    if gi_context.find_dates(text[start:end]) or _MONTH.search(text, start, end):
        return True
    future = _FUTURE_CLAUSE.search(text, start, end) is not None
    for m in _TIME_SIGNALS.finditer(text, start, end):
        if future and not re.fullmatch(_PAST_WORD, m.group(0), FLAGS):
            continue  # "it will be referred in 6 weeks": the plan's time
        if not re.fullmatch(_PAST_WORD, m.group(0), FLAGS) and any(
                f.start() <= m.start() < f.end() for f in _FUTURE_UNIT.finditer(text, max(start, m.start() - 40),
                                                                                  min(end, m.end()))):
            continue  # "in 3 years": a future form
        return True
    return False


def _exam_subject_holds(text: str, s: int, e: int, sentence_start: bool) -> bool:
    """Whether the sentence or clause [s, e) has the examination as its subject and says something an allow-list of
    today's predicates does not (N1). A pronoun subject ("It", "This", "That") is read at a sentence's start only."""
    m = _EXAM_SUBJECT.match(text, s, e)
    if m is not None:
        return _EXAM_PREDICATE_OK.match(text, m.end(), e) is None
    if sentence_start:
        p = _PRONOUN_SUBJECT.match(text, s, e)
        if p is not None:
            return (_EXAM_PREDICATE_OK.match(text, p.end() - 1, e) is None
                    and _PRONOUN_PREDICATE_OK.match(text, p.end(), e) is None)
    return False


def _line_index(starts: list[int], pos: int) -> int:
    return bisect.bisect_right(starts, pos) - 1


@dataclass(frozen=True)
class _Head:
    procedure_report: bool
    title_families: frozenset
    body_start: int = 0  # where the head ends: the first line that is neither a title line nor a head field


@functools.lru_cache(maxsize=16)
def _head(text: str) -> _Head:
    """P1 and P3's title families: the document's head is its first lines (at most sections.PROCEDURE_HEAD_LINES
    non-empty ones) up to its first section heading that is not a title line (a report title the layout reads as a
    procedure heading, "Upper Endoscopy Report", has no colon and is read here as a title). Bounded: those lines, each
    at most 200 characters read."""
    lay = gi_sections.layout(text)
    titles, fields, positive, denied, seen = [], [], False, False, 0
    pos, size = 0, len(text)
    while pos < size and seen < gi_sections.PROCEDURE_HEAD_LINES:
        nl = text.find('\n', pos)
        end = size if nl < 0 else nl
        section = lay.section_at(pos)
        if section.heading is not None and section.start == pos and ':' in section.heading.text:
            break  # the body's first heading ("Indications:", "Sedation:", "Procedure:")
        line = text[pos:min(end, pos + 200)].strip().strip('#*_>').strip()
        if line:
            seen += 1
            field = _label_at(line)
            if field is not None and len(field[0]) <= 60:
                fields.append(' '.join(field[0].lower().split()))
            elif line[-1] in '.!?;' or len(line) > 100:
                break  # a sentence: the body has begun
            else:
                titles.append(line)
        if nl < 0:
            pos = size
            break
        pos = nl + 1
    body_start = pos
    from studio.gi import detect  # local: detect imports this module (routing's own title-hold words)
    for line in titles:
        if _NOT_A_PROCEDURE_REPORT.search(line) or detect._GI4_TITLE_HOLD.search(line) \
                or gi_sections.AROUND_PROCEDURE_WORDS.search(line):
            denied = True
        bare = _SAFE_ASIDE.sub('', line)
        bare = re.sub(r'[ \t]++[-–—|:][ \t]++|[ \t]{2,}', ' ', bare).strip()
        if _PROCEDURE_REPORT_TITLE.fullmatch(bare):
            positive = True
    families = frozenset(f for line in titles for f, pattern in cues.SERVICE_PATTERNS if pattern.search(line))
    em = (any(s.kind in ('mdm', 'time', 'exam') or s.label in _EM_LABELS for s in lay.sections)
          or cues.EM_VISIT.search(text) is not None)
    if em or denied:
        return _Head(False, families, body_start)
    if positive:
        return _Head(True, families, body_start)
    untitled = not titles and bool(fields) and all(label in _HEAD_FIELDS for label in fields)
    return _Head(untitled, families, body_start)


def _candidates(text: str, lay: Layout) -> list[_Candidate]:
    """Every label line naming one GI service with narrative after its colon (not a layout heading), with the paragraph
    it opens. One pass over the lines."""
    lines = gi_sections._lines(text)
    section_starts = set(lay.section_starts)
    found: list[tuple[int, str, Span, int]] = []  # (line index, family, label span, body start)
    ends: list[bool] = []  # per line: whether it ends a paragraph running before it
    for i, (ls, le) in enumerate(lines):
        line = text[ls:min(le, ls + LABEL_READ + 200)]  # a label's line is read in its first characters only
        stripped = line.strip()
        label = _label_at(line) if stripped else None
        ends.append(not stripped or ls in section_starts
                    or (label is not None and len(label[0]) <= 60 and gi_sections._bare_label(label[0])))
        if label is None or len(label[0]) > 70 or gi_sections._heading(text, ls, le) is not None:
            continue
        family = gi_sections._service_name_only(label[0].strip())
        if family is None:
            continue
        lead = ls + label[1]
        colon = ls + line.index(':', label[1])
        found.append((i, family, Span(lead, colon + 1, text[lead:colon + 1]), ls + label[2]))
    out = []
    for n, (i, family, label, body) in enumerate(found):
        j = i + 1
        while j < len(lines) and not ends[j]:
            j += 1
        start = lines[i][0]
        end = lines[j][0] if j < len(lines) else len(text)
        index = bisect.bisect_right(lay.section_starts, start) - 1
        out.append(_Candidate(start, end, family, label, body, max(index, 0)))
    return out


@dataclass
class _Index:
    """Positions read once per text, for the per-paragraph questions (bisection only)."""
    sentence_starts: list
    sentences: tuple
    clause_starts: list
    clauses: tuple
    announce: list  # starts of _ANNOUNCE matches
    signalled: dict  # family or '*' -> sorted starts of sentences that name it (or an examination noun) with a signal
    positive_families: dict  # family -> set of indexes of positive layout sections that name it or its instrument


def _index(text: str, lay: Layout) -> _Index:
    sentence_starts = [s for s, _ in lay.sentences]
    clause_starts = [s for s, _ in lay.clauses]
    announce = [m.start() for m in _ANNOUNCE.finditer(text)]
    signalled: dict[str, list[int]] = {}
    mentions = sorted((m.start(), m.end(), family) for family, pattern in cues.SERVICE_PATTERNS
                      for m in pattern.finditer(text))
    nouns = [m.start() for m in re.finditer(r'\b(?:examinations?|exams?|procedures?|stud(?:y|ies)|endoscop(?:y|ies)|'
                                            r'above)\b', text, FLAGS)]
    seen: set = set()
    for pos, family in [(s, f) for s, _, f in mentions] + [(p, '*') for p in nouns]:
        k = bisect.bisect_right(sentence_starts, pos) - 1
        if k < 0 or (k, family) in seen:
            continue
        seen.add((k, family))
        s, e = lay.sentences[k]
        if not s <= pos < e:
            continue
        e = min(e, s + 400)  # a sentence is read in its first 400 characters (bounded work per sentence)
        plan = lay.section_at(s).kind == 'plan'
        if _signals(text, s, e, time=not plan):
            signalled.setdefault(family, []).append(s)
    for family in signalled:
        signalled[family].sort()
    positive_families: dict[str, set] = {}
    for n, (lo, hi) in _positive_bodies(text, lay).items():  # each body read once per family (linear)
        for family, pattern in cues.SERVICE_PATTERNS:
            if pattern.search(text, lo, hi):
                positive_families.setdefault(family, set()).add(n)
        from studio.gi import services as gi_services
        for m in gi_services.INSTRUMENTS.finditer(text, lo, hi):
            named = _instrument_family(m.group(0))
            if named:
                positive_families.setdefault(named, set()).add(n)
    return _Index(sentence_starts, lay.sentences, clause_starts, lay.clauses, announce, signalled, positive_families)


def _positive_bodies(text: str, lay: Layout) -> dict:
    """The report's own positive (procedure, findings, technique) sections, by index, with the range of each that is
    the body's: a section the layout opens at a head title line ("Upper Endoscopy Report") counts only from where the
    head ends, and not at all when nothing but the head lies in it."""
    body = _head(text).body_start
    out = {}
    for n, section in enumerate(lay.sections):
        if section.kind not in gi_sections.POSITIVE_KINDS:
            continue
        lo = max(section.start, body)
        if lo < section.end and text[lo:section.end].strip():
            out[n] = (lo, section.end)
    return out


def _any_between(sorted_starts: list, lo: int, hi: int) -> bool:
    k = bisect.bisect_left(sorted_starts, lo)
    return k < len(sorted_starts) and sorted_starts[k] < hi


def _procedure_lines(text: str, lay: Layout) -> tuple[frozenset, bool]:
    """(the families the report's procedure sections' heading lines name, whether one of those lines names a family with
    another time, place, agent or source on it)."""
    families, doubted = set(), False
    for section in lay.sections:
        if section.kind != 'procedure' or section.heading is None or ':' not in section.heading.text:
            continue  # a report title the layout reads as a procedure heading is the head's (P1, P3's title families)
        line_end = text.find('\n', section.heading.start)
        line_end = len(text) if line_end < 0 else line_end
        lo, hi = section.heading.start, min(line_end, section.heading.start + 400)
        named = {f for f, pattern in cues.SERVICE_PATTERNS if pattern.search(text, lo, hi)}
        if named and _signals(text, lo, hi):
            doubted = True
        families |= named
    return frozenset(families), doubted


def _family_regions(family: str) -> frozenset:
    """The anatomical regions (services.ANATOMY's) a family's instrument reaches: the services reader's own
    FAMILY_REGIONS, and for an EUS and an ERCP the upper tract and the organs each examines (a closed table: a region
    no family reaches holds, the safe side)."""
    from studio.gi import services as gi_services
    if family in gi_services.FAMILY_REGIONS:
        return frozenset(gi_services.FAMILY_REGIONS[family])
    return {'gi.eus': gi_services.UPPER | {'pancreas', 'biliary', 'node', 'liver'},
            'gi.ercp': frozenset(('esophagus', 'stomach', 'duodenum', 'biliary', 'pancreas'))}.get(family, frozenset())


def _regions_in(text: str, lo: int, hi: int) -> set:
    """The regions of the anatomy named in [lo, hi) (services.ANATOMY, first match wins as the reader reads it)."""
    from studio.gi import services as gi_services
    return {region for _, region, _, _ in gi_services._anatomy_in(text, lo, hi)}


def _tract_misfit(text: str, lay: Layout, kept: list, declared: frozenset) -> bool:
    """P3, the tract: whether the report narrates a site no family accounts for, outside its history, plan and
    indication sections - a site in a released paragraph its own family's instrument cannot reach, or a site elsewhere
    (a Findings line, an Impression) that neither a released family, a family declared on a procedure line nor a family
    the title names reaches ("Upper endoscopy: The gastroscope was advanced ..." then "Findings: A 9 mm sigmoid colon
    polyp was removed with a cold snare."). Such a report's labels do not account for its narrative, so nothing in it is
    released. Linear: one anatomy pass over the paragraphs and one over the other sections."""
    reach = set()
    for c in kept:
        own = _family_regions(c.family)
        if _regions_in(text, c.start, c.end) - own:
            return True
        reach |= own
    for family in declared:
        reach |= _family_regions(family)
    starts = [c.start for c in kept]
    for section in lay.sections:
        if section.kind in ('history', 'plan', 'indication') or section.heading is None:
            continue
        pos, i = section.start, max(bisect.bisect_right(starts, section.start) - 1, 0)
        while pos < section.end:  # the section's text outside the released paragraphs, gap by gap
            while i < len(kept) and kept[i].end <= pos:
                i += 1
            if i < len(kept) and kept[i].start <= pos:
                pos = kept[i].end
                continue
            stop = min(section.end, kept[i].start if i < len(kept) else section.end)
            if _regions_in(text, pos, stop) - reach:
                return True
            pos = stop
    return False


def _first_sentence_ok(text: str, c: _Candidate, ix: _Index) -> bool:
    """P2: the label line's own first sentence, from the colon on, narrates the scope's own course with the label's
    family's instrument."""
    k = bisect.bisect_right(ix.sentence_starts, c.body) - 1
    if k < 0:
        return False
    s, e = ix.sentences[k]
    if not s <= c.body < e or s < c.start:
        return False  # the layout runs the label line on from the line above: a sentence's continuation, no label
    m = _course_start().match(text, c.body, e)
    return m is not None and _instrument_family(m.group('instrument')) == c.family


def _paragraph_holds(text: str, c: _Candidate, ix: _Index, frames: tuple = ()) -> bool:
    """N1: another time, place, agent or source anywhere in the paragraph, an examination subject saying what the
    allow-list does not, or another family's service named in it outside its frame of today's steps (the derived layout
    reads the paragraph as the label's procedure section, which would read that service as performed too: "Sigmoidoscopy
    showed diverticula." inside a colonoscopy paragraph). Linear in the paragraph."""
    if _signals(text, c.start, c.end):
        return True
    for family, pattern in cues.SERVICE_PATTERNS:
        if family == c.family:
            continue
        for m in pattern.finditer(text, c.body, c.end):
            if not any(lo <= m.start() < hi for lo, hi in frames):
                return True
    if c.family != 'gi.flex_sig' and cues.FS_ABBREVIATION.search(text, c.body, c.end):
        return True
    lo = bisect.bisect_left(ix.sentence_starts, c.body)
    first = bisect.bisect_right(ix.sentence_starts, c.body) - 1
    for k in range(max(lo, first + 1), len(ix.sentences)):
        s, e = ix.sentences[k]
        if s >= c.end:
            break
        e = min(e, c.end)
        if _exam_subject_holds(text, s, e, sentence_start=True):
            return True
        if _EXAM_MENTION.search(text, s, e) and not _EXAM_TOLERATED.match(text, s, e) \
                and not (_EXAM_SUBJECT.match(text, s, e) and not _exam_subject_holds(text, s, e, sentence_start=True)):
            return True  # the examination named as anything but an allow-listed subject or the tolerated object
    for k in range(bisect.bisect_left(ix.clause_starts, c.body), len(ix.clauses)):
        s, e = ix.clauses[k]
        if s >= c.end:
            break
        if s > c.body and _exam_subject_holds(text, s, min(e, c.end), sentence_start=False):
            return True
    return False


def _announced(text: str, lay: Layout, c: _Candidate, first: _Candidate, ix: _Index) -> bool:
    """N3: the containing section's own text before its first labelled paragraph ([section start, first's start))
    announces what follows, names the family or an examination noun with a hold signal, or ends on an introducing
    line."""
    section = lay.sections[c.section]
    lo, hi = section.start, first.start
    if _any_between(ix.announce, lo, hi):
        return True
    from studio.gi import detect  # local: detect imports this module
    if section.kind == 'indication' and (_SOURCE_SIGNAL.search(text, lo, hi)
                                         or _unlisted_family_mention(text, c.family, lo, hi, ix)):
        return True  # a record, a report, a copy ... named in the indication, or the family named outside the allow-list
    if section.kind == 'indication' and detect.named_as_another_occasion(text, c.family, lo, hi):
        # an indication naming another occasion of the family ("She had a colonoscopy", "the index colonoscopy", "Her
        # last colonoscopy", "underwent a colonoscopy"): its account may be that occasion's. A positive section's
        # procedure line naming the family is the report's declaration (P3 reads its other time, place, agent, source)
        return True
    from studio.gi import detect  # local: detect imports this module
    if _any_between(ix.signalled.get('*', []), lo, hi):
        return True
    for k in range(bisect.bisect_left(ix.signalled.get(c.family, []), lo), len(ix.signalled.get(c.family, []))):
        s = ix.signalled[c.family][k]
        if s >= hi:
            break
        e = ix.sentences[bisect.bisect_right(ix.sentence_starts, s) - 1][1]
        if not detect.past_negation_only(text, s, e):
            return True  # the family named with a hold signal ("prior", a year ...), never as "no prior colonoscopy"
    before = text[lo:hi].rstrip()
    if before.endswith(':'):
        return True  # a line that introduces what follows ("Reason for referral:", "Her 2019 study:")
    line = before[before.rfind('\n') + 1:].strip()
    if line and line[-1] not in '.!?)"\'':
        # an unterminated last line may run on into the label ("Indications: Surveillance after an outside" then
        # "Colonoscopy: ..."): it holds when it ends on a function word or a determiner's phrase, or states a hold
        # signal of its own (sections' closed class of the words a sentence cannot end on)
        words = re.findall(r"[A-Za-z][A-Za-z'/-]*", line)
        last = words[-1].lower() if words else ''
        if last in gi_sections._WRAP_WORDS or last in gi_sections._WRAP_WORDS_LOWER \
                or (len(words) >= 2 and words[-2].lower() in _DETERMINERS) \
                or _signals(line, 0, len(line)):
            return True
    return False


def _unlisted_family_mention(text: str, family: str, lo: int, hi: int, ix: _Index) -> bool:
    """N3: whether the family's name occurs in [lo, hi) other than in a sentence of consent or discussion, qualified by
    an intent, or followed by its reason (the allow-list above). Bounded: each mention's own sentence, at most 400
    characters of it, and 40 characters before it."""
    from studio.gi import detect  # local: detect imports this module
    pattern = dict(cues.SERVICE_PATTERNS)[family]
    for m in pattern.finditer(text, lo, hi):
        k = bisect.bisect_right(ix.sentence_starts, m.start()) - 1
        s, e = ix.sentences[k] if k >= 0 else (lo, hi)
        if _CONSENT_SENTENCE.search(text, s, min(e, s + 400)):
            continue
        if detect.past_negation_only(text, m.start(), m.end()):
            continue  # "no prior colonoscopy": it denies another occasion
        if _INTENT_BEFORE.search(text, max(s, m.start() - 40), m.start()) or _REASON_AFTER.match(text, m.end(), e):
            continue
        return True
    return False


def _referred_back(c: _Candidate, ix: _Index) -> bool:
    """N2: a later sentence naming the family, an examination noun or 'above' with a hold signal."""
    return any(_any_between(ix.signalled.get(key, []), c.end, 1 << 62) for key in (c.family, '*'))


_SUMMARY_KINDS = ('impression', 'assessment', 'plan')


def _stray_mentions(text: str, lay: Layout, candidates: list) -> dict:
    """N2: per family, the sorted starts of the mentions of its name outside every labelled paragraph candidate and
    outside the report's summary sections (an impression, an assessment, a plan restate or plan the report's services):
    a later one names the family again in the report's own text ("Note: this colonoscopy is another patient's."), so
    the paragraph may be another occasion's account. One pass over the mentions, bisection for the candidates."""
    starts = [c.start for c in candidates]
    found: dict[str, list[int]] = {}
    for family, pattern in cues.SERVICE_PATTERNS:
        for m in pattern.finditer(text):
            k = bisect.bisect_right(starts, m.start()) - 1
            if k >= 0 and candidates[k].start <= m.start() < candidates[k].end:
                continue
            if lay.section_at(m.start()).kind in _SUMMARY_KINDS:
                continue
            found.setdefault(family, []).append(m.start())
    for family in found:
        found[family].sort()
    return found


def _frames(text: str, candidates: list, ix: _Index) -> tuple:
    """The spans of the candidates' first-sentence frames of today's steps (P2's allow-list: "After the upper
    endoscopy, the colonoscope ..."): a mention of another family there is today's sequence, never another occasion."""
    spans = []
    for c in candidates:
        k = bisect.bisect_right(ix.sentence_starts, c.body) - 1
        if k < 0:
            continue
        m = _course_start().match(text, c.body, ix.sentences[k][1])
        if m is not None and m.group('frame'):
            spans.append((m.start('frame'), m.end('frame')))
    return tuple(spans)


def _frames_released(text: str, candidates: list, out: list, ix: _Index) -> list:
    """P2, after the decisions: a released paragraph whose first-sentence frame names another family's procedure
    ("After the upper endoscopy, the colonoscope ...") stays released only while that family's own labelled paragraph
    is released too: the frame tells today's sequence only beside today's account of the procedure it names. Repeated
    until nothing changes (each pass can only hold more; at most one pass per candidate)."""
    named = {}
    for n, c in enumerate(candidates):
        k = bisect.bisect_right(ix.sentence_starts, c.body) - 1
        m = _course_start().match(text, c.body, ix.sentences[k][1]) if k >= 0 else None
        if m is not None and m.group('frame'):
            frame = m.group('frame')
            named[n] = {f for f, pattern in cues.SERVICE_PATTERNS if pattern.search(frame)} - {c.family}
    for _ in range(len(candidates)):
        released_families = {c.family for c, (_, why) in zip(candidates, out) if not why}
        changed = False
        for n, families in named.items():
            if not out[n][1] and families - released_families:
                out[n] = (out[n][0], "P2: its frame names a procedure whose own paragraph is not released")
                changed = True
        if not changed:
            break
    return out


def _later_occasion(text: str, c: _Candidate, frames: tuple) -> bool:
    """N2: whether a later mention of the family, anywhere after the paragraph, reads as another occasion of it by
    routing's own reading (detect.named_as_another_occasion: "Impression: No colonoscopy was performed today.", "The
    colonoscopy above was done last year."), a later paragraph's frame of today's steps apart. One reading per mention,
    memoised in the frozen analysis."""
    from studio.gi import detect  # local: detect imports this module
    return detect.named_as_another_occasion(text, c.family, c.end, len(text), skip=frames, doubt=True)


def _heading_has_content(text: str, section: Section) -> bool:
    if section.heading is None:
        return False
    line_end = text.find('\n', section.heading.end)
    line_end = len(text) if line_end < 0 else line_end
    return bool(text[section.heading.end:line_end].strip())


@functools.lru_cache(maxsize=16)
def decisions(text: str) -> tuple[tuple[LabelledParagraph, str], ...]:
    """Every labelled paragraph candidate of the text, in order, with '' when it is released or the first condition
    that holds it ('P1' to 'P4', 'N1' to 'N3', with a word of detail). For the tests and the probes; ``released`` reads
    it."""
    if not isinstance(text, str) or ':' not in text:
        return ()
    lay = gi_sections.layout(text)
    candidates = _candidates(text, lay)
    if not candidates:
        return ()
    head = _head(text)
    if not head.procedure_report:  # P1: every candidate keeps the base reading
        return tuple((LabelledParagraph(c.start, c.end, c.family, c.label), 'P1: not a procedure report')
                     for c in candidates)
    ix = _index(text, lay)
    declared, declared_doubted = _procedure_lines(text, lay)
    per_family: dict[str, int] = {}
    for c in candidates:
        per_family[c.family] = per_family.get(c.family, 0) + 1
    positive = set(_positive_bodies(text, lay))
    stray = _stray_mentions(text, lay, candidates)
    frames = _frames(text, candidates, ix)
    out: list[tuple[LabelledParagraph, str]] = []
    previous: Optional[_Candidate] = None  # the candidate before this one, and whether it was released
    previous_released = False
    first_in_section: dict[int, _Candidate] = {}
    for c in candidates:
        first_in_section.setdefault(c.section, c)
        section = lay.sections[c.section]
        follows = previous is not None and previous.section == c.section and previous.end == c.start
        why = ''
        if not _first_sentence_ok(text, c, ix):
            why = 'P2: the first sentence is not the scope\'s own course'
        elif head.title_families and c.family not in head.title_families:
            why = 'P3: the title names another family'
        elif declared and c.family not in declared:
            why = 'P3: the procedure line names another family'
        elif declared and declared_doubted:
            why = 'P3: the procedure line states another time, place, agent or source'
        elif per_family[c.family] > 1:
            why = 'P3: a second labelled paragraph of the family'
        elif ix.positive_families.get(c.family, set()) - {c.section}:
            why = 'P3: the family has a procedure section of its own'
        elif positive - {c.section} and c.family not in declared:
            why = 'P3: the report has a procedure section of its own that no procedure line declares the family for'
        elif previous is not None and previous.section == c.section and not previous_released:
            why = 'P4: it follows a labelled paragraph that is not released'
        elif section.kind not in gi_sections.POSITIVE_KINDS and not (
                section.kind == 'indication' and (_heading_has_content(text, section) or (follows and previous_released))):
            why = f'P4: it stands in a {section.kind} section' if section.kind != 'indication' \
                else 'P4: an empty indication heading introduces it'
        elif _paragraph_holds(text, c, ix, frames):
            why = 'N1: the paragraph states another time, place, agent or source'
        elif _referred_back(c, ix) or _any_between(stray.get(c.family, []), c.end, 1 << 62) \
                or _later_occasion(text, c, frames):
            why = 'N2: a later sentence refers back to it'
        elif _announced(text, lay, c, first_in_section[c.section], ix):
            why = 'N3: the containing section announces it'
        out.append((LabelledParagraph(c.start, c.end, c.family, c.label), why))
        previous, previous_released = c, not why
    out = _frames_released(text, candidates, out, ix)
    kept = [c for c, (_, why) in zip(candidates, out) if not why]
    if kept and _tract_misfit(text, lay, kept, declared | head.title_families):
        out = [(p, why or 'P3: the report narrates a site no labelled or declared family reaches') for p, why in out]
    return tuple(out)


@functools.lru_cache(maxsize=16)
def released(text: str) -> tuple[LabelledParagraph, ...]:
    """The text's released labelled procedure paragraphs, in order (see the module's docstring for P1-P4, N1-N3)."""
    return tuple(p for p, why in decisions(text) if not why)


def overlay(lay: Layout, paragraphs: tuple) -> Layout:
    """``lay`` with each of ``paragraphs`` read as a procedure section of its own (label: the service's name; heading:
    the label as written), cut out of whatever sections it overlaps; the pieces of a section a paragraph stood in keep
    that section's kind, label and heading. The sentences and clauses are ``lay``'s own. With no paragraphs it is
    ``lay`` itself. Linear in the sections and the paragraphs."""
    if not paragraphs:
        return lay
    cuts = sorted({b for p in paragraphs for b in (p.start, p.end)})
    starts = [p.start for p in paragraphs]
    out: list[Section] = []
    for section in lay.sections:
        lo, hi = bisect.bisect_right(cuts, section.start), bisect.bisect_left(cuts, section.end)
        edges = [section.start] + cuts[lo:hi] + [section.end]
        for a, b in zip(edges, edges[1:]):
            if b <= a:
                continue
            k = bisect.bisect_right(starts, a) - 1
            p = paragraphs[k] if k >= 0 and paragraphs[k].start <= a < paragraphs[k].end else None
            if p is None:
                out.append(section if (a, b) == (section.start, section.end)
                           else Section(section.kind, section.label, section.heading, a, b))
            elif out and out[-1].heading is p.label and out[-1].end == a:
                last = out.pop()  # the paragraph goes on across a section boundary of ``lay``: one section
                out.append(Section('procedure', last.label, p.label, last.start, b))
            else:
                out.append(Section('procedure', gi_sections.normalize_label(p.label.text), p.label, a, b))
    return Layout(lay.text, tuple(out), lay.sentences, lay.clauses, tuple(s.start for s in out))


@functools.lru_cache(maxsize=16)
def clinical_layout(text: str) -> Layout:
    """sections.layout(text) with the text's released labelled paragraphs read as procedure sections of their own
    (overlay). With nothing released it is sections.layout(text) itself."""
    return overlay(gi_sections.layout(text), released(text))


@functools.lru_cache(maxsize=16)
def reader_layout(text: str, original: str) -> Layout:
    """For a reader of a same-length view of ``original`` (the services reader's reflowed text, a soft line break read
    as a space): its own sections.layout(text) with ``original``'s released paragraphs overlaid, so it reads the same
    section fact as routing, which reads ``original``. With nothing released it is sections.layout(text) itself."""
    if original == text or len(original) != len(text):
        return clinical_layout(text)
    return overlay(gi_sections.layout(text), released(original))


def paragraph_at(text: str, pos: int) -> Optional[LabelledParagraph]:
    """The released labelled paragraph holding ``pos``, or None (one bisection)."""
    paragraphs = released(text)
    k = bisect.bisect_right([p.start for p in paragraphs], pos) - 1
    return paragraphs[k] if k >= 0 and paragraphs[k].start <= pos < paragraphs[k].end else None
