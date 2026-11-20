"""Reading the two final messages (BUILD-SPEC 4.4-4.6): the final JSON, the combination and the citations per code.

Parsing (4.4). The final JSON is the last ```json fenced block of the message's text blocks joined in order, or else
the widest {...} span; anything else is Unreadable and the round fails (nothing is resent). Validation is shape-only:
a field of the wrong type is dropped from display (None), never corrected. A shape that cannot be shown without losing
or inventing a code is Unreadable rather than dropped: the reader's ``codes`` and the checker's ``reviews`` must be
lists, ``missed_codes`` a list when present, every listed code a non-empty string, and every reader status one of the
three the reader is given (the combination reads them).

Combination (4.5), the only glue logic: a reader code keeps the reader's status when the checker's review of that code
says ``agree`` (every review of it, when it was reviewed more than once); otherwise it is ``needs_review``, with both
reasons kept. Every checker ``missed_codes`` entry is added as ``needs_review``. The questions are the reader's and then
the checker's, an exact duplicate after whitespace folding shown once. The problems are the reader's
documentation_problems.

Citations (4.6): the text blocks are walked in order; a line ``CODE <code>`` (reader) or ``REVIEW <code>`` (checker)
starts that code's section - markdown marks around it, a colon after the word or another letter case are read the
same - and every citation from then on, that block's own included, is filed under the code until the next such line;
citations before the first section go under ``_document``.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from .prompts import CHECKER_MARK, LISTING_KEYS, READER_MARK

READY, NEEDS_ANSWER, NOT_SUPPORTED, NEEDS_REVIEW = 'ready', 'needs_answer', 'not_supported', 'needs_review'
READER_STATUSES = (READY, NEEDS_ANSWER, NOT_SUPPORTED)
FINAL_STATUSES = (READY, NEEDS_ANSWER, NEEDS_REVIEW, NOT_SUPPORTED)
AGREE = 'agree'
DOCUMENT_KEY = '_document'
_FENCE = re.compile(r'```json\s*(.*?)```', re.S)


class Unreadable(Exception):
    """The answer holds no final JSON this step can show; the message says what was missing (for the operator)."""


def message_text(message: object) -> str:
    """The message's text blocks joined in order (the analysis and the final JSON)."""
    return ''.join(block['text'] for block in _blocks(message)
                   if block.get('type') == 'text' and isinstance(block.get('text'), str))


def last_json(text: str) -> object:
    """The last ```json fenced block that parses, else the widest {...} span when it parses, else None."""
    for chunk in reversed(_FENCE.findall(text)):
        try:
            return json.loads(chunk)
        except ValueError:
            continue
    first, last = text.find('{'), text.rfind('}')
    if first != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except ValueError:
            pass
    return None


def read_reader(message: object) -> dict:
    """The reader's final JSON object, as it was written; Unreadable when it cannot be shown (module docstring)."""
    parsed = _final_object(message, 'reader')
    if not isinstance(parsed.get('codes'), list):
        raise Unreadable('the reader result has no list of codes')
    for item in parsed['codes']:
        _reader_code(item)
    return parsed


def read_checker(message: object) -> dict:
    """The checker's final JSON object, as it was written; Unreadable when it cannot be shown."""
    parsed = _final_object(message, 'checker')
    if not isinstance(parsed.get('reviews'), list):
        raise Unreadable('the checker result has no list of reviews')
    missed = parsed.get('missed_codes')
    if missed is not None and not isinstance(missed, list):
        raise Unreadable('the checker result lists its missed codes in something other than a list')
    for item in missed or ():
        _missed_code(item)
    return parsed


def listing(reader: dict) -> list[dict]:
    """The reader's code list as the checker is given it (code, units, modifiers, status, question), as written."""
    return [{key: item.get(key) for key in LISTING_KEYS} for item in reader.get('codes') or () if isinstance(item, dict)]


def combine(reader: dict, checker: dict) -> dict[str, list]:
    """{'codes', 'questions', 'problems'} of a round from the two parsed results (4.5)."""
    reviews: dict[str, list[dict]] = {}
    for item in checker.get('reviews') or ():
        review = _review(item)
        if review is not None:
            reviews.setdefault(_key(review['code']), []).append(review)
    codes = []
    for item in reader.get('codes') or ():
        code = _reader_code(item)
        found = reviews.get(_key(code['code']), [])
        agrees = bool(found) and all(review['verdict'] == AGREE for review in found)
        codes.append({**_shown(code), 'status': code['status'] if agrees else NEEDS_REVIEW, 'listed_by': 'reader',
                      'second_check': _second_check(found, agrees)})
    for item in checker.get('missed_codes') or ():
        codes.append({**_shown(_missed_code(item)), 'status': NEEDS_REVIEW, 'listed_by': 'checker',
                      'second_check': None})
    return {'codes': codes, 'questions': _questions(reader, checker), 'problems': _strings(
        reader.get('documentation_problems'), keep=True) or []}


def citations(reader_message: object, checker_message: object) -> dict[str, list[dict]]:
    """{code: [{'text', 'page', 'source'}]} from both messages' citations (4.6); ``_document`` before any section."""
    found: dict[str, list[dict]] = {}
    for message, mark, source in ((reader_message, READER_MARK, 'reader'), (checker_message, CHECKER_MARK, 'checker')):
        header = re.compile(rf'^[ \t>#*_`]*{mark}:?[ \t]+([A-Za-z0-9]{{4,6}})(?![A-Za-z0-9])', re.M | re.I)
        current = DOCUMENT_KEY
        for block in _blocks(message):
            if block.get('type') != 'text':
                continue
            for match in header.finditer(block.get('text') if isinstance(block.get('text'), str) else ''):
                current = match.group(1)
            for cited in block.get('citations') or ():
                if not isinstance(cited, dict) or not isinstance(cited.get('cited_text'), str):
                    continue
                page = cited.get('start_page_number') if cited.get('type') == 'page_location' else None
                found.setdefault(current, []).append({'text': cited['cited_text'],
                                                      'page': page if type(page) is int else None, 'source': source})
    return found


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


def _reader_code(item: object) -> dict:
    item = _identity(item, 'reader code')
    if item.get('status') not in READER_STATUSES:
        raise Unreadable(f'the reader gave code {item["code"]!r} a status it was not given')
    return {'code': item['code'], 'units': _int(item.get('units')), 'modifiers': _strings(item.get('modifiers')),
            'listed_status': item['status'], 'reason': _str(item.get('reason')),
            'question': _str(item.get('question')), 'evidence': _evidence(item.get('evidence')),
            'status': item['status']}


def _missed_code(item: object) -> dict:
    item = _identity(item, 'missed code')
    return {'code': item['code'], 'units': _int(item.get('units')), 'modifiers': _strings(item.get('modifiers')),
            'listed_status': _str(item.get('status')), 'reason': _str(item.get('reason')),
            'question': _str(item.get('question')), 'evidence': _evidence(item.get('evidence'))}


def _shown(code: dict) -> dict:
    return {key: code[key] for key in ('code', 'units', 'modifiers', 'listed_status', 'reason', 'question',
                                       'evidence')}


def _review(item: object) -> Optional[dict]:
    """A review the combination can match to a reader code (its code a string), or None."""
    if not isinstance(item, dict) or not isinstance(item.get('code'), str):
        return None
    return {'code': item['code'], 'verdict': _str(item.get('verdict')), 'reason': _str(item.get('reason')),
            'question': _str(item.get('question')), 'correct_code': _str(item.get('correct_code')),
            'correct_units': _int(item.get('correct_units')),
            'correct_modifiers': _strings(item.get('correct_modifiers')),
            'correct_status': _str(item.get('correct_status')), 'evidence': _evidence(item.get('evidence'))}


def _second_check(found: list[dict], agrees: bool) -> dict:
    """The checker's view of a reader code: agrees True or False, or None when the checker did not review it. With
    more than one review the one shown is the first that does not agree (the first, when all do)."""
    if not found:
        return {'agrees': None, 'verdict': None, 'reason': None, 'question': None, 'correct_code': None,
                'correct_units': None, 'correct_modifiers': None, 'correct_status': None, 'evidence': []}
    shown = found[0] if agrees else next(review for review in found if review['verdict'] != AGREE)
    return {'agrees': agrees, **{key: value for key, value in shown.items() if key != 'code'}}


def _questions(reader: dict, checker: dict) -> list[dict]:
    out: list[dict] = []
    seen: dict[str, dict] = {}
    for parsed, source in ((reader, 'reader'), (checker, 'checker')):
        items = parsed.get('questions')
        for item in items if isinstance(items, list) else ():
            if not isinstance(item, dict) or not isinstance(item.get('question'), str) or not item['question'].strip():
                continue
            codes = _strings(item.get('affects')) or []
            folded = ' '.join(item['question'].split())
            if folded in seen:  # shown once; the codes it affects are kept together
                seen[folded]['codes'] += [code for code in codes if code not in seen[folded]['codes']]
                continue
            entry = {'id': f'q{len(out) + 1}', 'text': item['question'], 'codes': list(dict.fromkeys(codes)),
                     'source': source}
            seen[folded] = entry
            out.append(entry)
    return out


def _key(code: str) -> str:
    return code.strip().upper()


def _str(value: object) -> Optional[str]:
    return value if isinstance(value, str) else None


def _int(value: object) -> Optional[int]:
    return value if type(value) is int else None


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
