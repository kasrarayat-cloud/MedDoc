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
MODE = 'retained_live'
REVALIDATION_CONTRACT = 'retained-facts-independent-check-v1'
REVALIDATION_CONTRACTS = (REVALIDATION_CONTRACT,'retained-facts-independent-check-v2')


def need(value, message):
    if not value:
        raise ValidationError(message)


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
    need(isinstance(binding, dict) and set(binding) == {'contract', 'source_run_id',
         'source_input_digest', 'source_requests_digest', 'source_result_digest',
         'recovery_job_id', 'recovery_result_sha256', 'approved_answers_digest'}
         and binding.get('contract') == CONTRACT,
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
    stable_inputs = lambda value: {k: v for k, v in value.items()
        if k not in ('answers', 'documented_patient_name_evidence')}
    need(stable_inputs(source.inputs) == stable_inputs(run.inputs)
         and source.context == run.context and source.releases == run.releases
         and corti_prediction.payload(source) == corti_prediction.payload(run),
         'Retained output cannot cross a patient, source, date, revision, template, context or reference change.')
    expected_config = {**deepcopy(source.config), 'mode': MODE, 'max_calls': 0,
                       'retained_prediction': binding}
    need(run.config == expected_config, 'The retained prediction configuration changed.')
    from .semantic_revalidation import validate_completed
    validate_completed(job, run.inputs.get('answers'))
    need(run.result.get('retained_prediction') == binding,
         'The derived result does not retain its provenance.')
    live_receipt(source)
    return source


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
    receipt = live_receipt(source)
    inputs, context, releases, key = service.input_snapshot(e)
    old = CodingRun.objects.filter(encounter=e, input_digest=key).first()
    if old is not None:
        need(old.config.get('mode') == MODE, 'This answer snapshot already has another coding result.')
        source_for(old)
        return old
    binding = {'contract': CONTRACT, 'source_run_id': str(source.pk),
        'source_input_digest': source.input_digest, 'source_requests_digest': service.digest(source.requests),
        'source_result_digest': service.digest(source.result), 'recovery_job_id': str(recovery_job.pk),
        'recovery_result_sha256': recovery_job.result_sha256,
        'approved_answers_digest': service.digest(inputs['answers'])}
    config = {**deepcopy(source.config), 'mode': MODE, 'max_calls': 0,
              'retained_prediction': binding}
    run = CodingRun(encounter=e, user=recovery_job.user, inputs=inputs, context=context,
        releases=releases, input_digest=key, config=config, requests=[], actual_cost=Decimal('0'),
        state='needs_detail', started_at=timezone.now(), finished_at=timezone.now())
    # Validate the same identity and unchanged provider input before any result is
    # created. The new snapshot may change only independently checked answers.
    stable_inputs = lambda value: {k: v for k, v in value.items()
        if k not in ('answers', 'documented_patient_name_evidence')}
    need(stable_inputs(source.inputs) == stable_inputs(inputs) and source.user_id == run.user_id
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
