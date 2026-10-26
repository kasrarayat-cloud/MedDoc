"""Acrobat's standard field formats, so a field's stored value can be compared with what it shows.

A text field's format action (/AA /F) decides how viewers display its value:
with AFNumber_Format(1, ...) the stored 14 is shown as "14.0", and with
AFDate_FormatEx("mm/dd/yyyy") the stored 10/21/26 as "10/21/2026". That is
display formatting, not a disagreement. Only a script that is exactly one call
to a standard format function (AFNumber_Format, AFPercent_Format,
AFDate_FormatEx, AFDate_Format, AFTime_FormatEx, AFTime_Format,
AFSpecial_Format) with literal arguments is applied, and only to a value that
parses under it; anything else — custom JavaScript, an unparsable value — is
not interpreted, so a difference stays flagged. Times are rendered as
util.printd renders them (pdf.js and Acrobat: HH / H 24-hour, hh / h 12-hour,
MM minutes, ss seconds, tt am / pm) from the value as AFParseTime reads it:
hours and minutes, seconds optional, after the date; an am / pm marker if one
is written, else the hour as written. Where Acrobat's own output is ambiguous
(rounding of a half, the order of a minus sign and a currency symbol, a
two-digit year's century, the case of am / pm), every candidate is returned;
none changes the quantity.

Pure functions; importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import calendar
import datetime
import re
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation

_CALL = re.compile(r'\s*(AFNumber_Format|AFPercent_Format|AFDate_FormatEx|AFDate_Format|AFTime_FormatEx|AFTime_Format|'
                   r'AFSpecial_Format)\s*\((.*)\)\s*;?\s*\Z', re.S)
_ARGUMENT = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(-?\d+(?:\.\d+)?)|(true|false))\s*'
                       r'(,|\Z)')
# sepStyle: (group separator, decimal separator)
SEPARATORS = {0: (',', '.'), 1: ('', '.'), 2: ('.', ','), 3: ('', ','), 4: ("'", '.')}
_NUMBER = re.compile(r'([+-]?)(\d*)(?:[.,](\d*))?\Z')
# AFDate_Format(index): Acrobat's fixed list (AForm.js).
DATE_FORMATS = ['m/d', 'm/d/yy', 'mm/dd/yy', 'mm/yy', 'd-mmm', 'd-mmm-yy', 'dd-mmm-yy', 'yy-mm-dd', 'mmm-yy',
                'mmmm-yy', 'mmm d, yyyy', 'mmmm d, yyyy', 'm/d/yy h:MM tt', 'm/d/yy HH:MM']
_DATE_TOKEN = re.compile(r'yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d|HH|H|hh|h|MM|M|ss|s|tt|t|\\.|.', re.S)
_TIME_TOKENS = frozenset({'HH', 'H', 'hh', 'h', 'MM', 'M', 'ss', 's', 'tt', 't'})
# AFTime_Format(index): Acrobat's fixed list (AForm.js; pdf.js has the same).
TIME_FORMATS = ['HH:MM', 'h:MM tt', 'HH:MM:ss', 'h:MM:ss tt']
_TIME_FIELDS = {'HH': 'H', 'H': 'H', 'hh': 'H', 'h': 'H', 'MM': 'M', 'M': 'M', 'ss': 's', 's': 's'}
_DATE_FIELDS = frozenset({'yyyy', 'yy', 'mmmm', 'mmm', 'mm', 'm', 'dd', 'd'})
_DOTTED_MARKER = re.compile(r'(?<![A-Za-z])([AaPp])\.\s?[Mm]\.')
_MARKERS = {'am': True, 'a': True, 'pm': False, 'p': False}
_MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): number for number, name in enumerate(calendar.month_abbr) if name})
# AFSpecial_Format(psf): zip code, zip+4, phone number, social security number; 9 stands for a digit.
SPECIAL_FORMATS = {0: ('99999',), 1: ('99999-9999',), 2: ('999-9999', '(999) 999-9999'), 3: ('999-99-9999',)}


def displayed_texts(script: str, value: str) -> set[str]:
    """The texts the standard format ``script`` may display for ``value``; empty when ``script`` is not one
    call to a standard format function with literal arguments, or ``value`` does not parse under it."""
    call = _CALL.match(script or '')
    arguments = _arguments(call.group(2)) if call else None
    if arguments is None:
        return set()
    name, value = call.group(1), (value or '').strip()
    try:
        if name == 'AFNumber_Format' and len(arguments) == 6:
            decimals, separators, negative, _, currency, prepend = arguments
            return number_texts(value, int(decimals), int(separators), int(negative), str(currency), prepend is True)
        if name == 'AFPercent_Format' and len(arguments) in (2, 3):
            prepend = len(arguments) == 3 and arguments[2] is True
            return number_texts(value, int(arguments[0]), int(arguments[1]), 0, percent=True,
                                percent_prepend=prepend)
        if name == 'AFDate_FormatEx' and len(arguments) == 1 and isinstance(arguments[0], str):
            return date_texts(value, arguments[0])
        if name == 'AFDate_Format' and len(arguments) == 1 and not isinstance(arguments[0], (str, bool)):
            index = int(arguments[0])
            return date_texts(value, DATE_FORMATS[index]) if 0 <= index < len(DATE_FORMATS) else set()
        if name == 'AFTime_FormatEx' and len(arguments) == 1 and isinstance(arguments[0], str):
            return date_texts(value, arguments[0])
        if name == 'AFTime_Format' and len(arguments) == 1 and not isinstance(arguments[0], (str, bool)):
            index = int(arguments[0])
            return date_texts(value, TIME_FORMATS[index]) if 0 <= index < len(TIME_FORMATS) else set()
        if name == 'AFSpecial_Format' and len(arguments) == 1 and not isinstance(arguments[0], (str, bool)):
            return special_texts(value, int(arguments[0]))
    except (TypeError, ValueError, OverflowError, InvalidOperation):
        return set()
    return set()


def _arguments(text: str) -> list | None:
    """Literal arguments (strings, numbers, booleans) of a call, or None when one is anything else."""
    arguments, position = [], 0
    if not text.strip():
        return []
    while position < len(text):
        match = _ARGUMENT.match(text, position)
        if match is None:
            return None
        double, single, numeric, boolean, separator = match.groups()
        if double is not None or single is not None:
            arguments.append(re.sub(r'\\(.)', r'\1', double if double is not None else single))
        elif numeric is not None:
            arguments.append(Decimal(numeric))
        else:
            arguments.append(boolean == 'true')
        position = match.end()
        if not separator:
            break
    return arguments if position >= len(text.rstrip()) else None


# --- numbers --------------------------------------------------------------------------

def parse_number(value: str) -> Decimal | None:
    """A plain number as a viewer stores it: an optional sign, digits, one decimal separator ('.' or ',')."""
    match = _NUMBER.match(value.replace(' ', ''))
    if not match or not (match.group(2) or match.group(3)):
        return None
    sign, whole, fraction = match.group(1), match.group(2) or '0', match.group(3) or ''
    return Decimal(f'{sign}{whole}.{fraction or "0"}')


def number_texts(value: str, decimals: int, separators: int, negative: int, currency: str = '',
                 prepend: bool = True, *, percent: bool = False, percent_prepend: bool = False) -> set[str]:
    number = parse_number(value)
    if number is None or not 0 <= decimals <= 20 or separators not in SEPARATORS:
        return set()
    if percent:
        number *= 100
    step = Decimal(1).scaleb(-decimals)
    rounded = {number.quantize(step, rounding=ROUND_HALF_UP), number.quantize(step, rounding=ROUND_HALF_EVEN),
               Decimal(format(float(number), f'.{decimals}f'))}
    texts = set()
    for amount in rounded:
        digits = grouped(abs(amount), decimals, separators)
        if percent:
            bodies = {'%' + digits if percent_prepend else digits + '%'}
        elif currency:
            bodies = {currency + digits if prepend else digits + currency}
        else:
            bodies = {digits}
        for body in bodies:
            if amount >= 0:
                texts.add(body)
            elif negative == 0:  # a minus sign; with a leading currency symbol it may come before or after it
                texts.add('-' + body)
                if currency and prepend and not percent:
                    texts.add(currency + '-' + digits)
            elif negative == 1:  # shown in red, without a sign
                texts.add(body)
            else:  # in parentheses (2 black, 3 red)
                texts.add('(' + body + ')')
    return texts


def grouped(amount: Decimal, decimals: int, separators: int) -> str:
    group, point = SEPARATORS[separators]
    whole, _, fraction = f'{amount:.{decimals}f}'.partition('.')
    if group:
        whole = f'{int(whole):,}'.replace(',', group)
    return whole + (point + fraction if decimals else '')


# --- dates ----------------------------------------------------------------------------

def date_texts(value: str, form: str) -> set[str]:
    tokens = _DATE_TOKEN.findall(form)
    if any(token in _TIME_TOKENS for token in tokens):
        return time_texts(value, tokens)
    return {render_date(date, tokens) for date in parse_dates(value, tokens)}


def time_texts(value: str, tokens: list[str]) -> set[str]:
    """What a format with a time shows for ``value``: its date part (if the format has one) read as parse_dates
    reads it, then hours and minutes (seconds optional, else 0) with an optional am / pm marker; nothing when
    the value has any other word, more than one marker, or a part out of range."""
    value = _DOTTED_MARKER.sub(lambda match: match.group(1) + 'm', value)
    words = re.findall(r'[A-Za-z]+', value)
    markers = [word.lower() for word in words if word.lower() in _MARKERS]
    if len(markers) > 1 or any(word.lower() not in _MARKERS and word.lower() not in _MONTHS for word in words):
        return set()
    numbers = [int(part) for part in re.findall(r'\d+', value)]
    date_tokens = [token for token in tokens if token in _DATE_FIELDS]
    fields = list(dict.fromkeys(_TIME_FIELDS[token] for token in tokens if token in _TIME_FIELDS))
    first_time = next(index for index, token in enumerate(tokens) if token in _TIME_TOKENS)
    time_first = not any(token in _DATE_FIELDS for token in tokens[:first_time])
    date_count = len(date_tokens) - sum(1 for word in words if word.lower() in _MONTHS)
    time_count = len(numbers) - date_count
    if date_count < 0 or time_count not in (2, 3) or (time_count == 3 and 's' not in fields):
        return set()
    clock = numbers[:time_count] if time_first and date_tokens else numbers[date_count:]
    date_numbers = numbers[time_count:] if time_first and date_tokens else numbers[:date_count]
    hours, minutes, seconds = clock[0], clock[1], clock[2] if len(clock) == 3 else 0
    if markers:
        if not 1 <= hours <= 12:
            return set()
        hours = hours % 12 + (0 if _MARKERS[markers[0]] else 12)
    if hours > 23 or minutes > 59 or seconds > 59:
        return set()
    if date_tokens:
        months = ' '.join(word for word in words if word.lower() in _MONTHS)
        dates = parse_dates(' '.join([months, *map(str, date_numbers)]), date_tokens)
        if not dates:
            return set()
    else:
        dates = [datetime.date(2000, 1, 1)]  # no date is shown
    texts = set()
    for date in dates:
        moment = datetime.datetime(date.year, date.month, date.day, hours, minutes, seconds)
        for upper in (False, True):
            texts.add(render_date(moment, tokens, upper=upper))
    return texts


def parse_dates(value: str, tokens: list[str]) -> list[datetime.date]:
    """The dates ``value`` may name, read with the field order of the format (a two-digit year in either
    century); none when its parts do not fit that order."""
    order = [token[0] for token in tokens if token in _DATE_FIELDS]
    named = [_MONTHS[word.lower()] for word in re.findall(r'[A-Za-z]+', value) if word.lower() in _MONTHS]
    numbers = [int(part) for part in re.findall(r'\d+', value)]
    fields: dict[str, int] = {}
    if named:
        if len(named) != 1 or 'm' not in order:
            return []
        fields['m'] = named[0]
        order = [field for field in order if field != 'm']
    if len(numbers) != len(order):
        return []
    fields.update(zip(order, numbers))
    years = [fields['y']] if fields.get('y', 0) >= 100 else (
        [2000 + fields['y'], 1900 + fields['y']] if 'y' in fields else [2000])
    dates = []
    for year in years:
        try:
            dates.append(datetime.date(year, fields.get('m', 1), fields.get('d', 1)))
        except ValueError:
            continue
    return dates


def render_date(date: datetime.date, tokens: list[str], *, upper: bool = False) -> str:
    """``date`` (a datetime when the format has a time) as util.printd renders ``tokens``; ``upper`` writes the
    am / pm marker in capitals."""
    parts = []
    hours, minutes, seconds = (date.hour, date.minute, date.second) if isinstance(date, datetime.datetime) else (0, 0, 0)
    for token in tokens:
        if token in _TIME_TOKENS:
            parts.append(_time_part(token, hours, minutes, seconds, upper))
            continue
        if token == 'yyyy':
            parts.append(f'{date.year:04d}')
        elif token == 'yy':
            parts.append(f'{date.year % 100:02d}')
        elif token == 'mmmm':
            parts.append(calendar.month_name[date.month])
        elif token == 'mmm':
            parts.append(calendar.month_abbr[date.month])
        elif token == 'mm':
            parts.append(f'{date.month:02d}')
        elif token == 'm':
            parts.append(str(date.month))
        elif token == 'dddd':
            parts.append(calendar.day_name[date.weekday()])
        elif token == 'ddd':
            parts.append(calendar.day_abbr[date.weekday()])
        elif token == 'dd':
            parts.append(f'{date.day:02d}')
        elif token == 'd':
            parts.append(str(date.day))
        else:
            parts.append(token[1:] if token.startswith('\\') else token)
    return ''.join(parts)


def _time_part(token: str, hours: int, minutes: int, seconds: int, upper: bool) -> str:
    twelve = 1 + (hours + 11) % 12
    marker = ('am' if hours < 12 else 'pm')[:2 if token == 'tt' else 1]
    return {'HH': f'{hours:02d}', 'H': str(hours), 'hh': f'{twelve:02d}', 'h': str(twelve), 'MM': f'{minutes:02d}',
            'M': str(minutes), 'ss': f'{seconds:02d}', 's': str(seconds)}.get(token, marker.upper() if upper else marker)


# --- special formats ------------------------------------------------------------------

def special_texts(value: str, kind: int) -> set[str]:
    digits = re.sub(r'\D', '', value)
    texts = set()
    for pattern in SPECIAL_FORMATS.get(kind, ()):
        if pattern.count('9') == len(digits):
            remaining = iter(digits)
            texts.add(''.join(next(remaining) if char == '9' else char for char in pattern))
    return texts
