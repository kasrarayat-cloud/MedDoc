"""The strict reader of one Gemini answer (design/contract.md 3.3 and 4.5): read(answer_text) gives the parsed answer, or a
Refusal of the WHOLE answer.

The adapter owns the envelope (D13, FINAL 5.4) and hands this module the answer text of one accepted envelope: HTTP
200, modelVersion exactly gemini-4-argon, one candidate, finishReason STOP, no block reason, the text parts not marked
as thought. Its own refusals use stage ``envelope`` (refuse). Then, in this order, the first failure refuses the whole
answer, and nothing of it is read:

1. JSON, strictly (participants.reading.strict_json_text): a repeated key, NaN or Infinity, a number too large, NUL or a
   lone surrogate refuses it (stage ``json``).
2. The schema, by CPT Studio's own validator (participants.reading.schema_error against schema.LOCAL_SCHEMA): types,
   enumerations, every required field, no other field, ``sequence`` an integer and never a boolean (stage ``schema``).
   Gemini's responseSchema is a hint to the model, never trusted.
3. The bounds (schema.BOUNDS), each named by count and never truncated (stage ``bounds``).
4. The ids: every passage, lesion and event id is 1 to 24 letters, digits, '_', '.', ':' or '-', beginning with a letter
   or a digit, and unique in its list, since an ambiguous reference cannot be bound (stage ``ids``).
5. The ISO shapes: the date of service and every other date of this encounter (role this_encounter: a date-of-service
   candidate) is "" or a real YYYY-MM-DD date; an other date of any other role is "", a real YYYY-MM-DD date, or a real
   month or year, YYYY-MM or YYYY, where the document gives one with no day ('January 2024', 'in 2017') (stage ``schema``:
   the format is part of the answer's shape; the validator's keyword subset cannot state it). The partial shapes were
   admitted after the FRESH recording (S16): Gemini writes a history date at its own precision, and a refusal of the
   whole answer for it refused 27 of 69 answers.

Everything later is item-level and never refuses the answer: an id cited but not defined, an attribute not permitted on
its event, an inconsistent combination, an unlocated quote. Normalization records each as a problem and a state.

A refusal's reason is CPT Studio's own sentence. It names places by schema path and position and values by count, and
never repeats the model's text (I9; participants.reading quotes nothing a model wrote either).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Union

from studio import interpretation
from studio.interpretation import schema
from studio.participants import reading

REFUSED = 'The interpretation was not used: '  # every refusal sentence starts so; the reason follows
STAGES = ('envelope', 'json', 'schema', 'bounds', 'ids')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,23}')
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_PARTIAL_DATE = re.compile(r'[0-9]{4}(?:-[0-9]{2})?')
# The top-level lists and the encounter's lists, with what one entry is called.
_TOP_LISTS = (('passages', 'passages'), ('lesions', 'lesions'), ('events', 'events'),
              ('open_questions', 'open questions'))
_ENCOUNTER_LISTS = (('team', 'team members'), ('anatomy', 'anatomy entries'), ('reach', 'reach entries'),
                    ('visit_facts', 'visit facts'))
_WORDS_FIELDS = frozenset({'words', 'site_words', 'size_words'})
_QUESTION_LISTS = frozenset({'events', 'lesions', 'passages'})


@dataclass(frozen=True)
class Refusal:
    """A whole answer refused (contract 4.5): none of it is read, and the attempt is a definite failure. ``reason`` is CPT
    Studio's sentence, starting with REFUSED; ``stage`` names the step that refused it. Persisted as an EventInventory
    row in state ``refused`` (store.refused_row). Made by ``refuse``."""
    stage: str
    reason: str
    refused: bool = True

    def __post_init__(self):
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


def read(answer: str) -> Union[dict, Refusal]:
    """The answer, parsed and checked as the module docstring says, or the Refusal of all of it. The parsed answer is
    returned exactly as parsed: nothing is repaired, coerced, truncated or dropped. RuntimeError when LOCAL_SCHEMA no
    longer matches its pin (a changed schema needs a new INTERPRETATION_VERSION)."""
    check_pin()
    if not isinstance(answer, str):
        return refuse('json', 'there is no answer text')
    try:
        parsed = reading.strict_json_text(answer)
    except reading.JSONRefused as exc:
        return refuse('json', f'the answer {exc}')
    error = reading.schema_error(parsed, schema.LOCAL_SCHEMA, 'the interpretation')
    if error:
        return refuse('schema', f'the answer breaks the interpretation schema: {error}')
    error = bound_error(parsed)
    if error:
        return refuse('bounds', error)
    error = id_error(parsed)
    if error:
        return refuse('ids', error)
    error = date_error(parsed)
    if error:
        return refuse('schema', error)
    return parsed


def check_pin() -> None:
    """RuntimeError unless LOCAL_SCHEMA is byte for byte what INTERPRETATION_VERSION pins."""
    if schema.sha256_of(schema.LOCAL_SCHEMA) != interpretation.LOCAL_SCHEMA_SHA256:
        raise RuntimeError(f'The local schema no longer matches the {interpretation.INTERPRETATION_VERSION} pin; a '
                           'changed schema needs a new INTERPRETATION_VERSION.')


# --- 3: the bounds -----------------------------------------------------------------------------------------------------

def bound_error(answer: dict) -> str:
    """The first bound a schema-valid answer breaks, named by count, or ''. In order: the top-level lists, the
    encounter's lists, each passage's text, then every item in document order (an attribute's or a lesion's passage ids,
    an event's contradictions, a scope's targets, an open question's ids, every words field, every sequence), and last
    the passage ids cited in the whole answer."""
    bounds = schema.BOUNDS
    for key, label in _TOP_LISTS:
        count = len(answer[key])
        if count > bounds[key]:
            return f'it lists {count:,} {label}, more than the {bounds[key]:,} this contract accepts'
    encounter = answer['encounter']
    for key, label in _ENCOUNTER_LISTS:
        count = len(encounter[key])
        if count > bounds[key]:
            return f'encounter.{key} lists {count:,} {label}, more than the {bounds[key]:,} this contract accepts'
    count = len(encounter['date_of_service']['other_dates'])
    if count > bounds['other_dates']:
        return (f'encounter.date_of_service.other_dates lists {count:,} other dates, more than the '
                f'{bounds["other_dates"]:,} this contract accepts')
    least, most = bounds['passage_chars']
    for index, passage in enumerate(answer['passages']):
        size = len(passage['text'])
        if size < least:
            return f'passages[{index}].text is empty; a passage has at least {least:,} character'
        if size > most:
            return f'passages[{index}].text has {size:,} characters, more than the {most:,} one passage may have'
    cited = 0
    pending = [(answer[key], key, key) for key in reversed(('encounter', 'lesions', 'events', 'open_questions'))]
    while pending:
        value, path, field = pending.pop()
        if isinstance(value, dict):
            pending.extend((item, f'{path}.{key}', key) for key, item in reversed(value.items()))
        elif isinstance(value, list):
            error = _list_error(value, path, field)
            if error:
                return error
            if field == 'passages':
                cited += len(value)
            pending.extend((item, f'{path}[{index}]', field) for index, item in reversed(list(enumerate(value))))
        elif isinstance(value, str):
            if field in _WORDS_FIELDS and len(value) > bounds['words_chars']:
                return (f'{path} has {len(value):,} characters, more than the {bounds["words_chars"]:,} one words '
                        'field may have')
        elif field == 'sequence':
            least, most = bounds['sequence']
            if not least <= value <= most:
                return f'{path} is {_number(value)}, outside {least} to {most}'
    if cited > bounds['cited_passages']:
        return (f'it cites {cited:,} passage ids in all, more than the {bounds["cited_passages"]:,} this contract '
                'accepts')
    return ''


def _list_error(value: list, path: str, field: str) -> str:
    """The bound one list inside an item breaks, named by count, or ''."""
    bounds = schema.BOUNDS
    if path.startswith('open_questions[') and field in _QUESTION_LISTS:
        limit, label, owner = bounds['question_ids'], 'ids', 'open question list'
    elif field == 'passages':
        limit, label, owner = bounds['attribute_passages'], 'passage ids', 'passages list'
    elif field == 'contradicts':
        limit, label, owner = bounds['contradicts'], 'contradictions', 'event'
    elif field == 'targets':
        limit, label, owner = bounds['scope_targets'], 'targets', 'scope'
    else:
        return ''
    if len(value) > limit:
        return f'{path} lists {len(value):,} {label}, more than the {limit:,} one {owner} may have'
    return ''


def _number(value: int) -> str:
    """An integer the model wrote, for a refusal: as written up to a million, else only its side of the range."""
    if -1_000_000 < value < 1_000_000:
        return f'{value:,}'
    return 'over a million' if value > 0 else 'below minus a million'


# --- 4: the ids --------------------------------------------------------------------------------------------------------

def id_error(answer: dict) -> str:
    """The first passage, lesion or event id that is not an id or that repeats one in its list, or ''. The id itself is
    never repeated: it is the model's text."""
    for key, label in _TOP_LISTS[:3]:
        first = {}
        for index, item in enumerate(answer[key]):
            value = item['id']
            if not ID.fullmatch(value):
                return (f'{key}[{index}].id is not an id: 1 to 24 letters, digits, "_", ".", ":" or "-", beginning '
                        'with a letter or a digit')
            if value in first:
                return f'two {label} share one id ({key}[{first[value]}] and {key}[{index}])'
            first[value] = index
    return ''


# --- 5: the ISO shapes -------------------------------------------------------------------------------------------------

def date_error(answer: dict) -> str:
    """The first date whose value has no shape rule 5 admits, or '': the date of service, or an other date of this
    encounter, that is neither "" nor a real YYYY-MM-DD date; an other date of another role that is neither "", a real
    YYYY-MM-DD date nor a real YYYY-MM or YYYY."""
    when = answer['encounter']['date_of_service']
    places = [('encounter.date_of_service.value', when['value'], False)]
    places += [(f'encounter.date_of_service.other_dates[{index}].value', item['value'], item['role'] != 'this_encounter')
               for index, item in enumerate(when['other_dates'])]
    for path, value, partial in places:
        if not value or iso_date(value):
            continue
        if not partial:
            return f'a date is not YYYY-MM-DD ({path})'
        if not partial_date(value):
            return f'a date is not YYYY-MM-DD, YYYY-MM or YYYY ({path})'
    return ''


def partial_date(value: str) -> bool:
    """Whether ``value`` is a real month or year written YYYY-MM or YYYY in ASCII digits (year 1 or later)."""
    if not _PARTIAL_DATE.fullmatch(value):
        return False
    try:
        date(int(value[:4]), int(value[5:7]) if len(value) == 7 else 1, 1)
    except ValueError:
        return False
    return True


def iso_date(value: str) -> bool:
    """Whether ``value`` is a real calendar date written YYYY-MM-DD in ASCII digits."""
    if not _DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True
