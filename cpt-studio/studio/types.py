"""Shared, frozen data types exchanged between the pipeline modules.

These are the contracts between ingest, gi (context + routing), providers,
reference, validation, review and reports. They are pure data: no Django, no
I/O. ``to_jsonable`` / ``from_jsonable`` round-trip them through JSON fields.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import typing
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Protocol

# --- check / status vocabularies -------------------------------------------------

CHECK_STATUSES = ('pass', 'warn', 'fail', 'not_verified', 'not_applicable', 'info')
SERVICE_STATUSES = ('performed', 'incomplete', 'planned', 'historical', 'cancelled', 'negated', 'uncertain')
FACT_ORIGINS = ('document', 'user', 'missing', 'conflict')
CONTEXT_FACTS = ('service_date', 'setting', 'billing_context', 'patient_status')


@dataclass(frozen=True)
class Span:
    """A half-open [start, end) range over a revision's canonical text."""
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class PageSpan:
    page: int  # 1-based
    start: int
    end: int


@dataclass(frozen=True)
class ExtractionResult:
    status: str  # ok | partial | failed
    method: str  # txt | docx | pdf-text | pdf-ocr | pdf-mixed | paste | addendum
    text: str
    pages: tuple[PageSpan, ...] = ()
    messages: tuple[str, ...] = ()
    ocr_pages: tuple[int, ...] = ()
    engine: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Fact:
    name: str
    value: Optional[str]
    origin: str  # one of FACT_ORIGINS
    evidence: tuple[Span, ...] = ()
    note: str = ''


@dataclass(frozen=True)
class ServiceMention:
    family: str
    status: str  # one of SERVICE_STATUSES
    span: Span
    sentence: Span
    section: str  # procedure | findings | technique | impression | indication | history | plan | assessment | other
    cues: tuple[str, ...] = ()


@dataclass(frozen=True)
class FamilyFinding:
    family: str
    status: str  # aggregated over mentions; one of SERVICE_STATUSES
    mentions: tuple[ServiceMention, ...]
    facts: tuple[Fact, ...] = ()
    missing: tuple[str, ...] = ()  # names of the profile's required facts that are not documented


@dataclass(frozen=True)
class RoutingResult:
    version: str
    document_kind: str  # procedure_report | office_note | mixed | unknown
    findings: tuple[FamilyFinding, ...] = ()

    def finding(self, family: str) -> Optional[FamilyFinding]:
        for item in self.findings:
            if item.family == family:
                return item
        return None


@dataclass(frozen=True)
class EvidenceSpan:
    context_index: int
    start: int
    end: int
    text: str
    exact: bool  # contexts[context_index][start:end] == text, checked, never assumed
    page: Optional[int] = None


@dataclass(frozen=True)
class ProviderCode:
    role: str  # selected | candidate | alternative
    system: str  # the provider's raw system label
    code: str
    display: str  # untrusted provider wording; never shown as a descriptor
    evidence: tuple[EvidenceSpan, ...] = ()
    parent_code: Optional[str] = None  # for nested alternatives
    index: int = 0  # position in the provider's own list


@dataclass(frozen=True)
class ProviderRequest:
    provider: str
    adapter_version: str
    body: dict
    canonical_sha256: str
    contexts: tuple[str, ...]


@dataclass(frozen=True)
class RawExchange:
    outcome: str  # succeeded | failed | unknown | not_sent
    sent: bool
    http_status: Optional[int] = None
    response_bytes: Optional[bytes] = None
    response_sha256: str = ''
    latency_ms: Optional[float] = None
    usage: dict = field(default_factory=dict)
    usage_basis: str = ''
    provider_request_id: str = ''
    error: str = ''
    # What was actually called and what answered (HARNESS.md 6): the URL, the model the request named and the model the
    # response says answered (both '' for Corti, whose API takes no model), and the vendor's own object id (resp_..., msg_...).
    endpoint: str = ''
    requested_model: str = ''
    returned_model: str = ''
    response_id: str = ''


@dataclass(frozen=True)
class NormalizedResponse:
    provider: str
    adapter_version: str
    codes: tuple[ProviderCode, ...] = ()  # CPT-labelled codes, every role
    internal_context: tuple[ProviderCode, ...] = ()  # other systems (e.g. ICD-10-CM); never shown as results
    problems: tuple[str, ...] = ()
    refused: bool = False  # the whole response was not used and none of its codes was read; problems say why


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    status: str  # one of CHECK_STATUSES
    detail: str
    source: str = ''  # reference source key + release, or 'cpt-studio:<rule>@<version>'


@dataclass(frozen=True)
class ClarificationSpec:
    scope: str  # encounter | service | proposal
    fact: str
    question: str
    reason: str
    family: str = ''
    proposal_key: str = ''


@dataclass(frozen=True)
class ProposalAssessment:
    key: str
    bucket: str  # selected | alternative | excluded
    code: str
    code_kind: str  # cpt1 | cpt2 | cpt3 | pla | hcpcs | invalid
    family: str
    profile_version: str
    status: str  # ready | needs_clarification | excluded | informational
    exclusion_reason: str
    reinstatable: bool
    provider_display: str
    evidence: tuple[EvidenceSpan, ...]
    rationale: str
    checks: tuple[Check, ...]
    modifier_considerations: tuple[str, ...]
    units: int
    fingerprint: str
    clarifications: tuple[ClarificationSpec, ...] = ()
    # The documented service the code was matched to and how its passages relate to the coded act (reconcile.py):
    # {'service': id, 'state', 'reason', 'acts': [...], 'status': pass|warn|fail|not_applicable, 'supporting': [index],
    #  'unrelated': [index], 'source': [{start, end, text, page}]}; {} when no documented service was matched.
    support: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AssessmentResult:
    profiles_version: str
    engine_version: str
    proposals: tuple[ProposalAssessment, ...]
    encounter_checks: tuple[Check, ...]
    clarifications: tuple[ClarificationSpec, ...]  # encounter-scoped only
    unsupported: tuple[dict, ...]
    reference_sources: tuple[dict, ...]
    summary: dict = field(default_factory=dict)
    services: dict = field(default_factory=dict)  # the documented-service inventory (gi/services.py), JSON form
    completeness: dict = field(default_factory=dict)  # reconcile.completeness plus unresolved, bundled and covered


@dataclass(frozen=True)
class ReferenceSourceInfo:
    key: str
    kind: str
    publisher: str
    title: str
    release: str
    url: str
    sha256: str
    effective_start: str  # ISO date
    effective_end: str  # ISO date
    license_note: str
    scope_note: str


@dataclass(frozen=True)
class CodeReference:
    code: str
    pfs: Optional[dict] = None  # {status, global_days, mult_proc, endo_base, pctc, source_key}
    mue: Optional[dict] = None  # {value, mai, rationale, source_key}
    applicable_sources: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class ReferenceLookup(Protocol):
    def sources(self) -> tuple[ReferenceSourceInfo, ...]: ...

    def lookup(self, code: str, service_date: Optional[date]) -> CodeReference: ...


# --- harness participants (HARNESS.md 3-5) -----------------------------------------
# What an independent participant (Astra, Fable) said about one revision, as CPT Studio read and checked it. Every
# quote is located in the revision text; a quote that is not found verbatim is kept, unverified, and is never evidence.

PARTICIPANT_FAMILIES = ('office_em', 'egd', 'colonoscopy', 'flexible_sigmoidoscopy', 'eus', 'ercp', 'other_gi', 'not_gi')
PARTICIPANT_SERVICE_STATUSES = ('performed', 'attempted_incomplete', 'not_performed', 'planned', 'historical', 'unclear')
NOT_CODED_REASONS = ('not_performed_at_this_encounter', 'included_in_another_code', 'insufficient_documentation',
                     'outside_gi_scope', 'other')
CONFIDENCES = ('high', 'medium', 'low')
# How one participant stands on one revision (Assessment.participants, ParticipantInput.state): 'read' - its reading
# was used; 'refused' - it answered and the answer was not used (problems say why); 'failed', 'unknown', 'not_sent' -
# the run's state; 'blocked' - another run's unknown outcome stopped the send; 'not_configured' - disabled here;
# 'not_run' - no run exists for this revision.
PARTICIPANT_STATES = ('read', 'refused', 'failed', 'unknown', 'not_sent', 'blocked', 'not_configured', 'not_run')


@dataclass(frozen=True)
class LocatedQuote:
    quote: str  # as the participant wrote it (bounded)
    spans: tuple[EvidenceSpan, ...] = ()  # every exact occurrence in the revision text (context 0), at most 8
    reason: str = ''  # why it is unverified ('' when spans exist): not found, too short, too long


@dataclass(frozen=True)
class ParticipantLesion:
    site: str
    size: str
    morphology: str
    action: str
    specimen: str


@dataclass(frozen=True)
class ParticipantService:
    id: str
    family: str  # PARTICIPANT_FAMILIES
    status: str  # PARTICIPANT_SERVICE_STATUSES
    description: str
    anatomy: str
    extent: str
    technique: str
    lesions: tuple[ParticipantLesion, ...] = ()
    provider_role: str = ''
    evidence: tuple[LocatedQuote, ...] = ()


@dataclass(frozen=True)
class ParticipantCode:
    code: str
    modifiers: tuple[str, ...] = ()
    units: int = 1
    service_ids: tuple[str, ...] = ()
    basis: str = ''
    evidence: tuple[LocatedQuote, ...] = ()
    confidence: str = 'medium'  # CONFIDENCES


@dataclass(frozen=True)
class ParticipantNotCoded:
    service_ids: tuple[str, ...] = ()
    code: str = ''  # '' when no particular code is named
    reason: str = 'other'  # NOT_CODED_REASONS
    evidence: tuple[LocatedQuote, ...] = ()


@dataclass(frozen=True)
class ParticipantQuestion:
    question: str
    why: str
    service_ids: tuple[str, ...] = ()
    evidence: tuple[LocatedQuote, ...] = ()


@dataclass(frozen=True)
class ExtractionIssue:
    page: int
    issue: str


@dataclass(frozen=True)
class ReferenceUse:
    """A reference a participant says it relied on (HARNESS.md 11.2): a passage_key or 'fact:<source_key>:<code>:<field>'
    from its own tool results. ``retrieved`` is CPT Studio's check, never the participant's claim: True only when that
    participant's own tool results in the same run contained it."""
    ref: str
    use: str
    retrieved: bool = False


@dataclass(frozen=True)
class ParticipantReading:
    provider: str  # 'astra' | 'fable'
    adapter_version: str
    reading_version: str  # studio.participants.prompt.READING_VERSION
    requested_model: str
    returned_model: str
    date_of_service: str = ''  # 'YYYY-MM-DD' as the participant read it, or ''
    date_evidence: tuple[LocatedQuote, ...] = ()
    services: tuple[ParticipantService, ...] = ()
    codes: tuple[ParticipantCode, ...] = ()
    not_coded: tuple[ParticipantNotCoded, ...] = ()
    questions: tuple[ParticipantQuestion, ...] = ()
    extraction_issues: tuple[ExtractionIssue, ...] = ()
    problems: tuple[str, ...] = ()
    refused: bool = False  # the whole reading was not used and none of it was read; problems say why
    unverified_quotes: int = 0
    references_used: tuple[ReferenceUse, ...] = ()  # harness-reading@2 (HARNESS.md 11.2)


PEER_POSITIONS = ('supports', 'disputes', 'cannot_tell')


@dataclass(frozen=True)
class QuestionAnswer:
    question_id: str  # the open clarification's id as the peer request named it
    settled: bool  # False: the participant says the document does not settle it
    value: str
    evidence: tuple[LocatedQuote, ...] = ()


@dataclass(frozen=True)
class CodePosition:
    code: str
    position: str  # PEER_POSITIONS
    reason: str
    evidence: tuple[LocatedQuote, ...] = ()


@dataclass(frozen=True)
class PeerReview:
    """A participant's phase-2 output (HARNESS.md 11.1), made after its own first reading was frozen and with the frozen
    peer conclusions and CPT Studio's open questions in view. Recorded apart from the frozen reading; never replaces it."""
    provider: str
    adapter_version: str
    review_version: str  # studio.participants.prompt.PEER_VERSION
    requested_model: str
    returned_model: str
    frozen_inputs: tuple[tuple[str, str], ...] = ()  # (input name, sha256) of each frozen output the request showed
    answers: tuple[QuestionAnswer, ...] = ()
    positions: tuple[CodePosition, ...] = ()
    additional_codes: tuple[ParticipantCode, ...] = ()  # first proposed after peer review: never independent
    references_used: tuple[ReferenceUse, ...] = ()
    problems: tuple[str, ...] = ()
    refused: bool = False
    unverified_quotes: int = 0


@dataclass(frozen=True)
class ParticipantInput:
    """What the validation engine reads of one CONFIGURED participant (HARNESS.md 5, 11). A participant disabled on this
    installation is never passed, so with none configured the engine's input is () and its output is unchanged (I1)."""
    provider: str
    state: str  # PARTICIPANT_STATES
    reading: Optional[ParticipantReading] = None  # present only when state == 'read' (the frozen phase-1 reading)
    reason: str = ''
    peer_state: str = ''  # '' before phase 2; otherwise one of PARTICIPANT_STATES for its peer-review run
    peer: Optional[PeerReview] = None  # present only when peer_state == 'read'


@dataclass(frozen=True)
class ConfirmedFinding:
    """A reviewer-confirmed answer to an open question (HARNESS.md 11.3): a fact the cited passage documents, located by
    a participant and confirmed by an owner or reviewer with an attestation. The service date never comes this way; it
    enters through the context as the member's date."""
    scope: str  # service | proposal
    fact: str  # e.g. extent | performed_status | em_basis: the open clarification's own fact
    family: str
    proposal_key: str  # '' for a service-scope question
    value: str
    evidence: tuple[EvidenceSpan, ...]  # exact slices of the revision text
    located_by: tuple[str, ...]  # the participants whose quote it was
    confirmed_by: str  # the reviewer's label
    confirmation_id: str


# --- JSON round-trip ------------------------------------------------------------

def to_jsonable(value):
    """Dataclasses -> dicts, tuples -> lists, bytes refused (store them separately)."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, bytes):
        raise TypeError('bytes are not JSON data; store them in a binary field')
    if isinstance(value, date):
        return value.isoformat()
    return value


@functools.lru_cache(maxsize=None)
def _fields_of(tp) -> tuple:
    """A dataclass's (field name, resolved type) pairs, read once per class: typing.get_type_hints resolves every
    annotation again on each call, and rebuilding a mention-dense routing instance by instance spent most of the assess
    child's round trip there (round 7 bounded:1: from_jsonable 5.4 s against 0.5 s at 100,000 characters)."""
    hints = typing.get_type_hints(tp)
    return tuple((f.name, hints[f.name]) for f in dataclasses.fields(tp))


def _build(tp, data):
    origin = typing.get_origin(tp)
    if dataclasses.is_dataclass(tp):
        kwargs = {}
        for name, hint in _fields_of(tp):
            if name in data:
                kwargs[name] = _build(hint, data[name])
        return tp(**kwargs)
    if origin is tuple:
        args = typing.get_args(tp)
        inner = args[0] if args else typing.Any
        return tuple(_build(inner, item) for item in (data or ()))
    if origin is typing.Union:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if data is None:
            return None
        return _build(args[0], data) if len(args) == 1 else data
    return data


def from_jsonable(cls, data):
    return _build(cls, data)


def canonical_json(value) -> bytes:
    return json.dumps(to_jsonable(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha256_json(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()
