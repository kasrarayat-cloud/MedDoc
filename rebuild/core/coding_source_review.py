"""Explicit, append-only ICD source review; never calls a provider.

The provider run, its selections, and its approvals are immutable inputs here.
Source-derived suggestions have their own namespace and require an affirmative
clinician choice. Every display, decision and export recomputes eligibility.
"""
from copy import deepcopy
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from . import coding_service as service, coding_completeness as completeness
from .models import CodingDecision, CodingRelease, CodingRun, CodingSourceDecision
from .security import audit, membership

CONTRACT = 'source-icd-review-v1'
PROVIDER_REVIEW_FIRST = ('Review and approve the provider selections first, including any exclusions. '
    'Source suggestions remain unselected until you explicitly review them.')


def need(value, message):
    if not value:
        raise ValidationError(message)


def base_codes(run):
    """Only an intact, independently revalidated approval grants coverage."""
    decisions = list(CodingDecision.objects.filter(run=run)[:2])
    need(len(decisions) <= 1, 'The provider coding approval is ambiguous.')
    if not decisions:
        return None, []
    decision = decisions[0]
    need(decision.input_digest == run.input_digest
         and decision.selection_digest == service.selection_digest(run)
         and decision.selections == run.selection, 'The saved coding approval changed.')
    from .coding_dispatch import validate_selection
    service.approval_ready(run)
    need(validate_selection(run, deepcopy(decision.selections)) == decision.selections,
         'The saved code selections no longer validate.')
    rows = {r['id']: r for r in run.result.get('suggestions', [])}
    codes = []
    for key in decision.selections['selected_ids']:
        row = rows[key]
        if row['system'] == 'ICD-10-CM':
            codes.append(decision.selections['overrides'].get(key, {}).get('code', row['code']))
    return decision, sorted(set(codes))


def assess(encounter, run):
    need(run is not None and run.encounter_id == encounter.pk,
         'A completed coding result for this saved encounter is required.')
    service.assert_current(run, encounter)
    service.approval_ready(run)
    from .corti_coding import identity_blockers
    need(not identity_blockers(run), 'The complete source patient identity requires review before source coding.')
    need(not run.result.get('global_blockers'), 'Resolve the coding source or identity holds first.')
    base, approved = base_codes(run)
    releases = [r for r in run.releases if r.get('system') == 'ICD-10-CM']
    need(len(releases) == 1, 'One applicable dated ICD-10-CM reference is required.')
    bound = releases[0]
    metadata = CodingRelease.objects.select_related('release').defer('index', 'tabular', 'provenance').filter(
        release_id=bound['id'], digest=bound['coding_digest']).first()
    need(metadata is not None and metadata.release.effective_from <= encounter.service_date
         <= metadata.release.effective_until and metadata.release.version == bound['version']
         and metadata.release.sha256 == bound['sha256'], 'The dated ICD reference changed or does not apply.')
    inventory = completeness.inventory(encounter.notes)
    from .coding_reference_store import prediction_reference
    reference = prediction_reference(metadata, approved,
        source_contract='source-bound-clinical-coding-v4', source_inventory=inventory)
    evaluation = completeness.evaluate(run, reference, approved_codes=approved, inventory_result=inventory)
    review = {'contract': CONTRACT, 'encounter_id': str(encounter.pk), 'run_id': str(run.pk),
        'input_digest': run.input_digest, 'result_digest': service.digest(run.result),
        'requests_digest': service.digest(run.requests), 'selection_digest': service.selection_digest(run),
        'base_decision_id': str(base.pk) if base else None,
        'reference_id': str(metadata.pk), 'reference_digest': metadata.digest,
        'evaluation': evaluation}
    return review, base


def latest(run):
    if run is None:
        return None
    return CodingSourceDecision.objects.filter(run=run).select_related('user').order_by('-created_at', '-pk').first()


def provider_review_pending(run, base):
    # Provider approval freezes both included and excluded selections. Empty
    # provider output has no selections to review and supports a source-only
    # decision; service guards then keep that empty provider basis immutable.
    return base is None and bool(run.result.get('suggestions'))


def token_binding(encounter, run, user, review, previous):
    return {'contract': CONTRACT, 'actor': str(user.pk), 'encounter': str(encounter.pk),
        'run': str(run.pk), 'review_digest': service.digest(review),
        'previous': str(previous.pk) if previous else ''}


def _items(review):
    evaluation = review['evaluation']
    return evaluation['inventory']


def _candidates(review):
    return {row['id']: row for row in review['evaluation']['suggestions']}


def validated_choices(review, choices):
    """Recheck stored decisions without trusting saved eligibility booleans."""
    need(type(choices) is dict, 'Invalid source review outcomes.')
    rows = {r['id']: r for r in _items(review)}
    candidates = _candidates(review)
    need(set(choices) <= set(rows), 'A source review outcome refers to a different condition.')
    for key, value in choices.items():
        need(type(value) is dict and set(value) == {'action', 'suggestion_id', 'reason'},
             'Invalid source review outcome fields.')
        action, candidate_id, reason = value['action'], value['suggestion_id'], value['reason']
        need(type(reason) is str and len(reason) <= 2000 and type(candidate_id) is str,
             'Invalid source review reason or suggestion.')
        need(not rows[key].get('approved_codes'), 'This condition is already covered by a saved provider approval.')
        if action == 'accept':
            candidate = candidates.get(candidate_id)
            need(candidate is not None and candidate.get('eligible') is True
                 and candidate.get('condition_id') == key,
                 'Select one verified source-derived suggestion for this condition.')
        else:
            need(action in ('no_code', 'needs_clarification') and not candidate_id and bool(reason.strip()),
                 'An explicit no-code or clarification outcome requires a reason and no selected code.')
    return deepcopy(choices)


def current_decision(run, review):
    decision = latest(run)
    if decision is None:
        return None
    need(decision.review_digest == service.digest(review) and decision.review == review,
         'The saved source review no longer matches this source or reference. Its history is preserved.')
    validated_choices(review, decision.choices)
    return decision


def presentation(review, decision=None):
    choices = decision.choices if decision else {}
    candidates = _candidates(review)
    rows = []
    counts = {'approved': 0, 'reviewed_no_code': 0, 'needs_review': 0, 'needs_clarification': 0}
    for item in _items(review):
        chosen = choices.get(item['id'], {})
        state = ('approved_code' if item.get('approved_codes') or chosen.get('action') == 'accept'
                 else 'reviewed_no_code' if chosen.get('action') == 'no_code'
                 else 'needs_clarification' if chosen.get('action') == 'needs_clarification' else 'needs_review')
        counts['approved' if state == 'approved_code' else state] += 1
        approved = list(item.get('approved_codes', []))
        if chosen.get('action') == 'accept':
            approved.append(candidates[chosen['suggestion_id']]['code'])
        spans = item.get('evidence', [])
        rows.append({**item, 'label': item.get('condition_text', ''), 'status': state,
            'evidence': [{**span, 'text': span.get('text', span.get('quote', ''))} for span in spans],
            'approved_codes': approved, 'chosen': chosen,
            'suggestions': [c for c in candidates.values() if c.get('condition_id') == item['id']]})
    blockers = review['evaluation'].get('blockers', [])
    complete = bool(rows) and not blockers and not counts['needs_review'] and not counts['needs_clarification']
    all_coded = complete and counts['approved'] == len(rows)
    return {'rows': rows, 'counts': counts, 'current_count': len(rows), 'complete': complete,
        'all_coded': all_coded, 'blockers': blockers,
        'state_label': ('All conditions in this source review have approved ICD codes' if all_coded else
            'Source review complete; explicit no-code outcomes retained' if complete else 'Partial ICD coding — source review remains'),
        'coverage_limit': review['evaluation'].get('coverage', {}).get('limit', '')}


def view(encounter, run, user):
    if run is None or run.state not in ('succeeded', 'needs_detail'):
        return None
    try:
        review, base = assess(encounter, run)
        decision = current_decision(run, review)
        value = presentation(review, decision)
        previous = str(decision.pk) if decision else ''
        pending = provider_review_pending(run, base)
        value.update(available=True, review_digest=service.digest(review), prior_revision=previous,
            can_review=membership(user, encounter.department).role in ('owner', 'clinician')
                and any(r['status'] in ('needs_review', 'needs_clarification') for r in value['rows'])
                and not value['blockers'] and not pending,
            approval_pending_reason=PROVIDER_REVIEW_FIRST if pending else '',
            display_token=signing.dumps(token_binding(encounter, run, user, review, decision), salt=CONTRACT, compress=True),
            reviewer=decision.user if decision else None, approved_at=decision.approved_at if decision else None)
        return value
    except ValidationError as exc:
        return {'available': False, 'complete': False, 'can_review': False,
                'state_label': 'Partial ICD coding — source completeness could not be verified',
                'reason': '; '.join(exc.messages)}


@transaction.atomic
def decide(encounter, user, token, expected_digest, expected_previous, changes):
    e = service.locked_encounter(encounter, user, clinician=True)
    run = CodingRun.objects.select_for_update().filter(encounter=e,
        input_digest=service.input_snapshot(e)[3]).first()
    review, base = assess(e, run)
    need(not provider_review_pending(run, base), PROVIDER_REVIEW_FIRST)
    previous = current_decision(run, review)
    try:
        received = signing.loads(token, salt=CONTRACT, max_age=12*60*60)
    except signing.BadSignature as exc:
        raise ValidationError('The source review expired. Reopen Coding.') from exc
    expected = token_binding(e, run, user, review, previous)
    need(received == expected and expected_digest == expected['review_digest']
         and expected_previous == expected['previous'],
         'This source review changed. Reload it; nothing was saved.')
    need(not review['evaluation'].get('blockers'), 'Resolve the source completeness holds first.')
    need(type(changes) is dict and bool(changes), 'Choose an explicit source review outcome.')
    old = previous.choices if previous else {}
    for key, choice in changes.items():
        need(key not in old or old[key]['action'] == 'needs_clarification',
             'An approved source decision is retained unchanged.')
    choices = validated_choices(review, {**old, **changes})
    need(choices != old, 'No source review outcomes changed.')
    decision = CodingSourceDecision.objects.create(run=run, base_decision=base, previous=previous,
        user=user, review_digest=service.digest(review), review=review, choices=choices)
    audit(user, 'coding.source_review_approved', decision.pk, department=e.department,
        run_id=str(run.pk), previous=str(previous.pk) if previous else None,
        review_digest=decision.review_digest, choice_digest=service.digest(choices),
        review_execution='synthetic_clinician_account' if settings.SYNTHETIC_ONLY else 'clinician')
    return decision


def accepted_rows(encounter, run):
    """Return only explicitly approved, freshly verified source candidates."""
    if latest(run) is None:
        return None, [], None
    review, _ = assess(encounter, run)
    decision = current_decision(run, review)
    candidates = _candidates(review)
    rows, seen = [], set()
    summary = presentation(review, decision)
    for condition, choice in decision.choices.items():
        if choice['action'] != 'accept':
            continue
        candidate = candidates[choice['suggestion_id']]
        if candidate['code'] in seen:
            continue
        seen.add(candidate['code'])
        rows.append({**candidate, 'system': 'ICD-10-CM', 'export_route': 'source_derived_review',
            'source_decision_id': str(decision.pk), 'source_review_digest': decision.review_digest,
            'source_condition_id': condition,
            'evidence_spans': [{'quote': span['text'], 'start': span['start'], 'end': span['end']}
                               for span in candidate['evidence']],
            'review_execution': 'synthetic_clinician_account' if settings.SYNTHETIC_ONLY else 'clinician'})
    return decision, rows, {'state_label': summary['state_label'], 'complete': summary['complete'],
        'all_coded': summary['all_coded'], 'counts': summary['counts'], 'source_decision_id': str(decision.pk),
        'reviewed_outcomes': [{'condition': r['label'], 'action': r['chosen'].get('action'),
            'reason': r['chosen'].get('reason')} for r in summary['rows']
            if r['chosen'].get('action') in ('no_code', 'needs_clarification')]}
