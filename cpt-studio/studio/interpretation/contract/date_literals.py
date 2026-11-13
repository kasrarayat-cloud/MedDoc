"""The date literals of L1 (docs/gemini-migration/FINAL-V2.md 3.1 L1, 5.0, 5.2, 5.6, 5.7 measure 4; step 1c of 8.1):
v1's eight date functions of studio/interpretation/literals.py - ``_year``, ``_month``, ``_full_value``, ``full_dates``,
``dates`` (with its nested ``free``), ``compare``, ``stored_date`` and ``iso_date`` - copied so that each is AST-equal to
v1's, with the month and weekday tables they need, equal to v1's by sha. The new path executes no v1 code (5.7), and
contract/consistency.py's L1 (step 2b) is its one reader on the new path; interpretation/dates.py is rewired to it in
step 2d.

**Copied as source integrity only** (5.0, 5.6): L1 parses the date literal in Gemini's OWN date and timing words and
compares it with the value Gemini gave - the transcription check of a value, which can only demote. Nothing here reads a
unit around the words, decides a time, or produces a value.

**Pinned instead of exempted** (5.7 measure 4, NoWordLists; REFUTATIONS-V2 section 7 item 2): the two tables
(``_MONTHS``, ``_WEEKDAYS``) are the one module-level string collection in contract/ that NoWordLists cannot admit by
its rule, so tests/v2/test_date_literals.py pins this module's WHOLE top level (arbiter triage 1c#6): exactly the
imports and precision names below, then v1's named constants, its two tables (also by sha), DateLiteral and its eight
functions, each AST-equal to v1's and in v1's order. Any other top-level statement fails it - a timing frame list added
under a date-literal name, however it is built, or a reader in a lambda, a class or a function. The same test proves
every parser equal to v1's by value on v1's literal fixtures, the comparison computed in the test.

What is not v1's text: this docstring, and the three precision names, which are taken from the contract enumeration
(types.Precision) rather than written as a tuple of strings; their values are v1's ('day', 'month', 'year'). Below the
precision names, every line is v1's, in v1's order: the patterns and tables (literals.py 37-52), then DateLiteral and the
eight functions (literals.py 55-174).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from studio.interpretation.contract.types import Precision

DAY = Precision.DAY.value
MONTH = Precision.MONTH.value
YEAR = Precision.YEAR.value

_FLAGS = re.A | re.I
_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
_WEEKDAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')  # date.weekday()'s order
_MONTH = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?'
          r'|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')
_WEEKDAY = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)'
_FULL = (r'(?P<iy>\d{4})-(?P<im>\d{2})-(?P<id>\d{2})'
         r'|(?P<um>\d{1,2})/(?P<ud>\d{1,2})/(?P<uy>\d{4}|\d{2})'
         r'|(?P<lm>' + _MONTH + r')\.?[ \t]+(?P<ld>\d{1,2})(?:st|nd|rd|th)?,?[ \t]+(?P<ly>\d{4})'
         r'|(?P<dd>\d{1,2})(?:st|nd|rd|th)?(?:[ \t]+|-)(?P<dm>' + _MONTH + r')\.?(?:,?[ \t]+|-)(?P<dy>\d{4})')
FULL_DATE = re.compile(r'(?<![\w/-])(?:(?P<wd>' + _WEEKDAY + r')\.?,?[ \t]+)?(?:' + _FULL + r')(?![\w/-])', _FLAGS)
MONTH_YEAR = re.compile(r'(?<![\w/-])(?:(?P<mm>' + _MONTH + r')\.?,?[ \t]+(?P<my>(?:19|20)\d{2})'
                        r'|(?P<nm>\d{1,2})/(?P<ny>(?:19|20)\d{2}))(?![\w/-])', _FLAGS)
_UNITS_AFTER = r'(?:mg|mcg|g|ml|cc|units?|iu|kcal|mm|cm|kg|lbs?|%|x|hours?|hrs?|mins?|minutes?|days?|weeks?|months?)'
BARE_YEAR = re.compile(r'(?<![\w/.:-])(?P<year>(?:19|20)\d{2})(?!\w)(?![/.:-]\d)(?![ \t]*' + _UNITS_AFTER + r'(?!\w))',
                       _FLAGS)


@dataclass(frozen=True)
class DateLiteral:
    """A date read in a text: its offsets in that text, its value (the first day of the month or year for a coarser
    precision) and its precision."""
    start: int
    end: int
    value: date
    precision: str

    @property
    def iso(self) -> str:
        """The value at its own precision: YYYY-MM-DD, YYYY-MM or YYYY."""
        return {DAY: self.value.isoformat(), MONTH: self.value.isoformat()[:7], YEAR: f'{self.value.year:04d}'}[
            self.precision]


def _year(text: str) -> int:
    """A year as written: four digits as they are, two by the %y pivot (00-68 as 20xx, 69-99 as 19xx)."""
    value = int(text)
    if len(text) == 2:
        return 2000 + value if value <= 68 else 1900 + value
    return value


def _month(name: str) -> int:
    return _MONTHS.index(name[:3].lower()) + 1


def _full_value(match: re.Match) -> Optional[date]:
    """The calendar date of a FULL_DATE match; None when there is none, or when its weekday names another day."""
    if match.group('iy'):
        parts = (int(match.group('iy')), int(match.group('im')), int(match.group('id')))
    elif match.group('uy'):
        parts = (_year(match.group('uy')), int(match.group('um')), int(match.group('ud')))
    elif match.group('ly'):
        parts = (int(match.group('ly')), _month(match.group('lm')), int(match.group('ld')))
    else:
        parts = (int(match.group('dy')), _month(match.group('dm')), int(match.group('dd')))
    try:
        day = date(*parts)
    except ValueError:
        return None
    weekday = match.group('wd')
    if weekday and _WEEKDAYS.index(weekday[:3].lower()) != day.weekday():
        return None
    return day


def full_dates(text: str) -> tuple[DateLiteral, ...]:
    """Every full date read in ``text`` (day precision), in order. A date-shaped text that is no calendar date, or whose
    weekday names another day, is not read."""
    found = []
    for match in FULL_DATE.finditer(text):
        value = _full_value(match)
        if value is not None:
            found.append(DateLiteral(match.start(), match.end(), value, DAY))
    return tuple(found)


def dates(text: str) -> tuple[DateLiteral, ...]:
    """Every date literal in ``text``, in order: full dates, then months with a year and bare years only where no finer
    form (read or not) covers them, so "March 14, 2024" is one day and never also a year."""
    found, taken = [], []

    def free(start: int, end: int) -> bool:
        return all(end <= low or start >= high for low, high in taken)

    for match in FULL_DATE.finditer(text):
        taken.append(match.span())
        value = _full_value(match)
        if value is not None:
            found.append(DateLiteral(match.start(), match.end(), value, DAY))
    for match in MONTH_YEAR.finditer(text):
        month = _month(match.group('mm')) if match.group('mm') else int(match.group('nm'))
        year = int(match.group('my') or match.group('ny'))
        if free(*match.span()) and 1 <= month <= 12:
            found.append(DateLiteral(match.start(), match.end(), date(year, month, 1), MONTH))
            taken.append(match.span())
    for match in BARE_YEAR.finditer(text):
        if free(*match.span('year')):
            found.append(DateLiteral(match.start('year'), match.end('year'), date(int(match.group('year')), 1, 1),
                                     YEAR))
    return tuple(sorted(found, key=lambda literal: literal.start))


def compare(value: date, precision: str, service: date) -> int:
    """-1 when the literal is before the service date, 0 when it is the same at the literal's own precision, 1 after
    (gi/context.py compare_to_service, ported)."""
    if precision == YEAR:
        first, second = value.year, service.year
    elif precision == MONTH:
        first, second = (value.year, value.month), (service.year, service.month)
    elif precision == DAY:
        first, second = value, service
    else:
        raise ValueError(f'Unknown precision {precision!r}.')
    return (first > second) - (first < second)


_STORED = {DAY: re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})'), MONTH: re.compile(r'([0-9]{4})-([0-9]{2})'),
           YEAR: re.compile(r'([0-9]{4})')}


def stored_date(value: str, precision: str) -> Optional[date]:
    """The date a stored literal ({'value': iso at its precision, 'precision'}) names, or None when it is no such
    value (a stored record this release cannot read is never compared)."""
    pattern = _STORED.get(precision)
    match = pattern.fullmatch(value) if pattern and isinstance(value, str) else None
    if not match:
        return None
    parts = [int(part) for part in match.groups()] + [1] * (3 - len(match.groups()))
    try:
        return date(*parts)
    except ValueError:
        return None


def iso_date(value: str) -> Optional[date]:
    """A YYYY-MM-DD string as a date, or None."""
    return stored_date(value, DAY)
