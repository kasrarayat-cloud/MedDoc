"""Encounter context read from the document: service date, setting, billing
context and new/established patient status. See ARCHITECTURE.md section 5.2.

Only explicit statements count. Different documented values are a conflict
(value None, every statement kept as evidence), never a silent choice. A date
or setting written in a plan or history section, or qualified as previous /
next / scheduled, describes another encounter and is not read. Dated text the
reader does not read as the date, or cannot place, never supplies the date: it
is kept as evidence a member value must agree with. Only a date-of-service
label's own value is ever the date (refutation phase 2, P2DN): a dated title, a
"Date:" line or a dated line is evidence, and a date of birth is never read.
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
# asked, as for a document that states none. A real note states its setting a few times (the corpus's most is 8).
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

# Refutation phase 2, P2DN rule N2: a date of birth is never a service date. A date with a birth label before it - in
# any position, any row, any bracket - is no candidate's value, never agrees with a member's date and is never in the
# evidence a member date is matched against (dates:0, dates:2, interplay:0: a member's 1998-01-01 agreed with a date of
# birth a label's field or a dated line held, and was sent). The birth LABELS are a closed list: DOB, D.O.B., D-O-B,
# date of birth, birth date, birthday, birth, born, b., and their joined forms - joined to another field's name by a
# slash or an ampersand, or followed by a bracketed word ("DOB/Age", "Age/DOB", "DOB (age)"; the P2DATES skeptic's sk:4).
# P2DN's fix round, issue 7: "b." is the birth label only as it is written - lower case ("(b. 01/01/1998)", ", b.
# 01/01/1998", "Alex Synthetic b. 01/01/1998") - never a capital initial after a name ("Dr. Robin B. - 10/14/2026",
# "Synthetic, Alex B. - 10/14/2026"), which made the line's own date a date of birth, so the dated line was dropped and
# a member's 1998-01-01 taken and sent. The final refutation, fr-dr:5: the case is the whole rule - a lower-case "b."
# one space after a name ("Re: Colonoscopy for Alex Synthetic b. 01/01/1998") was refused as well, so the date of birth
# was the subject line's own date, a document conflict beside the note's labelled 10/14 listed it, and a member's
# 1998-01-01 was taken and sent. A bracket after the label may hold its format ("DOB (mm/dd/yyyy):", "Date of Birth
# (MM/DD/YYYY):"; issue 1: the date after it was read as another field's value the member's 1998-01-01 agreed with).
_BIRTH_LABEL = (r'(?:D[.\-]?+[ \t]?+O[.\-]?+[ \t]?+B\b\.?+|date[ \t]++of[ \t]++birth|birth(?:[ \t]*+(?:date|day))?+'
                r'|born(?:[ \t]++on)?+|(?-i:b)\.)')
_BIRTH_FORM = (r'(?:[A-Za-z]{1,12}+[ \t]*+[/&][ \t]*+)?' + _BIRTH_LABEL
               + r'(?:[ \t]*+[/&][ \t]*+[A-Za-z]{1,12}+|[ \t]*+\([ \t]*+[A-Za-z][A-Za-z/.\- ]{0,14}+\))?+')
# A date with a birth label right before it ("DOB: 01/01/1998", "(DOB 01/01/1998)", "Date of birth - 01/01/1998", "born
# on 01/01/1998", "b. 01/01/1998", "DOB (age) 01/01/1998"): read in the few characters before the date.
# The few characters before the date end at the date (\Z, never $: $ matches before a line break too, so a birth word
# ending the line above read the next line's first date as its value - P2DN's fix round, issue 7).
_BIRTH_BEFORE = cues.rx(r'(?<![\w/.-])' + _BIRTH_FORM + r'[ \t]*+(?:[:#=\u2013-][ \t]*+)?+(?:\([ \t]*+)?+\Z')
_BIRTH_REACH = 40
_BIRTH_HEAD = cues.rx(r'(?<![\w/.-])' + _BIRTH_FORM + r'(?![\w/-])')
_BIRTH_TAIL = re.compile(r'[ \t]*+(?P<sep>[:#=\u2013-])?+[ \t]*+')

# Refutation phase 2, ctxcost:0: every whitespace run in POS is possessive. 'POS', a long run of spaces and no code was
# read in time quadratic in the run (two adjacent optional runs, every split tried): a 96,000-character paste overran
# the analyze stage's 60 s, and 48,000 a member's POST /context (15 s).
POS = cues.rx(r'(?<![\w/-])(?:place[ \t]++of[ \t]++service|POS)\b[ \t]*+(?:\([ \t]*+POS[ \t]*+\)[ \t]*+)?+'
              r'(?:code[ \t]*+)?+[:#=\u2013-]?+[ \t]*+(?P<code>\d{2})(?![\w/-])')
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
    # 'read' | 'invalid' | 'unread' | 'empty' - a date-of-service field that states no date of its own (rule N3, P2DN's
    # fix round, issue 6): the label alone, never its field - or a dated line whose dates are all another field's or
    # dates of birth, its text before them; evidence that reads no date when the note states none, and never speaking
    # against the note's own date, as it states none that could differ. A field that STATES a date it cannot place is
    # 'unread', never 'empty' (the final refutation, fr-dr:0): it speaks, and the date is asked
    form: str
    # A table column's value cell, kept beside the label heading it (span): never the cells between them. Every span a
    # candidate keeps holds no date but its own value (refutation round 3, sk:1), so the dates its evidence reads are the
    # dates it states.
    extra: tuple[Span, ...] = ()
    # Refutation phase 2, P2DN rule N5: a read labelled date whose own field holds nothing but the date (a clock at most)
    # up to the field's end - the end of its line, a row's cell bar or the next field's label (_alone_in_field). A date
    # with a bracket or words after it in its field ("(pending authorization)", "(cancelled)") is never the note's own.
    alone: bool = True
    # P2DN's fix round, rule N7 (issue 8): a read labelled date written as the installed revision 057a7d398 reads one - a
    # plain date-of-service label (no time named), a separator that is no cell bar, a date written year-first,
    # month-first with slashes or with the month's name first (_installed_form). Only such a date is ever the note's own:
    # the known-limit qualifier shapes are a known limit only where the installed revision sends the same date, and in
    # another form ("3 Sep 2026", "Date/Time of Service:", "| Date of service | 09/03/2026 |") they sent another
    # occurrence's date where it sent none. Another form is evidence: asked, the member's answer agreeing with its date.
    installed: bool = True

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
    so a planned procedure's date was read as the service date. A field with a date of its own is 'dated' (P2DN's fix
    round, issue 5: on the label's own line it holds the date; elsewhere it is passed over as 'else' is)."""
    m = _FIELD_LABEL.match(text, q_end, limit)
    if m is None or '  ' in text[q_end:m.end()]:  # a field break ends the qualifier's words: no label of its own
        return None
    brk = _FIELD_BREAK.search(text, m.end(), min(limit, m.end() + VALUE_REACH))
    if has_date(m.end(), brk.start() if brk else min(limit, m.end() + VALUE_REACH)):
        return 'dated'
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

    def dated(a: int, b: int) -> list:
        """The other dates in [a, b) that are no date of birth (a date of birth dates no occurrence)."""
        return [d for d in other_dates(a, b) if not _is_birth(text, d.start)]

    # P2DN's fix round, issue 5 (and issue 8's E9): a qualifier on the label's own line with a date of its own - in its
    # own field ("Rescheduled to: 10/14/2026", "Next visit: 11/24/2026") or right after it ("Follow-up visit
    # 10/20/2026.", "Last colonoscopy 05/01/2019") - makes the line state two occurrences' dates, and the reader cannot
    # tell which is this encounter's: the date is asked (unplaced), never passed over. Round 2 (c2:1) passed such a
    # qualifier over as belonging elsewhere, so "Date of service: 10/07/2026 Rescheduled to: 10/14/2026" documented the
    # superseded 10/07, which was sent and 45385 done on 10/14 excluded against it, where the installed revision's
    # same-line window held it. One on the line above is still passed over (round 3's rule).
    # The final refutation, fr-dr:4, fr-di:0 and fr-di:1 (rule N7: nothing is sent that the installed revision would not
    # send): a DATE qualifier on the label's own line that opens a field of its own is never passed over, whatever that
    # field names ("Scheduled by: Front desk", "Requested by:", "Planned sedation: MAC", "Last name:") - the installed
    # revision's same-line window held every such date, and passed over, a planned procedure's 11/04 was sent with an
    # office visit's request, and a recall's 10/14/2029 instead of the encounter's 10/14/2026. A date of birth between a
    # qualifier and the date passes nothing over (it dates no occurrence; "Repeat colonoscopy for ... (DOB 01/01/1998)
    # Procedure date:", "... DOB: 01/01/1998    Status: Scheduled"). A HISTORY word opening a field about something else
    # ("Outside records:", "Recent labs:") is still passed over: the installed revision never read those words.
    reading = 'own'
    for q in _OTHER_OCCURRENCE.finditer(text, lo, label_start):
        field = _qualifier_field(text, q.start(), q.end(), label_start, has_date)
        qualifier = DATE_QUALIFIER.fullmatch(q.group()) is not None
        if field == 'dated' or (field == 'else' and qualifier) or (field != 'else' and dated(q.end(), label_start)):
            reading = 'unplaced'
            continue
        if field == 'else':
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
                    or _qualifier_field(text, q.start(), q.end(), above[1], has_date) in ('else', 'dated'):
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
        field = _qualifier_field(text, q.start(), q.end(), hi, has_date)
        qualifier = DATE_QUALIFIER.fullmatch(q.group()) is not None
        if field == 'else' and not qualifier:
            continue
        own = dated(q.end(), hi)  # a date of birth dates no occurrence (fr-di:0)
        nearer = bool(own) and own[0].start - q.end() < q.start() - date_end
        if field in ('dated', 'else') or nearer or dated(date_end, q.start()):
            # issue 5: the qualifier dates another occurrence on the label's line; fr-dr:4: a date qualifier's own field
            reading = 'unplaced'
            continue
        if not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[date_end:q.start()])):
            return 'another'
        if qualifier:  # a history word across a field break does not place the date
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
        self._aligned, self._above, self._dated = {}, {}, {}

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

    def aligned(self, ls: int, le: int) -> list[tuple[int, int]]:
        """The line's cells as a space- or tab-aligned row writes them: the non-blank runs between field breaks (a tab,
        or two blanks or more), stripped; read once per line (P2DN's fix round, issue 4)."""
        if ls not in self._aligned:
            found, pos = [], ls
            for gap in _CELL_GAP.finditer(self.text, ls, le):
                s, e = _strip_span(self.text, pos, gap.start())
                if s < e:
                    found.append((s, e))
                pos = gap.end()
            s, e = _strip_span(self.text, pos, le)
            if s < e:
                found.append((s, e))
            self._aligned[ls] = found
        return self._aligned[ls]

    def above(self, ls: int) -> Optional[tuple[int, int]]:
        """The line right above the line starting at ``ls`` when it is not blank (no blank line between), else None."""
        if ls not in self._above:
            found = None
            if ls > 0:
                ps = self.text.rfind('\n', 0, ls - 1) + 1
                if not _blank_to(self.text, ps, ls - 1):
                    found = (ps, ls - 1)
            self._above[ls] = found
        return self._above[ls]

    def states_a_date(self, start: int, end: int) -> bool:
        """_states_a_date for a row or a value line, read once (the labels of one header share the row below)."""
        if (start, end) not in self._dated:
            self._dated[start, end] = _states_a_date(self.text, start, end)
        return self._dated[start, end]

    def next_line(self, le: int) -> Optional[tuple[int, int]]:
        """The line right below the line ending at ``le`` when it is not blank (no blank line between), else None."""
        if le >= len(self.text):
            return None
        ne = self.text.find('\n', le + 1)
        ne = len(self.text) if ne < 0 else ne
        return None if _blank_to(self.text, le + 1, ne) else (le + 1, ne)


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
    return start >= end or _BLANKS.match(text, start, end).end() >= end


# P2DN's fix round, issues 3, 4 and 7 (rule N2 "in any position, any row"): a header names its fields in order, and each
# value is its own field's BY POSITION - a column by its column, a stacked label by its place in the stack, a joined
# header ("DOB / Date of Service: 01/01/1998 / 10/14/2026") by its place in the header. Where the positions do not match
# (more values than names, a stack with a value missing) no value is the label's: it states no date (fail closed). A
# space- or tab-aligned row ("DOB            Date of Service" over "01/01/1998     10/14/2026") or a stack ("DOB:" /
# "Date of service:" / "01/01/1998" / "10/14/2026") left the date of birth the label's value, so a member's 1998-01-01
# was taken and sent while the 10/14 the note states was held; a birth label joined to the label made the date of birth
# the documented service date, sent with no member at all. A birth word ending a line labels the next line only when it
# is the line's only text and the next line opens with the value: "To: Dr. Robin B." or "chronic hepatitis B." above
# "Colonoscopy 10/14/2026", or "DOB" heading the LAST column, marked 10/14 as a date of birth (issue 7).
_NO_VALUE = object()  # a field label whose value cannot be located: it states no date of its own
# The final refutation, fr-dr:0: a field label whose value cannot be placed although a date stands where it would be (a
# column or a stack whose positions do not match, one value under a joined header): it STATES a date the reader cannot
# take, so it is asked (form 'unread', the label alone - the date may be a date of birth, rule N2), never silent.
_UNPLACED = object()
_CELL_GAP = re.compile(r'[ \t]{2,}+|\t')  # a field break between aligned cells (possessive: a long run is read once)
_HEADER_CELL = re.compile(r"[A-Za-z][^\d:#|\n]{0,60}+[:#]?+")  # a whole cell that is a label: no digit, a colon at its end
HEADER_CELLS = 24  # a row with more aligned cells than this is never read as a header row
_LABEL_LINE = cues.rx(r'(?:(?P<dos>' + _DATE_LABEL + r')|(?P<birth>' + _BIRTH_FORM + r'))[ \t]*+[:#]?+'
                      r"|[A-Za-z][^\d:#|\n]{0,40}+:")
STACK_REACH = 8  # label-only lines read above and below a stacked label; a longer run is never read by position
_JOINER = r'[ \t]*+(?:[/&+,]|\band\b)[ \t]*+'
_JOINED_BEFORE = cues.rx(r'(?<![\w/.-])' + _BIRTH_FORM + _JOINER + r'\Z')
_JOINED_AFTER = cues.rx(_JOINER + r'(?:' + _BIRTH_FORM + r')(?![\w/-])')


def _header_row(text: str, rows: '_Rows', ls: int, le: int) -> Optional[list[tuple[int, int]]]:
    """The cells of a space- or tab-aligned header row - two cells or more, each a label alone - or None."""
    cells = rows.aligned(ls, le)
    if not 2 <= len(cells) <= HEADER_CELLS or not all(_HEADER_CELL.fullmatch(text, s, e) for s, e in cells):
        return None
    return cells


def _states_a_date(text: str, start: int, end: int) -> bool:
    """Whether [start, end) holds a value that starts as a date does with no birth label right before it (fr-dr:0): a
    date a field whose positions do not match may state as its own. Only _BIRTH_BEFORE is read here, never
    _birth_cells, which reads the positions this answers for."""
    return any(_BIRTH_BEFORE.search(text, max(0, at.start() - _BIRTH_REACH), at.start()) is None
               for at in _GAP_DATE.finditer(text, start, end))


def _column(text: str, rows: '_Rows', ls: int, le: int, cell_start: int, label_end: int, cell_tail: int):
    """For a label that is a whole cell of an aligned header row: the cell at its position in the row below, or - when
    the row below has another number of cells - _UNPLACED where that row states a date and _NO_VALUE where it states
    none (fr-dr:0); None when the label heads no aligned column (it is not one cell's only text, or runs across two
    cells)."""
    cells = _header_row(text, rows, ls, le)
    if cells is None:
        return None
    k = bisect.bisect_left(cells, (cell_start, -1))
    if k >= len(cells) or cells[k][0] != cell_start or label_end > cells[k][1] \
            or not _blank_to(text, cell_tail, cells[k][1]):
        return None
    row = rows.below(le)
    values = rows.aligned(*row) if row is not None else []
    if len(values) == len(cells) and _under_their_heads(cells, ls, values, row[0]) \
            and all(_line_label(text, *head) not in ('dos', 'birth') or _date_alone(text, *value)
                    for head, value in zip(cells, values)):
        return values[k]  # fr-dr:1: and every date or birth label's column holds a date alone, as a stack's place does
    return _UNPLACED if row is not None and rows.states_a_date(*row) else _NO_VALUE


def _under_their_heads(cells: list[tuple[int, int]], ls: int, values: list[tuple[int, int]], rs: int) -> bool:
    """Whether each value cell of a row lies under its own head (the final refutation, fr-dr:1): it overlaps the columns
    from its head's start to the next head's start (the last head's run to the line's end). A cell split at a double
    space ("Synthetic,  Alex" under "Patient") with a cell left empty matches the header's count while every value after
    it stands under another head: counted, the date-of-service column read the date of birth."""
    for j, (vs, ve) in enumerate(values):
        head = cells[j][0] - ls
        upto = cells[j + 1][0] - ls if j + 1 < len(cells) else None
        if ve - rs <= head or (upto is not None and vs - rs >= upto):
            return False
    return True


def _line_label(text: str, ls: int, le: int) -> Optional[str]:
    """'dos' | 'birth' | 'other' when the line holds nothing but a label ("DOB", "Date of service:", "Patient:")."""
    s, e = _strip_span(text, ls, le)
    if not s < e <= s + 64:
        return None
    m = _LABEL_LINE.fullmatch(text, s, e)
    return None if m is None else 'dos' if m.group('dos') else 'birth' if m.group('birth') else 'other'


def _opens_with_date(text: str, start: int, end: int) -> bool:
    return _VALUE_DATE_START.match(text, _strip_span(text, start, end)[0], end) is not None


def _date_alone(text: str, start: int, end: int) -> bool:
    """Whether the line [start, end) holds a date-shaped value and nothing else but a clock or a full stop (fr-dr:1): a
    stacked date or birth label's place holds one, and no other label's place does."""
    s, e = _strip_span(text, start, end)
    if not _opens_with_date(text, s, e):
        return False
    run = _VALUE_TOKEN.match(text, s, e)
    if run is None:
        return False
    pos = run.end()
    if pos < e and _GLUED.match(text, pos):
        pos = _NON_SPACE.match(text, pos, e).end()
    pos = _CLOCK_AFTER.match(text, pos, e).end()
    if pos < e and text[pos] == '.':
        pos += 1
    return _blank_to(text, pos, e)


def _place_fits(text: str, kind: str, start: int, end: int) -> bool:
    """Whether a stack's value line fits its label's kind (fr-dr:1): a date or birth label's place holds a date alone,
    any other label's place holds no date alone - a heading counted as a label ("PATIENT INFORMATION:") or a findings
    line counted as a value ("1.5 cm ...", "3/4 of the colon ...") shifts a date into a place of the other kind."""
    return _date_alone(text, start, end) == (kind != 'other')


def _stacked_value(text: str, rows: '_Rows', ls: int, le: int):
    """For a label alone on its line: (the line holding its value, whether read by position) - the value line at the
    label's place in the run of value lines under a stack of label-only lines, or the next line when it opens with a
    date - else None; when the stack's values cannot be placed, _UNPLACED where a date stands at a date or birth label's
    place and _NO_VALUE where none does (fr-dr:0) - for a date label last in a stack whose every label has its value
    line, where a date stands at any place (df-d:0)."""
    up, cur = [], ls
    for _ in range(STACK_REACH + 1):
        line = rows.above(cur)
        if line is None or _line_label(text, *line) is None:
            break
        up.append(line)
        cur = line[0]
    down, cur = [], le
    for _ in range(STACK_REACH + 1):
        line = rows.next_line(cur)
        if line is None or _line_label(text, *line) is None:
            break
        down.append(line)
        cur = line[1]
    if len(up) > STACK_REACH or len(down) > STACK_REACH:
        return _NO_VALUE
    lines = up[::-1] + [(ls, le)] + down
    here = len(up)
    kinds = [_line_label(text, *line) for line in lines]
    if len(lines) > 1:
        values, line = [], rows.below(lines[-1][1])
        while line is not None and len(values) < len(lines) and _line_label(text, *line) is None:
            values.append(line)
            line = rows.next_line(line[1])
        if len(values) == len(lines) and all(_place_fits(text, kind, *values[i]) for i, kind in enumerate(kinds)):
            return values[here], True
        other = 'birth' if kinds[here] == 'dos' else 'dos'
        if here != len(lines) - 1 or other in kinds:
            # fr-dr:0: "DOB:" / "Date of service:" over "10/14/2026" alone states a date whose place cannot be told
            return _UNPLACED if any(kind != 'other' and rows.states_a_date(*values[i])
                                    for i, kind in enumerate(kinds[:len(values)])) else _NO_VALUE
        if kinds[here] != 'birth' and len(values) == len(lines):
            # the differential round, df-d:0: every label has its value line and the places do not fit - another
            # label's place holds a date ("Patient DOB:", "Referral date:", "Date signed:" over theirs), or the date
            # label's holds a date and more ("10/14/2026 (done)") - so the line right below the date label is the FIRST
            # label's place, never its own: read, it gave the date of birth or the referral date as the label's value
            # (a member's 1998-01-01 taken and sent) or a name (silent: another labelled date sent). A date anywhere in
            # the values is asked, the label alone kept; also for a date label of the 'other' kind ("Date of Service
            # (DOS):").
            return _UNPLACED if any(rows.states_a_date(*value) for value in values) else _NO_VALUE
    row = rows.below(le)  # one label above its value, or the last of labels of another kind: the next line
    return (row, False) if row is not None and _opens_with_date(text, *row) else None


def _joined(text: str, rows: '_Rows', label_start: int, label_end: int):
    """A birth label joined to the date-of-service label in one header ("DOB / Date of Service:", "Date of Birth &
    DOS:", "Visit Date & Date of Birth:"): (the separator's end, the label's own value runs, the birth value runs), by
    position - two names, two values in their order; otherwise the label states no value and every value may be the
    date of birth. None when no birth label is joined to it."""
    ls, le = rows.line(label_start)
    before = _JOINED_BEFORE.search(text, max(ls, label_start - 48), label_start)
    after = None if before is not None else _JOINED_AFTER.match(text, label_end, le)
    if before is None and after is None:
        return None
    tail = _LABEL_TAIL.match(text, label_end if before is not None else after.end())
    sep_end = tail.end('sep') if tail.group('sep') not in (None, '|') else tail.start()
    end = _field_end(text, tail.end(), le) if tail.end() < le else tail.end()
    runs, pos = [], tail.end()
    while pos < end and len(runs) < 3:
        run = _first_value(text, pos, end, births=False)
        if run is None:
            break
        runs.append(run)
        pos = run[1]
    own = 1 if before is not None else 0
    if len(runs) == 2:
        return sep_end, (runs[own],), (runs[1 - own],)
    return sep_end, (), tuple(runs)


@functools.lru_cache(maxsize=16)
def _birth_cells(text: str) -> frozenset:
    """Where a date of birth starts whose birth label is not right before it (rule N2, "any row"): the cell under a
    birth label heading a table column ("Patient | DOB | Date of Service" above "Synthetic, Alex | 01/01/1998 |
    10/14/2026"), or an aligned column ("DOB            Date of Service" above "01/01/1998     10/14/2026"); the value
    line at a birth label's place in a stack, or the line under a birth label alone on its line when it opens with the
    value ("Date of birth:" above "01/01/1998"); the value at a birth label's place in a joined header ("DOB / Date of
    Service: 01/01/1998 / 10/14/2026"). One pass over the birth labels and one over the date labels; each line's cells
    and the row under it are read once (_Rows)."""
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
            continue
        column = _column(text, rows, ls, le, m.start(), m.end(), tail)
        if column is None and _blank_to(text, ls, m.start()) and _blank_to(text, tail, le):
            stacked = _stacked_value(text, rows, ls, le)  # the birth label alone on its line
            column = stacked[0] if isinstance(stacked, tuple) else None
        if isinstance(column, tuple):  # a value placed by position (never _NO_VALUE or _UNPLACED)
            value = _first_value(text, column[0], min(column[1], column[0] + VALUE_REACH), births=False)
            if value is not None:
                found.add(value[0])
    for m in DATE_LABEL.finditer(text):
        joined = _joined(text, rows, m.start('label'), m.end('label'))
        if joined is not None:
            found.update(run[0] for run in joined[2])
    return frozenset(found)


def _is_birth(text: str, start: int) -> bool:
    """Whether the date starting at ``start`` is a date of birth (rule N2): its birth label is right before it, in any
    bracket, or heads its column, its row's place or the line above it (_birth_cells)."""
    return (_BIRTH_BEFORE.search(text, max(0, start - _BIRTH_REACH), start) is not None
            or start in _birth_cells(text))


# Refutation phase 2, P2DN rule N5: a read labelled date is the note's own only when it stands alone in the label's own
# FIELD - never read from the lines around it. After the date may come a clock, then the field's end: the end of the
# line (a full stop may close it), a row's cell bar, or the next field's label - a few words and a colon that is not a
# clock's, after a field break ("Date of service: 10/14/2026    Place of service: Office") or, written with a capital,
# one space after the date (a flattened header row: "DOS: 10/14/2026 DOB: 01/01/1998", "Date of service: 2026-10-06
# Place of service: Office" - the capitalised label one space after a value, as _opens_field reads one). Anything else
# in the field - a bracket ("Procedure date: 11/04/2026 (pending authorization)", "(cancelled)"), words ("11/04/2026
# pending Status: open") or another date - makes the date a question (dates:8: B3 and V1 sent the planned 11/04). The
# structure only, never a word list; possessive runs, each date reads only what follows it up to the next label.
_CLOCK_AFTER = cues.rx(_CLOCK)
# P2DN's fix round, issue 2 (the label's field runs to the next field's LABEL): the words right before the next colon
# are that label only when they are one label - one to four words, no full stop, comma or semicolon ending a word before
# the last ("Pending authorization. Status:", "Not yet performed. Indication:"), no bracket but a format after the last
# ("DOB (mm/dd/yyyy):"), and written as a label is: one word, or a capitalised first word with no capitalised word after
# a word of its own ("Place of service", "Place of Service", "Referring physician"). Where the words may be the date's
# field's own and a label's - "Cancelled Status:", "pending authorization Status:", "Patient Name:" - where the label
# starts cannot be told, and the date is asked (the date's field held "Cancelled", and the planned or cancelled 11/04
# was documented and sent). The structure of the label only, never a word list: connecting words ("of", "and") are the
# grammar a label is written with.
_NEXT_FIELD = re.compile(r"(?P<words>[A-Za-z][A-Za-z0-9.,;'’/&#-]*+(?: [A-Za-z0-9#][A-Za-z0-9.,;'’/&#-]*+){0,3}+)"
                         r"(?:[ \t]*+\([^()\n]{1,20}+\))?+[ \t]*+[:=](?!\d)")
_CONNECTOR = re.compile(r'(?:of|and|or|for|the|to|in|on|at|by|per|with)', re.I)


def _one_label(words: list[str]) -> bool:
    """Whether the words before the next field's colon are one label (rule N5, P2DN's fix round, issue 2)."""
    if any(word[-1] in '.,;' for word in words[:-1]):
        return False  # a sentence or a list runs on into the label
    if len(words) == 1:
        return True
    if not words[0][0].isupper():
        return False
    return all(not word[0].isupper() or _CONNECTOR.fullmatch(word) or _CONNECTOR.fullmatch(before)
               for before, word in zip(words, words[1:]))


def _alone_in_field(text: str, date_end: int, line_end: int) -> bool:
    """Whether a read labelled date ending at ``date_end`` is alone in its field (rule N5; ``line_end``: its line's)."""
    pos = _CLOCK_AFTER.match(text, date_end, line_end).end()
    rest = _BLANKS.match(text, pos, line_end).end()
    if rest >= line_end or text[rest] == '|' or (text[rest] == '.' and _blank_to(text, rest + 1, line_end)):
        return True  # the line's end (a full stop may close it) or a row's cell bar
    gap = text[pos:rest]
    if not ('\t' in gap or len(gap) > 1 or (gap == ' ' and text[rest].isupper())):
        return False  # no field break, and no capitalised label one space after the date: the field runs on
    label = _NEXT_FIELD.match(text, rest, line_end)
    return label is not None and _one_label(label.group('words').split(' '))


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
    is passed over (rule N2: it is no candidate's value) unless ``births``."""
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


# Another field's label inside a label's value field ("DOB:", "MRN:", "Referral date:"): words and a colon that is not a
# clock's.
_NEXT_LABEL = re.compile(r"(?<![\w/.-])[A-Za-z][A-Za-z .'’/()#&-]{0,40}?[ \t]*+[:=](?!\d)")


def _value_extent(text: str, start: int, end: int) -> Optional[tuple[int, int]]:
    """The label's own value in its value field [start, end): the first date-shaped run (_first_value) before another
    field's label, when it OPENS the field (after blanks); that part whole when it has a digit and no date-shaped run;
    None when the field states no date of its own (rule N2). Refutation phase 2, dates:0: "DOS: DOB: 01/01/1998 MRN:
    0000", "Date of Service: Date of Birth: 01/01/1998" made the date of birth the label's value, so a member's
    1998-01-01 agreed with it and was sent. A field that opens with another field's label or whose only dates are dates
    of birth ("DOS: DOB/Age 01/01/1998", "Visit Date: TBD DOB (age) 01/01/1998", "DOS: N/A Referral date: 10/13/2026";
    the P2DATES skeptic's sk:3 and sk:4) states no date. A label's own value opens its field: a date after other words
    is not certainly its value ("see 10/20/2026" - only a word list could tell "see" from "TBD"), so no member date
    agrees with it. The final refutation, fr-dr:0: such a field still STATES a date - "rescheduled to 10/14/2026",
    "approx. 10/14/2026", "~10/14/2026", a date-shaped run that is no date of birth after other words - and is
    _UNPLACED: asked, the label alone kept (read as stating none, it never spoke, and "Procedure date: 10/07/2026"
    beside it was documented and sent). A number that is no date ("MRN 0000") states none."""
    other = _NEXT_LABEL.search(text, start, end)
    stop = other.start() if other is not None else end
    start = _BLANKS.match(text, start, stop).end()
    found = _first_value(text, start, stop)
    if found is not None and found[0] == start:
        return found
    # fr-dr:0: a date the field states after other words - wherever a date starts that is no date of birth, also where
    # a number before it glues to it in one run ("approx 2 10/14/2026")
    if any(not _is_birth(text, at.start()) for at in _GAP_DATE.finditer(text, start, stop)):
        return _UNPLACED
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
    # P2DN's fix round, issue 4: a label heading a column of a space- or tab-aligned header row reads the cell at its
    # position in the row below, never the row's first value; a label alone on its line in a stack of labels reads the
    # value line at its place (_stacked_value). Where the positions do not match no value is its own: it states no date
    # (_NO_VALUE), or - where a date stands there - a date it cannot place (_UNPLACED, the final refutation's fr-dr:0).
    column = _column(text, rows, line_start, line_end, m.start(), m.end(),
                     tail.end('sep') if sep is not None else m.end())
    if column is not None:
        if column is _NO_VALUE or column is _UNPLACED:
            return column
        if column[1] - m.start() > GAP_REACH or not _DIGIT.search(text, *column):
            return _NO_VALUE
        return column[0], column[1], True
    # Rule N3 (P2DN's fix round, issue 6): a date-of-service FIELD - a label with its separator, or alone on its line -
    # that states no date is kept as evidence that reads no date (_NO_VALUE): its value after an alignment gap ("DOS:
    # DOB: 01/01/1998" written with a field break), a value with no digit ("Date of service: N/A"), a label alone on its
    # line over another field ("Date of service:" over "DOB: 01/01/1998") or over nothing. Each kept nothing, so a
    # member's 1998-01-01 was taken and sent, and 45385 excluded against it. A label in prose has no field (None).
    if pos < line_end and (sep not in (None, '|') or ('\t' not in gap and '  ' not in gap)):
        end = _field_end(text, pos, line_end)
        if sep is None and not _VALUE_DATE_START.match(text, pos, max(end, pos)):
            return None
        if _DIGIT.search(text, pos, end):
            return pos, end, False
        if sep != '|':
            return None if sep is None else _NO_VALUE
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
            return _NO_VALUE  # N3: a column heading with no cell below
        start, end = _strip_span(text, *cells[col])
        if end - m.start() > GAP_REACH or not _DIGIT.search(text, start, end):
            return _NO_VALUE  # N3: its cell states no date
        return start, end, True
    if pos < line_end:
        return None
    if _blank_to(text, line_start, m.start()):
        stacked = _stacked_value(text, rows, line_start, line_end)
        if stacked is _UNPLACED:
            return _UNPLACED  # fr-dr:0: a stack whose values cannot be placed, a date at a date or birth label's place
        if stacked is None or stacked is _NO_VALUE:
            return _NO_VALUE  # N3: a label alone on its line whose value is on no line below
        (start, end), positional = stacked
        return start, _field_end(text, start, end), positional
    row = rows.below(line_end)
    start = _strip_span(text, *row)[0] if row is not None else None
    if start is None or not _VALUE_DATE_START.match(text, start, row[1]):
        return None if sep is None else _NO_VALUE  # N3: a field ending its line, its value on no line below
    return start, _field_end(text, start, row[1]), False


def _service_dates(text: str, lay: Layout) -> tuple[_Candidate, ...]:
    """Every date candidate outside a plan or history section (refutation round 2, rule A): the labelled dates of
    service, whatever their reading or form, and the dated titles near the top (_title_candidates)."""
    found = []
    read = set()
    rows = _Rows(text)
    for m in SERVICE_DATE.finditer(text):
        read.add(m.start())
        if lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        joined = _joined(text, rows, m.start('label'), m.end('label'))
        if joined is not None:  # P2DN's fix round, issue 3: a birth label joined to the label
            found.append(_joined_candidate(text, m.start('label'), m.end('label'), joined))
            continue
        value = date_from_match(m)
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.start('date'), m.end(), value)
        # rule N5 (refutation phase 2, P2DN): the date is the note's own only when it stands alone in its own field;
        # rule N7 (P2DN's fix round, issue 8): and only when it is written as the installed revision reads one
        found.append(_Candidate(_span(text, start, m.end()), value.isoformat() if value else None, 'label',
                                _READING[kind], 'read' if value else 'invalid',
                                alone=_alone_in_field(text, m.end(), rows.line(m.start())[1]),
                                installed=_installed_form(text, m)))
    for m in DATE_LABEL.finditer(text):
        # refutation r1, context-3, and round 2, c2:8: a labelled date the reader does not read is documented date text
        if m.start() in read or lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        joined = _joined(text, rows, m.start('label'), m.end('label'))
        if joined is not None:
            found.append(_joined_candidate(text, m.start('label'), m.end('label'), joined))
            continue
        where = _label_value(text, m, rows)
        if where is None:
            continue
        if where is _NO_VALUE or where is _UNPLACED:  # P2DN's fix round, issue 4: a header's positions do not match
            # it states no date ('empty'), or a date it cannot place ('unread': asked, the label alone - fr-dr:0)
            kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.end(), m.end(), None)
            tail = _LABEL_TAIL.match(text, m.end())
            label_end = tail.end('sep') if tail.group('sep') not in (None, '|') else m.end('label')
            found.append(_Candidate(_span(text, start, label_end), None, 'label', _READING[kind],
                                    'empty' if where is _NO_VALUE else 'unread'))
            continue
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), where[0], where[1], None)
        # refutation round 3, sk:1: the evidence is the label and its own value, never the text beside it; and a field
        # that states no date of its own (rule N2: another field opens it, or its only dates are dates of birth) is kept
        # as evidence that reads no date - the label alone, never its field, whose dates are not its own - so a member
        # date is held unless another candidate states it (rule N3; the P2DATES skeptic's sk:3: dropped with nothing
        # left behind, "Date of Service: Referral date: 10/13/2026" let a member's 1998-01-01 be taken and sent). A
        # field whose date comes after other words is unread evidence up to that date (fr-dr:0, _value_extent).
        extent = _value_extent(text, where[0], where[1])
        if extent is None or extent is _UNPLACED:  # it states no date ('empty'), or one it cannot place ('unread')
            tail = _LABEL_TAIL.match(text, m.end())
            label_end = tail.end('sep') if tail.group('sep') not in (None, '|') else m.end('label')
            found.append(_Candidate(_span(text, start, label_end), None, 'label', _READING[kind],
                                    'empty' if extent is None else 'unread'))
            continue
        value_start, value_end = extent
        if where[2]:  # a table column: the label's cell and its value's cell, never the cells between
            span, extra = _span(text, start, m.end('label')), (_span(text, value_start, value_end),)
        else:
            span, extra = _span(text, start, value_end), ()
        found.append(_Candidate(span, None, 'label', _READING[kind], 'unread', extra))
    return tuple(found) + _title_candidates(text, lay)


_TIME_WORD = cues.rx(r'\btime\b')


def _installed_form(text: str, m: re.Match) -> bool:
    """Whether a SERVICE_DATE match is written as the installed revision 057a7d398 reads a labelled date (rule N7): its
    label names no time, its separator is no cell bar, and its date is no day-first one ("14 Oct 2026",
    "14-Oct-2026")."""
    return (m.group('dd') is None and _TIME_WORD.search(text, m.start('label'), m.end('label')) is None
            and '|' not in text[m.end('label'):m.start('date')])


def _joined_candidate(text: str, label_start: int, label_end: int, joined) -> _Candidate:
    """A date-of-service label joined to a birth label in one header (P2DN's fix round, issue 3: "DOB / Date of Service:
    01/01/1998" documented the date of birth and sent it with no member at all): its own value is the one at its place
    in the header (_joined), kept beside the label - never the date of birth - and never the note's own date (two
    fields share the label's field, rule N5); with no value of its own it is kept as evidence that reads no date. A
    header stating values it cannot place (one value under two names: "DOB / Date of Service: 10/14/2026") states a
    date: asked ('unread'), the label alone - the value may be the date of birth - never silent (the final refutation,
    fr-dr:0: silent, it let "Procedure date: 10/07/2026" beside it be sent, where 057a7d398 sent no date)."""
    sep_end, own, births = joined
    if not own:
        kind, start = _labelled_kind(text, label_start, label_end, label_end, label_end, None)
        return _Candidate(_span(text, start, max(sep_end, label_end)), None, 'label', _READING[kind],
                          'unread' if births else 'empty')
    value_start, value_end = own[0]
    full = FULL_DATE.fullmatch(text, value_start, value_end)
    day = date_from_match(full) if full is not None else None
    form = 'read' if day else ('invalid' if full is not None else 'unread')
    kind, start = _labelled_kind(text, label_start, label_end, value_start, value_end, day)
    return _Candidate(_span(text, start, max(sep_end, label_end)), day.isoformat() if day else None, 'label',
                      _READING[kind], form, (_span(text, value_start, value_end),), alone=False)


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
    differs) and 'unplaced' otherwise; a later qualified one ("Next visit: ...") is another occurrence's: 'aside'. No
    title is ever the date (refutation phase 2, rule N1): its reading says only whether it speaks against the note's
    own labelled date, and every title is the evidence of a date asked when no label gives one."""
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
        out.append(_Candidate(span, value, source, reading, form))
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


# The start of a date after a service's name (refutation round 3, sk:1; "#2" or a clock is none).
_GAP_DATE = cues.rx(r'(?<![\w/.-])(?:' + _VALUE_DATE_START.pattern + r')')


# A letter's subject line opening a line ("Re: ", "Regarding: ", "Subject: "): the structure is the subject line naming
# the encounter the letter is about; these labels are its vocabulary.
_SUBJECT_FIELD = cues.rx(r'[ \t]*+(?:re|regarding|subject|subj)\.?[ \t]*+:[ \t]*+')


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
    Refutation round 3, sk:6 ("Date: 10/27/2026" won over "Procedure: Colonoscopy on 10/14/2026", "Regarding your
    colonoscopy of 10/14/2026" or a sentence ending "... colonoscopy on 10/14/2026.", so a letter's date was sent and a
    snare polypectomy done on 10/14 excluded as historical) is closed by rule N1: a bare "Date:" line is never the
    date, so beside it such a line is evidence a member's answer may agree with."""
    m = _LINE_END_DATE.search(text, ls, le)
    if m is None or m.start() - ls > 80:
        return None
    names = [name for p in _THIS_SERVICE for name in p.finditer(text, ls, m.start())]
    if not names:
        return None
    field = _SUBJECT_FIELD.match(text, ls, m.start())
    if field is not None and any(p.search(text, field.end(), m.start()) for p in _THIS_SERVICE):
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
    # Refutation phase 2, rule N2 (dates:2, interplay:0): the line's own date is its ONLY date after the service's name
    # that is no date of birth. Round 3 took the first date after the name whenever a field or a date stood between,
    # so in "Procedure: EGD  Patient: Alex Synthetic  DOB: 01/01/1998  Date: 10/14/2026" or "Re: Colonoscopy -
    # Synthetic, Alex (DOB 01/01/1998) - 10/14/2026" the date of birth was the line's value: a member's 1998-01-01
    # agreed with it and was sent, and the line's own 10/14 answer was held. A line with two such dates states none the
    # reader can tell ("Re: EGD referral 09/01/2026 10/14/2026"): it is kept, reading no date. Its evidence holds no
    # other date, so a member date agrees only with the line's own.
    # P2DN's fix round, issue 1 (a regression of that rule against a62a18c85): a date after ANOTHER field's label is that
    # field's, never the line's ("Procedure: Colonoscopy    Referral date: 10/13/2026", "Re: Colonoscopy - Signed:
    # 10/27/2026", "Visit Date: today Ordered: 10/13/2026"): the referral, order or signing date agreed with a member's
    # date, which was sent, and beside the note's own labelled 10/14 the subject line made it a question. Only a bare date
    # field ("Date:", "Date/Time:") or a date-of-service label after the service's name gives the line its date
    # (_other_field); a line whose dates are all other fields' or dates of birth states no date of the service.
    gap = name_end
    while gap < le and text[gap] in ' \t:,-–—':  # "Colonoscopy: 10/14/2026": the service's own field
        gap += 1
    runs, excluded, pos, unplaced = [], [], name_end, []
    for at in _GAP_DATE.finditer(text, name_end, le):  # the dates after the name ("#2" or a clock is none)
        run = _first_value(text, at.start(), le, births=False) if at.start() >= pos else None
        if run is None:
            continue
        pos = run[1]
        if _is_birth(text, run[0]):
            label = _BIRTH_BEFORE.search(text, max(start, run[0] - _BIRTH_REACH), run[0])
            excluded.append((run, label.start() if label else run[0]))
            continue
        other = _other_field(text, gap, run[0])
        if other == _AFTER_VALUE:
            unplaced.append(run)
        elif other is not None:
            excluded.append((run, other))
            continue
        runs.append(run)
    if unplaced:  # fr-dr:3: a date after another field's value ended - the line states a date it cannot place: it is
        # asked (speaking against the labelled date, as a line with two dates does) and reads no date - its text before
        # the first of its dates - so no member date agrees with it alone
        cut = _strip_span(text, start, min([r[0] for r in runs] + [label for _, label in excluded]))
        return _Candidate(_span(text, *cut), None, source, reading, 'unread') if cut[0] < cut[1] else None
    if not runs:  # the line's only dates are dates of birth or other fields' ("Colonoscopy DOB: 01/01/1998")
        # kept as evidence that reads no date - its text before the first of those dates - never dropped: dropped, the
        # document was left no dated text and any member date was taken, a date of birth too ("Exam: Colonoscopy
        # Patient DOB: 01/01/1998 Exam date: 10/14/2026", "Exam date" no label of the closed list; 36 fuzz texts)
        if not excluded:
            return None
        cut = _strip_span(text, start, min(label for _, label in excluded))
        return _Candidate(_span(text, *cut), None, source, reading, 'empty') if cut[0] < cut[1] else None
    if len(runs) > 1:
        cut = _strip_span(text, start, min([r[0] for r in runs] + [label for _, label in excluded]))
        return _Candidate(_span(text, *cut), None, source, reading, 'unread')
    own = runs[0]
    full = FULL_DATE.match(text, own[0], own[1])
    whole = full is not None and full.end() == own[1]
    day = date_from_match(full) if whole else None
    form = 'read' if day else ('invalid' if whole else 'unread')
    value = day.isoformat() if day else None
    before = sorted((run, label) for run, label in excluded if run[1] <= own[0])
    if not before:
        return _Candidate(_span(text, start, own[1]), value, source, reading, form)
    # a date of birth or another field's date between the name and the line's own date: the evidence is the line around
    # it, never that date
    head = _strip_span(text, start, before[0][1])
    tail = _strip_span(text, before[-1][0][1], own[1])
    spans = [_span(text, *s) for s in (head, tail) if s[0] < s[1]]
    return _Candidate(spans[0], value, source, reading, form, extra=tuple(spans[1:]))


# P2DN's fix round, issue 1: the field a date on a dated line follows - the last colon (not a clock's) between the
# service's name and the date, its label running back to the field's start (a field break, a cell bar, another field's
# colon, a comma, a semicolon or a spaced dash). Only a bare date field or a date-of-service label is the line's own.
_GAP_FIELD = re.compile(r'(?<!\d)[:=]|[:=](?!\d)')
_FIELD_START = re.compile(r'[ \t]{2,}+|\t|[:=|,;]|[ \t][-–—][ \t]')
# The final refutation, fr-dr:2: a bracket after the field's "date" or date-of-service label keeps the field the line's
# own date field only when it holds the date's FORMAT ("Date (mm/dd/yyyy):", "DOS (YYYY-MM-DD):") or "(DOS)". Any other
# bracket names another event ("Date (signed):", "Date (dictated):", "DOS (planned):"), so the field is another field's
# and its date never the line's: read as the line's own, the signing or planned date made the note's labelled 10/14 a
# question, and a member's 10/27 or 11/04 was taken as a listed documented value and sent. A format is the grammar of a
# date's parts (letters m, d and y with separators), never a word list.
_DATE_FORMAT = r'(?:DOS|[mdy]{1,4}+(?:[ \t]*+[-/.][ \t]*+[mdy]{1,4}+){1,2}+)'
_LINE_DATE_FIELD = cues.rx(r'(?:date' + _DATE_TIME + r'|' + _DATE_LABEL + r')(?:[ \t]*+\([ \t]*+' + _DATE_FORMAT
                           + r'[ \t]*+\))?+')


# The final refutation, fr-dr:3: where another field's VALUE ends before a later date - a semicolon, a comma, a spaced
# dash, a field break, a bracket it does not open, or the field's own date (_GAP_DATE).
_VALUE_END = re.compile(r'[;,]|[ \t][-–—][ \t]|\t| {2,}')
_AFTER_VALUE = -1  # _other_field: the date follows another field whose value had ended - neither that field's nor
# certainly the line's own


def _value_ended(text: str, start: int, end: int) -> bool:
    """Whether a field's value that starts at ``start`` ends before ``end`` (fr-dr:3; a dated line is short, so the
    bracket scan reads at most its own line)."""
    if _VALUE_END.search(text, start, end) or _GAP_DATE.search(text, start, end):
        return True
    depth = 0
    for ch in text[start:end]:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            if not depth:
                return True  # the field stood inside a bracket that closes here
            depth -= 1
    return False


def _other_field(text: str, gap: int, start: int) -> Optional[int]:
    """Where the label of the field a date at ``start`` follows begins, when that field is another one than the line's
    own date field (P2DN's fix round, issue 1); None when no field label stands between ``gap`` (after the service's
    name) and the date, or the label is a bare date field or a date-of-service label. _AFTER_VALUE when that other
    field's value ended before the date (the final refutation, fr-dr:3: "Re: Colonoscopy - Referral date: 10/13/2026;
    performed 10/21/2026" gave the performed date to the referral field, so the subject line was silenced and the
    labelled 10/14 it contradicts was sent): the date is not that field's, and the line states it in a place this
    service cannot read - it is asked, never the line's own value."""
    colon = None
    for colon in _GAP_FIELD.finditer(text, gap, start):
        pass
    if colon is None:
        return None
    lo = gap
    for brk in _FIELD_START.finditer(text, gap, colon.start()):
        lo = brk.end()
    s, e = _strip_span(text, lo, colon.start())
    if s >= e or _LINE_DATE_FIELD.fullmatch(text, s, e) is not None:
        return None
    return _AFTER_VALUE if _value_ended(text, colon.end(), start) else s


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
EVIDENCE_DATE_NOTE = ('A dated title, a "Date:" line, a dated line naming the service or a letter\'s subject line is kept '
                      'as evidence; it is never taken as the date of service by itself.')
FIELD_DATE_NOTE = ('A labelled date of service has other text in its field (a bracket or words after the date), so it is '
                   'not taken as the date of service by itself.')
FORM_DATE_NOTE = ('A labelled date of service is written in a form this release reads but does not send by itself (a '
                  'day-first date such as "14 Oct 2026", a label naming the time, or a table row), so it is asked; a '
                  "member's answer with that date is taken.")
EMPTY_DATE_NOTE = ('Dated text states no date of its own (an empty or non-date date-of-service field, or a line whose '
                   "dates are another field's or a date of birth), so a member's date is held until the document "
                   'states it.')


def _service_date_fact(found: tuple[_Candidate, ...]) -> Fact:
    """The service date fact (refutation round 2, rules A and B). The note's own labelled dates, when they agree, are the
    date - never a dated title (rule N1 below). They give the date only when every candidate that could speak for this
    note's date agrees with it: a labelled date this service cannot place or that does not stand alone in its field, the
    note's own dated title, a qualified first title and a "Re:" line. A difference is a conflict with every side kept
    (both sides listed when all are read), never a silent choice of the weaker or the stronger source (c2:1: a planned
    procedure's labelled date was taken over the report's title, sent, and an act done that day excluded against it).
    With no usable own date, every candidate is kept as evidence and the date is asked: a member value must agree with
    it (merge_user_values).

    Every set here is kept by identity, never by a list membership test: that compared each pair of candidates, so
    the fact was quadratic in the note's labelled dates (refutation round 3, sk:3: 'DOS: 10/14/2026' 24,000 times, under
    the paste cap, overran the analyze stage's 60 s, and 12,000 a member's POST /context).

    Refutation phase 2 (P2DN) narrows the own date by its SOURCE, never by vocabulary:
    - rule N1: a document date reaches the request only from a date-of-service label's own value. A dated title, a bare
      "Date:" or "Date/Time:" line (clocked or not), a dated line naming the service and a letter's subject line are
      evidence only: beside an own labelled date they question it when they differ, as before; as the only dated text
      they are the evidence of a date asked (a dateless request, a question for the member) - as the installed
      revision 057a7d398 sent no date for those shapes. Round 3 took them as the note's own: a fax's "Date/Time:
      10/27/2026 14:30", a letter's "Date:" over the encounter line it names and "Cardiology consultation: 10/09/2026"
      over a colonoscopy were sent, and the snare polypectomy done on 10/14 excluded against them (dates:1, 3, 5);
    - rule N4: only a label READ as the note's own ('own': the closed list of labels, at most with the name of a service
      this release codes) is ever the date; a label carrying words the reader cannot place ('unplaced': "Initial visit
      date", "Cancelled procedure date") is asked and still speaks against an own date, as before;
    - rule N5: a read labelled date stands alone in its own field (_Candidate.alone, _alone_in_field); one followed by a
      bracket or words there ("Procedure date: 11/04/2026 (pending authorization)", dates:8) is asked and speaks against
      an own date, its date kept as evidence a member's answer may agree with."""
    labels = [c for c in found if c.source == 'label']
    own = [c for c in labels if c.reading == 'own' and c.form == 'read' and c.alone and c.installed]
    # rule N7 (P2DN's fix round, issue 8): with no own date written as the installed revision reads one, the labelled
    # dates that would be the note's own but for their form lead the question as an own date leads the fact - never sent
    # (asked), but every speaking candidate is measured against them and the member's answer must agree with them (asked
    # by its table row, svc-18's "Date of service | 2026-10-05" had left a history line's 2021-08-17 - a prior colonoscopy
    # - a date the member's answer agreed with)
    withheld = [] if own else [c for c in labels if c.reading == 'own' and c.form == 'read' and c.alone]
    lead = own or withheld
    own_ids = {id(c) for c in lead}
    # rule N3 (P2DN's fix round, issue 6): a field that states no date never speaks against the note's own date (a
    # PDF form's blank "Date of service:" beside its filled "dos: 2026-10-21" asked the date it states); with no own date
    # it is the evidence of the date asked, holding every member date
    speaks = [c for c in labels if id(c) not in own_ids and c.reading in ('own', 'unplaced') and c.form != 'empty']
    support = list(speaks)  # what joins the date's evidence when it agrees: as before, labels only
    speaks += [c for c in found if c.source != 'label' and c.reading in ('own', 'unplaced') and c.form != 'empty']
    values = {c.value for c in lead}
    unusable = [c for c in (speaks if lead else found) if c.form != 'read']
    note = ' '.join(text for present, text in (
        (any(c.form == 'invalid' for c in unusable), INVALID_DATE_NOTE),
        (any(c.form == 'unread' for c in unusable), UNREAD_DATE_NOTE),
        (any(c.form == 'empty' for c in unusable), EMPTY_DATE_NOTE),
        (not own and any(c.source == 'label' and c.form == 'read' and c.reading == 'own' and not c.alone for c in found),
         FIELD_DATE_NOTE),
        (not own and any(c.source == 'label' and c.form == 'read' and c.reading == 'own' and c.alone and not c.installed
                         for c in found), FORM_DATE_NOTE),
        (not own and any(c.source != 'label' and c.form == 'read' for c in found), EVIDENCE_DATE_NOTE),
        (not own and any(c.form == 'read' and c.reading in ('aside', 'other', 'unplaced') for c in found),
         UNPLACED_DATE_NOTE)) if present)
    if lead and len(values) == 1 and all(c.form == 'read' and c.value in values for c in speaks):
        fact = _fact('service_date', [(c.value, s) for c in lead + support for s in c.spans])
        return fact if own else Fact('service_date', None, 'missing', fact.evidence, FORM_DATE_NOTE)
    unread = tuple(s for c in unusable for s in _evidence_spans(c))
    if lead:
        fact = _fact('service_date', [(c.value, s) for c in lead + speaks if c.form == 'read' for s in c.spans])
        if not unusable:
            return fact
        return Fact('service_date', None, 'conflict', _sorted_spans(fact.evidence + unread), note)
    # with no date of the note's own every candidate is the evidence of the date asked; another occurrence's or another
    # document's dated label or title is quoted, never a date a member's answer agrees with (fr-di:3, _ElsewhereSpan)
    fact = _fact('service_date', [(c.value, s) for c in found if c.form == 'read' for s in _evidence_spans(c)])
    if not found:
        return fact
    return Fact('service_date', None, 'missing', _sorted_spans(fact.evidence + unread), note)


def _sorted_spans(spans) -> tuple[Span, ...]:
    return tuple(sorted(dict.fromkeys(spans), key=lambda s: (s.start, s.end)))


class _ElsewhereSpan(Span):
    """Evidence a member date never agrees with (the final refutation, fr-di:3): a dated label or title this reader
    itself reads as ANOTHER occurrence's ('aside': "Next procedure date: 11/04/2026", "... (scheduled)", "Last visit
    date") or another document's ('other': "Surgical pathology report: 10/17/2026"). Kept as evidence with no date of the
    note's own, a member's answer equal to its date was taken and sent - an office visit's next procedure date - while
    the correct date was held. It is quoted, stored and shown as any span is (the same fields, equal to the plain span it
    copies, plain JSON through to_jsonable); only _date_readings reads the difference. A dated service line is no such
    span: it is evidence of the service's own date (rule N1)."""

    def __eq__(self, other):
        return isinstance(other, Span) and (self.start, self.end, self.text) == (other.start, other.end, other.text)

    __hash__ = Span.__hash__


def _evidence_spans(c: _Candidate) -> tuple[Span, ...]:
    """A candidate's spans as the date's evidence: _ElsewhereSpan for a label or title read as another occurrence's or
    another document's (fr-di:3)."""
    if c.source in ('label', 'title') and c.reading in ('aside', 'other'):
        return tuple(_ElsewhereSpan(s.start, s.end, s.text) for s in c.spans)
    return c.spans


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
    beside a date of service ("DOS: 10/14/26 DOB: 01/01/1998", "Patient | DOB | Date of Service") is never one. The final
    refutation, fr-di:3: nor is a date only another occurrence's or another document's dated label or title states
    (_ElsewhereSpan) - its date is not the note's, as the fact's own note says."""
    values = set()
    for span in spans:
        if isinstance(span, _ElsewhereSpan):
            continue
        quoted = str(span.text)
        # refutation phase 2, rule N2: a date of birth is never read, wherever an evidence span holds one
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
