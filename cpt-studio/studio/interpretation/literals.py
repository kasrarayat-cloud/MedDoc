"""Literal values inside an attribute's own words (design/contract.md 5.3; design/ADJUDICATION.md EB1): dates with their
precision, sizes, distances, durations and person names. Ported from the legacy date reader (gi/context.py FULL_DATE,
MONTH_YEAR, YEAR, date_from_match, compare_to_service), never calling it: nothing here imports studio.gi (FINAL 3.1).

Every function is pure and reads only the text it is given - which is always the document's own slice of an
attribute's words, never a passage and never the document (EB1). Nothing here decides a value: a parser finds the
literals, and the checks in verify.py compare them with the value Gemini gave.

Dates (contract 5.3):
- a full date at day precision: ISO ``YYYY-MM-DD``, ``M/D/YYYY``, ``M/D/YY`` (the ``%y`` pivot: 00-68 as 20xx, 69-99 as
  19xx), ``Month D, YYYY`` and ``D Month YYYY`` (an ordinal suffix and a full stop after an abbreviated month allowed),
  with an optional weekday before it that must name that date's own day: a weekday naming another day leaves the text
  unread, as an impossible date does (the owner decision of 2026-11-07, ported);
- a month and year at month precision (``January 2024``, ``1/2024``), where no full date covers it;
- a year 1900-2099 standing alone at year precision: not part of a longer number and not followed by a unit, where no
  finer literal covers it.

Person names (contract 5.3): parentheticals removed, closed or left open at the end (so "Grace Okafor, MD (fictional"
and "Grace Okafor, MD (fictional)" give one name), then split into names at commas, semicolons, slashes, ampersands and
the words and, with, or, plus. A name's tokens are its words of two or more letters that are capitalized (or the one word
right after a title, "dr. okafor") and are none of lexicon.NOT_NAMES (titles, credentials, role, facility and function
words); an initial is never a token, and any other word ends the name ("Dr. Lee removed it" is one name). A name is ``titled`` when a title stands right before it and ``credentialed`` when a
credential stands right after it (in its own part, or as the next part on its own: "Grace Okafor, MD").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from studio.interpretation import lexicon

DAY, MONTH, YEAR = 'day', 'month', 'year'
PRECISIONS = (DAY, MONTH, YEAR)

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


# --- sizes, distances, durations (contract 5.3, 6.2, 6.3) --------------------------------------------------------------

_NUMBER = r'\d+(?:\.\d+)?'
_DASH = '\\-\u2010\u2011\u2012\u2013\u2014\u2212'  # the hyphen escaped: safe anywhere in a character class
_BETWEEN = r'[ \t]*(?:[' + _DASH + r']|to|x|\u00d7|by)[ \t]*'
_LENGTH = r'(?P<unit>mm|cm|millimet(?:er|re)s?|centimet(?:er|re)s?)'
SIZE = re.compile(r'(?<![\w.])(?P<a>' + _NUMBER + r')(?:' + _BETWEEN + r'(?P<b>' + _NUMBER + r'))?(?:' + _BETWEEN
                  + r'(?P<c>' + _NUMBER + r'))?[ \t]*[' + _DASH + r']?[ \t]*' + _LENGTH + r'(?!\w)', _FLAGS)
_CM = r'(?:cm|centimet(?:er|re)s?)'
DISTANCE = re.compile(r'(?<!\w)(?:at|to|@)[ \t]+(?P<a>' + _NUMBER + r')[ \t]*' + _CM + r'(?!\w)'
                      r'|(?<![\w.])(?P<b>' + _NUMBER + r')[ \t]*' + _CM + r'(?=[ \t]+from(?!\w))', _FLAGS)
_NUMBER_WORD = (r'(?:(?:twenty|thirty|forty|fifty|sixty)(?:[ \t' + _DASH + r'](?:one|two|three|four|five|six|seven'
                r'|eight|nine))?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen'
                r'|fifteen|sixteen|seventeen|eighteen|nineteen|ninety)')
_WORD_VALUES = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
                'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
                'sixty': 60, 'ninety': 90}
DURATION = re.compile(r'(?<![\w.])(?P<n>' + _NUMBER + r'|' + _NUMBER_WORD + r')(?:[ \t]*(?:[' + _DASH
                      + r']|to)[ \t]*(?P<m>' + _NUMBER + r'))?[ \t]*[' + _DASH
                      + r']?[ \t]*(?P<unit>minutes?|mins?|hours?|hrs?)(?!\w)', _FLAGS)


def _mm(number: str, unit: str) -> float:
    value = float(number)
    return value * 10 if unit.lower().startswith(('cm', 'cent')) else value


def _clean(value: float):
    return int(value) if float(value).is_integer() else round(value, 3)


def distances_cm(text: str) -> tuple:
    """The distances ``text`` states in centimetres ("at 30 cm", "25 cm from the incisors"), in order."""
    return tuple(_clean(float(match.group('a') or match.group('b'))) for match in DISTANCE.finditer(text))


def sizes_mm(text: str) -> tuple:
    """The sizes ``text`` states, in millimetres, in order: each number of a measurement ("7 mm", "5-7 mm", "1.5 cm",
    "10 x 8 mm"), never a distance (distances_cm)."""
    taken = [match.span() for match in DISTANCE.finditer(text)]
    found = []
    for match in SIZE.finditer(text):
        if any(match.start() < high and low < match.end() for low, high in taken):
            continue
        unit = match.group('unit')
        found += [_clean(_mm(match.group(group), unit)) for group in ('a', 'b', 'c') if match.group(group)]
    return tuple(found)


def _number(text: str) -> float:
    if re.fullmatch(_NUMBER, text):
        return float(text)
    words = re.split(r'[ \t' + _DASH + r']+', text.lower())
    return float(sum(_WORD_VALUES[word] for word in words))


def durations_min(text: str) -> tuple:
    """The durations ``text`` states, in minutes ("45 minutes", "1 hour", "thirty mins"), in order."""
    found = []
    for match in DURATION.finditer(text):
        factor = 60 if match.group('unit').lower().startswith('h') else 1
        found.append(_clean(_number(match.group('n')) * factor))
        if match.group('m'):
            found.append(_clean(float(match.group('m')) * factor))
    return tuple(found)


# --- person names (contract 5.3) ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Name:
    """One person name read in a text: its tokens (case folded, in order), and whether a title or a credential marks it
    as a person's name."""
    tokens: tuple[str, ...]
    titled: bool = False
    credentialed: bool = False

    @property
    def surname(self) -> str:
        """The surname-like token: the name's last token ("Grace Okafor" -> okafor)."""
        return self.tokens[-1]

    def as_record(self) -> dict:
        return {'tokens': list(self.tokens), 'titled': self.titled, 'credentialed': self.credentialed}


_PARENTHETICAL = re.compile(r'\([^()]*\)|\[[^\[\]]*\]')
_OPEN_TO_END = re.compile(r'[(\[].*\Z', re.S)
_PART_BREAK = re.compile(r'[,;/&]|(?<!\w)(?:and|with|or|plus)(?!\w)', re.I)
_WORD = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)*")
_TITLES = frozenset(lexicon.fold(title) for title in lexicon.TITLES)
_CREDENTIALS = frozenset(lexicon.fold(credential) for credential in lexicon.CREDENTIALS)


def _without_parentheticals(text: str) -> str:
    previous = None
    while previous != text:
        previous, text = text, _PARENTHETICAL.sub(' ', text)
    return _OPEN_TO_END.sub(' ', text)


def _word(raw: str) -> str:
    """A word as a token compares: folded, a possessive 's removed."""
    folded = lexicon.fold(raw)
    return folded[:-2] if folded.endswith("'s") and len(folded) > 3 else folded


def names(text: str) -> tuple[Name, ...]:
    """The person names ``text`` holds, in order (module docstring)."""
    found: list[Name] = []
    for part in _PART_BREAK.split(_without_parentheticals(text)):
        words = list(_WORD.finditer(part))
        if not words:
            continue
        folded = [_word(word.group(0)) for word in words]
        if all(word in _CREDENTIALS for word in folded) and found:
            found[-1] = Name(found[-1].tokens, found[-1].titled, True)  # "Grace Okafor, MD": the credential's own part
            continue
        tokens: list[str] = []
        titled = credentialed = after_title = False
        for raw, word in zip(words, folded):
            text_ = raw.group(0)
            if word in _TITLES:
                if tokens:  # a title starts another name
                    found.append(Name(tuple(tokens), titled, credentialed))
                    tokens, credentialed = [], False
                titled, after_title = True, True
                continue
            if word in _CREDENTIALS and tokens:
                credentialed = True
                continue
            is_token = len(word) >= 2 and word not in lexicon.NOT_NAMES and (text_[0].isupper() or after_title)
            if is_token:
                tokens.append(word)
                after_title = False
                continue
            if len(text_) == 1 and text_.isupper():  # an initial ("G. Okafor"): part of the name, never a token
                continue
            if tokens:
                found.append(Name(tuple(tokens), titled, credentialed))
                tokens, credentialed = [], False
            titled = after_title = False
        if tokens:
            found.append(Name(tuple(tokens), titled, credentialed))
    return tuple(found)


def name_tokens(found: tuple[Name, ...]) -> frozenset:
    """Every token of ``found``'s names."""
    return frozenset(token for name in found for token in name.tokens)
