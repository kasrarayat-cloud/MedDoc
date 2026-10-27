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

_DATE_LABEL = (r'(?:date[ \t]+of[ \t]+service|DOS|service[ \t]+date|procedure[ \t]+date|date[ \t]+of[ \t]+procedure'
               r'|visit[ \t]+date|date[ \t]+of[ \t]+visit|encounter[ \t]+date|date[ \t]+of[ \t]+encounter)')
_DATE_LABEL_SEP = r'\b[ \t]*(?:\([ \t]*DOS[ \t]*\)[ \t]*)?[:#=\u2013|-]?[ \t]*'
SERVICE_DATE = cues.rx(r'(?<![\w/-])(?P<label>' + _DATE_LABEL + r')' + _DATE_LABEL_SEP
                       + r'(?P<date>' + _FULL_DATE + r')(?![\w/-])')
# Date-shaped text this reader does not read as a date (refutation r1, context-3): a weekday before a date, a
# two-digit year, dashes, dots or year-first slashes, "20th of October". Beside a date-of-service label, or as a title's
# date, it is documented date text a member value must agree with - never a gap a member value silently fills.
_WEEKDAY = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)\.?'
_FULL_DATE_SHAPE = re.sub(r'\(\?P<\w+>', '(?:', _FULL_DATE)
DATE_SHAPE = (r'(?:' + _WEEKDAY + r',?[ \t]+(?:' + _FULL_DATE_SHAPE + r')'
              r'|\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}'
              r'|\d{1,2}(?:st|nd|rd|th)?[ \t]+of[ \t]+' + _MONTH + r'\.?,?[ \t]+\d{2,4}'
              r'|' + _MONTH + r'\.?[ \t]+\d{1,2}(?:st|nd|rd|th)?,?[ \t]+\d{2}'
              r'|' + _FULL_DATE_SHAPE + r')(?![\w/])')
# A date-of-service label whose value is date-shaped text SERVICE_DATE does not read: on the label's own line, or on
# the line under a label that ends its line ("Date of service:" above "10/20/2026", as forms are extracted).
UNREAD_SERVICE_DATE = cues.rx(r'(?<![\w/-])(?P<label>' + _DATE_LABEL + r')' + _DATE_LABEL_SEP
                              + r'(?:(?:[ \t]*\n){1,2}[ \t]*)?(?P<date>' + DATE_SHAPE + r')')
# A note's own dated title line ("GI visit - 10/20/2026", "Colonoscopy report: 14 Oct 2026") or its bare header
# "Date:" field: read only near the top
# of the document and only when no labelled service date exists, never in a plan or history section. A title may
# carry a field label of its own ("Re: GI consultation of 10/20/2026"); such a line is a candidate, never the
# document's heading (refutation r1, negtime-14: a letter's "Date:" beside the consultation it names).
TITLE_DATE = cues.rx(r'[ \t]*(?P<field>[A-Za-z]{2,12}[ \t]*:[ \t]*(?=[A-Za-z]))?'
                     r'(?:(?P<words>[A-Za-z][A-Za-z /&,()\-]{0,60}?)\b(?:visit|encounter|consultation|consult|note|report)'
                     r'[ \t]*(?:[-\u2013\u2014:|,]|\bon\b|\bof\b)?|date[ \t]*[:|\u2013-])[ \t]*'
                     r'(?:' + _FULL_DATE + r'|(?P<unread>' + DATE_SHAPE + r'))[ \t]*$')
# A title whose date stands alone on the next line ("Colonoscopy Report" above "10/20/2026").
TITLE_HEAD = cues.rx(r'[ \t]*(?P<words>[A-Za-z][A-Za-z /&,()\-]{0,60}?)\b(?:visit|encounter|consultation|consult|note'
                     r'|report)[ \t]*[-\u2013\u2014:|,]?[ \t]*$')
DATE_LINE = cues.rx(r'[ \t]*' + DATE_SHAPE + r'[ \t]*$')
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
# The documents other disciplines write - the services reader's roles (pathology, radiology and its imaging,
# anesthesia, nursing). The rule is structural - a dated title names the document it heads - and this is only the
# vocabulary for "another discipline's document" (refutation r1, negtime-14: a pathology report's own date was read
# as the visit's and sent). A title naming a GI service is checked first ("Endoscopic ultrasound report").
_OTHER_DOCUMENT = cues.rx(r'\b(?:pathology|histopathology|histology|cytology|radiology|imaging|CT|MRI|x-?ray'
                          r'|ultrasound|sonography|anesthesia|anaesthesia|nursing|nurse)\b')
_NEUTRAL_WORDS = frozenset(('the', 'this', 'a', 'an'))

POS = cues.rx(r'(?<![\w/-])(?:place[ \t]+of[ \t]+service|POS)\b[ \t]*(?:\([ \t]*POS[ \t]*\)[ \t]*)?(?:code[ \t]*)?'
              r'[:#=\u2013-]?[ \t]*(?P<code>\d{2})(?![\w/-])')
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


@dataclass
class _ServiceDates:
    """What the document says about its date of service, before it becomes one fact (_service_date_fact)."""
    own: list  # (iso value, span): the note's own dates - a plain labelled date, the note's own dated title
    unplaced: list  # (iso value, span): dated text this service cannot place - never the date by itself
    invalid: list  # spans: labelled dates that are no calendar date
    unread: list  # spans: labelled dates in a form this reader does not read


_LABEL_WORDS = re.compile(r"(?<![A-Za-z'’-])((?:[A-Za-z][A-Za-z'’-]* ){1,4})$")
_NOT_ATTACHED = re.compile(r'[:=]|[.;!?](?:\s|$)|\t| {2,}')  # another field's label, a sentence end, a field break
_ROW_BAR = re.compile(r'[ \t]*\|[ \t]*')  # a table row's cell bar keeps the row's words on one item
_HEADS_FIELD = re.compile(r"[A-Za-z0-9 '’/-]{0,40}?[ \t]*[:=]")  # "Next colonoscopy:" - a label of its own
_COMPLETE_FIELD = re.compile(r"[A-Za-z0-9 '’/-]{0,40}?[ \t]*[:=][ \t]*[^\s:=|][^:=|\n]*?(?:\t| {2,}|\|)")
_LEFTOVER_WORD = re.compile(r'[A-Za-z]{2,}')
_THIS_SERVICE = tuple(p for _, p in cues.SERVICE_PATTERNS) + (cues.EM_VISIT, cues.TODAY)


def _label_words(text: str, label_start: int) -> tuple[str, int]:
    """The label's own words before it ("Outside" in "Outside procedure date") and where they start: words joined by
    single spaces only, so a field break (two spaces, a tab), punctuation, a digit or the line start ends them."""
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


def _line_reading(text: str, label_start: int, date_start: int, date_end: int, value: Optional[date]) -> str:
    """How the qualifiers on a labelled date's line read it: 'own', 'another' or 'unplaced' (refutation r1,
    negtime-15: a qualifier of another field or another date discarded the real date, and a letter or title date was
    then taken and sent).

    A qualifier that clearly belongs elsewhere is passed over: one heading a field of its own ("Last name: Synthetic",
    "Next colonoscopy: 10/2029") or one with another date of its own nearer to it ("recall due 10/2029"). One attached
    to the date - nothing but words, single spaces, commas, hyphens, brackets or a row's cell bars between them ("Prior
    DOS", "Outside colonoscopy | Procedure date | ...", "... (scheduled)") - makes it another occurrence's date. Any
    other - across another field's label, a sentence end or a field break ("Visit type: Follow-up", "Colonoscopy
    scheduled. Procedure date: ...") - may or may not be the date's own: the date is held as text this service cannot
    place, never dropped for a title date and never taken. Before the label the history words count too ("Outside"),
    after the date the date qualifiers only. The scans stop 80 characters either side, so a long line costs each date
    only its window."""
    lo = max(text.rfind('\n', max(0, label_start - 80), label_start) + 1, label_start - 80, 0)
    hi = text.find('\n', date_end, date_end + 80)
    hi = min(len(text), date_end + 80) if hi < 0 else hi
    dates, starts = find_dates(text), _date_starts(text)

    def other_dates(a: int, b: int) -> list:
        """The dates in [a, b) other than this one (another day than ``value`` when it is known)."""
        return [dates[j] for j in range(bisect.bisect_left(starts, a), bisect.bisect_left(starts, b))
                if not date_start <= dates[j].start < date_end
                and (value is None or compare_to_service(dates[j], value) != 0)]

    reading = 'own'
    for q in _OTHER_OCCURRENCE.finditer(text, lo, label_start):
        if _COMPLETE_FIELD.match(text, q.end(), label_start) or other_dates(q.end(), label_start):
            continue
        if not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[q.end():label_start])):
            return 'another'
        reading = 'unplaced'
    for q in DATE_QUALIFIER.finditer(text, date_end, hi):
        if other_dates(date_end, q.start()):
            continue
        own = other_dates(q.end(), hi)
        if _HEADS_FIELD.match(text, q.end(), own[0].start if own else hi):
            continue
        if own and own[0].start - q.end() < q.start() - date_end:
            continue
        if not _NOT_ATTACHED.search(_ROW_BAR.sub(' ', text[date_end:q.start()])):
            return 'another'
        reading = 'unplaced'
    return reading


def _labelled_kind(text: str, label_start: int, label_end: int, date_start: int, date_end: int,
                   value: Optional[date]) -> tuple[str, int]:
    """('own' | 'another' | 'unplaced', where the label's phrase starts). A label carrying a word of another occurrence
    ("Outside procedure date", "Index procedure date"), or qualified on its line by a word attached to it, is another
    occurrence's date and is not read. A label carrying any other word this service cannot place ("Initial visit
    date", "Referring visit date"), or one its line may qualify, is not the plain date-of-service label: its date is
    never taken by itself (refutation r1, negtime-8 and negtime-15)."""
    words, start = _label_words(text, label_start)
    if words and _OTHER_OCCURRENCE.search(words):
        return 'another', start
    reading = _line_reading(text, label_start, date_start, date_end, value)
    if reading == 'another':
        return 'another', start
    if reading == 'unplaced' or (words and not _names_this_service(words, words + ' ' + text[label_start:label_end])):
        return 'unplaced', start
    return 'own', label_start


def _service_dates(text: str, lay: Layout) -> _ServiceDates:
    """The labelled dates of service (and, when there are none, the dated titles near the top), sorted by what they
    can say about this note's date."""
    out = _ServiceDates([], [], [], [])
    labelled = set()
    for m in SERVICE_DATE.finditer(text):
        labelled.add(m.start())
        if lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        value = date_from_match(m)
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.start('date'), m.end(), value)
        if kind == 'another':
            continue
        span = _span(text, start, m.end())
        if value is None:
            out.invalid.append(span)
        else:
            (out.own if kind == 'own' else out.unplaced).append((value.isoformat(), span))
    for m in UNREAD_SERVICE_DATE.finditer(text):
        # refutation r1, context-3: a labelled date the reader does not read is still documented date text
        if m.start() in labelled or lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS:
            continue
        kind, start = _labelled_kind(text, m.start('label'), m.end('label'), m.start('date'), m.end('date'), None)
        if kind != 'another':
            out.unread.append(_span(text, start, m.end('date')))
    if not out.own and not out.invalid and not out.unread:
        own, unplaced, unread = _title_dates(text, lay)
        out.own += own
        out.unplaced += unplaced
        out.unread += unread
    return out


@dataclass(frozen=True)
class _Title:
    span: Span
    value: Optional[date]  # None when the title's date is in a form this reader does not read
    qualified: bool
    other_document: bool
    field: bool  # it opens with a field label of its own ("Re: ..."): a candidate, never the document's heading


def _title_dates(text: str, lay: Layout) -> tuple[list, list, list]:
    """(own, unplaced, unread) from the dated titles near the top. Only the FIRST dated title line can be the note's
    heading ("GI visit - 10/20/2026"). A qualified first title ("GI follow-up visit: ...", "Outside colonoscopy report:
    ...") or one whose date is not read gives no date, so the date is asked - and its date is kept as documented text a
    member value must agree with (refutation r1, context-3: such a member date had replaced it silently and was sent).
    A title naming another discipline's document ("Surgical pathology report: ...", "CT ... report: ...") is never the
    note's heading and alone gives no date (refutation r1, negtime-14: its own date was taken and sent); beside the
    note's own dated title it is a second candidate, a conflict with both sides kept. A later unqualified dated title
    with another date makes the date a conflict; a later title qualified as another time ("Next visit: ...") says
    nothing about this note's date."""
    lines = []
    for m in re.finditer(r'[^\n]+', text):
        if text[m.start():m.end()].strip():
            lines.append((m.start(), m.end()))
            if len(lines) == TITLE_LINES:
                break
    titles = []
    for index, (ls, le) in enumerate(lines):
        if lay.section_at(ls).kind in NOT_CURRENT_SECTIONS:
            continue
        m = TITLE_DATE.match(text, ls, le)
        if m is not None:
            value = None if m.group('unread') is not None else date_from_match(m)
            if m.group('unread') is None and value is None:
                continue  # no calendar date
            end, words, field = le, m.group('words') or '', m.group('field') is not None
        else:
            head = TITLE_HEAD.match(text, ls, le)
            if head is None or index + 1 == len(lines) or not DATE_LINE.match(text, *lines[index + 1]):
                continue
            value, end, words, field = None, lines[index + 1][1], head.group('words'), False
        start = ls + len(text[ls:le]) - len(text[ls:le].lstrip())
        other = not any(p.search(words) for _, p in cues.SERVICE_PATTERNS) and bool(_OTHER_DOCUMENT.search(words))
        titles.append(_Title(_span(text, start, end), value, _title_qualified(text, ls, le, m), other, field))
    first = next((t for t in titles if not t.other_document and not t.field), None)
    if first is None:
        return [], [], []
    if first.value is None:
        return [], [], [first.span]
    if first.qualified:
        return [], [(first.value.isoformat(), first.span)], []
    own, other, unread = [], [], []
    for t in titles:
        if t.qualified:
            continue
        if t.value is None:
            unread.append(t.span)
        else:
            (other if t.other_document else own).append((t.value.isoformat(), t.span))
    return own + other, [], unread


def _title_qualified(text: str, ls: int, le: int, m) -> bool:
    """Whether a dated title line names another occurrence: a date qualifier anywhere on it ("follow-up", "next",
    "planned"), or a history word before its date ("Outside", "Prior", "Index", "s/p"; routing's own cues)."""
    if DATE_QUALIFIER.search(text, ls, le):
        return True
    head = text[ls:le]
    return any(pattern.search(head) for _, pattern in _HISTORY_TITLE)


def _settings(text: str, lay: Layout) -> list[tuple[str, Span]]:
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
    for setting, pattern in SETTING_PHRASES:
        for m in pattern.finditer(text):
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


INVALID_DATE_NOTE = 'A labelled service date is not a valid calendar date.'
UNREAD_DATE_NOTE = 'A labelled or title date of service is not written in a form this service reads.'
UNPLACED_DATE_NOTE = ('A dated label or title is qualified, or carries words this service cannot place, so its date is '
                      'not taken as the date of service.')


def _service_date_fact(found: _ServiceDates) -> Fact:
    """The service date fact (refutation r1, context and negtime lenses). The note's own dates, when they agree, are the
    date; own dates that differ - or differ from a date this service cannot place - are a conflict with every side
    kept. Dated text this service does not read or cannot place never supplies the date by itself: the date is asked,
    and that text stays as evidence a member value must agree with (merge_user_values)."""
    unusable = found.invalid + found.unread
    note = ' '.join(text for present, text in ((found.invalid, INVALID_DATE_NOTE), (found.unread, UNREAD_DATE_NOTE),
                                               (found.unplaced and not found.own, UNPLACED_DATE_NOTE)) if present)
    if found.own:
        fact = _fact('service_date', found.own + found.unplaced)
        if not unusable:
            return fact
        return Fact('service_date', None, 'conflict', _sorted_spans(fact.evidence + tuple(unusable)), note)
    if not unusable and not found.unplaced:
        return _fact('service_date', [])
    return Fact('service_date', None, 'missing',
                _sorted_spans(tuple(span for _, span in found.unplaced) + tuple(unusable)), note)


def _sorted_spans(spans) -> tuple[Span, ...]:
    return tuple(sorted(dict.fromkeys(spans), key=lambda s: (s.start, s.end)))


@functools.lru_cache(maxsize=16)
def _context(text: str) -> tuple[Fact, ...]:
    lay = layout(text)
    service_date = _service_date_fact(_service_dates(text, lay))
    setting = _fact('setting', _settings(text, lay))
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
    """The calendar dates documented date text reads (ISO strings), or None when one of the spans reads none - a
    member date can then never be shown to agree with it."""
    values = set()
    for span in spans:
        read = {day.isoformat() for day in (date_from_match(m) for m in FULL_DATE.finditer(str(span.text))) if day}
        if not read:
            return None
        values |= read
    return values


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
            # is checked by the dates it reads: a member date agrees only when it is every one of them (refutation
            # r1, context-3: a member date had replaced such text silently and was sent to the provider).
            if name == 'service_date' and _date_readings(documented.evidence) == {value}:
                merged[name] = Fact(name, value, 'user', (), USER_NOTE)
                continue
            shown = ', '.join('\u201c' + ' '.join(ev.text.split())[:60] + '\u201d' for ev in documented.evidence[:3])
            merged[name] = Fact(name, None, 'conflict', documented.evidence,
                                USER_CONFLICT_NOTE.format(user=value, document=shown))
            continue
        merged[name] = Fact(name, value, 'user', (), USER_NOTE)
    return merged
