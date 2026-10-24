"""Persisted rows -> the JSON shapes in API.md. Read-only; no business rules."""
from django.conf import settings

from . import models, review
from .gi.profiles import PROFILES, profile


def _iso(value):
    return value.isoformat() if value else None


def _initials(user):
    name = (user.display_name or user.get_username() or '?').replace('-', ' ').replace('_', ' ')
    parts = [p for p in name.split() if p]
    letters = ''.join(p[0] for p in parts[:2]) or name[:2]
    return letters.upper()


def user_json(user):
    return {'id': str(user.pk), 'username': user.get_username(), 'label': user.label(),
            'actor_kind': user.actor_kind, 'initials': _initials(user)}


def session_json(user, membership):
    workspace = membership.workspace
    encounters = workspace.encounters.all()
    queue_states = {'needs_clarification', 'ready_for_review', 'provider_unknown'}
    return {
        'user': user_json(user),
        'workspace': {'id': str(workspace.pk), 'name': workspace.name, 'subtitle': 'Synthetic demonstration workspace',
                      'category': {'slug': workspace.category.slug, 'name': workspace.category.name,
                                   'profiles_version': workspace.category.profiles_version}},
        'role': membership.role, 'can_review': membership.can_review,
        'counts': {'documents': encounters.count(), 'queue': encounters.filter(state__in=queue_states).count()},
        'synthetic_only': settings.SYNTHETIC_ONLY, 'provider_mode': settings.PROVIDER_MODE,
        'release': settings.RELEASE_SHA,
    }


def _family_labels(encounter):
    assessment = encounter.current_assessment
    if assessment is None:
        return []
    seen = []
    for proposal in assessment.proposals.filter(bucket=models.Proposal.SELECTED):
        label = PROFILES[proposal.family].label if proposal.family in PROFILES else proposal.family
        if label not in seen:
            seen.append(label)
    return seen


def _service_date(encounter):
    context = encounter.current_context
    fact = (context.facts or {}).get('service_date') if context else None
    return (fact or {}).get('value') if (fact or {}).get('origin') in {'document', 'user'} else None


def _source_kind(revision):
    if revision is None:
        return None
    root = revision
    while root.parent_id:
        root = root.parent
    if root.kind == models.SourceRevision.PASTE:
        return 'paste'
    if root.source_file_id:
        return root.source_file.original_name.rsplit('.', 1)[-1].lower()
    return root.kind


def encounter_summary(encounter):
    return {
        'id': str(encounter.pk), 'title': encounter.title, 'state': encounter.state,
        'state_label': review.state_label(encounter.state), 'service_date': _service_date(encounter),
        'families': _family_labels(encounter), 'source_kind': _source_kind(encounter.current_revision),
        'open_clarifications': encounter.clarifications.filter(state=models.Clarification.OPEN,
                                                               assessment=encounter.current_assessment_id).count()
        if encounter.current_assessment_id else 0,
        'created_at': _iso(encounter.created_at),
    }


def _revision_json(revision):
    if revision is None:
        return None
    root = revision
    while root.parent_id:
        root = root.parent
    source = root.source_file
    addendum_offset = None
    if revision.kind == models.SourceRevision.ADDENDUM and revision.parent_id:
        addendum_offset = len(revision.parent.text)
    return {
        'id': str(revision.pk), 'number': revision.number, 'kind': revision.kind,
        'revisions_total': revision.encounter.revisions.count(), 'created_at': _iso(revision.created_at),
        'source_file': {'name': source.original_name, 'media_type': source.media_type, 'size': source.size,
                        'sha256': source.sha256} if source else None,
        'addendum_text': revision.addendum_text, 'addendum_offset': addendum_offset,
        'extraction': {'status': revision.extraction_status, 'method': revision.extraction_method,
                       'messages': revision.messages, 'ocr_pages': revision.ocr_pages,
                       'page_count': len(revision.pages), 'engine': revision.engine},
        'text': revision.text, 'text_sha256': revision.text_sha256, 'pages': revision.pages,
    }


def _routing_json(encounter):
    revision = encounter.current_revision
    if revision is None:
        return None
    # The routing the current assessment used: routing is stored per effective service date, so the
    # latest stored run may belong to another date than the one on screen.
    assessment = encounter.current_assessment
    run = assessment.routing if assessment is not None and assessment.revision_id == revision.pk else None
    if run is None:
        return None
    families = []
    for finding in run.result.get('findings', []):
        slug = finding.get('family')
        families.append({
            'family': slug, 'label': PROFILES[slug].label if slug in PROFILES else slug,
            'supported': PROFILES[slug].supported if slug in PROFILES else False,
            'status': finding.get('status'),
            'mentions': [{'status': m.get('status'), 'section': m.get('section'), 'cues': m.get('cues', []),
                          'span': m.get('span')} for m in finding.get('mentions', [])],
            'facts': finding.get('facts', []), 'missing': finding.get('missing', []),
        })
    return {'version': run.version, 'document_kind': run.result.get('document_kind'), 'families': families}


def _decision_json(decision):
    invalidation = getattr(decision, 'invalidation', None)
    return {
        'id': str(decision.pk), 'proposal_id': str(decision.proposal_id), 'code': decision.proposal.code,
        'action': decision.action, 'note': decision.note, 'reviewer': decision.reviewer.label(),
        'reviewer_kind': decision.reviewer_kind, 'created_at': _iso(decision.created_at),
        # When the reviewer decided; a carried row's own created_at is when it was carried (carried_at).
        'decided_at': _iso(review.decision_root(decision).created_at),
        'carried_at': _iso(decision.created_at) if decision.carried_from_id else None,
        'acknowledgement': decision.acknowledgement,
        'carried_from': str(decision.carried_from_id) if decision.carried_from_id else None,
        'invalidated': {'reason': invalidation.reason, 'created_at': _iso(invalidation.created_at)}
        if invalidation else None,
        'revision_number': decision.revision.number,
    }


DECISION_STATES = {models.Decision.APPROVE: 'approved', models.Decision.REJECT: 'rejected',
                   models.Decision.REINSTATE: 'reinstated'}


def _reinstated_by(proposal, decision):
    """Who reinstated an excluded proposal that now carries a decision, and when (the report names them too)."""
    if proposal.bucket != models.Proposal.EXCLUDED or decision is None:
        return None
    reinstate = review.reinstatement_for(decision)
    if reinstate is None:
        return None
    return {'reviewer': reinstate.reviewer.label(), 'reviewer_kind': reinstate.reviewer_kind,
            'decided_at': _iso(review.decision_root(reinstate).created_at)}


def _proposal_json(proposal, current, assessment, membership, clarification_ids):
    family = profile(proposal.family) if proposal.family in PROFILES else None
    decision = current.get(proposal.pk)
    return {
        'id': str(proposal.pk), 'key': proposal.key, 'bucket': proposal.bucket, 'code': proposal.code,
        'code_kind': proposal.code_kind, 'family': proposal.family,
        'family_label': family.label if family else proposal.family,
        'eyebrow': family.eyebrow if family else 'CPT', 'supported': family.supported if family else False,
        'profile_version': proposal.profile_version, 'status': proposal.status,
        'status_label': review.status_label(proposal.status), 'exclusion_reason': proposal.exclusion_reason,
        'reinstatable': proposal.reinstatable,
        'descriptor': {'status': 'withheld',
                       'label': 'Description withheld — no licensed CPT descriptor is connected.'},
        'evidence': proposal.evidence, 'rationale': proposal.rationale, 'units': proposal.units,
        'checks': proposal.checks, 'modifier_considerations': proposal.modifier_considerations,
        'clarification_ids': clarification_ids.get(proposal.pk, []),
        'decision': _decision_json(decision) if decision else None,
        'decision_state': DECISION_STATES.get(decision.action, 'undecided') if decision else 'undecided',
        'reinstated_by': _reinstated_by(proposal, decision),
        'allowed_actions': review.allowed_actions(proposal, assessment, membership),
    }


def _assessment_json(encounter, membership):
    assessment = encounter.current_assessment
    if assessment is None:
        return None, []
    current = review.current_decisions(assessment)
    clarifications = list(assessment.clarifications.all())
    by_proposal = {}
    for clarification in clarifications:
        if clarification.proposal_id and clarification.state == models.Clarification.OPEN:
            by_proposal.setdefault(clarification.proposal_id, []).append(str(clarification.pk))
    proposals = [_proposal_json(p, current, assessment, membership, by_proposal)
                 for p in assessment.proposals.select_related('assessment')]
    data = {
        'id': str(assessment.pk), 'profiles_version': assessment.profiles_version,
        'engine_version': assessment.engine_version, 'created_at': _iso(assessment.created_at),
        'proposals': proposals, 'encounter_checks': assessment.encounter_checks,
        'unsupported': assessment.unsupported, 'reference_sources': assessment.reference_sources,
        'summary': assessment.summary,
    }
    return data, clarifications


def _clarification_json(clarification):
    return {'id': str(clarification.pk), 'scope': clarification.scope,
            'proposal_id': str(clarification.proposal_id) if clarification.proposal_id else None,
            'family': clarification.family, 'fact': clarification.fact, 'question': clarification.question,
            'reason': clarification.reason, 'state': clarification.state}


def _provider_run_json(run):
    return {'id': str(run.pk), 'provider': run.provider, 'mode': 'replay' if run.provider == 'replay' else 'live',
            'state': run.state, 'http_status': run.http_status, 'latency_ms': run.latency_ms, 'usage': run.usage,
            'usage_basis': run.usage_basis, 'request_sha256': run.request_sha256,
            'response_sha256': run.response_sha256,
            'reused_from': str(run.reused_from_id) if run.reused_from_id else None, 'error': run.error,
            'reconciled': run.reconciled_at is not None, 'created_at': _iso(run.created_at)}


def _report_json(report):
    return {'id': str(report.pk), 'kind': report.kind, 'fmt': report.fmt, 'filename': report.filename,
            'sha256': report.sha256, 'generated_at': _iso(report.generated_at),
            'generated_by': report.generated_by.label(), 'download_url': f'/api/reports/{report.pk}/download'}


ACTIVITY_SUMMARIES = {
    'encounter.created': 'Document added', 'revision.extracted': 'Text extracted',
    'revision.addendum': 'Addendum added', 'context.changed': 'Encounter context changed',
    'provider.sending': 'Provider request sent', 'provider.finished': 'Provider response recorded',
    'provider.reused': 'Retained provider result reused (no new request)',
    'provider.reconciled': 'Unknown provider outcome reconciled', 'assessment.created': 'Checks completed',
    'decision.recorded': 'Review decision recorded', 'report.generated': 'Report generated',
    'pipeline.stopped': 'Processing stopped', 'pipeline.resumed': 'Processing resumed',
    'decisions.invalidated': 'Earlier decisions invalidated by a source revision',
    'account.provisioned': 'Account provisioned',
}


def _activity_json(event):
    actor = event.actor.label() if event.actor else 'CPT Studio'
    return {'event': event.event, 'summary': ACTIVITY_SUMMARIES.get(event.event, event.event),
            'actor': actor, 'actor_kind': event.actor_kind, 'created_at': _iso(event.created_at),
            'data': {k: v for k, v in event.data.items() if k in {'status', 'method', 'state', 'action', 'code',
                                                                  'kind', 'fmt', 'usage', 'http_status', 'pages',
                                                                  'ocr_pages', 'proposals', 'fields', 'stage'}}}


def encounter_detail(encounter, membership):
    from .jobs import busy  # local import: jobs imports this module's peers

    assessment, clarifications = _assessment_json(encounter, membership)
    revision = encounter.current_revision
    jobs = list(encounter.jobs.filter(revision=revision).order_by('created_at')) if revision else []
    return {
        **encounter_summary(encounter),
        'created_by': encounter.created_by.label(),
        'permissions': {'can_review': membership.can_review},
        'revision': _revision_json(revision),
        'context': {'facts': encounter.current_context.facts if encounter.current_context else {},
                    'user_values': encounter.user_values or {}},
        'routing': _routing_json(encounter),
        'pipeline': {'busy': busy(encounter), 'can_stop': busy(encounter) and membership.can_review,
                     'can_resume': review.can_resume(encounter) and membership.can_review,
                     # A member's Stop, as opposed to a stage the system cancelled (expired, or left by a dead worker).
                     'stopped_by_member': encounter.stopped_at is not None,
                     'stages': [{'kind': j.kind, 'state': j.state, 'error': j.error,
                                 'finished_at': _iso(j.finished_at)} for j in jobs]},
        'provider_runs': [_provider_run_json(r) for r in encounter.provider_runs.order_by('created_at')],
        'assessment': assessment,
        'clarifications': [_clarification_json(c) for c in clarifications],
        'decisions': {'history': [_decision_json(d) for d in encounter.decisions.select_related(
            'proposal', 'reviewer', 'revision').order_by('sequence')]},
        'readiness': review.readiness(encounter),
        'reports': [_report_json(r) for r in encounter.reports.order_by('-generated_at')],
        'activity': [_activity_json(e) for e in encounter.audit_events.select_related('actor').order_by('created_at')],
    }
