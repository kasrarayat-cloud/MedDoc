"""Persisted rows -> the JSON shapes in API.md. Read-only; no business rules.

This is the OPERATOR serializer (CORE-UX-DESIGN.md 5): complete provenance - participants, models, usage, runs,
hashes, rule ids, the trace - served only to platform operators under /ops/ (studio.operator). A workspace member
is served studio.customer_api's allowlist, never these payloads."""
from dataclasses import dataclass

from django.conf import settings

from . import models, participants, review
from .gi.context import charge_date_problem, is_member_conflict
from .gi.profiles import PROFILES, profile
from .participants import peer as participant_peer
from .participants import reading as participant_reading
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
      'question'        a question the review overlay leaves open on the assessment of the current revision
                        (review.open_questions_of: never one a member's answer closed);
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
        # completion repair (2026-11-06, U11): the questions the review overlay leaves open - the stored ones as the
        # decisions and the members' answers leave them, and the ones the overlay adds (review.open_questions_of) - so
        # the queue never says "question" of a question a member answered, nor misses one a decision raised
        if review.open_questions_of(assessment):
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
        # the modifier the reviewer chose on an approval (Decision.modifiers: [] or one of 59 and XS), the record the
        # download check and the walk compare a chosen modifier against (refutation round 2, L3-3)
        'modifiers': list(decision.modifiers or []),
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


@dataclass(frozen=True)
class ReviewingMember:
    """A member of the encounter's workspace whose role may review (an owner or a reviewer), as review.allowed_actions
    reads a membership: customer_codes asks what such a member may record on each code now, by the rule the customer
    page offers actions by. It is read by allowed_actions only - never stored, never given to record_decision (which
    also requires the member's own user) - so it authorises nothing."""
    workspace_id: object
    can_review: bool = True


def customer_codes(encounter, assessment, current):
    """{proposal id: what the customer page shows for that code}, the operator view's statement of the customer page
    (refutation round 3, B-02 and B-03): customer_api.code_rows over the review overlay - the very rows GET
    /api/encounters/<id> serves - each as its number, status, status label, sub label and ``reviewer_actions``, the
    actions a member who may review is allowed (review.allowed_actions for a ReviewingMember; a member who may not
    review is allowed none). The walk (ops/verify_browser.cjs) and the download check (ops/verify_downloads.py) judge the
    customer page and the exports against it, never against a re-derivation of the overlay's rules, which read a
    reinstated code whose needed detail a member answered unavailable as ready with approve accepted, and one still
    waiting on its detail as revoke only. {} while ``assessment`` is not the live one: the page then lists no code. A
    statement that cannot be made is logged and left out ({}), so the tools cannot verify the page rather than pass it,
    and the operator's diagnostics never fail on it."""
    from . import customer_api  # local import: customer_api imports this module

    live = review.live_assessment(encounter)
    if assessment is None or live is None or live.pk != assessment.pk:
        return {}
    try:
        rows, _ = customer_api.code_rows(assessment, current, customer_api.views_of(assessment, current),
                                         ReviewingMember(workspace_id=encounter.workspace_id))
    except Exception:  # noqa: BLE001 - logged; the statement serves the tools, and never fails the operator's page
        import logging

        logging.getLogger(__name__).exception('the customer page of encounter %s could not be stated', encounter.pk)
        return {}
    return {row['id']: {'number': row['number'], 'status': row['status'], 'status_label': row['status_label'],
                        'sub_label': row['sub_label'], 'reviewer_actions': list(row['allowed_actions'])}
            for row in rows}


def _proposal_json(proposal, current, assessment, membership, clarification_ids, customer=None):
    family = profile(proposal.family) if proposal.family in PROFILES else None
    decision = current.get(proposal.pk)
    # the review overlay (CORE-UX-DESIGN.md 4): status, checks and actions as the current decisions leave them; with no
    # decision and no member answer, exactly the stored proposal
    views = review.effective_view(assessment, current)
    view = views.get(proposal.key)
    status = view.status if view is not None else proposal.status
    return {
        'id': str(proposal.pk), 'key': proposal.key, 'bucket': proposal.bucket, 'code': proposal.code,
        'code_kind': proposal.code_kind, 'family': proposal.family,
        'family_label': family.label if family else proposal.family,
        'eyebrow': family.eyebrow if family else 'CPT', 'supported': family.supported if family else False,
        'profile_version': proposal.profile_version, 'status': status,
        'status_label': review.status_label(status), 'exclusion_reason': proposal.exclusion_reason,
        'reinstatable': proposal.reinstatable,
        'descriptor': {'status': 'withheld',
                       'label': 'Description withheld — no licensed CPT descriptor is connected.'},
        'evidence': proposal.evidence, 'rationale': proposal.rationale, 'units': proposal.units,
        'checks': list(view.checks) if view is not None else proposal.checks,
        'modifier_considerations': proposal.modifier_considerations,
        'support': proposal.support or {},
        'clarification_ids': clarification_ids.get(proposal.pk, []),
        'decision': _decision_json(decision) if decision else None,
        'decision_state': DECISION_STATES.get(decision.action, 'undecided') if decision else 'undecided',
        'reinstated_by': _reinstated_by(proposal, decision),
        'allowed_actions': review.allowed_actions(proposal, assessment, membership, views),
        'approve_withheld_by': review.approve_withheld_by(proposal, assessment, current, views),
        # the overlay's reason beside its status: 'detail_unavailable' while a member's answer that a needed detail is
        # not documented (or cannot be confirmed) excludes the code, else ''
        'overlay_reason': view.reason if view is not None else '',
        # what the customer page shows for this code (customer_codes), None where the page does not list it
        'customer': (customer or {}).get(str(proposal.pk)),
        # Who proposed it, what the CMS reference checks found, and (above) a member's decision: three statuses, never
        # one (I4). Participants' positions are shown beside it and decide nothing (I2, I3).
        'proposed_by': review.proposed_by(proposal),
        # the participants that only listed a participant's alternative's code, with no quote found verbatim: never
        # among proposed_by (refutation round 5, the session's D12)
        'listed_by': review.listed_by(proposal),
        # how Corti stands to the code where it is not among the proposers (HARNESS.md 11.4; refutation round 2,
        # truth-6): the page says "Corti did not propose this code" only when Corti has no entry for it at all
        'corti_relation': review.corti_relation(proposal),
        'participant_positions': review.participant_positions(proposal, assessment.participants),
        'reference_check': review.reference_check(proposal),
        # only a proposal a reviewer can decide is traced (review.decidable): no other card is served another's trace
        # of the same code (refutation round 8, retrieval-3: a participant's copy of Corti's code excluded for evidence
        # carried that code's 12 facts and passages beside its own "No CMS reference check ran for this code.")
        'retrieval': (review.proposal_retrieval(proposal, assessment.retrieval) if review.decidable(proposal)
                      else []),
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
    customer = customer_codes(encounter, assessment, current)
    proposals = [_proposal_json(p, current, assessment, membership, by_proposal, customer)
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
    # a harness participant's replayed run reads 'replay' too: its run records the mode it ran in (review.run_mode); and
    # the model it asked for and the one that answered, which the Activity tab names (refutation r1 FG-5: never served)
    return {'id': str(run.pk), 'provider': run.provider, 'mode': review.run_mode(run),
            'state': run.state, 'http_status': run.http_status, 'latency_ms': run.latency_ms, 'usage': run.usage,
            'usage_basis': run.usage_basis, 'request_sha256': run.request_sha256,
            'response_sha256': run.response_sha256,
            'reused_from': str(run.reused_from_id) if run.reused_from_id else None, 'error': run.error,
            'reconciled': run.reconciled_at is not None, 'created_at': _iso(run.created_at),
            'purpose': run.purpose, 'scope_items': list((run.scope or {}).get('items', [])),
            'requested_model': run.requested_model, 'returned_model': run.returned_model}


def _confirmation_assessment(confirmation):
    """The assessment a confirmation's effect is stated for: its encounter's current assessment - the one the page
    shows - when that assessment is of the confirmation's revision; None otherwise."""
    encounter = confirmation.encounter
    assessment = encounter.current_assessment if encounter.current_assessment_id else None
    return assessment if assessment is not None and assessment.revision_id == confirmation.revision_id else None


def confirmation_json(confirmation):
    """A FindingConfirmation (HARNESS.md 11.3, 12.6): the fact a reviewer confirmed from a participant's located
    passage, with that passage, who located it, who confirmed it and the attestation recorded - a confirmed fact,
    never a decision on a code - and ``current_effect``, what the current assessment made of it, in the words the
    reports' CONFIRMED FINDINGS use (review.confirmation_effect: read, or not read with why; refutation round 2,
    truth-5: the page said every confirmation of a fact other than the date was read)."""
    reviewer = confirmation.confirmed_by
    return {'id': str(confirmation.pk), 'clarification_id': str(confirmation.clarification_id),
            'scope': confirmation.scope, 'fact': confirmation.fact, 'family': confirmation.family,
            'proposal_key': confirmation.proposal_key, 'value': confirmation.value,
            'spans': list(confirmation.spans or []), 'located_by': list(confirmation.located_by or []),
            'runs': list(confirmation.runs or []), 'confirmed_by': reviewer.label(),
            'confirmed_by_kind': reviewer.actor_kind, 'attestation': confirmation.attestation,
            'created_at': _iso(confirmation.created_at), 'revision_number': confirmation.revision.number,
            'current_effect': review.confirmation_effect(confirmation, _confirmation_assessment(confirmation))}


def _report_json(report):
    return {'id': str(report.pk), 'kind': report.kind, 'fmt': report.fmt, 'filename': report.filename,
            'sha256': report.sha256, 'generated_at': _iso(report.generated_at),
            'generated_by': report.generated_by.label(), 'download_url': f'/ops/api/reports/{report.pk}/download'}


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
OPERATOR_VIEWED = 'operator.viewed'  # studio.operator.VIEWED (that module imports this one's peers)
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


def _row(name, label, vendor, model, state, detail, run, codes=(), unverified=0, unlisted=0):
    # ``unlisted``: how many codes the reading proposed - Corti's answers selected (corti_unlisted) - that the engine
    # cannot list, never served (I9): the page says which codes can be listed, never that a participant proposed none
    # (refutation round 2, truth-11; Corti's row, refutation round 3, truth-3)
    return {'name': name, 'label': label, 'vendor': vendor, 'model': model, 'state': state, 'detail': detail,
            'run_id': str(run.pk) if run is not None else None,
            'reused': bool(run is not None and run.reused_from_id), 'codes': list(codes), 'unlisted_codes': unlisted,
            'unverified_quotes': unverified, 'usage': dict(review.chain_usage(run)[0]) if run is not None else {},
            'usage_basis': run.usage_basis if run is not None else '',
            'estimated_cost_usd': review.chain_usage(run)[1] if run is not None else review.estimated_cost(run),
            'returned_model': run.returned_model if run is not None else ''}


def corti_codes(assessment) -> list:
    """The codes Corti proposed on ``assessment``, each once, sorted: the codes its answers selected that are a
    proposal - selected or excluded, of origin primary or second_review - never a code it only listed (an
    alternative)."""
    return sorted({p.code for p in assessment.proposals.all() if p.bucket != models.Proposal.ALTERNATIVE
                   and (p.support or {}).get('origin', 'primary') in ('primary', 'second_review')})


SECOND_REVIEW_CHECK = 'provider.second_review'  # the engine's check of the bounded second review it read


def corti_unlisted_counts(assessment) -> tuple[int, int]:
    """(primary, second): how many codes Corti's answers that ``assessment`` read returned that the engine cannot list
    (engine._listable: empty, or longer than MAX_LISTED_CODE) - every code of an answer, whatever its role (selected,
    a candidate, an alternative), as the engine counts them: its primary answer as its provider.unlisted check does,
    and a bounded second review as its provider.second_review check does, only where the engine read that second
    review (the assessment records that check: it reads none where its documented-service reading is inconsistent).
    The engine drops each such code, and none is ever served or truncated (I9). Counted from each stored answer as the
    engine read it (jobs._provider_inputs: its bytes checked against their sha256, read by the run's own normalizer;
    an answer refused whole has none), so Corti's row and the reports say the engine's own numbers: they counted only
    the codes Corti selected, "It returned 1 code that cannot be listed" beside the engine's "The provider returned 2
    codes" for a candidate it returned too (refutation round 4, truth-4), and never say that it proposed no code, or
    that its codes were checked, beside codes that cannot be listed (refutation round 3, truth-3). An answer that
    cannot be read again counts none, and the error is logged: the page never fails on it."""
    from .jobs import _provider_inputs  # local import: jobs imports this module's peers
    from .validation import engine  # local import: only the engine's rule is needed here

    read_second = any(isinstance(check, dict) and check.get('id') == SECOND_REVIEW_CHECK
                      for check in assessment.encounter_checks or [])
    counts = []
    for run, read in ((assessment.provider_run, True), (assessment.second_run, read_second)):
        count = 0
        if read and run is not None and run.state == models.ProviderRun.SUCCEEDED:
            try:
                _, normalized = _provider_inputs(run)
            except Exception:  # noqa: BLE001 - logged; the count is informational and never fails the page or a report
                import logging

                logging.getLogger(__name__).exception('the answer of run %s could not be read again', run.pk)
                normalized = None
            if normalized is not None and not normalized.refused:
                count = sum(1 for item in normalized.codes if not engine._listable(item.code))
        counts.append(count)
    return counts[0], counts[1]


def corti_unlisted(assessment) -> int:
    """How many codes Corti's answers that ``assessment`` read returned that the engine cannot list, its primary answer
    and any bounded second review together (corti_unlisted_counts): Corti's row's ``unlisted_codes``."""
    return sum(corti_unlisted_counts(assessment))


def corti_unlisted_words(primary, second) -> str:
    """The engine's own sentences for the codes Corti's answers returned that cannot be listed ('' for none), each
    answer's count apart, as the engine says them: the primary answer's as provider.unlisted does ("It returned 2 codes
    that cannot be listed: ..."), then the bounded second review's as provider.second_review does ("Its second review
    returned 1 code that cannot be listed: ..."), so the row and the reports say each number the Checks tab says."""
    from .validation import checks, engine  # local import: only the engine's wording is needed here

    words = [checks.unlisted_codes(primary, engine.MAX_LISTED_CODE, 'It')] if primary else []
    if second:
        words.append(checks.unlisted_codes(second, engine.MAX_LISTED_CODE, 'Its second review'))
    return ' '.join(words)


def corti_listed_apart(assessment) -> bool:
    """Whether Corti listed a code that can be listed without its being one of its proposals (corti_codes): an
    alternative of origin primary or second_review - a candidate, an alternative, or a code its bounded second review
    selected and did not add."""
    return any(p.bucket == models.Proposal.ALTERNATIVE and (p.support or {}).get('origin', 'primary')
               in ('primary', 'second_review') for p in assessment.proposals.all())


# Corti's answered state, as its row's detail and the reports' REVIEW PARTICIPANTS say it: its codes were checked, or,
# where its answers returned codes that cannot be listed (corti_unlisted), those that can be listed were, or it proposed
# none that can be listed (beside a code it listed apart), or none of its codes can be listed; in the last two, none
# was checked.
CORTI_CHECKED = 'answered; its codes were checked'
CORTI_SOME_LISTED = 'answered; its codes that can be listed were checked'
CORTI_NONE_PROPOSED = 'answered; it proposed no code that can be listed, so none was checked'
CORTI_NONE_LISTED = 'answered; none of its codes can be listed, so none was checked'


def corti_answered(listed, unlisted, apart=False) -> str:
    """Corti's answered state in one clause: ``listed``, whether it proposed a code that can be listed (corti_codes);
    ``unlisted``, how many codes it returned that cannot be (corti_unlisted); ``apart``, whether it listed a code that
    can be listed apart from its proposals (corti_listed_apart), where "none of its codes can be listed" would be false
    of the code its Alternatives list shows (refutation round 4, truth-4)."""
    if not unlisted:
        return CORTI_CHECKED
    if listed:
        return CORTI_SOME_LISTED
    return CORTI_NONE_PROPOSED if apart else CORTI_NONE_LISTED


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
    codes = corti_codes(assessment) if current else []
    if run.state == models.ProviderRun.SUCCEEDED and current and review._refused_run(assessment) == run:
        check = next((c for c in assessment.encounter_checks or [] if c.get('id') == 'provider.status'), {})
        return _row(name, label, vendor, model, 'refused',
                    f'Answered; the response was not used: {check.get("detail") or "it was refused whole"}', run)
    if run.state == models.ProviderRun.NOT_SENT and (run.scope or {}).get('held'):
        return _row(name, label, vendor, model, 'not_sent', run.error or 'Nothing was sent.', run)
    state = RUN_STATES.get(run.state, 'unknown')
    if run.state == models.ProviderRun.SUCCEEDED:
        # the codes its answers returned that the engine cannot list are counted, each answer's as the engine counts
        # it, never served (I9; refutation round 3, truth-3; round 4, truth-4)
        primary, second = corti_unlisted_counts(assessment) if current else (0, 0)
        unlisted = primary + second
        if current:
            apart = bool(unlisted) and not codes and corti_listed_apart(assessment)
            words = corti_answered(bool(codes), unlisted, apart)
            detail = f'{words[:1].upper()}{words[1:]}.' + (f' {corti_unlisted_words(primary, second)}' if unlisted
                                                           else '')
        else:
            detail = _run_detail(run)
        if run.reused_from_id:
            detail = 'Reused the retained answer to the identical request; nothing was sent. ' + detail
        return _row(name, label, vendor, model, state, detail, run, codes, unlisted=unlisted)
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
        # only the codes the engine lists; one it cannot list is counted, never served (I9; refutation r1 IND-1), in
        # the engine's own sentence for a participant's codes (refutation round 4, shapes-1) and with the engine's own
        # number, re-read from the frozen reading (refutation round 5, D13): None, and no sentence, where that reading
        # cannot be read again as recorded
        codes, unlisted = review.listed_codes(record), review.unlisted_count(assessment, record)
        if unlisted:
            from .validation import engine  # local import: only the engine's wording is needed here

            detail = f'{detail} {engine.participant_unlisted_codes(unlisted)}'
        return _row(name, label, vendor, model, RECORD_STATES.get(record.get('state'), 'unknown'), detail, run,
                    codes, int(record.get('unverified_quotes') or 0), unlisted)
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


# A failed entry's note where it carries none (refutation round 2, truth-4). It is said of any assessment, so it claims
# neither that the codes' checks read the CMS facts (jobs.RETRIEVAL_FAILED, true only where a CMS reference file
# applied) nor that none was checked (jobs.RETRIEVAL_FAILED_UNCHECKED): each code's checks stand as they are shown
# (refutation round 3, truth-1).
REFERENCE_FAILED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed, so no CMS "
                    "reference fact or passage is listed here; each code's CMS reference checks stand as shown for "
                    "that code.")


def retrieval_failed(entry) -> bool:
    """Whether an Assessment.retrieval entry is the record of a retrieval that failed (jobs.retrieval_failure): no
    code, no fact, no passage, marked 'failed' - never a trace of a code checked (refutation round 1, parity-1)."""
    return isinstance(entry, dict) and entry.get('failed') is True


def failure_note(entry) -> str:
    """A failed retrieval entry's note - CPT Studio's own sentence saying reference validation failed - or, where the
    entry carries none, CPT Studio's sentence for it."""
    notes = entry.get('notes') if isinstance(entry.get('notes'), list) else []
    return next((item.strip() for item in notes if isinstance(item, str) and item.strip()), REFERENCE_FAILED)


# What reference validation says when no installed CMS reference file applied to the assessment's service date, so no
# code was looked up in one (refutation round 2, truth-3: it said "Done - 2 codes checked against the CMS reference
# files" while every card's CMS checks were not verified).
NO_SOURCE_NO_DATE = ('No code was checked against the CMS reference files: no service date is established for this '
                     'encounter, so no dated CMS reference file applies.')
NO_SOURCE_FOR_DATE = ('No code was checked against the CMS reference files: no installed CMS reference file applies '
                      'to the service date, {date}.')


def source_applied(reference_sources) -> bool:
    """Whether an installed CMS reference file applied to the service date, so the codes were looked up in one: the
    engine's own record of the lookup the checks read and the retrieval traced (AssessmentResult.reference_sources, kept
    as Assessment.reference_sources: 'applies' is true only for the one source of its kind used for the date). The
    assess stage reads it to word a retrieval that failed (jobs.retrieval_failure), and reference validation here."""
    return any(isinstance(source, dict) and source.get('applies') is True for source in reference_sources or [])


def _source_applied(assessment) -> bool:
    """Whether an installed CMS reference file applied to the assessment's service date (source_applied)."""
    return source_applied(assessment.reference_sources)


def no_source_sentence(service_date) -> str:
    """Why no code was checked against the CMS reference files: no service date was established (None or ''), or no
    installed CMS reference file applies to ``service_date`` (an ISO date) - one sentence for reference validation and
    for a retrieval that failed (jobs.RETRIEVAL_FAILED_UNCHECKED)."""
    return NO_SOURCE_FOR_DATE.format(date=service_date) if service_date else NO_SOURCE_NO_DATE


def _no_source(retrieval) -> str:
    """Why no code was checked: no service date was established (the traces record none), or none applies to it."""
    dates = sorted({entry.get('service_date') for entry in retrieval if isinstance(entry.get('service_date'), str)
                    and entry.get('service_date')})
    return no_source_sentence(dates[0] if dates else None)


def _reference_validation(assessment, active):
    """'waiting' while processing; 'failed' when the assessment's retrieval failed - any entry is a failed one
    (retrieval_failed) - with that entry's note as ``detail``: never 'not_run' or 'done' (refutation round 1,
    parity-1); 'done' when retrieval ran for the assessment, its traces cover every code a reviewer can decide
    (review.decidable: selected, or excluded and reinstatable), and an installed CMS reference file applied to its
    service date (_source_applied);
    'not_verified' when they cover every such code but no CMS reference file applied - no service date established, or
    none covering it - so no code was checked against one, with why as ``detail`` (refutation round 2, truth-3: that was
    'done', its codes counted as checked); 'not_run' when there is no assessment, it predates the harness, or no
    retrieval ran for it - also when it has no code to retrieve for, never 'done' of nothing (no trace at all is what
    an absent passages module records too). ``detail`` is '' in every other state. ``codes_checked`` counts the traced
    codes only when a CMS reference file applied (0 otherwise), and a failed entry is no code checked, so it is counted
    in neither ``codes_checked`` nor ``passages``. Only the trace of a code a reviewer can decide is read, the one rule
    jobs._retrieval traces by, so with no code to decide on the state is never 'done' (refutation round 8,
    retrieval-2: a second review's code CPT Studio did not add read "Done 1 code checked"; round 9, retrieval-1 and
    page-1: so did a code excluded with no reinstatement, whose own reference check says none ran)."""
    out = {'state': 'not_run', 'detail': '', 'codes_checked': 0, 'passages': 0, 'sources': [],
           'not_connected': list(review.NOT_CONNECTED)}
    if active:
        out['state'] = 'waiting'
    if assessment is None:
        return out
    entries = [entry for entry in assessment.retrieval or [] if isinstance(entry, dict)]
    failures = [entry for entry in entries if retrieval_failed(entry)]
    decidable = {p.code for p in assessment.proposals.all() if review.decidable(p)}
    retrieval = [entry for entry in entries if not retrieval_failed(entry) and entry.get('code') in decidable]
    traced = {entry.get('code') for entry in retrieval}
    applied = _source_applied(assessment)
    if not active and failures:
        out.update(state='failed', detail=failure_note(failures[0]))
    elif not active and assessment.participants and traced and decidable <= traced:
        if applied:
            out['state'] = 'done'
        else:
            out.update(state='not_verified', detail=_no_source(retrieval))
    sources = {}
    for entry in retrieval:
        for item in review.retrieved(entry, 'facts') + review.retrieved(entry, 'passages'):
            key = str(item.get('source_key') or '')
            if key:
                sources.setdefault(key, str(item.get('release') or ''))
    known = _reference_sources(sorted(sources))
    out.update(codes_checked=len(traced) if applied else 0,
               passages=sum(len(review.retrieved(entry, 'passages')) for entry in retrieval),
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


def _codes_added(peer_review, assessment, name, record):
    """(added, repeated): the codes in a code's shape - a CPT or HCPCS code's, participants.peer.code_shaped, the
    engine's rule for a participant's code (refutation round 5, shapes-1: the CPT shape alone left an HCPCS code the
    engine read out of codes_added) - a peer review listed as additional codes, each once, in order, split by the phase
    participant ``name`` first proposed each in (peer_code_phases): ``added``, those first proposed in its peer review -
    the codes it proposed after peer review, never independent (HARNESS.md 11.1) - and ``repeated``, those its
    independent reading first proposed, which it listed again. A code none of its entries in either phase located is
    in neither: it listed the code and proposed it in no phase (refutation round 5, the session's D12). The phase is
    read from ``record`` and the review alone; ``assessment`` and ``name`` are not read."""
    if peer_review is None or peer_review.refused:
        return [], []
    phases = peer_code_phases(peer_review, record)
    return ([code for code, phase in phases.items() if phase == models.ProviderRun.PEER_REVIEW],
            [code for code, phase in phases.items() if phase == models.ProviderRun.INDEPENDENT])


def peer_code_phases(peer_review, record):
    """{code: 'independent' | 'peer_review' | ''} for each additional code in a code's shape (participants.peer.
    code_shaped) a participant's ``peer_review`` lists, each once, in order: the phase in which the participant first
    proposed it, read only from its entries that located a quote in the document (refutation round 1, EV-2 = IND-3: an
    entry whose quotes were not found proposed nothing; the engine's _Harness.phase reads the same entries) -
    'independent' where its frozen first reading, as ``record`` (its Assessment.participants entry) recorded it, has a
    located quote for the code (codes[].quote, its first located quote), else 'peer_review' where an entry of the review
    locates one, else '' (listed in peer review: proposed in neither phase). HARNESS.md 11.1: a code first proposed in
    phase 2 is marked proposed after peer review, never as independent - and a code its first reading proposed is never
    marked so (refutation round 2, truth-8). Refutation round 5 (the session's D12; truth-2, truth-3): a code its first
    reading only listed was "first proposed in its independent reading", and one its peer review only listed was
    "proposed after peer review, never independent", beside the engine's "so it did not propose it". One reading of
    that phase, for every place that words a peer review's additional codes."""
    first = {item.get('code') for item in (record or {}).get('codes') or []
             if isinstance(item, dict) and item.get('quote')}
    located = {}  # code -> whether any entry of the review for it located a quote
    for item in peer_review.additional_codes:
        if participant_peer.code_shaped(item.code):
            located[item.code] = located.get(item.code, False) or any(quote.spans for quote in item.evidence)
    independent, later = models.ProviderRun.INDEPENDENT, models.ProviderRun.PEER_REVIEW
    return {code: independent if code in first else later if found else '' for code, found in located.items()}


def _join(items):
    """'A', 'A and B', 'A, B and C'."""
    return items[0] if len(items) == 1 else f'{", ".join(items[:-1])} and {items[-1]}'


def _peer_detail(record, repeated=()):
    """A participant's peer review (its assess #2 entry) in one plain sentence; ``repeated``: the codes it listed again
    that its independent reading first proposed (peer_code_phases), said as such - they are never codes it proposed
    after peer review."""
    state = record.get('peer_state')
    if state == 'read':
        detail = 'Answered in peer review, after its first reading was frozen; the review was used.'
        if repeated:
            detail += (f' It listed {_join(list(repeated))} again in peer review; it first proposed '
                       f'{"it" if len(repeated) == 1 else "them"} in its independent reading.')
        count = int(record.get('peer_unverified_quotes') or 0)
        if count:
            detail += (f' {count} of its quotes {"was" if count == 1 else "were"} not found in the document, so '
                       f'{"it is" if count == 1 else "they are"} never used as evidence.')
        return detail
    words = review.record_words({'state': state, 'reason': record.get('peer_reason')})
    words = words.replace('the reading was not used', 'the review was not used', 1)
    return 'Peer review: ' + words + '.' + (RECONCILE_FIRST if state in ('unknown', 'blocked') else '')


# Why a final assessment of phase 1 read no peer review, by the pipeline's own rule (jobs.owed_peer_stages; HARNESS.md
# 12.7, the final assessment): none is owed while a member date conflict holds it, nor for a participant not configured
# now. The reports' PEER REVIEW says the same (refutation round 2, truth-9: the page read "No peer review is recorded
# for this revision" beside the revision's own peer-review runs).
PEER_HELD = ('Peer review: none is read by this assessment: the service date entered as encounter metadata conflicts '
             'with the document, and no peer review is sent while that question is open.')
PEER_NOT_CONFIGURED = 'Peer review: none follows this assessment: {label} is not configured on this installation now.'
PEER_NONE_READ = 'Peer review: none is read by this assessment.'


def _no_peer_review(assessment, name):
    """Why the final phase-1 ``assessment`` read no peer review of ``name``, whose first reading it read."""
    if review.peer_review_held(assessment):
        return PEER_HELD
    if name not in participants.configured():
        return PEER_NOT_CONFIGURED.format(label=participants.LABELS[name])
    return PEER_NONE_READ


def _harness2(row, assessment, jobs):
    """The harness@2 fields of one participant row (HARNESS.md 12.6): ``peer`` - its peer review's state, sentence,
    run, the codes it added and its unverified quotes ({} before phase 2, for Corti, or for a participant not
    configured) - and the references its phase-1 run (``references``) and its peer-review run (``peer_references``)
    retrieved and used, never merged with each other or with the reconciliation's (reference_validation). A final
    assessment of phase 1 serves, for each participant whose first reading it read, ``not_sent`` with why it read no
    peer review (_no_peer_review); an assess #1 whose peer stages are owed still serves none."""
    out = {'peer': {}, 'references': dict(NO_REFERENCES), 'peer_references': dict(NO_REFERENCES)}
    name = row['name']
    if name not in participants.PARTICIPANTS:
        return out
    run = models.ProviderRun.objects.filter(pk=row['run_id']).first() if row['run_id'] else None
    if run is not None and run.purpose == models.ProviderRun.INDEPENDENT:
        out['references'] = shown_references(review.participant_references(run))
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
        # codes_added: only those first proposed in its peer review (11.1); a repeated one is said in the detail
        added, repeated = _codes_added(peer_review, assessment, name, record)
        out['peer'] = {'state': RECORD_STATES.get(record.get('peer_state'), 'unknown'),
                       'detail': _peer_detail(record, repeated),
                       'run_id': str(peer_run.pk) if peer_run is not None else None, 'codes_added': added,
                       'unverified_quotes': int(record.get('peer_unverified_quotes') or 0)}
        if peer_run is not None:
            out['peer_references'] = shown_references(review.participant_references(peer_run, peer_review))
    elif (record is not None and record.get('state') == 'read' and review.assessment_phase(assessment) == 1
          and review.is_final(assessment)):
        out['peer'] = {'state': RECORD_STATES['not_sent'], 'detail': _no_peer_review(assessment, name), 'run_id': None,
                       'codes_added': [], 'unverified_quotes': 0}
    return out


def shown_used(item):
    """One reference a participant run says it used ({ref, use, retrieved, ...}), its ref as CPT Studio shows it: as
    given only when that run's own tool results returned it (``retrieved``: CPT Studio's own identifier), otherwise only
    as a short id of letters and digits or by its length (participants.peer.shown_reference; refutation round 4, the
    session's D9, shapes-3: a ref no tool returned is the participant's own text, and was served as written). The rest
    of the item is as the reader recorded it."""
    if not isinstance(item, dict):
        return item
    return dict(item, ref=participant_peer.shown_reference(item.get('ref'), item.get('retrieved')))


def shown_references(references):
    """A run's references (review.participant_references) as the API serves them: what its own tool calls retrieved -
    CPT Studio's own identifiers - as given, and each reference it says it used through shown_used."""
    return {**references, 'used': [shown_used(item) for item in references.get('used') or []]}


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
        # how many questions are open on the assessment of the current revision; None while that revision has none:
        # none was made, or the current assessment, whose questions clarifications and open_clarifications still serve,
        # is an earlier revision's (after an addendum, until its revision is first assessed). It was 0 there, and the
        # page's Clarification row drew "None open" beside those questions; the row reads None as no assessment
        # (refutation round 6, row-1)
        'clarification': {'open': assessment.clarifications.filter(state=models.Clarification.OPEN).count()
                          if assessment is not None else None},
        'final': {'state': encounter.state, 'label': review.encounter_state_label(encounter)},
    }


def _step_outcome(job):
    """progress._step_outcome for a finished stage, None while it is queued or running."""
    from . import progress  # local import: progress reads the review layer this module serializes
    return None if job.state in (models.Job.QUEUED, models.Job.RUNNING) else progress._step_outcome(job)


def encounter_detail(encounter, membership):
    from .jobs import busy, second_review_status  # local import: jobs imports this module's peers

    assessment, clarifications = _assessment_json(encounter, membership)
    revision = encounter.current_revision
    jobs = list(encounter.jobs.filter(revision=revision).order_by('created_at')) if revision else []
    state_run = review.state_run(encounter)
    # harness@2 (HARNESS.md 12.5): the candidates of each open question of the final assessment, and each question's
    # confirmation; every confirmation of the current revision is listed too, after its question has gone. can_confirm:
    # a reviewer, while confirmations are offered - never in this release (HARNESS.md 12.10, D7). Refutation round 4
    # (12.10 as amended, the session's D8): candidates are served only to a member who may confirm one - so to no one in
    # this release, where review.assessment_candidates is {} as well; the page draws them only for such a member
    can_confirm = membership.can_review and review.confirmations_offered()
    offered = review.assessment_candidates(review.live_assessment(encounter)) if can_confirm else {}
    confirmed = {c.clarification_id: c for c in reversed(models.FindingConfirmation.objects.filter(
        clarification__in=clarifications).select_related('confirmed_by', 'revision').order_by('created_at', 'pk'))}
    return {
        **encounter_summary(encounter),
        'created_by': encounter.created_by.label(),
        'permissions': {'can_review': membership.can_review, 'is_owner': is_owner(membership),
                        'can_confirm': can_confirm},
        'harness': harness_json(encounter, jobs),
        'revision': _revision_json(revision),
        'context': {'facts': _context_facts(encounter.current_context),
                    'user_values': encounter.user_values or {}},
        'routing': _routing_json(encounter),
        'pipeline': {'busy': busy(encounter), 'can_stop': busy(encounter) and membership.can_review,
                     'can_resume': review.can_resume(encounter) and membership.can_review,
                     # A member's Stop, as opposed to a stage the system cancelled (expired, or left by a dead worker).
                     'stopped_by_member': encounter.stopped_at is not None,
                     # step_outcome: the state the finished stage gives its customer step, by the page's own rule
                     # (progress._step_outcome: done, failed, stopped, or None when it did nothing for the step), so the
                     # walk folds the steps a member is shown from the persisted stages without a second copy of it
                     'stages': [{'kind': j.kind, 'state': j.state, 'error': j.error,
                                 'finished_at': _iso(j.finished_at),
                                 'step_outcome': _step_outcome(j)} for j in jobs]},
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
        # the encounter's own history: an operator's reads of it (operator.viewed, studio.operator) are the access log,
        # kept as audit rows and never part of the encounter's activity
        'activity': [_activity_json(e) for e in encounter.audit_events.exclude(event=OPERATOR_VIEWED)
                     .select_related('actor').order_by('created_at')],
    }


# --- the administrative trace (HARNESS.md 7; owner only, api.trace) ---------------------------------------------------

def _ids(values, ids):
    """A list of service ids a participant wrote, each as ``ids`` (the participant's one participants.peer.ShownIds for
    the whole trace, _trace_runs) serves it; anything that is not a list is returned as it is."""
    return [ids(value) for value in values] if isinstance(values, list) else values


def _code_entry(item, ids):
    """A code a participant proposed, advised not to code or took a position on, with its code-like fields in the
    strict shapes a peer request shows them in (HARNESS.md 12.4 after refutation round 3, peer-1; I9): the code only in
    a code's shape (participants.peer.shown_code), each modifier only as two capital letters or digits (shown_modifier),
    each service id only as letters and digits of at most 8 characters, any other under one name of CPT Studio's own for
    the participant's whole trace (``ids``: its reading and its peer review alike, _trace_runs); otherwise only by its
    length. The 20-character token rule the trace used before passed descriptor-like text such as 'SYNTH;WITH-POLYP(S)'
    verbatim (refutation round 3, R3-PEER's display note). Its free text is left for the page, which withholds what
    reads like a descriptor."""
    if not isinstance(item, dict):
        return item
    out = dict(item)
    if 'code' in out:
        out['code'] = participant_peer.shown_code(out['code'])
    if 'modifiers' in out:
        out['modifiers'] = ([participant_peer.shown_modifier(value) for value in out['modifiers']]
                            if isinstance(out['modifiers'], list) else out['modifiers'])
    if 'service_ids' in out:
        out['service_ids'] = _ids(out['service_ids'], ids)
    return out


def _trace_reading(run, ids=None):
    """A participant's first-reading run's full normalized reading - the quotes CPT Studio could not locate included,
    and each reference it says it used with CPT Studio's check against that run's own tool results - read as the
    adapter version that recorded it; None for Corti's runs, a peer-review run (its ``review``) and a run with no
    answer. ``ids``: the participant's one participants.peer.ShownIds for the whole trace (_trace_runs; a new one when
    none is given), which names its services first."""
    if (run.provider not in participants.PARTICIPANTS or run.purpose != models.ProviderRun.INDEPENDENT
            or run.state != models.ProviderRun.SUCCEEDED):
        return None
    reading, problem = review.stored_reading(run)
    if reading is None:
        return {'refused': True, 'problems': [problem], 'unverified_quotes': 0, 'date_of_service': {},
                'services': [], 'codes': [], 'not_coded': [], 'questions': [], 'extraction_issues': [],
                'references_used': []}
    data = to_jsonable(reading)
    ids = participant_peer.ShownIds() if ids is None else ids  # services first, then what refers to them
    return {'refused': data['refused'], 'problems': data['problems'], 'unverified_quotes': data['unverified_quotes'],
            'date_of_service': {'value': data['date_of_service'], 'evidence': data['date_evidence']},
            'services': [dict(service, id=ids(service.get('id'))) for service in data['services']],
            'codes': [_code_entry(item, ids) for item in data['codes']],
            'not_coded': [_code_entry(item, ids) for item in data['not_coded']],
            'questions': [dict(item, service_ids=_ids(item.get('service_ids'), ids)) for item in data['questions']],
            'extraction_issues': data['extraction_issues'],
            'references_used': _checked_against(run, data['references_used'])}


def _checked_against(run, used):
    """A run's references used as the trace serves them: as the reader recorded them, each ref as the API shows it
    (shown_used: as given only when that run's own tool results returned it, otherwise only as a short id or by its
    length; refutation round 4, shapes-3), and for a run that reused a retained answer each with ``reused_from``, the
    retained run whose tool calls CPT Studio checked it against (jobs.loop_run), so the trace never says a reuse
    retrieved anything by its own tool calls (refutation round 2, truth-13)."""
    used = [shown_used(item) for item in used]
    if not run.reused_from_id:
        return used
    return [dict(item, reused_from=str(run.reused_from_id)) if isinstance(item, dict) else item for item in used]


def _trace_review(run, assessment=None, ids=None):
    """A peer-review run's PeerReview (HARNESS.md 11.1) as JSON - its answers, positions, additional codes, references
    used (each checked against that run's own tool results), the frozen inputs it was shown, its problems - read as the
    adapter version that recorded it; None for any other run and a run with no answer. Each additional code carries
    ``phase``, where ``assessment`` - the current one - read this review: the phase its participant first proposed it in
    (peer_code_phases), except that an entry none of whose quotes was located is '' where that phase is 'peer_review'
    (refutation round 6, account-4: an entry is worded by its own quotes, so a second entry of a code another entry
    located, its quote not found, was called "proposed after peer review, never independent"; 'independent' stays on
    every entry, since "repeated in peer review" claims no proposal there), and '' for a code it proposed in neither
    phase (refutation round 2, truth-8: a code its first reading proposed was called "proposed after peer review, never
    independent"; round 5, the session's D12: so was a code no entry of its located). Where the current assessment did
    not read this review, every additional code carries ``phase`` None, never D12's '' (refutation round 6, account-5:
    '' read "listed in peer review" beside a quote found in the document, and the reuse of the same bytes was "proposed
    after peer review" in the same trace). ``ids``: the participant's one participants.peer.ShownIds for the whole trace
    (_trace_runs): an additional code's service ids name the services of its own frozen first reading, so each has the
    name that reading's run gave it (refutation round 4, shapes-2, truth-3)."""
    if (run.provider not in participants.PARTICIPANTS or run.purpose != models.ProviderRun.PEER_REVIEW
            or run.state != models.ProviderRun.SUCCEEDED):
        return None
    peer_review, problem = review.stored_peer_review(run)
    if peer_review is None:
        return {'refused': True, 'problems': [problem], 'unverified_quotes': 0, 'frozen_inputs': [], 'answers': [],
                'positions': [], 'additional_codes': [], 'references_used': []}
    data = to_jsonable(peer_review)
    record = review.model_records(assessment).get(run.provider) if assessment is not None else None
    read = record is not None and record.get('peer_state') == 'read' and record.get('peer_run') == str(run.pk)
    # a code in a code's shape, CPT or HCPCS, as the engine reads it (participants.peer.code_shaped; refutation round 5,
    # shapes-1: the CPT shape alone gave an HCPCS code no phase); any other is served by its length (_code_entry)
    shaped = [item.code if participant_peer.code_shaped(item.code) else '' for item in peer_review.additional_codes]
    phases = peer_code_phases(peer_review, record) if read else {}

    def phase(item, code):
        if not read:
            return None
        said = phases.get(code, '')
        located = any(quote.spans for quote in item.evidence)
        return '' if said == models.ProviderRun.PEER_REVIEW and not located else said

    ids = participant_peer.ShownIds() if ids is None else ids
    return {**data, 'positions': [_code_entry(item, ids) for item in data['positions']],
            'additional_codes': [{**_code_entry(entry, ids), 'phase': phase(item, code)}
                                 for entry, item, code in zip(data['additional_codes'], peer_review.additional_codes,
                                                              shaped)],
            'references_used': _checked_against(run, data['references_used'])}


def _trace_exchanges(run):
    """Each HTTP exchange of a participant run's tool loop (models.ProviderExchange, HARNESS.md 11.2) with the tool
    calls CPT Studio executed for it; the results themselves are named by their sha256. A call's tool and arguments are
    a model's own text, shown only in the tools' own shapes (participants.peer.shown_tool, shown_arguments; refutation
    round 4, shapes-4: a call's codes were served as written, 'Colonoscopy, flexible, diagnostic'); the refs it returned
    are CPT Studio's own."""
    return [{'turn': exchange.turn, 'state': exchange.state, 'http_status': exchange.http_status,
             'latency_ms': exchange.latency_ms, 'usage': exchange.usage or {},
             'request_sha256': exchange.request_sha256, 'response_sha256': exchange.response_sha256,
             'provider_request_id': exchange.provider_request_id, 'response_id': exchange.response_id,
             'error': exchange.error,
             'tool_calls': [{'call_id': call.call_id, 'tool': participant_peer.shown_tool(call.tool),
                             'arguments': participant_peer.shown_arguments(call.arguments),
                             'refs': list(call.refs or []), 'result_sha256': call.result_sha256,
                             'executed_at': _iso(call.executed_at)} for call in exchange.tool_calls.order_by('id')]}
            for exchange in run.exchanges.order_by('turn')]


def _trace_run(run, assessment=None, ids=None):
    """One run as HARNESS.md 6 records it: what was called and what answered, its identities (the run identity is the
    client request id a participant's vendor was given), usage and cost, the hashes, and who asked for it. ``ids``: the
    participant's one participants.peer.ShownIds for the whole trace (_trace_runs)."""
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
            'reconciled': run.reconciled_at is not None, 'reading': _trace_reading(run, ids),
            'review': _trace_review(run, assessment, ids), 'exchanges': _trace_exchanges(run)}


def _trace_runs(runs, assessment):
    """One participant's runs of the revision, oldest first, sharing one participants.peer.ShownIds (refutation round 4,
    shapes-2, truth-3): a peer review's service ids name the services of the participant's own frozen first reading,
    which the first-reading run before it names first, so a withheld id has one name across the participant's reading
    and its peer review, and two ids never share one. A ShownIds of the review's own had named the biopsy code a peer
    review added on 'colon-b' with 'id 1', the name the same trace gave the snare service 'colon-a'."""
    ids = participant_peer.ShownIds()
    return [_trace_run(run, assessment, ids) for run in runs]


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
                     'listed_by': review.listed_by(proposal),
                     'positions': review.participant_positions(proposal, assessment.participants),
                     'reference_check': review.reference_check(proposal),
                     'approved': decision is not None and decision.action == models.Decision.APPROVE})
    return {
        'encounter': {'id': str(encounter.pk), 'title': encounter.title},
        'revision': {'id': str(revision.pk), 'number': revision.number, 'text_sha256': revision.text_sha256}
        if revision is not None else None,
        'participants': [{'name': name, 'label': label, 'vendor': vendor, 'model': model,
                          'runs': _trace_runs([run for run in runs if review.participant_of(run) == name], assessment)}
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
