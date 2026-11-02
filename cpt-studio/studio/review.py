"""Review decisions, their carry/invalidation, readiness and the derived encounter state (ARCHITECTURE 5.7).

Decisions are append-only. A proposal's current decision is its LATEST
decision unless that one was invalidated or is a revoke; an earlier decision
is never resurrected. A decision is bound to the assessment, revision,
proposal fingerprint and profile version it was made on: a new revision
invalidates it, and a re-assessment of the same revision carries it only onto
a proposal with the same fingerprint, code, list, status and profile version.
Only the current assessment of the current revision can be decided on.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from . import audit, candidates, participants
from .gi.context import charge_date_problem
from .models import (Assessment, Clarification, Decision, DecisionInvalidation, Encounter, FindingConfirmation, Job,
                     Proposal, ProviderRun, SourceRevision, ToolCall)
from .providers.base import ProviderUnavailable
from .types import ProviderRequest, sha256_json, to_jsonable

log = logging.getLogger(__name__)


class AttestationRefused(ValidationError):
    """An approval whose acknowledgement is missing or is not the current attestation: invalid input (400, as
    API.md documents), not a state conflict, so a page loaded before the attestation changed is told to reload
    rather than read as 'not allowed right now' (round 6 bypass:2, pipeline:6)."""


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


def _actions(proposal, current, text, same_day_held=False):
    """``same_day_held``: an E/M that a reviewer's reinstatement of a same-day procedure now holds (no approve)."""
    if current is not None and current.action in (APPROVE, REJECT, CONFIRM):
        return [REVOKE]
    exact = bool(exact_evidence(proposal.evidence, text))
    if proposal.bucket == SELECTED and proposal.status in BUCKET_STATUSES[SELECTED]:
        actions = [APPROVE] if proposal.status == Proposal.READY and exact and not same_day_held else []
        return actions + [REJECT] + ([REVOKE] if current else [])
    if proposal.bucket == EXCLUDED and proposal.status == Proposal.STATUS_EXCLUDED:
        if current is None:
            # A documentation check's exclusion (reinstatable) is a recommendation: the reviewer confirms it or
            # reinstates the code, and the reviewed report waits for one of the two (round 4).
            if not proposal.reinstatable:
                return []
            return ([REINSTATE] if exact else []) + [CONFIRM]
        return ([APPROVE] if exact and _reinstatement_clear(proposal) and not same_day_held else []) + [REJECT, REVOKE]
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


def approve_withheld_by(proposal, assessment, decisions):
    """The check that withholds approve from a reinstated exclusion, whoever is looking: 'review.reinstatement' while
    that check does not pass, SAME_DAY_EM_GATE while a reinstated same-day procedure holds this E/M, else None. The
    same gates as _actions, read without the member's role, so a viewer is never told a code cannot be approved when
    a reviewer can approve it now (round 6 bypass:3)."""
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


def _allowed(proposal, assessment, membership, encounter):
    if not _is_reviewer(membership, encounter) or proposal.assessment_id != assessment.pk:
        return []
    if (encounter.current_assessment_id != assessment.pk
            or assessment.revision_id != encounter.current_revision_id):
        return []
    return _actions(proposal, _current_decision(proposal), assessment.revision.text,
                    _same_day_held(proposal, assessment))


def allowed_actions(proposal, assessment, membership):
    """The actions this member may record on ``proposal`` now; the only source of truth for the UI."""
    encounter = Encounter.objects.only('workspace', 'current_assessment', 'current_revision').get(
        pk=assessment.encounter_id)
    return _allowed(proposal, assessment, membership, encounter)


def record_decision(*, encounter, proposal, action, user, membership, note='', acknowledgement=''):
    """Append one decision after re-validating it under the encounter lock."""
    with transaction.atomic():
        locked = _lock(encounter)
        if not (_is_reviewer(membership, locked) and membership.user_id == user.pk and user.is_active):
            raise PermissionDenied('Your role in this workspace cannot record review decisions.')
        assessment = live_assessment(locked)
        if assessment is None or proposal.assessment_id != assessment.pk:
            raise ValidationError('That proposal is not part of the current review.')
        if action not in ACTION_LABELS:
            raise ValidationError('Unknown review action.')
        if action not in _allowed(proposal, assessment, membership, locked):
            raise ValidationError(f'{ACTION_LABELS[action]} is not available for {proposal.code} right now.')
        note, acknowledgement = (note or '').strip(), (acknowledgement or '').strip()
        if action == APPROVE and not acknowledgement:
            raise AttestationRefused('Approving requires an acknowledgement.')
        if action == APPROVE and acknowledgement != ACKNOWLEDGEMENTS.get(user.actor_kind):
            raise AttestationRefused('The acknowledgement is not the current review attestation. Reload the page '
                                     'and approve again.')
        decision = Decision.objects.create(
            encounter=locked, assessment=assessment, revision=assessment.revision, proposal=proposal, action=action,
            note=note, reviewer=user, reviewer_kind=user.actor_kind, acknowledgement=acknowledgement,
            profile_version=proposal.profile_version, proposal_fingerprint=proposal.fingerprint)
        audit.record(locked.workspace, 'decision.recorded', encounter=locked, actor=user, decision=str(decision.pk),
                     proposal=str(proposal.pk), assessment=str(assessment.pk), action=action, code=proposal.code)
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
        if locked.current_assessment_id is not None:
            for decision in current_decisions(locked.current_assessment).values():
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
    """``participants`` and ``retrieval`` (HARNESS.md 6) are recorded beside the result, outside its sha256: an
    assessment that read other participant runs or retrieved other passages is another assessment."""
    return (previous is not None and previous.sha256 == digest and previous.revision_id == revision.pk
            and previous.context_id == context.pk and previous.routing_id == routing_run.pk
            and previous.provider_run_id == (provider_run.pk if provider_run else None)
            and previous.second_run_id == (second_run.pk if second_run else None)
            and previous.participants == (participants or []) and previous.retrieval == (retrieval or []))


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
    """Carry or invalidate the previous assessment's current decisions; returns (carried, invalidated)."""
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
            profile_version=target.profile_version, proposal_fingerprint=target.fingerprint, carried_from=decision)
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
        carried, invalidated = _carry_decisions(previous, assessment, proposals, revision, context)
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


def _unreconciled_unknown(encounter):
    return encounter.provider_runs.filter(state=ProviderRun.UNKNOWN, reconciled_at__isnull=True).exists()


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
    blockers = []
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
    reinstated = _reinstated_procedures(assessment, current)
    reviewable = 0
    for proposal in assessment.proposals.all():
        decision = current.get(proposal.pk)
        if not _reviewable(proposal, decision):
            continue
        reviewable += 1
        if reinstated and _has_check(proposal, SAME_DAY_EM_GATE) and _could_bill(proposal, decision):
            # Also when this E/M was approved before the procedure was brought back.
            blockers.append(_same_day_blocker(proposal, reinstated))
        if decision is not None and decision.action in (APPROVE, REJECT, CONFIRM):
            continue
        if decision is not None:
            blockers.append(f'{proposal.code} was reinstated and has no decision')
        elif proposal.bucket == EXCLUDED:
            blockers.append(f'{proposal.code} was excluded by a documentation check: confirm the exclusion '
                            'or reinstate it')
        elif proposal.pk in asked:
            blockers.append(f'{proposal.code} has an open clarification')
        elif proposal.status == Proposal.NEEDS_CLARIFICATION:
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
            what = (f'No code is selected for approval: the {"response that was read" if unread else "provider"} '
                    'proposed only codes that were excluded or offered as alternatives'
                    if assessment.proposals.exists() else
                    f'No CPT code was proposed{" in the response that was read" if unread else ""}')
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
    waiting = reviewable = 0
    for proposal in assessment.proposals.all():
        decision = current.get(proposal.pk)
        if not _reviewable(proposal, decision):
            continue
        reviewable += 1
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
    open_questions = assessment.clarifications.filter(state=Clarification.OPEN).count()
    if open_questions:
        reasons.append(f'{open_questions} open question{"s" if open_questions != 1 else ""}')
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
    if job.kind in Job.PARTICIPANT_KINDS:
        # A harness participant's stage never makes the encounter provider_failed, which is Corti's state: its own
        # failures are runs of its own, and the chain goes on (I10). One its worker left mid-send is the encounter-wide
        # unknown outcome every further send waits on (HARNESS.md 2); any other failure is the stage's.
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
    if run.state in UNSETTLED_RUN_STATES:
        return 'provider_unknown', None
    if job.kind == Job.REVIEW2 and run.state in (ProviderRun.NOT_SENT, ProviderRun.CANCELLED):
        # Nor did one whose request was never sent - stopped before sending, or settled as not sent when the stage was
        # closed: no request failed, so never provider_failed ("The provider request failed" beside a primary answer
        # that succeeded, refutation P2FR, ROLLBACK 1: an undo then left that state to 057a7d39, which labels it by its
        # name). None: the assessment's own state, worded from that run ('Second review not sent').
        return None, None
    if run.state == ProviderRun.SUCCEEDED:
        return 'processing_failed', None
    return 'provider_failed', run


def _review_state(encounter, assessment):
    if readiness(encounter)['reviewed']:
        return 'reviewed'
    current = current_decisions(assessment)
    reviewable = [item for item in assessment.proposals.all() if _reviewable(item, current.get(item.pk))]
    encounter_question = assessment.clarifications.filter(
        state=Clarification.OPEN, scope='encounter', proposal__isnull=True).exists()
    if not reviewable:
        return 'needs_clarification' if encounter_question else 'no_codes'
    if encounter_question or any(item.status == Proposal.NEEDS_CLARIFICATION and item.pk not in current
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
    if revision.extraction_status == SourceRevision.FAILED:
        return 'extraction_failed', None
    latest = encounter.jobs.filter(revision=revision).order_by('-created_at', '-pk').first()
    if latest is not None and latest.state == Job.CANCELLED:
        return 'stopped', None
    if revision.extraction_status == SourceRevision.PENDING:
        return ('processing' if latest is None else 'extraction_failed'), None
    if latest is not None and latest.state in (Job.FAILED, Job.UNKNOWN):
        failed, run = _failed_stage_state(encounter, revision, latest)
        if failed is not None:
            return failed, run
    assessment = live_assessment(encounter)
    if assessment is None or assessment.context_id != encounter.current_context_id:
        return ('provider_unknown' if _unreconciled_unknown(encounter) else 'processing'), None
    run = assessment.provider_run
    if run is None:
        return 'provider_not_run', None
    if run.state in UNSETTLED_RUN_STATES or _unreconciled_unknown(encounter):
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


def proposed_by(proposal):
    """Who proposed the code, in harness order (I4: a proposal, never an approval): Corti for its own proposals and
    alternatives (origin primary or second_review), and each participant the engine named in support['proposed_by'] -
    the proposers of a participant's own proposal (origin participant), or a participant that also proposed Corti's."""
    support = proposal.support or {}
    named = {name for name in support.get('proposed_by') or [] if isinstance(name, str)}
    corti = (support.get('origin') or 'primary') in ('primary', 'second_review') or CORTI in named
    return ([CORTI] if corti else []) + [name for name in participants.PARTICIPANTS if name in named]


def participant_positions(proposal, records):
    """{name: {position, detail, quote}} for each harness participant the assessment had configured
    (Assessment.participants; {} when none was): from a reading that was used, 'proposed' (with its first located
    quote), 'advised_not_to_code' (its reason and quote) or 'not_proposed'; else 'not_run' with why. Positions are kept
    beside the proposal and decide nothing (I2, I3)."""
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
        if proposal.code in proposed:
            quote = proposed[proposal.code]
            located = (' with evidence located in the document' if quote else
                       '; none of its quotes was found in the document')
            out[name] = {'position': 'proposed', 'detail': f'{label} proposed this code{located}.', 'quote': quote}
        elif proposal.code in advised:
            item = advised[proposal.code]
            out[name] = {'position': 'advised_not_to_code', 'quote': item.get('quote') or '',
                         'detail': f'{label} advised not to code it: {_human(item.get("reason") or "other")}.'}
        else:
            out[name] = {'position': 'not_proposed', 'detail': f'{label} did not propose this code.', 'quote': ''}
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


def _usd(value):
    """An estimate as USD text with four decimals; None for no estimate."""
    if isinstance(value, dict):
        value = value.get('usd')
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (Decimal, int, float)):
        return f'{Decimal(str(value)):.4f}'
    return str(value)


def estimated_cost(run):
    """The run's estimated cost in USD as text ('0.0412'), from studio.participants.pricing's fixed, dated rates
    (HARNESS.md 6: estimated from published rates, not reconciled to an invoice). None for Corti (its usage is in
    credits, not USD), for a run that reported no usage (a reuse, a request not sent), where the pricing module is not
    installed, and where it cannot price the usage: an estimate is informational, so it never fails the page or a
    report (its error is logged)."""
    if run is None or run.provider not in participants.PARTICIPANTS or not run.usage:
        return None
    try:
        pricing = importlib.import_module(PRICING_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != PRICING_MODULE:
            raise
        return None
    try:
        return _usd(pricing.estimate(run.requested_model, dict(run.usage)))
    except Exception:  # noqa: BLE001 - logged; no estimate is shown rather than a failed page or report
        log.exception('the usage of run %s could not be priced', run.pk)
        return None


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
STORED_HASH_MISMATCH = 'The stored response no longer matches its recorded hash; it was not read.'
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
    """HARNESS.md 12.3: 0 when no model participant was configured for the assessment (today's record, I1); otherwise 2
    when an entry carries its peer review (assess #2 and its re-assessments) and 1 when none does."""
    if assessment is None:
        return 0
    records = model_records(assessment).values()
    if not any(record.get('state') != 'not_configured' for record in records):
        return 0
    return 2 if any('peer_state' in record for record in records) else 1


def is_final(assessment):
    """Whether ``assessment`` is its chain's final assessment (12.1): assess #2 or a re-assessment of it, or one that
    owed no peer stage because no model participant's first reading was read. An assess #1 that read one queued the
    peer stages, and assess #2 follows it."""
    if assessment is None:
        return False
    if assessment_phase(assessment) == 2:
        return True
    return not any(record.get('state') == 'read' for record in model_records(assessment).values())


def _uuid(value):
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def record_run(assessment, record, field='run'):
    """The run an entry names - its phase-1 'run' or its 'peer_run' - when it is that participant's run of the
    assessment's revision with that phase's purpose; None otherwise."""
    run_id = _uuid(record.get(field)) if isinstance(record, dict) else None
    if run_id is None:
        return None
    purpose = ProviderRun.PEER_REVIEW if field == 'peer_run' else ProviderRun.INDEPENDENT
    return ProviderRun.objects.filter(pk=run_id, revision_id=assessment.revision_id, provider=record.get('name'),
                                      purpose=purpose).first()


def run_tool_calls(run):
    """The run's tool calls (models.ToolCall), in exchange turn and call order; [] for a run with none."""
    if run is None:
        return []
    return list(ToolCall.objects.filter(exchange__run=run).select_related('exchange').order_by('exchange__turn', 'id'))


def run_refs(run, calls=None):
    """Every ref the run's own tool calls returned, in call order, each once (what its references used are checked
    against)."""
    refs = []
    for call in run_tool_calls(run) if calls is None else calls:
        refs += [ref for ref in call.refs or [] if isinstance(ref, str) and ref not in refs]
    return tuple(refs)


def stored_reading(run, refs=None):
    """(reading, '') of participant run ``run``'s stored first reading, read as the adapter version that recorded it
    after its bytes are checked against their recorded sha256, with the refs its own tool calls returned; (None, why)
    when it cannot be read. Needs no credentials."""
    return _stored(run, participants.reader_for, refs)


def stored_peer_review(run, refs=None):
    """(PeerReview, '') of peer-review run ``run``, read as stored_reading reads a first reading; (None, why)."""
    return _stored(run, participants.peer_reader_for, refs)


def _stored(run, reader_of, refs):
    from .jobs import PARTICIPANT_UNREADABLE_MESSAGE  # local import: jobs imports this module

    data = bytes(run.response_bytes or b'')
    if hashlib.sha256(data).hexdigest() != run.response_sha256:
        return None, STORED_HASH_MISMATCH
    request = ProviderRequest(provider=run.provider, adapter_version=run.adapter_version, body=run.request_body,
                              canonical_sha256=run.request_sha256, contexts=tuple(run.contexts or ()))
    try:
        reader = reader_of(run.provider, run.adapter_version)
    except ProviderUnavailable as exc:
        return None, str(exc)
    refs = run_refs(run) if refs is None else tuple(refs)
    try:
        # a run with no tool calls is read exactly as harness@1 read one: refs_retrieved stays its default
        return (reader(request, data, frozenset(refs)) if refs else reader(request, data)), ''
    except Exception as exc:  # noqa: BLE001 - logged; one participant's unreadable answer blocks only itself (I10)
        log.exception('the stored answer of participant run %s could not be read', run.pk)
        return None, PARTICIPANT_UNREADABLE_MESSAGE.format(error=type(exc).__name__)


def _dated(item, ref):
    """(source_key, release, effective_start, effective_end) a tool result states for ``ref``: the object that carries
    that passage key, or for a fact ref an object of its source key; '' for whatever the result does not state."""
    fact = ref.startswith(REF_FACT)
    source = ref[len(REF_FACT):].rsplit(':', 2)[0] if fact and ref.count(':') >= 3 else ''
    pending, found = [item], None
    while pending and found is None:
        node = pending.pop(0)
        if isinstance(node, dict):
            if (not fact and node.get('passage_key') == ref) or (fact and source and node.get('source_key') == source
                                                                 and 'release' in node):
                found = node
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    if found is None:
        return source, '', '', ''
    effective = found.get('effective') if isinstance(found.get('effective'), list) else []
    start = found.get('effective_start', effective[0] if len(effective) == 2 else '')
    end = found.get('effective_end', effective[1] if len(effective) == 2 else '')
    return (_shown(found.get('source_key', source)), _shown(found.get('release')), _shown(start), _shown(end))


def participant_references(run, review=None):
    """{'retrieved', 'used'} of one participant run (HARNESS.md 11.2, 12.6): each ref its own tool calls returned, once,
    with its kind (fact or passage), the source, release and effective window its tool result stated, and the tool;
    then each reference the run's answer says it used, with ``retrieved`` - CPT Studio's check, never the participant's
    claim: True only when that run's own tool results returned it (``used`` with retrieved false is
    cited_not_retrieved). ``review``: the run's reading or peer review when already read. Empty lists for no run."""
    out = {'retrieved': [], 'used': []}
    if run is None:
        return out
    calls = run_tool_calls(run)
    seen = set()
    for call in calls:
        for ref in call.refs or []:
            if not isinstance(ref, str) or ref in seen:
                continue
            seen.add(ref)
            source_key, release, start, end = _dated(call.result, ref)
            out['retrieved'].append({'ref': ref, 'kind': 'fact' if ref.startswith(REF_FACT) else 'passage',
                                     'source_key': source_key, 'release': release, 'effective_start': start,
                                     'effective_end': end, 'tool': call.tool})
    if review is None and run.state == ProviderRun.SUCCEEDED:
        reader = stored_peer_review if run.purpose == ProviderRun.PEER_REVIEW else stored_reading
        review, _ = reader(run, run_refs(run, calls))
    if review is not None and not review.refused:
        out['used'] = [{'ref': item.ref, 'use': item.use, 'retrieved': item.ref in seen}
                       for item in review.references_used]
    return out


def frozen_inputs(assessment):
    """(readings, peer reviews): the frozen phase-1 readings (candidates.FrozenReading) and the peer reviews ((name, run
    id, PeerReview)) ``assessment`` read, each read again from its run and used only when it matches the sha256 the
    assessment recorded for it (12.3: reading_sha256, peer_sha256) - anything else is not what was frozen (logged)."""
    readings, reviews = [], []
    for name, record in sorted(model_records(assessment).items(), key=lambda item: MODEL_PARTICIPANTS.index(item[0])):
        if record.get('state') != 'read':
            continue
        run = record_run(assessment, record)
        reading, _ = stored_reading(run) if run is not None else (None, '')
        if reading is None or reading.refused or not record.get('reading_sha256') \
                or sha256_json(reading) != record.get('reading_sha256'):
            log.warning('the frozen reading of %s on assessment %s could not be read as recorded', name, assessment.pk)
            continue
        readings.append(candidates.FrozenReading(name=name, run=str(run.pk), reading=reading))
        if record.get('peer_state') != 'read':
            continue
        peer_run = record_run(assessment, record, 'peer_run')
        review, _ = stored_peer_review(peer_run) if peer_run is not None else (None, '')
        if review is None or review.refused or not record.get('peer_sha256') \
                or sha256_json(review) != record.get('peer_sha256'):
            log.warning('the peer review of %s on assessment %s could not be read as recorded', name, assessment.pk)
            continue
        reviews.append((name, str(peer_run.pk), review))
    return readings, reviews


def question_identity(clarification):
    """What a question asks, whichever assessment raised it: (scope, family, fact, the key of its proposal) - the match
    engine._Confirmations reads a confirmation by."""
    return (clarification.scope, clarification.family, clarification.fact,
            clarification.proposal.key if clarification.proposal_id else '')


def peer_answers(assessment, questions, reviews):
    """{clarification pk: [candidates.PeerAnswer]} for ``questions`` of ``assessment``. A peer request named the open
    questions of the assess #1 it read by their clarification ids (12.4); assess #2 raised its own rows, so each answer
    is matched to the question of this assessment that asks the same thing (question_identity) as the clarification of
    this revision its id names."""
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
    return candidates.Question(id=str(clarification.pk), scope=clarification.scope, fact=clarification.fact,
                               family=clarification.family,
                               proposal_key=clarification.proposal.key if clarification.proposal_id else '')


def assessment_candidates(assessment):
    """{clarification id: [candidate]} (studio.candidates) for each OPEN clarification of ``assessment`` when it is the
    final assessment of a chain a model participant took part in; {} otherwise - a Corti-only assessment, an assess #1
    whose peer stages follow, or no open question."""
    if assessment is None or assessment_phase(assessment) == 0 or not is_final(assessment):
        return {}
    questions = list(assessment.clarifications.filter(state=Clarification.OPEN).select_related('proposal'))
    if not questions:
        return {}
    readings, reviews = frozen_inputs(assessment)
    answers = peer_answers(assessment, questions, reviews) if reviews else {}
    revision = assessment.revision
    return {str(question.pk): candidates.candidates(candidate_question(question), revision.text, revision.pages,
                                                    readings, answers.get(question.pk, ()))
            for question in questions}


def revision_confirmations(revision):
    """The FindingConfirmations of ``revision``, oldest first (a new revision's assessments never read them)."""
    if revision is None:
        return []
    return list(FindingConfirmation.objects.filter(revision=revision).select_related(
        'confirmed_by', 'clarification', 'clarification__proposal').order_by('created_at', 'pk'))


def confirm_finding(*, encounter, clarification_id, candidate_id, attestation, user, membership):
    """Record a reviewer's confirmation of one verified candidate answer to an open question (HARNESS.md 11.3, 12.5),
    then act on it; returns (FindingConfirmation, effect).

    Under the encounter row lock: an owner or reviewer only; the question open on the current revision's final
    assessment and confirmed by no one yet; nothing processing; the candidate one of its VERIFIED candidates, recomputed
    here; the attestation exactly candidates.attestation(value). The immutable FindingConfirmation and its audit event
    'finding.confirmed' are recorded, then a service date enters as the member's date through jobs.change_context
    (every date safeguard and I8 apply; effect 'context') and every other fact is read by the re-assessment
    jobs.reassess_after_confirmation queues (effect 'reassessment'). A refusal from either leaves nothing recorded.
    Never approves anything: approval stays a separate decision."""
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
            jobs.change_context(locked, user, {'service_date': candidate['value']})
        else:
            jobs.reassess_after_confirmation(locked, user)
        encounter.state = refresh_state(locked)
    return confirmation, effect
