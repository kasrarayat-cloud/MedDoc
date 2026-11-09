"""The date of service against a member's entered date (design/contract.md 8.1-8.2; design/FINAL.md 4.3, 6.4-6.5 and 6.10;
DECISIONS D1, D2 and D8): ``member_date_state(date_of_service, member_value)``, pure, read by analyze and by every context
save, with no text and nothing sent (D8: a save re-applies the member's value onto the FROZEN inventory).

The precedence, top to bottom; the first row that applies decides (contract 8.2):

| document side | member value M | state | hold | effective date |
|---|---|---|---|---|
| any | empty | no_member_value | no | the verified, unopened stated value, else none |
| stated, verified | M = value | agrees | no | value; the origin stays document |
| any | M a verified birth date, not the stated value | conflict_birth | YES | none |
| any | M a verified other_occurrence or other_document date, not the stated value | conflict_elsewhere | YES | none |
| stated, verified | M differs | conflict_differs | YES | none |
| several, verified candidates | M among them | settles | no | M (origin user) |
| several, verified candidates | M not among them | conflict_listed | YES | none |
| stated unverified or opened; several with no verified candidate | M among the readings | settles | no | M |
| the same | otherwise, the document side quotable | conflict_unverifiable | YES | none |
| the same, with no own words or located passage | otherwise | supplies | no | M (origin user) |
| not_stated | M | supplies | no | M (origin user) |

Two refinements of the contract's table, each toward the member's answer standing only where the document gives nothing
to compare it with, as merge_user_values does (gi/context.py:3436-3437: a documented fact with no evidence limits no
answer): a ``several`` date with no verified candidate is judged by its readings as an unverified stated date is (with
no candidate to choose, conflict_listed could never be settled); and an unverified date with no words or located
passage of its own holds nothing a member's date could be compared with or settled by, so the member's date supplies it.
Only VERIFIED other dates take part (contract 8.1: an unverified other date is kept with its reason and used in no
comparison).

What each row writes (FINAL 4.3; contract 8.2), so the gemini-context@1 record's service_date carries the legacy Fact shape
plus its ``state``:
- the held rows write the legacy note text - USER_BIRTH_NOTE, USER_ELSEWHERE_NOTE or USER_CONFLICT_NOTE, formatted as
  merge_user_values formats them (the documented value; the candidates joined by " or "; up to three quoted spans,
  whitespace collapsed, cut at 60 characters) - so the one shared is_member_conflict holds the encounter in both images,
  and a rollback keeps every hold. The constants are studio.context_facts' own objects (the re-homed legacy constants);
- a member's date that is taken (supplies, settles) is the legacy user Fact: origin ``user``, no evidence, USER_NOTE;
- agrees keeps the document's own origin (the trace's provenance defect, a document date recorded as the member's, is not
  repeated); several with no member value is the document conflict (DOCUMENT_CONFLICT_NOTE listing the candidates, so
  documented_values reads them); not_stated with no member value is missing, with the legacy missing note.
The evidence is the date's own spans (its words, else its located passages), plus the spans of the birth or elsewhere
dates for those rows.

Corti's date (D2): the member's date when the state is supplies, settles or agrees; else the verified stated value; with
neither, no date. A held state sends nothing. "Use the document date" is offered on a held row whose document side is
stated and verified.

Pure and Django-free; imports nothing from studio.gi (FINAL 3.1).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Optional

from studio.context_facts import DOCUMENT_CONFLICT_NOTE, USER_BIRTH_NOTE, USER_CONFLICT_NOTE, USER_ELSEWHERE_NOTE
from studio.interpretation import literals

NO_MEMBER_VALUE = 'no_member_value'
AGREES = 'agrees'
CONFLICT_BIRTH = 'conflict_birth'
CONFLICT_ELSEWHERE = 'conflict_elsewhere'
CONFLICT_DIFFERS = 'conflict_differs'
SETTLES = 'settles'
CONFLICT_LISTED = 'conflict_listed'
CONFLICT_UNVERIFIABLE = 'conflict_unverifiable'
SUPPLIES = 'supplies'
STATES = (NO_MEMBER_VALUE, AGREES, CONFLICT_BIRTH, CONFLICT_ELSEWHERE, CONFLICT_DIFFERS, SETTLES, CONFLICT_LISTED,
          CONFLICT_UNVERIFIABLE, SUPPLIES)
HELD = frozenset({CONFLICT_BIRTH, CONFLICT_ELSEWHERE, CONFLICT_DIFFERS, CONFLICT_LISTED, CONFLICT_UNVERIFIABLE})
TAKEN = frozenset({SUPPLIES, SETTLES, AGREES})  # the member's date is the effective date (and Corti's, D2)
DOCUMENT, USER, CONFLICT, MISSING = 'document', 'user', 'conflict', 'missing'

# The legacy notes that live only in studio/gi/context.py (its USER_NOTE and MISSING_NOTES['service_date']), copied here
# and pinned equal to them by tests/test_interpretation_dates.py through a test-only import, so no gi.context code runs.
USER_NOTE = 'Supplied by a workspace member as encounter metadata; not clinical documentation.'
MISSING_NOTE = 'No labelled date of service is documented.'
ELSEWHERE_ROLES = ('other_occurrence', 'other_document')
QUOTED = 3  # spans quoted in a note (merge_user_values)
QUOTE_CHARS = 60  # characters of each


@dataclass(frozen=True)
class MemberDate:
    """One member_date_state row and what it writes: ``state`` (STATES), whether it HOLDS the encounter, the effective
    date (ISO, or None), the record's origin, note and evidence (spans), the document's verified stated value, the
    member's value as entered (stripped), and whether "use the document date" is offered."""
    state: str
    hold: bool
    effective: Optional[str]
    origin: str
    note: str
    evidence: tuple
    document_value: Optional[str]
    member_value: str
    offer_document_date: bool

    @property
    def corti_date(self) -> Optional[str]:
        """The date Corti's request carries (D2): the effective date of a row that does not hold; none when held."""
        return None if self.hold else self.effective

    def as_record(self) -> dict:
        """The row as plain JSON (Assessment.interpretation's member_date_state; the context record's ``state``)."""
        return {'state': self.state, 'hold': self.hold, 'effective': self.effective, 'origin': self.origin,
                'note': self.note, 'evidence': [dict(span) for span in self.evidence],
                'document_value': self.document_value, 'member_value': self.member_value,
                'offer_document_date': self.offer_document_date, 'corti_date': self.corti_date}


def _span(span: Mapping) -> dict:
    return {'start': span['start'], 'end': span['end'], 'text': span['text']}


def _own_spans(date_of_service: Mapping, passages) -> list:
    """The date's own spans: its words, else the first place of each of its located passages."""
    if date_of_service.get('words'):
        return [_span(date_of_service['words'])]
    places = []
    for pid in date_of_service.get('passages') or ():
        record = passages.get(pid)
        if record and record.get('state') != 'unlocated' and record.get('spans'):
            places.append(_span(record['spans'][0]))
    return places


def quoted(spans: Sequence[Mapping]) -> str:
    """Up to three spans as merge_user_values quotes evidence in a note: each “…”, whitespace collapsed, cut at 60."""
    return ', '.join('“' + ' '.join(span['text'].split())[:QUOTE_CHARS] + '”' for span in spans[:QUOTED])


def _verified_others(date_of_service: Mapping, roles, value: str) -> list:
    others = date_of_service.get('others') or {}
    return [entry for role in roles for entry in others.get(role) or ()
            if entry.get('verified') and entry.get('value') == value and entry.get('words')]


def _passage_map(passages) -> dict:
    if isinstance(passages, Mapping):
        return dict(passages)
    return {record['id']: record for record in passages or ()}


def member_date_state(date_of_service: Mapping, member_value, passages=()) -> MemberDate:
    """The member_date_state row (module docstring) of the inventory's ``date_of_service`` (encounter_facts, contract
    8.1) and the member's entered date (a YYYY-MM-DD string; None or blank for none). ``passages`` are the inventory's
    passages (a list of records, or {id: record}), read only to quote the date's own located passages and to tell
    whether it has any. TypeError for a member value that is no string, ValueError for one that is no date (as
    merge_user_values refuses it)."""
    if member_value is not None and not isinstance(member_value, str):
        raise TypeError('A member value is a string.')
    member = (member_value or '').strip()
    state = date_of_service['state']
    verified = date_of_service['value'] if (state == 'stated' and date_of_service['verified']
                                           and date_of_service['value']) else None
    candidates = list(date_of_service.get('candidates') or ())
    own = _own_spans(date_of_service, _passage_map(passages))

    def row(name: str, *, effective=None, origin: str, note: str = '', evidence=()) -> MemberDate:
        held = name in HELD
        return MemberDate(state=name, hold=held, effective=effective, origin=origin, note=note,
                          evidence=tuple(evidence), document_value=verified, member_value=member,
                          offer_document_date=held and verified is not None)

    if not member:
        if verified:
            return row(NO_MEMBER_VALUE, effective=verified, origin=DOCUMENT, evidence=own)
        if state == 'several' and candidates:
            return row(NO_MEMBER_VALUE, origin=CONFLICT, evidence=own,
                       note=DOCUMENT_CONFLICT_NOTE + ', '.join(candidates) + '.')
        return row(NO_MEMBER_VALUE, origin=MISSING, evidence=own, note=MISSING_NOTE if state == 'not_stated' else '')
    if literals.iso_date(member) is None:
        raise ValueError('A member value for the date of service is a YYYY-MM-DD date.')
    if verified and member == verified:
        return row(AGREES, effective=verified, origin=DOCUMENT, evidence=own)
    births = _verified_others(date_of_service, ('birth',), member)
    if births:
        spans = [_span(entry['words']) for entry in births]
        return row(CONFLICT_BIRTH, origin=CONFLICT, evidence=own + spans,
                   note=USER_BIRTH_NOTE.format(user=member, document=quoted(spans)))
    elsewhere = _verified_others(date_of_service, ELSEWHERE_ROLES, member)
    if elsewhere:
        spans = [_span(entry['words']) for entry in elsewhere]
        return row(CONFLICT_ELSEWHERE, origin=CONFLICT, evidence=own + spans,
                   note=USER_ELSEWHERE_NOTE.format(user=member, document=quoted(spans)))
    if verified:
        return row(CONFLICT_DIFFERS, origin=CONFLICT, evidence=own,
                   note=USER_CONFLICT_NOTE.format(user=member, document=verified))
    if state == 'several' and candidates:
        if member in candidates:
            return row(SETTLES, effective=member, origin=USER, note=USER_NOTE)
        return row(CONFLICT_LISTED, origin=CONFLICT, evidence=own,
                   note=USER_CONFLICT_NOTE.format(user=member, document=' or '.join(candidates)))
    if state in ('stated', 'several'):
        if member in (date_of_service.get('readings') or ()):
            return row(SETTLES, effective=member, origin=USER, note=USER_NOTE)
        if own:
            return row(CONFLICT_UNVERIFIABLE, origin=CONFLICT, evidence=own,
                       note=USER_CONFLICT_NOTE.format(user=member, document=quoted(own)))
    return row(SUPPLIES, effective=member, origin=USER, note=USER_NOTE)


def effective_date(date_of_service: Mapping, member_value, passages=()) -> Optional[str]:
    """The effective date of service (contract 8.2): member_date_state's, None when it holds or there is none."""
    return member_date_state(date_of_service, member_value, passages).effective


def corti_date(date_of_service: Mapping, member_value, passages=()) -> Optional[str]:
    """The date Corti's request carries (D2), None when held or when there is none."""
    return member_date_state(date_of_service, member_value, passages).corti_date
