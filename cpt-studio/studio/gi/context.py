"""Encounter context read from the document: service date, setting, billing
context and new/established patient status. See ARCHITECTURE.md section 5.2.

Only explicit statements count. Different documented values are a conflict
(value None, every statement kept as evidence), never a silent choice. A date
or setting written in a plan or history section, or qualified as previous /
next / scheduled, describes another encounter and is not read.
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

SERVICE_DATE = cues.rx(r'(?<![\w/-])(?:date[ \t]+of[ \t]+service|DOS|service[ \t]+date|procedure[ \t]+date'
                       r'|date[ \t]+of[ \t]+procedure|visit[ \t]+date|date[ \t]+of[ \t]+visit|encounter[ \t]+date'
                       r'|date[ \t]+of[ \t]+encounter)\b[ \t]*(?:\([ \t]*DOS[ \t]*\)[ \t]*)?[:#=\u2013|-]?[ \t]*'
                       r'(?:' + _FULL_DATE + r')(?![\w/-])')
# A note's own dated title line ("GI visit - 10/20/2026", "Colonoscopy report: 14 Oct 2026") or its bare header
# "Date:" field: read only near the top
# of the document and only when no labelled service date exists, never in a plan or history section.
TITLE_DATE = cues.rx(r'[ \t]*(?:[A-Za-z][A-Za-z /&,()]{0,60}?\b(?:visit|encounter|consultation|consult|note|report)'
                     r'[ \t]*(?:[-\u2013\u2014:|,]|\bon\b|\bof\b)?|date[ \t]*[:|\u2013-])[ \t]*(?:' + _FULL_DATE + r')[ \t]*$')
TITLE_LINES = 12  # non-empty lines from the top in which a dated title is read
DATE_QUALIFIER = cues.rx(r'\b(?:previous|prior|last|next|planned|scheduled|future|follow-?up|repeat|anticipated'
                         r'|tentative|proposed|requested|rescheduled|upcoming|due)\b')

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
    return Fact(name, None, 'conflict', evidence, 'Conflicting documented values: ' + ', '.join(values) + '.')


def _service_dates(text: str, lay: Layout) -> tuple[list[tuple[str, Span]], list[Span]]:
    """(valid labelled service dates, labelled dates that are not calendar dates)."""
    found, invalid = [], []
    for m in SERVICE_DATE.finditer(text):
        lo, hi = _near(text, m.start(), m.end())
        qualified = DATE_QUALIFIER.search(text, lo, m.start()) or DATE_QUALIFIER.search(text, m.end(), hi)
        if lay.section_at(m.start()).kind in NOT_CURRENT_SECTIONS or qualified:
            continue
        value = date_from_match(m)
        span = _span(text, m.start(), m.end())
        if value is None:
            invalid.append(span)
        else:
            found.append((value.isoformat(), span))
    if not found and not invalid:
        seen = 0
        for ls, le in ((m.start(), m.end()) for m in re.finditer(r'[^\n]+', text)):
            if not text[ls:le].strip():
                continue
            seen += 1
            if seen > TITLE_LINES:
                break
            m = TITLE_DATE.match(text, ls, le)
            if m is None or lay.section_at(ls).kind in NOT_CURRENT_SECTIONS or DATE_QUALIFIER.search(text, ls, le):
                continue
            value = date_from_match(m)
            if value is not None:
                found.append((value.isoformat(), _span(text, ls + len(text[ls:le]) - len(text[ls:le].lstrip()), le)))
    return found, invalid


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


@functools.lru_cache(maxsize=16)
def _context(text: str) -> tuple[Fact, ...]:
    lay = layout(text)
    dates, invalid = _service_dates(text, lay)
    service_date = _fact('service_date', dates)
    if invalid and service_date.origin == 'missing':
        service_date = Fact('service_date', None, 'missing', tuple(invalid),
                            'A labelled service date is not a valid calendar date.')
    elif invalid:
        service_date = Fact('service_date', None, 'conflict',
                            tuple(sorted(service_date.evidence + tuple(invalid), key=lambda s: s.start)),
                            'A labelled service date is not a valid calendar date.')
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


USER_CONFLICT_NOTE = ('Encounter metadata entered by a workspace member gives {user}; the document gives {document}. '
                      'Both are kept and neither is used until they agree: correct the metadata, clear it, or add an '
                      'addendum to the document.')


def merge_user_values(facts: dict[str, Fact], user_values: dict[str, str]) -> dict[str, Fact]:
    """A non-empty user value is encounter metadata: it supplies a fact the document does not give or does not give
    unambiguously (a missing or conflicting documented value), and it agrees with a documented value. A user value
    that DIFFERS from a single documented value is a conflict, kept with both sides, never a silent replacement of the
    clinical documentation (2026-10-27: a member-entered service date 28 years before the documented one was used for
    every dated check and sent to the provider). An empty value leaves the document value. Unknown names or values are
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
        merged[name] = Fact(name, value, 'user', (), USER_NOTE)
    return merged
