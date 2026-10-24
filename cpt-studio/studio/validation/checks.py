"""Pure validation checks (ARCHITECTURE 5.6): plain data in, ``Check`` values out.

No I/O and no database access. A check never upgrades a status because two
sources agree, never states a rule the system does not hold, and reports
``not_verified`` with the reason whenever a reference is unavailable.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping, Optional, Sequence

from studio.gi.profiles import PROFILES_VERSION, ServiceProfile
from studio.reference.store import (KIND_LABELS, MUE, PFS, UNKNOWN_DATE_NOTE, applied_sources,
                                    modifier_only_prefix, source_applies)
from studio.types import (CONTEXT_FACTS, SERVICE_STATUSES, Check, ClarificationSpec, CodeReference, EvidenceSpan,
                          Fact, FamilyFinding, NormalizedResponse, PageSpan, ReferenceSourceInfo)

POSITIVE = ('performed', 'incomplete')
NEGATIVE = ('planned', 'historical', 'cancelled', 'negated')
DOCUMENTED = ('document', 'user')
EM_FAMILIES = ('gi.office_em', 'gi.em_other')

SCOPE_SOURCE = 'cpt-studio:scope@1'
EVIDENCE_SOURCE = 'cpt-studio:evidence@1'
ROUTING_SOURCE = f'cpt-studio:{PROFILES_VERSION}'
STATUS_SOURCE = 'cpt-studio:status@1'
EM_SOURCE = 'cpt-studio:em-procedure@1'
UNITS_SOURCE = 'cpt-studio:units@1'
CONTEXT_SOURCE = 'cpt-studio:context@1'
PROVIDER_SOURCE = 'cpt-studio:provider@1'
EXTRACTION_SOURCE = 'cpt-studio:extraction@1'
COVERAGE_SOURCE = 'cpt-studio:coverage@1'
REINSTATEMENT_SOURCE = 'cpt-studio:reinstatement@1'

EXCERPT_CHARS = 160


def excerpt(text: str) -> str:
    flat = ' '.join(text.split())
    return flat if len(flat) <= EXCERPT_CHARS else flat[:EXCERPT_CHARS - 1].rstrip() + '…'


def _join(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) <= 2:
        return ' and '.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def plural(count: int, word: str) -> str:
    return f'{count} {word}' + ('' if count == 1 else 's')


# --- scope ----------------------------------------------------------------------

SCOPE_FORMATS = (
    ('cpt1', re.compile(r'[0-9]{5}'), ''),
    ('cpt3', re.compile(r'[0-9]{4}T'), ''),
    ('cpt2', re.compile(r'[0-9]{4}F'),
     "CPT Category II performance-measurement code — outside this release's CPT coding scope"),
    ('pla', re.compile(r'[0-9]{4}U'),
     "CPT Proprietary Laboratory Analyses (PLA) code — outside this release's CPT coding scope"),
    ('hcpcs', re.compile(r'[A-Z][0-9]{4}'), 'HCPCS Level II code — CPT-only results'),
)
INVALID_REASON = "Not a CPT Category I or III code format — outside this release's CPT coding scope"
SCOPE_NAMES = {'cpt1': 'CPT Category I', 'cpt3': 'CPT Category III'}


def code_scope(code: str) -> tuple[str, str]:
    """(code kind, exclusion reason); the reason is empty for codes in scope."""
    for kind, pattern, reason in SCOPE_FORMATS:
        if isinstance(code, str) and pattern.fullmatch(code):
            return kind, reason
    return 'invalid', INVALID_REASON


def scope_check(code_kind: str, reason: str) -> Check:
    if reason:
        return Check('scope.cpt', 'CPT-only scope', 'fail', f'{reason}.', SCOPE_SOURCE)
    return Check('scope.cpt', 'CPT-only scope', 'pass', f'{SCOPE_NAMES[code_kind]} code format.', SCOPE_SOURCE)


# --- exact evidence -------------------------------------------------------------

def _evidence_problem(span: EvidenceSpan, text: str) -> str:
    if span.context_index != 0:
        return f'points into provider context {span.context_index}, not the document text'
    if not span.exact:
        return 'is not marked exact by the provider adapter'
    offsets = (span.start, span.end)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in offsets):
        return 'has invalid offsets'
    if not 0 <= span.start < span.end <= len(text):
        return 'lies outside the document text'
    if text[span.start:span.end] != span.text:
        return 'does not match the document text at its offsets'
    if not span.text.strip():
        return 'contains no text'
    return ''


def page_for(offset: int, pages: Sequence[PageSpan]) -> Optional[int]:
    return next((page.page for page in pages if page.start <= offset < page.end), None)


def exact_evidence(spans: Sequence[EvidenceSpan], text: str,
                   pages: Sequence[PageSpan]) -> tuple[tuple[EvidenceSpan, ...], tuple[str, ...]]:
    """(spans re-verified against ``text`` with their page, reasons for every span dropped)."""
    kept, dropped, seen = [], [], set()
    for span in spans:
        problem = _evidence_problem(span, text)
        if problem:
            dropped.append(problem)
        elif (span.start, span.end) not in seen:
            seen.add((span.start, span.end))
            kept.append(replace(span, page=page_for(span.start, pages)))
    return tuple(kept), tuple(dropped)


def _dropped_summary(dropped: Sequence[str]) -> str:
    return '; '.join(f'{count} {problem}' for problem, count in Counter(dropped).items())


def evidence_checks(kept: Sequence[EvidenceSpan], dropped: Sequence[str]) -> tuple[Check, ...]:
    if not kept:
        detail = 'No exact source evidence: no provider passage matches the revision text exactly.'
        if dropped:
            detail += f' Passages not used: {_dropped_summary(dropped)}.'
        return (Check('evidence.exact', 'Exact source evidence', 'fail', detail, EVIDENCE_SOURCE),)
    checks = [Check('evidence.exact', 'Exact source evidence', 'pass',
                    f'{plural(len(kept), "linked passage")} {"matches" if len(kept) == 1 else "match"} the '
                    'revision text exactly.', EVIDENCE_SOURCE)]
    if dropped:
        checks.append(Check('evidence.dropped', 'Provider passages not used', 'warn',
                            f'{plural(len(dropped), "provider passage")} not used: {_dropped_summary(dropped)}.',
                            EVIDENCE_SOURCE))
    return tuple(checks)


# --- family routing -------------------------------------------------------------

def routing_check(profile: ServiceProfile, finding: Optional[FamilyFinding]) -> Check:
    label = 'Service family routing'
    if not profile.supported:
        detail = 'No GI profile for this service in this release.' + (f' {profile.note}' if profile.note else '')
        return Check('routing.family', label, 'not_verified', detail, ROUTING_SOURCE)
    if finding is None:
        return Check('routing.family', label, 'warn',
                     f'Routed to {profile.label} ({profile.version}) by code number; routing did not detect this '
                     'service in the document.', ROUTING_SOURCE)
    if finding.status not in POSITIVE:
        return Check('routing.family', label, 'warn',
                     f'Routed to {profile.label} ({profile.version}) by code number; routing detected this service '
                     f'in the document only as {finding.status}.', ROUTING_SOURCE)
    return Check('routing.family', label, 'pass',
                 f'Routed to {profile.label} ({profile.version}); routing also detected this service in the document.',
                 ROUTING_SOURCE)


# --- service status -------------------------------------------------------------

@dataclass(frozen=True)
class Reading:
    """One status reading: from a linked evidence passage, or from routing's mentions of the family."""
    status: str
    cues: tuple[str, ...]
    origin: str  # evidence | routing
    passage: str


@dataclass(frozen=True)
class StatusOutcome:
    state: str  # performed | incomplete | not_performed | uncertain
    decisive: Optional[Reading]
    # performed/incomplete: a linked passage that reads otherwise; not_performed: routing reads the family as performed
    contrary: Optional[Reading] = None
    incomplete: Optional[Reading] = None
    # uncertain only: 'hedged' (the code's own passage hedges) or 'unnamed' (its passage reads as performed
    # but the document never names the code's service family).
    reason: str = ''


def normalise_span_status(value) -> Optional[tuple[str, tuple[str, ...]]]:
    """Accept a status string, a (status, cues) pair, or an object/dict with ``status`` and ``cues``.

    ``None`` (or a ``None`` status) means the span carries no status reading.
    Anything else is a contract violation and raises, so a mismatch can never
    pass silently as a reading.
    """
    if value is None:
        return None
    if isinstance(value, str):
        status, cues = value, ()
    elif isinstance(value, (tuple, list)) and value:
        status, cues = value[0], value[1] if len(value) > 1 else ()
    elif isinstance(value, dict) and 'status' in value:
        status, cues = value['status'], value.get('cues') or ()
    elif hasattr(value, 'status'):
        status, cues = value.status, getattr(value, 'cues', ()) or ()
    else:
        raise TypeError(f'status_for_span returned an unsupported value of type {type(value).__name__}.')
    if status is None:
        return None
    if status not in SERVICE_STATUSES:
        raise ValueError(f'status_for_span returned an unknown status {status!r}.')
    if cues is None:
        cues = ()
    elif isinstance(cues, str):
        cues = (cues,)
    if not isinstance(cues, (tuple, list)) or not all(isinstance(cue, str) for cue in cues):
        raise TypeError('status_for_span returned cues that are not a sequence of text.')
    return status, tuple(cues)


def routing_readings(finding: Optional[FamilyFinding]) -> tuple[Reading, ...]:
    if finding is None:
        return ()
    readings = (tuple(Reading(m.status, tuple(m.cues), 'routing', m.sentence.text or m.span.text)
                      for m in finding.mentions) or (Reading(finding.status, (), 'routing', ''),))
    unknown = sorted({r.status for r in readings if r.status not in SERVICE_STATUSES})
    if unknown:
        raise ValueError(f'Routing gave {finding.family} unknown statuses {unknown}.')
    return readings


def _first(readings: Sequence[Reading], statuses: Sequence[str]) -> Optional[Reading]:
    return next((reading for reading in readings if reading.status in statuses), None)


# Routing's reading of a span that carries no status wording at all. Only this is "silent"; any other
# 'uncertain' saw a hedge (a condition, a question, an unclear plan) and is the code's own answer.
SILENT_CUE_PREFIX = 'uncertain: no performance evidence'


def _silent(reading: Reading) -> bool:
    return reading.status == 'uncertain' and all(cue.startswith(SILENT_CUE_PREFIX) for cue in reading.cues)


def resolve_status(readings: Sequence[Reading], *, detectable: bool = False) -> StatusOutcome:
    """A code's own evidence decides first; routing decides only when that evidence is silent. Fail-closed.

    - A linked passage that reads as planned / historical / cancelled / negated excludes the code even when
      the family is performed elsewhere (another passage may support a different code of the same family);
      the exclusion stays reinstatable and names the performed mention.
    - A linked passage that hedges holds the code for clarification; routing never overrides it.
    - A positive passage cannot establish a family that routing documents only as not performed, nor
      (``detectable``: routing can recognise the family in text) a family the document never names.
    """
    own = [r for r in readings if r.origin == 'evidence']
    routed = [r for r in readings if r.origin == 'routing']
    own_positive, own_negative = _first(own, POSITIVE), _first(own, NEGATIVE)
    own_hedged = next((r for r in own if r.status == 'uncertain' and not _silent(r)), None)
    routed_positive, routed_negative = _first(routed, POSITIVE), _first(routed, NEGATIVE)
    incomplete = _first(readings, ('incomplete',))

    def positive(decisive: Reading, contrary: Optional[Reading] = None) -> StatusOutcome:
        return StatusOutcome('incomplete' if incomplete else 'performed', decisive, contrary=contrary,
                             incomplete=incomplete)

    if own_positive:
        if routed_negative and not routed_positive:
            return StatusOutcome('not_performed', routed_negative, contrary=own_positive)
        if detectable and not routed:
            return StatusOutcome('uncertain', own_positive, reason='unnamed')
        return positive(own_positive, contrary=own_negative)
    if own_negative:
        return StatusOutcome('not_performed', own_negative, contrary=routed_positive)
    if own_hedged:
        return StatusOutcome('uncertain', own_hedged, contrary=routed_positive, reason='hedged')
    if routed_positive:
        return positive(routed_positive)
    if routed_negative:
        return StatusOutcome('not_performed', routed_negative)
    return StatusOutcome('uncertain', _first(readings, ('uncertain',)))


def cite(reading: Reading) -> str:
    """'“<passage>” (cue “<cue>”, linked passage)'; routing readings say 'routing' instead."""
    origin = 'linked passage' if reading.origin == 'evidence' else 'routing'
    cue = next((c.strip() for c in reading.cues if c.strip()), '')
    detail = f'cue “{excerpt(cue)}”, {origin}' if cue else origin
    if reading.passage.strip():
        return f'“{excerpt(reading.passage)}” ({detail})'
    return f'per {detail}'


def service_name(profile: ServiceProfile, code: str) -> str:
    return profile.label if profile.supported else f'the service reported as {code}'


def status_check(outcome: StatusOutcome, name: str) -> Check:
    label = 'Service performed on this encounter'
    decisive = outcome.decisive
    if outcome.state in POSITIVE:
        detail = f'Documented as {decisive.status}: {cite(decisive)}.'
        if outcome.contrary:
            detail += f' Another linked passage reads as {outcome.contrary.status}: {cite(outcome.contrary)}.'
            return Check('service.status', label, 'warn', detail, STATUS_SOURCE)
        return Check('service.status', label, 'pass', detail, STATUS_SOURCE)
    if outcome.state == 'not_performed':
        return Check('service.status', label, 'fail', exclusion_reason(outcome, name), STATUS_SOURCE)
    return Check('service.status', label, 'warn', uncertain_reason(outcome, name), STATUS_SOURCE)


def exclusion_reason(outcome: StatusOutcome, name: str) -> str:
    reason = (f'Documented as {outcome.decisive.status}, not as performed on the date of service: '
              f'{cite(outcome.decisive)}.')
    if outcome.contrary:
        reason += (f' {name[0].upper()}{name[1:]} is documented as {outcome.contrary.status} elsewhere: '
                   f'{cite(outcome.contrary)}. Reinstate if this code is supported.')
    return reason


def uncertain_reason(outcome: StatusOutcome, name: str) -> str:
    reason = f'No documentation establishes that {name} was performed on the date of service.'
    if outcome.reason == 'unnamed' and outcome.decisive:
        reason += (f' The linked passage reads as {outcome.decisive.status} ({cite(outcome.decisive)}), but the '
                   f'document never names {name}.')
    elif outcome.decisive:
        reason += f' Read as uncertain: {cite(outcome.decisive)}.'
    if outcome.contrary:
        reason += f' Routing reads it as {outcome.contrary.status} elsewhere: {cite(outcome.contrary)}.'
    return reason


def performed_clarification(outcome: StatusOutcome, name: str, family: str, key: str) -> ClarificationSpec:
    return ClarificationSpec(scope='proposal', fact='performed_status',
                             question=f'Confirm whether {name} was performed on the date of service.',
                             reason=uncertain_reason(outcome, name), family=family, proposal_key=key)


def incomplete_check(outcome: StatusOutcome) -> Check:
    return Check('service.incomplete', 'Incomplete procedure documented', 'warn',
                 f'Documented as incomplete: {cite(outcome.incomplete)}. Kept for review: not treated as completed '
                 'and not excluded.', STATUS_SOURCE)


def incomplete_consideration(code: str, pfs: Optional[dict], release: str) -> str:
    text = ('Incomplete procedure: whether modifier 52 or 53 applies, or whether a different code describes the '
            'service actually performed, depends on the documented extent reached, the documented reason the '
            'procedure was not completed and the applicable payer rules, which are not connected to CPT Studio. '
            'No modifier is assigned.')
    if pfs and '53' in pfs.get('modifier_rows', ()):
        text += f' CMS PFS {release} carries a separate row for {code} with modifier 53.'
    return text


# --- required documentation -----------------------------------------------------

FACT_LABELS = {
    'setting': 'place of service',
    'patient_status': 'new or established patient status',
    'em_basis': 'basis for the visit level (total time or medical decision making)',
    'extent': 'extent reached',
    'target': 'structure examined',
    'cannulation': 'cannulation outcome',
}
FACT_QUESTIONS = {
    'setting': '{label}: confirm the place of service (for example office or hospital outpatient).',
    'patient_status': '{label}: confirm whether the patient is new or established.',
    'em_basis': '{label}: confirm whether the visit level rests on total time on the date of service or on medical '
                'decision making.',
    'extent': '{label}: confirm the furthest extent reached.',
    'target': '{label}: confirm the structure examined.',
    'cannulation': '{label}: confirm whether, and which, duct was cannulated.',
}


def fact_label(name: str) -> str:
    return FACT_LABELS.get(name, name.replace('_', ' '))


@dataclass(frozen=True)
class FactState:
    name: str
    fact: Optional[Fact]
    problem: str  # '' | missing | conflict


def is_documented(fact: Optional[Fact]) -> bool:
    return fact is not None and fact.origin in DOCUMENTED and fact.value not in (None, '')


def _problem(fact: Optional[Fact]) -> str:
    if is_documented(fact):
        return ''
    return 'conflict' if fact is not None and fact.origin == 'conflict' else 'missing'


def required_fact_states(profile: ServiceProfile, finding: Optional[FamilyFinding],
                         context: Mapping[str, Fact]) -> tuple[FactState, ...]:
    """Context facts (which carry member-supplied values) come from the context; the rest from routing,
    where a fact routing itself lists as missing stays missing."""
    states = []
    for name in profile.required_facts:
        if name in CONTEXT_FACTS:
            fact = context.get(name)
            problem = _problem(fact)
        else:
            fact = next((f for f in finding.facts if f.name == name), None) if finding else None
            listed_missing = finding is not None and name in finding.missing
            problem = _problem(fact) or ('missing' if listed_missing else '')
        states.append(FactState(name, fact, problem))
    return tuple(states)


def required_facts_check(profile: ServiceProfile, states: Sequence[FactState]) -> Optional[Check]:
    if not states:
        return None
    documented = [f'{fact_label(s.name)} = {excerpt(str(s.fact.value))}' for s in states if not s.problem]
    missing = [fact_label(s.name) for s in states if s.problem == 'missing']
    conflicting = [fact_label(s.name) for s in states if s.problem == 'conflict']
    parts = []
    if missing:
        parts.append(f'Not documented: {"; ".join(missing)}.')
    if conflicting:
        parts.append(f'Conflicting values documented: {"; ".join(conflicting)}.')
    if documented:
        parts.append(f'Documented: {"; ".join(documented)}.')
    status = 'warn' if missing or conflicting else 'pass'
    return Check('facts.required', 'Required documentation (CPT Studio profile)', status, ' '.join(parts),
                 f'cpt-studio:{profile.version}')


def _conflict_values(fact: Fact) -> str:
    quoted = [f'“{excerpt(span.text)}”' for span in fact.evidence if span.text.strip()]
    return ', '.join(quoted) or excerpt(fact.note) or 'values not quoted'


def fact_clarifications(states: Sequence[FactState], profile: ServiceProfile, family: str,
                        key: str) -> tuple[ClarificationSpec, ...]:
    out = []
    for state in states:
        if not state.problem:
            continue
        template = FACT_QUESTIONS.get(state.name)
        question = (template.format(label=profile.label) if template
                    else f'{profile.label}: confirm the documented {fact_label(state.name)}.')
        if state.problem == 'conflict':
            reason = (f'The document gives conflicting values for the {fact_label(state.name)}: '
                      f'{_conflict_values(state.fact)}.')
        else:
            reason = f'The {fact_label(state.name)} is not documented; the {profile.label} profile requires it.'
        out.append(ClarificationSpec(scope='proposal', fact=state.name, question=question, reason=reason,
                                     family=family, proposal_key=key))
    return tuple(out)


# --- E/M with a same-day procedure ------------------------------------------------

SEPARATE_EM_QUESTION = ('Was a significant, separately identifiable evaluation and management service performed on '
                        'the date of service, beyond the usual pre-procedure assessment? If so, add that '
                        'documentation.')
SEPARATE_EM_CONSIDERATION = ('Modifier 25 is a consideration only if a significant, separately identifiable E/M '
                             'service is documented; CPT Studio never assigns it.')


def same_day_reason(labels: Sequence[str]) -> str:
    verb = 'is' if len(labels) == 1 else 'are'
    return (f'{_join(labels)} {verb} documented as performed on the same date; a significant, separately '
            'identifiable E/M service is not established by this document.')


def separate_em_statement(finding) -> Optional[str]:
    """The documented statement of a significant, separately identifiable E/M, or None."""
    for fact in getattr(finding, 'facts', ()) or ():
        if fact.name == 'separate_em' and fact.value == 'documented' and fact.origin == 'document' and fact.evidence:
            return fact.evidence[0].text
    return None


def em_procedure_check(labels: Sequence[str], global_days_note: str, documented: Optional[str] = None) -> Check:
    if documented is not None:
        verb = 'is' if len(labels) == 1 else 'are'
        detail = (f'{_join(labels)} {verb} documented as performed on the same date. The documentation states a '
                  f'significant, separately identifiable E/M service (\u201c{documented}\u201d); whether it '
                  'supports a separate E/M code is the reviewer\u2019s judgement.')
        return Check('em.same_day_procedure', 'Separately identifiable E/M on a procedure day', 'warn',
                     f'{detail} {global_days_note}'.strip(), EM_SOURCE)
    return Check('em.same_day_procedure', 'Separately identifiable E/M on a procedure day', 'warn',
                 f'{same_day_reason(labels)} {global_days_note}'.strip(), EM_SOURCE)


def reinstatement_check(holds: Sequence[ClarificationSpec], *, date_unknown: bool) -> Check:
    """For an excluded, reinstatable code: what approval would wait for if a reviewer reinstated it.

    A reinstated code is held to the same gates as a selected one (required facts, the separately
    identifiable E/M on a procedure day, a known date of service). Review offers approve on a reinstated
    code only while this check passes.
    """
    label = 'Approval after reinstatement'
    waits = (['the date of service is not established for this encounter.'] if date_unknown else []) + [
        spec.question for spec in holds]
    if not waits:
        return Check('review.reinstatement', label, 'pass',
                     'If a reviewer reinstates this code, it can be approved: no clarification would be pending.',
                     REINSTATEMENT_SOURCE)
    return Check('review.reinstatement', label, 'warn',
                 'If a reviewer reinstates this code, it can only be rejected until the documentation is completed '
                 '(add it as an addendum): ' + ' '.join(waits), REINSTATEMENT_SOURCE)


def separate_em_clarification(labels: Sequence[str], family: str, key: str) -> ClarificationSpec:
    return ClarificationSpec(scope='proposal', fact='separate_em', question=SEPARATE_EM_QUESTION,
                             reason=same_day_reason(labels), family=family, proposal_key=key)


def global_days_note(entries: Sequence[tuple[str, str]], release: str, unavailable: str) -> str:
    """``entries``: (code, global days) of the same-day procedure codes that have a PFS row."""
    if entries:
        listed = ', '.join(f'{code} {days}' for code, days in entries)
        return f'CMS PFS global days ({release}): {listed}.'
    return f'Global days are not verified: {unavailable}'


# --- CMS references ---------------------------------------------------------------

def applied_source(kind: str, ref: CodeReference,
                   sources: Sequence[ReferenceSourceInfo]) -> Optional[ReferenceSourceInfo]:
    return next((s for s in sources if s.kind == kind and s.key in ref.applicable_sources), None)


def unavailable_reason(kind: str, sources: Sequence[ReferenceSourceInfo], service_date: Optional[date]) -> str:
    if service_date is None:
        return UNKNOWN_DATE_NOTE
    label = KIND_LABELS[kind]
    installed = [s for s in sources if s.kind == kind]
    if not installed:
        return f'No {label} source is installed.'
    covering = [s for s in installed if source_applies(s, service_date)]
    if covering:
        return (f'{len(covering)} installed {label} releases cover {service_date.isoformat()}; none was applied '
                'because the applicable release is ambiguous.')
    windows = '; '.join(f'{s.release} {s.effective_start} to {s.effective_end}' for s in installed)
    return f'No installed {label} release covers {service_date.isoformat()} (installed: {windows}).'


def _reference_source_label(source: ReferenceSourceInfo) -> str:
    return f'{source.key} {source.release}'


def pfs_check(code: str, ref: CodeReference, sources: Sequence[ReferenceSourceInfo],
              service_date: Optional[date]) -> Check:
    label = 'Present in the CMS fee schedule file'
    source = applied_source(PFS, ref, sources)
    if source is None:
        return Check('pfs.presence', label, 'not_verified', unavailable_reason(PFS, sources, service_date), '')
    origin = _reference_source_label(source)
    pfs = ref.pfs
    if pfs is None:
        prefix = modifier_only_prefix(code, source.release)
        detail = next((note for note in ref.notes if note.startswith(prefix)), f'Not listed in {source.release}.')
        return Check('pfs.presence', label, 'warn', detail, origin)
    extra = f', endoscopic base {pfs["endo_base"]}' if pfs.get('endo_base') else ''
    return Check('pfs.presence', label, 'pass',
                 f'Listed in {source.release} with status {pfs["status"]} (global days {pfs["global_days"]}, '
                 f'multiple procedure indicator {pfs["mult_proc"]}{extra}).', origin)


def mue_check(code: str, units: int, ref: CodeReference, sources: Sequence[ReferenceSourceInfo],
              service_date: Optional[date]) -> Check:
    label = 'Units within the practitioner MUE'
    source = applied_source(MUE, ref, sources)
    if source is None:
        return Check('mue.units', label, 'not_verified', unavailable_reason(MUE, sources, service_date), '')
    origin = _reference_source_label(source)
    mue = ref.mue
    if mue is None:
        return Check('mue.units', label, 'not_verified',
                     f'{code} is not listed in {source.release}; units are not verified against an MUE.', origin)
    mai = mue['mai']
    basis = f'MAI {mai["indicator"]}: {mai["label"]}'
    if mue.get('rationale'):
        basis += f'; rationale: {mue["rationale"]}'
    if units > mue['value']:
        return Check('mue.units', label, 'fail',
                     f'{plural(units, "unit")} exceed the MUE of {mue["value"]} for {code} in {source.release} '
                     f'({basis}).', origin)
    return Check('mue.units', label, 'pass',
                 f'{plural(units, "unit")} within the MUE of {mue["value"]} for {code} in {source.release} ({basis}).',
                 origin)


ENDOSCOPIC_PAIR = ('base endoscopy reported with a therapeutic code of the same family '
                   '(CMS PFS endoscopic base relationship)')


def endoscopic_check(code: str, ref: CodeReference, active: Mapping[str, dict], sources: Sequence[ReferenceSourceInfo],
                     service_date: Optional[date]) -> Check:
    """``active``: code -> PFS row of every selected, non-excluded proposal that has one."""
    label = 'Endoscopic family combination'
    source = applied_source(PFS, ref, sources)
    if source is None or ref.pfs is None:
        reason = (unavailable_reason(PFS, sources, service_date) if source is None
                  else f'{code} has no unmodified row in {source.release}.')
        origin = _reference_source_label(source) if source else ''
        return Check('pfs.endoscopic_base', label, 'not_verified', reason, origin)
    base = ref.pfs.get('endo_base')
    therapeutic = sorted(other for other, row in active.items() if other != code and row.get('endo_base') == code)
    siblings = sorted(other for other, row in active.items() if base and other != code and row.get('endo_base') == base)
    warnings = []
    if therapeutic:
        warnings.append(f'{code} is the endoscopic base of {_join(therapeutic)} in {source.release}, also selected: '
                        f'{ENDOSCOPIC_PAIR}.')
    if base and base != code and base in active:
        warnings.append(f'{code} has the endoscopic base {base} in {source.release}, also selected: {ENDOSCOPIC_PAIR}.')
    notes = []
    if siblings:
        indicator = ref.pfs.get('mult_proc')
        rule = ': multiple endoscopy rule' if indicator == '3' else ''
        notes.append(f'{_join([code] + siblings)} share the endoscopic base {base} in {source.release} (multiple '
                     f'procedure indicator {indicator}){rule}.')
    origin = _reference_source_label(source)
    if warnings:
        return Check('pfs.endoscopic_base', label, 'warn', ' '.join(warnings + notes), origin)
    if notes:
        return Check('pfs.endoscopic_base', label, 'info', ' '.join(notes), origin)
    return Check('pfs.endoscopic_base', label, 'pass',
                 f'No other selected code shares an endoscopic base relationship with {code} in {source.release}.',
                 origin)


def pctc_consideration(code: str, pfs: Optional[dict], release: str, billing: str) -> str:
    if not pfs or not {'26', 'TC'} <= set(pfs.get('modifier_rows', ())):
        return ''
    return (f'CMS PFS {release} carries separate professional-component (26) and technical-component (TC) rows for '
            f'{code}; which one applies depends on the billing context ({billing}). No modifier is assigned.')


NOT_CONNECTED_CHECKS = (
    Check('cpt.membership', 'CPT code-set membership for the service date', 'not_verified',
          'No licensed CPT edition is connected; code-set membership for the service date is not verified.', ''),
    Check('cpt.descriptor', 'CPT descriptor', 'not_verified',
          'Description withheld — no licensed CPT descriptor is connected.', ''),
    Check('ncci.ptp', 'NCCI procedure-to-procedure edits', 'not_verified',
          'NCCI procedure-to-procedure edits are not connected (CMS serves them only behind an AMA point-and-click '
          'agreement).', ''),
)


def duplicate_check(code: str, count: int) -> Check:
    return Check('units.duplicate', 'Duplicate selections', 'warn',
                 f'The provider selected {code} {count} times; it is one proposal with {count} units. Confirm the '
                 'number of separately documented services.', UNITS_SOURCE)


# --- service date -----------------------------------------------------------------

@dataclass(frozen=True)
class DateState:
    value: Optional[date]
    origin: str  # document | user | given | missing | unreadable | conflict
    fact: Optional[Fact] = None


def _iso_date(value) -> Optional[date]:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def service_date_state(context: Mapping[str, Fact], service_date: Optional[date]) -> DateState:
    """The usable service date. ``service_date`` must agree with the context fact when one exists."""
    fact = context.get('service_date')
    if fact is None:
        return DateState(service_date, 'given' if service_date else 'missing')
    documented = _iso_date(fact.value) if fact.origin in DOCUMENTED else None
    if service_date != documented:
        raise ValueError(f'service_date {service_date} does not match the context service_date fact '
                         f'({fact.origin}: {fact.value!r}).')
    if documented is not None:
        return DateState(documented, fact.origin, fact)
    if fact.origin == 'conflict':
        return DateState(None, 'conflict', fact)
    return DateState(None, 'unreadable' if fact.origin in DOCUMENTED and fact.value else 'missing', fact)


def _date_problem(state: DateState) -> str:
    if state.origin == 'conflict':
        return f'Conflicting dates of service are documented ({_conflict_values(state.fact)})'
    if state.origin == 'unreadable':
        return f'The date of service “{excerpt(str(state.fact.value))}” is not a readable date'
    return 'No date of service is documented'


def service_date_check(state: DateState) -> Check:
    label = 'Service date'
    if state.value is None:
        return Check('context.service_date', label, 'fail',
                     f'{_date_problem(state)}; reference applicability cannot be established.', CONTEXT_SOURCE)
    day = state.value.isoformat()
    if state.origin == 'user':
        detail = f'Date of service {day}, entered by a workspace member as encounter metadata.'
    elif state.origin == 'document':
        quoted = next((span.text for span in state.fact.evidence if span.text.strip()), '')
        detail = f'Date of service {day} is documented' + (f' (“{excerpt(quoted)}”).' if quoted else '.')
    else:
        detail = f'Date of service {day}.'
    return Check('context.service_date', label, 'pass', detail, CONTEXT_SOURCE)


def service_date_clarification(state: DateState) -> Optional[ClarificationSpec]:
    if state.value is not None:
        return None
    return ClarificationSpec(scope='encounter', fact='service_date',
                             question='Confirm the date of service for this encounter.',
                             reason=f'{_date_problem(state)}; every service and every dated reference check '
                                    'depends on it.')


PROPOSAL_DATE_CHECK = Check('context.service_date', 'Service date', 'fail',
                            'No usable date of service; this proposal waits on the encounter-level service date '
                            'question and date-dependent checks cannot run.', CONTEXT_SOURCE)


# --- encounter checks -------------------------------------------------------------

NO_PROPOSALS = 'This is not a finding that no codes apply.'


def provider_checks(provider_status: str, normalized: Optional[NormalizedResponse]) -> tuple[Check, ...]:
    label = 'Proposal provider'
    if provider_status == 'not_run':
        return (Check('provider.status', label, 'not_verified',
                      f'The proposal provider was not run for this revision, so there are no CPT proposals. '
                      f'{NO_PROPOSALS}', PROVIDER_SOURCE),)
    if provider_status == 'failed':
        return (Check('provider.status', label, 'fail',
                      'The proposal provider did not return a usable result (it failed, was not sent or was '
                      f'cancelled), so there are no CPT proposals. {NO_PROPOSALS}', PROVIDER_SOURCE),)
    if provider_status == 'unknown':
        return (Check('provider.status', label, 'warn',
                      'The proposal provider request was sent but its outcome is unknown, so there are no CPT '
                      'proposals; a workspace member must reconcile it before any new attempt. '
                      f'{NO_PROPOSALS}', PROVIDER_SOURCE),)
    selected = sum(1 for code in normalized.codes if code.role == 'selected')
    others = len(normalized.codes) - selected
    origin = f'{normalized.provider} ({normalized.adapter_version})'
    if selected:
        check = Check('provider.status', label, 'pass',
                      f'{origin} returned {plural(selected, "selected CPT-labelled code")} and '
                      f'{plural(others, "candidate or alternative")}.', PROVIDER_SOURCE)
    else:
        check = Check('provider.status', label, 'warn',
                      f'{origin} returned no selected CPT-labelled code ({plural(others, "candidate or alternative")}, '
                      'which cannot be approved).', PROVIDER_SOURCE)
    if not normalized.problems:
        return (check,)
    problems = Check('provider.problems', 'Provider response problems', 'warn',
                     f'{plural(len(normalized.problems), "problem")} reading the provider response: '
                     + '; '.join(normalized.problems), PROVIDER_SOURCE)
    return check, problems


def unlisted_codes_check(count: int, limit: int) -> Check:
    """Provider codes too malformed to list. Never quoted: an over-long 'code' may carry provider wording."""
    pronoun = 'it is' if count == 1 else 'they are'
    return Check('provider.unlisted', 'Provider codes not listed', 'warn',
                 f'The provider returned {plural(count, "code")} that cannot be listed: empty, or longer than {limit} '
                 f'characters (a CPT code has five). {pronoun[0].upper()}{pronoun[1:]} not shown and never truncated.',
                 PROVIDER_SOURCE)


def extraction_check(status: Optional[str], messages: Sequence[str]) -> Check:
    label = 'Text extraction'
    listed = ' '.join(m.strip() for m in messages if m.strip())
    if status is None:
        return Check('extraction.status', label, 'not_verified',
                     'The extraction status was not supplied to the validation engine.', EXTRACTION_SOURCE)
    if status == 'ok' and not listed:
        return Check('extraction.status', label, 'pass', 'Text extraction reported no limitations.', EXTRACTION_SOURCE)
    if status == 'ok':
        return Check('extraction.status', label, 'info', f'Text extraction completed with notes: {listed}',
                     EXTRACTION_SOURCE)
    if status == 'partial':
        return Check('extraction.status', label, 'warn',
                     'Text extraction was partial; services documented only in unextracted parts cannot be detected '
                     f'or proposed. {listed}'.strip(), EXTRACTION_SOURCE)
    if status == 'failed':
        return Check('extraction.status', label, 'fail', f'Text extraction failed. {listed}'.strip(),
                     EXTRACTION_SOURCE)
    raise ValueError(f'Unknown extraction status {status!r}.')


VISIT_NOT_MISSED = ('An E/M mention beside a same-day procedure is not counted as a missed service: a separate E/M '
                    'needs significant, separately identifiable documentation.')


def unproposed_check(missed: Sequence[str], visit_beside_procedure: bool) -> Check:
    """``visit_beside_procedure``: routing found an E/M service on a procedure day that was not counted as missed."""
    label = 'Performed services without a proposal'
    if missed:
        verb = 'is' if len(missed) == 1 else 'are'
        detail = f'Possible missed service: {_join(missed)} {verb} documented as performed with no selected proposal.'
        if visit_beside_procedure:
            detail += f' {VISIT_NOT_MISSED}'
        return Check('services.unproposed', label, 'warn', detail, COVERAGE_SOURCE)
    if visit_beside_procedure:
        return Check('services.unproposed', label, 'info', VISIT_NOT_MISSED, COVERAGE_SOURCE)
    return Check('services.unproposed', label, 'pass', 'Every performed service has a selected proposal.',
                 COVERAGE_SOURCE)


def unsupported_check(entries: Sequence[dict]) -> Check:
    label = 'Services outside the GI profiles'
    if not entries:
        return Check('services.unsupported', label, 'pass', 'No performed service falls outside the GI profiles.',
                     COVERAGE_SOURCE)
    names = [entry['label'] for entry in entries]
    return Check('services.unsupported', label, 'warn',
                 f'Performed without a GI profile in this release: {_join(names)}. Review required.', COVERAGE_SOURCE)


# --- reference sources ------------------------------------------------------------

NOT_CONNECTED_SOURCES = (
    {'key': 'ama-cpt', 'kind': 'cpt-code-set', 'publisher': 'American Medical Association',
     'title': 'CPT code set (AMA)', 'release': '', 'url': '', 'sha256': '', 'effective_start': '',
     'effective_end': '', 'applies': False, 'connected': False,
     'license_note': 'No CPT edition is licensed.',
     'scope_note': 'NOT CONNECTED: code-set membership for the service date is not verified and descriptors are '
                   'withheld.'},
    {'key': 'cms-ncci-ptp', 'kind': 'ncci-ptp', 'publisher': 'Centers for Medicare & Medicaid Services (CMS)',
     'title': 'NCCI PTP edits', 'release': '', 'url': '', 'sha256': '', 'effective_start': '', 'effective_end': '',
     'applies': False, 'connected': False,
     'license_note': 'CMS serves the PTP tables only behind an AMA point-and-click agreement, which has not been '
                     'accepted.',
     'scope_note': 'NOT CONNECTED: procedure-to-procedure edits are not verified.'},
)


def reference_source_entries(sources: Sequence[ReferenceSourceInfo], service_date: Optional[date]) -> tuple[dict, ...]:
    """Every installed source, with ``applies`` true only for the one source of its kind used for the date."""
    applied = {source.key for source in applied_sources(sources, service_date).values()}
    entries = []
    for s in sources:
        covers = source_applies(s, service_date)
        note = 'Not applied: another installed release of this kind also covers the date.' if (
            covers and s.key not in applied) else ''
        entries.append({'key': s.key, 'kind': s.kind, 'publisher': s.publisher, 'title': s.title,
                        'release': s.release, 'url': s.url, 'sha256': s.sha256,
                        'effective_start': s.effective_start, 'effective_end': s.effective_end,
                        'applies': s.key in applied, 'connected': True, 'note': note,
                        'license_note': s.license_note, 'scope_note': s.scope_note})
    return tuple(entries) + tuple(dict(entry, note='') for entry in NOT_CONNECTED_SOURCES)


# --- status_for_span seam ---------------------------------------------------------

def span_status(text: str, start: int, end: int, service_date: Optional[date] = None):
    """``studio.gi.detect.status_for_span``, resolved at call time: the routing module owns status language.
    ``service_date`` is the encounter's effective date, so dated history reads the same here as in routing."""
    from studio.gi.detect import status_for_span
    return status_for_span(text, start, end, service_date)


def evidence_readings(text: str, spans: Sequence[EvidenceSpan],
                      service_date: Optional[date] = None) -> tuple[Reading, ...]:
    readings = []
    for span in spans:
        parsed = normalise_span_status(span_status(text, span.start, span.end, service_date))
        if parsed is not None:
            readings.append(Reading(parsed[0], parsed[1], 'evidence', span.text))
    return tuple(readings)
