"""A participant's reading of one revision, as CPT Studio reads and checks it (HARNESS.md 4; I6, I7).

The vendor's structured-output mode is not trusted. The reading's JSON is parsed strictly: a repeated key, NaN or
Infinity, NUL or a lone surrogate refuses it whole. It is validated against prompt.SCHEMA by this module (types, enums,
every required field, nothing else). Its bounds refuse it whole, named by count and never truncated: more than 64
services, codes or not-coded items, more than 32 clarifications, more than 16 quotes on one item, a quote over 600
characters or any other text over 2,000. Four lists the contract leaves open are bounded the same way (64 lesions per
service, 16 modifiers per code, 64 service ids per item, 64 extraction issues), so no answer inside the 4 MiB response
cap can hand the engine an unbounded list.

Every quote is located in the revision text after collapsing runs of whitespace in both, and nothing else (no case
folding, no other normalization). Each occurrence found, at most 8, becomes an exact EvidenceSpan: the revision text's
own slice, re-checked against the quote before it is kept. A quote with fewer than 8 non-space characters, or one that
is not found, is kept UNVERIFIED with the reason and is never evidence.

Item-level findings never refuse the reading; they are recorded as problems. A code that is not five characters
([0-9]{4}[0-9A-Z]) is kept as given. A code whose units fall outside 1 to 99 is dropped. A date of service that is not
YYYY-MM-DD and an extraction issue on a page below 1 are not used. Repeated service ids and service ids that no service
has are named.
"""
from __future__ import annotations

import functools
import json
import math
import re
from array import array
from bisect import bisect_right
from datetime import date
from typing import Optional

from studio.participants import prompt
from studio.types import (EvidenceSpan, ExtractionIssue, LocatedQuote, ParticipantCode, ParticipantLesion,
                          ParticipantNotCoded, ParticipantQuestion, ParticipantReading, ParticipantService)

REFUSED = 'The reading was not used: '  # every refusal problem starts so; the reason follows
MAX_SERVICES = 64
MAX_CODES = 64
MAX_NOT_CODED = 64
MAX_QUESTIONS = 32
MAX_QUOTES = 16  # per item
MAX_QUOTE_CHARS = 600
MAX_TEXT_CHARS = 2000  # every string that is not a quote
MAX_LESIONS = 64  # per service
MAX_MODIFIERS = 16  # per code
MAX_SERVICE_IDS = 64  # per item
MAX_EXTRACTION_ISSUES = 64
MAX_SPANS = 8  # occurrences located per quote
MIN_QUOTE_CHARACTERS = 8  # non-space characters a quote needs before it is located at all
CODE = re.compile(r'[0-9]{4}[0-9A-Z]')
UNITS = range(1, 100)
TOO_SHORT, NOT_FOUND = 'too short', 'not found'
# The bounded lists inside an item, by field name: (limit, what one entry is called).
_ITEM_LISTS = {'evidence': (MAX_QUOTES, 'quotes'), 'lesions': (MAX_LESIONS, 'lesions'),
               'modifiers': (MAX_MODIFIERS, 'modifiers'), 'service_ids': (MAX_SERVICE_IDS, 'service ids')}
_TOP_LISTS = (('services', MAX_SERVICES, 'services'), ('codes', MAX_CODES, 'codes'),
              ('not_coded', MAX_NOT_CODED, 'not-coded items'), ('clarifications', MAX_QUESTIONS, 'clarifications'),
              ('extraction_issues', MAX_EXTRACTION_ISSUES, 'extraction issues'))
_SCHEMA_KEYWORDS = frozenset({'type', 'properties', 'required', 'additionalProperties', 'items', 'enum'})
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_RECORDED_MODEL = re.compile(r'[\x21-\x7e]{1,100}')  # fits ProviderRun.returned_model
_WHITESPACE = re.compile(r'\s+')
_SURROGATE = re.compile('[\ud800-\udfff]')


# --- strict JSON ---------------------------------------------------------------------

class JSONRefused(ValueError):
    """A JSON document was refused. The message says why in words, without quoting the document."""


def strict_json(raw) -> object:
    """Parse UTF-8 JSON bytes as strict_json_text does."""
    try:
        text = bytes(raw).decode('utf-8')
    except UnicodeDecodeError:
        raise JSONRefused('is not valid UTF-8') from None
    return strict_json_text(text)


def strict_json_text(text: str) -> object:
    """Parse JSON, refusing what Python would otherwise accept silently or PostgreSQL could not store: duplicate keys,
    NaN/Infinity, overflowing numbers, NUL, unpaired surrogates (studio/providers/corti.py, the same rules)."""
    try:
        value = json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_no_constant,
                           parse_float=_finite_float)
        unstorable = _unstorable(value)
    except JSONRefused:
        raise
    except json.JSONDecodeError as exc:
        raise JSONRefused(f'is not valid JSON ({exc.msg} at character {exc.pos})') from None
    except (ValueError, RecursionError):
        raise JSONRefused('is not valid JSON') from None
    if unstorable:
        raise JSONRefused('contains NUL or unpaired surrogate characters')
    return value


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise JSONRefused('repeats a JSON object key, so its meaning is ambiguous')
        result[key] = value
    return result


def _no_constant(name):
    raise JSONRefused('contains a non-finite number')


def _finite_float(literal: str) -> float:
    value = float(literal)
    if not math.isfinite(value):
        raise JSONRefused('contains a number too large to represent')
    return value


def _unstorable(value) -> bool:
    if isinstance(value, str):
        return '\x00' in value or _SURROGATE.search(value) is not None
    if isinstance(value, dict):
        return any(_unstorable(key) or _unstorable(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_unstorable(item) for item in value)
    return False


# --- the reading ---------------------------------------------------------------------

def recorded_model(value) -> str:
    """A model name as a response states it, when it fits the record (ProviderRun.returned_model: visible ASCII, at
    most 100 characters); '' otherwise. Never shortened or rewritten."""
    return value if isinstance(value, str) and _RECORDED_MODEL.fullmatch(value) else ''


def quoted(value, limit: int = 300) -> str:
    """Vendor text for a problem message: whitespace collapsed, at most ``limit`` characters, or a plain stand-in."""
    if not isinstance(value, str) or not value.strip():
        return 'no reason was given'
    text = ' '.join(value.split())
    return text if len(text) <= limit else text[:limit] + '...'


def refusal(provider: str, adapter_version: str, requested_model: str, returned_model: str,
            reason: str) -> ParticipantReading:
    """A reading refused whole: none of it is read, and its one problem says why."""
    ending = '' if reason.endswith(('.', '!', '?')) else '.'  # a vendor's own sentence keeps its full stop
    return ParticipantReading(provider=provider, adapter_version=adapter_version,
                              reading_version=prompt.READING_VERSION, requested_model=requested_model,
                              returned_model=returned_model, refused=True,
                              problems=(f'{REFUSED}{reason}{ending}',))


def read(answer: str, source: str, *, provider: str, adapter_version: str, requested_model: str,
         returned_model: str) -> ParticipantReading:
    """The reading in ``answer`` (the vendor's output text), its quotes located in ``source`` (the revision text the
    request carried as its context 0)."""
    def refused(reason: str) -> ParticipantReading:
        return refusal(provider, adapter_version, requested_model, returned_model, reason)

    if not isinstance(answer, str):
        return refused('there is no answer text')
    if not isinstance(source, str):
        return refused('the request carries no revision text to locate quotes in')
    try:
        parsed = strict_json_text(answer)
    except JSONRefused as exc:
        return refused(f'the answer {exc}')
    error = schema_error(parsed)
    if error:
        return refused(f'the answer breaks the reading schema: {error}')
    error = bound_error(parsed)
    if error:
        return refused(error)
    return _Reader(source, provider=provider, adapter_version=adapter_version, requested_model=requested_model,
                   returned_model=returned_model).read(parsed)


# --- schema --------------------------------------------------------------------------

def schema_error(value, schema: Optional[dict] = None) -> str:
    """The first place ``value`` breaks ``schema`` (prompt.SCHEMA by default), or ''. Interprets exactly the keywords
    prompt.py uses - type (object, array, string, integer), properties, required, additionalProperties (false only),
    items and enum - and refuses to judge a schema with any other, so a schema change cannot pass unchecked."""
    schema = prompt.SCHEMA if schema is None else schema
    _check_schema(json.dumps(schema, sort_keys=True))
    return _schema_error(value, schema, '')


@functools.lru_cache(maxsize=8)
def _check_schema(encoded: str) -> None:
    pending = [json.loads(encoded)]
    while pending:
        node = pending.pop()
        unknown = set(node) - _SCHEMA_KEYWORDS
        if unknown:
            raise ValueError(f'The reading schema uses keywords this validator does not implement: {sorted(unknown)}.')
        kind = node.get('type')
        if kind == 'object':
            if node.get('additionalProperties') is not False or not set(node.get('required', ())) <= set(
                    node['properties']):
                raise ValueError('Every object in the reading schema must forbid additional properties and require '
                                 'only fields it declares.')
            pending.extend(node['properties'].values())
        elif kind == 'array':
            pending.append(node['items'])
        elif kind not in ('string', 'integer'):
            raise ValueError(f'The reading schema uses the type {kind!r}, which this validator does not implement.')


def _schema_error(value, schema: dict, path: str) -> str:
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict):
            return f'{_subject(path)} is not an object'
        properties = schema['properties']
        for key in value:
            if key not in properties:
                return f'{_subject(path)} has a field the schema does not allow ({_name(key)})'
        for key in schema.get('required', ()):
            if key not in value:
                return f'{_subject(path)} lacks the required field {key!r}'
        for key, child in properties.items():
            if key in value:
                error = _schema_error(value[key], child, f'{path}.{key}' if path else key)
                if error:
                    return error
        return ''
    if kind == 'array':
        if not isinstance(value, list):
            return f'{path} is not a list'
        for index, item in enumerate(value):
            error = _schema_error(item, schema['items'], f'{path}[{index}]')
            if error:
                return error
        return ''
    if kind == 'string':
        if not isinstance(value, str):
            return f'{path} is not a string'
        if 'enum' in schema and value not in schema['enum']:
            return f'{path} is not one of the values the schema allows'
        return ''
    if type(value) is not int:  # 'integer': a JSON number with no fraction or exponent; a bool is not one
        return f'{path} is not an integer'
    return ''


def _subject(path: str) -> str:
    return path or 'the reading'


def _name(key: str) -> str:
    return repr(key if len(key) <= 40 else key[:40] + '...')


# --- bounds --------------------------------------------------------------------------

def bound_error(reading: dict) -> str:
    """The first bound a schema-valid reading breaks, named by count, or ''."""
    for key, limit, label in _TOP_LISTS:
        if len(reading[key]) > limit:
            return f'it lists {len(reading[key]):,} {label}, more than the {limit} this adapter accepts'
    pending = [(reading, '', '')]
    while pending:
        value, path, field = pending.pop()
        if isinstance(value, dict):
            pending.extend((item, f'{path}.{key}' if path else key, key) for key, item in reversed(value.items()))
        elif isinstance(value, list):
            limit, label = _ITEM_LISTS.get(field, (None, ''))
            if limit is not None and len(value) > limit:
                return f'{path} lists {len(value):,} {label}, more than the {limit} one item may have'
            pending.extend((item, f'{path}[{index}]', field) for index, item in reversed(list(enumerate(value))))
        elif isinstance(value, str):
            limit = MAX_QUOTE_CHARS if field == 'evidence' else MAX_TEXT_CHARS
            if len(value) > limit:
                what = 'one quote' if field == 'evidence' else 'one text field'
                return f'{path} has {len(value):,} characters, more than the {limit:,} {what} may have'
    return ''


# --- locating quotes -----------------------------------------------------------------------

class Locator:
    """Finds quotes in a revision text after collapsing every run of whitespace, in the text and in the quote, to one
    space. The collapsed text is mapped back to the revision text by segments (a run of non-space characters, or one
    collapsed run of whitespace), so every span is the revision text's own slice."""

    def __init__(self, source: str):
        self.source = source
        pieces, self._collapsed_at, self._source_at = [], array('q'), array('q')
        position = collapsed = 0
        for match in _WHITESPACE.finditer(source):
            start, end = match.span()
            if start > position:
                self._segment(collapsed, position)
                pieces.append(source[position:start])
                collapsed += start - position
            self._segment(collapsed, start)
            pieces.append(' ')
            collapsed += 1
            position = end
        if position < len(source):
            self._segment(collapsed, position)
            pieces.append(source[position:])
        self.collapsed = ''.join(pieces)
        self._found: dict[str, tuple[EvidenceSpan, ...]] = {}

    def _segment(self, collapsed: int, source: int) -> None:
        self._collapsed_at.append(collapsed)
        self._source_at.append(source)

    def _offset(self, index: int) -> int:
        """The revision-text offset of collapsed character ``index``. For a non-space character it is exact; a quote
        never starts or ends on a space, so only those are asked for."""
        segment = bisect_right(self._collapsed_at, index) - 1
        return self._source_at[segment] + (index - self._collapsed_at[segment])

    def locate(self, quote: str) -> LocatedQuote:
        needle = _WHITESPACE.sub(' ', quote).strip(' ')
        if len(needle) - needle.count(' ') < MIN_QUOTE_CHARACTERS:
            return LocatedQuote(quote=quote, reason=TOO_SHORT)
        spans = self._found.get(needle)
        if spans is None:
            spans = self._found[needle] = self._spans(needle)
        return LocatedQuote(quote=quote, spans=spans) if spans else LocatedQuote(quote=quote, reason=NOT_FOUND)

    def _spans(self, needle: str) -> tuple[EvidenceSpan, ...]:
        spans, at = [], self.collapsed.find(needle)
        while at != -1 and len(spans) < MAX_SPANS:
            start, end = self._offset(at), self._offset(at + len(needle) - 1) + 1
            text = self.source[start:end]
            # Checked, never assumed (EvidenceSpan.exact): the slice must collapse to the quote it was found for.
            if _WHITESPACE.sub(' ', text) == needle:
                spans.append(EvidenceSpan(context_index=0, start=start, end=end, text=text, exact=True))
            at = self.collapsed.find(needle, at + 1)
        return tuple(spans)


class _Reader:
    """Builds a ParticipantReading from a schema-valid, bounded reading, recording item-level problems in order."""

    def __init__(self, source: str, **identity):
        self.locator = Locator(source)
        self.identity = identity
        self.problems: list[str] = []
        self.unverified = 0

    def quotes(self, items) -> tuple[LocatedQuote, ...]:
        located = tuple(self.locator.locate(item) for item in items)
        self.unverified += sum(1 for item in located if not item.spans)
        return located

    def read(self, parsed: dict) -> ParticipantReading:
        when = parsed['date_of_service']
        value = when['value']
        if value and not _iso_date(value):
            self.problems.append(f'date_of_service {_name(value)} is not a YYYY-MM-DD date; it was not used.')
            value = ''
        date_evidence = self.quotes(when['evidence'])
        services, ids = [], set()
        for index, item in enumerate(parsed['services']):
            if item['id'] in ids:
                self.problems.append(f'services[{index}] repeats the service id {_name(item["id"])}.')
            ids.add(item['id'])
            services.append(ParticipantService(
                id=item['id'], family=item['family'], status=item['status'], description=item['description'],
                anatomy=item['anatomy'], extent=item['extent'], technique=item['technique'],
                lesions=tuple(ParticipantLesion(**lesion) for lesion in item['lesions']),
                provider_role=item['provider_role'], evidence=self.quotes(item['evidence'])))
        codes = []
        for index, item in enumerate(parsed['codes']):
            where = f'codes[{index}] ({_name(item["code"])})'
            if item['units'] not in UNITS:
                self.problems.append(f'{where} gives {_units(item["units"])} units, outside 1 to 99; it was dropped.')
                continue
            if not CODE.fullmatch(item['code']):
                self.problems.append(f'{where} is not a five-character CPT code; it is kept as given.')
            self.unknown_services(where, item['service_ids'], ids)
            codes.append(ParticipantCode(code=item['code'], modifiers=tuple(item['modifiers']), units=item['units'],
                                         service_ids=tuple(item['service_ids']), basis=item['basis'],
                                         evidence=self.quotes(item['evidence']), confidence=item['confidence']))
        not_coded = []
        for index, item in enumerate(parsed['not_coded']):
            where = f'not_coded[{index}]'
            if item['code'] and not CODE.fullmatch(item['code']):
                self.problems.append(f'{where} ({_name(item["code"])}) is not a five-character CPT code; '
                                     'it is kept as given.')
            self.unknown_services(where, item['service_ids'], ids)
            not_coded.append(ParticipantNotCoded(service_ids=tuple(item['service_ids']), code=item['code'],
                                                 reason=item['reason'], evidence=self.quotes(item['evidence'])))
        questions = []
        for index, item in enumerate(parsed['clarifications']):
            self.unknown_services(f'clarifications[{index}]', item['service_ids'], ids)
            questions.append(ParticipantQuestion(question=item['question'], why=item['why'],
                                                 service_ids=tuple(item['service_ids']),
                                                 evidence=self.quotes(item['evidence'])))
        issues = []
        for index, item in enumerate(parsed['extraction_issues']):
            if item['page'] < 1:
                self.problems.append(f'extraction_issues[{index}] names page {_units(item["page"])}, which no '
                                     'document has; it was not used.')
                continue
            issues.append(ExtractionIssue(page=item['page'], issue=item['issue']))
        return ParticipantReading(
            reading_version=prompt.READING_VERSION, date_of_service=value, date_evidence=date_evidence,
            services=tuple(services), codes=tuple(codes), not_coded=tuple(not_coded), questions=tuple(questions),
            extraction_issues=tuple(issues), problems=tuple(self.problems), refused=False,
            unverified_quotes=self.unverified, **self.identity)

    def unknown_services(self, where: str, service_ids, ids: set) -> None:
        unknown = sum(1 for item in service_ids if item not in ids)
        if unknown:
            self.problems.append(f'{where} names {unknown} service id{"s" if unknown != 1 else ""} '
                                 'that no service has.')


def _iso_date(value: str) -> bool:
    if not _DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _units(value: int) -> str:
    if -1_000_000 < value < 1_000_000:
        return str(value)
    return 'over a million' if value > 0 else 'below minus a million'
