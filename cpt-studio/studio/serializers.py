"""Persisted rows -> the JSON shapes in API.md. Read-only; no business rules."""
from django.conf import settings

from . import models, participants, review
from .gi.context import charge_date_problem, is_member_conflict
from .gi.profiles import PROFILES, profile
from .participants.reading import CODE as CODE_SHAPE
from .providers.base import ProviderUnavailable
from .types import to_jsonable


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
    # the review queue's own rule, row by row (queue_reasons): a state that always waited on a member is on it whatever
    # else is found, so its rows are counted without reading further
    queued = sum(1 for encounter in encounters.select_related('current_revision', 'current_context', 'current_assessment')
                 if encounter.state in QUEUE_STATES or queue_reasons(encounter))
    return {
        'user': user_json(user),
        'workspace': {'id': str(workspace.pk), 'name': workspace.name, 'subtitle': 'Synthetic demonstration workspace',
                      'category': {'slug': workspace.category.slug, 'name': workspace.category.name,
                                   'profiles_version': workspace.category.profiles_version}},
        'role': membership.role, 'can_review': membership.can_review,
        'acknowledgement': review.ACKNOWLEDGEMENTS.get(user.actor_kind, ''),
        'counts': {'documents': encounters.count(), 'queue': queued},
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


def _service_date_conflict(encounter):
    """Whether the service date is a conflict (within the document, or a member's against it): the list says so,
    never "not documented" (refutation r1, context-5). The question a closing charge block asks is no conflict
    (_service_date_asked)."""
    context = encounter.current_context
    fact = (context.facts or {}).get('service_date') if context else None
    return (fact or {}).get('origin') == 'conflict' and not charge_date_problem(fact)


def _service_date_asked(encounter):
    """Whether the service date is the question a closing charge block asks (context.charge_date_problem): its lines may
    record another occurrence, so the list says it is asked, never "in conflict" (the sixth refutation, dates-n6-2)."""
    context = encounter.current_context
    return charge_date_problem((context.facts or {}).get('service_date') if context else None) is not None


def _service_date_evidence(encounter):
    """The documented text the reader kept as the evidence of a service date it could not use (origin missing, with
    evidence): the lists quote it instead of saying "not documented", as the review page's date chip does (gi2
    integration; occurrence RC5 left the list cell and the overview card saying "Not documented"). '' otherwise."""
    context = encounter.current_context
    fact = (context.facts or {}).get('service_date') if context else None
    if not fact or fact.get('origin') != 'missing' or fact.get('value') not in (None, ''):
        return ''
    for item in fact.get('evidence') or []:
        text = ' '.join(str((item or {}).get('text') or '').split()) if isinstance(item, dict) else ''
        if text:
            return text[:120]
    return ''


def _context_facts(context):
    """The stored context facts, each with ``member_conflict`` (context.is_member_conflict) and ``date_asked``
    (context.charge_date_problem): the predicates every reader that words a conflict asks, so the screen never calls a
    member's value or a closing charge block's question conflicting documentation."""
    facts = (context.facts or {}) if context else {}
    return {name: {**fact, 'member_conflict': is_member_conflict(fact), 'date_asked': charge_date_problem(fact) is not None}
            for name, fact in facts.items()}


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


# The states that have always waited on a workspace member (a clarification, a review decision, a reconciliation): an
# encounter in one stays on the review queue whatever else is found (queue_reasons).
QUEUE_STATES = frozenset({'needs_clarification', 'ready_for_review', 'provider_unknown'})


def queue_reasons(encounter, coding=None):
    """What the encounter waits on a workspace member for, in this order; the review queue - and the session's count of it
    - lists the encounter when this is not empty (refutation gi2, demo RC6: ho-06, no code selected with a second review
    available, and ho-09, reviewed with a documented service unresolved, were off a queue of three states):
      'question'        an open clarification on the assessment of the current revision;
      'decision'        a code that needs a reviewer's decision - selected or reinstated with none that stands, or an
                        exclusion to confirm or reinstate - counted as readiness counts it (review._decisions_waiting);
      'reconciliation'  a provider request whose outcome is unknown and not reconciled;
      'incomplete'      the encounter's coding completeness reads incomplete (review.coding_completeness, the encounter
                        view's banner): a documented service or act without a supported proposal, a conflict in the
                        record, a question, or no provider response read;
      'second_review'   the bounded second review can be asked for now - only ever for a documented service left
                        without a supported proposal, so only beside 'incomplete' (jobs.second_review_status, by the
                        predicate POST second-review accepts an ask by: never for an ask already queued, whose stage
                        Resume runs or that failed - fix round gi2, truth-1);
      'state'           a state that always waited on a member (QUEUE_STATES), when none of the above is found.
    Nothing while the encounter is processing: it waits on its stages then. Read-only, from the rows; ``coding``: the
    coding completeness already read for this encounter."""
    if encounter.state == 'processing':
        return []
    reasons = []
    assessment = review.live_assessment(encounter)
    if assessment is not None:
        if assessment.clarifications.filter(state=models.Clarification.OPEN).exists():
            reasons.append('question')
        if review._decisions_waiting(assessment)[0]:
            reasons.append('decision')
    if review._unreconciled_unknown(encounter):  # the rule the derived state and every send block read
        reasons.append('reconciliation')
    coding = review.coding_completeness(encounter) if coding is None else coding
    if coding.get('state') == 'incomplete':
        reasons.append('incomplete')
        from .jobs import second_review_status  # local import: jobs imports this module's peers
        try:
            offered = second_review_status(encounter)['available']
        except ProviderUnavailable:
            # a provider this installation cannot build (no credentials configured) can be asked nothing: never claimed,
            # and the list and the session - every page - never fail for it (only the encounter view reads it otherwise)
            offered = False
        if offered:
            reasons.append('second_review')
    if not reasons and encounter.state in QUEUE_STATES:
        reasons.append('state')
    return reasons


def encounter_summary(encounter):
    coding = review.coding_completeness(encounter)
    return {
        'id': str(encounter.pk), 'title': encounter.title, 'state': encounter.state,
        # worded from the run a provider_failed state reads: a response refused whole is "not used" (7c8 reports-5)
        'state_label': review.encounter_state_label(encounter), 'service_date': _service_date(encounter),
        'service_date_conflict': _service_date_conflict(encounter),
        'service_date_asked': _service_date_asked(encounter),
        'service_date_evidence': _service_date_evidence(encounter),
        'families': _family_labels(encounter), 'source_kind': _source_kind(encounter.current_revision),
        'open_clarifications': encounter.clarifications.filter(state=models.Clarification.OPEN,
                                                               assessment=encounter.current_assessment_id).count()
        if encounter.current_assessment_id else 0,
        # the encounter view's coding completeness, so a reviewed encounter whose coding is incomplete says so in the
        # lists, and what it waits on a member for: on the review queue when not empty (refutation gi2, demo RC6)
        'coding_state': coding['state'], 'queue_reasons': queue_reasons(encounter, coding),
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
                   models.Decision.REINSTATE: 'reinstated', models.Decision.CONFIRM: 'exclusion_confirmed'}


def _reinstated_by(proposal, decision):
    """Who reinstated an excluded proposal that now carries a decision, and when (the report names them too)."""
    if proposal.bucket != models.Proposal.EXCLUDED or decision is None or decision.action == models.Decision.CONFIRM:
        return None  # a confirmed exclusion was never reinstated
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
        'support': proposal.support or {},
        'clarification_ids': clarification_ids.get(proposal.pk, []),
        'decision': _decision_json(decision) if decision else None,
        'decision_state': DECISION_STATES.get(decision.action, 'undecided') if decision else 'undecided',
        'reinstated_by': _reinstated_by(proposal, decision),
        'allowed_actions': review.allowed_actions(proposal, assessment, membership),
        'approve_withheld_by': review.approve_withheld_by(proposal, assessment, current),
        # Who proposed it, what the CMS reference checks found, and (above) a member's decision: three statuses, never
        # one (I4). Participants' positions are shown beside it and decide nothing (I2, I3).
        'proposed_by': review.proposed_by(proposal),
        'participant_positions': review.participant_positions(proposal, assessment.participants),
        'reference_check': review.reference_check(proposal),
        'retrieval': review.proposal_retrieval(proposal, assessment.retrieval),
        # harness@2 (HARNESS.md 11.1, 11.3, 12.6), from the engine's support record: the phase in which each participant
        # first proposed the code (a code first proposed in peer review is never independent), and the reviewer
        # confirmations this proposal's checks read - a confirmed fact, never a decision
        'phases': _phases(proposal.support), 'confirmed': _confirmed_ids(proposal.support),
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
        'summary': assessment.summary, 'services': assessment.services or {},
        # as the review leaves it: a code the reviewer reinstated counts as a selected one, as in the reports
        # (review.reviewed_completeness; refutation P2FR, EUS-SECOND)
        'completeness': review.reviewed_completeness(assessment, current) or {},
        'second_run': str(assessment.second_run_id) if assessment.second_run_id else None,
    }
    return data, clarifications


def _phases(support):
    """{participant: 'independent' | 'peer_review'} from a proposal's support record; {} when it records none."""
    phases = (support or {}).get('phases')
    if not isinstance(phases, dict):
        return {}
    return {name: phase for name, phase in phases.items()
            if isinstance(name, str) and phase in (models.ProviderRun.INDEPENDENT, models.ProviderRun.PEER_REVIEW)}


def _confirmed_ids(support):
    """The ids of the FindingConfirmations a proposal's checks read (the engine's support['confirmed'])."""
    confirmed = (support or {}).get('confirmed')
    return [str(item) for item in confirmed if isinstance(item, str)] if isinstance(confirmed, list) else []


def _clarification_json(clarification):
    return {'id': str(clarification.pk), 'scope': clarification.scope,
            'proposal_id': str(clarification.proposal_id) if clarification.proposal_id else None,
            'family': clarification.family, 'fact': clarification.fact, 'question': clarification.question,
            'reason': clarification.reason, 'state': clarification.state}


def _question_json(clarification, candidates=(), confirmation=None):
    """A clarification as _clarification_json serves it (ops/verification/test_verify_browser.cjs pins that text) with,
    harness@2 (HARNESS.md 12.5, 12.6), the candidate answers the participants' located passages offer for it (only an
    open question of the final assessment has any) and its confirmation, or null."""
    return {**_clarification_json(clarification), 'candidates': list(candidates),
            'confirmation': confirmation_json(confirmation) if confirmation is not None else None}


def _provider_run_json(run):
    # a harness participant's replayed run reads 'replay' too: its run records the mode it ran in (review.run_mode)
    return {'id': str(run.pk), 'provider': run.provider, 'mode': review.run_mode(run),
            'state': run.state, 'http_status': run.http_status, 'latency_ms': run.latency_ms, 'usage': run.usage,
            'usage_basis': run.usage_basis, 'request_sha256': run.request_sha256,
            'response_sha256': run.response_sha256,
            'reused_from': str(run.reused_from_id) if run.reused_from_id else None, 'error': run.error,
            'reconciled': run.reconciled_at is not None, 'created_at': _iso(run.created_at),
            'purpose': run.purpose, 'scope_items': list((run.scope or {}).get('items', []))}


def confirmation_json(confirmation):
    """A FindingConfirmation (HARNESS.md 11.3, 12.6): the fact a reviewer confirmed from a participant's located
    passage, with that passage, who located it, who confirmed it and the attestation recorded - a confirmed fact,
    never a decision on a code."""
    reviewer = confirmation.confirmed_by
    return {'id': str(confirmation.pk), 'clarification_id': str(confirmation.clarification_id),
            'scope': confirmation.scope, 'fact': confirmation.fact, 'family': confirmation.family,
            'proposal_key': confirmation.proposal_key, 'value': confirmation.value,
            'spans': list(confirmation.spans or []), 'located_by': list(confirmation.located_by or []),
            'runs': list(confirmation.runs or []), 'confirmed_by': reviewer.label(),
            'confirmed_by_kind': reviewer.actor_kind, 'attestation': confirmation.attestation,
            'created_at': _iso(confirmation.created_at), 'revision_number': confirmation.revision.number}


def _report_json(report):
    return {'id': str(report.pk), 'kind': report.kind, 'fmt': report.fmt, 'filename': report.filename,
            'sha256': report.sha256, 'generated_at': _iso(report.generated_at),
            'generated_by': report.generated_by.label(), 'download_url': f'/api/reports/{report.pk}/download'}


ACTIVITY_SUMMARIES = {
    'encounter.created': 'Document added', 'revision.extracted': 'Text extracted',
    'revision.addendum': 'Addendum added', 'context.changed': 'Encounter context changed',
    'provider.sending': 'Provider request started', 'provider.finished': 'Provider request finished',
    'provider.reused': 'Retained provider result reused (no new request)',
    'provider.second_review_requested': 'Second provider review requested by a reviewer',
    'provider.reconciled': 'Unknown provider outcome reconciled', 'assessment.created': 'Checks completed',
    'decision.recorded': 'Review decision recorded', 'report.generated': 'Report generated',
    'pipeline.stopped': 'Processing stopped', 'pipeline.resumed': 'Processing resumed',
    'decisions.invalidated': 'Earlier decisions invalidated by a source revision',
    'account.provisioned': 'Account provisioned',
    'finding.confirmed': "Finding confirmed from a participant's located passage (not a decision)",
}
# Repair gi2 (the recovery lens): 'provider.sending' is recorded before the exchange, so it says only that the attempt
# started, and 'provider.finished' is worded from the outcome its own row recorded (every revision records the state and
# the HTTP status there). An attempt the adapter recorded as not sent, or whose outcome is unknown, read "Provider request
# sent" and "Provider response recorded" beside a run the Provider runs card listed as not sent. Any other recorded value
# keeps the neutral 'Provider request finished'.
FINISHED_SUMMARIES = {'succeeded': 'Provider response recorded', 'failed': 'Provider request failed',
                      'unknown': 'Provider outcome unknown: no complete response was recorded',
                      'not_sent': 'Provider request not sent'}
# A harness participant's attempt is named by its participant ("Astra request started", "Fable response recorded"): its
# audit rows record the provider (jobs._send, stage_participant). Corti's rows read as before.
PARTICIPANT_EVENTS = {'provider.sending': '{label} request started',
                      'provider.reused': 'Retained {label} result reused (no new request)',
                      'provider.reconciled': 'Unknown {label} outcome reconciled'}


def _activity_summary(event):
    summary = ACTIVITY_SUMMARIES.get(event.event, event.event)
    data = event.data if isinstance(event.data, dict) else {}
    state = data.get('state')
    label = participants.LABELS.get(data.get('provider')) if isinstance(data.get('provider'), str) else None
    if label and event.event in PARTICIPANT_EVENTS:
        return PARTICIPANT_EVENTS[event.event].format(label=label)
    if event.event != 'provider.finished' or not isinstance(state, str) or state not in FINISHED_SUMMARIES:
        return summary
    finished = FINISHED_SUMMARIES[state] if label is None else FINISHED_SUMMARIES[state].replace('Provider', label, 1)
    status = data.get('http_status')
    if state == 'failed' and isinstance(status, int) and not isinstance(status, bool):
        return f'{finished} (HTTP {status})'
    return finished


def _activity_json(event):
    actor = event.actor.label() if event.actor else 'CPT Studio'
    return {'event': event.event, 'summary': _activity_summary(event),
            'actor': actor, 'actor_kind': event.actor_kind, 'created_at': _iso(event.created_at),
            'data': {k: v for k, v in event.data.items() if k in {'status', 'method', 'state', 'action', 'code',
                                                                  'kind', 'fmt', 'usage', 'http_status', 'pages',
                                                                  'ocr_pages', 'proposals', 'fields', 'stage',
                                                                  'fact', 'effect'}}}


def is_owner(membership):
    return membership.active and membership.role == models.Membership.OWNER


# --- the harness block (HARNESS.md 7): one row per participant, reference validation, clarification, final status -----

# The stages of a chain, in order (HARNESS.md 12.1): the assess stands twice - assess #1, which ends phase 1 (every
# assess before harness@2 is one), and assess #2, which follows the peer stages, as its re-assessments after a
# confirmation do. A job takes its kind's place; an assess, the place of what it reads (_stage_index).
STAGE_ORDER = (models.Job.EXTRACT, models.Job.ANALYZE, models.Job.PREDICT, models.Job.ASTRA, models.Job.FABLE,
               models.Job.ASSESS, models.Job.ASTRA_PEER, models.Job.FABLE_PEER, models.Job.ASSESS)
# Each row's stages, in chain order: Corti's predict; each model participant's first reading, then its peer review.
HARNESS_STAGES = {review.CORTI: (models.Job.PREDICT,), 'astra': (models.Job.ASTRA, models.Job.ASTRA_PEER),
                  'fable': (models.Job.FABLE, models.Job.FABLE_PEER)}
PEER_STAGES = tuple(kind for kind in STAGE_ORDER if kind in models.Job.PEER_KINDS)  # astra_peer, then fable_peer
# Assessment.participants states (types.PARTICIPANT_STATES) -> the row's state
RECORD_STATES = {'read': 'done', 'refused': 'refused', 'failed': 'failed', 'unknown': 'unknown', 'not_sent': 'not_sent',
                 'blocked': 'blocked', 'not_configured': 'not_configured', 'not_run': 'not_sent'}
RUN_STATES = {models.ProviderRun.SUCCEEDED: 'done', models.ProviderRun.FAILED: 'failed',
              models.ProviderRun.UNKNOWN: 'unknown', models.ProviderRun.NOT_SENT: 'not_sent',
              models.ProviderRun.CANCELLED: 'stopped'}
WAITING_DETAIL = 'Waiting for the earlier stages to finish.'
RUNNING_DETAIL = 'Running now.'
STOPPED_DETAIL = 'Processing stopped before this stage finished; Resume runs it.'
RECONCILE_FIRST = ' Reconcile it before anything else is sent for this document.'
BLOCKED_DETAIL = 'Nothing was sent: a previous request has an unknown outcome.' + RECONCILE_FIRST
REUSED_WORDS = ' (a retained answer to the identical request was reused; nothing was sent)'


def _stage_index(job):
    """``job``'s place in STAGE_ORDER, or None for a stage the chain does not list (the second review's): its kind's
    first place, except an assess that reads the peer reviews - assess #2 or a re-assessment after a confirmation
    (jobs._assess_mode, which reads the key it was queued under) - which takes the second assess's."""
    from .jobs import FIRST, _assess_mode  # local import: jobs imports this module's peers

    if job.kind not in STAGE_ORDER:
        return None
    if job.kind == models.Job.ASSESS and _assess_mode(job) != FIRST:
        return len(STAGE_ORDER) - 1
    return STAGE_ORDER.index(job.kind)


def _stage_progress(jobs, kind):
    """(the stage's latest job, whether the current chain has yet to reach it): a job of an earlier stage newer than the
    stage's own latest - or one while it has none - means the chain has not got there. ``jobs``: the current revision's,
    oldest first."""
    position = STAGE_ORDER.index(kind)
    earlier = [job for job in jobs if job.kind in STAGE_ORDER[:position] and _stage_index(job) < position]
    own = [job for job in jobs if job.kind == kind]
    latest = own[-1] if own else None
    return latest, bool(earlier) and (latest is None or earlier[-1].created_at > latest.created_at)


def _progress(jobs, kind, configured):
    """'running', 'waiting' or 'stopped' while the current chain has not finished the stage; None once its outcome
    stands (or nothing will run it)."""
    latest, ahead = _stage_progress(jobs, kind)
    if latest is not None and latest.state in (models.Job.QUEUED, models.Job.RUNNING):
        return 'running' if latest.state == models.Job.RUNNING else 'waiting'
    active = any(job.state in (models.Job.QUEUED, models.Job.RUNNING) for job in jobs)
    stopped = bool(jobs) and jobs[-1].state == models.Job.CANCELLED
    if ahead and configured and active:
        return 'waiting'
    if (ahead and configured and stopped) or (stopped and latest is not None and latest.pk == jobs[-1].pk):
        return 'stopped'
    return None


def _run_detail(run):
    """The outcome of ``run`` in one plain sentence (the row's detail where no assessment has read it yet)."""
    if run.state == models.ProviderRun.SUCCEEDED:
        return f'Answered{REUSED_WORDS if run.reused_from_id else ""}; the checks have not read the answer yet.'
    if run.state == models.ProviderRun.FAILED:
        status = f' (HTTP {run.http_status})' if run.http_status else ''
        return f'The request failed{status}; an identical request is never sent again. {run.error}'.strip()
    if run.state == models.ProviderRun.UNKNOWN:
        return 'The outcome is unknown: no complete response was recorded.' + RECONCILE_FIRST
    if run.state == models.ProviderRun.NOT_SENT and (run.scope or {}).get('held') == 'unknown_outcome':
        return BLOCKED_DETAIL
    return run.error or 'Nothing was sent.'


def _record_detail(record, run):
    """A participant's Assessment.participants entry as the row's detail sentence."""
    words = review.record_words(record)
    state = record.get('state')
    if state == 'failed' and run is not None and run.http_status:
        words = words.replace('the request failed', f'the request failed (HTTP {run.http_status})', 1)
    detail = words[:1].upper() + words[1:] + '.'
    if state == 'read' and run is not None and run.reused_from_id:
        detail = f'Answered{REUSED_WORDS}; the reading was used.'
    if state == 'read' and record.get('unverified_quotes'):
        count = int(record['unverified_quotes'])
        detail += (f' {count} of its quotes {"was" if count == 1 else "were"} not found in the document, so '
                   f'{"it is" if count == 1 else "they are"} never used as evidence.')
    if state in ('unknown', 'blocked'):
        detail += RECONCILE_FIRST
    return detail


def _row(name, label, vendor, model, state, detail, run, codes=(), unverified=0):
    return {'name': name, 'label': label, 'vendor': vendor, 'model': model, 'state': state, 'detail': detail,
            'run_id': str(run.pk) if run is not None else None,
            'reused': bool(run is not None and run.reused_from_id), 'codes': list(codes),
            'unverified_quotes': unverified, 'usage': dict(run.usage or {}) if run is not None else {},
            'usage_basis': run.usage_basis if run is not None else '', 'estimated_cost_usd': review.estimated_cost(run),
            'returned_model': run.returned_model if run is not None else ''}


def _corti_row(encounter, assessment, jobs):
    from .jobs import _run_in_use  # local import: jobs imports this module's peers

    name, label, vendor, model = review.HARNESS_PARTICIPANTS[0]
    configured = settings.PROVIDER_MODE != 'disabled'
    progress = _progress(jobs, models.Job.PREDICT, configured)
    if progress is not None:
        detail = {'running': RUNNING_DETAIL, 'waiting': WAITING_DETAIL, 'stopped': STOPPED_DETAIL}[progress]
        return _row(name, label, vendor, model, progress, detail, None)
    current = assessment is not None and assessment.context_id == encounter.current_context_id
    revision = encounter.current_revision
    run = assessment.provider_run if current else (_run_in_use(revision) if revision is not None else None)
    latest, _ = _stage_progress(jobs, models.Job.PREDICT)
    if (latest is not None and 'blocked' in (latest.result or {})
            and (run is None or latest.created_at > run.created_at)):
        return _row(name, label, vendor, model, 'blocked', BLOCKED_DETAIL, None)
    if run is None:
        if not configured:
            return _row(name, label, vendor, model, 'not_configured', 'Not configured on this installation.', None)
        return _row(name, label, vendor, model, 'not_sent', 'No request was made for this revision.', None)
    codes = sorted({p.code for p in assessment.proposals.all() if p.bucket != models.Proposal.ALTERNATIVE
                    and (p.support or {}).get('origin', 'primary') in ('primary', 'second_review')}) if current else []
    if run.state == models.ProviderRun.SUCCEEDED and current and review._refused_run(assessment) == run:
        check = next((c for c in assessment.encounter_checks or [] if c.get('id') == 'provider.status'), {})
        return _row(name, label, vendor, model, 'refused',
                    f'Answered; the response was not used: {check.get("detail") or "it was refused whole"}', run)
    if run.state == models.ProviderRun.NOT_SENT and (run.scope or {}).get('held'):
        return _row(name, label, vendor, model, 'not_sent', run.error or 'Nothing was sent.', run)
    state = RUN_STATES.get(run.state, 'unknown')
    if run.state == models.ProviderRun.SUCCEEDED:
        detail = ('Answered; its codes were checked.' if current else _run_detail(run))
        if run.reused_from_id:
            detail = 'Reused the retained answer to the identical request; nothing was sent. ' + detail
        return _row(name, label, vendor, model, state, detail, run, codes)
    return _row(name, label, vendor, model, state, _run_detail(run), run)


def _participant_row(encounter, assessment, jobs, name, configured):
    from .jobs import _participant_run, _unreconciled_unknown  # local import: jobs imports this module's peers

    _, label, vendor, model = next(entry for entry in review.HARNESS_PARTICIPANTS if entry[0] == name)
    progress = _progress(jobs, HARNESS_STAGES[name][0], name in configured)
    if progress is not None:
        detail = {'running': RUNNING_DETAIL, 'waiting': WAITING_DETAIL, 'stopped': STOPPED_DETAIL}[progress]
        return _row(name, label, vendor, model, progress, detail, None)
    revision = encounter.current_revision
    records = {r.get('name'): r for r in (assessment.participants or []) if isinstance(r, dict)} if assessment else {}
    record = records.get(name)
    if name not in configured and (record is None or record.get('state') == 'not_configured'):
        # disabled here, and no assessment read it: a run recorded while it was configured will not be read again
        return _row(name, label, vendor, model, 'not_configured', 'Not configured on this installation.', None)
    newest = _participant_run(revision, name) if revision is not None else None
    if record is not None and record.get('run') == (str(newest.pk) if newest is not None else None):
        # the assessment read this participant's newest run (or recorded why it had none)
        run = newest
        detail = _record_detail(record, run)
        if record.get('state') == 'not_configured' and name in configured:
            detail = f'{label} was not configured when these checks ran.'
        return _row(name, label, vendor, model, RECORD_STATES.get(record.get('state'), 'unknown'), detail, run,
                    [item.get('code') for item in record.get('codes') or []], int(record.get('unverified_quotes') or 0))
    if newest is not None:
        held = newest.state == models.ProviderRun.NOT_SENT and (newest.scope or {}).get('held')
        return _row(name, label, vendor, model, 'blocked' if held else RUN_STATES.get(newest.state, 'unknown'),
                    _run_detail(newest), newest)
    if name not in configured:
        return _row(name, label, vendor, model, 'not_configured', 'Not configured on this installation.', None)
    if _unreconciled_unknown(encounter):
        return _row(name, label, vendor, model, 'blocked', BLOCKED_DETAIL, None)
    return _row(name, label, vendor, model, 'not_sent', 'No request was made for this revision.', None)


def _reference_sources(keys):
    """{key: (title, effective_start, effective_end)} of the installed sources (facts) and passage sources named."""
    found = {}
    for row in models.ReferenceSource.objects.filter(key__in=keys):
        found[row.key] = (row.title, row.effective_start.isoformat(), row.effective_end.isoformat())
    for row in models.PassageSource.objects.filter(key__in=keys):
        found.setdefault(row.key, (row.title, row.effective_start.isoformat(), row.effective_end.isoformat()))
    return found


def _reference_validation(assessment, active):
    """'waiting' while processing; 'done' when retrieval ran for the assessment and its traces cover every code a
    proposal can be decided on (selected or excluded); 'not_run' when there is no assessment, it predates the harness,
    or no retrieval ran for it - also when it has no code to retrieve for, never 'done' of nothing (no trace at all is
    what an absent passages module records too)."""
    out = {'state': 'not_run', 'codes_checked': 0, 'passages': 0, 'sources': [],
           'not_connected': list(review.NOT_CONNECTED)}
    if active:
        out['state'] = 'waiting'
    if assessment is None:
        return out
    retrieval = [entry for entry in assessment.retrieval or [] if isinstance(entry, dict)]
    traced = {entry.get('code') for entry in retrieval}
    decidable = {p.code for p in assessment.proposals.all() if p.bucket != models.Proposal.ALTERNATIVE}
    if not active and assessment.participants and traced and decidable <= traced:
        out['state'] = 'done'
    sources = {}
    for entry in retrieval:
        for item in review.retrieved(entry, 'facts') + review.retrieved(entry, 'passages'):
            key = str(item.get('source_key') or '')
            if key:
                sources.setdefault(key, str(item.get('release') or ''))
    known = _reference_sources(sorted(sources))
    out.update(codes_checked=len(traced), passages=sum(len(review.retrieved(entry, 'passages')) for entry in retrieval),
               sources=[{'key': key, 'title': known.get(key, ('', '', ''))[0], 'release': release,
                         'effective_start': known.get(key, ('', '', ''))[1],
                         'effective_end': known.get(key, ('', '', ''))[2]} for key, release in sorted(sources.items())])
    return out


NO_REFERENCES = {'retrieved': [], 'used': []}
PEER_WAITING = {'waiting': WAITING_DETAIL, 'running': RUNNING_DETAIL, 'stopped': STOPPED_DETAIL}


def _peer_progress(jobs, name):
    """'waiting', 'running' or 'stopped' while the current chain has not finished ``name``'s peer stage (HARNESS.md
    12.1: astra_peer, then fable_peer, in STAGE_ORDER); None once its outcome stands or nothing will run it."""
    kind = HARNESS_STAGES[name][1]
    own = [job for job in jobs if job.kind == kind]
    if own and own[-1].state in (models.Job.QUEUED, models.Job.RUNNING):
        return 'running' if own[-1].state == models.Job.RUNNING else 'waiting'
    if own and own[-1].state == models.Job.CANCELLED and jobs and jobs[-1].pk == own[-1].pk:
        return 'stopped'
    # an earlier participant's peer stage (or this one's) is under way, and this participant's comes after it
    upto = PEER_STAGES[:PEER_STAGES.index(kind) + 1]
    ahead = [job for job in jobs if job.kind in upto and job.state in (models.Job.QUEUED, models.Job.RUNNING)]
    if ahead and (not own or own[-1].created_at < ahead[0].created_at):
        return 'waiting'
    return None


def _codes_added(peer_review):
    """The CPT codes a peer review proposed after peer review (its additional codes), each once, in order."""
    if peer_review is None or peer_review.refused:
        return []
    codes = [item.code for item in peer_review.additional_codes
             if isinstance(item.code, str) and CODE_SHAPE.fullmatch(item.code)]
    return list(dict.fromkeys(codes))


def _peer_detail(record):
    """A participant's peer review (its assess #2 entry) in one plain sentence."""
    state = record.get('peer_state')
    if state == 'read':
        detail = 'Answered in peer review, after its first reading was frozen; the review was used.'
        count = int(record.get('peer_unverified_quotes') or 0)
        if count:
            detail += (f' {count} of its quotes {"was" if count == 1 else "were"} not found in the document, so '
                       f'{"it is" if count == 1 else "they are"} never used as evidence.')
        return detail
    words = review.record_words({'state': state, 'reason': record.get('peer_reason')})
    words = words.replace('the reading was not used', 'the review was not used', 1)
    return 'Peer review: ' + words + '.' + (RECONCILE_FIRST if state in ('unknown', 'blocked') else '')


def _harness2(row, assessment, jobs):
    """The harness@2 fields of one participant row (HARNESS.md 12.6): ``peer`` - its peer review's state, sentence,
    run, the codes it added and its unverified quotes ({} before phase 2, for Corti, or for a participant not
    configured) - and the references its phase-1 run (``references``) and its peer-review run (``peer_references``)
    retrieved and used, never merged with each other or with the reconciliation's (reference_validation)."""
    out = {'peer': {}, 'references': dict(NO_REFERENCES), 'peer_references': dict(NO_REFERENCES)}
    name = row['name']
    if name not in participants.PARTICIPANTS:
        return out
    run = models.ProviderRun.objects.filter(pk=row['run_id']).first() if row['run_id'] else None
    if run is not None and run.purpose == models.ProviderRun.INDEPENDENT:
        out['references'] = review.participant_references(run)
    progress = _peer_progress(jobs, name)
    record = review.model_records(assessment).get(name) if assessment is not None else None
    if progress is not None:
        out['peer'] = {'state': progress, 'detail': PEER_WAITING[progress], 'run_id': None, 'codes_added': [],
                       'unverified_quotes': 0}
    elif record is not None and 'peer_state' in record:
        peer_run = review.record_run(assessment, record, 'peer_run')
        peer_review = None
        if peer_run is not None and record.get('peer_state') == 'read':
            peer_review = review.recorded_peer_review(assessment, record)  # the review assess #2 read, or None
        out['peer'] = {'state': RECORD_STATES.get(record.get('peer_state'), 'unknown'), 'detail': _peer_detail(record),
                       'run_id': str(peer_run.pk) if peer_run is not None else None,
                       'codes_added': _codes_added(peer_review),
                       'unverified_quotes': int(record.get('peer_unverified_quotes') or 0)}
        if peer_run is not None:
            out['peer_references'] = review.participant_references(peer_run, peer_review)
    return out


def harness_json(encounter, jobs):
    """The harness block of the encounter view (HARNESS.md 7): Corti, Astra and Fable, always in that order, each saying
    plainly whether it ran, is waiting, is not configured, failed, has an unknown outcome or was refused; then reference
    validation, clarification and the final status. ``jobs``: the current revision's, oldest first. harness@2 (12.6)
    adds each row's peer review and its references, and ``phase``: 0 with no model participant, 1 before the peer
    reviews are assessed, 2 after (read from the current assessment's record, 12.3)."""
    assessment = review.live_assessment(encounter)
    configured = participants.configured()
    active = any(job.state in (models.Job.QUEUED, models.Job.RUNNING) for job in jobs)
    rows = ([_corti_row(encounter, assessment, jobs)]
            + [_participant_row(encounter, assessment, jobs, name, configured) for name in participants.PARTICIPANTS])
    return {
        'participants': [{**row, **_harness2(row, assessment, jobs)} for row in rows],
        'phase': review.assessment_phase(assessment) if assessment is not None else (1 if configured else 0),
        'reference_validation': _reference_validation(assessment, active),
        'clarification': {'open': assessment.clarifications.filter(state=models.Clarification.OPEN).count()
                          if assessment is not None else 0},
        'final': {'state': encounter.state, 'label': review.encounter_state_label(encounter)},
    }


def encounter_detail(encounter, membership):
    from .jobs import busy, second_review_status  # local import: jobs imports this module's peers

    assessment, clarifications = _assessment_json(encounter, membership)
    revision = encounter.current_revision
    jobs = list(encounter.jobs.filter(revision=revision).order_by('created_at')) if revision else []
    state_run = review.state_run(encounter)
    # harness@2 (HARNESS.md 12.5): the candidates of each open question of the final assessment, and each question's
    # confirmation; every confirmation of the current revision is listed too, after its question has gone
    offered = review.assessment_candidates(review.live_assessment(encounter))
    confirmed = {c.clarification_id: c for c in reversed(models.FindingConfirmation.objects.filter(
        clarification__in=clarifications).select_related('confirmed_by', 'revision').order_by('created_at', 'pk'))}
    return {
        **encounter_summary(encounter),
        'created_by': encounter.created_by.label(),
        'permissions': {'can_review': membership.can_review, 'is_owner': is_owner(membership),
                        'can_confirm': membership.can_review},
        'harness': harness_json(encounter, jobs),
        'revision': _revision_json(revision),
        'context': {'facts': _context_facts(encounter.current_context),
                    'user_values': encounter.user_values or {}},
        'routing': _routing_json(encounter),
        'pipeline': {'busy': busy(encounter), 'can_stop': busy(encounter) and membership.can_review,
                     'can_resume': review.can_resume(encounter) and membership.can_review,
                     # A member's Stop, as opposed to a stage the system cancelled (expired, or left by a dead worker).
                     'stopped_by_member': encounter.stopped_at is not None,
                     'stages': [{'kind': j.kind, 'state': j.state, 'error': j.error,
                                 'finished_at': _iso(j.finished_at)} for j in jobs]},
        'provider_runs': [_provider_run_json(r) for r in encounter.provider_runs.order_by('created_at')],
        # The run the provider_failed state reads, named so the page never picks one by recency (ec5 skeptic).
        'state_run': str(state_run.pk) if state_run is not None else None,
        'second_review': {**second_review_status(encounter),
                          'can_request': membership.can_review},
        'assessment': assessment,
        'clarifications': [_question_json(c, offered.get(str(c.pk), ()), confirmed.get(c.pk))
                           for c in clarifications],
        'confirmations': [confirmation_json(c) for c in review.revision_confirmations(revision)],
        'decisions': {'history': [_decision_json(d) for d in encounter.decisions.select_related(
            'proposal', 'reviewer', 'revision').order_by('sequence')]},
        'readiness': review.readiness(encounter),
        'coding': review.coding_completeness(encounter),
        'reports': [_report_json(r) for r in encounter.reports.order_by('-generated_at')],
        'activity': [_activity_json(e) for e in encounter.audit_events.select_related('actor').order_by('created_at')],
    }


# --- the administrative trace (HARNESS.md 7; owner only, api.trace) ---------------------------------------------------

def _trace_reading(run):
    """A participant's first-reading run's full normalized reading - the quotes CPT Studio could not locate included,
    and each reference it says it used with CPT Studio's check against that run's own tool results - read as the
    adapter version that recorded it; None for Corti's runs, a peer-review run (its ``review``) and a run with no
    answer."""
    if (run.provider not in participants.PARTICIPANTS or run.purpose != models.ProviderRun.INDEPENDENT
            or run.state != models.ProviderRun.SUCCEEDED):
        return None
    reading, problem = review.stored_reading(run)
    if reading is None:
        return {'refused': True, 'problems': [problem], 'unverified_quotes': 0, 'date_of_service': {},
                'services': [], 'codes': [], 'not_coded': [], 'questions': [], 'extraction_issues': [],
                'references_used': []}
    data = to_jsonable(reading)
    return {'refused': data['refused'], 'problems': data['problems'], 'unverified_quotes': data['unverified_quotes'],
            'date_of_service': {'value': data['date_of_service'], 'evidence': data['date_evidence']},
            'services': data['services'], 'codes': data['codes'], 'not_coded': data['not_coded'],
            'questions': data['questions'], 'extraction_issues': data['extraction_issues'],
            'references_used': data['references_used']}


def _trace_review(run):
    """A peer-review run's PeerReview (HARNESS.md 11.1) as JSON - its answers, positions, additional codes, references
    used (each checked against that run's own tool results), the frozen inputs it was shown, its problems - read as the
    adapter version that recorded it; None for any other run and a run with no answer."""
    if (run.provider not in participants.PARTICIPANTS or run.purpose != models.ProviderRun.PEER_REVIEW
            or run.state != models.ProviderRun.SUCCEEDED):
        return None
    peer_review, problem = review.stored_peer_review(run)
    if peer_review is None:
        return {'refused': True, 'problems': [problem], 'unverified_quotes': 0, 'frozen_inputs': [], 'answers': [],
                'positions': [], 'additional_codes': [], 'references_used': []}
    return to_jsonable(peer_review)


def _trace_exchanges(run):
    """Each HTTP exchange of a participant run's tool loop (models.ProviderExchange, HARNESS.md 11.2) with the tool
    calls CPT Studio executed for it; the results themselves are named by their sha256."""
    return [{'turn': exchange.turn, 'state': exchange.state, 'http_status': exchange.http_status,
             'latency_ms': exchange.latency_ms, 'usage': exchange.usage or {},
             'request_sha256': exchange.request_sha256, 'response_sha256': exchange.response_sha256,
             'provider_request_id': exchange.provider_request_id, 'response_id': exchange.response_id,
             'error': exchange.error,
             'tool_calls': [{'call_id': call.call_id, 'tool': call.tool, 'arguments': call.arguments,
                             'refs': list(call.refs or []), 'result_sha256': call.result_sha256,
                             'executed_at': _iso(call.executed_at)} for call in exchange.tool_calls.order_by('id')]}
            for exchange in run.exchanges.order_by('turn')]


def _trace_run(run):
    """One run as HARNESS.md 6 records it: what was called and what answered, its identities (the run identity is the
    client request id a participant's vendor was given), usage and cost, the hashes, and who asked for it."""
    return {'id': str(run.pk), 'state': run.state, 'sent': run.sent, 'mode': review.run_mode(run),
            'purpose': run.purpose, 'run_identity': str(run.run_identity), 'authorization_ref': run.authorization_ref,
            'requested_by': run.requested_by.label() if run.requested_by_id else None,
            'adapter_version': run.adapter_version, 'endpoint': run.endpoint, 'requested_model': run.requested_model,
            'returned_model': run.returned_model, 'request_id': run.provider_request_id, 'response_id': run.response_id,
            'http_status': run.http_status, 'latency_ms': run.latency_ms, 'usage': run.usage or {},
            'usage_basis': run.usage_basis, 'estimated_cost_usd': review.estimated_cost(run),
            'request_sha256': run.request_sha256, 'response_sha256': run.response_sha256,
            'response_bytes': len(bytes(run.response_bytes or b'')), 'created_at': _iso(run.created_at),
            'finished_at': _iso(run.finished_at), 'error': run.error,
            'reused_from': str(run.reused_from_id) if run.reused_from_id else None,
            'reconciled': run.reconciled_at is not None, 'reading': _trace_reading(run),
            'review': _trace_review(run), 'exchanges': _trace_exchanges(run)}


def trace_json(encounter):
    """The owner-only trace of the current revision (HARNESS.md 7): each participant's runs - request identity,
    endpoint, models, usage, cost, raw-response hash, its exchanges and tool calls, and its full normalized reading or
    peer review - then each assessment of the revision with its phase and the frozen phase-1 outputs it recorded
    (12.3), the retrieval traces and the reconciliation table, which keeps proposed, reference-checked and approved
    apart (I4)."""
    revision = encounter.current_revision
    runs = (list(encounter.provider_runs.filter(revision=revision).select_related('requested_by')
                 .order_by('created_at', 'pk')) if revision else [])
    assessment = review.live_assessment(encounter)
    current = review.current_decisions(assessment) if assessment is not None else {}
    rows = []
    for proposal in assessment.proposals.all() if assessment is not None else ():
        decision = current.get(proposal.pk)
        rows.append({'code': proposal.code, 'family': proposal.family, 'bucket': proposal.bucket,
                     'status': proposal.status, 'proposed_by': review.proposed_by(proposal),
                     'positions': review.participant_positions(proposal, assessment.participants),
                     'reference_check': review.reference_check(proposal),
                     'approved': decision is not None and decision.action == models.Decision.APPROVE})
    return {
        'encounter': {'id': str(encounter.pk), 'title': encounter.title},
        'revision': {'id': str(revision.pk), 'number': revision.number, 'text_sha256': revision.text_sha256}
        if revision is not None else None,
        'participants': [{'name': name, 'label': label, 'vendor': vendor, 'model': model,
                          'runs': [_trace_run(run) for run in runs if review.participant_of(run) == name]}
                         for name, label, vendor, model in review.HARNESS_PARTICIPANTS],
        'assessments': [_trace_assessment(item, encounter) for item in (
            encounter.assessments.filter(revision=revision).order_by('created_at', 'pk') if revision else ())],
        'retrieval': assessment.retrieval if assessment is not None else [],
        'reconciliation': rows,
    }


def _trace_assessment(assessment, encounter):
    """One assessment of the revision: whether it is the current one, its phase, whether it is its chain's final
    assessment, and the frozen phase-1 outputs it recorded ([[input name, sha256], ...]; identical in every entry)."""
    frozen = next((record['frozen'] for record in review.model_records(assessment).values()
                   if isinstance(record.get('frozen'), list)), [])
    return {'id': str(assessment.pk), 'created_at': _iso(assessment.created_at),
            'current': assessment.pk == encounter.current_assessment_id, 'phase': review.assessment_phase(assessment),
            'final': review.is_final(assessment), 'frozen': frozen}
