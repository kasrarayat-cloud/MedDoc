"""A completed derivative of one live prediction, never another provider call.

This is used only by an independently checked semantic revalidation. The original
run owns its request, raw response and usage forever; a derivative has no request
receipt and explicitly reports zero additional provider operations.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from . import coding_service as service, corti_coding, corti_prediction
from .models import CodingRun, Job
from .security import audit, private_path

CONTRACT = 'retained-live-prediction-revalidation-v1'
COMPLETE_SOURCE_CONTRACT = 'retained-live-prediction-revalidation-v2'
COMPLETE_CHECK_CONTRACT = 'retained-facts-independent-check-v3'
MODE = 'retained_live'
REVALIDATION_CONTRACT = 'retained-facts-independent-check-v1'
REVALIDATION_CONTRACTS = (REVALIDATION_CONTRACT,'retained-facts-independent-check-v2',COMPLETE_CHECK_CONTRACT)
CONTEXT_CONTRACT = 'retained-live-context-review-v1'
IDENTITY_REVIEW_CONTRACT = 'retained-live-current-identity-review-v1'


def need(value, message):
    if not value:
        raise ValidationError(message)


def stable_revalidation_inputs(encounter, source, current, *, complete=False):
    """Identity projections may change only as a consequence of checked answers.

    V3 recomputes both projections from the same immutable original destinations.
    A caller cannot discard, forge or substitute an identity bridge merely by
    removing it from the stable-input comparison. Historical rules stay exact.
    """
    excluded = {'answers', 'documented_patient_name_evidence'}
    if complete:
        fields_digest = service.digest(encounter.template_version.fields)
        need(source.get('template', {}).get('fields_sha256') == fields_digest
             == current.get('template', {}).get('fields_sha256'),
             'The retained patient-name destinations changed.')
        for inputs in (source, current):
            expected = service.patient_name_inputs(encounter, inputs['answers'])
            actual = {key: inputs[key] for key in ('patient_name_answers', 'documented_patient_name_evidence')
                      if key in inputs}
            need(actual == expected, 'The patient-name input is not the exact projection of its checked source answer.')
        excluded.add('patient_name_answers')
    return ({k:v for k,v in source.items() if k not in excluded}
            == {k:v for k,v in current.items() if k not in excluded})


def live_receipt(source):
    """Read the original successful receipt with its original identity intact."""
    need(source.config.get('provider') == 'corti' and source.config.get('mode') == 'live'
         and source.state in ('succeeded', 'needs_detail') and len(source.requests) == 1,
         'The original live prediction is unavailable.')
    receipt = source.requests[0]
    request = corti_prediction.payload(source)
    envelope = receipt.get('envelope') or {}
    need(envelope == {'protocol': corti_prediction.PROTOCOL,
                     'identity': corti_prediction.receipts._identity(source),
                     'payload': request, 'config': source.config}
         and receipt.get('request_sha256') == hashlib.sha256(corti_prediction.receipts.encode(request)).hexdigest()
         and receipt.get('stage') == corti_prediction.STAGE and receipt.get('attempt') == 1
         and receipt.get('provider') == 'corti', 'The original prediction request binding changed.')
    response = receipt.get('raw_response') or {}
    body = response.get('body')
    need(receipt.get('state') == 'succeeded' and receipt.get('sent') is True
         and receipt.get('simulated') is False and response.get('redacted') is False
         and isinstance(body, str) and hashlib.sha256(body.encode()).hexdigest() == receipt.get('response_sha256'),
         'The original prediction response is not intact.')
    return receipt


def source_for(run):
    """Fail closed on every display, decision and export of a derivative."""
    need(settings.SYNTHETIC_ONLY and run.config.get('provider') == 'corti'
         and run.config.get('mode') == MODE and run.requests == [] and run.actual_cost == 0
         and run.state in ('succeeded', 'needs_detail'), 'This retained prediction is not a completed synthetic derivative.')
    binding = run.config.get('retained_prediction')
    if isinstance(binding, dict) and binding.get('contract') == IDENTITY_REVIEW_CONTRACT:
        return identity_source_for(run, binding)
    if isinstance(binding, dict) and binding.get('contract') == CONTEXT_CONTRACT:
        return context_source_for(run, binding)
    need(isinstance(binding, dict) and set(binding) == {'contract', 'source_run_id',
         'source_input_digest', 'source_requests_digest', 'source_result_digest',
         'recovery_job_id', 'recovery_result_sha256', 'approved_answers_digest'}
         and binding.get('contract') in (CONTRACT, COMPLETE_SOURCE_CONTRACT),
         'The retained prediction has no supported provenance contract.')
    try:
        source = CodingRun.objects.get(pk=binding['source_run_id'], encounter_id=run.encounter_id)
        job = Job.objects.get(pk=binding['recovery_job_id'], encounter_id=run.encounter_id)
    except (KeyError, ValueError, CodingRun.DoesNotExist, Job.DoesNotExist) as exc:
        raise ValidationError('The retained prediction provenance is unavailable.') from exc
    need(job.config.get('semantic_revalidation_contract') in REVALIDATION_CONTRACTS and job.state == 'succeeded'
         and job.result_sha256 and job.result_sha256 == binding.get('recovery_result_sha256')
         and job.user_id == run.user_id == source.user_id and job.revision == run.inputs.get('revision'),
         'The independent answer revalidation does not cover this coding record.')
    complete = job.config.get('semantic_revalidation_contract') == COMPLETE_CHECK_CONTRACT
    need(binding['contract'] == (COMPLETE_SOURCE_CONTRACT if complete else CONTRACT),
         'The coding interpretation must match its independent source-check contract.')
    parent = job.config.get('semantic_revalidation', {})
    need(parent.get('parent_run_id') == str(source.pk)
         and parent.get('parent_answers_sha256') == service.digest(source.inputs.get('answers'))
         and parent.get('encounter_id') == str(run.encounter_id)
         and parent.get('actor_id') == str(run.user_id),
         'The independent check belongs to a different original coding snapshot.')
    try:
        raw = private_path(job.result_path).read_bytes()
        verified = json.loads(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError('The independently checked answer artifact is unavailable.') from exc
    need(hashlib.sha256(raw).hexdigest() == job.result_sha256
         and verified.get('answers') == run.inputs.get('answers'),
         'The derived coding snapshot differs from the independently checked answer artifact.')
    need(source.input_digest == binding.get('source_input_digest')
         and service.digest(source.requests) == binding.get('source_requests_digest')
         and service.digest(source.result) == binding.get('source_result_digest')
         and service.digest(run.inputs.get('answers')) == binding.get('approved_answers_digest'),
         'Retained prediction or independently checked answer evidence changed.')
    need(stable_revalidation_inputs(run.encounter if complete else None, source.inputs, run.inputs, complete=complete)
         and source.context == run.context and source.releases == run.releases
         and corti_prediction.payload(source) == corti_prediction.payload(run),
         'Retained output cannot cross a patient, source, date, revision, template, context or reference change.')
    expected_config = {**deepcopy(source.config), 'mode': MODE, 'max_calls': 0,
                       'retained_prediction': binding}
    if complete:
        from .coding_engine import PROSPECTIVE_SOURCE_CONTRACT
        expected_config['clinical_source_contract'] = PROSPECTIVE_SOURCE_CONTRACT
    need(run.config == expected_config, 'The retained prediction configuration changed.')
    from .semantic_revalidation import validate_completed
    validate_completed(job, run.inputs.get('answers'))
    need(run.result.get('retained_prediction') == binding,
         'The derived result does not retain its provenance.')
    origin, _receipt = revalidation_receipt(source, complete=complete)
    return origin


def revalidation_receipt(source, *, complete=False):
    """V3 can retain an already saved context review of the original request.

    Only the existing independently verified context derivative is admitted.
    Historical answer revalidations and arbitrary chains cannot become origins.
    """
    if complete and source.config.get('mode') == MODE:
        binding = source.config.get('retained_prediction') or {}
        need(binding.get('contract') == CONTEXT_CONTRACT,
             'The source must be an original prediction or its intact context review.')
        origin = source_for(source)
    else:
        origin = source
    return origin, live_receipt(origin)


def context_source_for(run, binding):
    """Only saved review context may differ; source, answers and receipt cannot."""
    need(set(binding) == {'contract', 'source_run_id', 'source_input_digest',
                         'source_requests_digest', 'source_result_digest', 'review_context_digest'},
         'The context review provenance is malformed.')
    try:
        source = CodingRun.objects.get(pk=binding['source_run_id'], encounter_id=run.encounter_id)
    except (ValueError, CodingRun.DoesNotExist) as exc:
        raise ValidationError('The original prediction for this context review is unavailable.') from exc
    need(source.config.get('context_review_contract') == CONTEXT_CONTRACT
         and str(source.user_id) == str(run.user_id) and source.inputs == run.inputs and source.releases == run.releases
         and source.context != run.context and source.input_digest == binding['source_input_digest']
         and service.digest(source.requests) == binding['source_requests_digest']
         and service.digest(source.result) == binding['source_result_digest']
         and service.digest(run.context) == binding['review_context_digest']
         and source.input_digest == service.digest({'inputs': source.inputs, 'context': source.context,
                                                   'releases': source.releases})
         and run.input_digest == service.digest({'inputs': run.inputs, 'context': run.context,
                                                'releases': run.releases}),
         'A context review cannot change source, patient, answers, date, reference or original prediction.')
    need(run.config == {**deepcopy(source.config), 'mode': MODE, 'max_calls': 0, 'retained_prediction': binding}
         and run.result.get('retained_prediction') == binding
         and corti_prediction.payload(source) == corti_prediction.payload(run),
         'The retained context review configuration or provider payload changed.')
    live_receipt(source)
    return source


def reuse_for_context(encounter, user, inputs, context, releases, key):
    """Revalidate a known successful request when only review context changed.

    Called under the ordinary encounter save lock. Unknown, running and legacy
    requests cannot be relabelled as successful retained predictions.
    """
    if not settings.SYNTHETIC_ONLY:
        return None
    sources = CodingRun.objects.filter(encounter=encounter, user=user,
        config__provider='corti', config__mode='live',
        config__context_review_contract=CONTEXT_CONTRACT).order_by('-created_at', '-pk')
    source = next((row for row in sources if row.inputs == inputs and row.releases == releases
                   and row.context != context), None)
    if source is None:
        return None
    need(source.state in ('succeeded', 'needs_detail'),
         'The existing prediction is unfinished or requires reconciliation. No new request was sent; review it before saving changed coding context.')
    # An invalid retained receipt is a hard stop, never an automatic paid retry.
    receipt = live_receipt(source)
    binding = {'contract': CONTEXT_CONTRACT, 'source_run_id': str(source.pk),
        'source_input_digest': source.input_digest, 'source_requests_digest': service.digest(source.requests),
        'source_result_digest': service.digest(source.result), 'review_context_digest': service.digest(context)}
    config = {**deepcopy(source.config), 'mode': MODE, 'max_calls': 0, 'retained_prediction': binding}
    run = CodingRun(encounter=encounter, user=user, inputs=inputs, context=context, releases=releases,
        input_digest=key, config=config, requests=[], actual_cost=Decimal('0'), state='needs_detail',
        started_at=timezone.now(), finished_at=timezone.now())
    result = corti_coding.retained_result(run, corti_prediction.payload(run),
        json.loads(receipt['raw_response']['body']), receipt['response_sha256'])
    result['retained_prediction'] = binding
    run.result = result
    run.selection = {'selected_ids': sorted(row['id'] for row in result['suggestions'] if row.get('eligible') is True),
                     'overrides': {}}
    run.selection_revision = 1
    run.save(force_insert=True)
    source_for(run)
    audit(user, 'coding.retained_context_revalidated', run.pk, department=encounter.department,
          source_run_id=str(source.pk), input_digest=key, new_provider_calls=0,
          original_usage_retained_on_source=True)
    return run


def stable_identity_inputs(source, current):
    """Only the local identity/review proof may differ from a live request.

    Provider text equality alone is insufficient: patient, saved answers,
    revision, template and date remain independent immutable requirements.
    """
    from .coding_engine import CURRENT_IDENTITY_CONTRACT, SEMANTIC_IDENTITY_CONTRACT, checked_patient_name_evidence
    old = source.get('documented_patient_name_evidence', {})
    new = current.get('documented_patient_name_evidence', {})
    if (old.get('contract') not in (SEMANTIC_IDENTITY_CONTRACT, CURRENT_IDENTITY_CONTRACT)
            or new.get('contract') != CURRENT_IDENTITY_CONTRACT):
        return False
    checked_patient_name_evidence(source)
    checked_patient_name_evidence(current)
    return (service.canonical({k:v for k,v in source.items() if k != 'documented_patient_name_evidence'})
            == service.canonical({k:v for k,v in current.items() if k != 'documented_patient_name_evidence'}))


def assert_no_pending_prediction(encounter, inputs, *, sources=None):
    """A changed review/graph/context cannot repeat an unsettled exact request."""
    if not settings.SYNTHETIC_ONLY or inputs.get('engine_contract') != corti_coding.CONTRACT:
        return
    if sources is None:
        sources = CodingRun.objects.filter(encounter=encounter,
            config__provider='corti', config__mode='live').order_by('-created_at', '-pk')
    from types import SimpleNamespace
    requested = corti_prediction.payload(SimpleNamespace(inputs=inputs, config={'mode':'live'}))
    for source in sources:
        pending = (source.state in ('queued', 'running', 'uncertain', 'reconciliation')
            or any(receipt.get('state') in ('sending', 'unknown') for receipt in source.requests))
        need(not (pending and corti_prediction.payload(source) == requested),
             'An identical provider request is unfinished or uncertain. No duplicate prediction was submitted.')


def identity_source_for(run, binding):
    """Replay every join before displaying, approving or exporting a derivative."""
    need(set(binding) == {'contract', 'source_run_id', 'source_input_digest',
         'source_requests_digest', 'source_result_digest', 'current_identity_binding_sha256',
         'clinical_source_contract', 'cpt_time_source_contract'},
         'The current identity review provenance is malformed.')
    from .coding_engine import SHARED_SOURCE_CONTRACT
    from .corti_semantics import SHARED_TIME_CONTRACT
    need(binding['clinical_source_contract'] == SHARED_SOURCE_CONTRACT
         and binding['cpt_time_source_contract'] == SHARED_TIME_CONTRACT,
         'The current source review has an unknown prospective clinical policy.')
    need(service.digest({'inputs':run.inputs, 'context':run.context, 'releases':run.releases}) == run.input_digest,
         'The current identity-review input digest changed.')
    try:
        source = CodingRun.objects.get(pk=binding['source_run_id'], encounter_id=run.encounter_id)
    except (ValueError, CodingRun.DoesNotExist) as exc:
        raise ValidationError('The original identity-review prediction is unavailable.') from exc
    need(source.user_id == run.user_id and service.canonical(source.context) == service.canonical(run.context)
         and service.canonical(source.releases) == service.canonical(run.releases)
         and source.input_digest == binding['source_input_digest']
         and service.digest(source.requests) == binding['source_requests_digest']
         and service.digest(source.result) == binding['source_result_digest']
         and service.digest(run.inputs.get('documented_patient_name_evidence')) == binding['current_identity_binding_sha256']
         and stable_identity_inputs(source.inputs, run.inputs),
         'The original prediction or current saved identity evidence changed.')
    expected = {**deepcopy(source.config), 'mode':MODE, 'max_calls':0, 'retained_prediction':binding,
        'clinical_source_contract':SHARED_SOURCE_CONTRACT, 'cpt_time_source_contract':SHARED_TIME_CONTRACT}
    need(run.config == expected and run.result.get('retained_prediction') == binding
         and corti_prediction.payload(source) == corti_prediction.payload(run),
         'The current identity review configuration or exact provider input changed.')
    live_receipt(source)
    return source


def reuse_for_identity_review(encounter, user, inputs, context, releases, key):
    """Re-evaluate a completed exact prediction without repeating its submission.

    The parent keeps its original raw response, result, usage and unknown cost.
    Zero cost on the new local derivative means zero additional operations only.
    """
    from .coding_engine import CURRENT_IDENTITY_CONTRACT, SHARED_SOURCE_CONTRACT
    if (not settings.SYNTHETIC_ONLY or inputs.get('documented_patient_name_evidence', {}).get('contract')
            != CURRENT_IDENTITY_CONTRACT):
        return None
    from .corti_semantics import SHARED_TIME_CONTRACT
    sources = list(CodingRun.objects.filter(encounter=encounter,
        config__provider='corti', config__mode='live').order_by('-created_at', '-pk'))
    assert_no_pending_prediction(encounter, inputs, sources=sources)
    source = next((row for row in sources if str(row.user_id) == str(user.pk)
                   and row.inputs != inputs and row.context == context
                   and row.releases == releases and stable_identity_inputs(row.inputs, inputs)), None)
    if source is None:
        return None
    need(source.state in ('succeeded', 'needs_detail'),
         'The existing prediction is unfinished or uncertain. No new prediction was submitted; resolve its outcome first.')
    receipt = live_receipt(source)
    binding = {'contract':IDENTITY_REVIEW_CONTRACT, 'source_run_id':str(source.pk),
        'source_input_digest':source.input_digest, 'source_requests_digest':service.digest(source.requests),
        'source_result_digest':service.digest(source.result),
        'current_identity_binding_sha256':service.digest(inputs['documented_patient_name_evidence']),
        'clinical_source_contract':SHARED_SOURCE_CONTRACT, 'cpt_time_source_contract':SHARED_TIME_CONTRACT}
    config = {**deepcopy(source.config), 'mode':MODE, 'max_calls':0, 'retained_prediction':binding,
        'clinical_source_contract':SHARED_SOURCE_CONTRACT, 'cpt_time_source_contract':SHARED_TIME_CONTRACT}
    run = CodingRun(encounter=encounter, user=user, inputs=inputs, context=context, releases=releases,
        input_digest=key, config=config, requests=[], actual_cost=Decimal('0'), state='needs_detail',
        started_at=timezone.now(), finished_at=timezone.now())
    need(corti_prediction.payload(source) == corti_prediction.payload(run),
         'The exact provider input changed; no retained identity review was created.')
    result = corti_coding.retained_result(run, corti_prediction.payload(run),
        json.loads(receipt['raw_response']['body']), receipt['response_sha256'])
    result['retained_prediction'] = binding
    run.result = result
    run.selection = {'selected_ids':sorted(row['id'] for row in result['suggestions'] if row.get('eligible') is True),
                     'overrides':{}}
    run.selection_revision = 1
    run.save(force_insert=True)
    source_for(run)
    audit(user, 'coding.retained_identity_revalidated', run.pk, department=encounter.department,
          source_run_id=str(source.pk), input_digest=key, new_provider_calls=0,
          original_usage_retained_on_source=True)
    return run


@transaction.atomic
def derive(encounter, recovery_job, parent_run_id):
    """Adopt a new validated snapshot; never mutate or resubmit the source run."""
    e = service.locked_encounter(encounter, recovery_job.user, clinician=True)
    need(settings.SYNTHETIC_ONLY and e.status == 'review'
         and recovery_job.encounter_id == e.pk and recovery_job.revision == e.revision
         and recovery_job.state == 'succeeded' and recovery_job.result_sha256
         and recovery_job.config.get('semantic_revalidation_contract') in REVALIDATION_CONTRACTS,
         'A completed independent synthetic revalidation is required.')
    source = CodingRun.objects.select_for_update().get(pk=parent_run_id, encounter=e)
    complete = recovery_job.config.get('semantic_revalidation_contract') == COMPLETE_CHECK_CONTRACT
    _origin, receipt = revalidation_receipt(source, complete=complete)
    inputs, context, releases, key = service.input_snapshot(e)
    old = CodingRun.objects.filter(encounter=e, input_digest=key).first()
    if old is not None:
        need(old.config.get('mode') == MODE, 'This answer snapshot already has another coding result.')
        source_for(old)
        return old
    binding = {'contract': COMPLETE_SOURCE_CONTRACT if complete else CONTRACT, 'source_run_id': str(source.pk),
        'source_input_digest': source.input_digest, 'source_requests_digest': service.digest(source.requests),
        'source_result_digest': service.digest(source.result), 'recovery_job_id': str(recovery_job.pk),
        'recovery_result_sha256': recovery_job.result_sha256,
        'approved_answers_digest': service.digest(inputs['answers'])}
    config = {**deepcopy(source.config), 'mode': MODE, 'max_calls': 0,
              'retained_prediction': binding}
    if complete:
        from .coding_engine import PROSPECTIVE_SOURCE_CONTRACT
        config['clinical_source_contract'] = PROSPECTIVE_SOURCE_CONTRACT
    run = CodingRun(encounter=e, user=recovery_job.user, inputs=inputs, context=context,
        releases=releases, input_digest=key, config=config, requests=[], actual_cost=Decimal('0'),
        state='needs_detail', started_at=timezone.now(), finished_at=timezone.now())
    # Validate the same identity and unchanged provider input before any result is
    # created. The new snapshot may change only independently checked answers.
    need(stable_revalidation_inputs(e, source.inputs, inputs, complete=complete) and source.user_id == run.user_id
         and source.context == context and source.releases == releases
         and corti_prediction.payload(source) == corti_prediction.payload(run),
         'The retained coding payload or encounter identity changed; no new prediction was requested.')
    result = corti_coding.retained_result(run, corti_prediction.payload(run),
        json.loads(receipt['raw_response']['body']), receipt['response_sha256'])
    result['retained_prediction'] = binding
    run.result = result
    run.selection = {'selected_ids': sorted(row['id'] for row in result['suggestions'] if row.get('eligible') is True),
                     'overrides': {}}
    run.selection_revision = 1
    run.save()
    source_for(run)
    audit(recovery_job.user, 'coding.retained_prediction_revalidated', run.pk, department=e.department,
          source_run_id=str(source.pk), recovery_job_id=str(recovery_job.pk),
          input_digest=key, new_provider_calls=0, original_usage_retained_on_source=True)
    return run
