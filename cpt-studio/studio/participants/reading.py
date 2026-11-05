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

references_used (harness-reading@2, HARNESS.md 11.2) is the participant's claim. Each entry's ``retrieved`` is CPT
Studio's check of it: True only when the ref is among ``refs_retrieved``, the refs the tool results of that participant's
own run returned to it (loop.LoopOutcome.refs_retrieved); a reference cited but never retrieved stays False.

An answer no structured-output mode constrained (Fable's since anthropic-messages@cptstudio-harness-3, HARNESS.md 12.8)
is first reduced by sole_object - one implementation for the reading and the peer review - to the one JSON object it
must be, alone or alone in a single json code fence; anything else refuses it whole. The object's text is then read
here (or by peer.py) exactly as any answer is.

Since anthropic-messages@cptstudio-harness-4 (HARNESS.md, "Harness repair 3", F-CONTRACT), such an answer's object
fields that its schema does not declare are first set aside (set_aside), for that version alone. None of them is read,
and each is named in the reading's problems: where it was, whether it was empty, and its size, never its text. The raw
response keeps them. What remains is validated exactly as before (types, enums, every required field), so an answer
that lacks a field or gives one a wrong type is still refused whole. More than MAX_SET_ASIDE such fields refuse it
whole too. A constrained answer (Astra's) and every earlier version's stored answer are read exactly as before.
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
from studio.types import (EvidenceSpan, ExtractionIssue, ReferenceUse, LocatedQuote, ParticipantCode, ParticipantLesion,
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
MAX_REFERENCES = 64  # references_used entries (harness-reading@2, HARNESS.md 11.2)
MAX_SPANS = 8  # occurrences located per quote
MIN_QUOTE_CHARACTERS = 8  # non-space characters a quote needs before it is located at all
MAX_SET_ASIDE = 64  # fields outside the schema an unconstrained answer may carry before it is refused whole
CODE = re.compile(r'[0-9]{4}[0-9A-Z]')
UNITS = range(1, 100)
TOO_SHORT, NOT_FOUND = 'too short', 'not found'
# The bounded lists inside an item, by field name: (limit, what one entry is called).
_ITEM_LISTS = {'evidence': (MAX_QUOTES, 'quotes'), 'lesions': (MAX_LESIONS, 'lesions'),
               'modifiers': (MAX_MODIFIERS, 'modifiers'), 'service_ids': (MAX_SERVICE_IDS, 'service ids')}
_TOP_LISTS = (('services', MAX_SERVICES, 'services'), ('codes', MAX_CODES, 'codes'),
              ('not_coded', MAX_NOT_CODED, 'not-coded items'), ('clarifications', MAX_QUESTIONS, 'clarifications'),
              ('extraction_issues', MAX_EXTRACTION_ISSUES, 'extraction issues'),
              ('references_used', MAX_REFERENCES, 'references used'))
_SCHEMA_KEYWORDS = frozenset({'type', 'properties', 'required', 'additionalProperties', 'items', 'enum'})
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_RECORDED_MODEL = re.compile(r'[\x21-\x7e]{1,100}')  # fits ProviderRun.returned_model
_VENDOR_WORD = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]*')  # how a vendor states a status, a stop reason, a category
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


# --- an answer no structured-output mode constrained (HARNESS.md 12.8) ----------------------------------------------

NOT_ONE_OBJECT = ('the answer is not exactly one JSON object with nothing before or after it, either alone or alone in '
                  'a single json code fence')
_JSON_WHITESPACE = ' \t\n\r'  # the only whitespace JSON allows around a value (RFC 8259): no other is stripped
# One fence: ``` or ```json on its own line, the content, then ``` on its own line, ending the answer.
_FENCED = re.compile(r'```(?:json)?[ \t]*\r?\n(.*)\r?\n[ \t]*```', re.DOTALL)


def sole_object(text) -> tuple[str, str]:
    """(the object's text, '') when ``text`` - the answer of a request whose output no structured-output mode
    constrained - is, once the JSON whitespace around it is stripped, exactly one JSON object, or exactly one JSON
    object inside a single ```json (or ```) fence with nothing else; otherwise ('', why), ``why`` being CPT Studio's own
    sentence and never the model's text.

    Nothing is repaired or coerced. The text returned is the model's own, unchanged: the stripped answer, or the
    stripped content of its one fence, and it must open with '{' and close with '}' - so prose before or after the
    object, an array, a fence naming another language and anything after a fence are refused here. The strict reader
    (read, peer.read) then refuses whatever is still not exactly one JSON object - two objects, two fences, a truncated
    object that happens to close with '}' - exactly as it refuses any answer."""
    if not isinstance(text, str):
        return '', 'there is no answer text'
    candidate = text.strip(_JSON_WHITESPACE)
    fenced = _FENCED.fullmatch(candidate)
    if fenced is not None:
        candidate = fenced.group(1).strip(_JSON_WHITESPACE)
    if not (candidate.startswith('{') and candidate.endswith('}')):
        return '', NOT_ONE_OBJECT
    return candidate, ''


# --- the reading ---------------------------------------------------------------------

def recorded_model(value) -> str:
    """A model name as a response states it, when it fits the record (ProviderRun.returned_model: visible ASCII, at
    most 100 characters); '' otherwise. Never shortened or rewritten."""
    return value if isinstance(value, str) and _RECORDED_MODEL.fullmatch(value) else ''


def quoted(value, limit: int = 300) -> str:
    """Vendor text for a problem message: whitespace collapsed, at most ``limit`` characters, or a plain stand-in.
    Never for text a model may have written (vendor_word, refused_by_model): a problem message is shown on the page and
    in the reports, and must not repeat model-written wording (I9)."""
    if not isinstance(value, str) or not value.strip():
        return 'no reason was given'
    text = ' '.join(value.split())
    return text if len(text) <= limit else text[:limit] + '...'


def vendor_word(value, limit: int = 60) -> str:
    """A reason a vendor states - a status, a stop reason, a refusal category - for a problem message: as stated when it
    is one word of at most ``limit`` letters, digits and ``_.:/-``; otherwise named by its length and never repeated -
    longer text can be anything, model-written descriptor-like wording included (I9; refutation round 1, IND-2) - and
    'no reason was given' when there is none."""
    if not isinstance(value, str) or not value.strip():
        return 'no reason was given'
    if len(value) <= limit and _VENDOR_WORD.fullmatch(value):
        return value
    return f'a value of {len(value):,} characters, not repeated'


def refused_by_model(message) -> str:
    """Why a reading is refused when the model refused in its own words: the refusal, named by its length only. The
    model writes that message and can write descriptor-like wording into it, so it is never repeated (I9; refutation
    round 1, IND-2: it reached the participants card, the encounter check, both reports and the trace)."""
    if not isinstance(message, str) or not message.strip():
        return 'the model refused (no reason was given)'
    return f'the model refused (its message, {len(message):,} characters, is not repeated)'


def named(value: str, limit: int = 100) -> str:
    """A vendor-stated name for a problem message: quoted, so a difference in spacing or case is visible, and
    bounded."""
    return repr(value if len(value) <= limit else value[:limit] + '...')


def refusal(provider: str, adapter_version: str, requested_model: str, returned_model: str,
            reason: str) -> ParticipantReading:
    """A reading refused whole: none of it is read, and its one problem says why."""
    ending = '' if reason.endswith(('.', '!', '?')) else '.'  # a vendor's own sentence keeps its full stop
    return ParticipantReading(provider=provider, adapter_version=adapter_version,
                              reading_version=prompt.READING_VERSION, requested_model=requested_model,
                              returned_model=returned_model, refused=True,
                              problems=(f'{REFUSED}{reason}{ending}',))


def read(answer: str, source: str, *, provider: str, adapter_version: str, requested_model: str,
         returned_model: str, refs_retrieved=frozenset(), set_aside_unknown: bool = False) -> ParticipantReading:
    """The reading in ``answer`` (the vendor's output text), its quotes located in ``source`` (the revision text the
    request carried as its context 0), each reference it used checked against ``refs_retrieved``.
    ``set_aside_unknown``: the answer of a version whose output nothing constrained and whose reading sets aside the
    fields its schema does not declare (set_aside; Fable's harness-4); False reads it exactly as before."""
    refs = retrieved_refs(refs_retrieved)

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
    notes: tuple[str, ...] = ()
    if set_aside_unknown:
        parsed, removed = set_aside(parsed, prompt.SCHEMA)
        if len(removed) > MAX_SET_ASIDE:
            return refused(too_many_set_aside(len(removed)))
        notes = tuple(set_aside_note(item) for item in removed)
    error = schema_error(parsed)
    if error:
        return refused(f'the answer breaks the reading schema: {error}')
    error = bound_error(parsed)
    if error:
        return refused(error)
    return _Reader(source, provider=provider, adapter_version=adapter_version, requested_model=requested_model,
                   returned_model=returned_model, notes=notes).read(parsed, refs)


def retrieved_refs(value) -> frozenset:
    """``refs_retrieved`` as a set: a set, frozenset, list or tuple of ref strings. Anything else is a programming
    error (TypeError) - a string especially, whose characters would otherwise each count as a ref."""
    if not isinstance(value, (set, frozenset, list, tuple)):
        raise TypeError('refs_retrieved must be a set of ref strings.')
    refs = frozenset(value)
    if not all(isinstance(ref, str) for ref in refs):
        raise TypeError('refs_retrieved must be a set of ref strings.')
    return refs


# --- schema --------------------------------------------------------------------------

def set_aside(value, schema: dict) -> tuple[object, tuple[tuple[str, bool, int], ...]]:
    """(``value`` with every object field its schema does not declare removed, the removed fields). For the answer of a
    version whose output nothing constrained (Fable's since anthropic-messages@cptstudio-harness-4; HARNESS.md, "Harness
    repair 3", F-CONTRACT). Each removed field is (where it was, whether its value was empty, the length of that value
    as canonical JSON). ``where`` is a path of declared names and list positions, with the field's own name as _name
    gives it, never its text. Empty means JSON null, or an empty string, list or object. Only an object's fields that
    its schema does not declare are removed, and only inside a value of the type the schema gives, so whatever breaks
    the schema otherwise is left for schema_error to refuse. Nothing else is changed, and ``value`` is not mutated."""
    removed: list[tuple[str, bool, int]] = []

    def walk(node, node_schema: dict, path: str):
        kind = node_schema.get('type')
        if kind == 'object' and isinstance(node, dict):
            properties = node_schema['properties']
            kept = {}
            for key, item in node.items():
                if key in properties:
                    kept[key] = walk(item, properties[key], f'{path}.{key}' if path else key)
                else:
                    where = f'{path} field {_name(key)}' if path else f'top-level field {_name(key)}'
                    empty = item is None or (isinstance(item, (str, list, dict)) and len(item) == 0)
                    size = len(json.dumps(item, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
                    removed.append((where, empty, size))
            return kept
        if kind == 'array' and isinstance(node, list):
            return [walk(item, node_schema['items'], f'{path}[{index}]') for index, item in enumerate(node)]
        return node

    return walk(value, schema, ''), tuple(removed)


def set_aside_note(item: tuple[str, bool, int]) -> str:
    """The problem that names one field set_aside removed: where it was, and that it was empty or how long it was."""
    where, empty, size = item
    what = 'was empty' if empty else f'held {size:,} characters, kept in the raw response'
    return (f'{where} is outside the schema; it {what}, and it was set aside and not read '
            '(an answer nothing constrained, HARNESS.md F-CONTRACT).')


def too_many_set_aside(count: int) -> str:
    """Why an answer with more than MAX_SET_ASIDE fields outside its schema is refused whole."""
    return (f'the answer carries {count:,} fields outside its schema, more than the {MAX_SET_ASIDE} this adapter sets '
            'aside')


def schema_error(value, schema: Optional[dict] = None, subject: str = 'the reading') -> str:
    """The first place ``value`` breaks ``schema`` (prompt.SCHEMA by default), or ''; ``subject`` names the whole value
    in the message. Interprets exactly the keywords prompt.py uses - type (object, array, string, integer, boolean),
    properties, required, additionalProperties (false only), items and enum - and refuses to judge a schema with any
    other, so a schema change cannot pass unchecked."""
    schema = prompt.SCHEMA if schema is None else schema
    _check_schema(json.dumps(schema, sort_keys=True))
    return _schema_error(value, schema, '', subject)


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
        elif kind not in ('string', 'integer', 'boolean'):
            raise ValueError(f'The reading schema uses the type {kind!r}, which this validator does not implement.')


def _schema_error(value, schema: dict, path: str, subject: str) -> str:
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict):
            return f'{path or subject} is not an object'
        properties = schema['properties']
        for key in value:
            if key not in properties:
                return f'{path or subject} has a field the schema does not allow ({_name(key)})'
        for key in schema.get('required', ()):
            if key not in value:
                return f'{path or subject} lacks the required field {key!r}'
        for key, child in properties.items():
            if key in value:
                error = _schema_error(value[key], child, f'{path}.{key}' if path else key, subject)
                if error:
                    return error
        return ''
    if kind == 'array':
        if not isinstance(value, list):
            return f'{path} is not a list'
        for index, item in enumerate(value):
            error = _schema_error(item, schema['items'], f'{path}[{index}]', subject)
            if error:
                return error
        return ''
    if kind == 'string':
        if not isinstance(value, str):
            return f'{path} is not a string'
        if 'enum' in schema and value not in schema['enum']:
            return f'{path} is not one of the values the schema allows'
        return ''
    if kind == 'boolean':
        return '' if type(value) is bool else f'{path} is not true or false'
    if type(value) is not int:  # 'integer': a JSON number with no fraction or exponent; a bool is not one
        return f'{path} is not an integer'
    return ''


def _name(key: str) -> str:
    """An object key a model wrote, for a schema problem: as _token names a value (IND-2: never repeated when it is
    not a short token)."""
    return _token(key)


# The shapes in which a problem quotes a model-written value as written: a CPT code (CODE), an HCPCS Level II code, a
# short id or modifier of letters and digits, a date or time written with digits and date punctuation only, a question
# id (a UUID) - none of which can carry descriptor text. Anything else is named only by its length (refutation round 3:
# the 20-character token rule this replaces quoted 'SYNTH;WITH-POLYP(S)' in problems that the owner's trace shows and a
# refused reading's reason carries to the page and the reports; I9).
_QUOTED = (CODE, re.compile(r'[A-Z][0-9]{4}'), re.compile(r'[A-Za-z0-9]{1,8}'), re.compile(r'[0-9][0-9/.:T+-]{0,31}'),
           re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'))


def _token(value: str) -> str:
    """How a problem names a model-written code, id, date or key: quoted only in one of the _QUOTED shapes, otherwise
    by its length only, so no text the model wrote into the field (a piece of a descriptor, say; I9) is repeated."""
    if any(shape.fullmatch(value) for shape in _QUOTED):
        return repr(value)
    return f'a value of {len(value):,} characters'


# --- bounds --------------------------------------------------------------------------

def bound_error(reading: dict, top_lists: tuple = _TOP_LISTS) -> str:
    """The first bound a schema-valid reading breaks, named by count, or ''. ``top_lists``: (key, limit, label) of each
    top-level list; the item lists and the text limits are the same for every schema that uses their field names."""
    for key, limit, label in top_lists:
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

    def __init__(self, source: str, notes: tuple[str, ...] = (), **identity):
        self.locator = Locator(source)
        self.identity = identity
        self.problems: list[str] = list(notes)  # the fields set_aside removed, first (F-CONTRACT)
        self.unverified = 0

    def quotes(self, items) -> tuple[LocatedQuote, ...]:
        located = tuple(self.locator.locate(item) for item in items)
        self.unverified += sum(1 for item in located if not item.spans)
        return located

    def read(self, parsed: dict, refs: frozenset) -> ParticipantReading:
        when = parsed['date_of_service']
        value = when['value']
        if value and not _iso_date(value):
            self.problems.append(f'date_of_service {_token(value)} is not a YYYY-MM-DD date; it was not used.')
            value = ''
        date_evidence = self.quotes(when['evidence'])
        services, ids = [], set()
        for index, item in enumerate(parsed['services']):
            if item['id'] in ids:
                self.problems.append(f'services[{index}] repeats the service id {_token(item["id"])}.')
            ids.add(item['id'])
            services.append(ParticipantService(
                id=item['id'], family=item['family'], status=item['status'], description=item['description'],
                anatomy=item['anatomy'], extent=item['extent'], technique=item['technique'],
                lesions=tuple(ParticipantLesion(**lesion) for lesion in item['lesions']),
                provider_role=item['provider_role'], evidence=self.quotes(item['evidence'])))
        codes = []
        for index, item in enumerate(parsed['codes']):
            where = f'codes[{index}] ({_token(item["code"])})'
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
                self.problems.append(f'{where} ({_token(item["code"])}) is not a five-character CPT code; '
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
        # harness-reading@2: what the participant says it relied on. ``retrieved`` is CPT Studio's check, never the
        # participant's claim: True only for a ref its own run's tool results returned to it (HARNESS.md 11.2); a run
        # without tools retrieved nothing.
        references = tuple(ReferenceUse(ref=item['ref'], use=item['use'], retrieved=item['ref'] in refs)
                           for item in parsed['references_used'])
        return ParticipantReading(
            reading_version=prompt.READING_VERSION, date_of_service=value, date_evidence=date_evidence,
            services=tuple(services), codes=tuple(codes), not_coded=tuple(not_coded), questions=tuple(questions),
            extraction_issues=tuple(issues), problems=tuple(self.problems), refused=False,
            unverified_quotes=self.unverified, references_used=references, **self.identity)

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
