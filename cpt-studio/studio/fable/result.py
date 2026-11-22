"""Reading the two final messages (BUILD-SPEC 4.4-4.6; the fix passes, FIX-SPEC sections 1-3 and FIX-SPEC-2 sections
1-4): the final JSON, the code lines, the combination of the two reads, the questions and the citations per line.

The final answer (FIX-SPEC-2 section 1). The message's text blocks are joined in order. A fenced block opens at a line
holding three or more backticks or tildes, with any info string or none, in any case (a backtick fence's info string
holds no backtick), and closes at the next line holding at least as many of the same character and nothing else, or
runs to the end of the text. The final answer is the LAST fenced block; when it does not parse as strict JSON, the widest
{...} span of the whole text, read only when it reaches the last block (so an earlier block is never read in its place);
else the answer is Unreadable and the round fails (nothing is resent). Text after the last fenced block that holds a "{"
could be the final answer itself, so the code cannot tell which is final: Unreadable too. Strict JSON: a repeated key,
NaN, Infinity, -Infinity, a number too large to be finite, and the NUL character or a lone surrogate in any key or string
make the text unparseable.

Shape (FIX-SPEC-2 section 2): every field is read in the shape the instructions give it, and the only conversions are
lossless ones:
- the reader's ``codes`` and the checker's ``reviews`` are lists, ``missed_codes`` a list when present;
- a code line (a reader code or a missed code) names a code of the code shape (four digits and then a digit or F, T or
  U; or a capital letter and four digits), the CPT book's marks before it read as the code they mark ("+22614" is
  22614, "#+22853" is 22853: a lossless conversion, D390), and a status the instructions allow (the reader's three;
  ready or
  needs_answer for a missed code); a "line" label it writes on itself, when it writes one, is its own place in its list
  (the code cannot tell which numbering was meant otherwise);
- units: a whole number of zero or more (the reader writes 0 for a code it does not support: measured on the recorded
  answers, it is a value and is shown as written), a string of digits only read as that number, or null or absent (not
  given);
- modifiers: a list of strings, an integer item read as its decimal string, a blank item - which carries nothing -
  removed; null or absent they are not given;
- reason: a string, a list of strings joined with one space, or null or absent;
- a line's or a review's question: a string, a list of strings (one question each, tied to that line), an object with a
  string "question" and an optional "id" (read as a top-level question's is), or null or absent; the line shows its
  questions one per line of text;
- the top-level questions: a list, or a single object read as a list of one; an item is a string or an object with a
  string "question", an optional "affects" (codes or line labels: a list of strings or integers, or one of them) and an
  optional "id" (D370: a string that is not blank, or an integer read as its decimal string; an id in any other shape
  is no id - the question is kept and shown, and no reference reaches it);
- documentation_problems: a list, or a single value read as a list of one; an item that is no string is kept as its
  JSON text, never dropped;
- every review names its code as a non-empty string;
any other shape is Unreadable, so nothing Fable wrote is dropped, altered or guessed. A question is blank when nothing
is left of its text once U+FEFF and white space are removed (blank_question, the one test of it: every text the customer
page's trim() empties is blank to it, and it also calls blank U+001C to U+001F and U+0085, which the page keeps), and a
blank question carries nothing.
A review's other fields (correct_*) and the evidence items are kept where they can be read; the operator console shows
both answers whole.
What a line, a missed code or a review gives in "question_ids" (D370) never makes an answer Unreadable (today's answers
have no such field, and an Unreadable round costs a paid read): a list of items, or a single item read as a list of one.
An item is an id (a string that is not blank, or an integer read as its decimal string), or an object with a string
"question" that is not blank - question text written on the item, read as the same object in its "question" is, with
its optional "id"; a blank or null item names nothing; an item in any other shape, an object without such a "question"
among them, names no question and is kept as written for the operator console (dangling_references). A string item is
always an id, so question text written there as a plain string names no question and reaches only the operator console:
a known limit (D378), since telling such text from a malformed id such as "Q1, Q2" would mean guessing.

Line identity (FIX-SPEC 1). Every final code row carries ``line``: the reader's codes are "L1".."Ln" in the order of its
JSON list, the checker's missed codes "M1".."Mk" in theirs. The checker is given each reader line with its label and the
ids of the questions it names, and the reader's questions with their ids (listing); every review names the line it
reviews.

Combination (BUILD-SPEC 4.5; FIX-SPEC 1; FIX-SPEC-2 section 3), the only glue logic: a review belongs to a reader line
when it names that line and the code on that line. A reader line keeps the reader's status only when the reviews that
belong to it all say exactly ``agree`` (at least one) and no other review reaches it; otherwise it is ``needs_review``,
both reasons kept. A review that belongs to no line is unmatched: it reaches the reader line it names and every line
carrying its code; one that reaches no line that way - it names no line, or one that does not exist, and carries a code
no line holds - is placed nowhere, and the code cannot tell which line it is about, so it reaches EVERY line. An
unmatched review can only send lines to a human, never make one ready, and the code never picks a line for it; the
customer reads its reason as a note on the encounter (unmatched_reviews, studio.customer). Every missed code is a line of
its own, ``needs_review``. The problems are the reader's documentation_problems.

Questions (FIX-SPEC 3; D370, D372: each question is written once, with an id, and lines refer to it). The round's
questions are the reader's top-level questions in their order, then the checker's, then each line's own questions - its
"question" (today's shape) and the question objects in its question_ids - when the text is not listed yet (the reader's
lines in order, then the missed codes), then the questions the reviews define on themselves (below), then those of the
fallback (below). Two questions whose text is the same with case and whitespace folded are one question - today's
merge, the only comparison of wordings - and nothing else makes two questions one: not even an id, so a duplicate id
stays two questions. A question object an item writes on itself (in its "question" or its question_ids) that carries an
id also defines that id among its author's questions, after the author's top-level ones (the reader's for a reader
line; the checker's for a missed code or a review), and its id is one of the ids the item names. A review's own
questions are shown on its second check and asked only by the fallback, as today, except one that carries an id: it is
one of the checker's questions, so it is asked, naming the lines the review is about. Each question names the lines it
affects: its own "affects" (line labels, or codes: every line carrying the code), the line it is written on, every
reader line and missed code whose ids name it, and the lines of every review whose ids name it or that defines it (the
line the review belongs to; for a review that belongs to no line, the lines it reaches by naming them or their code -
none for one placed nowhere). An id names every question carrying it, compared case-insensitively, among the questions
its author was shown: a reader line's ids the reader's questions; a missed code's or a review's the reader's and the
checker's (the checker is given the reader's questions with their ids, those its lines define among them). An id that
names no question carries no text; the operator console lists it (dangling_references), and the ids both answers define
(shared_ids): a reference of the checker's to one reaches every question carrying it in either answer, which is one
question where their texts are the same, never fewer. A needs_answer line that no question names by its affects or by
its "question" text (today's naming) gets the questions the reviews that agreed with it wrote on themselves; when there
are none and no question names the line at all - by an id or a question object either - it gets CPT Studio's own
question about it, so a member can always answer it. A code row shows as its question its own question texts and then
the text of every question its ids name, one per line of text (a text already shown on it once); a question that names
the line only by its affects, or by another item's id, is not repeated there. Its second check shows the same of the
review shown. Each question is stored as {id (q1, q2.. in order), text, lines, codes, source}. The merge costs in
proportion to what it reads: no step rescans what an earlier one built.

Citations (FIX-SPEC 1; FIX-SPEC-2 section 4): the joined text is read line by line. A marker is a whole line holding
exactly ``LINE L<n> <code>`` (reader), ``REVIEW L<n> <code>`` or ``MISSED M<k> <code>`` (checker), case-sensitive,
optionally after a run of '#' and one space (trailing spaces aside). A section starts at a marker and ends at the next
marker, at a line holding exactly END (the reader and the checker are asked to end their last section with one) or at
the start of the final answer - its fence, or the start of its widest span - after which nothing starts a section; a
line that looks like a marker but is not one, a heading (a line starting with '#', or a line all in bold), a thematic
break (---) and a code fence end it too. A citation is filed under a marker's line only when it is in that marker's
section and the marker's code is the code on that line. Anything else goes under ``_document``: a citation outside
every section, and every citation of a text block whose own text holds a section change - a marker or END among them -
because the code cannot tell which part of the block each one belongs to.
"""
from __future__ import annotations

import bisect
import json
import math
import re
from typing import Any, NamedTuple, Optional

from .prompts import CHECKER_MARK, END_MARK, LISTING_KEYS, MISSED_MARK, READER_MARK

READY, NEEDS_ANSWER, NOT_SUPPORTED, NEEDS_REVIEW = 'ready', 'needs_answer', 'not_supported', 'needs_review'
READER_STATUSES = (READY, NEEDS_ANSWER, NOT_SUPPORTED)
MISSED_STATUSES = (READY, NEEDS_ANSWER)  # what the checker is told a missed code's status is (prompts.CHECKER_SYSTEM)
FINAL_STATUSES = (READY, NEEDS_ANSWER, NEEDS_REVIEW, NOT_SUPPORTED)
AGREE, DISAGREE = 'agree', 'disagree'
DOCUMENT_KEY = '_document'
READER_LINE, MISSED_LINE = 'L', 'M'  # the line labels' letters: L1..Ln (the reader's codes), M1..Mk (missed codes)
# CPT Studio's own question for a needs_answer line that no question names (FIX-SPEC 3): the member can always answer.
UNASKED_QUESTION = 'What does the coding review need to know to finish code {code}?'

_CODE_SHAPE = r'(?:[0-9]{4}[0-9FTU]|[A-Z][0-9]{4})'
_CODE = re.compile(_CODE_SHAPE)
_DIGITS = re.compile(r'[0-9]+')
_MARKER = re.compile(rf'(?:#+ )?(LINE|REVIEW|MISSED) ([LM][1-9][0-9]*) (?:\+#?|#\+?)?({_CODE_SHAPE})[ \t\r]*')
# a line that reads like a marker but is not one - led (after any list or emphasis marks) by LINE, REVIEW or MISSED in
# any case and naming a code further on, or naming a line label after one of them anywhere ("**LINE L2 45380**",
# "- REVIEW L1 45385", "Line 2 45380", "Review of 45380:"): it ends the current section, so a citation after it never
# falls to the line before it; prose such as "the first coder missed 2 polyps" ends nothing
_MARKER_LIKE = re.compile(
    rf'^[\s#*>_`~+.()\-0-9]*(?i:line|review|missed)\b.*?(?<![A-Za-z0-9]){_CODE_SHAPE}(?![A-Za-z0-9])'
    r'|(?i:\b(?:line|review|missed)[ \t]*[:#.-]?[ \t]*[lm][0-9])')
# a heading that is not a marker: a line starting with '#' (the instructions' own word for a heading line), or a line
# that is all bold or underlined ("**Summary**")
_HEADING = re.compile(r'[ \t]*#|[ \t]*(\*\*|__)(?=\S).*\S\1:?[ \t\r]*$')
_RULE = re.compile(r'[ \t]*([-*_])[ \t]*(?:\1[ \t]*){2,}\r?')  # a thematic break: ---, ***, ___, - - -
_FENCE = re.compile(r'[ \t]*(`{3,}|~{3,})(.*)')  # a line opening or closing a fenced block (the run, then the rest)
# PostgreSQL text cannot hold NUL, and a lone surrogate cannot be encoded at all
_UNSTORABLE = re.compile('[\x00\ud800-\udfff]')
# the markers each answer writes, and the letter of the lines each names
_ROLE_MARKS = {'reader': {READER_MARK: READER_LINE}, 'checker': {CHECKER_MARK: READER_LINE, MISSED_MARK: MISSED_LINE}}


# The CPT book's marks before a code: "+" an add-on, "#" a resequenced code, at most one of each, in either order.
_BOOK_MARKS = re.compile(rf'(?:\+#?|#\+?)({_CODE_SHAPE})')


def _written_code(value: object) -> object:
    """A code line's code as Fable wrote it, with the CPT book's marks read as the code they mark: "+22614" is 22614 and
    "#+22853" is 22853 (owner direction 2026-11-22, D390: nothing in CPT Studio may drop a code Fable writes, and
    spine and joint cases are built on add-on codes, some of them resequenced). A lossless conversion of the shape in
    the sense of FIX-SPEC-2 section 2, the code itself saying what the mark says; everything else is returned exactly
    as written, so the rest of that section stands - white space, lower case, a mark with a space after it or repeated,
    or a code joined to a modifier ("22614-62") still make the answer unreadable rather than altered or guessed.

    Read only where an answer writes a code LINE (a reader code, a missed code) and in a section marker: a review's
    code, the checker's correction and a question's target are read as before, because rounds already stored are read
    again whenever a page shows them, and a stored review must keep the reading it was stored under (refutation N1-1-1).
    Plumbing only - it decides no code (D358)."""
    if isinstance(value, str):
        marked = _BOOK_MARKS.fullmatch(value)
        if marked:
            return marked.group(1)
    return value


class Unreadable(Exception):
    """The answer holds no final JSON this step can show; the message says what was missing (for the operator)."""


def message_text(message: object) -> str:
    """The message's text blocks joined in order (the analysis and the final JSON)."""
    return ''.join(block['text'] for block in _blocks(message)
                   if block.get('type') == 'text' and isinstance(block.get('text'), str))


# --- the final answer -----------------------------------------------------------------------------------------------

class _Block(NamedTuple):
    start: int  # where its opening fence starts
    body: int  # where its content starts: the line after the opening fence
    end: int  # where its content ends: the closing fence's line, or the end of the text
    after: int  # where the text after it starts: after the closing fence's line


def _fenced_blocks(text: str) -> list[_Block]:
    """The text's fenced blocks, in order (module docstring)."""
    blocks, opened, offset = [], None, 0
    for line in text.split('\n'):
        start, offset = offset, offset + len(line) + 1
        fence = _FENCE.fullmatch(line)
        if fence is None:
            continue
        run, rest = fence.group(1), fence.group(2)
        if opened is None:
            if run[0] == '`' and '`' in rest:
                continue  # a backtick fence's info string holds no backtick: this is inline code, not a fence
            opened = (start + fence.start(1), run[0], len(run), min(offset, len(text)))
        elif run[0] == opened[1] and len(run) >= opened[2] and not rest.strip():
            blocks.append(_Block(opened[0], opened[3], start, min(offset, len(text))))
            opened = None
    if opened is not None:
        blocks.append(_Block(opened[0], opened[3], len(text), len(text)))
    return blocks


def _strict_object(pairs: list) -> dict:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError('an object repeats a key')
    return dict(pairs)


def _no_constant(name: str):
    raise ValueError(f'{name} is not JSON')


def _finite(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('a number too large to be finite')
    return value


def _unstorable(value: object) -> bool:
    """Whether a key or a string anywhere in ``value`` holds a character the database cannot store."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            if _UNSTORABLE.search(item):
                return True
        elif isinstance(item, dict):
            stack.extend(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def _loads(text: str) -> tuple[bool, object]:
    """(True, the value) when ``text`` is strict JSON (module docstring), else (False, None)."""
    try:
        value = json.loads(text, object_pairs_hook=_strict_object, parse_constant=_no_constant, parse_float=_finite)
    except (ValueError, RecursionError):  # RecursionError: nesting deeper than the parser allows
        return False, None
    return (False, None) if _unstorable(value) else (True, value)


def final_answer(text: str) -> Optional[tuple[object, int]]:
    """(the final answer, where it starts in ``text``: its block's opening fence, or its widest span's "{"), or None
    when the text holds none this step can read (module docstring)."""
    blocks = _fenced_blocks(text)
    last = blocks[-1] if blocks else None
    if last is not None:
        if '{' in text[last.after:]:
            return None  # what follows the last fenced block could be the final answer: the code cannot tell
        parsed, value = _loads(text[last.body:last.end])
        if parsed:
            return value, last.start
    first, final = text.find('{'), text.rfind('}')
    if first != -1 and final > first and (last is None or final >= last.start):
        parsed, value = _loads(text[first:final + 1])
        if parsed:
            return value, first
    return None


def last_json(text: str) -> object:
    """The final answer (FIX-SPEC-2 section 1), or None. Never an earlier fenced block."""
    found = final_answer(text)
    return found[0] if found is not None else None


def read_reader(message: object) -> dict:
    """The reader's final JSON object, as it was written; Unreadable when it cannot be shown (module docstring)."""
    parsed = _final_object(message, 'reader')
    if not isinstance(parsed.get('codes'), list):
        raise Unreadable('the reader result has no list of codes')
    _reader_lines(parsed)
    _asked(parsed, 'reader')
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
    _asked(parsed, 'checker')
    return parsed


def listing(reader: dict) -> dict[str, list[dict]]:
    """What the checker is given of the reader's answer (FIX-SPEC 1; D370): {'lines': each reader line's line, code,
    units, modifiers and status as the customer is shown them, the ids it names (question_ids, as read: the id of each
    question object it writes among them) and - only when it wrote one without an id, as in today's shape - its own
    question text; 'questions': the reader's top-level questions, each {'id' (as read, or None), 'question',
    'affects'}, then every question a line defines on itself with an id, {'id', 'question', 'affects': the lines it is
    written on} - one entry for one id and text (folded), so a question is never listed twice}."""
    questions, listed_by = [], {}
    for asked in _asked(reader, 'reader'):
        questions.append({'id': asked.id, 'question': asked.text, 'affects': asked.affects})
        if asked.id is not None:
            listed_by.setdefault((_key(asked.id), _folded(asked.text)), questions[-1])
    lines = []
    for line in _reader_lines(reader):
        values = {**line, 'status': line['listed_status'], 'question_ids': line['refs'].ids}
        listed = {key: values[key] for key in LISTING_KEYS}
        own = [item.text for item in line['asked'] if item.id is None]
        if own:
            listed['question'] = _question_text(own)
        lines.append(listed)
        for item in line['asked']:  # the questions it defines on itself, with their ids
            if item.id is None:
                continue
            entry = listed_by.get((_key(item.id), _folded(item.text)))
            if entry is None:
                entry = listed_by[(_key(item.id), _folded(item.text))] = {'id': item.id, 'question': item.text,
                                                                           'affects': []}
                questions.append(entry)
            if line['line'] not in entry['affects']:
                entry['affects'].append(line['line'])
    return {'lines': lines, 'questions': questions}


# --- the combination --------------------------------------------------------------------------------------------------

def combine(reader: dict, checker: dict) -> dict[str, list]:
    """{'codes', 'questions', 'problems'} of a round from the two parsed results (module docstring)."""
    lines, missed = _reader_lines(reader), _missed_lines(checker)
    by_label = {line['line']: line for line in lines}
    every = lines + missed
    matched: dict[str, list[dict]] = {label: [] for label in by_label}
    reached = dict.fromkeys(by_label, 0)  # the unmatched reviews that reach each reader line by naming it or its code
    unplaced = 0  # the unmatched reviews placed nowhere: each reaches every line
    about = []  # (each review, the lines a question it names by id is about: its line, or the lines it reaches)
    for item in checker.get('reviews') or ():
        review = _review(item)
        label, hits = _placement(review, by_label, every)
        if label is not None:
            matched[label].append(review)
        elif hits:
            for hit in hits & reached.keys():
                reached[hit] += 1
        else:
            unplaced += 1
        about.append((review, [label] if label is not None else [row['line'] for row in every if row['line'] in hits]))
    rows, shown = [], []
    for line in lines:
        found = matched[line['line']]
        agrees = bool(found) and all(review['verdict'] == AGREE for review in found)
        status = line['listed_status'] if agrees and not reached[line['line']] and not unplaced else NEEDS_REVIEW
        shown.append(_shown_review(found, agrees))
        rows.append({**_stored(line), 'status': status, 'listed_by': 'reader',
                     'second_check': {**_second_check(shown[-1], agrees), 'reviews': len(found),
                                      'unmatched': reached[line['line']], 'unplaced': unplaced}})
    for line in missed:
        rows.append({**_stored(line), 'status': NEEDS_REVIEW, 'listed_by': 'checker', 'second_check': None})
        shown.append(None)
    questions = _questions(reader, checker, rows, every, about, matched)
    for row, line, review in zip(rows, every, shown):  # what each line shows as its question (module docstring)
        row['question'] = _question_text(questions.texts(line['asked'], line['named']))
        if review is not None:
            row['second_check']['question'] = _question_text(questions.texts(review['asked'], review['named']))
    return {'codes': rows, 'questions': questions.out(), 'problems': _problems(reader.get('documentation_problems'))}


def _placement(review: dict, by_label: dict[str, dict], every: list[dict]) -> tuple[Optional[str], set]:
    """(the reader line the review belongs to, nothing) when it names that line and the code on it; else (None, the
    lines it reaches: the reader line it names and every line carrying its code - none for a review placed nowhere)."""
    line = by_label.get(review['line'])
    if line is not None and _key(review['code']) == _key(line['code']):
        return line['line'], set()
    hits = {item['line'] for item in every if _key(item['code']) == _key(review['code'])}
    if review['line'] in by_label:
        hits.add(review['line'])
    return None, hits


def unmatched_reviews(codes: object, checker: object) -> list[dict]:
    """The reviews of a round that belong to no line - combine's own placement, over the round's stored code rows - in
    the checker's order: each {'number' (its place in the checker's reviews, from 1), 'review' (exactly as written),
    'reaches' (the lines it reaches by naming them or their code, in the round's order; [] for a review placed nowhere,
    which reaches every line), 'reason' (as the combination reads it, or None)}."""
    rows = [row for row in codes or () if isinstance(row, dict) and isinstance(row.get('line'), str)
            and isinstance(row.get('code'), str)] if isinstance(codes, list) else []
    by_label = {row['line']: row for row in rows if row.get('listed_by') != 'checker'}
    reviews = checker.get('reviews') if isinstance(checker, dict) else None
    out = []
    for number, item in enumerate(reviews if isinstance(reviews, list) else (), start=1):
        try:
            review = _review(item)
        except Unreadable:  # an answer stored before this reading of the shape: it belongs to no line it can name
            out.append({'number': number, 'review': item, 'reaches': [], 'reason': None})
            continue
        label, hits = _placement(review, by_label, rows)
        if label is None:
            out.append({'number': number, 'review': item, 'reaches': [row['line'] for row in rows if row['line'] in hits],
                        'reason': review['reason']})
    return out


def dangling_references(reader: object, checker: object) -> list[dict]:
    """The references of a round's two answers (each as stored) that name no question - an id naming no question its
    author was shown, or an item of question_ids in a shape that names no question (module docstring) - for the
    operator console: each {'item' (the line: "L2", "M1"; or "review 3", its place in the checker's reviews), 'code'
    (as written; a line's as read, the CPT book's marks set aside - _written_code), 'reference' (exactly as written:
    an integer id stays an integer)}, the reader's lines first, then
    the checker's reviews, then its missed codes. A question defined only on a line or a review (a question object
    with an id) is a question its author was shown. A part that cannot be read (an answer stored before this reading
    of the shape) is left out: it named nothing and defines nothing."""
    reader = reader if isinstance(reader, dict) else {}
    checker = checker if isinstance(checker, dict) else {}
    known = {'reader': set(_definitions(reader, 'reader')), 'checker': set(_definitions(checker, 'checker'))}
    both = known['reader'] | known['checker']
    out = []
    for where, item, author in _items(reader, checker):
        names = known['reader'] if author == 'reader' else both
        refs = item['refs']
        out += [{'item': where, 'code': item['code'], 'reference': written}
                for ident, written in zip(refs.ids, refs.written) if _key(ident) not in names]
        out += [{'item': where, 'code': item['code'], 'reference': value} for value in refs.unread]
    return out


def shared_ids(reader: object, checker: object) -> list:
    """The question ids both answers of a round (each as stored) define, compared case-insensitively, for the operator
    console (F3 of the D370 round 2): each as the reader first wrote it (an integer stays an integer), in the reader's
    order. A reference of the checker's to such an id reaches every question that carries it in either answer, which
    is one question where their texts are the same (today's merge: a checker restating the reader's question, its id
    and all, adds no question); a reader line's reference reaches the reader's only (module docstring: Questions). An
    id is listed even when its two definitions merged into one question (G1 of round 3): another question carrying it
    in either answer can still give a reference more than one. A part that cannot be read defines nothing."""
    reader = reader if isinstance(reader, dict) else {}
    checker = checker if isinstance(checker, dict) else {}
    theirs = _definitions(checker, 'checker')
    return [written for key, written in _definitions(reader, 'reader').items() if key in theirs]


def _items(reader: dict, checker: dict) -> list[tuple[str, dict, str]]:
    """[(where, the item as read, its author)] of the lines, reviews and missed codes of two stored answers that can
    be read, for the operator console: the reader's lines ("L1"..), then the checker's reviews ("review 1"..: its place
    in its list), then its missed codes ("M1"..). A part that cannot be read is left out."""
    out = []
    try:
        out += [(line['line'], line, 'reader') for line in _reader_lines(reader)]
    except Unreadable:
        pass
    reviews = checker.get('reviews')
    for number, item in enumerate(reviews if isinstance(reviews, list) else (), start=1):
        try:
            out.append((f'review {number}', _review(item), 'checker'))
        except Unreadable:
            continue
    try:
        out += [(line['line'], line, 'checker') for line in _missed_lines(checker)]
    except Unreadable:
        pass
    return out


def _definitions(parsed: dict, author: str) -> dict[str, object]:
    """{id (as compared) -> the id as first written} of the ids an answer (as stored) defines: its top-level questions',
    then those of the question objects its lines, reviews and missed codes write on themselves. A part that cannot be
    read defines none."""
    found: dict[str, object] = {}
    try:
        for asked in _asked(parsed, author):
            if asked.id is not None:
                found.setdefault(_key(asked.id), asked.written)
    except Unreadable:
        pass
    for _where, item, _author in _items(parsed, {}) if author == 'reader' else _items({}, parsed):
        for own in item['asked']:
            if own.id is not None:
                found.setdefault(_key(own.id), own.written)
    return found


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
            key = _section_of(events, offsets, start, end)
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
    return [_line(item, 'reader code', f'{READER_LINE}{number}', READER_STATUSES)
            for number, item in enumerate(reader.get('codes') or (), start=1)]


def _missed_lines(checker: dict) -> list[dict]:
    """The checker's missed codes as lines M1..Mk, in its list's order; Unreadable when one cannot be read."""
    missed = checker.get('missed_codes')
    return [_line(item, 'missed code', f'{MISSED_LINE}{number}', MISSED_STATUSES)
            for number, item in enumerate(missed if isinstance(missed, list) else (), start=1)]


def _line(item: object, role: str, label: str, statuses: tuple) -> dict:
    """One code line as shown (module docstring: shape); ``asked`` - the questions it writes on itself (_Own), in its
    "question" and then in its question_ids - ``refs`` - the ids it names - and ``named`` - the round's questions those
    ids name (set by the combination) - are the combination's and never stored."""
    if not isinstance(item, dict):
        raise Unreadable(f'{role} {label} is not an object')
    code = _written_code(item.get('code'))
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise Unreadable(f'{role} {label} names no code of the code shape')
    where = f'{role} {label} ({item["code"]})'  # as written
    own = item.get('line')
    if own is not None and not (isinstance(own, str) and (not own.strip() or _key(own) == label)):
        raise Unreadable(f'{where} names itself as another line than its place in the list')
    if item.get('status') not in statuses:
        raise Unreadable(f'{where} has a status it was not given')
    asked, refs = _own_questions(item, where)
    return {'line': label, 'code': code, 'units': _units(item.get('units'), where),
            'modifiers': _modifiers(item.get('modifiers'), where), 'listed_status': item['status'],
            'reason': _reason(item.get('reason'), where), 'question': _question_text([own.text for own in asked]),
            'evidence': _evidence(item.get('evidence')), 'asked': asked, 'refs': refs}


_UNSTORED = ('asked', 'refs', 'named')  # what a line or a review carries for the combination only


def _stored(line: dict) -> dict:
    return {key: value for key, value in line.items() if key not in _UNSTORED}


def _line_codes(message: object, role: str) -> dict[str, str]:
    """{line: code} of the lines a message's final JSON lists (the reader's L lines; the checker's M lines), or {} when
    it cannot be read - its citations are then filed under no line."""
    try:
        parsed = _final_object(message, role)
        lines = _reader_lines(parsed) if role == 'reader' else _missed_lines(parsed)
    except Unreadable:
        return {}
    return {line['line']: line['code'] for line in lines}


# --- shapes ---------------------------------------------------------------------------------------------------------

def _blocks(message: object) -> list[dict]:
    content = message.get('content') if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _final_object(message: object, role: str) -> dict:
    parsed = last_json(message_text(message))
    if not isinstance(parsed, dict):
        raise Unreadable(f'the {role} answer holds no final JSON object that can be read')
    return parsed


def _review(item: object) -> dict:
    """A review as the combination reads it: the line it names (None when it names none), its code and verdict (as
    written, when it is text); Unreadable when it names no code (a review cannot be dropped without the customer being
    told it was never written) or a field it shows has another shape (module docstring)."""
    if not isinstance(item, dict) or not isinstance(item.get('code'), str) or not item['code'].strip():
        raise Unreadable('a review names no code')
    line, verdict = item.get('line'), item.get('verdict')
    asked, refs = _own_questions(item, 'a review')
    return {'line': _key(line) if isinstance(line, str) else None, 'code': item['code'],
            'verdict': verdict if isinstance(verdict, str) else None,
            'reason': _reason(item.get('reason'), 'a review'), 'question': _question_text([own.text for own in asked]),
            'correct_code': _str(item.get('correct_code')), 'correct_units': _plain_units(item.get('correct_units')),
            'correct_modifiers': _strings(item.get('correct_modifiers')),
            'correct_status': _str(item.get('correct_status')), 'evidence': _evidence(item.get('evidence')),
            'asked': asked, 'refs': refs}


def _shown_review(found: list[dict], agrees: bool) -> Optional[dict]:
    """The review the second check of a reader line shows: None when no review belongs to it; with more than one, the
    first that disagrees exactly, else the first whose verdict is neither agree nor disagree (no clear verdict), else -
    when all agree - the first."""
    if not found:
        return None
    if agrees:
        return found[0]
    return next((review for review in found if review['verdict'] == DISAGREE), None) or next(
        review for review in found if review['verdict'] != AGREE)


def _second_check(shown: Optional[dict], agrees: bool) -> dict:
    """The checker's view of a reader line from the review shown (_shown_review): agrees True or False, or None when no
    review belongs to it."""
    if shown is None:
        return {'agrees': None, 'verdict': None, 'reason': None, 'question': None, 'correct_code': None,
                'correct_units': None, 'correct_modifiers': None, 'correct_status': None, 'evidence': []}
    return {'agrees': agrees,
            **{key: value for key, value in shown.items() if key not in ('line', 'code', *_UNSTORED)}}


class _Asked(NamedTuple):
    """One top-level question as read (module docstring: shape)."""
    text: str
    affects: list[str]  # the codes or line labels it names
    id: Optional[str]  # its id as read (an integer as its decimal string), or None when it has none
    written: object = None  # its id exactly as written (an integer stays an integer), when it has one


class _Own(NamedTuple):
    """A question an item (a line, a missed code or a review) writes on itself (module docstring: shape)."""
    text: str
    id: Optional[str]  # the id of the object it is written as, read as an id is; None for text or an object without one
    written: object  # that id exactly as written, or None
    inline: bool  # written inside question_ids (True) or in "question" (False: today's shape)


class _Refs(NamedTuple):
    """The ids an item names (module docstring: shape) and what it wrote in question_ids that names no question."""
    ids: list[str]  # the ids, each as read (an integer as its decimal string), in order: the id of a question object
    #                 written in its "question" first, then those of its question_ids (its question objects' among them)
    written: list  # each of those ids exactly as written (an integer stays an integer), for the operator console
    unread: list  # the items of question_ids in a shape that names no question, as written


def _asked(parsed: dict, role: str) -> list[_Asked]:
    """An answer's top-level questions (module docstring: shape), blank ones left out; Unreadable for any other shape
    (an id never makes one Unreadable: it is read where it can be, else the question has none)."""
    value = parsed.get('questions')
    if value is None:
        return []
    items = [value] if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise Unreadable(f'the {role} lists its questions in something other than a list')
    out = []
    for item in items:
        if isinstance(item, str):
            text, affects, ident, written = item, [], None, None
        elif isinstance(item, dict) and isinstance(item.get('question'), str):
            text, affects, ident = item['question'], _affects(item.get('affects'), role), _question_id(item.get('id'))
            written = item['id'] if ident is not None else None
        else:
            raise Unreadable(f'the {role} lists a question that is neither text nor an object with a question')
        if not blank_question(text):
            out.append(_Asked(text, affects, ident, written))
    return out


def _question_id(value: object) -> Optional[str]:
    """An id as read: a string that is not blank, or an integer as its decimal string; None for anything else."""
    if isinstance(value, str):
        return None if blank_question(value) else value
    return str(value) if type(value) is int else None


def _own_questions(item: dict, where: str) -> tuple[list[_Own], _Refs]:
    """(The questions an item writes on itself - in its "question", then the question objects of its question_ids -
    and the ids it names: module docstring, shape). Unreadable only for a "question" in no shape it may have; what
    question_ids holds never makes it Unreadable."""
    field = _question_list(item.get('question'), where)
    inline, ids, written, unread = [], [], [], []
    for own in field:  # the id of a question object written in "question" is one the item names
        if own.id is not None:
            ids.append(own.id)
            written.append(own.written)
    value = item.get('question_ids')
    for entry in value if isinstance(value, list) else [value]:
        if isinstance(entry, dict) and isinstance(entry.get('question'), str) and not blank_question(entry['question']):
            ident = _question_id(entry.get('id'))  # question text written on the item, with its id when it has one
            inline.append(_Own(entry['question'], ident, entry['id'] if ident is not None else None, True))
            if ident is not None:
                ids.append(ident)
                written.append(entry['id'])
            continue
        ident = _question_id(entry)
        if ident is not None:
            ids.append(ident)
            written.append(entry)
        elif entry is not None and not isinstance(entry, str):
            unread.append(entry)
    return field + inline, _Refs(ids, written, unread)


def _affects(value: object, role: str) -> list[str]:
    """What a question names as affected: codes or line labels, an integer as its decimal string; absent, null or a
    null item names nothing; Unreadable for any other shape."""
    if value is None:
        return []
    out = []
    for entry in value if isinstance(value, list) else [value]:
        if entry is None:
            continue
        if isinstance(entry, str):
            out.append(entry)
        elif type(entry) is int:
            out.append(str(entry))
        else:
            raise Unreadable(f'the {role} names what a question affects in a shape that is neither a code nor a line')
    return out


def blank_question(text: str) -> bool:
    """Whether a question's text is blank: nothing is left of it once U+FEFF and white space are removed - the one test
    of a blank question (the shape, the round's questions, studio.decisions and studio.customer use it). The customer
    page drops a question whose text JavaScript's trim() empties. Every code point trim() removes is white space to
    Python's str.strip() too, except U+FEFF (tests.test_question_ids enumerates them), so a text blank to the page is
    blank here, and a question the server keeps is one the page shows. The converse does not hold: str.strip() also
    removes U+001C to U+001F and U+0085, which trim() keeps (tests.test_question_ids pins those five)."""
    return not text.replace('\ufeff', '').strip()


def _folded(text: str) -> str:
    """A question's text with case and whitespace folded: two questions whose folded texts are equal are one."""
    return ' '.join(text.split()).casefold()


class _Entry:
    """One question of the round as it is built: ``number`` - its place in the round, from 0, given when it is made:
    the key every set of questions uses (never id(), which a freed object can reuse) - its text and folded text, its
    source and the lines it names (a set; ordered by the round only when stored)."""
    __slots__ = ('number', 'text', 'folded', 'source', 'lines')

    def __init__(self, number: int, text: str, folded: str, source: str):
        self.number, self.text, self.folded, self.source, self.lines = number, text, folded, source, set()


class _Questions:
    """The round's questions as they are built (module docstring: Questions); out() gives them as stored, each {'id',
    'text', 'lines', 'codes', 'source'}, in the order asked. Each step costs in proportion to what it reads: a set of
    questions is a dict of entry numbers, and an item's ids are resolved once (resolve)."""

    def __init__(self, rows: list[dict]):
        self.order = [row['line'] for row in rows]
        self.codes = {row['line']: row['code'] for row in rows}
        self.by_code: dict[str, list[str]] = {}  # a code (as compared) -> the lines carrying it, in order
        for label in self.order:
            self.by_code.setdefault(_key(self.codes[label]), []).append(label)
        self.entries: list[_Entry] = []
        self.by_text: dict[str, _Entry] = {}
        # whose list -> id (as compared) -> the numbers of the questions carrying it, in the order they were defined
        self.ids: dict[str, dict[str, dict[int, None]]] = {'reader': {}, 'checker': {}}
        self.named_lines: set = set()  # the lines a question names
        self.plain_lines: set = set()  # the lines a question names by its affects or a line's "question" text

    def named(self, affects: list[str]) -> list[str]:
        """The lines a question's ``affects`` names: a line label, or every line carrying a code it names."""
        found = []
        for entry in affects:
            key = _key(entry)
            found += [key] if key in self.codes else self.by_code.get(key, [])
        return found

    def add(self, text: str, lines: list[str], source: str, *, plain: bool = True) -> _Entry:
        """The question with this text (folded), asked now unless it is already, naming ``lines`` too - by today's
        naming (its affects or a line's "question" text) when ``plain``."""
        folded = _folded(text)
        entry = self.by_text.get(folded)
        if entry is None:
            entry = self.by_text[folded] = _Entry(len(self.entries), text, folded, source)
            self.entries.append(entry)
        self._name(entry, lines, plain)
        return entry

    def _name(self, entry: _Entry, lines: list[str], plain: bool):
        entry.lines.update(lines)
        self.named_lines.update(lines)
        if plain:
            self.plain_lines.update(lines)

    def define(self, text: str, lines: list[str], source: str, ident: Optional[str], *, plain: bool):
        """A question of ``source``'s (add), defined under its id when it has one."""
        entry = self.add(text, lines, source, plain=plain)
        if ident is not None:
            self.ids[source].setdefault(_key(ident), {})[entry.number] = None

    def resolve(self, refs: _Refs, source: str) -> list[int]:
        """The numbers of the questions ``refs`` names, among those its author was shown (the reader's for the reader;
        the reader's and the checker's for the checker), each once, in the order of the ids."""
        found: dict[int, None] = {}
        for key in dict.fromkeys(_key(ident) for ident in refs.ids):
            for author in ('reader',) if source == 'reader' else ('reader', 'checker'):
                for number in self.ids[author].get(key, ()):
                    found[number] = None
        return list(found)

    def refer(self, numbers: list[int], lines: list[str]):
        """Every question in ``numbers`` names ``lines`` too."""
        for number in numbers:
            self._name(self.entries[number], lines, False)

    def names(self, label: str, *, plain: bool = False) -> bool:
        """Whether a question names line ``label`` - by today's naming only, when ``plain``."""
        return label in (self.plain_lines if plain else self.named_lines)

    def texts(self, own: list[_Own], numbers: list[int]) -> list[str]:
        """What a line or a review shows as its questions: its "question" texts as written, then the text of each
        question object it writes in its question_ids and of every question in ``numbers`` (what its ids name) that
        it does not show already."""
        out = [item.text for item in own if not item.inline]
        seen = {_folded(text) for text in out}
        for text, folded in [(item.text, _folded(item.text)) for item in own if item.inline] + [
                (self.entries[number].text, self.entries[number].folded) for number in numbers]:
            if folded not in seen:
                seen.add(folded)
                out.append(text)
        return out

    def out(self) -> list[dict]:
        """The round's questions as stored, in the order asked: {id (q1, q2..), text, lines (in the round's order),
        codes (those lines' codes, each once), source}."""
        stored = []
        for entry in self.entries:
            lines = [label for label in self.order if label in entry.lines]
            stored.append({'id': f'q{entry.number + 1}', 'text': entry.text, 'lines': lines,
                           'codes': list(dict.fromkeys(self.codes[label] for label in lines)), 'source': entry.source})
        return stored


def _questions(reader: dict, checker: dict, rows: list[dict], every: list[dict], about: list[tuple[dict, list[str]]],
               matched: dict[str, list[dict]]) -> _Questions:
    """The round's questions (module docstring). ``rows`` and ``every``: the stored rows and their lines, in order;
    ``about``: each review and the lines its ids are about; ``matched``: the reviews belonging to each reader line.
    Sets ``named`` on every line and review: the numbers of the questions its ids name."""
    questions = _Questions(rows)
    for parsed, source in ((reader, 'reader'), (checker, 'checker')):
        for asked in _asked(parsed, source):
            questions.define(asked.text, questions.named(asked.affects), source, asked.id, plain=True)
    for row, line in zip(rows, every):  # each line's own questions: its "question" text, then its question objects
        for own in line['asked']:
            questions.define(own.text, [row['line']], row['listed_by'], own.id, plain=not own.inline)
    for review, lines in about:  # a question a review defines on itself, with an id: one of the checker's
        for own in review['asked']:
            if own.id is not None:
                questions.define(own.text, lines, 'checker', own.id, plain=False)
    for row, line in zip(rows, every):  # the lines and missed codes naming questions by their ids
        line['named'] = questions.resolve(line['refs'], row['listed_by'])
        questions.refer(line['named'], [row['line']])
    for review, lines in about:  # and the reviews
        review['named'] = questions.resolve(review['refs'], 'checker')
        questions.refer(review['named'], lines)
    for row in rows:
        if row['status'] != NEEDS_ANSWER or questions.names(row['line'], plain=True):
            continue
        texts = [own.text for review in matched.get(row['line'], ()) for own in review['asked']]
        for text in texts:  # what the agreeing reviews wrote on themselves is asked as today, whatever an id names
            questions.add(text, [row['line']], 'checker')
        if not texts and not questions.names(row['line']):
            questions.add(UNASKED_QUESTION.format(code=row['code']), [row['line']], 'studio')
    return questions


def _problems(value: object) -> list[str]:
    """The documentation problems as shown: each string as written, any other item as its JSON text (module
    docstring)."""
    if value is None:
        return []
    return [item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            for item in (value if isinstance(value, list) else [value])]


# --- citations: the sections of an answer --------------------------------------------------------------------------

def _section_events(text: str, role: str, codes: dict[str, str]) -> list[tuple[int, str]]:
    """[(offset, key)] where a section starts (a marker: its line's key, or ``_document`` when its line or code is
    not that line's) or ends (an END line, a marker-like line, a heading, a thematic break, a code fence, the final
    answer: ``_document``), in order; nothing after the start of the final answer starts a section."""
    marks = _ROLE_MARKS[role]
    events, offset = [], 0
    for line in text.split('\n'):
        marker = _MARKER.fullmatch(line)
        if marker and marks.get(marker.group(1)) == marker.group(2)[0]:
            label, code = marker.group(2), marker.group(3)
            events.append((offset, label if label in codes and _key(codes[label]) == code else DOCUMENT_KEY))
        else:  # a section ends where what ends it starts on its line
            ends = [match.start() for match in (_MARKER_LIKE.search(line), _HEADING.match(line)) if match]
            if line.strip() == END_MARK or _RULE.fullmatch(line) or _FENCE.fullmatch(line):
                ends.append(len(line) - len(line.lstrip()))
            if ends:
                events.append((offset + min(ends), DOCUMENT_KEY))
        offset += len(line) + 1
    final = final_answer(text)
    if final is not None:  # the final answer, wherever it starts: nothing at or after its start is a section
        events = [event for event in events if event[0] < final[1]] + [(final[1], DOCUMENT_KEY)]
    return events


def _section_of(events: list[tuple[int, str]], offsets: list[int], start: int, end: int) -> str:
    """The key a text block [start, end) of the joined text is filed under: the section it is in; ``_document`` when
    it is in no section, or when a section starts or ends inside it (its citations cannot be told apart).
    ``offsets``: the events' offsets, in order."""
    first, past = bisect.bisect_left(offsets, start), bisect.bisect_left(offsets, end)
    if first != past:
        return DOCUMENT_KEY
    return events[first - 1][1] if first else DOCUMENT_KEY


# --- values ---------------------------------------------------------------------------------------------------------

def _key(code: str) -> str:
    return code.strip().upper()


def _str(value: object) -> Optional[str]:
    return value if isinstance(value, str) else None


def _int(value: object) -> Optional[int]:
    return value if type(value) is int else None


def _units(value: object, where: str) -> Optional[int]:
    """A line's units (module docstring: shape): a whole number of zero or more, or the number a string of digits only
    writes; None when absent or null (not given); Unreadable for any other shape."""
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and _DIGITS.fullmatch(value):
        try:
            return int(value)
        except ValueError:  # more digits than an integer may be read from
            pass
    raise Unreadable(f'{where} gives its units in a shape that is not a whole number')


def _plain_units(value: object) -> Optional[int]:
    """A review's correct_units as stored: a whole number of zero or more, else None."""
    return value if type(value) is int and value >= 0 else None


def _modifiers(value: object, where: str) -> Optional[list[str]]:
    """A line's modifiers (module docstring: shape): its string items as written, an integer item as its decimal
    string, a blank item removed; None when absent or null (not given); Unreadable for any other shape."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise Unreadable(f'{where} lists its modifiers in something other than a list')
    out = []
    for item in value:
        if isinstance(item, str):
            if item.strip():
                out.append(item)
        elif type(item) is int:
            out.append(str(item))
        else:
            raise Unreadable(f'{where} has a modifier that is neither text nor a whole number')
    return out


def _reason(value: object, where: str) -> Optional[str]:
    """A reason (module docstring: shape): text as written, a list of strings joined with one space; None when absent
    or null; Unreadable for any other shape."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ' '.join(value)
    raise Unreadable(f'{where} gives its reason in a shape that is not text')


def _question_list(value: object, where: str) -> list[_Own]:
    """A line's or a review's "question" (module docstring: shape): its questions, blank ones left out, each with the
    id its object carries (or none); Unreadable for any other shape."""
    if value is None:
        return []
    if isinstance(value, str):
        items = [_Own(value, None, None, False)]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = [_Own(item, None, None, False) for item in value]
    elif isinstance(value, dict) and isinstance(value.get('question'), str):
        ident = _question_id(value.get('id'))
        items = [_Own(value['question'], ident, value['id'] if ident is not None else None, False)]
    else:
        raise Unreadable(f'{where} asks its question in a shape that is not text')
    return [item for item in items if not blank_question(item.text)]


def _question_text(asked: list[str]) -> Optional[str]:
    """Questions as a line shows them: one per line of text, blank ones left out; None when none is left."""
    shown = [text for text in asked if not blank_question(text)]
    return '\n'.join(shown) if shown else None


def _strings(value: object) -> Optional[list[str]]:
    """A list of strings as written; None when it is not one."""
    if not isinstance(value, list):
        return None
    return list(value) if all(isinstance(item, str) for item in value) else None


def _evidence(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [{'quote': item['quote'], 'page': _int(item.get('page'))} for item in value
            if isinstance(item, dict) and isinstance(item.get('quote'), str)]
