"""Units, the citation substrate of design v2 (docs/gemini-migration/FINAL-V2.md 1.2, revised for CO-3, CO-4 and CO-5;
step 1a of 8.1): the revision text cut into numbered units meant to be sentences, each unit's sentence closure, and the
unit framing of the text both Gemini calls read.

**The rule** (1.2, rules 1-8), stated in characters, never in words:
1. Lines are split on ``\\n``. An empty or whitespace-only line is a paragraph break.
2. A line break inside a paragraph is a HARD WRAP, and the unit continues, when the earlier line does not end in
   ``.``, ``!``, ``?`` or ``:`` (closing quotes or brackets after them allowed) and the next line begins with a
   lowercase letter; every other line break ends the unit. The test reads two characters: the earlier line's last
   non-space character (closers skipped) and the next line's first non-space character [R:CO-3].
3. Inside a line, a unit ends after ``.``, ``!`` or ``?``, optionally followed by closing quotes or brackets, when one
   or more spaces follow and then a character that is not a lowercase letter, EXCEPT after a token of one or two letters
   whose first letter is uppercase (an initial or a short title: "E. Morgan", "Dr. B. Prior") [R:CO-4]. A letter is a
   character ``str.isalpha`` accepts and an uppercase letter one ``str.isupper`` accepts (DECISIONS D205), so a digit, a
   subscript, a fraction or a Roman-numeral character is not a letter, and a caseless or titlecase letter is not an
   uppercase one: "of O\u2082. The scope" and a list enumerator such as "1." before an uppercase word each end a unit.
4. A unit longer than UNIT_CHARS (600) characters is split at the last space before 600 (at 600 when it holds none),
   and every piece of it is marked ``forced``.
5. Units never cross a page boundary. Each unit is a contract ``Unit``: ``S<k>`` in document order, offsets in the
   revision text trimmed of surrounding whitespace, its first line, its paragraph and its page.
6. The SENTENCE CLOSURE of a run of units is extended backward over the preceding units of its paragraph while the
   preceding unit does not end in ``.``, ``!``, ``?`` or ``:``, and forward over the following units of the paragraph
   until one ends in them, at most CLOSURE_UNITS (12) units in all [R:CO-3].
7. (Words over consecutive units are located by contract/geometry.py, step 1c, from these offsets.)
8. The framed text keeps v1's page framing: a ``[Page N]`` line before each page. Each unit is written
   ``[S<k>] <text>``, a joined hard wrap inside it written as one space; the units of one line are separated by one
   space, lines by ``\\n``, blank lines kept. A revision that already holds a match of ``\\[S\\d+\\]`` is not framed.

**The interface** (imported by contract/geometry.py, step 1c, and the prompt builders, steps 2a and 2c):
- ``units(text, pages=())``: the units, a tuple of contract ``Unit`` (rules 1-5).
- ``closure(text, units, run)``: the unit ids of a run's sentence closure (rule 6).
- ``framed(text, pages=())``: the segmented document, everything the user turn holds between v1's two marker lines, or
  None when the text cannot be framed (rule 8). The request builder adds the document line and the marker lines.
- ``label_collision(text)``: the offset of the first ``\\[S\\d+\\]`` match, or None: why ``framed`` refused.
- ``rule_constants()``: the segmentation rule's constants, the object whose sha256 FINAL-V2 2.5 pins
  (``interpretation.SEGMENTATION_SHA256``, written by the integration owner after the wave's repairs, DECISIONS D202).
  The constants do not describe every part of the rule (the character classes, the wrap test, the closure order), so
  tests/v2/test_segment.py also pins this module's code by a normalized-AST sha256 (D202): a rule change that keeps
  the constants is still seen.

**Why this is not a reader** (FINAL-V2 5.6, P1): the module decides where a unit begins and ends from character
classes alone (space, lowercase, uppercase, letter, alphanumeric, a decimal digit) and from single characters compared
one at a time. It holds no word, phrase, marker or frame list, imports no ``re`` and calls no string method but
``isspace``, ``islower``, ``isupper``, ``isalpha``, ``isalnum`` and ``find`` with a one-character literal; ``int()``
reads one character of the text, and slices of the text are taken only to copy a unit into the framed text, never to
compare (5.7 measure 4, SingleCharacterGeometry and NoWordLists, with what DECISIONS D205 admits). The framed text, the
units and the closures are pure functions of their arguments: the module keeps no state, and imports only the standard
library and contract types.
"""
from __future__ import annotations

import bisect
from collections.abc import Sequence
from typing import Protocol

from studio.interpretation.contract.types import Unit

UNIT_CHARS = 600  # rule 4: a longer unit is split at the last space before this many characters
CLOSURE_UNITS = 12  # rule 6: a sentence closure holds at most this many units [R:CO-3]
SHORT_TOKEN = 2  # rule 3: a period after a token of at most this many letters, the first uppercase, ends no unit

_PAGE, _BLANK, _RUN = 0, 1, 2  # the three kinds of framed line: a [Page N] line, a blank line, a line of units


class Page(Protocol):
    """What a page is here: studio.types.PageSpan's fields. page: the page's number, as its [Page N] line shows it and
    as Unit.page records it; start, end: the page's offsets in the revision text. The pages, sorted by start (an empty
    page before the page that starts where it stands), must tile the text exactly, as v1's
    participants.prompt.framed_document requires: the first starts at 0, each starts where the one before ends, the
    last ends at the text's end."""

    @property
    def page(self) -> int: ...

    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


# --- the interface ----------------------------------------------------------------------------------------------------


def units(text: str, pages: Sequence[Page] = ()) -> tuple[Unit, ...]:
    """The units of ``text``, in document order (FINAL-V2 1.2 rules 1-5): ids S1..Sn; ``text[unit.start:unit.end]`` is
    the unit, trimmed of surrounding whitespace and never empty; ``line`` the 1-based number of the line holding its
    start (lines split on \\n); ``paragraph`` the 1-based number of its paragraph (paragraphs holding text, counted in
    order); ``page`` the number of the page holding it; ``forced`` True for every piece of a unit split at 600
    characters. Every non-whitespace character of the text lies in exactly one unit.

    ``pages``: the revision's page spans (studio.types.PageSpan), which must tile the text; none means one page,
    numbered 1. TypeError when ``text`` is not a str or a page field not an int; ValueError when the pages do not tile
    the text (``framed`` returns None for the same text, as v1's framing does)."""
    return _segment(text, _tiling(text, pages))[0]


def closure(text: str, units: Sequence[Unit], run: Sequence[str]) -> tuple[str, ...]:
    """The unit ids of the sentence closure of ``run`` (FINAL-V2 1.2 rule 6 [R:CO-3]), in document order: the run,
    extended backward over the preceding units of its paragraph while the preceding unit does not end in ``.``, ``!``,
    ``?`` or ``:`` (closing quotes or brackets after them allowed, as rule 2 reads a line's end), then forward over the
    following units of the paragraph until one ends in them; at most CLOSURE_UNITS units in all, the backward extension
    taken first, nearest unit first. Claims cite, and cards show, the closure of an anchor, and the evidence check
    (3.2.5) accepts any unit of it, so a wrap the join rule misses still brings its negator to the claim and the card.

    ``units`` must be ``units(text, pages)`` of this same text. ``run``: unit ids, one or more consecutive units of one
    paragraph in document order, at most CLOSURE_UNITS of them (3.1 I3's bound on a source or an anchor). ValueError
    otherwise: an unknown id, a gap, a repeat or a reversal, a run across paragraphs or over the bound."""
    if not run:
        raise ValueError('A run cites at least one unit.')
    if units and not units[-1].end <= len(text):
        raise ValueError('The units are not units of this text.')
    place = {unit.id: index for index, unit in enumerate(units)}
    indexes = []
    for unit_id in run:
        if unit_id not in place:
            raise ValueError(f'The run cites {unit_id!r}, which is not a unit of the text.')
        indexes.append(place[unit_id])
    first, last = indexes[0], indexes[-1]
    if indexes != list(range(first, first + len(indexes))):
        raise ValueError('A run cites consecutive units, each once, in document order.')
    if len(indexes) > CLOSURE_UNITS:
        raise ValueError(f'A run cites at most {CLOSURE_UNITS} units; this one cites {len(indexes)}.')
    paragraph = units[first].paragraph
    if units[last].paragraph != paragraph:
        raise ValueError('A run cites units of one paragraph.')
    while (last - first + 1 < CLOSURE_UNITS and first > 0 and units[first - 1].paragraph == paragraph
           and not _closed(text, units[first - 1].start, units[first - 1].end)):
        first -= 1
    while (last - first + 1 < CLOSURE_UNITS and last + 1 < len(units) and units[last + 1].paragraph == paragraph
           and not _closed(text, units[last].start, units[last].end)):
        last += 1
    return tuple(units[index].id for index in range(first, last + 1))


def framed(text: str, pages: Sequence[Page] = ()) -> str | None:
    """The segmented document (FINAL-V2 1.2 rule 8): a ``[Page N]`` line before each page, as v1's framing writes it,
    and the page's lines, each unit written ``[S<k>] <text>`` with every joined hard wrap inside it written as one
    space, the units of one line separated by one space, lines by ``\\n``, every blank line kept as an empty line.

    It is everything the user turn holds between v1's two marker lines: the request builder (contract/extract_prompt,
    step 2a; contract/appraise_prompt, step 2c) adds the document line and the marker lines, as v1's
    participants.prompt.framed_document does. A pure function of the text and its pages: nothing else is read.

    None, so that no request is built, when the text already holds a match of ``\\[S\\d+\\]`` (``label_collision``
    says where; the run is not sent, ``refused: unbuilt``, recorded as a limit) or when the pages do not tile the text
    (as v1's framing). TypeError when ``text`` is not a str or a page field not an int."""
    if not isinstance(text, str):
        raise TypeError('The document text must be a str.')
    if label_collision(text) is not None:
        return None
    try:
        spans = _tiling(text, pages)
    except ValueError:
        return None
    _, items, by_run = _segment(text, spans)
    body = ''
    written = 0
    for kind, index in items:
        if kind == _PAGE:
            line = f'[Page {spans[index][2]}]'
        elif kind == _BLANK:
            line = ''
        elif by_run[index]:
            line = ''
            for unit in by_run[index]:
                if line:
                    line += ' '
                line += f'[{unit.id}] '
                line += _rendered(text, unit.start, unit.end)
        else:
            continue  # a stretch of a line that holds no unit (a page boundary inside its spaces) writes no line
        if written:
            body += '\n'
        body += line
        written += 1
    return body


def label_collision(text: str) -> int | None:
    """The offset of the first match of ``\\[S\\d+\\]`` in ``text`` (FINAL-V2 1.2 rule 8), or None. Scanned by
    characters: an opening bracket, a capital S, one or more decimal digits (``\\d``: any Unicode decimal digit, as the
    pattern matches them), a closing bracket. A text holding one is never framed: its own label could not be told
    from the unit labels."""
    if not isinstance(text, str):
        raise TypeError('The document text must be a str.')
    size = len(text)
    at = text.find('[')
    while at >= 0:
        if at + 1 < size and text[at + 1] == 'S':
            digit = at + 2
            while digit < size and _decimal(text, digit):
                digit += 1
            if at + 2 < digit < size and text[digit] == ']':
                return at
        at = text.find('[', at + 1)
    return None


def rule_constants() -> dict[str, object]:
    """The segmentation rule's constants (FINAL-V2 2.5): the object INTERPRETATION_VERSION's pin hashes, as
    ``contract.jsonschema.sha256_of(rule_constants())``. Each character set here is the exact set its predicate below
    accepts (tests/v2/test_segment.py proves it over every code point). The constants are not the whole rule: the
    letter, uppercase and space classes, the wrap test and the closure order are code, which tests/v2/test_segment.py
    pins by a normalized-AST sha256 of this module (DECISIONS D202), so a rule change that keeps these constants is
    still seen there."""
    return {
        'unit_chars': UNIT_CHARS,
        'closure_units': CLOSURE_UNITS,
        'short_token_letters': SHORT_TOKEN,
        'unit_enders': '.!?',
        'line_enders': '.!?:',
        'closers': '"\'\u201d\u2019)]}\u00bb',
        'label': '[S<k>] ',
        'page_line': '[Page <n>]',
        'refused_when_text_holds': '\\[S\\d+\\]',
    }


# --- the character classes: one character at a time, never a word -----------------------------------------------------


def _ender(character: str) -> bool:
    """``.``, ``!`` or ``?``: after one of them a unit can end inside a line (rule 3)."""
    return character == '.' or character == '!' or character == '?'


def _closer(character: str) -> bool:
    """A closing quote or bracket, allowed after a sentence's end (rules 2, 3 and 6)."""
    return (character == '"' or character == "'" or character == '\u201d' or character == '\u2019'
            or character == ')' or character == ']' or character == '}' or character == '\u00bb')


def _decimal(text: str, at: int) -> bool:
    """Whether ``text[at]`` is a decimal digit, exactly as ``\\d`` matches one in a str pattern (Unicode category Nd):
    int() accepts a single character exactly when it is one. int() reads that one character of the text and nothing
    else (DECISIONS D205)."""
    try:
        int(text[at])
    except ValueError:
        return False
    return True


def _letter(character: str) -> bool:
    """A letter, for the short-token exception (rule 3): a character ``str.isalpha`` accepts (DECISIONS D205). A digit,
    a subscript, a fraction or a Roman-numeral character is not one."""
    return character.isalpha()


def _uppercase(character: str) -> bool:
    """An uppercase letter, for the short-token exception (rule 3): a character ``str.isupper`` accepts (DECISIONS
    D205). A caseless or a titlecase letter is not one."""
    return character.isupper()


# --- the rule ---------------------------------------------------------------------------------------------------------


def _closed(text: str, start: int, end: int) -> bool:
    """Whether ``text[start:end]`` ends in ``.``, ``!``, ``?`` or ``:``, closing quotes or brackets after them allowed:
    its last non-space character, closers skipped (rules 2 and 6)."""
    at = end - 1
    while at >= start and text[at].isspace():
        at -= 1
    while at >= start and _closer(text[at]):
        at -= 1
    return at >= start and (_ender(text[at]) or text[at] == ':')


def _short_token(text: str, start: int, period: int) -> bool:
    """Whether the period at ``period`` follows a token of one or two letters whose first letter is uppercase (rule 3):
    the letters right before it, preceded by no alphanumeric character since ``start`` (the line's stretch)."""
    first = period
    while first > start and _letter(text[first - 1]):
        first -= 1
    if not 0 < period - first <= SHORT_TOKEN:
        return False
    if first > start and text[first - 1].isalnum():
        return False
    return _uppercase(text[first])


def _tiling(text: str, pages: Sequence[Page]) -> list[tuple[int, int, int]]:
    """The pages as (start, end, number), in that order (so an empty page sorts before the page that starts where it
    stands, whatever order the pages came in): one page numbered 1 when none is given. TypeError for a text that is
    not a str or a page field that is not an int; ValueError unless the pages tile the text exactly."""
    if not isinstance(text, str):
        raise TypeError('The document text must be a str.')
    if not pages:
        return [(0, len(text), 1)]
    spans = [(page.start, page.end, page.page) for page in pages]
    for span in spans:
        if not all(type(value) is int for value in span):
            raise TypeError('A page has an int number, start and end.')
    spans.sort()
    if (spans[0][0] != 0 or spans[-1][1] != len(text)
            or any(spans[index - 1][1] != spans[index][0] for index in range(1, len(spans)))):
        raise ValueError('The pages do not tile the text: each starts where the one before ends, from 0 to its end.')
    return spans


def _page_at(starts: list[int], offset: int) -> int:
    """The index of the page holding ``offset``: the last page that starts at or before it."""
    return max(bisect.bisect_right(starts, offset) - 1, 0)


def _headers(items: list[tuple[int, int]], shown: int, page: int) -> int:
    """Writes the [Page N] items of every page up to index ``page`` not yet written; returns how many are written."""
    while shown <= page:
        items.append((_PAGE, shown))
        shown += 1
    return shown


def _layout(text: str, spans: list[tuple[int, int, int]]
            ) -> tuple[list[list[int]], list[tuple[int, int]], list[int]]:
    """The text's stretches (rules 1, 2 and 5): each a run of one or more lines joined by hard wraps, inside one page
    and one paragraph, from its first non-space character to its last, as [start, end, page index, paragraph]; the
    framed lines in document order, as (_PAGE, page index), (_BLANK, 0) or (_RUN, stretch index); each line's start."""
    starts = [span[0] for span in spans]
    runs: list[list[int]] = []
    items: list[tuple[int, int]] = []
    lines: list[int] = []
    shown = 0
    paragraph = 0
    in_paragraph = False
    previous = -1  # the last non-space offset of the line before, when that line holds text
    previous_start = 0
    run: list[int] | None = None
    start = 0
    size = len(text)
    while True:
        newline = text.find('\n', start)
        end = size if newline < 0 else newline
        lines.append(start)
        first = start
        while first < end and text[first].isspace():
            first += 1
        if first == end:  # rule 1: an empty or whitespace-only line is a paragraph break
            shown = _headers(items, shown, _page_at(starts, start))
            items.append((_BLANK, 0))
            in_paragraph, previous, run = False, -1, None
        else:
            last = end - 1
            while text[last].isspace():
                last -= 1
            if not in_paragraph:
                paragraph, in_paragraph = paragraph + 1, True
            wrap = (previous >= 0 and not _closed(text, previous_start, previous + 1) and text[first].islower()
                    and _page_at(starts, previous) == _page_at(starts, first))
            if not wrap:  # rule 2: every line break but a hard wrap ends the unit
                run = None
            at = first
            while at <= last:  # rule 5: a page boundary inside the line ends the unit
                page = _page_at(starts, at)
                shown = _headers(items, shown, page)
                stop = min(last + 1, spans[page][1])
                if run is not None and run[2] == page:
                    run[1] = stop
                else:
                    run = [at, stop, page, paragraph]
                    runs.append(run)
                    items.append((_RUN, len(runs) - 1))
                at = stop
            previous, previous_start = last, start
        if newline < 0:
            break
        start = newline + 1
    _headers(items, shown, len(spans) - 1)
    return runs, items, lines


def _sentences(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """A stretch cut after ``.``, ``!`` or ``?`` (closers allowed) followed by one or more spaces and a character that
    is not a lowercase letter, except after a short token (rule 3); the pieces are not yet trimmed."""
    pieces = []
    begin = at = start
    while at < end:
        mark = text[at]
        if _ender(mark):
            after = at + 1
            while after < end and _closer(text[after]):
                after += 1
            follow = after
            while follow < end and text[follow].isspace():
                follow += 1
            if (after < follow < end and not text[follow].islower()
                    and not (mark == '.' and _short_token(text, start, at))):
                pieces.append((begin, after))
                begin = at = follow
                continue
        at += 1
    pieces.append((begin, end))
    return pieces


def _trimmed(text: str, start: int, end: int) -> tuple[int, int]:
    """[start, end) without surrounding whitespace (rule 5)."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _forced(text: str, start: int, end: int) -> list[tuple[int, int, bool]]:
    """A trimmed unit, split while longer than UNIT_CHARS at the last space before UNIT_CHARS (or at UNIT_CHARS when
    there is none), every piece then marked forced (rule 4)."""
    if end - start <= UNIT_CHARS:
        return [(start, end, False)]
    pieces = []
    while end - start > UNIT_CHARS:
        space = start + UNIT_CHARS - 1
        while space > start and not text[space].isspace():
            space -= 1
        if space > start:
            stop, resume = space, space + 1
            while text[stop - 1].isspace():
                stop -= 1
        else:
            stop = resume = start + UNIT_CHARS
        while text[resume].isspace():
            resume += 1
        pieces.append((start, stop, True))
        start = resume
    pieces.append((start, end, True))
    return pieces


def _segment(text: str, spans: list[tuple[int, int, int]]
             ) -> tuple[tuple[Unit, ...], list[tuple[int, int]], list[list[Unit]]]:
    """The units (rules 1-5), the framed lines, and each stretch's units."""
    runs, items, lines = _layout(text, spans)
    found: list[Unit] = []
    by_run: list[list[Unit]] = []
    for start, end, page, paragraph in runs:
        mine: list[Unit] = []
        for begin, finish in _sentences(text, start, end):
            begin, finish = _trimmed(text, begin, finish)
            if begin == finish:
                continue
            for first, last, forced in _forced(text, begin, finish):
                unit = Unit(id=f'S{len(found) + 1}', start=first, end=last, line=bisect.bisect_right(lines, first),
                            paragraph=paragraph, page=spans[page][2], forced=forced)
                found.append(unit)
                mine.append(unit)
        by_run.append(mine)
    return tuple(found), items, by_run


def _rendered(text: str, start: int, end: int) -> str:
    """A unit as the framed text writes it (rule 8): its own characters, each joined hard wrap inside it (the line
    break with the spaces around it) written as one space. Every line break inside a unit is a joined wrap."""
    out = ''
    copied = start
    newline = text.find('\n', start, end)
    while newline >= 0:
        before = newline
        while before > copied and text[before - 1].isspace():
            before -= 1
        after = newline + 1
        while after < end and text[after].isspace():
            after += 1
        out += text[copied:before]
        out += ' '
        copied = after
        newline = text.find('\n', after, end)
    out += text[copied:end]
    return out
