"""Validation engine (ARCHITECTURE 5.6): provider codes -> one combined, checked assessment.

Pure apart from the reference lookup it is given. Only provider-selected codes
become reviewable proposals (bucket ``selected``, or ``excluded`` with the
reason); candidates and alternatives are informational and never approvable.
When the provider did not succeed there are no proposals, and an encounter
check says exactly why.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping, Optional, Sequence

from studio.gi import services as gi_services
from studio.gi.profiles import DETECTED_FAMILIES, PROFILES, PROFILES_VERSION, ServiceProfile, family_for_code
from studio.reference.store import PFS, applied_sources
from studio.types import (CONTEXT_FACTS, AssessmentResult, Check, ClarificationSpec, CodeReference, EvidenceSpan, Fact,
                          FamilyFinding, NormalizedResponse, PageSpan, ProposalAssessment, ProviderCode,
                          ReferenceLookup, ReferenceSourceInfo, RoutingResult, ServiceMention, sha256_json)
from studio.gi.detect import DOUBT_PREFIX
from studio.validation import checks, rationale, reconcile

ENGINE_VERSION = 'cpt-studio-validation@4'
# The documented-service inventory decides the status of the codes it matches (5.10). Off, every code is judged by the
# routing-era reading alone - the path the inventory falls back to when its reading is inconsistent; the routing-era
# unit tests, whose stubbed passage readings describe no real document, run that path.
READ_DOCUMENTED_SERVICES = True
PROVIDER_STATUSES = ('succeeded', 'not_run', 'failed', 'unknown')
EXTRACTION_STATUSES = ('ok', 'partial', 'failed')
NO_EVIDENCE = 'No exact source evidence'
MAX_LISTED_CODE = 10  # what a stored proposal code holds; codes are never truncated
OTHER_GI = 'gi.other'
# Families gi-profiles@3 carved out of earlier ones. Their codes keep the routing-era reading of the family they were
# routed to before (gi.other's doubt guards, the upper GI finding), as the second opinion that can only hold.
LEGACY_FAMILIES = {'gi.capsule': OTHER_GI, 'gi.motility': OTHER_GI, 'gi.reflux': OTHER_GI, 'gi.anorectal': OTHER_GI,
                   'gi.feeding_tube': OTHER_GI, 'gi.enteroscopy': 'gi.egd'}


def legacy_family(family: str) -> str:
    return LEGACY_FAMILIES.get(family, family)


@dataclass(frozen=True)
class _Evaluation:
    """What is known about a code that is in scope and has exact evidence."""
    finding: Optional[FamilyFinding]
    outcome: checks.StatusOutcome
    reference: CodeReference
    own: tuple[checks.Reading, ...] = ()  # the status readings of its own linked passages
    # (start, end) of the routed gi.other mentions that corroborated one of its passages (round 4d validation:10): the
    # report's procedure line a findings sentence opening with the code's own procedure counts through. The code speaks
    # for them (_cited), so its own procedure is never called a missed service with no selected proposal.
    speaks_for: tuple[tuple[int, int], ...] = ()
    # The documented service the code was matched to (engine @4): its status decides the code's, never a fragment of a
    # provider passage read alone. None when the inventory documents no service of the code's family.
    match: Optional[reconcile.Match] = None
    support: Optional[reconcile.Support] = None


@dataclass(frozen=True)
class _Selection:
    """One provider-selected code (duplicates merged), before the checks that depend on other proposals."""
    code: str
    units: int
    display: str
    code_kind: str
    scope_reason: str
    evidence: tuple[EvidenceSpan, ...]
    dropped: tuple[str, ...]
    family: str
    evaluation: Optional[_Evaluation] = None  # None: excluded for scope or evidence, not reinstatable
    origin: str = 'primary'  # 'second_review': selected by the bounded second review for an unresolved service

    @property
    def profile(self) -> ServiceProfile:
        return PROFILES[self.family]

    @property
    def excluded(self) -> bool:
        return self.evaluation is None or self.evaluation.outcome.state == 'not_performed'

    @property
    def performed(self) -> bool:
        return self.evaluation is not None and self.evaluation.outcome.state in checks.POSITIVE


@dataclass(frozen=True)
class _Encounter:
    """Encounter-level inputs shared by every proposal's checks."""
    provider: str
    context: Mapping[str, Fact]
    sources: tuple[ReferenceSourceInfo, ...]
    date_state: checks.DateState
    pfs_source: Optional[ReferenceSourceInfo]
    active_pfs: Mapping[str, dict]  # code -> PFS row of every selected, non-excluded proposal that has one
    procedure_labels: tuple[str, ...]  # procedure families performed on this date
    possible_labels: tuple[str, ...]  # procedure families whose performance on this date is not established
    global_days: str
    # Off a procedure day: the excluded, reinstatable procedural selections ((code, profile label or '')) that a
    # reviewer's reinstatement would make same-day procedures, and the E/M codes (no separately identifiable E/M
    # documented) that such a reinstatement would hold. Review gates approval on them; empty when nothing would.
    if_reinstated: tuple[tuple[str, str], ...] = ()
    gated_visits: tuple[str, ...] = ()
    # Engine @4: a family's base (diagnostic) code selected beside a code of the same documented service that accounts
    # for one of its interventions: (base code, the other codes). The base is held, never excluded.
    bases_included: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def procedure_day(self) -> bool:
        return bool(self.procedure_labels or self.possible_labels)


def assess(*, text: str, pages: tuple[PageSpan, ...], context: dict[str, Fact], routing: RoutingResult,
           normalized: Optional[NormalizedResponse], reference: ReferenceLookup, service_date: Optional[date],
           provider_status: str, extraction_status: Optional[str] = None,
           extraction_messages: Sequence[str] = (), second: Optional[NormalizedResponse] = None,
           second_scope: Optional[dict] = None) -> AssessmentResult:
    if provider_status not in PROVIDER_STATUSES:
        raise ValueError(f'Unknown provider status {provider_status!r}.')
    if extraction_status is not None and extraction_status not in EXTRACTION_STATUSES:
        raise ValueError(f'Unknown extraction status {extraction_status!r}.')
    response = normalized if provider_status == 'succeeded' else None
    if provider_status == 'succeeded' and response is None:
        raise ValueError('A succeeded provider status needs its normalized response.')
    date_state = checks.service_date_state(context, service_date)
    sources = tuple(reference.sources())
    selections: list[_Selection] = []
    proposals: tuple[ProposalAssessment, ...] = ()
    provider = list(checks.provider_checks(provider_status, response))
    coverage: list[Check] = []
    # The documented-service inventory is read from the text alone, before and independently of the proposals.
    inventory = (gi_services.build(text, service_date=date_state.value, routing=routing, context_facts=context)
                 if READ_DOCUMENTED_SERVICES else gi_services.ServiceInventory(version=gi_services.INVENTORY_VERSION))
    problems = gi_services.validate(inventory, text)
    usable = inventory if not problems else None  # an inconsistent reading never decides a status; it is reported
    if response is not None:
        listable = [c for c in response.codes if isinstance(c.code, str) and 0 < len(c.code) <= MAX_LISTED_CODE]
        if len(listable) < len(response.codes):
            provider.append(checks.unlisted_codes_check(len(response.codes) - len(listable), MAX_LISTED_CODE))
        selections = [_select(group, text, pages, routing, reference, date_state.value, usable)
                      for group in _merge_selected(listable)]
        second_alternatives: list[ProposalAssessment] = []
        if second is not None and usable is not None:
            selections, second_alternatives, second_check = _second_review(
                second, second_scope or {}, selections, text, pages, routing, reference, date_state.value, usable)
            provider.append(second_check)
        encounter = _encounter(response.provider, context, routing, sources, date_state, selections)
        alternatives = (c for c in listable if c.role != 'selected')
        proposals = (_keyed(selections, encounter)
                     + tuple(_alternative(index, item, text, pages, response.provider)
                             for index, item in enumerate(alternatives))
                     + tuple(second_alternatives))
        reconciled = {s.family for s in usable.services if s.status in checks.POSITIVE} if usable else set()
        coverage.append(checks.unproposed_check(*_missed(routing, selections, encounter.procedure_day,
                                                         reconciled if usable else set())))
    active = [(s.code, s.family) for s in selections if not s.excluded]
    unresolved, bundled, covered = reconcile.reconcile(usable, active) if usable else ([], [], {})
    service_questions = _service_questions(usable, proposals) if usable else []
    unsupported = _unsupported(routing, selections)
    encounter_checks = [*provider, checks.extraction_check(extraction_status, extraction_messages),
                        checks.service_date_check(date_state), reconcile.inventory_check(inventory, problems),
                        *coverage]
    if usable and response is not None:
        encounter_checks.append(reconcile.unresolved_check(unresolved))
    if usable:
        encounter_checks.append(reconcile.conflicts_check(usable))
        attribution = reconcile.attribution_check(usable, [code for code, _ in active])
        if attribution:
            encounter_checks.append(attribution)
    encounter_checks.append(checks.unsupported_check(unsupported))
    clarification = checks.service_date_clarification(date_state)
    clarifications = ((clarification,) if clarification else ()) + tuple(service_questions)
    open_questions = len(clarifications) + sum(len(p.clarifications) for p in proposals)
    complete = reconcile.completeness(usable or inventory, unresolved, open_questions,
                                      provider_status == 'succeeded' and response is not None)
    if problems:
        complete['state'] = 'incomplete'
        complete['reasons'] = list(complete['reasons']) + ['the documented-service reading was inconsistent']
    complete.update({
        'unresolved_items': [_jsonable_unresolved(u) for u in unresolved],
        'bundled': [{'service': b.service, 'act': b.act, 'label': b.label, 'why': b.why} for b in bundled],
        'covered': covered, 'catalogue_version': reconcile.catalogue.CATALOGUE_VERSION,
        'inventory_problems': list(problems)})
    return AssessmentResult(
        profiles_version=PROFILES_VERSION, engine_version=ENGINE_VERSION, proposals=proposals,
        encounter_checks=tuple(encounter_checks), clarifications=clarifications,
        unsupported=unsupported, reference_sources=checks.reference_source_entries(sources, date_state.value),
        summary=_summary(proposals, provider_status, extraction_status, date_state),
        services=_jsonable_inventory(inventory), completeness=complete)


def _second_review(second: NormalizedResponse, scope: dict, selections: list, text: str, pages, routing, reference,
                   day, inventory) -> tuple[list, list, Check]:
    """Merge the bounded second review (ARCHITECTURE 5.11). Only a code it SELECTED that accounts for a documented
    service or act left unresolved by the primary proposals becomes a proposal (marked as from the second review); every
    other code it lists is informational. Nothing is promoted from an alternative and nothing is invented."""
    active = [(s.code, s.family) for s in selections if not s.excluded]
    unresolved, _, _ = reconcile.reconcile(inventory, active)
    open_items = [(u.service, u.family, u.act) for u in unresolved if u.reason in ('no_proposal', 'not_covered')]
    have = {s.code for s in selections}
    listable = [c for c in second.codes if isinstance(c.code, str) and 0 < len(c.code) <= MAX_LISTED_CODE]
    added, listed = [], []
    for group in _merge_selected(listable):
        code = group[0].code
        if code in have:
            continue
        candidate = _select(group, text, pages, routing, reference, day, inventory)
        profile = reconcile.catalogue.code_profile(code)
        accounts = profile is not None and any(
            family == candidate.family and (act == '' or act in profile.covers
                                            or (act in ('tattoo', 'injection') and {'tattoo', 'injection'}
                                                & set(profile.covers)))
            for _, family, act in open_items)
        if accounts and candidate.evaluation is not None and not candidate.excluded:
            added.append(replace(candidate, origin='second_review'))
            have.add(code)
        else:
            listed.append(group[0])
    alternatives = [_alternative(index, replace(item, role='candidate'), text, pages, f'{second.provider} (second review)')
                    for index, item in enumerate(listed + [c for c in listable if c.role != 'selected'])]
    alternatives = [replace(a, key=f'alt2:{index}') for index, a in enumerate(alternatives)]
    what = '; '.join(scope.get('items', [])[:4]) or 'the unresolved documented services'
    if second.refused:
        detail = f'A second review was requested for: {what}. Its response was not used ({"; ".join(second.problems)}).'
        status = 'warn'
    elif added:
        detail = (f'A second review limited to the passages of {what} selected '
                  + ', '.join(s.code for s in added) + ', which account for them and are added as proposals for '
                  'review (marked as from the second review).')
        if listed:
            detail += ' It also listed ' + ', '.join(c.code for c in listed) + ', shown as alternatives only.'
        status = 'info'
    else:
        detail = (f'A second review limited to the passages of {what} selected no code that accounts for them'
                  + (' (it listed ' + ', '.join(c.code for c in listed) + ', shown as alternatives only)' if listed else '')
                  + '. They stay unresolved; nothing is added.')
        status = 'warn'
    return list(selections) + added, alternatives, Check('provider.second_review', 'Second review', status, detail,
                                                         'cpt-studio:provider@1')


def _jsonable_unresolved(u: reconcile.Unresolved) -> dict:
    return {'service': u.service, 'family': u.family, 'act': u.act, 'label': u.label, 'reason': u.reason,
            'evidence': [{'start': e.start, 'end': e.end, 'text': e.text} for e in u.evidence]}


def _jsonable_inventory(inventory) -> dict:
    from studio.types import to_jsonable
    return to_jsonable(inventory)


def _service_questions(inventory, proposals) -> list[ClarificationSpec]:
    """Every materially necessary question about a documented service, asked together and once: its missing
    documentation (a sparse visit note's setting, status and basis together) and each conflict in the record. A
    question a proposal of the same family already asks is not asked again."""
    asked = {(c.family, c.fact) for p in proposals for c in p.clarifications}
    out: list[ClarificationSpec] = []
    for service in inventory.services:
        for spec in reconcile.documentation_clarifications(service):
            if (spec.family, spec.fact) not in asked:
                asked.add((spec.family, spec.fact))
                out.append(spec)
    for conflict in inventory.conflicts:
        service = inventory.service(conflict.service)
        spec = reconcile.conflict_clarification(conflict, service)
        if (spec.family, spec.fact) not in asked:
            asked.add((spec.family, spec.fact))
            out.append(spec)
    return out


# --- phase 1: each selected code on its own --------------------------------------------

def _merge_selected(codes: Sequence[ProviderCode]) -> list[list[ProviderCode]]:
    """Selected codes grouped by code, in the provider's order of first appearance."""
    groups: dict[str, list[ProviderCode]] = {}
    for item in codes:
        if item.role == 'selected':
            groups.setdefault(item.code, []).append(item)
    return list(groups.values())


def _select(group: list[ProviderCode], text: str, pages, routing: RoutingResult, reference: ReferenceLookup,
            day: Optional[date], inventory=None) -> _Selection:
    code = group[0].code
    code_kind, scope_reason = checks.code_scope(code)
    kept, dropped = checks.exact_evidence([span for item in group for span in item.evidence], text, pages)
    displays = dict.fromkeys(item.display for item in group if item.display)
    selection = _Selection(code=code, units=len(group), display=' | '.join(displays), code_kind=code_kind,
                           scope_reason=scope_reason, evidence=kept, dropped=dropped, family=family_for_code(code))
    if scope_reason or not kept:
        return selection
    # Only a family routing detects is read through its routed finding. A gi.other finding gathers different
    # procedures (the shared routing contract), so it never speaks for one code: a gi.other code's status, family
    # check and rationale come from its own passages, as for every family routing does not detect.
    legacy = legacy_family(selection.family)
    finding = routing.finding(legacy) if legacy in DETECTED_FAMILIES else None
    own = checks.evidence_readings(text, kept, day)
    speaks_for: tuple = ()
    if legacy == OTHER_GI:
        # round 4d repair 2: a passage read cancelled only through a detected family's judgement is held, not excluded
        own = checks._V2_judged_away(text, own, day)
        own, speaks_for = _unnamed_other(own, text, routing, day, code)
    if legacy in checks.EM_FAMILIES:
        own = _undated_visit(own, routing, text, day)
    families = _VAL_family_index(routing) if any(r.status == 'uncertain' for r in own) else {}
    own = tuple(replace(r, other_service=True) if _other_service(r, legacy, families, text) else r
                for r in own)
    outcome = checks.resolve_status(own + checks.routing_readings(finding),
                                    detectable=legacy in DETECTED_FAMILIES)
    found = reconcile.match(code, inventory, selection.family) if inventory is not None else None
    supported = None
    if found is not None:
        # Engine @4: the documented service and act decide the code's status; its passages are verified against them.
        found = _second_opinion(outcome, found, code, text, inventory)
        if found.reason == 'act_missing' and outcome.state == 'not_performed':
            # The inventory documents no such act and the code's own passage reads it as not performed today (a
            # planned repeat, an earlier procedure): the inventory has nothing to add, and the exclusion stands.
            found = None
    if found is not None:
        outcome = _service_outcome(found)
        supported = reconcile.support(found, kept, current=lambda span: gi_services.current_statement(
            text, span.start, span.end, day))
    return replace(selection, evaluation=_Evaluation(finding, outcome, reference.lookup(code, day), own, speaks_for,
                                                     found, supported))


def _second_opinion(old: checks.StatusOutcome, found: reconcile.Match, code: str, text: str,
                    inventory=None) -> reconcile.Match:
    """The documented service decides the code's status, with the routing-era reading as a second opinion that can
    only hold (ARCHITECTURE 5.10):
    - a hedge, a denial or a cancellation read in the code's OWN passage, when that passage is about the matched
      service (it overlaps the service's or one of its acts' evidence, or names the service or the code's act), holds
      the code with both readings - a doubt about this act is never released by a second reader;
    - a passage read as about another TIME (an earlier visit, a planned repeat) does not decide: the inventory reads
      time per clause and per service, and an unrelated historical reference never invalidates a current service;
    - a passage about something else (a fragment of a findings sentence) does not decide;
    - where the documented service is not performed but the routing-era reading is positive, the code is held, never
      newly excluded.
    Routing's own family doubts are folded into the service's status by the inventory (services._finish)."""
    positive = found.state in checks.POSITIVE
    if positive and old.state in ('uncertain', 'not_performed'):
        doubt = old.decisive
        own = doubt is not None and doubt.origin == 'evidence' and doubt.start is not None
        holds = (old.state == 'uncertain' and own and _about(doubt, found, code, text)) or (
            old.state == 'not_performed' and own and doubt.status in ('negated', 'cancelled')
            and _about(doubt, found, code, text))
        if holds and old.state == 'uncertain' and _negation_resolved(doubt, found):
            # The routing-era reader left a negation unresolved ("was complete and was not discontinued") in a passage
            # the documented-service reader reads, clause by clause, as this service's own positive statement: the doubt
            # is that reader's, not the document's. A hedge, a denial or a cancellation still holds.
            return replace(found, detail=f'{found.detail} The routing-era reading left a negation unresolved in '
                                         f'{checks.cite(doubt)}; the documented-service reader reads that passage as '
                                         'this service\'s own positive statement.')
        if holds:
            # Any hold the routing-era reading makes on a passage about this service stands (a hedge, a doubt guard,
            # a passage that reads performed only by its section): only a fragment about something else, or a passage
            # about another time, is overruled by the documented service.
            reading = 'is not established as performed' if doubt.status in checks.POSITIVE else f'reads as {doubt.status}'
            name = checks.service_name(PROFILES[legacy_family(found.service.family)], code)
            why = checks.uncertain_reason(old, name) if old.state == 'uncertain' else checks.exclusion_reason(old, name)
            return replace(found, state='uncertain', reason='readings_disagree', question=(
                f'Confirm whether {code} is supported: a passage it cites about this service {reading}.'),
                detail=f'{found.detail} But the routing-era reading of the passage the code cites holds it: {why} '
                       'Held for the reviewer.')
        return found
    if found.reason == 'act_missing' and old.state in checks.POSITIVE and old.decisive is not None \
            and old.decisive.origin == 'evidence' and old.decisive.start is not None \
            and not _elsewhere(old.decisive, found, inventory):
        # The documented service is performed and the code's own passage states its act (the routing-era reader reads
        # it performed: a form row, a check box, a phrasing this reader does not parse); the inventory does not read
        # that act at all - it neither denies it nor gives the passage to another service - so the code's own reading
        # stands, and says so.
        positive_state = 'incomplete' if found.service.status == 'incomplete' else 'performed'
        return replace(found, state=positive_state, reason='own_passage', question='',
                       detail=f'The {reconcile.service_label(found.service)} is documented as {found.service.status}; '
                              f'the act {code} accounts for is read from its own passage by the routing-era reader '
                              f'({checks.cite(old.decisive)}), not by the documented-service reader.')
    if found.state == 'not_performed' and old.state != 'not_performed':
        # Never a new exclusion: the documented service reads as not performed, the routing-era reading does not
        # exclude the code, so it is held for the reviewer.
        return replace(found, state='uncertain', reason='readings_disagree',
                       question=f'Confirm whether {code} was performed on the date of service.',
                       detail=f'{found.detail} Its own passages do not read it as not performed; held for the reviewer, '
                              'not excluded.')
    return found


def _negation_resolved(doubt: checks.Reading, found: reconcile.Match) -> bool:
    """The doubt is only an unresolved negation, and the passage is part of the service's positive reading (its
    statement of performance, a performed act, or a completion read as complete), never of anything it denies."""
    if not any(c.startswith(DOUBT_PREFIX) for c in doubt.cues) or doubt.start is None:
        return False
    service = found.service
    positive = list(service.evidence) if service.status in checks.POSITIVE else []
    if service.completion == 'complete':
        positive += list(service.completion_evidence)
    positive += [ev for a in service.acts if a.status == 'performed' for ev in a.evidence]
    other = [ev for a in service.acts if a.status != 'performed' for ev in a.evidence]

    def overlaps(spans):
        return any(doubt.start < t.end and t.start < doubt.end for t in spans)
    return overlaps(positive) and not overlaps(other)


def _elsewhere(reading: checks.Reading, found: reconcile.Match, inventory) -> bool:
    """Whether the inventory gives the passage to another documented service (an act of another service, or another
    service's own statement)."""
    if inventory is None:
        return False
    for service in inventory.services:
        if service.id == found.service.id:
            continue
        spans = list(service.evidence) + [ev for a in service.acts for ev in a.evidence]
        if any(reading.start < t.end and t.start < reading.end for t in spans):
            return True
    return False


STATUS_WORDS = re.compile(r'\b(?:perform\w*|done|complet\w*|cancel\w*|abort\w*|terminat\w*|discontinu\w*|postpon\w*|'
                          r'defer\w*|declin\w*|refus\w*|pending|incomplete|attempt\w*|stopp\w*|halt\w*|resched\w*|'
                          r'called\s+off|on\s+hold|tbd|unknown|requested)\b', re.I)


def _about(reading: checks.Reading, found: reconcile.Match, code: str, text: str) -> bool:
    """Whether a passage the code cites is about the matched service: it overlaps the service's evidence or any of
    its acts' evidence, or it names the service or the act the code accounts for."""
    service = found.service
    targets = list(service.evidence) + list(service.completion_evidence) + [ev for a in service.acts for ev in a.evidence]
    if any(reading.start < t.end and t.start < reading.end for t in targets):
        return True
    passage = text[reading.start:reading.end]
    if any(family == service.family and pattern.search(passage) for family, _, pattern in gi_services.SERVICES):
        return True
    if service.family == 'gi.office_em' and (gi_services.EM_EVALUATED.search(passage)
                                             or gi_services.EM_VISIT.search(passage)):
        return True  # a visit statement ("Established patient office visit: ...") is about the visit
    if service.scope_start <= reading.start and reading.end <= service.scope_end and STATUS_WORDS.search(passage):
        return True  # a bare status statement inside the service's own report ("☒ Not performed", "Aborted ...")
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    return any(kind in kinds and pattern.search(passage) for kind, pattern in gi_services.ACTS)


def _service_outcome(found: reconcile.Match) -> checks.StatusOutcome:
    service = found.service
    passage = found.acts[0].evidence[0] if found.acts else (service.evidence[0] if service.evidence else None)
    status = {'performed': 'performed', 'incomplete': 'incomplete', 'uncertain': 'uncertain'}.get(
        found.state, service.status if service.status in checks.NEGATIVE else 'negated')
    reading = checks.Reading(status, (found.detail,), 'service', passage.text if passage else '',
                             passage.start if passage else None, passage.end if passage else None)
    incomplete = None
    if found.state == 'incomplete':
        ev = service.completion_evidence[0] if service.completion_evidence else passage
        incomplete = checks.Reading('incomplete', ('incomplete: ' + (ev.text if ev else 'documented'),), 'service',
                                    ev.text if ev else '', ev.start if ev else None, ev.end if ev else None)
    return checks.StatusOutcome(found.state, reading, incomplete=incomplete, reason=found.reason)


def _VAL_overlap_test(intervals):
    """A test of whether [start, end) overlaps any of the (start, end) intervals: two bisections per question (the
    intervals starting before ``end``, less those ending by ``start``), never a scan."""
    starts = sorted(s for s, _ in intervals)
    ends = sorted(e for _, e in intervals)
    return lambda start, end: bisect.bisect_left(starts, end) - bisect.bisect_right(ends, start) > 0


def _unnamed_other(own: tuple[checks.Reading, ...], text: str, routing: RoutingResult, day: Optional[date],
                   code: str) -> tuple[tuple[checks.Reading, ...], tuple[tuple[int, int], ...]]:
    """A gi.other code's linked passages, each positive one that rests on its section alone (or on the office visit's
    own documentation, checks.states_no_procedure) marked ``unnamed`` unless it documents the code's own procedure as
    done (round 4 validation:2, validation:3, evidence:0, release:11): a routed gi.other mention read as done lies in
    it, or it lies in the first sentence of a procedure section whose routed mention is read as done - in both, a
    mention whose name is the code's own procedure (checks._VAL_owns, by the gi.other number ranges) and not an act
    its sentence only tells of (checks._VAL_told_act: "The hemorrhoids that were banded at the first session have
    resolved.") - or it states the code's own act today (checks.names_procedure). "Grade 2 internal hemorrhoids were
    seen on retroflexion." and "Banding sites well healed." under Findings read performed only because of their
    section, "Established patient office visit was performed today." as E/M documentation, and "Anoscopy showed grade 3
    internal hemorrhoids." names another procedure for 46221: none is evidence that the code's procedure was done.
    Fail-closed: an unnamed passage holds the code (section_only), never excludes it. Routing's gi.other finding still
    never decides the code's status (it may be another procedure). Indexed once per code: each passage costs a few
    bisections. Also returns the (start, end) of each routed opening mention a passage counted through
    (_VAL_opens_with), which the code then speaks for (round 4d validation:10)."""
    if not any(r.status in checks.POSITIVE and checks._VAL_states_no_procedure_of_its_own(text, r, day) for r in own):
        return own, ()
    other = routing.finding(OTHER_GI)
    done = [m for m in (other.mentions if other else ())
            if m.status in checks.POSITIVE and checks._VAL_owns(code, m.span.text)
            and not checks._VAL_told_act(text, m.span.start, m.span.end, day)]
    names = _VAL_overlap_test([(m.span.start, m.span.end) for m in done])
    openings = [sentence for sentence in checks._VAL_opening_sentences(text, day) if names(*sentence)]
    opened = _VAL_overlap_test(openings)
    # the code's own procedure as a procedure section's first sentence documents it done: what a later sentence of the
    # report may open with, read by its section alone (round 5 validation:2)
    openers = [m for m in done if opened(m.span.start, m.span.end)]
    opening_names = [m.span.text for m in openers]
    # ... unless the document reads the code's own procedure denied, called off or doubted somewhere (fail-closed).
    # Routing's gi.other finding never reads such a denial ("Anoscopy was not performed; the patient declined." names
    # no mention), so the same doubt also withdraws the routed mention and the procedure line themselves (round 4c).
    doubted = None
    marked, speaks, spoken = [], [], set()
    lead_openers: dict[str, tuple[int, ...]] = {}  # an owned sentence lead -> the openers it opens with, read once
    emitted: set[str] = set()  # the leads whose openers the code already speaks for
    for reading in own:
        if (reading.status in checks.POSITIVE and checks._VAL_states_no_procedure_of_its_own(text, reading, day)
                and not checks.names_procedure(text, reading.start, reading.end, code, day)):
            routed_done = names(reading.start, reading.end) or opened(reading.start, reading.end)
            counted = False
            if routed_done or (opening_names and checks.by_section_alone(reading)):
                doubted = checks._VAL_doubted(text, code, day) if doubted is None else doubted
                counted = not doubted and routed_done
                if not routed_done:
                    # _VAL_opens_with over the opening names, to know which mentions corroborate; the code speaks for
                    # them even in a document that doubts the procedure (round 4d repair 2: it is held, so that
                    # procedure has a selected proposal and is never called missed). The passage's own leads are read
                    # once and each lead is compared with the openers once per code (round 7 validation:1,
                    # validation:2: name by name, a passage was rescanned per opener and every match was appended
                    # per passage, openers x passages); the openers it speaks for keep the order that reading
                    # passage by passage, opener by opener, gives.
                    hits = []
                    for lead in checks._VAL_owned_leads(text, reading.start, reading.end, code, day):
                        if lead not in lead_openers:
                            lead_openers[lead] = tuple(index for index, m in enumerate(openers)
                                                       if checks._VAL_lead_matches(code, lead, m.span.text))
                        if lead_openers[lead]:
                            hits.append(lead)
                    counted = not doubted and bool(hits)
                    fresh = [lead for lead in hits if lead not in emitted]
                    emitted.update(fresh)
                    for index in sorted({index for lead in fresh for index in lead_openers[lead]}):
                        span = (openers[index].span.start, openers[index].span.end)
                        if span not in spoken:
                            spoken.add(span)
                            speaks.append(span)
            if not counted:  # round 4d validation:4: and which procedure's judgement made it incomplete, if any
                reading = replace(reading, unnamed=True, judged_by=checks._V2_judged_by(text, reading, day))
        marked.append(reading)
    return tuple(marked), tuple(speaks)


def _VAL_family_index(routing: RoutingResult) -> dict:
    """{family: an overlap test over that family's routed mention spans (_VAL_overlap_test)}, built once per code
    (round 5 bounded:4): "which routed families does this passage touch" then costs two bisections per family, never a
    scan of every routed mention for every hedged passage (20,000 hedged lines took 82 s in assess())."""
    spans: dict[str, list[tuple[int, int]]] = {}
    for finding in routing.findings:
        # round 4c-2 box2:E: a part routing holds as coordinated with the visit is no other service (hold-only)
        spans.setdefault(finding.family, []).extend(
            (m.span.start, m.span.end) for m in finding.mentions
            if not any(cue.startswith(checks._B2_COORDINATED_CUE) for cue in m.cues))
    return {family: _VAL_overlap_test(found) for family, found in spans.items()}


def _other_service(reading: checks.Reading, family: str, families: dict, text: str) -> bool:
    """Whether a hedging linked passage is about another service than the code's (validation:4). For an E/M code: it
    touches no E/M documentation routing reads (visit statement, chief complaint, MDM, time), as "Possible EGD if
    symptoms persist." or "Epigastric pain; rule out celiac disease?" do not. For any other code: it names a routed
    service of another family, none of the code's own, and none of the code family's interventions ("Possible EGD
    ..." cited for a colonoscopy code; never "Possible EGD and biopsy of the sigmoid colon?" for 45380). A hedge that
    names no service is the code's own for a procedure code (fail-closed: "It is unclear whether biopsies were
    taken."). ``families``: the routed mentions indexed once per code (_VAL_family_index)."""
    if reading.status != 'uncertain' or checks.silent(reading.status, reading.cues):
        return False
    named = {name for name, overlaps in families.items() if overlaps(reading.start, reading.end)}
    if family in checks.EM_FAMILIES:
        return 'gi.office_em' not in named
    return bool(named) and family not in named and not checks.names_intervention(text, reading.start, reading.end,
                                                                                  family)


def _undated_visit(own: tuple[checks.Reading, ...], routing: RoutingResult, text: str,
                   day: Optional[date]) -> tuple[checks.Reading, ...]:
    """An E/M code's linked passages without the negative readings its section default alone gave them. The history
    and the plan of an office visit are that visit's own documentation: "Intermittent heartburn for 8 weeks despite
    omeprazole." under History of present illness is not a historical E/M, and "Increase omeprazole to 40 mg twice
    daily." under Assessment and plan is not a planned one, so such a passage is silent and routing's E/M reading
    (visit statement, MDM, time) decides. The same holds for a plan sentence routing holds only because its clause
    says today ("Start omeprazole 40 mg today.": checks.PLAN_TODAY_CUE). Kept: any cue that dates, plans or denies the
    visit ("Return office visit is scheduled for 2026-12-01.", "Return in three months."), and a passage that is itself
    a visit statement routing reads in that section ("Follow-up office visit." under Plan).

    A negative reading by a cue, in a passage that touches no routed E/M mention and names another service (a routed
    mention of another family lies in it, or checks._VAL_names_other_service: "No laboratory testing, imaging,
    endoscopy or other procedure was performed at this encounter."), is about that service, not the visit: it holds
    the E/M (checks._VAL_OTHER_SERVICE_CUE, round 4 validation:6), never excludes it and never stays silent. Indexed
    once per code: two bisections per passage for each overlap question."""
    visits = _VAL_overlap_test([(m.span.start, m.span.end) for f in routing.findings if f.family == 'gi.office_em'
                                for m in f.mentions])
    others = _VAL_overlap_test([(m.span.start, m.span.end) for f in routing.findings
                                if f.family not in checks.EM_FAMILIES for m in f.mentions])
    kept = []
    for reading in own:
        if reading.status not in checks.POSITIVE and not visits(reading.start, reading.end):
            if checks.section_default(reading):
                continue
            if reading.status in checks.NEGATIVE and (
                    others(reading.start, reading.end)
                    or checks._VAL_names_other_service(text, reading.start, reading.end, day)):
                reading = replace(reading, status='uncertain', cues=(checks._VAL_OTHER_SERVICE_CUE,) + reading.cues)
        kept.append(reading)
    return tuple(kept)


# --- phase 2: checks that depend on the other proposals -----------------------------------

# Sections that do not document today's service by default (ARCHITECTURE 5.3): a plan or recommendation reads as
# planned, history as historical, and an indication or chief complaint says why the patient came.
NOT_TODAY_SECTIONS = ('plan', 'history', 'indication')


def _speaks_for_today(mention: ServiceMention) -> bool:
    """Whether a routed mention can document its procedure as done on the date of service, read only from routing's
    status, section and cues.

    Outside plan, history and indication / chief-complaint sections, an 'uncertain' mention counts when routing saw
    something in it (a hedge or a doubt), never when it is silent: in an assessment, impression or examination section
    too, since a hedge there may be about the diagnosis of a procedure stated as done ("Flexible sigmoidoscopy was
    performed with biopsies, proctitis versus infection.", round 4 validation:0). Inside plan, history and indication
    sections a hedge is not a doubt about today's service - a plan that discusses, weighs or conditions a procedure is
    planning it - so only an explicit performance statement that routing downgraded for its section (a 'performed:'
    cue: "EGD was performed today" under Assessment and plan), a plan passage routing holds because its clause says
    today (PLAN_TODAY), and routing's own holds of a procedure stated with no performance cue or at a time that may be
    another date (OTHER_STATED, ANOTHER_TIME: "Two internal hemorrhoids were banded today without complication." on the
    line after "Chief complaint:", round 4 release:7) count there.
    """
    if mention.status in checks.POSITIVE:
        return True
    if mention.status != 'uncertain':
        return False
    if any(cue.startswith(checks.PERFORMED_CUE_PREFIX) for cue in mention.cues):
        return True
    if mention.section in NOT_TODAY_SECTIONS:
        # routing holds a plan passage whose clause says today (PLAN_TODAY): it may be today's procedure (validation:1)
        return checks.says_today_in_plan(mention.cues) or checks._VAL_routing_holds(mention.cues)
    return not checks.silent(mention.status, mention.cues)


NOT_TODAY_SECTION_CUES = tuple(f'section: {kind}' for kind in NOT_TODAY_SECTIONS)


def _stated_as_done(s: _Selection) -> bool:
    """An excluded code whose own linked passage states the act explicitly (a 'performed:' cue) although its reading
    is not performed: the negative status came from elsewhere - the family's document-level judgement - and not from
    the passage's own date, wording or section (a plan or history downgrade names its section). Fail-closed for the
    E/M hold: such a code is possibly performed on the date of service (status:1)."""
    if not s.excluded or s.evaluation is None:
        return False
    return any(r.status in checks.NEGATIVE
               and any(cue.startswith(checks.PERFORMED_CUE_PREFIX) for cue in r.cues)
               and not any(cue.startswith(NOT_TODAY_SECTION_CUES) for cue in r.cues)
               for r in s.evaluation.own)


def _done_today(finding: FamilyFinding) -> Optional[str]:
    """The status in which a routed family documents a service as done on the date of service (performed or
    incomplete), or None. A gi.other finding gathers different procedures, and its family status may rank another
    procedure's denial first ("Anoscopy: patient declined." beside a banding performed today), so one of its
    mentions read as done is enough. No selected code discounts a routed procedure: a test code's passage may state a
    second procedure, or name it after a comma (round 4 validation:1, contract:3, evidence:1, release:1)."""
    if finding.status in checks.POSITIVE:
        return finding.status
    if finding.family == OTHER_GI:
        return next((m.status for m in finding.mentions if m.status in checks.POSITIVE), None)
    return None


def _possibly_today(finding: FamilyFinding) -> bool:
    """A routed family whose performance on the date of service is not established, through a mention that can speak
    for that date. A gi.other finding is read mention by mention: each of its mentions may be another procedure. So,
    outside plan, history and indication sections, is a detected family not read as done (round 4d validation:6): its
    aggregate may rank what the history says of another encounter first ("History of present illness: EGD and
    colonoscopy last month were unremarkable." beside "Assessment: EGD was performed today and showed esophagitis
    versus reflux."), and a hedged mention there is still a possible same-day procedure (ARCHITECTURE 5.6)."""
    if finding.family == OTHER_GI:
        return any(m.status == 'uncertain' and _speaks_for_today(m) for m in finding.mentions)
    if finding.status == 'uncertain' and any(_speaks_for_today(m) for m in finding.mentions):
        return True
    return finding.status not in checks.POSITIVE and any(
        m.status == 'uncertain' and m.section not in NOT_TODAY_SECTIONS and _speaks_for_today(m)
        for m in finding.mentions)


def _cited(mentions: Sequence[ServiceMention], selections: Sequence[_Selection]) -> set[int]:
    """The positions in ``mentions`` of the routed gi.other mentions read as done that a selected, non-excluded
    gi.other code speaks for (validation:5; round 4 validation:7, validation:13). An exact evidence span of such a code
    (whitespace at its ends ignored) speaks for a done mention when it overlaps
    - that mention's sentence and no other done mention's sentence ("Rubber band ligation was performed today. Three
      bands were placed ..." cited whole: one procedure, its passage running past its sentence), or
    - that mention's name and no other done mention's name ("Rubber band ligation x3 was completed today" cited out of
      "..., and incision and drainage of a perianal abscess was performed.").
    A passage across two procedures, by their sentences and by their names, speaks for neither, so neither is certified
    as proposed. Indexed once per assessment: each span costs four bisections, never a pass over every mention."""
    done = [index for index, m in enumerate(mentions) if m.status in checks.POSITIVE]
    spans = []
    for s in selections:
        if legacy_family(s.family) != OTHER_GI or s.excluded:
            continue
        for span in s.evidence:
            start = span.start + len(span.text) - len(span.text.lstrip())
            end = span.end - (len(span.text) - len(span.text.rstrip()))
            if start < end:
                spans.append((start, end))
    if not done or not spans:
        return set()

    def index(of):
        """(starts in order, ends sorted, furthest) over the done mentions' intervals ``of(mention)``; furthest[k] is,
        of the first k + 1 intervals by start, the one that ends last."""
        order = sorted(done, key=lambda i: of(mentions[i])[0])
        furthest, last = [], None
        for i in order:
            last = i if last is None or of(mentions[i])[1] > of(mentions[last])[1] else last
            furthest.append(last)
        return [of(mentions[i])[0] for i in order], sorted(of(mentions[i])[1] for i in order), furthest

    def only(found, start, end) -> Optional[int]:
        """The one done mention whose interval overlaps [start, end), or None: the intervals that start before ``end``,
        less those that end by ``start``; when one is left, it is the one of them that ends last."""
        starts, ends, furthest = found
        before = bisect.bisect_left(starts, end)
        return furthest[before - 1] if before - bisect.bisect_right(ends, start) == 1 else None

    sentences = index(lambda m: (m.sentence.start, m.sentence.end))
    names = index(lambda m: (m.span.start, m.span.end))
    found = {i for start, end in spans for i in (only(sentences, start, end), only(names, start, end)) if i is not None}
    # round 4d validation:10: and the routed mention that corroborated one of its passages (_Evaluation.speaks_for)
    corroborated = {span for s in selections if legacy_family(s.family) == OTHER_GI and not s.excluded
                    for span in s.evaluation.speaks_for}
    return found | {i for i in done if (mentions[i].span.start, mentions[i].span.end) in corroborated}


def _VAL_named_again(mentions: Sequence[ServiceMention], selections: Sequence[_Selection]) -> set[int]:
    """The positions of the done gi.other mentions that name again a procedure a selected, non-excluded gi.other code
    speaks for (_cited, code by code; round 5 validation:5): "Procedure: Anoscopy" cited by 46600 also covers "Anoscopy
    was performed and showed ..." under Findings - one procedure, named twice. Two names are one procedure when they are
    the same single procedure for that code (checks._VAL_same_procedure: equal as words, or both in its one-procedure
    class - 46221 banding, 46600-46615 anoscopy - and neither a hemorrhoidectomy); never a range sibling (an uncoded
    hemorrhoidectomy beside 46221, a capsule endoscopy or another manometry beside 91010), which stays a possible
    missed service. Indexed once per code: a set of its cited names and its class, one look per mention."""
    done = [index for index, m in enumerate(mentions) if m.status in checks.POSITIVE]
    covered: set[int] = set()
    for s in selections:
        if legacy_family(s.family) != OTHER_GI or s.excluded:
            continue
        own = _cited(mentions, [s])
        if not own:
            continue
        names = {checks._VAL_name(mentions[i].span.text) for i in own}
        in_class = any(checks._VAL_in_class(s.code, mentions[i].span.text) for i in own)
        for index in done:
            text = mentions[index].span.text
            if index not in own and (checks._VAL_name(text) in names
                                     or (in_class and checks._VAL_in_class(s.code, text))):
                covered.add(index)
    return covered


def _same_day_family(finding: FamilyFinding) -> bool:
    """A routed family that is a procedure for the same-day E/M rule: a procedure profile, or another GI service.
    Routing emits a gi.other finding only for a procedure documented at this encounter that names none of the
    recognised families (the shared routing contract); with no code its global period is unknown, so it counts the
    way a code without a fee-schedule row does (fail-closed)."""
    profile = PROFILES.get(finding.family)
    return profile is not None and (profile.procedure or finding.family == OTHER_GI)


def _encounter(provider, context, routing, sources, date_state, selections) -> _Encounter:
    active = [s for s in selections if not s.excluded]
    pfs_source = applied_sources(sources, date_state.value).get(PFS)
    procedures = [s for s in active if _same_day_procedure(s)]
    possible = [s for s in active if _same_day_procedure(s, state='uncertain')]
    possible += [s for s in selections if _procedural(s) and _stated_as_done(s)]
    same_day = [f for f in routing.findings if _same_day_family(f)]
    labels = [PROFILES[f.family].label for f in same_day if _done_today(f)]
    labels += [checks.service_name(s.profile, s.code) for s in procedures]
    # A routed family whose performance is not established holds the E/M only through a mention that can speak for
    # the date of service; a selected procedural code whose own status is uncertain always does.
    possible_labels = [PROFILES[f.family].label for f in same_day if _possibly_today(f)]
    possible_labels += [checks.service_name(s.profile, s.code) for s in possible]
    possible_labels = [label for label in dict.fromkeys(possible_labels) if label not in labels]
    rows = {s.code: s.evaluation.reference.pfs for s in active if s.evaluation and s.evaluation.reference.pfs}
    # A reinstated procedure holds an E/M as a selected one does (review:0). On a procedure day the E/M is held
    # already; otherwise record which reinstatements would hold which E/Ms, for review to gate approval on.
    reinstatable = [s for s in selections if s.excluded and s.evaluation is not None and _procedural(s)]
    visits = [s for s in selections if s.family in checks.EM_FAMILIES and s.evaluation is not None
              and checks.separate_em_statement(s.evaluation.finding) is None]
    gate = bool(reinstatable and visits and not (labels or possible_labels))
    bases = []
    for s in active:
        profile = reconcile.catalogue.code_profile(s.code)
        match = s.evaluation.match if s.evaluation is not None else None
        if profile is None or not profile.base or match is None:
            continue
        others = tuple(t.code for t in active if t is not s and t.family == s.family
                       and (reconcile.catalogue.code_profile(t.code) or reconcile.catalogue.CodeProfile('')).covers
                       and t.evaluation is not None and t.evaluation.match is not None
                       and t.evaluation.match.service.id == match.service.id)
        entry = reconcile.catalogue.entry(s.family)
        reportable = [a for a in match.service.acts if a.status == 'performed' and a.role in ('physician', 'unknown')
                      and entry is not None and a.kind in entry.acts and not reconcile._bundled(match.service, a)]
        if others or reportable:
            bases.append((s.code, others or tuple(sorted({reconcile.act_label(a.kind) for a in reportable}))))
    return _Encounter(bases_included=tuple(bases), provider=provider, context=context, sources=sources,
                      date_state=date_state,
                      pfs_source=pfs_source, active_pfs=rows, procedure_labels=tuple(dict.fromkeys(labels)),
                      possible_labels=tuple(possible_labels),
                      global_days=_global_days(procedures + possible, pfs_source, sources, date_state.value),
                      if_reinstated=tuple((s.code, s.profile.label if s.profile.supported else '')
                                          for s in reinstatable) if gate else (),
                      gated_visits=tuple(s.code for s in visits) if gate else ())


def _procedural(s: _Selection) -> bool:
    """A non-E/M code that is procedural: a procedure profile, or a CMS global period other than XXX. A code
    with no fee-schedule row for the date counts (fail-closed): the E/M is then held."""
    if s.family in checks.EM_FAMILIES or s.evaluation is None:
        return False
    if s.profile.procedure:
        return True
    pfs = s.evaluation.reference.pfs
    return not pfs or pfs.get('global_days') != 'XXX'


def _same_day_procedure(s: _Selection, state: str = 'performed') -> bool:
    """A procedural code (``_procedural``) in the given state: 'performed' asks for a performed or incomplete code,
    'uncertain' for one whose performance is not established."""
    if not _procedural(s):
        return False
    return s.performed if state == 'performed' else s.evaluation.outcome.state == 'uncertain'


def _global_days(procedures: Sequence[_Selection], pfs_source, sources, day) -> str:
    if pfs_source is None:
        return checks.global_days_note((), '', checks.unavailable_reason(PFS, sources, day))
    entries = [(s.code, s.evaluation.reference.pfs['global_days']) for s in procedures
               if s.evaluation and s.evaluation.reference.pfs]
    unavailable = (f'the same-day procedure codes are not listed in {pfs_source.release}.' if procedures
                   else 'no same-day procedure code is selected.')
    return checks.global_days_note(entries, pfs_source.release, unavailable)


def _keyed(selections: Sequence[_Selection], encounter: _Encounter) -> tuple[ProposalAssessment, ...]:
    """Selected-bucket proposals first, then excluded; keys count within each bucket in provider order."""
    selected, excluded = [], []
    for selection in selections:
        bucket, prefix = (excluded, 'exc') if selection.excluded else (selected, 'sel')
        bucket.append(_proposal(selection, f'{prefix}:{len(bucket)}', encounter))
    return tuple(selected + excluded)


def _proposal(s: _Selection, key: str, enc: _Encounter) -> ProposalAssessment:
    if s.evaluation is None:
        return _excluded_early(s, key, enc.provider)
    finding, outcome, ref = s.evaluation.finding, s.evaluation.outcome, s.evaluation.reference
    profile, name, day = s.profile, checks.service_name(s.profile, s.code), enc.date_state.value
    release = enc.pfs_source.release if enc.pfs_source else ''
    m, supported = s.evaluation.match, s.evaluation.support
    status_found = checks.status_check(outcome, name) if m is None else _service_status_check(m)
    found: list[Check] = [checks.scope_check(s.code_kind, s.scope_reason),
                          *checks.evidence_checks(s.evidence, s.dropped),
                          checks.routing_check(profile, finding), status_found]
    if supported is not None:
        found.append(reconcile.support_check(supported))
    clarifications: list[ClarificationSpec] = []
    considerations: list[str] = []
    if outcome.state == 'incomplete':
        found.append(checks.incomplete_check(outcome))
        considerations.append(checks.incomplete_consideration(s.code, ref.pfs, release))
    if m is not None:
        considerations += _service_considerations(s, m)
    included = dict(enc.bases_included).get(s.code)
    if included and not s.excluded:
        service_name = reconcile.service_label(m.service) if m else 'service'
        if all(code[:1].isdigit() for code in included):
            reason = (f'The documented {service_name} has interventions that {", ".join(included)} account for; its '
                      'diagnostic examination is normally included in them (internal profile rule; NCCI procedure-to-'
                      'procedure edits are not connected). Held for the reviewer, not excluded.')
        else:
            reason = (f'The documented {service_name} includes {", ".join(included)}, which this diagnostic code does '
                      'not account for (internal profile rule). Held for the reviewer, not excluded.')
        found.append(Check('services.base_included', 'Diagnostic examination beside its interventions', 'warn', reason,
                           reconcile.SOURCE))
        clarifications.append(ClarificationSpec(scope='proposal', fact='base_included', family=s.family,
                                                proposal_key=key, reason=reason,
                                                question=f'Is {s.code} reported separately from {", ".join(included)} '
                                                         'for this examination?'))
    states = checks.required_fact_states(profile, finding, enc.context)
    facts_check = checks.required_facts_check(profile, states)
    if facts_check:
        found.append(facts_check)
    if s.family in checks.EM_FAMILIES and not enc.procedure_day:
        found.append(checks.SAME_DAY_COVERAGE_CHECK)
        if s.code in enc.gated_visits:
            found.append(checks.same_day_if_reinstated_check(enc.if_reinstated))
    if not s.excluded:
        if outcome.state == 'uncertain' and m is not None:
            fact = f'conflict:{m.conflict.subject}' if m.conflict is not None else 'performed_status'
            clarifications.append(ClarificationSpec(
                scope='proposal', fact=fact, family=s.family, proposal_key=key,
                question=m.question or f'Confirm whether {s.code} is supported by what was done on the date of service.',
                reason=m.detail))
        elif outcome.state == 'uncertain':
            clarifications.append(checks.performed_clarification(outcome, name, s.family, key))
        clarifications += checks.fact_clarifications(states, profile, s.family, key)
        if s.family in checks.EM_FAMILIES and enc.procedure_day:
            documented = checks.separate_em_statement(finding)
            found.append(checks.em_procedure_check(enc.procedure_labels, enc.global_days, documented,
                                                   enc.possible_labels))
            if documented is None:
                clarifications.append(checks.separate_em_clarification(enc.procedure_labels, s.family, key,
                                                                        enc.possible_labels))
            considerations.append(checks.SEPARATE_EM_CONSIDERATION)
    if day is None:
        found.append(checks.PROPOSAL_DATE_CHECK)
    found += [checks.pfs_check(s.code, ref, enc.sources, day), checks.mue_check(s.code, s.units, ref, enc.sources, day)]
    if profile.procedure or (ref.pfs and ref.pfs.get('endo_base')):
        found.append(checks.endoscopic_check(s.code, ref, enc.active_pfs, enc.sources, day))
    found += checks.NOT_CONNECTED_CHECKS
    if s.units > 1:
        found.append(checks.duplicate_check(s.code, s.units))
    pctc = checks.pctc_consideration(s.code, ref.pfs, release, _billing(enc.context))
    if pctc:
        considerations.append(pctc)

    if s.excluded:
        holds = list(checks.fact_clarifications(states, profile, s.family, key))
        if s.family in checks.EM_FAMILIES and enc.procedure_day and checks.separate_em_statement(finding) is None:
            holds.append(checks.separate_em_clarification(enc.procedure_labels, s.family, key, enc.possible_labels))
        found.append(checks.reinstatement_check(holds, date_unknown=day is None))
        if any(code == s.code for code, _ in enc.if_reinstated):
            found.append(checks.same_day_em_check(enc.gated_visits))
    if s.excluded:
        status = 'excluded'
    elif clarifications or day is None:  # an unknown service date holds every proposal on the encounter question
        status = 'needs_clarification'
    else:
        status = 'ready'
    return ProposalAssessment(
        key=key, bucket='excluded' if s.excluded else 'selected', code=s.code, code_kind=s.code_kind,
        family=s.family, profile_version=profile.version, status=status,
        exclusion_reason=(_service_exclusion(m) if m is not None else checks.exclusion_reason(outcome, name))
        if s.excluded else '', reinstatable=s.excluded,
        provider_display=s.display, evidence=s.evidence,
        rationale=rationale.selected_rationale(provider=(f'{enc.provider} in a second review limited to the '
                                                         'unresolved documented service'
                                                         if s.origin == 'second_review' else enc.provider),
                                               units=s.units, evidence_count=len(s.evidence),
                                               profile=profile, detected=finding is not None, outcome=outcome,
                                               facts=_documented_facts(finding, states, m)),
        checks=tuple(found), modifier_considerations=tuple(considerations), units=s.units,
        fingerprint=_fingerprint(s.code, s.family, profile.version, s.evidence, found,
                                 _relevant_context(s.family, enc, bool(pctc)), s.units, status),
        clarifications=tuple(clarifications), support=_support_json(m, supported, s.origin))


def _service_status_check(m: reconcile.Match) -> Check:
    status = {'performed': 'pass', 'incomplete': 'pass', 'not_performed': 'fail', 'uncertain': 'warn'}[m.state]
    if m.reason == 'profile_unknown' and m.state != 'uncertain':
        status = 'warn'
    return Check('service.status', 'Service performed on this encounter', status, m.detail, reconcile.INVENTORY_SOURCE)


def _service_exclusion(m: reconcile.Match) -> str:
    return f'{m.detail} Reinstate if this code is supported.'


def _service_considerations(s: _Selection, m: reconcile.Match) -> list[str]:
    """Modifier considerations the documented service supports (never assigned; payer and NCCI sources are not
    connected): separate lesions within one endoscopic family, and screening that became therapeutic."""
    out = []
    service = m.service
    lesions = {a.lesion for a in m.acts if a.lesion}
    others = [a for a in service.acts if a.status == 'performed' and a.lesion and a.lesion not in lesions
              and a.kind in reconcile.REMOVAL_KINDS + ('biopsy', 'ablation', 'injection', 'tattoo')]
    if lesions and others:
        here = '; '.join(reconcile.lesion_words(service, l) for l in sorted(lesions))
        there = '; '.join(sorted({reconcile.lesion_words(service, a.lesion) for a in others}))
        out.append(f'Separate lesions are documented: this code\'s act is on {here}, and another act is on {there}. '
                   'If an NCCI procedure-to-procedure edit pairs the two codes, a distinct-lesion modifier (59 or XS) '
                   'may apply. NCCI edits are not connected; no modifier is assigned.')
    if service.intent == 'screening' and m.acts:
        out.append('The documented intent is screening and a therapeutic or diagnostic act was performed: payer rules '
                   'for a screening examination that becomes therapeutic (for example Medicare modifier PT, '
                   'commercial modifier 33) are not connected. No modifier is assigned.')
    return out


def _support_json(m, supported, origin='primary') -> dict:
    if m is None:
        return {'origin': origin} if origin != 'primary' else {}
    out = {'origin': origin, 'service': m.service.id, 'family': m.service.family, 'state': m.state, 'reason': m.reason,
           'detail': m.detail, 'acts': [{'id': a.id, 'kind': a.kind, 'label': reconcile.describe_act(m.service, a)}
                                        for a in m.acts]}
    if supported is not None:
        out.update({'status': supported.status, 'supporting': list(supported.supporting),
                    'unrelated': list(supported.unrelated), 'detail_support': supported.detail,
                    'source': [{'start': sp.start, 'end': sp.end, 'text': sp.text} for sp in supported.source]})
    return out


def _excluded_early(s: _Selection, key: str, provider: str) -> ProposalAssessment:
    """Out of scope, or no exact evidence: not reinstatable, and only the checks that ran."""
    found = [checks.scope_check(s.code_kind, s.scope_reason)]
    if not s.scope_reason:
        found += checks.evidence_checks(s.evidence, s.dropped)
    profile = s.profile
    return ProposalAssessment(
        key=key, bucket='excluded', code=s.code, code_kind=s.code_kind, family=s.family,
        profile_version=profile.version, status='excluded', exclusion_reason=s.scope_reason or NO_EVIDENCE,
        reinstatable=False, provider_display=s.display, evidence=s.evidence,
        rationale=rationale.selected_rationale(provider=provider, units=s.units, evidence_count=len(s.evidence),
                                               profile=profile, detected=False, outcome=None, facts=()),
        checks=tuple(found), modifier_considerations=(), units=s.units,
        fingerprint=_fingerprint(s.code, s.family, profile.version, s.evidence, found, {}, s.units, 'excluded'))


def _alternative(index: int, item: ProviderCode, text: str, pages, provider: str) -> ProposalAssessment:
    code_kind, scope_reason = checks.code_scope(item.code)
    kept, _ = checks.exact_evidence(item.evidence, text, pages)
    family = family_for_code(item.code)
    found = (checks.scope_check(code_kind, scope_reason),)
    profile_version = PROFILES[family].version
    # A parent code is quoted only in a strict code shape: an unlisted provider 'code' may carry wording or line
    # breaks, and is never shown anywhere.
    parent = item.parent_code if item.parent_code and checks.code_scope(item.parent_code)[0] != 'invalid' else None
    unlisted_parent = bool(item.parent_code) and parent is None
    return ProposalAssessment(
        key=f'alt:{index}', bucket='alternative', code=item.code, code_kind=code_kind, family=family,
        profile_version=profile_version, status='informational',
        exclusion_reason=rationale.alternative_note(item.role, parent, unlisted_parent=unlisted_parent),
        reinstatable=False, provider_display=item.display, evidence=kept,
        rationale=rationale.alternative_rationale(provider=provider, role=item.role, parent_code=parent,
                                                  evidence_count=len(kept), unlisted_parent=unlisted_parent),
        checks=found, modifier_considerations=(), units=1,
        fingerprint=_fingerprint(item.code, family, profile_version, kept, found, {}, 1, 'informational'))


def _billing(context: Mapping[str, Fact]) -> str:
    fact = context.get('billing_context')
    return str(fact.value) if fact is not None and checks.is_documented(fact) else 'not documented'


def _documented_facts(finding: Optional[FamilyFinding], states, m=None) -> list[tuple[str, str]]:
    if m is not None:
        # The documented service's own reading (acts read with their negation and time), never a flat word list.
        service = m.service
        facts = [(name, value) for name, value in (('extent', service.extent), ('completion', service.completion
                                                                                  if service.completion != 'unknown'
                                                                                  else ''),
                                                   ('intent', service.intent)) if value]
        acts = [reconcile.describe_act(service, a) for a in service.acts if a.status == 'performed'
                and a.role in ('physician', 'unknown')]
        if acts:
            facts.append(('interventions', '; '.join(dict.fromkeys(acts))))
        facts += [(state.name, str(state.fact.value)) for state in states
                  if not state.problem and state.fact is not None and state.name in CONTEXT_FACTS]
        return list(dict.fromkeys(facts))
    facts = [(f.name, str(f.value)) for f in (finding.facts if finding else ()) if checks.is_documented(f)]
    facts += [(state.name, str(state.fact.value)) for state in states
              if not state.problem and state.fact is not None and state.name in CONTEXT_FACTS]
    return list(dict.fromkeys(facts))


def _relevant_context(family: str, enc: _Encounter, pctc: bool) -> dict:
    """Context values a decision on this proposal depends on; a change to any of them changes the fingerprint."""
    day = enc.date_state.value
    values = {'service_date': day.isoformat() if day else None}
    names = ('setting', 'patient_status', 'billing_context') if family in checks.EM_FAMILIES else (
        ('billing_context',) if pctc else ())
    for name in names:
        fact = enc.context.get(name)
        values[name] = fact.value if fact is not None and checks.is_documented(fact) else None
    return values


def _fingerprint(code, family, profile_version, evidence, found, context_values, units, status) -> str:
    return sha256_json({'code': code, 'family': family, 'profile_version': profile_version,
                        'evidence': sorted(span.text for span in evidence),
                        'checks': sorted([check.id, check.status] for check in found),
                        'context': context_values, 'units': units, 'status': status})


# --- encounter level -------------------------------------------------------------------

def _missed(routing: RoutingResult, selections: Sequence[_Selection], procedure_day: bool,
            reconciled: frozenset | set = frozenset()) -> tuple[list[str], bool]:
    """(labels of performed, profiled families - and other GI services routing detected - without a selected
    proposal, whether an E/M was not counted).

    On a procedure day an unproposed E/M is never reported as missed: that would push toward adding an office
    visit because a procedure report contains history or examination text. Other GI services are read mention by
    mention (validation:5): a procedure done today is covered only by a selected gi.other code whose passage speaks for
    it (_cited), and when another gi.other code is selected the uncovered procedures are named.
    """
    proposed = {s.family for s in selections if not s.excluded}
    unproposed, named = [], {}
    for f in routing.findings:
        if not (f.family in PROFILES and (PROFILES[f.family].supported or f.family == OTHER_GI) and _done_today(f)):
            continue
        if f.family in reconciled and f.family != OTHER_GI:
            continue  # the documented-service reconciliation (services.unresolved) reports this family, act by act
        if f.family == OTHER_GI and f.mentions:
            cited = _cited(f.mentions, selections) | _VAL_named_again(f.mentions, selections)
            uncited = [m.span.text for index, m in enumerate(f.mentions)
                       if m.status in checks.POSITIVE and index not in cited]
            if uncited and OTHER_GI in proposed:
                named[OTHER_GI] = checks.uncited_label(PROFILES[OTHER_GI].label, uncited)
            if uncited:
                unproposed.append(f.family)
        elif f.family not in proposed:
            unproposed.append(f.family)
    visit_skipped = procedure_day and any(family in checks.EM_FAMILIES for family in unproposed)
    labels = [named.get(family, PROFILES[family].label) for family in unproposed
              if not (procedure_day and family in checks.EM_FAMILIES)]
    return list(dict.fromkeys(labels)), visit_skipped


def _unsupported(routing: RoutingResult, selections: Sequence[_Selection]) -> tuple[dict, ...]:
    """Services outside the GI profiles: routed or selected ones documented as done, then selected ones held for
    clarification (status 'uncertain'), then selected ones their status reading excluded, which a reviewer may
    reinstate (status 'excluded', round 4 validation:8), so a held or excluded code is neither called performed nor
    reported as absent."""
    entries: dict[str, dict] = {}
    held: dict[str, dict] = {}
    excluded: dict[str, dict] = {}
    for finding in routing.findings:
        profile = PROFILES.get(finding.family)
        done = _done_today(finding)
        if (profile is None or not profile.supported) and done:
            entries.setdefault(finding.family, _unsupported_entry(finding.family, done))
    for s in selections:
        if s.profile.supported or s.evaluation is None:
            continue
        if s.performed:
            entry = entries.setdefault(s.family, _unsupported_entry(s.family, s.evaluation.outcome.state))
        elif s.evaluation.outcome.state == 'uncertain':
            entry = held.setdefault(s.family, _unsupported_entry(s.family, 'uncertain'))
        else:
            entry = excluded.setdefault(s.family, _unsupported_entry(s.family, 'excluded'))
        entry['codes'].append(s.code)
    return tuple(entries.values()) + tuple(held.values()) + tuple(excluded.values())


def _unsupported_entry(family: str, status: str) -> dict:
    profile = PROFILES.get(family)
    detail = (profile.note if profile and profile.note
              else 'Not covered by any GI profile in this release; review required.')
    return {'family': family, 'label': profile.label if profile else family, 'status': status, 'detail': detail,
            'codes': []}


def _summary(proposals: Sequence[ProposalAssessment], provider_status: str, extraction_status: Optional[str],
             date_state: checks.DateState) -> dict:
    def count(field: str, value: str) -> int:
        return sum(1 for proposal in proposals if getattr(proposal, field) == value)
    return {'selected': count('bucket', 'selected'), 'alternatives': count('bucket', 'alternative'),
            'excluded': count('bucket', 'excluded'), 'ready': count('status', 'ready'),
            'needs_clarification': count('status', 'needs_clarification'), 'provider_status': provider_status,
            'extraction_status': extraction_status,
            'service_date': date_state.value.isoformat() if date_state.value else None}
