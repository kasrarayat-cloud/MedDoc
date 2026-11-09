"""The persisted event inventory (design/contract.md 4.2, 4.3, 4.5 and 8.1; design/FINAL.md 4.1): the fields of one
EventInventory row, built for an answer that was read (row) or refused (refused_row), and the versioned reader that
gives them back (load).

load RAISES on anything it does not know, and never answers with None or an empty inventory: an unknown version pair,
an unknown state, a field missing, added or of the wrong type, a closed value it does not know, a quote whose offsets
are not its own text's, a passage whose spans do not fit its state, a verification report that names another label,
request or response, a refused row that carries content, a sha256 that no longer matches, a row bound to another
revision text or another response. The legacy review_view._inventory returned None for a record it could not read and
so silently stopped the base rules (contract 1); a new-path consumer gets a StoreError instead, and a refused row's
events cannot be read as an empty list by mistake (StoredInventory.events raises).

Every quote is the document's, never the model's (contract 4.2-4.4, P9). A quote is a record with a start, an end and a
text: a passage span, the words of an attribute or a lesion, a size span, the date's words, or one inside a record the
contract leaves open (a team member's name span). row is given the revision text, checks it against text_sha256, and
writes nothing unless every quote's text IS that text's slice at [start, end) (Mismatch). load, which has no text, keeps
the parts that need none: start at least 0 and end exactly start plus the text's length; a located passage has one span,
an ambiguous one 2 to 8 (reading.MAX_SPANS) and an unlocated one none, so it keeps its length only, never its text. The
row's sha256 and text_sha256 then bind what row checked to the text it was checked against.

The shapes are the contract's: the attribute record of 4.2 (with FINAL C2's ``occurrences`` on a words span), the
passages, lesions, events and relations of 4.3, the date of service of 8.1, the derived facts, the open questions and
the verification report. They are versioned by the (INTERPRETATION_VERSION, INVENTORY_VERSION) pair: a later shape is a
later version, and this reader refuses a pair it does not know. Every enumerated value is closed to its enumeration,
an event's target landmark included (schema.LANDMARKS). Where the contract leaves a record's inside open (an event's
``key``, an attribute's ``literals``, a team or reach entry, ``identity_by``) the reader asks for JSON data of the
stated container type and nothing more; an attribute's ``checks`` and ``reasons`` are strings until normalization's
closed lists exist (slice S02).

``sha256`` is types.sha256_json over every field but itself (FINAL 4.1: everything but ``id`` and ``created_at``), the
bindings included, so a row's hash binds its content to its encounter, revision and Gemini run. Pure and Django-free;
the persistence code maps FIELDS onto the model (the bindings are its foreign keys' attnames).
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Optional

from studio.interpretation import INTERPRETATION_VERSION, INVENTORY_VERSION, LABEL, schema
from studio.interpretation.read import STAGES, Refusal, iso_date
from studio.types import sha256_json, to_jsonable

READ, REFUSED = 'read', 'refused'
STATES = (READ, REFUSED)
BINDINGS = ('encounter_id', 'revision_id', 'provider_run_id')
COLUMNS = ('interpretation_version', 'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256', 'state')
CONTENT = ('events', 'encounter_facts', 'open_questions', 'verification')
HASHED = BINDINGS + COLUMNS + CONTENT
FIELDS = HASHED + ('sha256',)
EMPTY_EVENTS = {'passages': [], 'lesions': [], 'events': [], 'relations': []}

BASES = ('stated', 'default', 'absent')
ATTRIBUTE_STATES = ('verified', 'unverified', 'absent', 'discarded')
PASSAGE_STATES = ('located', 'ambiguous', 'unlocated')
# The spans each passage state has (contract 4.3): one place; 2 to 8 places (the Locator keeps at most
# reading.MAX_SPANS = 8 occurrences, contract 5.1); none, so an unlocated passage keeps its length only.
SPANS = MappingProxyType({'located': (1, 1), 'ambiguous': (2, 8), 'unlocated': (0, 0)})
QUOTE_KEYS = frozenset({'start', 'end', 'text'})  # a record holding all three is a quote of the revision text
MATCHES = ('exact', 'normalized')
EXTENDED = ('', 'closing_bracket')
IDENTITIES = ('verified', 'unresolved', 'none')
CURRENT = ('yes', 'no', 'unresolved')
RELATION_TYPES = ('contradiction', 'doubt', 'unresolved', 'independent', 'dismissed_claim', 'step', 'bundling_identity')
COUNTS = ('claimed', 'verified', 'unverified', 'absent', 'discarded', 'open')

_SHA256 = re.compile(r'[0-9a-f]{64}')
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,39}')


class StoreError(ValueError):
    """A stored interpretation this release cannot read. Never caught to mean "no inventory"."""


class UnknownVersion(StoreError):
    """The row's (interpretation_version, inventory_version) pair is not one this release reads."""


class UnknownShape(StoreError):
    """A field is missing, added, of the wrong type, or holds a closed value this release does not know."""


class Mismatch(StoreError):
    """The row disagrees with itself (sha256, verification report) or with what it is bound to (text, response)."""


# --- the shapes --------------------------------------------------------------------------------------------------------
# Each spec's problem(value, path) gives '' or the first problem, naming the place and never the stored value: a stored
# value can be a slice of the revision text.

class _Spec:
    def problem(self, value, path: str) -> str:
        raise NotImplementedError


class _Type(_Spec):
    def __init__(self, test, what: str):
        self.test, self.what = test, what

    def problem(self, value, path: str) -> str:
        return '' if self.test(value) else f'{path} is not {self.what}'


def _finite_number(value) -> bool:
    return (type(value) is int) or (type(value) is float and math.isfinite(value))


_STR = _Type(lambda value: isinstance(value, str), 'a string')
_INT = _Type(lambda value: type(value) is int, 'an integer')
_BOOL = _Type(lambda value: type(value) is bool, 'true or false')
_NULL = _Type(lambda value: value is None, 'null')
_NUMBER = _Type(_finite_number, 'a finite number')
_SHA = _Type(lambda value: isinstance(value, str) and _SHA256.fullmatch(value) is not None, 'a sha256')
_ISO = _Type(lambda value: isinstance(value, str) and iso_date(value), 'a YYYY-MM-DD date')


class _Enum(_Spec):
    def __init__(self, values):
        self.values = frozenset(values)

    def problem(self, value, path: str) -> str:
        return '' if isinstance(value, str) and value in self.values else f'{path} is not a value this release knows'


class _Const(_Spec):
    def __init__(self, value):
        self.value = value

    def problem(self, value, path: str) -> str:
        return '' if value == self.value and type(value) is type(self.value) else f'{path} is not empty'


class _Either(_Spec):
    def __init__(self, *specs: _Spec):
        self.specs = specs

    def problem(self, value, path: str) -> str:
        problems = [spec.problem(value, path) for spec in self.specs]
        return '' if '' in problems else problems[0]


class _List(_Spec):
    def __init__(self, item: _Spec):
        self.item = item

    def problem(self, value, path: str) -> str:
        if not isinstance(value, list):
            return f'{path} is not a list'
        for index, item in enumerate(value):
            problem = self.item.problem(item, f'{path}[{index}]')
            if problem:
                return problem
        return ''


class _Map(_Spec):
    """An object whose keys the contract leaves open: string keys, each value of one spec."""

    def __init__(self, value: _Spec):
        self.value = value

    def problem(self, value, path: str) -> str:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            return f'{path} is not an object'
        for key, item in value.items():
            problem = self.value.problem(item, f'{path}[{_named(key)}]')
            if problem:
                return problem
        return ''


class _Obj(_Spec):
    """An object with exactly its required fields, plus any of its optional ones."""

    def __init__(self, required: dict, optional: Optional[dict] = None):
        self.required, self.optional = required, optional or {}

    def problem(self, value, path: str) -> str:
        if not isinstance(value, dict):
            return f'{path} is not an object'
        for key in self.required:
            if key not in value:
                return f'{path} lacks the field {key}'
        for key in value:
            if key not in self.required and key not in self.optional:
                return f'{path} has a field this release does not know ({_named(key)})'
        for key, item in value.items():
            spec = self.required.get(key) or self.optional[key]
            problem = spec.problem(item, f'{path}.{key}')
            if problem:
                return problem
        return ''


class _Quote(_Spec):
    """A quote of the revision text (contract 4.2): the record ``shape`` gives, whose offsets are its own text's - start
    at least 0, end exactly start plus the text's length. Whether the text IS the revision text's slice there needs the
    text, so row checks it (_quotes); a stored row keeps that check through its sha256 and text_sha256."""

    def __init__(self, shape: _Spec):
        self.shape = shape

    def problem(self, value, path: str) -> str:
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        if value['start'] < 0 or value['end'] - value['start'] != len(value['text']):
            return f'{path} has offsets that are not those of its own text'
        return ''


class _Passage(_Spec):
    """A passage (contract 4.3) whose spans fit its state (SPANS): one when located, 2 to 8 when ambiguous, none when
    unlocated."""

    def __init__(self, shape: _Spec):
        self.shape = shape

    def problem(self, value, path: str) -> str:
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        least, most = SPANS[value['state']]
        count = len(value['spans'])
        if least <= count <= most:
            return ''
        wanted = 'none' if most == 0 else 'exactly one' if least == most == 1 else f'{least} to {most}'
        return f'{path} has {count:,} span{"" if count == 1 else "s"}; {value["state"]} passages have {wanted}'


class _Json(_Spec):
    """Any JSON data: objects with string keys, lists, strings, integers, finite numbers, true, false, null."""

    def problem(self, value, path: str) -> str:
        pending = [value]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if not all(isinstance(key, str) for key in node):
                    return f'{path} is not JSON data'
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
            elif not (node is None or isinstance(node, (str, bool)) or _finite_number(node)):
                return f'{path} is not JSON data'
        return ''


def _named(key) -> str:
    """A stored object key for a problem: as written when it is a short name, else by its length only."""
    if isinstance(key, str) and _NAME.fullmatch(key):
        return key
    return f'a key of {len(key):,} characters' if isinstance(key, str) else 'a key that is not a string'


_JSON = _Json()
_IDS = _List(_STR)
_SPAN = _Quote(_Obj({'start': _INT, 'end': _INT, 'text': _STR}))
_WORDS = _Quote(_Obj({'start': _INT, 'end': _INT, 'text': _STR, 'match': _Enum(MATCHES)}, {'occurrences': _INT}))


def _attribute(values: Optional[tuple] = None, extra: Optional[dict] = None,
               optional: Optional[dict] = None) -> _Obj:
    """The one attribute record (contract 4.2), its value one of ``values`` when the attribute has an enumeration."""
    return _Obj({
        'value': _Enum(values) if values else _Either(_STR, _INT, _NULL),
        'basis': _Enum(BASES),
        'state': _Enum(ATTRIBUTE_STATES),
        'open': _BOOL,
        'words': _Either(_WORDS, _NULL),
        'passages': _IDS,
        'checks': _List(_STR),
        'literals': _Map(_JSON),
        'reasons': _List(_STR),
        **(extra or {}),
    }, optional)


_PASSAGE = _Passage(_Obj({'id': _STR, 'state': _Enum(PASSAGE_STATES), 'spans': _List(_SPAN), 'reason': _STR,
                           'chars': _INT, 'extended': _Enum(EXTENDED)}))
_LESION = _Obj({
    'id': _STR,
    'words': _Either(_WORDS, _NULL),
    'landmark': _Enum(schema.LANDMARKS),
    'site': _attribute(schema.LANDMARKS),
    'size': _Obj({'mm': _List(_NUMBER), 'span': _Either(_WORDS, _SPAN, _NULL)}),
    'multiplicity': _Enum(schema.MULTIPLICITY),
    'passages': _IDS,
    'state': _Enum(ATTRIBUTE_STATES),
    'reasons': _List(_STR),
    'distinct_from': _IDS,
    'possibly_same_as': _IDS,
})
_EVENT = _Obj({
    'id': _STR,
    'family': _STR,
    'procedure': _attribute(schema.PROCEDURES),
    'kind': _attribute(schema.KINDS),
    'technique': _attribute(schema.DEVICES),
    'target': _attribute(schema.LANDMARKS, extra={'lesion': _STR, 'identity': _Enum(IDENTITIES), 'identity_by': _JSON}),
    'time': _attribute(schema.TIMES),
    'performer': _attribute(schema.PERFORMERS),
    'status': _attribute(schema.STATUSES),
    'scope': _attribute(schema.SCOPES, optional={'targets': _IDS}),
    'purpose': _attribute(schema.PURPOSES),
    'part_of': _Either(_attribute(), _STR),
    'sequence': _Either(_attribute(), _INT),
    'extent': _Either(_attribute(schema.LANDMARKS), _NULL),
    'completion': _Either(_attribute(schema.COMPLETIONS), _NULL),
    'visit': _Either(_Obj({'basis': _attribute(schema.EM_BASES),
                           'separately_identifiable': _attribute(schema.SEPARATE)}), _NULL),
    'catalogue_kind': _STR,
    'code_technique': _STR,
    'positive': _BOOL,
    'current': _Enum(CURRENT),
    'key': _Map(_JSON),
})
_RELATION = _Obj({'id': _STR, 'type': _Enum(RELATION_TYPES), 'statement': _STR, 'event': _STR, 'attribute': _STR,
                  'reason': _STR, 'claimed_by_model': _BOOL, 'passages': _IDS})
_EVENTS = _Obj({'passages': _List(_PASSAGE), 'lesions': _List(_LESION), 'events': _List(_EVENT),
                'relations': _List(_RELATION)})
_DATE_OF_SERVICE = _Obj({
    'state': _Enum(schema.DATE_STATES),
    'value': _Either(_ISO, _NULL),
    'verified': _BOOL,
    'words': _Either(_WORDS, _NULL),
    'passages': _IDS,
    'reasons': _List(_STR),
    'candidates': _List(_ISO),
    'readings': _List(_ISO),
    'others': _Obj({role: _List(_Map(_JSON)) for role in schema.DATE_ROLES if role != 'this_encounter'}),
})
_ENCOUNTER_FACTS = _Obj({
    'date_of_service': _DATE_OF_SERVICE,
    'documenting_endoscopist': _Map(_JSON),
    'team': _List(_Map(_JSON)),
    'anatomy': _List(_Map(_JSON)),
    'reach': _List(_Map(_JSON)),
    'visits': _List(_Map(_JSON)),
    'derived': _Obj({'current_families': _IDS,
                     'procedure_day': _Obj({'performed': _IDS, 'possible': _IDS}),
                     'absent': _IDS}),
})
_OPEN_QUESTIONS = _List(_Obj({'about': _Enum(schema.QUESTION_ABOUT), 'events': _IDS, 'lesions': _IDS, 'passages': _IDS,
                              'attached_to': _List(_JSON)}))
_VERIFICATION = {
    'label': _STR,
    'request_sha256': _SHA,
    'response_sha256': _SHA,
    'counts': _Map(_Obj({name: _INT for name in COUNTS})),
    'reasons': _Map(_INT),
    'relations': _Map(_INT),
    'discarded': _List(_Obj({'where': _STR, 'reason': _STR})),
    'problems': _List(_STR),
    'refused': _BOOL,
}
_REFUSED_VERIFICATION = {**_VERIFICATION, 'counts': _Const({}), 'reasons': _Const({}), 'relations': _Const({}),
                         'discarded': _Const([]), 'stage': _Enum(STAGES)}

# What each known version pair stores, by state. A new pair is added here only with its own shapes.
_SHAPES = {
    (INTERPRETATION_VERSION, INVENTORY_VERSION): {
        READ: {'events': _EVENTS, 'encounter_facts': _ENCOUNTER_FACTS, 'open_questions': _OPEN_QUESTIONS,
               'verification': _Obj(_VERIFICATION)},
        REFUSED: {'events': _Const(EMPTY_EVENTS), 'encounter_facts': _Const({}), 'open_questions': _Const([]),
                  'verification': _Obj(_REFUSED_VERIFICATION)},
    },
}
_LABELS = {(INTERPRETATION_VERSION, INVENTORY_VERSION): LABEL}
KNOWN_VERSIONS = frozenset(_SHAPES)


# --- what a consumer gets ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StoredInventory:
    """One EventInventory row as load read and checked it. The content of a read row is reached through ``events``,
    ``encounter_facts`` and ``open_questions``; on a refused row each of them raises StoreError, so a refused answer is
    never taken for one that documents nothing. ``refusal`` gives a refused row's Refusal (None for a read row)."""
    encounter_id: str
    revision_id: str
    provider_run_id: str
    interpretation_version: str
    inventory_version: str
    text_sha256: str
    request_sha256: str
    response_sha256: str
    state: str
    verification: dict
    sha256: str
    _content: dict = field(repr=False)  # read through the properties only, so a refusal is never read as empty

    @property
    def label(self) -> str:
        return _LABELS[(self.interpretation_version, self.inventory_version)]

    @property
    def refused(self) -> bool:
        return self.state == REFUSED

    @property
    def refusal(self) -> Optional[Refusal]:
        if not self.refused:
            return None
        return Refusal(stage=self.verification['stage'], reason=self.verification['problems'][0])

    @property
    def events(self) -> dict:
        return self._readable('events')

    @property
    def encounter_facts(self) -> dict:
        return self._readable('encounter_facts')

    @property
    def open_questions(self) -> list:
        return self._readable('open_questions')

    def _readable(self, name: str):
        if self.refused:
            raise StoreError(f'This interpretation was refused, so it has no {name.replace("_", " ")}: '
                             f'{self.verification["problems"][0]}')
        return self._content[name]


# --- writing -----------------------------------------------------------------------------------------------------------

def row(*, encounter_id, revision_id, provider_run_id, revision_text: str, text_sha256: str, request_sha256: str,
        response_sha256: str, events, encounter_facts, open_questions, verification) -> dict:
    """The FIELDS of the row for an answer that was read and normalized, at the current versions, with its sha256.
    ``revision_text`` is the text the answer was read against; its sha256 must be ``text_sha256`` (Mismatch), and it is
    not stored. The content is converted to JSON data (types.to_jsonable). The verification report gets the label and
    the run's request and response sha256 where it does not carry them, and ``refused`` False; a value it carries must
    already be right. The row is then read back by load, so nothing is written that the reader would refuse, and last
    every quote in it is checked against ``revision_text`` (contract 4.2, re-checked on store): Mismatch unless each is
    that text's own slice at its offsets. StoreError otherwise; TypeError when ``revision_text`` is not a string."""
    if not isinstance(revision_text, str):
        raise TypeError('The revision text must be a string.')
    report = to_jsonable(verification)
    if not isinstance(report, dict):
        raise UnknownShape('verification is not an object')
    for key, value in (('label', LABEL), ('request_sha256', request_sha256), ('response_sha256', response_sha256),
                       ('refused', False)):
        if key in report and report[key] != value:
            raise Mismatch(f'The verification report names another {key.replace("_", " ")} than this row.')
        report[key] = value
    fields = _finished(_bound(encounter_id, revision_id, provider_run_id), READ, text_sha256, request_sha256,
                       response_sha256, {'events': to_jsonable(events), 'encounter_facts': to_jsonable(encounter_facts),
                                         'open_questions': to_jsonable(open_questions), 'verification': report})
    if _text_sha256(revision_text) != fields['text_sha256']:
        raise Mismatch('The revision text given is not the text this row names (text_sha256).')
    _quotes(fields, revision_text)
    return fields


def refused_row(refusal: Refusal, *, encounter_id, revision_id, provider_run_id, text_sha256: str,
                request_sha256: str, response_sha256: str) -> dict:
    """The FIELDS of the row for an answer refused whole (contract 4.5): state ``refused``, no events, no encounter
    facts, no open questions, and a verification report holding the refusal's sentence as its one problem and its stage.
    It is bound to its run like any row, so the operator record and the retry door read a durable fact."""
    if not isinstance(refusal, Refusal):
        raise TypeError('A refused row records a read.Refusal.')
    report = {'label': LABEL, 'request_sha256': request_sha256, 'response_sha256': response_sha256, 'counts': {},
              'reasons': {}, 'relations': {}, 'discarded': [], 'problems': [refusal.reason], 'refused': True,
              'stage': refusal.stage}
    return _finished(_bound(encounter_id, revision_id, provider_run_id), REFUSED, text_sha256, request_sha256,
                     response_sha256, {'events': copy.deepcopy(EMPTY_EVENTS), 'encounter_facts': {},
                                       'open_questions': [], 'verification': report})


def _bound(encounter_id, revision_id, provider_run_id) -> dict:
    return {name: _uuid(value, name) for name, value in zip(BINDINGS, (encounter_id, revision_id, provider_run_id))}


def _finished(bindings: dict, state: str, text_sha256: str, request_sha256: str, response_sha256: str,
              content: dict) -> dict:
    fields = {**bindings, 'interpretation_version': INTERPRETATION_VERSION, 'inventory_version': INVENTORY_VERSION,
              'text_sha256': text_sha256, 'request_sha256': request_sha256, 'response_sha256': response_sha256,
              'state': state, **content}
    try:
        fields['sha256'] = content_sha256(fields)
    except (TypeError, ValueError):
        raise UnknownShape('The interpretation to store is not JSON data.') from None
    load(fields, text_sha256=text_sha256, response_sha256=response_sha256)
    return fields


def _text_sha256(text: str) -> str:
    """SourceRevision.text_sha256's value for ``text``: the sha256 of its UTF-8 bytes (jobs.stage_extract). '' for a text
    UTF-8 cannot encode (a lone surrogate), which no revision's text_sha256 can name."""
    try:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    except UnicodeEncodeError:
        return ''


def _quotes(fields: Mapping, revision_text: str) -> None:
    """Mismatch unless every quote in the content (a record holding QUOTE_KEYS, wherever it sits: in a shape this module
    knows or inside a record the contract leaves open) is ``revision_text``'s own slice at its offsets, never the
    model's string (contract 4.2-4.4, P9). UnknownShape for such a record whose offsets are not integers or whose text is
    not a string. A problem names the place, never the text."""
    pending = [(fields[name], name) for name in reversed(CONTENT)]
    while pending:
        value, path = pending.pop()
        if isinstance(value, dict):
            if QUOTE_KEYS.issubset(value):
                start, end, text = value['start'], value['end'], value['text']
                if type(start) is not int or type(end) is not int or not isinstance(text, str):
                    raise UnknownShape(f'The interpretation to store is not readable: {path} is a quote whose offsets '
                                       'are not integers or whose text is not a string.')
                if not 0 <= start <= end <= len(revision_text) or revision_text[start:end] != text:
                    raise Mismatch(f'The interpretation to store quotes at {path} what the revision text does not hold '
                                   'at those offsets.')
            pending.extend((item, f'{path}.{_named(key)}') for key, item in reversed(list(value.items())))
        elif isinstance(value, list):
            pending.extend((item, f'{path}[{index}]') for index, item in reversed(list(enumerate(value))))


def content_sha256(fields: Mapping) -> str:
    """types.sha256_json over the HASHED fields of ``fields`` (every field but ``sha256``), the bindings as UUID
    strings."""
    hashed = {name: fields[name] for name in HASHED}
    hashed.update({name: _uuid(fields[name], name) for name in BINDINGS})
    return sha256_json(hashed)


# --- reading -----------------------------------------------------------------------------------------------------------

def fields_of(instance) -> dict:
    """The FIELDS of an EventInventory-like object (its foreign keys by attname), for load. UnknownShape when one is
    missing."""
    missing = object()
    fields = {name: getattr(instance, name, missing) for name in FIELDS}
    absent = [name for name, value in fields.items() if value is missing]
    if absent:
        raise UnknownShape(f'The stored interpretation lacks {", ".join(absent)}.')
    return fields


def load(fields: Mapping, *, text_sha256: str, response_sha256: str) -> StoredInventory:
    """The row's content as StoredInventory, after every check the module docstring names. ``text_sha256`` is the bound
    revision's text_sha256 and ``response_sha256`` the sha256 of the bound run's stored response bytes, as the reader
    computes them: the row must name both. Raises UnknownVersion, UnknownShape or Mismatch (all StoreError); never
    returns None."""
    if not isinstance(fields, Mapping):
        raise UnknownShape('A stored interpretation must be a mapping of its fields.')
    missing = [name for name in FIELDS if name not in fields]
    extra = [name for name in fields if name not in FIELDS]
    if missing or extra:
        raise UnknownShape('The stored interpretation does not have exactly its fields'
                           f'{" (lacks " + ", ".join(missing) + ")" if missing else ""}'
                           f'{" (has " + ", ".join(_named(name) for name in extra) + ")" if extra else ""}.')
    versions = (fields['interpretation_version'], fields['inventory_version'])
    if not all(isinstance(value, str) for value in versions) or versions not in _SHAPES:
        raise UnknownVersion('This release reads no interpretation stored as '
                             f'{_version(versions[0])} with {_version(versions[1])}.')
    state = fields['state']
    if state not in STATES:
        raise UnknownShape('The stored interpretation has a state this release does not know.')
    bindings = {name: _uuid(fields[name], name) for name in BINDINGS}
    for name in ('text_sha256', 'request_sha256', 'response_sha256', 'sha256'):
        problem = _SHA.problem(fields[name], name)
        if problem:
            raise UnknownShape(f'The stored interpretation is not readable: {problem}.')
    shapes = _SHAPES[versions][state]
    for name in CONTENT:
        problem = shapes[name].problem(fields[name], name)
        if problem:
            raise UnknownShape(f'The stored interpretation is not readable: {problem}.')
    if state == READ:
        _unique_ids(fields['events'])
    _consistent(fields, versions, state)
    if content_sha256(fields) != fields['sha256']:
        raise Mismatch('The stored interpretation no longer matches its sha256.')
    if fields['text_sha256'] != text_sha256:
        raise Mismatch('The stored interpretation was made from another revision text.')
    if fields['response_sha256'] != response_sha256:
        raise Mismatch('The stored interpretation was read from another response than the stored one.')
    return StoredInventory(**bindings, interpretation_version=versions[0], inventory_version=versions[1],
                           text_sha256=fields['text_sha256'], request_sha256=fields['request_sha256'],
                           response_sha256=fields['response_sha256'], state=state,
                           verification=copy.deepcopy(fields['verification']), sha256=fields['sha256'],
                           _content=copy.deepcopy({name: fields[name] for name in CONTENT[:3]}))


def _unique_ids(events: dict) -> None:
    for key in ('passages', 'lesions', 'events', 'relations'):
        seen = set()
        for index, item in enumerate(events[key]):
            if item['id'] in seen:
                raise UnknownShape(f'The stored interpretation is not readable: events.{key}[{index}] repeats an id.')
            seen.add(item['id'])


def _consistent(fields: Mapping, versions: tuple, state: str) -> None:
    report = fields['verification']
    if report['label'] != _LABELS[versions]:
        raise Mismatch('The stored verification report names another interpretation label than its row.')
    if report['request_sha256'] != fields['request_sha256'] or report['response_sha256'] != fields['response_sha256']:
        raise Mismatch('The stored verification report names another request or response than its row.')
    if report['refused'] is not (state == REFUSED):
        raise Mismatch('The stored verification report and the row disagree on whether the answer was refused.')
    if state == REFUSED:
        problems = report['problems']
        if len(problems) != 1:
            raise UnknownShape('A refused interpretation records exactly one problem: its refusal.')
        try:
            Refusal(stage=report['stage'], reason=problems[0])
        except ValueError:
            raise UnknownShape('A refused interpretation records a refusal this release does not know.') from None


def _uuid(value, name: str) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        try:
            return str(uuid.UUID(value))
        except ValueError:
            pass
    raise UnknownShape(f'{name} is not a UUID.')


def _version(value) -> str:
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,39}', value):
        return repr(value)
    return 'an unknown value'
