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

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import audit
from .models import (Assessment, Clarification, Decision, DecisionInvalidation, Encounter, Job, Proposal,
                     ProviderRun, SourceRevision)
from .types import sha256_json, to_jsonable

APPROVE, REJECT, REINSTATE, REVOKE = Decision.APPROVE, Decision.REJECT, Decision.REINSTATE, Decision.REVOKE
ACTION_LABELS = dict(Decision.ACTIONS)
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


def _actions(proposal, current, text):
    if current is not None and current.action in (APPROVE, REJECT):
        return [REVOKE]
    exact = bool(exact_evidence(proposal.evidence, text))
    if proposal.bucket == SELECTED and proposal.status in BUCKET_STATUSES[SELECTED]:
        actions = [APPROVE] if proposal.status == Proposal.READY and exact else []
        return actions + [REJECT] + ([REVOKE] if current else [])
    if proposal.bucket == EXCLUDED and proposal.status == Proposal.STATUS_EXCLUDED:
        if current is None:
            return [REINSTATE] if proposal.reinstatable and exact else []
        return ([APPROVE] if exact and _reinstatement_clear(proposal) else []) + [REJECT, REVOKE]
    return [REVOKE] if current else []


def _reinstatement_clear(proposal):
    """A reinstated exclusion is approvable only under the gates a selected code meets, as the validation layer
    recorded them in its 'review.reinstatement' check. Fail-closed: without a passing check, no approve."""
    return any(c.get('id') == 'review.reinstatement' and c.get('status') == 'pass' for c in proposal.checks or [])


def _allowed(proposal, assessment, membership, encounter):
    if not _is_reviewer(membership, encounter) or proposal.assessment_id != assessment.pk:
        return []
    if (encounter.current_assessment_id != assessment.pk
            or assessment.revision_id != encounter.current_revision_id):
        return []
    return _actions(proposal, _current_decision(proposal), assessment.revision.text)


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
            raise ValidationError('Approving requires an acknowledgement.')
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


def _same_assessment(previous, digest, revision, context, routing_run, provider_run):
    return (previous is not None and previous.sha256 == digest and previous.revision_id == revision.pk
            and previous.context_id == context.pk and previous.routing_id == routing_run.pk
            and previous.provider_run_id == (provider_run.pk if provider_run else None))


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


def _carry_target(decision, old, candidates, all_new):
    """(new proposal, '') when ``decision`` still holds in the new assessment, else (None, why not)."""
    if not candidates:
        if any(item.code == old.code for item in all_new):
            return None, f'the evidence or checks for {old.code} changed'
        return None, f'{old.code} is no longer proposed'
    target = next((item for item in candidates if item.key == old.key), candidates[0])
    for field, label, show in (('code', 'code', str), ('bucket', 'list', str),
                               ('status', 'status', status_label), ('profile_version', 'profile version', str)):
        before, after = getattr(old, field), getattr(target, field)
        if before != after:
            return None, f'the {label} of {old.code} changed from {show(before)} to {show(after)}'
    if decision.action == REINSTATE and not target.reinstatable:
        return None, f'{old.code} can no longer be reinstated'
    return target, ''


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
        target, problem = _carry_target(decision, old, candidates, new_items)
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


def persist_assessment(*, encounter, revision, context, routing_run, provider_run, result):
    """Record an AssessmentResult as the encounter's current assessment, in one transaction.

    Creates the immutable Assessment and Proposal rows and the Clarification
    rows, withdraws earlier open clarifications that were not raised again,
    then carries or invalidates the previous assessment's current decisions.
    Re-persisting an identical result on identical inputs returns the current
    assessment unchanged.
    """
    digest = sha256_json(result)
    with transaction.atomic():
        locked = _lock(encounter)
        revision = SourceRevision.objects.get(pk=revision.pk)
        _check_inputs(locked, revision, context, routing_run, provider_run)
        previous = locked.current_assessment
        if _same_assessment(previous, digest, revision, context, routing_run, provider_run):
            encounter.state = refresh_state(locked)
            return previous
        _check_result(result, revision.text)
        assessment = Assessment.objects.create(
            encounter=locked, revision=revision, context=context, routing=routing_run, provider_run=provider_run,
            profiles_version=result.profiles_version, engine_version=result.engine_version,
            reference_sources=to_jsonable(result.reference_sources),
            encounter_checks=to_jsonable(result.encounter_checks), unsupported=to_jsonable(result.unsupported),
            summary=to_jsonable(result.summary), sha256=digest)
        proposals = {}
        for position, item in enumerate(result.proposals):
            proposals[item.key] = Proposal.objects.create(
                assessment=assessment, key=item.key, bucket=item.bucket, code=item.code, code_kind=item.code_kind,
                family=item.family, profile_version=item.profile_version, status=item.status,
                exclusion_reason=item.exclusion_reason, reinstatable=item.reinstatable,
                provider_display=item.provider_display, evidence=to_jsonable(item.evidence),
                rationale=item.rationale, checks=to_jsonable(item.checks),
                modifier_considerations=list(item.modifier_considerations), units=item.units,
                fingerprint=item.fingerprint, position=position)
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
    """Selected proposals, and excluded ones a reviewer has reinstated, need an approve or reject."""
    return proposal.bucket == SELECTED or (proposal.bucket == EXCLUDED and decision is not None)


def _assessment_blockers(encounter, assessment):
    blockers = []
    if assessment.context_id != encounter.current_context_id:
        blockers.append('The encounter context changed; re-assessment has not finished')
    run = assessment.provider_run
    if run is None:
        blockers.append('The provider was not run')
    elif run.state in UNSETTLED_RUN_STATES:
        blockers.append('The provider outcome is unknown')
    elif run.state != ProviderRun.SUCCEEDED:
        blockers.append('The provider request failed')
    open_clarifications = list(assessment.clarifications.filter(state=Clarification.OPEN))
    for clarification in open_clarifications:
        if clarification.scope == 'encounter' and clarification.proposal_id is None:
            blockers.append(f'Open clarification: {_human(clarification.fact)}')
    asked = {item.proposal_id for item in open_clarifications if item.proposal_id}
    current = current_decisions(assessment)
    reviewable = 0
    for proposal in assessment.proposals.all():
        decision = current.get(proposal.pk)
        if not _reviewable(proposal, decision):
            continue
        reviewable += 1
        if decision is not None and decision.action in (APPROVE, REJECT):
            continue
        if decision is not None:
            blockers.append(f'{proposal.code} was reinstated and has no decision')
        elif proposal.pk in asked:
            blockers.append(f'{proposal.code} has an open clarification')
        elif proposal.status == Proposal.NEEDS_CLARIFICATION:
            blockers.append(f'{proposal.code} needs clarification')
        else:
            blockers.append(f'{proposal.code} has no decision')
    if run is not None and run.state == ProviderRun.SUCCEEDED and reviewable == 0:
        blockers.append('No CPT code was proposed')
    return blockers


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
    if job.kind == Job.EXTRACT:
        return 'extraction_failed'
    if job.kind != Job.PREDICT:
        return 'processing_failed'
    if job.state == Job.UNKNOWN:
        return 'provider_unknown'
    run = (encounter.provider_runs.filter(revision=revision, created_at__gte=job.created_at)
           .order_by('-created_at', '-pk').first())
    if run is None:
        return 'provider_not_run'
    if run.state in UNSETTLED_RUN_STATES:
        return 'provider_unknown'
    return 'processing_failed' if run.state == ProviderRun.SUCCEEDED else 'provider_failed'


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
    revision = encounter.current_revision
    if revision is None or _active_jobs(encounter):
        return 'processing'
    if revision.extraction_status == SourceRevision.FAILED:
        return 'extraction_failed'
    latest = encounter.jobs.filter(revision=revision).order_by('-created_at', '-pk').first()
    if latest is not None and latest.state == Job.CANCELLED:
        return 'stopped'
    if revision.extraction_status == SourceRevision.PENDING:
        return 'processing' if latest is None else 'extraction_failed'
    if latest is not None and latest.state in (Job.FAILED, Job.UNKNOWN):
        return _failed_stage_state(encounter, revision, latest)
    assessment = live_assessment(encounter)
    if assessment is None or assessment.context_id != encounter.current_context_id:
        return 'provider_unknown' if _unreconciled_unknown(encounter) else 'processing'
    run = assessment.provider_run
    if run is None:
        return 'provider_not_run'
    if run.state in UNSETTLED_RUN_STATES:
        return 'provider_unknown'
    if run.state != ProviderRun.SUCCEEDED:
        return 'provider_failed'
    return _review_state(encounter, assessment)


def refresh_state(encounter):
    """Recompute the cached Encounter.state (API.md vocabulary); writes only when it changed."""
    with transaction.atomic():
        locked = _lock(encounter)
        state = _derive_state(locked)
        if locked.state != state:
            Encounter.objects.filter(pk=locked.pk).update(state=state, updated_at=timezone.now())
    encounter.state = state
    return state
