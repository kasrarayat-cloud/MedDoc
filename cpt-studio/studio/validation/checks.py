"""Pure validation checks (ARCHITECTURE 5.6): plain data in, ``Check`` values out.

No I/O and no database access. A check never upgrades a status because two
sources agree, never states a rule the system does not hold, and reports
``not_verified`` with the reason whenever a reference is unavailable.
"""
from __future__ import annotations

import bisect
import functools
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping, Optional, Sequence

from studio.gi.profiles import DETECTED_FAMILIES, PROFILES, PROFILES_VERSION, ServiceProfile
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
    start: Optional[int] = None  # a linked passage's offsets in the text
    end: Optional[int] = None
    # Set by the engine on a linked passage of a gi.other code: a positive reading that rests on its section or on E/M
    # documentation alone, in a passage that is not read as documenting the code's own procedure as done (see
    # engine._unnamed_other). It is not evidence that the code's service was done.
    unnamed: bool = False
    # Set by the engine on a linked passage that hedges another service than the code's (see engine._other_service):
    # "Possible EGD if symptoms persist." cited for an E/M. It holds the code alone, but never contests it.
    other_service: bool = False


@dataclass(frozen=True)
class StatusOutcome:
    state: str  # performed | incomplete | not_performed | uncertain
    decisive: Optional[Reading]
    # performed/incomplete: a linked passage that reads otherwise; not_performed: routing reads the family as performed
    contrary: Optional[Reading] = None
    incomplete: Optional[Reading] = None
    # uncertain only: 'hedged' (the code's own passage hedges), 'unnamed' (its passage reads as performed but the
    # document never names the code's service family), 'unestablished' (its passage reads as performed but routing
    # names the family only as uncertain; ``contrary`` is that routing reading), 'contested' (one of its own
    # passages reads as performed and another hedges; ``decisive`` is the hedge, ``contrary`` the performed one) or
    # 'section_only' (every positive passage of a gi.other code reads performed only by its section or as the office
    # visit's own documentation, and is not read as documenting the code's own procedure as done; ``decisive`` is that
    # passage).
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
# Routing's cue for an explicit performance statement ("was performed", "was advanced"). On a reading that is not
# 'performed' it survives only where something else downgraded the statement: its plan or history section, or the
# family's document-level judgement.
PERFORMED_CUE_PREFIX = 'performed:'
# Routing's cue for a reading that its section decided ("section: findings (Findings)"): the section default, or the
# section that downgraded an explicit performance statement.
SECTION_CUE_PREFIX = 'section: '


def silent(status: str, cues: Sequence[str]) -> bool:
    """Whether a status reading carries no status wording at all (no cues reads the same way)."""
    return status == 'uncertain' and all(cue.startswith(SILENT_CUE_PREFIX) for cue in cues)


def _silent(reading: Reading) -> bool:
    return silent(reading.status, reading.cues)


# Routing's cue for a reading of the office visit's own documentation ("performed: office E/M documentation (visit
# statement)"): it says the visit was documented, never that a procedure was done.
EM_DOCUMENTATION_CUE_PREFIX = 'performed: office E/M documentation'
# Routing's cue for a plan-section passage whose clause says today (studio.gi.detect.PLAN_TODAY, round 3b): its section
# no longer makes it planned, it only holds it. Part of the cue contract (ARCHITECTURE 5.3 / 5.6).
PLAN_TODAY_CUE = 'uncertain: its clause says today, so its plan section does not make it planned'


def says_today_in_plan(cues: Sequence[str]) -> bool:
    """Whether routing held a plan-section passage only because its clause says today (PLAN_TODAY_CUE)."""
    return any(cue.startswith(PLAN_TODAY_CUE) for cue in cues)


# Routing's own holds of a procedure, never hedges (studio.gi.detect.OTHER_STATED, ANOTHER_TIME_PREFIX; part of the cue
# contract): a procedure stated by its act or its findings with no performance cue ("Two internal hemorrhoids were
# banded today without complication."), and a time that may place it on another date ("... was performed an hour
# ago.").
_VAL_OTHER_STATED_CUE = 'uncertain: a procedure is stated by its act or its findings'
_VAL_ANOTHER_TIME_CUE = 'uncertain: another time'


# Validation's hold of an E/M code's own negative reading that is about another service its passage names (round 4
# validation:6): "No laboratory testing, imaging, endoscopy or other procedure was performed at this encounter." denies
# other services, not the visit. Never silent and never an exclusion: the E/M is held, and a reviewer decides.
_VAL_OTHER_SERVICE_CUE = 'uncertain: its negative reading is about another service it names, not about this visit'
# Words that name a service other than the visit, beside routing's own procedure form (_PROCEDURE_WORD) and its named
# services: used only to hold an E/M's negative reading, never to release or exclude anything.
_VAL_SERVICE_NOUNS = re.compile(r'\b(?:procedures?|tests?|testing|imaging|laborator(?:y|ies)|labs?)\b', re.A | re.I)


def _VAL_names_other_service(text: str, start: int, end: int, service_date: Optional[date] = None) -> bool:
    """Whether the passage [start, end) names a service other than the visit: by routing's own procedure form
    (detect._PROCEDURE_WORD: "endoscopy", "banding") or service names and intervention words (touches_service), or by
    a test or procedure word (_VAL_SERVICE_NOUNS: "laboratory testing", "imaging", "no procedure"). Resolved at call
    time, like span_status."""
    from studio.gi import detect
    an = detect._analysis(text, service_date)[0]
    return bool(detect._PROCEDURE_WORD.search(text, start, end) or an.touches_service(start, end)
                or _VAL_SERVICE_NOUNS.search(text, start, end))


def _VAL_routing_holds(cues: Sequence[str]) -> bool:
    """Whether routing held a passage for a procedure stated with no performance cue, or for a time that may place it on
    another date (round 4 release:7): in a plan, history or indication section these may be today's procedure, as a
    plan clause that says today may (says_today_in_plan)."""
    return any(cue.startswith((_VAL_OTHER_STATED_CUE, _VAL_ANOTHER_TIME_CUE)) for cue in cues)


def by_section_alone(reading: Reading) -> bool:
    """A reading that only its section decided: every cue is a 'section: <kind>' cue (routing's section default), so
    no wording in the passage says anything of a service."""
    return bool(reading.cues) and all(cue.startswith(SECTION_CUE_PREFIX) for cue in reading.cues)


def section_default(reading: Reading) -> bool:
    """A reading its section's default decided, plain or held because its clause says today: every cue is a 'section:
    <kind>' cue or routing's PLAN_TODAY cue, so no wording in the passage says anything of a service."""
    return bool(reading.cues) and all(cue.startswith((SECTION_CUE_PREFIX, PLAN_TODAY_CUE)) for cue in reading.cues)


def states_no_procedure(reading: Reading) -> bool:
    """A reading that only its section or the office visit's own documentation decided: every cue is a 'section:
    <kind>' cue or routing's E/M documentation cue, so nothing in the passage states that a procedure was done. A
    reading that carries the E/M documentation cue is the visit statement's own, so its other 'performed:' cues are the
    visit's words too ("Established patient office visit was performed today.": round 4 validation:3)."""
    visit = any(cue.startswith(EM_DOCUMENTATION_CUE_PREFIX) for cue in reading.cues)
    allowed = (SECTION_CUE_PREFIX, EM_DOCUMENTATION_CUE_PREFIX) + ((PERFORMED_CUE_PREFIX,) if visit else ())
    return bool(reading.cues) and all(cue.startswith(allowed) for cue in reading.cues)


def restated(reading: Reading) -> bool:
    """An explicit performance statement that only its section downgraded ("Colonoscopy with cold snare polypectomy
    was performed today." under Assessment and plan): 'performed:' and 'section: <kind>' cues and nothing else but
    routing's PLAN_TODAY cue, which a plan-section performance statement that says today carries since round 4
    withdrew its release (routing:1). It restates the act; it is not a hedge."""
    return (reading.status == 'uncertain' and any(cue.startswith(PERFORMED_CUE_PREFIX) for cue in reading.cues)
            and any(cue.startswith(SECTION_CUE_PREFIX) for cue in reading.cues)
            and all(cue.startswith((PERFORMED_CUE_PREFIX, SECTION_CUE_PREFIX, PLAN_TODAY_CUE)) for cue in reading.cues))


def resolve_status(readings: Sequence[Reading], *, detectable: bool = False) -> StatusOutcome:
    """A code's own evidence decides first; routing decides only when that evidence is silent. Fail-closed.

    - A linked passage that reads as planned / historical / cancelled / negated excludes the code even when
      the family is performed elsewhere (another passage may support a different code of the same family);
      the exclusion stays reinstatable and names the performed mention.
    - A linked passage that hedges holds the code for clarification; neither routing nor another of the code's own
      passages reading as performed overrides it, and the hold names both passages. Beside a performed passage only a
      hedge about the code's own service holds it: a hedge marked ``other_service`` is named in a warn, and a
      performance statement that only its section downgraded (``restated``) supports the code.
    - A positive passage cannot establish a family that routing documents only as not performed, nor
      (``detectable``: routing can recognise the family in text) a family the document never names or names only
      as uncertain: a passage about another service, or about none in particular, is not evidence for this one.
    - Nor can a passage marked ``unnamed`` (a gi.other code's passage read performed only by its section or as E/M
      documentation, not read as documenting the code's own procedure as done): when it is the only positive passage
      the code is held, never excluded.
    """
    own = [r for r in readings if r.origin == 'evidence']
    routed = [r for r in readings if r.origin == 'routing']
    own_positive = _first([r for r in own if not r.unnamed], POSITIVE) or _first(own, POSITIVE)
    own_negative = _first(own, NEGATIVE)
    own_hedged = next((r for r in own if r.status == 'uncertain' and not _silent(r)), None)
    hedges = [r for r in own if r.status == 'uncertain' and not _silent(r) and not restated(r)]
    own_contesting = next((r for r in hedges if not r.other_service), None)
    own_other = next((r for r in hedges if r.other_service), None)
    routed_positive, routed_negative = _first(routed, POSITIVE), _first(routed, NEGATIVE)
    incomplete = _first(readings, ('incomplete',))

    def positive(decisive: Reading, contrary: Optional[Reading] = None) -> StatusOutcome:
        return StatusOutcome('incomplete' if incomplete else 'performed', decisive, contrary=contrary,
                             incomplete=incomplete)

    if own_positive:
        if routed_negative and not routed_positive:
            return StatusOutcome('not_performed', routed_negative, contrary=own_positive)
        if detectable and not routed_positive:
            named = next((r for r in routed if not _silent(r)), None) or _first(routed, ('uncertain',))
            return StatusOutcome('uncertain', own_positive, contrary=named,
                                 reason='unestablished' if routed else 'unnamed')
        if own_positive.unnamed:
            return StatusOutcome('uncertain', own_positive, contrary=own_hedged or own_negative, reason='section_only')
        if own_contesting:
            return StatusOutcome('uncertain', own_contesting, contrary=own_positive, reason='contested')
        return positive(own_positive, contrary=own_negative or own_other)
    if own_negative:
        return StatusOutcome('not_performed', own_negative, contrary=routed_positive)
    if own_hedged:
        return StatusOutcome('uncertain', own_hedged, contrary=routed_positive, reason='hedged')
    if routed_positive:
        return positive(routed_positive)
    if routed_negative:
        return StatusOutcome('not_performed', routed_negative)
    return StatusOutcome('uncertain', _first(readings, ('uncertain',)))


def _section_cue(reading: Reading) -> str:
    return next((cue for cue in reading.cues if cue.startswith(SECTION_CUE_PREFIX)), '')


def cite(reading: Reading) -> str:
    """'“<passage>” (cue “<cue>”, linked passage)'; routing readings say 'routing' instead. The cue is the one that
    decided the reading: for an explicit performance statement held because of its section, that section's cue."""
    origin = 'linked passage' if reading.origin == 'evidence' else 'routing'
    cue = _section_cue(reading) if restated(reading) else next((c.strip() for c in reading.cues if c.strip()), '')
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
    contrary = outcome.contrary
    if contrary and contrary.origin == 'evidence':
        # The code's own passage reads as performed, but it is not about this service: routing documents the
        # family only as not performed. It is never presented as this service "documented as performed".
        reason += (f' The linked passage reads as {contrary.status} ({cite(contrary)}), but the document does not '
                   f'establish {name} as performed on the date of service. Reinstate if this code is supported.')
    elif contrary:
        reason += (f' {name[0].upper()}{name[1:]} is documented as {contrary.status} elsewhere: '
                   f'{cite(contrary)}. Reinstate if this code is supported.')
    return reason


def uncertain_reason(outcome: StatusOutcome, name: str) -> str:
    if outcome.reason == 'contested' and outcome.decisive and outcome.contrary:
        # Never "no documentation establishes ... performed": one of the code's own passages says it was.
        return (f'A linked passage reads as {outcome.contrary.status}: {cite(outcome.contrary)}, but another linked '
                f'passage reads as uncertain: {cite(outcome.decisive)}. A passage that hedges holds the code, so '
                f'{name} is not established as performed as coded on the date of service.')
    if outcome.reason == 'section_only' and outcome.decisive:
        # Only the linked passages are judged: the document may document the service in a passage not linked to it.
        # Worded from the rule that decided it (engine._unnamed_other), never from what the passage names: it may name
        # a procedure, even the code's own, without being read as documenting it done (round 5 validation:1).
        documented = any(cue.startswith(EM_DOCUMENTATION_CUE_PREFIX) for cue in outcome.decisive.cues)
        basis = 'as E/M documentation' if documented else 'by its section'
        reason = (f'No linked passage establishes that {name} was performed on the date of service: the linked passage '
                  f'reads as {outcome.decisive.status} only {basis} ({cite(outcome.decisive)}), and it is not read as '
                  'documenting that service as done on that date.')
        if outcome.contrary:
            reason += f' Another linked passage reads as {outcome.contrary.status}: {cite(outcome.contrary)}.'
        return reason
    if outcome.reason in ('', 'hedged') and outcome.decisive and restated(outcome.decisive):
        # The act is stated; only its section holds it: never "no documentation establishes ... performed".
        heading = re.match(r'section: (\w+)(?: \((.+)\))?', _section_cue(outcome.decisive))
        where = heading.group(2) or f'its {heading.group(1)} section'
        subject = 'The linked passage' if outcome.decisive.origin == 'evidence' else 'Routing'
        reason = (f'{subject} states {name} as performed under {where}: {cite(outcome.decisive)}; confirm it was '
                  'performed on the date of service.')
        if outcome.contrary:
            reason += f' Routing reads it as {outcome.contrary.status} elsewhere: {cite(outcome.contrary)}.'
        return reason
    reason = f'No documentation establishes that {name} was performed on the date of service.'
    if outcome.reason == 'unnamed' and outcome.decisive:
        reason += (f' The linked passage reads as {outcome.decisive.status} ({cite(outcome.decisive)}), but the '
                   f'document never names {name}.')
    elif outcome.reason == 'unestablished' and outcome.decisive:
        named = f': {cite(outcome.contrary)}' if outcome.contrary else ''
        return (f'{reason} The linked passage reads as {outcome.decisive.status} ({cite(outcome.decisive)}), but the '
                f'document names {name} only as uncertain{named}.')
    elif outcome.decisive:
        reason += f' Read as uncertain: {cite(outcome.decisive)}.'
    if outcome.contrary:
        reason += f' Routing reads it as {outcome.contrary.status} elsewhere: {cite(outcome.contrary)}.'
    return reason


def performed_clarification(outcome: StatusOutcome, name: str, family: str, key: str) -> ClarificationSpec:
    question = f'Confirm whether {name} was performed on the date of service.'
    if outcome.reason == 'contested':
        question = (f'Confirm whether {name} was performed on the date of service as coded: one of its linked passages '
                    'reads as uncertain.')
    return ClarificationSpec(scope='proposal', fact='performed_status', question=question,
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


def _same_day_subject(labels: Sequence[str], possible: Sequence[str] = ()) -> str:
    """Procedures documented as performed, then procedures whose performance is not established (fail-closed:
    an uncertain procedure holds the E/M as a performed one does, until its status is answered)."""
    parts = []
    for items, phrase in ((labels, 'documented as performed on the same date'),
                          (possible, 'possibly performed on the same date (its performance is not established)')):
        if items:
            parts.append(f'{_join(items)} {"is" if len(items) == 1 else "are"} {phrase}')
    return '; '.join(parts)


def same_day_reason(labels: Sequence[str], possible: Sequence[str] = ()) -> str:
    return (f'{_same_day_subject(labels, possible)}; a significant, separately identifiable E/M service is not '
            'established by this document.')


def separate_em_statement(finding) -> Optional[str]:
    """The documented statement of a significant, separately identifiable E/M, or None."""
    for fact in getattr(finding, 'facts', ()) or ():
        if fact.name == 'separate_em' and fact.value == 'documented' and fact.origin == 'document' and fact.evidence:
            return fact.evidence[0].text
    return None


def em_procedure_check(labels: Sequence[str], global_days_note: str, documented: Optional[str] = None,
                       possible: Sequence[str] = ()) -> Check:
    if documented is not None:
        detail = (f'{_same_day_subject(labels, possible)}. The documentation states a significant, separately '
                  f'identifiable E/M service (\u201c{documented}\u201d); whether it supports a separate E/M code is '
                  'the reviewer\u2019s judgement.')
        return Check('em.same_day_procedure', 'Separately identifiable E/M on a procedure day', 'warn',
                     f'{detail} {global_days_note}'.strip(), EM_SOURCE)
    return Check('em.same_day_procedure', 'Separately identifiable E/M on a procedure day', 'warn',
                 f'{same_day_reason(labels, possible)} {global_days_note}'.strip(), EM_SOURCE)


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


def same_day_if_reinstated_check(procedures: Sequence[tuple[str, str]]) -> Check:
    """On an E/M with no same-day procedure detected and no separately identifiable E/M documented: the excluded,
    reinstatable procedural codes ((code, profile label or '')) that a reviewer's reinstatement would make same-day
    procedures. Review withholds approve from this E/M while one of them has a current reinstate or approve decision,
    and blocks the reviewed report if this E/M was approved first; rejecting or revoking it releases the E/M."""
    listed = _join([f'{code} ({label})' if label else code for code, label in procedures])
    one = len(procedures) == 1
    return Check('em.same_day_if_reinstated', 'Separately identifiable E/M if a procedure is reinstated', 'warn',
                 f'{listed} {"is" if one else "are"} excluded but reinstatable. If a reviewer reinstates '
                 f'{"it" if one else "one of them"}, it is a same-day procedure: this E/M then cannot be approved '
                 'until a significant, separately identifiable E/M service is documented (add it as an addendum), and '
                 'an approval already recorded keeps the reviewed report blocked. Rejecting or revoking that '
                 'reinstatement releases this E/M.', EM_SOURCE)


def same_day_em_check(visits: Sequence[str]) -> Check:
    """On an excluded, reinstatable procedural code beside an E/M that has no same-day procedure detected."""
    one = len(visits) == 1
    return Check('review.same_day_em', 'Same-day E/M after reinstatement', 'warn',
                 f'If a reviewer reinstates this code, it is a same-day procedure beside the E/M {_join(visits)}: '
                 f'{"that E/M" if one else "those E/Ms"} then cannot be approved until a significant, separately '
                 'identifiable E/M service is documented.', REINSTATEMENT_SOURCE)


def separate_em_clarification(labels: Sequence[str], family: str, key: str,
                              possible: Sequence[str] = ()) -> ClarificationSpec:
    return ClarificationSpec(scope='proposal', fact='separate_em', question=SEPARATE_EM_QUESTION,
                             reason=same_day_reason(labels, possible), family=family, proposal_key=key)


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
# What routing recognises in document text. Coverage is never claimed beyond it: a service of another kind is
# detected only from a selected code or where routing happens to recognise it.
RECOGNISED = _join([PROFILES[family].label for family in DETECTED_FAMILIES])
RECOGNISED_PROCEDURES = _join([PROFILES[family].label for family in DETECTED_FAMILIES if PROFILES[family].procedure])
# Names no family: a family named here would read as one that was examined and found missing.
UNPROPOSED_PASS = ('Every performed service that routing detected in the document has a selected proposal. Routing '
                   'detects the profiled GI service families; a performed service of another kind may not be '
                   'detected, so whether it has a proposal is not verified.')
UNSUPPORTED_NONE = ('No selected code or detected service falls outside the GI profiles. Routing recognises '
                    f'{RECOGNISED} in the document text, so a performed service of another kind with no selected code '
                    'may not be detected; that is not verified.')
# On an office E/M with no same-day procedure detected: what that absence does not establish.
SAME_DAY_COVERAGE_CHECK = Check(
    'em.same_day_coverage', 'Same-day procedures outside the recognised families', 'not_verified',
    f'No same-day procedure is detected. Routing recognises {RECOGNISED_PROCEDURES} in the document text; a same-day '
    'procedure of another kind (for example hemorrhoid banding or anoscopy) holds this E/M only when its code is '
    'selected or routing detects it. Whether one was performed on the date of service, which would need a '
    'significant, separately identifiable E/M service, is not verified.', COVERAGE_SOURCE)


def uncited_label(label: str, names: Sequence[str]) -> str:
    """A family label that names the procedures no selected code cites ("Other GI service (“Rubber band ligation
    x3”)"), when another code of the family is selected."""
    return f'{label} ({_join([f"“{excerpt(name)}”" for name in dict.fromkeys(names)])})'


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
    return Check('services.unproposed', label, 'pass', UNPROPOSED_PASS, COVERAGE_SOURCE)


def unsupported_check(entries: Sequence[dict]) -> Check:
    """``entries``: services outside the GI profiles, performed (routed or selected), selected and held ('uncertain':
    its performance is not established, so it is never called performed and never left unnamed), or selected and
    excluded by its status reading ('excluded': a reviewer may reinstate it, so it is never left unnamed either; round 4
    validation:8)."""
    label = 'Services outside the GI profiles'
    if not entries:
        return Check('services.unsupported', label, 'not_verified', UNSUPPORTED_NONE, COVERAGE_SOURCE)
    performed = [entry['label'] for entry in entries if entry['status'] not in ('uncertain', 'excluded')]
    held = [f'{entry["label"]} ({_join(entry["codes"])})' for entry in entries if entry['status'] == 'uncertain']
    excluded = [f'{entry["label"]} ({_join(entry["codes"])})' for entry in entries if entry['status'] == 'excluded']
    parts = [f'Performed without a GI profile in this release: {_join(performed)}.'] if performed else []
    if held:
        parts.append(f'Selected without a GI profile in this release, not established as performed: {_join(held)}.')
    if excluded:
        parts.append(f'Selected without a GI profile in this release, excluded by its documented status (a reviewer '
                     f'may reinstate it): {_join(excluded)}.')
    return Check('services.unsupported', label, 'warn', f'{" ".join(parts)} Review required.', COVERAGE_SOURCE)


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
            readings.append(Reading(parsed[0], parsed[1], 'evidence', span.text, span.start, span.end))
    return tuple(readings)


# A procedure's act stated by its participle after an auxiliary, or after "we" / "I" ("Internal hemorrhoids were banded
# x3 today", "we banded two columns"): the participles of routing's gi.other procedure words that routing's performance
# cues do not read (they read "was ligated", "was dilated", "was injected" and "was resected" themselves).
_ACT_STATED = re.compile(r'\b(?:was|were|been|we|i)\s+(?:(?!not\b|never\b)[a-z]+\s+)?(?:banded|drained|excised|ablated|'
                         r'cauteri[sz]ed)\b', re.A | re.I)
# The procedure each number range of the gi.other profile reports (studio.gi.profiles), as (low, high, the patterns a
# routed name of it holds - every one -, the participle that states its act or ''). Internal and used only to hold: a
# passage read performed only by its section, or as the visit's own documentation, counts for a gi.other code only
# through its own procedure (round 4 release:11), and a code in a range listed nowhere here (43752-43761) never counts
# through such a passage (fail-closed). Never shown as a descriptor.
_VAL_OWN_PROCEDURES = tuple(
    (low, high, tuple(re.compile(pattern, re.A | re.I) for pattern in names), act) for low, high, names, act in (
        ('43450', '43453', (r'\bdilat(?:ion|ation)s?\b', r'\b(?:esophag\w*|bougie\w*|maloney|savary)\b'), ''),
        ('45300', '45327', (r'\bprocto(?:sigmoido)?scop(?:y|ies)\b',), ''),
        ('46221', '46250', (r'\b(?:band(?:ed|ing)|ligat(?:ion|ions|ed)|RBL|hemorrhoidectom(?:y|ies))\b',), 'banded'),
        ('46600', '46615', (r'\banoscop(?:y|ies)\b',), ''),
        ('47000', '47001', (r'\bliver\b', r'\bbiops(?:y|ies)\b'), ''),
        ('49082', '49084', (r'\bparacentes[ie]s\b',), ''),
        ('91010', '91299', (r'\b(?:manometr(?:y|ies)|capsule\s+endoscop(?:y|ies))\b',), ''),
    ))
# A relative pronoun right before a stated act, or before up to three auxiliaries or adverbs that lead it (round 5
# validation:4: "that had been banded", "which have already been banded"): the act is told of something else's subject
# ("The hemorrhoids that were banded at the first session have resolved."), never stated as this sentence's own.
_VAL_RELATIVE_BEFORE = re.compile(r'\b(?:that|which|who|whom|whose)\s+(?:(?:has|have|had|is|are|was|were|be|being|been|'
                                  r'already|previously|recently|also|then|since|just|all|both|each|once|ever|only|'
                                  r'not|never|originally|initially|subsequently|successfully)\s+){0,3}$', re.A | re.I)
_VAL_RELATIVE_REACH = 80  # how far back from the act the relative pronoun is looked for (bounds the work per act)
_VAL_WE_LEAD = 40  # how far back "we" / "I" may follow its clause's start, by at most one word ("Today we banded ...")
# "we" / "I" after an introductory phrase - one that ends in a comma, or opens with a preposition or an adverb of time -
# acting on an object (round 5 validation:2: "After informed consent, we banded the right posterior column.", "Using
# the McGivney ligator we banded two columns."): the act the sentence states. A noun subject before "we" with no such
# lead ("The internal hemorrhoids we banded have resolved."), or no object after the act, still only tells of it.
_VAL_INTRO = re.compile(r'[ \t]*(?:after|under|using|with|following|during|upon|through|via|this|then|subsequently)\b',
                        re.A | re.I)
_VAL_OBJECT = re.compile(r'[ \t]+(?:the|a|an|one|two|three|four|five|six|both|all|each|\d+|it|them|internal|external|'
                         r'right|left|anterior|posterior|lateral|columns?|hemorrhoids?)\b', re.A | re.I)
_VAL_INTRO_REACH = 100  # how long an introductory phrase before "we" / "I" may be (bounds the work per act)


def _VAL_introduced(text: str, start: int, m) -> bool:
    """Whether "we" / "I" of the act ``m`` follows an introductory phrase that opens its clause at ``start`` and acts on
    an object (_VAL_INTRO, _VAL_OBJECT)."""
    if m.start() - start > _VAL_INTRO_REACH or not _VAL_OBJECT.match(text, m.end()):
        return False
    return text[start:m.start()].rstrip().endswith(',') or bool(_VAL_INTRO.match(text, start, m.start()))


def _VAL_stated(an, text: str, m) -> bool:
    """Whether an _ACT_STATED match ``m`` is the act its sentence states rather than one it tells of: not after a
    relative pronoun and the auxiliaries that lead the act ("The hemorrhoids that were banded at the first session have
    resolved.", "The columns which have been banded look healed today."), and "we" / "I" opening its clause or following
    one word ("Today we banded ...", never "The internal hemorrhoids we banded have resolved."). ``an``: routing's
    analysis of ``text``. Bounded: a window of a few words before the match."""
    from studio.gi import detect
    if _VAL_RELATIVE_BEFORE.search(text, max(0, m.start() - _VAL_RELATIVE_REACH), m.start()):
        return False
    if m.group(0).split()[0].lower() in ('we', 'i'):
        clause = detect._clause_at(an, m.start())
        if ((clause[0] < m.start() - _VAL_WE_LEAD or len(text[clause[0]:m.start()].split()) > 1)
                and not _VAL_introduced(text, clause[0], m)):
            return False
    return True


def _VAL_told_act(text: str, start: int, end: int, service_date: Optional[date] = None) -> bool:
    """Whether the routed name at [start, end) holds an act its sentence only tells of (_VAL_stated): routing's stated-
    act mention "hemorrhoids that were banded", read done by a findings section, names no banding done today; nor does
    a stated act whose clause tells another time (_VAL_another_time, round 5 validation:4: "Two columns were banded at
    her last visit and look healed today.", read done because its clause says today)."""
    from studio.gi import detect
    an = detect._analysis(text, service_date)[0]
    for m in _ACT_STATED.finditer(text, max(0, start - 12), end):
        if not _VAL_stated(an, text, m):
            return True
        lo, hi = an.lay.window(detect._clause_at(an, m.start()), m.start(), m.end(), detect.CLAUSE_REACH)
        if _VAL_another_time(an, lo, hi):
            return True
    return False


def _VAL_own_procedure(code: str):
    """The _VAL_OWN_PROCEDURES entry whose number range holds the code, or None."""
    return next((entry for entry in _VAL_OWN_PROCEDURES if entry[0] <= code <= entry[1]), None)


# The codes whose number range is ONE procedure, with that procedure's words (round 5 validation:2 and validation:5):
# two routed names of it are the same procedure whatever else they say. Never a range sibling: a hemorrhoidectomy is
# not 46221's banding, and the 91010-91299 manometries are different procedures (no class: only equal names match).
_VAL_ONE_PROCEDURE = (
    ('46221', '46221', re.compile(r'\b(?:band(?:s|ed|ing)?|ligat(?:ion|ions|ed)|RBL)\b', re.A | re.I)),
    ('46600', '46615', re.compile(r'\banoscop(?:y|ies)\b', re.A | re.I)),
)
_VAL_SIBLING = re.compile(r'hemorrhoidectom', re.A | re.I)
_VAL_NAME_LEAD = re.compile(r'(?:(?:and|then|also|the|an?)\s+)+', re.A | re.I)


def _VAL_name(text: str) -> str:
    """A routed procedure name compared as words: case-folded, single-spaced, without a leading 'and' / 'the' / 'a'."""
    flat = ' '.join(text.split()).casefold()
    return flat[_VAL_NAME_LEAD.match(flat).end():] if _VAL_NAME_LEAD.match(flat) else flat


def _VAL_one_procedure_words(code: str):
    """The words of the code's one-procedure class (_VAL_ONE_PROCEDURE), or None for a code whose range is not one
    procedure."""
    return next((pattern for low, high, pattern in _VAL_ONE_PROCEDURE if low <= code <= high), None)


def _VAL_in_class(code: str, name: str) -> bool:
    """Whether a routed procedure name is in the code's one-procedure class and is no range sibling (a
    hemorrhoidectomy)."""
    words = _VAL_one_procedure_words(code)
    return bool(words and words.search(name) and not _VAL_SIBLING.search(name))


def _VAL_same_procedure(code: str, one: str, other: str) -> bool:
    """Whether two routed procedure names are the same single procedure for the code: equal as words, or both in the
    code's own one-procedure class (_VAL_in_class)."""
    return _VAL_name(one) == _VAL_name(other) or (_VAL_in_class(code, one) and _VAL_in_class(code, other))


def _VAL_owns(code: str, name: str) -> bool:
    """Whether a routed procedure's name is the gi.other code's own procedure (_VAL_OWN_PROCEDURES): "Anoscopy" is
    46600's and never 46221's. False for a code whose range lists no procedure (fail-closed)."""
    entry = _VAL_own_procedure(code)
    return entry is not None and all(pattern.search(name) for pattern in entry[2])


def _VAL_another_time(an, lo: int, hi: int) -> bool:
    """Whether an act's clause window [lo, hi) also tells a time that may not be the date of service (round 5
    validation:4), so its "today" may be another predicate's ("Two columns were banded at her last visit and look
    healed today."): routing's own reader of such a time (detect._another_encounters_time: a history cue of time or
    place, an unlisted time that may not be the date of service, a month and day with no year that are not its own),
    or a date that is not the date of service (any date when that is unknown). Used only to hold: such an act is not
    counted as stated today."""
    from studio.gi import context as gi_context
    from studio.gi import detect
    if detect._another_encounters_time(an, lo, hi):
        return True
    day = an.service_date
    return any(day is None or gi_context.compare_to_service(d, day) != 0 for d in an.dates_in(lo, hi))


@functools.lru_cache(maxsize=4)
def _VAL_text_index(text: str, service_date: Optional[date]):
    """Read once per text: (routing's sentence starts, its sentences, the first sentence of each procedure section - as
    routing's gi.other rule finds it -, and per own act participle the indexes of the sentences that state it explicitly
    on the date of service, sorted). Bounded: one scan of the text for the act participles, a bounded window each."""
    from studio.gi import cues as words
    from studio.gi import detect
    an = detect._analysis(text, service_date)[0]
    sentences = an.lay.sentences
    opening = []
    for section in an.lay.sections:
        if section.kind != 'procedure':
            continue
        first = detect._SEPARATOR.match(text, section.heading.end if section.heading else section.start,
                                        section.end).end()
        index = detect._sentence_index(an, first)
        if index >= 0 and an.lay.section_at(first) is section:
            opening.append(sentences[index])
    detected = [family for family in detect.PROCEDURE_FAMILIES if any(m.family == family for m in an.services)]
    owned = {entry[3] for entry in _VAL_OWN_PROCEDURES if entry[3]}
    acts: dict[str, list[int]] = {}
    for m in _ACT_STATED.finditer(text):
        participle = m.group(0).split()[-1].lower()
        index = detect._sentence_index(an, m.start())
        if participle not in owned or index < 0 or not _VAL_stated(an, text, m):
            continue
        lo, hi = an.lay.window(detect._clause_at(an, m.start()), m.start(), m.end(), detect.CLAUSE_REACH)
        sentence = sentences[index]
        scope = (max(sentence[0], m.start() - detect.CLAUSE_REACH), min(sentence[1], m.end() + detect.CLAUSE_REACH))
        if (words.TODAY.search(text, lo, hi) and not _VAL_another_time(an, lo, hi)
                and not detect._about_a_detected_family(an, *scope, detected)):
            acts.setdefault(participle, []).append(index)
    return (tuple(s for s, _ in sentences), sentences, tuple(opening),
            {participle: tuple(sorted(set(found))) for participle, found in acts.items()})


def _VAL_opening_sentences(text: str, service_date: Optional[date] = None) -> tuple[tuple[int, int], ...]:
    """The first sentence of each procedure section, found as routing's gi.other rule finds it (_VAL_text_index)."""
    return _VAL_text_index(text, service_date)[2]


# What may open a sentence before its procedure's name: a list marker ("2)", "(2)", "2.", "-", "*", a bullet). A
# sentence opened by a time or a condition ("Before banding, ...", "If anoscopy ...") names no procedure done by its
# lead.
_VAL_LIST_MARKER = re.compile(r'[ \t]*(?:\(?\d{1,3}[.)]|[-*\u2022])[ \t]+', re.A)
_VAL_TEMPORAL_LEAD = re.compile(r'[ \t]*(?:after|before|once|when|while|following|until|if|unless|since)\b',
                                re.A | re.I)


@functools.lru_cache(maxsize=4)
def _VAL_sentence_leads(text: str, service_date: Optional[date]) -> dict:
    """Per text, filled lazily by _VAL_lead_name: {sentence index: its leading procedure name or ''}. Each sentence is
    read once, however many passages a provider cites in it (round 5's bounded:3 lesson)."""
    return {}


def _VAL_lead_name(an, text: str, index: int, service_date: Optional[date]) -> str:
    """The procedure name the sentence ``index`` opens with, after a list marker (routing's _procedure_name), or '':
    never one led by a time or a condition ("Before anoscopy, ..."), a history word ("Prior anoscopy showed ..."), a
    negation or a plan, nor an examination or a person, a name about a detected family's procedure, nor any name of a
    sentence that only tells of an act (_VAL_told_act). Memoised per text and sentence (_VAL_sentence_leads)."""
    from studio.gi import detect
    memo = _VAL_sentence_leads(text, service_date)
    if index in memo:
        return memo[index]
    if 'detected' not in memo:
        memo['detected'] = [family for family in detect.PROCEDURE_FAMILIES
                            if any(m.family == family for m in an.services)]
    s, e = an.lay.sentences[index]
    name = ''
    marker = _VAL_LIST_MARKER.match(text, s, e)
    lead = marker.end() if marker else s
    if not _VAL_TEMPORAL_LEAD.match(text, lead, e):
        lead = detect._NAME_LEAD.match(text, lead, e).end()
        span = None if detect._HISTORY_LEAD.match(text, lead, e) else detect._procedure_name(an, lead, e)
        found = text[span[0]:span[1]] if span else ''
        if (found and detect._PROCEDURE_WORD.search(found) and not detect._NOT_A_PROCEDURE.search(found)
                and not detect._NOT_DONE_LED.match(found)):
            scope = (max(s, span[0] - detect.CLAUSE_REACH), min(e, span[1] + detect.CLAUSE_REACH))
            if not detect._about_a_detected_family(an, *scope, memo['detected']) \
                    and not _VAL_told_act(text, s, e, service_date):
                name = found
    memo[index] = name
    return name


def _VAL_opens_with(text: str, start: int, end: int, code: str, names: Sequence[str],
                    service_date: Optional[date] = None) -> bool:
    """Whether a sentence the passage [start, end) overlaps opens with the code's own procedure named as one of the
    routed ``names`` (round 5 validation:2): "Anoscopy revealed grade 2 internal hemorrhoids." under the Findings of a
    report whose "Procedure: Anoscopy" routing reads done. The sentence's leading name (_VAL_lead_name) must be the
    code's own procedure (_VAL_owns) and start with one of those names as words, or be the same single procedure
    (_VAL_same_procedure). ``names``: routed gi.other mentions of the code's own procedure read done in the first
    sentence of a procedure section - the corroboration, so a passage's wording alone never releases a held code.
    Bounded: each sentence's lead is read once per text; a passage costs one bisection and a look per sentence it
    overlaps."""
    from studio.gi import detect
    if not names or start >= end:
        return False
    an = detect._analysis(text, service_date)[0]
    sentences = an.lay.sentences
    index = max(bisect.bisect_right(sentences, (start, 1 << 62)) - 1, 0)
    while index < len(sentences) and sentences[index][0] < end:
        if sentences[index][1] > start:
            name = _VAL_lead_name(an, text, index, service_date)
            if name and _VAL_owns(code, name):
                said = _VAL_name(name)
                if any(said == _VAL_name(other) or said.startswith(_VAL_name(other) + ' ')
                       or _VAL_same_procedure(code, other, name) for other in names):
                    return True
        index += 1
    return False


def names_intervention(text: str, start: int, end: int, family: str) -> bool:
    """Whether [start, end) names one of the family's interventions by routing's own words (studio.gi.cues
    INTERVENTIONS: a biopsy, a snare, a dilation ...), resolved at call time."""
    from studio.gi import cues as words
    return any(family in families and pattern.search(text, start, end) for _, pattern, families in words.INTERVENTIONS)


def names_procedure(text: str, start: int, end: int, code: str, service_date: Optional[date] = None) -> bool:
    """Whether the passage [start, end) states the gi.other code's own procedure as done today by its act (round 4
    validation:2, evidence:0, release:11): a sentence it overlaps holds the code's own act participle
    (_VAL_OWN_PROCEDURES: "banded" for 46221-46250) after an auxiliary or after "we" / "I" (_ACT_STATED), in a clause
    that says today by routing's own words (cues.TODAY), not right after a relative pronoun ("The hemorrhoids that were
    banded at the first session have resolved."), with "we" / "I" opening its clause or following one word ("Today we
    banded two internal hemorrhoids.", never "The internal hemorrhoids we banded have resolved."), and not about a
    detected family's procedure. A sentence that only opens with a procedure word names nothing done ("Banding sites
    well healed.", "S/p hemorrhoid banding.", "Hemorrhoidectomy scar noted."): a routed mention read as done must say
    so (engine._unnamed_other). Each sentence is read whole, whatever part of it the provider cited. Read once per
    text (_VAL_text_index): each passage costs three bisections."""
    entry = _VAL_own_procedure(code)
    if entry is None or not entry[3] or start >= end:
        return False
    starts, sentences, _, acts = _VAL_text_index(text, service_date)
    found = acts.get(entry[3], ())
    if not found:
        return False
    last = bisect.bisect_left(starts, end) - 1  # the last sentence starting before the passage ends
    first = max(bisect.bisect_right(starts, start) - 1, 0)
    if first <= last and sentences[first][1] <= start:
        first += 1  # that sentence ends before the passage starts
    at = bisect.bisect_left(found, first)
    return first <= last and at < len(found) and found[at] <= last
