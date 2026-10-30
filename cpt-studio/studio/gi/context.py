"""Encounter context read from the document: service date, setting, billing
context and new/established patient status. See ARCHITECTURE.md section 5.2.

Only explicit statements count. Different documented values are a conflict
(value None, every statement kept as evidence), never a silent choice. A date
or setting written where a plan or history section governs it, or qualified as
previous / next / scheduled, describes another encounter and is not read; a
section governs only within its reach (gi3: _binding), and a label it no longer
governs speaks but is never the note's own by itself. Dated text the reader
does not read as the date, or cannot place, never supplies the date: it is kept
as evidence a member value must agree with. Only a date-of-service label's own
value is ever the date (refutation phase 2, P2DN): a dated title, a "Date:"
line or a dated line is evidence, and a date of birth is never read.
"""
from __future__ import annotations

import bisect
import functools
import itertools
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Optional

from studio.gi import cues
from studio.gi import sections as _sections  # gi3 dates: the section reader's own predicates (_binding)
from studio.gi.sections import ADDENDUM_HEADER, DOCUMENT_PART, HEADINGS, Layout, layout
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
# gi3 fix round 1 (dates-9): a label written with an em dash (U+2014), a full stop or a full-width colon (U+FF1A) before
# its date ("Date of service <em dash> 10/05/2026", "Date of service. 10/05/2026"; a word processor's dash, a
# sentence-style stop, an East Asian input's colon) left no candidate at all, so the fact said no date is documented and
# any member date was taken and sent. Its date is read, never as the note's own date by itself (_installed_form: the
# installed revision read none of the three) - it is asked, and a member's answer equal to it is taken.
_UNREAD_SEPARATOR = re.compile('[\u2014\uff1a.]')
_DATE_LABEL_SEP = r'\b[ \t]*+(?:\([ \t]*+DOS[ \t]*+\)[ \t]*+)?+[:#=\u2013\u2014\uff1a.|-]?+[ \t]*+'
SERVICE_DATE = cues.rx(r'(?<![\w/-])(?P<label>' + _DATE_LABEL + r')' + _DATE_LABEL_SEP
                       + r'(?P<date>' + _FULL_DATE + r')(?![\w/-])')
# gi3 dates, X3: the encounter's own date-of-service label broken by ONE line break between its words, as OCR and a
# narrow column break it ("Date of" / "service: 2026-10-06", "Date" / "of service: ...", "Service" / "date: ...",
# "Encounter" / "date: ..."): the first line holds the label's opening words and nothing after them, the next opens with
# the rest, its separator (never optional here, never a cell bar) and the date. Unread, the charge block's "Date of" /
# "service: 2026-10-06" was silent and the header's 2026-10-05 it contradicts was sent. Read only where nothing but
# blanks stands before the opening words and their line opens a sentence of its own (_broken_label_opens): a first line
# that continues prose ("... we confirmed the date of" / "service: ...") is never joined. Never the note's own date by
# itself (_installed_form: the installed revision never read a label broken over two lines) - it speaks, and is asked.
_BROKEN_LABEL = (r'(?:date' + _DATE_TIME + r'(?:[ \t]*+\n[ \t]*+of[ \t]++|[ \t]++of[ \t]*+\n[ \t]*+)(?:service|encounter)'
                 r'|(?:service|encounter)[ \t]*+\n[ \t]*+date' + _DATE_TIME + r')')
BROKEN_SERVICE_DATE = cues.rx(r'(?<![^\n \t])(?P<label>' + _BROKEN_LABEL + r')\b[ \t]*+(?:\([ \t]*+DOS[ \t]*+\)[ \t]*+)?+'
                              r'[:#=\u2013-][ \t]*+(?P<date>' + _FULL_DATE + r')(?![\w/-])')
# Date-shaped text this reader does not read as a date (refutation r1, context-3): a weekday before a date, a
# two-digit year, dashes, dots or year-first slashes, "20th of October". As a title's date it is documented date text a
# member value must agree with - never a gap a member value silently fills.
_WEEKDAY_NAME = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)'
_WEEKDAY = _WEEKDAY_NAME + r'\.?'
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
# The differential round, df-d:5: "b." one space or tab after a letter ("Alex Synthetic b. 01/01/1998", "part b.
# 10/21/2026") - the form c3c034a08 read as no birth label. It may be one, or a list's letter, and only the date's
# meaning could tell: its date stays no candidate's value and no member date's agreement (rule N2, fr-dr:5), but a dated
# line stating it is asked, never silent (_dated_service_line).
_WORD_B = re.compile(r'(?<=[A-Za-z][ \t])b\.')

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
    """False when the statement sits in a plan/history section (never the one the document's own follow-up title opens:
    gi3 dates, RC5), or its clause carries a planned/historical/cancelled cue or a negation before it."""
    sec = lay.section_at(start)
    if sec.kind in NOT_CURRENT_SECTIONS and sec.start != _title_start(text):
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
    # | 'beside' (it may be the date or another occurrence's: a qualifier stands beside it across a date of birth, df-d:4)
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
    # Fix round (dates lens, F1): why an own labelled date is asked though nothing qualifies it (_own_dates_in_doubt):
    # 'birth' - its date is the date the document gives as the patient's date of birth ('beside': never a member's
    # answer); 'part' - it stands in a later numbered part that documents no procedure ('unplaced'); 'order' - it is
    # earlier than a date the note reads as an earlier occurrence's ('unplaced'); gi3 dates, part 3: 'plan' - it stands
    # under a procedure heading right after the plan that documents no procedure ('unplaced').
    doubt: str = ''

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
_READING = {'own': 'own', 'unplaced': 'unplaced', 'another': 'aside', 'beside': 'beside'}


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


def _label_words(text: str, label_start: int, label_end: int, fields: bool = True) -> tuple[str, int]:
    """The label's own words before it ("Outside" in "Outside procedure date") and where they start: words joined by
    single spaces only, so a field break (two spaces, a tab), punctuation, a digit or the line start ends them - and a
    label that opens a field of its own has none (refutation round 2, c2:2). A label that opens its line in lower case
    continues the line above, as a wrapped line does ("Outside" above "procedure date: ...", c2:6). ``fields`` False
    reads the words before a label that opens a field of its own too (_measured_on: "Total Time on Date of Service")."""
    if fields and _opens_field(text, label_start, label_end):
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
    # The differential round, df-d:4: nor does a date of birth attach the qualifier - standing between it and the label,
    # between the date and it, or after it nearer to it than the date, it leaves the qualifier beside the date ('beside':
    # it speaks against another labelled date - asked - but is never a member's answer, as it may be another
    # occurrence's). Read as attached, the date was another occurrence's, which never speaks, and "Date of service:
    # 10/21/2026" in an addendum was sent where c3c034a08 asked.
    reading, beside = 'own', False
    for q in _OTHER_OCCURRENCE.finditer(text, lo, label_start):
        field = _qualifier_field(text, q.start(), q.end(), label_start, has_date)
        qualifier = DATE_QUALIFIER.fullmatch(q.group()) is not None
        if field == 'dated' or (field == 'else' and qualifier) or (field != 'else' and dated(q.end(), label_start)):
            reading = 'unplaced'
            continue
        if field == 'else':
            continue
        if not opens and not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[q.end():label_start])):
            if not other_dates(q.end(), label_start):  # here only a date of birth can stand between them
                return 'another'
            beside = True  # df-d:4
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
            after = other_dates(q.end(), hi)  # here only dates of birth (the dated ones were read above)
            if not other_dates(date_end, q.start()) and not (after and after[0].start - q.end() < q.start() - date_end):
                return 'another'
            reading, beside = 'unplaced', True  # df-d:4
            continue
        if qualifier:  # a history word across a field break does not place the date
            reading = 'unplaced'
    return 'beside' if beside and reading == 'unplaced' else reading


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
    if reading in ('another', 'beside'):  # df-d:4: 'beside'
        return reading, start
    if reading == 'unplaced' or (words and not _names_this_service(words, words + ' ' + text[label_start:label_end])):
        return 'unplaced', start
    # the owner's narrow source rule (2026-10-28): read again only here, and only ever moved to 'beside'
    if _another_occurrence_governs(text, label_start, label_end, date_start, date_end, value, start):
        return 'beside', label_start
    return 'own', label_start


# --- the narrow source rule (owner decision 2026-10-28, second round; ARCHITECTURE 5.2) -------------------------------
# Interpretation 28 left one family to the owner: a labelled date the text around it marks as ANOTHER occurrence's - a
# heading over its block ("Outside colonoscopy:" above "Facility: ..." above "Procedure date: 09/03/2026"), a title
# ("Cancelled colonoscopy" above the label) or a field on its row more than 80 characters before it ("Planned procedure:
# colonoscopy with ... Procedure Date: 11/04/2026") - was read as the note's own date, documented and sent, and an act
# done that day excluded against it. The owner ruled the narrow source rule: such a date is asked, never sent, and a
# member's answer equal to it is not taken (an addendum settles it); a neutral heading the reader cannot place
# ("Patient information:", "Recall:") changes nothing. It reads again only a label the installed reading reads as the
# note's own (_labelled_kind) and only moves it to 'beside' (_another_occurrence_governs): the label keeps speaking - the
# date is asked - and is quoted but never a member's answer (_ElsewhereSpan), so no candidate is silenced ('aside') and
# no date is created.
ROW_REACH = 400  # characters of a label's row read before it (the installed reading reads 80)
# The rule's vocabulary: the installed reader's (_OTHER_OCCURRENCE: the date qualifiers and the history words) and the
# act status the services reader reads (cues.CANCELLED_CLAUSE: cancelled, postponed, deferred, not done, called off, not
# started, no-show) - the reader's own closed class of status words, read as date qualifiers for the date only. Fix
# round (dates lens, F2): only a status word that says the dated occurrence did NOT happen on its date - an aborted
# procedure happened on its date ("Status: procedure aborted at the splenic flexure" is today's own status, and
# "Incomplete colonoscopy - aborted" today's own title), so "aborted" is no word of the rule.
_STATUS_WORDS = '|'.join('(?:' + pattern.pattern + ')' for name, pattern in cues.CANCELLED_CLAUSE if name != 'aborted')
_STATUS = cues.rx(_STATUS_WORDS)
_OCCURRENCE_WORDS = cues.rx(r'(?:' + _OTHER_OCCURRENCE.pattern + '|' + _STATUS_WORDS + ')')
# Fix round, F2: a heading's word that names another occurrence by itself ("Outside colonoscopy:", "Index procedure:",
# "Cancelled procedure:", "Postponed colonoscopy:"). The rest of the vocabulary may name something else in a heading -
# "Last name:", "Last updated:", "Balance due:", "Requested by:", "Cancellation policy:" - and governs a block only
# beside an occurrence noun or a coded service's name ("Last colonoscopy:", "Requested procedure:"):
# _heading_names_another.
_HEADING_OCCURRENCE = cues.rx(r'(?:outside|prior|previous(?:ly)?|earlier|index|cancel(?:l)?ed|postponed|deferred'
                              r'|rescheduled|scheduled|planned|next|upcoming|future|proposed|anticipated|tentative'
                              r'|not\s+done|called\s+off|not\s+(?:started|begun)|no[- ]show(?:ed)?'
                              r'|did\s+not\s+(?:show|arrive|present\s+for)|history\s+of|hx\s+of|h/o|s/p|status\s+post)')
# Fix round, F2: a status word answered as not having happened ("Cancelled: No", "Cancellation reason: N/A",
# "Cancelled? no."): the rest of its field label, then the answer alone in its field.
_STATUS_LABEL_REST = re.compile(r"[A-Za-z0-9 '’/()-]{0,40}?[ \t]*+[:=?](?!\d)")
_NO_ANSWER = cues.rx(r'[ \t]*+(?:none|n/?a|not[ \t]++applicable|no|nil)[ \t]*+\.?+[ \t]*+')
# ... or the first word of another field's value whose label names neither an occurrence nor a status ("Copay:
# deferred", "Payment: deferred"): that field's own status, never the dated occurrence's.
_VALUE_OF_FIELD = re.compile(r"(?<![A-Za-z0-9'’-])(?P<label>[A-Za-z][A-Za-z0-9 '’/()&-]{0,40}?)[ \t]*+[:=][ \t]*+\Z")
_STATUS_FIELD = cues.rx(r'\bstatus\b')


def _status_marks(text: str, start: int, end: int) -> bool:
    """Fix round, F2 (the refutation lens "dates": "Examination complete, not aborted.", "Cancelled: No", "Copay:
    deferred" were read as marking another occurrence, so today's date was asked and a member's correct answer held):
    whether the status word at [start, end) may say that the dated occurrence did not happen - it is not negated (the
    negation that governs a status word, cues.status_negation: "not cancelled", "was never cancelled"), not answered
    No, N/A or none in its own field ("Cancelled: No", "Cancellation reason: N/A"), and not the first word of the value
    of a field about something else ("Copay: deferred"; a field naming an occurrence or a status still speaks:
    "Status: cancelled", "Procedure: cancelled"). Each reads a few characters around the word only (the rule's index
    reads every word once)."""
    if cues.status_negation(text, start) is not None:
        return False
    line_end = text.find('\n', end, end + VALUE_REACH + 60)
    line_end = min(len(text), end + VALUE_REACH + 60) if line_end < 0 else line_end
    rest = _STATUS_LABEL_REST.match(text, end, line_end)
    if rest is not None and '  ' not in text[end:rest.end()] and '\t' not in text[end:rest.end()]:
        brk = _FIELD_BREAK.search(text, rest.end(), line_end)
        if _NO_ANSWER.fullmatch(text, rest.end(), brk.start() if brk else line_end):
            return False
    line_start = text.rfind('\n', max(0, start - 60), start) + 1
    field = _VALUE_OF_FIELD.search(text, max(line_start, start - 60), start)
    if field is not None:
        label = field.group('label')
        if not (_OCCURRENCE_NOUN.search(label) or _STATUS_FIELD.search(label)
                or any(p.search(label) for p in _THIS_SERVICE)):
            return False
    return True
# The sections whose heading is never read: the document's top, the app's addendum header and a PDF form or annotation
# block (studio/gi/sections).
_UNREAD_SECTIONS = frozenset(('', 'addendum', 'pdf form fields', 'pdf annotation text'))
_LIST_MARK = re.compile(r'[ \t]*+(?:[-*\u2022][ \t]++|\d{1,2}[.)][ \t]++)')
_NON_BLANK = re.compile(r'\S')


class _OccurrenceScope:
    """What the narrow source rule reads of one text, each part computed once - never a scan per label of a long line
    (refutation phase 2's cost rule): every word of the rule's vocabulary, found in one pass the first time a label
    needs one, as (start, end, whether it is a status word); and each section heading's verdict."""

    def __init__(self, text: str):
        self.text, self._index, self._headings = text, None, {}

    def words(self, start: int, end: int) -> list[tuple[int, int, bool]]:
        """The vocabulary's words standing wholly in [start, end)."""
        if self._index is None:
            found = []
            for m in _OCCURRENCE_WORDS.finditer(self.text):
                status = _STATUS.fullmatch(m.group()) is not None
                if status and not _status_marks(self.text, m.start(), m.end()):
                    continue  # fix round, F2: a negated, answered or another field's status word marks no occurrence
                found.append((m.start(), m.end(), status))
            self._index = (found, [w[0] for w in found])
        found, starts = self._index
        out, i = [], bisect.bisect_left(starts, start)
        while i < len(found) and found[i][0] < end:
            if found[i][1] <= end:
                out.append(found[i])
            i += 1
        return out

    def heading_governs(self, label_start: int) -> bool:
        """(a) Whether the label stands, below its heading's line, in a section studio/gi/sections opened with a heading
        it cannot place (kind 'other', no heading it knows) whose own words name another occurrence
        (_heading_names_another). Never the document's top, the app's addendum header or a PDF form block, nor a heading
        on the label's own line ("Date of service:" alone on its line opens a section of its own)."""
        sec = layout(self.text).section_at(label_start)
        if sec.heading is None or sec.kind != 'other' or sec.label in HEADINGS or sec.label in _UNREAD_SECTIONS:
            return False
        verdict = self._headings.get(sec.heading.start)
        if verdict is None:
            line_end = self.text.find('\n', sec.heading.end)
            verdict = self._headings[sec.heading.start] = (len(self.text) if line_end < 0 else line_end,
                                                           _heading_names_another(self.text, sec.heading))
        return verdict[1] and label_start > verdict[0]


@functools.lru_cache(maxsize=16)
def _occurrence_scope(text: str) -> _OccurrenceScope:
    return _OccurrenceScope(text)


def _heading_names_another(text: str, heading: Span) -> bool:
    """Whether a section heading names another occurrence: a word of the rule's vocabulary outside a name of a service
    this release codes ("Outside colonoscopy:", "Cancelled procedure:", "Index EMR:"). Never a heading naming only such a
    service ("Colonoscopy:", "Follow-up visit:"), a date-of-service or birth label alone on its line (an empty field over
    its value), or a label alone on its line over another label or a bare value (a stacked header's field: "Patient:"
    over "DOB:" over their values; _stacked_label). A heading naming no other occurrence ("Recall:", "Patient
    information:", "Pending colonoscopy:") changes nothing (the owner's decision). Fix round (dates lens, F2): a word
    that may name something else in a heading ("Last name:", "Last updated:", "Balance due:", "Requested by:") names
    another occurrence only beside an occurrence noun or a coded service's name ("Last colonoscopy:", "Requested
    procedure:"); the words that name one by themselves are _HEADING_OCCURRENCE ("Outside", "Index", "Cancelled")."""
    words = str(heading.text).rstrip(': \t')
    if not words or _names_this_service(words, words) or DATE_LABEL.fullmatch(words) or _BIRTH_HEAD.fullmatch(words):
        return False
    names = [(n.start(), n.end()) for p in _THIS_SERVICE for n in p.finditer(words)]
    found = [q for q in _OCCURRENCE_WORDS.finditer(words) if not any(s <= q.start() and q.end() <= e for s, e in names)]
    if not found:
        return False  # no word of the vocabulary outside a service's name
    if not any(_HEADING_OCCURRENCE.fullmatch(q.group()) for q in found) \
            and not (names or _OCCURRENCE_NOUN.search(words)):
        return False  # fix round, F2: only a word that may name something else, beside no occurrence
    return not _stacked_label(text, heading.end)


def _stacked_label(text: str, heading_end: int) -> bool:
    """Whether a label alone on its line heads no block: the next non-blank line starting within GAP_REACH characters is
    neither a field with a value nor a list item (another label alone or a bare value, as a stacked header writes its
    fields), or there is none."""
    end = text.find('\n', heading_end)
    start = end + 1
    while 0 < start < min(len(text), end + 1 + GAP_REACH):
        stop = text.find('\n', start)
        stop = len(text) if stop < 0 else stop
        if _NON_BLANK.search(text, start, stop) is not None:
            if _LIST_MARK.match(text, start, stop) is not None:
                return False
            field = _LINE_FIELD.match(text, start, stop)
            return field is None or _NON_BLANK.search(text, field.end(), stop) is None
        start = stop + 1
    return True


def _phrase_end(text: str, date_end: int) -> int:
    """Where _line_reading stops reading after a labelled date (the same window): the end of the date's line within 80
    characters, or of the next line within 80 more when the phrase wraps onto it (that line opens in lower case or a
    bracket)."""
    hi = text.find('\n', date_end, date_end + 80)
    hi = min(len(text), date_end + 80) if hi < 0 else hi
    if hi < len(text) and text[hi] == '\n':
        wrap = hi + 1
        while wrap < min(len(text), hi + 81) and text[wrap] in ' \t':
            wrap += 1
        if wrap < len(text) and (text[wrap].islower() or text[wrap] in '(['):
            stop = text.find('\n', wrap, hi + 81)
            hi = min(len(text), hi + 81) if stop < 0 else stop
    return hi


def _another_occurrence_governs(text: str, label_start: int, label_end: int, date_start: int, date_end: int,
                                value: Optional[date], phrase_start: int) -> bool:
    """The narrow source rule for a label the installed reading reads as the note's own: whether a heading, a title or a
    field on its row names another occurrence and governs the label, read where the installed reading does not read:
    (a) the heading of the label's section (_OccurrenceScope.heading_governs);
    (c) a status word (cues.CANCELLED_CLAUSE) read exactly as _line_reading reads a date qualifier, where it reads one:
        any one on the label's line within its 80 characters before the label, or after the date within its phrase,
        makes the date another occurrence's or one it cannot place (fr-dr:4: a date qualifier there is never passed
        over: "Status: cancelled    Procedure date:", "11/04/2026 (cancelled)", "11/04/2026 cancelled Status: closed");
        one on the line above a label opening its line governs unless that rule passes it over (inside a coded
        service's name, before another date on that line, or opening a field about something else or with a date of
        its own) - a title or heading above ("Cancelled colonoscopy", "Cancelled procedure:");
    (b) beyond those 80 characters, up to ROW_REACH on the label's row (refutation phase 2, dates:4), a word of the
        vocabulary governs only when it names the label's occurrence by structure: it opens a field naming an occurrence
        ("Planned procedure: colonoscopy with ... Procedure Date:", "Cancelled colonoscopy: yes ...") or is attached to
        the label (nothing but words, commas, hyphens, brackets or a row's cell bars between them: "Outside colonoscopy
        at ... adenomas, procedure date:"), with no date but a date of birth between them. A field about something else
        ("Last name:"), one with a date of its own ("Next visit: 11/24/2026"), or a word across a break ("Visit type:
        Follow-up", "Indication: history of polyps.") that far back names no occurrence of the label: nothing changes.
    The label's own words need no reading: any word there but a coded service's name already makes the installed
    reading 'unplaced'."""
    scope = _occurrence_scope(text)
    if scope.heading_governs(label_start):
        return True
    near = max(text.rfind('\n', max(0, label_start - 80), label_start) + 1, label_start - 80, 0)
    far = max(text.rfind('\n', max(0, label_start - ROW_REACH), label_start) + 1, label_start - ROW_REACH, 0)
    row = scope.words(far, label_start)
    if any(status and q_start >= near for q_start, _, status in row) \
            or any(status for _, _, status in scope.words(date_end, _phrase_end(text, date_end))):
        return True  # (c) on the label's line, where every date qualifier holds the date
    farther = [w for w in row if w[0] < near]
    above = _line_above(text, phrase_start)
    window = 0 if above is None else min(above[1], above[0] + 200)
    upper = [] if above is None else [w for w in scope.words(above[0], window) if w[2]]
    if not (farther or upper):
        return False
    dates, starts = find_dates(text), _date_starts(text)

    def other_dates(a: int, b: int) -> list:  # _line_reading's: the dates in [a, b) other than this one
        return [dates[j] for j in range(bisect.bisect_left(starts, a), bisect.bisect_left(starts, b))
                if not date_start <= dates[j].start < date_end
                and (value is None or compare_to_service(dates[j], value) != 0)]

    def has_date(a: int, b: int) -> bool:
        return bool(other_dates(a, b))

    if upper:  # (c) on the line above, as _line_reading reads its date qualifiers there
        names = [(n.start(), n.end()) for p in _THIS_SERVICE for n in p.finditer(text, above[0], min(above[1], window + 60))]
        for q_start, q_end, _ in upper:
            if not (any(s <= q_start and q_end <= e for s, e in names) or other_dates(q_end, above[1])
                    or _qualifier_field(text, q_start, q_end, above[1], has_date) in ('else', 'dated')):
                return True
    opens = _opens_field(text, label_start, label_end)
    for q_start, q_end, _ in farther:  # (b)
        field = _qualifier_field(text, q_start, q_end, label_start, has_date)
        if field in ('dated', 'else') or any(not _is_birth(text, d.start) for d in other_dates(q_end, label_start)):
            continue
        if field == 'occurrence' or not opens and not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[q_end:label_start])):
            return True
    return False


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


def _column(text: str, rows: '_Rows', ls: int, le: int, cell_start: int, label_end: int, cell_tail: int,
            births: bool = False):
    """For a label that is a whole cell of an aligned header row: the cell at its position in the row below, or - when
    the row below has another number of cells - _UNPLACED where that row states a date and _NO_VALUE where it states
    none (fr-dr:0); None when the label heads no aligned column (it is not one cell's only text, or runs across two
    cells). ``births``: the label is a birth label (_birth_places) - its cell is placed whatever the other columns hold,
    and by count alone (_Counted) where the cells do not lie under their heads (df-d:1)."""
    cells = _header_row(text, rows, ls, le)
    if cells is None:
        return None
    k = bisect.bisect_left(cells, (cell_start, -1))
    if k >= len(cells) or cells[k][0] != cell_start or label_end > cells[k][1] \
            or not _blank_to(text, cell_tail, cells[k][1]):
        return None
    row = rows.below(le)
    values = rows.aligned(*row) if row is not None else []
    if births and len(values) == len(cells):
        # the differential round, df-d:1: the tests below say where a date label's VALUE is, never where a date of
        # birth stands - read for "DOB" too, a date-of-service cell "TBD" (or tabs whose offsets do not line up) left
        # the cell under it unmarked, a dated service line "Colonoscopy  TBD  01/01/1998" read it as its own date, and
        # a member's 1998-01-01 was taken and sent where c3c034a08, placing it by count, held it
        return values[k] if _under_their_heads(cells, ls, values, row[0]) else _Counted(values[k])
    if len(values) == len(cells) and _under_their_heads(cells, ls, values, row[0]) \
            and all(_line_label(text, *head) not in ('dos', 'birth') or _date_alone(text, *value)
                    for head, value in zip(cells, values)):
        return values[k]  # fr-dr:1: and every date or birth label's column holds a date alone, as a stack's place does
    # the differential round, df-d:3: also where the cell at the label's place holds a digit ("20261014", "10142026": a
    # date written without separators is no date start, _GAP_DATE) - read as stating none, it was silent and "Date of
    # service: 10/07/2026" beside it was sent, where c3c034a08 read the cell as the label's value and asked (fr-dr:0: a
    # field stating what it cannot place speaks; only a cell with no digit - "TBD", "N/A" - states no date)
    if row is not None and (rows.states_a_date(*row) or (len(values) == len(cells) and _DIGIT.search(text, *values[k]))):
        return _UNPLACED
    return _NO_VALUE


class _Counted(tuple):
    """A birth label's column cell placed by count alone - the row's cells number the header's but do not lie under their
    heads (df-d:1): its date may be the date of birth, so it is no candidate's value and no member date's agreement, but
    a dated line stating it is asked, never silent (it may as well be the line's own date, shifted under "DOB")."""


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
def _birth_places(text: str) -> tuple[frozenset, frozenset]:
    """Where a date of birth starts whose birth label is not right before it (rule N2, "any row"): the cell under a
    birth label heading a table column ("Patient | DOB | Date of Service" above "Synthetic, Alex | 01/01/1998 |
    10/14/2026"), or an aligned column ("DOB            Date of Service" above "01/01/1998     10/14/2026"); the value
    line at a birth label's place in a stack, or the line under a birth label alone on its line when it opens with the
    value ("Date of birth:" above "01/01/1998"); the value at a birth label's place in a joined header ("DOB / Date of
    Service: 01/01/1998 / 10/14/2026"). One pass over the birth labels and one over the date labels; each line's cells
    and the row under it are read once (_Rows). (Those, and apart the aligned cells placed by count alone: _Counted.)"""
    found, counted, rows = set(), set(), _Rows(text)
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
        column = _column(text, rows, ls, le, m.start(), m.end(), tail, births=True)
        if column is None and _blank_to(text, ls, m.start()) and _blank_to(text, tail, le):
            stacked = _stacked_value(text, rows, ls, le)  # the birth label alone on its line
            column = stacked[0] if isinstance(stacked, tuple) else None
        if isinstance(column, tuple):  # a value placed by position (never _NO_VALUE or _UNPLACED), or by count
            value = _first_value(text, column[0], min(column[1], column[0] + VALUE_REACH), births=False)
            if value is not None:
                (counted if isinstance(column, _Counted) else found).add(value[0])
    for m in DATE_LABEL.finditer(text):
        joined = _joined(text, rows, m.start('label'), m.end('label'))
        if joined is not None:
            found.update(run[0] for run in joined[2])
    return frozenset(found), frozenset(counted - found)


@functools.lru_cache(maxsize=16)
def _birth_cells(text: str) -> frozenset:
    """Every date of birth _birth_places finds, placed by position or by count: no candidate's value, no reading."""
    found, counted = _birth_places(text)
    return found | counted


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

# GI round 2 (session 7c8d38da; the one preserved failure of the 2b82889f acceptance walk, ho-04): elapsed time is no
# date. "Total time on the date of service: 34 minutes, including record review, ..." was read as a date-of-service
# FIELD whose value "34" is a date this service cannot read, so the note's own "Date of service: 2026-10-22" was asked
# (its request went without the date and 99214 waited for a member's answer) and, where no label states the date, every
# member date was held - 057a7d398 read 2026-10-22. A DURATION is the grammar of a quantity of time: a number, or a
# range of two, and a unit of time. Units of time are this rule's only vocabulary (a closed class); days, weeks and
# months are left out on purpose, because a date offset is written in them ("2 weeks after the index procedure"). A
# field holds one only when nothing else in it may state a day: it does not open with another number, and outside its
# durations no date starts (_GAP_DATE), no number runs to three digits ("20261022", "2026"), and no ordinal day or
# weekday stands ("the 23rd", "Friday": the calendar's own names, _WEEKDAY_NAME) - a time stated on another day keeps
# the installed reading (asked). Two places read it (_measured_on, the date-label loop of _service_dates; _value_extent).
_TIME_UNIT = r'(?:minutes?+|mins?+|hours?+|hrs?+|seconds?+|secs?+)'
_DURATION_NUMBER = r'\d{1,4}+(?:\.\d{1,2}+)?+'
DURATION = cues.rx(r'(?<![\w/.:-])' + _DURATION_NUMBER + r'(?:[ \t]*+(?:-|–|\bto\b)[ \t]*+' + _DURATION_NUMBER
                   + r')?+[ \t]*+' + _TIME_UNIT + r'(?![A-Za-z0-9])\.?+')
_LONG_NUMBER = re.compile(r'\d{3,}')
_DAY_WORD = cues.rx(r'\b' + _WEEKDAY_NAME + r'\b|(?<![\w/.-])\d{1,2}(?:st|nd|rd|th)\b')
_WORD_OR_DIGIT = re.compile(r'[A-Za-z0-9]')


def _holds_duration(text: str, start: int, end: int, alone: bool = False) -> bool:
    """Whether a label's value field [start, end) holds a duration and nothing that may state a day (the elapsed-time
    rule above). The field ends at another field's label, never at one whose words run back over a duration's unit
    ("34 minutes. Date of service: ..." - the next label is "Date of service:", not "minutes. Date of service:").
    ``alone``: the field holds nothing but durations (blanks and punctuation between them)."""
    spans = [(d.start(), d.end()) for d in DURATION.finditer(text, start, end)]
    if not spans:
        return False
    pos = start
    while True:
        other = _NEXT_LABEL.search(text, pos, end)
        inside = None if other is None else next((e for s, e in spans if s <= other.start() < e), None)
        if inside is None:
            stop = end if other is None else other.start()
            break
        pos = inside
    spans = [(s, e) for s, e in spans if e <= stop]
    if not spans:
        return False
    opening = _BLANKS.match(text, start, stop).end()
    if opening != spans[0][0] and _DIGIT.match(text, opening):
        return False  # the field opens with another number: its value, as _value_extent reads it
    pos = start
    for s, e in spans + [(stop, stop)]:
        if (_GAP_DATE.search(text, pos, s) is not None or _LONG_NUMBER.search(text, pos, s) is not None
                or _DAY_WORD.search(text, pos, s) is not None
                or (alone and _WORD_OR_DIGIT.search(text, pos, s) is not None)):
            return False
        pos = e
    # fix round 2 (the differential round, edges-2 and F-2): and the time statement's soft-wrapped RUN states no day
    return _run_states_no_day(text, start)


# Fix round 2 (the differential round's edges-2 and F-2, against aec8edf3f; narrowing the fix round's F4 toward the
# installed reading). F4 read the time statement's whole LINE for a token that may state a day. A line is not the
# statement: a PDF upload breaks it every 90 characters, so the other day landed on the next line ("... counseling and"
# / "care coordination; Date: 10/23/2026") and the header's date was sent where the installed tree asked - a TXT or DOCX
# upload of the same note was asked. And its tokens missed the day words with no digit beside them ("34 minutes on the
# twenty-third", "October twenty-third") and the Roman-numeral months ("23/X/26"): sent, where installed asked. The rule
# now reads the statement's RUN - the lines the layout joins into its sentence (a soft wrap: studio/gi/sections' layout,
# whose sentences run on over a joined break) - with the next line where the run leaves its field open (it ends on ':',
# ';', ',', a dash, a slash, '&', '|', an open bracket or a word a sentence cannot end on, or leaves a bracket open: "|
# Date:" over "10/23/2026", "(see note dated" over "10/23/2026)."), where it does not close its sentence ('.', '!' or
# '?') and that line opens no field or list item of its own ("34 minutes" over "(10/23/2026)."), or where that line
# opens with a bracket, a date field or a date ("34 minutes" over "Date: 10/23/2026", "34 minutes." over "10/23/2026");
# and with the line above where that line leaves its field open over the statement ("Time spent on 10/23/2026:" over it)
# or opens with a date field. Rules (a) and (b) apply only where that run, outside its durations and outside a
# date-of-service label with its own read date (SERVICE_DATE: that date is the label's, and it speaks as a label of its
# own), holds NO digit at all and no month's name or abbreviation, weekday or ordinal word (_RUN_DAY: the calendar's own
# names, closed classes; the ordinal words "first" to "thirty-first", written with a hyphen, a space or neither).
# Anything else keeps the installed reading (asked). The run, its marks and the lines' joins are found once per text, so
# a time field's run is a few bisections (never a scan per label).
_ORDINAL_UNITS = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth')
_ORDINAL_WORDS = (_ORDINAL_UNITS + ('tenth', 'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth',
                                    'sixteenth', 'seventeenth', 'eighteenth', 'nineteenth', 'twentieth', 'thirtieth')
                  + tuple('twenty' + sep + unit for unit in _ORDINAL_UNITS for sep in ('-', ' ', ''))
                  + tuple('thirty' + sep + 'first' for sep in ('-', ' ', '')))
_RUN_DAY = cues.rx(r'\d++|\b(?:' + _MONTH + '|' + _WEEKDAY_NAME + '|'
                   + '|'.join(sorted((re.escape(w).replace(r'\ ', r'[ \t]') for w in _ORDINAL_WORDS),
                                     key=len, reverse=True)) + r')\b')
_LINE_BREAK = re.compile('\n')
# A run that closes its sentence: a full stop, '!' or '?', perhaps inside a closing bracket or quote.
_RUN_CLOSED = re.compile(r'[.!?][)\]"\'”’]*+[ \t\r]*+\Z')
# A run (or the line above it) that leaves its field open: a separator, a dash, a slash, '&', '|', an open bracket, or a
# word a sentence cannot end on (the articles, conjunctions and prepositions labels are written with: a closed class).
_RUN_OPEN = cues.rx(r'(?:[:;,&|/(\[–—-]|\b(?:and|or|of|on|to|by|at|in|for|with|the|a|an))[ \t\r]*+\Z')
# A line that opens a statement of its own: a list item or a field ("Plan: ...", "Date: ...").
_OPENS_ITS_OWN = re.compile(r"[ \t]*+(?:[-*•][ \t]++|\d{1,2}[.)][ \t]++"
                            r"|[A-Za-z][A-Za-z0-9 '’/()&,.-]{0,40}?[ \t]*+:(?!\d))")
_OPENS_BRACKET = re.compile(r'[ \t]*+[(\[]')
# A line that opens with a date field ("Date: 10/23/2026", "Date/Time: ...", a date-of-service label): it may state the
# statement's day, whatever the run's end (the reader's own date-field grammar, as _LINE_DATE_FIELD reads it).
_OPENS_DATE_FIELD = cues.rx(r'[ \t]*+(?:date' + _DATE_TIME + r'|' + _DATE_LABEL + r')\b(?:[ \t]*+\([^()\n]{0,20}+\))?+'
                            r'[ \t]*+[:#=\u2013|-]')
# A line that opens with a date (a date start the reader reads, as _GAP_DATE: "10/23/2026", "Oct 23", "23 Oct").
_OPENS_DATE = cues.rx(r'[ \t]*+(?:' + _VALUE_DATE_START.pattern + r')')
RUN_TAIL = 200  # characters of a run's end read for its shape (bounds the work per run)


class _TimeRuns:
    """What the elapsed-time rule reads of one text, each part found once (refutation phase 2's cost rule; the fix round
    2 differential's edges-1: a reading per label of a long soft-wrapped run is quadratic): each line's start, where its
    soft-wrapped run starts and ends (a line runs on into the next where a sentence of the layout spans their break -
    exactly the layout's joins), where a token that may state a day (_RUN_DAY) starts outside every duration and every
    read date-of-service label, and each run's statement bounds once read (_statement_bounds)."""

    __slots__ = ('starts', 'run_starts', 'run_ends', 'free', 'bounds')

    def __init__(self, text: str):
        lay = layout(text)
        sentence_starts = [s for s, _ in lay.sentences]
        breaks = [m.start() for m in _LINE_BREAK.finditer(text)]
        self.starts = (0,) + tuple(b + 1 for b in breaks)
        ends = tuple(breaks) + (len(text),)

        def joined(at: int) -> bool:
            k = bisect.bisect_left(sentence_starts, at) - 1
            return k >= 0 and lay.sentences[k][1] > at

        joins = [joined(b) for b in breaks] + [False]
        run_starts, run_ends = list(self.starts), list(ends)
        for k in range(1, len(run_starts)):
            if joins[k - 1]:
                run_starts[k] = run_starts[k - 1]
        for k in range(len(run_ends) - 2, -1, -1):
            if joins[k]:
                run_ends[k] = run_ends[k + 1]
        self.run_starts, self.run_ends = tuple(run_starts), tuple(run_ends)
        masked_starts, masked_ends = [], []
        # gi3 fix round 1 (dates-9): the labels the installed revision read, as before - a label written with a separator
        # it did not read (_UNREAD_SEPARATOR) is asked, so its date still makes the run state a day here
        for s, e in sorted([(m.start(), m.end()) for m in DURATION.finditer(text)]
                           + [(m.start(), m.end()) for m in SERVICE_DATE.finditer(text)
                              if _UNREAD_SEPARATOR.search(text, m.end('label'), m.start('date')) is None]):
            if masked_ends and s < masked_ends[-1]:
                masked_ends[-1] = max(masked_ends[-1], e)
            else:
                masked_starts.append(s)
                masked_ends.append(e)
        free = []
        for m in _RUN_DAY.finditer(text):
            k = bisect.bisect_right(masked_starts, m.start()) - 1
            if k < 0 or m.start() >= masked_ends[k]:
                free.append(m.start())
        self.free = tuple(free)
        self.bounds = {}


@functools.lru_cache(maxsize=16)
def _time_runs(text: str) -> _TimeRuns:
    return _TimeRuns(text)


def _blank_end(text: str, lo: int, hi: int) -> int:
    """Where [lo, hi) ends without its trailing blanks."""
    while hi > lo and text[hi - 1] in ' \t\r':
        hi -= 1
    return hi


def _left_open(text: str, lo: int, hi: int) -> bool:
    """Whether the run [lo, hi) leaves its field open (_RUN_OPEN at its end, read in its last RUN_TAIL characters) or
    leaves a bracket open."""
    end = _blank_end(text, lo, hi)
    return (_RUN_OPEN.search(text, max(lo, end - RUN_TAIL), end) is not None
            or text.count('(', lo, hi) > text.count(')', lo, hi) or text.count('[', lo, hi) > text.count(']', lo, hi))


def _statement_bounds(text: str, runs: _TimeRuns, line: int) -> tuple[int, int]:
    """The span the elapsed-time rule reads for a time statement on ``line``: its soft-wrapped run, with the next line
    where the run leaves its field open, or does not close its sentence ('.', '!', '?') and that line opens no field
    or list item of its own, or that line opens with a bracket, a date field or a date; and with the line above where
    that line leaves its field open over the statement or opens with a date field. Read once per run."""
    lo, hi = runs.run_starts[line], runs.run_ends[line]
    got = runs.bounds.get(lo)
    if got is not None:
        return got
    starts = runs.starts
    first, last = bisect.bisect_right(starts, lo) - 1, bisect.bisect_right(starts, hi) - 1  # the run's lines
    out_lo, out_hi = lo, hi
    if last + 1 < len(starts):
        nxt, nxt_end = starts[last + 1], runs.run_ends[last + 1]
        if _NON_BLANK.search(text, nxt, nxt_end) is not None:
            end = _blank_end(text, lo, hi)
            if (_left_open(text, lo, hi) or _OPENS_BRACKET.match(text, nxt, nxt_end)
                    or _OPENS_DATE_FIELD.match(text, nxt, nxt_end) or _OPENS_DATE.match(text, nxt, nxt_end)
                    or not (_RUN_CLOSED.search(text, max(lo, end - RUN_TAIL), end)
                            or _OPENS_ITS_OWN.match(text, nxt, nxt_end))):
                out_hi = nxt_end
    if first > 0 and (_left_open(text, runs.run_starts[first - 1], starts[first] - 1)
                      or _OPENS_DATE_FIELD.match(text, runs.run_starts[first - 1], starts[first] - 1)):
        out_lo = runs.run_starts[first - 1]
    runs.bounds[lo] = (out_lo, out_hi)
    return out_lo, out_hi


def _run_states_no_day(text: str, pos: int) -> bool:
    """Whether the time statement at ``pos`` - its soft-wrapped run, with the lines beside it the rule above reads -
    holds no token that may state a day outside its durations and date-of-service labels."""
    runs = _time_runs(text)
    lo, hi = _statement_bounds(text, runs, bisect.bisect_right(runs.starts, pos) - 1)
    j = bisect.bisect_left(runs.free, lo)
    return not (j < len(runs.free) and runs.free[j] < hi)


def _measured_on(text: str, label_start: int, label_end: int) -> bool:
    """Whether the date-of-service phrase at [label_start, label_end) dates what the words before it name - it is the
    object of their connecting word: those words (as _label_words reads them, also before a capitalised label, "Total
    Time on Date of Service") end with a connecting word (_CONNECTOR, the grammar labels are written with), or with a
    neutral word after one ("Total time on the date of service", "Time spent on DOS", "Total time spent on this date of
    service"). A word of the label's own ("Initial date of service", "Previous DOS", "Colonoscopy date of service")
    makes it no quantity's label: a date label, read as before."""
    words = _label_words(text, label_start, label_end, fields=False)[0].split()
    if not words:
        return False
    if _CONNECTOR.fullmatch(words[-1]):
        return True
    return len(words) > 1 and words[-1].lower() in _NEUTRAL_WORDS and _CONNECTOR.fullmatch(words[-2]) is not None


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
    beside it was documented and sent). A number that is no date ("MRN 0000") states none, and nor does a field holding
    nothing but durations ("Date of service: 34 minutes": GI round 2, the elapsed-time rule, _holds_duration): it is
    kept as a field that states no date (rule N3) - never a date this service cannot read, which spoke against the
    note's own date. A date stated relative to another event ("48 hours after the index procedure") is read as before."""
    if _holds_duration(text, start, end, alone=True):
        return None
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


# gi3 dates (the owner's directive of 2026-10-29, interpretation 42): which section governs a label. A plan or history
# section drops every date label it holds ("describes another encounter and is not read"), and the section reader opens
# sections only at headings it can place, so a heading it cannot place ("Charge information", "Billing", "Visit
# details") inherited the plan or history section before it: h2-08 sent its header's 2026-10-05 while its charge block
# labelled 2026-10-06, the second date dropped with nothing left behind. A plan or history section now governs a label
# only while its reach lasts (_binding); the section boundaries themselves are not moved, as routing, extent and the
# inventory read them:
# - part 1, a block heading: the nearest line above the label inside its section, after the section's heading line,
#   that stands as a heading the section reader could not place (_Governance: a bare label of at most six words with no
#   verb, no closing punctuation, no colon, cell bar or tab, no list marker unless its number continues the section
#   heading's - "4. Assessment and plan" ... "5. Charge information" - and a sentence of its own). One whose words name
#   another occurrence, a plan, a history, a service, an act or another document, or that ends on an occurrence noun
#   ("Return visit", "Recall", "Transplant evaluation"; _names_another_block: the readers' own closed vocabularies),
#   governs the label as before; any other - a neutral heading - ends the section's reach;
# - part 2 and B4, no block heading: inside a plan section whose own heading names no occurrence ("Plan:", "Assessment
#   and plan"; never "Follow-up:" or "Next appointment"), a FIELD of the encounter's own date-of-service label (date of
#   service, DOS, service or encounter date) speaks - a plan schedules visits and procedures, it does not restate the
#   date of service of the note it is in - and so does a visit or procedure date field (B4), unless the plan item right
#   before it names a later occurrence (_Governance.item_names_later) and its date is later than every date the note
#   labels as its own: it then dates that later occurrence and stays governed ("Return to clinic in 6 weeks." / "Visit
#   date: 2026-11-16"). The same item keeps such a field governed after a neutral heading ("Visit details" / "Return in 6
#   weeks." / "Visit date: 2026-11-16");
# - RC5, a plan section the document's own title opens ("GI clinic follow-up", "Hepatology follow-up": _title_section)
#   governs no label: its header reads as an untitled header does.
# A label no section governs any longer speaks, but never as the note's own date by itself (_settled: asked, and a
# member's answer equal to it is taken), so outside a title's section the binding only ever asks where the installed
# reading sent. Part 3 (_plans_procedure) and part 4 (_time_directed) ask two more shapes the plan section misread.
# The setting and patient-status readers share the binding (RC6: _settings, _patient_status).
#
# gi3 integration (the integration owner, after the repairs were merged; interpretation 42 refined):
# - H1: the encounter's own date-of-service label in a plan section, under a block heading that names its block only
#   as a kind of service (_Governance.names_a_kind: a service's name or a noun this encounter may be - "Office visit",
#   "Clinic visit", "Coding review", "Procedure", "Colonoscopy" - with no plan, history, other-occurrence, status,
#   other-document, return or recall word), is no longer dropped with nothing left behind. Such a heading names a kind
#   of service, not another occurrence of it ("Next appointment", "Prior visit", "Return visit", "Recall", "Results",
#   "Labs" and "Follow-up appointment" still govern), so the billing label under it may state this note's date ("Office
#   visit" / "CPT: 99214" / "Date of service: 2026-10-06" under an "Assessment and plan" whose header says 2026-10-05
#   sent the header's date). A table's column label ("Test | Date of service | Result") dates each row's item, never
#   the note, and stays governed;
# - H2: B4's visit or procedure date field that no later-occurrence item governs, in a note that labels no date of its
#   own, stays dropped as the installed reading dropped it: settled, its date would be the only answer a member may
#   give, and in "Plan:" / "Colonoscopy with possible polypectomy." / "Procedure date: 11/04/2026" that is the planned
#   colonoscopy's date.
# Each speaks only against a date the note labels as its own (_AGAINST_OWN): settled (_settled: asked, never sent)
# where the note labels one, dropped as before where it labels none - so neither ever sends a date.
#
# gi3 fix round 1 (the independent refutation of the integrated candidate 543bae72a; interpretations 42 and 48 as
# ruled). Each rule below only asks, or reads as the installed revision read:
# - dates-1: RC5 took a plan heading as the document's own follow-up title - "Follow-up appointment", "Follow-up
#   procedures", "Pending follow-up", "Recall follow-up", or a heading standing after prose ("Telephone encounter" /
#   "Spoke with the patient ... Questions answered." / "Follow-up appointment" / "Visit date: 11/16/2026") - and sent
#   the planned visit's date as the call's. The title now opens the document (_title_section: every line above it a
#   letterhead line, neither a field nor prose) and names the follow-up visit itself: the follow-up is its last words
#   or is followed only by a visit-title noun, and no return, recall or pending word stands before it;
# - dates-2: RC5 read its whole section as an untitled header, so a "Procedure date" (an index, scheduled or recalled
#   procedure's: "Surveillance follow-up" / "Index colonoscopy: ..." / "Procedure date: 05/01/2019"), a "Return visit
#   date" or a results table's "Date of service" column was sent as the follow-up visit's date, or became the only
#   answer a member may give. In the title's section only the header's own field dating THIS visit reads as an
#   untitled header's (_TITLE: the encounter's own label or a visit date field, read 'own' - no word qualifies it - and
#   no table column, under no heading naming another block); every other label there speaks only against the note's
#   own date (_AGAINST_OWN), and the setting and status read as before (RC6) unless such a heading stands over them;
# - dates-5: a heading between the plan item and the field that books the item ("Plan:" / "Colonoscopy with possible
#   polypectomy." / "Scheduling" / "Procedure date: 11/04/2026", "Appointment details") was read as neutral, so the
#   planned date became the only answer a member may give. Its words name another occurrence (_BOOKING), so it governs
#   as interpretation 42 rules such a heading to; this encounter's own administrative block ("Billing" / "Procedure
#   date: 2026-10-15", "Encounter summary" / "Visit date: ...") still ends the plan's reach and speaks;
# - dates-7: inside a plan with no block heading, a table's column label ("Test | Date of service | Result") dates each
#   row's item, so it is no field of the encounter's own (part 2): the plan governs it, as interpretation 48(a) rules a
#   column label governed and as the installed reading read it - the results' date is never the only answer, and the
#   header's own date is sent. Past a neutral heading the plan's reach has ended, and a table there still speaks
#   (interpretation 42; the corpus's charge table under "Charge information", A20);
# - dates-6 and dates-8: see _names_a_kind and _joined_heading.
_READ, _GOVERNED, _SPEAKS, _LATER, _AGAINST_OWN = 'read', 'governed', 'speaks', 'later', 'against-own'
_TITLE = 'title'  # gi3 fix round 1 (dates-2): read where its reading is the note's own ('own'), else _AGAINST_OWN
# The encounter's own date-of-service labels: _DATE_LABEL less the visit and procedure date labels ("Visit date:",
# "Date of procedure:"), which a plan item may own.
_ENCOUNTER_LABEL = cues.rx(r'date' + _DATE_TIME + r'[ \t]++of[ \t]++(?:service|encounter)|DOS' + _DATE_TIME
                           + r'|(?:service|encounter)[ \t]++date' + _DATE_TIME)
# gi3 fix round 1 (dates-2): the visit date labels of _DATE_LABEL - a follow-up title names a visit, never a procedure
_VISIT_LABEL = cues.rx(r'date' + _DATE_TIME + r'[ \t]++of[ \t]++visit|visit[ \t]++date' + _DATE_TIME)
# A block heading's head noun - its last word, as the section reader reads a colon-less label by the noun it ends with -
# naming an occurrence or an item a plan or history holds: the date reader's occurrence nouns and the section reader's
# own section nouns (sections._SECTION_NOUN: "Transplant evaluation", "Outside records", "Supportive care").
_OCCURRENCE_NOUNS = (r'(?:visits?|appointments?|procedures?|exams?|examinations?|consultations?|consults?|referrals?'
                     r'|recalls?|surger(?:y|ies)|sessions?|scans?|reviews?|labs?|bloodwork|results?)')
_OCCURRENCE_HEAD = cues.rx(r'(?:\b' + _OCCURRENCE_NOUNS + '|' + _sections._SECTION_NOUN.pattern + r')[ \t*#]*+$')
# H1 (gi3 integration): the occurrence nouns of _OCCURRENCE_HEAD this note's own encounter may be named by in its
# billing block - a visit, an encounter, a procedure, an examination, a consultation, a session or a review of the
# coding - as against a later booking, another discipline's or another day's work, or a section's own noun
# ("Appointment", "Referral", "Recall", "Labs", "Results", "Transplant evaluation"), which name another occurrence.
_OWN_KIND_HEAD = cues.rx(r'\b(?:visits?|encounters?|procedures?|exams?|examinations?|consultations?|consults?|sessions?'
                         r'|reviews?)[ \t*#]*+$')
# H1: the words that make a visit or a procedure another occurrence's in a heading that carries no date qualifier: a
# return, a recall, a pending one, or a follow up written with a space ("Return visit", "Pending procedures").
_H1_OTHER = cues.rx(r'\b(?:return(?:ing)?|recalls?|pending|follow[ \t]+up)\b')
# gi3 fix round 1 (dates-5): the words of a block heading that name another occurrence wherever they stand in it, not
# only as its head noun - the occurrence nouns this note's own encounter is never named by (_OCCURRENCE_NOUNS less
# _OWN_KIND_HEAD's: "a later booking, another discipline's or another day's work", H1's own reading) and the verb that
# books one (schedule, scheduling: its participles "scheduled" and "rescheduled" are already the readers' words). After
# a plan item, "Scheduling" / "Procedure date: 11/04/2026" and "Appointment details" / ... date the booked occurrence:
# such a heading governs, as the installed reading governed it, so the planned date is never the only answer. A
# neutral heading of this encounter's own block ("Billing", "Encounter summary") still ends the plan's reach.
_BOOKING = cues.rx(r'\b(?:appointments?|referrals?|recalls?|surger(?:y|ies)|scans?|labs?|bloodwork|results?'
                   r'|schedul(?:e|es|ing))\b')
# A plan section whose own heading names an occurrence ("Next appointment", "Scheduled procedure", "Follow-up:",
# "Pending procedures", "Referral:"): the fields right under it date that occurrence, so part 2 and B4 never read them.
_SECTION_NAMES_OCCURRENCE = cues.rx(r'\b' + _OCCURRENCE_NOUNS + r'[ \t*#:]*+$')
# What a block heading may name (_names_another_block): the section reader's plan and history label words, the date
# reader's occurrence, heading and status words, another discipline's document ("Labs", "Surveillance ultrasound"), and
# the clause cues routing reads as planned, historical or cancelled - each the reader's own closed class. An intent
# alone ("Diagnostic codes") names none of these: it says why a service is done, never which occurrence.
_BLOCK_WORDS = (_sections._PLAN_LABEL, _sections._HISTORY_LABEL, _OTHER_OCCURRENCE, _HEADING_OCCURRENCE, _STATUS,
                _OTHER_DOCUMENT) + _NOT_CURRENT_CUES
_FIELD_LEAD = re.compile(r'[ \t]*+(?:[-*•][ \t]++|\d{1,2}[.)][ \t]++)?', re.A)
_FIELD_BREAK_END = re.compile(r'(?:\|[ \t]*+|\t[ \t]*+|[ ]{2,}+|[.;][ \t]++)\Z', re.A)
# gi3 fix round 1 (dates-8): a heading's words joined to the label on its line, each capitalised (_field_start)
_JOINED_HEADING = re.compile(r"[ \t]*+(?:[A-Z][A-Za-z'’&/-]*+[ \t]++){1,6}+", re.A)
# A numbered line is a plan's or a history's own list item, unless its number continues the numbering of the section's
# own heading line ("4. Assessment and plan" ... "5. Charge information"): a sibling heading of a numbered template.
_NUMBER_MARK = re.compile(r'[ \t]*+(?P<n>\d{1,2}|[A-Za-z])[.)][ \t]++', re.A)
# RC5: the plan word a document's own title may carry - it names the follow-up visit the note documents, as "Hepatology
# follow-up note" does. A title naming a plan's content ("Bowel prep instructions", "Management plan"), another
# occurrence ("Next follow-up", "Scheduled follow-up") or a history heads that content, and still governs.
_FOLLOW_UP = re.compile(r'follow[- ]?up', re.A | re.I)
# gi3 fix round 1 (dates-1): what may follow the title's follow-up word - nothing, or the visit-title noun routing reads
# (cues._EM_TITLE_NOUN's note, visit, visit note or encounter, after an optional office or clinic): the follow-up is then
# what the title names. Any other word after it names what the plan holds ("Follow-up appointment", "Follow-up
# procedures", "Follow-up care", "Follow-up testing"), never the visit the note documents.
_TITLE_TAIL = cues.rx(r'(?:[ \t]++(?:(?:office|clinic)[ \t]++)?+(?:note|visit(?:[ \t]++note)?+|encounter))?+[ \t*#]*+')
# ... and a line above the title that is prose: a sentence's end on it (the layout's own stops)
_PROSE_END = re.compile(r'[.!?](?![^ \t\r])')
# gi3 fix round 1 (dates-6): the samples a procedure takes, named after it in its billing descriptor ("Colonoscopy with
# biopsy", "Colonoscopy, specimen collection", "Colonoscopy with cytology brushing"): the words of _OTHER_DOCUMENT that
# name a sample, not another discipline's document (a closed class: the biopsy, the specimen, the cytology sample).
_SAMPLE = cues.rx(r'\b(?:biops(?:y|ies)|specimens?|cytology)\b')
# ... and the coded services' own names, whose words are the service's (the "ultrasound" of "Endoscopic ultrasound", the
# "management" of "Evaluation and management"): routing's service patterns, the "FS" abbreviation and the E/M visit's
_SERVICE_NAMES = tuple(p for _, p in cues.SERVICE_PATTERNS) + (cues.FS_ABBREVIATION, cues.EM_VISIT)


def _names_a_kind(body: str) -> bool:
    """H1 (gi3 integration; _Governance.names_a_kind): whether a block heading names its block only as a kind of service.

    gi3 fix round 1 (dates-6): a charge line names its service as the billing descriptor does, and the descriptor's
    words of the plan and other-document vocabularies are the service's own - a word a coded service's name covers
    (_SERVICE_NAMES: "Endoscopic ultrasound", "Evaluation and management, level 4") and a sample named after a procedure
    (_SAMPLE after a coded service or a procedure named by its form, routing's gi.other word: "Colonoscopy with biopsy",
    "Anoscopy with biopsy"). They named no other document or plan, yet "Colonoscopy with biopsy" / "CPT: 45380" / "Date of
    service: 10/15/2026" was dropped and the header's contradicted 10/14 sent. Every other word governs as before:
    another occurrence, a history, a status, a return or a recall wherever it stands ("Follow-up visit, level 4" names a
    follow-up, as interpretation 48(a)'s "Return visit" names a return), and a document named beside a service
    ("Colonoscopy pathology")."""
    names = [m.span() for p in _SERVICE_NAMES for m in p.finditer(body)]
    after = min((m.end() for m in itertools.chain((n for p in _SERVICE_NAMES for n in p.finditer(body)),
                                                   _sections._S2_PROCEDURE_WORD.finditer(body))
                 if not _SAMPLE.fullmatch(m.group())), default=None)

    def described(m: re.Match) -> bool:
        return any(s <= m.start() and m.end() <= e for s, e in names) or (
            after is not None and after <= m.start() and _SAMPLE.fullmatch(m.group()) is not None)

    for p in _BLOCK_WORDS:
        for m in p.finditer(body):
            if not ((p is _sections._PLAN_LABEL or p is _OTHER_DOCUMENT) and described(m)):
                return False
    if _H1_OTHER.search(body) or _BOOKING.search(body):  # gi3 fix round 1 (dates-5): a booking's heading is no kind
        return False
    return _OCCURRENCE_HEAD.search(body) is None or _OWN_KIND_HEAD.search(body) is not None


def _plan_names_occurrence(heading: Optional[Span]) -> bool:
    words = '' if heading is None else str(heading.text)
    return bool(_OTHER_OCCURRENCE.search(words) or _HEADING_OCCURRENCE.search(words) or _STATUS.search(words)
                or _sections._service_named(words) or _SECTION_NAMES_OCCURRENCE.search(words))


def _names_another_block(line: str) -> bool:
    """Whether a block heading names another occurrence, a plan, a history, a service, an act or another document, or
    ends on an occurrence noun that is not today's ("Today's visit" names this one)."""
    if _sections._service_named(line) or _sections._act_or_place_named(line) or _sections._S2_PROCEDURE_WORD.search(line):
        return True
    if any(p.search(line) for p in _BLOCK_WORDS) or _BOOKING.search(line):  # gi3 fix round 1 (dates-5): _BOOKING
        return True
    return _OCCURRENCE_HEAD.search(line) is not None and cues.TODAY.search(line) is None


def _field_start(text: str, line_start: int, label_start: int, label_end: int) -> bool:
    """Whether a label opens a field: nothing but blanks or a list marker before it on its line; a cell bar, a tab, a run
    of spaces or a sentence's end right before it (read in the 40 characters before it); or a capitalised label one
    space after a word in lower case (_opens_field, refutation round 2, c2:2: "Charge information Date of service:")."""
    lo = max(line_start, label_start - 40)
    if lo == line_start and _FIELD_LEAD.fullmatch(text, lo, label_start):
        return True
    return _FIELD_BREAK_END.search(text, lo, label_start) is not None or _opens_field(text, label_start, label_end)


def _joined_heading(text: str, line_start: int, label_start: int) -> bool:
    """gi3 fix round 1 (dates-8): whether a capitalised label follows a neutral heading joined to it on its line, as a PDF
    line join writes a heading in Title Case or capitals ("Charge Information Date of Service: 2026-10-06", "CHARGE
    INFORMATION Date of Service: ...", "Billing Date of Service: ..."; c2:2 read only a heading word in lower case, so
    the label was dropped and the header's contradicted date sent): the line opens with capitalised words only, within
    the 40 characters _field_start reads - a bare label of at most six words and no verb (the section reader's own test)
    - naming no other block (_names_another_block: "Follow Up Date of Service:" still governs, as its heading on a line
    of its own would). Such words cannot be told from a word qualifying the date ("Expected Date of Service:"), so the
    field speaks only against the note's own date (_binding: _AGAINST_OWN) - never the only answer. A label in prose has
    a word in lower case before it ("Labs on the date of service: normal.") and stays governed."""
    if label_start - line_start > 40 or not text[label_start:label_start + 1].isupper() \
            or _JOINED_HEADING.fullmatch(text, line_start, label_start) is None:
        return False
    words = text[line_start:label_start].strip()
    return _sections._bare_label(words) and not _names_another_block(words)


def _sibling_number(text: str, sec, number: str) -> bool:
    """Whether ``number`` continues the number the section's own heading line opens with ("4." then "5.", "C)" then
    "D)")."""
    if sec.heading is None:
        return False
    own = _NUMBER_MARK.match(text, text.rfind('\n', 0, sec.heading.start) + 1, sec.heading.start + 1)
    if own is None:
        return False
    a, b = own.group('n'), number
    if a.isdigit() and b.isdigit():
        return int(b) == int(a) + 1
    return len(a) == len(b) == 1 and a.isalpha() and b.isalpha() and a.isupper() == b.isupper() and ord(b) == ord(a) + 1


def _title_section(text: str, lay: Layout) -> Optional[int]:
    """RC5: where the plan section the document's own title opens starts, or None. The title is the document's first
    heading, among its first TITLE_LINES non-empty lines, a colon-less line no heading list of the section reader holds
    ("GI clinic follow-up", "Hepatology follow-up", "Liver clinic follow up"), whose only plan word is a follow-up and
    which names no other occurrence, status or history. A bare "Follow-up" is the section reader's own plan heading, and
    stays one.

    gi3 fix round 1 (dates-1): and the title names the follow-up visit itself - its follow-up is its last words, or only
    a visit-title noun follows it (_TITLE_TAIL), and no return, recall or pending word stands before it (H1's
    _H1_OTHER: "Pending follow-up", "Recall follow-up") - and it opens the document: every non-empty line above it is a
    letterhead line, neither a field (_LINE_FIELD: "Patient: ...") nor prose (_PROSE_END). "Follow-up appointment",
    "Follow-up procedures" and a follow-up heading after "Spoke with the patient ... Questions answered." head the
    plan's content, and their section governs as before."""
    first = next((s for s in lay.sections if s.heading is not None), None)
    if first is None or first.kind != 'plan' or first.label in HEADINGS:
        return None
    words = str(first.heading.text)
    if words.rstrip().endswith(':') or not all(_FOLLOW_UP.fullmatch(m.group())
                                               for m in _sections._PLAN_LABEL.finditer(words)):
        return None
    if _HEADING_OCCURRENCE.search(words) or _STATUS.search(words) or _sections._HISTORY_LABEL.search(words):
        return None
    follow = None
    for follow in _FOLLOW_UP.finditer(words):
        pass
    if follow is None or _TITLE_TAIL.fullmatch(words, follow.end()) is None or _H1_OTHER.search(words, 0, follow.start()):
        return None
    lines = 0
    for m in re.finditer(r'[^\n]+', text):
        if m.start() > first.heading.start:
            break
        if text[m.start():m.end()].strip():
            lines += 1
            if lines > TITLE_LINES:
                return None
            if m.end() <= first.heading.start and (_LINE_FIELD.match(text, m.start(), m.end()) is not None
                                                   or _PROSE_END.search(text, m.start(), m.end()) is not None):
                return None  # gi3 fix round 1 (dates-1): a field or prose above it - it heads a block of the body
    return first.start


class _Governance:
    """What _binding reads of one text, each part found once (refutation phase 2's cost rule: never a scan per label of a
    long line): the text's line starts (every label bisects them), and every block heading inside a plan or history
    section - its line's start and its words, whose verdict (_names_another_block) is read once, the first time a label
    under it asks."""

    def __init__(self, text: str, lay: Layout):
        self.text, self.lay = text, lay
        self.lines = [0] + [m.end() for m in re.finditer('\n', text)]
        self.starts, self.bodies, self.names = [], [], {}
        # gi3 fix round 1 (dates-6, dates-3 and cost-3): each heading's H1 verdict, each line's B4 verdict and each
        # item sentence's, read once (a long soft-wrapped item, or labels on one line under a long blank run, made every
        # label rescan it: 100 s at 80,000 characters)
        self.kinds, self.later, self.items = {}, {}, {}
        sentence_starts = [s for s, _ in lay.sentences]
        for n, ls in enumerate(self.lines):
            s0, e0 = _strip_span(text, ls, self.end(n))
            if s0 >= e0 or e0 - s0 > 60 or any(ch in text[s0:e0] for ch in ':|\t'):
                continue
            sec = lay.section_at(ls)
            if sec.kind not in NOT_CURRENT_SECTIONS or sec.heading is None or sec.heading.start >= ls:
                continue
            numbered = _NUMBER_MARK.match(text, s0, e0)
            if numbered is not None and _sibling_number(text, sec, numbered.group('n')):
                body = text[numbered.end():e0].strip(' \t*#')  # "5. Charge information" after "4. Assessment and plan"
            elif _sections._LIST_ITEM.match(text, s0, e0) or _sections._SEC_LIST_MARK.match(text, s0, e0):
                continue  # a plan's or a history's own list item
            else:
                body = text[s0:e0].strip(' *#')
            if not body or not _sections._bare_label(body) or BROKEN_SERVICE_DATE.match(text, s0):
                continue  # ... never the opening words of a label broken over two lines (X3)
            k = bisect.bisect_right(sentence_starts, s0) - 1
            if k < 0 or lay.sentences[k][0] != s0:
                continue  # it continues the line above
            # the sentence holding its words (a sibling's number closes a sentence of its own: "5." / "Charge ...")
            end = lay.sentences[bisect.bisect_right(sentence_starts, text.find(body, s0, e0)) - 1][1]
            if end < e0:
                continue  # a sentence ends inside it
            if end > e0 and (n + 1 == len(self.lines) or not _LINE_FIELD.match(text, self.lines[n + 1], self.end(n + 1))):
                continue  # it runs on into the next line, which opens no field of its own
            self.starts.append(ls)
            self.bodies.append(body)

    def end(self, n: int) -> int:
        return self.lines[n + 1] - 1 if n + 1 < len(self.lines) else len(self.text)

    def line_start(self, pos: int) -> int:
        return self.lines[bisect.bisect_right(self.lines, pos) - 1]

    def block_heading(self, sec, line_start: int) -> Optional[bool]:
        """Whether the nearest block heading above the line starting at ``line_start`` inside its section names another
        block; None when there is none."""
        k = bisect.bisect_left(self.starts, line_start) - 1
        if k < 0 or self.starts[k] < sec.start:
            return None
        if k not in self.names:
            self.names[k] = _names_another_block(self.bodies[k])
        return self.names[k]

    def names_a_kind(self, sec, line_start: int) -> bool:
        """H1: whether the nearest block heading above the line starting at ``line_start`` inside its section names its
        block only as a kind of service: no word of _BLOCK_WORDS or _H1_OTHER (a plan, a history, another occurrence, a
        status, another document, a return or a recall), and no head noun but one this note's own encounter may be
        (_OWN_KIND_HEAD: "Office visit", "Coding review", "Procedure") or a service's name ("Colonoscopy") - never
        "Results", "Labs", "Appointment", "Referral" or "Transplant evaluation". A billing descriptor's own words are its
        service's (gi3 fix round 1, dates-6: _names_a_kind)."""
        k = bisect.bisect_left(self.starts, line_start) - 1
        if k < 0 or self.starts[k] < sec.start:
            return False
        if k not in self.kinds:
            self.kinds[k] = _names_a_kind(self.bodies[k])
        return self.kinds[k]

    def item_names_later(self, sec, line_start: int) -> bool:
        """B4: whether the plan item right before the line starting at ``line_start`` - the last sentence of the previous
        non-empty line in its section, never the section's own heading - names a later occurrence (_LATER_CUES) and
        holds no word routing reads as a denial or a doubt (cues.DOUBT_TOKEN: "Repeat colonoscopy is not needed." names
        none). gi3 fix round 1 (dates-3, cost-3): the verdict is read once per line and once per item sentence - labels
        on one line shared a walk back over every blank line above it, and lines soft-wrapped into one sentence each
        rescanned it whole (quadratic: 100 s at 80,000 characters, past the member's 15 s and analyze's 60 s)."""
        key = (sec.start, line_start)
        if key not in self.later:
            self.later[key] = self._item_names_later(sec, line_start)
        return self.later[key]

    def _item_names_later(self, sec, line_start: int) -> bool:
        n = bisect.bisect_right(self.lines, line_start) - 1
        while n > 0:
            n -= 1
            ls, le = self.lines[n], self.end(n)
            if ls < sec.start:
                return False
            if _blank_to(self.text, ls, le):
                continue
            end = _strip_span(self.text, ls, le)[1]
            ss, se = self.lay.sentence_for(end - 1, end)
            if sec.heading is not None and ss < sec.heading.end:
                ss = sec.heading.end  # the heading's own line: only the item after the heading
            if (ss, se) not in self.items:
                self.items[(ss, se)] = ss < se and not cues.DOUBT_TOKEN.search(self.text, ss, se) \
                    and any(p.search(self.text, ss, se) for p in _LATER_CUES)
            return self.items[(ss, se)]
        return False


@functools.lru_cache(maxsize=16)
def _governance(text: str) -> _Governance:
    return _Governance(text, layout(text))


@functools.lru_cache(maxsize=16)
def _title_start(text: str) -> Optional[int]:
    """RC5: where the section the document's own follow-up title opens starts (_title_section), once per text."""
    return _title_section(text, layout(text))


def _binding(text: str, lay: Layout, start: int, end: int, label: str = '') -> str:
    """How the section a label stands in binds it (see above): _READ - no plan or history section holds it, or the
    document's own title opened its section (RC5); _GOVERNED - dropped, as before; _SPEAKS - the section's reach ended at
    a neutral heading, or the plan does not govern the field (part 2, B4); _LATER - governed only if its date is later
    than every date the note labels as its own (B4); _AGAINST_OWN - it speaks only against a date the note labels as
    its own (gi3 integration, H1 and H2); _TITLE - in the title's section, read where its reading is the note's own and
    otherwise _AGAINST_OWN (gi3 fix round 1, dates-2). ``label``: 'encounter' (date of service, DOS, service or encounter
    date), 'visit' (a visit or procedure date), or '' (a setting or patient-status statement: RC6)."""
    sec = lay.section_at(start)
    if sec.kind not in NOT_CURRENT_SECTIONS:
        return _READ
    gov = _governance(text)
    line_start = gov.line_start(start)
    block = gov.block_heading(sec, line_start)
    if sec.start == _title_start(text):
        # gi3 fix round 1 (dates-2): only the header's own field dating this visit reads as an untitled header's
        if block or (label and (lay.in_table_header(start)
                                or (label == 'visit' and _VISIT_LABEL.fullmatch(text, start, end) is None))):
            return _AGAINST_OWN
        return _TITLE if label else _READ
    plan = sec.kind == 'plan'
    if block:
        if plan and label == 'encounter' and gov.names_a_kind(sec, line_start) and not lay.in_table_header(start):
            return _AGAINST_OWN  # gi3 integration, H1
        return _GOVERNED
    if block is None:
        if not (plan and label) or _plan_names_occurrence(sec.heading):
            return _GOVERNED
        if not _field_start(text, line_start, start, end):
            # gi3 fix round 1 (dates-8): a field joined to a neutral heading on its line speaks only against the note's own
            return _AGAINST_OWN if _joined_heading(text, line_start, start) else _GOVERNED
        if label == 'encounter':
            # gi3 fix round 1 (dates-7): a table's column label is no field of the encounter's own: the plan governs it
            return _GOVERNED if lay.in_table_header(start) else _SPEAKS  # part 2
    if plan and label == 'visit' and gov.item_names_later(sec, line_start):
        return _LATER
    if plan and label == 'visit' and block is None:
        return _AGAINST_OWN  # gi3 integration, H2 (B4)
    return _SPEAKS


def _settled(c: Optional[_Candidate]) -> Optional[_Candidate]:
    """The candidate of a label no plan or history section governs any longer (_SPEAKS), as it may state this note's
    date: never one its own words read as another occurrence's ('aside') or a field that states no date ('empty') -
    neither is a conflicting applicable date, so each stays dropped as the installed reading dropped it (kept, they would
    only hold every member answer) - and never the note's own date by itself ('own' -> 'unplaced': it speaks, it is
    asked, and a member's answer equal to it is taken)."""
    if c is None or c.reading == 'aside' or c.form == 'empty':
        return None
    return replace(c, reading='unplaced') if c.reading == 'own' else c


def _later_settled(found: list, later: dict, against: dict) -> list:
    """B4: each candidate of a label governed only when later (_LATER) is dropped when its date is later than every date
    the note labels as its own - as the installed reading dropped it, also where the note labels none - and is otherwise
    settled (_settled): an earlier, equal or unread date cannot be the later occurrence's. Each candidate of a label that
    speaks only against the note's own dates (_AGAINST_OWN) is settled where the note labels a date of its own, and is
    otherwise dropped as the installed reading dropped it."""
    if not later and not against:
        return found
    own = [c.value for c in found if id(c) not in later and id(c) not in against and c.source == 'label'
           and c.reading == 'own' and c.form == 'read' and c.value]
    out = []
    for c in found:
        if id(c) in later:
            c = None if c.value and all(value < c.value for value in own) else _settled(c)
        elif id(c) in against:
            c = _settled(c) if own else None
        if c is not None:
            out.append(c)
    return out


def _time_directed(text: str, lay: Layout, governed: list, found: list) -> list:
    """Part 4: a read date label a plan or history section governs, whose date the note's own labelled dates say cannot
    be that section's - a history section's date LATER than every one of them, or a plan section's date EARLIER than
    every one (a prior occurrence is never after the visit, a planned one never before it). Unqualified on its line
    (its own reading 'own'), it is asked ('unplaced'), never sent and never dropped: "Plan:" / "Date of service:
    2026-09-01" under a visit of 2026-10-05."""
    own = [c.value for c in found if c.source == 'label' and c.reading == 'own' and c.form == 'read' and c.value]
    if not own:
        return []
    latest, earliest = max(own), min(own)
    out = []
    for m in governed:
        value = date_from_match(m)
        if value is None:
            continue
        iso, kind = value.isoformat(), lay.section_at(m.start('label')).kind
        if not ((kind == 'history' and iso > latest) or (kind == 'plan' and iso < earliest)):
            continue
        reading, start = _labelled_kind(text, m.start('label'), m.end('label'), m.start('date'), m.end(), value)
        if reading == 'own':
            out.append(_Candidate(_span(text, start, m.end()), iso, 'label', 'unplaced', 'read'))
    return out


def _broken_label_opens(text: str, lay: Layout, rows: '_Rows', label_start: int) -> bool:
    """X3: whether a label broken over two lines opens its first line (nothing but blanks before it) and a sentence of
    its own there - so the line above does not run on into it."""
    return (_blank_to(text, rows.line(label_start)[0], label_start)
            and lay.sentence_for(label_start, label_start + 1)[0] == label_start)


def _read_label(text: str, rows: '_Rows', m: re.Match) -> _Candidate:
    """The candidate of a date-of-service label SERVICE_DATE (or BROKEN_SERVICE_DATE) reads a date after."""
    joined = _joined(text, rows, m.start('label'), m.end('label'))
    if joined is not None:  # P2DN's fix round, issue 3: a birth label joined to the label
        return _joined_candidate(text, m.start('label'), m.end('label'), joined)
    value = date_from_match(m)
    kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.start('date'), m.end(), value)
    # rule N5 (refutation phase 2, P2DN): the date is the note's own only when it stands alone in its own field;
    # rule N7 (P2DN's fix round, issue 8): and only when it is written as the installed revision reads one
    return _Candidate(_span(text, start, m.end()), value.isoformat() if value else None, 'label', _READING[kind],
                      'read' if value else 'invalid', alone=_alone_in_field(text, m.end(), rows.line(m.start('date'))[1]),
                      installed=_installed_form(text, m))


def _unread_label(text: str, rows: '_Rows', m: re.Match) -> Optional[_Candidate]:
    """The candidate of a date-of-service label DATE_LABEL finds where SERVICE_DATE read no date after it (refutation r1,
    context-3, and round 2, c2:8: a labelled date the reader does not read is documented date text), or None."""
    joined = _joined(text, rows, m.start('label'), m.end('label'))
    if joined is not None:
        return _joined_candidate(text, m.start('label'), m.end('label'), joined)
    where = _label_value(text, m, rows)
    if where is None:
        return None
    if where is _NO_VALUE or where is _UNPLACED:  # P2DN's fix round, issue 4: a header's positions do not match
        # it states no date ('empty'), or a date it cannot place ('unread': asked, the label alone - fr-dr:0)
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.end(), m.end(), None)
        tail = _LABEL_TAIL.match(text, m.end())
        label_end = tail.end('sep') if tail.group('sep') not in (None, '|') else m.end('label')
        return _Candidate(_span(text, start, label_end), None, 'label', _READING[kind],
                          'empty' if where is _NO_VALUE else 'unread')
    if _holds_duration(text, where[0], where[1]) and _measured_on(text, m.start('label'), m.end('label')):
        # GI round 2, the elapsed-time rule (ho-04): a date-of-service phrase that is the object of the words before
        # it ("Total time on the date of service: 34 minutes, including ...", "Time spent on DOS - 40 min") dates the
        # quantity those words name, and its field - a duration, nothing that may state a day - is that quantity's:
        # no date field at all, so no date candidate (rule A keeps every DATE a label states; this field states
        # none). Kept as a date this service cannot read, it made the note's own date a conflict and held every
        # member date where the note labels none; the note now reads as it does without the time statement.
        return None
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
        return _Candidate(_span(text, start, label_end), None, 'label', _READING[kind],
                          'empty' if extent is None else 'unread')
    value_start, value_end = extent
    if where[2]:  # a table column: the label's cell and its value's cell, never the cells between
        span, extra = _span(text, start, m.end('label')), (_span(text, value_start, value_end),)
    else:
        span, extra = _span(text, start, value_end), ()
    return _Candidate(span, None, 'label', _READING[kind], 'unread', extra)


def _label_kind(text: str, m: re.Match) -> str:
    """_binding's label: 'encounter' for the encounter's own date-of-service label (a broken one is always one), else
    'visit'."""
    return 'encounter' if (m.re is BROKEN_SERVICE_DATE
                           or _ENCOUNTER_LABEL.fullmatch(text, m.start('label'), m.end('label'))) else 'visit'


def _service_dates(text: str, lay: Layout) -> tuple[_Candidate, ...]:
    """Every date candidate of a label no plan or history section governs (refutation round 2, rule A; gi3 dates,
    _binding): the labelled dates of service, whatever their reading or form, and the dated titles near the top
    (_title_candidates). A label the section's reach no longer covers speaks, never by itself (_settled)."""
    found = []
    read = set()
    rows = _Rows(text)
    # the read labels a plan or history section governs (part 4); B4's pending candidates; H1's and H2's
    governed, later, against = [], {}, {}

    def bind(candidate: Optional[_Candidate], binding: str) -> None:
        if binding == _TITLE:  # gi3 fix round 1 (dates-2): the title's header field is read only as the note's own
            binding = _READ if candidate is None or candidate.reading == 'own' else _AGAINST_OWN
        if binding == _SPEAKS:
            candidate = _settled(candidate)
        elif binding == _LATER and candidate is not None:
            later[id(candidate)] = candidate
        elif binding == _AGAINST_OWN and candidate is not None:
            against[id(candidate)] = candidate
        if candidate is not None:
            found.append(candidate)

    broken = (m for m in BROKEN_SERVICE_DATE.finditer(text) if _broken_label_opens(text, lay, rows, m.start('label')))
    for m in itertools.chain(SERVICE_DATE.finditer(text), broken):
        read.add(m.start('label'))
        binding = _binding(text, lay, m.start('label'), m.end('label'), _label_kind(text, m))
        if binding == _GOVERNED:
            governed.append(m)
            continue
        bind(_read_label(text, rows, m), binding)
    for m in DATE_LABEL.finditer(text):
        if m.start() in read:
            continue
        binding = _binding(text, lay, m.start('label'), m.end('label'), _label_kind(text, m))
        if binding != _GOVERNED:
            bind(_unread_label(text, rows, m), binding)
    found = _later_settled(found, later, against)
    found += _time_directed(text, lay, governed, found)
    return _own_dates_in_doubt(text, lay, _after_another_header(text, lay, tuple(found) + _title_candidates(text, lay)))


# Fix round (dates lens, F1; the refutation of the integrated head b8cc7b5b5). The elapsed-time rule stopped reading
# "Total time on the date of service: 34 minutes" as a date this service cannot read; that misreading had made the
# installed tree ASK - by accident - a labelled date it otherwise sends, so with a time statement added the head sent
# dates neither installed revision sends. Decided per shape from the source: the note's own date of service beside
# another occurrence's qualified date, or in a procedure part that documents its procedure, is the encounter's date and
# is sent (the installed ask was the misread "34"). Three shapes are wrong or genuinely uncertain, and are asked with or
# without a time statement - each moves an own label only (never a date created or sent):
# - BIRTH: its date is the date the document gives as the patient's date of birth ("Encounter date: 01/01/1998" beside
#   "DOB: 01/01/1998"). Rule N2: a date of birth is never a service date. 'beside' - it speaks (asked) and is quoted,
#   but is never a member's answer: an addendum settles it.
# - PART: it stands in a later numbered part of the document (sections.DOCUMENT_PART numbered after the first: "PART 2 -
#   PROCEDURE NOTE", "Section B: Procedure note", "Part 2: Procedure: Colonoscopy") that the section reader opens as a
#   procedure, and that part documents no procedure - no technique, findings or impression heading in it, up to the
#   next numbered part. Its date then dates the procedure the part only names (an office visit's planned colonoscopy, a
#   2019 procedure note's colonoscopy), not a service this note documents. 'unplaced' - asked; a member's answer equal
#   to it is taken (the member confirms the part dates this encounter).
# - ORDER: it is EARLIER than a labelled date the note itself reads as an EARLIER occurrence's - another occurrence's
#   ('aside') with a history word around it that states an earlier time (_EARLIER_TIME_WORDS: prior, previous, last,
#   recent, index, s/p, ...; never the place word 'outside', fix round 2)
#   and no date qualifier of a planned one (next, planned, scheduled, due, ...) - outside an authored addendum, which
#   is written later ("DOS: 05/01/2019" beside "Index colonoscopy - Encounter date: 10/14/2026"; "Encounter date:
#   01/01/1998" beside "Recent colonoscopy - Date of service: 11/04/2026"). Both cannot be right: a genuine date
#   conflict, never ignored. 'unplaced' - asked; a member's answer equal to it is taken. Both vocabularies are the
#   reader's own closed classes, split by the direction in time they name.
#   Fix round 2 (the differential round, F-4): ORDER's vocabulary is only the history words that state an EARLIER
#   TIME, never a PLACE. "Outside" names another facility, not an earlier time: "Outside colonoscopy (Synthetic
#   Regional Hospital) date of service: 10/27/2026" beside the visit's own "Date of service: 10/13/2026" is consistent
#   with it (a referred, pending or later outside procedure), and ORDER asked the visit's correct date - and, with the
#   own date in doubt, let a member's answer equal to any dated line be taken (F-1). The installed reading is restored.
_PART_NUMBER = re.compile(r'[ \t]*(?=' + DOCUMENT_PART + r')[A-Za-z]+[ \t]+(?P<number>\w+)', re.A)
_FIRST_PART = frozenset(('1', '01', 'I', 'i', 'A'))
_REPORT_BODY = ('technique', 'findings', 'impression')
_PLACE_WORDS = ('outside',)  # the history words that name a place, not a time (fix round 2, F-4)
_EARLIER_TIME_WORDS = tuple(w for words in (words for _, words in _HISTORY_WORDS) for w in words.split('|')
                            if w not in _PLACE_WORDS)
_EARLIER_OCCURRENCE = cues.rx(r'\b(?:' + '|'.join(_EARLIER_TIME_WORDS) + r')\b')
_PLANNED_OCCURRENCE = cues.rx(r'\b(?:next|planned|scheduled|future|follow-?up|repeat|anticipated|tentative|proposed'
                              r'|requested|rescheduled|upcoming|due)\b')
# gi3 dates, B4: what makes a plan item name a later occurrence (_Governance.item_names_later) - the date reader's planned
# qualifiers above (next, planned, scheduled, follow-up, repeat, due ...) and routing's planned clause cues ("will",
# "recommend", "in 6 weeks", "to be scheduled"): each the reader's own closed class.
_LATER_CUES = (_PLANNED_OCCURRENCE,) + tuple(p for _, p in cues.PLANNED_CLAUSE)


def _own_dates_in_doubt(text: str, lay: Layout, found: tuple[_Candidate, ...]) -> tuple[_Candidate, ...]:
    """The own labelled dates the three F1 shapes above put in doubt, moved to 'beside' (BIRTH) or 'unplaced' (PART,
    ORDER); each part of the text read once per text (the numbered parts and the report sections are bisected per label,
    the earlier occurrences' windows read once each)."""
    own = [c for c in found if c.source == 'label' and c.reading == 'own' and c.form == 'read']
    if not own:
        return found
    # the dates the document gives as a date of birth (rule N2's _is_birth), never an own label's own value: a joined
    # header's values are each field's by position ("Visit Date & Date of Birth: 10/14/2026 & 01/01/1998"), where the
    # birth label right before the visit's date does not make it a date of birth
    held_starts, held_ends = [], []
    for s, e in sorted((s.start, s.end) for c in own for s in c.spans):
        if held_ends and s < held_ends[-1]:
            held_ends[-1] = max(held_ends[-1], e)
        else:
            held_starts.append(s)
            held_ends.append(e)

    def own_value(pos: int) -> bool:
        k = bisect.bisect_right(held_starts, pos) - 1
        return k >= 0 and pos < held_ends[k]

    births = {d.value.isoformat() for d in find_dates(text)
              if d.precision == 'day' and _is_birth(text, d.start) and not own_value(d.start)}
    parts = [s for s in lay.sections if s.heading is not None and _PART_NUMBER.match(text, s.start)]
    part_starts = [s.start for s in parts]
    bodies = [s.start for s in lay.sections if s.kind in _REPORT_BODY and s.label in HEADINGS]
    authored = _AUTHORED_ADDENDUM.search(text)
    earlier = ''  # the latest date the note reads as an earlier occurrence's (ORDER), read in the label's 80-character
    for c in found:  # windows either side on its line, as _line_reading reads its qualifiers
        if c.source == 'label' and c.reading == 'aside' and c.form == 'read' and c.value and c.value > earlier \
                and (authored is None or c.span.start < authored.start()):
            lo = max(text.rfind('\n', max(0, c.span.start - 80), c.span.start) + 1, c.span.start - 80, 0)
            hi = text.find('\n', c.span.end, c.span.end + 80)
            hi = min(len(text), c.span.end + 80) if hi < 0 else hi
            if _EARLIER_OCCURRENCE.search(text, lo, hi) and not _PLANNED_OCCURRENCE.search(text, lo, hi):
                earlier = c.value
    moved = {}
    for c in own:
        if c.value in births:
            moved[id(c)] = replace(c, reading='beside', doubt='birth')
            continue
        if c.value < earlier:
            moved[id(c)] = replace(c, reading='unplaced', doubt='order')
            continue
        k = bisect.bisect_right(part_starts, c.span.start) - 1
        if k < 0 or parts[k].kind != 'procedure' \
                or _PART_NUMBER.match(text, parts[k].start).group('number') in _FIRST_PART:
            continue
        part_end = part_starts[k + 1] if k + 1 < len(parts) else len(text)
        b = bisect.bisect_left(bodies, part_starts[k])
        if b < len(bodies) and bodies[b] < part_end:
            continue  # the part documents its procedure: the date is that procedure's, the note's own
        moved[id(c)] = replace(c, reading='unplaced', doubt='part')
    read = {}  # gi3 fix round 1 (dates-4, cost-2): each procedure section's account read once, never once per label
    for c in own:  # gi3 dates, part 3
        if id(c) not in moved and _plans_procedure(text, lay, c.span.start, bodies, read):
            moved[id(c)] = replace(c, reading='unplaced', doubt='plan')
    return tuple(moved.get(id(c), c) for c in found) if moved else found


# gi3 dates, part 3 (the gi2 known limit dates-planned-no-part, read by the source): after "Plan:" and its item, a
# planned procedure's own heading line ("Procedure: Colonoscopy    Procedure date: 11/04/2026") is a heading the section
# reader knows, so it opened a procedure section that documents nothing, and the planned date was read as the note's own
# and sent. An own label in a procedure section that directly follows a plan section and documents no procedure - no
# technique, findings or impression heading the reader knows from its start on, no statement of what was done in it
# (cues.PERFORMED_CLAUSE, cues.COURSE) - is asked ('plan', as PART asks; interpretation 37's member bound holds: a
# member's answer is taken only where the reading without the doubt takes it).
_PART_ACCOUNT_CUES = tuple(p for _, p in cues.PERFORMED_CLAUSE) + (cues.COURSE,)


def _plans_procedure(text: str, lay: Layout, pos: int, bodies: list, read: Optional[dict] = None) -> bool:
    """Part 3: whether the label at ``pos`` stands in a procedure section right after a plan section that documents no
    procedure (``bodies``: where the report's technique, findings and impression sections start, in order). ``read``
    keeps each section's verdict (gi3 fix round 1, dates-4 and cost-2: every own label rescanned its whole section with
    every cue - quadratic, 72 s at 128,000 characters, past the member's 15 s and analyze's 60 s)."""
    k = bisect.bisect_right(lay.section_starts, pos) - 1  # the layout's own index: never a list per label
    if k < 1 or lay.sections[k].kind != 'procedure' or lay.sections[k - 1].kind != 'plan':
        return False
    sec = lay.sections[k]
    if bodies and bodies[-1] >= sec.start:
        return False  # a technique, findings or impression section from here on: the procedure is documented
    read = {} if read is None else read
    if k not in read:
        read[k] = not any(p.search(text, sec.start, sec.end) for p in _PART_ACCOUNT_CUES)
    return read[k]


_BODY_KINDS = ('technique', 'findings', 'impression', 'assessment', 'exam', 'mdm', 'time')
# Fix round (dates lens, F3): an authored addendum's heading - the part's name alone on its line, perhaps marked as a
# heading ("## Addendum", "**Addendum**") or closed by a colon or a dash. A closed list of part names; prose that names
# an addendum ("An addendum may follow.") and the app's own header ("ADDENDUM (revision 2, added ...)") are none.
_AUTHORED_ADDENDUM = cues.rx(r'^[ \t#*]*+(?:addendum|late[ \t]++entry|amendment)[ \t*]*+[:\u2013\u2014-]?+[ \t*]*+$',
                             cues.FLAGS | re.M)


def _after_another_header(text: str, lay: Layout, found: tuple[_Candidate, ...]) -> tuple[_Candidate, ...]:
    """An own labelled date that stands only after the note's body, where the note's header dates another occurrence,
    is asked (gi2 triage, rule U; the installed reader sent the later date: "Outside Procedure date: 10/14/2026" over
    the report's body, then "Addendum" / "Date of service: 10/21/2026" - the body's procedure is dated by the header,
    and 10/21 may only date what was written after it; a must-fix wrong date in 522 constructed texts).

    It applies when the earliest labelled date read as another occurrence's ('aside', a read date) is followed by a
    clinical content section the layout opens with a heading of its closed list (sections.HEADINGS, kinds _BODY_KINDS:
    "Technique:", "Findings:", "Impression:", "Assessment:" - never a title or a header field such as "Procedure note"
    or "Procedure: Colonoscopy"), nothing before that section states the note's own date (no candidate read 'own', or
    'unplaced' with a stated date: an empty "Date of service: TBD" field or an own dated title keeps the header the
    note's own), a header 'aside' date is EARLIER than the own date (a later header date is a planned occurrence no
    performed service is dated by), and no own label stands in the app's addendum or a PDF form or annotation block
    (which extraction places after its page's text). Then the own labels, all after the body, are read 'unplaced':
    they speak and are asked, a member's answer equal to one of them is taken, and the header's other-occurrence date
    stays one (never a member's answer). It only moves a label from 'own' to 'unplaced': no date is created or sent.

    Fix round (dates lens, F3): only own labels that stand in an AUTHORED addendum part after the body - after a line
    that is an addendum's heading alone (_AUTHORED_ADDENDUM: "Addendum", "Addendum:", "ADDENDUM", "Late entry",
    "Amendment"; a closed list of part names, never prose): the date written in an addendum dates the addendum, not what
    the header dates. A footer's own date of service ("Signature" / "Electronically signed ..." / "Date of service:
    10/22/2026" under "Last visit date: 07/14/2026") is the note's own, as at the installed revision. The app's own
    addendum is its header (sections.ADDENDUM_HEADER), never an authored "Addendum:" heading of the same label."""
    aside = [c for c in found if c.source == 'label' and c.reading == 'aside' and c.form == 'read']
    own = [c for c in found if c.source == 'label' and c.reading == 'own' and c.form == 'read']
    if not aside or not own:
        return found
    first = min(aside, key=lambda c: c.span.start)
    body = next((s.start for s in lay.sections if s.start >= first.span.end and s.label in HEADINGS
                 and s.kind in _BODY_KINDS), None)
    # gi3 dates: a candidate a plan or history section holds - a label its reach no longer covers (_settled) or one part
    # 4 asks - is read only to be asked, so it never keeps the header the note's own (the installed reading had none)
    if body is None or any(c.span.start < body and (c.reading == 'own' or (
            c.reading == 'unplaced' and c.form != 'empty'
            and lay.section_at(c.span.start).kind not in NOT_CURRENT_SECTIONS)) for c in found):
        return found
    earliest_own = min(c.value for c in own)
    if not any(c.span.start < body and c.value < earliest_own for c in aside):
        return found
    authored = _AUTHORED_ADDENDUM.search(text, body)
    if authored is None or any(c.span.start < authored.end() for c in own):
        return found  # fix round, F3: an own label that stands in no authored addendum part is the note's own
    added = next((s.start for s in lay.sections if s.heading is not None
                  and ADDENDUM_HEADER.fullmatch(str(s.heading.text))), None)
    if any((added is not None and c.span.start >= added) or lay.section_at(c.span.start).label.startswith('pdf ')
           for c in own):
        return found
    own_ids = {id(c) for c in own}
    return tuple(replace(c, reading='unplaced') if id(c) in own_ids else c for c in found)


_TIME_WORD = cues.rx(r'\btime\b')


def _installed_form(text: str, m: re.Match) -> bool:
    """Whether a SERVICE_DATE match is written as the installed revision 057a7d398 reads a labelled date (rule N7): its
    label names no time and stands on one line (gi3 dates, X3: a label broken over two lines, BROKEN_SERVICE_DATE, was
    never read), its separator is no cell bar (nor, gi3 fix round 1, dates-9, an em dash, a full stop or a full-width
    colon: _UNREAD_SEPARATOR), and its date is no day-first one ("14 Oct 2026", "14-Oct-2026")."""
    return (m.group('dd') is None and _TIME_WORD.search(text, m.start('label'), m.end('label')) is None
            and '\n' not in text[m.start('label'):m.end('label')] and '|' not in text[m.end('label'):m.start('date')]
            and _UNREAD_SEPARATOR.search(text, m.end('label'), m.start('date')) is None)


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
    out, heading, title = [], None, _title_start(text)
    for index, (ls, le) in enumerate(lines):
        sec = lay.section_at(ls)
        if sec.kind in NOT_CURRENT_SECTIONS and sec.start != title:  # gi3 dates, RC5: the title's section reads as any
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
                    out.append(_line_under_another(text, dated, ls))
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


def _line_under_another(text: str, c: _Candidate, ls: int) -> _Candidate:
    """The narrow source rule (a) for a dated service line ('line', 'aside': it never speaks, and its date is the
    evidence a member's answer may agree with when the note gives no date of its own): standing in a section whose
    heading names another occurrence (_OccurrenceScope.heading_governs), its date is that occurrence's - quoted as
    _ElsewhereSpan, never a member's answer. Read as the service's own, it gave a member's answer once the label beside
    it under the same heading was asked: "Index procedure - Encounter date:" over "Colonoscopy: 10/27/2026" took a
    member's 10/27, the index procedure's date."""
    if c.source != 'line' or not _occurrence_scope(text).heading_governs(ls):
        return c
    return _Candidate(_ElsewhereSpan(c.span.start, c.span.end, c.span.text), c.value, c.source, c.reading, c.form,
                      tuple(_ElsewhereSpan(e.start, e.end, e.text) for e in c.extra), c.alone, c.installed)


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
            certain, counted = _birth_places(text)
            if run[0] not in certain and (run[0] in counted if label is None
                                          else _WORD_B.match(text, label.start()) is not None):
                # df-d:1 and df-d:5: a date of birth only by a count placement (_Counted) or by a "b." after a word
                # (_WORD_B) - no value, but the line states a date it cannot place: asked, never silent ("Re: Colonoscopy
                # part b. 10/21/2026" let the labelled 10/14 it contradicts be sent)
                unplaced.append(run)
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
# The differential round, df-d:2: the same field with a bracket that is no format ("Date (performed):", "Date of service
# (corrected):", as c3c034a08 read a bracket of up to 20 characters). Only a word list could tell one naming THIS service
# from one naming another event ("Date (signed):"), so its date is neither the line's own nor another field's: one this
# service cannot place - the line speaks against the labelled date and reads no date (_AFTER_VALUE). Read as another
# field's, the line was silent, and "Date of service: 10/14/2026" it contradicts was sent where c3c034a08 asked.
_BRACKETED_DATE_FIELD = cues.rx(r'(?:date' + _DATE_TIME + r'|' + _DATE_LABEL + r')[ \t]*+\([^()\n]{0,20}+\)')


# The final refutation, fr-dr:3: where another field's VALUE ends before a later date - a semicolon, a comma, a spaced
# dash, a field break, a bracket it does not open, or the field's own date (_GAP_DATE).
_VALUE_END = re.compile(r'[;,]|[ \t][-–—][ \t]|\t| {2,}')
_AFTER_VALUE = -1  # _other_field: the date follows another field whose value had ended, or a date field whose bracket
# is no format (df-d:2) - neither that field's nor certainly the line's own


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
    if _BRACKETED_DATE_FIELD.fullmatch(text, s, e) is not None:
        return _AFTER_VALUE  # df-d:2: a date field whose bracket is no format - a date this service cannot place
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
    # gi3 dates, RC6: the place-of-service and setting labels share the date labels' binding (_binding). A label the
    # plan's or history's reach no longer covers ("Charge information" / "Place of service: 22") speaks against the
    # setting the note states as its own - a conflict, asked - but is never the setting by itself (alone, it is left
    # unread as the installed reading left it, so a member's answer is taken as before).
    found, beside = [], []
    for m in POS.finditer(text):
        binding = _binding(text, lay, m.start(), m.end())
        if binding == _GOVERNED:
            continue
        code = m.group('code')
        (found if binding == _READ else beside).append(
            (POS_CODES.get(code, f'unrecognised place-of-service code {code}'), _span(text, m.start(), m.end())))
    for m in SETTING_LABEL.finditer(text):
        if POS.match(text, m.start()):
            continue
        binding = _binding(text, lay, m.start(), m.end())
        if binding == _GOVERNED:
            continue
        value_start = m.start('value')
        for setting, pattern in SETTING_WORDS:
            for w in pattern.finditer(m.group('value')):
                (found if binding == _READ else beside).append((setting, _span(text, m.start(), value_start + w.end())))
    for setting, m in phrases:
        if is_current_statement(text, lay, m.start(), m.end()):
            found.append((setting, _span(text, m.start(), m.end())))
    return found + beside if found else found


def _patient_status(text: str, lay: Layout) -> list[tuple[str, Span]]:
    """The documented new/established statements: never one a plan section governs (gi3 dates, RC6: the date labels'
    binding, _binding - one the plan's reach no longer covers speaks against the note's own, never by itself; a history
    section's statement is read, as before)."""
    found, beside = [], []
    for m in PATIENT_STATUS.finditer(text):
        lo, _ = _near(text, m.start(), m.end(), 40)
        if NEGATED_BEFORE.search(text, lo, m.start()):
            continue
        binding = _binding(text, lay, m.start(), m.end()) if lay.section_at(m.start()).kind == 'plan' else _READ
        if binding == _GOVERNED:
            continue
        value = (m.group('v') or m.group('v2') or m.group('v3')).lower()
        (found if binding == _READ else beside).append((value, _span(text, m.start(), m.end())))
    return found + beside if found else found


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
# gi3 fix round 1 (dates-9): the forms named are every form _installed_form refuses - a label broken over two lines
# (gi3 dates, X3) and the separators it did not read now among them - so the note never names forms the source lacks.
FORM_DATE_NOTE = ('A labelled date of service is written in a form this release reads but does not send by itself (a '
                  'day-first date such as "14 Oct 2026", a label naming the time or broken over two lines, an em dash, '
                  "full stop or full-width colon after the label, or a table row), so it is asked; a member's answer "
                  'with that date is taken.')
EMPTY_DATE_NOTE = ('Dated text states no date of its own (an empty or non-date date-of-service field, or a line whose '
                   "dates are another field's or a date of birth), so a member's date is held until the document "
                   'states it.')
# Fix round (dates lens, F1; _own_dates_in_doubt): why an own labelled date nothing qualifies is asked.
BIRTH_DATE_NOTE = ("A labelled date of service states the date the document gives as the patient's date of birth, so "
                   'it is not taken as the date of service.')
PLAN_PROC_DATE_NOTE = ('A date of service is labelled under a procedure heading that follows the plan and documents no '
                       'procedure (no technique, findings or impression), so it may date the planned procedure and is '
                       'not taken as the date of service by itself.')
PART_DATE_NOTE = ('A date of service is labelled in a later numbered part of the document that documents no procedure '
                  '(no technique, findings or impression), so it may date another service than the one the note '
                  'documents and is not taken as the date of service by itself.')
ORDER_DATE_NOTE = ('A labelled date of service is earlier than a date the document gives for an earlier occurrence (a '
                   'prior, last, recent or index one), so the two cannot both be right and it is not taken as '
                   'the date of service by itself.')


def _service_date_fact(found: tuple[_Candidate, ...]) -> Fact:
    """The service date fact (_date_fact). Fix round 2 (the differential round, F-1): where the own-dates-in-doubt rules
    (BIRTH, ORDER, PART) put an own labelled date in doubt, they may only ask - never let a member's answer be taken
    that the reading without them does not take. With the doubted label read as the note's own (as the installed reading
    and b8cc7b5b5 read it), the answers are its own value, or the values a documented conflict lists, or the dates its
    evidence reads; with it in doubt and no other own date, every candidate became the evidence of the date asked, so a
    member's answer equal to ANY dated line was taken and sent (an office visit's "EGD on 05/01/2019": 2019-05-01 sent,
    where 2b82889f held it). Now the date asked is answered only by those answers, less a date of birth (BIRTH:
    _BirthSpan, never a member's answer). The fact itself - its origin, value, note and the spans it quotes, as stored -
    is unchanged; only which of its spans answers moves."""
    if not any(c.doubt for c in found):
        return _date_fact(found)
    without = _date_fact(tuple(replace(c, reading='own', doubt='') if c.doubt else c for c in found))
    if without.origin == 'document' and without.value:
        answers = {without.value}
    else:
        answers = set(documented_values(without)) or _date_readings(without.evidence) or set()
    return _date_fact(found, answers)


def _date_fact(found: tuple[_Candidate, ...], answers: Optional[set] = None) -> Fact:
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
    speaks = [c for c in labels if id(c) not in own_ids and c.reading in ('own', 'unplaced', 'beside')
              and c.form != 'empty']
    support = list(speaks)  # what joins the date's evidence when it agrees: as before, labels only
    speaks += [c for c in found if c.source != 'label' and c.reading in ('own', 'unplaced') and c.form != 'empty']
    values = {c.value for c in lead}
    # df-d:4: a date read 'beside' speaks, but is no value a documented conflict lists, nor a member's answer
    unusable = [c for c in (speaks if lead else found) if c.form != 'read' or c.reading == 'beside']
    note = ' '.join(text for present, text in (
        (any(c.form == 'invalid' for c in unusable), INVALID_DATE_NOTE),
        (any(c.form == 'unread' for c in unusable), UNREAD_DATE_NOTE),
        (any(c.form == 'empty' for c in unusable), EMPTY_DATE_NOTE),
        (not own and any(c.source == 'label' and c.form == 'read' and c.reading == 'own' and not c.alone for c in found),
         FIELD_DATE_NOTE),
        (not own and any(c.source == 'label' and c.form == 'read' and c.reading == 'own' and c.alone and not c.installed
                         for c in found), FORM_DATE_NOTE),
        (not own and any(c.source != 'label' and c.form == 'read' for c in found), EVIDENCE_DATE_NOTE),
        (any(c.reading == 'beside' and not c.doubt for c in unusable)
         or not own and any(c.form == 'read' and c.reading in ('aside', 'other', 'unplaced') and not c.doubt
                            for c in found),
         UNPLACED_DATE_NOTE),
        (any(c.doubt == 'birth' for c in (speaks if lead else found)), BIRTH_DATE_NOTE),
        (any(c.doubt == 'part' for c in (speaks if lead else found)), PART_DATE_NOTE),
        (any(c.doubt == 'plan' for c in (speaks if lead else found)), PLAN_PROC_DATE_NOTE),
        (any(c.doubt == 'order' for c in (speaks if lead else found)), ORDER_DATE_NOTE)) if present)
    if lead and len(values) == 1 and all(c.form == 'read' and c.value in values for c in speaks):
        fact = _fact('service_date', [(c.value, s) for c in lead + support for s in c.spans])
        return fact if own else Fact('service_date', None, 'missing', fact.evidence, FORM_DATE_NOTE)
    unread = tuple(s for c in unusable for s in _evidence_spans(c))
    if lead:
        fact = _fact('service_date', [(c.value, s) for c in lead + speaks if c.form == 'read' and c.reading != 'beside'
                                      for s in c.spans])
        if not unusable:
            return fact
        return Fact('service_date', None, 'conflict', _sorted_spans(fact.evidence + unread), note)
    # with no date of the note's own every candidate is the evidence of the date asked; another occurrence's or another
    # document's dated label or title is quoted, never a date a member's answer agrees with (fr-di:3, _ElsewhereSpan).
    # Fix round 2 (the differential round, F-1): with an own date in doubt, nor is a date the reading without the doubt
    # does not answer with (``answers``, _service_date_fact): a span stating any other date is quoted as _DoubtSideSpan
    fact = _fact('service_date', [(c.value, s) for c in found if c.form == 'read'
                                  for s in _evidence_spans(c, answers)])
    if not found:
        return fact
    if answers is not None:
        unread = tuple(s for c in unusable for s in _evidence_spans(c, answers))
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


class _BirthSpan(_ElsewhereSpan):
    """An own labelled date's evidence whose date is the date the document gives as the patient's date of birth (fix
    round, dates lens F1): never a member's answer, as any _ElsewhereSpan; merge_user_values says why it is held."""


class _DoubtSideSpan(Span):
    """Evidence of a date asked because the own-dates-in-doubt rules (BIRTH, ORDER, PART) put the note's own labelled
    date in doubt and no other own date remains (fix round 2, the differential round's F-1), that states a date the
    reading without those rules does not answer with (_service_date_fact): quoted, stored and shown as any span (equal
    to the plain span it copies), but never a member's answer. Read as the evidence of the date asked, any dated line
    answered the question - an office visit's "EGD on 05/01/2019" took a member's 2019-05-01 and sent it, where the
    installed reading held it beside the note's own "Date of service: 10/13/2026". Not an
    _ElsewhereSpan: its date is not read as another occurrence's, and a member's date equal to it is held with the
    installed note (USER_CONFLICT_NOTE)."""

    def __eq__(self, other):
        return isinstance(other, Span) and (self.start, self.end, self.text) == (other.start, other.end, other.text)

    __hash__ = Span.__hash__


def _evidence_spans(c: _Candidate, answers: Optional[set] = None) -> tuple[Span, ...]:
    """A candidate's spans as the date's evidence: _ElsewhereSpan for a label or title read as another occurrence's or
    another document's (fr-di:3), or as maybe another occurrence's (df-d:4, 'beside'); _BirthSpan for a labelled date
    equal to the document's date of birth (fix round, F1); ``answers`` (an own date in doubt and none other, fix round
    2, F-1: the dates the reading without the doubt answers with): _DoubtSideSpan for a span stating any other date."""
    if c.doubt == 'birth':
        return tuple(_BirthSpan(s.start, s.end, s.text) for s in c.spans)
    if c.source in ('label', 'title') and c.reading in ('aside', 'other', 'beside'):
        return tuple(_ElsewhereSpan(s.start, s.end, s.text) for s in c.spans)
    if answers is not None:
        return tuple(s if _span_dates(s) <= answers else _DoubtSideSpan(s.start, s.end, s.text) for s in c.spans)
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
# GI round 2 (the occurrence investigation's R4 (ii)): a member's date equal to a date this reader reads in the document
# as another occurrence's or another document's, or as possibly one (_ElsewhereSpan: fr-di:3, df-d:4), and never as
# this encounter's, is held as before - but USER_CONFLICT_NOTE said 'the document gives “Date of service: 10/14/2026”.
# Both are kept and neither is used until they agree', as if the two dates differed. This note says why it is held. It
# speaks of what this service READS, never of everything the document states: the same day may also be written in a
# form it does not read ("Date of service: 11/04/26" beside "Next procedure date: 11/04/2026"). It opens with
# USER_CONFLICT_NOTE's prefix, by which every reader - and a rollback to 2b82889f - knows a member conflict.
USER_ELSEWHERE_NOTE = (_USER_CONFLICT_PREFIX + "{user}; this service reads that date in the document as another "
                       "occurrence's or another document's date, or as possibly one ({document}), and not as this "
                       "encounter's date of service. Both are kept and neither is used: correct the metadata, clear it, "
                       'or add an addendum to the document.')
# Fix round (dates lens, F1): a member's date equal to an own labelled date that states the document's date of birth
# (_BirthSpan) - held, and said to be so, never as if it were another occurrence's date. Same prefix.
USER_BIRTH_NOTE = (_USER_CONFLICT_PREFIX + "{user}; the document gives that date as the patient's date of birth, and "
                   "this service does not read the date-of-service label stating it ({document}) as this encounter's "
                   'date of service. Both are kept and neither is used: correct the metadata, clear it, or add an '
                   'addendum to the document.')


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
        if isinstance(span, (_ElsewhereSpan, _DoubtSideSpan)):  # fix round 2, F-1: nor beside an own date in doubt
            continue
        values |= _span_dates(span)
    return values or None


def _span_dates(span) -> set:
    """The calendar dates one evidence span states (ISO strings) - never a date of birth (refutation phase 2, rule N2:
    a date of birth is never read, wherever an evidence span holds one)."""
    quoted = str(span.text)
    return {day.isoformat() for day in (date_from_match(m) for m in FULL_DATE.finditer(quoted)
                                        if _BIRTH_BEFORE.search(quoted, max(0, m.start() - _BIRTH_REACH),
                                                                m.start()) is None) if day}


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
            # GI round 2, R4 (ii): a date this reader reads only as another occurrence's or another document's (or
            # possibly one) is said to be so, quoting the spans that state it - never as if the two dates differed
            elsewhere = [ev for ev in documented.evidence if isinstance(ev, _ElsewhereSpan)
                         and value in _span_dates(ev)] if name == 'service_date' else []
            births = [ev for ev in elsewhere if isinstance(ev, _BirthSpan)]  # fix round, F1
            shown = ', '.join('\u201c' + ' '.join(ev.text.split())[:60] + '\u201d'
                              for ev in (births or elsewhere or documented.evidence)[:3])
            merged[name] = Fact(name, None, 'conflict', documented.evidence,
                                (USER_BIRTH_NOTE if births else USER_ELSEWHERE_NOTE if elsewhere
                                 else USER_CONFLICT_NOTE).format(user=value, document=shown))
            continue
        merged[name] = Fact(name, value, 'user', (), USER_NOTE)
    return merged
