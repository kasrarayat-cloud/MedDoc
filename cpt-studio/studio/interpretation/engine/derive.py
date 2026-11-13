"""The derived context and the routing stand-in over facts (docs/gemini-migration/FINAL-V2.md 4.7's last row, 5.5's
facts.py row, 1.1's CONTEXT_VERSION and ROUTING_VERSION @2; step 2d of 8.1): v1's facts.derive, context_of,
document_date, routing_stand_in and _status, forked, with their word readers deleted - day_of, its SAME_DAY_WORDS and
its frames (5.1 rows 4-7) - and their inputs rewired to the settled inventory: the date of service and the other dates,
the member values, and each act's status and effective date relation.

``derive(inventory, user_values, *, quote=None)`` gives what v1's gave (a Derived: ``facts``, ``document_date``,
``effective``, ``member_date``), for gemini-context@2 (interpretation.CONTEXT_VERSION_V2):
- ``facts``: the context record in the legacy Fact shape {name, value, origin, evidence, note}, service_date with its
  ``state``. The date of service is interpretation/dates.py's member_date_state over a date record built from the
  encounter's facts (``date_record``, below), so the precedence, the held rows' legacy notes and Corti's date are
  dates.py's, unchanged. setting, billing_context and patient_status come only from member values (D3), as in v1.
- ``document_date``: the document's own date before any member value, in the shape answers.py reads.
- ``effective``: the effective date of service (ISO) or None; ``member_date``: the dates.MemberDate row.

**The text-free boundary.** The engine reads no text (FINAL-V2 1.7, 5.7 measure 4), yet the context record quotes
the document's date in its evidence and in the held rows' notes, exactly as v1's did. Those quotes are made by
dates.py, outside the engine: ``quote(start, end)`` is the caller's display slice of the revision (jobs.py has the
revision text; wording.quote's role), handed to member_date_state, never called here. Without one every quoted text is
'' - for a caller that reads the decisions only - and nothing decided changes (P-TEXTFREE: the states, the effective
date and the origins never depend on a quote). The ``inventory`` is store.textfree_v2's view of the stored row, as
engine/facts.py reads it (DECISIONS D188). A span quoted here is the located words of the fact's first source (its
Cited.at), else that source's units when it cites its whole units, so a quote is the date's located words, as v1's
was (triage 2d:D3).

**The date record** (``date_record``; the fact-equivalence of v1's contract 8.1 record and v2's facts):
- ``state``: not_stated for a silent date of service, several for a contradicted one (pass 1 reported several dates for
  this encounter), stated otherwise;
- ``verified`` and ``value``: the date of service established (supported) at day precision, and its value - unless an
  other date whose role is possibly this_encounter (its role fact not established as another role) has another value:
  the document then gives this encounter a second date, and v1's normalize._bind_date left the stated date unverified
  (``date_mismatch``). other_dates.role is outside CLAIMED (3.2.1), so such a role is never established, and an
  omission can only hold (triage 2d#4);
- ``candidates`` (several): the day-precision values of its sides - the dates pass 1 reported - only when every side
  is known to be verified, as v1's candidates were (normalize._bind_date kept a date only when its words were bound
  and stated it, verify.date_words): the fact's result is contradicted (3.3 row 1) AND its stored integrity and L1
  checks both passed (facts.EncounterDates.checks_passed: every side's sources passed I1-I3 and every side's own
  words state its value). The row keeps those checks per fact, never per side, so when one failed no side is known to
  be verified and none is a candidate (triage 2d#3), where v1 kept the side that was: a fact that settled unresolved
  or unknown (3.3 row 1: a side failing integrity gives unresolved, still a doubt), one contradicted by a conflict
  doubt although a side failed integrity (row 1's second clause), and one whose side's words state another date than
  its value (row 1 comes before L1's row 4). Never a doubt's reading, which is no date the document gives. A several
  date with no candidate offers no documented date (document_date: origin missing), as v1's with no verified one;
- ``readings`` (stated - pass 1's claim supported, whatever its result - and not verified): the day-precision literals
  L1 read in its own words (checks.literals: v1's readings were the full dates in its words), less any other date's
  value, as v1's; none for a negated date of service, which never settles a member's date (DECISIONS D207, 2d's
  readings). A several date has none: its literals are every side's words' dates, and which side each came from is not
  stored. When its checks passed, every day literal L1 stored is a side's value (L1 passes only then), so each is a
  candidate already; when one failed, a reading would take the date of the side that failed, or a date no side gives
  (one a side's words name beside its value), which v1 held (its verified side the only candidate) and the
  contradicted twin holds (P6: a weakened fact never releases; the refutation of 2d#3's first repair);
- ``words``: the located words of its first source, else that source's units (triage 2d:D3); ``passages``: none;
- ``others``: each other date under every role (birth, other_occurrence, other_document, report_time, unclear) its role
  fact possibly has (facts.possibly), with the located words of its role fact's first source. Read as v1's "verified"
  only when established, a birth date would never hold a member's date - CLAIMED's omission would RELEASE. 3.2.1
  rules that an omission can only hold, so a possible role takes part, and the record marks it verified (DECISIONS
  D207). An other date with a this_encounter role is no candidate here (the contradicted date of service carries
  several dates); it only leaves a stated date unverified (above).

``routing_stand_in(inventory, effective_date, ...)``, over the same view, is gemini-routing@2's derived RoutingRun
record: one finding per family the events' sessions name (a session's kind, the value claimed in any state), its status
the strongest its events give - from each act's status and its date relation, read over ``facts.effective`` for the
date, never a word.

**Imports**: the standard library, studio.types (the legacy Fact and Span, and CONTEXT_FACTS), the package's labels,
interpretation/dates.py (kept, the member precedence), contract/types.py and engine's types, facts and catalogue; no
retired v1 module, none of contract's text modules. Member values are a member's typed input, never the document's: they
are trimmed by str.isspace, as v1's strip() trimmed them, and compared with CPT Studio's own value lists (the Enums
below, pinned equal to gi.context's by test).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, unique
from typing import Optional

from studio import types as studio_types
from studio.interpretation import ROUTING_VERSION_V2, dates
from studio.interpretation.contract.types import (Attribute, DateRelation, DateRole, FactState, Precision, Result,
                                                  SessionKind, Status)
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine.types import Fact, FactSet, Id, IsoDate

Quote = Callable[[int, int], str]


@unique
class ContextFact(Enum):
    """The encounter context facts (studio.types.CONTEXT_FACTS, in its order)."""
    SERVICE_DATE = 'service_date'
    SETTING = 'setting'
    BILLING_CONTEXT = 'billing_context'
    PATIENT_STATUS = 'patient_status'


@unique
class Setting(Enum):
    """The settings a member may enter (gi.context.SETTINGS = v1's facts.SETTINGS)."""
    OFFICE = 'office'
    HOSPITAL_OUTPATIENT = 'hospital_outpatient'
    ASC = 'asc'
    INPATIENT = 'inpatient'
    EMERGENCY = 'emergency'
    TELEHEALTH = 'telehealth'


@unique
class BillingContext(Enum):
    """The billing contexts a member may enter (gi.context.BILLING_CONTEXTS)."""
    PROFESSIONAL = 'professional'
    FACILITY = 'facility'


@unique
class PatientStatus(Enum):
    """The patient statuses a member may enter (gi.context.PATIENT_STATUSES)."""
    NEW = 'new'
    ESTABLISHED = 'established'


# D3: on the new path setting, billing context and patient status come only from member values (v1's MEMBER_FACTS).
MEMBER_FACTS: tuple[ContextFact, ...] = (ContextFact.SETTING, ContextFact.BILLING_CONTEXT, ContextFact.PATIENT_STATUS)
ALLOWED: Mapping[ContextFact, type[Enum]] = {ContextFact.SETTING: Setting, ContextFact.BILLING_CONTEXT: BillingContext,
                                             ContextFact.PATIENT_STATUS: PatientStatus}
# The other dates' roles dates.py's record holds (v1's normalize.OTHER_ROLES): every role but this_encounter.
OTHER_ROLES: tuple[DateRole, ...] = (DateRole.BIRTH, DateRole.OTHER_OCCURRENCE, DateRole.OTHER_DOCUMENT,
                                     DateRole.REPORT_TIME, DateRole.UNCLEAR)


def missing_note(name: ContextFact) -> str:
    """The legacy missing note of a context fact (gi.context.MISSING_NOTES = v1's facts.MISSING_NOTES; pinned equal by
    tests/v2/test_derive.py through a test-only import)."""
    if name is ContextFact.SERVICE_DATE:
        return dates.MISSING_NOTE
    if name is ContextFact.SETTING:
        return 'No place of service or care setting is documented.'
    if name is ContextFact.BILLING_CONTEXT:
        return 'No explicit professional or facility billing statement is documented.'
    return 'New or established patient status is not documented.'


@dataclass(frozen=True)
class Derived:
    """What derive() gives (module docstring): v1's Derived, field for field."""
    facts: dict[str, dict[str, object]]
    document_date: dict[str, object]
    effective: Optional[str]
    member_date: dates.MemberDate


def _no_text(start: int, end: int) -> str:
    """The quote of a caller that reads decisions only: no text (module docstring)."""
    return ''


def _trimmed(value: str) -> str:
    """``value`` without its surrounding whitespace - str.strip()'s result, by str.isspace (module docstring)."""
    start, end = 0, len(value)
    while start < end and value[start].isspace():
        start += 1
    while end > start and value[end - 1].isspace():
        end -= 1
    return value[start:end]


def _iso_day(value: str) -> bool:
    """A YYYY-MM-DD date (v1's literals.iso_date(value) is not None, by calendar arithmetic)."""
    try:
        return facts_.iso_value(value).precision is Precision.DAY
    except ValueError:
        return False


def _valid(name: ContextFact, value: str) -> bool:
    if name is ContextFact.SERVICE_DATE:
        return _iso_day(value)
    return value in {member.value for member in ALLOWED[name]}


# --- the date record (module docstring) ----------------------------------------------------------------------------------


def _day(value: object) -> str | None:
    return value.iso if isinstance(value, IsoDate) and value.precision is Precision.DAY else None


def _located(fact: Fact) -> dict[str, object] | None:
    """The span a record quotes for ``fact`` (module docstring; triage 2d:D3): the located words of its first source
    (Cited.at, DECISIONS D188), else that source's units when it cites its whole units; None for a fact with no
    source."""
    if not fact.cited:
        return None
    first = fact.cited[0]
    span = first.at if first.at is not None else first.units
    return {'start': span.start, 'end': span.end}


def date_record(found: facts_.EncounterDates) -> dict[str, object]:
    """The date of service record dates.member_date_state reads (v1's contract 8.1 shape), built from the encounter's
    facts (module docstring: the fact-equivalence). Its spans are {start, end}: dates.py adds each quote."""
    fact = found.date_of_service
    if fact.state is None:
        state = 'not_stated'
    elif fact.state is FactState.CONTRADICTED:
        state = 'several'
    else:
        state = 'stated'
    # another date possibly given for this encounter leaves a stated date unverified (v1's date_mismatch; 2d#4)
    second = any(facts_.possibly(other.role, DateRole.THIS_ENCOUNTER) and other.value != fact.value
                 for other in found.others)
    verified = (state == 'stated' and fact.result is Result.SUPPORTED and _day(fact.value) is not None
                and not second)
    candidates: list[str] = []
    # every side known to be verified: contradicted (3.3 row 1) with its integrity and L1 checks passed (2d#3)
    if state == 'several' and fact.result is Result.CONTRADICTED and found.checks_passed:
        candidates = sorted({day for day in (_day(side) for side in found.sides) if day})
    elsewhere = {other.value.iso for other in found.others
                 if any(facts_.possibly(other.role, role) for role in OTHER_ROLES)}
    readings: list[str] = []
    if fact.state is FactState.SUPPORTED and not verified:  # a stated date only: never a several one's (2d#3)
        readings = sorted({day for day in (_day(literal) for literal in found.literals)
                           if day and day not in elsewhere})
    others: dict[str, list[dict[str, object]]] = {role.value: [] for role in OTHER_ROLES}
    for other in found.others:
        located = _located(other.role)
        for role in OTHER_ROLES:
            if facts_.possibly(other.role, role):
                others[role.value].append({'value': other.value.iso, 'verified': True, 'words': located,
                                           'passages': [], 'reasons': []})
    return {'state': state, 'value': _day(fact.value) if verified else None, 'verified': verified,
            'words': _located(fact), 'passages': [], 'reasons': [reason.value for reason in fact.reasons],
            'candidates': candidates, 'readings': readings, 'others': others}


# --- derive -------------------------------------------------------------------------------------------------------------


def derive(inventory: object, user_values: Optional[Mapping[str, object]] = None, *,
           quote: Optional[Quote] = None) -> Derived:
    """The gemini-context@2 facts of ``inventory`` (store.textfree_v2's view of a stored v2 row, DECISIONS D188) with
    the encounter's member values (module docstring), as v1's derive: unknown names, values that are not strings, and
    values not valid for their fact are refused (ValueError), as the legacy merge refuses them. ``quote``: the caller's
    display slice of the revision, for the quoted evidence and notes."""
    record = date_record(facts_.encounter_dates(inventory))
    given = dict(user_values or {})
    names = {member.value: member for member in ContextFact}
    for raw_name, raw in given.items():
        if raw_name not in names:
            raise ValueError(f'{raw_name!r} is not an encounter context fact.')
        if not isinstance(raw, str):
            raise ValueError(f'{raw_name} must be a string.')
        value = _trimmed(raw)
        if value and not _valid(names[raw_name], value):
            raise ValueError(f'{value!r} is not a valid {raw_name}.')
    member_date = given.get(ContextFact.SERVICE_DATE.value)
    row = dates.member_date_state(record, member_date if isinstance(member_date, str) else None, (),
                                  quote=quote or _no_text)
    service: dict[str, object] = {'name': ContextFact.SERVICE_DATE.value,
                                  'value': row.effective if not row.hold else None, 'origin': row.origin,
                                  'evidence': [dict(span) for span in row.evidence], 'note': row.note,
                                  'state': row.state}
    if service['origin'] in (dates.MISSING, dates.CONFLICT):
        service['value'] = None
    if row.origin == dates.MISSING and not row.note and record['state'] == 'not_stated':
        service['note'] = missing_note(ContextFact.SERVICE_DATE)
    out: dict[str, dict[str, object]] = {ContextFact.SERVICE_DATE.value: service}
    for name in MEMBER_FACTS:
        raw = given.get(name.value)
        value = _trimmed(raw) if isinstance(raw, str) else ''
        if value:
            out[name.value] = {'name': name.value, 'value': value, 'origin': dates.USER, 'evidence': [],
                               'note': dates.USER_NOTE}
        else:
            out[name.value] = {'name': name.value, 'value': None, 'origin': dates.MISSING, 'evidence': [],
                               'note': missing_note(name)}
    return Derived(facts=out, document_date=_document_date(record, quote),
                   effective=row.effective if not row.hold else None, member_date=row)


def context_of(facts: Optional[Mapping[str, Mapping[str, object]]]) -> dict[str, studio_types.Fact]:
    """{name: studio.types.Fact} of stored or derived context facts (jobs.context_facts' reading; the ``state`` key is
    not a field), as v1's context_of. Each evidence span is rebuilt by studio.types.from_jsonable, so a stored quote is
    carried as it was stored and never read here."""
    out = {}
    for name, value in (facts or {}).items():
        # studio.types is v1's untyped module, kept (6.4): its from_jsonable has no annotations for mypy --strict
        evidence = tuple(studio_types.from_jsonable(studio_types.Span, span)  # type: ignore[no-untyped-call]
                         for span in _spans(value.get('evidence')))
        note = value.get('note', '')
        out[name] = studio_types.Fact(name=str(value.get('name', name)), value=_optional(value.get('value')),
                                      origin=str(value.get('origin', dates.MISSING)), evidence=evidence,
                                      note=str(note) if note else '')
    return out


def _spans(value: object) -> tuple[object, ...]:
    return tuple(value) if isinstance(value, list | tuple) else ()


def _optional(value: object) -> Optional[str]:
    return value if isinstance(value, str) else None


def _document_date(record: Mapping[str, object], quote: Optional[Quote]) -> dict[str, object]:
    own = list(dates.member_date_state(record, None, (), quote=quote or _no_text).evidence)
    verified = record['state'] == 'stated' and record['verified'] is True and isinstance(record['value'], str)
    value = record['value'] if verified else None
    candidates = list(record['candidates']) if record['state'] == 'several' and isinstance(
        record['candidates'], list) else []
    if value:
        origin, values = dates.DOCUMENT, [value]
    elif candidates:
        origin, values = dates.CONFLICT, candidates
    else:
        origin, values = dates.MISSING, []
    return {'origin': origin, 'value': value, 'single': bool(value), 'values': values, 'asked': False,
            'quote': own[0] if value and own else None, 'evidence': own}


def document_date(inventory: object, *, quote: Optional[Quote] = None) -> dict[str, object]:
    """The document's own date of service before any member value, in the shape answers.py reads (v1's document_date),
    from ``inventory``, store.textfree_v2's view of the stored row (DECISIONS D188): ``single`` only where the
    document gives one established date; ``values`` the dates it offers (that date, or the candidates of several);
    ``quote`` its first own span, for a single date only; ``evidence`` its own spans."""
    return _document_date(date_record(facts_.encounter_dates(inventory)), quote)


# --- the routing stand-in (FINAL 4.3; gemini-routing@2) ------------------------------------------------------------------


@unique
class ServiceStatus(Enum):
    """A family status of the stand-in (types.SERVICE_STATUSES), in v1's facts.RANK order: the strongest first."""
    PERFORMED = 'performed'
    INCOMPLETE = 'incomplete'
    UNCERTAIN = 'uncertain'
    PLANNED = 'planned'
    HISTORICAL = 'historical'
    NEGATED = 'negated'
    CANCELLED = 'cancelled'


RANK: Mapping[ServiceStatus, int] = {status: index for index, status in enumerate(ServiceStatus)}


def status_of(R: FactSet, event: Id) -> ServiceStatus | None:
    """v1's _status over facts: a family status read from one act's established status and effective date relation;
    None for an act that states nothing a status reads. A status not established leaves every status possible (4.2):
    uncertain. A positive act on the date of service is performed (incomplete when only begun); on an earlier date
    historical, a later one planned; with its date relation not established, uncertain. A planned act is planned, a
    denied one negated."""
    status = facts_.fact(R, event, Attribute.STATUS)
    if not facts_.established(status):
        return ServiceStatus.UNCERTAIN
    if status.result is Result.NEGATED:
        return ServiceStatus.NEGATED if status.value is Status.PERFORMED else None
    if status.value is Status.PERFORMED or status.value is Status.ATTEMPTED_NOT_COMPLETED:
        relation = facts_.fact(R, event, Attribute.DATE_RELATION)
        if facts_.holds(relation, DateRelation.ON_DATE_OF_SERVICE):
            return ServiceStatus.PERFORMED if status.value is Status.PERFORMED else ServiceStatus.INCOMPLETE
        if facts_.holds(relation, DateRelation.EARLIER_DATE):
            return ServiceStatus.HISTORICAL
        if facts_.holds(relation, DateRelation.LATER_DATE):
            return ServiceStatus.PLANNED
        return ServiceStatus.UNCERTAIN
    return ServiceStatus.PLANNED if status.value is Status.PLANNED else None


def family_of(R: FactSet, event: Id) -> SessionKind | None:
    """The family an act names: its session's kind, each value claimed in any state (v1's event family was Gemini's
    procedure, read unverified); None when either is silent."""
    session = facts_.fact(R, event, Attribute.SESSION).value
    if not isinstance(session, Id):
        return None
    kind = facts_.fact(R, session, Attribute.KIND).value
    return kind if isinstance(kind, SessionKind) else None


def family_slug(family: SessionKind) -> str:
    """A family's gi.profiles slug (v1's lexicon.FAMILY_OF): gi.<value>, gi.other and gi.unsupported."""
    if family is SessionKind.OTHER_GI:
        return 'gi.other'
    if family is SessionKind.NOT_GI:
        return 'gi.unsupported'
    return f'gi.{family.value}'


def routing_stand_in(inventory: object, effective_date: object, *, inventory_id: str = '',
                     inventory_sha256: str = '') -> dict[str, object]:
    """The gemini-routing@2 stand-in for ``effective_date`` (module docstring): {version, document_kind: '', findings:
    [{family, status, mentions: [], facts: [], missing: []}], inventory, inventory_sha256}. One finding per family an
    act names, in catalogue.FAMILY_ORDER, its status the strongest its acts give (performed first)."""
    R = facts_.effective(inventory, effective_date)
    found: dict[SessionKind, ServiceStatus] = {}
    for event in R.events:
        family = family_of(R, event)
        status = status_of(R, event)
        if family is None or status is None:
            continue
        if family not in found or RANK[status] < RANK[found[family]]:
            found[family] = status
    findings: list[dict[str, object]] = [
        {'family': family_slug(family), 'status': found[family].value, 'mentions': [], 'facts': [], 'missing': []}
        for family in catalogue.FAMILY_ORDER if family in found]
    return {'version': ROUTING_VERSION_V2, 'document_kind': '', 'findings': findings,
            'inventory': str(inventory_id or ''), 'inventory_sha256': str(inventory_sha256 or '')}
