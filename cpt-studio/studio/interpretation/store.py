"""The persisted event inventory (design/contract.md 4.2, 4.3, 4.5, 8.1 and 8.3; design/FINAL.md 4.1): the fields of one
EventInventory row, built for an answer that was read (row) or refused (refused_row), and the versioned reader that
gives them back (load).

load RAISES on anything it does not know, and never answers with None or an empty inventory: an unknown version pair,
an unknown state, a field missing, added or of the wrong type, a closed value it does not know, a quote whose offsets
are not its own text's, a passage whose spans do not fit its state or repeat a place, a verification report that names
another label, request or response, a refused row that carries content, a sha256 that no longer matches, a row bound
to another revision text or another response. The legacy review_view._inventory returned None for a record it could
not read and so silently stopped the base rules (contract 1); a new-path consumer gets a StoreError instead, and a
refused row's events cannot be read as an empty list by mistake (StoredInventory.events raises).

Every quote is the document's, never the model's (contract 4.2-4.4, P9). A quote is a record with a start, an end and a
text: a passage span, the words of an attribute or a lesion, a size span, the date's words, or one inside a record the
contract leaves open (a team member's name span). row is given the revision text, checks it against text_sha256, and
writes nothing unless every quote's text IS that text's slice at [start, end) (Mismatch). load, which has no text, keeps
the parts that need none: start at least 0 and end exactly start plus the text's length; a located passage has one span,
an ambiguous one 2 to 8 (reading.MAX_SPANS), each at a place of its own, and an unlocated one none, so it keeps its
length only, never its text. The row's sha256 and text_sha256 then bind what row checked to the text it was checked
against.

The shapes are the contract's: the attribute record of 4.2 (with FINAL C2's ``occurrences`` on a words span), the
passages, lesions, events and relations of 4.3, the date of service of 8.1, the reach, visit and anatomy entries of 4.3
and 8.3 in the shapes normalization writes (slice S02), the derived facts, the open questions and the verification
report. They are versioned by the (INTERPRETATION_VERSION, INVENTORY_VERSION) pair: a later shape is a later version,
and this reader refuses a pair it does not know. A field whose value the contract draws from an enumeration (the
schema's, or its own: BASES, ATTRIBUTE_STATES, PASSAGE_STATES, MATCHES, EXTENDED, IDENTITIES, CURRENT, RELATION_TYPES)
is closed to it, in an attribute (an event's target landmark included, schema.LANDMARKS), a passage, a lesion, an
event, a relation, the date of service, a reach, visit or anatomy entry and an open question; the report's relation
counts are keyed by relation type. Left open, as the contract leaves them, and read as JSON data of the stated
container type and nothing more: an event's ``key``, an attribute's ``literals``, a target's ``identity_by``, the
documenting endoscopist and team records (name spans and tokens, 8.3), the date's other-date entries and an open
question's ``attached_to``. The names of checks and reasons - an attribute's ``checks`` and ``reasons``, a relation's
and a discarded entry's ``reason``, the report's ``reasons`` and ``counts`` keys - are strings: their closed lists are
normalization's (verify.REASONS and CHECKS, normalize.COUNTED), which this module does not import.

``sha256`` is types.sha256_json over every field but itself (FINAL 4.1: everything but ``id`` and ``created_at``), the
bindings included, so a row's hash binds its content to its encounter, revision and Gemini run. Pure and Django-free;
the persistence code maps FIELDS onto the model (the bindings are its foreign keys' attnames).

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 1.7, 3.1 B1, 3.2.4, 6.2 and 6.3; step 1d of its 8.1) adds its own writer
and reader beside v1's, in the section ``design v2`` at the end of this module, under v2 names - the suffix _V2 or _v2
where a v1 name exists, as interpretation/__init__.py names v2's labels: row_v2, refused_row_v2, load_v2,
fields_of_v2, content_sha256_v2, StoredInventoryV2, BINDINGS_V2 (which adds ``appraisal_run_id``, migration 0015, so a
v2 row's sha256 binds both of its Gemini runs), HASHED_V2, FIELDS_V2 and READ_VERSIONS; and textfree_v2, the text-free
view of a read row's events that the engine builds its FactSet from (DECISIONS D188). Every v1 name above keeps its
value and its behaviour: jobs.py and readers.py call them until steps 5b and 5c switch, v1's tests read them for good
(FINAL-V2 5.0), and every stored v1 row's sha256 is over v1's HASHED. v1's reader is also kept as ``_v1_reader``, the
one handle readers' V1 branch (label legacy_record) reads a v1 row through once 5c switches. The v2 section imports
only contract/ and the package's labels - pass 1's refusal stages and sentence and the ISO date shapes are
contract/extract_read's own (FINAL-V2 5.7), never copies - so it executes no line of schema, read or studio.types, and
no line of v1's reader above it (tests/v2/test_store.py traces both). It imports contract/ on first use (_v2), so
importing this module still loads exactly the modules v1's store did (tests/test_interpretation_prompt.py pins that
set, and the tests of the retired modules are edited by no step, FINAL-V2 8.0).
"""
from __future__ import annotations

import copy
import dataclasses
import enum
import hashlib
import math
import re
import string
import threading
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Optional
from typing import Any  # design v2: the names _v2_build binds on first use

from studio.interpretation import INTERPRETATION_VERSION, INVENTORY_VERSION, LABEL, schema
from studio.interpretation.read import STAGES, Refusal, iso_date
from studio.types import sha256_json, to_jsonable

# design v2 (the section ``design v2`` below): the package's labels here, and contract/ on first use only (_v2)
from studio.interpretation import INTERPRETATION_PAIR, INVENTORY_VERSION_V2

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
    """An object of string keys, each value of one spec. Its keys are closed to ``keys`` when given (the report's
    relation counts, by relation type); without them they are left open, as the contract leaves them."""

    def __init__(self, value: _Spec, keys=None):
        self.value, self.keys = value, None if keys is None else frozenset(keys)

    def problem(self, value, path: str) -> str:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            return f'{path} is not an object'
        for key, item in value.items():
            if self.keys is not None and key not in self.keys:
                return f'{path} has a key this release does not know ({_named(key)})'
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
    unlocated - each span at a place of its own, so a passage located once is never stored as ambiguous. A place is
    where a span starts: the Locator finds each occurrence once, from its own start (occurrences may overlap), and the
    closing-bracket rule moves an end only."""

    def __init__(self, shape: _Spec):
        self.shape = shape

    def problem(self, value, path: str) -> str:
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        least, most = SPANS[value['state']]
        count = len(value['spans'])
        if not least <= count <= most:
            wanted = 'none' if most == 0 else 'exactly one' if least == most == 1 else f'{least} to {most}'
            return f'{path} has {count:,} span{"" if count == 1 else "s"}; {value["state"]} passages have {wanted}'
        if len({item['start'] for item in value['spans']}) != count:
            return f'{path} has two spans at one place; a passage is located at places that differ'
        return ''


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
# The reach, visit and anatomy entries (contract 4.3 and 8.3) in the shapes normalization writes (slice S02:
# normalize.Draft._attach_reach, _attach_visits and _bind_anatomy), every value closed to its enumeration. A reach entry
# is contract 4.3's event id, family, landmark and state, plus its reasons and whether it was attached to its
# examination; a visit entry gives its basis and its separate identifiability, each with its state, and whether it was
# attached to its visit; an anatomy entry is the attribute record over LANDMARKS plus the structure's anatomy state.
_REACH = _Obj({'event': _STR, 'family': _STR, 'landmark': _Enum(schema.LANDMARKS), 'state': _Enum(ATTRIBUTE_STATES),
               'reasons': _List(_STR), 'attached': _BOOL})
_VISIT = _Obj({'event': _STR, 'basis': _Enum(schema.EM_BASES), 'basis_state': _Enum(ATTRIBUTE_STATES),
               'separately_identifiable': _Enum(schema.SEPARATE),
               'separately_identifiable_state': _Enum(ATTRIBUTE_STATES), 'attached': _BOOL})
_ANATOMY = _attribute(schema.LANDMARKS, extra={'anatomy': _Enum(schema.ANATOMY_STATES)})
_ENCOUNTER_FACTS = _Obj({
    'date_of_service': _DATE_OF_SERVICE,
    'documenting_endoscopist': _Map(_JSON),
    'team': _List(_Map(_JSON)),
    'anatomy': _List(_ANATOMY),
    'reach': _List(_REACH),
    'visits': _List(_VISIT),
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
    'relations': _Map(_INT, keys=RELATION_TYPES),  # {type: count} (contract 4.3)
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


# --- v1's reader, kept (FINAL-V2 5.7 and 6.2) -------------------------------------------------------------------------

def _v1_fields_of(instance) -> dict:
    """fields_of for readers' V1 branch: v1's FIELDS of an EventInventory-like object, refused (UnknownShape) when it
    names an appraisal run, since a v1 row binds one Gemini run and migration 0015's column is design v2's."""
    if getattr(instance, 'appraisal_run_id', None) is not None:
        raise UnknownShape(f'A stored interpretation of {INTERPRETATION_VERSION} names an appraisal run, which only '
                           'design v2 rows bind.')
    return fields_of(instance)


class _v1_reader:  # noqa: N801 - the name FINAL-V2 5.7 gives it
    """v1's reader, kept whole for the rows v1 wrote (FINAL-V2 5.7 and 6.2): this module's v1 objects themselves, so a
    v1 row reads exactly as it always has. jobs.py and readers.py reach them by their v1 names until steps 5b and 5c
    switch; from then on readers' V1 branch (label legacy_record) is their one caller, reading a v1 row AS STORED. They
    execute v1's schema and read; the v2 reader below never does. ``fields_of`` adds one refusal to v1's: a row that
    names an appraisal run is not a v1 row."""
    KNOWN_VERSIONS = KNOWN_VERSIONS
    FIELDS = FIELDS
    StoredInventory = StoredInventory
    load = staticmethod(load)
    fields_of = staticmethod(_v1_fields_of)
    content_sha256 = staticmethod(content_sha256)


# ======================================================================================================================
# === design v2 (FINAL-V2 1.7, 3.1 B1, 3.2.4, 6.2, 6.3): everything below executes contract/ and the standard library
# === only - never schema, read, studio.types, or a line of v1's reader above (tests/v2/test_store.py traces it).
# ======================================================================================================================
#
# ONE v2 EventInventory row (FINAL-V2 1.7, 6.3). Its columns: the four BINDINGS_V2 (the encounter, the revision, pass
# 1's ProviderRun and the appraisal ProviderRun of pass 2, NULL only on a refused row), interpretation_version
# INTERPRETATION_PAIR and inventory_version INVENTORY_VERSION_V2, text_sha256, pass 1's request_sha256 and
# response_sha256, state, the four JSON columns and sha256 - sha256_of (contract/jsonschema) over every field but
# itself, which is types.sha256_json's value for JSON data, so a row's hash binds its content to its revision and both
# runs.
#
# A READ row (both passes settled; never one pass alone):
#   events          = {units, encounter, people, sections, sessions, anatomy, lesions, events, doubts, claims, unlisted}
#   encounter_facts = {}    (the encounter is events.encounter; the column is NOT NULL)
#   open_questions  = []    (doubts are events.doubts; the column is NOT NULL)
#   verification    = {label, request_sha256, response_sha256 (pass 1's, as the row's), appraisal_request_sha256,
#                      appraisal_response_sha256 (the appraisal run's), claims_sha256 (claims_sha256_v2 of
#                      events.claims), refused: false, counts {attribute: {result: n}}, reasons {reason: n}, doubts,
#                      health, coherence (JSON data), unlisted {kept: n, dropped: [{units, what, kind, session,
#                      event}]}, usage {interpretation, appraisal} (JSON objects)}
# A REFUSED row records a refused pass-1 answer: appraisal_run_id NULL, events {}, encounter_facts {}, open_questions
#   [], verification {label, request_sha256, response_sha256, refused: true, stage (one of pass 1's), problems: [the
#   refusal sentence]}. A refused or unhealthy pass-2 answer is recorded on its ProviderRun and the stage, never as a
#   row (6.3): refused_row_v2 takes no appraisal run, and load_v2 refuses a refused row that names one.
#
# events, field by field (FACT is one settled fact, below; [FACT] a FACTS field, one per member; ids canonical as
# engine/types.Id.parse reads them; UNITS a list of unit ids S<k>; SOURCE a settled source, below):
#   units     [{id S1..Sn in document order, start, end, line, paragraph, page, forced}]    offsets only, no text (1.7)
#   encounter {date_of_service FACT(ISO date), other_dates [{value: ISO date, role FACT(DateRole)}],
#              documenting_clinician FACT(P)}
#   people    [{id P, name SOURCE, role FACT(PersonRole)}]
#   sections  [{id N, start SOURCE, end [SOURCE], owner FACT(Owner), role FACT(SectionRole), occasion
#              FACT(DateRelation), performer FACT(Performer), performer_person FACT(P)}]
#   sessions  [{id X, examination FACT(E), kind FACT(SessionKind), encounter FACT(EncounterRelation), tract FACT(Tract),
#              approach FACT(Approach), through FACT(Y), reached [FACT(Extent)], device_reached [FACT(Extent)],
#              reached_anatomy FACT(Y), completion FACT(Completion), stations [FACT(Station)], part_of_session FACT(X),
#              completeness: null | {appraisal, result (supported | unresolved), reasons}}]   the stations completeness
#              claim's settled result, for an upper EUS session whose stations list is empty (3.2.2 [R:SC-B])
#   anatomy   [{id Y, type FACT(AnatomyType), organ FACT(Landmark), subtype FACT(AnastomosisSubtype), joins
#              [FACT(Landmark)]}]
#   lesions   [{id L, description SOURCE, multiplicity FACT(Multiplicity), places [FACT(Landmark)], distinct_from
#              [FACT(L)], same_as [FACT(L)]}]
#   events    [{id E, anchor {units UNITS, kind_words WORDS|null, status_words WORDS|null}, restatements [{units UNITS,
#              role FACT(RestatementRole)}], kind FACT(Kind), other_class FACT(OtherClass), status FACT(Status), session
#              FACT(X), date_relation FACT(DateRelation), date FACT(ISO date), performer FACT(Performer),
#              performer_person FACT(P), entry FACT(Owner), target {lesion FACT(L), structure FACT(Structure), places
#              [FACT(Landmark)], anatomy FACT(Y), duct FACT(Duct)}, technique {device FACT(Device), route FACT(Route)},
#              purpose FACT(Purpose), cause FACT(Cause), cause_event FACT(E), part_of FACT(E), part_relation
#              FACT(PartRelation), yield FACT(Material), access_outcome FACT(AccessOutcome), scope {breadth
#              FACT(Breadth), targets [FACT(L)], segment [FACT(Landmark)], covers [FACT(E)], excepts [FACT(E)]}, visit
#              {basis FACT(EmBasis), separately_identifiable FACT(Separate)}}]
#              An act's date_relation, performer and performer_person are its EFFECTIVE facts (1.5: inherited ones carry
#              claim.inherited_from, the section's id), and entry is the owner of its anchor's section, settled per act
#              (3.3); every Attribute of contract/types is one of these fields.
#   doubts    [{about DoubtAbout, objects [ids], units UNITS, basis DoubtBasis, readings [values]}]    as pass 1 gave
#              them, each reading a value (no free text, P9)
#   claims    [{id K1..Kn in their seeded order, role CLAIM_ROLES, template (a claims.py template id), subject (the
#              object's id; '' for the encounter), attribute Attribute, value, units UNITS, content (the claim's
#              content key), verdict: null | {verdict, attached, qualifiers, evidence}}]: every claim sent to pass 2
#              (controls, pair controls and the completeness claim included), each with pass 2's verdict stored
#              beside its content key (3.2.4 [R:MO-5])
#   unlisted  [{units UNITS, what UnlistedWhat, kind Kind|null, session X|null}]                 the kept ones (3.2.6)
#
# FACT (contract/types.SettledFact, FINAL-V2 1.7): {claim {state FactState|null (null: silent), value ('' when silent
#   or contradicted), qualifiers [Qualifier], options [{value, sources [SOURCE]}], inherited_from N|null}, sources
#   [SOURCE], checks {integrity, geometry, literal, consistency (ok | failed), literals [{value ISO, precision}],
#   qualified}, appraisal: null | {claim K, content, verdict, attached, qualifiers [Qualifier2], evidence UNITS,
#   control: null | {claim K, verdict}}, result Result, reasons [Reason]}
# SOURCE (contract/types.SettledSource): {units UNITS, link Link, words WORDS|null (null: the whole units), geometry}
# WORDS (contract/types.LocatedWords): {start, end, text}: text is the revision's own slice there (row_v2 proves it, P9)
#
# What load_v2 holds a fact to, besides its shape (FINAL-V2 3.3, read as integrity; any failure is UnknownShape): its
# value and its options' values are values of its attribute's domain ('' when not established); a silent claim holds
# no value, option, qualifier, source or appraisal and settles unknown or contradicted; an appraisal is only on a
# supported or negated claim; an ESTABLISHED result (supported or negated) is its claim's own state, with a value of
# the right domain (an id of the right family), at least one source, every check and source geometry ok, no qualifier
# but approximate, no reason, and an appraisal that supports with no qualifier (DECISIONS D186: a supports verdict
# naming qualifiers is read as qualified), attached yes, with at least one evidence unit (3.2.3's "evidence attached",
# 3.2.5), its control (if any) contradicted (3.2.3); and, against the row (_v2_established_bound), every unit its
# sources and its evidence cite is in the row's units table (3.1 I1) and an id value names an object of its family in
# the row (3.1 I4). Every other result carries a reason. A pair control asks a value of its attribute's domain: a
# Landmark for target.places, a lesion id for target.lesion (3.2.3). Across records (Mismatch): each appraisal names a
# claim stored for THAT fact - role claim, its subject, attribute and value, the same content key and the same verdict
# - and a control stored for its subject with the same verdict, whose attribute is the fact's own or the partner
# 3.2.3 writes its control in (CONTROL_ATTRIBUTES; a control of another attribute is UnknownShape); no claim is read by
# two facts; the report's bindings, label, claims_sha256 and kept-unlisted count agree with the row.
#
# textfree_v2 gives the engine a read row's events with no text (DECISIONS D188): every source's ``words`` record is
# ``at`` {start, end} (null when words is null: the source cites its whole units), an anchor's kind_words and
# status_words keep their start and end, and no ``text`` remains; engine/facts.py builds from it alone (5.7 measure 4).

BINDINGS_V2 = ('encounter_id', 'revision_id', 'provider_run_id', 'appraisal_run_id')
COLUMNS_V2 = ('interpretation_version', 'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256',
              'state')
CONTENT_V2 = ('events', 'encounter_facts', 'open_questions', 'verification')
HASHED_V2 = BINDINGS_V2 + COLUMNS_V2 + CONTENT_V2
FIELDS_V2 = HASHED_V2 + ('sha256',)

# Every v2 version pair this release reads AS STORED (FINAL-V2 6.2 [R:MO-5]), as the adapter keeps READ_VERSIONS: a
# later INVENTORY_VERSION is added beside the earlier pair with its own shapes and label (_V2_SHAPES, _V2_LABELS) and
# never replaces it, so no stored v2 inventory becomes unreadable when a version moves. A pair is
# (EventInventory.interpretation_version, inventory_version). Rows are written at the last pair only.
READ_VERSIONS = ((INTERPRETATION_PAIR, INVENTORY_VERSION_V2),)
LABEL_V2 = f"{INTERPRETATION_PAIR}+{INVENTORY_VERSION_V2.removeprefix('gemini-')}"  # names the pair in the report

# A refused row records a refused PASS-1 answer only (FINAL-V2 6.3; 3.1 S1, "as v1"): its stage is one of pass 1's
# refusal stages and its one problem CPT Studio's sentence, opening with the refusal prefix and ending with a full stop.
# Both are contract/extract_read's own STAGES and REFUSED (FINAL-V2 5.7: "Refusal, iso_date and the enumerations are
# copied there"), read on first use (_v2) and never copied here; tests/v2/test_extract_read.py proves them v1's.

# The attribute 3.2.3 writes a fact's contrary control in, where it is not the fact's own: a control stored for a fact
# names a claim of the fact's attribute or of its partner here (_v2_verdicts_bound), so no fact is read against the
# control of another of its subject's facts. Each pair is a row of 3.2.3 (claims.CONTROLS' as_attribute, pinned equal by
# tests/v2/test_store.py): act.cause -> "caused by act {A}"; statement.excepts -> the covers form; statement.targets
# (segment) -> the place form, (single, listed) -> the lesion form; session.reached_anatomy -> the reached form;
# lesion.distinct_from -> the same-lesion form. Status's controls (performed against negated, attempted or planned
# against performed) are status claims, so status has no partner.
CONTROL_ATTRIBUTES = MappingProxyType({
    'cause': 'cause_event', 'scope.excepts': 'scope.covers', 'scope.segment': 'target.places',
    'scope.targets': 'target.lesion', 'reached_anatomy': 'reached', 'distinct_from': 'same_as',
})

# What a stored claim is (FINAL-V2 3.2.2-3.2.3): a fact's own claim; its contrary control; a pair control (asked of an
# act or a statement about a place or a lesion of another); the stations completeness claim; its control. The role is
# stored only: a request never marks a control (2.4). The claim list's sha256 is over CLAIM_IDENTITY, never a verdict.
CLAIM_ROLES = ('claim', 'control', 'pair_control', 'completeness', 'completeness_control')
CLAIM_IDENTITY = ('id', 'role', 'template', 'subject', 'attribute', 'value', 'units', 'content')
ID_LETTERS_V2 = ('E', 'X', 'N', 'L', 'Y', 'P', 'S')  # engine/types.IdFamily's letters: events, sessions .. units
CLAIM_LETTER = 'K'

_V2_CURRENT = READ_VERSIONS[-1]
_V2_OBJECT_LETTERS = ID_LETTERS_V2[:-1]  # every object family but the units
# Each object family's letter and the events list that holds its objects (1.7), for the ids an established value names.
_V2_FAMILIES = (('E', 'events'), ('X', 'sessions'), ('N', 'sections'), ('L', 'lesions'), ('Y', 'anatomy'),
                ('P', 'people'))
_V2_CHECK_NAMES = ('integrity', 'geometry', 'literal', 'consistency')
_V2_KEY_FIRST = frozenset(string.ascii_letters + '_')
_V2_KEY_CHARACTERS = frozenset(string.ascii_letters + string.digits + '_')
_V2_NAME_CHARACTERS = frozenset(string.ascii_letters + string.digits + '_.:-')
_V2_HEX = frozenset('0123456789abcdef')

# contract/ is imported on FIRST USE (_v2), never when this module is imported: importing store loads exactly the
# modules v1's store did, which tests/test_interpretation_prompt.py - a retired module's test, which no step edits
# (FINAL-V2 8.0) - pins. _v2_build binds these three names, and every shape below that reads contract/types'
# enumerations; each v2 entry point calls _v2() first.
ct: Any = None  # contract/types
sha256_of: Any = None  # contract/jsonschema.sha256_of
xr: Any = None  # contract/extract_read: pass 1's refusal STAGES and REFUSED, iso_date and partial_date (FINAL-V2 5.7)
_V2_BUILT = False
_V2_LOCK = threading.Lock()
_V2_DOMAINS: dict = {}  # (object family letter, '' for the encounter; attribute) -> the domain of its facts

# The names _v2_build binds on first use: None until then, and every v2 entry point calls _v2() before reading one.
_A: Any = None
_V2_ESTABLISHED: Any = None
_V2_PAIR_ATTRIBUTES: Any = None
_V2_VALUE_ENUMERATIONS: Any = None
_V2_ANY_VALUE: Any = None
_V2_CHECK: Any = None
_V2_SOURCE: Any = None
_V2_CONTROL: Any = None
_V2_APPRAISAL: Any = None
_V2_FACT_SHAPE: Any = None
_V2_ENCOUNTER: Any = None
_V2_PERSON: Any = None
_V2_SECTION: Any = None
_V2_SESSION: Any = None
_V2_ANATOMY: Any = None
_V2_LESION: Any = None
_V2_EVENT: Any = None
_V2_DOUBT: Any = None
_V2_UNLISTED: Any = None
_V2_VERDICT: Any = None
_V2_CLAIM: Any = None
_V2_EVENTS: Any = None
_V2_REPORT_READ: Any = None
_V2_REPORT_REFUSED: Any = None
_V2_SHAPES: Any = None
_V2_LABELS: Any = None


def _v2() -> None:
    """Import contract/ and build the v2 shapes, once (thread-safe; a second call does nothing)."""
    global _V2_BUILT
    if not _V2_BUILT:
        with _V2_LOCK:
            if not _V2_BUILT:
                _v2_build()
                _V2_BUILT = True


def _v2_values(*enumerations) -> frozenset:
    return frozenset(member.value for enumeration in enumerations for member in enumeration)


def _v2_id(value: object, letters: tuple) -> bool:
    """Whether ``value`` is a canonical id of one of ``letters``: the letter, then its number in canonical decimal
    digits, as engine/types.Id.parse reads one ('E3', 'N0'; never 'E03', 'E+3' or 'E 3'), at most 9 digits."""
    if not isinstance(value, str) or not 2 <= len(value) <= 10 or value[0] not in letters:
        return False
    digits = value[1:]
    return digits.isascii() and digits.isdigit() and (digits == '0' or digits[0] != '0')


def _v2_date_precision(value: object) -> str:
    """The precision an ISO date is written at, read by pass 1's own date shapes (contract/extract_read, FINAL-V2 3.1
    S1 and 5.7): 'day' for a real YYYY-MM-DD date (iso_date), 'month' or 'year' for a real YYYY-MM or YYYY one
    (partial_date), in ASCII digits, the year at least 1; '' for anything else, a value that is not a string
    included."""
    if not isinstance(value, str):
        return ''
    if xr.iso_date(value):
        return ct.Precision.DAY.value
    if xr.partial_date(value):
        return (ct.Precision.MONTH if len(value) == 7 else ct.Precision.YEAR).value
    return ''


def _v2_value(value: object) -> bool:
    """A value a fact, an option, a doubt's reading or a claim may hold - '', an enumeration value, an object's id or an
    ISO date - and never free text (P9)."""
    return (value == '' or (isinstance(value, str) and value in _V2_ANY_VALUE) or _v2_id(value, _V2_OBJECT_LETTERS)
            or bool(_v2_date_precision(value)))


def _v2_named(key: object) -> str:
    """A stored object key for a problem: as written when it is a short name, else by its length only (a stored key or
    value can be a slice of the revision text, and a problem never repeats one)."""
    if (isinstance(key, str) and 1 <= len(key) <= 40 and key[0] in _V2_KEY_FIRST
            and all(character in _V2_KEY_CHARACTERS for character in key)):
        return key
    return f'a key of {len(key):,} characters' if isinstance(key, str) else 'a key that is not a string'


def _v2_same(first: object, second: object) -> bool:
    """Equal as JSON data, the types included ({} is not [], false is not 0, 1 is not 1.0)."""
    try:
        return sha256_of([first]) == sha256_of([second])
    except (TypeError, ValueError):
        return False


def _v2_json(value: object) -> bool:
    """Any JSON data: objects with string keys, lists, strings, integers, finite numbers, true, false, null."""
    pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if not all(isinstance(key, str) for key in node):
                return False
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
        elif not (node is None or isinstance(node, (str, bool, int))
                  or (isinstance(node, float) and math.isfinite(node))):
            return False
    return True


# --- the v2 shapes ----------------------------------------------------------------------------------------------------
# problem(value, path) gives '' or the first problem, naming the place and never the stored value. facts(value, path,
# subject) yields (path, subject, spec, record) for every settled fact - and stations completeness record - inside a
# value problem() found well-shaped, the subject being the id of the nearest object that holds it ('' for the
# encounter's). describe() is the shape as JSON data, which shape_signature_v2 hashes.

class _V2Spec:
    def problem(self, value: object, path: str) -> str:
        raise NotImplementedError

    def facts(self, value: object, path: str, subject: str) -> Iterator[tuple]:
        return iter(())

    def describe(self) -> object:
        raise NotImplementedError


class _V2Test(_V2Spec):
    def __init__(self, test, what: str) -> None:
        self.test, self.what = test, what

    def problem(self, value, path):
        return '' if self.test(value) else f'{path} is not {self.what}'

    def describe(self):
        return ['test', self.what]


class _V2Closed(_V2Spec):
    """A value of a closed list: an enumeration's values, or one of CPT Studio's own lists of names."""

    def __init__(self, values) -> None:
        self.values = frozenset(values)

    def problem(self, value, path):
        return '' if isinstance(value, str) and value in self.values else f'{path} is not a value this release knows'

    def describe(self):
        return ['closed', sorted(self.values)]


class _V2Const(_V2Spec):
    """Exactly this JSON value, its type included: {}, [], true or false."""

    def __init__(self, value: object) -> None:
        self.value = value
        self.what = str(value).lower() if isinstance(value, bool) else 'empty'

    def problem(self, value, path):
        return '' if _v2_same(value, self.value) else f'{path} is not {self.what}'

    def describe(self):
        return ['const', self.value]


class _V2Nullable(_V2Spec):
    def __init__(self, inner: _V2Spec) -> None:
        self.inner = inner

    def problem(self, value, path):
        return '' if value is None else self.inner.problem(value, path)

    def facts(self, value, path, subject):
        return iter(()) if value is None else self.inner.facts(value, path, subject)

    def describe(self):
        return ['nullable', self.inner.describe()]


class _V2List(_V2Spec):
    def __init__(self, item: _V2Spec) -> None:
        self.item = item

    def problem(self, value, path):
        if not isinstance(value, list):
            return f'{path} is not a list'
        for index, item in enumerate(value):
            problem = self.item.problem(item, f'{path}[{index}]')
            if problem:
                return problem
        return ''

    def facts(self, value, path, subject):
        for index, item in enumerate(value):
            yield from self.item.facts(item, f'{path}[{index}]', subject)

    def describe(self):
        return ['list', self.item.describe()]


class _V2Map(_V2Spec):
    """An object of string keys, each value of one spec; its keys closed to ``keys`` when given."""

    def __init__(self, value: _V2Spec, keys=None) -> None:
        self.value, self.keys = value, None if keys is None else frozenset(keys)

    def problem(self, value, path):
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            return f'{path} is not an object'
        for key, item in value.items():
            if self.keys is not None and key not in self.keys:
                return f'{path} has a key this release does not know ({_v2_named(key)})'
            problem = self.value.problem(item, f'{path}[{_v2_named(key)}]')
            if problem:
                return problem
        return ''

    def describe(self):
        return ['map', self.value.describe(), None if self.keys is None else sorted(self.keys)]


class _V2Obj(_V2Spec):
    """An object with exactly its fields; ``check(value, path)`` runs once they are well-shaped. When it has an ``id``,
    that id is the subject of the facts inside it."""

    def __init__(self, fields: dict, check=None) -> None:
        self.fields, self.check = fields, check

    def problem(self, value, path):
        if not isinstance(value, dict):
            return f'{path} is not an object'
        for key in self.fields:
            if key not in value:
                return f'{path} lacks the field {key}'
        for key in value:
            if key not in self.fields:
                return f'{path} has a field this release does not know ({_v2_named(key)})'
        for key, spec in self.fields.items():
            problem = spec.problem(value[key], f'{path}.{key}')
            if problem:
                return problem
        return self.check(value, path) if self.check is not None else ''

    def facts(self, value, path, subject):
        subject = value['id'] if 'id' in self.fields else subject
        for key, spec in self.fields.items():
            yield from spec.facts(value[key], f'{path}.{key}', subject)

    def describe(self):
        return ['object', {key: spec.describe() for key, spec in self.fields.items()},
                None if self.check is None else self.check.__name__]


class _V2Json(_V2Spec):
    def __init__(self, object_only: bool = False) -> None:
        self.object_only = object_only

    def problem(self, value, path):
        if self.object_only and not isinstance(value, dict):
            return f'{path} is not an object'
        return '' if _v2_json(value) else f'{path} is not JSON data'

    def describe(self):
        return ['json', self.object_only]


_V2_STR = _V2Test(lambda value: isinstance(value, str), 'a string')
_V2_BOOL = _V2Test(lambda value: type(value) is bool, 'true or false')
_V2_INT = _V2Test(lambda value: type(value) is int and value >= 0, 'an integer of at least 0')
_V2_SHA = _V2Test(lambda value: isinstance(value, str) and len(value) == 64 and all(c in _V2_HEX for c in value),
                  'a sha256')
_V2_ISO = _V2Test(lambda value: bool(_v2_date_precision(value)), 'an ISO date at its precision')
_V2_UNIT_ID = _V2Test(lambda value: _v2_id(value, ('S',)), 'a unit id')
_V2_CLAIM_ID = _V2Test(lambda value: _v2_id(value, (CLAIM_LETTER,)), 'a claim id')
_V2_ANY_ID = _V2Test(lambda value: _v2_id(value, _V2_OBJECT_LETTERS), 'an id')
_V2_SUBJECT = _V2Test(lambda value: value == '' or _v2_id(value, _V2_OBJECT_LETTERS), "an id or ''")
_V2_VALUE = _V2Test(_v2_value, 'a value')
_V2_NAME = _V2Test(lambda value: isinstance(value, str) and 1 <= len(value) <= 64 and value[0] in _V2_KEY_FIRST
                   and all(character in _V2_NAME_CHARACTERS for character in value), 'a name')
_V2_UNITS = _V2List(_V2_UNIT_ID)


def _v2_object_id(letter: str) -> _V2Test:
    return _V2Test(lambda value: _v2_id(value, (letter,)), f'an id of {letter}')


class _V2Located(_V2Spec):
    """Words located in the revision (FINAL-V2 1.7 sources[].words; contract/types.LocatedWords): {start, end, text},
    the offsets its own text's - start at least 0, end exactly start plus the text's length, at least one character.
    Whether the text IS the revision's slice needs the text: row_v2 checks it, and the row's sha256 and text_sha256
    keep that check (P9)."""

    def __init__(self) -> None:
        self.shape = _V2Obj({'start': _V2_INT, 'end': _V2_INT, 'text': _V2_STR})

    def problem(self, value, path):
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        if not value['text'] or value['end'] - value['start'] != len(value['text']):
            return f'{path} has offsets that are not those of its own words'
        return ''

    def describe(self):
        return ['located', self.shape.describe()]


class _V2Domain:
    """What a fact's value may be (FINAL-V2 1.3: "an enumeration value, an id or an ISO date"): a value of ``values``;
    an id, of ``letter``'s family once the fact is established - before that, of any object family, because an id that
    names no object of the answer is an item-level finding (1.8) that settles the fact unresolved and keeps its value;
    or an ISO date at its precision."""

    def __init__(self, values=None, letter: str = '', date: bool = False) -> None:
        self.values, self.letter, self.date = None if values is None else frozenset(values), letter, date

    def holds(self, value: str, established: bool) -> bool:
        if self.values is not None:
            return value in self.values
        if self.letter:
            return _v2_id(value, (self.letter,) if established else _V2_OBJECT_LETTERS)
        return bool(_v2_date_precision(value))

    def describe(self):
        if self.values is not None:
            return ['values', sorted(self.values)]
        return ['id', self.letter] if self.letter else ['date']


_V2_DATE = _V2Domain(date=True)


def _v2_literal_check(value, path):
    """A stored date literal's value is written at its precision (FINAL-V2 1.7 checks.literals; 3.1 L1)."""
    return '' if _v2_date_precision(value['value']) == value['precision'] else f'{path} is not written at its precision'


def _v2_appraisal_check(value, path):
    """Pass 2 gave a verdict and its attachment together, or neither; with no verdict, no qualifier and no evidence."""
    if (value['verdict'] is None) is not (value['attached'] is None):
        return f'{path} has a verdict without its attachment, or an attachment without a verdict'
    if value['verdict'] is None and (value['qualifiers'] or value['evidence']):
        return f'{path} has qualifiers or evidence but no verdict'
    return ''


def _v2_appraisal_establishes(appraisal, controlled: Optional[bool] = None) -> bool:
    """FINAL-V2 3.2.3's established pair: the claim supported - with no qualifier, since a supports verdict that names
    one is read as qualified (DECISIONS D186) - attached yes, with at least one evidence unit (the coherence table's
    "evidence attached", 3.2.5; with none it is appraisal_detached), and its control (when there is one, or when
    ``controlled`` demands one) contradicted. Whether each evidence unit is one of the row's units is checked by
    _v2_established_bound."""
    control = appraisal['control']
    return (appraisal['verdict'] == ct.VerdictValue.SUPPORTS.value and not appraisal['qualifiers']
            and appraisal['attached'] == ct.Attached.YES.value and len(appraisal['evidence']) > 0
            and (control is not None if controlled else True)
            and (control is None or control['verdict'] == ct.VerdictValue.CONTRADICTS.value))


class _V2Fact(_V2Spec):
    """One settled fact of ``attribute`` (FINAL-V2 1.7; contract/types.SettledFact), its value in ``domain``, held to
    the module's fact rules (the comment at the head of design v2)."""

    def __init__(self, attribute, domain: _V2Domain) -> None:
        self.attribute, self.domain = attribute, domain

    def problem(self, value, path):
        problem = _V2_FACT_SHAPE.problem(value, path)
        if problem:
            return problem
        claim, checks, appraisal = value['claim'], value['checks'], value['appraisal']
        state, stated, result = claim['state'], claim['value'], value['result']
        if stated and not self.domain.holds(stated, False):
            return f'{path}.claim.value is not a value this release knows'
        for index, option in enumerate(claim['options']):
            if option['value'] and not self.domain.holds(option['value'], False):
                return f'{path}.claim.options[{index}].value is not a value this release knows'
        qualified = any(q != ct.Qualifier.APPROXIMATE.value for q in claim['qualifiers'])
        if checks['qualified'] is not qualified:
            return f'{path}.checks.qualified does not say what the claim\'s qualifiers say'
        if appraisal is not None and state not in _V2_ESTABLISHED:
            return f'{path} has an appraisal, which only a supported or negated claim gets'
        if state is None:
            if stated or claim['options'] or claim['qualifiers'] or value['sources']:
                return f'{path} is silent and still holds a value, an option, a qualifier or a source'
            if result not in (ct.Result.UNKNOWN.value, ct.Result.CONTRADICTED.value):
                return f'{path} is silent and settled {result}'
        if result in _V2_ESTABLISHED:
            if not (state == result and stated and self.domain.holds(stated, True) and not claim['options']
                    and value['sources'] and not value['reasons'] and not checks['qualified']
                    and all(checks[name] == ct.CheckStatus.OK.value for name in _V2_CHECK_NAMES)
                    and all(source['geometry'] == ct.CheckStatus.OK.value for source in value['sources'])
                    and appraisal is not None and _v2_appraisal_establishes(appraisal)):
                return f'{path} is {result} without what establishing it needs (FINAL-V2 3.3 row 8)'
        elif not value['reasons']:
            return f'{path} is {result} with no reason (FINAL-V2 3.3)'
        return ''

    def facts(self, value, path, subject):
        yield path, subject, self, value

    def describe(self):
        return ['fact', self.attribute.value, self.domain.describe()]


class _V2Completeness(_V2Spec):
    """The stations completeness claim's settled result (FINAL-V2 3.2.2 [R:SC-B]; engine/types.FactSet.completeness),
    for an upper EUS session whose stations list is empty: its appraisal (its control demanded, 3.2.3), its result -
    supported, only as an established pair, or unresolved with a reason - and its reasons. CPT Studio's claim, not a
    fact of pass 1, so it has no claim record."""

    def __init__(self) -> None:
        self.shape = _V2Obj({'appraisal': _V2_APPRAISAL,
                             'result': _V2Closed((ct.Result.SUPPORTED.value, ct.Result.UNRESOLVED.value)),
                             'reasons': _V2List(_V2Closed(_v2_values(ct.Reason)))})

    def problem(self, value, path):
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        if value['result'] == ct.Result.SUPPORTED.value:
            if value['reasons'] or not _v2_appraisal_establishes(value['appraisal'], controlled=True):
                return f'{path} is supported without what establishing it needs (FINAL-V2 3.2.3)'
        elif not value['reasons']:
            return f'{path} is unresolved with no reason (FINAL-V2 3.3)'
        return ''

    def facts(self, value, path, subject):
        yield path, subject, self, value

    def describe(self):
        return ['completeness', self.shape.describe()]


def _v2_fact(letter: str, attribute, domain: _V2Domain, many: bool = False) -> _V2Spec:
    _V2_DOMAINS[(letter, attribute.value)] = domain
    spec = _V2Fact(attribute, domain)
    return _V2List(spec) if many else spec


def _v2_enum(enumeration) -> _V2Domain:
    return _V2Domain(values=_v2_values(enumeration))


def _v2_ids(letter: str) -> _V2Domain:
    return _V2Domain(letter=letter)


def _v2_claim_check(value, path):
    """A stored claim is about an object and an attribute it may be about: a fact's own claim names an attribute its
    subject's family has (_V2_DOMAINS), with a value of that attribute's domain; a pair control asks an act or a
    statement about a place or a lesion (3.2.3 [R:SC-B]) - "This act was done in the {place}." or "... to lesion
    {L}." - so its value is a place (a Landmark, target.places' domain) or a lesion's id (a canonical L id), never ''
    (the FactSet builder refuses a row whose pair control asks anything else, so the store does too: 3.1 B1); the
    completeness claim and its control are about a session's stations (3.2.2)."""
    role, subject, attribute = value['role'], value['subject'], value['attribute']
    if role == 'claim':
        domain = _V2_DOMAINS.get((subject[:1], attribute))
        if domain is None:
            return f'{path} claims an attribute its subject does not have'
        if value['value'] and not domain.holds(value['value'], False):
            return f'{path}.value is not a value of its attribute'
    elif role == 'pair_control':
        if not subject.startswith('E') or attribute not in _V2_PAIR_ATTRIBUTES:
            return f'{path} is a pair control that does not ask an act about a place or a lesion'
        if not _V2_DOMAINS[('E', attribute)].holds(value['value'], True):
            return f'{path}.value is not a {"lesion id" if attribute == _A.TARGET_LESION.value else "place"}'
    elif role in ('completeness', 'completeness_control'):
        if not subject.startswith('X') or attribute != _A.STATIONS.value:
            return f'{path} is a completeness claim that is not about a session\'s stations'
    return ''


class _V2Claims(_V2Spec):
    """Every claim sent to pass 2, in their seeded order: K1, K2, ... (FINAL-V2 3.2.2-3.2.4)."""

    def __init__(self) -> None:
        self.shape = _V2List(_V2_CLAIM)

    def problem(self, value, path):
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        for index, claim in enumerate(value):
            if claim['id'] != f'{CLAIM_LETTER}{index + 1}':
                return (f'{path}[{index}] is not claim {CLAIM_LETTER}{index + 1}: claims are stored in their seeded '
                        'order')
        return ''

    def describe(self):
        return ['claims', self.shape.describe()]


class _V2Units(_V2Spec):
    """The segmentation table (FINAL-V2 1.2 rule 5, 1.7): S1, S2, ... in document order, each at least one character,
    none overlapping the one before, their lines, paragraphs and pages never going back. Offsets only, no text; row_v2
    proves each lies within the revision text."""

    def __init__(self) -> None:
        self.shape = _V2List(_V2Obj({'id': _V2_UNIT_ID, 'start': _V2_INT, 'end': _V2_INT, 'line': _V2_INT,
                                     'paragraph': _V2_INT, 'page': _V2_INT, 'forced': _V2_BOOL}))

    def problem(self, value, path):
        problem = self.shape.problem(value, path)
        if problem:
            return problem
        previous = None
        for index, unit in enumerate(value):
            where = f'{path}[{index}]'
            if unit['id'] != f'S{index + 1}':
                return f'{where} is not unit S{index + 1}: units are numbered in document order'
            if unit['end'] <= unit['start']:
                return f'{where} is empty or runs backward'
            if previous is not None and (unit['start'] < previous['end'] or any(
                    unit[name] < previous[name] for name in ('line', 'paragraph', 'page'))):
                return f'{where} does not follow the unit before it'
            previous = unit
        return ''

    def describe(self):
        return ['units', self.shape.describe()]


def _v2_build() -> None:
    """Import contract/ and build every shape that reads its enumerations (called once, by _v2). The shapes are the
    comment at the head of design v2, field for field."""
    global ct, sha256_of, xr, _A, _V2_ESTABLISHED, _V2_PAIR_ATTRIBUTES, _V2_VALUE_ENUMERATIONS, _V2_ANY_VALUE, _V2_CHECK
    global _V2_SOURCE, _V2_CONTROL, _V2_APPRAISAL, _V2_FACT_SHAPE, _V2_ENCOUNTER, _V2_PERSON, _V2_SECTION, _V2_SESSION
    global _V2_ANATOMY, _V2_LESION, _V2_EVENT, _V2_DOUBT, _V2_UNLISTED, _V2_VERDICT, _V2_CLAIM, _V2_EVENTS
    global _V2_REPORT_READ, _V2_REPORT_REFUSED, _V2_SHAPES, _V2_LABELS
    from studio.interpretation.contract import extract_read as xr
    from studio.interpretation.contract import types as ct
    from studio.interpretation.contract.jsonschema import sha256_of

    _A = ct.Attribute
    _V2_ESTABLISHED = (ct.Result.SUPPORTED.value, ct.Result.NEGATED.value)
    _V2_PAIR_ATTRIBUTES = (_A.TARGET_PLACES.value, _A.TARGET_LESION.value)  # what a pair control asks (3.2.3)
    # Every value a fact, an option, a doubt's reading or a claim may hold that is an enumeration value (1.4).
    _V2_VALUE_ENUMERATIONS = (
        ct.Kind, ct.DateRole, ct.Multiplicity, ct.Device, ct.Landmark, ct.Extent, ct.Status, ct.DateRelation,
        ct.EncounterRelation, ct.Performer, ct.Owner, ct.SectionRole, ct.PersonRole, ct.OtherClass, ct.SessionKind,
        ct.Tract, ct.Approach, ct.Completion, ct.Station, ct.Structure, ct.Duct, ct.Route, ct.Purpose, ct.Cause,
        ct.PartRelation, ct.Material, ct.AccessOutcome, ct.Breadth, ct.AnatomyType, ct.AnastomosisSubtype,
        ct.RestatementRole, ct.EmBasis, ct.Separate)
    _V2_ANY_VALUE = _v2_values(*_V2_VALUE_ENUMERATIONS)
    _V2_CHECK = _V2Closed(_v2_values(ct.CheckStatus))

    _V2_SOURCE = _V2Obj({'units': _V2_UNITS, 'link': _V2Closed(_v2_values(ct.Link)),
                         'words': _V2Nullable(_V2Located()), 'geometry': _V2_CHECK})
    _V2_CONTROL = _V2Obj({'claim': _V2_CLAIM_ID, 'verdict': _V2Nullable(_V2Closed(_v2_values(ct.VerdictValue)))})
    _V2_APPRAISAL = _V2Obj({
        'claim': _V2_CLAIM_ID, 'content': _V2_SHA,
        'verdict': _V2Nullable(_V2Closed(_v2_values(ct.VerdictValue))),
        'attached': _V2Nullable(_V2Closed(_v2_values(ct.Attached))),
        'qualifiers': _V2List(_V2Closed(_v2_values(ct.Qualifier2))), 'evidence': _V2_UNITS,
        'control': _V2Nullable(_V2_CONTROL),
    }, _v2_appraisal_check)
    _V2_FACT_SHAPE = _V2Obj({
        'claim': _V2Obj({'state': _V2Nullable(_V2Closed(_v2_values(ct.FactState))), 'value': _V2_STR,
                         'qualifiers': _V2List(_V2Closed(_v2_values(ct.Qualifier))),
                         'options': _V2List(_V2Obj({'value': _V2_STR, 'sources': _V2List(_V2_SOURCE)})),
                         'inherited_from': _V2Nullable(_v2_object_id('N'))}),
        'sources': _V2List(_V2_SOURCE),
        'checks': _V2Obj({'integrity': _V2_CHECK, 'geometry': _V2_CHECK, 'literal': _V2_CHECK,
                          'literals': _V2List(_V2Obj({'value': _V2_STR,
                                                      'precision': _V2Closed(_v2_values(ct.Precision))},
                                                     _v2_literal_check)),
                          'consistency': _V2_CHECK, 'qualified': _V2_BOOL}),
        'appraisal': _V2Nullable(_V2_APPRAISAL),
        'result': _V2Closed(_v2_values(ct.Result)),
        'reasons': _V2List(_V2Closed(_v2_values(ct.Reason))),
    })

    _V2_ENCOUNTER = _V2Obj({
        'date_of_service': _v2_fact('', _A.DATE_OF_SERVICE, _V2_DATE),
        'other_dates': _V2List(_V2Obj({'value': _V2_ISO,
                                       'role': _v2_fact('', _A.OTHER_DATES_ROLE, _v2_enum(ct.DateRole))})),
        'documenting_clinician': _v2_fact('', _A.DOCUMENTING_CLINICIAN, _v2_ids('P')),
    })
    _V2_PERSON = _V2Obj({'id': _v2_object_id('P'), 'name': _V2_SOURCE,
                         'role': _v2_fact('P', _A.ROLE, _v2_enum(ct.PersonRole))})
    _V2_SECTION = _V2Obj({
        'id': _v2_object_id('N'), 'start': _V2_SOURCE, 'end': _V2List(_V2_SOURCE),
        'owner': _v2_fact('N', _A.OWNER, _v2_enum(ct.Owner)),
        'role': _v2_fact('N', _A.ROLE, _v2_enum(ct.SectionRole)),
        'occasion': _v2_fact('N', _A.OCCASION, _v2_enum(ct.DateRelation)),
        'performer': _v2_fact('N', _A.PERFORMER, _v2_enum(ct.Performer)),
        'performer_person': _v2_fact('N', _A.PERFORMER_PERSON, _v2_ids('P')),
    })
    _V2_SESSION = _V2Obj({
        'id': _v2_object_id('X'),
        'examination': _v2_fact('X', _A.EXAMINATION, _v2_ids('E')),
        'kind': _v2_fact('X', _A.KIND, _v2_enum(ct.SessionKind)),
        'encounter': _v2_fact('X', _A.ENCOUNTER, _v2_enum(ct.EncounterRelation)),
        'tract': _v2_fact('X', _A.TRACT, _v2_enum(ct.Tract)),
        'approach': _v2_fact('X', _A.APPROACH, _v2_enum(ct.Approach)),
        'through': _v2_fact('X', _A.THROUGH, _v2_ids('Y')),
        'reached': _v2_fact('X', _A.REACHED, _v2_enum(ct.Extent), many=True),
        'device_reached': _v2_fact('X', _A.DEVICE_REACHED, _v2_enum(ct.Extent), many=True),
        'reached_anatomy': _v2_fact('X', _A.REACHED_ANATOMY, _v2_ids('Y')),
        'completion': _v2_fact('X', _A.COMPLETION, _v2_enum(ct.Completion)),
        'stations': _v2_fact('X', _A.STATIONS, _v2_enum(ct.Station), many=True),
        'part_of_session': _v2_fact('X', _A.PART_OF_SESSION, _v2_ids('X')),
        'completeness': _V2Nullable(_V2Completeness()),
    })
    _V2_ANATOMY = _V2Obj({
        'id': _v2_object_id('Y'),
        'type': _v2_fact('Y', _A.TYPE, _v2_enum(ct.AnatomyType)),
        'organ': _v2_fact('Y', _A.ORGAN, _v2_enum(ct.Landmark)),
        'subtype': _v2_fact('Y', _A.SUBTYPE, _v2_enum(ct.AnastomosisSubtype)),
        'joins': _v2_fact('Y', _A.JOINS, _v2_enum(ct.Landmark), many=True),
    })
    _V2_LESION = _V2Obj({
        'id': _v2_object_id('L'), 'description': _V2_SOURCE,
        'multiplicity': _v2_fact('L', _A.MULTIPLICITY, _v2_enum(ct.Multiplicity)),
        'places': _v2_fact('L', _A.PLACES, _v2_enum(ct.Landmark), many=True),
        'distinct_from': _v2_fact('L', _A.DISTINCT_FROM, _v2_ids('L'), many=True),
        'same_as': _v2_fact('L', _A.SAME_AS, _v2_ids('L'), many=True),
    })
    _V2_EVENT = _V2Obj({
        'id': _v2_object_id('E'),
        'anchor': _V2Obj({'units': _V2_UNITS, 'kind_words': _V2Nullable(_V2Located()),
                          'status_words': _V2Nullable(_V2Located())}),
        'restatements': _V2List(_V2Obj({'units': _V2_UNITS, 'role': _v2_fact('E', _A.RESTATEMENTS_ROLE,
                                                                             _v2_enum(ct.RestatementRole))})),
        'kind': _v2_fact('E', _A.KIND, _v2_enum(ct.Kind)),
        'other_class': _v2_fact('E', _A.OTHER_CLASS, _v2_enum(ct.OtherClass)),
        'status': _v2_fact('E', _A.STATUS, _v2_enum(ct.Status)),
        'session': _v2_fact('E', _A.SESSION, _v2_ids('X')),
        'date_relation': _v2_fact('E', _A.DATE_RELATION, _v2_enum(ct.DateRelation)),
        'date': _v2_fact('E', _A.DATE, _V2_DATE),
        'performer': _v2_fact('E', _A.PERFORMER, _v2_enum(ct.Performer)),
        'performer_person': _v2_fact('E', _A.PERFORMER_PERSON, _v2_ids('P')),
        'entry': _v2_fact('E', _A.ENTRY, _v2_enum(ct.Owner)),
        'target': _V2Obj({
            'lesion': _v2_fact('E', _A.TARGET_LESION, _v2_ids('L')),
            'structure': _v2_fact('E', _A.TARGET_STRUCTURE, _v2_enum(ct.Structure)),
            'places': _v2_fact('E', _A.TARGET_PLACES, _v2_enum(ct.Landmark), many=True),
            'anatomy': _v2_fact('E', _A.TARGET_ANATOMY, _v2_ids('Y')),
            'duct': _v2_fact('E', _A.TARGET_DUCT, _v2_enum(ct.Duct)),
        }),
        'technique': _V2Obj({'device': _v2_fact('E', _A.TECHNIQUE_DEVICE, _v2_enum(ct.Device)),
                             'route': _v2_fact('E', _A.TECHNIQUE_ROUTE, _v2_enum(ct.Route))}),
        'purpose': _v2_fact('E', _A.PURPOSE, _v2_enum(ct.Purpose)),
        'cause': _v2_fact('E', _A.CAUSE, _v2_enum(ct.Cause)),
        'cause_event': _v2_fact('E', _A.CAUSE_EVENT, _v2_ids('E')),
        'part_of': _v2_fact('E', _A.PART_OF, _v2_ids('E')),
        'part_relation': _v2_fact('E', _A.PART_RELATION, _v2_enum(ct.PartRelation)),
        'yield': _v2_fact('E', _A.YIELD, _v2_enum(ct.Material)),
        'access_outcome': _v2_fact('E', _A.ACCESS_OUTCOME, _v2_enum(ct.AccessOutcome)),
        'scope': _V2Obj({
            'breadth': _v2_fact('E', _A.SCOPE_BREADTH, _v2_enum(ct.Breadth)),
            'targets': _v2_fact('E', _A.SCOPE_TARGETS, _v2_ids('L'), many=True),
            'segment': _v2_fact('E', _A.SCOPE_SEGMENT, _v2_enum(ct.Landmark), many=True),
            'covers': _v2_fact('E', _A.SCOPE_COVERS, _v2_ids('E'), many=True),
            'excepts': _v2_fact('E', _A.SCOPE_EXCEPTS, _v2_ids('E'), many=True),
        }),
        'visit': _V2Obj({'basis': _v2_fact('E', _A.VISIT_BASIS, _v2_enum(ct.EmBasis)),
                         'separately_identifiable': _v2_fact('E', _A.VISIT_SEPARATELY_IDENTIFIABLE,
                                                             _v2_enum(ct.Separate))}),
    })
    _V2_DOUBT = _V2Obj({'about': _V2Closed(_v2_values(ct.DoubtAbout)), 'objects': _V2List(_V2_ANY_ID),
                        'units': _V2_UNITS, 'basis': _V2Closed(_v2_values(ct.DoubtBasis)),
                        'readings': _V2List(_V2_VALUE)})
    _V2_UNLISTED = _V2Obj({'units': _V2_UNITS, 'what': _V2Closed(_v2_values(ct.UnlistedWhat)),
                           'kind': _V2Nullable(_V2Closed(_v2_values(ct.Kind))),
                           'session': _V2Nullable(_v2_object_id('X'))})
    _V2_VERDICT = _V2Obj({'verdict': _V2Closed(_v2_values(ct.VerdictValue)),
                          'attached': _V2Closed(_v2_values(ct.Attached)),
                          'qualifiers': _V2List(_V2Closed(_v2_values(ct.Qualifier2))), 'evidence': _V2_UNITS})
    _V2_CLAIM = _V2Obj({'id': _V2_CLAIM_ID, 'role': _V2Closed(CLAIM_ROLES), 'template': _V2_NAME,
                        'subject': _V2_SUBJECT, 'attribute': _V2Closed(_v2_values(ct.Attribute)), 'value': _V2_VALUE,
                        'units': _V2_UNITS, 'content': _V2_SHA, 'verdict': _V2Nullable(_V2_VERDICT)},
                       _v2_claim_check)
    _V2_EVENTS = _V2Obj({
        'units': _V2Units(), 'encounter': _V2_ENCOUNTER, 'people': _V2List(_V2_PERSON),
        'sections': _V2List(_V2_SECTION), 'sessions': _V2List(_V2_SESSION), 'anatomy': _V2List(_V2_ANATOMY),
        'lesions': _V2List(_V2_LESION), 'events': _V2List(_V2_EVENT), 'doubts': _V2List(_V2_DOUBT),
        'claims': _V2Claims(), 'unlisted': _V2List(_V2_UNLISTED),
    })
    _V2_REPORT_READ = _V2Obj({
        'label': _V2_STR, 'request_sha256': _V2_SHA, 'response_sha256': _V2_SHA, 'appraisal_request_sha256': _V2_SHA,
        'appraisal_response_sha256': _V2_SHA, 'claims_sha256': _V2_SHA, 'refused': _V2Const(False),
        'counts': _V2Map(_V2Map(_V2_INT, keys=_v2_values(ct.Result)), keys=_v2_values(ct.Attribute)),
        'reasons': _V2Map(_V2_INT, keys=_v2_values(ct.Reason)),
        'doubts': _V2Json(), 'health': _V2Json(object_only=True), 'coherence': _V2Json(object_only=True),
        'unlisted': _V2Obj({'kept': _V2_INT,
                            'dropped': _V2List(_V2Obj({'units': _V2_UNITS,
                                                       'what': _V2Closed(_v2_values(ct.UnlistedWhat)),
                                                       'kind': _V2Nullable(_V2Closed(_v2_values(ct.Kind))),
                                                       'session': _V2Nullable(_v2_object_id('X')),
                                                       'event': _v2_object_id('E')}))}),
        'usage': _V2Obj({'interpretation': _V2Json(object_only=True), 'appraisal': _V2Json(object_only=True)}),
    })
    _V2_REPORT_REFUSED = _V2Obj({'label': _V2_STR, 'request_sha256': _V2_SHA, 'response_sha256': _V2_SHA,
                                 'refused': _V2Const(True), 'stage': _V2Closed(xr.STAGES),
                                 'problems': _V2List(_V2_STR)})

    # What each read v2 version pair stores, by state, and its report label. A pair added to READ_VERSIONS brings its
    # own shapes beside these, and these never change under a shipped pair (shape_signature_v2).
    _V2_SHAPES = {
        READ_VERSIONS[0]: {
            READ: {'events': _V2_EVENTS, 'encounter_facts': _V2Const({}), 'open_questions': _V2Const([]),
                   'verification': _V2_REPORT_READ},
            REFUSED: {'events': _V2Const({}), 'encounter_facts': _V2Const({}), 'open_questions': _V2Const([]),
                      'verification': _V2_REPORT_REFUSED},
        },
    }
    _V2_LABELS = {READ_VERSIONS[0]: LABEL_V2}


def shape_signature_v2(versions: tuple) -> str:
    """The sha256 of the shapes a read v2 version pair stores, with every closed list they read (contract/types'
    enumerations included), its label, its refusal rules (contract/extract_read's stages and sentence prefix) and its
    claim rules (the roles, the claim identity, the control partners CONTROL_ATTRIBUTES and what a pair control asks):
    tests/v2/test_store.py pins it per shipped pair, so nothing - an enumeration changed in contract/types or a stage in
    contract/extract_read included - silently changes how a stored v2 inventory is read (FINAL-V2 6.2 [R:MO-5])."""
    _v2()
    shapes = _V2_SHAPES[versions]
    return sha256_of({
        'shapes': {state: {name: spec.describe() for name, spec in parts.items()} for state, parts in shapes.items()},
        'fact': _V2_FACT_SHAPE.describe(), 'label': _V2_LABELS[versions], 'fields': list(FIELDS_V2),
        'refusal': [list(xr.STAGES), xr.REFUSED], 'roles': list(CLAIM_ROLES),
        'controls': sorted([fact, control] for fact, control in CONTROL_ATTRIBUTES.items()),
        'pair_controls': list(_V2_PAIR_ATTRIBUTES),
        'identity': list(CLAIM_IDENTITY), 'letters': list(ID_LETTERS_V2) + [CLAIM_LETTER],
        'values': sorted(_V2_ANY_VALUE),
        'domains': sorted([letter, attribute, domain.describe()]
                          for (letter, attribute), domain in _V2_DOMAINS.items()),
    })


# --- what a v2 consumer gets ------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StoredInventoryV2:
    """One v2 EventInventory row as load_v2 read and checked it. A read row's settled inventory is ``events``; on a
    refused row it raises StoreError, so a refused answer is never taken for one that documents nothing, and the refusal
    is ``refusal_stage`` and ``refusal_reason`` (None on a read row). ``appraisal_run_id`` is None exactly on a refused
    row."""
    encounter_id: str
    revision_id: str
    provider_run_id: str
    appraisal_run_id: Optional[str]
    interpretation_version: str
    inventory_version: str
    text_sha256: str
    request_sha256: str
    response_sha256: str
    state: str
    verification: dict
    sha256: str
    _events: dict = field(repr=False)  # read through ``events`` only, so a refusal is never read as empty

    @property
    def label(self) -> str:
        return _V2_LABELS[(self.interpretation_version, self.inventory_version)]

    @property
    def refused(self) -> bool:
        return self.state == REFUSED

    @property
    def refusal_stage(self) -> Optional[str]:
        return self.verification['stage'] if self.refused else None

    @property
    def refusal_reason(self) -> Optional[str]:
        return self.verification['problems'][0] if self.refused else None

    @property
    def events(self) -> dict:
        if self.refused:
            raise StoreError(f'This interpretation was refused, so it has no events: {self.refusal_reason}')
        return self._events

    @property
    def claims_sha256(self) -> str:
        if self.refused:
            raise StoreError('This interpretation was refused, so it has no claims.')
        return self.verification['claims_sha256']


# --- writing v2 -------------------------------------------------------------------------------------------------------

def row_v2(*, encounter_id, revision_id, provider_run_id, appraisal_run_id, revision_text: str, text_sha256: str,
           request_sha256: str, response_sha256: str, appraisal_request_sha256: str, appraisal_response_sha256: str,
           events, verification) -> dict:
    """The FIELDS_V2 of the row for an inventory both passes settled, at the current version pair, with its sha256.
    ``events`` is the settled inventory (JSON data, or contract/types records and Enum members, converted) and
    ``verification`` settle's report, which gets the label, both runs' request and response sha256, claims_sha256 (of
    events.claims) and ``refused`` false where it does not carry them; a value it carries must already be right
    (Mismatch). The row is read back by load_v2 first, so nothing is written that the reader would refuse; then
    ``revision_text`` (not stored) must be the text text_sha256 names, every unit must lie within it and every stored
    words record must be its own slice at its offsets (Mismatch; FINAL-V2 3.1 B1, P9). StoreError otherwise;
    TypeError when ``revision_text`` is not a string."""
    _v2()
    if not isinstance(revision_text, str):
        raise TypeError('The revision text must be a string.')
    content = _v2_jsonable(events, 'events')
    report = _v2_jsonable(verification, 'verification')
    if not isinstance(report, dict):
        raise UnknownShape('The stored interpretation is not readable: verification is not an object.')
    if not isinstance(content, dict):
        raise UnknownShape('The stored interpretation is not readable: events is not an object.')
    try:
        claims = claims_sha256_v2(content['claims'])
    except (KeyError, TypeError, ValueError):
        raise UnknownShape('The stored interpretation is not readable: events.claims is not a claim list.') from None
    for key, value in (('label', LABEL_V2), ('request_sha256', request_sha256), ('response_sha256', response_sha256),
                       ('appraisal_request_sha256', appraisal_request_sha256),
                       ('appraisal_response_sha256', appraisal_response_sha256), ('claims_sha256', claims),
                       ('refused', False)):
        if key in report and not _v2_same(report[key], value):
            raise Mismatch(f'The verification report names another {key.replace("_", " ")} than this row.')
        report[key] = value
    fields = {**_v2_bound(encounter_id, revision_id, provider_run_id, appraisal_run_id),
              'interpretation_version': _V2_CURRENT[0], 'inventory_version': _V2_CURRENT[1], 'text_sha256': text_sha256,
              'request_sha256': request_sha256, 'response_sha256': response_sha256, 'state': READ, 'events': content,
              'encounter_facts': {}, 'open_questions': [], 'verification': report}
    fields = _v2_finished(fields, appraisal_response_sha256)
    if _v2_text_sha256(revision_text) != fields['text_sha256']:
        raise Mismatch('The revision text given is not the text this row names (text_sha256).')
    _v2_bound_to_text(fields, revision_text)
    return fields


def refused_row_v2(refusal, *, encounter_id, revision_id, provider_run_id, text_sha256: str, request_sha256: str,
                   response_sha256: str) -> dict:
    """The FIELDS_V2 of the row for a PASS-1 answer refused whole (FINAL-V2 6.3; 3.1 S1, as v1): state ``refused``, no
    appraisal run, no events, and a report holding the refusal's sentence as its one problem and its stage.
    ``refusal`` is an object with the ``stage`` and ``reason`` of the refusal (contract's, or v1's read.Refusal); there
    is no way to give it an appraisal run, because a refused or unhealthy pass-2 answer is never stored as a row - it
    is recorded on its ProviderRun and the stage, and a row with an appraisal run is a read row. TypeError when
    ``refusal`` is not one; StoreError for a stage or sentence load_v2 refuses."""
    _v2()
    stage, reason = getattr(refusal, 'stage', None), getattr(refusal, 'reason', None)
    if not isinstance(stage, str) or not isinstance(reason, str) or getattr(refusal, 'refused', True) is not True:
        raise TypeError('A refused row records the refusal of a pass-1 answer: its stage and its reason.')
    report = {'label': LABEL_V2, 'request_sha256': request_sha256, 'response_sha256': response_sha256,
              'refused': True, 'stage': stage, 'problems': [reason]}
    fields = {**_v2_bound(encounter_id, revision_id, provider_run_id, None),
              'interpretation_version': _V2_CURRENT[0], 'inventory_version': _V2_CURRENT[1], 'text_sha256': text_sha256,
              'request_sha256': request_sha256, 'response_sha256': response_sha256, 'state': REFUSED, 'events': {},
              'encounter_facts': {}, 'open_questions': [], 'verification': report}
    return _v2_finished(fields, None)


def _v2_bound(encounter_id, revision_id, provider_run_id, appraisal_run_id) -> dict:
    return {name: _v2_uuid(value, name, nullable=name == 'appraisal_run_id') for name, value in
            zip(BINDINGS_V2, (encounter_id, revision_id, provider_run_id, appraisal_run_id))}


def _v2_finished(fields: dict, appraisal_response_sha256: Optional[str]) -> dict:
    try:
        fields['sha256'] = content_sha256_v2(fields)
    except StoreError:
        raise
    except (TypeError, ValueError):
        raise UnknownShape('The interpretation to store is not JSON data.') from None
    load_v2(fields, text_sha256=fields['text_sha256'], response_sha256=fields['response_sha256'],
            appraisal_response_sha256=appraisal_response_sha256)
    return {name: fields[name] for name in FIELDS_V2}


def _v2_jsonable(value: object, path: str) -> object:
    """``value`` as JSON data: a dataclass (contract/types' records) as the object of its fields, an Enum member as its
    value, a tuple as a list; UnknownShape for anything that is not JSON data then."""
    if isinstance(value, enum.Enum):
        return _v2_jsonable(value.value, path)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: _v2_jsonable(getattr(value, item.name), path) for item in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [_v2_jsonable(item, path) for item in value]
    if isinstance(value, Mapping):
        converted = {}
        for key, item in value.items():
            key = key.value if isinstance(key, enum.Enum) else key
            if not isinstance(key, str):
                raise UnknownShape(f'The interpretation to store is not JSON data: {path} has a key that is not a '
                                   'string.')
            converted[key] = _v2_jsonable(item, path)
        return converted
    if value is None or isinstance(value, (str, bool, int)) or (isinstance(value, float) and math.isfinite(value)):
        return value
    raise UnknownShape(f'The interpretation to store is not JSON data: {path} holds a {type(value).__name__}.')


def _v2_text_sha256(text: str) -> str:
    """SourceRevision.text_sha256's value for ``text``: the sha256 of its UTF-8 bytes; '' for a text UTF-8 cannot
    encode, which no revision's text_sha256 names."""
    try:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    except UnicodeEncodeError:
        return ''


def _v2_bound_to_text(fields: Mapping, revision_text: str) -> None:
    """Mismatch unless every unit lies within ``revision_text`` and every words record of the content (a record holding
    a start, an end and a text, wherever it sits) is that text's own slice at its offsets, never the model's string
    (FINAL-V2 3.1 B1, P9). A problem names the place, never the text."""
    if fields['state'] == READ:
        for index, unit in enumerate(fields['events']['units']):
            if unit['end'] > len(revision_text):
                raise Mismatch(f'The interpretation to store has events.units[{index}] beyond the revision text.')
    pending = [(fields[name], name) for name in reversed(CONTENT_V2)]
    while pending:
        value, path = pending.pop()
        if isinstance(value, dict):
            if {'start', 'end', 'text'} <= value.keys():
                start, end, text = value['start'], value['end'], value['text']
                if type(start) is not int or type(end) is not int or not isinstance(text, str):
                    raise UnknownShape(f'The interpretation to store is not readable: {path} holds words whose '
                                       'offsets are not integers or whose text is not a string.')
                if not 0 <= start <= end <= len(revision_text) or revision_text[start:end] != text:
                    raise Mismatch(f'The interpretation to store quotes at {path} what the revision text does not hold '
                                   'at those offsets.')
            pending.extend((item, f'{path}.{_v2_named(key)}') for key, item in reversed(list(value.items())))
        elif isinstance(value, list):
            pending.extend((item, f'{path}[{index}]') for index, item in reversed(list(enumerate(value))))


def claims_sha256_v2(claims) -> str:
    """The claim list's sha256 (FINAL-V2 1.7 [R:MO-5]): sha256_of each claim's CLAIM_IDENTITY, in their seeded order -
    never a verdict, so the same claim set has the same sha256 whatever pass 2 answered. KeyError or TypeError for a
    list that is not one of claims."""
    _v2()
    return sha256_of([{name: claim[name] for name in CLAIM_IDENTITY} for claim in claims])


def content_sha256_v2(fields: Mapping) -> str:
    """sha256_of the HASHED_V2 fields of ``fields`` (every field but ``sha256``), the bindings as UUID strings and the
    appraisal run None when there is none: types.sha256_json's value for the same data, as EventInventory.sha256
    says."""
    _v2()
    hashed = {name: fields[name] for name in HASHED_V2}
    hashed.update(_v2_bound(*(fields[name] for name in BINDINGS_V2)))
    return sha256_of(hashed)


# --- reading v2 -------------------------------------------------------------------------------------------------------

def fields_of_v2(instance) -> dict:
    """The FIELDS_V2 of an EventInventory-like object (its foreign keys by attname), for load_v2. UnknownShape when one
    is missing. A v1 row's fields are read, and load_v2 refuses its versions."""
    missing = object()
    fields = {name: getattr(instance, name, missing) for name in FIELDS_V2}
    absent = [name for name, value in fields.items() if value is missing]
    if absent:
        raise UnknownShape(f'The stored interpretation lacks {", ".join(absent)}.')
    return fields


def load_v2(fields: Mapping, *, text_sha256: str, response_sha256: str,
            appraisal_response_sha256: Optional[str]) -> StoredInventoryV2:
    """The v2 row's content as StoredInventoryV2, read AS STORED under its own version pair's shapes (READ_VERSIONS),
    after every check the head of design v2 names. ``text_sha256`` is the bound revision's text_sha256,
    ``response_sha256`` the sha256 of pass 1's run's stored response bytes and ``appraisal_response_sha256`` that of the
    appraisal run's (None for a refused row, which has none), as the reader computes them: the row must name each.
    Raises UnknownVersion (a v1 row's pair included: v2 never reads a v1 row), UnknownShape or Mismatch (all
    StoreError); never returns None."""
    _v2()
    if not isinstance(fields, Mapping):
        raise UnknownShape('A stored interpretation must be a mapping of its fields.')
    missing = [name for name in FIELDS_V2 if name not in fields]
    extra = [name for name in fields if name not in FIELDS_V2]
    if missing or extra:
        raise UnknownShape('The stored interpretation does not have exactly the fields of design v2'
                           f'{" (lacks " + ", ".join(missing) + ")" if missing else ""}'
                           f'{" (has " + ", ".join(_v2_named(name) for name in extra) + ")" if extra else ""}.')
    versions = (fields['interpretation_version'], fields['inventory_version'])
    if not all(isinstance(value, str) for value in versions) or versions not in _V2_SHAPES:
        raise UnknownVersion('This release reads no design v2 interpretation stored as '
                             f'{_v2_version(versions[0])} with {_v2_version(versions[1])}.')
    state = fields['state']
    if state not in (READ, REFUSED):
        raise UnknownShape('The stored interpretation has a state this release does not know.')
    bindings = _v2_bound(*(fields[name] for name in BINDINGS_V2))
    if (bindings['appraisal_run_id'] is None) is not (state == REFUSED):
        raise UnknownShape('The stored interpretation is not readable: a read row names its appraisal run, and a '
                           'refused row - a refused pass-1 answer - names none (a pass-2 answer is never stored as a '
                           'row).')
    for name in ('text_sha256', 'request_sha256', 'response_sha256', 'sha256'):
        problem = _V2_SHA.problem(fields[name], name)
        if problem:
            raise UnknownShape(f'The stored interpretation is not readable: {problem}.')
    shapes = _V2_SHAPES[versions][state]
    for name in CONTENT_V2:
        problem = shapes[name].problem(fields[name], name)
        if problem:
            raise UnknownShape(f'The stored interpretation is not readable: {problem}.')
    _v2_consistent(fields, versions, state)
    if content_sha256_v2(fields) != fields['sha256']:
        raise Mismatch('The stored interpretation no longer matches its sha256.')
    if fields['text_sha256'] != text_sha256:
        raise Mismatch('The stored interpretation was made from another revision text.')
    if fields['response_sha256'] != response_sha256:
        raise Mismatch('The stored interpretation was read from another response than the stored one.')
    expected = None if state == REFUSED else fields['verification']['appraisal_response_sha256']
    if appraisal_response_sha256 != expected:
        raise Mismatch('The stored interpretation was settled from another appraisal response than the stored one.'
                       if expected else 'A refused interpretation has no appraisal response.')
    return StoredInventoryV2(**bindings, interpretation_version=versions[0], inventory_version=versions[1],
                             text_sha256=fields['text_sha256'], request_sha256=fields['request_sha256'],
                             response_sha256=fields['response_sha256'], state=state,
                             verification=copy.deepcopy(fields['verification']), sha256=fields['sha256'],
                             _events=copy.deepcopy(fields['events']))


# --- the engine's text-free view (DECISIONS D188) ---------------------------------------------------------------------

def textfree_v2(stored: StoredInventoryV2) -> Mapping[str, object]:
    """A read row's ``events`` as the engine reads them, holding no text (DECISIONS D188; FINAL-V2 1.7, 4.1 and 5.7
    measure 4): a deep copy in which every source's ``words`` record (1.7 sources[].words, wherever a source sits: a
    fact's, an option's, a section's start or end, a person's name, a lesion's description) becomes ``at`` - {start,
    end}, the offsets of its located words in the revision, or None when ``words`` is None (pass 1's words '': the
    source cites its whole units) - and every ``text`` key is dropped, so an anchor's kind_words and status_words keep
    their start and end only. Every other key and value is as stored. engine/facts.py builds the FactSet from this
    view alone, so no ``words`` or ``text`` name is read in engine/; wording.quote slices the revision after the
    decision. StoreError for a refused row (it has no events, StoredInventoryV2.events); TypeError for anything that
    is not a StoredInventoryV2 (the view is only of a row load_v2 read and checked)."""
    if not isinstance(stored, StoredInventoryV2):
        raise TypeError('textfree_v2 reads a StoredInventoryV2, as load_v2 gives one.')
    return _v2_textfree_object(stored.events)


def _v2_textfree_object(value: Mapping) -> dict:
    """An object of the stored events, copied with its ``words`` record as ``at`` {start, end} (None for None) and no
    ``text`` key, and every value inside it copied the same way."""
    view: dict = {}
    for key, item in value.items():
        if key == 'text':
            continue
        if key == 'words':
            view['at'] = None if item is None else {'start': item['start'], 'end': item['end']}
        else:
            view[key] = _v2_textfree(item)
    return view


def _v2_textfree(value: object) -> object:
    if isinstance(value, dict):
        return _v2_textfree_object(value)
    if isinstance(value, list):
        return [_v2_textfree(item) for item in value]
    return value


def _v2_consistent(fields: Mapping, versions: tuple, state: str) -> None:
    """The row agrees with itself (FINAL-V2 1.7, 3.2.4): the report names the row's label, request and response, and
    for a read row its claim list, its kept unlisted statements, and verdicts read against the claims they answered;
    a refused row records exactly one refusal sentence. Ids are unique per object family, and every established fact
    rests on the row's own units and objects (_v2_established_bound)."""
    report = fields['verification']
    if report['label'] != _V2_LABELS[versions]:
        raise Mismatch('The stored verification report names another interpretation label than its row.')
    if report['request_sha256'] != fields['request_sha256'] or report['response_sha256'] != fields['response_sha256']:
        raise Mismatch('The stored verification report names another request or response than its row.')
    if state == REFUSED:
        problems = report['problems']
        if len(problems) != 1 or not _v2_refusal_sentence(problems[0]):
            raise UnknownShape('A refused interpretation records exactly one problem: its refusal sentence.')
        return
    events = fields['events']
    for key in ('people', 'sections', 'sessions', 'anatomy', 'lesions', 'events'):
        seen = set()
        for index, item in enumerate(events[key]):
            if item['id'] in seen:
                raise UnknownShape(f'The stored interpretation is not readable: events.{key}[{index}] repeats an id.')
            seen.add(item['id'])
    _v2_established_bound(events)
    if report['claims_sha256'] != claims_sha256_v2(events['claims']):
        raise Mismatch('The stored verification report names another claim list than its row holds.')
    if report['unlisted']['kept'] != len(events['unlisted']):
        raise Mismatch('The stored verification report counts other unlisted statements than its row keeps.')
    _v2_verdicts_bound(events)


def _v2_established_bound(events: Mapping) -> None:
    """UnknownShape unless every ESTABLISHED fact rests on the row itself (FINAL-V2 3.3 row 8, read as integrity with
    3.1 I1 and I4; arbiter triage 1d#3): each unit its sources cite and each evidence unit of its appraisal is one of
    the row's units, and an id value names an object of its family in the row (E2's session X9 with no session X9 is
    refused); a supported completeness record's evidence units likewise. A fact that is not established may keep a unit
    or an id that names nothing: that is an item-level finding (1.8), which settled it unresolved, its value kept. A
    problem names the place, never the stored value."""
    units = {unit['id'] for unit in events['units']}
    objects = {letter: {item['id'] for item in events[key]} for letter, key in _V2_FAMILIES}
    unreadable = 'The stored interpretation is not readable: '
    for path, _subject, spec, record in _V2_EVENTS.facts(events, 'events', ''):
        if isinstance(spec, _V2Completeness):
            if record['result'] == ct.Result.SUPPORTED.value and not set(record['appraisal']['evidence']) <= units:
                raise UnknownShape(f'{unreadable}{path} is supported on evidence that names a unit the row does not '
                                   'have (FINAL-V2 3.2.3, 3.1 I1).')
            continue
        if record['result'] not in _V2_ESTABLISHED:
            continue
        for index, source in enumerate(record['sources']):
            if not set(source['units']) <= units:
                raise UnknownShape(f'{unreadable}{path} is established on {path}.sources[{index}], which cites a unit '
                                   'the row does not have (FINAL-V2 3.3 row 8, 3.1 I1).')
        if not set(record['appraisal']['evidence']) <= units:
            raise UnknownShape(f'{unreadable}{path} is established on evidence that names a unit the row does not '
                               'have (FINAL-V2 3.3 row 8, 3.1 I1).')
        if spec.domain.letter and record['claim']['value'] not in objects[spec.domain.letter]:
            raise UnknownShape(f'{unreadable}{path} is established on an id that names no object of its family in the '
                               'row (FINAL-V2 3.3 row 8, 3.1 I4).')


def _v2_refusal_sentence(reason: object) -> bool:
    """Whether ``reason`` is a refusal sentence as contract/extract_read.Refusal holds one: its REFUSED prefix, then a
    reason, then a full stop."""
    return (isinstance(reason, str) and reason.startswith(xr.REFUSED)
            and len(reason) > len(xr.REFUSED) + 1 and reason.endswith('.'))


def _v2_verdicts_bound(events: Mapping) -> None:
    """Mismatch unless every verdict a fact (or a completeness record) stores is the one stored with the claim it names,
    and that claim is the one made for THAT fact: role claim (completeness), the fact's subject, attribute and value,
    the same content key; its control a control (completeness control) of the same subject, with the same verdict. No
    claim is read by two facts. So a verdict is never read against a different claim (FINAL-V2 3.2.4 [R:MO-5]). And
    UnknownShape unless that control is about the fact's own attribute or the partner 3.2.3 writes its control in
    (CONTROL_ATTRIBUTES): E2's kind is never read against the control of E2's status (arbiter triage 1d#4)."""
    claims = {claim['id']: claim for claim in events['claims']}
    read = set()
    for path, subject, spec, record in _V2_EVENTS.facts(events, 'events', ''):
        appraisal = record['appraisal']
        if appraisal is None:
            continue
        completeness = isinstance(spec, _V2Completeness)
        claim = claims.get(appraisal['claim'])
        if (claim is None or appraisal['claim'] in read
                or claim['role'] != ('completeness' if completeness else 'claim') or claim['subject'] != subject
                or claim['attribute'] != (_A.STATIONS.value if completeness else spec.attribute.value)
                or claim['content'] != appraisal['content']
                or (not completeness and claim['value'] != record['claim']['value'])
                or not _v2_same(claim['verdict'], None if appraisal['verdict'] is None else {
                    'verdict': appraisal['verdict'], 'attached': appraisal['attached'],
                    'qualifiers': appraisal['qualifiers'], 'evidence': appraisal['evidence']})):
            raise Mismatch(f'The stored interpretation reads a verdict at {path}.appraisal against another claim than '
                           'the one made for it.')
        read.add(appraisal['claim'])
        control = appraisal['control']
        if control is None:
            continue
        other = claims.get(control['claim'])
        if (other is None or control['claim'] in read
                or other['role'] != ('completeness_control' if completeness else 'control')
                or other['subject'] != subject
                or (None if other['verdict'] is None else other['verdict']['verdict']) != control['verdict']):
            raise Mismatch(f'The stored interpretation reads a control at {path}.appraisal.control against another '
                           'claim than its control.')
        attribute = _A.STATIONS.value if completeness else spec.attribute.value
        if other['attribute'] not in (attribute, CONTROL_ATTRIBUTES.get(attribute)):
            raise UnknownShape(f'The stored interpretation is not readable: the control at {path}.appraisal.control '
                               'is about another attribute than its fact (FINAL-V2 3.2.3; CONTROL_ATTRIBUTES).')
        read.add(control['claim'])


def _v2_uuid(value: object, name: str, nullable: bool = False) -> Optional[str]:
    if value is None and nullable:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        try:
            return str(uuid.UUID(value))
        except ValueError:
            pass
    raise UnknownShape(f'{name} is not a UUID.')


def _v2_version(value: object) -> str:
    """A stored version for a problem: as written when it has a version's shape, else 'an unknown value'."""
    if (isinstance(value, str) and 1 <= len(value) <= 40 and value[0] in _V2_KEY_FIRST
            and all(character in _V2_NAME_CHARACTERS or character in '@+/' for character in value)):
        return repr(value)
    return 'an unknown value'
