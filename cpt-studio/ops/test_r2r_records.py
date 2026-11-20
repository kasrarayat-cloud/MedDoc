"""Repair round r2, lens records (DECISIONS D294 F4). The tree's own source only; no Docker, no database, no network.
(F1, the D15 rollback test's record kinds, went with that test in the Fable coding build.)

F4 - whenever an ops text states a container's stop bound, it states that role's STOP_SECONDS (the worker's 3,600 s
since the Fable coding build, 1,800 s from round r3 to it, the web's 30 s), so a moved bound leaves no stale
statement. The guard reads the forms
STOP_FORMS lists (DECISIONS D297 R2RX-4: it states the forms it reads) - ``--time N``, ``stop timeout N s``, ``N s
outlasts``, ``up to N minutes``, the remaining stage time's ``up to N s``, ``the N s pass``, ``STOP_SECONDS['<role>'],
N s``, the web's graceful stop ``(graceful, N s)``, and the seconds a comment beside a stop_service_container(...,
'<role>') call names - in every ops text: install.py's and every other ops/*.py's comments, docstrings and strings, and
INSTALL.md's prose, each with its whitespace collapsed so a wrapped statement is read whole. Its completeness check
covers every bound it claims (DECISIONS D301 RBRX-2): every statement of EACH role's bound in any spelling must lie in a
listed form, so a statement in a new form fails until its form is listed; a stale value in a form not listed is the one
statement it cannot read. The spellings (``spellings``) are derived from every syntax that states a bound (DECISIONS
D303 RDRX-2, D309 F2): the flags the installer passes it with, a key naming its unit, and its number in every unit it
is in, in every numeral form (digits with any grouping separator, leading or trailing decimal zeros, number words, a
fraction of a larger unit) with every unit form in any letter case and any joiner (spaces, none, any hyphen or dash),
and as a sum of hours, minutes and seconds. A spelling of a role's bound that
states another bound sharing its literal lies in a form OTHER_BOUNDS lists (systemctl reload's 30 s client timeout and
the database's 30 s lock timeout share the web's), each of which must read a statement. The other bounds that shared
the worker's old literal (the 600 s stale-stage sweep, the drain's 600 s) are left alone.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_r2r_*.py' -v
"""
import ast
import functools
import io
import itertools
import re
import sys
import tokenize
import unicodedata
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402

OPS = Path(__file__).resolve().parent


# --- F4 --------------------------------------------------------------------------------------------------------------

TIME = re.compile(r'--time\s+(\d[\d,]*)')
SECONDS = re.compile(r'(\d[\d,]*)\s*s\b')
STOP_CALL = re.compile(r"stop_service_container\([^)]*'(web|worker)'\)")
NUMBER = r'(\d[\d,]*)'
# Every form a statement of a container's stop bound takes in the ops texts (the module docstring, F4): (its name, its
# pattern - the number its last group -, the seconds one unit of the number is, and how it names its role: the group
# naming it (an int), the role the form itself states (a str: a graceful stop is the web's, stopped once its requests
# are drained; the worker's stop lets its stage finish), or None). A form naming no role takes the role named nearest
# before it within ROLE_WINDOW characters, else any role's bound.
STOP_FORMS = (
    ('--time N', re.compile(rf'--time\s+{NUMBER}'), 1, None),
    ('stop timeout N s', re.compile(rf'stop timeout\W{{0,3}}{NUMBER}\s*s\b'), 1, None),
    ('N s outlasts', re.compile(rf'{NUMBER}\s*s outlasts\b'), 1, None),
    ('up to N minutes', re.compile(rf'\bup to {NUMBER} minutes\b'), 60, None),
    ('the remaining stage time, up to N s', re.compile(rf'remaining stage time\W[^.;]*?\bup to {NUMBER}\s*s\b'), 1,
     None),
    ('the N s pass', re.compile(rf'\bthe {NUMBER}\s*s pass\b'), 1, None),
    ("STOP_SECONDS['<role>'], N s", re.compile(rf"STOP_SECONDS\['(web|worker)'\],\s*{NUMBER}\s*s\b"), 1, 1),
    ('(graceful, N s)', re.compile(rf'\(graceful,\s*{NUMBER}\s*s\)'), 1, 'web'),
)
ROLE = re.compile(r'\b(worker|web)\b')
ROLE_WINDOW = 160
# The other bounds a role's bound shares its literal with in the ops texts (DECISIONS D301 RBRX-2): (its name, its
# pattern). A spelling of a role's bound inside one states that other bound, never a stop bound: the completeness check
# leaves it alone, and each must read a statement (an entry that reads nothing is stale).
OTHER_BOUNDS = (
    ("systemctl reload's client timeout, 'gives up at the N s timeout'",
     re.compile(rf'\bgives up at the {NUMBER}\s*s timeout\b')),
    ("the database's lock timeout, \"lock_timeout = 'Ns'\"", re.compile(rf"\block_timeout = '{NUMBER}s'")),
)


def seconds(text: str) -> int:
    return int(text.replace(',', ''))


def stated_stop_bounds(source: str) -> list:
    """(line, role or None, seconds) of every statement of a container's stop bound in a Python source's comments and
    string tokens: each ``--time N`` (the role the same line names, 'worker' before 'web'), and each ``N s`` a comment
    beside a stop_service_container(..., '<role>') call states."""
    found = []
    lines = source.splitlines()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        for offset, line in enumerate(token.string.splitlines()):
            number = token.start[0] + offset
            for match in TIME.finditer(line):
                role = 'worker' if 'worker' in line else 'web' if 'web' in line else None
                found.append((number, role, seconds(match.group(1))))
            if token.type == tokenize.COMMENT:
                call = STOP_CALL.search(lines[number - 1])
                if call:
                    found += [(number, call.group(1), seconds(match.group(1))) for match in SECONDS.finditer(line)]
    return found


def prose(path: Path, text: str | None = None) -> str:
    """What the forms are read over: a Python file's comments (without their '#') and string tokens, in order, or a
    Markdown file's text - its whitespace collapsed, so a statement wrapped across lines or comment lines is one."""
    return _prose(path.suffix, path.read_text(encoding='utf-8') if text is None else text)


@functools.lru_cache(maxsize=64)
def _prose(suffix: str, text: str) -> str:
    """prose over one text, read once per text (a plant changes one text; the guard reads every text for each role)."""
    if suffix == '.py':
        kinds = {tokenize.COMMENT, tokenize.STRING}
        if hasattr(tokenize, 'FSTRING_MIDDLE'):  # an f-string's text, tokenized apart since Python 3.12
            kinds.add(tokenize.FSTRING_MIDDLE)
        text = ' '.join(token.string.lstrip('#') for token in tokenize.generate_tokens(io.StringIO(text).readline)
                        if token.type in kinds)
    return ' '.join(text.split())


def stop_statements(text: str) -> list:
    """(form, (start, end), role or None, seconds) of every statement of a stop bound ``text`` (``prose``) holds in a
    form of STOP_FORMS."""
    found = []
    for name, pattern, unit, names in STOP_FORMS:
        for match in pattern.finditer(text):
            if isinstance(names, int):
                role = match.group(names)
            elif isinstance(names, str):
                role = names
            else:
                before = list(ROLE.finditer(text, max(0, match.start() - ROLE_WINDOW), match.start()))
                role = before[-1].group(1) if before else None
            found.append((name, match.span(), role, seconds(match.group(match.re.groups)) * unit))
    return found


def other_statements(text: str) -> list:
    """(name, (start, end)) of every statement of another bound OTHER_BOUNDS lists that ``text`` (``prose``) holds."""
    return [(name, match.span()) for name, pattern in OTHER_BOUNDS for match in pattern.finditer(text)]


def unaccounted(text: str, bound: int) -> list:
    """Every spelling of ``bound`` (``spellings``) in ``text`` (``prose``) that lies in no listed form - neither a
    statement of a stop bound (STOP_FORMS) nor one of another bound sharing the literal (OTHER_BOUNDS) - with the words
    around it."""
    spans = [span for _, span, _, _ in stop_statements(text)] + [span for _, span in other_statements(text)]
    return [text[max(0, begin - 40):end + 10] for begin, end in _spelled(spellings(bound), text)
            if not any(start <= begin < finish for start, finish in spans)]


@functools.lru_cache(maxsize=256)
def _spelled(pattern: re.Pattern, text: str) -> tuple:
    """The spans of ``pattern``'s matches in ``text``, found once per pattern and text (the completeness check reads
    each role's bound in every ops text, and each plant changes one text)."""
    return tuple(match.span() for match in pattern.finditer(text))


# DECISIONS D303 (RDRX-2) and D309 (F2): every syntax a statement of a container's stop bound takes (``spellings``). The
# flags install.py's own setter and stopper pass a role's STOP_SECONDS with (``setter_flags``, read from its source:
# docker run's --stop-timeout, docker stop's --time), with docker's other spellings of the same option (FLAG_ALIASES:
# docker stop's and restart's short -t and docker compose's --timeout); a key that names its unit ('TimeoutStopSec=1500',
# 'stop_timeout_s: 30'); and the bound's number in each unit of UNITS and SUBSECOND_UNITS it is in - in every numeral
# form (digits with or without any grouping separator, leading zeros, trailing decimal zeros, number words, and, where
# the bound is a fraction of a larger unit, its decimal, '1/2' or '\u00bd', 'half', 'a quarter', 'and a half'
# forms), with
# every unit form in any letter case, joined to its number by spaces, nothing, or any hyphen or dash character - and as
# a sum of hours, minutes and seconds ('25m0s', '1 minute 30 seconds').
FLAG_ALIASES = {'--time': ('-t', '--timeout'), '--stop-timeout': ()}
UNITS = ((Fraction(1), ('s', 'sec', 'secs', 'second', 'seconds', '\u2033')),
         (Fraction(60), ('m', 'min', 'mins', 'minute', 'minutes', '\u2032')),
         (Fraction(3600), ('h', 'hr', 'hrs', 'hour', 'hours')))
MILLISECOND_UNITS = ('ms', 'msec', 'msecs', 'millisecond', 'milliseconds')
SUBSECOND_UNITS = ((Fraction(1, 1000), MILLISECOND_UNITS),
                   (Fraction(1, 10 ** 6), ('\u00b5s', '\u03bcs', 'us', 'usec', 'usecs', 'microsecond', 'microseconds')),
                   (Fraction(1, 10 ** 9), ('ns', 'nsec', 'nsecs', 'nanosecond', 'nanoseconds')))
# the characters a numeral groups its digits with: these and every Unicode space separator (Zs); its decimal separators
GROUPING = ",.'_\u2019\u066c"
DECIMAL = '.,'
SLASHES = '/\u2044\u2215'  # a vulgar fraction's slashes: the solidus, the fraction slash, the division slash
# the fractions of a larger unit a statement names in words or by a vulgar fraction: (numerator, denominator) ->
# (its character, its words)
FRACTIONS = {(1, 2): ('\u00bd', ('half', 'a half', 'one half')),
             (1, 3): ('\u2153', ('a third', 'one third')),
             (2, 3): ('\u2154', ('two thirds',)),
             (1, 4): ('\u00bc', ('quarter', 'a quarter', 'one quarter', 'a fourth', 'one fourth')),
             (3, 4): ('\u00be', ('three quarters', 'three fourths'))}
ONES = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
        'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen')
TENS = ('', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety')
SCALES = ((10 ** 9, 'billion'), (10 ** 6, 'million'), (1000, 'thousand'))


def setter_flags(source: str | None = None) -> tuple:
    """The flags install.py's own setter and stopper pass a role's stop bound with (DECISIONS D303, RDRX-2): every string
    literal starting with '-' that is followed, in a call's arguments or a list or tuple, by an expression naming
    STOP_SECONDS - read from ``source`` (install.py's own, by default, as it stands on disk), so a flag the installer
    starts passing the bound with is a spelling the completeness check reads without being listed by hand."""
    return _flags_of((OPS / 'install.py').read_text(encoding='utf-8') if source is None else source)


@functools.lru_cache(maxsize=8)
def _flags_of(source: str) -> tuple:
    """setter_flags over one source text, parsed once per text (the completeness check spells each role's bound for
    every ops text)."""
    tree = ast.parse(source)
    found = set()
    for node in ast.walk(tree):
        items = node.args if isinstance(node, ast.Call) else node.elts if isinstance(node, (ast.List, ast.Tuple)) else []
        for flag, value in zip(items, items[1:]):
            if (isinstance(flag, ast.Constant) and isinstance(flag.value, str) and flag.value.startswith('-')
                    and 'STOP_SECONDS' in ast.unparse(value)):
                found.add(flag.value)
    return tuple(sorted(found))


@functools.lru_cache(maxsize=1)
def dashes() -> str:
    """Every hyphen or dash character: Unicode's dash punctuation (Pd) with the soft hyphen, the minus sign, the hyphen
    bullet and the modifier minus."""
    found = {chr(code) for code in range(sys.maxunicode + 1) if unicodedata.category(chr(code)) == 'Pd'}
    return ''.join(sorted(found | {'\u00ad', '\u2212', '\u2043', '\u02d7'}))


@functools.lru_cache(maxsize=1)
def spaces() -> str:
    """Every Unicode space separator (Zs): a digit-grouping character as well as a space."""
    return ''.join(chr(code) for code in range(sys.maxunicode + 1) if unicodedata.category(chr(code)) == 'Zs')


@functools.lru_cache(maxsize=1)
def digit_classes() -> tuple:
    """For each digit 0-9, a character class of every Unicode decimal digit of that value (Nd: ASCII, Arabic-Indic,
    fullwidth, ...): a numeral's digits in any script."""
    found = [[] for _ in range(10)]
    for code in range(sys.maxunicode + 1):
        value = unicodedata.decimal(chr(code), None)
        if value is not None:
            found[value].append(chr(code))
    return tuple(_class(''.join(chars)) for chars in found)


# characters that join without a visible mark (zero width space, non-joiner, joiner, word joiner, byte order mark)
INVISIBLE = '\u200b\u200c\u200d\u2060\ufeff'


def _class(chars: str) -> str:
    return '[' + ''.join(re.escape(char) for char in chars) + ']'


def _either(items) -> str:
    return '(?:' + '|'.join(sorted(set(items), key=len, reverse=True)) + ')'


def _joiner() -> str:
    """Between a number and its unit, and between a number word's parts: spaces, nothing (or a joiner without a visible
    mark, INVISIBLE), or any hyphen or dash."""
    gap = rf'[\s{_class(INVISIBLE)[1:-1]}]*'
    return rf'(?:{gap}{_class(dashes())}{gap}|{gap})'


def _written(form: str) -> str:
    """A numeral's text as a pattern: each digit in any script (digit_classes), every other character as itself."""
    classes = digit_classes()
    return ''.join(classes[int(char)] if char.isdigit() else re.escape(char) for char in form)


def _unit(names, final: bool = True) -> str:
    """A unit's forms, in any letter case; a unit inside a sum may run on into the next number ('25m0s')."""
    return '(?i:' + _either(re.escape(name) for name in names) + (r')(?!\w)' if final else r')(?![^\W\d_])')


def _digits(n: int, *, decimals: bool = True) -> str:
    """``n`` in digits: with leading zeros, without or with any one grouping separator (thousands, and the Indian lakh
    grouping), and - ``decimals`` - with trailing decimal zeros; never the tail of a longer number."""
    plain = str(n)
    forms = {plain}
    groups = []
    if n >= 1000:
        groups.append(f'{n:,}'.split(','))
    if n >= 100000:
        head, lakh = plain[:-3], [plain[-3:]]
        while len(head) > 2:
            lakh.insert(0, head[-2:])
            head = head[:-2]
        groups.append([head] + lakh)
    for parts in groups:
        for separator in GROUPING + spaces():
            forms.add(separator.join(parts))
    zero = digit_classes()[0]
    tail = rf'(?:{_class(DECIMAL)}{zero}+)?' if decimals else ''
    return rf'(?<!\d)(?<!\d{_class(GROUPING)}){zero}*' + _either(_written(form) for form in forms) + tail


def _cardinal(n: int) -> list:
    """``n``'s number words (regular expressions), each word's case left to the caller; its words joined by spaces,
    nothing or any dash ('fifteen-hundred', 'twenty-five')."""
    space = join = _joiner()
    if n < 20:
        return [ONES[n]]
    if n < 100:
        tens, ones = divmod(n, 10)
        return [TENS[tens] if ones == 0 else TENS[tens] + join + ONES[ones]]
    out = []
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = rf'(?:a|one){space}hundred' if hundreds == 1 else rf'{ONES[hundreds]}{space}hundred'
        out.append(head if rest == 0 else rf'{head}(?:{space}and)?{space}{_either(_cardinal(rest))}')
    else:
        for size, name in SCALES:
            if n >= size:
                count, rest = divmod(n, size)
                head = rf'(?:a|one){space}{name}' if count == 1 else rf'{_either(_cardinal(count))}{space}{name}'
                out.append(head if rest == 0 else rf'{head}(?:\s*,)?(?:{space}and)?{space}{_either(_cardinal(rest))}')
                break
    if 1100 <= n < 10000 and (n // 100) % 10:  # 'fifteen hundred'
        hundreds, rest = divmod(n, 100)
        head = rf'{_either(_cardinal(hundreds))}{space}hundred'
        out.append(head if rest == 0 else rf'{head}(?:{space}and)?{space}{_either(_cardinal(rest))}')
    return out


def _numeral(n: int) -> str:
    """``n`` in every numeral form a count of units takes: its digits and its words (one: also 'a' or 'an')."""
    words = _cardinal(n) + (['a', 'an'] if n == 1 else [])
    return _either([_digits(n), r'(?<!\w)(?i:' + _either(words) + ')'])


def _fraction_words(fraction: tuple, *, article: bool) -> str:
    """The words of a fraction (a half, two thirds), its parts joined by spaces or any dash; without its article too
    unless ``article`` (after 'and': 'and a half')."""
    words = FRACTIONS[fraction][1]
    if article:
        words = tuple(word for word in words if ' ' in word)
    return '(?i:' + _either(re.escape(word).replace(r'\ ', _joiner()) for word in words) + ')'


def _fractional(value: Fraction, names) -> list:
    """The spellings of a ``value`` of the unit ``names`` that is not whole: its decimal (when it ends), its vulgar
    fraction in lowest terms ('1/2', '5/12', mixed '1 1/2' or improper '3/2') and, for the halves, thirds and
    quarters, its fraction character ('\u00bd', mixed '1\u00bd') and its words ('half a minute', 'a quarter of
    an hour', 'one and a half minutes', 'a minute and a half'), each with its unit."""
    unit, join, out = _unit(names), _joiner(), []
    whole, part = divmod(value.numerator, value.denominator)
    zero = digit_classes()[0]
    denominator = value.denominator
    while denominator % 2 == 0:
        denominator //= 2
    while denominator % 5 == 0:
        denominator //= 5
    if denominator == 1:  # a decimal that ends: 0.5, 2.25
        digits = str(value.numerator * 10 ** 12 // value.denominator).rjust(13, '0')
        integer, decimals = digits[:-12].lstrip('0'), digits[-12:].rstrip('0')
        head = (rf'(?<!\d)(?<!\d{_class(GROUPING)}){zero}*' if not integer else _digits(int(integer), decimals=False))
        out.append(rf'{head}{_class(DECIMAL)}{_written(decimals)}{zero}*{join}{unit}')
    fraction = (part, value.denominator)
    over = rf'\s*{_class(SLASHES)}\s*{_written(str(value.denominator))}(?!\d)'
    slash = _written(str(part)) + over
    char = FRACTIONS[fraction][0] if fraction in FRACTIONS else None
    vulgar = rf'(?:{slash}|{re.escape(char)})' if char else rf'(?:{slash})'
    if whole == 0:
        out.append(rf'(?<![\d{_class(SLASHES)[1:-1]}]){vulgar}{join}{unit}')
    else:
        out.append(rf'{_digits(whole, decimals=False)}{join}{vulgar}{join}{unit}')  # 1 1/2 minutes, 1\u00bd minutes
        improper = _written(str(value.numerator)) + over
        out.append(rf'(?<![\d{_class(SLASHES)[1:-1]}]){improper}{join}{unit}')  # 3/2 minutes
    if fraction not in FRACTIONS:
        return out
    if whole == 0:
        lead = _either([vulgar, _fraction_words(fraction, article=False)])
        out.append(rf'(?<!\w){lead}{join}{unit}')  # half-minute, a quarter hour
        out.append(rf'(?<!\w){lead}\s+(?i:(?:of\s+)?(?:an|a|one))\s+{unit}')  # half a minute, a quarter of an hour
        return out
    after = _fraction_words(fraction, article=True)
    out.append(rf'{_numeral(whole)}\s+(?i:and)\s+{after}{join}{unit}')  # one and a half minutes
    out.append(rf'{_numeral(whole)}{join}{unit}\s+(?i:and)\s+{after}(?!\w)')  # a minute and a half
    return out


def _sums(bound: int) -> list:
    """``bound`` seconds as a sum of hours, minutes and seconds ('25m0s', '1 minute 30 seconds', '0h25m'): every unit
    whose share is not 0, and any of the others, two or more of them, in that order."""
    shares = (bound // 3600, bound % 3600 // 60, bound % 60)
    names = [unit[1] for unit in reversed(UNITS)]
    out = []
    for chosen in itertools.product((False, True), repeat=3):
        if sum(chosen) < 2 or any(share and not take for share, take in zip(shares, chosen)):
            continue
        parts = [(share, unit) for share, unit, take in zip(shares, names, chosen) if take]
        pieces = [rf'{_numeral(share)}{_joiner()}{_unit(unit, final=index == len(parts) - 1)}'
                  for index, (share, unit) in enumerate(parts)]
        out.append(r'(?:\s*,\s*(?i:and\s+)?|\s+(?i:and)\s+|\s*)'.join(pieces))
    return out


def _keys(names, n: int) -> str:
    """``n`` of the unit ``names`` stated as a key that names its unit and its value ('TimeoutStopSec=1500',
    "stop_timeout_s: 30", 'seconds: 30', "STOP_SECONDS['worker'] = 1500")."""
    plain = [name for name in names if name.isascii() and name.isalpha()]
    camel = {name[0].upper() + name[1:] for name in plain if len(name) > 1}
    camel |= {name[0].upper() + name[1].upper() + name[2:] for name in plain if len(name) > 3 and name[1:4] == 'sec'}
    alone = [name for name in plain if len(name) > 2]
    unit = (rf'(?:[A-Za-z_][\w.\-]*?(?:[_.\-](?i:{_either(plain)})|(?<=[a-z\d]){_either(camel)})'
            rf'|(?i:{_either(alone)}))')
    value = rf'(?:\[[^\[\]]{{0,40}}\])?["\']?\s*[:=]\s*["\']?'
    return (rf'(?<![\w.\-])(?=[\w.\-]*(?:\[[^\[\]]{{0,40}}\])?["\']?\s*[:=])' + unit + value + _digits(n)
            + rf'(?!\d)(?!{_class(GROUPING)}\d)')


@functools.lru_cache(maxsize=64)
def _spelling_pattern(bound: int, flags: tuple) -> re.Pattern:
    """spellings(bound) for the flags ``flags`` (setter_flags with FLAG_ALIASES), compiled once."""
    alternatives = _sums(bound)
    for size, names in SUBSECOND_UNITS + UNITS:
        value = Fraction(bound) / size
        if value.denominator == 1:
            alternatives += [rf'{_numeral(int(value))}{_joiner()}{_unit(names)}', _keys(names, int(value))]
        else:
            alternatives += _fractional(value, names)
    for flag in sorted(flags, key=len, reverse=True):
        joiner = r'(?:\s+|\s*=\s*|)' if not flag.startswith('--') else r'(?:\s+|\s*=\s*)'
        alternatives.append(rf'(?<![\w-]){re.escape(flag)}{joiner}{_digits(bound)}(?!\d)(?!{_class(GROUPING)}\d)')
    # every spelling starts at a digit, a decimal separator or a vulgar fraction, a word's first letter, or a flag's
    # dash: one look at the position first, so the alternatives are tried only where a spelling can start
    start = r'(?:(?=[\d.,\u00bd\u2153\u2154\u00bc\u00be])|(?<!\w)(?=[A-Za-z_])|(?=-))'
    return re.compile(start + '(?:' + '|'.join(f'(?:{item})' for item in alternatives) + ')')


def spellings(bound: int) -> re.Pattern:
    """Every spelling of ``bound`` seconds a statement may take (DECISIONS D303 RDRX-2 and D309 F2: derived from every
    syntax that states the bound, where D301's set read N s, N seconds, --time N and N/60 minutes alone): each flag of
    ``setter_flags`` and its FLAG_ALIASES, as '--flag N', '--flag=N' or (a short flag) '-tN'; a key naming its unit
    (_keys); and the number in each unit of UNITS and SUBSECOND_UNITS it is whole in - in digits (_digits: in any
    script, with leading zeros, any grouping separator of GROUPING or a space, trailing decimal zeros) or in words
    (_cardinal: any letter case, its words joined by spaces, nothing or any dash) - or, where it is a fraction of that
    unit, in its decimal, vulgar and word forms (_fractional); its unit in any of its forms and any letter case, joined
    by spaces, nothing (or a joiner without a visible mark), or any hyphen or dash (_joiner: a compound adjective, 'a
    1,500-second stop'); and as a sum of hours, minutes and seconds (_sums). A spelling read inside a longer statement
    ('two hundred thirty seconds' read as thirty seconds, '1 minute 30 seconds' as 30 seconds) is the fail-closed side:
    the guard fails on it, never passes it. Not read: a number whose unit stands elsewhere (a table's header), a range
    or list whose unit follows its last number only ('25-30 minutes'), clock notation ('0:25:00'), a scale word or
    suffix on digits ('1.5 thousand seconds', '1.5k s'), scientific notation ('1.5e3 s'), a fraction not in lowest
    terms ('25/60 hour'), an arithmetic expression ('25 x 60 s'), a key whose value is in words, Roman numerals and
    other languages' words."""
    flags = tuple(sorted({alias for flag in setter_flags() for alias in (flag, *FLAG_ALIASES.get(flag, ()))}))
    return _spelling_pattern(bound, flags)


def ops_texts() -> list:
    """Every ops text the guard reads: INSTALL.md and every ops/*.py that is not a test module."""
    return sorted(path for path in OPS.glob('*.py') if not path.name.startswith('test_')) + [OPS / 'INSTALL.md']


class R2RStopBoundStated(unittest.TestCase):
    """F4 (module docstring): the forms STOP_FORMS lists, in every ops text, state their role's bound, and every
    statement of each role's bound is in a listed form (DECISIONS D301 RBRX-2)."""

    def test_every_stated_stop_bound_in_the_installer_is_its_roles(self):
        found = stated_stop_bounds((OPS / 'install.py').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len([item for item in found if item[1] == 'worker']), 3)  # the scan reads something
        for number, role, value in found:
            with self.subTest(line=number):
                self.assertIn(role, install.STOP_SECONDS, f'install.py:{number} states a stop bound of no role')
                self.assertEqual(value, install.STOP_SECONDS[role], f'install.py:{number}')

    def test_every_stated_docker_stop_in_the_ops_texts_is_a_stop_bound(self):
        for path in sorted(OPS.glob('*.py')) + [OPS / 'INSTALL.md']:
            text = path.read_text(encoding='utf-8')
            for number, line in enumerate(text.splitlines(), 1):
                for match in TIME.finditer(line):
                    with self.subTest(path=path.name, line=number):
                        self.assertIn(seconds(match.group(1)), set(install.STOP_SECONDS.values()))

    def test_every_statement_in_a_listed_form_states_its_roles_bound(self):
        read = 0
        for path in ops_texts():
            for name, span, role, value in stop_statements(prose(path)):
                read += 1
                with self.subTest(path=path.name, form=name, at=span):
                    if role is None:
                        self.assertIn(value, set(install.STOP_SECONDS.values()))
                    else:
                        self.assertEqual(value, install.STOP_SECONDS[role])
        self.assertGreaterEqual(read, 15)  # the forms read the texts' statements (16 when the web's form was listed)

    def test_every_statement_of_each_roles_bound_is_in_a_listed_form(self):
        """DECISIONS D301 RBRX-2: the completeness check covers every bound the guard claims - each role's spellings,
        not one role's (a spelling stating another bound that shares the literal lies in a form OTHER_BOUNDS lists)."""
        for role, bound in install.STOP_SECONDS.items():
            for path in ops_texts():
                with self.subTest(role=role, path=path.name):
                    self.assertEqual(unaccounted(prose(path), bound), [],
                                     'a statement of the bound in a form STOP_FORMS does not list')

    def test_each_other_bound_reads_a_statement_and_never_a_stop_statement(self):
        """OTHER_BOUNDS states what the completeness check leaves alone: each form reads a statement in the texts, and
        none lies inside a statement of a stop bound."""
        for name, _ in OTHER_BOUNDS:
            read = 0
            for path in ops_texts():
                text = prose(path)
                stops = [span for _, span, _, _ in stop_statements(text)]
                for other, (start, end) in other_statements(text):
                    if other == name:
                        read += 1
                        with self.subTest(form=name, path=path.name, at=(start, end)):
                            self.assertFalse(any(begin < end and start < finish for begin, finish in stops))
            with self.subTest(form=name):
                self.assertGreaterEqual(read, 1, 'an OTHER_BOUNDS form that reads no statement is stale')

    def test_the_scan_refuses_a_planted_stale_statement(self):
        stale = '--' + 'time 600'  # built, so this file states no stale bound itself (the scan above reads it)
        planted = ("def park():\n"
                   f"    '''park the old worker (docker stop {stale}: its current stage finishes)'''\n"
                   "    stop_service_container(worker, 'worker')  # its current stage finishes (600 s)\n")
        self.assertEqual(stated_stop_bounds(planted), [(2, 'worker', 600), (3, 'worker', 600)])

    def test_the_other_bounds_of_600_s_are_left_alone(self):
        """The boundary: the drain's 600 s (and the stale-stage sweep's, which the texts state since the Fable coding
        build only as the earlier pipeline's) are other bounds, and no listed form reads them."""
        self.assertEqual(install.DRAIN_MAX_SECONDS, 600)
        said = ' '.join((OPS / 'INSTALL.md').read_text(encoding='utf-8').split())
        self.assertTrue('never longer than 600 s' in said, 'INSTALL.md no longer states the drain bound')
        self.assertTrue("(`STALE_RUNNING_SECONDS`, 600 s" in said or 'STALE_RUNNING_SECONDS' not in said)
        self.assertEqual(install.STOP_SECONDS, {'web': 30, 'worker': 3600})
        for path in ops_texts():
            with self.subTest(path=path.name):
                self.assertNotIn(600, {value for _, _, _, value in stop_statements(prose(path))})


if __name__ == '__main__':
    unittest.main()
