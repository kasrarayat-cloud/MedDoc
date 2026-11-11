"""The gemini-context@1 facts and the gemini-routing@1 stand-in, derived from one event inventory (design/FINAL.md 3.1, 4.3,
6.4, 6.5 and 6.10; design/contract.md 8.1-8.3; DECISIONS D1-D3, D6, D8): pure, with no text read for meaning, no network
and no legacy call. analyze records them, and every context save re-derives them over the FROZEN inventory (D8).

``derive(inventory, user_values)`` gives:
- ``facts``: the context record's facts in the legacy Fact shape {name, value, origin, evidence, note} (types.Fact, as
  jobs.context_facts reads them) - ``service_date`` also carries ``state``, the member_date_state row of contract 8.2
  (from_jsonable ignores the extra key, and so does the old image). The held rows write the legacy note texts
  (dates.member_date_state chooses them), so the one shared context_facts.is_member_conflict holds the encounter in both
  images; several dates with no member value write the document conflict (DOCUMENT_CONFLICT_NOTE listing the verified
  candidates), so context_facts.documented_values reads them. ``setting``, ``billing_context`` and ``patient_status``
  come only from member values (D3): taken as the legacy user Fact, else missing with the legacy missing note.
- ``document_date``: the document's own date before the member's value, in the shape answers.py reads
  (gi/context.document_service_date_fact's: origin, value, single, values, asked, quote, evidence), from the inventory's
  date attribute.
- ``effective``: the effective date of service (ISO) or None - Corti's date and every dated check's (D2).
- ``member_date``: the dates.MemberDate row (its as_record() is Assessment.interpretation's member_date_state).

``routing_stand_in(inventory, effective_date, ...)`` is the derived RoutingRun record (FINAL 4.3): a version, no document
kind, one finding per family the inventory's events name - with a status read from those events' VERIFIED attributes and
no mention, fact or missing entry - and the inventory's id and sha256. Nothing reads it as a reading: the operator console
labels it derived, the old image reads it after a rollback, and persist_assessment's same-revision guard compares it.

Imports nothing from studio.gi (FINAL 3.1: dates, context_facts; the legacy constants it needs are copied and pinned
equal by tests/test_interpretation_facts.py through a test-only import).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Optional

from studio.interpretation import ROUTING_VERSION, dates, lexicon, literals, verify
from studio.types import CONTEXT_FACTS, Fact

# Copied from studio/gi/context.py (SETTINGS, BILLING_CONTEXTS, PATIENT_STATUSES, MISSING_NOTES) and pinned equal: the
# values a member may enter, and the missing notes the legacy context writes.
SETTINGS = ('office', 'hospital_outpatient', 'asc', 'inpatient', 'emergency', 'telehealth')
BILLING_CONTEXTS = ('professional', 'facility')
PATIENT_STATUSES = ('new', 'established')
ALLOWED = {'setting': SETTINGS, 'billing_context': BILLING_CONTEXTS, 'patient_status': PATIENT_STATUSES}
MISSING_NOTES = {
    'service_date': 'No labelled date of service is documented.',
    'setting': 'No place of service or care setting is documented.',
    'billing_context': 'No explicit professional or facility billing statement is documented.',
    'patient_status': 'New or established patient status is not documented.',
}
MEMBER_FACTS = ('setting', 'billing_context', 'patient_status')  # D3: member values only on the new path


@dataclass(frozen=True)
class Derived:
    """What derive() gives (module docstring)."""
    facts: dict
    document_date: dict
    effective: Optional[str]
    member_date: dates.MemberDate


def content(inventory) -> tuple[dict, dict]:
    """(events, encounter_facts) of an inventory: a store.StoredInventory (whose properties raise on a refused row), a
    normalize.Inventory, or a mapping with those two keys. Anything else is a programming error."""
    if isinstance(inventory, Mapping):
        return inventory['events'], inventory['encounter_facts']
    return inventory.events, inventory.encounter_facts


def _span(record: Mapping) -> dict:
    return {'start': record['start'], 'end': record['end'], 'text': record['text']}


def _passages(events: Mapping) -> dict:
    return {record['id']: record for record in events.get('passages') or ()}


def _valid(name: str, value: str) -> bool:
    if name == 'service_date':
        return literals.iso_date(value) is not None
    return value in ALLOWED[name]


def derive(inventory, user_values: Optional[Mapping] = None) -> Derived:
    """The gemini-context@1 facts of ``inventory`` with the encounter's member values (module docstring). Unknown names,
    values that are not strings, and values that are not valid for their fact are refused (ValueError), as the legacy
    merge refuses them."""
    events, encounter = content(inventory)
    given = dict(user_values or {})
    for name, raw in given.items():
        if name not in CONTEXT_FACTS:
            raise ValueError(f'{name!r} is not an encounter context fact.')
        if not isinstance(raw, str):
            raise ValueError(f'{name} must be a string.')
        if raw.strip() and not _valid(name, raw.strip()):
            raise ValueError(f'{raw.strip()!r} is not a valid {name}.')
    passages = _passages(events)
    row = dates.member_date_state(encounter['date_of_service'], given.get('service_date'), passages)
    facts = {'service_date': {'name': 'service_date', 'value': row.effective if not row.hold else None,
                              'origin': row.origin, 'evidence': [dict(span) for span in row.evidence],
                              'note': row.note, 'state': row.state}}
    if facts['service_date']['origin'] in ('missing', 'conflict'):
        facts['service_date']['value'] = None
    if row.origin == dates.MISSING and not row.note and encounter['date_of_service']['state'] == 'not_stated':
        facts['service_date']['note'] = MISSING_NOTES['service_date']
    for name in MEMBER_FACTS:
        value = (given.get(name) or '').strip()
        if value:
            facts[name] = {'name': name, 'value': value, 'origin': 'user', 'evidence': [], 'note': dates.USER_NOTE}
        else:
            facts[name] = {'name': name, 'value': None, 'origin': 'missing', 'evidence': [], 'note': MISSING_NOTES[name]}
    return Derived(facts=facts, document_date=document_date(inventory), effective=row.effective if not row.hold else None,
                   member_date=row)


def context_of(facts: Mapping) -> dict:
    """{name: types.Fact} of stored or derived facts (jobs.context_facts' reading; the ``state`` key is not a field)."""
    out = {}
    for name, value in (facts or {}).items():
        evidence = tuple(_fact_span(span) for span in value.get('evidence') or ())
        out[name] = Fact(name=value.get('name', name), value=value.get('value'), origin=value.get('origin', 'missing'),
                         evidence=evidence, note=value.get('note', '') or '')
    return out


def _fact_span(span: Mapping):
    from studio.types import Span

    return Span(start=span['start'], end=span['end'], text=span['text'])


def document_date(inventory) -> dict:
    """The document's own date of service before any member value (module docstring), in the shape answers.py reads.
    ``single`` only where the document gives one verified date; ``values`` the dates the document itself offers as an
    answer (that date, or the verified candidates of several); ``quote`` the date's own words, else its first located
    passage, for a single date only."""
    events, encounter = content(inventory)
    record = encounter['date_of_service']
    passages = _passages(events)
    own = []
    if record.get('words'):
        own.append(_span(record['words']))
    for pid in record.get('passages') or ():
        passage = passages.get(pid)
        if passage and passage.get('state') != 'unlocated' and passage.get('spans'):
            own.append(_span(passage['spans'][0]))
    value = record['value'] if record['state'] == 'stated' and record['verified'] and record['value'] else None
    candidates = list(record.get('candidates') or ()) if record['state'] == 'several' else []
    if value:
        origin, values = 'document', [value]
    elif candidates:
        origin, values = 'conflict', candidates
    else:
        origin, values = 'missing', []
    return {'origin': origin, 'value': value, 'single': bool(value), 'values': values, 'asked': False,
            'quote': own[0] if value and own else None, 'evidence': own}


# --- the same date of service (ADJUDICATION C-3) -----------------------------------------------------------------------

ON, OFF, UNDATABLE = 'on', 'off', 'undatable'
# The words that place an act on the date of service itself, read in its time attribute's OWN words only (EB1): the
# event's own statement that it was done today ("earlier today", "this morning"), never a scan of a passage.
SAME_DAY_WORDS = ('today', 'this morning', 'this afternoon', 'this evening', 'tonight', 'same day', 'same date')


def _words_of(attribute: Mapping) -> str:
    words = attribute.get('words') if isinstance(attribute, Mapping) else None
    return words['text'] if isinstance(words, Mapping) else ''


def _same_day_word(text: str) -> bool:
    if not text:
        return False
    folded = ' ' + ' '.join(lexicon.fold(text).replace('-', ' ').split()) + ' '
    return any(f' {word} ' in folded for word in SAME_DAY_WORDS)


# DECISIONS D109 (the round-4 refutation, finding 14): the same-date frames (lexicon.SAME_DAY_FRAMES), read WHOLE as D54
# reads a current time's words (lexicon.current_frame): folded, the punctuation and whitespace at the edges stripped
# (lexicon._FRAME_EDGES: every character that is not alphanumeric), split at commas, semicolons and a standalone " and "
# (lexicon._FRAME_JOINS), each part stripped - the same split, written here without a pattern and pinned equal to
# lexicon's by tests/test_interpretation_r4_em_same_day.py.
_SAME_DAY_FRAMES = frozenset(lexicon.fold(frame) for frame in lexicon.SAME_DAY_FRAMES)


def _frame_parts(text: str) -> list:
    folded = lexicon.fold(text)
    start, end = 0, len(folded)
    while start < end and not folded[start].isalnum():
        start += 1
    while end > start and not folded[end - 1].isalnum():
        end -= 1
    pieces = [piece for part in folded[start:end].replace(';', ',').split(',') for piece in part.split(' and ')]
    return [piece.strip() for piece in pieces]


def _same_day_frame(text: str) -> bool:
    """D109: whether a time's own words are made only of whole same-date frames: "Earlier in the day", "earlier that
    day", "Earlier in the morning", "later in the day, earlier today"; never "earlier in the day, before her visit"."""
    parts = [part for part in _frame_parts(text or '') if part]
    return bool(parts) and all(part in _SAME_DAY_FRAMES for part in parts)


def day_of(event: Mapping, effective) -> str:
    """Whether an event is ON the date of service, OFF it, or UNDATABLE (ADJUDICATION C-3: procedure_day is by date of
    service). ON: a usable current_encounter time; or time words whose date literals are all at day precision and equal
    to the effective date; or time words that say so (SAME_DAY_WORDS: "earlier today"; DECISIONS D109: or words made
    only of whole same-date frames, lexicon.SAME_DAY_FRAMES - "earlier in the day", "Earlier in the morning" - whatever
    time Gemini gives, earlier_encounter included; DECISIONS D112: frames anchored to today only, never the anaphoric
    "Earlier that day", which names whatever day the sentence before it names). OFF: a usable earlier or future time
    whose words place it on no such day. UNDATABLE: a time that is not usable (unknown, unverified, open, discarded) and
    whose words place it on no such day - "any event whose date is unresolved" (C-3); combination.procedure_day reads
    which of those an act's own time value makes a question (DECISIONS D111). ``effective``: the effective date (a
    date, an ISO string or None); with none, a date literal places nothing."""
    time = event.get('time') or {}
    text = _words_of(time)
    if verify.usable(time) and time.get('value') == 'current_encounter':
        return ON
    service = _as_date(effective)
    found = [(item.get('value'), item.get('precision')) for item in ((time.get('literals') or {}).get('dates') or ())]
    if service is not None and found and all(precision == literals.DAY and literals.iso_date(value) == service
                                             for value, precision in found):
        return ON
    if (_same_day_word(text) or _same_day_frame(text)) and not found:
        return ON
    if verify.usable(time) and time.get('value') in ('earlier_encounter', 'future'):
        return OFF
    return UNDATABLE


def _as_date(value) -> Optional[date]:
    if value is None or (isinstance(value, date) and not hasattr(value, 'hour')):
        return value
    return literals.iso_date(value) if isinstance(value, str) else None


# --- the routing stand-in (FINAL 4.3) ----------------------------------------------------------------------------------

def _status(event: Mapping, effective) -> str:
    """A family status (types.SERVICE_STATUSES) read from one event's verified attributes; '' for an event that states
    nothing usable."""
    status, time = event.get('status') or {}, event.get('time') or {}
    value = status.get('value')
    if value == 'uncertain' or not verify.usable(status):
        return 'uncertain' if value in ('performed', 'attempted_not_completed', 'uncertain') else ''
    day = day_of(event, effective)
    if value in verify.POSITIVE:
        if day == ON:
            return 'performed' if value == 'performed' else 'incomplete'
        if day == OFF:
            return 'planned' if time.get('value') == 'future' else 'historical'
        return 'uncertain'
    if value == 'planned':
        return 'planned'
    if value == 'not_performed':
        return 'negated'
    return ''


RANK = {'performed': 0, 'incomplete': 1, 'uncertain': 2, 'planned': 3, 'historical': 4, 'negated': 5, 'cancelled': 6}


def routing_stand_in(inventory, effective_date, *, inventory_id: str = '', inventory_sha256: str = '') -> dict:
    """The gemini-routing@1 stand-in for ``effective_date`` (module docstring): {version, document_kind: '', findings:
    [{family, status, mentions: [], facts: [], missing: []}], inventory, inventory_sha256}. One finding per family an
    event names, in the families' order, its status the strongest its events give (performed first)."""
    events, _ = content(inventory)
    found: dict = {}
    for event in events.get('events') or ():
        family = event.get('family') or ''
        if not family:
            continue
        status = _status(event, effective_date)
        if status and (family not in found or RANK[status] < RANK[found[family]]):
            found[family] = status
    order = {family: index for index, family in enumerate(lexicon.FAMILY_ORDER)}
    findings = [{'family': family, 'status': found[family], 'mentions': [], 'facts': [], 'missing': []}
                for family in sorted(found, key=lambda value: (order.get(value, len(order)), value))]
    return {'version': ROUTING_VERSION, 'document_kind': '', 'findings': findings, 'inventory': str(inventory_id or ''),
            'inventory_sha256': str(inventory_sha256 or '')}
