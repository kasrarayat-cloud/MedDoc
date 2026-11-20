"""Reading the two final messages (BUILD-SPEC 4.4-4.6; the fix pass, FIX-SPEC sections 1-3): the final JSON, the code
lines, the combination of the two reads, the questions and the citations per line.

Parsing (FIX-SPEC 2). The final answer is exactly the LAST ```json fenced block of the message's text blocks joined in
order (to its closing fence, or to the end of the text when it has none); when that does not parse, the widest {...}
span of the whole text; when that does not parse either, the answer is Unreadable and the round fails (nothing is
resent). An earlier fenced block is never read in its place. Validation is of the shape only:
- the reader's ``codes`` and the checker's ``reviews`` are lists, ``missed_codes`` a list when present;
- every code line (a reader code or a missed code) and every review names its code as a non-empty string, and every
  reader status is one of the three the reader is given;
- a line's modifiers are a list whose items are strings, an integer item read as its decimal string ("25"); absent or
  null they are not given; any other shape is Unreadable, so no modifier is ever dropped or guessed;
- a line's units are a positive integer, or else not given (None), never corrected;
- any other field of the wrong type is not shown (None), never corrected.

Line identity (FIX-SPEC 1). Every final code row carries ``line``: the reader's codes are "L1".."Ln" in the order of its
JSON list, the checker's missed codes "M1".."Mk" in theirs. The checker is given each reader line with its label
(listing) and every review names the line it reviews.

Combination (BUILD-SPEC 4.5; FIX-SPEC 1), the only glue logic: a review belongs to a reader line when it names that line
and the code on that line. A reader line keeps the reader's status only when the reviews that belong to it all say
exactly ``agree`` (at least one) and no other review names it or its code; otherwise it is ``needs_review``, both
reasons kept. A review that belongs to no line - it names no line, an unknown line, or a line with another code - is
unmatched: the round keeps it in the checker's stored result for the operator, and every line it names or whose code it
carries becomes ``needs_review``. An unmatched review can only send a line to a human, never make one ready; the code
never picks a line for it. Every missed code is a line of its own, ``needs_review``. The problems are the reader's
documentation_problems.

Questions (FIX-SPEC 3): the reader's and then the checker's top-level questions, then each line's own question when its
text is not listed yet (compared with case and whitespace folded), each naming the lines it affects; a needs_answer line
that no question names gets the questions of the reviews that agreed with it or, when there are none, CPT Studio's own
question about it, so a member can always answer it.

Citations (FIX-SPEC 1): the joined text is read line by line. A marker is a whole line holding exactly
``LINE L<n> <code>`` (reader), ``REVIEW L<n> <code>`` or ``MISSED M<k> <code>`` (checker), case-sensitive, optionally
after a run of '#' and one space (trailing spaces aside); a code there is 4 digits and then a digit or F, T or U, or a
capital letter and 4 digits. A citation belongs to the most recent marker, and it is filed under that marker's line only
when the marker's code is the code on that line; anything else goes under ``_document``. A line that looks like a marker
but is not one, a heading line that is not a marker (a markdown heading, or a line all in bold), and a code fence (the
final JSON among them) end the current section, so a citation after them is never filed under the line before them. A
cited block that a section change splits is filed under ``_document``.
"""
from __future__ import annotations

import bisect
import json
import re
from typing import Any, Optional

from .prompts import CHECKER_MARK, LISTING_KEYS, MISSED_MARK, READER_MARK

READY, NEEDS_ANSWER, NOT_SUPPORTED, NEEDS_REVIEW = 'ready', 'needs_answer', 'not_supported', 'needs_review'
READER_STATUSES = (READY, NEEDS_ANSWER, NOT_SUPPORTED)
FINAL_STATUSES = (READY, NEEDS_ANSWER, NEEDS_REVIEW, NOT_SUPPORTED)
AGREE = 'agree'
DOCUMENT_KEY = '_document'
READER_LINE, MISSED_LINE = 'L', 'M'  # the line labels' letters: L1..Ln (the reader's codes), M1..Mk (missed codes)
FENCE = '```json'
# CPT Studio's own question for a needs_answer line that no question names (FIX-SPEC 3): the member can always answer.
UNASKED_QUESTION = 'What does the coding review need to know to finish code {code}?'

_CODE_SHAPE = r'(?:[0-9]{4}[0-9FTU]|[A-Z][0-9]{4})'
_MARKER = re.compile(rf'(?:#+ )?(LINE|REVIEW|MISSED) ([LM][1-9][0-9]*) ({_CODE_SHAPE})[ \t\r]*')
# a line that reads like a marker but is not one - led (after any list or emphasis marks) by LINE, REVIEW or MISSED in
# any case and naming a code further on, or naming a line label after one of them anywhere ("**LINE L2 45380**",
# "- REVIEW L1 45385", "Line 2 45380", "Review of 45380:"): it ends the current section, so a citation after it never
# falls to the line before it; prose such as "the first coder missed 2 polyps" ends nothing
_MARKER_LIKE = re.compile(
    rf'^[\s#*>_`~+.()\-0-9]*(?i:line|review|missed)\b.*?(?<![A-Za-z0-9]){_CODE_SHAPE}(?![A-Za-z0-9])'
    r'|(?i:\b(?:line|review|missed)[ \t]*[:#.-]?[ \t]*[lm][0-9])')
# a heading that is not a marker: a markdown heading, or a line that is all bold or underlined ("**Summary**")
_HEADING = re.compile(r'#+[ \t]|[ \t]*(\*\*|__)(?=\S).*\S\1:?[ \t\r]*$')
# the markers each answer writes, and the letter of the lines each names
_ROLE_MARKS = {'reader': {READER_MARK: READER_LINE}, 'checker': {CHECKER_MARK: READER_LINE, MISSED_MARK: MISSED_LINE}}


class Unreadable(Exception):
    """The answer holds no final JSON this step can show; the message says what was missing (for the operator)."""


def message_text(message: object) -> str:
    """The message's text blocks joined in order (the analysis and the final JSON)."""
    return ''.join(block['text'] for block in _blocks(message)
                   if block.get('type') == 'text' and isinstance(block.get('text'), str))


def _loads(text: str) -> tuple[bool, object]:
    try:
        return True, json.loads(text)
    except (ValueError, RecursionError):  # RecursionError: nesting deeper than the parser allows
        return False, None


def last_json(text: str) -> object:
    """The final answer (FIX-SPEC 2): the last ```json fenced block (to its closing fence, or to the end of the text);
    when it does not parse, the widest {...} span of the whole text; else None. Never an earlier fenced block."""
    start = text.rfind(FENCE)
    if start != -1:
        body = text[start + len(FENCE):]
        end = body.find('```')
        parsed, value = _loads(body if end == -1 else body[:end])
        if parsed:
            return value
    first, last = text.find('{'), text.rfind('}')
    if first != -1 and last > first:
        parsed, value = _loads(text[first:last + 1])
        if parsed:
            return value
    return None


def read_reader(message: object) -> dict:
    """The reader's final JSON object, as it was written; Unreadable when it cannot be shown (module docstring)."""
    parsed = _final_object(message, 'reader')
    if not isinstance(parsed.get('codes'), list):
        raise Unreadable('the reader result has no list of codes')
    _reader_lines(parsed)
    return parsed


def read_checker(message: object) -> dict:
    """The checker's final JSON object, as it was written; Unreadable when it cannot be shown."""
    parsed = _final_object(message, 'checker')
    if not isinstance(parsed.get('reviews'), list):
        raise Unreadable('the checker result has no list of reviews')
    missed = parsed.get('missed_codes')
    if missed is not None and not isinstance(missed, list):
        raise Unreadable('the checker result lists its missed codes in something other than a list')
    for item in parsed['reviews']:
        _review(item)
    _missed_lines(parsed)
    return parsed


def listing(reader: dict) -> list[dict]:
    """The reader's lines as the checker is given them (FIX-SPEC 1): line, code, units, modifiers, status, question -
    each as the customer is shown it."""
    return [{key: line['listed_status' if key == 'status' else key] for key in LISTING_KEYS}
            for line in _reader_lines(reader)]


def combine(reader: dict, checker: dict) -> dict[str, list]:
    """{'codes', 'questions', 'problems'} of a round from the two parsed results (module docstring)."""
    lines, missed = _reader_lines(reader), _missed_lines(checker)
    by_label = {line['line']: line for line in lines}
    matched: dict[str, list[dict]] = {label: [] for label in by_label}
    unmatched = []
    for item in checker.get('reviews') or ():
        review = _review(item)
        line = by_label.get(review['line'])
        if line is not None and _key(review['code']) == _key(line['code']):
            matched[line['line']].append(review)
        else:
            unmatched.append(review)
    # which reader lines each unmatched review reaches: the line it names, and every line carrying its code
    reached = dict.fromkeys(by_label, 0)
    unplaced = 0  # unmatched reviews that name no line and carry no line's code
    for review in unmatched:
        hits = {line['line'] for line in lines + missed if _key(line['code']) == _key(review['code'])}
        if review['line'] in by_label:
            hits.add(review['line'])
        for label in hits & reached.keys():
            reached[label] += 1
        unplaced += not hits
    rows = []
    for line in lines:
        found = matched[line['line']]
        agrees = bool(found) and all(review['verdict'] == AGREE for review in found)
        status = line['listed_status'] if agrees and not reached[line['line']] else NEEDS_REVIEW
        rows.append({**line, 'status': status, 'listed_by': 'reader',
                     'second_check': {**_second_check(found, agrees), 'reviews': len(found),
                                      'unmatched': reached[line['line']], 'unplaced': unplaced}})
    for line in missed:
        rows.append({**line, 'status': NEEDS_REVIEW, 'listed_by': 'checker', 'second_check': None})
    return {'codes': rows, 'questions': _questions(reader, checker, rows, matched),
            'problems': _strings(reader.get('documentation_problems'), keep=True) or []}


def citations(reader_message: object, checker_message: object) -> dict[str, list[dict]]:
    """{line: [{'text', 'page', 'source'}]} from both messages' citations (module docstring); ``_document`` for a
    citation no line's section holds."""
    found: dict[str, list[dict]] = {}
    reader_codes = _line_codes(reader_message, 'reader')
    every_code = {**reader_codes, **_line_codes(checker_message, 'checker')}
    for message, role, codes in ((reader_message, 'reader', reader_codes), (checker_message, 'checker', every_code)):
        source = role
        blocks, offset = [], 0
        for block in _blocks(message):
            if block.get('type') != 'text' or not isinstance(block.get('text'), str):
                continue
            blocks.append((offset, offset + len(block['text']), block))
            offset += len(block['text'])
        text = ''.join(block['text'] for _, _, block in blocks)
        events = _section_events(text, role, codes)
        offsets = [offset for offset, _ in events]
        for start, end, block in blocks:
            key = _section_of(events, offsets, text, start, end)
            for cited in block.get('citations') or ():
                if not isinstance(cited, dict) or not isinstance(cited.get('cited_text'), str):
                    continue
                page = cited.get('start_page_number') if cited.get('type') == 'page_location' else None
                found.setdefault(key, []).append({'text': cited['cited_text'],
                                                  'page': page if type(page) is int else None, 'source': source})
    return found


# --- lines ---------------------------------------------------------------------------------------------------------

def _reader_lines(reader: dict) -> list[dict]:
    """The reader's code lines L1..Ln as shown, in its list's order; Unreadable when one cannot be read."""
    out = []
    for number, item in enumerate(reader.get('codes') or (), start=1):
        line = _line(item, 'reader code', f'{READER_LINE}{number}')
        if line['listed_status'] not in READER_STATUSES:
            raise Unreadable(f'the reader gave code {line["code"]!r} a status it was not given')
        out.append(line)
    return out


def _missed_lines(checker: dict) -> list[dict]:
    """The checker's missed codes as lines M1..Mk, in its list's order; Unreadable when one cannot be read."""
    missed = checker.get('missed_codes')
    return [_line(item, 'missed code', f'{MISSED_LINE}{number}')
            for number, item in enumerate(missed if isinstance(missed, list) else (), start=1)]


def _line(item: object, role: str, label: str) -> dict:
    item = _identity(item, role)
    return {'line': label, 'code': item['code'], 'units': _units(item.get('units')),
            'modifiers': _modifiers(item.get('modifiers'), f'{role} {item["code"]!r}'),
            'listed_status': item['status'] if isinstance(item.get('status'), str) else None,
            'reason': _str(item.get('reason')), 'question': _str(item.get('question')),
            'evidence': _evidence(item.get('evidence'))}


def _line_codes(message: object, role: str) -> dict[str, str]:
    """{line: code} of the lines a message's final JSON lists (the reader's L lines; the checker's M lines), or {} when
    it cannot be read - its citations are then filed under no line."""
    try:
        if role == 'reader':
            return {line['line']: line['code'] for line in _reader_lines(_final_object(message, role))}
        return {line['line']: line['code'] for line in _missed_lines(_final_object(message, role))}
    except Unreadable:
        return {}


# --- shapes ---------------------------------------------------------------------------------------------------------

def _blocks(message: object) -> list[dict]:
    content = message.get('content') if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _final_object(message: object, role: str) -> dict:
    parsed = last_json(message_text(message))
    if not isinstance(parsed, dict):
        raise Unreadable(f'the {role} answer holds no final JSON object')
    return parsed


def _identity(item: object, role: str) -> dict:
    if not isinstance(item, dict) or not isinstance(item.get('code'), str) or not item['code'].strip():
        raise Unreadable(f'a {role} entry names no code')
    return item


def _review(item: object) -> dict:
    """A review as the combination reads it: the line it names (None when it names none), its code and verdict;
    Unreadable when it names no code (a review cannot be dropped without the customer being told it was never
    written)."""
    item = _identity(item, 'review')
    line = item.get('line')
    return {'line': _key(line) if isinstance(line, str) else None, 'code': item['code'],
            'verdict': _str(item.get('verdict')), 'reason': _str(item.get('reason')),
            'question': _str(item.get('question')), 'correct_code': _str(item.get('correct_code')),
            'correct_units': _units(item.get('correct_units')),
            'correct_modifiers': _strings(item.get('correct_modifiers')),
            'correct_status': _str(item.get('correct_status')), 'evidence': _evidence(item.get('evidence'))}


def _second_check(found: list[dict], agrees: bool) -> dict:
    """The checker's view of a reader line: agrees True or False, or None when no review belongs to it. With more than
    one review the one shown is the first that does not agree (the first, when all do)."""
    if not found:
        return {'agrees': None, 'verdict': None, 'reason': None, 'question': None, 'correct_code': None,
                'correct_units': None, 'correct_modifiers': None, 'correct_status': None, 'evidence': []}
    shown = found[0] if agrees else next(review for review in found if review['verdict'] != AGREE)
    return {'agrees': agrees, **{key: value for key, value in shown.items() if key not in ('line', 'code')}}


def _questions(reader: dict, checker: dict, rows: list[dict], matched: dict[str, list[dict]]) -> list[dict]:
    """The round's questions (module docstring), each {'id', 'text', 'lines', 'codes', 'source'}."""
    order = [row['line'] for row in rows]
    codes = {row['line']: row['code'] for row in rows}
    out: list[dict] = []
    seen: dict[str, dict] = {}

    def named(affects) -> list[str]:
        """The lines a question's ``affects`` names: a line label, or every line carrying a code it names."""
        found = []
        for entry in affects:
            key = _key(entry)
            found += [key] if key in codes else [label for label in order if _key(codes[label]) == key]
        return found

    def add(text: str, lines: list[str], source: str):
        folded = ' '.join(text.split()).casefold()
        entry = seen.get(folded)
        if entry is None:
            entry = seen[folded] = {'id': f'q{len(out) + 1}', 'text': text, 'lines': [], 'codes': [],
                                    'source': source}
            out.append(entry)
        entry['lines'] = [label for label in order if label in entry['lines'] or label in lines]
        entry['codes'] = list(dict.fromkeys(codes[label] for label in entry['lines']))

    for parsed, source in ((reader, 'reader'), (checker, 'checker')):
        items = parsed.get('questions')
        for item in items if isinstance(items, list) else ():
            if isinstance(item, str) and item.strip():
                add(item, [], source)
            elif isinstance(item, dict) and isinstance(item.get('question'), str) and item['question'].strip():
                affects = item.get('affects')
                add(item['question'], named(_texts(affects) if isinstance(affects, list) else ()), source)
    for row in rows:
        if isinstance(row['question'], str) and row['question'].strip():
            add(row['question'], [row['line']], row['listed_by'])
    for row in rows:
        if row['status'] != NEEDS_ANSWER or any(row['line'] in entry['lines'] for entry in out):
            continue
        asked = [review['question'] for review in matched.get(row['line'], ())
                 if isinstance(review['question'], str) and review['question'].strip()]
        for text in asked or [UNASKED_QUESTION.format(code=row['code'])]:
            add(text, [row['line']], 'checker' if asked else 'studio')
    return out


# --- citations: the sections of an answer --------------------------------------------------------------------------

def _section_events(text: str, role: str, codes: dict[str, str]) -> list[tuple[int, str]]:
    """[(offset, key)] where a section starts (a marker: its line's key, or ``_document`` when its line or code is
    not that line's) or ends (a marker-like line, a heading, a code fence: ``_document``), in order."""
    marks = _ROLE_MARKS[role]
    events, offset = [], 0
    for line in text.split('\n'):
        marker = _MARKER.fullmatch(line)
        if marker and marks.get(marker.group(1)) == marker.group(2)[0]:
            label, code = marker.group(2), marker.group(3)
            events.append((offset, label if label in codes and _key(codes[label]) == code else DOCUMENT_KEY))
        else:  # a section ends where what ends it starts on its line
            ends = [match.start() for match in (_MARKER_LIKE.search(line), _HEADING.match(line)) if match]
            if line.lstrip().startswith('```'):
                ends.append(len(line) - len(line.lstrip()))
            if ends:
                events.append((offset + min(ends), DOCUMENT_KEY))
        offset += len(line) + 1
    final = text.rfind(FENCE)
    if final != -1:  # the final JSON, wherever its fence starts
        events.append((final, DOCUMENT_KEY))
        events.sort(key=lambda event: event[0])
    return events


def _section_of(events: list[tuple[int, str]], offsets: list[int], text: str, start: int, end: int) -> str:
    """The key a text block [start, end) of the joined text is filed under: the section it is in; when a section
    starts or ends inside it, the section after that change only if nothing but blank text precedes it in the block,
    else ``_document`` (the block's citations cannot be told apart). ``offsets``: the events' offsets, in order."""
    first, past = bisect.bisect_left(offsets, start), bisect.bisect_left(offsets, end)
    if first == past:  # no change inside the block
        return events[first - 1][1] if first else DOCUMENT_KEY
    if text[start:offsets[first]].strip():
        return DOCUMENT_KEY
    return events[past - 1][1]


# --- values ---------------------------------------------------------------------------------------------------------

def _key(code: str) -> str:
    return code.strip().upper()


def _str(value: object) -> Optional[str]:
    return value if isinstance(value, str) else None


def _int(value: object) -> Optional[int]:
    return value if type(value) is int else None


def _units(value: object) -> Optional[int]:
    """Units as shown: a positive integer, else None (not given)."""
    return value if type(value) is int and value > 0 else None


def _modifiers(value: object, where: str) -> Optional[list[str]]:
    """A line's modifiers (FIX-SPEC 2): its string items as written, an integer item as its decimal string; None when
    absent or null (not given); Unreadable for any other shape."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise Unreadable(f'{where} lists its modifiers in something other than a list')
    out = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        elif type(item) is int:
            out.append(str(item))
        else:
            raise Unreadable(f'{where} has a modifier that is neither text nor a whole number')
    return out


def _texts(value: list) -> list[str]:
    """A list's string items, an integer item as its decimal string; any other item is left out."""
    return [item if isinstance(item, str) else str(item) for item in value
            if isinstance(item, str) or type(item) is int]


def _strings(value: object, *, keep: bool = False) -> Optional[list[str]]:
    """A list of strings as written; None when it is not one. ``keep``: its string items, the rest dropped."""
    if not isinstance(value, list):
        return None
    if keep:
        return [item for item in value if isinstance(item, str)]
    return list(value) if all(isinstance(item, str) for item in value) else None


def _evidence(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [{'quote': item['quote'], 'page': _int(item.get('page'))} for item in value
            if isinstance(item, dict) and isinstance(item.get('quote'), str)]
