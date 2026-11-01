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

from studio.gi.context import charge_question_day, is_member_conflict
from studio.gi import sections as gi_sections
from studio.gi import services as gi_services
from studio.gi.profiles import DETECTED_FAMILIES, PROFILES, PROFILES_VERSION, ServiceProfile, family_for_code
from studio.participants import LABELS as PARTICIPANT_LABELS, PARTICIPANTS as PARTICIPANT_ORDER
from studio.participants import VENDORS as PARTICIPANT_VENDORS
from studio.reference.store import PFS, applied_sources
from studio.types import (CONFIDENCES, CONTEXT_FACTS, PARTICIPANT_STATES, AssessmentResult, Check, ClarificationSpec,
                          CodeReference, EvidenceSpan, Fact, FamilyFinding, LocatedQuote, NormalizedResponse, PageSpan,
                          ParticipantInput, ProposalAssessment, ProviderCode, ReferenceLookup, ReferenceSourceInfo,
                          RoutingResult, ServiceMention, sha256_json)
from studio.gi.detect import DOUBT_PREFIX, UNESTABLISHED
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
    # The routing-era reading of its own passages that did not decide a status the documented service decided as
    # performed (engine._undecided): named in the status check, never dropped. '' when there is none to name.
    note: str = ''
    # Where the document places the act the code accounts for when no service of its family is documented
    # (reconcile.placed_check). None when the inventory documents no such act, or names no service holding it.
    placed: Optional[Check] = None
    # The fee-schedule row a reader reads: the one the installed reading has, while a closing charge block's question leaves
    # ``reference`` empty for the gates. It decides whether the code is a procedure at all (_procedural).
    read_pfs: Optional[dict] = None


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
    # 'participant': proposed by an independent participant no decidable proposal carried the code of (HARNESS.md 5);
    # proposers names them, in stage order: only those that quoted it verbatim (its evidence is their quotes alone).
    proposers: tuple[str, ...] = ()

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
           second_scope: Optional[dict] = None, participants: Sequence[ParticipantInput] = ()) -> AssessmentResult:
    """``participants``: one input per CONFIGURED independent participant (HARNESS.md 5). With none (an installation
    where Astra and Fable are disabled) nothing below reads them and the result is the one this engine made before them
    (I1). With any, _Harness merges their codes: they never decide a status (I2) and agreement never promotes (I3)."""
    if provider_status not in PROVIDER_STATUSES:
        raise ValueError(f'Unknown provider status {provider_status!r}.')
    if extraction_status is not None and extraction_status not in EXTRACTION_STATUSES:
        raise ValueError(f'Unknown extraction status {extraction_status!r}.')
    response = normalized if provider_status == 'succeeded' else None
    if provider_status == 'succeeded' and response is None:
        raise ValueError('A succeeded provider status needs its normalized response.')
    harness = _Harness(participants, text, pages) if participants else None
    # Whether any answer is read: the proposal provider's, or an independent participant's reading (I10: the proposal
    # provider's failure blocks only itself). With no participant it is exactly "the provider answered".
    answered = response is not None or (harness is not None and harness.answered)
    date_state = checks.service_date_state(context, service_date)
    # GI round 3, the narrow release: the question a closing charge block asks holds the date and what hangs on it, never
    # the reading. Every reader reads the date the installed reading sends, as routing does, so the document reads as
    # installed reads it; every gate keeps date_state.value, None: each proposal holds on the encounter question and no
    # dated reference applies (the sixth refutation, parity-6-1 and 6-2: read with no date, a 2025 colonoscopy read as done
    # today, and a code went from ready to excluded). So does a member's held answer that keeps the dateless request's
    # answer (the seventh refutation, parity-7-1 and pipe7-2). A held answer with no provider answer is a state the installed
    # revision reaches, with nothing to misread, and reads as it does (the eighth refutation, delta-1). An independent
    # participant's reading is an answer to read as the provider's is (``answered``; the same as before with none).
    read_day = date_state.value or (None if not answered and is_member_conflict(date_state.fact)
                                    else charge_question_day(text))
    sources = tuple(reference.sources())
    selections: list[_Selection] = []
    proposals: tuple[ProposalAssessment, ...] = ()
    provider = list(checks.provider_checks(provider_status, response))
    coverage: list[Check] = []
    # The documented-service inventory is read from the text alone, before and independently of the proposals; the
    # page spans tell it where a page turns inside a sentence (refutation r1, formats-6).
    inventory = (gi_services.build(text, service_date=read_day, routing=routing, context_facts=context,
                                   pages=pages)
                 if READ_DOCUMENTED_SERVICES else gi_services.ServiceInventory(version=gi_services.INVENTORY_VERSION))
    problems = gi_services.validate(inventory, text)
    usable = inventory if not problems else None  # an inconsistent reading never decides a status; it is reported
    second_merge: Optional[_SecondMerge] = None
    participant_alternatives: tuple[ProposalAssessment, ...] = ()
    if response is not None:
        listable = [c for c in response.codes if isinstance(c.code, str) and 0 < len(c.code) <= MAX_LISTED_CODE]
        if len(listable) < len(response.codes):
            provider.append(checks.unlisted_codes_check(len(response.codes) - len(listable), MAX_LISTED_CODE))
        selections = [_select(group, text, pages, routing, reference, read_day, usable, dated=date_state.value is not None)
                      for group in _merge_selected(listable)]
        second_alternatives: list[ProposalAssessment] = []
        if second is not None and usable is not None:
            primary_day = _encounter(response.provider, context, routing, sources, date_state, selections).procedure_day
            selections, second_alternatives, second_merge = _second_review(
                second, second_scope or {}, selections, text, pages, routing, reference, date_state.value, usable,
                procedure_day=primary_day)
        if harness is not None:
            selections, participant_alternatives = harness.merge(selections, routing, reference, read_day, usable,
                                                                 dated=date_state.value is not None)
        encounter = _encounter(response.provider, context, routing, sources, date_state, selections)
        procedure_day = encounter.procedure_day
        alternatives = (c for c in listable if c.role != 'selected')
        proposals = (_keyed(selections, encounter, harness)
                     + tuple(_alternative(index, item, text, pages, response.provider)
                             for index, item in enumerate(alternatives))
                     + tuple(second_alternatives) + participant_alternatives)
    elif harness is not None:
        # No usable answer from the proposal provider: the participants' codes are judged on their own, by the same path
        # (I10: the provider's failure blocks only itself).
        selections, participant_alternatives = harness.merge(selections, routing, reference, read_day, usable,
                                                             dated=date_state.value is not None)
        encounter = _encounter('', context, routing, sources, date_state, selections)
        procedure_day = encounter.procedure_day
        proposals = _keyed(selections, encounter, harness) + participant_alternatives
    else:
        procedure_day = _encounter('', context, routing, sources, date_state, selections).procedure_day
    if harness is not None:
        proposals = harness.recorded(proposals)
        provider = harness.provider_checks(provider, provider_status, response, proposals)
    active = [(s.code, s.family) for s in selections if not s.excluded]
    # The same-day E/M rule decides for the reconciliation too: on a (possible) procedure day - a routed procedure
    # family or another GI service done or possibly done today, or a selected procedural code (_Encounter) - an office
    # visit without a proposal is not pushed as unresolved, whatever families the inventory reads.
    unresolved, bundled, covered = (reconcile.reconcile(usable, active, procedure_day=procedure_day) if usable
                                    else ([], [], {}))
    included_by = _included_by(usable, covered)
    if second_merge is not None:
        # worded once the reconciliation this assessment records is known (refutation 7c8, reports-2)
        provider.append(_second_review_check(second_merge, unresolved))
    # documented services performed with no proposal that the reconciliation does not list (refutation 7c8, reports-1):
    # recorded in completeness and named by the services.unresolved check, which never passes beside one (its skeptic)
    not_listed = reconcile.uncounted(usable, unresolved, covered) if usable else []
    if answered:
        # Read once the reconciliation is known (refutation p2, reports2:0): a performed service routing detected with no
        # selected proposal is named whatever services.unresolved also lists, never covered by "every performed service
        # that routing detected has a selected proposal"; only a family the reconciliation accounts for with another
        # service's selected code is not.
        documented_em = any(checks.separate_em_statement(f) for f in routing.findings if f.family in checks.EM_FAMILIES)
        coverage.append(checks.unproposed_check(*_missed(routing, selections, procedure_day,
                                                         _accounted_elsewhere(usable, included_by, routing)),
                                                separate_em=documented_em))
    service_questions = _service_questions(usable, proposals, context) if usable else []
    unsupported = _unsupported(routing, selections)
    encounter_checks = [*provider, checks.extraction_check(extraction_status, extraction_messages),
                        checks.service_date_check(date_state), reconcile.inventory_check(inventory, problems),
                        *coverage]
    if usable and answered:
        encounter_checks.append(reconcile.unresolved_check(unresolved, usable.problems, not_listed))
    if usable:
        encounter_checks.append(reconcile.conflicts_check(usable))
        attribution = reconcile.attribution_check(usable, [code for code, _ in active])
        if attribution:
            encounter_checks.append(attribution)
    encounter_checks.append(checks.unsupported_check(unsupported))
    if harness is not None:
        encounter_checks += harness.encounter_checks(usable or inventory)
    clarification = checks.service_date_clarification(date_state)
    clarifications = ((clarification,) if clarification else ()) + tuple(service_questions)
    clarifications += tuple(_member_conflict_questions(context, clarifications, proposals))
    open_questions = len(clarifications) + sum(len(p.clarifications) for p in proposals)
    read = {s.evaluation.match.service.id for s in selections
            if s.evaluation is not None and getattr(s.evaluation, 'match', None) is not None}
    unestablished = sum(1 for svc in (usable or inventory).services if svc.status == 'uncertain' and svc.id not in read)
    complete = reconcile.completeness(usable or inventory, unresolved, open_questions,
                                      provider_status == 'succeeded' and response is not None,
                                      unestablished=unestablished, not_listed=not_listed)
    if problems:
        complete['state'] = 'incomplete'
        complete['reasons'] = list(complete['reasons']) + ['the documented-service reading was inconsistent']
    if harness is not None:
        harness.complete(complete, usable or inventory)
    complete.update({
        'unresolved_items': [_jsonable_unresolved(u, i < SECOND_REVIEW_CHECKED
                                                  and _routing_agrees(u, usable or inventory, routing, text, service_date))
                             for i, u in enumerate(unresolved)],
        'bundled': [{'service': b.service, 'act': b.act, 'label': b.label, 'why': b.why} for b in bundled],
        # documented services performed with no proposal and not listed as unresolved (refutation 7c8, reports-1)
        'not_listed': [{'service': s.id, 'family': s.family, 'label': reconcile.uncounted_label(s)} for s in not_listed],
        'covered': covered, 'catalogue_version': reconcile.catalogue.CATALOGUE_VERSION,
        # the selected codes of the service each included service is read as part of that include its examination: the
        # documented services' inclusion line is worded from it (refutation P2RA, EUS lens 1)
        'included_by': included_by,
        'inventory_problems': list(problems)})
    return AssessmentResult(
        profiles_version=PROFILES_VERSION, engine_version=ENGINE_VERSION, proposals=proposals,
        encounter_checks=tuple(encounter_checks), clarifications=clarifications,
        unsupported=unsupported, reference_sources=checks.reference_source_entries(sources, date_state.value),
        summary=_summary(proposals, provider_status, extraction_status, date_state),
        services=_jsonable_inventory(inventory), completeness=complete)


@dataclass(frozen=True)
class _SecondMerge:
    """What merging the bounded second review did, worded into its check (_second_review_check) once the reconciliation
    the assessment records is known, so the check never says more than the stored completeness."""
    what: str  # the asked items, as its request named them, quoted as items (_asked_items)
    asked: tuple[str, ...]  # their labels
    refused: bool
    problems: tuple[str, ...]
    added: tuple[str, ...]  # the codes added as proposals
    listed: tuple[str, ...]  # the codes it selected that are not added (alternatives, each with why)
    accounts_for: tuple[str, ...]  # the labels of the unresolved items the added codes account for
    unlisted: int = 0  # codes it returned that cannot be listed (empty, or longer than MAX_LISTED_CODE)


SECOND_REVIEW_NAMED = 4  # asked items the second review's check names; the rest are counted, never dropped unseen


def _asked_items(labels: Sequence[str]) -> str:
    """The asked items quoted as items: each label as the reconciliation worded it, separated by semicolons, for a list
    that follows a colon and ends its sentence. A label is a clause ("endoscopic ultrasound (documented as performed)
    has no supported proposal") or a phrase, so it is never worded into a sentence as a noun phrase (seen live on
    2026-10-28: "A second review limited to the passages of endoscopic ultrasound (documented as performed) has no
    supported proposal added no proposal for them."). Past SECOND_REVIEW_NAMED the rest are counted."""
    more = len(labels) - SECOND_REVIEW_NAMED
    return '; '.join(labels[:SECOND_REVIEW_NAMED]) + (f' and {more} more' if more > 0 else '')


def _second_review(second: NormalizedResponse, scope: dict, selections: list, text: str, pages, routing, reference,
                   day, inventory, procedure_day: bool = False) -> tuple[list, list, _SecondMerge]:
    """Merge the bounded second review (ARCHITECTURE 5.11). Only a code it SELECTED that accounts for a documented
    service or act left unresolved by the primary proposals becomes a proposal (marked as from the second review); every
    other code it lists is informational. Nothing is promoted from an alternative and nothing is invented. A service
    read as part of another is accounted for by a code of that other service that includes its examination, as the
    reconciliation reads it (reconcile.includes_through)."""
    active = [(s.code, s.family) for s in selections if not s.excluded]
    unresolved, _, _ = reconcile.reconcile(inventory, active, procedure_day=procedure_day)
    open_items = [(u.service, u.family, u.act, u.label) for u in unresolved
                  if u.reason in ('no_proposal', 'not_covered')]
    # A code is already proposed only by a primary proposal a reviewer can decide (selected, or excluded and
    # reinstatable). A selection excluded for scope or evidence (no exact passage; never reinstatable) is none, so it
    # never hides the second review's selection of that code, which is judged as any other; and a code a decidable
    # primary proposal carries is listed with why, never dropped unseen (refutation 7c8, reports-0: the second review's
    # exactly quoted 45380 was skipped behind the primary's inexact one, and its check said it selected no code that
    # accounts for the biopsy).
    have = {s.code for s in selections if s.evaluation is not None}
    listable = [c for c in second.codes if isinstance(c.code, str) and 0 < len(c.code) <= MAX_LISTED_CODE]
    added, listed = [], []  # listed: (a code it selected that is not added, why it is not added)
    accounted: list[str] = []  # the labels of the open items the added codes account for
    for group in _merge_selected(listable):
        code = group[0].code
        if code in have:
            listed.append((group[0], 'a primary proposal already carries it'))
            continue
        candidate = _select(group, text, pages, routing, reference, day, inventory)
        profile = reconcile.catalogue.code_profile(code)
        match = candidate.evaluation.match if candidate.evaluation is not None else None
        # a whole service left without a proposal is accounted for only by a code the document supports as done (its
        # base code, or an act it documents) - never by a code for an act nothing documents, which would hide the
        # missing service behind a held proposal (refutation r1, sends lens)
        supported = match is not None and match.state in ('performed', 'incomplete')
        covered = [label for service, family, act, label in open_items if profile is not None and (
            (family == candidate.family and ((act == '' and supported) or act in profile.covers
                                             or (act in ('tattoo', 'injection') and {'tattoo', 'injection'}
                                                 & set(profile.covers))))
            # a whole service read as part of another (an EGD inside an EUS) is accounted for by a code of that other
            # service that includes its examination - documented as done, which is why it is listed - as the
            # reconciliation reads it once the code is selected, whatever that code's own acts leave to the reviewer
            # (reconcile.includes_through; refutation P2RA, EUS lens 2: an EGD-with-EUS code the second review selected
            # for the listed EGD was kept as an alternative that "accounts for no documented service or act the primary
            # proposals left unresolved", the EGD stayed listed, and the one second review was used up)
            or (act == '' and _includes_through(inventory, service, code, candidate.family)))]
        accounts = bool(covered)
        if accounts and candidate.evaluation is not None and not candidate.excluded:
            added.append(replace(candidate, origin='second_review'))
            have.add(code)
            accounted += covered
        elif profile is None:
            listed.append((group[0], 'the coverage catalogue does not establish which documented act it accounts for'))
        elif not accounts and any(family == candidate.family and act == '' for _, family, act, _ in open_items):
            # Why a whole service's own family's code accounts for nothing is said from what was read: only its exact
            # passages are read, so with none (or out of scope) nothing was, and that is the reason - never a statement
            # about the document (eus2 F1: an EUS documented as performed with its sampling, a 43242 whose one passage
            # was three characters off, had read "not documented as done"); an act the document states both ways is the
            # conflict the assessment records, never one it does not document as done.
            listed.append((group[0], (candidate.scope_reason or NO_EVIDENCE).rstrip('.') if candidate.evaluation is None
                           else 'the document states the act it accounts for both as done and as not done (both are '
                                'kept; neither is chosen)' if match is not None and match.reason == 'conflict'
                           else 'the act it accounts for is not documented as done in the service left unresolved'))
        elif not accounts:
            listed.append((group[0], 'it accounts for no documented service or act the primary proposals left '
                                     'unresolved'))
        elif candidate.evaluation is None:
            listed.append((group[0], (candidate.scope_reason or NO_EVIDENCE).rstrip('.')))
        else:
            listed.append((group[0], 'the document reads what it accounts for as not performed on the date of '
                                     'service'))
    # A code it selected keeps its role, shown with why it is not added - never as a candidate the provider did not select
    # (refutation r1, report lens: the TXT, the CSV and the UI had said "Provider candidate; not selected" of it) - and
    # every code it lists carries the second review as its origin.
    alternatives = [_alternative(index, item, text, pages, f'{second.provider} (second review)', not_added=why)
                    for index, (item, why) in enumerate(listed + [(c, '') for c in listable if c.role != 'selected'])]
    alternatives = [replace(a, key=f'alt2:{index}', support={'origin': 'second_review'})
                    for index, a in enumerate(alternatives)]
    asked = [item for item in scope.get('items', []) if isinstance(item, str) and item]
    merge = _SecondMerge(what=_asked_items(asked) or 'the unresolved documented services', asked=tuple(asked),
                         refused=bool(second.refused), problems=tuple(second.problems),
                         added=tuple(s.code for s in added), listed=tuple(item.code for item, _ in listed),
                         accounts_for=tuple(dict.fromkeys(accounted)), unlisted=len(second.codes) - len(listable))
    return list(selections) + added, alternatives, merge


def _includes_through(inventory, service_id: str, code: str, family: str) -> bool:
    """Whether ``code``, of ``family``, includes the examination of the documented service ``service_id`` through the
    service it is read as part of (reconcile.includes_through)."""
    service = inventory.service(service_id)
    return service is not None and reconcile.includes_through(inventory, service, code, family)


def _second_review_check(merge: _SecondMerge, unresolved: Sequence[reconcile.Unresolved]) -> Check:
    """The second review's check, worded from what the merge did and from ``unresolved``, the reconciliation the
    assessment records: it names the items the added codes account for and the asked items that stay unresolved (a
    warning while any does), never an asked item no added code accounts for (refutation 7c8, reports-2: "selected 45380,
    which account for them" of a biopsy and a dilation, while the dilation stayed unresolved).

    Each sentence states one persisted fact, and every list of items is quoted as items - after a colon, ending its
    sentence (_asked_items): the items the run's scope records as asked; the codes added, and the items this
    reconciliation reads them as accounting for; the codes it selected that are listed as alternatives; the asked items
    this reconciliation still lists. Its response's own problems and the codes it returned that cannot be listed are
    said as the primary's are (provider.problems, provider.unlisted), and make it a warning (eus2 F2: they had been
    said nowhere unless the response was refused whole)."""
    asked, codes = f'A second review was requested for: {merge.what}.', ', '.join(merge.listed)
    if merge.refused:
        # Refused whole, unread: a failed provider check, as provider.status records a refused primary response (round
        # 7 bypass:1), so nothing reports this run's response as used.
        return Check('provider.second_review', 'Second review', 'fail',
                     f'{asked} Its response was not used ({"; ".join(merge.problems)}).', 'cpt-studio:provider@1')
    left = {u.label for u in unresolved}
    still = [label for label in dict.fromkeys(merge.asked) if label in left]
    alternatives = 'an alternative' if len(merge.listed) == 1 else 'alternatives'
    limited = ('It was limited to the text that documents '
               + ('this item' if len(merge.asked) == 1 else 'these items' if merge.asked else 'them'))
    if merge.added:
        one, added = len(merge.added) == 1, ', '.join(merge.added)
        accounted = [label for label in merge.accounts_for if label not in left]
        detail = (f'{asked} {limited} and selected {added}, added as {"a proposal" if one else "proposals"} for review '
                  '(marked as from the second review).')
        if accounted:
            detail += f' {added} {"accounts" if one else "account"} for: {"; ".join(accounted)}.'
        if merge.listed:
            detail += f' It also listed {codes}, shown as {alternatives} only.'
        if still:
            detail += f' Still unresolved: {"; ".join(still)}.'
        status = 'warn' if still else 'info'
    else:
        # "selected no code that accounts for them" was false of a code it selected that accounts for an item but is
        # not added (refutation 7c8, reports-0): what is true is that nothing was added; each alternative says why.
        detail = (f'{asked} {limited} and added no proposal'
                  + (f' (it listed {codes}, shown as {alternatives} only, with why '
                     f'{"it is" if len(merge.listed) == 1 else "each is"} not added)' if merge.listed else '') + '.')
        if still and set(still) == set(merge.asked):
            detail += ' The item stays unresolved.' if len(merge.asked) == 1 else ' The items stay unresolved.'
        elif still:
            detail += f' Still unresolved: {"; ".join(still)}.'
        status = 'warn'
    if merge.problems:
        detail += ' ' + checks.response_problems(merge.problems, "the second review's response")
    if merge.unlisted:
        detail += ' ' + checks.unlisted_codes(merge.unlisted, MAX_LISTED_CODE, 'The second review')
    if merge.problems or merge.unlisted:
        status = 'warn'
    return Check('provider.second_review', 'Second review', status, detail, 'cpt-studio:provider@1')


def _jsonable_unresolved(u: reconcile.Unresolved, second_review: bool = False) -> dict:
    return {'service': u.service, 'family': u.family, 'act': u.act, 'label': u.label, 'reason': u.reason,
            'evidence': [{'start': e.start, 'end': e.end, 'text': e.text} for e in u.evidence],
            'second_review': bool(second_review)}


# A second review is paid for only what both readers read as done today (refutation r1: the documented-service
# reader's misreadings - a missed "no", an earlier procedure, a plan section's boxes, a possibility - each queued one).
# The routing-era reading of the item's own passage must be performed, or silent beside the strict check-box and
# form-field rule (interpretation 24); a whole service needs routing's reading of its family performed. Fail-closed: an
# item routing reads otherwise stays listed for the reviewer and is never sent.
SECOND_REVIEW_CHECKED = 64  # unresolved items checked (a second review asks about at most eight)
STRICT_PROMOTIONS = (gi_services.OWN_BOX_CHECKED, 'performed: its form field is checked')


def _routing_agrees(u: reconcile.Unresolved, inventory, routing: Optional[RoutingResult], text: str,
                    day: Optional[date]) -> bool:
    """Whether the routing-era reader also reads the unresolved item as done today (see SECOND_REVIEW_CHECKED), or -
    GI round 4, package PO - does not contradict the documented-service reading of it on a document whose own head
    makes it today's procedure report (_po_not_contradicted). Either only marks the item as one a second review may ask
    about: the review is still asked for by a member, once per revision and date (jobs.request_second_review), and no
    stage sends one."""
    if u.reason not in ('no_proposal', 'not_covered') or routing is None:
        return False
    families = {u.family, legacy_family(u.family)}
    if not u.act and any(f.family in families and f.status in ('performed', 'incomplete') for f in routing.findings):
        return True
    from studio.gi import detect  # the analysis is cached per text: one routing analysis for every item
    service = next((s for s in inventory.services if s.id == u.service), None)
    strict = bool(u.act) and any(c in STRICT_PROMOTIONS for a in (service.acts if service is not None else ())
                                 if a.kind == u.act and a.status == 'performed' for c in a.cues)
    for ev in u.evidence:
        if not (0 <= ev.start < ev.end <= len(text)):
            continue
        status, cues = detect.status_for_span(text, ev.start, ev.end, day)
        if status in ('performed', 'incomplete'):
            return True
        if status == 'uncertain' and cues[:1] and cues[0].startswith('performed') \
                and all(c == detect.UNESTABLISHED for c in cues[1:]):
            return True  # its own clause states it done; only routing's family summary doubts the service
        if strict and status == 'uncertain' and cues[:1] and cues[0].startswith(detect.SILENT):
            return True
    return _po_not_contradicted(u, routing, text, day, families, inventory)


# GI round 4, package PO (the plan's M1 and PO-2). Routing reads a family that is named only in a title, a grid header
# or a line under a heading it does not know as silent, and reads a passage that a runaway section reaches across an
# unread heading-like line as that section's (h4-02, h4-05): such readings say nothing against the documented-service
# reading, so the unresolved item is offered for the member-asked second review. Every condition only withholds the
# offer (fail-closed), and the document's own head must make it today's procedure report: a records review, a pasted
# outside report, an education handout or a note written around a procedure (booking, call, consent) is never offered
# this way, whatever routing reads in it. Amended 2026-11-01 (tests/fixtures/gi4/declarations/po.json,
# amendment_20261101) with five holds the package's own refutation earned: A1 a head field labelled sedation or
# anaesthesia, A2 the family named on a title line of the head, A3 (PO-2) a passage of the item on such a title line,
# A4 (PO-2) no unread heading naming another occurrence anywhere within the reach, A5 no statement that a procedure was
# called off or not performed which names none.
_PO_OWN_TIME = ('historical:', 'planned:')  # routing's cue for a time word of the mention's own clause
# A1: a field of the head whose LABEL names sedation or anaesthesia ("Sedation:", "Sedation provider:", "Sedation and
# airway:", "Anesthetic care:"). The PS head guard also accepts the word anywhere in a head line ("She tolerated
# sedation poorly in the past.") and any "Attending:" field, which a clinic note carries.
_PO_SEDATION_FIELD = re.compile(r'^[ \t]*+[^:\n]{0,60}?\b(?:sedation|sedative|an(?:a)?esthesia|an(?:a)?esthetic'
                                r'|an(?:a)?esthesiology)\b[^:\n]{0,60}?:', re.A | re.I | re.M)
# A5: a procedure called off or not performed, referred to and not named, in forms routing's own
# cues.PROCEDURE_CANCELLED and cues.PROCEDURE_NOT_PERFORMED do not read (a closed list, read only to hold): "No
# endoscopic procedure was performed today." (never "No other procedures were performed."), "Procedure not
# performed.", "The examination did not take place.", "Status: Cancelled - the patient had eaten breakfast."
_PO_NOT_DONE = re.compile(
    r"\bno\s+(?!(?:other|further|additional|more|separate|extra|second)\b)(?:[\w-]+\s+){1,2}?"
    r"(?:procedures?|endoscop(?:y|ies)|exam(?:ination)?s?|stud(?:y|ies))\s+(?:was|were|has\s+been|have\s+been)\s+"
    r"(?:performed|done|undertaken|attempted)\b"
    r"|\b(?:procedure|exam|examination|study|endoscopy)\s+(?:was\s+|were\s+|is\s+|has\s+been\s+|had\s+been\s+)?"
    r"not\s+(?:been\s+)?(?:performed|done|started|begun|undertaken|attempted|carried\s+out)\b"
    r"|\b(?:procedure|exam|examination|study|endoscopy)\s+(?:did\s+not|didn['’]t|never|could\s+not"
    r"|couldn['’]t)\s+(?:happen|occur|take\s+place|start|begin|proceed|be\s+(?:performed|done))\b"
    r"|\b(?:procedure\s+)?(?:status|outcome)[ \t]*+:[ \t]*+(?:cancel(?:l)?ed|not\s+(?:performed|done|started)"
    r"|postponed|deferred|rescheduled|aborted|called\s+off|no[- ]show)\b", re.A | re.I)


def _po_cached(fn):
    """``fn`` cached as this module's other per-text readers would be: functools.lru_cache(maxsize=4), which
    jobs.release_routing_caches clears (this module is one of its ROUTING_CACHE_MODULES)."""
    import functools  # local: the package edits only functions of its own
    return functools.lru_cache(maxsize=4)(fn)


def _po_not_contradicted(u: reconcile.Unresolved, routing: RoutingResult, text: str, day: Optional[date],
                         families: set, inventory=None) -> bool:
    """Whether routing says nothing against the unresolved item ``u`` the installed rule does not offer: the document is
    today's procedure report by its own head (_po_todays_procedure_report), routing names the item's family on a title
    line of that head where it reads done today or says nothing (A2: a family routing never names has no such
    mention), and either
    - PO-1: every mention of the family is silent, no passage of the item (its evidence) is read as not done today
      or with a worded doubt (_po_says_nothing), and - positive evidence beyond that silence (Wave 1 repair cycle 1,
      refutation F4) - the documented-service reader reads an act of the item's own service as done by an act
      predicate of its own (_po_done_in_body); or
    - PO-2: no mention of the family contradicts - each is done today, says nothing, is another occasion's by a time
      word of its own clause, or is not done today only by a section that reaches it across an unread heading-like line
      (_po_section_only_across_unread_heading) - a passage of the item on a title line says nothing (A3: the
      documented-service reader takes the item from the report's own title), and every passage of the item says
      nothing or is not done today only by such a section, at least one of them so.
    A passage outside the text is never read as saying nothing."""
    report, titles = _po_document(text)
    if not report:
        return False
    mentions = [m for f in routing.findings if f.family in families for m in f.mentions]
    named = any(_po_on_title(titles, m.span.start)
                and (m.status in checks.POSITIVE or _po_says_nothing(m.status, m.cues)) for m in mentions)
    if not named:  # A2
        return False
    from studio.gi import detect  # the analysis is cached per text
    readings = []
    for ev in u.evidence:
        if not (0 <= ev.start < ev.end <= len(text)):
            return False
        readings.append((ev.start, *detect.status_for_span(text, ev.start, ev.end, day)))
    if all(_po_silent(m.status, m.cues) for m in mentions):  # PO-1
        if not _po_done_in_body(u, inventory, text):  # P1: silence is no evidence that anything was done today
            return False
        return all(_po_says_nothing(status, cues) for _, status, cues in readings)
    for m in mentions:  # PO-2: no mention contradicts
        if m.status in checks.POSITIVE or _po_says_nothing(m.status, m.cues):
            continue
        if m.status in ('historical', 'planned') and (_po_another_occasion(m.cues)
                                                      or _po_section_only_across_unread_heading(text, m.span.start,
                                                                                                m.status, m.cues)):
            continue
        return False
    if not any(_po_on_title(titles, pos) and _po_says_nothing(status, cues)
               for pos, status, cues in readings):  # A3
        return False
    runaway = [_po_section_only_across_unread_heading(text, pos, status, cues) for pos, status, cues in readings]
    return any(runaway) and all(r or _po_says_nothing(status, cues) for r, (_, status, cues) in zip(runaway, readings))


# GI round 4, Wave 1 repair cycle 1 (PO-1; refutation F4 of b840ae756): routing's silence about a family and the
# documented-service reader's title are not evidence that anything was done today. A titled report whose procedure was
# called off in words A5 does not list ("we did not go ahead", "the scope was not inserted", "nothing further was done
# today"), or a pre-procedure note titled with the procedure ("Pre-colonoscopy Assessment", "Colonoscopy Admission
# Checklist"), had been offered. PO-1 now also needs the documented-service reader to read an act of the item's own
# service as done by an act predicate of its own ("Cold forceps samples were taken", "the polyp was removed with a hot
# snare") - never an act read only from a title or a procedure line ("Colonoscopy With Cold Snare Polypectomy") - in a
# passage under no line naming another occurrence's record. Hold-only: it withholds offers and offers nothing new.
_PO_ACT_PREDICATE = 'performed: an act predicate'  # services: an act predicate of its own, in a current report or not


def _po_done_in_body(u: reconcile.Unresolved, inventory, text: str) -> bool:
    """P1 (PO-1's positive evidence): an act of the item's own service - for an act item, that act - that the
    documented-service reader reads performed by an act predicate of its own (_PO_ACT_PREDICATE: never only from a
    title, a procedure line, a box or a field), with a passage in the text under no line naming another occurrence's
    record (sections.under_another_occurrence: "Outside records"). False without an inventory or the item's service."""
    service = next((s for s in inventory.services if s.id == u.service), None) if inventory is not None else None
    if service is None:
        return False
    for a in service.acts:
        if u.act and a.kind != u.act:
            continue
        if a.status != 'performed':
            continue
        if not any(c.startswith(_PO_ACT_PREDICATE) for c in a.cues):
            continue
        if any(0 <= ev.start < ev.end <= len(text) and not gi_sections.under_another_occurrence(text, ev.start)
               for ev in a.evidence):
            return True
    return False


def _po_another_occasion(cues: Sequence[str]) -> bool:
    """A not-today mention that is another occasion's by a time word of its own clause ("Earlier EUS: 2025-04-09",
    "slightly larger than at the earlier EUS", "a colonoscopy has been scheduled for 2026-12-03"): at least one such
    cue, and nothing but such cues, section labels and statements of performance (a doubt or a denial riding along says
    something)."""
    return any(c.startswith(_PO_OWN_TIME) for c in cues) and all(
        c.startswith(_PO_OWN_TIME + (checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in cues)


@_po_cached
def _po_document(text: str) -> tuple:
    """(whether the document is today's procedure report by its own head, the spans of its title lines): read once per
    text, whatever the number of unresolved items (the head readers scan the text up to the head's last line)."""
    return _po_todays_procedure_report(text), _po_title_lines(text)


def _po_todays_procedure_report(text: str) -> bool:
    """Positive evidence that the document is a procedure's own report, of a procedure that took place: its head
    carries a sedation or anesthesia line or a field naming who performed it (GI round 4, PS: the judge's guard 1) and
    a field labelled sedation or anaesthesia (A1); none of its head lines is the title of a note written around a
    procedure (booking, scheduling, pre-procedure, telephone or call, instructions, consent, education, handout,
    correspondence, letter, records review); and it never says that a procedure was called off or not performed while
    naming none (A5)."""
    return (gi_sections.procedure_report_head(text)
            and _po_sedation_field(text)
            and not gi_sections.around_procedure_title(text)
            and not _po_procedure_not_done(text))


def _po_sedation_field(text: str) -> bool:
    """A1: a field of the head (its first PROCEDURE_HEAD_LINES non-empty lines) whose label names sedation or
    anaesthesia (_PO_SEDATION_FIELD)."""
    end = gi_sections.head_lines_end(text, gi_sections.PROCEDURE_HEAD_LINES)
    return end > 0 and _PO_SEDATION_FIELD.search(text, 0, end) is not None


def _po_procedure_not_done(text: str) -> bool:
    """A5: whether the text says that a procedure was called off or not performed without naming it ("The procedure was
    cancelled before sedation.", "No endoscopic procedure was performed today."): routing reads such a statement for
    the family the sentence names and attaches it to none, so routing's silence about a family is then no agreement.
    Read anywhere in the text and only to hold (an earlier encounter's cancellation written the same way holds too)."""
    from studio.gi import cues  # local, as detect is in _routing_agrees
    return any(p.search(text) for p in (cues.PROCEDURE_CANCELLED, cues.PROCEDURE_NOT_PERFORMED, _PO_NOT_DONE))


def _po_title_lines(text: str) -> tuple:
    """A2/A3: the (start, end) of the head's title lines - among its first AROUND_PROCEDURE_TITLE_LINES non-empty lines,
    those before its first field line (a colon with a value after it), each a stand-alone line of at most
    AROUND_PROCEDURE_TITLE_CHARS characters with no sentence end, read as sections.around_procedure_title reads a title
    (without its markup; a line longer than four times that is never one). A line under the head's fields is no title:
    the first line of a record copied there ("EGD at Mercy GI") is not the report's."""
    end = gi_sections.head_lines_end(text, gi_sections.AROUND_PROCEDURE_TITLE_LINES)
    out, start = [], 0
    while start < end:
        nl = text.find('\n', start, end)
        line_end = end if nl < 0 else nl
        if line_end - start <= 4 * gi_sections.AROUND_PROCEDURE_TITLE_CHARS:
            line = text[start:line_end].strip().lstrip('#*_>').rstrip('#*_').strip()
            if line and gi_sections._TITLE_FIELD.search(line):
                break  # the head's first field line: the title stands before it
            elif line and len(line) <= gi_sections.AROUND_PROCEDURE_TITLE_CHARS and line[-1] not in '.!?;,':
                out.append((start, line_end))
        elif gi_sections._TITLE_FIELD.search(text, start, line_end):
            break  # a long field line is a field line too
        if nl < 0:
            break
        start = nl + 1
    return tuple(out)


def _po_on_title(titles: tuple, pos: int) -> bool:
    """Whether ``pos`` lies on one of the title lines ``titles`` (_po_title_lines)."""
    return any(start <= pos < end for start, end in titles)


def _po_silent(status: str, cues: Sequence[str]) -> bool:
    """Routing's silence (checks.silent), never read from a reading with no cue at all."""
    return bool(cues) and checks.silent(status, cues)


def _po_says_nothing(status: str, cues: Sequence[str]) -> bool:
    """A reading that says nothing against today: silence, or an uncertain reading no word decided - only section
    labels, a statement of performance its section holds (a runaway indication), or routing's family summary
    (detect.UNESTABLISHED). Any worded doubt (a negation, a hedge, a deferral, a denial) and any not-today status say
    something."""
    if _po_silent(status, cues):
        return True
    return status == 'uncertain' and bool(cues) and all(
        c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX, checks.SILENT_CUE_PREFIX))
        or c == UNESTABLISHED for c in cues)


def _po_section_only_across_unread_heading(text: str, pos: int, status: str, cues: Sequence[str]) -> bool:
    """Whether a not-today reading at ``pos`` takes its time only from its section (historical or planned, every cue a
    section label or a statement of performance, at least one section label), and that section reaches ``pos`` only
    across a heading-like line the layout does not read (sections.beyond_heading_reach), with no occurrence words on the
    nearest heading-like line above (sections.under_another_occurrence: "Previous EUS Findings" tells another time
    itself) nor on any unread heading-like line between the section's heading and ``pos`` (A4:
    _po_unread_line_names_another_occurrence). The section's heading must lie within the helper's reach
    (HEADING_REACH_CHARS and HEADING_REACH_LINES): beyond it beyond_heading_reach answers True without finding a line,
    which fails closed for a hold and would release here, so it is never read as a found line."""
    if status not in ('historical', 'planned') or not cues \
            or not all(c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in cues) \
            or not any(c.startswith(checks.SECTION_CUE_PREFIX) for c in cues):
        return False
    lay = gi_sections.layout(text)
    section = lay.section_at(pos)
    if section.heading is None:
        return False
    lo = text.find('\n', section.heading.end)
    if lo < 0 or lo >= pos or pos - lo > gi_sections.HEADING_REACH_CHARS \
            or text.count('\n', lo, pos) > gi_sections.HEADING_REACH_LINES:
        return False
    return (gi_sections.beyond_heading_reach(text, lay, pos)
            and not gi_sections.under_another_occurrence(text, pos)
            and not _po_unread_line_names_another_occurrence(text, lo, pos))


def _po_heading_like(line: str) -> bool:
    """A short stand-alone line written as a heading, as sections.beyond_heading_reach reads one: at most 60
    characters, opening with a letter, no sentence end, no colon, no list item, two words or more, and every word of
    four letters or more capitalised ("What the Earlier Echoendoscope Showed")."""
    return bool(line) and len(line) <= 60 and line[0].isalpha() and line[-1] not in '.;:!?,' and ':' not in line \
        and not gi_sections._LIST_ITEM.match(line) and len(line.split()) >= 2 \
        and all(w[:1].isupper() for w in gi_sections._HEADING_WORD.findall(line) if len(w) >= 4)


def _po_unread_line_names_another_occurrence(text: str, lo: int, pos: int) -> bool:
    """A4: whether a heading-like line (_po_heading_like) between ``lo`` (the end of the section heading's line) and
    the line of ``pos`` names another occurrence's record (sections.ANOTHER_OCCURRENCE_HEAD: "What the Earlier
    Echoendoscope Showed", "Earlier EUS Report Excerpt"), wherever it stands: sections.under_another_occurrence reads
    only OCCURRENCE_HEAD_LINES lines and OCCURRENCE_HEAD_REACH characters back. Bounded: at most HEADING_REACH_LINES
    lines and HEADING_REACH_CHARS characters, the reach the caller keeps ``pos`` within; False when no such line is
    found there."""
    lo = max(lo, pos - gi_sections.HEADING_REACH_CHARS)
    end = text.rfind('\n', lo, pos)
    for _ in range(gi_sections.HEADING_REACH_LINES):
        if end <= lo:
            return False
        start = text.rfind('\n', lo, end) + 1
        line = text[max(start, lo):end].strip()
        if _po_heading_like(line) and gi_sections.ANOTHER_OCCURRENCE_HEAD.search(line):
            return True
        end = start - 1
    return False


def _jsonable_inventory(inventory) -> dict:
    from studio.types import to_jsonable
    return to_jsonable(inventory)


def _member_conflict_questions(context, asked, proposals) -> list[ClarificationSpec]:
    """A member's encounter metadata that conflicts with the document (context.is_member_conflict) is asked once, at the
    encounter, unless a question already asks about that fact: both sides are kept and neither is used until they
    agree (session interpretations 11 and 19). The service date has its own encounter question."""
    from studio.gi.context import is_member_conflict
    seen = {c.fact for c in asked} | {c.fact for p in proposals for c in p.clarifications}
    out = []
    for name, fact in sorted((context or {}).items()):
        if name == 'service_date' or name in seen or not is_member_conflict(fact):
            continue
        label = checks.fact_label(name)
        out.append(ClarificationSpec(scope='encounter', fact=name, question=f'Which {label} is right for this encounter?',
                                     reason=f'The {label} is in conflict. {fact.note}'))
    return out


def _service_questions(inventory, proposals, context=None) -> list[ClarificationSpec]:
    """Every materially necessary question about a documented service, asked together and once: its missing
    documentation (a sparse visit note's setting, status and basis together) and each conflict in the record. A
    question a proposal of the same family already asks is not asked again."""
    asked = {(c.family, c.fact) for p in proposals for c in p.clarifications}
    out: list[ClarificationSpec] = []
    for service in inventory.services:
        for spec in reconcile.documentation_clarifications(service, context):
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
            day: Optional[date], inventory=None, *, dated: bool = True) -> _Selection:
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
    unmatched = found is None  # the inventory documents no service of the code's family (found is reset below too)
    if found is None and READ_DOCUMENTED_SERVICES and inventory is not None and outcome.state == 'not_performed':
        # No documented service of the code's family: the routing-era reading of its own passage decided alone. The
        # documented-service reader reads that passage too; unless it reads the same not-done status there, the readers
        # do not agree and the code is held with a question, never excluded (ec5 and 7c8, cluster EXCL: both readers
        # must agree; an earlier visit's reference never decides an E/M code). With that reader off
        # (READ_DOCUMENTED_SERVICES) there is no second reading, and the routing-era path stands as before.
        outcome = _held_unless_agreed(outcome, text, day, legacy, pages)
    supported = None
    note = ''
    placed = None
    if found is not None:
        # Engine @4: the documented service and act decide the code's status; its passages are verified against them.
        found = _second_opinion(outcome, found, code, text, inventory, routing)
        if found.reason == 'act_missing' and outcome.state == 'not_performed' \
                and not _time_in_doubt(code, found.service) \
                and _agreed_not_done(code, outcome, found.service, text, day, pages):
            # The inventory documents no such act and the code's own passage reads it as not performed today (a
            # planned repeat, an earlier procedure), and the inventory reads the same not-done status there: the
            # exclusion stands. Never when the inventory states the act done and holds only its time in doubt (a date
            # or a time word in its clause is something else's), nor when it reads that passage otherwise - an act done
            # today, another status, or nothing at all: both readers must agree before a code is excluded, so it is
            # held (7c8 skeptic, sk:9).
            found = None
        elif found.reason == 'act_missing' and outcome.state == 'not_performed' \
                and not _time_in_doubt(code, found.service):
            # Held: GI round 4, Wave 1 repair (PA, CTS-4) - a one-cause disagreement says so, true of the document
            found = _pa_one_cause_hold(found, outcome, code, text, day, pages)
        elif found.reason == 'service_uncertain' and outcome.state == 'not_performed' \
                and _own_passage_decides(outcome) and gi_services.doubted_by_routing_alone(found.service) \
                and not _act_documented(code, found.service, inventory):
            # The same, for a service the inventory reads as performed and only routing's reading of the family makes
            # uncertain (a form field it cannot tie to a printed item, a contrary statement in today's report): the
            # code's own passage reads its act as not performed today (an unchecked box, a "No"), and the inventory
            # documents no act the code accounts for as done or in conflict - it has nothing to add, and the exclusion
            # stands. A code whose act the inventory reads as done, or a base or E/M code, stays held.
            found = None

    def today(span):
        return _today_passage(text, span, day)

    def report_family(span):
        # the study's own report speaks for the study only where a report states what was done, found or concluded:
        # never its header, its signature or another line no such section heads (OWN_REPORT_SECTIONS); and only where
        # the document reports that study alone and the passage states nothing else (attr-F3: never another study's
        # result in a combined report, never a biopsy taken after the study)
        layout = gi_sections.layout(text)
        if any(layout.section_at(pos).kind not in OWN_REPORT_SECTIONS for pos in (span.start, max(span.start,
                                                                                                    span.end - 1))):
            return ''
        return gi_services.report_family_at(text, span.start, span.end, day, pages, sections=OWN_REPORT_SECTIONS)

    if found is not None:
        # For an office visit a passage shows the visit when it is a statement of this visit: neither the clause reader
        # nor the routing-era reading with its E/M rules (_undated_visit: a cue that dates or plans the visit, a visit
        # statement in a plan section) puts it at another time - "Return in three months.", "Follow-up office visit."
        # under Plan. The visit's own history and plan sentences are no such reading, so they still show it. A study's
        # own result sentence, or a passage of its own report, shows the study (today=, report_family=).
        another_time = {(r.start, r.end) for r in own if r.status in checks.NEGATIVE}
        supported = reconcile.support(found, kept, current=lambda span: (span.start, span.end) not in another_time
                                      and gi_services.current_statement(text, span.start, span.end, day),
                                      today=today, report_family=report_family)
        note = _undecided(outcome, found, supported, kept)
        outcome = _service_outcome(found)
    elif unmatched and inventory is not None:
        # No documented service of the code's family: its own passages still decide its status. Where the inventory
        # documents the act it accounts for in another family's service, its passages are verified against that act,
        # and the service is named where the act's own passage names it (refutation gi2 RC5, reconcile.elsewhere).
        elsewhere = reconcile.elsewhere(code, inventory)
        if elsewhere is not None:
            supported = reconcile.support(elsewhere, kept, today=today, report_family=report_family)
            placed = reconcile.placed_check(elsewhere, inventory, PROFILES[selection.family].label)
    row = reference.lookup(code, day if dated else None)
    return replace(selection, evaluation=_Evaluation(finding, outcome, row, own, speaks_for, found, supported, note, placed,
                                                     (row if dated else reference.lookup(code, day)).pfs))


def _today_passage(text: str, span, day: Optional[date]) -> bool:
    """A passage that states something of this encounter in its own sections: none of them a plan, history or
    indication section (NOT_TODAY_SECTIONS), and not read as about another time, planned, denied or cancelled."""
    layout = gi_sections.layout(text)
    if any(layout.section_at(pos).kind in NOT_TODAY_SECTIONS for pos in (span.start, max(span.start, span.end - 1))):
        return False
    return gi_services.current_statement(text, span.start, span.end, day)


def _second_opinion(old: checks.StatusOutcome, found: reconcile.Match, code: str, text: str,
                    inventory=None, routing: Optional[RoutingResult] = None) -> reconcile.Match:
    """The documented service decides the code's status, with the routing-era reading as a second opinion that can
    only hold (ARCHITECTURE 5.10):
    - a hedge, a denial or a cancellation read in the code's OWN passage, when that passage is about the matched
      service (it overlaps the service's or one of its acts' evidence, or names the service or the code's act), holds
      the code with both readings - a doubt about this act is never released by a second reader;
    - a passage read as about another TIME (an earlier visit, a planned repeat) does not decide: the inventory reads
      time per clause and per service, and an unrelated historical reference never invalidates a current service;
      except where that reading rests on the passage's SECTION alone (routing reads it inside a plan or history section,
      "3. Upcoming procedures" over "4. Polyp removed by EMR at a tertiary center.") and the inventory reads the same
      passage as the very act the code accounts for: the two readers then disagree about that passage's own time, so it
      holds (never excludes);
    - a passage about something else (a fragment of a findings sentence) does not decide;
    - where the documented service is not performed but the routing-era reading is positive, the code is held, never
      newly excluded.
    Routing's own family doubts are folded into the service's status by the inventory (services._finish)."""
    positive = found.state in checks.POSITIVE
    if positive and old.state in ('uncertain', 'not_performed'):
        doubt = old.decisive
        own = doubt is not None and doubt.origin == 'evidence' and doubt.start is not None
        holds = (old.state == 'uncertain' and own and _about(doubt, found, code, text, routing, inventory)) or (
            old.state == 'not_performed' and own and doubt.status in ('negated', 'cancelled')
            and _about(doubt, found, code, text, routing, inventory)) or (
            old.state == 'not_performed' and own and _section_time(doubt) and _on_matched_act(doubt, found))
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
            and not _elsewhere(old.decisive, found, inventory) and _states_unread_act(old.decisive, found, code, text):
        # The documented service is performed and the code's own passage states its act (the routing-era reader reads
        # it performed: a form row, a check box, a phrasing this reader does not parse); the inventory does not read
        # that act at all - it neither denies it nor gives the passage to another service - so the code's own reading
        # stands, and says so.
        positive_state = 'incomplete' if found.service.status == 'incomplete' else 'performed'
        return replace(found, state=positive_state, reason='own_passage', question='',
                       detail=f'The {reconcile.service_label(found.service)} is documented as {found.service.status}; '
                              f'the act {code} accounts for is read from its own passage by the routing-era reader '
                              f'({checks.cite(old.decisive)}), not by the documented-service reader.')
    name = checks.service_name(PROFILES[legacy_family(found.service.family)], code)
    if found.state == 'not_performed' and old.state != 'not_performed':
        # Never a new exclusion: the documented service reads as not performed, the routing-era reading does not
        # exclude the code, so it is held for the reviewer - with both readings (5.10).
        why = checks.uncertain_reason(old, name) if old.state == 'uncertain' else checks.status_check(old, name).detail
        return replace(found, state='uncertain', reason='readings_disagree',
                       question=f'Confirm whether {code} was performed on the date of service.',
                       detail=f'{found.detail} The routing-era reading of the passages it cites does not exclude it: '
                              f'{why} Held for the reviewer, not excluded.')
    if found.state == 'uncertain' and old.state == 'uncertain':
        # Held by both readers: the code is held with both readings (5.10), never with the documented service's alone -
        # a hedge in a passage it cites about this service, or routing naming the family only as uncertain.
        doubt = old.decisive
        own = doubt is not None and doubt.origin == 'evidence' and doubt.start is not None
        # (coverage: an explicit performance statement held only by its section is such a reading too - checks.restated
        # - "Colonoscopy was performed with cold snare polypectomy" under Assessment and plan)
        if old.reason == 'unestablished' or (own and (doubt.status not in checks.POSITIVE or checks.restated(doubt))
                                              and _about(doubt, found, code, text, routing, inventory)):
            return replace(found, detail=f'{found.detail} The routing-era reading of the passages it cites also holds '
                                         f'it: {checks.uncertain_reason(old, name)}')
    if found.state == 'not_performed' and old.state == 'not_performed':
        apart = _not_the_same_not_done(found, old, code, text)
        if apart:
            # Both readers read it as not performed, but not the same way (a denial against a plan, an earlier date
            # against a denial) or not from the code's own passage: two different misreadings are no agreement, so it is
            # held, never excluded (7c8 skeptic, sk:9). GI round 4 (PA): or the same status from one cause, the section
            # both readers read (_not_the_same_not_done) - said as the same reading, never as another.
            other = checks.exclusion_reason(old, name).removesuffix(' Reinstate if this code is supported.')
            how = 'reads it the same way' if _pa_same_not_done(found, old) else 'reads it otherwise'
            return replace(found, state='uncertain', reason='readings_disagree',
                           question=f'Confirm whether {code} was performed on the date of service.',
                           detail=f'{found.detail} The routing-era reading of the passages it cites {how}: '
                                  f'{other} {apart} Held for the reviewer, not excluded.')
        # Excluded by both readers: the reason keeps the routing-era reading too, which quotes the passage that
        # dates, plans or denies the service and says what the code's own passages read.
        agreed = checks.exclusion_reason(old, name).removesuffix(' Reinstate if this code is supported.')
        return replace(found, detail=f'{found.detail} The routing-era reading agrees: {agreed}')
    return found


# The cues of a routing-era reading that marks the item itself off: its own box unchecked ("☐ Biopsy"), or its own
# field's denying answer ("Biopsy taken: No") - never a prose sentence, whose not-performed reading can come from the
# family's or the section's status ("A 6 mm polyp was removed." beside "Procedure cancelled: ☒").
OWN_MARK_DENIALS = ('negated: an unchecked box', 'box: negated', 'negated: a field', 'negated: its form field',
                    'negated: the form field', 'field:')


def _own_passage_decides(outcome: checks.StatusOutcome) -> bool:
    """Whether the routing-era outcome is decided by the code's own passage marking its item off - an unchecked box or
    a denying field answer read from that passage - not by routing's reading of the family, and not by prose (triage
    round 2 skeptic: a stated act beside a checked "Procedure cancelled" box had been newly excluded)."""
    decisive = outcome.decisive
    return decisive is not None and decisive.origin == 'evidence' and decisive.start is not None \
        and decisive.status == 'negated' and any(cue.startswith(OWN_MARK_DENIALS) for cue in decisive.cues) \
        and not any(cue.startswith('performed') for cue in decisive.cues)


def _time_in_doubt(code: str, service) -> bool:
    """Whether the inventory states an act ``code`` accounts for as done in ``service`` and holds only its time in
    doubt: an act read uncertain because a time in its clause is something else's (services.OTHER_TIME_CUE; refutation
    r1, negtime-5 and negtime-7). The routing-era reading alone never excludes such a code (ec5, cluster EXCL)."""
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    return any(a.kind in kinds and a.status == 'uncertain'
               and any(cue.startswith(gi_services.OTHER_TIME_CUE) for cue in a.cues) for a in service.acts)


def _not_done_class(status: str) -> str:
    """A not-done status as one reading: a plan, a history, or a denial (negated and cancelled alike)."""
    return 'denied' if status in ('negated', 'cancelled') else status


def _second_reading(outcome: checks.StatusOutcome, text: str, day: Optional[date], pages=()) -> str:
    """Why the documented-service reader does not agree with the routing-era not-performed reading of the code's own
    deciding passage, or '' when it does: what it reads in that passage (services.passage_readings - its acts, service
    and procedure names and act predicates, each in its own clause) holds nothing done today, nothing it reads another
    way (a doubt, another time, a denial against a plan) and at least one thing with the same not-done status. An act
    read done today, another reading, a passage too full to read through, or nothing read at all: no agreement (ec5 and
    7c8, cluster EXCL; sk:7 - a procedure named outside the act vocabulary is read by its name or its predicate), on
    the page-joined view build() reads (``pages``; 7c8 FORMATS skeptic, sk:11). Nor is the same status read only from
    the section the passage stands in, where routing's reading too is that section's alone and the section reaches the
    passage only across a heading-like line the layout does not read: one cause, not two readings (GI round 4, PA: the
    h4-05 counterfactual, a runaway "Prior Studies" section)."""
    decisive = outcome.decisive
    readings = gi_services.passage_readings(text, decisive.start, decisive.end, day, pages)
    if readings is None:
        return 'does not read it through: there is too much in it to read'
    want = _not_done_class(decisive.status)
    agreed = False
    one_cause = None  # whether routing's reading is its section's alone, beyond the heading's reach (read once)
    for reading, clause in readings:
        if gi_services.done_today(reading):
            return f'reads an act in it as done today: \u201c{checks.excerpt(clause.text)}\u201d'
        if _says_nothing(reading.status, reading.cues):
            continue  # named, with nothing said about it either way
        if reading.status in checks.NEGATIVE and _not_done_class(reading.status) == want:
            if _section_only_service_reading(reading.cues):
                if one_cause is None:
                    one_cause = _section_only_routing_reading(decisive, text)
                if one_cause:
                    # GI round 4 (PA): both readers take the time from one section - the layout - so no agreement
                    # (the words that say so come first: a cue is shown to EXCERPT_CHARS characters)
                    return (f'{_PA_ONE_CAUSE}; {_pa_reach(text, decisive.start)} '
                            f'(\u201c{checks.excerpt(clause.text)}\u201d)')
            agreed = True
            continue
        return f'reads it as {reading.status}: \u201c{checks.excerpt(clause.text)}\u201d'
    if agreed or _own_passage_decides(outcome):
        # The same not-done status - or, where this reader says nothing, routing's reading of the item's own mark (its
        # unchecked box, its field's "No"), which this reader leaves to routing's box reader by the box contract.
        return ''
    return 'reads nothing in it as done or as not done'


def _says_nothing(status: str, cues: Sequence[str]) -> bool:
    """A documented-service reading that says nothing either way: silence, or an unchecked box it leaves to routing's
    box reader (services.SAYS_NOTHING)."""
    return status == 'uncertain' and bool(cues) and cues[0] in gi_services.SAYS_NOTHING


# GI round 4, package PA (the diagnosis's S3): a not-today reading whose time is only its section's. The documented-
# service reader writes it "historical: in a history section" or "planned: in a plan section" (services.read_clause);
# routing's carries its section's cue ("section: history (Prior Studies)") and no time cue of its own. Two such readings
# share one cause - the section layout both readers read - so where that section reaches the passage only across a
# heading-like line the layout does not read, they are no agreement: the code is held, never excluded. A section whose
# own heading stands above the passage is the document's own statement, and its readings still agree.
_SECTION_ONLY_SERVICES = ('historical: in a history section', 'planned: in a plan section')
_PA_ONE_CAUSE = 'reads it the same only by its section: one cause, not two readings'  # _second_reading's words


def _pa_own_time(cue: str) -> bool:
    """Whether a reading's cue states a not-done time or status: historical, planned, negated or cancelled (GI round 4,
    PA). A section's own cue (_SECTION_ONLY_SERVICES) is one too."""
    return cue.startswith(('historical:', 'planned:', 'negated:', 'cancelled:'))


def _section_only_service_reading(cues: Sequence[str]) -> bool:
    """Whether a documented-service reading takes its not-done time only from its section: one of its cues is a
    section's (_SECTION_ONLY_SERVICES) and every cue that states a time or a status is one (GI round 4, PA). A time
    word, a date, a denial or a cancellation of its own ("historical: had been", "historical: earlier") is a reading of
    its own, independent of the layout."""
    return any(cue in _SECTION_ONLY_SERVICES for cue in cues) \
        and all(cue in _SECTION_ONLY_SERVICES for cue in cues if _pa_own_time(cue))


def _section_only_routing_reading(reading: checks.Reading, text: str = '') -> bool:
    """Whether routing's reading of the code's own passage takes its time only from its section - its section's cue and
    no time or status cue of its own ("section: history (Prior Studies)", or a performance statement its section made
    historical: "performed: was introduced") - AND that section reaches the passage only across a heading-like line the
    layout does not read as a heading, or from further below its heading than that is read (sections.
    beyond_heading_reach, fail-closed: a runaway history or plan section; GI round 4, PA). A section whose own heading
    stands above the passage is the document's own statement: False, and a reading by it still agrees. Wave 1 repair
    cycle 1 (refutations F6 and CTS-3): only a REAL unread heading counts (_pa_unread_heading) - never a list entry, a
    provider, facility or page line, a bare procedure name, the section's first line, or a line that names another
    occurrence itself."""
    if reading.start is None:  # a reading of the whole family has no passage of its own (and no text: no heading)
        return False
    if not any(cue.startswith(checks.SECTION_CUE_PREFIX) for cue in reading.cues) \
            or any(_pa_own_time(cue) for cue in reading.cues):
        return False
    return bool(_pa_unread_heading(text, reading.start))


# GI round 4, Wave 1 repair cycle 1 (PA; refutations F6 and CTS-3 of b840ae756). The one-cause rule had counted every
# short title-case line between a history or plan heading and the passage as an unread heading: an entry of a surgical
# history list ("Colonoscopy With Biopsy" / "Upper Endoscopy With Dilation"), a provider's or facility's name ("Alan
# Synthetic MD", "Synthetic Regional Medical Center"), a page's running number ("Page 2 of 3"), a procedure's name
# opening a history entry ("Endoscopic Retrograde Cholangiopancreatography"), and a line that itself names an earlier
# occurrence ("What the Earlier Echoendoscope Showed"). Each turned a correct exclusion into a hold, and a held
# procedure then held a READY E/M as possibly same-day. Only a REAL unread heading makes the section's reading one
# cause now: the nearest heading-like line above the passage that stands as a heading - bounded above (a blank line, a
# sentence's end or a field line), followed by content (a sentence, a field, a bulleted item or a long line), not the
# section's first line, and no name, page or bare procedure-name line; such lines are read past as the section's own
# content. When the nearest heading-like line names another occurrence, the document's own words date the passage, and
# the agreement stands. Every rule here only narrows the hold back to the installed exclusion; past the reach read it
# still fails closed (_PA_FAR).
_PA_FAR = '\x00beyond the reach read'  # _pa_unread_heading: the heading lies too far back (fail-closed)
_PA_PAGE_LINE = re.compile(r'(?:page[ \t]*+\d{1,4}(?:[ \t]*+(?:of|/)[ \t]*+\d{1,4})?+'
                           r'|\d{1,4}[ \t]*+(?:of|/)[ \t]*+\d{1,4})', re.A | re.I)
_PA_CREDENTIAL = re.compile(r'(?:,|[ \t])[ \t]*+(?:M\.?D|D\.?O|R\.?N|N\.?P|P\.?A(?:-?C)?|CRNA|Ph\.?D|MBBS|MBChB|FACG'
                            r'|FACP|FASGE|AGAF|FRCPC?|DNP|APRN|ARNP|FNP(?:-BC)?|CNP|LPN)\.?$', re.A)
_PA_TITLE_PREFIX = re.compile(r'(?:Dr|Mr|Mrs|Ms|Mx|Prof)\.?[ \t]+[A-Z]', re.A)
_PA_FACILITY = re.compile(r'\b(?:hospital|medical[ \t]+cent(?:er|re)|health[ \t]+(?:cent(?:er|re)|system|services)'
                          r'|healthcare|clinic|infirmary|university|institute|surgery[ \t]+cent(?:er|re)'
                          r'|surgical[ \t]+cent(?:er|re)|endoscopy[ \t]+(?:cent(?:er|re)|unit|suite)|medical[ \t]+group'
                          r'|associates)\b', re.A | re.I)
_PA_TRAILING_ASIDE = re.compile(r'(?:[ \t]*+\([^()\n]{0,40}\))+$')
# The words a bare procedure name carries beside the service's own name ("Colonoscopy With Biopsy", "Upper Endoscopy
# With Dilation"): connectors, an act or a qualifier. Read only to say a line is an entry of a history, not a heading.
_PA_PROCEDURE_WORDS = frozenset((
    'with', 'without', 'and', 'or', 'of', 'the', 'a', 'an', 'plus', 'via', 'under', 'using', 'to', 'into',
    'biopsy', 'biopsies', 'dilation', 'dilations', 'dilatation', 'polypectomy', 'polypectomies', 'ligation', 'banding',
    'band', 'bands', 'stent', 'stents', 'stenting', 'placement', 'removal', 'exchange', 'sphincterotomy', 'cannulation',
    'ablation', 'injection', 'tattoo', 'tattooing', 'aspiration', 'fine', 'needle', 'fna', 'fnb', 'hemostasis', 'clip',
    'clips', 'clipping', 'snare', 'cold', 'hot', 'forceps', 'balloon', 'upper', 'lower', 'flexible', 'diagnostic',
    'screening', 'surveillance', 'therapeutic', 'emr', 'mucosal', 'resection', 'endoscopic', 'retrograde'))
_PA_NEXT_LINES = 3  # lines read down from a heading-like line for the content it heads


def _pa_bounded_above(line: str) -> bool:
    """Whether a heading may stand right under ``line``: a blank line, a sentence's end or a field line - never a list's
    previous entry or a sentence the heading-like line would continue (GI round 4 Wave 1 repair, PA)."""
    return not line or line[-1] in '.!?' or gi_sections._TITLE_FIELD.search(line) is not None


def _pa_content(line: str) -> bool:
    """Whether ``line`` is content a heading heads: a sentence, a field, a bulleted or numbered item, or a line longer
    than a heading - never another short entry of an unbulleted list (GI round 4 Wave 1 repair, PA)."""
    return len(line) > 60 or line[-1] in '.!?' or gi_sections._TITLE_FIELD.search(line) is not None \
        or gi_sections._LIST_ITEM.match(line) is not None


def _pa_name_line(line: str) -> bool:
    """A page's running number, a provider's name or a facility's ("Page 2 of 3", "Alan Synthetic MD", "Dr. Alan
    Synthetic", "Synthetic Regional Medical Center"; an aside in brackets at its end is read past): never a heading
    (GI round 4 Wave 1 repair, PA)."""
    bare = _PA_TRAILING_ASIDE.sub('', line).strip()
    return _PA_PAGE_LINE.fullmatch(bare) is not None or _PA_CREDENTIAL.search(bare) is not None \
        or _PA_TITLE_PREFIX.match(bare) is not None or _PA_FACILITY.search(bare) is not None


def _pa_procedure_name_line(line: str) -> bool:
    """A bare procedure name ("Endoscopic Retrograde Cholangiopancreatography", "Colonoscopy With Biopsy"): a service
    the documented-service reader names (services.SERVICES) and nothing else but _PA_PROCEDURE_WORDS - an entry of a
    history of procedures, never a heading ("Endosonographic Conclusion" says more: a heading) (GI round 4 Wave 1
    repair, PA)."""
    rest, named = list(line), False
    for _, _, pattern in gi_services.SERVICES:
        for m in pattern.finditer(line):
            named = True
            rest[m.start():m.end()] = ' ' * (m.end() - m.start())
    return named and all(w.lower() in _PA_PROCEDURE_WORDS for w in gi_sections._HEADING_WORD.findall(''.join(rest)))


def _pa_real_heading(text: str, start: int, end: int, first: int, line: str) -> bool:
    """Whether the heading-like ``line`` at [start, end) stands as a REAL heading: not the section's first line under
    its heading (``first``: an entry or a sub-title of the section's own content), no name, page or bare procedure-name
    line, bounded above (_pa_bounded_above), and followed by content (_pa_content: the next non-empty line, read at
    most _PA_NEXT_LINES lines down) (GI round 4 Wave 1 repair, PA)."""
    if start == first or _pa_name_line(line) or _pa_procedure_name_line(line):
        return False
    above = text.rfind('\n', 0, start - 1) + 1
    if not _pa_bounded_above(text[above:start - 1].strip()):
        return False
    nxt, after = end + 1, ''
    for _ in range(_PA_NEXT_LINES):
        if nxt >= len(text):
            break
        stop = text.find('\n', nxt)
        stop = len(text) if stop < 0 else stop
        after = text[nxt:stop].strip()
        if after:
            break
        nxt = stop + 1
    return not after or _pa_content(after)


def _pa_unread_heading(text: str, pos: int) -> str:
    """The REAL unread heading line through which the section at ``pos`` reaches it: reading up from ``pos`` to the
    section's heading line, the nearest heading-like line (as sections.beyond_heading_reach reads one: _po_heading_like)
    that stands as a heading (_pa_real_heading); a list entry, a name or page line, a bare procedure name or the
    section's first line is read past as the section's own content. '' when none stands there, or when the nearest
    heading-like line names another occurrence's record (sections.ANOTHER_OCCURRENCE_HEAD: the document's own words date
    the passage); _PA_FAR, fail-closed, when the heading lies more than HEADING_REACH_LINES lines or HEADING_REACH_CHARS
    characters back and nothing nearer decides. Bounded: those lines and characters, three lines down per candidate."""
    section = gi_sections.layout(text).section_at(pos)
    if section.heading is None:
        return ''
    lo = text.find('\n', section.heading.end)  # the heading's own line (its label's answer) is never such a line
    if lo < 0 or lo >= pos:
        return ''
    first = lo + 1  # the section's first non-empty line under its heading
    while first < pos:
        nl = text.find('\n', first, pos)
        if nl < 0 or text[first:nl].strip():
            break
        first = nl + 1
    floor = max(lo, pos - gi_sections.HEADING_REACH_CHARS)
    end = text.rfind('\n', lo, pos)
    for _ in range(gi_sections.HEADING_REACH_LINES):
        if end <= floor:
            return _PA_FAR if floor > lo else ''
        nl = text.rfind('\n', floor, end)
        if nl < 0:
            return _PA_FAR  # a line begun before the characters read: fail-closed
        start = nl + 1
        line = text[start:end].strip()
        if _po_heading_like(line):
            if gi_sections.ANOTHER_OCCURRENCE_HEAD.search(line):
                return ''  # the passage stands under a line that names another occurrence itself (F6)
            if _pa_real_heading(text, start, end, first, line):
                return line
        end = start - 1
    return _PA_FAR


def _pa_reach(text: str, pos: int, what: str = 'it') -> str:
    """How the section at ``pos`` reaches it, said for a reading _section_only_routing_reading finds one-cause: from
    further below its heading than is read (HEADING_REACH_LINES lines or HEADING_REACH_CHARS characters: fail-closed),
    or else past the real unread heading line _pa_unread_heading finds, quoted whole. Words only; it decides nothing
    (GI round 4, PA; the line quoted since Wave 1 repair cycle 1)."""
    section = gi_sections.layout(text).section_at(pos)
    heading = section.heading.text.rstrip(':').strip() if section.heading is not None else ''
    named = f' \u201c{heading}\u201d' if heading else ''
    line = _pa_unread_heading(text, pos)
    if line == _PA_FAR:
        return (f'its section{named} reaches {what} from more than {gi_sections.HEADING_REACH_LINES} lines or '
                f'{gi_sections.HEADING_REACH_CHARS:,} characters below its heading, further than a heading is read')
    if line:
        return (f'its section{named} reaches {what} only past the line \u201c{line}\u201d, written as a heading, which '
                'the layout does not read as one')
    return (f'its section{named} reaches {what} only past a line written as a heading that the layout does not read '
            'as one')


def _pa_same_not_done(found: reconcile.Match, old: checks.StatusOutcome) -> bool:
    """Whether a documented service read as not performed has the same not-done status as the routing-era reading
    (_not_done_class): where _not_the_same_not_done still finds them apart, that is one cause, not two readings (GI
    round 4, PA), and the hold says the two read it the same way."""
    return found.reason == 'service_negative' and old.decisive is not None \
        and _not_done_class(found.service.status) == _not_done_class(old.decisive.status)


def _agreed_not_done(code: str, outcome: checks.StatusOutcome, service, text: str, day: Optional[date],
                     pages=()) -> bool:
    """Whether both readers read the act ``code`` accounts for with the same not-done status (_not_done_class) from the
    code's own deciding passage - only then does the routing-era reading exclude a code whose documented service
    documents no such act done (7c8 skeptic, sk:9: one reader's "negated" and the other's "planned" had counted as
    agreement). The documented acts of the code's kind in that passage decide, every one of them; with none there, what
    the documented-service reader reads in the passage does (_second_reading). A routing reading of the whole family,
    with no passage of the code's own, never agrees."""
    decisive = outcome.decisive
    if decisive is None or decisive.origin != 'evidence' or decisive.start is None or decisive.end is None:
        return False
    want = _not_done_class(decisive.status)
    here = _acts_in_passage(code, decisive, service)
    if here:
        return all(a.status in checks.NEGATIVE and _not_done_class(a.status) == want for a in here)
    return not _second_reading(outcome, text, day, pages)


def _acts_in_passage(code: str, decisive: checks.Reading, service) -> list:
    """The documented acts of a kind ``code`` accounts for that the deciding passage holds, each saying something
    either way: they decide the act path's agreement before anything else (_agreed_not_done)."""
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    return [a for a in service.acts if a.kind in kinds and not _says_nothing(a.status, a.cues)
            and any(decisive.start < ev.end and ev.start < decisive.end for ev in a.evidence)]


def _pa_one_cause_hold(found: reconcile.Match, outcome: checks.StatusOutcome, code: str, text: str,
                       day: Optional[date], pages=()) -> reconcile.Match:
    """The act path's hold (GI round 4, Wave 1 repair cycle 1, PA; refutation CTS-4) where the agreement an exclusion
    needs fails only because both readers read the code's own passage as not today by one section (_second_reading's
    one-cause words: no act of the code's kind in the passage decided it). The hold then says that, which is true of
    the document, in place of the inventory's words for a missing act ("... but no endosonographic examination is
    documented as done in it"), which the documented-service reader's act vocabulary makes false of a passage that
    states one (h4-05: "Echoendoscopic views were obtained ..."). Any other disagreement keeps its hold and its words;
    the bucket and the status are the same either way (held, never excluded)."""
    decisive = outcome.decisive
    if decisive is None or decisive.origin != 'evidence' or decisive.start is None or decisive.end is None \
            or _acts_in_passage(code, decisive, found.service):
        return found
    why = _second_reading(outcome, text, day, pages)
    if not why.startswith(_PA_ONE_CAUSE):
        return found
    return replace(found, state='uncertain', reason='readings_disagree',
                   question=f'Confirm whether {code} was performed on the date of service.',
                   detail=f'The routing-era reading of the passage it cites reads it as {decisive.status} only by its '
                          f'section: {checks.cite(decisive)}. The documented-service reader {why}. Held for the '
                          'reviewer, not excluded.')


def _not_the_same_not_done(found: reconcile.Match, old: checks.StatusOutcome, code: str, text: str = '') -> str:
    """Why a documented service or act read as not performed and a not-performed routing-era reading are not the same
    reading, or '' when they are: the same not-done status (_not_done_class: a denied act or service against a plan or a
    history is no agreement; 7c8 skeptic, sk:9). A denial read from another representation of the same item - a form's
    field line beside its printed box - is the same denial. A service read as not performed only by its section,
    against a routing-era reading of the code's own passage that its section alone makes not-today across a
    heading-like line the layout does not read (_section_only_routing_reading, on ``text``), is the same status from one
    cause: no agreement either (GI round 4, PA)."""
    decisive = old.decisive
    if decisive is None:
        return ''
    want = _not_done_class(decisive.status)
    if found.reason == 'service_negative':
        if _not_done_class(found.service.status) != want:
            return (f'The documented-service reader reads the {reconcile.service_label(found.service)} as '
                    f'{found.service.status}, the routing-era reading as {decisive.status}: not the same reading.')
        if _section_only_service_reading(found.service.cues) and _section_only_routing_reading(decisive, text):
            # GI round 4 (PA): both readers take the service's time from one section - the layout - so no agreement
            return (f'Both readers read the {reconcile.service_label(found.service)} as {found.service.status} only by '
                    f'the section it stands in: one cause, not two readings; '
                    f'{_pa_reach(text, decisive.start, "the passage")}.')
        return ''
    if found.reason == 'act_denied' and want != 'denied':
        profile = reconcile.catalogue.code_profile(code)
        kinds = set(profile.covers) if profile is not None else set()
        denied = [a for a in found.service.acts if a.kind in kinds and a.status in ('negated', 'cancelled')]
        return (f'The documented-service reader reads the act as {denied[0].status if denied else "denied"}, the '
                f'routing-era reading as {decisive.status}: not the same reading.')
    return ''


def _held_unless_agreed(outcome: checks.StatusOutcome, text: str, day: Optional[date],
                        legacy: str, pages=()) -> checks.StatusOutcome:
    """The routing-era not-performed outcome of a code whose family no documented service names, unless the
    documented-service reader reads the code's own deciding passage with the same not-done status (_second_reading):
    otherwise the code is held (uncertain) with that disagreement as its reading, never excluded ("No bleeding occurred
    after two rubber bands were placed ...", 46221 read "negated" by routing alone; "Hemorrhoid banding was performed and
    will be repeated in 6 weeks.", read "planned"). For an E/M code a reference to an earlier visit or service is no
    reading of this visit at all, so routing's "historical" never excludes it alone (7c8 skeptic, sk:8: "Last seen by Dr.
    Ramos on 2026-03-02." had excluded 99213)."""
    decisive = outcome.decisive
    if decisive is None or decisive.origin != 'evidence' or decisive.start is None or decisive.end is None:
        return outcome
    why = _second_reading(outcome, text, day, pages)
    if not why and legacy in checks.EM_FAMILIES and decisive.status == 'historical':
        why = 'reads no reading of this visit in it: a reference to an earlier visit or service never decides a current one'
    if not why:
        return outcome
    held = checks.Reading('uncertain', (f'uncertain: the routing-era reading reads it as {decisive.status}, but the '
                                        f'documented-service reader {why}',),
                          'evidence', decisive.passage, decisive.start, decisive.end)
    return checks.StatusOutcome('uncertain', held)


def _act_documented(code: str, service, inventory) -> bool:
    """Whether the inventory documents as done, or in conflict, an act ``code`` accounts for in ``service``. A base,
    E/M or uncatalogued code (or one of another family) accounts for the service itself, so it counts as documented."""
    profile = reconcile.catalogue.code_profile(code)
    if profile is None or profile.family != service.family or profile.base or 'em_visit' in profile.covers:
        return True
    kinds = set(profile.covers)
    if any(a.kind in kinds and a.status == 'performed' for a in service.acts):
        return True
    marking = bool(kinds & {'tattoo', 'injection'})  # one conflict for both, as reconcile.match reads it
    return inventory is not None and any(
        c.service == service.id and (c.subject in kinds or marking and c.subject in ('tattoo', 'injection'))
        for c in inventory.conflicts)


def _section_time(reading: checks.Reading) -> bool:
    """A passage read as planned or historical by its section alone: every cue is a section cue ("section: plan
    (Upcoming procedures)"), no clause of it states another time."""
    return reading.status in ('planned', 'historical') and bool(reading.cues) \
        and all(cue.startswith(checks.SECTION_CUE_PREFIX) for cue in reading.cues)


def _on_matched_act(reading: checks.Reading, found: reconcile.Match) -> bool:
    """Whether the passage overlaps the evidence of an act the code accounts for (the matched performed acts)."""
    return reading.start is not None and any(reading.start < ev.end and ev.start < reading.end
                                             for act in found.acts for ev in act.evidence)


def _undecided(old: checks.StatusOutcome, found: reconcile.Match, supported: Optional[reconcile.Support] = None,
               evidence: Sequence[EvidenceSpan] = ()) -> str:
    """The routing-era reading of the code's own passages that did not decide a status the documented service decided
    as performed (ARCHITECTURE 5.10): named in the status check, never dropped - as validation:4 names a hedge about
    another service in a warn, never a hold. '' when there is nothing to name: no such passage, a positive one, or a
    doubt that is only the routing-era reader's own (silence, a negation it could not resolve, or a reading no wording
    of a passage ``supported`` reads as showing the coded act decided - _unworded: a results row of the study's own
    report, refutation gi2 RC4, ho-08, had been named as "not about the documented manometry")."""
    if found.state not in checks.POSITIVE:
        return ''
    if old.state in checks.POSITIVE:
        other = old.contrary
        if other is None or other.origin != 'evidence' or other.status in checks.POSITIVE or _readers_own(other):
            return ''
        return f'Another linked passage reads as {other.status}: {checks.cite(other)}.'
    doubt = old.decisive
    if doubt is None or doubt.origin != 'evidence' or doubt.status in checks.POSITIVE or _readers_own(doubt):
        return ''
    if _unworded(doubt) and supported is not None and any(
            i < len(evidence) and (evidence[i].start, evidence[i].end) == (doubt.start, doubt.end)
            for i in supported.supporting):
        return ''
    why = ('it is about another time' if doubt.status in ('planned', 'historical')
           else f'it is not about the documented {reconcile.service_label(found.service)}')
    return f'A linked passage reads as {doubt.status}: {checks.cite(doubt)}; {why}, so it does not decide.'


def _unworded(reading: checks.Reading) -> bool:
    """A routing-era reading no wording of its passage decided: its section's default, held at most by routing's summary
    that no mention of the family documents it as performed (detect.UNESTABLISHED, a family-level reading the inventory
    already weighs, as _routing_agrees reads it)."""
    return bool(reading.cues) and all(c.startswith(checks.SECTION_CUE_PREFIX) or c == UNESTABLISHED for c in reading.cues)


def _readers_own(reading: checks.Reading) -> bool:
    """A doubt that is only the routing-era reader's own: silence, or a negation it could not resolve."""
    if checks.silent(reading.status, reading.cues):
        return True
    doubts = [c for c in reading.cues if c.startswith('uncertain:')]
    return reading.status == 'uncertain' and bool(doubts) and all(c.startswith(DOUBT_PREFIX) for c in doubts)


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


def _states_unread_act(reading: checks.Reading, found: reconcile.Match, code: str, text: str) -> bool:
    """Whether the code's own passage can stand for an act the inventory does not read at all: it names the act the
    code accounts for, the inventory reads no act of that kind in the service (an act it reads as uncertain, planned or
    past is read, and never released by the routing-era reading), and none of the service's acts claims the passage. A
    statement of the service itself ("The colonoscope was advanced to the cecum.") never stands for a biopsy."""
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    if not kinds or any(a.kind in kinds for a in found.service.acts):
        return False
    if any(reading.start < t.end and t.start < reading.end for a in found.service.acts for t in a.evidence):
        return False
    passage = text[reading.start:reading.end]
    return any(kind in kinds and pattern.search(passage) for kind, pattern in gi_services.ACTS)


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


def _about(reading: checks.Reading, found: reconcile.Match, code: str, text: str,
           routing: Optional[RoutingResult] = None, inventory=None) -> bool:
    """Whether a passage the code cites is about the matched service: it overlaps the service's evidence or any of
    its acts' evidence, or it names the service or the act the code accounts for. For an office visit, the visit's own
    documentation routing reads (visit statement, chief complaint, MDM, time) is about the visit whatever its reading:
    the service's evidence keeps only the statements read as performed, so a hedged one ("Total time: approximately 30
    minutes?") would otherwise read as about nothing, and its doubt would be released.

    A bare status statement ("\u2612 Not performed", "Physical exam and anoscopy were completed?") is the matched
    procedure's when it lies in the service's own report, or when it is about no other service at all (_other_named):
    the routing-era reader's fail-closed rule for a procedure code (validation:4: a doubt that names no other service is
    the code's own). A service whose report has no title is scoped by its own passages, so a status line after its last
    passage lay outside it and its hold was released. An office visit keeps validation:4's own rule (the visit's
    documentation, above): a status statement about procedures is not about the visit."""
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
    if service.family == 'gi.office_em' and routing is not None and any(
            reading.start < m.span.end and m.span.start < reading.end
            for f in routing.findings if f.family == 'gi.office_em' for m in f.mentions):
        return True  # the visit's own E/M documentation, whatever routing read it as (validation:4, engine._other_service)
    # a bare status statement inside the service's own report ("☒ Not performed", "Aborted ..."), or, for a procedure,
    # about no other service at all
    if _status_signal(reading, passage) and (
            (service.scope_start <= reading.start and reading.end <= service.scope_end)
            or (service.family not in checks.EM_FAMILIES and inventory is not None
                and not _other_named(reading, found, passage, inventory, routing))):
        return True
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    return any(kind in kinds and pattern.search(passage) for kind, pattern in gi_services.ACTS)


def _status_signal(reading: checks.Reading, passage: str) -> bool:
    """Whether a passage states a status of its own: a status word ("completed", "not performed", "aborted"), a hedge
    ("?", "unclear", "possible"), or a routing-era reading from a check-box or status-option row ("Yes \u2610 No
    \u2612", "\u2612 No", "Carried out \u2610 Not carried out \u2612") - structural signals, so the hold no longer depends on
    the status word list alone (triage round 2 skeptic: "were carried out?" and "unclear if adequate" were released).
    A hedge on what was seen ("A 5 mm cecal lesion was seen?") doubts a finding, not a status (interpretation 9), and a
    fragment with none of them ("No gastric") still decides nothing."""
    if STATUS_WORDS.search(passage):
        return True
    if gi_services.HEDGE_WORDS.search(passage) and not gi_services.OBSERVED.search(passage):
        return True
    return any('box' in cue.lower() for cue in reading.cues)


def _other_named(reading: checks.Reading, found: reconcile.Match, passage: str, inventory,
                 routing: Optional[RoutingResult]) -> bool:
    """Whether a passage is about a service other than the matched one: it lies in another documented service's report
    or passages (_elsewhere), names another family's service, or overlaps a routed mention of another family (the
    validation:4 index, _VAL_family_index, which never counts a part routing holds as named together with a visit:
    box2:E, hold-only). Bounded: one pass over the inventory's services, one search per service pattern, and two
    bisections per routed family."""
    own = {found.service.family, legacy_family(found.service.family)}
    for service in inventory.services:
        if service.id != found.service.id and service.scope_start <= reading.start \
                and reading.end <= service.scope_end:
            return True
    if _elsewhere(reading, found, inventory):
        return True
    if any(family not in own and pattern.search(passage) for family, _, pattern in gi_services.SERVICES):
        return True
    if routing is None:
        return False
    index = _VAL_family_index(routing)
    return any(family not in own and overlaps(reading.start, reading.end) for family, overlaps in index.items())


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
# The sections in which a report states what was done, found or concluded (studio.gi.sections): a passage of a study's
# own report there - its results under the technique, its interpretation - shows the study (reconcile._study_named). A
# header line, a signature or any other line no such section heads does not (refutation gi2 RC4).
OWN_REPORT_SECTIONS = ('procedure', 'technique', 'findings', 'impression', 'assessment')


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
    with no fee-schedule row for the date counts (fail-closed): the E/M is then held. The row is the one a reader reads
    (read_pfs): whether a breath test is a procedure does not wait on a closing charge block's question (the seventh
    refutation's parity-7-2 and pipe7-1), so no same-day E/M question is raised for it."""
    if s.family in checks.EM_FAMILIES or s.evaluation is None:
        return False
    if s.profile.procedure:
        return True
    pfs = s.evaluation.read_pfs
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


def _keyed(selections: Sequence[_Selection], encounter: _Encounter,
           harness: Optional['_Harness'] = None) -> tuple[ProposalAssessment, ...]:
    """Selected-bucket proposals first, then excluded; keys count within each bucket in provider order. ``harness``: the
    independent participants' merge, whose contradiction checks a decidable proposal carries (HARNESS.md 5); None adds
    nothing."""
    selected, excluded = [], []
    for selection in selections:
        bucket, prefix = (excluded, 'exc') if selection.excluded else (selected, 'sel')
        extra = harness.disagreements(selection) if harness is not None else ()
        bucket.append(_proposal(selection, f'{prefix}:{len(bucket)}', encounter, extra))
    return tuple(selected + excluded)


def _proposal(s: _Selection, key: str, enc: _Encounter, extra: Sequence[Check] = ()) -> ProposalAssessment:
    """``extra``: checks added after every rule's own (an independent participant's contradiction, which never changes
    the status); like every check, they are part of the fingerprint."""
    if s.evaluation is None:
        return _excluded_early(s, key, enc.provider)
    finding, outcome, ref = s.evaluation.finding, s.evaluation.outcome, s.evaluation.reference
    profile, name, day = s.profile, checks.service_name(s.profile, s.code), enc.date_state.value
    release = enc.pfs_source.release if enc.pfs_source else ''
    m, supported = s.evaluation.match, s.evaluation.support
    status_found = checks.status_check(outcome, name) if m is None else _service_status_check(m, s.evaluation.note)
    found: list[Check] = [checks.scope_check(s.code_kind, s.scope_reason),
                          *checks.evidence_checks(s.evidence, s.dropped),
                          checks.routing_check(profile, finding), status_found]
    if supported is not None:
        found.append(reconcile.support_check(supported))
    if s.evaluation.placed is not None:
        found.append(s.evaluation.placed)
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
    # GI round 4 (E1): the matched documented service, whose own endpoint statement may supply the extent routing lacks
    states = checks.required_fact_states(profile, finding, enc.context, service=m.service if m is not None else None)
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
    found += extra
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
                                                         if s.origin == 'second_review'
                                                         else _participant_names(s.proposers)
                                                         if s.origin == 'participant' else enc.provider),
                                               units=s.units, evidence_count=len(s.evidence),
                                               profile=profile, detected=finding is not None, outcome=outcome,
                                               facts=_documented_facts(finding, states, m),
                                               entered=_entered_facts(states)),
        checks=tuple(found), modifier_considerations=tuple(considerations), units=s.units,
        fingerprint=_fingerprint(s.code, s.family, profile.version, s.evidence, found,
                                 _relevant_context(s.family, enc, bool(pctc)), s.units, status),
        clarifications=tuple(clarifications), support=_support_json(m, supported, s.origin))


def _service_status_check(m: reconcile.Match, note: str = '') -> Check:
    status = {'performed': 'pass', 'incomplete': 'pass', 'not_performed': 'fail', 'uncertain': 'warn'}[m.state]
    if m.reason == 'profile_unknown' and m.state != 'uncertain':
        status = 'warn'
    detail = m.detail
    if note:
        # A passage the code cites that the routing-era reader reads otherwise, and that did not decide (_undecided):
        # named in a warn, never a hold.
        status, detail = ('warn' if status == 'pass' else status), f'{detail} {note}'
    return Check('service.status', 'Service performed on this encounter', status, detail, reconcile.INVENTORY_SOURCE)


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
    if m is None and supported is None:
        return {'origin': origin} if origin != 'primary' else {}
    if m is None:
        # No documented service of the code's family: how its passages relate to the act it accounts for, documented in
        # another family's service (reconcile.elsewhere) - never a documented service or a match of its own.
        return {'origin': origin, 'status': supported.status, 'supporting': list(supported.supporting),
                'unrelated': list(supported.unrelated), 'detail_support': supported.detail,
                'source': [{'start': sp.start, 'end': sp.end, 'text': sp.text} for sp in supported.source]}
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


def _alternative(index: int, item: ProviderCode, text: str, pages, provider: str,
                 not_added: str = '') -> ProposalAssessment:
    """An informational code. ``not_added``: why a code the bounded second review selected is not added as a proposal
    (it is worded as selected, never as a candidate the provider did not select)."""
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
        exclusion_reason=rationale.alternative_note(item.role, parent, unlisted_parent=unlisted_parent,
                                                    not_added=not_added),
        reinstatable=False, provider_display=item.display, evidence=kept,
        rationale=rationale.alternative_rationale(provider=provider, role=item.role, parent_code=parent,
                                                  evidence_count=len(kept), unlisted_parent=unlisted_parent,
                                                  not_added=not_added),
        checks=found, modifier_considerations=(), units=1,
        fingerprint=_fingerprint(item.code, family, profile_version, kept, found, {}, 1, 'informational'))


def _billing(context: Mapping[str, Fact]) -> str:
    """The billing context as stored, for the PC/TC consideration: a conflict is worded as one (a member's value against
    the document's asks context.is_member_conflict) and a member's value as entered - never "not documented" for a
    conflict, nor a member's value as a documented one (ec5, the context-5 class inside the engine)."""
    from studio.gi.context import is_member_conflict
    fact = context.get('billing_context')
    if fact is not None and fact.origin == 'conflict':
        return ('in conflict: member-entered encounter metadata differs from the document' if is_member_conflict(fact)
                else 'conflicting documented values')
    if checks.is_member_entered(fact) and checks.is_documented(fact):
        return f'{fact.value}, entered by a workspace member as encounter metadata'
    return str(fact.value) if fact is not None and checks.is_documented(fact) else 'not documented'


def _documented_facts(finding: Optional[FamilyFinding], states, m=None) -> list[tuple[str, str]]:
    # A member-entered value is encounter metadata, never a documented fact: it is listed apart (_entered_facts) -
    # refutation r1, context-7: the exported rationale said "Documented facts: place of service = office" of it.
    context = [(state.name, str(state.fact.value)) for state in states
               if not state.problem and state.fact is not None and state.name in CONTEXT_FACTS
               and not checks.is_member_entered(state.fact)]
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
        return list(dict.fromkeys(facts + context))
    facts = [(f.name, str(f.value)) for f in (finding.facts if finding else ())
             if checks.is_documented(f) and not checks.is_member_entered(f)]
    return list(dict.fromkeys(facts + context))


def _entered_facts(states) -> list[tuple[str, str]]:
    """The facts a workspace member supplied as encounter metadata (origin 'user'), named as such in the rationale."""
    return list(dict.fromkeys((state.name, str(state.fact.value)) for state in states
                              if not state.problem and checks.is_member_entered(state.fact)))


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

def reviewed_completeness(services: Optional[dict], completeness: Optional[dict], selected: Sequence[tuple[str, str]],
                          reinstated: Sequence[tuple[str, str]], read: Sequence[str]) -> Optional[dict]:
    """The documented-service reconciliation the assessment recorded (``completeness``) as the review leaves it: the
    excluded codes a reviewer reinstated and has not rejected (``reinstated``: (code, family)) counted as selected ones
    beside the assessment's own selected codes (``selected``), by the reconciliation's own rules over the documented
    services it recorded (``services``) - what each covers, includes and leaves unresolved, and the coding completeness
    that follows. ``read``: the documented services the proposals' own readings matched (their support), as the
    assessment counted services not established as performed. A reinstated code is one a reviewer decides like a
    selected one, so every statement of which code accounts for a documented service - the documented services, the
    unresolved ones, coding completeness, the second review's items - counts it (refutation P2FR, EUS-SECOND: an EGD-with-
    EUS code excluded on a misreading, reinstated and approved, read "no selected code of that service includes this
    examination", and the EUS "has no supported proposal", with coding incomplete and a second review offered for it).
    Rejections stay as the reports state them (refutation r1, report-6). ``completeness`` itself when nothing is
    reinstated, or when the assessment recorded no reconciliation (none, or a reading that was inconsistent and decided
    nothing). Pure: the second review's mark is carried from the item the assessment recorded, never added."""
    if not reinstated or not completeness or not services or not isinstance(completeness.get('covered'), dict) \
            or completeness.get('inventory_problems'):
        return completeness
    from studio.types import from_jsonable
    inventory = from_jsonable(gi_services.ServiceInventory, services)
    stored = [u for u in completeness.get('unresolved_items') or [] if isinstance(u, dict)]
    # the assessment's own procedure-day reading: it listed an office visit only on a date with no procedure it saw; a
    # reinstated procedural code makes the date a procedure day, as the engine reads a selected one (_Encounter)
    procedure_day = (not any(u.get('family') == 'gi.office_em' and u.get('reason') == 'no_proposal' for u in stored)
                     or any(PROFILES[family].procedure for _, family in reinstated if family in PROFILES))
    unresolved, bundled, covered = reconcile.reconcile(inventory, [*selected, *reinstated], procedure_day=procedure_day)
    marks = {(u.get('service'), u.get('act'), u.get('reason')): bool(u.get('second_review')) for u in stored}
    not_listed = reconcile.uncounted(inventory, unresolved, covered)
    reasons = [str(r) for r in completeness.get('reasons') or []]
    asked = next((int(m.group()) for r in reasons if 'open question' in r for m in [re.match(r'\d+', r)] if m), 0)
    fresh = reconcile.completeness(
        inventory, unresolved, asked, 'the provider response was not available' not in reasons,
        unestablished=sum(1 for s in inventory.services if s.status == 'uncertain' and s.id not in set(read)),
        not_listed=not_listed)
    # An independent participant's performed service the documented-service reading does not read (HARNESS.md 5) is no
    # reconciliation of codes, so no reinstatement answers it: its reason stays. None recorded, nothing is added.
    noted = [str(item['reason']) for item in completeness.get('participant_services') or []
             if isinstance(item, dict) and item.get('reason')]
    if noted:
        fresh = {**fresh, **_incomplete(list(fresh['reasons']) + noted)}
    return {**completeness, **fresh,
            'unresolved_items': [_jsonable_unresolved(u, marks.get((u.service, u.act, u.reason), False))
                                 for u in unresolved],
            'bundled': [{'service': b.service, 'act': b.act, 'label': b.label, 'why': b.why} for b in bundled],
            'not_listed': [{'service': s.id, 'family': s.family, 'label': reconcile.uncounted_label(s)}
                           for s in not_listed],
            'covered': covered, 'included_by': _included_by(inventory, covered),
            'reinstated': list(dict.fromkeys(code for code, _ in reinstated))}


def _included_by(inventory: Optional[gi_services.ServiceInventory], covered: Mapping[str, Sequence[str]]) -> dict:
    """{service id: the selected, non-excluded codes of the service it is read as part of that include its examination}
    for every service done today read as part of another (an EGD inside an EUS of the upper GI tract), by the
    reconciliation's own test (reconcile.includes_through over ``covered``, the codes it reconciled). Recorded with the
    assessment (completeness.included_by), so the documented services are worded from the inclusion rule itself, never
    from whether the reconciliation listed the service (refutation P2RA, EUS lens 1: an EGD with its own code beside an
    EUS whose selected code includes no upper endoscopy read "included in S2: that service's code includes this
    examination", and on the page "... so no code of its own is asked", beside the approved code of its own)."""
    if inventory is None:
        return {}
    out = {}
    for service in inventory.services:
        if service.status in checks.POSITIVE and service.included_in:
            including = inventory.service(service.included_in)
            family = including.family if including is not None else ''
            out[service.id] = [code for code in covered.get(service.included_in, ())
                               if reconcile.includes_through(inventory, service, code, family)]
    return out


def _accounted_elsewhere(inventory: Optional[gi_services.ServiceInventory], included_by: Mapping[str, Sequence[str]],
                         routing: Optional[RoutingResult] = None) -> dict:
    """{routing family: the labels services.unproposed names it by} for each family routing reads of which the
    documented-service reconciliation accounts for a service done today with ANOTHER service's selected code: the
    service is included in another one (an EGD inside an EUS of the upper GI tract) of whose selected, non-excluded
    codes one includes its examination (``included_by``, _included_by: an EGD-with-EUS code). Any other selected code
    of that service - a sigmoidoscopy, colonoscopy, stoma or esophagoscopy EUS code - includes no upper endoscopy, so the
    family is named (refutation p2, reports2:0: any selected code of the EUS had accounted for the EGD).

    Services are counted under the family routing reads them under (legacy_family): routing reads a push enteroscopy
    under the upper GI family gi-profiles@3 carved it out of. () when every service done today that routing reads under
    the family is so accounted for: it is not named. Otherwise the labels of the services that are not: what is missed,
    never the examination the code includes (refutation P2RA, EUS lens 0: an EGD inside an EUS whose EGD-with-EUS code
    was selected made the whole upper GI routing family read as accounted for, so a push enteroscopy beside it with no
    proposal passed as "Every performed service that routing detected in the document has a selected proposal" - which
    the installed revision named).

    Keyed on ``routing``'s own reading too, since the check speaks for what routing detected: every mention routing
    reads as performed under the family is accounted for only when the service it names - read by the inventory's own
    service names (gi_services.SERVICES, its first match) - is a service done today that such a code includes; any
    other is named by that service's label. A service the inventory does not read as done today is never counted as
    accounted for (refutation P2FR, EUS-SECOND 0: a push enteroscopy routing read as performed under the upper GI family,
    which the inventory held as uncertain, was not among the services counted, so the family again read as accounted
    for). A mention routing itself does not read as performed names nothing: never "documented as performed"."""
    if inventory is None:
        return {}
    done = [s for s in inventory.services if s.status in checks.POSITIVE]
    accounted = {}
    for family in dict.fromkeys(legacy_family(s.family) for s in done):
        under = [s for s in done if legacy_family(s.family) == family]
        left = [s.family for s in under if not included_by.get(s.id)]
        if len(left) < len(under):
            included = {s.family for s in under if included_by.get(s.id)}
            finding = routing.finding(family) if routing is not None else None
            for mention in finding.mentions if finding is not None else ():
                if mention.status in checks.POSITIVE:
                    named = next((f for f, _, pattern in gi_services.SERVICES if pattern.search(mention.span.text)),
                                 family)
                    if named not in included:
                        left.append(named)
            accounted[family] = tuple(dict.fromkeys(PROFILES[f].label if f in PROFILES else f for f in left))
    return accounted


def _missed(routing: RoutingResult, selections: Sequence[_Selection], procedure_day: bool,
            accounted: Optional[Mapping[str, tuple[str, ...]]] = None) -> tuple[list[str], bool]:
    """(labels of performed, profiled families - and other GI services routing detected - without a selected
    proposal, whether an E/M was not counted).

    On a procedure day an unproposed E/M is never reported as missed: that would push toward adding an office
    visit because a procedure report contains history or examination text. Other GI services are read mention by
    mention (validation:5): a procedure done today is covered only by a selected gi.other code whose passage speaks for
    it (_cited), and when another gi.other code is selected the uncovered procedures are named.

    Routing still reads the families gi-profiles@3 carved out under the family they came from (a manometry or a capsule
    study is a gi.other mention, a push enteroscopy an upper GI one), so a selected code of a carved-out family counts
    for its routing-era family here as well (LEGACY_FAMILIES), as it does in _cited.

    ``accounted``: {family: labels} of the families the documented-service reconciliation accounts for with another
    service's selected code (_accounted_elsewhere): one with no labels is not named, one with labels is named by them -
    what of it is left. Every other family is named whatever the reconciliation also lists (refutation p2, reports2:0:
    skipping every family the documented-service reading read as done let the check pass with "Every performed service
    that routing detected in the document has a selected proposal" beside a detected EGD, or a colonoscopy, that had
    none - which the installed revision named).
    """
    accounted = accounted or {}
    proposed = {family for s in selections if not s.excluded for family in (s.family, legacy_family(s.family))}
    unproposed, named = [], {}
    for f in routing.findings:
        if not (f.family in PROFILES and (PROFILES[f.family].supported or f.family == OTHER_GI) and _done_today(f)):
            continue
        if f.family in accounted and f.family != OTHER_GI:
            if not accounted[f.family]:
                continue  # another service's selected code includes it (an EGD inside an EUS)
            # only some of it is (refutation P2RA, EUS lens 0): what is left is named, never the included examination
            named[f.family] = accounted[f.family]
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
    labels = []
    for family in unproposed:
        if not (procedure_day and family in checks.EM_FAMILIES):
            name = named.get(family, PROFILES[family].label)
            labels += list(name) if isinstance(name, tuple) else [name]
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


# --- the independent participants (HARNESS.md 5) ---------------------------------------------------------------------

PRIMARY = 'corti'  # the proposal provider among the proposers: the API names the three corti, astra and fable
# The participants' service families (studio.types.PARTICIPANT_FAMILIES) as CPT Studio's own (studio.gi.profiles). A
# service a participant reads as performed is one the documented-service reading does not read when the inventory reads
# no performed service of any family it maps to. 'other_gi' maps to every profiled family outside the six the
# instructions name and to gi.other, which the inventory never reads; 'not_gi' is outside the GI scope this release
# codes, so it maps to none and never counts.
PARTICIPANT_FAMILY_MAP = {
    'office_em': ('gi.office_em',), 'egd': ('gi.egd',), 'colonoscopy': ('gi.colonoscopy',),
    'flexible_sigmoidoscopy': ('gi.flex_sig',), 'eus': ('gi.eus',), 'ercp': ('gi.ercp',),
    'other_gi': ('gi.enteroscopy', 'gi.capsule', 'gi.motility', 'gi.reflux', 'gi.anorectal', 'gi.feeding_tube',
                 OTHER_GI),
    'not_gi': (),
}
PARTICIPANT_SERVICE_LABELS = {'office_em': 'office / outpatient visit', 'egd': 'upper endoscopy',
                              'colonoscopy': 'colonoscopy', 'flexible_sigmoidoscopy': 'flexible sigmoidoscopy',
                              'eus': 'endoscopic ultrasound', 'ercp': 'ERCP', 'other_gi': 'other GI service'}
NOT_PERFORMED_HERE = 'not_performed_at_this_encounter'
NOT_CODED_WORDS = {NOT_PERFORMED_HERE: 'it reads the service as not performed at this encounter',
                   'included_in_another_code': 'it reads the service as included in another code',
                   'insufficient_documentation': 'it reads the documentation as insufficient to code it',
                   'outside_gi_scope': 'it reads the service as outside the GI scope',
                   'other': 'for another reason'}
# Why a participant did not read the document (studio.types.PARTICIPANT_STATES other than 'read').
PARTICIPANT_STATE_WORDS = {
    'refused': 'it answered, and its answer was not used',
    'failed': 'its request failed',
    'unknown': 'its request was sent and its outcome is unknown; a workspace member must reconcile it',
    'not_sent': 'its request was not sent',
    'blocked': 'its request was not sent while another run\'s outcome is unknown',
    'not_configured': 'it is not configured on this installation',
    'not_run': 'it has not run for this revision',
}
UNLOCATED = ('none of its quotes was found verbatim in the document text, and a quote that is not found is never '
             'evidence')
LISTED_IN_SUMMARY = 8  # codes a participant's summary sentence names; the rest are counted
MODIFIER_SHAPE = re.compile(r'[A-Z0-9]{2}', re.A)  # a modifier as a participant may state one; anything else is counted
OPEN_QUESTION = 'open question'  # the words review.coding_completeness drops a completeness reason for


def participant_codes(participants: Sequence[ParticipantInput]) -> tuple[str, ...]:
    """The codes an assessment with ``participants`` may look up beside the proposal provider's (the assess stage
    prefetches the union for the bounded child, which has no database): every listable code a used reading proposes
    with at least one located quote. A superset of what _Harness.merge reads; never a code it would miss."""
    return tuple(sorted({item.code for p in participants if p.state == 'read' and p.reading is not None
                         and not p.reading.refused for item in p.reading.codes
                         if isinstance(item.code, str) and 0 < len(item.code) <= MAX_LISTED_CODE
                         and any(q.spans for q in item.evidence)}))


def _participant_names(names: Sequence[str]) -> str:
    """'Astra (independent participant)', 'Astra and Fable (independent participants)'."""
    return (checks._join([PARTICIPANT_LABELS.get(name, name) for name in names])
            + (' (independent participant)' if len(names) == 1 else ' (independent participants)'))


def _reason_words(reason: str) -> str:
    """A not-coded entry's enumerated reason in words (a reason outside the enumeration, which the reading's schema
    refuses, reads as 'another reason': never the participant's own wording)."""
    return NOT_CODED_WORDS.get(reason, NOT_CODED_WORDS['other'])


def _incomplete(reasons: Sequence[str]) -> dict:
    """Coding completeness as reconcile.completeness words an incomplete one, for ``reasons``."""
    return {'state': 'incomplete', 'reasons': list(reasons),
            'statement': 'Coding for this encounter is incomplete: ' + '; '.join(reasons) + '.'}


@dataclass(frozen=True)
class _Said:
    """One participant's entry about one code, with its quotes' spans as CPT Studio verified them: ``good`` are exact
    slices of the revision text (each once, with its page), ``bad`` every span that is not (never evidence)."""
    entry: object  # ParticipantCode or ParticipantNotCoded
    good: tuple[EvidenceSpan, ...]
    bad: tuple[EvidenceSpan, ...] = ()


class _Harness:
    """The independent participants' merge (HARNESS.md 5), made once per assessment from the inputs of the configured
    participants, in stage order. Only what CPT Studio itself verified is used: a quote is evidence only where its span
    is an exact slice of the revision text, checked here again and never assumed (I7), and nothing a participant wrote
    in its own words reaches the result - only its codes, its enumerated reasons and the document's own passages.

    - A code a decidable proposal carries (the proposal provider's or the bounded second review's: one a reviewer can
      decide, as _second_review reads it) stays that proposal, changed only by the record of who proposed it
      (support['proposed_by'], from 'corti', and support['participants'], each participant's position).
    - Any other code is read by the proposal provider's own path (_select, then _proposal), once, from the quotes of
      every participant that quoted it verbatim, as one selection of one unit (I2). In scope with exact evidence it is a
      proposal of its own (support['origin'] 'participant'); otherwise an alternative saying why ('altp:<n>'). A
      participant's stated units, modifiers and confidence are recorded in its position and never used.
    - Agreement never promotes (I3): a second proposer adds its quotes to the code's evidence and its name to the
      record; with the same quotes it changes nothing else - not the bucket, status, checks, units or fingerprint (only
      the rationale's first sentence, which names the proposers).
    - A participant that advises not to code a code because its service was not performed at this encounter, quoting
      the document, adds a warn to each decidable proposal of that code (participants.disagree); the status stays the
      readers' own.
    - A service a participant reads as performed, quoting the document, of a kind of which the documented-service
      reading reads no performed service, makes coding completeness incomplete (participants.services).
    - Its questions never become clarifications: participants.summary counts them, as notes."""

    def __init__(self, participants: Sequence[ParticipantInput], text: str, pages):
        order = {name: index for index, name in enumerate(PARTICIPANT_ORDER)}
        seen: set[str] = set()
        for p in participants:
            if not isinstance(p, ParticipantInput):
                raise ValueError(f'A participant input must be a ParticipantInput, not {type(p).__name__}.')
            if p.provider not in order:
                raise ValueError(f'Unknown participant {p.provider!r}.')
            if p.provider in seen:
                raise ValueError(f'Participant {p.provider!r} is given twice.')
            seen.add(p.provider)
            if p.state not in PARTICIPANT_STATES:
                raise ValueError(f'Unknown participant state {p.state!r}.')
            if (p.state == 'read') != (p.reading is not None):
                raise ValueError(f'Participant {p.provider!r}: a reading is given exactly when its state is read.')
            if p.reading is not None and (p.reading.provider != p.provider or p.reading.refused):
                raise ValueError(f'Participant {p.provider!r}: its reading is another participant\'s or was refused.')
        self.inputs = tuple(sorted(participants, key=lambda p: order[p.provider]))
        self.text, self.pages = text, pages
        self.readings = {p.provider: p.reading for p in self.inputs if p.state == 'read'}
        self.answered = bool(self.readings)
        # code -> participant -> its entries, in first appearance (stage order, then each reading's own order)
        self.codes: dict[str, dict[str, list[_Said]]] = {}
        self.advised: dict[str, dict[str, list[_Said]]] = {}
        self.unlisted: dict[str, int] = {}
        for name, reading in self.readings.items():
            for item in reading.codes:
                if not (isinstance(item.code, str) and 0 < len(item.code) <= MAX_LISTED_CODE):
                    self.unlisted[name] = self.unlisted.get(name, 0) + 1
                    continue
                self.codes.setdefault(item.code, {}).setdefault(name, []).append(self._said(item))
            for item in reading.not_coded:
                if isinstance(item.code, str) and 0 < len(item.code) <= MAX_LISTED_CODE:
                    self.advised.setdefault(item.code, {}).setdefault(name, []).append(self._said(item))
        self._missing: Optional[list[dict]] = None

    def _said(self, entry) -> _Said:
        good, bad = self._partition(entry.evidence)
        return _Said(entry, good, bad)

    def _partition(self, quotes: Sequence[LocatedQuote]) -> tuple[tuple[EvidenceSpan, ...], tuple[EvidenceSpan, ...]]:
        spans = [span for quote in quotes for span in quote.spans]
        good, _ = checks.exact_evidence(spans, self.text, self.pages)
        return good, tuple(span for span in spans if checks._evidence_problem(span, self.text))

    # --- one code ---------------------------------------------------------------------------------------------------

    def proposers(self, code: str) -> tuple[str, ...]:
        """The participants that proposed ``code`` quoting the document verbatim, in stage order."""
        return tuple(name for name, said in self.codes.get(code, {}).items() if any(s.good for s in said))

    def _good(self, code: str, names: Sequence[str]) -> tuple[EvidenceSpan, ...]:
        """The exact spans ``names`` quoted for ``code``, each once, in the order of the document: the same quotes give
        the same evidence whoever gave them and in whatever order (I3)."""
        found = {}
        for name in names:
            for said in self.codes.get(code, {}).get(name, ()):
                for span in said.good:
                    found.setdefault((span.start, span.end), span)
        return tuple(found[key] for key in sorted(found))

    def _evidence(self, code: str, names: Sequence[str]) -> tuple[EvidenceSpan, ...]:
        """What _select reads for ``code``: the exact spans of its proposers, then every span of theirs that is not
        exact, which _select drops and its evidence check names."""
        return self._good(code, names) + tuple(span for name in names for said in self.codes[code][name]
                                               for span in said.bad)

    def merge(self, selections: list, routing: RoutingResult, reference: ReferenceLookup, day: Optional[date],
              inventory, *, dated: bool) -> tuple[list, tuple[ProposalAssessment, ...]]:
        """(``selections`` with the participants' own proposals after them, the participants' alternatives)."""
        have = {s.code for s in selections if s.evaluation is not None}  # decidable, as _second_review reads it
        added, listed = [], []
        for code, by in self.codes.items():
            if code in have:
                continue  # recorded on that proposal (recorded): nothing else about it changes
            proposers = self.proposers(code)
            _, scope_reason = checks.code_scope(code)
            if scope_reason:
                why = scope_reason
            elif not proposers:
                why = UNLOCATED
            else:
                group = [ProviderCode('selected', 'participant', code, '', self._evidence(code, proposers))]
                candidate = _select(group, self.text, self.pages, routing, reference, day, inventory, dated=dated)
                if candidate.evaluation is not None:
                    added.append(replace(candidate, origin='participant', proposers=proposers))
                    continue
                why = candidate.scope_reason or NO_EVIDENCE
            listed.append(self._alternative(len(listed), code, tuple(by), why))
        return list(selections) + added, tuple(listed)

    def _alternative(self, index: int, code: str, names: tuple[str, ...], why: str) -> ProposalAssessment:
        """A participant's code that is not a proposal, saying why: informational, never approvable."""
        code_kind, scope_reason = checks.code_scope(code)
        kept = self._good(code, names)
        family = family_for_code(code)
        found = (checks.scope_check(code_kind, scope_reason),)
        profile_version = PROFILES[family].version
        who, why = _participant_names(names), why.rstrip('.')
        return ProposalAssessment(
            key=f'altp:{index}', bucket='alternative', code=code, code_kind=code_kind, family=family,
            profile_version=profile_version, status='informational',
            exclusion_reason=f'Proposed by {who}, but not added as a proposal: {why}. Alternatives cannot be approved.',
            reinstatable=False, provider_display='', evidence=kept,
            rationale=(f'Proposed by {who}; not added as a proposal: {why}. Informational only.'
                       + (f' {checks.plural(len(kept), "exact evidence passage")}.' if kept else '')),
            checks=found, modifier_considerations=(), units=1,
            fingerprint=_fingerprint(code, family, profile_version, kept, found, {}, 1, 'informational'),
            support={'origin': 'participant'})

    def disagreements(self, s: _Selection) -> tuple[Check, ...]:
        """The participants.disagree warn of a decidable proposal: each participant that advises not to code its code
        because its service was not performed at this encounter, quoting the document."""
        if s.evaluation is None:
            return ()
        items = []
        for name, said in self.advised.get(s.code, {}).items():
            quoted = next((x for x in said if x.entry.reason == NOT_PERFORMED_HERE and x.good), None)
            if quoted is not None:
                items.append((PARTICIPANT_LABELS[name], quoted.good[0].text))
        return (checks.participants_disagree_check(s.code, items),) if items else ()

    # --- the record ---------------------------------------------------------------------------------------------------

    def recorded(self, proposals: Sequence[ProposalAssessment]) -> tuple[ProposalAssessment, ...]:
        """Every proposal with who proposed it (support['proposed_by']) and each participant's position on its code
        (support['participants']). Outside the fingerprint: who proposed a code never changes its decision."""
        return tuple(replace(p, support={**(p.support or {}), 'proposed_by': self._proposed_by(p),
                                         'participants': self.positions(p.code)}) for p in proposals)

    def _proposed_by(self, p: ProposalAssessment) -> list[str]:
        origin = (p.support or {}).get('origin', 'primary')
        if p.bucket == 'alternative':
            # an alternative is proposed by no one; a participant's lists every participant that gave the code
            return list(self.codes.get(p.code, {})) if origin == 'participant' else []
        if origin == 'participant':
            return list(self.proposers(p.code))
        if p.bucket == 'selected' or p.reinstatable:  # decidable: the participants' proposals were merged into it
            return [PRIMARY, *self.proposers(p.code)]
        return [PRIMARY]  # excluded for scope or evidence: a participant's code of its own stands apart from it

    def positions(self, code: str) -> dict:
        """{participant: {'position', 'detail', 'quote'}} for every configured participant: 'proposed', 'not_proposed',
        'advised_not_to_code' or 'not_run'. The quote is a passage of the document it quoted, found verbatim."""
        out = {}
        for p in self.inputs:
            label = PARTICIPANT_LABELS[p.provider]
            if p.provider not in self.readings:
                out[p.provider] = {'position': 'not_run', 'detail': self._state_sentence(p), 'quote': ''}
                continue
            said = self.codes.get(code, {}).get(p.provider, [])
            advised = self.advised.get(code, {}).get(p.provider, [])
            if said:
                good = list({(span.start, span.end): span for x in said for span in x.good}.values())
                detail = f'{label} proposed {code}' + (f' {len(said)} times' if len(said) > 1 else '')
                detail += f' ({self._stated([x.entry for x in said])})'
                detail += (f', quoting the document verbatim in {checks.plural(len(good), "passage")}.' if good
                           else '; none of its quotes was found verbatim in the document, so it is not counted as a '
                                'proposer.')
                if advised:
                    detail += f' It also lists {code} as not to code: {_reason_words(advised[0].entry.reason)}.'
                out[p.provider] = {'position': 'proposed', 'detail': detail,
                                   'quote': checks.excerpt(good[0].text) if good else ''}
            elif advised:
                first = next((x for x in advised if x.entry.reason == NOT_PERFORMED_HERE and x.good),
                             next((x for x in advised if x.good), advised[0]))
                out[p.provider] = {'position': 'advised_not_to_code',
                                   'detail': f'{label} advises not to code {code}: '
                                             f'{_reason_words(first.entry.reason)}.',
                                   'quote': checks.excerpt(first.good[0].text) if first.good else ''}
            else:
                out[p.provider] = {'position': 'not_proposed', 'detail': f'{label} did not propose {code}.',
                                   'quote': ''}
        return out

    @staticmethod
    def _stated(entries) -> str:
        """What a participant stated with a code: its units, modifiers and confidence, each shown only in the shape the
        reading's schema allows (a whole number, two characters, one of CONFIDENCES); any other value is counted, never
        shown, so no wording of the participant's own reaches the record."""
        units = [str(entry.units) for entry in entries if type(entry.units) is int]
        modifiers = [m for entry in entries for m in entry.modifiers
                     if isinstance(m, str) and MODIFIER_SHAPE.fullmatch(m)]
        confidences = [entry.confidence for entry in entries if entry.confidence in CONFIDENCES]
        others = (2 * len(entries) - len(units) - len(confidences)
                  + sum(len(entry.modifiers) for entry in entries) - len(modifiers))
        stated = (f'stated units {", ".join(units) or "none"}; '
                  f'modifiers {", ".join(dict.fromkeys(modifiers)) or "none"}; '
                  f'confidence {", ".join(dict.fromkeys(confidences)) or "none"}')
        return stated + (f' ({others} other value{"s" if others != 1 else ""} not shown)' if others else '')

    def _state_sentence(self, p: ParticipantInput) -> str:
        reason = checks.excerpt(str(p.reason or '')).rstrip('.')
        return (f'{PARTICIPANT_LABELS[p.provider]} ({PARTICIPANT_VENDORS[p.provider]}) did not read the document: '
                f'{PARTICIPANT_STATE_WORDS[p.state]}' + (f' ({reason})' if reason else '') + '.')

    def provider_checks(self, provider: list, provider_status: str, response: Optional[NormalizedResponse],
                        proposals: Sequence[ProposalAssessment]) -> list:
        """The proposal provider's checks, with its status reworded where it proposed nothing and a participant's code
        is a proposal: "so there are no CPT proposals" would be false beside it."""
        decidable = [p for p in proposals if p.bucket != 'alternative']
        if any((p.support or {}).get('origin') != 'participant' for p in decidable):
            return provider
        names = [PARTICIPANT_LABELS[name] for name in PARTICIPANT_ORDER
                 if any(name in p.support.get('proposed_by', ()) for p in decidable)]
        check = checks.provider_status_beside_participants(provider_status, response, names) if names else None
        return provider if check is None else [check if c.id == 'provider.status' else c for c in provider]

    # --- the encounter ------------------------------------------------------------------------------------------------

    def encounter_checks(self, inventory) -> list[Check]:
        out = [checks.participants_summary_check([self._summary_sentence(p) for p in self.inputs])]
        missing = self.missing(inventory)
        if missing:
            out.append(checks.participants_services_check([(PARTICIPANT_LABELS[m['participant']], m['label'],
                                                            m['quote']) for m in missing]))
        return out

    def _summary_sentence(self, p: ParticipantInput) -> str:
        reading = self.readings.get(p.provider)
        if reading is None:
            return self._state_sentence(p)
        label = PARTICIPANT_LABELS[p.provider]
        model = f', {reading.requested_model}' if reading.requested_model else ''
        parts = [f'{label} ({PARTICIPANT_VENDORS[p.provider]}{model}) read the document.']
        codes = [code for code, by in self.codes.items() if p.provider in by]
        if codes:
            quoted = sum(1 for code in codes if any(x.good for x in self.codes[code][p.provider]))
            more = len(codes) - LISTED_IN_SUMMARY
            named = ', '.join(codes[:LISTED_IN_SUMMARY]) + (f' and {more} more' if more > 0 else '')
            parts.append(f'It proposed {checks.plural(len(codes), "code")} ({named}), {quoted} quoting the document '
                         'verbatim.')
        else:
            parts.append('It proposed no code.')
        if self.unlisted.get(p.provider):
            parts.append(checks.unlisted_codes(self.unlisted[p.provider], MAX_LISTED_CODE, 'It'))
        if reading.unverified_quotes:
            one = reading.unverified_quotes == 1
            parts.append(f'{checks.plural(reading.unverified_quotes, "quote")} it gave {"was" if one else "were"} not '
                         f'found verbatim in the document and {"is" if one else "are"} never evidence.')
        if reading.questions:
            notes = 'is a note' if len(reading.questions) == 1 else 'are notes'
            parts.append(f'{checks.plural(len(reading.questions), "question")} it asked {notes}, never a '
                         'clarification.')
        if reading.extraction_issues:
            parts.append(f'It reported {checks.plural(len(reading.extraction_issues), "extraction issue")}.')
        return ' '.join(parts)

    def missing(self, inventory) -> list[dict]:
        """The services a participant reads as performed, quoting the document verbatim, of a kind of which
        ``inventory`` reads no performed service: one per participant and family, the first quote of its first."""
        if self._missing is None:
            done = {s.family for s in inventory.services if s.status in checks.POSITIVE}
            out, seen = [], set()
            for name, reading in self.readings.items():
                for service in reading.services:
                    families = PARTICIPANT_FAMILY_MAP.get(service.family, ())
                    if service.status != 'performed' or not families or done.intersection(families) \
                            or (name, service.family) in seen:
                        continue
                    good, _ = self._partition(service.evidence)
                    if not good:
                        continue
                    seen.add((name, service.family))
                    label = PARTICIPANT_SERVICE_LABELS[service.family]
                    reason = (f'{PARTICIPANT_LABELS[name]} reads a performed {label} that the documented-service '
                              'reading does not read as performed')
                    quoted = f'{reason} ({reconcile.quote(good[0])})'
                    out.append({'participant': name, 'family': service.family, 'families': list(families),
                                'label': label, 'quote': good[0].text, 'start': good[0].start, 'end': good[0].end,
                                'page': good[0].page,
                                # review.coding_completeness drops every reason that holds "open question" (it
                                # recounts the open questions): a quote that holds it is kept in the entry and the
                                # check, never in the reason, so the reason cannot be dropped with the count
                                'reason': quoted if OPEN_QUESTION not in quoted else f'{reason} (quoted under the '
                                                                                     'participants\' services)'})
            self._missing = out
        return self._missing

    def complete(self, complete: dict, inventory) -> None:
        """Coding completeness, incomplete beside each service only a participant reads (recorded under
        'participant_services', which reviewed_completeness keeps)."""
        missing = self.missing(inventory)
        if missing:
            complete.update(_incomplete(list(complete['reasons']) + [m['reason'] for m in missing]))
            complete['participant_services'] = missing
