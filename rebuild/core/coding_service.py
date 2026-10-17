"""Durable coding work and approval, independent of clinical document state."""
import copy
import hashlib
import json
import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from .coding_licensing import cpt_status
from .models import CodingContext, CodingDecision, CodingRelease, CodingRun, CodeSet, CodeSuggestion, Encounter, Job
from .security import audit, membership

CONTRACT = 'outpatient-coding-v1'
PENDING = ('queued', 'running', 'reconciliation')
CONTEXT_DEFAULTS = {
    'setting': 'unknown', 'patient_status': 'unknown', 'em_basis': 'unknown',
    'time_minutes': '', 'time_evidence': '', 'time_qualified_clinician': False,
    'time_same_day': False, 'time_excludes_separately_reported': False,
    'mdm_problems': 'unknown', 'mdm_data': 'unknown', 'mdm_risk': 'unknown',
    'mdm_problems_evidence': '', 'mdm_data_evidence': '', 'mdm_risk_evidence': '',
    'identity_review_reason': '',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def context_data(encounter):
    row = CodingContext.objects.filter(encounter=encounter).first()
    if row is not None:
        return {**CONTEXT_DEFAULTS, **row.data}
    # Source facts are suggestions, not clinician time attestations. They permit
    # one direct request from a new documented office encounter without a second
    # prediction merely to populate setting/status. Confirmation remains explicit
    # in the separately bound output review; all time attestations stay false.
    from .coding_dispatch import provider, source_context_enabled
    if provider(encounter) == 'corti' and source_context_enabled(encounter):
        from .corti_semantics import office_time_facts
        observed = office_time_facts(encounter.notes)
        if observed['status'] == 'documented':
            facts = {f['key']: f['value'] for f in observed['facts']}
            return {**CONTEXT_DEFAULTS, **{k: facts[k] for k in ('setting', 'patient_status', 'em_basis')}}
    return dict(CONTEXT_DEFAULTS)


def release_snapshot(encounter):
    # Diagnosis content and CPT rights have independent admission paths.
    releases = list(CodeSet.objects.filter(system='ICD-10-CM',
        effective_from__lte=encounter.service_date, effective_until__gte=encounter.service_date)
        .order_by('system', 'version', 'pk'))
    cpt = cpt_status(encounter.service_date)
    if cpt['available']:
        releases.append(CodeSet.objects.get(pk=cpt['release_id'], system='CPT'))
    references = {str(r.release_id): r for r in CodingRelease.objects.filter(release__in=releases).only('release_id','digest')}
    return [{'id': str(r.pk), 'system': r.system, 'version': r.version,
             'sha256': r.sha256, 'coding_digest': references[str(r.pk)].digest if str(r.pk) in references else '',
             'license_reference': r.license_reference, 'effective_from': r.effective_from.isoformat(),
             'effective_until': r.effective_until.isoformat()}
            for r in releases]


def input_snapshot(encounter):
    patient = encounter.patient
    from .coding_dispatch import contract
    ENGINE_CONTRACT = contract(encounter)
    inputs = {'workflow_contract': CONTRACT, 'engine_contract': ENGINE_CONTRACT, 'encounter_id': str(encounter.pk),
              'department_id': str(encounter.department_id), 'patient_id': str(encounter.patient_id),
              'patient_identity': {'id': str(patient.pk), 'display_name': patient.display_name,
                                   'reference': patient.reference},
              'template_version_id': str(encounter.template_version_id),
              'notes': encounter.notes, 'answers': copy.deepcopy(encounter.answers),
              'revision': encounter.revision, 'service_date': encounter.service_date.isoformat()}
    birth = getattr(patient, 'date_of_birth', None)
    if birth is not None:
        inputs['patient_identity']['date_of_birth'] = birth.isoformat()
    version = encounter.template_version
    approved, required_name_keys = None, set()
    if any(isinstance(d, dict) and d.get('version') == 3 for d in version.semantic_definitions.values()):
        from .semantic_generation import requires_patient_name
        from .semantic_preparation import validated_semantic_definitions
        approved = validated_semantic_definitions(version)
        required_name_keys = {key for key, d in approved.items() if d['version'] == 3 and requires_patient_name(d)}
    inputs['patient_name_answers'] = []
    for field in version.fields:
        if field['key'] in required_name_keys:
            continue  # The validated identity fact below replaces label-only narrative interpretation.
        label = field.get('label', '')
        normalized = ' '.join(re.sub(r'[^\w\s]', ' ', label.casefold().replace("'", '').replace('’', '')).split()) if isinstance(label, str) else ''
        if normalized not in ('patient name', 'full name', 'name of patient', 'what is the patients full name'):
            continue
        answer = encounter.answers.get(field.get('key'), {})
        text = answer.get('text') if isinstance(answer, dict) else None
        if isinstance(text, str) and text.strip():
            inputs['patient_name_answers'].append({'key': field['key'], 'label': label, 'text': text})
    if required_name_keys:
        from .coding_engine import semantic_patient_name_evidence
        inputs['documented_patient_name_evidence'] = {'contract':'approved-semantic-patient-name-v1',
            'fields':semantic_patient_name_evidence(encounter.notes, version.fields, approved, encounter.answers)}
    inputs['template'] = {'fields_sha256': digest(version.fields),
                          'definitions_sha256': digest(version.semantic_definitions),
                          'original_sha256': version.template.sha256,
                          'prepared_sha256': version.prepared_sha256}
    context = context_data(encounter)
    releases = release_snapshot(encounter)
    return inputs, context, releases, digest({'inputs': inputs, 'context': context, 'releases': releases})


def eligible(encounter):
    return (encounter.status in ('review', 'finalized') and bool(encounter.notes.strip())
            and bool(encounter.answers) and not Job.objects.filter(
                encounter=encounter, state__in=PENDING).exists())


def locked_encounter(encounter, user, clinician=False):
    row = Encounter.objects.select_related('patient', 'department', 'template_version__template').select_for_update(
        of=('self',)).get(pk=encounter.pk)
    membership(user, row.department, roles=['owner', 'clinician'] if clinician else None)
    return row


@transaction.atomic
def ensure_run(encounter, user, automatic=False):
    """Durable enqueue inside the save transaction; a GET never calls this."""
    e = locked_encounter(encounter, user, clinician=True)
    if (automatic and e.status == 'finalized') or not eligible(e):
        return None
    inputs, context, releases, key = input_snapshot(e)
    old = CodingRun.objects.filter(input_digest=key, encounter=e).first()
    if old:
        return old
    available = any(r['coding_digest'] for r in releases)
    config = {}
    state, error_code, error = 'queued', '', ''
    if not available:
        state, error_code = 'needs_detail', 'terminology_unavailable'
        error = 'No verified coding reference covers this date of service. Contact your administrator.'
    else:
        from .coding_dispatch import configuration
        try:
            config = configuration(user, e)
        except ValidationError:
            state, error_code = 'failed', 'service_unavailable'
            error = 'Coding is not configured for this workspace. Contact your administrator.'
    run = CodingRun.objects.create(encounter=e, user=user, input_digest=key,
        inputs=inputs, context=context, releases=releases, config=config, state=state,
        error_code=error_code, error=error,
        finished_at=timezone.now() if state != 'queued' else None,
        actual_cost=Decimal('0') if state != 'queued' else None)
    audit(user, 'coding.run_requested', run.pk, department=e.department,
          input_digest=key, automatic=automatic, state=state)
    return run


def normalize_context(data):
    if type(data) is not dict or set(data) - set(CONTEXT_DEFAULTS):
        raise ValidationError('Coding context contains unknown fields.')
    result = {**CONTEXT_DEFAULTS, **data}
    choices = {'setting': {'unknown', 'outpatient_office'},
               'patient_status': {'unknown', 'new', 'established'},
               'em_basis': {'unknown', 'mdm', 'time'}}
    choices.update({k: {'unknown', 'straightforward', 'low', 'moderate', 'high'}
                    for k in ('mdm_problems', 'mdm_data', 'mdm_risk')})
    for key, allowed in choices.items():
        if type(result[key]) is not str or result[key] not in allowed:
            raise ValidationError('Choose a valid coding context option.')
    for key in ('time_qualified_clinician', 'time_same_day', 'time_excludes_separately_reported'):
        if type(result[key]) is not bool:
            raise ValidationError('Time attestations must be explicit yes or no values.')
    for key in ('time_minutes', 'time_evidence', 'identity_review_reason',
                'mdm_problems_evidence', 'mdm_data_evidence', 'mdm_risk_evidence'):
        if type(result[key]) is not str or len(result[key]) > (6 if key == 'time_minutes' else 4000):
            raise ValidationError('Coding context text is invalid or too long.')
        result[key] = result[key].strip()
    if result['time_minutes'] and (not result['time_minutes'].isascii()
            or not result['time_minutes'].isdigit() or not 0 < int(result['time_minutes']) <= 1440):
        raise ValidationError('Enter documented time as whole minutes between 1 and 1440.')
    return result


@transaction.atomic
def update_context(encounter, user, data):
    e = locked_encounter(encounter, user, clinician=True)
    normalized = normalize_context(data)
    evidence = e.notes + '\n' + '\n'.join(str(v.get('text', '')) for v in e.answers.values() if isinstance(v, dict))
    for key in ('time_evidence', 'mdm_problems_evidence', 'mdm_data_evidence', 'mdm_risk_evidence'):
        if normalized[key] and normalized[key] not in evidence:
            raise ValidationError('Supporting quotations must match the saved documentation exactly.')
    if normalized['identity_review_reason'] and not getattr(settings, 'SYNTHETIC_ONLY', False):
        raise ValidationError('Identity discrepancies require correction in the clinical record.')
    row, _ = CodingContext.objects.get_or_create(encounter=e,
        defaults={'data': normalized, 'updated_by': user})
    if row.data != normalized:
        row.data = normalized
        row.updated_by = user
        row.save(update_fields=['data', 'updated_by', 'updated_at'])
    audit(user, 'coding.context_saved', row.pk, department=e.department, context_digest=digest(normalized))
    return ensure_run(e, user)


def selection_digest(run):
    return digest({'input_digest': run.input_digest, 'result_digest': digest(run.result),
                   'selection_revision': run.selection_revision, 'selections': run.selection})


def approval_ready(run):
    if run.context.get('setting') != 'outpatient_office' or run.result.get('global_blockers'):
        raise ValidationError('Resolve the visit setting and required review details before approving coding.')
    ids = set(run.selection.get('selected_ids', []))
    systems = {r['system'] for r in run.result.get('suggestions', []) if r['id'] in ids}
    if any(q.get('blocking') and q.get('system') in systems for q in run.result.get('questions', [])):
        raise ValidationError('Resolve the required details for the selected codes before approving.')


def displayed_run(encounter):
    key = input_snapshot(encounter)[3]
    return (CodingRun.objects.filter(encounter=encounter, input_digest=key).first()
            or CodingRun.objects.filter(encounter=encounter).order_by('-created_at', '-pk').first())


def assert_current(run, encounter):
    if not eligible(encounter) or input_snapshot(encounter)[3] != run.input_digest:
        raise ValidationError('The saved documentation or coding context changed. Review the current coding result.')
    if run.state not in ('succeeded', 'needs_detail'):
        raise ValidationError('Wait for a completed coding result before reviewing selections.')
    if run.config.get('mode') == 'retained_live':
        from .coding_recovery import source_for
        return source_for(run)
    return run


@transaction.atomic
def update_selection(run, user, selections, expected_selection_revision):
    e = locked_encounter(run.encounter, user, clinician=True)
    run = CodingRun.objects.select_for_update().get(pk=run.pk, encounter=e)
    assert_current(run, e)
    if CodingDecision.objects.filter(run=run).exists():
        raise ValidationError('This coding record has already been approved. Its approval is retained unchanged.')
    if type(expected_selection_revision) is not int or expected_selection_revision != run.selection_revision:
        raise ValidationError('These selections changed in another window. Review the saved selections.')
    from .coding_dispatch import validate_selection
    value = validate_selection(run, selections)
    if value != run.selection:
        run.selection = value
        run.selection_revision += 1
        run.save(update_fields=['selection', 'selection_revision'])
        audit(user, 'coding.selections_saved', run.pk, department=e.department,
              selection_digest=selection_digest(run), selection_revision=run.selection_revision)
    return run


@transaction.atomic
def approve(run, user, expected_input_digest, expected_selection_digest):
    e = locked_encounter(run.encounter, user, clinician=True)
    run = CodingRun.objects.select_for_update().get(pk=run.pk, encounter=e)
    assert_current(run, e)
    if expected_input_digest != run.input_digest or expected_selection_digest != selection_digest(run):
        raise ValidationError('This coding review changed. Review the current displayed selections before approving.')
    from .coding_dispatch import validate_selection
    approval_ready(run)
    selections = validate_selection(run, run.selection)
    if selections != run.selection:
        raise ValidationError('The saved selections need review.')
    previous = CodingDecision.objects.filter(run=run).first()
    if previous:
        if previous.selection_digest != expected_selection_digest:
            raise ValidationError('A different selection was already approved.')
        return previous
    decision = CodingDecision.objects.create(run=run, user=user, input_digest=run.input_digest,
        selection_digest=expected_selection_digest, selections=copy.deepcopy(selections), approved_at=timezone.now())
    audit(user, 'coding.approved', decision.pk, department=e.department,
          run_id=str(run.pk), input_digest=run.input_digest, selection_digest=expected_selection_digest)
    return decision


def display_binding(encounter, user, run=None):
    return {'actor': str(user.pk), 'encounter': str(encounter.pk),
            'context_digest': input_snapshot(encounter)[3],
            'run': str(run.pk) if run else None, 'result_digest': digest(run.result) if run else None,
            'selection_digest': selection_digest(run) if run else None}


def verify_display(encounter, user, token, run=None):
    try:
        value = signing.loads(token, salt=CONTRACT, max_age=12*60*60)
    except signing.BadSignature as exc:
        raise ValidationError('This coding review expired. Reopen the coding panel.') from exc
    if value != display_binding(encounter, user, run):
        raise ValidationError('This coding panel changed. Review the current result; nothing was saved.')


@transaction.atomic
def snapshot(encounter, user):
    # A read-only panel must not hold the encounter row while it validates
    # retained evidence. Mutations independently lock and rebind every token.
    e = Encounter.objects.select_related('patient', 'department', 'template_version__template').get(pk=encounter.pk)
    membership(user, e.department)
    inputs, context, releases, key = input_snapshot(e)
    run = CodingRun.objects.filter(encounter=e, input_digest=key).first()
    latest = run or CodingRun.objects.filter(encounter=e).order_by('-created_at', '-pk').first()
    stale = latest is not None and run is None
    saved_decision = CodingDecision.objects.filter(run=latest).select_related('user').first() if latest else None
    current = bool(run and eligible(e))
    decision = saved_decision if current and saved_decision and saved_decision.input_digest == key else None
    state = ('stale' if stale else 'approved' if decision else latest.state if latest else 'unrequested')
    if not eligible(e):
        state = 'documentation_pending'
    elif latest and not stale and latest.error_code == 'terminology_unavailable':
        state = 'terminology_unavailable'
    elif not latest and not any(r['coding_digest'] for r in releases):
        state = 'terminology_unavailable'
    result = latest.result if latest else {}
    if state == 'succeeded' and not result.get('suggestions'):
        state = 'empty'
    labels = {'unrequested': 'Coding has not been requested', 'queued': 'Coding queued',
              'running': 'Reviewing the saved documentation', 'succeeded': 'Ready for coding review',
              'needs_detail': 'More detail is needed', 'failed': 'Coding could not complete',
              'uncertain': 'Coding outcome needs reconciliation', 'stale': 'Saved documentation or context changed',
              'approved': 'Selections approved', 'empty': 'No supported codes found',
              'terminology_unavailable': 'Coding reference unavailable for this date',
              'documentation_pending': 'Save and generate the document before coding'}
    can_edit = bool(membership(user, e.department).role in ('owner', 'clinician'))
    # An approval describes the persisted decision, including its exclusions.
    # Earlier decisions remain history and never approve the current revision.
    selections = saved_decision.selections if saved_decision else latest.selection if latest else {}
    selected = (selections or {}).get('selected_ids', [])
    overrides = (selections or {}).get('overrides', {})
    suggestions = []
    for item in result.get('suggestions', []):
        if (item.get('system') == 'CPT' and not any(r['system'] == 'CPT' for r in releases)
                and latest.config.get('provider') != 'corti'):
            continue
        displayed = dict(item)
        replacement = overrides.get(item['id'], {}).get('code')
        if replacement:
            candidate = next((c for c in result.get('candidates', {}).get(item['id'], [])
                              if c['code'] == replacement and c['system'] == item['system']), None)
            if candidate:
                displayed.update(code=replacement, description=candidate['description'],
                                 instructions=candidate.get('instructions', []), original_code=item['code'])
        suggestions.append({**displayed, 'selected': item['id'] in selected,
                            'override_code': overrides.get(item['id'], {}).get('code', ''),
                            'override_reason': overrides.get(item['id'], {}).get('reason', '')})
    can_review = bool(can_edit and current and not saved_decision
                      and run.state in ('succeeded', 'needs_detail') and suggestions)
    summary = {
        'approved': sum(item['selected'] for item in suggestions) if decision else 0,
        'awaiting_review': len(suggestions) if current and not saved_decision else 0,
        'not_included': sum(not item['selected'] for item in suggestions) if decision else 0,
        'unresolved_questions': len(result.get('questions', [])) if current else 0,
    }
    if decision and summary['unresolved_questions']:
        labels['approved'] = 'Selections approved; questions remain'
    can_approve = False
    approval_error = ''
    if can_review:
        from .coding_dispatch import validate_selection
        try:
            approval_ready(run)
            validate_selection(run, run.selection)
            can_approve = True
        except ValidationError as exc:
            approval_error = '; '.join(exc.messages)
    view = {'encounter_id': str(e.pk), 'context': context, 'context_digest': key,
            'service_date': e.service_date, 'state': state, 'state_label': labels.get(state, 'Coding needs review'),
            'pending': state in ('queued', 'running'), 'stale': stale, 'run': latest,
            'run_id': str(latest.pk) if latest else '', 'suggestions': suggestions,
            'questions': result.get('questions', []), 'excluded': result.get('excluded', []),
            'global_blockers': result.get('global_blockers', []), 'decision': decision,
            'historical_decision': saved_decision if not decision else None,
            'summary': summary, 'current': current,
            'can_request': can_edit and eligible(e) and not run, 'can_edit': can_edit,
            'can_review': can_review, 'can_approve': can_approve, 'approval_error': approval_error,
            'selection_digest': selection_digest(latest) if latest else '',
            'display_token': signing.dumps(display_binding(e, user, latest), salt=CONTRACT, compress=True),
            'cpt_available': any(r['system'] == 'CPT' and r['coding_digest'] for r in releases),
            'releases': releases, 'error': latest.error if latest else '',
            'corti': bool(latest and latest.config.get('provider') == 'corti'),
            'replay': bool(latest and latest.config.get('mode') == 'replay'),
            'retained_prediction': result.get('retained_prediction'),
            'diagnostics': result.get('diagnostics_summary', {})}
    view['context_derived'] = bool(view['corti'] and context['setting'] != 'unknown'
        and not CodingContext.objects.filter(encounter=e).exists())
    view['mdm_rows'] = [{'key': k, 'label': label, 'value': context[k], 'evidence': context[k + '_evidence']}
                        for k, label in [('mdm_problems', 'Problems addressed'), ('mdm_data', 'Data reviewed'), ('mdm_risk', 'Risk of management')]]
    view['levels'] = ['unknown', 'straightforward', 'low', 'moderate', 'high']
    from .coding_engine import norm
    saved_identity_discrepancy = any(norm(answer['text']) != norm(inputs['patient_identity']['display_name'])
                                     for answer in inputs['patient_name_answers'])
    saved_identity_discrepancy = saved_identity_discrepancy or any(
        norm(name['name_evidence']['quote']) != norm(inputs['patient_identity']['display_name'])
        for row in inputs.get('documented_patient_name_evidence', {}).get('fields', []) for name in row['names'])
    view['identity_review_available'] = getattr(settings, 'SYNTHETIC_ONLY', False) and (
        saved_identity_discrepancy or bool(context['identity_review_reason']) or any(
            'identity' in str(b).lower() for b in result.get('global_blockers', [])))
    entitled_ids=[r['id'] for r in releases if r['system']=='CPT']
    view['legacy_codes']=list(CodeSuggestion.objects.filter(encounter=e).filter(
        models.Q(terminology__release__system='ICD-10-CM') | models.Q(terminology__release_id__in=entitled_ids)
    ).select_related('terminology__release','accepted_by').order_by('created_at','pk'))
    from . import coding_output
    output_review = coding_output.view(e, latest, user)
    view['output_review'] = output_review
    if output_review and output_review.get('available'):
        outcome = output_review['state']
        view['questions'] = [({**question, 'question': output_review['code'] +
            ': description and upstream terminology version remain unresolved. The code number has a separate, case-bound review below.'}
            if question.get('id') == output_review['identifier'] else question) for question in view['questions']]
        summary['approved'] += int(outcome == 'accepted')
        summary['awaiting_review'] += int(outcome == 'pending')
        summary['not_included'] -= int(outcome == 'accepted')
        view['state_label'] = ('Selections approved; CPT number accepted with description withheld' if outcome == 'accepted'
                               else 'ICD decision saved; CPT number awaiting confirmation' if outcome == 'pending'
                               else 'Coding decisions saved; CPT number rejected')
    view['version'] = digest({'context': key, 'run': view['run_id'], 'state': state,
                              'selection': view['selection_digest'], 'result': digest(result),
                              'decision': str(decision.pk) if decision else None,
                              'can_edit': can_edit, 'can_review': can_review, 'can_approve': can_approve,
                              'output_review': {k: output_review.get(k) for k in ('available', 'reason', 'state', 'review_digest')} if output_review else None})
    return view


def run_one():
    """Claim once, retain provider outcomes, and never mutate an Encounter."""
    mark_abandoned()
    with transaction.atomic():
        candidate = CodingRun.objects.filter(state='queued').exclude(
            encounter_id__in=Job.objects.filter(state__in=PENDING).values('encounter_id')).order_by('created_at', 'pk').first()
        if candidate is None:
            return False
        e = Encounter.objects.select_for_update().get(pk=candidate.encounter_id)
        run = CodingRun.objects.select_for_update(skip_locked=True).filter(pk=candidate.pk, state='queued').first()
        if run is None:
            return False
        if Job.objects.filter(encounter=e, state__in=PENDING).exists():
            return False
        try:
            membership(run.user, e.department)
            if not eligible(e) or input_snapshot(e)[3] != run.input_digest:
                raise ValidationError('Documentation changed before coding started. Request the current saved version.')
        except (ValidationError, PermissionDenied):
            run.state = 'failed'; run.error_code = 'stale_before_start'
            run.error = 'The documentation or access changed before processing. No provider request was sent.'
            run.finished_at = timezone.now(); run.actual_cost = Decimal('0')
            run.save(update_fields=['state', 'error_code', 'error', 'finished_at', 'actual_cost'])
            return True
        run.state = 'running'; run.started_at = timezone.now()
        run.save(update_fields=['state', 'started_at'])
    try:
        from .coding_dispatch import generate
        result = generate(run)
        with transaction.atomic():
            e = locked_encounter(e, run.user)
            run = CodingRun.objects.select_for_update().get(pk=run.pk)
            if run.state != 'running':
                return True
            run.result = result
            run.selection = {'selected_ids': sorted(x['id'] for x in result.get('suggestions', []) if x.get('eligible') is True), 'overrides': {}}
            run.selection_revision += 1
            run.state = 'needs_detail' if result.get('global_blockers') or any(
                q.get('blocking') or q.get('system') != 'CPT' for q in result.get('questions', [])) else 'succeeded'
            run.finished_at = timezone.now()
            fields = ['result', 'selection', 'selection_revision', 'state', 'finished_at']
            if not run.requests:
                run.actual_cost = Decimal('0'); fields.append('actual_cost')
            run.save(update_fields=fields)
            audit(run.user, 'coding.completed', run.pk, department=e.department,
                  input_digest=run.input_digest, result_digest=digest(result),
                  current=input_snapshot(e)[3] == run.input_digest)
    except Exception as exc:
        # The provider owns receipt/cost/unknown-outcome evidence; never overwrite it.
        with transaction.atomic():
            saved = CodingRun.objects.select_for_update().get(pk=run.pk)
            if saved.state == 'running':
                from .coding_provider import CodingUnknown, CodingNotSent, CodingFailure
                uncertain = isinstance(exc, CodingUnknown) or any(
                    r.get('state') in ('sending', 'unknown') or r.get('sent') is True and r.get('actual_cost') is None
                    for r in saved.requests)
                saved.state = 'uncertain' if uncertain else 'failed'
                saved.error_code = 'outcome_uncertain' if uncertain else 'processing_failed'
                saved.error = failure_message(exc, uncertain)
                saved.finished_at = timezone.now()
                fields = ['state', 'error_code', 'error', 'finished_at']
                if uncertain:
                    saved.actual_cost = None; fields.append('actual_cost')
                elif not saved.requests:
                    saved.actual_cost = Decimal('0'); fields.append('actual_cost')
                saved.save(update_fields=fields)
    return True


def failure_message(exc, uncertain):
    if uncertain:
        return 'A provider outcome needs reconciliation. Contact your administrator. No automatic retry will be sent.'
    from .coding_provider import CodingNotSent, CodingFailure
    if isinstance(exc, CodingNotSent):
        if exc.messages == ['Coding request exceeds its byte limit; nothing was truncated or sent.']:
            return 'This coding stage exceeds the supported request size and was not sent. No content was truncated. Earlier request evidence and any known cost are retained. Contact your administrator to review this attempt.'
        return 'The coding stage was not sent. Contact your administrator to check provider availability and configuration. The attempt is retained.'
    if isinstance(exc, CodingFailure):
        return 'The provider response could not be validated. Contact your administrator. Its evidence and known cost are retained; no retry will be sent.'
    # Only static local validation descriptions are displayed, never an arbitrary
    # transport exception, credential, payload, or traceback.
    safe_prefixes = ('Coding evidence ', 'Exactly one ICD-10-CM release ',
                     'The bound coding reference ', 'The extracted patient name ',
                     'The coding extractor ', 'The coding resolver ',
                     'An integral-symptom reference ', 'Coding lookup terms ')
    if isinstance(exc, ValidationError) and len(exc.messages) == 1:
        reason = exc.messages[0]
        if len(reason) <= 240 and reason.startswith(safe_prefixes) and not any(ord(c) < 32 for c in reason):
            return reason + ' Contact your administrator to review this retained attempt. No automatic retry will be sent.'
    return 'Coding could not complete. Contact your administrator to review the retained attempt. No automatic retry will be sent.'


def mark_abandoned():
    # Each stage has a 120-second deadline; fifteen minutes allows worker overhead.
    # Never replay a request whose process disappeared.
    with transaction.atomic():
        for run in CodingRun.objects.select_for_update(skip_locked=True).filter(
                state='running', started_at__lt=timezone.now()-timedelta(minutes=15)):
            uncertain = any(r.get('state') in ('sending', 'unknown') or r.get('sent') is True and r.get('actual_cost') is None
                            for r in run.requests)
            run.state = 'uncertain' if uncertain else 'failed'
            run.error_code = 'worker_interrupted'
            run.error = 'Coding processing was interrupted. The attempt is retained and will not be resent automatically.'
            run.finished_at = timezone.now()
            fields = ['state', 'error_code', 'error', 'finished_at']
            if uncertain:
                run.actual_cost = None; fields.append('actual_cost')
            elif not run.requests:
                run.actual_cost = Decimal('0'); fields.append('actual_cost')
            run.save(update_fields=fields)
