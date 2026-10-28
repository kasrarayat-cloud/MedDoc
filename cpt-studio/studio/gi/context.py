"""Encounter context read from the document: service date, setting, billing
context and new/established patient status. See ARCHITECTURE.md section 5.2.

Only explicit statements count. Different documented values are a conflict
(value None, every statement kept as evidence), never a silent choice. A date
or setting written in a plan or history section, or qualified as previous /
next / scheduled, describes another encounter and is not read. Dated text the
reader does not read as the date, or cannot place, never supplies the date: it
is kept as evidence a member value must agree with.
"""
from __future__ import annotations

import bisect
import functools
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from studio.gi import cues
from studio.gi.sections import Layout, layout
from studio.types import CONTEXT_FACTS, Fact, Span

SETTINGS = ('office', 'hospital_outpatient', 'asc', 'inpatient', 'emergency', 'telehealth')
BILLING_CONTEXTS = ('professional', 'facility')
PATIENT_STATUSES = ('new', 'established')
USER_NOTE = 'Supplied by a workspace member as encounter metadata; not clinical documentation.'
MISSING_NOTES = {
    'service_date': 'No labelled date of service is documented.',
    'setting': 'No place of service or care setting is documented.',
    'billing_context': 'No explicit professional or facility billing statement is documented.',
    'patient_status': 'New or established patient status is not documented.',
}
POS_CODES = {'11': 'office', '22': 'hospital_outpatient', '19': 'hospital_outpatient', '24': 'asc',
             '21': 'inpatient', '23': 'emergency', '02': 'telehealth', '10': 'telehealth'}
NOT_CURRENT_SECTIONS = ('plan', 'history')
CLAUSE_REACH = 300  # cues further away than this do not qualify a statement
# Refutation phase 2, ctxcost:1: each setting phrase ("office visit", "HOPD") is checked as a statement - about 37 cue
# searches over a clause window of up to 600 characters, about 0.45 ms - so 'HOPD ' 70,000 times (350,000 characters,
# under the paste cap) took 30 s: the analyze stage read it within its 60 s, and every member's POST /context (15 s)
# was then refused. A document stating setting phrases more often than this is not read for them: the setting is
# asked, as for a document that states none. A real note states its setting a few times.
SETTING_STATEMENT_LIMIT = 200
TOO_MANY_SETTINGS_NOTE = ('The document states a care setting more than {limit} times, more than this service reads; '
                          'its setting statements were not read, so the setting is asked.')

_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
_MONTH = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?'
          r'|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')
_FULL_DATE = (r'(?P<iy>\d{4})-(?P<im>\d{2})-(?P<id>\d{2})'
              r'|(?P<um>\d{1,2})/(?P<ud>\d{1,2})/(?P<uy>\d{4})'
              r'|(?P<lm>' + _MONTH + r')\.?[ \t]+(?P<ld>\d{1,2})(?:st|nd|rd|th)?,?[ \t]+(?P<ly>\d{4})'
              r'|(?P<dd>\d{1,2})(?:st|nd|rd|th)?(?:[ \t]+|-)(?P<dm>' + _MONTH + r')\.?(?:,?[ \t]+|-)(?P<dy>\d{4})')
FULL_DATE = cues.rx(r'(?<![\w/-])(?:' + _FULL_DATE + r')(?![\w/-])')
MONTH_YEAR = cues.rx(r'(?<![\w/-])(?:(?P<mm>' + _MONTH + r')\.?,?[ \t]+(?P<my>(?:19|20)\d{2})'
                     r'|(?P<nm>\d{1,2})/(?P<ny>(?:19|20)\d{2}))(?![\w/-])')
# A bare year: after a preposition or bracket, or standing alone when no unit follows ("2000 mg").
YEAR = cues.rx(r'(?:\b(?P<lead>in|since|from|during|until|by|circa)[ \t]+|(?P<bracket>\()|(?<![\w/.:-]))(?P<year>(?:19[5-9]|20\d)\d)\b'
               r'(?![/.:-]?\d)(?![ \t]*(?:mg|mcg|g|ml|cc|units?|iu|kcal|mm|cm|kg|lbs?|%|x|hours?|hrs?)\b)')

# A date label may name the time too ("Date/Time of Service", "Visit Date & Time"): the label is the structure, these
# words its vocabulary (refutation round 2, c2:8). Every whitespace run here and in the separator is possessive, so two
# adjacent runs never backtrack into each other (refutation round 2, c2:4: a label, a long run and no date was read in
# time quadratic in the run).
_DATE_TIME = r'(?:[ \t]*+(?:/|&|and)[ \t]*+time\b)?+'
# "DOS" names its time the same way ("DOS/Time: 10/20/2026 09:15"; refutation round 3, sk:7: it kept no evidence, so a
# member's 1998-01-01 became the date and was sent).
_DATE_LABEL = (r'(?:date' + _DATE_TIME + r'[ \t]++of[ \t]++(?:service|procedure|visit|encounter)|DOS' + _DATE_TIME
               + r'|(?:service|procedure|visit|encounter)[ \t]++date' + _DATE_TIME + r')')
# A clock after a title's or a dated line's date ("GI visit - 10/20/2026 09:15", "Date & Time: 10/20/2026 9:15 AM";
# refutation round 3, sk:7). Possessive: an optional run that never backtracks into the line's trailing run.
_CLOCK = r'(?:[ \t]++(?:at[ \t]++)?+\d{1,2}:\d{2}(?::\d{2})?+(?:[ \t]*+[ap]\.?m\.?)?+)?+'
_DATE_LABEL_SEP = r'\b[ \t]*+(?:\([ \t]*+DOS[ \t]*+\)[ \t]*+)?+[:#=\u2013|-]?+[ \t]*+'
SERVICE_DATE = cues.rx(r'(?<![\w/-])(?P<label>' + _DATE_LABEL + r')' + _DATE_LABEL_SEP
                       + r'(?P<date>' + _FULL_DATE + r')(?![\w/-])')
# Date-shaped text this reader does not read as a date (refutation r1, context-3): a weekday before a date, a
# two-digit year, dashes, dots or year-first slashes, "20th of October". As a title's date it is documented date text a
# member value must agree with - never a gap a member value silently fills.
_WEEKDAY = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)\.?'
_FULL_DATE_SHAPE = re.sub(r'\(\?P<\w+>', '(?:', _FULL_DATE)
DATE_SHAPE = (r'(?:' + _WEEKDAY + r',?[ \t]+(?:' + _FULL_DATE_SHAPE + r')'
              r'|\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}'
              r'|\d{1,2}(?:st|nd|rd|th)?[ \t]+of[ \t]+' + _MONTH + r'\.?,?[ \t]+\d{2,4}'
              r'|' + _MONTH + r'\.?[ \t]+\d{1,2}(?:st|nd|rd|th)?,?[ \t]+\d{2}'
              r'|' + _FULL_DATE_SHAPE + r')(?![\w/])')
# A date-of-service label alone. Where SERVICE_DATE reads no date after it, its value is found by a scan
# (_label_value), never by a pattern with optional runs and line breaks (refutation round 2, c2:4: that pattern
# backtracked quadratically, and a 32,226-character paste overran the analyze stage and a member's POST /context).
DATE_LABEL = cues.rx(r'(?<![\w/-])(?P<label>' + _DATE_LABEL + r')\b')
_LABEL_TAIL = cues.rx(r'[ \t]*+(?:\([ \t]*+DOS[ \t]*+\)[ \t]*+)?+(?P<sep>[:#=\u2013|-])?+(?P<gap>[ \t]*+)')
# A value that starts the way a date does ("20-Oct-26", "10 / 20 / 2026", "Tuesday, October 20, 2026").
_VALUE_DATE_START = cues.rx(r'(?:' + _WEEKDAY + r',?[ \t]*+)?(?:' + _MONTH + r'\.?[ \t]*+\d|\d{1,4}[ \t]*+[-/.][ \t]*+'
                            r'(?:\d|' + _MONTH + r')|\d{1,2}(?:st|nd|rd|th)?[ \t]++(?:of[ \t]++)?' + _MONTH + r'\b)')
_DIGIT = re.compile(r'\d')
_FIELD_BREAK = re.compile(r'\t| {2,}|\|')
VALUE_REACH = 60  # characters of a label's value read on its line
GAP_REACH = 400  # characters from a label to a value it heads in a table column or on a later line
# A note's own dated title line ("GI visit - 10/20/2026", "Colonoscopy report: 14 Oct 2026") or its bare header "Date:"
# field, read near the top of the document, never in a plan or history section. A title may carry a field label of its
# own ("Re: GI consultation of 10/20/2026", "Re: Consultation of 10/20/2026"); such a line is a candidate, never the
# document's heading (refutation r1, negtime-14: a letter's "Date:" beside the consultation it names). Possessive runs,
# as above (refutation round 2, c2:4: a title, a long run and no date was read in time quadratic in the run).
_TITLE_WORD = r'(?P<keyword>visit|encounter|consultation|consult|note|report)'
_TITLE_WORDS = r'[A-Za-z][A-Za-z /&,()\-]{0,60}?'
TITLE_DATE = cues.rx(r'[ \t]*+(?:(?P<field>[A-Za-z]{2,12}[ \t]*+:[ \t]*+)(?=[A-Za-z]))?'
                     r'(?:(?P<words>(?(field)(?:' + _TITLE_WORDS + r')??|' + _TITLE_WORDS + r'))\b' + _TITLE_WORD
                     + r'[ \t]*+(?:[-\u2013\u2014:|,]|\bon\b|\bof\b)?+|date' + _DATE_TIME + r'[ \t]*+[:|\u2013-])[ \t]*+'
                     r'(?:' + _FULL_DATE + r'|(?P<unread>' + DATE_SHAPE + r'))' + _CLOCK + r'[ \t]*+$')
# A title whose date stands alone on the next line ("Colonoscopy Report" above "10/20/2026").
TITLE_HEAD = cues.rx(r'[ \t]*+(?P<words>' + _TITLE_WORDS + r')\b' + _TITLE_WORD
                     + r'[ \t]*+[-\u2013\u2014:|,]?+[ \t]*+$')
DATE_LINE = cues.rx(r'[ \t]*+' + DATE_SHAPE + _CLOCK + r'[ \t]*+$')
TITLE_LINES = 12  # non-empty lines from the top in which a dated title is read
TITLE_LINE_CHARS = 200  # a longer line is no title line (rule 1 reads each title line in bounded time)
_HISTORY_WORDS = (('history of', r'history\s+of|hx\s+of|h/o|s/p|status\s+post'),
                  ('prior', r'prior|previous|previously|last|most\s+recent|recent|recently|remote|earlier|past|index'
                            r'|outside'))
_HISTORY_TITLE = tuple((name, cues.rx(r'\b(?:' + words + r')\b')) for name, words in _HISTORY_WORDS)
_DATE_QUALIFIER_WORDS = (r'previous|prior|last|next|planned|scheduled|future|follow-?up|repeat|anticipated'
                         r'|tentative|proposed|requested|rescheduled|upcoming|due')
DATE_QUALIFIER = cues.rx(r'\b(?:' + _DATE_QUALIFIER_WORDS + r')\b')
# The words that make a date another occurrence's: the date qualifiers and the history words the title reader already
# reads ("Outside", "Index"), one vocabulary for labels and titles (refutation r1, negtime-8).
_OTHER_OCCURRENCE = cues.rx(r'\b(?:' + _DATE_QUALIFIER_WORDS + '|' + '|'.join(w for _, w in _HISTORY_WORDS) + r')\b')
# The documents other disciplines write - the services reader's roles (pathology and the laboratory, radiology and its
# imaging, anesthesia, nursing). The rule is structural - a dated title names the document it heads (_title_names) -
# and this is only the vocabulary for "another discipline's document" (refutation r1, negtime-14: a pathology report's
# own date was read as the visit's and sent; round 2, c2:7: "path", "cytopathology", a biopsy or laboratory report). A
# GI service name speaks only for the words it covers ("Endoscopic ultrasound report", but "Colonoscopy pathology
# report").
_OTHER_DOCUMENT = cues.rx(r'\b(?:[a-z]*patholog[a-z]*|path|histolog[a-z]*|[a-z]*cytolog[a-z]*|biops(?:y|ies)'
                          r'|specimens?|lab|laborator(?:y|ies)|radiology|imaging|CT|MRI|x-?ray|ultrasound|sonography'
                          r'|anesthesia|anaesthesia|nursing|nurse)\b')
_NEUTRAL_WORDS = frozenset(('the', 'this', 'a', 'an'))

# Refutation phase 2 (P2DATES): the date sent is read by its SOURCE, never by vocabulary. Four rounds of qualifier words
# and reaches were each refuted by the next paraphrase, so the reader no longer decides what a date means; it decides
# only where a date may come from (ARCHITECTURE 5.2):
# 1. a document date reaches the request only from a date-of-service label's own value, when that value is a date alone
#    (a clock may follow it) and the label's block - its paragraph and the line above it - holds nothing but the
#    document's title, header fields of the closed list below (their values are read: a qualifier word there still
#    holds the date) and date-of-service labels that agree. Anything else in the block makes the date a question;
# 2. a dated title, a "Date:" line, a dated line naming the service or a letter's subject line is evidence only: it can
#    question a labelled date, or be the only dated text (the date is then asked, as on the installed revision);
# 3. a date of birth is no candidate's value and is never read from the evidence a member date must agree with;
# 4. a member date is taken only when it is a date some candidate states as its own value (merge_user_values).
_BIRTH_LABEL = r'(?:D\.?+[ \t]?+O\.?+[ \t]?+B\b\.?+|date[ \t]++of[ \t]++birth|birth[ \t]*+date|born(?:[ \t]++on)?+|b\.)'
# A date with a birth label right before it, in any position or bracket ("DOB: 01/01/1998", "(DOB 01/01/1998)",
# "Date of birth - 01/01/1998", "born on 01/01/1998", "b. 01/01/1998"): read in the few characters before the date.
_BIRTH_BEFORE = cues.rx(r'(?<![\w/.-])' + _BIRTH_LABEL + r'[ \t]*+(?:[:#=\u2013-][ \t]*+)?+(?:\([ \t]*+)?+$')
_BIRTH_REACH = 32
_BIRTH_HEAD = cues.rx(r'(?<![\w/.-])' + _BIRTH_LABEL + r'(?![\w/-])')
# The header fields rule 1 allows beside a date of service: a closed allow-list of LABELS (the patient, a name, the
# record, chart or account number, the date of birth, age, sex, the physician, the location or facility, the referring
# physician; a patient's status or type, a place of service or care setting, the operator, assistant or anesthesia
# provider are those fields too). Their
# values are read for the words of another occurrence and for any date but a date of birth; no other field is a
# header field.
_HEADER_LABEL = (r'(?:patient(?:[ \t]++(?:name|id|number|no\.?+|status|type))?+'
                 r'|(?:full|first|last|given|family|middle)[ \t]++name|name|MRN'
                 r'|(?:(?:medical|patient|synthetic)[ \t]++)?+record(?:[ \t]++(?:number|no\.?+|id))?+'
                 r'|chart(?:[ \t]++(?:number|no\.?+))?+|account(?:[ \t]++(?:number|no\.?+))?+|acct\.?+|age|sex|gender'
                 r'|(?:(?:performing|attending|rendering|treating|primary|assisting)[ \t]++)?+(?:physician|provider'
                 r'|endoscopist|endosonographer|clinician|surgeon|gastroenterologist|operator|proceduralist|assistant'
                 r'|anesthesiologist|anesthetist|anesthesia(?:[ \t]++provider)?+|CRNA)|(?:service[ \t]++)?+location'
                 r'|facility(?:[ \t]++name)?+|site|place[ \t]++of[ \t]++service|POS|(?:care[ \t]++|service[ \t]++)?+setting'
                 r'|referring(?:[ \t]++(?:physician|provider|clinician|doctor))?+|referred[ \t]++by)')
# A field's head on a header line: a date-of-service label, a birth label or a header label, each a whole label.
_FIELD_HEAD = cues.rx(r'(?<![\w/.-])(?:(?P<svc>' + _DATE_LABEL + r')|(?P<birth>' + _BIRTH_LABEL + r')|(?P<hdr>'
                      + _HEADER_LABEL + r'))(?![\w/-])')
_HDR_TAIL = re.compile(r'[ \t]*+(?:(?P<hash>#)[ \t]*+)?+(?P<sep>[:=])?+[ \t]*+')
_BIRTH_TAIL = re.compile(r'[ \t]*+(?P<sep>[:#=\u2013-])?+[ \t]*+')
# A lone date in a date label's field: the date, a clock at most, then nothing but the field's end.
_LONE_DATE = cues.rx(r'(?:' + _FULL_DATE + r')(?![\w/-])(?:[ \t]++(?:at[ \t]++)?+\d{1,2}:\d{2}(?::\d{2})?+'
                     r'(?:[ \t]*+[ap]\.?m\.?)?+)?+[ \t|]*+$')
_VALUE_FIELD = re.compile(r'(?<!\d)[:=]|[:=](?!\d)')  # another field's label inside a value (a clock's colon is none)
_VALUE_DATE = cues.rx(r'(?<![\w/])(?:' + r'\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}|' + _MONTH + r'\.?[ \t]+\d{1,2}(?:st|nd|rd|th)?,?'
                      r'[ \t]+\d{2,4}|\d{1,2}(?:st|nd|rd|th)?[ \t]+(?:of[ \t]+)?' + _MONTH + r'\b)')
_LIST_MARKER = re.compile(r'[ \t]*+(?:[-*>\u2022\u25cf\u25aa\u2013\u2014]|\d{1,3}[.)]|[A-Za-z][.)])[ \t]')

POS = cues.rx(r'(?<![\w/-])(?:place[ \t]++of[ \t]++service|POS)\b[ \t]*+(?:\([ \t]*+POS[ \t]*+\)[ \t]*+)?+'
              r'(?:code[ \t]*+)?+[:#=\u2013-]?+[ \t]*+(?P<code>\d{2})(?![\w/-])')
# Refutation phase 2, ctxcost:0: every whitespace run in POS is possessive. 'POS', a long run of spaces and no code was
# read in time quadratic in the run (two adjacent optional runs, every split tried): a 96,000-character paste overran
# the analyze stage's 60 s, and 48,000 a member's POST /context (15 s).
SETTING_LABEL = cues.rx(r'(?<![\w/-])(?:place[ \t]+of[ \t]+service|site[ \t]+of[ \t]+service|care[ \t]+setting'
                        r'|service[ \t]+setting|service[ \t]+location|setting|location|facility|encounter[ \t]+type'
                        r'|visit[ \t]+type)[ \t]*[:\u2013-][ \t]*(?P<value>[^\n]{1,160})')
# Words read inside a labelled setting value.
SETTING_WORDS = (
    ('telehealth', cues.rx(r'\b(?:telehealth|telemedicine|video|virtual|audio-video|audio-only)\b')),
    ('asc', cues.rx(r'\bambulatory[ \t]+(?:surgery|surgical|endoscopy)[ \t]+(?:center|centre)\b|\bASC\b')),
    ('hospital_outpatient', cues.rx(r'\bhospital[ \t]+outpatient\b|\boutpatient[ \t]+hospital\b'
                                    r'|\bhospital-based[ \t]+outpatient\b|\bHOPD\b')),
    ('inpatient', cues.rx(r'\binpatient\b')),
    ('emergency', cues.rx(r'\bemergency[ \t]+(?:department|room)\b')),
    ('office', cues.rx(r'\boffice\b|\bclinic\b')),
)
# Explicit statements read anywhere outside plan and history sections.
SETTING_PHRASES = (
    ('telehealth', cues.rx(r'\b(?:telehealth|telemedicine|video|virtual|audio-video)\s+(?:visit|encounter|consultation)\b')),
    ('asc', cues.rx(r'\bambulatory\s+(?:surgery|surgical|endoscopy)\s+(?:center|centre)\b')),
    ('hospital_outpatient', cues.rx(r'\bhospital\s+outpatient\s+(?:department|endoscopy|unit|setting)\b'
                                    r'|\boutpatient\s+hospital\b|\bHOPD\b')),
    ('inpatient', cues.rx(r'\binpatient\s+(?:consultation|admission|stay|setting|unit|service)\b')),
    ('emergency', cues.rx(r'\b(?:emergency\s+(?:department|room)\s+(?:visit|encounter|evaluation)|seen\s+in\s+the\s+'
                          r'emergency\s+(?:department|room))\b')),
    ('office', cues.rx(r'\b(?:office|clinic)\s+(?:visit|encounter|consultation)\b|\bseen\s+in\s+(?:the\s+)?'
                       r'(?:office|clinic)\b')),
)
PATIENT_STATUS = cues.rx(r'\bpatient[ \t]+(?:status|type)[ \t]*[:\u2013-][ \t]*(?P<v2>new|established)\b'
                         r'|(?<![\w-])(?P<v>new|established)[ \t-]+patient\b'
                         r'|\b(?P<v3>new)\s+to\s+(?:the|this|our)\s+(?:practice|clinic)\b')
NEGATED_BEFORE = cues.rx(r'\b(?:not|no\s+longer|never)\s+(?:an?\s+|the\s+)?$')
BILLING = cues.rx(r'(?<![\w-])(?:billing(?:[ \t]+(?:context|type))?|claim[ \t]+type|bill[ \t]+type|charge[ \t]+type)'
                  r'[ \t]*[:\u2013-][ \t]*(?P<v>professional|facility)\b'
                  r'|\b(?P<v2>professional)\s+(?:claim|component|services\s+only|billing)\b'
                  r'|\b(?P<v3>facility)\s+(?:claim|billing|component)\b'
                  r'|(?P<p>\bCMS-?[ \t]?1500\b|\b837P\b)|(?P<f>\bUB-?04\b|\b837I\b)')


@dataclass(frozen=True)
class DateMention:
    start: int
    end: int
    value: date  # first day of the month/year for coarser precisions
    precision: str  # day | month | year
    bare: bool = False  # a year standing alone ("Colonoscopy 2019"); also how room numbers look


def _month(name: str) -> int:
    return _MONTHS.index(name[:3].lower()) + 1


def date_from_match(m: re.Match) -> Optional[date]:
    """The calendar date of a FULL_DATE / SERVICE_DATE match; None when invalid."""
    if m.group('iy'):
        parts = (m.group('iy'), m.group('im'), m.group('id'))
    elif m.group('uy'):
        parts = (m.group('uy'), m.group('um'), m.group('ud'))
    elif m.group('ly'):
        parts = (m.group('ly'), _month(m.group('lm')), m.group('ld'))
    else:
        parts = (m.group('dy'), _month(m.group('dm')), m.group('dd'))
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


@functools.lru_cache(maxsize=16)
def find_dates(text: str) -> tuple[DateMention, ...]:
    """Every valid date in the text, coarser forms only where no finer one covers them."""
    found: list[DateMention] = []
    taken: list[tuple[int, int]] = []  # sorted, non-overlapping

    def free(start, end):
        i = bisect.bisect_left(taken, (start, -1))
        return (i == len(taken) or taken[i][0] >= end) and (i == 0 or taken[i - 1][1] <= start)

    for m in FULL_DATE.finditer(text):
        value = date_from_match(m)
        if value:
            found.append(DateMention(m.start(), m.end(), value, 'day'))
        taken.append((m.start(), m.end()))
    for m in MONTH_YEAR.finditer(text):
        month = _month(m.group('mm')) if m.group('mm') else int(m.group('nm'))
        year = int(m.group('my') or m.group('ny'))
        if free(m.start(), m.end()) and 1 <= month <= 12:
            found.append(DateMention(m.start(), m.end(), date(year, month, 1), 'month'))
            bisect.insort(taken, (m.start(), m.end()))
    for m in YEAR.finditer(text):
        if free(m.start('year'), m.end('year')):
            found.append(DateMention(m.start('year'), m.end('year'), date(int(m.group('year')), 1, 1), 'year',
                                     bare=not (m.group('lead') or m.group('bracket'))))
    return tuple(sorted(found, key=lambda d: d.start))


def compare_to_service(mention: DateMention, service: date) -> int:
    """-1 before the service date, 0 same (at the mention's precision), 1 after."""
    if mention.precision == 'year':
        a, b = mention.value.year, service.year
    elif mention.precision == 'month':
        a, b = (mention.value.year, mention.value.month), (service.year, service.month)
    else:
        a, b = mention.value, service
    return (a > b) - (a < b)


def _span(text: str, start: int, end: int) -> Span:
    return Span(start, end, text[start:end])


def _near(text: str, start: int, end: int, reach: int = 80) -> tuple[int, int]:
    """The same line within ``reach`` characters of [start, end), ending on whitespace
    so no word is cut (a regex reads endpos as the end of the text)."""
    lo = max(text.rfind('\n', 0, start) + 1, start - reach)
    line_end = text.find('\n', end)
    line_end = len(text) if line_end < 0 else line_end
    hi = min(line_end, end + reach)
    if hi < line_end:
        space = max(text.rfind(' ', end, hi), text.rfind('\t', end, hi))
        hi = space if space >= 0 else end
    return lo, hi


_NOT_CURRENT_CUES = tuple(p for _, p in cues.PLANNED_CLAUSE + cues.HISTORICAL_CLAUSE + cues.CANCELLED_CLAUSE)


def is_current_statement(text: str, lay: Layout, start: int, end: int) -> bool:
    """False when the statement sits in a plan/history section, or its clause
    carries a planned/historical/cancelled cue or a negation before it."""
    if lay.section_at(start).kind in NOT_CURRENT_SECTIONS:
        return False
    for clause_span in lay.clauses_for(start, end):
        c_start, c_end = lay.window(clause_span, start, end, CLAUSE_REACH)
        clause = text[c_start:c_end]
        if any(p.search(clause) for p in _NOT_CURRENT_CUES):
            return False
        before = text[c_start:start] if c_start <= start else ''
        if any(p.search(before) for _, p in cues.NEGATED_PRE):
            return False
    return True


def _fact(name: str, found: list[tuple[str, Span]]) -> Fact:
    # Overlapping readings of one value are one statement; the longest is kept. Readings are taken longest first, and
    # one is kept unless a reading already kept for its value overlaps it. The kept readings of one value never
    # overlap, so held sorted by start they are sorted by end as well, and the only one that can overlap [start, end)
    # is the last one starting before end: one bisection per reading, never a scan of all of them (round 4,
    # pipeline:3; the scan made 36,000 readings take 80 s). Nothing kept starts inside a reading that is kept, so that
    # bisection is also where the reading goes. Readings are match spans, so start <= end.
    kept: list[tuple[str, Span]] = []
    by_value: dict[str, tuple[list[int], list[int]]] = {}
    for value, span in sorted(found, key=lambda item: item[1].start - item[1].end):
        starts, ends = by_value.setdefault(value, ([], []))
        at = bisect.bisect_left(starts, span.end)
        if at and ends[at - 1] > span.start:
            continue
        starts.insert(at, span.start)
        ends.insert(at, span.end)
        kept.append((value, span))
    found = sorted(kept, key=lambda item: item[1].start)
    values = list(dict.fromkeys(value for value, _ in found))
    evidence = tuple(sorted(dict.fromkeys(span for _, span in found), key=lambda s: (s.start, s.end)))
    if not values:
        if name == 'billing_context':
            return Fact(name, 'not_documented', 'missing', (), MISSING_NOTES[name])
        return Fact(name, None, 'missing', (), MISSING_NOTES[name])
    if len(values) == 1:
        return Fact(name, values[0], 'document', evidence)
    return Fact(name, None, 'conflict', evidence, DOCUMENT_CONFLICT_NOTE + ', '.join(values) + '.')


@dataclass(frozen=True)
class _Candidate:
    """One date candidate the reader considers (refutation round 2, rule A: every one is either the note's own date or
    kept as documented evidence, never dropped with nothing left behind)."""
    span: Span
    value: Optional[str]  # ISO date; None when the text is no calendar date or not read as one
    source: str  # 'label' (a date-of-service label) | 'title' (a dated title or "Date:" line) | 'field' ("Re: ...")
    reading: str  # 'own' | 'unplaced' (it may be the date) | 'aside' (another occurrence's) | 'other' (another document)
    form: str  # 'read' | 'invalid' | 'unread'
    # A table column's value cell, kept beside the label heading it (span): never the cells between them. Every span a
    # candidate keeps holds no date but its own value (refutation round 3, sk:1), so the dates its evidence reads are the
    # dates it states.
    extra: tuple[Span, ...] = ()
    # A "Date:" line with no title word (refutation round 3, sk:6): it names no encounter - a letter's or a document's
    # date - so a dated line naming the service beside it ('line') questions it.
    bare: bool = False
    # Refutation phase 2, rule 1: a date-of-service label whose value is a date alone and whose block holds nothing but
    # the title, header fields and date labels that agree (_Blocks). Only such a label's date is ever the note's own.
    header: bool = False

    @property
    def spans(self) -> tuple[Span, ...]:
        return (self.span,) + self.extra


_LABEL_WORDS = re.compile(r"(?<![A-Za-z'’-])((?:[A-Za-z][A-Za-z'’-]* ){1,4})$")
_PREVIOUS_WORD = re.compile(r"(?<![A-Za-z'’-])([A-Za-z][A-Za-z'’-]*) $")
_WRAPPED_WORDS = re.compile(r"(?<![A-Za-z'’-])((?:[A-Za-z][A-Za-z'’-]* ){0,3}[A-Za-z][A-Za-z'’-]*)[ \t\r]*$")
# Another field's label, a sentence end or a field break between a qualifier and the date. A clock's colon ("8:00") is no
# field label (refutation round 2, c2:1).
_NOT_ATTACHED = re.compile(r'(?<!\d)[:=]|[:=](?!\d)|[.;!?](?:\s|$)|\t| {2,}')
_ROW_BAR = re.compile(r'[ \t]*\|[ \t]*')  # a table row's cell bar keeps the row's words on one item
# A field label a qualifier opens ("Next colonoscopy:", "Last name:"): words that end in a letter or a bracket, then a
# colon that is not a clock's (refutation round 2, c2:1: "scheduled for 8:00 AM" read as a field of its own).
_FIELD_LABEL = re.compile(r"[A-Za-z0-9 '’/()-]{0,40}?[A-Za-z)][ \t]*+[:=](?!\d)")
# A field label naming an occurrence: the date labels' own nouns; a service's name is read with _THIS_SERVICE. The rule
# is the structure (_qualifier_field); this is its vocabulary.
_OCCURRENCE_NOUN = cues.rx(r'\b(?:services?|procedures?|visits?|encounters?|appointments?|exams?|examinations?|dates?'
                           r'|DOS)\b')
# A bracket opened right after a date by a history word qualifies that date ("(outside facility; ...)", "(index EMR of
# ...)"; refutation round 2, c2:6), as a date qualifier there does.
_BRACKET_HISTORY = cues.rx(r'[ \t]*+[(\[][ \t]*+(?:' + '|'.join(w for _, w in _HISTORY_WORDS) + r')\b')
_LEFTOVER_WORD = re.compile(r'[A-Za-z]{2,}')
_THIS_SERVICE = tuple(p for _, p in cues.SERVICE_PATTERNS) + (cues.EM_VISIT, cues.TODAY)
_READING = {'own': 'own', 'unplaced': 'unplaced', 'another': 'aside'}


def _opens_field(text: str, label_start: int, label_end: int) -> bool:
    """Whether the label opens a field of its own where it stands (refutation round 2, c2:2): a label written with a
    capital and lower case ("Date of service", "Procedure date") one space after a word written in lower case ("...
    colon polyps Date of service:", as a flattened header row writes the value of the field before it). The words
    before it are then that field's value, never the label's own - but a qualifier among them still holds the date, as
    one across a field break does (_line_reading; refutation round 3, sk:2). An all-capital label ("DOS") or a
    lower-case one says nothing by its case."""
    label = text[label_start:label_end]
    if not label[:1].isupper() or label.upper() == label:
        return False
    word = _PREVIOUS_WORD.search(text, max(0, label_start - 40), label_start)
    return word is not None and word.group(1)[:1].islower()


def _label_words(text: str, label_start: int, label_end: int) -> tuple[str, int]:
    """The label's own words before it ("Outside" in "Outside procedure date") and where they start: words joined by
    single spaces only, so a field break (two spaces, a tab), punctuation, a digit or the line start ends them - and a
    label that opens a field of its own has none (refutation round 2, c2:2). A label that opens its line in lower case
    continues the line above, as a wrapped line does ("Outside" above "procedure date: ...", c2:6)."""
    if _opens_field(text, label_start, label_end):
        return '', label_start
    newline = text.rfind('\n', max(0, label_start - 200), label_start)  # bounded: a long line costs each label 200
    if newline >= 0 and text[label_start].islower() and not text[newline + 1:label_start].strip():
        m = _WRAPPED_WORDS.search(text, max(0, newline - 60), newline)
        if m is not None:
            return m.group(1), m.start(1)
    lo = max(text.rfind('\n', max(0, label_start - 60), label_start) + 1, label_start - 60, 0)
    m = _LABEL_WORDS.search(text, lo, label_start)
    if m is None:
        return '', label_start
    return m.group(1).strip(), m.start()


def _names_this_service(words: str, phrase: str) -> bool:
    """Whether every word a label carries is part of a name of a service this release codes or of today ("Colonoscopy
    procedure date", "Office visit date", "Today's visit date"): no word is left that could name another occurrence.
    ``phrase`` is ``words`` followed by the label."""
    covered = [(m.start(), m.end()) for pattern in _THIS_SERVICE for m in pattern.finditer(phrase)]
    for w in _LEFTOVER_WORD.finditer(phrase, 0, len(words)):
        if w.group().lower() not in _NEUTRAL_WORDS and not any(s <= w.start() and w.end() <= e for s, e in covered):
            return False
    return True


@functools.lru_cache(maxsize=16)
def _date_starts(text: str) -> tuple[int, ...]:
    """find_dates' starts, once per text: every labelled date bisects them (never a list rebuilt per date)."""
    return tuple(d.start for d in find_dates(text))


def _qualifier_field(text: str, q_start: int, q_end: int, limit: int, has_date) -> Optional[str]:
    """When a qualifier opens a field label of its own before ``limit`` ("Next colonoscopy:", "Last name:"): 'else' when
    that field is about something else - it carries a date of its own, or its label names no occurrence ("Last name",
    "Previous surgeries") - and 'occurrence' when its label names one ("Planned procedure: EGD", "Next procedure:
    Colonoscopy"): it may date what the date label dates. None when it opens no field: the qualifier alone ("Scheduled:
    Yes") or a clock ("scheduled for 8:00 AM"). Refutation round 2, c2:1: a qualifier heading any field was passed over,
    so a planned procedure's date was read as the service date."""
    m = _FIELD_LABEL.match(text, q_end, limit)
    if m is None or '  ' in text[q_end:m.end()]:  # a field break ends the qualifier's words: no label of its own
        return None
    brk = _FIELD_BREAK.search(text, m.end(), min(limit, m.end() + VALUE_REACH))
    if has_date(m.end(), brk.start() if brk else min(limit, m.end() + VALUE_REACH)):
        return 'else'
    label = text[q_start:m.end() - 1]
    if _OCCURRENCE_NOUN.search(label) or any(p.search(label) for p in _THIS_SERVICE):
        return 'occurrence'
    return 'else'


# A field line: a label of at most 40 characters opening its line, then a colon that is not a clock's ("Outside
# colonoscopy:", "Next procedure: Colonoscopy", "Scheduled: Yes"). A title or a sentence is no field.
_LINE_FIELD = re.compile(r"[ \t]*+[A-Za-z][A-Za-z0-9 '’/()&,.-]{0,40}?[ \t]*+:(?!\d)")


def _line_above(text: str, start: int) -> Optional[tuple[int, int]]:
    """The nearest non-blank line above the line ``start`` opens (nothing but blanks before ``start`` on its line),
    across blank lines within GAP_REACH characters: (line start, line end), or None when ``start`` does not open its
    line or no such line is in reach. A non-blank line is the line above for one line at most - the next one, which one
    label at most opens - so a long line costs its length once."""
    ls = text.rfind('\n', max(0, start - VALUE_REACH), start) + 1
    if ls == 0 or text[ls:start].strip():
        return None
    end = ls - 1
    while ls - end <= GAP_REACH:
        line_start = text.rfind('\n', 0, end) + 1
        if text[line_start:end].strip():
            return line_start, end
        if line_start == 0:
            return None
        end = line_start - 1
    return None


def _line_reading(text: str, label_start: int, label_end: int, date_start: int, date_end: int,
                  value: Optional[date], phrase_start: Optional[int] = None) -> str:
    """How the qualifiers on a labelled date's line read it: 'own', 'another' or 'unplaced' (refutation r1,
    negtime-15: a qualifier of another field or another date discarded the real date, and a letter or title date was
    then taken and sent).

    A qualifier that clearly belongs elsewhere is passed over: one opening a field about something else ("Last name:
    Synthetic", "Next colonoscopy: 10/2029") or one with another date of its own nearer to it ("recall due 10/2029").
    One attached to the date - nothing but words, single spaces, commas, hyphens, brackets or a row's cell bars between
    them ("Prior DOS", "Outside colonoscopy | Procedure date | ...", "... (scheduled)", "... (outside facility)") -
    makes it another occurrence's date. Any other - across another field's label, a sentence end or a field break
    ("Visit type: Follow-up", "Planned procedure: EGD    Procedure date: ...") - may or may not be the date's own: the
    date is held as text this service cannot place. Before the label the history words count too ("Outside"), after the
    date the date qualifiers and a bracket a history word opens. Before a label that opens a field of its own (round 2,
    c2:2: "... colon polyps Date of service:") the words are another field's, so a qualifier there is never attached to
    it: it holds the date as one across a field break does (refutation round 3, sk:2: round 2 read nothing there, and
    "Colonoscopy status: scheduled Procedure Date: 11/04/2026" or "Prior colonoscopy: yes Procedure Date: 05/01/2019"
    gave the documented date, which was sent and an act done that day excluded against it).

    Refutation round 3, sk:5 (only the label's own line was read, so an outside or planned date under an undated title
    was the documented date, sent, and an act done that day excluded against it): a label whose phrase opens its line
    (``phrase_start``) reads the field on the nearest line above it (_line_above, _LINE_FIELD; a title or a sentence is
    no field). A field label ending its line heads the lines below it, so a qualifier in it makes the date another
    occurrence's ("Outside colonoscopy:" above "Procedure date: 09/03/2026"); a field with a value may or may not date
    what follows ("Next procedure: Colonoscopy", "Planned procedure: EGD", "Scheduled: Yes"): the date is held. The
    qualifiers passed over there are those passed over on the label's line. After the date the history words count too
    when attached to it ("09/03/2026, outside facility", "(performed at an outside facility)"); one across a field break
    ("Indication: history of polyps") does not place the date. A phrase that wraps onto the next line - it opens in lower
    case - is read on that line too ("11/04/2026," above "scheduled for 8:00 AM."). The scans stop 80 characters either
    side (200 on the line above), so a long line costs each date only its window.

    A heading, a title or a sentence above is read as a field with a value is (a paraphrase of sk:5: "OUTSIDE
    COLONOSCOPY", "Previous procedure", "Next procedure - Colonoscopy" or "Scheduled = yes" above "Procedure date:
    ..." gave the documented date): a qualifier there holds the date - unless it is part of a name of a service this
    release codes ("Follow-up visit" names the visit itself), has a date of its own after it, or opens a field about
    something else. A line wrapping onto the next one may open it with a bracket too ("09/03/2026" above "(outside
    facility)")."""
    lo = max(text.rfind('\n', max(0, label_start - 80), label_start) + 1, label_start - 80, 0)
    opens = _opens_field(text, label_start, label_end)
    hi = text.find('\n', date_end, date_end + 80)
    hi = min(len(text), date_end + 80) if hi < 0 else hi
    if hi < len(text) and text[hi] == '\n':  # a phrase wrapping onto the next line: it opens in lower case or a bracket
        wrap = hi + 1
        while wrap < min(len(text), hi + 81) and text[wrap] in ' \t':
            wrap += 1
        if wrap < len(text) and (text[wrap].islower() or text[wrap] in '(['):
            stop = text.find('\n', wrap, hi + 81)
            hi = min(len(text), hi + 81) if stop < 0 else stop
    dates, starts = find_dates(text), _date_starts(text)

    def other_dates(a: int, b: int) -> list:
        """The dates in [a, b) other than this one (another day than ``value`` when it is known)."""
        return [dates[j] for j in range(bisect.bisect_left(starts, a), bisect.bisect_left(starts, b))
                if not date_start <= dates[j].start < date_end
                and (value is None or compare_to_service(dates[j], value) != 0)]

    def has_date(a: int, b: int) -> bool:
        return bool(other_dates(a, b))

    reading = 'own'
    for q in _OTHER_OCCURRENCE.finditer(text, lo, label_start):
        if other_dates(q.end(), label_start) or _qualifier_field(text, q.start(), q.end(), label_start,
                                                                 has_date) == 'else':
            continue
        if not opens and not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[q.end():label_start])):
            return 'another'
        reading = 'unplaced'
    above = _line_above(text, label_start if phrase_start is None else phrase_start)
    if above is not None:  # refutation round 3, sk:5: the line above
        field = _LINE_FIELD.match(text, *above)
        heads = field is not None and not text[field.end():above[1]].strip()
        window = min(above[1], above[0] + 200)
        names = [(n.start(), n.end()) for p in _THIS_SERVICE for n in p.finditer(text, above[0], min(above[1], window + 60))]
        for q in _OTHER_OCCURRENCE.finditer(text, above[0], window):
            if any(s <= q.start() and q.end() <= e for s, e in names) or other_dates(q.end(), above[1]) \
                    or _qualifier_field(text, q.start(), q.end(), above[1], has_date) == 'else':
                continue
            if heads:
                return 'another'
            reading = 'unplaced'
    bracket = _BRACKET_HISTORY.match(text, date_end, hi)
    if bracket is not None:
        close = text.find(')', bracket.end(), hi)
        if not other_dates(date_end, hi if close < 0 else close):
            return 'another'
    for q in _OTHER_OCCURRENCE.finditer(text, date_end, hi):
        if other_dates(date_end, q.start()):
            continue
        own = other_dates(q.end(), hi)
        if own and own[0].start - q.end() < q.start() - date_end:
            continue
        if _qualifier_field(text, q.start(), q.end(), hi, has_date) == 'else':
            continue
        if not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[date_end:q.start()])):
            return 'another'
        if DATE_QUALIFIER.fullmatch(q.group()):  # a history word across a field break does not place the date
            reading = 'unplaced'
    return reading


def _labelled_kind(text: str, label_start: int, label_end: int, date_start: int, date_end: int,
                   value: Optional[date]) -> tuple[str, int]:
    """('own' | 'another' | 'unplaced', where the label's phrase starts). A label carrying a word of another occurrence
    ("Outside procedure date", "Index procedure date"), or qualified on its line by a word attached to it, is another
    occurrence's date. A label carrying any other word this service cannot place ("Initial visit date", "Referring visit
    date"), or one its line may qualify, is not the plain date-of-service label: its date is never taken by itself
    (refutation r1, negtime-8 and negtime-15). Neither is ever dropped: each is kept as a candidate (_Candidate)."""
    words, start = _label_words(text, label_start, label_end)
    if words and _OTHER_OCCURRENCE.search(words):
        return 'another', start
    reading = _line_reading(text, label_start, label_end, date_start, date_end, value, start)
    if reading == 'another':
        return 'another', start
    if reading == 'unplaced' or (words and not _names_this_service(words, words + ' ' + text[label_start:label_end])):
        return 'unplaced', start
    return 'own', label_start


class _Rows:
    """The table rows the labels of one text read, each found once: a line's cell bars, the row under a line and its
    cells (refutation round 2, c2:8: a label heading a column, "Date of Service | Provider" above "10/20/2026 | ...")."""

    def __init__(self, text: str):
        self.text, self._bars, self._below, self._cells, self._breaks = text, {}, {}, {}, None

    def line(self, pos: int) -> tuple[int, int]:
        """The line holding ``pos``: one index of the text's line breaks, bisected (never a scan per label: many labels
        on one long line would each read it whole)."""
        if self._breaks is None:
            self._breaks = [m.start() for m in re.finditer('\n', self.text)]
        i = bisect.bisect_left(self._breaks, pos)
        return (self._breaks[i - 1] + 1 if i else 0), (self._breaks[i] if i < len(self._breaks) else len(self.text))

    def bars(self, ls: int, le: int) -> list[int]:
        if ls not in self._bars:
            found, at = [], self.text.find('|', ls, le)
            while at >= 0:
                found.append(at)
                at = self.text.find('|', at + 1, le)
            self._bars[ls] = found
        return self._bars[ls]

    def below(self, le: int) -> Optional[tuple[int, int]]:
        """The next non-blank line after the line ending at ``le`` that starts within GAP_REACH characters, past one
        table rule ("| --- | --- |")."""
        if le not in self._below:
            text, pos, found, ruled = self.text, le + 1, None, False
            while pos < min(len(text), le + 1 + GAP_REACH):
                end = text.find('\n', pos)
                end = len(text) if end < 0 else end
                line = text[pos:end]
                if line.strip():
                    if not ruled and '-' in line and not line.strip(' \t\r|:=+-'):
                        ruled, pos = True, end + 1
                        continue
                    found = (pos, end)
                    break
                pos = end + 1
            self._below[le] = found
        return self._below[le]

    def cells(self, rs: int, re_: int) -> list[tuple[int, int]]:
        if rs not in self._cells:
            bars = self.bars(rs, re_)
            edges = [rs - 1] + bars + [re_]
            self._cells[rs] = [(edges[i] + 1, edges[i + 1]) for i in range(len(edges) - 1)]
        return self._cells[rs]


def _strip_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] in ' \t\r':
        start += 1
    while end > start and text[end - 1] in ' \t\r':
        end -= 1
    return start, end


def _field_end(text: str, pos: int, line_end: int) -> int:
    """The end of the value field that starts at ``pos``: a field break, a cell bar, the line's end or VALUE_REACH."""
    limit = min(line_end, pos + VALUE_REACH)
    brk = _FIELD_BREAK.search(text, pos, limit)
    return _strip_span(text, pos, brk.start() if brk else limit)[1]


_BLANKS = re.compile(r'[ \t\r]*+')


def _blank_to(text: str, start: int, end: int) -> bool:
    """Whether [start, end) holds nothing but blanks: a scan of its leading blanks only (never a slice of a long line)."""
    return _BLANKS.match(text, start, end).end() >= end


@functools.lru_cache(maxsize=16)
def _birth_cells(text: str) -> frozenset:
    """Where a date of birth starts whose birth label is not right before it (rule 3, "any row"): the cell under a
    birth label heading a table column ("Patient | DOB | Date of Service" above "Synthetic, Alex | 01/01/1998 |
    10/14/2026"), and the value on the line under a birth label that ends its line ("Date of birth:" above
    "01/01/1998"). One pass over the birth labels; each line's bars and the row under it are read once (_Rows)."""
    found, rows = set(), _Rows(text)
    for m in _BIRTH_HEAD.finditer(text):
        ls, le = rows.line(m.start())
        tail = _BIRTH_TAIL.match(text, m.end(), le).end()
        bars = rows.bars(ls, le)
        if bars:
            col = bisect.bisect_left(bars, m.start())
            cell_start = bars[col - 1] + 1 if col else ls
            cell_end = bars[col] if col < len(bars) else le
            if not (_blank_to(text, cell_start, m.start()) and _blank_to(text, tail, cell_end)):
                continue  # the label is not its cell's only text
            row = rows.below(le)
            cells = rows.cells(*row) if row else []
            if col < len(cells):
                value = _first_value(text, *cells[col], births=False)
                if value is not None:
                    found.add(value[0])
        elif _blank_to(text, tail, le):
            row = rows.below(le)
            if row is not None:
                value = _first_value(text, row[0], min(row[1], row[0] + VALUE_REACH), births=False)
                if value is not None:
                    found.add(value[0])
    return frozenset(found)


def _is_birth(text: str, start: int) -> bool:
    """Whether the date starting at ``start`` is a date of birth (rule 3): its birth label is right before it, in any
    bracket, or heads its table column or the line above it (_birth_cells)."""
    return (_BIRTH_BEFORE.search(text, max(0, start - _BIRTH_REACH), start) is not None
            or start in _birth_cells(text))


def _title_line(text: str, ls: int, le: int) -> bool:
    """Whether a line near the top can be part of the document's title (rule 1): no field (a colon, unless it is a
    dated title's own, "Colonoscopy report: 10/14/2026"), no "Date:" or "Re:" line, no sentence or list item, no date
    but a dated title's own, and no word of another occurrence that is not part of the name of a service this release
    codes ("Office follow-up visit" names the visit itself; "Outside colonoscopy" is no title), no table row's bar. Fail
    closed: a line this cannot place is not the title, so a block holding it is asked."""
    start, end = _strip_span(text, ls, le)
    if (start >= end or end - start > TITLE_LINE_CHARS or text[end - 1] in '.,;!?'
            or _LIST_MARKER.match(text, start, end) or text.find('|', start, end) >= 0):
        return False  # a long line, a sentence, a list item or a table row
    m = TITLE_DATE.match(text, ls, le)
    if m is not None:
        if m.group('field') is not None or not m.group('keyword'):
            return False
    elif text.find(':', start, end) >= 0 or _DIGIT.search(text, start, end):
        return False
    names = [(n.start(), n.end()) for p in _THIS_SERVICE for n in p.finditer(text, start, end)]
    return not any(not any(a <= q.start() and q.end() <= b for a, b in names)
                   for q in _OTHER_OCCURRENCE.finditer(text, start, end))


def _header_line(text: str, ls: int, le: int) -> Optional[tuple]:
    """A header line (rule 1): fields only, each headed by a date-of-service label, a birth label or a header label of
    the closed list (_HEADER_LABEL), the first opening the line - "Patient: Synthetic, Alex    DOB: 01/01/1998    MRN:
    0000", "Date of service: 10/14/2026". Returns the values its date-of-service labels state (an ISO date, or None
    when a label's value is not a lone date: rule 1's "nothing else follows it"), or None when the line is anything
    else: another field, a heading, a sentence, a list item, a header value naming another occurrence, holding another
    field's label or a date that is no date of birth. One scan of the line's heads."""
    start, end = _strip_span(text, ls, le)
    heads = []
    for h in _FIELD_HEAD.finditer(text, start, end):
        kind = h.lastgroup
        if kind == 'hdr':
            tail = _HDR_TAIL.match(text, h.end(), end)
            if tail.group('hash') is None and tail.group('sep') is None:
                continue  # a header word with no separator is a value's word ("Established patient")
        elif kind == 'birth':
            tail = _BIRTH_TAIL.match(text, h.end(), end)
            if tail.group('sep') is None and not _VALUE_DATE_START.match(text, tail.end(), end):
                continue
        else:
            tail = _LABEL_TAIL.match(text, h.end(), end)
        heads.append((kind, h.start(), tail.end()))
    if not heads or heads[0][1] != start:
        return None
    values = []
    for i, (kind, _, value_start) in enumerate(heads):
        value_end = heads[i + 1][1] if i + 1 < len(heads) else end
        if kind == 'svc':
            lone = _LONE_DATE.match(text, value_start, value_end)
            values.append(date_from_match(lone).isoformat() if lone and date_from_match(lone) else None)
        elif kind == 'hdr':
            if (_OTHER_OCCURRENCE.search(text, value_start, value_end) or _VALUE_FIELD.search(text, value_start, value_end)
                    or _VALUE_DATE.search(text, value_start, value_end)):
                return None
    return tuple(values)


class _Blocks:
    """Rule 1's header of one text, read once from the top: the document's title (its first non-blank lines that
    _title_line reads as title, at most TITLE_LINES of them), then header lines (_header_line), blank lines between;
    the header ends at the first other line. A date-of-service label's date is the note's own only when the label's
    whole paragraph (its contiguous non-blank lines) lies in that header and every date label from the top to the
    paragraph's end states that one date alone. This is the block of rule 1 - the label's paragraph and the line above
    it - read up to the title: a heading two paragraphs above ("Outside colonoscopy:", a blank line, "Patient: ...", a
    blank line, "Procedure date: ...") holds the date as one on the line above does. Linear: each line is read once."""

    def __init__(self, text: str):
        lines, pos = [], 0
        while pos <= len(text):
            end = text.find('\n', pos)
            end = len(text) if end < 0 else end
            lines.append((pos, end))
            pos = end + 1
        self.starts = [ls for ls, _ in lines]
        blank = [_blank_to(text, ls, le) for ls, le in lines]
        count = len(lines)
        self.last = [0] * count  # each line's paragraph's last line (one pass from the end)
        for i in range(count - 1, -1, -1):
            self.last[i] = self.last[i + 1] if i + 1 < count and not blank[i] and not blank[i + 1] else i
        self.end, self.bad, self.value, titles, title = count, count, None, 0, True
        stated = False
        for i, (ls, le) in enumerate(lines):
            if blank[i]:
                continue
            if title and titles < TITLE_LINES and _title_line(text, ls, le):
                titles += 1
                continue
            title = False
            got = _header_line(text, ls, le)
            if got is None:
                self.end = i
                break
            for value in got:
                if not stated:
                    stated, self.value = True, value
                if (value is None or value != self.value) and self.bad == count:
                    self.bad = i

    def own(self, pos: int, value: Optional[str]) -> bool:
        """Whether the date-of-service label at ``pos`` stating ``value`` alone is the note's own (rule 1)."""
        last = self.last[bisect.bisect_right(self.starts, pos) - 1]
        return value is not None and value == self.value and last < self.end and last < self.bad


# The value a date label states: the first date-shaped run of its value field - a weekday, then at most three date
# parts (digits with an ordinal, or a month name) joined by a separator, "of" or a space ("10/14/26", "20-Oct-26",
# "Tuesday, October 20, 2026"). The rest of the field is not the label's value (refutation round 3, sk:1: the field of
# "DOS: 10/14/26 DOB: 01/01/1998" ran on over the date of birth, so a member's 1998-01-01 agreed with the label's
# evidence and was sent). Linear: possessive runs, at most three parts.
_DATE_PART = r'(?:\d{1,4}(?:st|nd|rd|th)?|' + _MONTH + r'\.?)(?![A-Za-z0-9])'
_VALUE_TOKEN = cues.rx(r'(?<![A-Za-z0-9])(?:' + _WEEKDAY + r',?[ \t]*+)?' + _DATE_PART
                       + r'(?:[ \t]*+(?:[-/.,–]|of\b)?+[ \t]*+' + _DATE_PART + r'){0,2}')
_GLUED = re.compile(r'[\w/-]')
_NON_SPACE = re.compile(r'\S*')


def _first_value(text: str, start: int, end: int, births: bool = True) -> Optional[tuple[int, int]]:
    """The first date-shaped run in [start, end) that carries a digit (_VALUE_TOKEN), or None; one glued to more of its
    kind ("10/14/2026-10/15/2026") runs on to the next space, so a cut never makes a date of its own. A date of birth
    is passed over (rule 3: it is no candidate's value) unless ``births``."""
    pos = start
    while True:
        m = _VALUE_TOKEN.search(text, pos, end)
        if m is None:
            return None
        if _DIGIT.search(text, m.start(), m.end()):
            stop = m.end()
            if stop < end and _GLUED.match(text, stop):
                stop = _NON_SPACE.match(text, stop, end).end()
            if births and _is_birth(text, m.start()):
                pos = stop
                continue
            return m.start(), stop
        pos = m.end()


# Another field's label inside a label's value field ("DOB:", "MRN:", "Note:"): words and a colon that is not a clock's.
_NEXT_LABEL = re.compile(r"(?<![\w/.-])[A-Za-z][A-Za-z .'’/()#&-]{0,40}?[ \t]*+[:=](?!\d)")


def _value_extent(text: str, start: int, end: int) -> Optional[tuple[int, int]]:
    """The label's own value in its value field [start, end): the first date-shaped run that is no date of birth
    (_first_value) before another field's label; that part whole when it has a digit and no date-shaped run; None when
    another field opens it or its only dates are dates of birth (refutation phase 2, dates:0: "DOS: DOB: 01/01/1998 MRN:
    0000", "Date of Service: Date of Birth: 01/01/1998" made the date of birth the label's value, so a member's
    1998-01-01 agreed with it and was sent - an empty field states no date)."""
    other = _NEXT_LABEL.search(text, start, end)
    stop = other.start() if other is not None else end
    found = _first_value(text, start, stop)
    if found is not None:
        return found
    if _first_value(text, start, stop, births=False) is not None or not _DIGIT.search(text, start, stop):
        return None
    return _strip_span(text, start, stop)


def _label_value(text: str, m: re.Match, rows: _Rows) -> Optional[tuple[int, int, bool]]:
    """Where a date-of-service label's value is, when SERVICE_DATE read no date after it and the value carries a digit:
    (start, end, column), else None (refutation round 2, rule A and c2:8: such a label kept nothing, so a member's date
    became the date and was sent). The value is the label's field on its own line ("20-Oct-26", "10 / 20 / 2026"); the
    same column of the next row, under a label heading a table column (column True: the cells between are not the
    label's); or the next non-blank line, under a label that ends its line ("Date of service:" above "10/20/2026", blank
    lines between). Without a separator the value must start as a date does, so a label in prose ("the procedure date
    was moved twice") has none. A scan: each label reads its own tail, and each line's bars and the row under it are
    read once."""
    tail = _LABEL_TAIL.match(text, m.end())
    pos, sep, gap = tail.end(), tail.group('sep'), tail.group('gap')
    line_start, line_end = rows.line(m.start())
    if pos < line_end and '\t' not in gap and '  ' not in gap:
        end = _field_end(text, pos, line_end)
        if sep is None and not _VALUE_DATE_START.match(text, pos, max(end, pos)):
            return None
        if _DIGIT.search(text, pos, end):
            return pos, end, False
        if sep != '|':
            return None
    bars = rows.bars(line_start, line_end)
    if bars:
        col = bisect.bisect_left(bars, m.start())
        cell_start = bars[col - 1] + 1 if col else line_start
        cell_end = bars[col] if col < len(bars) else line_end
        if m.start() - cell_start > VALUE_REACH or cell_end - m.end() > VALUE_REACH \
                or text[cell_start:m.start()].strip() or text[m.end():cell_end].strip(' \t\r:#=-\u2013'):
            return None  # the label is not its cell's only words (each label reads at most its own short cell)
        row = rows.below(line_end)
        cells = rows.cells(*row) if row else []
        if col >= len(cells):
            return None
        start, end = _strip_span(text, *cells[col])
        if end - m.start() > GAP_REACH or not _DIGIT.search(text, start, end):
            return None
        return start, end, True
    if pos < line_end:
        return None
    row = rows.below(line_end)
    if row is None:
        return None
    start = _strip_span(text, *row)[0]
    if not _VALUE_DATE_START.match(text, start, row[1]):
        return None
    return start, _field_end(text, start, row[1]), False


def _service_dates(text: str, lay: Layout) -> tuple[_Candidate, ...]:
    """Every date candidate outside a plan or history section (refutation round 2, rule A): the labelled dates of
    service, whatever their reading or form, and the dated titles near the top (_title_candidates)."""
    found = []
    read = set()
    blocks = _Blocks(text)
    for m in SERVICE_DATE.finditer(text):
        read.add(m.start())
        if lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        value = date_from_match(m)
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.start('date'), m.end(), value)
        # rule 1 (refutation phase 2): the date is the note's own only from a header block that states it alone
        header = value is not None and blocks.own(m.start(), value.isoformat())
        found.append(_Candidate(_span(text, start, m.end()), value.isoformat() if value else None, 'label',
                                _READING[kind], 'read' if value else 'invalid', header=header))
    rows = _Rows(text)
    for m in DATE_LABEL.finditer(text):
        # refutation r1, context-3, and round 2, c2:8: a labelled date the reader does not read is documented date text
        if m.start() in read or lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        where = _label_value(text, m, rows)
        if where is None:
            continue
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), where[0], where[1], None)
        # refutation round 3, sk:1: the evidence is the label and its own value, never the text beside it; and a field
        # whose only dates are dates of birth states no date (refutation phase 2, rule 3)
        extent = _value_extent(text, where[0], where[1])
        if extent is None:
            continue
        value_start, value_end = extent
        if where[2]:  # a table column: the label's cell and its value's cell, never the cells between
            span, extra = _span(text, start, m.end('label')), (_span(text, value_start, value_end),)
        else:
            span, extra = _span(text, start, value_end), ()
        found.append(_Candidate(span, None, 'label', _READING[kind], 'unread', extra))
    return tuple(found) + _title_candidates(text, lay)


def _title_names(words: str, keyword: Optional[str]) -> str:
    """What a dated title names (refutation round 2, c2:3 and c2:7): 'own' - this note's heading: an encounter (a visit,
    encounter or consultation title, whatever it was for), a bare "Date:", a note, or a report of a service this release
    codes; 'other' - another discipline's document or a report this reader cannot place ("Biopsy report", "Laboratory
    report"). A title naming another discipline is never the note's heading, whatever its title word (refutation round
    3, sk:4: "Surgical pathology consultation: 10/17/2026" was read as the note's own, so 10/17 was sent and a snare
    polypectomy done on 10/14 was excluded as historical): it is kept as the evidence of the date asked. A service name
    speaks only for the words it covers: "Colonoscopy pathology report" names a pathology report, "Endoscopic
    ultrasound report" an EUS."""
    kind = (keyword or '').lower()
    covered = [(m.start(), m.end()) for pattern in _THIS_SERVICE for m in pattern.finditer(words)]
    if any(not any(s <= o.start() and o.end() <= e for s, e in covered) for o in _OTHER_DOCUMENT.finditer(words)):
        return 'other'
    if kind in ('', 'visit', 'encounter', 'consultation', 'consult'):
        return 'own'
    return 'other' if kind == 'report' and not covered else 'own'


def _title_candidates(text: str, lay: Layout) -> tuple[_Candidate, ...]:
    """The dated titles, "Date:" and "Re:" lines near the top (refutation round 2, rule A: every one is kept, whatever its
    reading). Only the FIRST title naming this note can be its heading ("GI visit - 10/20/2026"): 'own', or 'unplaced'
    when qualified ("GI follow-up visit: ...", "Outside colonoscopy report: ..."), with its form when its date is not read
    (a day-first "20/10/2026", a date on the line below). A title naming another document ("Surgical pathology report:
    ...") is never the heading: 'other', or 'aside' when qualified. A title opening with a field label ("Re: ...") is a
    candidate, never the heading. A later unqualified title is 'own' beside an own heading (a conflict when its date
    differs) and 'unplaced' otherwise; a later qualified one ("Next visit: ...") is another occurrence's: 'aside'."""
    lines = []
    for m in re.finditer(r'[^\n]+', text):
        if text[m.start():m.end()].strip():
            lines.append((m.start(), m.end()))
            if len(lines) == TITLE_LINES:
                break
    out, heading = [], None
    for index, (ls, le) in enumerate(lines):
        if lay.section_at(ls).kind in NOT_CURRENT_SECTIONS:
            continue
        m = TITLE_DATE.match(text, ls, le)
        if m is not None:
            day = None if m.group('unread') is not None else date_from_match(m)
            form = 'read' if day else ('unread' if m.group('unread') is not None else 'invalid')
            end, words, keyword, field = le, m.group('words') or '', m.group('keyword'), m.group('field') is not None
        else:
            head = TITLE_HEAD.match(text, ls, le)
            if head is None or index + 1 == len(lines) or not DATE_LINE.match(text, *lines[index + 1]):
                dated = _dated_service_line(text, ls, le)
                if dated is not None:
                    out.append(dated)
                continue
            day, form, end, words, keyword, field = None, 'unread', lines[index + 1][1], head.group('words'), \
                head.group('keyword'), False
        span = _span(text, _strip_span(text, ls, le)[0], end)
        value = day.isoformat() if day else None
        qualified = _title_qualified(text, ls, le, m)
        if field:
            reading, source = 'unplaced', 'field'
        elif _title_names(words, keyword) == 'other':
            reading, source = ('aside' if qualified else 'other'), 'title'
        elif heading is None:
            reading, source = ('unplaced' if qualified else 'own'), 'title'
            heading = reading == 'own' and form == 'read'
        else:
            reading, source = ('aside' if qualified else 'own' if heading else 'unplaced'), 'title'
        out.append(_Candidate(span, value, source, reading, form, bare=m is not None and not keyword and not field))
    return tuple(out)


def _title_qualified(text: str, ls: int, le: int, m) -> bool:
    """Whether a dated title line names another occurrence: a date qualifier anywhere on it ("follow-up", "next",
    "planned"), or a history word before its date ("Outside", "Prior", "Index", "s/p"; routing's own cues)."""
    if DATE_QUALIFIER.search(text, ls, le):
        return True
    head = text[ls:le]
    return any(pattern.search(head) for _, pattern in _HISTORY_TITLE)


# A date that ends a line near the top ("Colonoscopy - 10/14/2026", "EGD 10/14/2026"): read by _dated_service_line.
# A sentence's full stop may end the line after the date ("Your patient underwent colonoscopy on 10/14/2026.";
# refutation round 3, sk:6), and a clock may follow it ("Colonoscopy - 10/14/2026 08:30"; sk:7).
_LINE_END_DATE = cues.rx(r'(?<![\w/-])(?:' + _FULL_DATE + r'|(?P<unread>' + DATE_SHAPE + r'))' + _CLOCK
                         + r'[ \t]*+\.?+[ \t]*+$')


# Between a service's name and the date ending its line: another field's label (a colon that is not a clock's) or the
# start of another date (refutation round 3, sk:1).
_GAP_DATE = cues.rx(r'(?<![\w/.-])(?:' + _VALUE_DATE_START.pattern + r')')


# A letter's subject line opening a line ("Re: ", "Regarding: ", "Subject: "): the structure is the subject line naming
# the encounter the letter is about; these labels are its vocabulary.
_SUBJECT_FIELD = cues.rx(r'[ \t]*+(?:re|regarding|subject|subj)\.?[ \t]*+:[ \t]*+')
SERVICE_LINE_READ = 160  # a line near the top this long or shorter is read for a service's date anywhere on it


def _dated_service_line(text: str, ls: int, le: int) -> Optional[_Candidate]:
    """A line near the top that ends with a date and names a service this release codes, but carries no title word
    ("Colonoscopy - 10/14/2026", "EGD 10/14/2026"): documented date text the title grammar does not read. It is never the
    date and never questions the note's own labelled date or titled heading ('aside', source 'line'), but when the note
    gives no usable date of its own it is kept as the evidence a member date must agree with (refutation round 2, rule
    A: such a line kept nothing, so a member's date became the date and was sent). A line qualified as another
    occurrence's ("Last colonoscopy 05/01/2019") is not one, and a line naming no service ("Date of birth: ...") is not
    one. A letter's subject line naming the service ("Re: Colonoscopy on 10/14/2026") names the encounter as a "Re:"
    title does: a candidate a letter's "Date:" and the note's own labelled date must agree with ('unplaced', as a field
    title), whatever its qualifier. Any other field naming the service ("Procedure: Colonoscopy ... 2026-10-01",
    "Indication: ... colonoscopy 2023-05-02") is only evidence - beside the note's own labelled date or titled heading.
    Beside a bare "Date:" line, which names no encounter, every such line is a candidate that date must agree with
    (refutation round 3, sk:6: "Date: 10/27/2026" won over "Procedure: Colonoscopy on 10/14/2026", "Regarding your
    colonoscopy of 10/14/2026" or a sentence ending "... colonoscopy on 10/14/2026.", so a letter's date was sent and a
    snare polypectomy done on 10/14 excluded as historical; only a "Re:", "Regarding:" or "Subject:" line questioned it)."""
    m = _LINE_END_DATE.search(text, ls, le)
    if m is not None and m.start() - ls <= 80:
        hi = m.start()
    elif le - ls <= SERVICE_LINE_READ and _GAP_DATE.search(text, ls, le):
        # refutation phase 2, rule 2: a short line naming the service with its date anywhere ("Procedure: Colonoscopy
        # on 10/14/2026 at Synthetic Endoscopy Center", "Your patient underwent colonoscopy on 10/14/2026 at our unit.")
        # is kept as evidence too, so a member's answer with its date agrees with it
        hi = le
    else:
        return None
    names = [name for p in _THIS_SERVICE for name in p.finditer(text, ls, hi)]
    if not names:
        return None
    field = _SUBJECT_FIELD.match(text, ls, hi)
    if field is not None and any(p.search(text, field.end(), hi) for p in _THIS_SERVICE):
        source, reading = 'field', 'unplaced'
    elif _title_qualified(text, ls, le, None):
        return None
    else:
        source, reading = 'line', 'aside'
    # refutation round 3, sk:1: the evidence holds no date but the line's own. A date before the line's service name
    # ("Synthetic, Alex DOB 01/01/1998 Colonoscopy 10/14/26") is not its value: the evidence starts after it. And the
    # line's last date is the service's only when no other field or date stands between the service's name and it:
    # in "Colonoscopy DOS: 10-14-26 DOB: 01/01/1998" or "Colonoscopy 10-14-26 DOB 01/01/1998" it is the date of birth,
    # and the service's own is the first date after its name (here one this service does not read) - so a member's date
    # of birth never agrees with this line.
    name_start, name_end = min((name.start(), name.end()) for name in names)  # the dates after its first name
    start = _strip_span(text, ls, le)[0]
    for before in FULL_DATE.finditer(text, start, name_start):
        start = before.end()
    while start < name_start and text[start] in ' \t,;:|-–':
        start += 1
    # Refutation phase 2 (rules 3 and 4; dates:2, interplay:0): the line's own date is its ONLY date after the service's
    # name that is no date of birth. Round 3 took the first date after the name whenever a field or a date stood
    # between, so in "Procedure: EGD  Patient: Alex Synthetic  DOB: 01/01/1998  Date: 10/14/2026" or "Re: Colonoscopy
    # - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026" the date of birth was the line's value: a member's 1998-01-01
    # agreed with it and was sent, and the line's own 10/14 answer was held. A line with two such dates states none the
    # reader can tell ("Re: EGD referral 09/01/2026 10/14/2026"): it is kept, reading no date. Its evidence holds no
    # other date, so a member date agrees only with the line's own.
    runs, born, pos = [], [], name_end
    for at in _GAP_DATE.finditer(text, name_end, le):  # the dates after the name ("#2" or a clock is none)
        run = _first_value(text, at.start(), le, births=False) if at.start() >= pos else None
        if run is None:
            continue
        (born if _is_birth(text, run[0]) else runs).append(run)
        pos = run[1]
    if not runs:  # the line's only dates are dates of birth ("Colonoscopy DOB: 01/01/1998")
        return None
    if len(runs) > 1:
        cut = _strip_span(text, start, min(r[0] for r in runs + born))
        return _Candidate(_span(text, *cut), None, source, reading, 'unread')
    own = runs[0]
    full = FULL_DATE.match(text, own[0], own[1])
    whole = full is not None and full.end() == own[1]
    day = date_from_match(full) if whole else None
    form = 'read' if day else ('invalid' if whole else 'unread')
    value = day.isoformat() if day else None
    before = [r for r in born if r[1] <= own[0]]
    if not before:
        return _Candidate(_span(text, start, own[1]), value, source, reading, form)
    # a date of birth between the name and the line's own date: the evidence is the line around it, never the birth date
    label = _BIRTH_BEFORE.search(text, max(start, before[0][0] - _BIRTH_REACH), before[0][0])
    head = _strip_span(text, start, label.start() if label else before[0][0])
    tail = _strip_span(text, before[-1][1], own[1])
    spans = [_span(text, *s) for s in (head, tail) if s[0] < s[1]]
    return _Candidate(spans[0], value, source, reading, form, extra=tuple(spans[1:]))


def _settings(text: str, lay: Layout) -> Optional[list[tuple[str, Span]]]:
    """The documented settings, or None when the text states setting phrases more often than SETTING_STATEMENT_LIMIT
    (refutation phase 2, ctxcost:1): each phrase is checked as a statement, and that check is not repeated without
    bound - the phrases are then not read, and the setting is asked (never a choice among the first ones read)."""
    phrases = []
    for setting, pattern in SETTING_PHRASES:
        for m in pattern.finditer(text):
            phrases.append((setting, m))
            if len(phrases) > SETTING_STATEMENT_LIMIT:
                return None
    found = []
    for m in POS.finditer(text):
        if lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        code = m.group('code')
        found.append((POS_CODES.get(code, f'unrecognised place-of-service code {code}'), _span(text, m.start(), m.end())))
    for m in SETTING_LABEL.finditer(text):
        if POS.match(text, m.start()) or lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        value_start = m.start('value')
        for setting, pattern in SETTING_WORDS:
            for w in pattern.finditer(m.group('value')):
                found.append((setting, _span(text, m.start(), value_start + w.end())))
    for setting, m in phrases:
        if is_current_statement(text, lay, m.start(), m.end()):
            found.append((setting, _span(text, m.start(), m.end())))
    return found


def _patient_status(text: str, lay: Layout) -> list[tuple[str, Span]]:
    found = []
    for m in PATIENT_STATUS.finditer(text):
        lo, _ = _near(text, m.start(), m.end(), 40)
        if lay.section_at(m.start()).kind == 'plan' or NEGATED_BEFORE.search(text, lo, m.start()):
            continue
        value = (m.group('v') or m.group('v2') or m.group('v3')).lower()
        found.append((value, _span(text, m.start(), m.end())))
    return found


def _billing(text: str) -> list[tuple[str, Span]]:
    found = []
    for m in BILLING.finditer(text):
        if m.group('p'):
            value = 'professional'
        elif m.group('f'):
            value = 'facility'
        else:
            value = (m.group('v') or m.group('v2') or m.group('v3')).lower()
        found.append((value, _span(text, m.start(), m.end())))
    return found


INVALID_DATE_NOTE = 'A labelled or title date of service is not a valid calendar date.'
UNREAD_DATE_NOTE = 'A labelled or title date of service is not written in a form this service reads.'
UNPLACED_DATE_NOTE = ('A dated label or title is qualified, names another occurrence or another document, or carries '
                      'words this service cannot place, so its date is not taken as the date of service.')
HEADER_DATE_NOTE = ('A date of service is taken only from a labelled date standing alone in a header block that holds '
                    'nothing but the title, patient, record, birth date, age, sex, physician, location or referring '
                    'fields and agreeing date labels; other text beside this labelled date may date another '
                    'occurrence, so it is asked.')
EVIDENCE_DATE_NOTE = ('A dated title, a "Date:" line or a dated line naming the service is kept as evidence; it is never '
                      'taken as the date of service by itself.')


def _service_date_fact(found: tuple[_Candidate, ...]) -> Fact:
    """The service date fact (refutation round 2, rules A and B). The note's own labelled dates, when they agree, are the
    date; failing them, its own dated title near the top. Either gives the date only when every candidate that could
    speak for this note's date agrees with it: beside an own labelled date, a labelled date this service cannot place,
    the note's own dated title, a qualified first title and a "Re:" line; beside an own title, EVERY labelled date -
    also one set aside as another occurrence's, which the reader may have misread (c2:2, c2:5, c2:6) -, a "Re:" line
    and another document's title. A difference is a conflict with every side kept (both sides listed when all are
    read), never a silent choice of the weaker or the stronger source (c2:1: a planned procedure's labelled date was
    taken over the report's title, sent, and an act done that day excluded against it). With no usable own date, every
    candidate is kept as evidence and the date is asked: a member value must agree with it (merge_user_values).

    Every set here is kept by identity, never by a list membership test: that compared each pair of candidates, so
    the fact was quadratic in the note's labelled dates (refutation round 3, sk:3: 'DOS: 10/14/2026' 24,000 times, under
    the paste cap, overran the analyze stage's 60 s, and 12,000 a member's POST /context).

    A dated line naming the service ('line', _dated_service_line) questions only a bare "Date:" line, which names no
    encounter (refutation round 3, sk:6: a letter's "Date:" won over "Procedure: Colonoscopy on 10/14/2026").

    Refutation phase 2 (P2DATES) narrows the own date by its source, never by vocabulary. Only a date-of-service label
    whose value is a date alone and whose block holds nothing but the title, header fields and agreeing date labels
    (rule 1, _Candidate.header) is the note's own date; a labelled date in any other block is asked. A dated title, a
    "Date:" line, a dated line or a letter's subject line is never the date (rule 2): it can only question a labelled
    date, or stand as the evidence of the date asked - as the installed revision (057a7d398) sent no date for those
    shapes. Round 3 read them as the note's own and a fax's "Date/Time: 10/27/2026 14:30", a letter's "Date:" above the
    encounter it names, or "Cardiology consultation: 10/09/2026" above a colonoscopy was sent, and the snare
    polypectomy done on 10/14 excluded against it (dates:1, 3, 5); a planned, outside, cancelled or pending date beside a
    label was documented whenever its qualifier was a word, a reach or a line the reader did not read (dates:4, 6-8)."""
    labels = [c for c in found if c.source == 'label']
    own = [c for c in labels if c.reading != 'aside' and c.form == 'read' and c.header]
    own_ids = {id(c) for c in own}
    speaks = [c for c in labels if id(c) not in own_ids and c.reading in ('own', 'unplaced')]
    support = list(speaks)  # what joins the date's evidence when it agrees: as before, labels only
    speaks += [c for c in found if c.source != 'label' and c.reading in ('own', 'unplaced')]
    values = {c.value for c in own}
    unusable = [c for c in (speaks if own else found) if c.form != 'read']
    note = ' '.join(text for present, text in (
        (any(c.form == 'invalid' for c in unusable), INVALID_DATE_NOTE),
        (any(c.form == 'unread' for c in unusable), UNREAD_DATE_NOTE),
        (not own and any(c.source == 'label' and c.form == 'read' and c.reading != 'aside' for c in found),
         HEADER_DATE_NOTE),
        (not own and any(c.source != 'label' and c.form == 'read' for c in found), EVIDENCE_DATE_NOTE),
        (not own and any(c.form == 'read' and c.reading in ('aside', 'other') for c in found), UNPLACED_DATE_NOTE))
        if present)
    if own and len(values) == 1 and all(c.form == 'read' and c.value in values for c in speaks):
        return _fact('service_date', [(c.value, s) for c in own + support for s in c.spans])
    unread = tuple(s for c in unusable for s in c.spans)
    if own:
        fact = _fact('service_date', [(c.value, s) for c in own + speaks if c.form == 'read' for s in c.spans])
        if not unusable:
            return fact
        return Fact('service_date', None, 'conflict', _sorted_spans(fact.evidence + unread), note)
    fact = _fact('service_date', [(c.value, s) for c in found if c.form == 'read' for s in c.spans])
    if not found:
        return fact
    return Fact('service_date', None, 'missing', _sorted_spans(fact.evidence + unread), note)


def _sorted_spans(spans) -> tuple[Span, ...]:
    return tuple(sorted(dict.fromkeys(spans), key=lambda s: (s.start, s.end)))


@functools.lru_cache(maxsize=16)
def _context(text: str) -> tuple[Fact, ...]:
    lay = layout(text)
    service_date = _service_date_fact(_service_dates(text, lay))
    settings_found = _settings(text, lay)
    setting = (_fact('setting', settings_found) if settings_found is not None else
               Fact('setting', None, 'missing', (), TOO_MANY_SETTINGS_NOTE.format(limit=SETTING_STATEMENT_LIMIT)))
    if setting.origin == 'document' and setting.value not in SETTINGS:
        setting = Fact('setting', None, 'missing', setting.evidence,
                       f'The documented {setting.value} is not a care setting this service recognises.')
    return (service_date, setting, _fact('billing_context', _billing(text)),
            _fact('patient_status', _patient_status(text, lay)))


def extract_context(text: str) -> dict[str, Fact]:
    """The CONTEXT_FACTS documented in the text; missing facts have origin 'missing'."""
    return {fact.name: fact for fact in _context(text)}


def service_date_of(text: str) -> Optional[date]:
    fact = _context(text)[0]
    return date.fromisoformat(fact.value) if fact.origin == 'document' else None


def _valid_user_value(name: str, value: str) -> bool:
    if name == 'service_date':
        try:
            return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)) and date.fromisoformat(value) is not None
        except ValueError:
            return False
    allowed = {'setting': SETTINGS, 'billing_context': BILLING_CONTEXTS, 'patient_status': PATIENT_STATUSES}[name]
    return value in allowed


DOCUMENT_CONFLICT_NOTE = 'Conflicting documented values: '


def documented_values(fact) -> tuple[str, ...]:
    """The values a document-internal conflict lists (its note, written by _fact), or () for any other fact."""
    note = str(getattr(fact, 'note', '') or '')
    if getattr(fact, 'origin', None) != 'conflict' or not note.startswith(DOCUMENT_CONFLICT_NOTE) or not note.endswith('.'):
        return ()
    return tuple(v for v in note[len(DOCUMENT_CONFLICT_NOTE):-1].split(', ') if v)


USER_CONFLICT_NOTE = ('Encounter metadata entered by a workspace member gives {user}; the document gives {document}. '
                      'Both are kept and neither is used until they agree: correct the metadata, clear it, or add an '
                      'addendum to the document.')
_USER_CONFLICT_PREFIX = USER_CONFLICT_NOTE.split('{', 1)[0]


def is_member_conflict(fact) -> bool:
    """Whether ``fact`` is a member's encounter metadata that differs from the document's single value
    (merge_user_values), as opposed to values that conflict within the document itself. Every reader that words a
    conflict asks this one question, so a member's value is never described as conflicting documentation. ``fact`` is
    a Fact or a stored context fact (a mapping)."""
    if fact is None:
        return False
    get = fact.get if isinstance(fact, dict) else (lambda name, default=None: getattr(fact, name, default))
    return get('origin') == 'conflict' and str(get('note', '') or '').startswith(_USER_CONFLICT_PREFIX)


def _date_readings(spans) -> Optional[set]:
    """The calendar dates documented date text reads (ISO strings), or None when it reads none - a member date can then
    never be shown to agree with it. Refutation round 2: every candidate is now kept, so the evidence can hold text that
    reads a date beside text that reads none ("GI visit - 10/20/2026" beside "Last visit date: 04/15/26"); the dates it
    does read are the ones a member can answer with, so the date asked is never stuck when the member answers with one.
    Refutation round 3, sk:1: these are only the dates the candidates state as their own values - each candidate's
    evidence holds no other date (_Candidate.extra, _value_extent, _dated_service_line), so a date of birth written
    beside a date of service ("DOS: 10/14/26 DOB: 01/01/1998", "Patient | DOB | Date of Service") is never one."""
    values = set()
    for span in spans:
        quoted = str(span.text)
        # refutation phase 2, rule 3: a date of birth is never read, wherever an evidence span holds one
        values |= {day.isoformat() for day in (date_from_match(m) for m in FULL_DATE.finditer(quoted)
                                                if _BIRTH_BEFORE.search(quoted, max(0, m.start() - _BIRTH_REACH),
                                                                        m.start()) is None) if day}
    return values or None


def merge_user_values(facts: dict[str, Fact], user_values: dict[str, str]) -> dict[str, Fact]:
    """A non-empty user value is encounter metadata: it supplies a fact the document does not give or does not give
    unambiguously (a missing or conflicting documented value), and it agrees with a documented value. A user value
    that DIFFERS from a single documented value is a conflict, kept with both sides, never a silent replacement of the
    clinical documentation (2026-10-27: a member-entered service date 28 years before the documented one was used for
    every dated check and sent to the provider). Where the document itself gives conflicting values, a member value
    settles it only by choosing one of them. An empty value leaves the document value. Unknown names or values are
    refused."""
    merged = dict(facts)
    for name, raw in user_values.items():
        if name not in CONTEXT_FACTS:
            raise ValueError(f'{name!r} is not an encounter context fact.')
        if not isinstance(raw, str):
            raise ValueError(f'{name} must be a string.')
        value = raw.strip()
        if not value:
            continue
        if not _valid_user_value(name, value):
            raise ValueError(f'{value!r} is not a valid {name}.')
        documented = facts.get(name)
        if documented is not None and documented.origin == 'document' and documented.value \
                and str(documented.value) != value:
            merged[name] = Fact(name, None, 'conflict', documented.evidence,
                                USER_CONFLICT_NOTE.format(user=value, document=documented.value))
            continue
        listed = documented_values(documented)
        if listed and value not in listed:
            # The document itself gives several values: a member value settles the conflict only by choosing one of
            # them. Any other value is a third side, kept with the documented ones (the Elena class: a member-entered
            # 1998-01-01 against two documented dates was taken as the service date and sent to the provider).
            merged[name] = Fact(name, None, 'conflict', documented.evidence,
                                USER_CONFLICT_NOTE.format(user=value, document=' or '.join(listed)))
            continue
        if not listed and documented is not None and documented.origin in ('missing', 'conflict') \
                and documented.evidence:
            # The document labels this fact but its value cannot be used here (a labelled date that is no calendar
            # date, a place-of-service code this service does not recognise): a member value cannot be checked
            # against it, so both sides are kept (refutation r1: such a member date was used and sent to the provider,
            # and such a member setting made a held office visit ready). Dated text the reader does not read as the
            # date or cannot place - "Tuesday, October 20, 2026", a label above its value, a qualified first title -
            # is checked by the dates it reads (refutation r1, context-3: a member date had replaced such text silently
            # and was sent to the provider). A member date agrees when it is one of them, as a member settles a
            # documented conflict by choosing one of its values: the date asked is never stuck when the member
            # answers with a date the evidence reads, also where the evidence reads more than one (refutation round 2:
            # every candidate is now kept). Any other date is a conflict, and so is any date where the evidence reads
            # none ("Date of service: 20-Oct-26" alone: amend the document or clear the value). The evidence reads
            # only the dates its candidates state as their own (refutation round 3, sk:1: a date of birth beside the
            # date of service was read too, and a member's 1998-01-01 was taken and sent).
            readings = _date_readings(documented.evidence) if name == 'service_date' else None
            if readings is not None and value in readings:
                merged[name] = Fact(name, value, 'user', (), USER_NOTE)
                continue
            shown = ', '.join('\u201c' + ' '.join(ev.text.split())[:60] + '\u201d' for ev in documented.evidence[:3])
            merged[name] = Fact(name, None, 'conflict', documented.evidence,
                                USER_CONFLICT_NOTE.format(user=value, document=shown))
            continue
        merged[name] = Fact(name, value, 'user', (), USER_NOTE)
    return merged
