"""Validation engine (ARCHITECTURE 5.6): provider codes -> one combined, checked assessment.

Pure apart from the reference lookup it is given. Only provider-selected codes
become reviewable proposals (bucket ``selected``, or ``excluded`` with the
reason); candidates and alternatives are informational and never approvable.
When the provider did not succeed there are no proposals, and an encounter
check says exactly why.
"""
from __future__ import annotations

import bisect
import functools
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping, Optional, Sequence

from studio.gi.context import charge_question_day, is_member_conflict
from studio.gi import cues as gi_cues
from studio.gi import sections as gi_sections
from studio.gi import structure as gi_structure
from studio.gi import services as gi_services
from studio.gi.profiles import DETECTED_FAMILIES, PROFILES, PROFILES_VERSION, ServiceProfile, family_for_code
from studio.participants import LABELS as PARTICIPANT_LABELS, PARTICIPANTS as PARTICIPANT_ORDER
from studio.participants import VENDORS as PARTICIPANT_VENDORS
from studio.participants.reading import MIN_QUOTE_CHARACTERS
from studio.reference.store import PFS, applied_sources
from studio.types import (CONFIDENCES, CONTEXT_FACTS, PARTICIPANT_STATES, PEER_POSITIONS, AssessmentResult, Check,
                          ClarificationSpec, CodePosition, CodeReference, ConfirmedFinding, EvidenceSpan, Fact,
                          FamilyFinding, LocatedQuote, NormalizedResponse, PageSpan, ParticipantCode, ParticipantInput,
                          ParticipantNotCoded, ParticipantReading, ParticipantService, PeerReview, ProposalAssessment,
                          ProviderCode, QuestionAnswer, ReferenceLookup, ReferenceSourceInfo, RoutingResult,
                          ServiceMention, Span, sha256_json)
from studio.gi.detect import DOUBT_PREFIX, UNESTABLISHED
from studio.validation import checks, questions, rationale, reconcile

ENGINE_VERSION = 'cpt-studio-validation@8'  # @8: harness repair 3 (P-ADMIT2)
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
    # HARNESS.md 11.3: the reviewer-confirmed answer that decided ``outcome`` (and ``match``) in place of the readers'
    # hold, with the readers' own words for that hold; None when the readers decided it (_Confirmations).
    confirmed: Optional['_Answer'] = None
    held: str = ''


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
    # 'participant' only: the rationale's first sentence - who proposed it, in which phase, and that Corti did not
    # (HARNESS.md 11.4), never "Selected by" (_Harness._lead)
    lead: str = ''
    # P-ADMIT2 (harness repair 3): the other decidable codes that claim one same documented act as this one, where at
    # least one of the two is a participant's admitted code; each is then held by one question naming the others
    # (competing_hold), whoever proposed it, and a reviewer's rejection of the others releases it (review_view)
    competes: tuple[str, ...] = ()
    # Completion repair (owner directive 2026-11-06, builder Q1): the provider codes this selection was read from, so the
    # harness can read the same code again with an independent participant's own passages added (_Harness.merge); and,
    # once it has, who cited each passage: ((start, end, (proposer, ...)), ...) in evidence order, recorded in the
    # support as 'provenance' (never in the fingerprint's inputs beyond the evidence itself). Empty with no participant.
    group: tuple = ()
    cited_by: tuple = ()

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
    # P2 READ-HOLD, R8 D15: a base code whose documented service is the endoscopic portion of another (an EGD inside an
    # EUS): (base code, the selected codes of that service that include the examination - none when it has no selected
    # code). Held, never excluded; empty when no base is so read (I1).
    bases_within: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def procedure_day(self) -> bool:
        return bool(self.procedure_labels or self.possible_labels)


def assess(*, text: str, pages: tuple[PageSpan, ...], context: dict[str, Fact], routing: RoutingResult,
           normalized: Optional[NormalizedResponse], reference: ReferenceLookup, service_date: Optional[date],
           provider_status: str, extraction_status: Optional[str] = None,
           extraction_messages: Sequence[str] = (), second: Optional[NormalizedResponse] = None,
           second_scope: Optional[dict] = None, participants: Sequence[ParticipantInput] = (),
           confirmed: Sequence[ConfirmedFinding] = (),
           member_answers: Sequence[questions.MemberAnswerInput] = ()) -> AssessmentResult:
    """``participants``: one input per CONFIGURED independent participant (HARNESS.md 5). With none (an installation
    where Astra and Fable are disabled) nothing below reads them and the result is the one this engine made before them
    (I1). With any, _Harness merges their codes, from both phases (HARNESS.md 11.1): they never decide a status (I2) and
    agreement never promotes (I3).

    ``confirmed``: the reviewer-confirmed findings of this revision (HARNESS.md 11.3). Each answers exactly the open
    question it was made for, read against the assessment these same inputs make without any confirmation
    (_Confirmations); none read, nothing below changes. Empty, the result is the one this engine made before them (I1).

    ``member_answers``: the revision's standing member answers (completion repair 2026-11-06; _MemberAnswers). Each
    answers exactly the question it was given to - its (code, family, fact) asked with its fingerprint
    (studio.validation.questions) - in the assessment these same inputs make without any answer; one that answers no
    such question is kept as an earlier answer and changes nothing. Empty, the result is the one this engine made before
    them."""
    if provider_status not in PROVIDER_STATUSES:
        raise ValueError(f'Unknown provider status {provider_status!r}.')
    if extraction_status is not None and extraction_status not in EXTRACTION_STATUSES:
        raise ValueError(f'Unknown extraction status {extraction_status!r}.')
    # read once, whatever iterable is given: an exhausted or empty iterator is no input (I1), never a dropped one
    participants, confirmed, member_answers = tuple(participants), tuple(confirmed), tuple(member_answers)
    answering = _MemberAnswers(member_answers, text) if member_answers else None
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
    # page spans tell it where a page turns inside a sentence (refutation r1, formats-6). With a participant configured
    # the reading also records where it read each service mention (``located``, beside the inventory and never an input
    # to it: the inventory is the same), which _Harness.missing reads (refutation round 8, wording-1 and wording-2).
    located = [] if harness is not None else None
    inventory = (gi_services.build(text, service_date=read_day, routing=routing, context_facts=context,
                                   pages=pages, located=located)
                 if READ_DOCUMENTED_SERVICES else gi_services.ServiceInventory(version=gi_services.INVENTORY_VERSION))
    if harness is not None:
        harness.located = tuple(located)
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
            # the codes the proposal provider only listed (a candidate, an alternative), and the codes its bounded
            # second review listed as an alternative (alt2): a participant's own proposal of one says so, never that
            # Corti did not propose it (refutation round 2, truth-7; review.corti_relation reads the same entries)
            listed = tuple(c.code for c in listable if c.role != 'selected')
            second_listed = tuple(item.code for item in second_alternatives)
            # HARNESS.md P-ADMIT: the open items are those Corti's selections and the second review's additions leave,
            # on the procedure day those selections make, as the second review reads them
            merge_day = _encounter(response.provider, context, routing, sources, date_state, selections).procedure_day
            selections, participant_alternatives = harness.merge(selections, routing, reference, read_day, usable,
                                                                 dated=date_state.value is not None,
                                                                 procedure_day=merge_day,
                                                                 corti_listed=listed,
                                                                 corti_second_listed=second_listed)
        encounter = _encounter(response.provider, context, routing, sources, date_state, selections)
        procedure_day = encounter.procedure_day
        alternatives = (c for c in listable if c.role != 'selected')
        proposals = (_keyed(selections, encounter, harness)
                     + tuple(_alternative(index, item, text, pages, response.provider)
                             for index, item in enumerate(alternatives))
                     + tuple(second_alternatives) + participant_alternatives)
    elif harness is not None:
        # No usable answer from the proposal provider: its failure blocks only itself (I10), and a participant's
        # first-reading proposal is checked for admission exactly as beside an answer (HARNESS.md P-ADMIT; the
        # session's D14 had listed every one as an alternative)
        selections, participant_alternatives = harness.merge(
            selections, routing, reference, read_day, usable, dated=date_state.value is not None,
            procedure_day=_encounter('', context, routing, sources, date_state, selections).procedure_day)
        encounter = _encounter('', context, routing, sources, date_state, selections)
        procedure_day = encounter.procedure_day
        proposals = _keyed(selections, encounter, harness) + participant_alternatives
    else:
        procedure_day = _encounter('', context, routing, sources, date_state, selections).procedure_day
    confirmation = _Confirmations(confirmed, text, pages) if confirmed else None
    keyed = _keys(selections)  # the decidable proposals' keys, in selection order (_MemberAnswers maps them back)
    if confirmation is not None:
        # HARNESS.md 11.3: each confirmation is matched to the question these inputs ask without any - a proposal's by
        # the proposal it was made for, never by its key - then read; the proposals keep the keys they have without them
        selections, proposals, procedure_day = confirmation.apply(
            selections, proposals, procedure_day, harness=harness,
            provider=response.provider if response is not None else '', context=context, routing=routing,
            sources=sources, date_state=date_state, inventory=usable, day=service_date)
    if harness is not None:
        proposals = harness.recorded(proposals)
        provider = harness.provider_checks(provider, provider_status, response, proposals)
    # The questions these inputs ask without any member answer: what each answer is bound against (_MemberAnswers), and
    # what the documented services' own questions are read beside, so an answer never makes another question asked.
    unanswered = proposals
    if answering is not None:
        answering.reading = _jsonable_inventory(inventory)  # the documented-service reading, as it is recorded
        proposals = answering.apply(proposals, dict(zip(keyed, selections)),
                                    None if problems else answering.reading,
                                    checks.reference_source_entries(sources, date_state.value), sources,
                                    date_state.value)
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
    service_questions = (_service_questions(usable, unanswered, context,
                                            confirmation.answered if confirmation is not None else ())
                         if usable else [])
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
    if confirmation is not None:
        encounter_checks += confirmation.encounter_checks()
    clarification = checks.service_date_clarification(date_state)
    clarifications = ((clarification,) if clarification else ()) + tuple(service_questions)
    clarifications += tuple(_member_conflict_questions(context, clarifications, unanswered))
    if answering is not None:
        answering.close_service(clarifications)  # a documented service's question a member answered: closed
    open_questions = len(clarifications) + sum(len(p.clarifications) for p in proposals)
    if answering is not None:
        open_questions -= answering.closed  # the questions a member answered are kept, answered, and are not open
    read = {s.evaluation.match.service.id for s in selections
            if s.evaluation is not None and getattr(s.evaluation, 'match', None) is not None}
    unestablished = sum(1 for svc in (usable or inventory).services if svc.status == 'uncertain' and svc.id not in read)
    # Harness repair 2026-11-05: a response refused whole was not used, so it is no available answer: completeness says
    # so even where an independent participant's admitted codes account for every documented act (a refused or failed
    # participant means partial completion, never a complete result - owner directive 2026-11-05)
    complete = reconcile.completeness(usable or inventory, unresolved, open_questions,
                                      provider_status == 'succeeded' and response is not None
                                      and not response.refused,
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
    if confirmation is not None:
        complete['confirmations'] = confirmation.record()
    if answering is not None:
        complete['member_answers'] = answering.record()
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
        covered = [label for _, _, _, label in _open_items_covered(candidate, code, open_items, inventory)]
        if covered and candidate.evaluation is not None and not candidate.excluded:
            added.append(replace(candidate, origin='second_review'))
            have.add(code)
            accounted += covered
        else:
            listed.append((group[0], _not_added_why(candidate, code, bool(covered), open_items)))
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


def _open_items_covered(candidate: '_Selection', code: str, open_items: Sequence[tuple], inventory) -> list[tuple]:
    """The open items - (service, family, act, label) of the reconciliation's ``no_proposal`` and ``not_covered``
    items - that ``code``, read as ``candidate``, accounts for, through the coverage catalogue: the rule a code the
    bounded second review selected is added by (_second_review), and the one an independent participant's first-reading
    proposal is admitted by (_Harness.merge, HARNESS.md P-ADMIT). A code the catalogue does not know accounts for
    nothing."""
    profile = reconcile.catalogue.code_profile(code)
    if profile is None:
        return []
    match = candidate.evaluation.match if candidate.evaluation is not None else None
    # a whole service left without a proposal is accounted for only by a code the document supports as done (its
    # base code, or an act it documents) - never by a code for an act nothing documents, which would hide the
    # missing service behind a held proposal (refutation r1, sends lens)
    # R1a-r5 (hold-only): an act tied to its service only by a lesion's name is documented as done; its code is
    # added and held (named_only), never dropped to an alternative that leaves the service silently uncoded
    supported = match is not None and (match.state in ('performed', 'incomplete') or match.reason == 'named_only') \
        and (not match.acts or any(a.role in reconcile.OWN_ROLES for a in match.acts))
    return [item for item in open_items if (
        (item[1] == candidate.family and ((item[2] == '' and supported) or item[2] in profile.covers
                                          or (item[2] in ('tattoo', 'injection') and {'tattoo', 'injection'}
                                              & set(profile.covers))))
        # a whole service read as part of another (an EGD inside an EUS) is accounted for by a code of that other
        # service that includes its examination - documented as done, which is why it is listed - as the
        # reconciliation reads it once the code is selected, whatever that code's own acts leave to the reviewer
        # (reconcile.includes_through; refutation P2RA, EUS lens 2: an EGD-with-EUS code the second review selected
        # for the listed EGD was kept as an alternative that "accounts for no documented service or act the primary
        # proposals left unresolved", the EGD stayed listed, and the one second review was used up)
        or (item[2] == '' and _includes_through(inventory, item[0], code, candidate.family)))]


def _claimed(candidate: '_Selection', items: Sequence[tuple], lay=None) -> set:
    """What an admissible participant code claims (HARNESS.md P-ADMIT): the documented acts it is read as accounting
    for - for an open item of one act kind, the service's acts of that kind; for a whole service left without a
    proposal, its match's acts - narrowed to those its own exact passages show (an act's evidence overlaps one of them),
    or all of them where its passages show none; and the service itself for a code that accounts for no act of it (a
    base code). Two different codes compete only where they claim one same act: an EGD's dilation code and its biopsy
    code never compete, two dilation codes for its one dilation do, and an esophageal and a pyloric dilation code for
    two different dilations do not (refutation multi-4: both had been left alternatives, the EGD uncoded)."""
    match = candidate.evaluation.match if candidate.evaluation is not None else None
    spans = [(e.start, e.end) for e in candidate.evidence]
    support = candidate.evaluation.support if candidate.evaluation is not None else None
    # what the engine supports the code by: the acts of a match it reads as done - never a held one's (completion repair,
    # builder Q1: a code the evidence hold keeps from READY, because its own passages state another act of its kind not
    # done, claims no done act it does not show; it can never be the second READY code for that act - F4)
    supported_by = ({a.id for a in match.acts} if match is not None and match.state in checks.POSITIVE
                    and support is not None and support.status in ('pass', 'warn') else set())

    def summary(a) -> bool:
        # A restatement of the report's own account of an act: an act stated only in an Impression, an assessment
        # ("Diagnosis:") or a findings summary, or one named with no act predicate of its own - a procedure line's
        # listing ("Procedure: Upper endoscopy with balloon dilation"). Refutation cycle 3, C3-3-1: cycle 2 read only the
        # Impression so, and a procedure line's or a Diagnosis line's restatement became a second act, its code READY
        # beside the narrative act's code.
        if a.cues and (a.cues[0] in gi_services.SILENT_READINGS or a.cues[0] == gi_services.LISTED_CUE):
            return True
        return lay is not None and bool(a.evidence) and all(
            lay.section_at(ev.start).kind in RESTATING_SECTIONS for ev in a.evidence)

    def shows(a) -> bool:
        return any(ev.start < hi and lo < ev.end for ev in a.evidence for lo, hi in spans)

    def claims(acts, possible, kinds=(), pool=()):
        """The acts the code claims among ``acts`` (performed acts of the kind it accounts for): those its own passages
        show, an Impression's restatement read as the narrative's acts of its kind, and - where its passages show no act
        of those kinds at all - the one act it can account for when there is only one (refutation cycle 2, C2-4-1:
        Corti's 43249 on "A Schatzki ring was found" claims the one dilation). With several and none shown, nothing:
        which one is not established (L4-2: an Impression naming two strictures claims neither dilation). Passages that
        show an act of the kind that is not done claim no other act (L4-2's control: "It is unclear whether the ring
        was also dilated with a Savary bougie" is a doubted second dilation, never the balloon dilation done)."""
        own = [a for a in acts if shows(a)]
        undone = [a for a in pool if a.status != 'performed' and a.kind in kinds and shows(a)]
        backed = [a for a in acts if a.id in supported_by]
        if not own and backed:
            # a code the engine supports by acts its passages do not show claims every act its support rests on
            # (refutation cycle 3, C3-3-4; cycle 4, C4-2-3: Corti's 43248 on "Possibly the ring was also dilated with a
            # Savary bougie" is READY on the balloon dilations done, so it competes with any code for one of them).
            # On the safe side: two codes for one act are never both READY (an Impression naming two strictures holds
            # both dilation codes, L4-2's first case, recorded)
            own = backed
        elif not own and not undone:
            own = list(acts)
        narrative = [a for a in possible if not summary(a)]
        out = []
        for a in own:
            told = [b for b in narrative if b.kind == a.kind] if summary(a) else []
            out.extend(told or [a])
        return {('act', a.service, a.kind, a.lesion, ','.join(a.anatomy), a.id, summary(a)) for a in out}

    claimed = set()
    for service, family, act, label in items:
        svc = match.service if match is not None and match.service.id == service else None
        if act:
            acts = [a for a in (svc.acts if svc is not None else ()) if a.status == 'performed'
                    and a.role in reconcile.OWN_ROLES
                    and (a.kind == act or (act in ('tattoo', 'injection') and a.kind in ('tattoo', 'injection')))]
            if not acts:
                claimed.add(('item', service, family, act, label))
            kinds = {'tattoo', 'injection'} if act in ('tattoo', 'injection') else {act}
            claimed.update(claims(acts, acts, kinds, svc.acts if svc is not None else ()))
            continue
        acts = match.acts if svc is not None else ()
        if acts:
            claimed.update(claims(acts, acts, {a.kind for a in acts}, svc.acts))
        else:
            claimed.add(('service', service, family))
    return claimed


def _not_added_why(candidate: '_Selection', code: str, accounts: bool, open_items: Sequence[tuple],
                   left_by: str = 'the primary proposals') -> str:
    """Why a code read as ``candidate`` that is not excluded-and-accounting is not added as a proposal: the second
    review's reasons, also an independent participant's (HARNESS.md P-ADMIT). ``left_by`` names the proposals that
    left the open items unresolved."""
    profile = reconcile.catalogue.code_profile(code)
    match = candidate.evaluation.match if candidate.evaluation is not None else None
    if profile is None:
        return 'the coverage catalogue does not establish which documented act it accounts for'
    if not accounts and any(family == candidate.family and act == '' for _, family, act, _ in open_items):
        # Why a whole service's own family's code accounts for nothing is said from what was read: only its exact
        # passages are read, so with none (or out of scope) nothing was, and that is the reason - never a statement
        # about the document (eus2 F1: an EUS documented as performed with its sampling, a 43242 whose one passage
        # was three characters off, had read "not documented as done"); an act the document states both ways is the
        # conflict the assessment records, never one it does not document as done.
        return ((candidate.scope_reason or NO_EVIDENCE).rstrip('.') if candidate.evaluation is None
                else 'the document states the act it accounts for both as done and as not done (both are '
                     'kept; neither is chosen)' if match is not None and match.reason == 'conflict'
                else 'the act it accounts for is part of another documented act, not a separate service'
                if match is not None and match.reason == 'act_included'
                else 'CPT Studio could not find the act it accounts for documented as done in the service left '
                     'unresolved')
    if not accounts:
        return f'it accounts for no documented service or act {left_by} left unresolved'
    if candidate.evaluation is None:
        return (candidate.scope_reason or NO_EVIDENCE).rstrip('.')
    return 'the document reads what it accounts for as not performed on the date of service'


def _documented_items(inventory, procedure_day: bool = False) -> list[tuple]:
    """Every documented service and act the reconciliation reads as needing a code, as if nothing were proposed
    (P-ADMIT2): (service, family, act, label) - each service the reading reads done with no proposal, act '' (what the
    reconciliation lists for it), and each of its acts the reconciliation would list as not covered by a code of its
    service that accounts for none of them (its family's diagnostic base code: the reconciliation's own reading of which
    acts are separate services, its bundling included - a lift injection inside an EMR is none). The same items
    _open_items_covered reads for the second review, over the whole document instead of what other codes left open."""
    services, _, _ = reconcile.reconcile(inventory, [], procedure_day=procedure_day)
    items = [(u.service, u.family, u.act, u.label) for u in services if u.reason in ('no_proposal', 'not_covered')]
    families = {u.family for u in services if u.reason == 'no_proposal'}
    bases = [(next(code for code, profile in reconcile.catalogue.CODES.items()
                   if profile.family == family and profile.base), family)
             for family in sorted(families)
             if any(profile.family == family and profile.base for profile in reconcile.catalogue.CODES.values())]
    if bases:
        acts, _, _ = reconcile.reconcile(inventory, bases, procedure_day=procedure_day)
        items += [(u.service, u.family, u.act, u.label) for u in acts if u.reason == 'not_covered' and u.act]
    # refutation round 1 of harness repair 3 (L4-1): an office visit documented as done is a documented service, beside
    # a same-day procedure too. The reconciliation never pushes one there (it lists none), which is a rule about what
    # it asks for, not about what a proposal may account for: the visit's own checks (separate_em) judge the proposal
    listed = {item[0] for item in items}
    items += [(service.id, service.family, '', reconcile.service_label(service)) for service in inventory.services
              if service.family == 'gi.office_em' and service.status in ('performed', 'incomplete')
              and service.id not in listed]
    # Refutation cycle 2 of harness repair 3 (provider-neutral admission, the owner's "validation is provider-neutral"),
    # narrowed by cycle 3: an act the reading states done, inside a service the reading documents in doubt (its time,
    # place or performance not established), is a documented item too: what a code for it claims (_competition), whoever
    # proposed it (the completion repair admits every explicit participant code by the same path as Corti's).
    have = {(item[0], item[2]) for item in items}
    for service in inventory.services:
        entry = reconcile.catalogue.entry(service.family)
        if entry is None or entry.support != reconcile.catalogue.SUPPORTED or service.status != 'uncertain':
            continue
        # its acts stated done, where the service is documented in doubt (39f0ac49's labelled procedure paragraphs
        # inside its Indications) - never an act read in doubt itself (_in_doubt)
        for kind in sorted({a.kind for a in service.acts if _in_doubt(a, service) and a.role in reconcile.OWN_ROLES
                            and a.kind in entry.acts}):
            if (service.id, kind) not in have:
                items.append((service.id, service.family, kind, reconcile.service_label(service)))
                have.add((service.id, kind))
    return items


def _in_doubt(act, service) -> bool:
    """Whether ``act`` is a documented item of a service in doubt (_documented_items): an act the reading states done
    ('performed') inside a service the reading documents in doubt ('uncertain'), which a code for it claims in the
    competition (_competition). Never an act whose own reading is 'uncertain' (refutation cycle 3, C3-2-1 to C3-2-3).

    Completion repair (builder Q1): no longer an admission rule. Every explicit participant code is admitted and read by
    the shared per-code path, as Corti's selection is - the recorded asymmetry (a participant's code listed where
    Corti's was held) is gone; an act the document states not done is excluded with its passage for every proposer
    (_stated_not_done), and every other doubt is held for every proposer."""
    return act.status == 'performed' and service.status == 'uncertain'


# Sections whose acts restate the report's own narrative account (_claimed): an Impression and an assessment
# ("Diagnosis:", "Clinical impression:"). A findings section is narrative - many reports state the acts there - and
# its acts are read by _same_claim (refutation cycle 4, C4-2-1 and C4-2-2)
RESTATING_SECTIONS = ('impression', 'assessment')


# --- completion repair (owner directive 2026-11-06, items 3 and 5; builder Q1): an act the document states not done --
# The shared per-code path held a code whose act the document itself states was not done today - "Hot snare polypectomy
# failed.", "... is to be performed at a later date." - with a question asking whether it was done, and the held code
# held its family's base code as included in it (base_included). Item 5 resolves a fact the source states before the
# doctor is asked, and "not done" is said only with the passage that says so: such a code is EXCLUDED, with that
# passage, reinstatable - whoever proposed it (equal eligibility: before, a participant's code for it was an
# alternative, and Corti's own selection of the same passage was held; refutation cycle 3, C3-2-1).

# The documented-service reader's own readings (services.read_clause: a status and its deciding first cue) that state
# an act NOT done on the date of service. A closed class of the reader's categories, never words of the document, and
# its failure mode is the safe side: every other reading - a hedge or an attempt ("was attempted"), a condition or an
# open question ("It is unknown whether ..."), a consent's object, a question, another source or agent, an indication,
# silence, an unknown cue - is no statement that the act was not done, and the code keeps the shared path's hold. A
# consent's object and a bare question were measured as unsafe to exclude on: "Consent was obtained for biopsy, which was
# performed." and "Were biopsies taken from the polyp? Yes." read as the consent's object and as a question alone.
STATED_NOT_DONE_STATUSES = ('planned', 'historical', 'negated', 'cancelled')
STATED_FAILURE_CUES = ('uncertain: failed', 'uncertain: unsuccessful', 'uncertain: unsuccessfully',
                       'uncertain: abandoned')  # services._failed_act's own words, cues.FAILED_ACT


def _time_from_section(cues: Sequence[str]) -> bool:
    """Whether a documented-service reading's time is its section's alone ("historical: in a history section", "planned:
    in a plan section", "planned: listed under a plan heading", a plan read from a plan section or label alone): the
    layout's reading, never the act's own clause's (round 4 PA: "one cause, not two readings"; a numbered "3. Upcoming
    procedures" item makes today's item after it planned)."""
    first = cues[0] if cues else ''
    return first.startswith(_SECTION_ONLY_SERVICES + ('planned: listed under a plan heading',)
                            + tuple(gi_services.SECTION_PLAN_CUES))


def _states_not_done(status: str, cues: Sequence[str], *, own: bool = True) -> bool:
    """Whether a documented-service reading states the act NOT done on the date of service: planned, historical,
    denied or cancelled; failed (its own failure word, services._failed_act, or a later clause of its sentence stating the
    same act failed, LATER_FAILURE_CUE); or still to be done (an infinitive predicate, INFINITIVE_CUE). ``own``: only a
    statement of the act's own clause - never a time its section alone gives it (_time_from_section); a reading read after
    such a statement (``own=False``) may take its section's time."""
    first = cues[0] if cues else ''
    if status in STATED_NOT_DONE_STATUSES:
        return not (own and _time_from_section(cues))
    return status == 'uncertain' and (first in STATED_FAILURE_CUES or first == gi_services.INFINITIVE_CUE
                                      or first.startswith(gi_services.LATER_FAILURE_CUE))


def _stated_words(status: str, cue: str) -> str:
    """How a not-done reading is said in a reason."""
    if status in ('planned', 'historical', 'cancelled'):
        return {'planned': 'planned', 'historical': 'on another occasion', 'cancelled': 'cancelled'}[status]
    if status == 'negated':
        return 'not done'
    return 'still to be done' if cue == gi_services.INFINITIVE_CUE else 'failed'


def _mention_readings(text: str, flow: str, ev, kind: str, day: Optional[date], pages=()) -> Optional[list]:
    """The documented-service reader's own reading of each mention of an act of ``kind`` in the passage ``ev``
    (services.passage_readings over the mention alone: the mention read in its own clause, as pass 3 reads acts), or
    None where the passage holds no such mention or is not read through. ``flow``: the reflowed text the reader reads
    (services.reflow, one character for one)."""
    pattern = next((p for k, p in gi_services.ACTS if k == kind), None)
    if pattern is None:
        return None
    out = []
    for m in pattern.finditer(flow, ev.start, ev.end):
        readings = gi_services.passage_readings(text, m.start(), m.end(), day, pages)
        if readings is None:
            return None
        out += [reading for reading, _clause in readings]
    return out or None


def _stated_not_done(code: str, found: reconcile.Match, own: Sequence[checks.Reading], text: str,
                     day: Optional[date], pages=()) -> tuple:
    """((status, cue, passage), ...): where the documented service is performed and every act it documents of a kind
    ``code`` accounts for is stated NOT done today by the document itself, each such statement with its passage - else
    () and the code keeps the shared path's hold. Conjunctive, every condition read on the readers' own output:
    - the code accounts for an act (never a base, E/M or uncatalogued code), matched 'act_missing' - no act of its kinds
      is documented as done, denied or in conflict;
    - every act of its kinds is the physician's own, and each either reads not done (_states_not_done) or is the
      procedure line's listing that the report itself withheld (LISTED_WITHHELD_CUE), each of whose passages reads, at
      every mention of the act, either nothing (the listing line, a bare name) or not done;
    - at least one passage states it not done;
    - from each such passage to the end of the service's text, nothing the reader reads says anything was done or is in
      doubt (services.passage_readings: a later "The polyp was then removed.", "It is unclear whether ...", or a passage
      too full to read through keeps the hold) - so a failure the document later overtakes never excludes;
    - the routing-era reader reads none of the code's own passages as performed by a cue of its own clause.
    Bounded: a few reads per act of the code's kinds, each bounded by services.PASSAGE_READS."""
    profile = reconcile.catalogue.code_profile(code)
    service = found.service
    if profile is None or profile.base or not profile.covers or 'em_visit' in profile.covers \
            or found.state != 'uncertain' or found.reason != 'act_missing' or service.status not in checks.POSITIVE:
        return ()
    if any(r.origin == 'evidence' and r.status == 'performed'
           and any(c.startswith(checks.PERFORMED_CUE_PREFIX) for c in r.cues) for r in own):
        return ()
    kinds = set(profile.covers)
    if kinds & {'tattoo', 'injection'}:
        kinds |= {'tattoo', 'injection'}  # one marking for both, as reconcile.match reads it
    acts = [a for a in service.acts if a.kind in kinds]
    if not acts or any(a.role not in reconcile.OWN_ROLES for a in acts):
        return ()
    # the reader's own reflowed view, its sentences and its act mentions: one index per document, date and pages
    # (_reader_index) - never a rescan of the text per code
    flow, sentences, starts, mentions, mention_starts = _reader_index(text, day, tuple(pages or ()))
    stated, listing = [], []
    for act in acts:
        if _states_not_done(act.status, act.cues):
            stated += [(act.status, act.cues[0] if act.cues else '', ev) for ev in act.evidence]
            continue
        if not (act.status == 'uncertain' and gi_services.LISTED_CUE in act.cues
                and gi_services.LISTED_WITHHELD_CUE in act.cues):
            return ()
        for ev in act.evidence:
            readings = _mention_readings(text, flow, ev, act.kind, day, pages)
            if readings is None:
                return ()
            said = [r for r in readings if not _says_nothing(r.status, r.cues)]
            if not said:
                listing.append(ev)
                continue  # the procedure line itself, or a bare name: it names the act and states nothing either way
            if not all(_states_not_done(r.status, r.cues) for r in said):
                return ()
            stated.append((said[0].status, said[0].cues[0] if said[0].cues else '', ev))
    if not stated:
        return ()
    # Second review of the rule (builder Q1, measured before it shipped): the reader is silent on many statements that
    # the act was done after all - "... was then successful", "repeated with success", "it was successful on the second
    # attempt", "a second pass yielded tissue", a failure in a relative clause ("that failed last year was successfully
    # repeated today"), "unsuccessful x1, successful x1" - and its silence is no statement. Each read the code EXCLUDED
    # and released its base code READY. So the statement must close what the document says: it ends its sentence (and,
    # for a failure, the sentence ends with the reader's own failure word, cues.FAILED_ACT); its sentence ends its
    # paragraph (a blank line or the document's end follows); no other mention of an act of the code's kinds in the
    # service, before or after it, reads anything but not done (a silent one included); and nothing read after it says
    # anything was done or is in doubt.
    texts = [ev for _s, _c, ev in stated]
    for status, cue, ev in stated:
        failure = status == 'uncertain' and (cue in STATED_FAILURE_CUES or cue.startswith(gi_services.LATER_FAILURE_CUE))
        if not _closes_its_paragraph(flow, sentences, starts, mentions, mention_starts, kinds, ev, failure):
            return ()
    lo = min([service.scope_start] + [ev.start for ev in texts])
    hi = max([service.scope_end] + [ev.end for ev in texts])
    first = bisect.bisect_left(mention_starts, lo)
    last = bisect.bisect_left(mention_starts, hi)
    if last - first > gi_services.PASSAGE_READS:
        return ()  # too many mentions to read through: what they say is not established
    for kind, ms, me in mentions[first:last]:
        if kind not in kinds or any(ev.start <= ms and me <= ev.end for ev in texts + listing):
            continue
        readings = gi_services.passage_readings(text, ms, me, day, pages)
        if not readings or not all(_states_not_done(r.status, r.cues, own=False) for r, _clause in readings):
            return ()  # another mention of the act - silent, done, in doubt, or unread - keeps the hold
    for _status, _cue, ev in stated:
        end = service.scope_end if service.scope_end > ev.end else len(text)
        rest = gi_services.passage_readings(text, ev.start, end, day, pages)
        if rest is None or any(not _says_nothing(r.status, r.cues) and not _states_not_done(r.status, r.cues, own=False)
                               for r, _clause in rest):
            return ()
    return tuple(stated)


@functools.lru_cache(maxsize=1)
def _reader_index(text: str, day: Optional[date], pages: tuple) -> tuple:
    """(flow, sentences, their starts, act mentions (kind, start, end), their starts): the documented-service reader's
    own reflowed view and sentences (services._act_frame, which passage_readings reads) and its act mentions
    (services._acts_in over the whole view), computed once per document, date and pages and searched by bisection."""
    flow, _dates, _plist, _starts, sentences = gi_services._act_frame(text, day, pages)
    mentions = tuple(gi_services._acts_in(flow, 0, len(flow)))
    return flow, tuple(sentences), tuple(s for s, _ in sentences), mentions, tuple(m[1] for m in mentions)


_WORD = re.compile(r'[^\W\d_]+')
_BLANK_LINE = re.compile(r'\n[ \t]*\n')
_CLAUSE_MARK = re.compile(r'[,;:()\[\]\u2013\u2014]|\s-\s')  # what opens another clause or an aside before the act


def _closes_its_paragraph(flow: str, sentences: Sequence[tuple], starts: Sequence[int], mentions: Sequence[tuple],
                          mention_starts: Sequence[int], kinds, ev, failure: bool) -> bool:
    """Whether the not-done statement ``ev`` is the whole end of what its paragraph says: nothing but punctuation
    follows it in its sentence (the reader's own sentences); a failure's sentence ends with the reader's own failure
    word (cues.FAILED_ACT: "Hot snare polypectomy failed.", "Polypectomy: unsuccessful.") and nothing before its first
    mention of the act opens another clause - no comma, semicolon, colon, dash or bracket, and no act predicate of the
    reader's (ACT_VERB, BARE_PARTICIPLE): never "failed initially; it was successful ...", "failed last year was
    successfully repeated today", "Although the first attempt was successful, a second ... failed." or "Despite the polyp
    being removed ..."; and a blank line or the document's end follows the sentence. Any other shape keeps the hold."""
    i = bisect.bisect_right(starts, max(ev.start, ev.end - 1)) - 1
    if i < 0:
        return False
    ss, se = sentences[i]
    if not ss <= max(ev.start, ev.end - 1) < se or _WORD.search(flow, ev.end, max(ev.end, se)):
        return False
    if failure:
        words = _WORD.findall(flow, ss, se)
        if not words or not gi_cues.FAILED_ACT.fullmatch(words[-1]):
            return False
        first = None
        for kind, ms, _me in mentions[bisect.bisect_left(mention_starts, ss):]:
            if ms >= se:
                break
            if kind in kinds:
                first = ms
                break
        if first is None or _CLAUSE_MARK.search(flow, ss, first) or gi_services.ACT_VERB.search(flow, ss, first) \
                or gi_services.BARE_PARTICIPLE.search(flow, ss, first):
            return False
    nxt = sentences[i + 1][0] if i + 1 < len(sentences) else len(flow)
    return not _WORD.search(flow, se, nxt) and (nxt >= len(flow) or bool(_BLANK_LINE.search(flow, se, nxt + 1)))


def _not_done_match(code: str, found: reconcile.Match, stated: Sequence[tuple]) -> reconcile.Match:
    """The match of a code whose act the document states not done (_stated_not_done): not performed, saying so with
    the passages that say it (item 5), the first three quoted and the rest counted."""
    what = ' or '.join(reconcile.act_label(k) for k in reconcile.catalogue.code_profile(code).covers)
    seen, quoted = set(), []
    for status, cue, ev in stated:
        if (ev.start, ev.end) not in seen:
            seen.add((ev.start, ev.end))
            quoted.append(f'{reconcile.quote(ev, 120)} ({_stated_words(status, cue)})')
    more = f'; and {len(quoted) - 3} more' if len(quoted) > 3 else ''
    return replace(found, state='not_performed', reason='act_not_done', acts=(), question='',
                   detail=f'The {reconcile.service_label(found.service)} is documented as {found.service.status}, but '
                          f'the document states the {what} was not done on the date of service: '
                          f'{"; ".join(quoted[:3])}{more}.')


def _another_roles_hold(code: str, found: reconcile.Match) -> reconcile.Match:
    """Completion repair (owner directive 2026-11-06, item 2: "other-provider acts must remain distinct from completed
    current services"; builder Q1): a code whose documented service the readers read as done, but every act of which it
    accounts for is documented only in another role's entry - a pathology addendum, a nursing note, an anesthesia
    record, a radiology report (services' role reader) - is held with a question naming that entry, whoever proposed it.
    Before, a participant's code there was kept out by an admission rule of its own (own-3, the reconciliation's role
    rule applied to admission) while Corti's own selection of the same passage was READY: equal eligibility made the
    base's false READY the participants' too. It is a hold, never an exclusion: the role reader can be wrong (refutation
    round 2, over-6: an Impression right after "Pathology results: pending." is read as the pathology entry's), and a
    held code keeps its family's base code held beside it, so a misread role never releases anything. Unchanged
    otherwise."""
    if found.state not in checks.POSITIVE or found.reason != 'service' or not found.acts \
            or any(a.role in reconcile.OWN_ROLES for a in found.acts):
        return found
    what = ' or '.join(reconcile.act_label(k) for k in reconcile.catalogue.code_profile(code).covers) \
        if reconcile.catalogue.code_profile(code) is not None else 'act'
    entry = found.acts[0]
    roles = checks._join(sorted({a.role for a in found.acts}))
    passage = reconcile.quote(entry.evidence[0], 120) if entry.evidence else ''
    return replace(found, state='uncertain', reason='another_role',
                   detail=f'{found.detail} But the {what} it accounts for is documented only in the {roles} entry'
                          + (f' ({passage})' if passage else '') + ', not by the physician performing the '
                          f'{reconcile.service_label(found.service)}. Held for the reviewer, not excluded.',
                   question=(f'The {what} is documented only in the {roles} entry' + (f' ({passage})' if passage else '')
                             + f'. Was it performed in this {reconcile.service_label(found.service)} on the date of '
                               'service?'))


def _not_done_outcome(found: reconcile.Match, stated: Sequence[tuple]) -> checks.StatusOutcome:
    """The not-performed outcome of a _not_done_match: its deciding reading is the first passage that says so."""
    status, _cue, ev = stated[0]
    reading = checks.Reading(status if status in checks.NEGATIVE else 'negated', (found.detail,), 'service', ev.text,
                             ev.start, ev.end)
    return checks.StatusOutcome('not_performed', reading, reason=found.reason)


def _competition(admissible: Mapping[str, tuple], selections: Sequence['_Selection'],
                 documented: Sequence[tuple], inventory, text: Optional[str] = None) -> dict[str, tuple[str, ...]]:
    """code -> the codes it competes with (P-ADMIT2, harness repair 3): two different decidable codes compete where
    each claims one same documented act (_claimed: an EGD's dilation code and its biopsy code never do; two dilation
    codes for its one dilation do), and at least one of them is a participant's admitted code (``admissible``: code ->
    (its reading, the documented items it accounts for, its first proposers)). A participant's code competes with every
    other such code, a proposal provider's or a second review's only with the participants' (two codes the proposal
    provider alone selected read as before). Each is then held by one question naming the others, whoever proposed it:
    CPT Studio never chooses between codes, nor prefers one for its proposer."""
    lay = gi_structure.clinical_layout(text) if text is not None else None
    # Completion repair (builder Q1): every explicit participant code is admitted now, excluded ones too (reinstatable,
    # with the passage); a code that is not active claims nothing and holds nothing, whoever proposed it, as an
    # excluded selection of Corti's never did
    admissible = {code: entry for code, entry in admissible.items() if not entry[0].excluded}
    claims_of: dict[str, set] = {code: _claimed(candidate, items, lay)
                                 for code, (candidate, items, _) in admissible.items()}
    for selection in selections:
        if selection.evaluation is None or selection.excluded or selection.code in claims_of:
            continue
        items = (_open_items_covered(selection, selection.code, documented, inventory)
                 if inventory is not None else [])
        claims_of[selection.code] = _claimed(selection, items, lay) if items else set()
    out: dict[str, tuple[str, ...]] = {}
    for code, claimed in claims_of.items():
        # one act claimed twice competes: the same act, an Impression's restatement of it (refutation round 1, L4-3;
        # cycle 2, C2-4-2), or the same kind at one site stated twice in the narrative (_same_claim)
        rivals = {other for other, theirs in claims_of.items() if other != code
                  and any(_same_claim(mine, their) for mine in claimed for their in theirs)}
        if code not in admissible:
            rivals &= set(admissible)  # a decidable code competes only with the participants' codes
        if rivals:
            out[code] = tuple(sorted(rivals))
    return out


def _same_claim(mine: tuple, theirs: tuple) -> bool:
    """Whether two _claimed claims ('act', service, kind, lesion id, anatomy, act id, restated) may be one act, so that
    two codes claiming them compete: always, for one service's act kind, unless the two are told apart - two lesion
    records (compared whole: S1-L1 is never S1-L10's, C3-3-3), or two stated sites neither of which contains the other
    (whole-word: "distal esophagus" contains "esophagus"). A statement whose site the reader leaves unread may restate
    the other ("The dilation was performed without complication.", C4-2-4; a Findings line, C4-2-1), so it competes -
    even one that opens with "a second" ("A second photograph of the snare polypectomy site was taken." names a snare
    act to the reader; a release for such openers made two READY codes for one polypectomy, so it was dropped).

    Refutation cycle 4: the act-identity reading failed in every cycle in one direction or the other, so it errs toward
    competing - two codes for one documented act are never both READY, and the false holds this costs (two dilations
    whose second site is unread, C2-4-3; a site-less Impression restating one of two, C3-3-2) are recorded."""
    if mine[0] != 'act' or theirs[0] != 'act':
        return mine == theirs
    if mine[1] != theirs[1] or mine[2] != theirs[2]:
        return False
    if mine[5] == theirs[5]:
        return True
    if mine[3] and theirs[3]:
        return mine[3] == theirs[3]
    a = [part.strip() for part in mine[4].lower().split(',') if part.strip()]
    b = [part.strip() for part in theirs[4].lower().split(',') if part.strip()]
    if a and b:
        return any(_site_contains(x, y) or _site_contains(y, x) for x in a for y in b)
    return True


def _site_contains(outer: str, inner: str) -> bool:
    """Whether the site ``outer`` names ``inner`` whole-word ("distal esophagus" names "esophagus")."""
    return re.search(r'(?<![\w-])' + re.escape(inner) + r'(?![\w-])', outer) is not None


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
        if _po_called_off(text):  # C1 (cycle 2): the document says its procedure was called off or not done today
            return False
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
# GI round 4, Wave 1 repair cycle 2 (po.json amendment_20261101_cycle2; refutation PO1-PASTED-ACT-OFFER of fbc59ee53):
# one act pasted from another record gave P1 its positive evidence, so a report whose procedure was called off was
# offered again - the act 9 lines under "Previous Report" or "Outside Report" (sections.under_another_occurrence reads 6
# lines and 600 characters back), under "Attached Report" (no occurrence word), or under no heading at all. Two holds:
# C1, PO-1 offers nothing where the document says its procedure was called off, cancelled or not done today, whatever a
# pasted act elsewhere says (_PO_CALLED_OFF: a closed list read only to hold - "After discussion we did not go ahead",
# "the scope was not inserted", "nothing further was done today", "she will be rebooked next week"); C2, P1's act is no
# evidence where the nearest heading-like line above it, read back as far as a section's heading
# (sections.HEADING_REACH_LINES lines, HEADING_REACH_CHARS characters), names another occurrence's record or an
# attachment (_po_under_another_record). Hold-only: each withholds offers and offers nothing new.
_PO_PROCEDURE_NOUN = (r'(?:procedures?|examinations?|exams?|study|studies|endoscopy|colonoscopy|gastroscopy'
                      r'|sigmoidoscopy|egd|eus|ercp|case)')
_PO_CALLED_OFF = re.compile(
    # "After discussion we did not go ahead", "decided not to proceed with the colonoscopy" (never "could not proceed
    # beyond the sigmoid": a procedure begun and stopped is an incomplete one, a performed reading)
    r"\b(?:did\s+not|didn['’]t|could\s+not|couldn['’]t|would\s+not|chose\s+not\s+to|decided\s+not\s+to"
    r"|elected\s+not\s+to|opted\s+not\s+to|unable\s+to|not\s+able\s+to)\s+go\s+ahead\b"
    r"|\b(?:did\s+not|didn['’]t|chose\s+not\s+to|decided\s+not\s+to|elected\s+not\s+to|opted\s+not\s+to)\s+proceed"
    r"(?:\s+with\s+(?:the\s+|her\s+|his\s+|their\s+|this\s+|today['’]s\s+)?" + _PO_PROCEDURE_NOUN + r"\b"
    r"|[ \t]*+(?:[.;,\n]|\Z|today\b|and\b|because\b|as\b|since\b|given\b|due\b))"
    # "the scope was not inserted", "nothing further was done today", "she will be rebooked next week"
    r"|\b(?:scope|endoscope|colonoscope|gastroscope|sigmoidoscope|echoendoscope|duodenoscope|instrument)\s+(?:was|were)"
    r"\s+(?:not|never)\s+(?:inserted|introduced)\b"
    r"|\bnothing\s+(?:further\s+|else\s+|more\s+)?(?:was\s+|were\s+)?(?:done|performed)\s+today\b"
    r"|\b(?:will\s+be|was|were|is|are|has\s+been|have\s+been|had\s+to\s+be|to\s+be|being)\s+(?:re-?booked"
    r"|re-?scheduled|postponed|called\s+off)\b"
    # "called off", "not performed today", "no colonoscopy today", "sent home without the procedure"
    r"|\bcalled\s+off\b"
    r"|\bnot\s+(?:done|performed|carried\s+out|undertaken|attempted|started|begun)\s+today\b"
    r"|\bno\s+" + _PO_PROCEDURE_NOUN + r"\s+(?:(?:was|were)\s+(?:done|performed)\s+)?today\b"
    r"|\bsent\s+home\s+without\s+(?:the\s+|a\s+|any\s+|her\s+|his\s+)?" + _PO_PROCEDURE_NOUN + r"\b"
    # "the procedure was aborted before insertion", "the case was cancelled", "cancelled at the time-out"
    r"|\b" + _PO_PROCEDURE_NOUN + r"\s+(?:was\s+|were\s+)?(?:aborted|abandoned|stopped|halted)\s+before\s+"
    r"(?:insertion|intubation|sedation|induction|starting|it\s+(?:began|started)"
    r"|the\s+(?:scope|endoscope|colonoscope|start))\b"
    r"|\bcase\s+(?:was\s+|has\s+been\s+|had\s+to\s+be\s+)?cancel(?:l)?ed\b"
    r"|\bcancel(?:l)?ed\s+(?:today|on\s+arrival|at\s+(?:the\s+)?time-?out|before\s+(?:sedation|insertion|induction"
    r"|the\s+procedure|starting))\b", re.A | re.I)
# C2: the words of an attachment or an enclosed copy, beside sections.ANOTHER_OCCURRENCE_HEAD's ("Attached Report",
# "Enclosed Records", "Scanned Outside Pages")
_PO_RECORD_WORDS = re.compile(r'\b(?:attach(?:ed|ments?)|enclos(?:ed|ures?)|scanned|faxed|imported|excerpts?|appended'
                              r'|external|received)\b', re.A | re.I)


@_po_cached
def _po_called_off(text: str) -> bool:
    """C1 (cycle 2): whether the document says that its procedure was called off, cancelled or not done today in the
    words of _PO_CALLED_OFF - read anywhere in the text and only to hold PO-1 (a statement of another encounter written
    the same way holds too). Read once per text (a cache this module's ROUTING_CACHE_MODULES entry clears)."""
    return _PO_CALLED_OFF.search(text) is not None


def _po_under_another_record(text: str, pos: int) -> bool:
    """C2 (cycle 2): whether the nearest heading-like line above the line of ``pos`` - a short line (at most 60
    characters) with a letter and no sentence end, as sections.under_another_occurrence reads one, a closing colon
    allowed - names another occurrence's record (sections.ANOTHER_OCCURRENCE_HEAD: "Previous Report", "Outside Report")
    or an attachment (_PO_RECORD_WORDS: "Attached Report"), read back from the line's start as far as a section's
    heading may stand (sections.HEADING_REACH_LINES lines and HEADING_REACH_CHARS characters; under_another_occurrence
    reads only OCCURRENCE_HEAD_LINES lines and OCCURRENCE_HEAD_REACH characters). False when no such line is found
    there. Read once per line of a text (_po_record_line), whatever the number of acts and items asking."""
    return _po_record_line(text, text.rfind('\n', 0, pos) + 1)


def _po_line_cached(fn):
    """``fn`` cached per (text, line) as functools.lru_cache(maxsize=1024), which jobs.release_routing_caches clears
    with this module's other caches."""
    import functools  # local, as in _po_cached
    return functools.lru_cache(maxsize=1024)(fn)


@_po_line_cached
def _po_record_line(text: str, line_start: int) -> bool:
    """C2 for the line starting at ``line_start`` (_po_under_another_record). Bounded: at most HEADING_REACH_LINES
    lines and HEADING_REACH_CHARS characters read back."""
    lo = max(0, line_start - gi_sections.HEADING_REACH_CHARS)
    end = line_start - 1
    for _ in range(gi_sections.HEADING_REACH_LINES):
        if end <= lo:
            return False
        start = text.rfind('\n', lo, end) + 1
        line = text[max(start, lo):end].strip()
        if line and len(line) <= 60 and line[-1] not in '.;!?' and any(c.isalpha() for c in line):
            return bool(gi_sections.ANOTHER_OCCURRENCE_HEAD.search(line) or _PO_RECORD_WORDS.search(line))
        end = start - 1
    return False


def _po_done_in_body(u: reconcile.Unresolved, inventory, text: str) -> bool:
    """P1 (PO-1's positive evidence): an act of the item's own service - for an act item, that act - that the
    documented-service reader reads performed by an act predicate of its own (_PO_ACT_PREDICATE: never only from a
    title, a procedure line, a box or a field), with a passage in the text under no line naming another occurrence's
    record (sections.under_another_occurrence: "Outside records"), nor - cycle 2, C2 - under a heading-like line further
    up naming another occurrence's record or an attachment (_po_under_another_record: "Previous Report" 9 lines up,
    "Attached Report"). False without an inventory or the item's service."""
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
               and not _po_under_another_record(text, ev.start)
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
    lay = gi_structure.clinical_layout(text)
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


def _service_questions(inventory, proposals, context=None, answered=()) -> list[ClarificationSpec]:
    """Every materially necessary question about a documented service, asked together and once: its missing
    documentation (a sparse visit note's setting, status and basis together) and each conflict in the record. A
    question a proposal of the same family already asks is not asked again; nor is one a reviewer-confirmed finding
    answers (``answered``: (family, fact) pairs, _Confirmations.answered) - answering it at one scope never makes it
    asked again at another."""
    asked = {(c.family, c.fact) for p in proposals for c in p.clarifications} | set(answered)
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
            day: Optional[date], inventory=None, *, dated: bool = True,
            extra: Sequence[EvidenceSpan] = ()) -> _Selection:
    """One code read from ``group`` (its proposer's entries for it). ``extra``: another proposer's exact passages for
    the same code (an independent participant's first reading, _Harness.merge): read with the group's, each passage
    once and all of them in document order, so the same passages give the same reading whoever cited which; they add
    no unit and no display. Empty, the reading is exactly the group's (I1)."""
    code = group[0].code
    code_kind, scope_reason = checks.code_scope(code)
    kept, dropped = checks.exact_evidence([span for item in group for span in item.evidence] + list(extra), text, pages)
    if extra:
        kept = tuple(sorted(kept, key=lambda span: (span.start, span.end)))
    displays = dict.fromkeys(item.display for item in group if item.display)
    selection = _Selection(code=code, units=len(group), display=' | '.join(displays), code_kind=code_kind,
                           scope_reason=scope_reason, evidence=kept, dropped=dropped, family=family_for_code(code),
                           group=tuple(group))
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
                and not _listing_contradicted(code, found.service) \
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
    # Completion repair (builder Q1): an act the document itself states not done today - failed, planned, historical,
    # still to be done - is no doubt to ask about: the code is excluded with the passage that says so, reinstatable,
    # whoever proposed it (_stated_not_done; every other reading keeps the hold above)
    stated = _stated_not_done(code, found, own, text, day, pages) if found is not None else ()
    if stated:
        found = _not_done_match(code, found, stated)
    if found is not None:
        found = _another_roles_hold(code, found)

    def today(span):
        return _today_passage(text, span, day)

    def report_family(span):
        # the study's own report speaks for the study only where a report states what was done, found or concluded:
        # never its header, its signature or another line no such section heads (OWN_REPORT_SECTIONS); and only where
        # the document reports that study alone and the passage states nothing else (attr-F3: never another study's
        # result in a combined report, never a biopsy taken after the study)
        layout = gi_structure.clinical_layout(text)
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
        if found.state in checks.POSITIVE and supported.status in ('warn', 'fail') and found.reason != 'own_passage' \
                and legacy not in checks.EM_FAMILIES:
            # P2 READ-HOLD, R3 7.5.1: the narrow evidence hold (_passages_elsewhere), for a procedure code. Never over
            # the own-passage release, whose passage the inventory reads no act in by definition and which its own gates
            # already placed (_own_passage_may_stand: D1, D4, D5); never for an office visit, whose own plan and history
            # sentences are documentation of that visit ("Return in three months.": validation:6's pinned reading)
            # a passage another time's or denied by a cue of its OWN: a time read only from the section it stands in is
            # the layout's reading, not the passage's (round 4 PA's "one cause"; a numbered "3. Upcoming procedures"
            # item makes today's "4. 6 mm sigmoid polyp removed with cold snare." planned: test_repairs_r4_sections)
            own_time = {(r.start, r.end) for r in own if r.status in checks.NEGATIVE and not _section_time(r)}
            elsewhere = _passages_elsewhere(kept, own_time, found, inventory, code, text)
            if elsewhere:
                found = replace(found, state='uncertain', reason='readings_disagree', question=(
                    f'Confirm whether {code} is supported: none of the passages it cites shows what was done on the date '
                    'of service.'),
                    detail=f'{found.detail} But none of the passages the code cites shows it: {elsewhere} Held for the '
                           'reviewer, not excluded.')
        note = _undecided(outcome, found, supported, kept)
        outcome = _not_done_outcome(found, stated) if stated else _service_outcome(found)
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


def _passages_elsewhere(kept: Sequence[EvidenceSpan], another_time: set, found: reconcile.Match, inventory,
                        code: str = '', text: str = '') -> str:
    """P2 READ-HOLD, R3 7.5.1 (the narrow evidence hold): why EVERY passage the code cites is about something other
    than the matched service today - each lies in another documented service's evidence or acts (_elsewhere), or in
    another service's scope and outside the matched service's, or is read by the routing-era reader as planned,
    historical, negated or cancelled by a cue of its own (``another_time``: never by its section alone), or states
    another act of the kinds ``code`` accounts for that the documented-service reader reads NOT done - failed, in doubt,
    planned - and no act of those kinds done (_another_act_of_its_kind) - or '' when one is not. Read only where the
    documented service reads the code as performed and the passages' support is warn or fail; the code is then held,
    never excluded. A passage of the matched service's own (its procedure-level statement) is never elsewhere: such a
    code stays as it is (R3 open question 1, the narrow choice). Bounded: one pass over the inventory's services per
    passage."""
    if inventory is None or not kept:
        return ''
    own = found.service
    why = []
    for span in kept:
        if (span.start, span.end) in another_time:
            why.append(f'{reconcile.quote(span, 80)} reads as another time or a denial')
            continue
        other_act = _another_act_of_its_kind(span, found, code, text)
        if other_act is not None:
            why.append(f'{reconcile.quote(span, 80)} states another {reconcile.act_label(other_act.kind)}, which the '
                       f'document does not give as done ({other_act.status})')
            continue
        stand_in = checks.Reading('performed', (), 'evidence', span.text, span.start, span.end)
        if _elsewhere(stand_in, found, inventory):
            why.append(f'{reconcile.quote(span, 80)} is another documented service\'s')
            continue
        inside_own = own.scope_end > own.scope_start and own.scope_start <= span.start and span.end <= own.scope_end
        if not inside_own and any(s.id != own.id and s.scope_end > s.scope_start and s.scope_start <= span.start
                                  and span.end <= s.scope_end for s in inventory.services):
            why.append(f'{reconcile.quote(span, 80)} lies in another documented service')
            continue
        return ''
    return '; '.join(why) + '.'


def _another_act_of_its_kind(span, found: reconcile.Match, code: str, text: str = ''):
    """Completion repair (builder Q1; F4, refutation cycle 3 C3-3-4 and cycle 4 C4-2-3): the act of a kind ``code``
    accounts for that the passage ``span`` states and the documented-service reader reads NOT done - failed, in doubt,
    planned, another provider's ("Possibly the ring was also dilated with a Savary bougie.", "Dilation with a Savary bougie
    failed.") - where the passage shows no act of those kinds done; else None. Such a passage is about another act of its
    kind than the one the matched service documents as done, so a code it alone cites is held by the evidence hold, never
    READY on the done act it does not show (the base read Corti's bougie-dilation code READY there, and once a
    participant's code of the same passages reached review, both dilation codes were held as competing for the one
    balloon dilation)."""
    profile = reconcile.catalogue.code_profile(code) if code else None
    if profile is None or not profile.covers:
        return None
    kinds = set(profile.covers) | ({'tattoo', 'injection'} if {'tattoo', 'injection'} & set(profile.covers) else set())

    def shows(act) -> bool:
        return any(span.start < ev.end and ev.start < span.end for ev in act.evidence)

    acts = [a for a in found.service.acts if a.kind in kinds and shows(a)]
    if any(a.status == 'performed' for a in acts):
        return None
    # only an act its own sentence states otherwise: never one named and nothing said of it, one read in an indication,
    # one whose time is its section's alone (_time_from_section - engine @4's time_plan triage keeps the procedure line's
    # act READY there), a form's field or box reading ("Biopsy taken:   Yes   No" printed with no mark beside the
    # field's own "Biopsy taken: Yes"), or an act listed on the procedure line ("Procedure: Colonoscopy with cold snare
    # polypectomy for a positive FIT last month.", whose time is the test's: routing:0) - each measured holding a code
    # the base read READY (tests/test_repairs_r3_forms_pdf.py, tests/test_repairs_r3_time.py)
    return next((a for a in acts if a.role in reconcile.OWN_ROLES and not _says_nothing(a.status, a.cues)
                 and not _time_from_section(a.cues) and (a.cues[:1] != (gi_services.INDICATION_READING,))
                 and not (a.cues and a.cues[0].startswith(('field:', 'box:')))
                 and not any(_on_a_procedure_line(text, ev.start) for ev in a.evidence)), None)


def _on_a_procedure_line(text: str, pos: int) -> bool:
    """Whether ``pos`` lies on a procedure field line ("Procedure: ...", services.PROCEDURE_FIELD): the line that lists
    what the report's procedure was. With no text, never."""
    if not text:
        return False
    start = text.rfind('\n', 0, pos) + 1
    end = text.find('\n', pos)
    return bool(gi_services.PROCEDURE_FIELD.match(text[start:end if end >= 0 else len(text)]))


def _today_passage(text: str, span, day: Optional[date]) -> bool:
    """A passage that states something of this encounter in its own sections: none of them a plan, history or
    indication section (NOT_TODAY_SECTIONS), and not read as about another time, planned, denied or cancelled."""
    layout = gi_structure.clinical_layout(text)
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
      except where the inventory reads that same passage as the very act the code accounts for (routing reads it inside
      a plan or history section, "3. Upcoming procedures" over "4. Polyp removed by EMR at a tertiary center.", or by a
      cue of its own clause, "Last colonoscopy: 9 mm polyp removed with hot snare.") or, for a code matched to a service
      with no act, as that service's own statement (an attached prior report's title): the two readers then disagree
      about that passage's own time, so it holds, never excludes (_another_time_on_the_act; P2 READ-HOLD, R8 D9, D6,
      D10);
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
            old.state == 'not_performed' and own and _another_time_on_the_act(doubt, found, text))
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
            and not _elsewhere(old.decisive, found, inventory) and _states_unread_act(old.decisive, found, code, text) \
            and _own_passage_may_stand(old.decisive, found, code, text, inventory):
        # The documented service is performed and the code's own passage states its act (the routing-era reader reads
        # it performed: a form row, a check box, a phrasing this reader does not parse); the inventory does not read
        # that act at all - it neither denies it nor gives the passage to another service - so the code's own reading
        # stands, and says so. Only where nothing in that passage says the act was not done (_own_passage_may_stand:
        # P2 READ-HOLD); otherwise the inventory's act_missing hold stays.
        included = _passage_act_included(old.decisive, found, code, text)
        if included:
            # Harness repair 2026-11-05, refutation own-4: the act the passage states is part of another documented
            # act, as the reconciliation reads such an act (reconcile._bundled): "a 17 mm flat lesion was lifted by a
            # submucosal injection of saline" beside the lesion's EMR is the EMR's lift, so 45381 is held as the
            # one-sentence form is (act_included), never released READY on the routing-era reading
            what = ' or '.join(reconcile.act_label(k) for k in reconcile.catalogue.code_profile(code).covers)
            return replace(found, reason='act_included',
                           detail=f'The {reconcile.service_label(found.service)} is documented as '
                                  f'{found.service.status}; the {what} {code} accounts for, read from its own passage '
                                  f'by the routing-era reader ({checks.cite(old.decisive)}), is part of another '
                                  f'documented act: {included} No separate {what} is documented for this code.',
                           question=f'The {what} documented ({checks.cite(old.decisive)}) is part of another procedure '
                                    f'documented with it. Was a separate {what} performed on the date of service?')
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


def _listing_contradicted(code: str, service) -> bool:
    """Whether ``service`` documents an act ``code`` accounts for as a procedure-line listing the report contradicts
    (services.listed_contradicted; completion repair, builder A). The inventory holds that listing in doubt: it reads
    the act neither done nor not done, so it never agrees with the routing-era reading of the code's own passage that
    the act was not done, and the code is held, never newly excluded through it (cux-hold R8 D3 N17: "The polyp was not
    removed." cited for 45385 under "Procedure: Colonoscopy with hot snare polypectomy" stays held, as the base read it).
    """
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    return any(a.kind in kinds and gi_services.listed_contradicted(a) for a in service.acts)


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
    section = gi_structure.clinical_layout(text).section_at(pos)
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
    section = gi_structure.clinical_layout(text).section_at(pos)
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


def _another_time_on_the_act(doubt: checks.Reading, found: reconcile.Match, text: str) -> bool:
    """The third hold arm of _second_opinion (P2 READ-HOLD, R8 D9 with D6's and D10's engine halves): the routing-era
    reading of the code's own passage is planned or historical, by its section (_section_time, as before) or by a cue
    of its own clause ("historical: Last", "historical: 2026-09-02 is before the service date", "planned: tomorrow") -
    never a clause cue in a passage whose own words say today ("The polyp seen at the prior colonoscopy was removed
    with a hot snare today.": the inventory read its "today") - and the passage is what the matched status rests on:
    the evidence of a matched act (_on_matched_act), or, for a match with no act (a base or a service code), the
    service's own statement (_on_service_statement). Hold-only: the code is held with both readings, never excluded;
    an unrelated historical passage still never decides against a current service."""
    if doubt.status not in ('planned', 'historical') or doubt.start is None:
        return False
    if not _section_time(doubt) and gi_services.TODAY_WORDS.search(text, doubt.start, doubt.end):
        return False
    return _on_matched_act(doubt, found) or (not found.acts and _on_service_statement(doubt, found))


def _on_service_statement(reading: checks.Reading, found: reconcile.Match) -> bool:
    """Whether the passage overlaps the matched service's own evidence (its statement of performance, its report
    title)."""
    return any(reading.start < ev.end and ev.start < reading.end for ev in found.service.evidence)


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
    statement of performance, a performed act, or a completion read as complete), never of anything it denies.

    Harness repair 2026-11-05, refutation round 3: main's rule, exactly. The stage-3 exception (another act's denial in
    the passage set aside where the code's own act reads as performed there) was refuted in three rounds - it believed
    an act done "at the referring facility", "elsewhere", "historically" or "unsuccessfully", and two narrowings did not
    close it - and is dropped under the two-cycle rule; 88d9db32's 45380 is held again (HARNESS.md, round 3)."""
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
    # lead integration L3 (cux-lead.json; P1 rule 2): the act mentions services._acts_in reads, not the raw ACTS
    # patterns - an attributive act compound ("biopsy-proven Barrett esophagus", "a biopsy-confirmed adenoma")
    # presupposes an earlier act and states none today, so it never stands for the act this code accounts for
    return any(kind in kinds for kind, _, _ in gi_services._acts_in(text, reading.start, reading.end))


def _passage_act_included(reading: checks.Reading, found: reconcile.Match, code: str, text: str) -> str:
    """Why the act of ``code``'s kinds that its own passage names is part of another act ``found.service`` documents,
    as the reconciliation reads a documented act of that kind there (reconcile._bundled: the lift injection of a lesion
    the service resects by EMR or ESD, a resection's own snare, a clip), or ''. Read only on the own-passage release,
    whose act the inventory does not read by definition (refutation own-4)."""
    profile = reconcile.catalogue.code_profile(code)
    if profile is None or reading.start is None:
        return ''
    passage = text[reading.start:reading.end]
    span = gi_services._span(text, reading.start, reading.end)
    for kind, pattern in gi_services.ACTS:
        if kind in profile.covers and pattern.search(passage):
            sites = tuple(dict.fromkeys(name for name, _, _, _ in gi_services._anatomy_in(text, reading.start,
                                                                                            reading.end)))
            why = reconcile._bundled(found.service, gi_services.Act(id='', service=found.service.id, kind=kind,
                                                                    status='performed', role='physician',
                                                                    anatomy=sites, evidence=(span,)))
            if why:
                return why
    return ''


def _own_passage_may_stand(reading: checks.Reading, found: reconcile.Match, code: str, text: str, inventory) -> bool:
    """Whether the routing-era reading of the code's own passage may stand for an act the inventory does not read (the
    own-passage release), package P2 READ-HOLD (R8 section 1.3). Hold-only: a gate that fails leaves the inventory's
    act_missing hold (held with its question, never excluded).
    - D1 (candidate_rb): only a 'performed' reading - never 'incomplete' ("was attempted", "was unsuccessful", which the
      release had turned into the service's 'performed') - and never a passage that states the act failed, was abandoned
      or only attempted, or yielded nothing (cues.UNDONE_ACT: "Hot snare polypectomy failed.", "no tissue was
      obtained"). Never a worded reading only (candidate_ra): the pinned "Cecal biopsies x2." is read by its section
      alone and still stands.
    - D4: only where the documented-service reader's own placement rule (services._family_for_act, with no report
      part) puts every act kind of the code the passage names, at every anatomy it names, in the matched service's
      family alone among the services documented as done or in doubt today. Fail-closed: an act no one service owns
      ("Biopsies were taken with cold forceps." in a combined EGD and colonoscopy report) is held for every family's
      code, the correct one too.
    - D5: never inside a non-physician role part (_in_another_roles_part: a pathology, nursing, anesthesia, radiology or
      facility entry). Not the narrower-looking repairs (the service's scope, or no section-default cue): both break
      the pinned "Cecal biopsies x2." control."""
    if reading.status != 'performed':
        return False
    if gi_cues.UNDONE_ACT.search(text, reading.start, reading.end):
        return False
    if _in_another_roles_part(reading, text):
        return False
    return _placed_in_matched_family(reading, found, code, text, inventory)


def _in_another_roles_part(reading: checks.Reading, text: str) -> bool:
    """D5: whether the passage starts inside a part services.parts cuts for another role than the physician's (a
    pathology, nursing, anesthesia, radiology or facility entry: services.ROLE_HEADINGS), whose acts reconcile already
    never counts. Read only on the own-passage release path (one parts() reading per such passage)."""
    return any(p.role != 'physician' and p.start <= reading.start < p.end for p in gi_services.parts(text))


def _placed_in_matched_family(reading: checks.Reading, found: reconcile.Match, code: str, text: str, inventory) -> bool:
    """D4: whether services._family_for_act places each act kind of ``code`` that the passage names, at each anatomy
    region the passage names (none named: no region), in found.service.family alone; the candidate owners are the
    documented non-E/M services read as performed, incomplete or uncertain (a planned or earlier procedure owns no act
    of today's report). Bounded: the passage's acts and anatomy, once each."""
    if inventory is None:
        return True
    profile = reconcile.catalogue.code_profile(code)
    covers = set(profile.covers) if profile is not None else set()
    passage = text[reading.start:reading.end]
    kinds = [kind for kind, pattern in gi_services.ACTS if kind in covers and pattern.search(passage)]
    regions = {region for _, region, _, _ in gi_services._anatomy_in(text, reading.start, reading.end)} or {''}
    present = list(dict.fromkeys(s.family for s in inventory.services if s.family != 'gi.office_em'
                                 and s.status in ('performed', 'incomplete', 'uncertain')))
    return bool(kinds) and all(gi_services._family_for_act(kind, region, '', present) == found.service.family
                               for kind in kinds for region in regions)


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
    if _status_signal(reading, passage, code) and (
            (service.scope_start <= reading.start and reading.end <= service.scope_end)
            or (service.family not in checks.EM_FAMILIES and inventory is not None
                and not _other_named(reading, found, passage, inventory, routing))):
        return True
    profile = reconcile.catalogue.code_profile(code)
    kinds = set(profile.covers) if profile is not None else set()
    return any(kind in kinds and pattern.search(passage) for kind, pattern in gi_services.ACTS)


def _status_signal(reading: checks.Reading, passage: str, code: str = '') -> bool:
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
    if (reading.status in ('negated', 'cancelled') or any(cue.startswith(DOUBT_PREFIX) for cue in reading.cues)) \
            and _denies_an_act_of(code, passage):
        # P2 READ-HOLD, R8 D3: the routing-era reader's own denial, cancellation or unresolved negation of a passage that
        # states an act the code accounts for, or an act of no named kind ("No polyps were removed.", "The polyp was
        # not removed.", "We did not remove the polyp."): a status of its own, so a denial in the matched service's own
        # report holds with both readings instead of "not about the documented colonoscopy, so it does not decide".
        # Never a denial of a finding ("No gastric ulcer or mass was identified.") or of another act ("so no clip was
        # needed" cited for a snare code: h4-04's 43251 stays READY)
        return True
    return any('box' in cue.lower() for cue in reading.cues)


def _denies_an_act_of(code: str, passage: str) -> bool:
    """Whether a passage read as denied states an act ``code`` accounts for (an act kind of its profile's covers,
    services.ACTS), or an act of no named kind by its predicate (a participle, services.ACT_VERB / BARE_PARTICIPLE, or a
    denied act verb, cues.DENIED_ACT_VERB). A passage naming only another act kind, or no act at all, is no status of
    this code's act (P2 READ-HOLD, R8 D3)."""
    profile = reconcile.catalogue.code_profile(code)
    covers = set(profile.covers) if profile is not None else set()
    named = {kind for kind, pattern in gi_services.ACTS if pattern.search(passage)}
    if named:
        return bool(named & covers)
    return bool(gi_services.ACT_VERB.search(passage) or gi_services.BARE_PARTICIPLE.search(passage)
                or gi_cues.DENIED_ACT_VERB.search(passage))


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
    rows = endoscopic_rows((s.code, s.evaluation.reference.pfs if s.evaluation else None) for s in active)
    # A reinstated procedure holds an E/M as a selected one does (review:0). On a procedure day the E/M is held
    # already; otherwise record which reinstatements would hold which E/Ms, for review to gate approval on.
    reinstatable = [s for s in selections if s.excluded and s.evaluation is not None and _procedural(s)]
    visits = [s for s in selections if s.family in checks.EM_FAMILIES and s.evaluation is not None
              and checks.separate_em_statement(s.evaluation.finding) is None]
    gate = bool(reinstatable and visits and not (labels or possible_labels))
    members = [(s.code, s.family, s.evaluation.match.service if s.evaluation is not None and s.evaluation.match is not None
                else None) for s in active]
    bases = base_included(members)
    within = base_within(members)
    return _Encounter(bases_included=bases, bases_within=within, provider=provider, context=context, sources=sources,
                      date_state=date_state,
                      pfs_source=pfs_source, active_pfs=rows, procedure_labels=tuple(dict.fromkeys(labels)),
                      possible_labels=tuple(possible_labels),
                      global_days=_global_days(procedures + possible, pfs_source, sources, date_state.value),
                      if_reinstated=tuple((s.code, s.profile.label if s.profile.supported else '')
                                          for s in reinstatable) if gate else (),
                      gated_visits=tuple(s.code for s in visits) if gate else ())


# --- the combination rules the review overlay re-applies over the current decisions (CORE-UX-DESIGN.md 4) -----------
# One implementation each: the engine reads them over its own active selections (_encounter, _proposal), and the
# read-time review overlay (studio.validation.review_view) over the effective set a reviewer's decisions leave - a
# second copy of either would drift from this one.

def base_included(members) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Engine @4's base rule. ``members``: (code, family, the documented service it was matched to or None) of every
    ACTIVE code, in order. A family's base (diagnostic) code matched to a documented service is held, never excluded,
    beside another active code of its family matched to the same service that accounts for one of its interventions
    (its profile covers an act), or when that service documents a performed, reportable act no profile rule bundles:
    (base code, the other codes - or, with none, the labels of those acts), in member order."""
    bases = []
    for index, (code, family, service) in enumerate(members):
        profile = reconcile.catalogue.code_profile(code)
        if profile is None or not profile.base or service is None:
            continue
        others = tuple(other for position, (other, other_family, other_service) in enumerate(members)
                       if position != index and other_family == family
                       and (reconcile.catalogue.code_profile(other) or reconcile.catalogue.CodeProfile('')).covers
                       and other_service is not None and other_service.id == service.id)
        entry = reconcile.catalogue.entry(family)
        reportable = [a for a in service.acts if a.status == 'performed' and a.role in ('physician', 'unknown')
                      and entry is not None and a.kind in entry.acts and not reconcile._bundled(service, a)]
        # Completion repair (2026-11-06, F5; builder A): an intervention the procedure line lists and the report states
        # only in doubt ("It is unknown whether hot snare polypectomy was performed.") may have been done, and then this
        # base code is included in it: held beside it, never final alone (never excluded either)
        # Full-suite repair (builder A): so too a listed removal the report contradicts (every lesion it records stated
        # not removed today, services.listed_contradicted). The listing and the report disagree, and that rule only
        # holds: the base code stays held beside it as the base read it (cux-hold R8 D3 N17), never released READY
        doubted = [a for a in service.acts if (gi_services.listed_in_doubt(a) or gi_services.listed_contradicted(a))
                   and a.role in ('physician', 'unknown')
                   and entry is not None and a.kind in entry.acts and not reconcile._bundled(service, a)]
        if others or reportable or doubted:
            bases.append((code, others or tuple(sorted({reconcile.act_label(a.kind) for a in reportable}
                                                       | {reconcile.act_label(a.kind) + (' (stated in doubt)'
                                                                                         if gi_services.listed_in_doubt(a)
                                                                                         else ' (listed, stated not done)')
                                                          for a in doubted}))))
    return tuple(bases)


def base_within(members) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """P2 READ-HOLD, R8 D15 (r1 missed-14), the second base rule, over the same ``members`` as base_included: a base code
    whose matched documented service is the endoscopic portion of another (DocumentedService.included_in: an EGD inside
    an upper EUS) is held, as the base rule holds a base beside a same-family intervention: (base code, the codes of the
    active codes matched to that service that include the examination - reconcile's own inclusion test,
    catalogue.includes_examination: an EGD-with-EUS code - or () when that service has no active code at all, the code
    it asks for including the examination, reconcile.inclusion_asks_no_code). No entry - no hold - when the code is no
    base, its service is part of no other, or that service's active codes include no such examination (a sigmoidoscopy
    EUS code: the EGD is a service of its own). Bounded: one pass over the members per base code."""
    held = []
    for index, (code, family, service) in enumerate(members):
        profile = reconcile.catalogue.code_profile(code)
        if profile is None or not profile.base or service is None or not service.included_in:
            continue
        including = [other for position, (other, _other_family, other_service) in enumerate(members)
                     if position != index and other_service is not None and other_service.id == service.included_in]
        if not including:
            held.append((code, ()))
            continue
        codes = tuple(other for other in including if reconcile.catalogue.includes_examination(other, service.kind))
        if codes:
            held.append((code, codes))
    return tuple(held)


def base_within_hold(code: str, family: str, key: str, within: Sequence[str], service) -> tuple[Check, ClarificationSpec]:
    """The services.base_included check and the base_included question of a base code base_within holds (D15): its
    service is the endoscopic portion of an endoscopic ultrasound documented with it (``within``: that service's codes
    that include the examination, possibly none)."""
    service_name = reconcile.service_label(service) if service is not None else 'service'
    coded = f', which {", ".join(within)} {"accounts" if len(within) == 1 else "account"} for' if within else ''
    reason = (f'The documented {service_name} is the endoscopic portion of the endoscopic ultrasound documented with '
              f'it{coded}; that examination is normally included in it, not reported separately (internal profile '
              'rule; NCCI procedure-to-procedure edits are not connected). Held for the reviewer, not excluded.')
    return (Check('services.base_included', 'Diagnostic examination beside its interventions', 'warn', reason,
                  reconcile.SOURCE),
            ClarificationSpec(scope='proposal', fact='base_included', family=family, proposal_key=key, reason=reason,
                              question=f'Is {code} reported separately from '
                                       f'{", ".join(within) or "the endoscopic ultrasound"} for this examination?'))


def base_hold(code: str, family: str, key: str, included: Sequence[str], service) -> tuple[Check, ClarificationSpec]:
    """The services.base_included check and the base_included question of a base code the base rule holds beside
    ``included`` (base_included's other codes or act labels); ``service``: the documented service it was matched to."""
    service_name = reconcile.service_label(service) if service is not None else 'service'
    if all(other[:1].isdigit() for other in included):
        reason = (f'The documented {service_name} has interventions that {", ".join(included)} account for; its '
                  'diagnostic examination is normally included in them (internal profile rule; NCCI procedure-to-'
                  'procedure edits are not connected). Held for the reviewer, not excluded.')
    else:
        reason = (f'The documented {service_name} includes {", ".join(included)}, which this diagnostic code does '
                  'not account for (internal profile rule). Held for the reviewer, not excluded.')
    return (Check('services.base_included', 'Diagnostic examination beside its interventions', 'warn', reason,
                  reconcile.SOURCE),
            ClarificationSpec(scope='proposal', fact='base_included', family=family, proposal_key=key, reason=reason,
                              question=f'Is {code} reported separately from {", ".join(included)} for this examination?'))


COMPETING_CHECK, COMPETING_FACT = 'proposals.competing', 'competing_codes'


def competing_hold(code: str, family: str, key: str, rivals: Sequence[str], service) -> tuple[Check, ClarificationSpec]:
    """The proposals.competing check and the competing_codes question of a code that claims one same documented act as
    ``rivals`` (P-ADMIT2, harness repair 3): CPT Studio does not choose between them, whoever proposed each, so each is
    held for the reviewer, never excluded; a reviewer's rejection of the others releases it (review_view). ``service``:
    the documented service it was matched to. No proposer is named: the question is the same for every origin."""
    service_name = reconcile.service_label(service) if service is not None else 'service'
    codes = checks._join([code, *rivals])
    reason = (f'{codes} are each proposed for one same documented act of the {service_name}. CPT Studio does not '
              'choose between them: each is held for the reviewer, not excluded, until the others are rejected.')
    return (Check(COMPETING_CHECK, 'Codes proposed for the same documented act', 'warn', reason, reconcile.SOURCE),
            ClarificationSpec(scope='proposal', fact=COMPETING_FACT, family=family, proposal_key=key, reason=reason,
                              question=(f'{codes} are proposed for the same documented act. Reject the code or codes '
                                        'the documentation does not support; the one left is then ready for review.')))


def endoscopic_rows(pairs) -> dict:
    """code -> PFS row, of every (code, PFS row or None) pair of an active code that has a row: what the CMS PFS
    endoscopic-family check reads of the other codes (checks.endoscopic_check's ``active``)."""
    return {code: pfs for code, pfs in pairs if pfs}


# The acts a separate-lesion (distinct-procedure) modifier consideration can concern, beside another code's act.
DISTINCT_LESION_KINDS = reconcile.REMOVAL_KINDS + ('biopsy', 'ablation', 'injection', 'tattoo')


def distinct_lesions(service, acts) -> tuple[tuple[str, ...], tuple]:
    """(the documented lesions of ``acts`` - a code's matched acts - sorted; every performed act of ``service`` on
    another documented lesion that a separate-lesion modifier can concern, DISTINCT_LESION_KINDS) - the reading
    _service_considerations words and the review overlay's modifier review pairs with the other codes."""
    lesions = tuple(sorted({a.lesion for a in acts if a.lesion}))
    others = tuple(a for a in service.acts if a.status == 'performed' and a.lesion and a.lesion not in lesions
                   and a.kind in DISTINCT_LESION_KINDS)
    return lesions, others


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


def _keys(selections: Sequence[_Selection]) -> list[str]:
    """Each selection's key, in selection order: 'sel:<n>' or 'exc:<n>', counted within its bucket in provider order."""
    counts = {'sel': 0, 'exc': 0}
    keys = []
    for selection in selections:
        prefix = 'exc' if selection.excluded else 'sel'
        keys.append(f'{prefix}:{counts[prefix]}')
        counts[prefix] += 1
    return keys


def _keyed(selections: Sequence[_Selection], encounter: _Encounter, harness: Optional['_Harness'] = None,
           keys: Optional[Sequence[str]] = None,
           answers: Optional[Mapping[int, '_Answers']] = None) -> tuple[ProposalAssessment, ...]:
    """Selected-bucket proposals first, then excluded; keys count within each bucket in provider order. ``harness``: the
    independent participants' merge, whose contradiction checks a decidable proposal carries (HARNESS.md 5); None adds
    nothing. ``keys`` and ``answers`` (by selection index): the keys these selections have without any reviewer-confirmed
    finding, and the confirmed answers each proposal reads (_Confirmations.apply); None gives the keys above. With a
    harness, each decidable proposal records its identity (_identity)."""
    keys = _keys(selections) if keys is None else keys
    selected, excluded = [], []
    for index, selection in enumerate(selections):
        bucket = excluded if selection.excluded else selected
        extra = harness.disagreements(selection) if harness is not None else ()
        bucket.append(_proposal(selection, keys[index], encounter, extra, (answers or {}).get(index),
                                identify=harness is not None))
    return tuple(selected + excluded)


def _identity(s: _Selection, enc: _Encounter) -> str:
    """The identity of a decidable proposal's own reading (support['identity']): the sha256 of its code, family, profile
    version, cited passages, units and the context values a decision on it depends on - its fingerprint without its
    checks and status, which the other proposals and the reviewer-confirmed findings move. A confirmation of one of its
    questions is bound to it (HARNESS.md 11.3, 12.5), never to the key it holds: keys count in selection order, and
    another reading, a peer review or a new answer can select a code ahead of it."""
    release = enc.pfs_source.release if enc.pfs_source else ''
    pctc = checks.pctc_consideration(s.code, s.evaluation.reference.pfs, release, _billing(enc.context))
    return sha256_json({'code': s.code, 'family': s.family, 'profile_version': s.profile.version,
                        'evidence': sorted(span.text for span in s.evidence),
                        'context': _relevant_context(s.family, enc, bool(pctc)), 'units': s.units})


def _proposal(s: _Selection, key: str, enc: _Encounter, extra: Sequence[Check] = (),
              answers: Optional['_Answers'] = None, *, identify: bool = False) -> ProposalAssessment:
    """``extra``: checks added after every rule's own (an independent participant's contradiction, which never changes
    the status); like every check, they are part of the fingerprint. ``answers``: the reviewer-confirmed answers to the
    required-fact questions this proposal reads (HARNESS.md 11.3; a confirmed status is in its evaluation already).
    ``identify``: record support['identity'] (_identity), what a confirmation of a question of this proposal is bound
    to - only while an independent participant is configured, so with none the result is unchanged (I1)."""
    if s.evaluation is None:
        return _excluded_early(s, key, enc.provider)
    finding, outcome, ref = s.evaluation.finding, s.evaluation.outcome, s.evaluation.reference
    profile, name, day = s.profile, checks.service_name(s.profile, s.code), enc.date_state.value
    release = enc.pfs_source.release if enc.pfs_source else ''
    m, supported = s.evaluation.match, s.evaluation.support
    told = s.evaluation.confirmed  # a reviewer-confirmed status, read in place of the readers' hold
    states = checks.required_fact_states(profile, finding, enc.context)
    used: list[_Answer] = []  # the reviewer-confirmed answers this proposal reads (HARNESS.md 11.3)
    if answers is not None and answers.facts:
        # a confirmed value stands only where the readers leave the fact missing or in conflict: never over a reading
        states = tuple(answers.state(state) for state in states)
        used = [answers.facts[state.name] for state in states if state.confirmed]
    if told is not None:
        used.insert(0, told)
    # a confirmed fact the readers read as an incomplete procedure gives a performed service their incomplete result:
    # the incomplete check, the modifier 52/53 consideration, the status worded incomplete (refutation round 1, EV-4)
    short = next((answer for answer in used if answer.short), None) if outcome.state == 'performed' else None
    if told is not None:
        status_found = checks.confirmed_status_check(told.performed, told.status, told.words, told.quoted,
                                                     s.evaluation.held)
    else:
        status_found = checks.status_check(outcome, name) if m is None else _service_status_check(m, s.evaluation.note)
    if short is not None:
        note = checks.confirmed_incomplete_note(short.fact, short.value, short.words)
        status_found = replace(status_found, detail=f'{status_found.detail} {note}')
    found: list[Check] = [checks.scope_check(s.code_kind, s.scope_reason),
                          *checks.evidence_checks(s.evidence, s.dropped),
                          checks.routing_check(profile, finding), status_found]
    if supported is not None:
        found.append(reconcile.support_check(supported))
    if s.evaluation.placed is not None:
        found.append(s.evaluation.placed)
    clarifications: list[ClarificationSpec] = []
    considerations: list[str] = []
    if short is not None:
        found.append(checks.confirmed_incomplete_check(short.fact, short.value, short.words, short.quoted, short.short))
        considerations.append(checks.incomplete_consideration(s.code, ref.pfs, release))
    elif outcome.state == 'incomplete':
        found.append(checks.incomplete_check(outcome))
        considerations.append(checks.incomplete_consideration(s.code, ref.pfs, release))
    if m is not None:
        considerations += _service_considerations(s, m)
    included = dict(enc.bases_included).get(s.code)
    if included and not s.excluded:
        held, question = base_hold(s.code, s.family, key, included, m.service if m else None)
        found.append(held)
        clarifications.append(question)
    within = dict(enc.bases_within).get(s.code)
    if within is not None and not included and not s.excluded:
        # P2 READ-HOLD, R8 D15: the base code of a service read as the endoscopic portion of another (base_within)
        held, question = base_within_hold(s.code, s.family, key, within, m.service if m else None)
        found.append(held)
        clarifications.append(question)
    if s.competes and not s.excluded:
        held, question = competing_hold(s.code, s.family, key, s.competes, m.service if m else None)
        found.append(held)
        clarifications.append(question)
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
    if not s.excluded:
        exclusion = ''
    elif told is not None:
        exclusion = checks.confirmed_exclusion(told.status, told.words, told.quoted)
    else:
        exclusion = _service_exclusion(m) if m is not None else checks.exclusion_reason(outcome, name)
    context_values = _relevant_context(s.family, enc, bool(pctc))
    support = _support_json(m, supported, s.origin)
    if s.cited_by:
        # item 2 (builder Q1): who cited each of its passages, in evidence order - with the support's 'supporting' and
        # 'unrelated' indices, the evidence report of a proposer whose passages are about another act. Operator-only
        # diagnostics (the participants' names stay out of every customer surface, as support['proposed_by'] does)
        support = {**support, 'provenance': [{'start': start, 'end': end, 'by': list(by)}
                                             for start, end, by in s.cited_by]}
    if s.competes and not s.excluded:
        support = {**support, 'competes': list(s.competes)}  # what review_view releases the hold by (P-ADMIT2)
    if used:
        # what a decision rests on: the confirmed facts, their values and passages (a decision made on one confirmed
        # reading never carries to another), and in the record the confirmations read
        context_values = {**context_values, 'confirmed': [answer.basis() for answer in used]}
        support = {**support, 'confirmed': sorted({i for answer in used for i in answer.ids})}
    if identify:
        support = {**support, 'identity': _identity(s, enc)}  # what a confirmation of a question of its is bound to
    return ProposalAssessment(
        key=key, bucket='excluded' if s.excluded else 'selected', code=s.code, code_kind=s.code_kind,
        family=s.family, profile_version=profile.version, status=status,
        exclusion_reason=exclusion, reinstatable=s.excluded,
        provider_display=s.display, evidence=s.evidence,
        rationale=rationale.selected_rationale(provider=(f'{enc.provider} in a second review limited to the '
                                                         'unresolved documented service'
                                                         if s.origin == 'second_review'
                                                         else _participant_names(s.proposers)
                                                         if s.origin == 'participant' else enc.provider),
                                               units=s.units, evidence_count=len(s.evidence),
                                               profile=profile, detected=finding is not None,
                                               outcome=replace(outcome, state='incomplete') if short else outcome,
                                               facts=_documented_facts(finding, states, m),
                                               entered=_entered_facts(states),
                                               lead=s.lead if s.origin == 'participant' else '',
                                               status_words=(told.words if told is not None else
                                                             f'on the reviewer-confirmed '
                                                             f'{checks.fact_label(short.fact)}' if short else ''),
                                               confirmed=tuple(answer.sentence() for answer in used
                                                               if answer is not told)),
        checks=tuple(found), modifier_considerations=tuple(considerations), units=s.units,
        fingerprint=_fingerprint(s.code, s.family, profile.version, s.evidence, found, context_values, s.units, status),
        clarifications=tuple(clarifications), support=support)


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
    lesions, others = distinct_lesions(service, m.acts)
    if lesions and others:
        here = '; '.join(reconcile.lesion_words(service, l) for l in lesions)
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


# --- the independent participants (HARNESS.md 5, 11) -----------------------------------------------------------------

PRIMARY = 'corti'  # the proposal provider among the proposers: the API names the three corti, astra and fable
# The phases a participant proposes a code in (HARNESS.md 11.1), as ProviderRun.purpose names its runs.
INDEPENDENT, PEER_REVIEW = 'independent', 'peer_review'
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
# A participant's service at this encounter that coding must account for (harness@1 integration owner, 2026-11-01): one
# performed, and one started and not completed as intended.
MISSING_STATUSES = ('performed', 'attempted_incomplete')
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
PEER_POSITION_WORDS = {'supports': 'supports', 'disputes': 'disputes',
                       'cannot_tell': 'cannot tell whether the document supports'}
UNLOCATED = ('none of its quotes was found verbatim in the document text, and a quote that is not found is never '
             'evidence')
# Why a participant's code that no decidable proposal carries, in scope and quoted verbatim, is listed and never added
# as a proposal of its own (refutation round 6, the session's D14; HARNESS.md 5 as amended). The owner's directive of
# 2026-11-03 - "A quotation existing verbatim must not itself establish clinical support." - and the meaning check it
# asked for: on its quote alone such a code was READY and approvable where the quote states a failed, denied, earlier or
# another procedure's act (negation-1..3, ownership-1, -4, time-1), and it recast Corti's base code as included in it
# and cleared CPT Studio's own unresolved-act warning (time-2). Whether a participant's own code may ever be a proposal
# again, and on what reader guarantee, is the owner's question.
PARTICIPANT_NOT_ADDED = ('a quote found verbatim in the document does not by itself show that the coded act was done '
                         "at this encounter, and in this release a participant's code is never added as a proposal of "
                         'its own')  # D14's reason, given by the releases up to b0dc3446c64c; P-ADMIT gives it no more
# HARNESS.md P-ADMIT (owner directive 2026-11-05): why an independent participant's code is not added as a proposal,
# beside the second review's own reasons (_not_added_why), which it shares
PARTICIPANT_PEER_ONLY = ("it was proposed only in peer review, after the participant had seen its peers' conclusions, and "
                         "only a code a participant's first reading proposes, before any peer conclusion is shown to it, "
                         'is checked for admission')
PARTICIPANT_COMPETING = ('independent readings propose different codes for the same documented act ({codes}); CPT '
                         'Studio does not choose between them')
PARTICIPANT_UNREAD = ('the documented-service reading was not available, so no participant code could be checked '
                      'against it')
# P-ADMIT2 (harness repair 3): what CPT Studio's own reading left a participant's code that accounted for nothing it
# read done. RETIRED by the completion repair (owner directive 2026-11-06, items 3 and 5; builder Q1): an explicit code
# is admitted and read by the shared per-code path, so none of these is produced any more - before, they listed a code
# "not documented as done" from a reader's silence (U9: the retained cases' participant codes for "the bolus was
# removed").
# Kept, in CPT Studio's own "could not find" words, for the earlier releases' records and their tests.
PARTICIPANT_NO_SERVICE = 'CPT Studio could not find a service of its family documented as done on the date of service'
PARTICIPANT_NO_ACT = 'CPT Studio could not find the act it accounts for documented as done on the date of service'
PARTICIPANT_LEFT_BY = 'the other proposals'
PARTICIPANT_NOT_SHOWN = 'CPT Studio could not find the act it accounts for in its passages'
PARTICIPANT_NOT_ESTABLISHED = ("CPT Studio's readers could not confirm from its passages the act it accounts for as done "
                               'on the date of service')
# What a participant that gave a code with no entry quoting the document verbatim did: it listed the code and did not
# propose it (refutation round 1, EV-2 = IND-3), said wherever who proposed an alternative is said (refutation round 5,
# the session's D12: "Proposed by Astra" was said of a reading the same assessment says did not propose the code).
LISTED_NOT_PROPOSED = 'with no quote found verbatim in the document, so not proposed'
LISTED_IN_SUMMARY = 8  # codes a participant's summary sentence names; the rest are counted
MODIFIER_SHAPE = re.compile(r'[A-Z0-9]{2}', re.A)  # a modifier as a participant may state one; anything else is counted
OPEN_QUESTION = 'open question'  # the words review.coding_completeness drops a completeness reason for


def _listable(code) -> bool:
    return isinstance(code, str) and 0 < len(code) <= MAX_LISTED_CODE


def participant_listable(code) -> bool:
    """Whether the engine reads a model participant's ``code`` at all: only in a code's shape, a CPT code's or an HCPCS
    Level II code's (participants.peer.code_shaped, the one rule by which a peer request and the owner's trace show a
    code as given; refutation round 4, the session's D9). Any other code a participant gives is counted, as the proposal
    provider's codes that cannot be listed are, and never listed: no proposal, alternative, position or summary names
    it, so it reaches neither the reconciliation, the reference retrieval (recorded for proposals only), the page nor
    the reports (shapes-1: 'W/LES(S)' passed _listable, the proposal provider's rule of 1 to MAX_LISTED_CODE characters,
    and reached all of them as a participant's alternative). The proposal provider's own rule is I1's and does not
    change."""
    from studio.participants.peer import code_shaped  # local: the peer module's rule (it imports the HTTP layer)

    return code_shaped(code)


def participant_unlisted_count(entries) -> int:
    """How many of a model participant's code entries - a reading's codes, or a peer review's additional codes - the
    engine does not read (participant_listable): every entry, a value given twice counted twice, as the proposal
    provider's codes that cannot be listed are counted one per code its answer returned. The one count of them
    (refutation round 5, the session's D13): _Harness states it in participants.summary, and a participant row states it
    re-read from the frozen reading (review.unlisted_count) - the row had counted the assessment's record of the reading,
    which keeps one entry per code value, so '45385-59' given twice was 2 in the summary and 1 on the row."""
    return sum(1 for item in entries if not participant_listable(item.code))


def participant_unlisted_codes(count: int, who: str = 'It') -> str:
    """The sentence for codes a model participant gave that the engine does not read (participant_listable): counted,
    never named or truncated. The proposal provider's (checks.unlisted_codes: "empty, or longer than 10 characters") is
    not true of a participant's 'W/LES(S)', 8 characters in no code's shape."""
    pronoun = 'It is' if count == 1 else 'They are'
    return (f'{who} returned {checks.plural(count, "code")} that cannot be listed: not in the shape of a CPT code '
            '(four digits, then a digit or a capital letter) or of an HCPCS Level II code (a capital letter, then four '
            f'digits). {pronoun} not shown and never truncated.')


# A participant's position on a code only the proposal provider can list - one in no code's shape - when the participant
# gave that very value: its entry is not read (participant_listable), so neither "proposed" nor "did not propose" is
# said of it, and the value is never named as the participant's.
UNREAD_CODE_POSITION = ("{label} gave this code in an entry CPT Studio does not read: a participant's code is read "
                        "only in the shape of a CPT or HCPCS code, and this code is not in one.")
UNREAD_PEER_POSITION = ("In peer review, {label} took a position on this code, which CPT Studio does not read: a "
                        "participant's code is read only in the shape of a CPT or HCPCS code, and this code is not in "
                        "one.")


def participant_codes(participants: Sequence[ParticipantInput]) -> tuple[str, ...]:
    """The codes an assessment with ``participants`` may look up beside the proposal provider's (the assess stage
    prefetches the union for the bounded child, which has no database): every code in a code's shape
    (participant_listable) a used reading, or a used peer review's additional codes, proposes with at least one located
    quote. A superset of what _Harness.merge reads; never a code it would miss. Inputs read as _Harness reads them
    (_usable_inputs): a malformed one proposes nothing."""
    found = set()
    for p in _usable_inputs(participants):
        entries = list(p.reading.codes) if p.state == 'read' else []
        if p.state == 'read' and p.peer_state == 'read':
            entries += list(p.peer.additional_codes)
        found |= {item.code for item in entries
                  if participant_listable(item.code) and any(q.spans for q in item.evidence)}
    return tuple(sorted(found))


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


# --- what CPT Studio reads of a participant's input (I10: one broken participant blocks only itself) ---

def _quotes_ok(quotes) -> bool:
    return isinstance(quotes, (tuple, list)) and all(
        isinstance(q, LocatedQuote) and isinstance(q.spans, (tuple, list))
        and all(isinstance(span, EvidenceSpan) for span in q.spans) for q in quotes)


def _items_ok(items, kind) -> bool:
    return isinstance(items, (tuple, list)) and all(isinstance(item, kind) and _quotes_ok(item.evidence)
                                                    for item in items)


def _codes_ok(items) -> bool:
    return _items_ok(items, ParticipantCode) and all(isinstance(item.modifiers, (tuple, list)) for item in items)


def _malformed_reading(reading: ParticipantReading) -> str:
    """What of a reading CPT Studio cannot read, in its own words ('' when nothing): every part the merge reads must be
    of its declared type, so that no participant's input can stop the assessment of the others."""
    if not _codes_ok(reading.codes):
        return 'its codes'
    if not _items_ok(reading.not_coded, ParticipantNotCoded) or not all(isinstance(item.reason, str)
                                                                        for item in reading.not_coded):
        return 'its not-coded items'
    if not _items_ok(reading.services, ParticipantService) or not all(
            isinstance(s.family, str) and isinstance(s.status, str) for s in reading.services):
        return 'its services'
    if not isinstance(reading.questions, (tuple, list)) or not isinstance(reading.extraction_issues, (tuple, list)):
        return 'its questions or extraction issues'
    if type(reading.unverified_quotes) is not int or not isinstance(reading.requested_model, str):
        return 'its counts or model'
    return ''


def _malformed_peer(peer: PeerReview) -> str:
    """What of a peer review CPT Studio cannot read ('' when nothing), as _malformed_reading."""
    if not _items_ok(peer.positions, CodePosition) or not all(isinstance(x.position, str) for x in peer.positions):
        return 'its positions'
    if not _codes_ok(peer.additional_codes):
        return 'its additional codes'
    if not _items_ok(peer.answers, QuestionAnswer):
        return 'its answers'
    if type(peer.unverified_quotes) is not int:
        return 'its count of unverified quotes'
    return ''


def _first_problem(p: ParticipantInput) -> str:
    """Why CPT Studio cannot read a participant's frozen first reading as given ('' when it can)."""
    if p.state not in PARTICIPANT_STATES:
        return 'its state is not one CPT Studio knows'
    if p.state == 'read' and p.reading is None:
        return 'its state is read but no reading was given'
    if p.state != 'read' and p.reading is not None:
        return 'a reading was given with a state other than read'
    if p.reading is not None:
        if not isinstance(p.reading, ParticipantReading):
            return 'its reading is malformed'
        if p.reading.provider != p.provider:
            return "its reading is another participant's"
        if p.reading.refused:
            return 'its reading was refused'
        what = _malformed_reading(p.reading)
        if what:
            return f'its reading is malformed ({what})'
    return ''


def _peer_problem(p: ParticipantInput) -> str:
    """Why CPT Studio cannot read a participant's peer review as given ('' when it can, or when there is none)."""
    if p.peer_state not in ('',) + PARTICIPANT_STATES:
        return 'its peer review state is not one CPT Studio knows'
    if p.state != 'read' and (p.peer_state == 'read' or p.peer is not None):
        return 'a peer review was given although its first reading was not read'
    if p.peer_state == 'read' and p.peer is None:
        return 'its peer review state is read but no peer review was given'
    if p.peer_state != 'read' and p.peer is not None:
        return 'a peer review was given with a peer state other than read'
    if p.peer is not None:
        if not isinstance(p.peer, PeerReview):
            return 'its peer review is malformed'
        if p.peer.provider != p.provider:
            return "its peer review is another participant's"
        if p.peer.refused:
            return 'its peer review was refused'
        what = _malformed_peer(p.peer)
        if what:
            return f'its peer review is malformed ({what})'
    return ''


def _refused_input(provider: str, why: str, peer_state: str = '') -> ParticipantInput:
    return ParticipantInput(provider, 'refused', None, f'CPT Studio could not use its input: {why}', peer_state, None)


def _usable(p: ParticipantInput) -> ParticipantInput:
    """``p`` as CPT Studio reads it: unchanged when well formed, else the phase that is not degraded to 'refused' with
    CPT Studio's own reason (harness@1 integration owner, 2026-11-01: never a raise, so it blocks only itself). A peer
    review is read only beside a first reading that is (HARNESS.md 11.1)."""
    why = _first_problem(p)
    if why:
        given = p.peer_state != '' or p.peer is not None
        return _refused_input(p.provider, why, 'refused' if given else '')
    why = _peer_problem(p)
    if not why:
        return p
    if p.state != 'read':
        return replace(p, peer_state='refused', peer=None)  # the reason stays its first phase's
    return replace(p, peer_state='refused', peer=None, reason=f'CPT Studio could not use its peer review: {why}')


def _usable_inputs(participants: Sequence[ParticipantInput]) -> tuple[ParticipantInput, ...]:
    """The configured participants' inputs as CPT Studio reads them, in stage order (_usable); a participant given more
    than once is read as refused. An input that is no ParticipantInput, or that names no harness participant, belongs to
    no participant that could be blocked alone: it is a contract violation of the caller and raises."""
    order = {name: index for index, name in enumerate(PARTICIPANT_ORDER)}
    given: dict[str, list] = {}
    for p in participants:
        if not isinstance(p, ParticipantInput):
            raise ValueError(f'A participant input must be a ParticipantInput, not {type(p).__name__}.')
        if not isinstance(p.provider, str) or p.provider not in order:
            raise ValueError(f'Unknown participant {p.provider!r}.')
        given.setdefault(p.provider, []).append(p)
    return tuple(_usable(entries[0]) if len(entries) == 1
                 else _refused_input(name, 'its input was given more than once')
                 for name, entries in sorted(given.items(), key=lambda item: order[item[0]]))


def _unread(store: dict, name: str, value) -> None:
    """Keep ``value``, a code participant ``name`` gave that is not read (participant_listable), in ``store``: only to
    word its position on the proposal provider's own code of that value (_Harness.positions), never to list it."""
    if isinstance(value, str) and value:
        store.setdefault(name, set()).add(value)


@dataclass(frozen=True)
class _Said:
    """One participant's entry about one code, with its quotes' spans as CPT Studio verified them: ``good`` are exact
    slices of the revision text (each once, with its page), ``bad`` every span that is not (never evidence). ``phase``:
    the participant's first reading ('independent') or its peer review ('peer_review', HARNESS.md 11.1)."""
    entry: object  # ParticipantCode, ParticipantNotCoded or CodePosition
    good: tuple[EvidenceSpan, ...]
    bad: tuple[EvidenceSpan, ...] = ()
    phase: str = INDEPENDENT


class _Harness:
    """The independent participants' merge (HARNESS.md 5, 11), made once per assessment from the inputs of the
    configured participants, in stage order (_usable_inputs: a malformed input is read as refused, never raised on).
    Only what CPT Studio itself verified is used: a quote is evidence only where its span is an exact slice of the
    revision text, checked here again and never assumed (I7), and nothing a participant wrote in its own words reaches
    the result - only its codes, its enumerated reasons and positions, and the document's own passages.

    - A code a decidable proposal carries (the proposal provider's or the bounded second review's: one a reviewer can
      decide, as _second_review reads it) stays that proposal, changed only by the record of who proposed it
      (support['proposed_by'], from 'corti'; support['phases'], each participant's phase; support['participants'],
      each participant's position in both phases).
    - Any other code (HARNESS.md P-ADMIT, owner directive 2026-11-05, which replaces the session's D14): one a
      participant's frozen first reading proposes, quoting the document verbatim, is read by the proposal provider's
      own path (_select) from those first-reading spans alone, and becomes a proposal of its own (support['origin']
      'participant') only as a code the bounded second review selected does: not excluded, and accounting for a
      documented service or act the other proposals left unresolved (_open_items_covered). Where two different such
      codes account for one same item neither is added: CPT Studio does not choose between participants. Every other
      code is an alternative saying why ('altp:<n>'), its evidence the exact spans of every participant that quoted it
      verbatim. (D14, refutation round 6 to b0dc3446c64c: no participant's code was a proposal; before D14 every code in
      scope with exact evidence was, so a verbatim quote of a failed, denied, earlier or another procedure's act made it
      READY - the owner's D10/D12 meaning check of 2026-11-03.) A participant's stated units, modifiers and confidence
      are recorded in its position and never used.
    - Peer review (11.1): a code a peer review adds is read exactly as a first reading's code, after every code a
      first reading listed, and is recorded as proposed after peer review, never as independent. Keys still move
      between assessments (a new answer of the proposal provider selects other codes), so a question's key never
      identifies its proposal across assessments: a confirmation is bound by code and identity.
    - Agreement never promotes (I3): a second proposer adds its quotes to the code's evidence and its name to the
      record; with the same quotes it changes nothing else - not the bucket, status, checks, units or fingerprint (only
      the sentences that name the proposers: a rationale's first one, and an alternative's reason). A peer review's
      'supports' changes nothing at all.
    - A participant that advises not to code a code because its service was not performed at this encounter, quoting
      the document, or that disputes it in peer review, quoting the document, adds a warn to each decidable proposal of
      that code (participants.disagree, naming the phase); the status stays the readers' own.
    - A service a participant reads as performed, or as started and not completed, quoting the document, of a kind of
      which the documented-service reading reads no performed service, makes coding completeness incomplete
      (participants.services).
    - Its questions and its peer-review answers never become clarifications or answers: participants.summary counts
      them, as notes; an answer is recorded and decides nothing by itself (only a reviewer's confirmation of a
      candidate is read, on the dormant path: _Confirmations; HARNESS.md 12.10)."""

    def __init__(self, participants: Sequence[ParticipantInput], text: str, pages):
        self.inputs = _usable_inputs(participants)
        self.text, self.pages = text, pages
        # where the documented-service reading read each service mention, and how (gi_services.build's ``located``:
        # (family, kind, status, start, end)); assess sets it, and missing reads it
        self.located: tuple = ()
        self.readings = {p.provider: p.reading for p in self.inputs if p.state == 'read'}
        self.peers = {p.provider: p.peer for p in self.inputs if p.state == 'read' and p.peer_state == 'read'}
        self.answered = bool(self.readings)
        # code -> participant -> its entries, in first appearance (each first reading in stage order, then each peer
        # review in stage order, each in its own order)
        self.codes: dict[str, dict[str, list[_Said]]] = {}
        self.advised: dict[str, dict[str, list[_Said]]] = {}
        self.stances: dict[str, dict[str, list[_Said]]] = {}  # code -> participant -> its peer-review positions
        self.unlisted: dict[str, int] = {}
        self.peer_unlisted: dict[str, int] = {}
        # a participant's code is read only in a code's shape (participant_listable; refutation round 4, shapes-1):
        # any other it gave is counted (codes) and kept only as a value it gave, unread (unread, unread_stances), so
        # that its position on the proposal provider's own code of that value is never said to be "did not propose"
        self.unread: dict[str, set] = {}
        self.unread_stances: dict[str, set] = {}
        for name, reading in self.readings.items():
            unlisted = participant_unlisted_count(reading.codes)  # the one count (refutation round 5, D13)
            if unlisted:
                self.unlisted[name] = unlisted
            for item in reading.codes:
                if not participant_listable(item.code):
                    _unread(self.unread, name, item.code)
                    continue
                self.codes.setdefault(item.code, {}).setdefault(name, []).append(self._said(item))
            for item in reading.not_coded:
                if participant_listable(item.code):
                    self.advised.setdefault(item.code, {}).setdefault(name, []).append(self._said(item))
                else:
                    _unread(self.unread, name, item.code)
        for name, peer in self.peers.items():
            unlisted = participant_unlisted_count(peer.additional_codes)
            if unlisted:
                self.peer_unlisted[name] = unlisted
            for item in peer.additional_codes:
                if not participant_listable(item.code):
                    _unread(self.unread, name, item.code)
                    continue
                self.codes.setdefault(item.code, {}).setdefault(name, []).append(self._said(item, PEER_REVIEW))
            for item in peer.positions:
                if participant_listable(item.code):
                    self.stances.setdefault(item.code, {}).setdefault(name, []).append(self._said(item, PEER_REVIEW))
                else:
                    _unread(self.unread_stances, name, item.code)
        self._missing: Optional[list[dict]] = None

    def _said(self, entry, phase: str = INDEPENDENT) -> _Said:
        good, bad = self._partition(entry.evidence)
        return _Said(entry, good, bad, phase)

    def _partition(self, quotes: Sequence[LocatedQuote]) -> tuple[tuple[EvidenceSpan, ...], tuple[EvidenceSpan, ...]]:
        spans = [span for quote in quotes for span in quote.spans]
        good, _ = checks.exact_evidence(spans, self.text, self.pages)
        return good, tuple(span for span in spans if checks._evidence_problem(span, self.text))

    # --- one code ---------------------------------------------------------------------------------------------------

    def proposers(self, code: str) -> tuple[str, ...]:
        """The participants that proposed ``code`` quoting the document verbatim, in stage order."""
        by = self.codes.get(code, {})
        return tuple(name for name in PARTICIPANT_ORDER if any(s.good for s in by.get(name, ())))

    def first_proposers(self, code: str) -> tuple[str, ...]:
        """The participants whose frozen first reading proposed ``code`` quoting the document verbatim, in stage order:
        the only proposers an admission reads (HARNESS.md P-ADMIT). A participant that located its quote only in peer
        review proposed the code after seeing its peers' conclusions (phase())."""
        by = self.codes.get(code, {})
        return tuple(name for name in PARTICIPANT_ORDER
                     if any(s.good and s.phase == INDEPENDENT for s in by.get(name, ())))

    def _first_evidence(self, code: str, names: Sequence[str]) -> tuple[EvidenceSpan, ...]:
        """What _select reads for a first-reading proposal: the exact spans of ``names``' first-reading entries for
        ``code``, each once, in the order of the document (the same quotes give the same evidence whoever gave them:
        I3), then their spans that are not exact, which _select drops and its evidence check names. Never a peer
        review's quotes."""
        found, bad = {}, []
        for name in names:
            for said in self.codes.get(code, {}).get(name, ()):
                if said.phase != INDEPENDENT:
                    continue
                for span in said.good:
                    found.setdefault((span.start, span.end), span)
                bad.extend(said.bad)
        return tuple(found[key] for key in sorted(found)) + tuple(bad)

    def phase(self, code: str, name: str) -> str:
        """The phase in which ``name`` first proposed ``code``: its first reading, else its peer review - read only from
        its entries that quote the document verbatim, as proposers() counts them (refutation round 1, EV-2 = IND-3: a
        first reading's entry whose quotes were not found proposed nothing, so a code its peer review then located was
        proposed after peer review); '' for a participant none of whose entries did, which proposed the code in no
        phase: it listed it (refutation round 5, the session's D12 - the fallback to all its entries named such a
        participant as an alternative's proposer, with a phase)."""
        counted = [s for s in self.codes.get(code, {}).get(name, ()) if s.good]
        if not counted:
            return ''
        return INDEPENDENT if any(s.phase == INDEPENDENT for s in counted) else PEER_REVIEW

    def _who(self, code: str, names: Sequence[str]) -> str:
        """'Astra (independent participant)', 'Fable after peer review', 'Astra (independent participant) and Fable
        after peer review': a code first proposed in peer review is never described as independent (11.1)."""
        first = [name for name in names if self.phase(code, name) == INDEPENDENT]
        later = [name for name in names if self.phase(code, name) == PEER_REVIEW]
        return ' and '.join(([_participant_names(first)] if first else [])
                            + ([f'{checks._join([PARTICIPANT_LABELS[name] for name in later])} after peer review']
                               if later else []))

    def _lead(self, code: str, proposers: Sequence[str], selections: Sequence[_Selection],
              listed: Sequence[str] = (), second_listed: Sequence[str] = ()) -> str:
        """The rationale's first sentence of a participant's own proposal (HARNESS.md 11.4): who proposed it, and what
        Corti did with the code - selected it with no exact passage (its selection listed apart, excluded), listed it
        without selecting it (``listed``: a candidate, or an alternative to a code it selected), listed it in its
        bounded second review without that review adding it (``second_listed``: alt2, a code that review selected and
        that was not added, or a candidate or an alternative of it), or nothing at all; never "Selected by". "Corti did
        not propose this code." is said only where Corti has no entry for the code (refutation round 2, truth-7: a Corti
        candidate of the same code was its alternative while this sentence denied it; the page's words,
        review.corti_relation and app.js CORTI_RELATIONS, are the same). ``listed`` and ``second_listed`` name codes
        only, not the role each was listed in, so neither sentence names one role: the Alternatives row of the code says
        which (refutation round 3, truth-5: an alternative to 45385 was said to be "listed only as a candidate", and a
        second review's candidate "listed ... as an alternative")."""
        who = self._who(code, proposers)
        if any(s.code == code and s.origin == 'primary' for s in selections):
            return (f'Proposed by {who}; Corti also selected this code, with no exact passage; it is listed apart, '
                    'excluded.')
        if code in listed:
            return (f'Proposed by {who}; Corti listed this code as a candidate or an alternative, not selected; see '
                    'Alternatives.')
        if code in second_listed:
            return (f"Proposed by {who}; Corti's second review also listed this code without adding it as a proposal; "
                    'see Alternatives.')
        return f'Proposed by {who}; Corti did not propose this code.'

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
              inventory, *, dated: bool, procedure_day: bool = False,
              corti_listed: Sequence[str] = (),
              corti_second_listed: Sequence[str] = ()) -> tuple[list, tuple[ProposalAssessment, ...]]:
        """(``selections`` with the participants' admitted proposals after them, the participants' alternatives).
        HARNESS.md P-ADMIT (owner directive 2026-11-05, replacing the session's D14). A participant's code that a
        decidable proposal carries is recorded on it (recorded). Any other is checked in order: its scope reason,
        UNLOCATED where none of its quotes was found verbatim, NO_EVIDENCE where none is an exact slice of the text,
        PARTICIPANT_PEER_ONLY where no first reading proposed it with one, PARTICIPANT_UNREAD where the
        documented-service reading is unavailable; otherwise it is read by the proposal provider's own path (_select:
        scope, exact evidence, the routed family, the documented service and act, the P2 READ-HOLD holds, the passages'
        support, required facts, PFS, MUE, the endoscopic base) from its first-reading proposers' spans alone (until
        2026-11-06 it was then admissible only where it was not excluded, its own passages showed the act and it
        accounted for a documented item - P-ADMIT2's narrowed form - and was otherwise an alternative; see below). Codes
        of different proposers for one documented
        act each reach review, held by one question naming the others (_competition): CPT Studio never chooses between
        them. An added code is a selection like any other - its status, checks and questions are the readers',
        it counts as covering what it accounts for, and only a member's decision approves it. ``corti_listed`` and
        ``corti_second_listed`` word its rationale's first sentence (_lead).

        Completion repair (owner directive 2026-11-06, items 3 and 5; builder Q1) - EQUAL ELIGIBILITY. A participant's
        explicit first-reading code (in scope, quoted verbatim with an exact span, by its frozen first reading) that no
        decidable proposal carries is ADMITTED: it is read by the same per-code path as a code Corti selects (_select,
        from its first-reading proposers' spans), and its outcome is that path's - READY where the readers document
        the act today, held with that path's question where they read it in doubt or cannot find it, excluded with the
        passage (reinstatable) where the path excludes it. No rule of the admission's own decides it any more: before,
        a code that accounted for no documented item, or whose own passages did not show the act, was an alternative
        "not documented as done", never reinstatable, where Corti's selection of the same passages was held (U8, U9;
        the participants' foreign-body removal code for "the bolus was removed" on two retained cases). Corti
        selecting, omitting or listing the code changes nothing. Only a genuine non-proposal stays an alternative: out
        of scope, no quote found verbatim, no exact span, proposed only in peer review, or no documented-service reading
        to read it by.

        A code a decidable proposal carries that a participant's first reading also proposed is read ONCE, over every
        proposer's exact passages (_select's ``extra``; item 2, evidence-based reconciliation): so it is never held by
        the evidence hold (P2 READ-HOLD) because one proposer cited text about another act while another proposer's
        passage shows the act, and a passage that reads the code's own act in doubt, historical, planned or denied still
        holds it, whoever cited it. Who cited each passage is recorded (support['provenance']). A participant whose
        quotes add no passage changes nothing but the record (I3).

        Cross-code effects are computed once over every active selection, whoever proposed it: the base rules
        (base_included, base_within) and competition (_competition, over the codes that are not excluded)."""
        have = {s.code for s in selections if s.evaluation is not None}  # decidable, as _second_review reads it
        # The documented items each admitted code's claims are read from (_competition): every documented service and act
        # the reading reads done, as if nothing were proposed (P-ADMIT2); refutation round 1 (L4-1): never the same-day
        # office-visit suppression, which reads Corti's own procedure selections
        documented = _documented_items(inventory, False) if inventory is not None else []
        selections = [self._with_first_passages(s, routing, reference, day, inventory, dated) for s in selections]
        order: list[str] = []
        why: dict[str, str] = {}
        admissible: dict[str, tuple] = {}  # code -> (its reading, the documented items it accounts for, its proposers)
        for code in self.codes:
            if code in have:
                continue  # read with that proposal (_with_first_passages) and recorded on it (recorded)
            order.append(code)
            proposers, first = self.proposers(code), self.first_proposers(code)
            _, scope_reason = checks.code_scope(code)
            if scope_reason:
                why[code] = scope_reason
            elif not proposers:
                why[code] = UNLOCATED
            elif not checks.exact_evidence(self._evidence(code, proposers), self.text, self.pages)[0]:
                why[code] = NO_EVIDENCE  # what _select reads as no exact source evidence
            elif not first:
                why[code] = PARTICIPANT_PEER_ONLY
            elif inventory is None:
                why[code] = PARTICIPANT_UNREAD
            else:
                group = [ProviderCode('selected', 'participant', code, '', self._first_evidence(code, first))]
                candidate = _select(group, self.text, self.pages, routing, reference, day, inventory, dated=dated)
                if candidate.evaluation is None:  # unreachable after the gates above; never an unread admission
                    why[code] = (candidate.scope_reason or NO_EVIDENCE).rstrip('.')
                    continue
                candidate = replace(candidate, cited_by=self._cited_by(code, candidate.evidence, first))
                admissible[code] = (candidate, _open_items_covered(candidate, code, documented, inventory), first)
        competes = _competition(admissible, selections, documented, inventory, self.text)
        added, listed = [], []
        for code in order:
            if code in admissible:
                candidate, items, first = admissible[code]
                # its evidence is its first readings' spans alone (proposers); its first sentence names every
                # participant that proposed it, each in its own phase, as its record does (recorded). A code another
                # decidable code claims one same act as is added too, and both are held (P-ADMIT2: competes)
                added.append(replace(candidate, origin='participant', proposers=first,
                                     lead=self._lead(code, self.proposers(code), selections, corti_listed,
                                                     corti_second_listed),
                                     competes=competes.get(code, ()) if not candidate.excluded else ()))
                continue
            names = tuple(n for n in PARTICIPANT_ORDER if n in self.codes[code])
            listed.append(self._alternative(len(listed), code, names, why[code]))
        kept = [replace(s, competes=competes[s.code]) if s.code in competes and s.evaluation is not None
                and not s.excluded else s for s in selections]
        return kept + added, tuple(listed)

    def _cited_by(self, code: str, evidence: Sequence[EvidenceSpan], names: Sequence[str],
                  primary: Sequence[EvidenceSpan] = (), by: str = PRIMARY) -> tuple:
        """Who cited each passage of ``evidence`` (support['provenance']): ``by`` for the ``primary`` spans (a decidable
        proposal's own: Corti's, or its second review's), each of ``names`` for its own first-reading exact spans."""
        own = {(span.start, span.end) for span in primary}
        quoted = {name: {(span.start, span.end) for said in self.codes.get(code, {}).get(name, ())
                         if said.phase == INDEPENDENT for span in said.good} for name in names}
        return tuple((span.start, span.end, tuple(([by] if (span.start, span.end) in own else [])
                                                  + [name for name in names if (span.start, span.end) in quoted[name]]))
                     for span in evidence)

    def _with_first_passages(self, s: '_Selection', routing: RoutingResult, reference: ReferenceLookup,
                             day: Optional[date], inventory, dated: bool) -> '_Selection':
        """A decidable proposal ``s`` read again over its own passages and those of every participant whose first
        reading proposed its code with exact quotes (item 2: one code, read once, over all its proposers' passages),
        keeping its own units, display and origin. Unchanged where no such participant adds a passage it lacks (I3:
        the same quotes change nothing but the record), where it has no reading (no exact passage of its own: the
        participant's code is then read on its own beside it, as before), or where it has no group to read again."""
        if s.evaluation is None or not s.group or s.origin != 'primary':
            # a second review's addition was read on the date its own review reads (_second_review): it keeps that
            # reading, and a participant's code of its number is recorded on it, as before
            return s
        first = self.first_proposers(s.code)
        spans = self._first_evidence(s.code, first) if first else ()
        have = {(span.start, span.end) for span in s.evidence}
        extra = tuple(span for span in spans if not checks._evidence_problem(span, self.text)
                      and (span.start, span.end) not in have)
        if not extra:
            return s
        again = _select(list(s.group), self.text, self.pages, routing, reference, day, inventory, dated=dated,
                        extra=extra)
        return replace(again, origin=s.origin, proposers=s.proposers, lead=s.lead,
                       cited_by=self._cited_by(s.code, again.evidence, first, s.evidence))

    def _alternative(self, index: int, code: str, names: tuple[str, ...], why: str) -> ProposalAssessment:
        """A participant's code that is not a proposal, saying why: informational, never approvable. ``names``: every
        participant that gave the code. Only those with an entry that quotes the document verbatim proposed it
        (proposers()); the others listed it, and are said to have, never to have proposed it (refutation round 5, the
        session's D12: "Proposed by Astra (independent participant)" was said of a reading whose every quote was not
        found, beside the same assessment's "so it did not propose it")."""
        code_kind, scope_reason = checks.code_scope(code)
        kept = self._good(code, names)
        family = family_for_code(code)
        found = (checks.scope_check(code_kind, scope_reason),)
        profile_version = PROFILES[family].version
        located = [name for name in names if name in self.proposers(code)]
        listed = checks._join([PARTICIPANT_LABELS[name] for name in names if name not in located])
        why = why.rstrip('.')
        if not located:
            exclusion = f'Listed by {listed} {LISTED_NOT_PROPOSED}, and not added as a proposal: {why}.'
            rationale = f'Listed by {listed} {LISTED_NOT_PROPOSED}; not added as a proposal: {why}.'
        else:
            who = self._who(code, located)
            apart = f' Listed by {listed} {LISTED_NOT_PROPOSED} by {listed}.' if listed else ''
            exclusion = f'Proposed by {who}, but not added as a proposal: {why}.{apart}'
            rationale = f'Proposed by {who}; not added as a proposal: {why}.{apart}'
        return ProposalAssessment(
            key=f'altp:{index}', bucket='alternative', code=code, code_kind=code_kind, family=family,
            profile_version=profile_version, status='informational',
            exclusion_reason=f'{exclusion} Alternatives cannot be approved.',
            reinstatable=False, provider_display='', evidence=kept,
            # a participant's verbatim quote is never called evidence for the code (refutation round 7, display-5: "1
            # exact evidence passage" was said of "Hot snare polypectomy failed." beside this reason; the owner's D10/D12
            # directive: a quotation existing verbatim must not itself establish clinical support)
            rationale=(f'{rationale} Informational only.'
                       + (f' {checks.plural(len(kept), "passage")} of the document quoted verbatim.' if kept else '')),
            checks=found, modifier_considerations=(), units=1,
            fingerprint=_fingerprint(code, family, profile_version, kept, found, {}, 1, 'informational'),
            support={'origin': 'participant'})

    def disagreements(self, s: _Selection) -> tuple[Check, ...]:
        """The participants.disagree warn of a decidable proposal: each participant that advises not to code its code
        because its service was not performed at this encounter, quoting the document, and each that disputes it in
        peer review, quoting the document (11.1). A 'supports' or 'cannot tell' position adds nothing (I3)."""
        if s.evaluation is None:
            return ()
        advised, disputed = [], []
        for name in PARTICIPANT_ORDER:
            quoted = next((x for x in self.advised.get(s.code, {}).get(name, ())
                           if x.entry.reason == NOT_PERFORMED_HERE and x.good), None)
            if quoted is not None:
                advised.append((PARTICIPANT_LABELS[name], quoted.good[0].text))
            quoted = next((x for x in self.stances.get(s.code, {}).get(name, ())
                           if x.entry.position == 'disputes' and x.good), None)
            if quoted is not None:
                disputed.append((PARTICIPANT_LABELS[name], quoted.good[0].text))
        return (checks.participants_disagree_check(s.code, advised, disputed),) if advised or disputed else ()

    # --- the record ---------------------------------------------------------------------------------------------------

    def recorded(self, proposals: Sequence[ProposalAssessment]) -> tuple[ProposalAssessment, ...]:
        """Every proposal with who proposed it (support['proposed_by']), the phase each participant among them first
        proposed it in (support['phases']: 'independent' or 'peer_review'; only for a participant whose entry for the
        code quotes the document verbatim, phase()), each participant's position on its code in both phases
        (support['participants']) and, for a participant's alternative, the participants that gave its code with no
        entry quoting the document verbatim, which listed it and did not propose it (support['listed_by']; refutation
        round 5, the session's D12). Outside the fingerprint: who proposed a code never changes its decision."""
        out = []
        for p in proposals:
            by = self._proposed_by(p)
            support = {**(p.support or {}), 'proposed_by': by, 'participants': self.positions(p.code)}
            phases = {name: self.phase(p.code, name) for name in by}  # '' for a name that proposed in no phase
            phases = {name: phase for name, phase in phases.items() if phase}
            if phases:
                support['phases'] = phases
            listed = self._listed_by(p)
            if listed:
                support['listed_by'] = listed
            out.append(replace(p, support=support))
        return tuple(out)

    def _proposed_by(self, p: ProposalAssessment) -> list[str]:
        origin = (p.support or {}).get('origin', 'primary')
        if p.bucket == 'alternative':
            # an alternative is proposed by no one; a participant's names the participants that proposed its code - an
            # entry quoting the document verbatim (proposers()) - and never one that only listed it (_listed_by;
            # refutation round 5, the session's D12)
            return list(self.proposers(p.code)) if origin == 'participant' else []
        if origin == 'participant':
            return list(self.proposers(p.code))
        if p.bucket == 'selected' or p.reinstatable:  # decidable: the participants' proposals were merged into it
            return [PRIMARY, *self.proposers(p.code)]
        return [PRIMARY]  # excluded for scope or evidence: a participant's code of its own stands apart from it

    def _listed_by(self, p: ProposalAssessment) -> list[str]:
        """The participants that gave a participant's alternative's code with no entry quoting the document verbatim,
        in stage order: they listed it and did not propose it (refutation round 1, EV-2 = IND-3), so they are never
        among its proposers; [] for any other proposal (refutation round 5, the session's D12)."""
        if p.bucket != 'alternative' or (p.support or {}).get('origin') != 'participant':
            return []
        proposers = self.proposers(p.code)
        return [name for name in PARTICIPANT_ORDER if name in self.codes.get(p.code, {}) and name not in proposers]

    def positions(self, code: str) -> dict:
        """{participant: {'position', 'detail', 'quote'}} for every configured participant: 'proposed', 'not_proposed',
        'advised_not_to_code' or 'not_run' - from both phases, each 'proposed' saying in which, its detail counting as
        proposals only the entries that quote the document verbatim and naming any other as a listing in its phase;
        and, once its peer review stage exists for it, 'peer': its peer-review position ('supports', 'disputes',
        'cannot_tell', 'no_position' or 'not_run'). The quote is a passage of the document it quoted, found
        verbatim."""
        out = {}
        for p in self.inputs:
            label = PARTICIPANT_LABELS[p.provider]
            said = self.codes.get(code, {}).get(p.provider, [])
            advised = self.advised.get(code, {}).get(p.provider, [])
            if p.provider not in self.readings:
                entry = {'position': 'not_run', 'detail': self._state_sentence(p), 'quote': ''}
            elif said and not any(x.good for x in said):
                # no entry of either phase quotes the document verbatim: it proposed nothing (refutation round 1,
                # EV-2 = IND-3), so its position is never 'proposed' (refutation round 4, truth-2)
                detail = (f'{label} listed {code}' + (f' {len(said)} times' if len(said) > 1 else '')
                          + f' ({self._stated([x.entry for x in said])}); none of its quotes was found verbatim in the '
                          'document, so it did not propose it and is not counted as a proposer.')
                if advised:
                    detail += f' It also lists {code} as not to code: {_reason_words(advised[0].entry.reason)}.'
                entry = {'position': 'not_proposed', 'detail': detail, 'quote': ''}
            elif said:
                good = list({(span.start, span.end): span for x in said for span in x.good}.values())
                # only an entry that quotes the document verbatim proposed the code, so only those are counted and give
                # its phases; each other entry is named as a listing in its own phase (refutation round 6, account-3:
                # every entry was counted - "Astra proposed 45385 2 times" beside one located entry - and "again in
                # peer review" was said of a peer-review entry none of whose quotes was found)
                proposed = [x for x in said if x.good]
                phases = {x.phase for x in proposed}
                listed = {x.phase for x in said if not x.good}
                detail = f'{label} proposed {code}' + (f' {len(proposed)} times' if len(proposed) > 1 else '')
                if phases == {PEER_REVIEW} and INDEPENDENT in listed:
                    # a first reading whose quotes were not found proposed nothing there (11.1: a phase is the phase of
                    # the located evidence), so its listing is not called a proposal (refutation round 3, R3-TRUTH's
                    # note on truth-2: the API serves this detail in the proposal's support)
                    detail += (', listed in its independent reading with no quote found verbatim there, and proposed '
                               'after peer review')
                    listed.discard(INDEPENDENT)
                elif phases == {PEER_REVIEW}:
                    detail += ' after peer review, not in its independent reading'
                elif PEER_REVIEW in phases:
                    detail += ', in its independent reading and again in peer review'
                elif listed:
                    detail += ' in its independent reading'
                if listed:
                    where = ' and '.join(words for phase, words in ((INDEPENDENT, 'in its independent reading'),
                                                                    (PEER_REVIEW, 'in peer review')) if phase in listed)
                    detail += f', and also listed it {where} with no quote found verbatim in the document'
                detail += f' ({self._stated([x.entry for x in said])})'
                detail += (f', quoting the document verbatim in {checks.plural(len(good), "passage")}.' if good
                           else '; none of its quotes was found verbatim in the document, so it is not counted as a '
                                'proposer.')
                if advised:
                    detail += f' It also lists {code} as not to code: {_reason_words(advised[0].entry.reason)}.'
                entry = {'position': 'proposed', 'detail': detail,
                         'quote': checks.excerpt(good[0].text) if good else ''}
            elif advised:
                first = next((x for x in advised if x.entry.reason == NOT_PERFORMED_HERE and x.good),
                             next((x for x in advised if x.good), advised[0]))
                entry = {'position': 'advised_not_to_code',
                         'detail': f'{label} advises not to code {code}: {_reason_words(first.entry.reason)}.',
                         'quote': checks.excerpt(first.good[0].text) if first.good else ''}
            else:
                entry = {'position': 'not_proposed', 'quote': '',
                         'detail': (UNREAD_CODE_POSITION.format(label=label) if code in self.unread.get(p.provider, ())
                                    else f'{label} did not propose {code}.')}
            if p.peer_state:
                entry['peer'] = self._peer_position(p, code)
            out[p.provider] = entry
        return out

    def _peer_position(self, p: ParticipantInput, code: str) -> dict:
        label = PARTICIPANT_LABELS[p.provider]
        if p.provider not in self.peers:
            return {'position': 'not_run', 'detail': self._peer_sentence(p), 'quote': ''}
        stances = self.stances.get(code, {}).get(p.provider, [])
        known = [x for x in stances if x.entry.position in PEER_POSITIONS]
        chosen = (next((x for x in known if x.entry.position == 'disputes' and x.good), None)
                  or next((x for x in known if x.entry.position == 'disputes'), None)
                  or next((x for x in known if x.entry.position == 'supports'), None)
                  or next((x for x in known if x.entry.position == 'cannot_tell'), None))
        if chosen is None:
            return {'position': 'no_position', 'quote': '',
                    'detail': (UNREAD_PEER_POSITION.format(label=label)
                               if code in self.unread_stances.get(p.provider, ())
                               else f'{label} took no position on {code} in peer review.')}
        position = chosen.entry.position
        detail = f'In peer review, {label} {PEER_POSITION_WORDS[position]} {code}' + (
            ', quoting the document verbatim.' if chosen.good
            else '; none of its quotes was found verbatim in the document' + (
                ', so its dispute adds no warning.' if position == 'disputes' else '.'))
        if len(stances) > 1:
            detail += f' It stated {checks.plural(len(stances) - 1, "other position")} on {code}.'
        quote = checks.excerpt(chosen.good[0].text) if chosen.good else ''
        return {'position': position, 'detail': detail, 'quote': quote}

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

    def _peer_sentence(self, p: ParticipantInput) -> str:
        """Its peer review in words: '' before its peer-review stage exists for it (assess #1). ``reason`` speaks for
        the peer review only beside a first reading that was read (it speaks for the first reading otherwise)."""
        if not p.peer_state:
            return ''
        if p.state != 'read':
            return 'It takes no part in peer review: its first reading was not read.'
        if p.peer_state != 'read':
            reason = checks.excerpt(str(p.reason or '')).rstrip('.')
            return (f'Its peer review was not read: {PARTICIPANT_STATE_WORDS[p.peer_state]}'
                    + (f' ({reason})' if reason else '') + '.')
        peer = self.peers[p.provider]
        counts = Counter(x.position for x in peer.positions if x.position in PEER_POSITIONS)
        other = len(peer.positions) - sum(counts.values())
        parts = [f'In peer review, after its first reading was frozen, it took '
                 f'{checks.plural(len(peer.positions), "position")} on codes ({counts["supports"]} supports, '
                 f'{counts["disputes"]} disputes, {counts["cannot_tell"]} cannot tell'
                 + (f', {other} other not shown' if other else '') + ').']
        added = [code for code, by in self.codes.items() if any(x.phase == PEER_REVIEW for x in by.get(p.provider, ()))]
        if added:
            quoted = sum(1 for code in added
                         if any(x.good for x in self.codes[code][p.provider] if x.phase == PEER_REVIEW))
            more = len(added) - LISTED_IN_SUMMARY
            named = ', '.join(added[:LISTED_IN_SUMMARY]) + (f' and {more} more' if more > 0 else '')
            parts.append(f'It listed {checks.plural(len(added), "additional code")} ({named}), {quoted} quoting the '
                         'document verbatim; a code first proposed in peer review is never counted as independent.')
        else:
            parts.append('It listed no additional code.')
        if self.peer_unlisted.get(p.provider):
            parts.append(participant_unlisted_codes(self.peer_unlisted[p.provider], 'In peer review it'))
        if peer.answers:
            # true whether or not confirmations are offered (refutation round 4, d7-5; HARNESS.md 12.10 as amended): it
            # said an answer "is read only as the passage a reviewer confirms", in a release that offers no confirmation.
            # The questions are counted by the ids its answers name (the reader keeps every answer to a question it
            # listed, a repeated one with a note), never by its answers: one question answered twice was "It answered 2
            # open questions" (refutation round 5, d8-3)
            asked = len({str(answer.question_id) for answer in peer.answers})
            said = (f'It answered {checks.plural(asked, "open question")}' if asked == len(peer.answers) else
                    f'It gave {checks.plural(len(peer.answers), "answer")} to {checks.plural(asked, "open question")}')
            parts.append(f'{said}; an answer is recorded and decides nothing by itself.')
        if peer.unverified_quotes:
            one = peer.unverified_quotes == 1
            parts.append(f'{checks.plural(peer.unverified_quotes, "quote")} it gave in peer review '
                         f'{"was" if one else "were"} not found verbatim in the document and {"is" if one else "are"} '
                         'never evidence.')
        return ' '.join(parts)

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
                                                            m['quote'], m['status'], m['read_as'], m['read_in'])
                                                           for m in missing]))
        return out

    def _summary_sentence(self, p: ParticipantInput) -> str:
        reading = self.readings.get(p.provider)
        if reading is None:
            return ' '.join(part for part in (self._state_sentence(p), self._peer_sentence(p)) if part)
        label = PARTICIPANT_LABELS[p.provider]
        model = f', {reading.requested_model}' if reading.requested_model else ''
        parts = [f'{label} ({PARTICIPANT_VENDORS[p.provider]}{model}) read the document.']
        given = [code for code, by in self.codes.items() if any(x.phase == INDEPENDENT for x in by.get(p.provider, ()))]
        # a code its first reading listed with no quote found verbatim is not one it proposed (refutation round 4,
        # truth-2: "It proposed 2 codes (45385, 45380), 1 quoting the document verbatim" beside the card's "did not
        # propose it")
        codes = [code for code in given if any(x.good for x in self.codes[code][p.provider] if x.phase == INDEPENDENT)]
        unlocated = [code for code in given if code not in codes]
        if codes:
            more = len(codes) - LISTED_IN_SUMMARY
            named = ', '.join(codes[:LISTED_IN_SUMMARY]) + (f' and {more} more' if more > 0 else '')
            parts.append(f'It proposed {checks.plural(len(codes), "code")} ({named}), {len(codes)} quoting the '
                         'document verbatim.')
        else:
            parts.append('It proposed no code.')
        if unlocated:
            more = len(unlocated) - LISTED_IN_SUMMARY
            named = ', '.join(unlocated[:LISTED_IN_SUMMARY]) + (f' and {more} more' if more > 0 else '')
            parts.append(f'It listed {checks.plural(len(unlocated), "code")} ({named}) with no quote found verbatim in '
                         f'the document, so it did not propose {"it" if len(unlocated) == 1 else "them"}.')
        if self.unlisted.get(p.provider):
            parts.append(participant_unlisted_codes(self.unlisted[p.provider], 'It'))
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
        peer = self._peer_sentence(p)
        if peer:
            parts.append(peer)
        return ' '.join(parts)

    def missing(self, inventory) -> list[dict]:
        """The services a participant reads as performed, or as started and not completed (MISSING_STATUSES), quoting
        the document verbatim, of a kind of which ``inventory`` reads no performed service: one per participant and
        family, the first quote of its first. Coding completeness is incomplete beside each all the same (complete):
        the safety net stays.

        The reason names a reading the documented-service reading itself made of one quote's own words, at the places
        that quote is found verbatim (_read_as, from where the reading read each service mention, ``located``; never
        another reader's, and never another quote's: refutation round 10, wording-1): a mention of a service of the
        quoted kind that it reads as not done at this encounter (checks.NEGATIVE: negated, cancelled, planned or
        historical), with the status its inventory gives that family's service - 'the upper endoscopy as negated'
        (refutation round 6, R6-MEANING, negation-5). A reading of another passage is never attached to the quote
        (refutation round 7, display-1). The first quote whose places name a reading is the entry's, and its passage
        the first of those places that names one. Where no quote names one, the reason says what makes the service
        missing - the documented-service reading reads no performed service of that kind - which is true of every input
        (refutation round 10, wording-2: "does not read as performed" had been printed beside a quote whose words the
        reading reads as a performed act's), and with it what the reading reads as done in a quote's own words, of a
        family that kind does not map to (_read_in: the first quote whose places name one, its passage the first of
        those places), so the quoted service is never left looking denied (refutation round 11, wording-1: Astra's
        "other GI service" quoting the title of a transnasal esophagoscopy report, which the reading files under the
        upper GI endoscopy family, as performed, and the approved 43197 cites)."""
        if self._missing is None:
            done = {s.family for s in inventory.services if s.status in checks.POSITIVE}
            out, seen = [], set()
            for name, reading in self.readings.items():
                for service in reading.services:
                    families = PARTICIPANT_FAMILY_MAP.get(service.family, ())
                    if service.status not in MISSING_STATUSES or not families or done.intersection(families) \
                            or (name, service.family) in seen:
                        continue
                    good, _ = self._partition(service.evidence)
                    if not good:
                        continue
                    seen.add((name, service.family))
                    label = PARTICIPANT_SERVICE_LABELS[service.family]
                    what = (f'a performed {label}' if service.status == 'performed'
                            else f'an attempted, incomplete {label}')
                    read_as, read_in, place = '', '', good[0]
                    for arm, reader in (('as', self._read_as), ('in', self._read_in)):
                        named = ''
                        for quote in service.evidence:
                            own = {(span.start, span.end) for span in quote.spans}
                            places = [span for span in good if (span.start, span.end) in own]
                            named = reader(places, families, inventory) if places else ''
                            if named:
                                place = next(span for span in places if reader((span,), families, inventory))
                                break
                        if named:
                            read_as, read_in = (named, '') if arm == 'as' else ('', named)
                            break
                    reason = (f'{PARTICIPANT_LABELS[name]} reads {what} where the documented-service reading reads '
                              + (read_as or 'no performed service of that kind'
                                 + (f', and reads in the quoted words {read_in}' if read_in else '')))
                    quoted = f'{reason} ({reconcile.quote(place)})'
                    out.append({'participant': name, 'family': service.family, 'families': list(families),
                                'label': label, 'status': service.status, 'read_as': read_as, 'read_in': read_in,
                                'quote': place.text,
                                'start': place.start, 'end': place.end, 'page': place.page,
                                # review.coding_completeness drops every reason that holds "open question" (it
                                # recounts the open questions): a quote that holds it is kept in the entry and the
                                # check, never in the reason, so the reason cannot be dropped with the count
                                'reason': quoted if OPEN_QUESTION not in quoted else f'{reason} (quoted under the '
                                                                                     'participants\' services)'})
            self._missing = out
        return self._missing

    def _read_as(self, spans, families, inventory) -> str:
        """What the documented-service reading reads of one quote's words, at the places ``spans`` (half-open, the
        revision's text) give, for missing: each service mention of ``families`` it read inside a place (``located``)
        as not done at this encounter (checks.NEGATIVE), where its inventory gives that family's service that status,
        named by the mention's own kind (reconcile.mention_label: a kind with no service label by its act label), each
        status once, in reading order - 'the upper endoscopy as cancelled'; '' when it reads none there. An instrument
        names no kind of its own (``located`` gives it its family's), so it is never named here (refutation round 11,
        wording-2: "the ultrathin gastroscope was not inserted" had been named "the upper endoscopy as negated" beside
        the inventory's negated esophagoscopy).
        Refutation round 8, wording-1: round 7 named a reading only where routing read the same family with the same
        status in the quote, which routing never does for "declined", "could not be performed" or a family it does not
        route. Wording-2: the inventory's upper-endoscopy service takes its kind from its first mention, so with a PEG
        line first a quoted upper endoscopy had been named "the peg". Round 9, wording-2: a quoted PEG line's own kind
        has no service label. Rounds 8 and 9 also named an act read as performed in the quote; round 10 (wording-2 to
        wording-5) removed that: it was false where the act's words lay outside its mention, where its service's label
        was the family's and not the service's, where the inventory had dropped the act, or where the act kept no
        passage for the mention. The fallback now says only what makes the service missing, so the reason needs no act
        named to be true."""
        statuses = {(s.family, s.status) for s in inventory.services}
        read: dict[str, list[str]] = {}
        for what, family, kind, status, start, end in self.located:
            if what == 'service' and any(span.start <= start and end <= span.end for span in spans) \
                    and family in families and status in checks.NEGATIVE and (family, status) in statuses:
                states = read.setdefault(reconcile.mention_label(kind), [])
                if status not in states:
                    states.append(status)
        return ' and '.join(f'the {kind} as ' + ' and as '.join(states) for kind, states in read.items())

    def _read_in(self, spans, families, inventory) -> str:
        """What the documented-service reading reads as done (checks.POSITIVE) in one quote's words, at the places
        ``spans`` give, for missing where no quote names a not-done reading: each service mention it read as done
        inside a place (``located``: a service's name, a report title or an instrument) of a family that ``families``
        does not hold, where its inventory gives that family's service the same status, named by that family's own
        label (PROFILES, as the inventory heads the service) and that status, never by a mention's kind, each family
        and status once, in reading order: 'a performed service under Upper GI endoscopy (EGD, esophagoscopy, POEM)';
        '' when it reads none there. A family ``families`` holds never has a service read as done here: missing names
        none then. Refutation round 11, wording-1: the reason had said only that the reading reads no performed service
        of the participant's kind, beside a quote the reading files under another family, as performed. Round 12,
        wording-1: the status is the mention's own, never the whole service's - "an incomplete service under ERCP" had
        been printed beside a quoted reach the reading reads as performed, its incompleteness read in other passages."""
        statuses = {(s.family, s.status) for s in inventory.services}
        read: list[tuple[str, str]] = []
        for what, family, kind, status, start, end in self.located:
            if any(span.start <= start and end <= span.end for span in spans) and family not in families \
                    and status in checks.POSITIVE and (family, status) in statuses and (family, status) not in read:
                read.append((family, status))
        return ' and '.join(f'{"a performed" if status == "performed" else "an incomplete"} service under '
                            f'{PROFILES[family].label if family in PROFILES else family}' for family, status in read)

    def complete(self, complete: dict, inventory) -> None:
        """Coding completeness, incomplete beside each service only a participant reads (recorded under
        'participant_services', which reviewed_completeness keeps)."""
        missing = self.missing(inventory)
        if missing:
            complete.update(_incomplete(list(complete['reasons']) + [m['reason'] for m in missing]))
            complete['participant_services'] = missing


# --- reviewer-confirmed findings (HARNESS.md 11.3) -------------------------------------------------------------------
# A participant's located passage, accepted by an owner or reviewer with an attestation, answers the open question the
# readers' hold raised. It is read as documented by that passage, said to be confirmed (never as a reading of CPT
# Studio's own), answers only its own question, and approves nothing: approval stays a separate decision.

STATUS_FACT = 'performed_status'  # a proposal's status in doubt: performed or not, on the cited passage
# The required facts the readers take from the document (routing's): the extent reached, the structure examined, the
# cannulation outcome, the E/M basis. The service date and the other encounter-context facts never come this way: they
# enter through the encounter context as a member's value, where every date and conflict safeguard applies.
CONFIRMABLE_FACTS = tuple(sorted({fact for profile in PROFILES.values() for fact in profile.required_facts
                                  if fact not in CONTEXT_FACTS}))
# A confirmed status's value: 'performed', or how the passage documents the service as not performed at this encounter
# (the reading status the status path then words: a plain 'not performed' is a denial).
NOT_PERFORMED_VALUES = {'not_performed': 'negated', 'negated': 'negated', 'cancelled': 'cancelled',
                        'planned': 'planned', 'historical': 'historical'}
# The participants whose quote a confirmed passage can be: the model participants, whose frozen readings and peer-review
# answers are the only candidates (HARNESS.md 11.3, step 1). With none configured there is no candidate, and the assess
# stage gives the engine no confirmation at all (jobs.stage_assess, HARNESS.md 12.7), so nothing is confirmed (I1); the
# engine itself reads only what it is given, checked as below.
LOCATORS = dict(PARTICIPANT_LABELS)
NOT_OPEN = ('it answers no question this assessment asks (the question is not open here, or its proposal is held for '
            'another reason or not at all)')
DISAGREEING = 'confirmations of the same question disagree, so none of them is read and the question stays open'
CONTEXT_ONLY = ('the service date and the other encounter-context facts enter through the encounter context as a '
                "member's value, never by a confirmation")
# A proposal's question is bound to the proposal it was made for, never to the key it held (HARNESS.md 12.5, EV-1).
UNBOUND = ('it does not name the proposal it was made for (its code and the identity of its reading), and a '
           'confirmation is never read for whichever proposal holds a key now')
MOVED = ('the proposal it was made for is not in this assessment (no proposal of its code reads the same passages '
         'under the same context), so it answers nothing here; it is never read for the proposal that holds its key '
         'now')
TWICE = 'the proposal it was made for is in this assessment more than once, so CPT Studio cannot tell which it answers'
TOO_SHORT = (f'its passage is shorter than any quote CPT Studio locates (fewer than {MIN_QUOTE_CHARACTERS} non-space '
             'characters), so it is no located passage and never evidence (I7)')
# The required facts the readers read a procedure's completion from (refutation round 1, EV-4): a confirmed value of one
# is read as they read the same fact, so one they would read as incomplete makes the procedure incomplete.
REACH_FACTS = ('extent', 'cannulation')
UNPLACED = ("CPT Studio cannot place its value on its readers' own scale - one landmark routing reads, for an extent; "
            'successful or failed, for a cannulation - so it cannot tell whether the procedure was completed, and the '
            'question stays open')


def _status_value(value: str) -> str:
    return re.sub(r'[\s-]+', '_', value.strip().lower())


def _shortfall(family: str, fact: str, value: str, text: str, day: Optional[date]) -> Optional[str]:
    """How a reviewer-confirmed ``value`` of ``fact`` leaves its procedure incomplete, as CPT Studio's readers read the
    same fact: '' when they would read it completed, why when incomplete ('a failed cannulation'; 'short of the cecum,
    ...'), None when CPT Studio cannot place it (UNPLACED). An extent is one of routing's own landmarks, placed against
    the depth the procedure calls for as detect places a reach: the cecum for a colonoscopy (cues.CECUM_DEPTH), the
    depth the document's named upper endoscopy calls for (detect._expected_upper_depth), none for a flexible
    sigmoidoscopy. A cannulation is successful or failed, as detect._cannulation reads one. Any other fact has no
    completion reading ('')."""
    from studio.gi import cues, detect  # local, as in _routing_agrees; the analysis is cached per text and date
    word = ' '.join(value.split()).casefold()
    if fact == 'cannulation':
        return {'successful': '', 'failed': 'a failed cannulation'}.get(word)
    if fact != 'extent':
        return ''
    if family == 'gi.colonoscopy':
        table, expected = cues.LOWER_LANDMARKS, cues.CECUM_DEPTH
    elif family == 'gi.flex_sig':
        table, expected = cues.LOWER_LANDMARKS, 0  # a flexible sigmoidoscopy calls for no depth
    elif family in ('gi.egd', 'gi.enteroscopy'):  # an enteroscopy's codes are read through the EGD routing (legacy)
        table, expected = cues.UPPER_LANDMARKS, detect._expected_upper_depth(detect._analysis(text, day)[0])
    else:
        return None
    depth = next((depth for label, depth, _ in table if label == word), None)
    if depth is None:
        return None
    if depth >= expected:
        return ''
    called = next((label for label, at, _ in table if at == expected), 'depth')
    return f'short of the {called}, the depth the procedure calls for'


def _confirmation_order(c: ConfirmedFinding) -> tuple:
    """The order confirmations are read and listed in, whatever order they are given in (every field, so that even two
    confirmations sharing an id are read the same way each time)."""
    return tuple(str(getattr(c, name)) for name in ('scope', 'family', 'proposal_key', 'fact', 'confirmation_id',
                                                    'value', 'confirmed_by', 'located_by', 'evidence',
                                                    'proposal_code', 'proposal_identity'))


@dataclass(frozen=True)
class _Answer:
    """The reviewer-confirmed answer to one open question: one confirmation, or several that agree on its value."""
    scope: str  # service | proposal
    family: str
    key: str  # the proposal's key; '' for a service question
    code: str  # the proposal's code; '' for a service question
    fact: str
    value: str  # as confirmed, whitespace collapsed
    spans: tuple[EvidenceSpan, ...]  # their passages: exact slices of the revision text, each once, in document order
    ids: tuple[str, ...]
    words: str  # "confirmed from Fable's located passage by <reviewer>" (each confirmation's)
    short: str = ''  # how the confirmed value leaves the procedure incomplete, as the readers read it (_shortfall)

    @property
    def performed(self) -> bool:
        return _status_value(self.value) == 'performed'

    @property
    def status(self) -> str:
        """A confirmed status as a reading's status: 'performed', or the not-performed one its value names."""
        value = _status_value(self.value)
        return 'performed' if value == 'performed' else NOT_PERFORMED_VALUES.get(value, '')

    @property
    def quoted(self) -> str:
        return checks.quoted_passages([span.text for span in self.spans])

    def basis(self) -> list:
        """What a decision on the proposal rests on: the fact, its value and its passages (never who confirmed it)."""
        return [self.fact, self.status if self.fact == STATUS_FACT else self.value,
                [[span.start, span.end] for span in self.spans]]

    def sentence(self) -> str:
        return f'{checks.fact_label(self.fact)} = {checks.excerpt(self.value)}, {self.words} ({self.quoted})'

    def target(self) -> str:
        if self.scope == 'proposal':
            return f'{self.code} ({self.key})'
        return f'the documented {PROFILES[self.family].label}'

    def item(self) -> str:
        """The answer as the confirmations.applied check lists it."""
        if self.fact == STATUS_FACT:
            what = ('performed on the date of service' if self.performed
                    else f'not performed on the date of service (documented as {self.status})')
            return f'{self.target()}: {what}, {self.words} ({self.quoted})'
        return (f'{checks.fact_label(self.fact)} of {self.target()} = {checks.excerpt(self.value)}, {self.words} '
                f'({self.quoted})')


@dataclass(frozen=True)
class _Answers:
    """The confirmed answers to the required-fact questions one proposal reads, by fact: its own questions' and its
    family's service questions'."""
    facts: Mapping[str, _Answer]

    def state(self, state: checks.FactState) -> checks.FactState:
        """``state`` with its confirmed value, where the readers leave the fact missing or in conflict; otherwise as it
        is - a confirmation never replaces a value the readers read."""
        answer = self.facts.get(state.name)
        if answer is None or not state.problem:
            return state
        fact = Fact(state.name, answer.value, 'document', tuple(Span(sp.start, sp.end, sp.text) for sp in answer.spans),
                    answer.words)
        return checks.FactState(state.name, fact, '', confirmed=f'{answer.words} ({answer.quoted})')


def _confirmed(s: _Selection, answer: _Answer, held: str) -> _Selection:
    """``s`` with its status decided by the reviewer-confirmed ``answer`` on its cited passage, through the status path:
    performed, or not performed with the status the passage documents - then excluded, reinstatable as every status
    exclusion is. ``held``: the readers' own words for the hold it answers, kept beside it."""
    ev = s.evaluation
    first = answer.spans[0]
    state = 'performed' if answer.performed else 'not_performed'
    reading = checks.Reading(answer.status, (f'{checks.CONFIRMED_CUE}{answer.words}',), 'confirmed', first.text,
                             first.start, first.end)
    outcome = checks.StatusOutcome(state, reading, reason='confirmed')
    detail = checks.confirmed_status_detail(answer.performed, answer.status, answer.words, answer.quoted)
    match, support = ev.match, ev.support
    if match is not None:
        match = replace(match, state=state, reason='confirmed', question='', detail=detail)
        if support is not None:
            support = replace(support, status='not_applicable',
                              detail=f'Not checked against the documented service: {detail}')
    return replace(s, evaluation=replace(ev, outcome=outcome, match=match, support=support, note='', confirmed=answer,
                                         held=held))


class _Confirmations:
    """The reviewer-confirmed findings an assessment reads (HARNESS.md 11.3).

    Each is checked on its own, and one not read is listed with why (confirmations.ignored, a warn), never dropped
    unseen: its scope, fact and family must be ones a confirmation answers (STATUS_FACT at a proposal, or a required
    fact the readers take from the document, CONFIRMABLE_FACTS); it must name its value, the participants that located
    its passage and the reviewer; and every one of its passages must be an exact slice of the revision text.

    It is then matched to the open question it was made for, in the assessment these same inputs make WITHOUT any
    confirmation: a proposal's question by the proposal it was made for - the one proposal whose code and identity
    (_identity: its own reading, whatever else is proposed) are the confirmation's, asking (family, fact) - and never by
    the key it held, which another reading, a peer review or a new answer can give to another code; a service question
    by (family, fact). One whose proposal is not there, or is there twice, or that answers no such question, answers
    nothing; so does a status confirmation whose passages CPT Studio's readers do not read as stating its status for
    the act its proposal's code accounts for, or its service, in the documented service its hold was decided on - the
    one check every status candidate passes (reconcile.status_stated, refutation round 2, EV2-1), listed with its why;
    confirmations of one question that disagree are all left unread. So a confirmation never touches another
    question, and none depends on which others are read.

    Read, it answers its question and nothing else (apply): a status is decided as performed or not performed on its
    passage (_confirmed), through the status path; a required fact takes its confirmed value, with its passages as the
    evidence, for that proposal - for every proposal of the family, from a service question - where the readers leave it
    missing or in conflict. Every check, rationale and support record that uses it says so ("confirmed from Fable's
    located passage by <reviewer>") and support['confirmed'] lists the confirmations. Everything else - the same-day
    rules, the base inclusion, the references, every other question - applies as usual, so a confirmed code can still be
    held for another reason; and it approves nothing. The proposals keep the keys they have without confirmations."""

    def __init__(self, confirmed: Sequence[ConfirmedFinding], text: str, pages):
        confirmed = tuple(confirmed)
        self.text, self.pages = text, pages
        for c in confirmed:
            if not isinstance(c, ConfirmedFinding):
                raise ValueError(f'A confirmed finding must be a ConfirmedFinding, not {type(c).__name__}.')
        self.candidates: list[tuple[ConfirmedFinding, tuple[EvidenceSpan, ...]]] = []
        self.ignored: list[tuple[ConfirmedFinding, str]] = []
        self.applied: list[_Answer] = []
        self.answered: frozenset = frozenset()  # (family, fact) of every question an applied answer answers
        for c in sorted(confirmed, key=_confirmation_order):
            why = self._malformed(c)
            if not why:
                kept, dropped = checks.exact_evidence(c.evidence, text, pages)
                if dropped or not kept:
                    why = "its passage is not an exact slice of this revision's text"
            if why:
                self.ignored.append((c, why))
            else:
                self.candidates.append((c, kept))

    @staticmethod
    def _malformed(c: ConfirmedFinding) -> str:
        for name in ('scope', 'fact', 'family', 'proposal_key', 'value', 'confirmed_by', 'confirmation_id',
                     'proposal_code', 'proposal_identity'):
            if not isinstance(getattr(c, name), str):
                return f'its {name.replace("_", " ")} is not text'
        if not c.confirmation_id.strip():
            return 'it has no confirmation id'
        if c.scope == 'encounter' or c.fact in CONTEXT_FACTS:
            return CONTEXT_ONLY
        if c.scope not in ('service', 'proposal'):
            return 'its scope is neither a service nor a proposal question'
        if c.fact == STATUS_FACT and c.scope != 'proposal':
            return 'whether a code was performed is a question about a proposal'
        if c.fact != STATUS_FACT and c.fact not in CONFIRMABLE_FACTS:
            return ('a confirmation answers whether a code was performed or a required fact the readers take from the '
                    f'document ({checks._join([checks.fact_label(f) for f in CONFIRMABLE_FACTS])}), not this question')
        if c.family not in PROFILES:
            return 'it names no service family CPT Studio knows'
        if c.scope == 'proposal' and not c.proposal_key:
            return 'it names no proposal'
        if c.scope == 'proposal' and not (c.proposal_code.strip() and c.proposal_identity.strip()):
            return UNBOUND
        if c.scope == 'service' and (c.proposal_key or c.proposal_code or c.proposal_identity):
            return 'a service question names no proposal'
        if not c.value.strip():
            return 'it confirms no value'
        if c.fact == STATUS_FACT and _status_value(c.value) not in ('performed', *NOT_PERFORMED_VALUES):
            return ('its value is neither performed nor a status documenting the service as not performed at this '
                    f'encounter ({", ".join(NOT_PERFORMED_VALUES)})')
        if not isinstance(c.located_by, (tuple, list)) or not c.located_by \
                or not all(isinstance(name, str) and name in LOCATORS for name in c.located_by):
            return 'it names neither Astra nor Fable as the participant that located its passage'
        if not c.confirmed_by.strip():
            return 'it names no reviewer'
        if not isinstance(c.evidence, (tuple, list)) or not c.evidence \
                or not all(isinstance(span, EvidenceSpan) for span in c.evidence):
            return 'it cites no passage'
        if any(isinstance(span.text, str) and len(re.sub(r'\s+', '', span.text)) < MIN_QUOTE_CHARACTERS
               for span in c.evidence):
            return TOO_SHORT  # as the reading normaliser's Locator counts a quote (refutation round 1, EV-3)
        return ''

    def _status_unstated(self, c: ConfirmedFinding, spans: Sequence[EvidenceSpan], s: _Selection, inventory) -> str:
        """Why CPT Studio's readers do not read the passages of status confirmation ``c`` as stating its status for the
        proposal ``s`` it answers - the act its code accounts for, or its service, in the documented service its hold
        was decided on (reconcile.status_stated: the same check every status candidate passes, HARNESS.md 12.5,
        refutation round 2, EV2-1); '' when every passage does. So a stored or forged status confirmation is never read
        on a passage that does not state it (another act, the examination alone, a hedge or a slice of one, a
        denial)."""
        match = s.evaluation.match if s.evaluation is not None else None
        service = match.service.id if match is not None else ''
        for span in spans:
            why = reconcile.status_stated(inventory, service, s.code, s.family, c.value, span.start, span.end,
                                          self.text, self.pages)
            if why:
                return why
        return ''

    @staticmethod
    def _words(confirmations: Sequence[ConfirmedFinding]) -> str:
        """The words "confirmed from Fable's located passage by <reviewer>", each confirmation's, joined."""
        phrases = []
        for c in confirmations:
            owners = [f"{LOCATORS[name]}'s" for name in sorted(set(c.located_by), key=list(LOCATORS).index)]
            phrases.append(f'{checks._join(owners)} located passage by {checks.excerpt(c.confirmed_by)}')
        return 'confirmed from ' + '; and from '.join(dict.fromkeys(phrases))

    def apply(self, selections: list, proposals: tuple, procedure_day: bool, *, harness, provider: str, context,
              routing: RoutingResult, sources, date_state, inventory,
              day: Optional[date] = None) -> tuple[list, tuple, bool]:
        """(selections, proposals, procedure day) with the confirmed answers read. ``proposals``: the assessment's
        proposals without any - one per selection (_keyed), then the alternatives, which no confirmation touches.
        ``day``: the date the routing was read on (an extent is placed as its reading places one, _shortfall)."""
        count = len(selections)
        keyed, tail = tuple(proposals[:count]), tuple(proposals[count:])
        keys = _keys(selections)
        index = {key: i for i, key in enumerate(keys)}
        held = {p.key: p for p in keyed}
        asked = {(p.key, q.family, q.fact) for p in keyed for q in p.clarifications}
        services = {(q.family, q.fact) for q in (_service_questions(inventory, proposals, context)
                                                 if inventory is not None else ()) if q.scope == 'service'}
        # each decidable proposal's identity, as these inputs make it without any confirmation (_identity reads no check
        # and no status, so the same proposal has it whichever confirmations an assessment reads)
        unconfirmed = _encounter(provider, context, routing, sources, date_state, selections)
        identities = {keys[i]: (s.code, _identity(s, unconfirmed)) for i, s in enumerate(selections)
                      if s.evaluation is not None}
        groups: dict[tuple, list] = {}
        for c, spans in self.candidates:
            key = c.proposal_key
            if c.scope == 'proposal':
                # bound to the proposal it was made for, wherever its key is now: never to whichever holds the key
                bound = [k for k, identity in identities.items() if identity == (c.proposal_code, c.proposal_identity)]
                if len(bound) != 1:
                    self.ignored.append((c, TWICE if bound else MOVED))
                    continue
                key = bound[0]
            asks = ((key, c.family, c.fact) in asked if c.scope == 'proposal'
                    else (c.family, c.fact) in services)
            if not asks:
                self.ignored.append((c, NOT_OPEN))
                continue
            unstated = self._status_unstated(c, spans, selections[index[key]], inventory) \
                if c.fact == STATUS_FACT else ''
            if unstated:  # refutation round 2, EV2-1: a status is read only where the readers read it on its passage
                self.ignored.append((c, unstated))
                continue
            groups.setdefault((c.scope, c.family, key, c.fact), []).append((c, spans))
        status: dict[int, _Answer] = {}
        own: dict[int, dict[str, _Answer]] = {}
        family_wide: dict[str, dict[str, _Answer]] = {}
        for (scope, family, key, fact), items in groups.items():
            if fact == STATUS_FACT:  # performed, or the not-performed status it documents ('not_performed' a denial)
                same = {NOT_PERFORMED_VALUES.get(_status_value(c.value), 'performed') for c, _ in items}
            else:
                same = {' '.join(c.value.split()).casefold() for c, _ in items}
            if len(same) > 1:
                self.ignored += [(c, DISAGREEING) for c, _ in items]
                continue
            value = ' '.join(items[0][0].value.split())
            short = _shortfall(family, fact, value, self.text, day) if fact in REACH_FACTS else ''
            if short is None:  # neither complete nor incomplete on the readers' scale: fail closed (EV-4)
                self.ignored += [(c, UNPLACED) for c, _ in items]
                continue
            spans = {(sp.start, sp.end): sp for _, kept in items for sp in kept}
            answer = _Answer(scope, family, key, selections[index[key]].code if scope == 'proposal' else '', fact,
                             value, tuple(spans[k] for k in sorted(spans)),
                             tuple(sorted(dict.fromkeys(c.confirmation_id for c, _ in items))),
                             self._words([c for c, _ in items]), short)
            self.applied.append(answer)
            if fact == STATUS_FACT:
                status[index[key]] = answer
            elif scope == 'proposal':
                own.setdefault(index[key], {})[fact] = answer
            else:
                family_wide.setdefault(family, {})[fact] = answer
        self.ignored.sort(key=lambda item: _confirmation_order(item[0]))
        self.answered = frozenset((answer.family, answer.fact) for answer in self.applied)
        if not self.applied:
            return selections, proposals, procedure_day
        current = list(selections)
        for i, answer in status.items():
            before = next((c.detail for c in held[keys[i]].checks if c.id == 'service.status'), '')
            current[i] = _confirmed(selections[i], answer, before)
        encounter = _encounter(provider, context, routing, sources, date_state, current)
        answers = {}
        for i, s in enumerate(current):
            facts = {**family_wide.get(s.family, {}), **own.get(i, {})}
            if facts:
                answers[i] = _Answers(facts)
        return current, _keyed(current, encounter, harness, keys, answers) + tail, encounter.procedure_day

    def encounter_checks(self) -> list[Check]:
        out = []
        if self.applied:
            out.append(checks.confirmations_applied_check([answer.item() for answer in self.applied]))
        if self.ignored:
            out.append(checks.confirmations_ignored_check([self._ignored_item(c, why) for c, why in self.ignored]))
        return out

    @staticmethod
    def _ignored_item(c: ConfirmedFinding, why: str) -> str:
        fact = c.fact if isinstance(c.fact, str) else ''
        what = 'whether it was performed' if fact == STATUS_FACT else checks.excerpt(checks.fact_label(fact) or 'a fact')
        family = c.family if isinstance(c.family, str) else ''
        key = c.proposal_key if isinstance(c.proposal_key, str) else ''
        code = c.proposal_code.strip() if isinstance(c.proposal_code, str) else ''
        named = f' ({checks.excerpt(code)})' if code else ''  # the code of the proposal it was made for
        target = (f'proposal {checks.excerpt(key)}{named}' if c.scope == 'proposal' and key
                  else f'the documented {PROFILES[family].label}' if family in PROFILES else 'an unnamed service')
        return f'the confirmation of {what} for {target}: {why}'

    def record(self) -> dict:
        """What the assessment read (completeness['confirmations']): each answer with its confirmations' ids, and each
        confirmation not read with why."""
        return {'applied': [{'ids': list(a.ids), 'scope': a.scope, 'family': a.family, 'proposal_key': a.key,
                             'code': a.code, 'fact': a.fact, 'value': a.value,
                             'spans': [{'start': sp.start, 'end': sp.end, 'text': sp.text, 'page': sp.page}
                                       for sp in a.spans]} for a in self.applied],
                'ignored': [{'id': c.confirmation_id if isinstance(c.confirmation_id, str) else '', 'why': why}
                            for c, why in self.ignored]}


# --- member answers, read as an input (completion repair 2026-11-06: U10, U11; contract C5) -------------------------

MEMBER_ANSWER_CHECK = 'member.answer'
MEMBER_ANSWER_SOURCE = 'cpt-studio:member-answer@1'
ANSWERED_SUPPORT = questions.ANSWERED_SUPPORT  # support[...] of a code a member's answer excluded: {fact, value, answers}
MEMBER_ANSWER_LABELS = {questions.NOT_DOCUMENTED: 'Not documented', questions.CANNOT_CONFIRM: 'Cannot confirm'}
_ENDOSCOPIC_CHECK = 'pfs.endoscopic_base'  # checks.endoscopic_check's id
NOT_APPLIED = 'not_applied'  # an answer bound to a question asked that excluded nothing (recorded, never dropped)


answered_away = questions.answered_away  # the one reading of support['answered'] (questions.py)


def answered_fingerprint(fingerprint: str, found: Sequence[Check], status: str) -> str:
    """The fingerprint of a proposal whose checks or status a member's answer moved: the one it has without the answer,
    with what moved - so a decision made on one carries only onto the same reading (review._carry_decisions), and a
    decision made without the answer never carries onto it."""
    return sha256_json({'unanswered': fingerprint, 'checks': sorted([check.id, check.status] for check in found),
                        'status': status})


def _shape(found: Sequence[Check], status: str) -> tuple:
    return sorted([check.id, check.status] for check in found), status


class _MemberAnswers:
    """The revision's standing member answers, read as an input (``assess(member_answers=...)``).

    Each answer is bound to the question it was given to - its (code, family, fact) asked, in the assessment these same
    inputs make WITHOUT any answer, with the fingerprint it carries (studio.validation.questions.bind) - and is read
    there only. An answer that answers no question asked now, or a question asked differently, or that was recorded
    before answers carried a fingerprint, is kept as an earlier answer (completeness['member_answers']['earlier'], with
    why) and changes nothing.

    Read, an answer ("Not documented" or "Cannot confirm") excludes the code whose question it answers - and nothing
    else - by the review overlay's one rule (studio.validation.review_view: the first open question of the code a
    member answered as unavailable): the code is excluded by the member's answer (a 'member.answer' check, its reason
    naming the answer, support['answered']), its answered questions are kept, answered, and its other questions are
    not asked of an excluded code. Its cross-code effects are the overlay's: it still holds every code its presence
    held - a diagnostic base beside it keeps its base_included question, an E/M beside a procedure its separate-visit
    question (session decision (e) of 2026-11-03; refutation round 2, L7-01) - a competition it was a rival in is
    released or narrowed (refutation round 1 of harness repair 3, L4-5), and the CMS endoscopic-family check of every
    other code is read again without it. A documented service's question a member answered is closed and changes
    nothing else. No answer confirms a clinical fact, and none approves (decision D7)."""

    def __init__(self, given: Sequence[questions.MemberAnswerInput], text: str):
        self.text = text
        answers = []
        for answer in given:
            if not isinstance(answer, questions.MemberAnswerInput):
                raise ValueError(f'A member answer must be a MemberAnswerInput, not {type(answer).__name__}.')
            if not all(isinstance(getattr(answer, name), str)
                       for name in ('code', 'family', 'fact', 'value', 'question', 'answer_id')):
                raise ValueError('A member answer names its code, family, fact, value, question and id as text.')
            answers.append(answer)
        self.answers = sorted(answers, key=lambda a: (a.answer_id, a.code, a.family, a.fact, a.value, a.question))
        self.reading: dict = {}  # the documented-service reading's JSON form, as Assessment.services records it
        self.asked: dict = {}  # member key -> fingerprint of every question these inputs ask without any answer
        self.applied: list = []  # (answer, scope, proposal key or '')
        self.closed = 0  # the questions an applied answer answers: kept, answered, never open

    def _proposal_questions(self, proposals) -> dict:
        pairs = []
        acts = questions.acts_of(self.reading)
        for p in proposals:
            shown = questions.passages(p.evidence, p.support, self.text, acts)
            for spec in p.clarifications:
                family = spec.family or p.family
                pairs.append((questions.member_key(p.code, family, spec.fact),
                              questions.instance(spec.scope, family, spec.fact, p.code, spec.question, spec.reason,
                                                 shown)))
        return questions.group(pairs)

    def apply(self, proposals: Sequence[ProposalAssessment], by_key: Mapping[str, '_Selection'], services,
              reference_sources, sources, day: Optional[date]) -> tuple[ProposalAssessment, ...]:
        """``proposals`` as the bound answers leave them. ``by_key``: each decidable proposal's selection by its key;
        ``services``: the documented-service reading's JSON form (None when it was inconsistent, as the review overlay
        reads it); ``sources`` and ``day``: what the CMS endoscopic-family check reads (engine._proposal's)."""
        from studio.validation import review_view  # local import: review_view imports this module

        asked = self._proposal_questions(proposals)
        self.asked.update(asked)
        bound, _ = questions.bind([a for a in self.answers if a.code], asked)
        answer_of: dict = {}
        for answer in bound:
            answer_of.setdefault(questions.member_key(answer.code, answer.family, answer.fact), answer)
        if not answer_of:
            return tuple(proposals)
        views = review_view.review_view(
            [review_view.stored_from(p) for p in proposals], {}, services=services, retrieval=(),
            reference_sources=reference_sources, service_date=day,
            answers=[{'code': a.code, 'family': a.family, 'fact': a.fact, 'value': a.value}
                     for a in answer_of.values()])
        away = {p.key for p in proposals if getattr(views.get(p.key), 'reason', '') == review_view.DETAIL_UNAVAILABLE}
        if not away:
            return tuple(proposals)
        # the CMS endoscopic-family check of every other code reads the codes still in review (the overlay's EFFECTIVE
        # set): engine._encounter's active rows without the codes a member's answer excluded
        rows = endoscopic_rows((s.code, s.evaluation.reference.pfs) for key, s in by_key.items()
                               if key not in away and not s.excluded and s.evaluation is not None)
        out = []
        for p in proposals:
            view = views.get(p.key)
            if p.key in away:
                out.append(self._excluded(p, view, answer_of))
                continue
            found, specs, status = list(p.checks), list(p.clarifications), p.status
            if view is not None and COMPETING_CHECK in view.recomputed:
                # L4-5: a rival a member's answer to one of its own questions excluded is no longer in review
                new = next((c for c in view.checks if c.get('id') == COMPETING_CHECK), None)
                found = [Check(**{name: str(new.get(name) or '') for name in ('id', 'label', 'status', 'detail',
                                                                             'source')})
                         if c.id == COMPETING_CHECK else c for c in found if c.id != COMPETING_CHECK or new is not None]
                worded = next((q for q in view.questions if q.get('fact') == COMPETING_FACT), None)
                specs = [spec for spec in specs if spec.fact != COMPETING_FACT or worded is not None]
                specs = [replace(spec, question=str(worded['question']), reason=str(worded['reason']))
                         if spec.fact == COMPETING_FACT and worded is not None else spec for spec in specs]
                status = view.status
            selection = by_key.get(p.key)
            if selection is not None and selection.evaluation is not None:
                found = [checks.endoscopic_check(p.code, selection.evaluation.reference, rows, sources, day)
                         if c.id == _ENDOSCOPIC_CHECK and c.status != 'not_verified' else c for c in found]
            if (tuple(found), tuple(specs), status) == (tuple(p.checks), tuple(p.clarifications), p.status):
                out.append(p)
                continue
            moved = _shape(found, status) != _shape(p.checks, p.status)
            out.append(replace(p, checks=tuple(found), clarifications=tuple(specs), status=status,
                               fingerprint=answered_fingerprint(p.fingerprint, found, status) if moved
                               else p.fingerprint))
        return tuple(out)

    def _excluded(self, p: ProposalAssessment, view, answer_of: Mapping) -> ProposalAssessment:
        """``p`` excluded by the member's answer that left the detail its view names unavailable: its answered questions
        kept (answered), the 'member.answer' check and reason naming the answer, support['answered'] recording it."""
        keys = [questions.member_key(p.code, spec.family or p.family, spec.fact) for spec in p.clarifications]
        mine = [spec for spec, key in zip(p.clarifications, keys) if key in answer_of]
        answered = list(dict.fromkeys(key for key in keys if key in answer_of))
        deciding = answer_of.get(questions.member_key(p.code, p.family, getattr(view, 'answered', '') or '')) \
            or answer_of[answered[0]]
        subject = deciding.fact.split(':', 1)[1] if deciding.fact.startswith('conflict:') else ''
        what = questions.missing(deciding.fact, reconcile.act_label(subject) if subject else '')
        reason = (f'The member answered "{MEMBER_ANSWER_LABELS[deciding.value]}" to {what}; this code is excluded by '
                  'that answer until it is withdrawn.')
        found = tuple(p.checks) + (Check(MEMBER_ANSWER_CHECK, 'Member answer', 'fail', reason, MEMBER_ANSWER_SOURCE),)
        ids = sorted({answer_of[key].answer_id for key in answered})
        for key in answered:
            self.applied.append((answer_of[key], 'proposal', p.key))
        self.closed += len(mine)
        support = {**(p.support or {}),
                   ANSWERED_SUPPORT: {'fact': deciding.fact, 'value': deciding.value, 'answers': ids}}
        return replace(p, bucket='excluded', status='excluded', exclusion_reason=reason, reinstatable=False,
                       checks=found, clarifications=tuple(mine), support=support,
                       fingerprint=answered_fingerprint(p.fingerprint, found, 'excluded'))

    def close_service(self, specs: Sequence[ClarificationSpec]) -> None:
        """Bind the answers given for a documented service's question (no code) to the service questions ``specs`` ask,
        and close each one answered: it is kept, answered, and changes nothing else."""
        pairs = [(questions.member_key('', spec.family, spec.fact),
                  questions.instance(spec.scope, spec.family, spec.fact, '', spec.question, spec.reason,
                                     questions.service_passages(self.reading, spec.family, spec.fact, self.text)))
                 for spec in specs if spec.scope == 'service' and not spec.proposal_key]
        asked = questions.group(pairs)
        self.asked.update(asked)
        bound, _ = questions.bind([a for a in self.answers if not a.code], asked)
        counts = Counter(key for key, _ in pairs)
        done = set()
        for answer in bound:
            key = questions.member_key('', answer.family, answer.fact)
            if key in done:
                continue
            done.add(key)
            self.applied.append((answer, 'service', ''))
            self.closed += counts[key]

    def closes(self, scope: str, key: str, family: str, fact: str, code: str = '') -> str:
        """The id of the applied answer that answers this question ('' for none): a proposal's by its key, a documented
        service's by its family and fact. What persisting the assessment closes the stored question with."""
        for answer, where, proposal_key in self.applied:
            if where == scope and (proposal_key == key if scope == 'proposal' else True) \
                    and questions.member_key(answer.code, answer.family, answer.fact) == (code, family, fact):
                return answer.answer_id
        return ''

    def record(self) -> dict:
        """completeness['member_answers']: each answer read, with the question it answered and where; each answer not
        read, with why (questions.bind's reasons; NOT_APPLIED for one bound that excluded nothing)."""
        applied: dict = {}
        for answer, scope, key in self.applied:
            entry = applied.setdefault(answer.answer_id, {
                'answer': answer.answer_id, 'scope': scope, 'code': answer.code, 'family': answer.family,
                'fact': answer.fact, 'value': answer.value, 'question': answer.question, 'proposals': []})
            if key and key not in entry['proposals']:
                entry['proposals'].append(key)
        rest = [answer for answer in self.answers if answer.answer_id not in applied]
        bound, earlier = questions.bind(rest, self.asked)
        why = {id(answer): reason for answer, reason in earlier}
        listed = [{'answer': a.answer_id, 'code': a.code, 'family': a.family, 'fact': a.fact, 'value': a.value,
                   'why': why.get(id(a), NOT_APPLIED)}
                  for a in rest if a.value in questions.UNAVAILABLE]
        return {'form': questions.FORM, 'applied': list(applied.values()), 'earlier': listed}
