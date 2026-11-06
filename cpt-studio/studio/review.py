"""Review decisions, their carry/invalidation, readiness and the derived encounter state (ARCHITECTURE 5.7).

Decisions are append-only. A proposal's current decision is its LATEST
decision unless that one was invalidated or is a revoke; an earlier decision
is never resurrected. A decision is bound to the assessment, revision,
proposal fingerprint and profile version it was made on: a new revision
invalidates it, and a re-assessment of the same revision carries it only onto
a proposal with the same fingerprint, code, list, status and profile version.
Only the current assessment of the current revision can be decided on, and only
when it is its chain's final assessment (HARNESS.md 12.1): decisions are recorded
and carried between FINAL assessments only. An assess #1 that owes peer stages
takes no decision and neither carries nor invalidates one; the next final
assessment carries from the assessment that holds the encounter's current
decisions (refutation r1, Q1).
"""
from __future__ import annotations

import importlib
import json
import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from . import audit, candidates, participants
from .gi.context import charge_date_problem
from .participants import loop as participant_loop
from .models import (Assessment, Clarification, Decision, DecisionInvalidation, Encounter, FindingConfirmation, Job,
                     Proposal, ProviderExchange, ProviderRun, SourceRevision, ToolCall)
from .types import sha256_json, to_jsonable

log = logging.getLogger(__name__)


class AttestationRefused(ValidationError):
    """An approval whose acknowledgement is missing or is not the current attestation: invalid input (400, as
    API.md documents), not a state conflict, so a page loaded before the attestation changed is told to reload
    rather than read as 'not allowed right now' (round 6 bypass:2, pipeline:6)."""


class ModifierRefused(ValidationError):
    """A modifier choice that is not one of the offered values, or comes with another action than an approval: invalid
    input (the decisions endpoint answers 400), not a state conflict."""


APPROVE, REJECT, REINSTATE, REVOKE = Decision.APPROVE, Decision.REJECT, Decision.REINSTATE, Decision.REVOKE
CONFIRM = Decision.CONFIRM  # confirm a documentation check's exclusion (round 4: never a silent drop)
ACTION_LABELS = dict(Decision.ACTIONS)
# The whole-document attestation an approval records, one per actor kind. The page shows the server's text
# (/api/session) and the server accepts only that text, so an approval can never carry an attestation that
# says less (round 5, bypass:4). studio/static/studio/app.js keeps the same two strings for a page served
# before the session loads; tests/test_repairs_r4c_lead_review.py holds them equal.
ACKNOWLEDGEMENTS = {
    'human': ('I read the whole source document, not only the cited passages, and it supports this code as a '
              'service performed at this encounter. The documentation checks can miss wording they do not '
              'recognise. This synthetic review is not clinical approval or billing advice.'),
    'agent': ('I am an automated agent. I read the whole source document, not only the cited passages, and it '
              'supports this code as a service performed at this encounter. The documentation checks can miss '
              'wording they do not recognise. This agent-executed synthetic review is not clinical approval or '
              'billing advice.'),
}
SELECTED, EXCLUDED, ALTERNATIVE = Proposal.SELECTED, Proposal.EXCLUDED, Proposal.ALTERNATIVE
# The only (bucket, status) pairs a proposal may have; anything else is refused when persisted.
BUCKET_STATUSES = {
    SELECTED: (Proposal.READY, Proposal.NEEDS_CLARIFICATION),
    EXCLUDED: (Proposal.STATUS_EXCLUDED,),
    ALTERNATIVE: (Proposal.INFORMATIONAL,),
}
CLARIFICATION_SCOPES = ('encounter', 'service', 'proposal')
ACTIVE_JOB_STATES = (Job.QUEUED, Job.RUNNING)
UNSETTLED_RUN_STATES = (ProviderRun.RESERVED, ProviderRun.SENDING, ProviderRun.UNKNOWN)
# The derived failures whose customer error tells the member to upload the document again (progress.ERRORS): while an
# outcome is unknown, that upload would make the same paid request again, so none of them outranks it (_state_and_run).
RESUBMIT_STATES = ('extraction_failed', 'processing_failed', 'provider_failed')
MAX_CODE_LENGTH = Proposal._meta.get_field('code').max_length

STATE_LABELS = {
    'processing': 'Processing',
    'stopped': 'Stopped',
    'extraction_failed': 'Extraction failed',
    'processing_failed': 'Processing failed',
    'provider_not_run': 'Provider not run',
    'provider_failed': 'Provider request failed',
    'provider_unknown': 'Provider outcome unknown',
    'needs_clarification': 'Needs clarification',
    'ready_for_review': 'Ready for review',
    'reviewed': 'Reviewed',
    'no_codes': 'No CPT codes proposed',
}
STATUS_LABELS = {
    Proposal.READY: 'Ready for review',
    Proposal.NEEDS_CLARIFICATION: 'Needs clarification',
    Proposal.STATUS_EXCLUDED: 'Excluded',
    Proposal.INFORMATIONAL: 'Not selected',
}


def state_label(state):
    return STATE_LABELS.get(state, 'Unknown state')


# provider_failed when the run it reads is a response refused whole (_refused_run): read and not used, so it is neither a
# failed request nor one that proposed nothing (skeptic of refutation 7c8 reports-5).
REFUSED_LABEL = 'Provider response not used'
# no_codes (nothing left to decide) beside a second review made for the answer the assessment reads that the assessment
# did not read: that review's outcome, from its row, never "No CPT codes proposed" of a response nobody read (refutation
# p2, reports2:2) - as the panel and the readiness blocker state it.
SECOND_REVIEW_LABELS = {ProviderRun.UNKNOWN: 'Second review outcome unknown', ProviderRun.FAILED: 'Second review failed',
                        ProviderRun.NOT_SENT: 'Second review not sent', ProviderRun.CANCELLED: 'Second review not sent',
                        ProviderRun.SUCCEEDED: 'Second review not read yet'}
# no_codes where the provider's codes are all listed and none can be decided - excluded with no reinstatement (outside
# CPT-only results, no exact source evidence) or offered only as alternatives: codes were proposed, so never "No CPT
# codes proposed" (refutation p2, reports2:3), worded as the panel words it.
NOT_REVIEWABLE_LABEL = 'No code selected for approval'


def encounter_state_label(encounter):
    """The label of the encounter's stored state, worded from the rows: a provider_failed state reading a response refused
    whole says that the response was not used; a no_codes state says how the second review made for the answer the
    assessment reads ended when the assessment did not read it, else that no code is selected for approval when the
    provider's codes are listed and none can be decided."""
    if encounter.state == 'provider_failed':
        run = state_run(encounter)
        if run is not None and run.state == ProviderRun.SUCCEEDED:
            return REFUSED_LABEL
    if encounter.state == 'no_codes':
        assessment = live_assessment(encounter)
        if assessment is not None:
            # one query for the many rows with no second review (the documents list labels every row)
            second = (_unread_second_review(assessment) if encounter.provider_runs.filter(
                purpose=ProviderRun.SECOND_REVIEW).exists() else None)
            if second is not None:
                return SECOND_REVIEW_LABELS.get(second.state, 'Second review not finished')
            if assessment.proposals.exists():  # nothing is reviewable in a no_codes state (_review_state)
                return NOT_REVIEWABLE_LABEL
    return state_label(encounter.state)


def status_label(status):
    return STATUS_LABELS.get(status, 'Unknown status')


def _human(name):
    return str(name).replace('_', ' ')


def revised_reason(revision):
    return f'Source revised to revision {revision.number}'


# --- evidence and the assessment that can be decided on --------------------------

def exact_evidence(evidence, text):
    """The stored evidence spans that are exact substrings of the revision text, re-checked, never assumed."""
    spans = []
    for span in evidence or ():
        start, end = span.get('start'), span.get('end')
        if (span.get('context_index') == 0 and span.get('exact') is True and type(start) is int
                and type(end) is int and 0 <= start < end <= len(text) and text[start:end] == span.get('text')):
            spans.append(span)
    return spans


def live_assessment(encounter):
    """The current assessment when it was made on the current revision, else None."""
    if encounter.current_assessment_id is None:
        return None
    assessment = encounter.current_assessment
    return assessment if assessment.revision_id == encounter.current_revision_id else None


def _lock(encounter):
    return Encounter.objects.select_for_update().get(pk=encounter.pk)


# A decision is recorded on its chain's final assessment only (HARNESS.md 12.1; refutation r1, Q1): an assess #1 whose
# peer stages are owed is not the review's last word, and does not have the codes a peer review adds.
NOT_FINAL_DECISION = ('The peer reviews of this document have not finished: a decision is recorded on its final '
                      'assessment.')
NOT_FINAL_BLOCKER = 'The peer reviews have not finished: decisions are recorded on the final assessment'
# refutation round 2, L7-02: an upload date that chose between the dates the document states is asked back as a
# confirmation (answers.date_confirmation_open); the approved export waits for it
DATE_CONFIRMATION_BLOCKER = ('The date of service entered at upload chooses between the dates the document states and '
                             'has not been confirmed')


def decision_holder(encounter, *, exclude=None):
    """The assessment that holds the encounter's current decisions: the one its latest decision was recorded or carried
    onto (sequence order, under the encounter lock), or None when nothing was ever decided. Decisions are recorded and
    carried onto final assessments only, and persisting a final assessment carries or invalidates every current decision
    of this one - so a later final assessment that holds none had nothing left to carry, and this one then has no
    current decision. Read from the decisions themselves rather than by asking which earlier assessment was final:
    whether an assess #1 owed peer stages depends on the participants configured now (jobs.owed_peer_stages)."""
    decisions = Decision.objects.filter(encounter_id=encounter.pk)
    if exclude is not None:
        decisions = decisions.exclude(assessment_id=exclude.pk)
    latest = decisions.order_by('-sequence').values_list('assessment_id', flat=True).first()
    return Assessment.objects.get(pk=latest) if latest is not None else None


def _is_reviewer(membership, encounter):
    return (membership is not None and membership.can_review
            and membership.workspace_id == encounter.workspace_id)


# --- current decisions and allowed actions ---------------------------------------

def current_decisions(assessment):
    """proposal id -> its current Decision on ``assessment`` (approve, reject or reinstate)."""
    latest = {}
    for decision in assessment.decisions.select_related('reviewer').order_by('sequence'):
        latest[decision.proposal_id] = decision
    invalidated = set(DecisionInvalidation.objects.filter(
        decision_id__in=[d.pk for d in latest.values()]).values_list('decision_id', flat=True))
    return {proposal_id: decision for proposal_id, decision in latest.items()
            if decision.action != REVOKE and decision.pk not in invalidated}


def _current_decision(proposal):
    latest = proposal.decisions.order_by('-sequence').first()
    if latest is None or latest.action == REVOKE or DecisionInvalidation.objects.filter(decision=latest).exists():
        return None
    return latest


# --- the effective review view (CORE-UX-DESIGN.md 4; studio/validation/review_view.py) ---------------------------------
#
# Assessment and Proposal rows are immutable, so the combination gates the engine computed once over its own selection
# (the diagnostic-base rule, the CMS PFS endoscopic-family check) are re-applied at read time over the current decisions
# and member answers. Every gate and reader below reads this one view: actions, decision validation, readiness, coding
# completeness, the encounter state, the operator API, the report snapshot, the customer API and the approved export.

DETAIL_UNAVAILABLE = 'detail_unavailable'  # review_view.DETAIL_UNAVAILABLE


def _member_answers(assessment):
    """The member-answer effects (CORE-UX-DESIGN.md 6; P5's details flow): the standing member answers of
    ``assessment``'s revision - MemberAnswer rows no MemberAnswerRevocation withdrew (answers.saved_answers) - each a
    mapping with ``code``, ``family``, ``fact`` and ``value`` ('not_documented' | 'cannot_confirm'), bound to the
    (code, family, fact) it was asked of and never to a proposal key (lesson EV-1); ``code`` is '' for a documented
    service's question. The review overlay applies them at read time (review_view.review_view: a code's answered
    question makes it detail_unavailable - excluded, never approvable, nothing to decide - until the answer is
    withdrawn; a service's closes that question only), so every reader of the overlay - the actions, readiness, coding
    completeness, the encounter state, both APIs and the reports - reads the same answers."""
    from . import answers  # local import: answers imports this module
    return answers.saved_answers(assessment)


def effective_view(assessment, current=None):
    """{proposal key: review_view.View} of ``assessment`` as its current decisions and member answers leave it
    (studio.validation.review_view): each proposal's status, checks, open questions, approve gate, readiness blocker,
    modifier review and summary. With no decision and no answer every view equals its stored proposal. ``current``:
    current_decisions(assessment), when the caller has it. {} for no assessment, or one never persisted."""
    from .jobs import context_service_date  # local import: jobs imports this module
    from .validation import review_view  # local import: the validation layer is only needed with an assessment

    if assessment is None or not getattr(assessment, 'pk', None):
        return {}
    current = current_decisions(assessment) if current is None else current
    proposals = list(assessment.proposals.all())
    rows = {}
    for clarification in assessment.clarifications.all():  # every state: the open ones are the questions shown
        if clarification.proposal_id:
            rows.setdefault(clarification.proposal_id, []).append(clarification)
    stored = [review_view.stored_from(proposal, rows.get(proposal.pk, [])) for proposal in proposals]
    decided = {proposal.key: review_view.Decided(current[proposal.pk].action,
                                                 tuple(current[proposal.pk].modifiers or ()))
               for proposal in proposals if proposal.pk in current}
    completeness = assessment.completeness or {}
    # an inconsistent documented-service reading decided nothing (engine: usable is None), and nothing re-reads it here
    services = None if completeness.get('inventory_problems') else assessment.services
    return review_view.review_view(stored, decided, services=services, retrieval=assessment.retrieval,
                                   reference_sources=assessment.reference_sources,
                                   service_date=context_service_date(assessment.context),
                                   answers=_member_answers(assessment))


def open_questions_of(assessment, views=None):
    """Every question of ``assessment`` the review overlay leaves open, in the order they were raised, as dicts {id,
    scope, family, fact, question, reason, code}: the encounter's and the documented services' (one a member answered for
    the service is closed), each proposal's as its view leaves it (a released one dropped, a recomputed one in its new
    words), then each one the view adds (id '').  With no decision and no answer: every open Clarification row."""
    from .validation import review_view  # local import

    views = effective_view(assessment) if views is None else views
    proposals = {proposal.pk: proposal for proposal in assessment.proposals.all()}
    closed = review_view.service_answers(_member_answers(assessment))
    out = []
    for row in assessment.clarifications.filter(state=Clarification.OPEN).order_by('created_at', 'pk'):
        entry = {'id': str(row.pk), 'scope': row.scope, 'family': row.family, 'fact': row.fact,
                 'question': row.question, 'reason': row.reason, 'code': None}
        proposal = proposals.get(row.proposal_id) if row.proposal_id else None
        if proposal is None:
            if not (row.scope != 'proposal' and (row.family, row.fact) in closed):
                out.append(entry)
            continue
        view = views.get(proposal.key)
        if view is None:
            out.append({**entry, 'code': proposal.code})
            continue
        shown = next((q for q in view.questions if q.get('id') == str(row.pk)), None)
        if shown is not None:
            out.append({**entry, **shown, 'code': proposal.code})
    for proposal in sorted(proposals.values(), key=lambda item: item.position):
        view = views.get(proposal.key)
        for question in (view.questions if view is not None else ()):
            if not question.get('id'):
                out.append({**question, 'code': proposal.code})
    return out


# The support statuses that record the documented act as shown (reconcile.support): 'pass', a provider passage shows it;
# 'warn', none does and CPT Studio located the passages that do (support.source). Every other status shows nothing:
# 'not_applicable' (the act is not established as performed), 'fail', or no support reading at all.
SHOWN_SUPPORT = ('pass', 'warn')
MAX_PASSAGES = 4  # a short list: CPT Studio's own located passages first, then the provider's supporting ones


def _page_of(pages, offset):
    """The page holding character ``offset`` among the revision's pages (dicts, as SourceRevision.pages stores them,
    or PageSpans), None when none does."""
    for page in pages or ():
        if isinstance(page, dict):
            start, end, number = page.get('start'), page.get('end'), page.get('page')
        else:
            start, end, number = (getattr(page, name, None) for name in ('start', 'end', 'page'))
        if type(start) is int and type(end) is int and type(number) is int and start <= offset < end:
            return number
    return None


def act_index(services):
    """{act id: act} of a recorded documented-service reading (Assessment.services): what evidence_spans reads of
    each act a code was matched to."""
    out = {}
    listed = services.get('services') if isinstance(services, dict) else None
    for service in listed if isinstance(listed, list) else []:
        if isinstance(service, dict):
            for act in service.get('acts') or []:
                if isinstance(act, dict) and isinstance(act.get('id'), str):
                    out[act['id']] = act
    return out


def evidence_spans(proposal, text, pages, acts):
    """The exact passages a code rests on, by ONE rule that "Why this code?" (customer_api) and the approved export
    (approved_items) both read, so the page and the export never quote different passages (CORE-UX-DESIGN.md 7;
    refutation round 2, L3-7 and L3-10). Only where the code's support reading records its documented act as shown
    (SHOWN_SUPPORT): CPT Studio's own located passages for the matched act first - support.source, then the evidence of
    each matched act the recorded reading (``acts``: act_index) gives as performed or incomplete - then the provider's
    exact passages the support records as showing it (support.supporting). Nothing where the support records no act as
    shown - an act denied or in doubt (never the service's own passages, which show no such act), a 'fail', or no
    support reading at all (never a provider's passage nothing checked): fail-closed, never a passage that does not
    support. At most MAX_PASSAGES, each re-checked against ``text``; a passage inside one already listed adds nothing.
    Each {text, start, end, page, origin}: origin 'cited' when the provider cited exactly that passage, else
    'located'."""
    support = proposal.support or {}
    if not isinstance(support, dict) or support.get('status') not in SHOWN_SUPPORT:
        return []
    exact = exact_evidence(proposal.evidence, text)
    evidence = list(proposal.evidence or [])
    supporting = support.get('supporting')
    cited = [evidence[index] for index in (supporting if isinstance(supporting, (list, tuple)) else ())
             if type(index) is int and 0 <= index < len(evidence) and evidence[index] in exact]
    cited_at = {(span['start'], span['end']) for span in cited}
    located = list(support.get('source') or [])
    for act in support.get('acts') or []:
        stored = acts.get(act.get('id')) if isinstance(act, dict) and isinstance(acts, dict) else None
        if isinstance(stored, dict) and stored.get('status') in ('performed', 'incomplete'):
            located += list(stored.get('evidence') or [])
    out, seen = [], []
    for span in located + cited:
        if not isinstance(span, dict) or len(out) >= MAX_PASSAGES:
            continue
        start, end, quoted = span.get('start'), span.get('end'), span.get('text')
        if not (type(start) is int and type(end) is int and isinstance(quoted, str)
                and 0 <= start < end <= len(text) and text[start:end] == quoted):
            continue
        if any(a <= start and end <= b for a, b in seen):
            continue
        seen.append((start, end))
        out.append({'text': quoted, 'start': start, 'end': end, 'page': _page_of(pages, start),
                    'origin': 'cited' if (start, end) in cited_at else 'located'})
    return out


def approved_items(assessment):
    """The approved export's items (CORE-UX-DESIGN.md 4): the APPROVED proposals of ``assessment`` only - never an
    unresolved, undecided, rejected or excluded one, nor an approval the review overlay no longer supports (its view
    carries a readiness blocker, a member answer excluded it, or a reinstated same-day procedure holds the E/M) - in
    stored order. Not a readiness check: the approved export renders these only once readiness(encounter)['reviewed']. Each a dict: proposal_id, key, code,
    units, modifiers (the reviewer's chosen modifier), approved_by (the approver's label), approver_kind ('human' |
    'agent'), decided_at (ISO, when the approver decided; a carried approval keeps its root's time), note, evidence
    (evidence_spans: exact spans with page and character offsets, the passages "Why this code?" shows), summary (one
    sentence of CPT Studio's own reading), reinstated (an excluded code the reviewer reinstated before approving it)."""
    if assessment is None:
        return []
    current = current_decisions(assessment)
    views = effective_view(assessment, current)
    revision = assessment.revision
    acts = act_index(assessment.services)
    items = []
    for proposal in assessment.proposals.order_by('position'):
        decision, view = current.get(proposal.pk), views.get(proposal.key)
        if decision is None or decision.action != APPROVE or proposal.bucket == ALTERNATIVE:
            continue
        if view is not None and (view.blocker or view.reason == DETAIL_UNAVAILABLE or view.same_day_held):
            continue  # an approval readiness blocks (the overlay's, a member answer's, the same-day E/M gate's)
        root = decision_root(decision)
        items.append({
            'proposal_id': str(proposal.pk), 'key': proposal.key, 'code': proposal.code, 'units': proposal.units,
            'modifiers': list(decision.modifiers or []), 'approved_by': decision.reviewer.label(),
            'approver_kind': decision.reviewer_kind,
            'decided_at': root.created_at.isoformat() if root.created_at else None, 'note': decision.note,
            'evidence': evidence_spans(proposal, revision.text, revision.pages, acts),
            'summary': view.summary if view is not None else '',
            'reinstated': proposal.bucket == EXCLUDED})
    return items


def _actions(proposal, current, text, same_day_held=False, view=None):
    """``same_day_held``: an E/M that a reviewer's reinstatement of a same-day procedure now holds (no approve).
    ``view``: the proposal's effective review view (effective_view; CORE-UX-DESIGN.md 4) - its status, its reinstatement
    gate and a member answer's exclusion are read in place of the stored row's; None reads the stored row."""
    if current is not None and current.action in (APPROVE, REJECT, CONFIRM):
        return [REVOKE]
    if view is not None and view.reason == DETAIL_UNAVAILABLE:
        return [REVOKE] if current else []  # a needed detail is answered as unavailable: nothing to decide
    status = proposal.status if view is None else view.status
    exact = bool(exact_evidence(proposal.evidence, text))
    if proposal.bucket == SELECTED and status in BUCKET_STATUSES[SELECTED]:
        actions = [APPROVE] if status == Proposal.READY and exact and not same_day_held else []
        return actions + [REJECT] + ([REVOKE] if current else [])
    if proposal.bucket == EXCLUDED and proposal.status == Proposal.STATUS_EXCLUDED:
        if current is None:
            # A documentation check's exclusion (reinstatable) is a recommendation: the reviewer confirms it or
            # reinstates the code, and the reviewed report waits for one of the two (round 4).
            if not proposal.reinstatable:
                return []
            return ([REINSTATE] if exact else []) + [CONFIRM]
        clear = _reinstatement_clear(proposal) if view is None else view.reinstatement_clear
        return ([APPROVE] if exact and clear and not same_day_held else []) + [REJECT, REVOKE]
    return [REVOKE] if current else []


def _reinstatement_clear(proposal):
    """A reinstated exclusion is approvable only under the gates a selected code meets, as the validation layer
    recorded them in its 'review.reinstatement' check. Fail-closed: without a passing check, no approve."""
    return any(c.get('id') == 'review.reinstatement' and c.get('status') == 'pass' for c in proposal.checks or [])


# The same-day E/M gate on procedures a reviewer brings back (review:0), as the validation layer recorded it: an E/M
# with no same-day procedure detected carries SAME_DAY_EM_GATE, and each excluded, reinstatable procedure that would
# make the date a procedure day carries SAME_DAY_PROCEDURE.
SAME_DAY_EM_GATE = 'em.same_day_if_reinstated'
SAME_DAY_PROCEDURE = 'review.same_day_em'


def _has_check(proposal, check_id):
    return any(c.get('id') == check_id for c in proposal.checks or [])


def _reinstated_procedures(assessment, current):
    """The marked same-day procedures with a current reinstate or approve decision: brought back by a reviewer."""
    return [p for p in assessment.proposals.all()
            if p.bucket == EXCLUDED and _has_check(p, SAME_DAY_PROCEDURE)
            and p.pk in current and current[p.pk].action in (REINSTATE, APPROVE)]


def _same_day_held(proposal, assessment):
    """A gated E/M while a reviewer's reinstatement of a same-day procedure stands: it is then held exactly as
    beside a selected procedure until a separately identifiable E/M is documented."""
    return _has_check(proposal, SAME_DAY_EM_GATE) and bool(
        _reinstated_procedures(assessment, current_decisions(assessment)))


def approve_withheld_by(proposal, assessment, decisions, views=None):
    """The check that withholds approve from a reinstated exclusion, whoever is looking: 'review.reinstatement' while
    that check does not pass, SAME_DAY_EM_GATE while a reinstated same-day procedure holds this E/M, else None. The
    same gates as _actions, read without the member's role, so a viewer is never told a code cannot be approved when
    a reviewer can approve it now (round 6 bypass:3). The review overlay's own (effective_view; CORE-UX-DESIGN.md 4):
    'services.base_included' while the diagnostic-base rule, read over the current decisions, holds a selected or a
    reinstated base code it did not hold when the assessment was made (D14)."""
    views = effective_view(assessment, decisions) if views is None else views
    view = views.get(proposal.key)
    if view is not None:
        return view.withheld_by or None
    current = decisions.get(proposal.pk)
    if current is None or current.action != REINSTATE:
        return None
    if not _reinstatement_clear(proposal):
        return 'review.reinstatement'
    if _same_day_held(proposal, assessment):
        return SAME_DAY_EM_GATE
    return None


def _same_day_blocker(visit, procedures):
    codes = [p.code for p in procedures]
    listed = codes[0] if len(codes) == 1 else ', '.join(codes[:-1]) + ' and ' + codes[-1]
    done = 'was reinstated as a same-day procedure' if len(codes) == 1 else 'were reinstated as same-day procedures'
    return f'{visit.code} needs a separately identifiable E/M: {listed} {done}'


def _allowed(proposal, assessment, membership, encounter, views=None):
    if not _is_reviewer(membership, encounter) or proposal.assessment_id != assessment.pk:
        return []
    if (encounter.current_assessment_id != assessment.pk
            or assessment.revision_id != encounter.current_revision_id or not is_final(assessment)):
        return []
    view = (effective_view(assessment) if views is None else views).get(proposal.key)
    return _actions(proposal, _current_decision(proposal), assessment.revision.text,
                    view.same_day_held if view is not None else _same_day_held(proposal, assessment), view)


def allowed_actions(proposal, assessment, membership, views=None):
    """The actions this member may record on ``proposal`` now; the only source of truth for the UI. ``views``: the
    assessment's effective_view when the caller has it."""
    encounter = Encounter.objects.only('workspace', 'current_assessment', 'current_revision').get(
        pk=assessment.encounter_id)
    return _allowed(proposal, assessment, membership, encounter, views)


def _chosen_modifiers(value):
    """The modifier a reviewer chose for an approval: () or ONE of checks.DISTINCT_LESION_OPTIONS ('59' or 'XS'),
    never both, never another value (CORE-UX-DESIGN.md 4). A list of strings; anything else is refused."""
    from .validation.checks import DISTINCT_LESION_OPTIONS  # local import: the validation layer's own options
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or any(not isinstance(m, str) for m in value):
        raise ModifierRefused('Modifiers are a list: [] or one of 59 and XS.')
    chosen = tuple(value)
    if len(chosen) > 1:
        raise ModifierRefused('Choose at most one modifier, 59 or XS - never both.')
    if any(m not in DISTINCT_LESION_OPTIONS for m in chosen):
        raise ModifierRefused('A modifier is 59 or XS.')
    return chosen


def record_decision(*, encounter, proposal, action, user, membership, note='', acknowledgement='', modifiers=()):
    """Append one decision after re-validating it under the encounter lock, against the review overlay as the current
    decisions leave it (effective_view). ``modifiers``: on an approval only, () or the ONE modifier the reviewer chose,
    and only where the proposal's view offers a separate-lesion modifier review (CORE-UX-DESIGN.md 4); never prefilled."""
    chosen = _chosen_modifiers(modifiers)
    with transaction.atomic():
        locked = _lock(encounter)
        if not (_is_reviewer(membership, locked) and membership.user_id == user.pk and user.is_active):
            raise PermissionDenied('Your role in this workspace cannot record review decisions.')
        assessment = live_assessment(locked)
        if assessment is None or proposal.assessment_id != assessment.pk:
            raise ValidationError('That proposal is not part of the current review.')
        if action not in ACTION_LABELS:
            raise ValidationError('Unknown review action.')
        if not is_final(assessment):
            raise ValidationError(NOT_FINAL_DECISION)
        views = effective_view(assessment)
        if action not in _allowed(proposal, assessment, membership, locked, views):
            raise ValidationError(f'{ACTION_LABELS[action]} is not available for {proposal.code} right now.')
        if chosen:
            view = views.get(proposal.key)
            offered = tuple((view.modifier_review or {}).get('options') or ()) if view is not None else ()
            if action != APPROVE:
                raise ModifierRefused('A modifier is chosen only with an approval.')
            if not offered:
                raise ValidationError(f'No modifier review is offered for {proposal.code}: approve it with no '
                                      'modifier.')
            if any(m not in offered for m in chosen):
                raise ModifierRefused(f'The modifier review of {proposal.code} offers {" or ".join(offered)} only.')
        note, acknowledgement = (note or '').strip(), (acknowledgement or '').strip()
        if action == APPROVE and not acknowledgement:
            raise AttestationRefused('Approving requires an acknowledgement.')
        if action == APPROVE and acknowledgement != ACKNOWLEDGEMENTS.get(user.actor_kind):
            raise AttestationRefused('The acknowledgement is not the current review attestation. Reload the page '
                                     'and approve again.')
        decision = Decision.objects.create(
            encounter=locked, assessment=assessment, revision=assessment.revision, proposal=proposal, action=action,
            note=note, reviewer=user, reviewer_kind=user.actor_kind, acknowledgement=acknowledgement,
            modifiers=list(chosen), profile_version=proposal.profile_version,
            proposal_fingerprint=proposal.fingerprint)
        audit.record(locked.workspace, 'decision.recorded', encounter=locked, actor=user, decision=str(decision.pk),
                     proposal=str(proposal.pk), assessment=str(assessment.pk), action=action, code=proposal.code,
                     **({'modifiers': list(chosen)} if chosen else {}))
        encounter.state = refresh_state(locked)
    return decision


def _invalidate(decision, reason, *, by_revision=None, by_context=None):
    DecisionInvalidation.objects.create(decision=decision, reason=reason, by_revision=by_revision,
                                        by_context=by_context)


def invalidate_for_new_revision(encounter, new_revision):
    """Invalidate every current decision because the source changed; returns how many were invalidated."""
    if new_revision.encounter_id != encounter.pk:
        raise ValueError('The new revision belongs to another encounter.')
    with transaction.atomic():
        locked = _lock(encounter)
        count = 0
        holder = decision_holder(locked)  # the current assessment, unless an assess #1 owing peer stages followed it
        if holder is not None:
            for decision in current_decisions(holder).values():
                if decision.revision_id != new_revision.pk:
                    _invalidate(decision, revised_reason(new_revision), by_revision=new_revision)
                    count += 1
        if count:
            audit.record(locked.workspace, 'decisions.invalidated', encounter=locked,
                         revision=str(new_revision.pk), number=new_revision.number, decisions=count)
        encounter.state = refresh_state(locked)
    return count


# --- persisting an assessment ----------------------------------------------------

def _check_inputs(encounter, revision, context, routing_run, provider_run):
    if revision.encounter_id != encounter.pk:
        raise ValueError('The revision belongs to another encounter.')
    if encounter.current_revision_id != revision.pk:
        raise ValueError(f'Revision {revision.number} is no longer the current revision; '
                         'its assessment was not recorded.')
    if revision.extraction_status not in (SourceRevision.OK, SourceRevision.PARTIAL):
        raise ValueError(f'Revision {revision.number} has no extracted text to assess.')
    if context.encounter_id != encounter.pk or context.revision_id != revision.pk:
        raise ValueError('The encounter context was not taken from this revision.')
    if encounter.current_context_id != context.pk:
        raise ValueError('The encounter context changed while this assessment ran; it was not recorded.')
    if routing_run.revision_id != revision.pk:
        raise ValueError('The routing was computed for another revision.')
    if provider_run is not None and (provider_run.encounter_id != encounter.pk
                                     or provider_run.revision_id != revision.pk):
        raise ValueError('The provider run was made for another revision.')


def _check_result(result, text):
    keys = [item.key for item in result.proposals]
    if not all(keys) or len(set(keys)) != len(keys):
        raise ValueError('Proposal keys must be present and unique within an assessment.')
    for item in result.proposals:
        if item.status not in BUCKET_STATUSES.get(item.bucket, ()):
            raise ValueError(f'Proposal {item.key} has an invalid list/status pair ({item.bucket}/{item.status}).')
        if not item.code or len(item.code) > MAX_CODE_LENGTH:
            raise ValueError(f'Proposal {item.key} has a missing or over-long code; codes are never truncated.')
        if not item.fingerprint:
            raise ValueError(f'Proposal {item.key} has no fingerprint.')
        if item.bucket == SELECTED and not exact_evidence(to_jsonable(item.evidence), text):
            raise ValueError(f'Proposal {item.key} ({item.code}) has no exact evidence in this revision; '
                             'it cannot be a selected proposal.')
        source = (item.support or {}).get('source') or []
        if any(not (type(sp.get('start')) is int and type(sp.get('end')) is int and 0 <= sp['start'] < sp['end'] <= len(text)
                    and text[sp['start']:sp['end']] == sp.get('text')) for sp in source):
            raise ValueError(f'Proposal {item.key} ({item.code}) cites a source passage that does not match this '
                             'revision; it was not recorded.')


def _same_assessment(previous, digest, revision, context, routing_run, provider_run, second_run=None, participants=None,
                     retrieval=None):
    """Whether ``previous`` already is this assessment: the same result (its sha256) on the same inputs - the revision,
    the context, the routing run, the Corti run and the second-review run, exactly what the round-4 head compared (I1) -
    and, while a model participant is configured, the same participant runs: each entry's name, state and run and, on an
    assess #2 or its re-assessments, its peer state and peer run (HARNESS.md 12.3).

    Nothing else recorded beside the result decides it (refutation round 2, parity-r2-2; the round-2 plan's D6). Never
    the retrieval traces (``retrieval`` is not read): they read the CMS passages installed at the time, so an identical
    re-assessment made after the passages were imported is the same assessment and keeps the retrieval it recorded. And
    with no model participant configured on either side - every entry 'not configured', or none, as a round-4 row
    holds (migration 0007) - not the participants record either. A record that is not a list of entries is never taken
    for one: it is compared, and differs."""
    if not (previous is not None and previous.sha256 == digest and previous.revision_id == revision.pk
            and previous.context_id == context.pk and previous.routing_id == routing_run.pk
            and previous.provider_run_id == (provider_run.pk if provider_run else None)
            and previous.second_run_id == (second_run.pk if second_run else None)):
        return False

    def runs(record):
        if not isinstance(record, list) or not all(isinstance(entry, dict) for entry in record):
            return None
        return [{key: entry[key] for key in ('name', 'state', 'run', 'peer_state', 'peer_run') if key in entry}
                for entry in record]
    new, old = runs(participants or []), runs(previous.participants)
    if new is not None and old is not None and all(entry.get('state') == 'not_configured' for entry in new + old):
        return True
    return new is not None and new == old


def _clarification(encounter, assessment, spec, proposal):
    if spec.scope not in CLARIFICATION_SCOPES:
        raise ValueError(f'Unknown clarification scope {spec.scope!r}.')
    if spec.scope == 'encounter' and proposal is not None:
        raise ValueError('An encounter-scoped clarification cannot belong to one proposal.')
    if spec.scope == 'proposal' and proposal is None:
        raise ValueError(f'The proposal-scoped clarification about {spec.fact!r} names no proposal.')
    return Clarification.objects.create(encounter=encounter, assessment=assessment, proposal=proposal,
                                        scope=spec.scope, family=spec.family, fact=spec.fact,
                                        question=spec.question, reason=spec.reason)


def _create_clarifications(encounter, assessment, result, proposals):
    created = []
    for item in result.proposals:
        for spec in item.clarifications:
            if spec.proposal_key and spec.proposal_key != item.key:
                raise ValueError(f'A clarification of proposal {item.key} names proposal {spec.proposal_key}.')
            created.append(_clarification(encounter, assessment, spec, proposals[item.key]))
    for spec in result.clarifications:
        owner = None
        if spec.proposal_key:
            owner = proposals.get(spec.proposal_key)
            if owner is None:
                raise ValueError(f'A clarification names proposal {spec.proposal_key}, which does not exist.')
        created.append(_clarification(encounter, assessment, spec, owner))
    return created


def _clarification_identity(clarification):
    proposal = clarification.proposal
    return (clarification.scope, clarification.family, clarification.fact, proposal.fingerprint if proposal else '')


def _withdraw_superseded(encounter, assessment, raised):
    """Withdraw earlier open clarifications that this assessment does not raise again."""
    reraised = {_clarification_identity(item) for item in raised}
    withdrawn = 0
    earlier = (encounter.clarifications.select_related('proposal')
               .filter(state=Clarification.OPEN).exclude(assessment=assessment))
    for clarification in earlier:
        if _clarification_identity(clarification) not in reraised:
            clarification.state = Clarification.WITHDRAWN
            clarification.save(update_fields=['state'])
            withdrawn += 1
    return withdrawn


def _fact_value(fact):
    if not fact:
        return ('absent', '')
    if charge_date_problem(fact):
        return ('asked', 'asked')  # a closing charge block's question is no conflict in the document (dates-n6-2)
    return (fact.get('value') or 'not documented', fact.get('origin') or '')


def _show_fact(value):
    text, origin = value
    return {'user': f'{text} [member-supplied]', 'conflict': 'conflicting values'}.get(origin, text)


def _provider_identity(assessment):
    run = assessment.provider_run
    return None if run is None else (run.state, run.response_sha256)


def _what_changed(previous, current):
    """Short phrases naming what differs between two assessments of the same revision."""
    changes = []
    before, after = previous.context.facts or {}, current.context.facts or {}
    for name in sorted(set(before) | set(after)):
        old, new = _fact_value(before.get(name)), _fact_value(after.get(name))
        if old != new:
            changes.append(f'{_human(name)}: {_show_fact(old)} → {_show_fact(new)}')
    old_user, new_user = previous.context.user_values or {}, current.context.user_values or {}
    for name in sorted(set(old_user) | set(new_user)):
        if old_user.get(name) != new_user.get(name) and name not in before and name not in after:
            changes.append(f'member-supplied {_human(name)}')
    if _provider_identity(previous) != _provider_identity(current):
        changes.append('provider result')
    if previous.routing.sha256 != current.routing.sha256:
        changes.append('document routing')
    if previous.profiles_version != current.profiles_version:
        changes.append(f'profiles {previous.profiles_version} → {current.profiles_version}')
    if previous.engine_version != current.engine_version:
        changes.append(f'engine {previous.engine_version} → {current.engine_version}')
    if sha256_json(previous.reference_sources) != sha256_json(current.reference_sources):
        changes.append('reference sources')
    return changes


def _context_reason(changes, problem):
    if changes:
        return f'Re-assessed after changes ({"; ".join(changes)}): {problem}.'
    return f'Re-assessed: {problem}.'


def _carry_target(decision, old, candidates, all_new, same_engine):
    """(new proposal, '') when ``decision`` still holds in the new assessment, else (None, why not)."""
    if not candidates:
        same_code = [item for item in all_new if item.code == old.code]
        if same_code:
            return None, _what_differs(old, next((item for item in same_code if item.key == old.key), same_code[0]),
                                       same_engine)
        return None, f'{old.code} is no longer proposed'
    target = next((item for item in candidates if item.key == old.key), candidates[0])
    for field, label, show in (('code', 'code', str), ('bucket', 'list', str),
                               ('status', 'status', status_label), ('profile_version', 'profile version', str)):
        before, after = getattr(old, field), getattr(target, field)
        if before != after:
            return None, f'the {label} of {old.code} changed from {show(before)} to {show(after)}'
    if decision.action in (REINSTATE, CONFIRM) and not target.reinstatable:
        return None, f'{old.code} can no longer be reinstated'
    return target, ''


def _what_differs(old, new, same_engine):
    """Why a decision on ``old`` does not carry to ``new``, the same code proposed again with another fingerprint:
    the part of the fingerprint that differs, named from the persisted rows - or, when every persisted part is the
    same under the same engine, the one part a row does not keep: the context values the decision depends on (the
    service date; for an E/M the setting, patient status and billing context; for a PC/TC code the billing context).
    Round 7 bypass:0: "the evidence or checks changed" was printed in the reviewed report when only those had."""
    for field, label, show in (('family', 'family', str), ('bucket', 'list', str), ('status', 'status', status_label),
                               ('profile_version', 'profile version', str), ('units', 'units', str)):
        before, after = getattr(old, field), getattr(new, field)
        if before != after:
            return f'the {label} of {old.code} changed from {show(before)} to {show(after)}'
    changed = [label for label, read in (('evidence', _evidence_texts), ('checks', _check_results))
               if read(old) != read(new)]
    if changed:
        return f'the {" and ".join(changed)} for {old.code} changed'
    if same_engine:
        return f'the decision on {old.code} depends on a context value that changed'
    return f'{old.code} was re-assessed by another engine version'


def _evidence_texts(proposal):
    """The evidence as the fingerprint reads it: its passages' text, sorted."""
    return sorted(str(span.get('text', '')) for span in proposal.evidence)


def _check_results(proposal):
    """The checks as the fingerprint reads them: each check's id and status."""
    return sorted([str(check.get('id', '')), str(check.get('status', ''))] for check in proposal.checks)


def _carry_decisions(previous, assessment, proposals, revision, context):
    """Carry or invalidate the current decisions of ``previous`` - the assessment that holds them, decision_holder -
    onto the final assessment ``assessment``; returns (carried, invalidated)."""
    if previous is None:
        return 0, 0
    current = current_decisions(previous)
    if not current:
        return 0, 0
    old_proposals = {item.pk: item for item in previous.proposals.all()}
    ordered = sorted(current.values(), key=lambda d: (old_proposals[d.proposal_id].position, d.sequence))
    if previous.revision_id != revision.pk:
        for decision in ordered:
            _invalidate(decision, revised_reason(revision), by_revision=revision)
        return 0, len(ordered)
    changes = _what_changed(previous, assessment)
    new_items = sorted(proposals.values(), key=lambda item: item.position)
    used, carried = set(), 0
    for decision in ordered:
        old = old_proposals[decision.proposal_id]
        candidates = [item for item in new_items
                      if item.fingerprint == decision.proposal_fingerprint and item.pk not in used]
        target, problem = _carry_target(decision, old, candidates, new_items,
                                        previous.engine_version == assessment.engine_version)
        if target is None:
            _invalidate(decision, _context_reason(changes, problem), by_context=context)
            continue
        used.add(target.pk)
        Decision.objects.create(
            encounter=assessment.encounter, assessment=assessment, revision=revision, proposal=target,
            action=decision.action, note=decision.note, reviewer_id=decision.reviewer_id,
            reviewer_kind=decision.reviewer_kind, acknowledgement=decision.acknowledgement,
            modifiers=list(decision.modifiers or []), profile_version=target.profile_version,
            proposal_fingerprint=target.fingerprint, carried_from=decision)
        carried += 1
    return carried, len(ordered) - carried


def persist_assessment(*, encounter, revision, context, routing_run, provider_run, result, second_run=None,
                       participants=(), retrieval=()):
    """Record an AssessmentResult as the encounter's current assessment, in one transaction.

    Creates the immutable Assessment and Proposal rows and the Clarification
    rows, withdraws earlier open clarifications that were not raised again,
    then carries or invalidates the previous assessment's current decisions.
    Re-persisting an identical result on identical inputs returns the current
    assessment unchanged. ``participants`` (one entry per harness participant,
    its state and run) and ``retrieval`` (the reference retrieval traces) are
    recorded beside the result, outside its sha256 (HARNESS.md 6, I1).
    """
    digest = sha256_json(result)
    participants, retrieval = to_jsonable(list(participants)), to_jsonable(list(retrieval))
    with transaction.atomic():
        locked = _lock(encounter)
        revision = SourceRevision.objects.get(pk=revision.pk)
        _check_inputs(locked, revision, context, routing_run, provider_run)
        previous = locked.current_assessment
        if _same_assessment(previous, digest, revision, context, routing_run, provider_run, second_run, participants,
                            retrieval):
            encounter.state = refresh_state(locked)
            return previous
        _check_result(result, revision.text)
        assessment = Assessment.objects.create(
            encounter=locked, revision=revision, context=context, routing=routing_run, provider_run=provider_run,
            second_run=second_run, profiles_version=result.profiles_version, engine_version=result.engine_version,
            reference_sources=to_jsonable(result.reference_sources),
            encounter_checks=to_jsonable(result.encounter_checks), unsupported=to_jsonable(result.unsupported),
            summary=to_jsonable(result.summary), services=to_jsonable(result.services),
            completeness=to_jsonable(result.completeness), participants=participants, retrieval=retrieval,
            sha256=digest)
        # One INSERT for every proposal (round 6 bounded:5): a row per query held the assess stage in the worker.
        rows = Proposal.objects.bulk_create([
            Proposal(
                assessment=assessment, key=item.key, bucket=item.bucket, code=item.code, code_kind=item.code_kind,
                family=item.family, profile_version=item.profile_version, status=item.status,
                exclusion_reason=item.exclusion_reason, reinstatable=item.reinstatable,
                provider_display=item.provider_display, evidence=to_jsonable(item.evidence),
                rationale=item.rationale, checks=to_jsonable(item.checks),
                modifier_considerations=list(item.modifier_considerations), units=item.units,
                fingerprint=item.fingerprint, position=position, support=to_jsonable(item.support))
            for position, item in enumerate(result.proposals)])
        proposals = {row.key: row for row in rows}
        raised = _create_clarifications(locked, assessment, result, proposals)
        withdrawn = _withdraw_superseded(locked, assessment, raised)
        # Decisions carry between FINAL assessments only (HARNESS.md 12.1; refutation r1, Q1). An assess #1 whose peer
        # stages are owed neither carries nor invalidates one: it does not have the codes a peer review adds, so a code
        # whose checks read them (an endoscopic base, say) would lose its approval there for good. The final assessment
        # carries from the one that holds the current decisions - with Corti alone, the previous assessment, as before.
        carried = invalidated = 0
        if is_final(assessment):
            carried, invalidated = _carry_decisions(decision_holder(locked, exclude=assessment), assessment, proposals,
                                                    revision, context)
        locked.current_assessment = assessment
        locked.save(update_fields=['current_assessment', 'updated_at'])
        buckets = [item.bucket for item in result.proposals]
        audit.record(locked.workspace, 'assessment.created', encounter=locked, assessment=str(assessment.pk),
                     revision=revision.number, proposals=len(buckets), selected=buckets.count(SELECTED),
                     alternatives=buckets.count(ALTERNATIVE), excluded=buckets.count(EXCLUDED),
                     clarifications=len(raised), withdrawn=withdrawn, carried=carried, invalidated=invalidated)
        encounter.state = refresh_state(locked)
    encounter.current_assessment = assessment
    return assessment


# --- readiness and derived state -------------------------------------------------

def _active_jobs(encounter):
    return encounter.jobs.filter(state__in=ACTIVE_JOB_STATES).exists()


def _orphaned_sending(encounter):
    """Decision (k) of the core repair (2026-11-03; R6 4.6): whether a provider run of ``encounter`` was left 'sending'
    by a stage that no longer runs - its outcome never recorded (an answer that arrived and could not be written, or a
    write after it that failed: the job failed, and the stale sweep visits only running stages). A stage running now
    creates its own run after it starts, so a run created before the running stage started (or with none running) is
    never that stage's request in flight. Such a run may have reached the vendor and been billed."""
    sending = encounter.provider_runs.filter(state=ProviderRun.SENDING)
    running = encounter.jobs.filter(state=Job.RUNNING, started_at__isnull=False).order_by('-started_at').first()
    if running is not None:
        sending = sending.filter(created_at__lt=running.started_at)
    return sending.exists()


def _unreconciled_unknown(encounter):
    """Whether a provider outcome of ``encounter`` is unknown and not reconciled - the rule the derived state and every
    send door read (jobs._unreconciled_unknown is this one): a run recorded unknown, or one left 'sending' by a stage
    that no longer runs (_orphaned_sending, decision (k)), which blocks every further send like an unknown outcome."""
    return (encounter.provider_runs.filter(state=ProviderRun.UNKNOWN, reconciled_at__isnull=True).exists()
            or _orphaned_sending(encounter))


def decidable(proposal) -> bool:
    """Whether a reviewer can decide ``proposal``, an engine ProposalAssessment or a stored Proposal (both carry its
    bucket and reinstatable): selected, or excluded and reinstatable - _reviewable's rule before any decision. Never an
    alternative, nor a code excluded with no reinstatement (outside CPT-only results, or with no exact source evidence),
    which no action reaches (_actions) and whose CMS checks never ran. The assess stage traces only these codes and the
    API reads only their traces (jobs._retrieval, serializers; refutation round 9, retrieval-1, retrieval-2, page-1)."""
    return proposal.bucket == SELECTED or (proposal.bucket == EXCLUDED and bool(proposal.reinstatable))


def _reviewable(proposal, decision):
    """Selected proposals need an approve or reject. A documentation check's exclusion (reinstatable) needs the
    reviewer to confirm it or to reinstate the code and decide it; a reinstated exclusion needs an approve or reject."""
    return proposal.bucket == SELECTED or (proposal.bucket == EXCLUDED
                                           and (decision is not None or proposal.reinstatable))


def _could_bill(proposal, decision):
    """Whether a gated E/M is still on its way to a reviewed approval: selected and undecided, reinstated, or
    approved. A rejection, a confirmed exclusion and an exclusion nobody has decided yet bill nothing, so the same-day
    rule has nothing to hold (round 5, bypass:0); the exclusion's own blocker covers the undecided one."""
    if decision is None:
        return proposal.bucket == SELECTED
    return decision.action in (APPROVE, REINSTATE)


def _assessment_blockers(encounter, assessment):
    from . import answers  # local import: the details flow reads this module
    blockers = []
    if not is_final(assessment):
        blockers.append(NOT_FINAL_BLOCKER)
    if answers.date_confirmation_open(encounter):
        blockers.append(DATE_CONFIRMATION_BLOCKER)
    if assessment.context_id != encounter.current_context_id:
        blockers.append('The encounter context changed; re-assessment has not finished')
    run = assessment.provider_run
    if run is None:
        blockers.append('The provider was not run')
    elif run.state in UNSETTLED_RUN_STATES:
        blockers.append('The provider outcome is unknown')
    elif run.state == ProviderRun.NOT_SENT and (run.scope or {}).get('held') == ProviderRun.HELD_MEMBER_DATE_CONFLICT:
        # interpretation 19: held on purpose, never a failure (refutation r1, context lens)
        blockers.append('Nothing was sent: the service date entered as encounter metadata conflicts with the document')
    elif run.state != ProviderRun.SUCCEEDED:
        blockers.append('The provider request failed')
    open_clarifications = list(assessment.clarifications.filter(state=Clarification.OPEN))
    for clarification in open_clarifications:
        if clarification.scope == 'encounter' and clarification.proposal_id is None:
            blockers.append(f'Open clarification: {_human(clarification.fact)}')
    asked = {item.proposal_id for item in open_clarifications if item.proposal_id}
    current = current_decisions(assessment)
    # The review overlay (CORE-UX-DESIGN.md 4): each proposal's status and open questions as the current decisions and
    # member answers leave them, and the blocker of a decision the view no longer supports (D14: an approval of a base
    # code a reinstatement holds again waits until it is revoked).
    views = effective_view(assessment, current)
    reinstated = [p for p in _reinstated_procedures(assessment, current)
                  if views.get(p.key) is None or views[p.key].active]
    reviewable = 0
    for proposal in assessment.proposals.all():
        decision = current.get(proposal.pk)
        if not _reviewable(proposal, decision):
            continue
        reviewable += 1
        view = views.get(proposal.key)
        if (reinstated and _has_check(proposal, SAME_DAY_EM_GATE) and _could_bill(proposal, decision)
                and not (view is not None and view.reason == DETAIL_UNAVAILABLE)):
            # Also when this E/M was approved before the procedure was brought back. A visit a member's answer
            # excluded (its separate_em row answered 'Not documented' or 'Cannot confirm', refutation round 3 B-05) is
            # resolved (decision (f)): it names no same-day blocker, and its approval stays blocked by the view's own.
            blockers.append(_same_day_blocker(proposal, reinstated))
        if view is not None and view.blocker:
            blockers.append(view.blocker)
        if decision is not None and decision.action in (APPROVE, REJECT, CONFIRM):
            continue
        if view is not None and view.reason == DETAIL_UNAVAILABLE:
            continue  # a needed detail answered as unavailable: excluded, nothing to decide (P5's answers)
        if decision is not None:
            blockers.append(f'{proposal.code} was reinstated and has no decision')
        elif proposal.bucket == EXCLUDED:
            blockers.append(f'{proposal.code} was excluded by a documentation check: confirm the exclusion '
                            'or reinstate it')
        elif (bool(view.questions) if view is not None else proposal.pk in asked):
            blockers.append(f'{proposal.code} has an open clarification')
        elif (view.status if view is not None else proposal.status) == Proposal.NEEDS_CLARIFICATION:
            blockers.append(f'{proposal.code} needs clarification')
        else:
            blockers.append(f'{proposal.code} has no decision')
    if run is not None and run.state == ProviderRun.SUCCEEDED and reviewable == 0:
        # A succeeded run's provider check fails only when its response was refused whole, unread: the provider's
        # codes were never read, so nothing may say that none was proposed (round 7 bypass:1) - the merged second
        # review's as the primary's (skeptic of refutation 7c8 reports-5).
        refused = _refused_run(assessment) is not None
        # Nor while the second review made for this answer was not read: none was proposed in what was read only
        # (found while refuting the reports-5 repairs: "No CPT code was proposed" beside an unknown or failed one).
        unread = '' if refused else _second_review_unread(assessment)
        if refused:
            blockers.append('The provider response was not used')
        else:
            # Codes the provider proposed that nobody can decide - excluded with no reinstatement, or offered only as
            # alternatives (nothing here is reviewable) - were proposed: said as the panel says it, never "No CPT code
            # was proposed" beside the stored response and its own provider check (refutation p2, reports2:3).
            origins = [(proposal.support or {}).get('origin') for proposal in assessment.proposals.all()]
            if origins and all(origin == 'participant' for origin in origins):
                # A participant's code is never a proposal (refutation round 6, the session's D14): where every code
                # listed is a participant's alternative, this never says the provider proposed them - said as the panel
                # says it (app.js emptySelectionCopy; found at the integration of R6-MEANING). Who gave them, never
                # "independent": a code first given in peer review is never independent (refutation round 7,
                # display-2; HARNESS.md 11.1). Nor that the provider did not give them: its second review, unread here,
                # can select the same code (refutation round 8, wording-3).
                what = ('No code is selected for approval: each code listed was given by Astra or Fable and is offered '
                        'only as an alternative')
            elif origins:
                what = (f'No code is selected for approval: the {"response that was read" if unread else "provider"} '
                        'proposed only codes that were excluded or offered as alternatives')
            else:
                what = f'No CPT code was proposed{" in the response that was read" if unread else ""}'
            blockers.append(f'{what}; the second review {unread}' if unread else what)
    return blockers


SECOND_REVIEW_ENDED = {ProviderRun.UNKNOWN: 'has an unknown outcome', ProviderRun.FAILED: 'failed',
                       ProviderRun.NOT_SENT: 'was not sent', ProviderRun.CANCELLED: 'was not sent',
                       ProviderRun.SUCCEEDED: 'has not been read yet'}


def _unread_second_review(assessment):
    """The second review made for the answer the assessment reads (jobs._second_run_for, whatever its outcome) when the
    assessment did not read it; None when none was made or the assessment read it."""
    from .jobs import _second_run_for  # local import: jobs imports this module
    second = _second_run_for(assessment.revision, assessment.provider_run, any_outcome=True)
    if second is None or second.pk == assessment.second_run_id:
        return None
    return second


def _unread_second_reviews(assessment):
    """Every second review made for the answer the assessment reads (jobs._second_runs_for, whatever its outcome) that
    the assessment did not read, newest first: behind a newer retry an older one can stand whose outcome is unknown
    (refutation P2FR, ROLLBACK 0)."""
    from .jobs import _second_runs_for  # local import: jobs imports this module
    return [second for second in _second_runs_for(assessment.revision, assessment.provider_run, any_outcome=True)
            if second.pk != assessment.second_run_id]


def _second_review_unread(assessment):
    """How the second review made for the answer the assessment reads ended when the assessment did not read it; '' when
    none was made or the assessment read it."""
    second = _unread_second_review(assessment)
    return '' if second is None else SECOND_REVIEW_ENDED.get(second.state, 'has not finished')


def _refused_run(assessment):
    """The run whose response the assessment read and refused whole - its own provider check failed on a succeeded
    run: provider.status for the primary, provider.second_review for the merged second review - or None. (A succeeded
    run's check fails only for a refusal: provider checks, round 7 bypass:1; engine._second_review_check.)"""
    failed = {check.get('id') for check in assessment.encounter_checks or [] if check.get('status') == 'fail'}
    for check_id, run in (('provider.status', assessment.provider_run), ('provider.second_review',
                                                                        assessment.second_run)):
        if run is not None and run.state == ProviderRun.SUCCEEDED and check_id in failed:
            return run
    return None


def _decisions_waiting(assessment):
    """(waiting, reviewable): the proposals a reviewer decides, and those of them with no decision that stands - counted
    as readiness counts them (_assessment_blockers)."""
    current = current_decisions(assessment)
    views = effective_view(assessment, current)
    waiting = reviewable = 0
    for proposal in assessment.proposals.all():
        decision = current.get(proposal.pk)
        if not _reviewable(proposal, decision):
            continue
        reviewable += 1
        view = views.get(proposal.key)
        if view is not None and view.reason == DETAIL_UNAVAILABLE and (decision is None
                                                                        or decision.action != APPROVE):
            continue  # excluded by a member's answer: it needs no decision
        if decision is None or decision.action not in (APPROVE, REJECT, CONFIRM):
            waiting += 1
    return waiting, reviewable


def _sentence(text):
    plain = str(text).strip()
    return plain if not plain or plain.endswith(('.', '!', '?')) else f'{plain}.'


def reinstated_codes(assessment, current=None):
    """(code, family) of the excluded proposals a reviewer reinstated and has not rejected (their current decision is
    the reinstatement, or an approval that rests on it): decided like selected codes, so counted as selected ones
    wherever a documented service's code is stated (reviewed_completeness)."""
    current = current_decisions(assessment) if current is None else current
    return [(proposal.code, proposal.family) for proposal in assessment.proposals.filter(bucket=EXCLUDED)
            if current.get(proposal.pk) is not None and current[proposal.pk].action in (REINSTATE, APPROVE)]


def reviewed_completeness(assessment, current=None):
    """The documented-service reconciliation the assessment recorded, as the review leaves it: with the codes a reviewer
    reinstated counted as selected ones (engine.reviewed_completeness; refutation P2FR, EUS-SECOND). The assessment's
    own record when none is reinstated. The reports, the encounter view, coding completeness and the bounded second
    review's items all read this one view."""
    completeness = assessment.completeness or {}
    # an assessment not persisted (a reading the engine just made) carries no reviewer's decision
    reinstated = reinstated_codes(assessment, current) if completeness and getattr(assessment, 'pk', None) else []
    if not reinstated:
        return completeness
    from .validation import engine  # local import: the engine is only needed when a code was reinstated
    proposals = list(assessment.proposals.exclude(bucket=ALTERNATIVE))
    return engine.reviewed_completeness(
        assessment.services, completeness, [(p.code, p.family) for p in proposals if p.bucket == SELECTED], reinstated,
        [(p.support or {}).get('service') for p in proposals if (p.support or {}).get('service')])


def coding_completeness(encounter):
    """Whether the ENCOUNTER's coding is complete - kept apart from whether one proposal is ready for review.

    'incomplete' while a documented service has no supported proposal, a conflict in the record is unanswered, or a
    question is open; 'pending_review' when every documented service has a proposal and the reviewed report cannot be
    produced yet - its statement counts the decisions missing, or, when every proposal is decided, names what readiness
    still waits for (refutation 7c8, reports-3); 'reviewed' when the reviewed report could be produced. Never 'verified':
    code-set membership and NCCI edits are not connected, and the documented-service reading can miss wording it does
    not recognise."""
    assessment = live_assessment(encounter)
    if assessment is None:
        return {'state': 'not_established', 'statement': 'The current revision has not been assessed yet.',
                'reasons': []}
    base = dict(reviewed_completeness(assessment) or {})  # a reinstated code counts (refutation P2FR, EUS-SECOND)
    if not base:
        return {'state': 'not_established', 'reasons': [],
                'statement': 'This assessment was made before the documented-service reconciliation existed, so its '
                             'completeness is not established.'}
    reasons = [r for r in base.get('reasons', []) if 'open question' not in r]
    # the questions the review overlay leaves open: a released one is not counted, an added one is (CORE-UX-DESIGN.md 4)
    views = effective_view(assessment)
    open_questions = len(open_questions_of(assessment, views))
    if open_questions:
        reasons.append(f'{open_questions} open question{"s" if open_questions != 1 else ""}')
    unavailable = [view.code for view in views.values() if view.reason == DETAIL_UNAVAILABLE]
    if unavailable:
        reasons.append(f'{", ".join(dict.fromkeys(unavailable))} excluded: a needed detail was answered as not '
                       'documented or not confirmable')
    standing = ('Code-set membership and NCCI edits are not verified (no licensed source is connected), and the '
                'documented-service reading can miss wording it does not recognise.')
    if reasons:
        return {'state': 'incomplete', 'reasons': reasons,
                'statement': 'Coding for this encounter is incomplete: ' + '; '.join(reasons) + '. Supported proposals '
                             'stay available for review. ' + standing}
    ready = readiness(encounter)
    if ready['reviewed']:
        return {'state': 'reviewed', 'reasons': [],
                'statement': 'Every documented service has a proposal with a reviewer\'s decision. This is reviewed, '
                             'not verified, coding. ' + standing}
    # A decision is said to be missing only of the proposals that have none: a decided set waiting on a context change,
    # processing or a gate is told what it waits for (refutation 7c8, reports-3: "each still needs a reviewer's
    # decision" beside current approvals that carried unchanged once the re-assessment ran).
    waiting, reviewable = _decisions_waiting(assessment)
    if waiting:
        missing = ('each still needs a reviewer\'s decision' if waiting == reviewable else
                   f'{waiting} of {reviewable} still need{"s" if waiting == 1 else ""} a reviewer\'s decision')
        return {'state': 'pending_review', 'reasons': [],
                'statement': f'Every documented service has a proposal; {missing}. ' + standing}
    lead = ('Every documented service has a proposal with a reviewer\'s decision' if reviewable
            else 'No proposal waits for a reviewer\'s decision')
    return {'state': 'pending_review', 'reasons': [],
            'statement': f'{lead}, but the review is not complete. '
                         + ''.join(f'{_sentence(blocker)} ' for blocker in ready['blockers']) + standing}


def readiness(encounter):
    """{'draft', 'reviewed', 'blockers'}: a reviewed report needs every selected (or reinstated) proposal
    decided, no open encounter-scoped clarification, a settled provider result and no pending processing."""
    encounter = Encounter.objects.get(pk=encounter.pk)
    revision = encounter.current_revision
    if revision is None:
        return {'draft': False, 'reviewed': False, 'blockers': ['No document has been recorded yet']}
    blockers = []
    if _active_jobs(encounter):
        blockers.append('Processing has not finished')
    if revision.extraction_status == SourceRevision.FAILED:
        blockers.append('No text was extracted')
    assessment = live_assessment(encounter)
    if assessment is None:
        return {'draft': False, 'reviewed': False,
                'blockers': blockers or [f'Revision {revision.number} has not been assessed yet']}
    blockers += _assessment_blockers(encounter, assessment)
    blockers = list(dict.fromkeys(blockers))
    return {'draft': True, 'reviewed': not blockers, 'blockers': blockers}


def _failed_stage_state(encounter, revision, job):
    """(state, run): the state a failed or unknown stage leaves, with the stage's own request when that state is
    provider_failed (else None); (None, None) when the assessment's own state stands."""
    if job.kind == Job.EXTRACT:
        return 'extraction_failed', None
    if job.kind in Job.PARTICIPANT_KINDS + Job.PEER_KINDS:
        # A harness participant's stage - its first reading's or its peer review's (HARNESS.md 12.1) - never makes the
        # encounter provider_failed, which is Corti's state: its own failures are runs of its own, and the chain goes on
        # (I10). One its worker left mid-send is the encounter-wide unknown outcome every further send waits on
        # (HARNESS.md 2); any other failure is the stage's.
        return ('provider_unknown' if job.state == Job.UNKNOWN else 'processing_failed'), None
    if job.kind not in (Job.PREDICT, Job.REVIEW2):
        return 'processing_failed', None
    if job.state == Job.UNKNOWN:
        return 'provider_unknown', None
    purpose = ProviderRun.PRIMARY if job.kind == Job.PREDICT else ProviderRun.SECOND_REVIEW
    run = (encounter.provider_runs.filter(revision=revision, created_at__gte=job.created_at, purpose=purpose)
           .order_by('-created_at', '-pk').first())
    if run is None:
        # A second review that failed before recording its run sent nothing and left the assessment as it was: the
        # assessment's own state stands, and the second-review card says why it did not complete (ec5 re-check: it read
        # "Provider not run" beside the primary request's proposals). None: derive the state from the assessment.
        return (None if job.kind == Job.REVIEW2 else 'provider_not_run'), None
    # Refutation r2, L5-3: a reservation is written before any network I/O and is marked 'sending' only as the request
    # leaves (jobs._send), so one its stage left behind - the stage failed between the two, and nothing runs now (the
    # caller reads no active job) - never reached the provider. Nothing is being confirmed and nothing could settle it
    # as an unknown outcome (reconcile takes only unknown ones): it reads as the request recorded not sent that
    # jobs._send and the stale sweep settle it to, never as provider_unknown ("Nothing will be sent again") while every
    # send door, which reads _unreconciled_unknown, sends.
    state = ProviderRun.NOT_SENT if run.state == ProviderRun.RESERVED else run.state
    if state in UNSETTLED_RUN_STATES:
        return 'provider_unknown', None
    if job.kind == Job.REVIEW2 and state in (ProviderRun.NOT_SENT, ProviderRun.CANCELLED):
        # Nor did one whose request was never sent - stopped before sending, or settled as not sent when the stage was
        # closed: no request failed, so never provider_failed ("The provider request failed" beside a primary answer
        # that succeeded, refutation P2FR, ROLLBACK 1: an undo then left that state to 057a7d39, which labels it by its
        # name). None: the assessment's own state, worded from that run ('Second review not sent').
        return None, None
    if state == ProviderRun.SUCCEEDED:
        return 'processing_failed', None
    return 'provider_failed', run


def _review_state(encounter, assessment):
    if readiness(encounter)['reviewed']:
        return 'reviewed'
    current = current_decisions(assessment)
    views = effective_view(assessment, current)
    reviewable = [item for item in assessment.proposals.all() if _reviewable(item, current.get(item.pk))]
    encounter_question = assessment.clarifications.filter(
        state=Clarification.OPEN, scope='encounter', proposal__isnull=True).exists()
    if not reviewable:
        return 'needs_clarification' if encounter_question else 'no_codes'

    def status(item):
        view = views.get(item.key)
        return item.status if view is None else view.status

    if encounter_question or any(status(item) == Proposal.NEEDS_CLARIFICATION and item.pk not in current
                                 for item in reviewable):
        return 'needs_clarification'
    return 'ready_for_review'


def decision_root(decision):
    """The decision a carried decision was copied from, followed back to the reviewer's own act."""
    root = decision
    while root.carried_from_id:
        root = root.carried_from
    return root


def reinstatement_for(decision):
    """The reinstate decision that a current decision on an excluded proposal rests on, following carries."""
    node = decision
    while node is not None:
        if node.action == Decision.REINSTATE:
            return node
        prior = (Decision.objects.filter(proposal_id=node.proposal_id, action=Decision.REINSTATE,
                                         sequence__lt=node.sequence, invalidation__isnull=True)
                 .select_related('reviewer').order_by('-sequence').first())
        if prior is not None:
            return prior
        node = node.carried_from
    return None


def latest_job(encounter):
    """The most recently created job of the encounter's current revision, or None."""
    if encounter.current_revision_id is None:
        return None
    return encounter.jobs.filter(revision_id=encounter.current_revision_id).order_by('-created_at', '-pk').first()


def can_resume(encounter):
    """Whether a member may resume: the current revision's latest stage was cancelled and nothing runs."""
    return _derive_state(encounter) == 'stopped'


def _derive_state(encounter):
    return _state_and_run(encounter)[0]


def _state_and_run(encounter):
    """(state, run): the derived state and, for provider_failed, the provider run that state reads - the failed stage's
    own request, else the run the live assessment read - so a screen explains the failure with that run, never with one
    picked by recency (ec5 skeptic, new:provider-failed-card-older-run: a request stopped or swept before sending is
    newer than the run in use). None for every other state."""
    revision = encounter.current_revision
    if revision is None or _active_jobs(encounter):
        return 'processing', None
    # Decision (k), HARNESS.md 2 (refutation r2, L5-1): an outcome still unknown - a run recorded unknown and not
    # reconciled, or one left 'sending' by a stage that no longer runs - blocks every further send, and the encounter
    # waits on its reconciliation whatever failed after it. A failure read past it tells the member to upload the
    # document again (RESUBMIT_STATES), and that upload makes the same paid request again while the first may have been
    # answered and billed: such a failure never outranks it. A member's Stop still reads stopped where it did (its
    # Resume sends nothing past the block), and provider_not_run, which says no request was made and offers nothing,
    # reads as before; the review queue lists the reconciliation either way.
    unknown = _unreconciled_unknown(encounter)

    def failure(state, run=None):
        return ('provider_unknown', None) if unknown and state in RESUBMIT_STATES else (state, run)

    if revision.extraction_status == SourceRevision.FAILED:
        return failure('extraction_failed')
    latest = encounter.jobs.filter(revision=revision).order_by('-created_at', '-pk').first()
    if latest is not None and latest.state == Job.CANCELLED:
        return 'stopped', None
    if revision.extraction_status == SourceRevision.PENDING:
        return ('processing', None) if latest is None else failure('extraction_failed')
    if latest is not None and latest.state in (Job.FAILED, Job.UNKNOWN):
        failed, run = _failed_stage_state(encounter, revision, latest)
        if failed is not None:
            return failure(failed, run)
    assessment = live_assessment(encounter)
    if assessment is None or assessment.context_id != encounter.current_context_id:
        return ('provider_unknown' if unknown else 'processing'), None
    run = assessment.provider_run
    if run is None:
        return 'provider_not_run', None
    if run.state in UNSETTLED_RUN_STATES or unknown:
        # An outcome still unknown - the second review's included - blocks every further send until a member reconciles
        # it, so the encounter waits on that, whatever the run in use says (refutation r1, sends-5: a second review the
        # provider never answered left "Ready for review", then "Reviewed" and off the review queue, while the same
        # runs left by a worker that died mid-send read "Provider outcome unknown").
        return 'provider_unknown', None
    if run.state == ProviderRun.NOT_SENT and (run.scope or {}).get('held') == ProviderRun.HELD_MEMBER_DATE_CONFLICT:
        # nothing was sent on purpose: the date question is open, and the encounter waits on it, not on the provider
        return _review_state(encounter, assessment), None
    if run.state != ProviderRun.SUCCEEDED:
        return 'provider_failed', run
    state = _review_state(encounter, assessment)
    refused = _refused_run(assessment) if state == 'no_codes' else None
    if refused is not None:
        # A response refused whole - the primary's or the second review's - was never read, so 'no_codes' ("No CPT codes
        # proposed") would report it as one that proposed nothing (round 7 bypass:1; skeptic of refutation 7c8
        # reports-5): the provider gave no usable result, and the state reads that run. Only in place of 'no_codes': a
        # question or a proposal to decide still holds the encounter for the reviewer.
        return 'provider_failed', refused
    return state, None


def state_run(encounter):
    """The provider run the encounter's provider_failed state reads, or None: also when the stored state (the one the
    API serves) is not provider_failed, so the run named always explains the state shown."""
    if encounter.state != 'provider_failed':
        return None
    state, run = _state_and_run(encounter)
    return run if state == 'provider_failed' else None


def refresh_state(encounter):
    """Recompute the cached Encounter.state (API.md vocabulary); writes only when it changed."""
    with transaction.atomic():
        locked = _lock(encounter)
        state = _derive_state(locked)
        if locked.state != state:
            Encounter.objects.filter(pk=locked.pk).update(state=state, updated_at=timezone.now())
    encounter.state = state
    return state


# --- the harness record, as the screen and the reports state it (HARNESS.md 5-7) --------------------------------------
#
# Read-only, from the rows. Three kinds of status are never conflated (I4): who PROPOSED a code (proposed_by), what the
# CMS reference checks found (reference_check), and a member's decision (current_decisions). None of them decides
# another: agreement between participants and passing checks approve nothing (I3).

CORTI = 'corti'
# (name, label, vendor, model requested), in harness order: the models are HARNESS.md 1's code constants (Corti's API
# takes no model identifier); the adapters own them, and a run records what it actually requested and got back.
HARNESS_PARTICIPANTS = ((CORTI, 'Corti', 'Corti', ''),
                        ('astra', participants.LABELS['astra'], participants.VENDORS['astra'], 'gpt-6-astra'),
                        ('fable', participants.LABELS['fable'], participants.VENDORS['fable'], 'claude-fable-5-1'))
CORTI_PROVIDERS = ('corti', 'replay')  # Corti's runs, live or replayed from its recordings
CMS_CHECKS = ('pfs.presence', 'mue.units', 'pfs.endoscopic_base')
CHECK_WORDS = {'pass': 'passed', 'warn': 'needs attention', 'fail': 'failed', 'not_verified': 'not verified',
               'info': 'noted', 'not_applicable': 'not applicable'}
PTP_NOT_CONNECTED = ('NCCI procedure-to-procedure edits are not connected, so bundling with other codes is not '
                     'verified.')
# What is not connected, stated on every proposal and the encounter (HARNESS.md 5).
NOT_CONNECTED = ('NCCI procedure-to-procedure edits (AMA licence agreement not accepted)',
                 'AMA CPT descriptors and guidelines (no licence)', 'Payer policies')
COST_BASIS = 'estimated from published rates, not reconciled to an invoice'
PRICING_MODULE = 'studio.participants.pricing'
# A participant's state in Assessment.participants (types.PARTICIPANT_STATES), in words.
RECORD_WORDS = {
    'read': 'answered; the reading was used',
    'refused': 'answered; the reading was not used',
    'failed': 'the request failed',
    'unknown': 'the outcome is unknown: no complete response was recorded',
    'not_sent': 'nothing was sent',
    'blocked': 'nothing was sent: a previous request has an unknown outcome',
    'not_configured': 'not configured on this installation',
    'not_run': 'no request was made for this revision',
}


def participant_of(run):
    """The harness participant a provider run belongs to: Corti for its live or replayed runs, else its provider."""
    return CORTI if run.provider in CORTI_PROVIDERS else run.provider


def run_mode(run):
    """'replay' for a recorded response, which never presents as live output: Corti's replay provider, or a harness
    participant whose adapter ran in replay mode (its run's scope records the mode), in either phase; 'live'
    otherwise."""
    if run.provider == 'replay':
        return 'replay'
    if run.purpose in (ProviderRun.INDEPENDENT, ProviderRun.PEER_REVIEW) and (run.scope or {}).get('mode') == 'replay':
        return 'replay'
    return 'live'


# The participant states whose recorded reason can say more than the state does (a refusal reason, an error, why
# nothing was sent or no request was made).
REASONED_STATES = ('refused', 'failed', 'not_sent', 'unknown', 'not_run')


def record_reason(record):
    """The reason a participant's Assessment.participants entry recorded, where it says more than its state's words
    (RECORD_WORDS); '' otherwise."""
    state = record.get('state')
    reason = str(record.get('reason') or '').strip()
    words = RECORD_WORDS.get(state, '')
    if state not in REASONED_STATES or reason.rstrip('.').lower() == words.lower():
        return ''
    return reason


def record_words(record):
    """A participant's Assessment.participants entry in one plain clause, with the reason it recorded where that says
    more than the state (a refusal reason, an error, why nothing was sent)."""
    state = record.get('state')
    words = RECORD_WORDS.get(state, str(state or 'unknown state'))
    reason = record_reason(record).rstrip('.')
    if not reason:
        return words
    if state in ('not_sent', 'not_run') and reason.lower().startswith('nothing was sent'):
        return 'n' + reason[1:]  # the reason already says so: "Nothing was sent: ..."
    return f'{words}: {reason}'


def listed_codes(record):
    """The codes of a participant's Assessment.participants entry it proposed that may be listed by name, each once,
    in order - the engine's own rule for a participant's code (engine.participant_listable: a CPT or HCPCS code's shape;
    refutation round 4, the session's D9, shapes-1: the proposal provider's rule of 1 to MAX_LISTED_CODE characters
    listed 'W/LES(S)' here), as its participants.summary lists them. Any other 'code' may carry wording, a CPT
    descriptor say, so it is never shown, never truncated (I9; refutation r1 IND-1: the participants row served whatever
    text a participant wrote as a code); how many there are is unlisted_count's. Read when serving, so records already
    stored are covered."""
    from .validation import engine  # local import: only the engine's rule is needed here

    codes = []
    for item in record.get('codes') or []:
        code = item.get('code') if isinstance(item, dict) else None
        if engine.participant_listable(code) and code not in codes and item.get('quote'):
            # a code its reading listed with no quote found in the document is not one it proposed (the engine counts
            # no such entry; refutation round 4, truth-2: "Codes it proposed: 45385, 45380." beside the card's "Astra
            # did not propose it")
            codes.append(code)
    return codes


def unlisted_count(assessment, record):
    """How many codes the frozen first reading an Assessment.participants entry of ``assessment`` names gave that the
    engine does not read: engine.participant_unlisted_count, the number its participants.summary states, of the reading
    re-read when serving as the assessment read it (jobs.recorded_reading: the run the entry names, read by the adapter
    version that recorded it, and only when its sha256 is the entry's reading_sha256), so records already stored are
    covered (refutation round 5, the session's D13: the row counted the entry's codes, which keep one entry per value,
    so '45385-59' given twice was 1 on the row beside the summary's 2). 0 for an entry whose reading was not used (the
    engine read none of its codes). None when that reading cannot be read again as recorded: the row then states no
    count rather than another one."""
    from .jobs import recorded_reading  # local import: jobs imports this module
    from .validation import engine  # local import: only the engine's count is needed here

    if record.get('state') != 'read':
        return 0
    _, reading = recorded_reading(assessment.revision, record)
    if reading is None:
        log.warning('the frozen reading of %s on assessment %s could not be read as recorded', record.get('name'),
                    assessment.pk)
        return None
    return engine.participant_unlisted_count(reading.codes)


def proposed_by(proposal):
    """Who proposed the code, in harness order (I4: a proposal, never an approval): Corti for its own proposals and
    alternatives (origin primary or second_review), and each participant the engine named in support['proposed_by'] -
    the proposers of a participant's own proposal (origin participant), or a participant that also proposed Corti's."""
    support = proposal.support or {}
    named = {name for name in support.get('proposed_by') or [] if isinstance(name, str)}
    corti = (support.get('origin') or 'primary') in ('primary', 'second_review') or CORTI in named
    return ([CORTI] if corti else []) + [name for name in participants.PARTICIPANTS if name in named]


def listed_by(proposal):
    """The participants the engine recorded as having listed a participant's alternative's code with no entry that
    quotes the document verbatim (support['listed_by']): they did not propose it, so they are never among proposed_by,
    and each surface that says who proposed the alternative names them apart, as having listed it (refutation round 5,
    the session's D12). In harness order; [] for any other proposal, and for a record that carries none or no list."""
    listed = (proposal.support or {}).get('listed_by')
    named = {name for name in listed if isinstance(name, str)} if isinstance(listed, list) else set()
    proposers = set(proposed_by(proposal))
    return [name for name in participants.PARTICIPANTS if name in named and name not in proposers]


# How Corti stands to a proposal's code (corti_relation), in the order a Corti entry of the code is looked for.
CORTI_RELATIONS = ('proposer', 'selected_without_exact_passage', 'selected_apart', 'candidate', 'second_review', 'none')


def corti_relation(proposal):
    """How Corti stands to ``proposal``'s code on its assessment, so that "Corti did not propose this code" is said
    only when Corti has no entry for the code at all (HARNESS.md 11.4; refutation round 2, truth-6: a participant's own
    proposal said so beside Corti's own excluded selection of the same code):
      'proposer'                        Corti is among its proposers (proposed_by);
      'selected_without_exact_passage'  Corti's response selected the code, and that selection is excluded because none
                                        of its passages matches the document text exactly (the engine's NO_EVIDENCE),
                                        so it is listed apart and carries no proposal;
      'selected_apart'                  Corti's response selected it, and that selection is another entry: excluded for
                                        another reason - out of scope, beside a participant's own entry of the code,
                                        which is then an alternative (or, which the engine never records, a proposal of
                                        its own);
      'candidate'                       Corti's response listed it without selecting it: as a candidate, or as an
                                        alternative to a code it selected (the token names no role; the code's
                                        Alternatives row says which);
      'second_review'                   only Corti's bounded second review listed it, without adding it as a proposal
                                        (a code it selected and did not add, or a candidate or an alternative of it:
                                        its record does not say which);
      'none'                            Corti has no entry for the code on this assessment.
    Read from the assessment's own proposals of the same code; Corti's are those of origin primary or second_review,
    as proposed_by reads them. The page and the engine's rationale (_Harness._lead) word 'candidate' and
    'second_review' in one sentence each that names no role (refutation round 3, truth-5: an alternative to 45385 was
    said to be listed "only as a candidate")."""
    from .validation.engine import NO_EVIDENCE  # local import: only the engine's exclusion reason is needed here

    if CORTI in proposed_by(proposal):
        return 'proposer'
    entries = [other for other in Proposal.objects.filter(assessment_id=proposal.assessment_id, code=proposal.code)
               .exclude(pk=proposal.pk) if ((other.support or {}).get('origin') or 'primary') in ('primary',
                                                                                                  'second_review')]
    primary = [other for other in entries if ((other.support or {}).get('origin') or 'primary') == 'primary']
    selected = [other for other in primary if other.bucket != Proposal.ALTERNATIVE]
    if any(other.bucket == Proposal.EXCLUDED and other.exclusion_reason == NO_EVIDENCE for other in selected):
        return 'selected_without_exact_passage'
    if selected:
        return 'selected_apart'
    if primary:
        return 'candidate'
    return 'second_review' if entries else 'none'


def participant_positions(proposal, records):
    """{name: {position, detail, quote}} for each harness participant the assessment had configured
    (Assessment.participants; {} when none was): its position in the reading the entry records - the frozen first
    reading (HARNESS.md 12.3) - from a reading that was used, 'proposed' (with its first located quote),
    'advised_not_to_code' (its reason and quote) or 'not_proposed'; else 'not_run' with why. A participant that first
    proposed the code after peer review (the engine's support['phases'], HARNESS.md 11.1) keeps its first reading's
    position, and its detail says both - that this is its first reading's position, and that it proposed the code after
    peer review - so a proposer is never said not to have proposed its own code (refutation round 2, truth-2: "Fable did
    not propose this code." beside proposed_by ['fable']). A first reading that listed the code with no quote found in
    the document proposed nothing (the engine counts no such entry: refutation round 1, EV-2 = IND-3), so its position
    is 'not_proposed', and its detail says the first reading listed it and did not propose it - whether or not the
    participant then proposed the code after peer review, which its detail then adds. One frozen first reading has one
    position: it was 'proposed' ("... none of its quotes was found in the document") where peer review did not propose
    the code, beside proposed_by and the engine's "not counted as a proposer" (refutation round 4, truth-2), and it is
    never said to have proposed the code in its first reading and "again" after peer review (refutation round 3,
    truth-2). Positions are kept beside the proposal and decide nothing (I2, I3)."""
    phases = (proposal.support or {}).get('phases')
    later = ({name for name, phase in phases.items() if phase == ProviderRun.PEER_REVIEW}
             if isinstance(phases, dict) else set())
    out = {}
    for record in records or []:
        name = record.get('name') if isinstance(record, dict) else None
        if name not in participants.PARTICIPANTS or record.get('state') == 'not_configured':
            continue
        label = participants.LABELS[name]
        if record.get('state') != 'read':
            out[name] = {'position': 'not_run', 'detail': f'{label}: {record_words(record)}.', 'quote': ''}
            continue
        proposed = {item.get('code'): item.get('quote') or '' for item in record.get('codes') or []}
        advised = {item.get('code'): item for item in record.get('not_coded') or []}
        first = ' in its first reading' if name in later else ''
        if proposal.code in proposed and not proposed[proposal.code]:
            out[name] = {'position': 'not_proposed', 'quote': '',
                         'detail': f'{label} listed this code in its first reading, but none of its quotes was found '
                                   'in the document, so that reading did not propose it.'}
            again = ''
        elif proposal.code in proposed:
            # the engine's own words for a located quote (support['participants']): never "with evidence", which called
            # a denial, a failed act or another procedure's sentence evidence for the code (refutation round 6,
            # R6-MEANING, negation-4, ownership-7; the owner's 2026-11-03 directive: a quotation existing verbatim must
            # not itself establish clinical support)
            out[name] = {'position': 'proposed',
                         'detail': f'{label} proposed this code{first}, quoting the document verbatim.',
                         'quote': proposed[proposal.code]}
            again = ' again'
        elif proposal.code in advised:
            item = advised[proposal.code]
            out[name] = {'position': 'advised_not_to_code', 'quote': item.get('quote') or '',
                         'detail': f'{label} advised not to code it{first}: {_human(item.get("reason") or "other")}.'}
            again = ''
        else:
            out[name] = {'position': 'not_proposed', 'detail': f'{label} did not propose this code{first}.',
                         'quote': ''}
            again = ''
        if first:
            out[name]['detail'] += f' It proposed it{again} after peer review.'
    return out


def reference_check(proposal):
    """The proposal's CMS reference check (I4: apart from who proposed it and from any decision), from its pfs.presence,
    mue.units and pfs.endoscopic_base checks: 'attention' when one warns or fails, 'not_verified' when none ran or one
    could not be verified, else 'passed'. Its detail always says that PTP edits are not connected."""
    checks = [check for check in proposal.checks or [] if check.get('id') in CMS_CHECKS]
    statuses = {check.get('status') for check in checks}
    if statuses & {'warn', 'fail'}:
        state = 'attention'
    elif not checks or 'not_verified' in statuses:
        state = 'not_verified'
    else:
        state = 'passed'
    ran = '; '.join(f'{check.get("label") or check.get("id")}: '
                    f'{CHECK_WORDS.get(check.get("status"), str(check.get("status")))}' for check in checks)
    return {'state': state, 'detail': (f'{ran}. ' if ran else 'No CMS reference check ran for this code. ')
            + PTP_NOT_CONNECTED}


def _shown(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return '' if value is None else str(value)


def retrieved(entry, field):
    """An Assessment.retrieval entry's facts or passages: the dict items of that list, [] for anything else (the entries
    come from the passages package; a malformed one shows nothing rather than failing the page or the report)."""
    items = entry.get(field) if isinstance(entry, dict) else None
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def proposal_retrieval(proposal, retrieval):
    """The retrieval trace of the proposal's code (Assessment.retrieval) as one list: each fact the checks' lookup read,
    then each CMS passage retrieved for it, with its source key, release and page or section."""
    out = []
    for entry in retrieval or []:
        if not isinstance(entry, dict) or entry.get('code') != proposal.code:
            continue
        for fact in retrieved(entry, 'facts'):
            out.append({'kind': 'fact', 'source_key': _shown(fact.get('source_key')),
                        'release': _shown(fact.get('release')), 'label': _shown(fact.get('field')),
                        'value': _shown(fact.get('value')), 'page': '', 'section': '', 'text': ''})
        for passage in retrieved(entry, 'passages'):
            topic = _shown(passage.get('topic')) + (f' {_shown(passage.get("topic_value"))}'
                                                    if passage.get('topic_value') else '')
            out.append({'kind': 'passage', 'source_key': _shown(passage.get('source_key')),
                        'release': _shown(passage.get('release')), 'label': topic, 'value': '',
                        'page': _shown(passage.get('page')), 'section': _shown(passage.get('section')),
                        'text': _shown(passage.get('text'))})
    return out


USD_PLACES = Decimal('0.0001')  # an estimate is shown to four decimals (API.md: "0.0270")


def _usd(value):
    """An estimate - studio.participants.pricing's {'estimated_usd': '0.027000', 'rates': ..., 'basis': ...} - as USD
    text with four decimals, rounded half up as pricing rounds ('0.0270'); None for no estimate, or for one that is not
    a finite amount. (Review read the key 'usd', which pricing never returns, so no cost was ever shown: refutation r1
    FG-3, sends-4.)"""
    if isinstance(value, dict):
        value = value.get('estimated_usd')
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        return f'{amount.quantize(USD_PLACES, rounding=ROUND_HALF_UP):f}' if amount.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def estimated_cost(run):
    """The run's estimated cost in USD as text ('0.0412'), from studio.participants.pricing's fixed, dated rates
    (HARNESS.md 6: estimated from published rates, not reconciled to an invoice). A tool loop (HARNESS.md 11.2) is
    several requests, so it is priced exchange by exchange (pricing.estimate_loop: Astra's long-context rate is a
    property of one request), never as its usage summed over the exchanges - and only when the exchanges recorded add up
    to the usage the run records. None for Corti (its usage is in credits, not USD), for a run that reported no usage (a
    reuse, a request not sent), where the pricing module is not installed, where a loop's exchanges do not add up to its
    usage, where an exchange that may have been billed reported no usage (unpriced_exchanges: an estimate of the others
    is no estimate of the run), and where pricing cannot price the usage: an estimate is informational, so it never
    fails the page or a report (its error is logged)."""
    if run is None or run.provider not in participants.PARTICIPANTS or not run.usage:
        return None
    try:
        pricing = importlib.import_module(PRICING_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != PRICING_MODULE:
            raise
        return None
    try:
        exchanges = list(run.exchanges.order_by('turn').values_list('turn', 'state', 'usage'))
        usages = [dict(usage or {}) for _, _, usage in exchanges]
        if run.usage_basis != participant_loop.LOOP_USAGE_BASIS and len(usages) <= 1:
            return _usd(pricing.estimate(run.requested_model, dict(run.usage)))
        reported = participant_loop.summed_usage([usage for usage in usages if usage])
        if _unpriced(exchanges) or reported != dict(run.usage):
            return None
        return _usd(pricing.estimate_loop(run.requested_model, usages))
    except Exception:  # noqa: BLE001 - logged; no estimate is shown rather than a failed page or report
        log.exception('the usage of run %s could not be priced', run.pk)
        return None


def _unpriced(exchanges):
    """[(turn, state)] of the (turn, state, usage) ``exchanges`` of a tool loop that may have reached the vendor - every
    one not recorded not sent - and reported no usage; [] for one exchange or none, whose run's own usage decides."""
    if len(exchanges) <= 1:
        return []
    return [(turn, state) for turn, state, usage in exchanges if state != ProviderRun.NOT_SENT and not usage]


def unpriced_exchanges(run):
    """The exchanges of a participant's tool loop that leave its cost unknown, as (turn, state): each may have been
    billed - it was not recorded not sent - and reported no usage, so the run has no estimate (estimated_cost), and the
    reports and the trace say which (refutation round 2, truth-12: pricing.estimate_loop counted such an exchange and
    priced the rest, and that sum was shown as the run's cost). An exchange recorded not sent cost nothing. [] for
    Corti's runs and for a run of one exchange or none."""
    if run is None or run.provider not in participants.PARTICIPANTS:
        return []
    return _unpriced(list(run.exchanges.order_by('turn').values_list('turn', 'state', 'usage')))


# --- harness@2: phases, frozen records, the participants' references, candidates, confirmations (HARNESS.md 11-12) --
#
# Read-only from the rows, except confirm_finding. Assessment.participants carries each model participant's frozen
# phase-1 record and, on assess #2 and its re-assessments, its peer review (12.3). A stored run is read again as the
# adapter version that recorded it, with the refs its own tool calls returned (12.1), so its references used are
# checked against those exactly as when it was first read. Three kinds of reference are never merged (11.2): what each
# participant retrieved (its tool calls), what it says it used (its references_used, each checked against its own
# run's), and what the reconciliation retrieved (Assessment.retrieval). A confirmation is a fact a reviewer confirmed
# from a participant's located passage, never a decision: it approves nothing (I3, I4).

MODEL_PARTICIPANTS = participants.PARTICIPANTS
REF_FACT = 'fact:'  # 'fact:<source_key>:<code>:<field>' (studio/reference/tools.py); any other ref is a passage key
# what a participant's retrieved reference states of its source (studio.reference.tools.retrieved_references)
REFERENCE_DATES = ('source_key', 'release', 'effective_start', 'effective_end')
EFFECT_CONTEXT, EFFECT_REASSESSMENT = 'context', 'reassessment'


class ConfirmationRefused(ValidationError):
    """A confirmation the encounter's state does not allow (409, as API.md documents): the question is not open on the
    final assessment, it was confirmed already, processing is under way, or the candidate is not one of its verified
    candidates."""


def model_records(assessment):
    """name -> the assessment's Assessment.participants entry of each model participant (Astra, Fable)."""
    return {record.get('name'): record for record in (assessment.participants or [])
            if isinstance(record, dict) and record.get('name') in MODEL_PARTICIPANTS}


def assessment_phase(assessment):
    """HARNESS.md 12.3: 0 when no model participant was configured for the assessment (today's record, I1) or there is
    no assessment; otherwise 2 when an entry carries its peer review (assess #2 and its re-assessments) and 1 when none
    does. The pipeline's own reading (jobs.assessment_phase), so the API, the trace and the reports state the phase the
    pipeline acts on."""
    from .jobs import assessment_phase as phase  # local import: jobs imports this module

    return phase(assessment)


def is_final(assessment):
    """Whether ``assessment`` is its chain's final assessment (12.1): assess #2 or a re-assessment of it, or one that
    owes no peer stage - no model participant's first reading was read, or a member date conflict holds it, while
    which nothing is sent. The pipeline's own rule (jobs.owed_peer_stages): an assess #1 that owes a peer stage queued
    it, and assess #2 follows it."""
    if assessment is None:
        return False
    return assessment_phase(assessment) == 2 or not owed_peer_stages(assessment)


def owed_peer_stages(assessment):
    """The peer stages assess #1 ``assessment`` owes, by the pipeline's own rule (jobs.owed_peer_stages)."""
    from .jobs import owed_peer_stages as owed  # local import: jobs imports this module

    return owed(assessment)


def peer_review_held(assessment):
    """Whether a member date conflict holds ``assessment``, while which no peer review is sent (jobs.peer_review_held).
    """
    from .jobs import peer_review_held as held  # local import: jobs imports this module

    return held(assessment)


def recorded_peer_review(assessment, record):
    """The peer review an assess #2 entry ``record`` names, read back exactly as the assessment recorded it, or None
    (jobs.recorded_peer_review: the same re-read and the same sha256 the pipeline checks)."""
    from .jobs import recorded_peer_review as recorded  # local import: jobs imports this module

    return recorded(assessment.revision, record)[1]


def _uuid(value):
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def record_run(assessment, record, field='run'):
    """The run an entry names - its phase-1 'run' or its 'peer_run' - when it is that participant's run of the
    assessment's revision with that phase's purpose; None otherwise (jobs.entry_run, which the pipeline reads an entry's
    runs by)."""
    from .jobs import entry_run  # local import: jobs imports this module

    purpose = ProviderRun.PEER_REVIEW if field == 'peer_run' else ProviderRun.INDEPENDENT
    return entry_run(assessment.revision, record, purpose)


def run_tool_calls(run):
    """The tool calls (models.ToolCall) of the loop that answered ``run`` - itself, or for a reuse the retained run it
    reuses (jobs.loop_run, HARNESS.md 12.1) - in exchange turn and call order; [] for a run with none."""
    from .jobs import loop_run  # local import: jobs imports this module

    from .jobs import loop_runs  # local import: jobs imports this module

    if run is None:
        return []
    # refutation round 1 of harness repair 3 (L6-3): a continuation's loop is its whole chain (jobs.loop_runs)
    return list(ToolCall.objects.filter(exchange__run__in=loop_runs(run)).select_related('exchange')
                .order_by('exchange__turn', 'id'))


def run_refs(run):
    """Every ref the tool calls of ``run``'s own loop returned (jobs.run_refs): what its references used are checked
    against, exactly as when the pipeline read it."""
    from .jobs import run_refs as refs  # local import: jobs imports this module

    return refs(run)


def stored_reading(run):
    """(reading, '') of participant run ``run``'s stored first reading, or (None, why): the pipeline's own read
    (jobs.participant_reading) - as the adapter version that recorded it, its bytes checked against their sha256, with
    the refs of its own loop - so every page and report reads exactly what the assessments read."""
    from .jobs import participant_reading  # local import: jobs imports this module

    return participant_reading(run)


def stored_peer_review(run):
    """(PeerReview, '') of peer-review run ``run``, or (None, why): the pipeline's own read (jobs.peer_reading)."""
    from .jobs import peer_reading  # local import: jobs imports this module

    return peer_reading(run)


def _delivered_turns(run):
    """The turns of the loop that answered ``run`` (jobs.loop_run) whose tool results reached its participant: each one
    whose next exchange - the request that carried those results - was recorded and was not 'not_sent'. A loop that
    ends once CPT Studio has answered an exchange's tool calls, sending nothing more (the next exchange not sent, a
    member's Stop, a follow-up it could not build, the deadline), keeps the calls it answered on that exchange's record
    (studio.participants.loop), and their results never reached the participant."""
    from .jobs import loop_runs  # local import: jobs imports this module

    # the whole chain's exchanges (L6-3): a continuation numbers its turns after the ones it carries
    states = dict(ProviderExchange.objects.filter(run__in=loop_runs(run)).values_list('turn', 'state'))
    return {turn for turn in states if states.get(turn + 1) not in (None, ProviderRun.NOT_SENT)}


def participant_references(run, review=None):
    """{'retrieved', 'used'} of one participant run (HARNESS.md 11.2, 12.6): each ref the tool calls of its own loop
    returned to its participant (run_tool_calls: a reuse's are the run's it reuses; a call whose result the loop never
    sent - no later exchange carried it, _delivered_turns - is none of its references: refutation round 2, sends-r2-3),
    once, with its kind (fact or passage), the source, release and effective window its tool result stated - read by
    the executor's own reader of a stored result, studio.reference.tools.retrieved_references, '' where it states none -
    and the tool; then each reference the run's answer says it used, with ``retrieved``: the reader's own check against
    those refs (ReferenceUse.retrieved), never the participant's claim (``used`` with retrieved false is
    cited_not_retrieved); and, only for a run that reused a retained answer and made no tool call itself,
    ``reused_from``: the id of the retained run whose tool calls these are, so no page or report says they are this
    run's own (refutation round 2, truth-13). ``review``: the run's reading or peer review when already read. Empty
    lists for no run."""
    from .jobs import loop_run  # local import: jobs imports this module
    from .reference.tools import retrieved_references  # local import: the tools module reads the reference store

    out = {'retrieved': [], 'used': []}
    if run is None:
        return out
    answered = loop_run(run)
    if answered is not None and answered.pk != run.pk:
        out['reused_from'] = str(answered.pk)
    seen = set()
    delivered = _delivered_turns(run)
    for call in run_tool_calls(run):
        if call.exchange.turn not in delivered:
            continue  # answered by CPT Studio, never sent to the participant (refutation round 2, sends-r2-3)
        stated = {}
        for item in retrieved_references(call.result):
            stated.setdefault(item['ref'], item)
        for ref in call.refs or []:
            if not isinstance(ref, str) or ref in seen:
                continue
            seen.add(ref)
            dated = stated.get(ref, {})
            out['retrieved'].append({'ref': ref, 'kind': 'fact' if ref.startswith(REF_FACT) else 'passage',
                                     **{name: _shown(dated.get(name)) for name in REFERENCE_DATES},
                                     'tool': call.tool})
    if review is None and run.state == ProviderRun.SUCCEEDED:
        review, _ = (stored_peer_review if run.purpose == ProviderRun.PEER_REVIEW else stored_reading)(run)
    if review is not None and not review.refused:
        out['used'] = [{'ref': item.ref, 'use': item.use, 'retrieved': bool(item.retrieved)}
                       for item in review.references_used]
    return out

CONFIRMATION_READ, CONFIRMATION_NOT_READ = 'read', 'not_read'


def confirmation_effect(confirmation, assessment):
    """{'state': 'read' | 'not_read', 'detail': words}: what ``assessment`` made of the reviewer's FindingConfirmation
    ``confirmation`` (HARNESS.md 11.3, 12.5, 12.7) - the one reading the reports' CONFIRMED FINDINGS ("Effect: <words>")
    and the API's confirmations (current_effect) both state (refutation round 2, truth-5: the page said every
    confirmation of a fact other than the date was read by the assessment, beside the Checks tab's "1 confirmation not
    read"). A service date enters as the member's date through the encounter context, so it is read when this
    assessment's context carries it; any other fact is read when the assessment's own record lists it among those it
    read (completeness['confirmations']['applied'], engine._Confirmations.record) or a proposal's checks read it
    (support['confirmed'], which the code cards show), and otherwise not read, with why: the reason the engine recorded
    for not reading it (['ignored']), that the assessment was made before it, or that it records no reading of it.
    ``assessment`` None: no assessment of its revision is current. Read-only; a confirmation is a confirmed fact, never
    a decision (I3, I4)."""
    if assessment is None:
        return {'state': CONFIRMATION_NOT_READ, 'detail': 'not read: no assessment of its revision is current'}
    if confirmation.fact == candidates.DATE_FACT:
        carried = (assessment.context.user_values or {}).get('service_date') == confirmation.value
        return {'state': CONFIRMATION_READ if carried else CONFIRMATION_NOT_READ,
                'detail': ("entered as the member's service date through the encounter context; this assessment's "
                           'context ' + ('carries it' if carried else
                                         'does not carry it (made before it, or with another member date)'))}
    record = (assessment.completeness or {}).get('confirmations') if isinstance(assessment.completeness, dict) else {}
    record = record if isinstance(record, dict) else {}
    key = str(confirmation.pk)
    applied = {str(i) for item in record.get('applied') or [] if isinstance(item, dict) for i in item.get('ids') or []}
    for support in assessment.proposals.values_list('support', flat=True):
        read = (support or {}).get('confirmed') if isinstance(support, dict) else None
        applied |= {item for item in read if isinstance(item, str)} if isinstance(read, list) else set()
    ignored = {str(item.get('id')): str(item.get('why') or '') for item in record.get('ignored') or []
               if isinstance(item, dict)}
    if key in applied:
        return {'state': CONFIRMATION_READ, 'detail': 'read by this assessment'}
    if key in ignored:
        return {'state': CONFIRMATION_NOT_READ, 'detail': f'not read by this assessment: {ignored[key]}'}
    if assessment.created_at < confirmation.created_at:
        return {'state': CONFIRMATION_NOT_READ, 'detail': 'not read by this assessment, which was made before it'}
    return {'state': CONFIRMATION_NOT_READ, 'detail': 'not read by this assessment, which records no reading of it'}


def frozen_inputs(assessment):
    """(readings, peer reviews): the frozen phase-1 readings (candidates.FrozenReading) and the peer reviews ((name, run
    id, PeerReview)) ``assessment`` read, each read again from its run and used only when it matches the sha256 the
    assessment recorded for it (12.3: reading_sha256, peer_sha256) - anything else is not what was frozen (logged). The
    pipeline's own re-reads (jobs.recorded_reading, jobs.recorded_peer_review), which its peer stage builds from."""
    from .jobs import recorded_peer_review as recorded, recorded_reading  # local import: jobs imports this module

    readings, reviews = [], []
    for name, record in sorted(model_records(assessment).items(), key=lambda item: MODEL_PARTICIPANTS.index(item[0])):
        if record.get('state') != 'read':
            continue
        run, reading = recorded_reading(assessment.revision, record)
        if reading is None:
            log.warning('the frozen reading of %s on assessment %s could not be read as recorded', name, assessment.pk)
            continue
        readings.append(candidates.FrozenReading(name=name, run=str(run.pk), reading=reading))
        if record.get('peer_state') != 'read':
            continue
        peer_run, review = recorded(assessment.revision, record)
        if review is None:
            log.warning('the peer review of %s on assessment %s could not be read as recorded', name, assessment.pk)
            continue
        reviews.append((name, str(peer_run.pk), review))
    return readings, reviews


def question_identity(clarification):
    """What a question asks, whichever assessment raised it: (scope, family, fact, the key and code of its proposal). A
    proposal's key counts within its list in selection order, and assess #2 can select a code assess #1 did not (a
    participant's code that peer review located) ahead of later ones, so the same key may name another code there: the
    code is part of the match, and a question whose proposal changed takes no peer answer (fail closed)."""
    proposal = clarification.proposal if clarification.proposal_id else None
    return (clarification.scope, clarification.family, clarification.fact, proposal.key if proposal else '',
            proposal.code if proposal else '')


def peer_answers(assessment, questions, reviews):
    """{clarification pk: [candidates.PeerAnswer]} for ``questions`` of ``assessment``. A peer request named the open
    questions of the assess #1 it read by their clarification ids (12.4: "QuestionAnswer.value for its id"); assess #2
    raised its own rows, so each answer is matched to the question of this assessment that asks the same thing
    (question_identity) as the clarification of this revision its id names."""
    named = {_uuid(answer.question_id) for _, _, review in reviews for answer in review.answers} - {None}
    asked = {str(item.pk): question_identity(item) for item in Clarification.objects.select_related('proposal').filter(
        pk__in=named, encounter_id=assessment.encounter_id, assessment__revision_id=assessment.revision_id)}
    by_identity = {}
    for name, run_id, review in reviews:
        for answer in review.answers:
            identity = asked.get(_uuid(answer.question_id))
            if identity is not None:
                by_identity.setdefault(identity, []).append(candidates.PeerAnswer(name=name, run=run_id,
                                                                                  answer=answer))
    return {question.pk: by_identity.get(question_identity(question), []) for question in questions}


def candidate_question(clarification):
    """The open question as studio.candidates reads it: with, for a proposal's question, its proposal's code and the
    documented service the readers decided that proposal's hold on (support['service'], '' when none did), where a
    status is read (refutation round 2, EV2-1)."""
    proposal = clarification.proposal if clarification.proposal_id else None
    service = (proposal.support or {}).get('service') if proposal is not None else ''
    return candidates.Question(id=str(clarification.pk), scope=clarification.scope, fact=clarification.fact,
                               family=clarification.family, proposal_key=proposal.key if proposal is not None else '',
                               code=proposal.code if proposal is not None else '',
                               service=service if isinstance(service, str) else '')


def recorded_inventory(assessment):
    """The documented-service inventory ``assessment`` recorded (Assessment.services), read back as the engine read it
    when it decided the holds - None when it recorded none, one that cannot be read back, or one that was inconsistent
    with its revision's text (services.validate, as the engine reads it: an inconsistent reading decides no status)."""
    from .gi import services as gi_services  # local import: read only where a status is checked
    from .types import from_jsonable

    data = assessment.services
    if not isinstance(data, dict) or not isinstance(data.get('services'), list):
        return None
    try:
        inventory = from_jsonable(gi_services.ServiceInventory, data)
    except (TypeError, ValueError, AttributeError, KeyError):
        return None  # fail closed: a record CPT Studio cannot read back answers no status
    try:
        problems = gi_services.validate(inventory, assessment.revision.text)
    except (TypeError, ValueError, AttributeError):
        return None
    return None if problems else inventory


# The encounter's context changed after the live assessment (refutation round 2, truth-10): no candidate is offered and
# no confirmation is taken, as jobs.reassess_after_confirmation would refuse it (HARNESS.md 12.5).
CONTEXT_CHANGED = ('The encounter context changed after this assessment; resume processing and confirm on its new '
                   'assessment.')


def on_current_context(assessment):
    """Whether ``assessment`` is made on its encounter's current revision AND context: the only assessment a candidate
    is offered on and a confirmation is accepted for (the condition jobs.reassess_after_confirmation enforces)."""
    encounter = assessment.encounter
    return (assessment.revision_id == encounter.current_revision_id
            and assessment.context_id == encounter.current_context_id)


# Release scope after refutation round 3 (HARNESS.md 12.10, the session's D7): this release offers no reviewer
# confirmation. Three rounds of refutation each found blocking defects in the check that called a participant's passage
# "Verified", each in the previous round's repair, and the check cannot converge: a question is asked because CPT
# Studio's own readers did not establish its answer, so a check of what a passage states is either those readers again
# or a second, weaker reader. While confirmations_offered() is off (settings.STUDIO_OFFER_CONFIRMATIONS, a code-level
# False): confirm_finding and jobs.reassess_after_confirmation refuse first with CONFIRMATIONS_NOT_OFFERED and record
# nothing; jobs.confirmed_findings hands the engine no confirmation, not even a row that exists; and a candidate is
# served as the participant's located passage only (located_passages), never checked, so CPT Studio claims nothing about
# what it states. The checks, the engine's _Confirmations and the re-assessment stay, dormant, behind the setting.
# Refutation round 4 (the session's D8; d7-1, d7-2, truth-1): those located passages were not the participants' answers
# - a candidate's value is CPT Studio's own inference from a reading (an E/M basis its own reader read in the passage,
# which also chose the passages shown; a service's status or extent paired with every quote of that service) - so while
# confirmations are not offered no candidate is served at all (assessment_candidates), and located_passages and its
# fixed why are removed. A participant's own answers stay in its peer review, as its own words. And the refusal says
# only what happened (d7-3): "a question is answered with an addendum, or a date of service in the encounter context"
# was false for a documented conflict or an included base code, which an addendum leaves open, and for a member's
# setting, which only the encounter context corrects - no sentence names a way a question is settled.
CONFIRMATIONS_NOT_OFFERED = 'This release offers no reviewer confirmation, so nothing was recorded.'


def confirmations_offered():
    """Whether reviewer confirmations are offered (HARNESS.md 12.10): only while settings.STUDIO_OFFER_CONFIRMATIONS is
    the literal True, which this release never is - a code-level False no environment variable, installer file or
    member action changes; only a test's override_settings turns on the dormant path. Fail closed: anything else is
    off."""
    from django.conf import settings  # local import: read where the release scope is decided

    return getattr(settings, 'STUDIO_OFFER_CONFIRMATIONS', False) is True


def assessment_candidates(assessment):
    """{clarification id: [candidate]} (studio.candidates) for each OPEN clarification of ``assessment`` when it is the
    final assessment of a chain a model participant took part in, made on the encounter's current revision and context;
    {} otherwise - a Corti-only assessment, an assess #1 whose peer stages follow, no open question, no model
    participant configured now (no assessment would read a confirmation then: the pipeline gives the engine none, I1),
    or an assessment of an earlier context (no confirmation could be read then: refutation round 2, truth-10). A status
    is read against the documented-service inventory the assessment recorded (recorded_inventory). Refutation round 4
    (HARNESS.md 12.10 as amended, the session's D8): while confirmations are not offered - the release default - {}
    before anything is read: no candidate is served at all, since a candidate's value is CPT Studio's own inference from
    a participant's reading, never its answer to the question (round 3's located passages showed it as one)."""
    if not confirmations_offered():
        return {}
    if (assessment is None or assessment_phase(assessment) == 0 or not is_final(assessment)
            or not participants.configured() or not on_current_context(assessment)):
        return {}
    questions = list(assessment.clarifications.filter(state=Clarification.OPEN).select_related('proposal'))
    if not questions:
        return {}
    readings, reviews = frozen_inputs(assessment)
    answers = peer_answers(assessment, questions, reviews) if reviews else {}
    revision = assessment.revision
    inventory = (recorded_inventory(assessment)
                 if any(question.fact == candidates.STATUS_FACT for question in questions) else None)
    return {str(question.pk): candidates.candidates(candidate_question(question), revision.text, revision.pages,
                                                    readings, answers.get(question.pk, ()), inventory=inventory)
            for question in questions}


def revision_confirmations(revision):
    """The FindingConfirmations of ``revision``, oldest first (a new revision's assessments never read them)."""
    if revision is None:
        return []
    return list(FindingConfirmation.objects.filter(revision=revision).select_related(
        'confirmed_by', 'revision', 'clarification', 'clarification__proposal').order_by('created_at', 'pk'))


def confirm_finding(*, encounter, clarification_id, candidate_id, attestation, user, membership):
    """Record a reviewer's confirmation of one verified candidate answer to an open question (HARNESS.md 11.3, 12.5),
    then act on it; returns (FindingConfirmation, effect).

    Under the encounter row lock: an owner or reviewer only; the question open on the current revision's final
    assessment, made on the encounter's current context (CONTEXT_CHANGED otherwise, refutation round 2, truth-10), and
    confirmed by no one yet; nothing processing; the candidate one of its VERIFIED candidates, recomputed here; the
    attestation exactly candidates.attestation(value). The immutable FindingConfirmation and its audit event
    'finding.confirmed' are recorded, then a service date enters as the member's date through jobs.change_context
    (every date safeguard and I8 apply; effect 'context') and every other fact is read by the re-assessment
    jobs.reassess_after_confirmation queues (effect 'reassessment'). A refusal from either leaves nothing recorded.
    Never approves anything: approval stays a separate decision.

    Refutation round 3 (HARNESS.md 12.10, D7): while confirmations are not offered - the release default - it refuses
    first, before it reads the encounter, the question, the candidate or anything else, with CONFIRMATIONS_NOT_OFFERED
    (ConfirmationRefused: the endpoint's 409); nothing is recorded: no FindingConfirmation, no audit row, no job, no
    request."""
    if not confirmations_offered():
        raise ConfirmationRefused(CONFIRMATIONS_NOT_OFFERED)
    from . import jobs  # local import: jobs imports this module

    with transaction.atomic():
        locked = _lock(encounter)
        if not (_is_reviewer(membership, locked) and membership.user_id == user.pk and user.is_active):
            raise PermissionDenied('Your role in this workspace cannot confirm findings.')
        clarification = (Clarification.objects.select_related('proposal')
                         .filter(pk=clarification_id, encounter=locked).first())
        if clarification is None:
            raise Http404()
        assessment = live_assessment(locked)
        if assessment is None or clarification.assessment_id != assessment.pk:
            raise ConfirmationRefused('That question belongs to an earlier assessment; reload the page and answer the '
                                      'current one.')
        if assessment.context_id != locked.current_context_id and not jobs.busy(locked):
            # refutation round 2, truth-10: a confirmation is never taken for an assessment of an earlier context, which
            # no re-assessment would read; said before anything else is checked (while processing runs, the wait is)
            raise ConfirmationRefused(CONTEXT_CHANGED)
        if not is_final(assessment):
            raise ConfirmationRefused('The peer reviews of this document have not finished: a finding can be confirmed '
                                      'once its final assessment is recorded.')
        if clarification.state != Clarification.OPEN:
            raise ConfirmationRefused('That question is not open.')
        if FindingConfirmation.objects.filter(clarification=clarification).exists():
            raise ConfirmationRefused('That question was confirmed already; a question takes one confirmation.')
        if jobs.busy(locked):
            raise ConfirmationRefused('Wait for processing to finish (or stop it) before confirming a finding.')
        offered = assessment_candidates(assessment).get(str(clarification.pk), [])
        candidate = next((item for item in offered if item['id'] == candidate_id), None)
        if candidate is None:
            raise ConfirmationRefused("That candidate is not one of this question's candidates; reload the page.")
        if not candidate['verified']:
            raise ConfirmationRefused(f'That candidate is not verified, so it cannot be confirmed: {candidate["why"]}')
        expected = candidates.attestation(candidate['value'])
        if attestation != expected:
            raise AttestationRefused(f'The attestation must read exactly: {expected}')
        if clarification.scope == 'proposal' and not (
                clarification.proposal_id and isinstance((clarification.proposal.support or {}).get('identity'), str)
                and clarification.proposal.support['identity']):
            # a proposal's question is bound to its proposal's code and identity (jobs.confirmed_findings), never to the
            # key alone: a question whose proposal records no identity could be read for no proposal (EV-1)
            raise ConfirmationRefused("That question's proposal records no identity for a confirmation to be bound to, "
                                      'so it cannot be confirmed; nothing was recorded.')
        confirmation = FindingConfirmation.objects.create(
            encounter=locked, revision=assessment.revision, clarification=clarification, scope=clarification.scope,
            fact=clarification.fact, family=clarification.family,
            proposal_key=clarification.proposal.key if clarification.proposal_id else '', value=candidate['value'],
            spans=candidate['spans'], located_by=list(candidate['located_by']), runs=list(candidate['runs']),
            confirmed_by=user, attestation=attestation)
        effect = EFFECT_CONTEXT if clarification.fact == candidates.DATE_FACT else EFFECT_REASSESSMENT
        audit.record(locked.workspace, 'finding.confirmed', encounter=locked, actor=user,
                     confirmation=str(confirmation.pk), clarification=str(clarification.pk),
                     assessment=str(assessment.pk), revision=assessment.revision.number, fact=clarification.fact,
                     candidate=candidate_id, located_by=list(candidate['located_by']), runs=list(candidate['runs']),
                     effect=effect)
        if effect == EFFECT_CONTEXT:
            jobs.change_context(locked, user, {'service_date': candidate['value']}, confirmation=confirmation)
        else:
            jobs.reassess_after_confirmation(locked, user)
        encounter.state = refresh_state(locked)
    return confirmation, effect
