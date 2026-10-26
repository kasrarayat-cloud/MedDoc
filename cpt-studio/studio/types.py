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
