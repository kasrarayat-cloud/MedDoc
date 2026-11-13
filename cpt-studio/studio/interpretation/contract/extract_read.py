"""The strict reader of pass 1's answer (gemini-events@2; docs/gemini-migration/FINAL-V2.md 3.1 rows S1, S2, I1, I3's
per-source bound and I4, and 1.8; step 1b of 8.1): read(answer_text, unit_count) gives the answer with its item-level
findings (ReadAnswer), or a Refusal of the WHOLE answer.

**S1: the whole answer, in this order; the first failure refuses it and nothing of it is read** (as v1's read.py):
1. JSON, strictly (participants.reading.strict_json_text): a repeated key, NaN or Infinity, a number too large, NUL or a
   lone surrogate refuses it (stage ``json``).
2. LOCAL_SCHEMA_2, by CPT Studio's own validator (participants.reading.schema_error): types, enumerations, every
   required field, no other field (stage ``schema``). Gemini's responseSchema is a hint, never trusted.
3. BOUNDS_2 (1.8), each named by count, never truncated (stage ``bounds``): the lists 1.8 numbers (a section's closing
   signatures are not one of them: only the cited units bound them), each slot at one fact, each words value at 600
   characters, and the unit ids cited in the whole answer.
4. The ids, in one grammar (stage ``ids``; DECISIONS D185): every object id is its family's letter (Family.letter: P, N,
   X, Y, L, E) followed by its number in canonical decimal digits - 0, or at most 9 ASCII digits not opening with 0
   ('E1', 'N0'; never 'E01', 'e1' or 'E 1') - and unique in its family; every id-valued reference (a FACT's value but
   '', the contradicted value S2 reads; every option's value; every member of an id list), every object a doubt names
   and every cited unit id ('S' and its number) has the same shape. The store's v2 check admits exactly these and
   engine/types.Id.parse reads each of them back, so a breach can no longer pass here and fail at the store or the
   FactSet.
5. The ISO shapes (stage ``schema``, as v1): the date of service is '' or a real YYYY-MM-DD date and each of its options
   a real YYYY-MM-DD date; an other date, and an act's date, is '' or a real date at its precision (YYYY-MM-DD, YYYY-MM
   or YYYY), and each option of an act's date such a date.

**Item-level findings never refuse the answer** (3.1; 1.8). Each makes the fact it touches UNRESOLVED when settle
applies it (3.3 row 4), with a reason from the closed list types.Reason:
- S2 ``shape_inconsistent``: a fact whose value is not empty exactly when it is contradicted, a supported or negated fact
  with no source or with options, a contradicted fact with fewer than two options, two options of one value, or an
  option with no source; a source citing no unit (1.2 rule 7: a source cites one or more units); the date of service's
  shape by the same rule (stated: a value and sources, no option; several: no value, sources, and two or more options
  of distinct dates, each with sources; not_stated: no value, no source, no option; the shape DECISIONS D187
  confirms). A malformed doubt - one naming an object that does not carry its attribute
  (extract_schema.DOUBT_ATTRIBUTES, confirmed by DECISIONS D200), a reading that is not a value of that attribute (a
  date of service's reading is a day, as the date of service is: D200), no object (but for the date of service, which
  only the encounter carries), no unit, an unknown unit or an object that does not resolve - applies to EVERY claimed
  fact of its objects (fail-closed; ReadDoubt.named). One that names no object names nothing here: settle (step 3a)
  applies it to every claimed fact of every event whose anchor units include one of its units, else keeps it as an
  unlisted doubt (D200), reading the doubt's unit ids and the anchors' units this reader gives.
- I1 ``unit_unknown``: a cited unit id, well formed (S1's ids stage), that is not one of the revision's units 'S1' ..
  'S<unit_count>'.
- I3's per-source bound ``source_too_long``: a source, or an anchor, of more than 12 units [R:CO-5]. The answer is read.
- I4 ``reference_invalid``: a well-formed id that names no object of the family its field refers to (none at all, or
  an object of another family: D185); a self reference (part_of, cause_event, part_of_session, distinct_from, same_as,
  covers, excepts); a cycle of part_of, of cause_event or of part_of_session (an edge is a supported value or a
  contradicted fact's option; a negated value denies the relation).
I2, I3's consecutiveness and the G checks are contract/geometry.py's (step 1c); K, L and Q are contract/consistency.py's
(step 2b); settle (step 3a) applies them all with these and the doubts.

**Nothing here sets, changes or removes a value.** Every fact is read exactly as written (types.Fact); a finding is a
reason beside it, never an edit. The parsed answer is kept as parsed.

A refusal's reason is CPT Studio's own sentence: it names places by path and position and values by count, and never
repeats the model's text (I9). Refusal, refuse, iso_date and partial_date are v1's (read.py), copied so that the new
path runs no v1 code (5.7: store's v2 reader imports them from here), with v1's regular expressions replaced by
character tests; tests/v2/test_extract_read.py proves each equal to v1's.

Versions (1.1): S1 is a read rule of INTERPRETATION_VERSION_V2; the item-level checks are checks of
INVENTORY_VERSION_V2, re-run on stored pass-1 bytes by a re-settle. An answer is read only under LOCAL_SCHEMA_2's pin
(check_pin), which stays empty until the integration owner writes it (2.5): until then no answer is read.

This module imports no regular-expression or text module (5.6 lists it nowhere): it reads ids, values and counts.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum, unique
from typing import Any, cast

from studio import interpretation
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import jsonschema
from studio.interpretation.contract.types import (Attribute, DateState, Doubt, DoubtAbout, DoubtBasis, Fact, FactState,
                                                  Link, Option, Qualifier, Reason, Source)
from studio.participants import reading

Family, Arity, Bound = xs.Family, xs.Arity, xs.Bound

# --- the Refusal (v1's read.Refusal, copied) --------------------------------------------------------------------------

REFUSED = 'The interpretation was not used: '  # every refusal sentence starts so; the reason follows


@unique
class Stage(Enum):
    """Where a whole answer was refused: the adapter's envelope (step 3b), then S1's steps (v1's read.STAGES)."""
    ENVELOPE = 'envelope'
    JSON = 'json'
    SCHEMA = 'schema'
    BOUNDS = 'bounds'
    IDS = 'ids'


STAGES: tuple[str, ...] = tuple(stage.value for stage in Stage)


@dataclass(frozen=True)
class Refusal:
    """A whole answer refused: none of it is read, and the attempt is a definite failure. ``reason`` is CPT Studio's
    sentence, starting with REFUSED; ``stage`` names the step that refused it (STAGES). Made by ``refuse``. v1's
    read.Refusal, field for field."""
    stage: str
    reason: str
    refused: bool = True

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ValueError(f'A refusal stage is one of {", ".join(STAGES)}.')
        if (not isinstance(self.reason, str) or not self.reason.startswith(REFUSED)
                or len(self.reason) <= len(REFUSED) + 1 or not self.reason.endswith('.')):
            raise ValueError(f'A refusal reason is one sentence starting {REFUSED!r} and ending with a full stop.')
        if self.refused is not True:
            raise ValueError('A Refusal is always refused.')


def refuse(stage: str, why: str) -> Refusal:
    """The Refusal of a whole answer at ``stage``, ``why`` being CPT Studio's own words (never the model's)."""
    ending = '' if why.endswith('.') else '.'
    return Refusal(stage=stage, reason=f'{REFUSED}{why}{ending}')


# --- shapes, by character (D185's id grammar; v1's read.py iso_date and partial_date, without a regular expression) --

UNIT_LETTER = 'S'  # every unit id opens with it (1.2 rule 5: 'S<k>')
OBJECT_LETTERS = ''.join(family.letter for family in xs.Family)  # the families' letters, in Family's order: PNXYLE


def _digit(character: str) -> bool:
    return '0' <= character <= '9'


def is_id(value: str, letters: str) -> bool:
    """Whether ``value`` is an id of one of ``letters`` (DECISIONS D185; FINAL-V2 1.4, 1.2 rule 5): one of the letters,
    then its number in canonical ASCII decimal digits - 0, or 1 to 9 digits the first of which is not 0 ('E1', 'N0',
    'S12'; never 'E01', 'e1', 'E 1', 'E+1', 'E²' or ten digits). It admits exactly what store._v2_id admits, and
    engine/types.Id.parse reads every id it admits back to the same letter and number."""
    digits = value[1:]
    return (2 <= len(value) <= 10 and value[0] in letters and all(_digit(character) for character in digits)
            and (digits == '0' or digits[0] != '0'))


def _digits_with_dashes(value: str, length: int, dashes: tuple[int, ...]) -> bool:
    """Whether ``value`` has ``length`` characters, '-' exactly at ``dashes`` and an ASCII digit everywhere else."""
    return len(value) == length and all(
        character == '-' if at in dashes else _digit(character) for at, character in enumerate(value))


def iso_date(value: str) -> bool:
    """Whether ``value`` is a real calendar date written YYYY-MM-DD in ASCII digits (v1's read.iso_date)."""
    if not _digits_with_dashes(value, 10, (4, 7)):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def partial_date(value: str) -> bool:
    """Whether ``value`` is a real month or year written YYYY-MM or YYYY in ASCII digits, year 1 or later (v1's
    read.partial_date)."""
    if not (_digits_with_dashes(value, 4, ()) or _digits_with_dashes(value, 7, (4,))):
        return False
    try:
        date(int(value[:4]), int(value[5:7]) if len(value) == 7 else 1, 1)
    except ValueError:
        return False
    return True


def unit_known(value: str, unit_count: int) -> bool:
    """Whether ``value`` is the id of one of the revision's ``unit_count`` units, as contract/segment.py numbers them
    (1.2 rule 5): 'S' and a decimal from 1 to unit_count, with no leading zero."""
    digits = value[1:]
    return (len(value) >= 2 and value[0] == 'S' and digits[0] != '0' and len(digits) <= len(str(unit_count))
            and all(_digit(character) for character in digits) and int(digits) <= unit_count)


# --- the pin -----------------------------------------------------------------------------------------------------------


def check_pin() -> None:
    """RuntimeError unless LOCAL_SCHEMA_2 is byte for byte what INTERPRETATION_VERSION_V2 pins (2.5, v1's read.check_pin
    pattern). An empty pin (the placeholder before the integration owner writes it) is refused too: no answer is read
    under a schema nobody pinned."""
    pinned = interpretation.LOCAL_SCHEMA_SHA256_V2
    version = interpretation.INTERPRETATION_VERSION_V2
    if not pinned:
        raise RuntimeError(f'The local schema of {version} has no pin yet; an answer is read only under its pin.')
    if jsonschema.sha256_of(xs.LOCAL_SCHEMA_2) != pinned:
        raise RuntimeError(f'The local schema no longer matches the {version} pin; a changed schema needs a new '
                           'INTERPRETATION_VERSION.')


# --- what the reader gives -------------------------------------------------------------------------------------------


@unique
class Cited(Enum):
    """A citation in the answer that is not a fact's source (1.4): a person's name, a section's start and its closing
    signatures, a lesion's description, an event's anchor and its restatements."""
    NAME = 'name'
    START = 'start'
    END = 'end'
    DESCRIPTION = 'description'
    ANCHOR = 'anchor'
    RESTATEMENT = 'restatements'


@dataclass(frozen=True, slots=True)
class FactKey:
    """Where a fact, or a member of a scope list, sits in the answer: its family, its object's id ('' for the
    encounter), its attribute, and its position - in a FACTS or scope list, or among the encounter's other dates
    (other_dates.role); 0 for a FACT or a slot's one fact."""
    family: xs.Family
    object: str
    attribute: Attribute
    index: int


@dataclass(frozen=True, slots=True)
class DateOfService:
    """The encounter's date of service as pass 1 wrote it (1.4 ENCOUNTER.date_of_service: v1's states). state:
    DateState. value: a YYYY-MM-DD date, or ''. sources: its sources. options: for state several, one per date given."""
    state: DateState
    value: str
    sources: tuple[Source, ...]
    options: tuple[Option, ...]


@dataclass(frozen=True, slots=True)
class ReadFact:
    """One fact of the answer, read. key: where it is. fact: as pass 1 wrote it (types.Fact; the date of service as
    DateOfService). reasons: every finding of this reader on it (S2, I1, I3's per-source bound, I4), in Reason order,
    () when it passed them. sides: each option's own findings - its sources', its value's and its shape's - aligned
    with fact.options, so settle can tell a contradiction whose sides all pass from one with a failing side (3.3 row
    1); reasons includes them."""
    key: FactKey
    fact: Fact | DateOfService
    reasons: tuple[Reason, ...]
    sides: tuple[tuple[Reason, ...], ...]


@dataclass(frozen=True, slots=True)
class ReadCitation:
    """A citation that is not a fact's source, read. family and object: whose it is. cited: which (Cited). index: its
    position among the section's closing signatures or the event's restatements, else 0. units: its unit ids, as
    written. source: the Source, for a name, a start, an end or a description; None for an anchor or a restatement,
    whose other fields stay in the answer. reasons: I1 and, for a source or an anchor, the per-source bound; a citation
    of no unit is shape_inconsistent, except a section's start (the opening part's start cites none, 1.4; where a start
    sits is G2's, step 1c)."""
    family: xs.Family
    object: str
    cited: Cited
    index: int
    units: tuple[str, ...]
    source: Source | None
    reasons: tuple[Reason, ...]


@dataclass(frozen=True, slots=True)
class ReadMember:
    """One member of a statement's scope list (targets, segment, covers, excepts), read: key, its value as written,
    and its I4 findings (reference_invalid for an id naming no object of its family, or the event itself)."""
    key: FactKey
    value: str
    reasons: tuple[Reason, ...]


@dataclass(frozen=True, slots=True)
class ReadDoubt:
    """One entry of the answer's doubts, read (1.3 DOUBT, 3.1 S2).

    index: its position in the doubts list. doubt: as pass 1 wrote it (types.Doubt). objects: the objects it names,
    resolved as (family, id) in the order named, each once - every named id is well formed (S1's ids stage), so its
    letter is one family's and no id is borne by two families (DECISIONS D185); one that names no object is
    reference_invalid; a doubt about the date of service also names the encounter, (ENCOUNTER, ''), the one object that
    carries it. reasons: shape_inconsistent, unit_unknown, reference_invalid. malformed: whether there is any reason. A
    doubt can only demote: it never creates, sets or changes a value. A malformed doubt that resolves no object has no
    objects to apply ``named`` to, so it names no fact here: settle applies DECISIONS D200's unit rule to it (step 3a),
    from its doubt.units and the events' anchor citations."""
    index: int
    doubt: Doubt
    objects: tuple[tuple[xs.Family, str], ...]
    reasons: tuple[Reason, ...]
    malformed: bool

    def named(self, family: xs.Family) -> tuple[Attribute, ...]:
        """The attributes this doubt names on an object of ``family`` among its objects: DOUBT_ATTRIBUTES' row for a
        well-formed doubt; EVERY attribute of the family for a malformed one (3.1 S2: a malformed doubt applies to every
        claimed fact of its objects, fail-closed)."""
        if self.malformed:
            return xs.attributes(family)
        return xs.DOUBT_ATTRIBUTES[self.doubt.about].get(family, ())


@dataclass(frozen=True, slots=True)
class ReadAnswer:
    """An answer read: answer, the parsed JSON exactly as parsed; unit_count, the revision's units it was read against;
    facts, every fact in the answer's order (the encounter's, then each family's objects in turn, each object's in
    ATTRIBUTES' order); citations, members and doubts likewise. Every finding is item-level: settle applies them."""
    answer: dict[str, Any]
    unit_count: int
    facts: tuple[ReadFact, ...]
    citations: tuple[ReadCitation, ...]
    members: tuple[ReadMember, ...]
    doubts: tuple[ReadDoubt, ...]

    def fact(self, key: FactKey) -> ReadFact | None:
        """The fact at ``key``, None when the answer has none there (a silent slot)."""
        return next((item for item in self.facts if item.key == key), None)


# --- reading ------------------------------------------------------------------------------------------------------------


def read(answer: object, unit_count: int) -> Refusal | ReadAnswer:
    """The answer, parsed, checked whole as S1 says and then item by item, or the Refusal of all of it. ``unit_count`` is
    the number of units contract/segment.py cut the revision into (I1). Nothing is repaired, coerced, truncated or
    dropped. RuntimeError when LOCAL_SCHEMA_2 is not pinned or no longer matches its pin; ValueError for a unit count
    that is not a whole number of at least 0."""
    check_pin()
    if type(unit_count) is not int or unit_count < 0:
        raise ValueError('The unit count is a whole number of at least 0.')
    if not isinstance(answer, str):
        return refuse('json', 'there is no answer text')
    try:
        parsed = reading.strict_json_text(answer)
    except reading.JSONRefused as exc:
        return refuse('json', f'the answer {exc}')
    error = reading.schema_error(parsed, xs.LOCAL_SCHEMA_2, 'the interpretation')
    if error:
        return refuse('schema', f'the answer breaks the interpretation schema: {error}')
    parsed = cast(dict[str, Any], parsed)  # the schema's root is an object
    error = bound_error(parsed)
    if error:
        return refuse('bounds', error)
    error = id_error(parsed)
    if error:
        return refuse('ids', error)
    error = date_error(parsed)
    if error:
        return refuse('schema', error)
    return _Items(parsed, unit_count).read()


# --- S1.3: the bounds --------------------------------------------------------------------------------------------------


def _what(family: xs.Family) -> str:
    """What the objects of ``family`` are called in a sentence."""
    return 'anatomy entries' if family is Family.ANATOMY else family.value


def _too_many(items: list[Any], bound: xs.Bound, path: str, label: str, owner: str) -> str:
    """The refusal sentence when ``items`` is over ``bound``, else ''."""
    limit = xs.BOUNDS_2[bound]
    if len(items) > limit:
        return f'{path} lists {len(items):,} {label}, more than the {limit:,} one {owner} may have'
    return ''


def _words_error(value: str, path: str) -> str:
    limit = xs.BOUNDS_2[Bound.WORDS_CHARS]
    if len(value) > limit:
        return f'{path} has {len(value):,} characters, more than the {limit:,} one words value may have'
    return ''


def _source_bound(source: Mapping[str, Any], path: str) -> str:
    return _words_error(source['words'], f'{path}.words')


def _sources_bound(sources: list[Any], path: str, owner: str) -> str:
    error = _too_many(sources, Bound.SOURCES, path, 'sources', owner)
    for index, source in enumerate(sources):
        error = error or _source_bound(source, f'{path}[{index}]')
    return error


def _fact_bound(fact: Mapping[str, Any], path: str) -> str:
    """The first bound one fact (or the date of service) breaks: its sources, its options, each option's sources, each
    source's words."""
    error = (_sources_bound(fact['sources'], f'{path}.sources', 'fact')
             or _too_many(fact['options'], Bound.OPTIONS, f'{path}.options', 'options', 'fact'))
    for index, option in enumerate(fact['options']):
        error = error or _sources_bound(option['sources'], f'{path}.options[{index}].sources', 'option')
    return error


def _at(item: Mapping[str, Any], field: xs.Field) -> Any:
    """The value of ``field`` in ``item`` (a schema-valid object of its family)."""
    value: Any = item
    for key in field.path:
        value = value[key]
    return value


def _field_bound(item: Mapping[str, Any], field: xs.Field, path: str) -> str:
    """The first bound one attribute of one object breaks."""
    if field.arity is Arity.FACT:
        return _fact_bound(_at(item, field), path)
    if field.arity is Arity.LIST:
        return _too_many(_at(item, field), Bound.SCOPE_LIST, path, 'values', 'scope list')
    if field.arity in (Arity.SLOT, Arity.FACTS):
        facts = _at(item, field)
        if field.bound is None:
            raise RuntimeError(f'{field.attribute.name} has no bound in ATTRIBUTES.')
        owner = 'slot' if field.arity is Arity.SLOT else f'list of {field.attribute.value}'
        error = _too_many(facts, field.bound, path, 'facts', owner)
        for index, fact in enumerate(facts):
            error = error or _fact_bound(fact, f'{path}[{index}]')
        return error
    return ''  # OTHER: no list of its own here


def _object_bound(family: xs.Family, item: Mapping[str, Any], path: str) -> str:
    """The first bound one object breaks: its own citations and lists, then its attributes in ATTRIBUTES' order. A
    section's closing signatures take no count of their own (1.8 numbers none: only the cited units bound them), and
    each one's words take the words bound."""
    error = ''
    if family is Family.PERSON:
        error = _source_bound(item['name'], f'{path}.name')
    elif family is Family.SECTION:
        error = _source_bound(item['start'], f'{path}.start')
        for index, source in enumerate(item['end']):
            error = error or _source_bound(source, f'{path}.end[{index}]')
    elif family is Family.LESION:
        error = _source_bound(item['description'], f'{path}.description')
    elif family is Family.EVENT:
        anchor = item['anchor']
        error = (_words_error(anchor['kind_words'], f'{path}.anchor.kind_words')
                 or _words_error(anchor['status_words'], f'{path}.anchor.status_words')
                 or _too_many(item['restatements'], Bound.RESTATEMENTS, f'{path}.restatements', 'restatements',
                              'event'))
    for field in xs.ATTRIBUTES[family]:
        error = error or _field_bound(item, field, f'{path}.{field.attribute.value}')
    return error


def _cited(answer: Mapping[str, Any]) -> int:
    """How many unit ids the whole answer cites: every list of unit ids counted (sources, options' sources, names,
    starts, ends, descriptions, anchors, restatements, doubts)."""
    count = 0
    pending: list[Any] = [answer]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'units':
                    count += len(item)
                else:
                    pending.append(item)
        elif isinstance(value, list):
            pending.extend(value)
    return count


def bound_error(answer: Mapping[str, Any]) -> str:
    """The first bound of BOUNDS_2 a schema-valid answer breaks, named by count, or ''. In order: the top-level lists
    (1.8's order: events, sections, sessions, people, anatomy entries, lesions), the other dates and the doubts; then
    every object in the answer's order (the encounter, then each family), its citations and lists, each slot, each fact's
    sources and options and every words value; then each doubt's objects and readings; last, the unit ids cited in the
    whole answer. A source over 12 units is not here: that bound is item-level (I3)."""
    for family, bound in ((Family.EVENT, Bound.EVENTS), (Family.SECTION, Bound.SECTIONS),
                          (Family.SESSION, Bound.SESSIONS), (Family.PERSON, Bound.PEOPLE),
                          (Family.ANATOMY, Bound.ANATOMY), (Family.LESION, Bound.LESIONS)):
        count, limit = len(answer[family.value]), xs.BOUNDS_2[bound]
        if count > limit:
            return f'it lists {count:,} {_what(family)}, more than the {limit:,} this contract accepts'
    encounter = answer['encounter']
    for items, bound, path, label in ((encounter['other_dates'], Bound.OTHER_DATES, 'encounter.other_dates',
                                       'other dates'),
                                      (answer['doubts'], Bound.DOUBTS, 'doubts', 'doubts')):
        if len(items) > xs.BOUNDS_2[bound]:
            return (f'{path} lists {len(items):,} {label}, more than the {xs.BOUNDS_2[bound]:,} this contract '
                    'accepts')
    error = _fact_bound(encounter['date_of_service'], 'encounter.date_of_service')
    for index, other in enumerate(encounter['other_dates']):
        error = error or _fact_bound(other['role'], f'encounter.other_dates[{index}].role')
    error = error or _field_bound(encounter, xs.field(Family.ENCOUNTER, Attribute.DOCUMENTING_CLINICIAN),
                                  'encounter.documenting_clinician')
    for family in xs.Family:
        if family is Family.ENCOUNTER:
            continue
        for index, item in enumerate(answer[family.value]):
            error = error or _object_bound(family, item, f'{family.value}[{index}]')
    for index, doubt in enumerate(answer['doubts']):
        error = (error or _too_many(doubt['objects'], Bound.DOUBT_OBJECTS, f'doubts[{index}].objects', 'ids', 'doubt')
                 or _too_many(doubt['readings'], Bound.DOUBT_READINGS, f'doubts[{index}].readings', 'readings',
                              'doubt'))
    if error:
        return error
    cited, limit = _cited(answer), xs.BOUNDS_2[Bound.CITED_UNITS]
    if cited > limit:
        return f'it cites {cited:,} unit ids in all, more than the {limit:,} this contract accepts'
    return ''


# --- S1.4: the ids (DECISIONS D185) -----------------------------------------------------------------------------------

# (where, the value, the letters it may open with, what it is called): one id-valued place of the answer
_Held = tuple[str, Any, str, str]


def _shape(letters: str) -> str:
    """How an id of ``letters`` is written, for a refusal sentence (never the id itself: it is the model's text)."""
    named = letters if len(letters) == 1 else ', '.join(letters[:-1]) + ' or ' + letters[-1]
    return f'the letter {named} and then a number of at most 9 decimal digits with no leading zero'


def _units_held(node: Mapping[str, Any], path: str) -> Iterator[_Held]:
    """Each unit id one citation (a source, a name, a start, an anchor, a restatement, a doubt) cites."""
    for index, unit in enumerate(node['units']):
        yield f'{path}.units[{index}]', unit, UNIT_LETTER, 'a unit id'


def _sources_held(sources: list[Any], path: str) -> Iterator[_Held]:
    for index, source in enumerate(sources):
        yield from _units_held(source, f'{path}[{index}]')


def _fact_held(fact: Mapping[str, Any], path: str, refers: bool) -> Iterator[_Held]:
    """The ids one fact (or the date of service) holds, in its own order: its value when it ``refers`` to objects and is
    not '' (the value of a contradicted fact: S2 reads where it stands), its sources' units, then each option's value
    when it ``refers`` (an option is a value, never ''), and that option's sources' units."""
    if refers and fact['value'] != '':
        yield f'{path}.value', fact['value'], OBJECT_LETTERS, 'an id'
    yield from _sources_held(fact['sources'], f'{path}.sources')
    for index, option in enumerate(fact['options']):
        if refers:
            yield f'{path}.options[{index}].value', option['value'], OBJECT_LETTERS, 'an id'
        yield from _sources_held(option['sources'], f'{path}.options[{index}].sources')


def _field_held(item: Mapping[str, Any], field: xs.Field, path: str) -> Iterator[_Held]:
    """The ids one attribute of one object holds: its facts', or each member of an id list."""
    refers = field.refers_to is not None
    if field.arity is Arity.FACT:
        yield from _fact_held(_at(item, field), path, refers)
    elif field.arity in (Arity.SLOT, Arity.FACTS):
        for index, fact in enumerate(_at(item, field)):
            yield from _fact_held(fact, f'{path}[{index}]', refers)
    elif field.arity is Arity.LIST and refers:
        for index, value in enumerate(_at(item, field)):
            yield f'{path}[{index}]', value, OBJECT_LETTERS, 'an id'


def _held(answer: Mapping[str, Any]) -> Iterator[_Held]:
    """Every id-valued place of the answer but the objects' own ids, in the answer's order: the encounter's (the date of
    service's and each other date's units, the documenting clinician), then each family's objects in turn (each one's
    citations, then its attributes in ATTRIBUTES' order), then the doubts (each one's objects, then its units)."""
    encounter = answer['encounter']
    yield from _fact_held(encounter['date_of_service'], 'encounter.date_of_service', False)
    for index, other in enumerate(encounter['other_dates']):
        yield from _fact_held(other['role'], f'encounter.other_dates[{index}].role', False)
    yield from _field_held(encounter, xs.field(Family.ENCOUNTER, Attribute.DOCUMENTING_CLINICIAN),
                           'encounter.documenting_clinician')
    for family in xs.Family:
        if family is Family.ENCOUNTER:
            continue
        for index, item in enumerate(answer[family.value]):
            path = f'{family.value}[{index}]'
            if family is Family.PERSON:
                yield from _units_held(item['name'], f'{path}.name')
            elif family is Family.SECTION:
                yield from _units_held(item['start'], f'{path}.start')
                yield from _sources_held(item['end'], f'{path}.end')
            elif family is Family.LESION:
                yield from _units_held(item['description'], f'{path}.description')
            elif family is Family.EVENT:
                yield from _units_held(item['anchor'], f'{path}.anchor')
                for at, restatement in enumerate(item['restatements']):
                    yield from _units_held(restatement, f'{path}.restatements[{at}]')
            for field in xs.ATTRIBUTES[family]:
                yield from _field_held(item, field, f'{path}.{field.attribute.value}')
    for index, doubt in enumerate(answer['doubts']):
        for at, name in enumerate(doubt['objects']):
            yield f'doubts[{index}].objects[{at}]', name, OBJECT_LETTERS, 'an id'
        yield from _units_held(doubt, f'doubts[{index}]')


def id_error(answer: Mapping[str, Any]) -> str:
    """The first breach of D185's id grammar, or ''. First every object's own id, family by family: its family's letter
    and number (is_id), and unique in its family. Then every other id-valued place in the answer's order (_held): every
    reference and option of one, every member of an id list and every object a doubt names opens with one of the
    families' letters, and every cited unit id with 'S'. Where a well-formed id leads (no object, an object of another
    family, a unit the revision lacks) is item-level (I4, I1). The id itself is never repeated: it is the model's
    text."""
    for family in xs.Family:
        if family is Family.ENCOUNTER:
            continue
        key, first = family.value, dict[str, int]()
        for index, item in enumerate(answer[key]):
            value = item['id']
            if not is_id(value, family.letter):
                return f'{key}[{index}].id is not an id of {_what(family)}: {_shape(family.letter)}'
            if value in first:
                return f'two {_what(family)} share one id ({key}[{first[value]}] and {key}[{index}])'
            first[value] = index
    for path, value, letters, what in _held(answer):
        if not is_id(value, letters):
            return f'{path} is not {what}: {_shape(letters)}'
    return ''


# --- S1.5: the ISO shapes ----------------------------------------------------------------------------------------------


def date_error(answer: Mapping[str, Any]) -> str:
    """The first date whose value has no shape S1 admits, or '': the date of service, '' or a day, and each of its
    options, a day; an other date and an act's date, '' or a date at its precision, and each option of an act's date,
    a date at its precision."""
    when = answer['encounter']['date_of_service']
    days = [('encounter.date_of_service.value', when['value'], True)]
    days += [(f'encounter.date_of_service.options[{index}].value', option['value'], False)
             for index, option in enumerate(when['options'])]
    for path, value, empty in days:
        if not (iso_date(value) or (empty and value == '')):
            return f'a date is not YYYY-MM-DD ({path})'
    dated = [(f'encounter.other_dates[{index}].value', other['value'], True)
             for index, other in enumerate(answer['encounter']['other_dates'])]
    for index, event in enumerate(answer['events']):
        for at, fact in enumerate(event['date']):
            dated.append((f'events[{index}].date[{at}].value', fact['value'], True))
            dated += [(f'events[{index}].date[{at}].options[{side}].value', option['value'], False)
                      for side, option in enumerate(fact['options'])]
    for path, value, empty in dated:
        if not (iso_date(value) or partial_date(value) or (empty and value == '')):
            return f'a date is not YYYY-MM-DD, YYYY-MM or YYYY ({path})'
    return ''


# --- the item-level checks: S2, I1, I3's per-source bound, I4 ----------------------------------------------------------


def _ordered(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """``reasons`` once each, in the closed list's order."""
    found = set(reasons)
    return tuple(reason for reason in Reason if reason in found)


def _source(node: Mapping[str, Any]) -> Source:
    return Source(units=tuple(node['units']), words=node['words'], link=Link(node['link']))


def _option(node: Mapping[str, Any]) -> Option:
    return Option(value=node['value'], sources=tuple(_source(source) for source in node['sources']))


def _fact(node: Mapping[str, Any]) -> Fact:
    return Fact(state=FactState(node['state']), value=node['value'],
                qualifiers=tuple(Qualifier(qualifier) for qualifier in node['qualifiers']),
                sources=tuple(_source(source) for source in node['sources']),
                options=tuple(_option(option) for option in node['options']))


def _date_of_service(node: Mapping[str, Any]) -> DateOfService:
    return DateOfService(state=DateState(node['state']), value=node['value'],
                         sources=tuple(_source(source) for source in node['sources']),
                         options=tuple(_option(option) for option in node['options']))


@dataclass(slots=True)
class _Draft:
    """A fact while its findings are gathered."""
    key: FactKey
    fact: Fact | DateOfService
    reasons: set[Reason]
    sides: list[set[Reason]]


class _Items:
    """The item-level checks of one schema-valid answer within its bounds and ids (read's last step)."""

    def __init__(self, answer: dict[str, Any], unit_count: int) -> None:
        self.answer, self.unit_count = answer, unit_count
        self.ids: dict[xs.Family, frozenset[str]] = {
            family: frozenset(item['id'] for item in answer[family.value])
            for family in xs.Family if family is not Family.ENCOUNTER}

    # -- citations and references --

    def units(self, units: Iterable[str], *, need: bool, bounded: bool) -> set[Reason]:
        """I1 on cited unit ids, the per-source bound when ``bounded``, and, when ``need``, at least one unit."""
        cited = tuple(units)
        reasons: set[Reason] = set()
        if need and not cited:
            reasons.add(Reason.SHAPE_INCONSISTENT)
        if any(not unit_known(unit, self.unit_count) for unit in cited):
            reasons.add(Reason.UNIT_UNKNOWN)
        if bounded and len(cited) > xs.BOUNDS_2[Bound.SOURCE_UNITS]:
            reasons.add(Reason.SOURCE_TOO_LONG)
        return reasons

    def source(self, source: Source, *, need: bool = True) -> set[Reason]:
        return self.units(source.units, need=need, bounded=True)

    def reference(self, value: str, refers_to: xs.Family, family: xs.Family, owner: str) -> set[Reason]:
        """I4 on one id: it names an object of ``refers_to``, and not the object that holds it."""
        if value not in self.ids[refers_to] or (refers_to is family and value == owner):
            return {Reason.REFERENCE_INVALID}
        return set()

    # -- facts --

    def fact(self, key: FactKey, field: xs.Field, node: Mapping[str, Any]) -> _Draft:
        """S2, I1, the per-source bound and I4 on one fact."""
        fact = _fact(node)
        reasons: set[Reason] = set()
        sides: list[set[Reason]] = [set() for _ in fact.options]
        if fact.state is FactState.CONTRADICTED:
            values = [option.value for option in fact.options]
            if fact.value != '' or not fact.sources or len(values) < 2 or len(set(values)) != len(values):
                reasons.add(Reason.SHAPE_INCONSISTENT)
        elif fact.value == '' or not fact.sources or fact.options:
            reasons.add(Reason.SHAPE_INCONSISTENT)
        for source in fact.sources:
            reasons |= self.source(source)
        for side, option in zip(sides, fact.options):
            if option.value == '' or not option.sources:
                side.add(Reason.SHAPE_INCONSISTENT)
            for source in option.sources:
                side |= self.source(source)
        if field.refers_to is not None:
            if fact.state is not FactState.CONTRADICTED and fact.value != '':
                reasons |= self.reference(fact.value, field.refers_to, key.family, key.object)
            for side, option in zip(sides, fact.options):
                if option.value != '':
                    side |= self.reference(option.value, field.refers_to, key.family, key.object)
        return _Draft(key, fact, reasons, sides)

    def date_of_service(self, node: Mapping[str, Any]) -> _Draft:
        """The date of service, by S2's rule read for its own states: stated, a value and sources and no option;
        several, no value and two or more options of distinct dates, each with sources; not_stated, nothing."""
        when = _date_of_service(node)
        reasons: set[Reason] = set()
        values = [option.value for option in when.options]
        if when.state is DateState.STATED:
            shaped = when.value != '' and bool(when.sources) and not when.options
        elif when.state is DateState.SEVERAL:
            shaped = (when.value == '' and bool(when.sources) and len(values) >= 2
                      and len(set(values)) == len(values))
        else:
            shaped = when.value == '' and not when.sources and not when.options
        if not shaped:
            reasons.add(Reason.SHAPE_INCONSISTENT)
        for source in when.sources:
            reasons |= self.source(source)
        sides: list[set[Reason]] = []
        for option in when.options:
            side = {Reason.SHAPE_INCONSISTENT} if not option.sources else set()
            for source in option.sources:
                side |= self.source(source)
            sides.append(side)
        key = FactKey(Family.ENCOUNTER, '', Attribute.DATE_OF_SERVICE, 0)
        return _Draft(key, when, reasons, sides)

    def facts(self) -> list[_Draft]:
        """Every fact of the answer, checked, in the answer's order."""
        encounter = self.answer['encounter']
        drafts = [self.date_of_service(encounter['date_of_service'])]
        role = xs.field(Family.ENCOUNTER, Attribute.OTHER_DATES_ROLE)
        drafts += [self.fact(FactKey(Family.ENCOUNTER, '', role.attribute, index), role, other['role'])
                   for index, other in enumerate(encounter['other_dates'])]
        clinician = xs.field(Family.ENCOUNTER, Attribute.DOCUMENTING_CLINICIAN)
        drafts += [self.fact(FactKey(Family.ENCOUNTER, '', clinician.attribute, index), clinician, node)
                   for index, node in enumerate(_at(encounter, clinician))]
        for family in xs.Family:
            if family is Family.ENCOUNTER:
                continue
            for item in self.answer[family.value]:
                for field in xs.ATTRIBUTES[family]:
                    if field.arity is Arity.FACT:
                        drafts.append(self.fact(FactKey(family, item['id'], field.attribute, 0), field,
                                                _at(item, field)))
                    elif field.arity in (Arity.SLOT, Arity.FACTS):
                        drafts += [self.fact(FactKey(family, item['id'], field.attribute, index), field, node)
                                   for index, node in enumerate(_at(item, field))]
        self.acyclic(drafts)
        return drafts

    def acyclic(self, drafts: list[_Draft]) -> None:
        """I4: part_of, cause_event and part_of_session acyclic. An edge is a supported value or a contradicted fact's
        option, naming another object of the family; every fact with an edge on a cycle is reference_invalid (the side
        that carries it too)."""
        relations = ((Family.EVENT, Attribute.PART_OF), (Family.EVENT, Attribute.CAUSE_EVENT),
                     (Family.SESSION, Attribute.PART_OF_SESSION))
        for family, attribute in relations:
            edges: list[tuple[str, str, _Draft, int]] = []  # (from, to, the fact, its side or -1)
            for draft in drafts:
                if draft.key.family is not family or draft.key.attribute is not attribute:
                    continue
                fact = draft.fact
                if not isinstance(fact, Fact):
                    continue
                if fact.state is FactState.SUPPORTED:
                    edges.append((draft.key.object, fact.value, draft, -1))
                elif fact.state is FactState.CONTRADICTED:
                    edges += [(draft.key.object, option.value, draft, side)
                              for side, option in enumerate(fact.options)]
            graph: dict[str, set[str]] = {}
            for start, end, _, _ in edges:
                if end in self.ids[family] and end != start:
                    graph.setdefault(start, set()).add(end)
            for start, end, draft, side in edges:
                if end != start and end in self.ids[family] and start in _reachable(graph, end):
                    draft.reasons.add(Reason.REFERENCE_INVALID)
                    if side >= 0:
                        draft.sides[side].add(Reason.REFERENCE_INVALID)

    # -- the rest --

    def citations(self) -> list[ReadCitation]:
        found: list[ReadCitation] = []

        def cite(family: xs.Family, owner: str, cited: Cited, index: int, node: Mapping[str, Any], *,
                 need: bool = True, bounded: bool = True, is_source: bool = True) -> None:
            source = _source(node) if is_source else None
            reasons = self.units(node['units'], need=need, bounded=bounded)
            found.append(ReadCitation(family, owner, cited, index, tuple(node['units']), source, _ordered(reasons)))

        for item in self.answer['people']:
            cite(Family.PERSON, item['id'], Cited.NAME, 0, item['name'])
        for item in self.answer['sections']:
            cite(Family.SECTION, item['id'], Cited.START, 0, item['start'], need=False)
            for index, node in enumerate(item['end']):
                cite(Family.SECTION, item['id'], Cited.END, index, node)
        for item in self.answer['lesions']:
            cite(Family.LESION, item['id'], Cited.DESCRIPTION, 0, item['description'])
        for item in self.answer['events']:
            cite(Family.EVENT, item['id'], Cited.ANCHOR, 0, item['anchor'], is_source=False)
            for index, node in enumerate(item['restatements']):
                cite(Family.EVENT, item['id'], Cited.RESTATEMENT, index, node, bounded=False, is_source=False)
        return found

    def members(self) -> list[ReadMember]:
        found: list[ReadMember] = []
        for item in self.answer['events']:
            for field in xs.ATTRIBUTES[Family.EVENT]:
                if field.arity is not Arity.LIST:
                    continue
                for index, value in enumerate(_at(item, field)):
                    reasons: set[Reason] = set()
                    if field.refers_to is not None:
                        reasons = self.reference(value, field.refers_to, Family.EVENT, item['id'])
                    found.append(ReadMember(FactKey(Family.EVENT, item['id'], field.attribute, index), value,
                                            _ordered(reasons)))
        return found

    def doubt(self, index: int, node: Mapping[str, Any]) -> ReadDoubt:
        """S2's doubt shape, I1 on its units and I4 on its objects."""
        doubt = Doubt(about=DoubtAbout(node['about']), objects=tuple(node['objects']), units=tuple(node['units']),
                      basis=DoubtBasis(node['basis']), readings=tuple(node['readings']))
        reasons = self.units(doubt.units, need=True, bounded=False)
        objects: list[tuple[xs.Family, str]] = []
        for name in doubt.objects:
            bearers = [family for family, ids in self.ids.items() if name in ids]  # at most one family (D185)
            if len(bearers) != 1:
                reasons.add(Reason.REFERENCE_INVALID)  # names no object of the answer
            objects += [(family, name) for family in bearers if (family, name) not in objects]
        row = xs.DOUBT_ATTRIBUTES[doubt.about]
        if doubt.about is DoubtAbout.DATE_OF_SERVICE:
            if doubt.objects:
                reasons.add(Reason.SHAPE_INCONSISTENT)  # only the encounter carries it, and it has no id
            objects.append((Family.ENCOUNTER, ''))
        elif not doubt.objects:
            reasons.add(Reason.SHAPE_INCONSISTENT)  # it names nothing it doubts
        for family, _ in objects:
            if family not in row:
                reasons.add(Reason.SHAPE_INCONSISTENT)  # the object does not carry the attribute
            elif any(not self.reading(reading_, family, row[family]) for reading_ in doubt.readings):
                reasons.add(Reason.SHAPE_INCONSISTENT)  # a reading is not a value of that attribute
        ordered = _ordered(reasons)
        return ReadDoubt(index, doubt, tuple(objects), ordered, bool(ordered))

    def reading(self, value: str, family: xs.Family, named: tuple[Attribute, ...]) -> bool:
        """Whether ``value`` is a value of one of the attributes ``named`` on ``family``: a member's value of its
        enumeration, an id of the family it refers to, or a date at the precision the attribute admits - a day for the
        date of service (1.4; S1 admits nothing coarser for it, DECISIONS D200), a day, a month or a year for an act's
        date."""
        for attribute in named:
            field = xs.field(family, attribute)
            if field.values is not None and any(member.value == value for member in field.values):
                return True
            if field.refers_to is not None and value in self.ids[field.refers_to]:
                return True
            day_only = attribute is Attribute.DATE_OF_SERVICE
            if field.is_date and (iso_date(value) or (not day_only and partial_date(value))):
                return True
        return False

    def read(self) -> ReadAnswer:
        drafts = self.facts()
        facts = tuple(ReadFact(draft.key, draft.fact, _ordered(draft.reasons.union(*draft.sides)),
                               tuple(_ordered(side) for side in draft.sides)) for draft in drafts)
        doubts = tuple(self.doubt(index, node) for index, node in enumerate(self.answer['doubts']))
        return ReadAnswer(self.answer, self.unit_count, facts, tuple(self.citations()), tuple(self.members()), doubts)


def _reachable(graph: Mapping[str, set[str]], start: str) -> set[str]:
    """Every node reachable from ``start`` by one or more edges of ``graph``."""
    seen: set[str] = set()
    pending = list(graph.get(start, ()))
    while pending:
        node = pending.pop()
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return seen
