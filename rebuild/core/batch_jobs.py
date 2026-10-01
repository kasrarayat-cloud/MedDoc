"""One immutable attempt per batch part; only a complete form reaches a draft."""
import hashlib
import json
import os
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import generation as g, generation_batch as b, v3_mapping
from .billing import reserve, settle, release, absorb_failed_job
from .models import (Encounter, Job, ProviderReceipt, Usage, Reservation, GenerationBatch,
    GenerationBatchPart, GenerationBatchEvent, GenerationBatchResponse)
from .security import membership, audit, private_path


def pending(encounter):
    return (Job.objects.filter(encounter=encounter, state__in=['queued','running','staged','reconciliation']).exists()
            or GenerationBatch.objects.filter(encounter=encounter, state__in=b.ACTIVE).exists())


def quote(encounter, config):
    plan = b.plan_for(encounter, config)
    return {**config, 'batch_quote': {'admission_key': str(uuid.uuid4()), 'plan_sha256': b.digest(plan),
                                    'maximum_charge': plan['maximum_charge']}}, Decimal(plan['maximum_charge'])


def event(batch, kind, *, part=None, details=None):
    key = f'{batch.pk}:{part.ordinal if part else 0}:{kind}'
    return GenerationBatchEvent.objects.get_or_create(event_key=key, defaults={
        'batch': batch, 'part': part, 'kind': kind, 'details': details or {}})


@transaction.atomic
def enqueue(encounter, user, config, expected_revision=None):
    from .views import clinician_decided
    e = Encounter.objects.select_for_update().get(pk=encounter.pk)
    from .disposition_execution import require_access
    require_access(e.pk)
    membership(user, e.department)
    if e.status == 'finalized' or clinician_decided(e):
        b.refuse('A finalized or clinician-reviewed document cannot be replaced.')
    if expected_revision is not None and expected_revision != e.revision:
        b.refuse('Source notes changed after the quote.')
    completed=GenerationBatch.objects.filter(encounter=e,revision=e.revision,state='succeeded').first()
    if completed:
        job=completed.parts.order_by('ordinal').first().job;job.reused=True
        return job
    authorization = config.get('batch_quote')
    if not isinstance(authorization, dict) or set(authorization) != {'admission_key','plan_sha256','maximum_charge'}:
        b.refuse('Reload to review the complete large-form charge before submitting.')
    try: admission = uuid.UUID(authorization['admission_key'])
    except (ValueError, TypeError, AttributeError): b.refuse('Invalid batch admission identity.')
    old = GenerationBatch.objects.filter(admission_key=admission).first()
    if old:
        if old.user_id != user.pk or old.encounter_id != e.pk or old.plan_sha256 != authorization['plan_sha256']:
            b.refuse('A batch admission cannot be reused for another source or user.')
        job = old.parts.order_by('ordinal').first().job; job.reused = True
        return job
    if pending(e): b.refuse('This encounter already has a pending operation.')
    base_config = {k:v for k,v in config.items() if k != 'batch_quote'}
    if base_config != g.configuration(): b.refuse('The quoted model, mode, rate or generation contract changed.')
    if refusal := v3_mapping.generation_refusal(e.template_version): raise ValidationError(refusal)
    # ⚠️ The complete-form plan binds the whole catalogue: a field on a role place of the ORIGINAL (read now, never from
    # the stored mapping) is refused before anything is held or sent, never silently narrowed out of the plan.
    from . import destination_roles
    from documents import DocumentError
    try: held = destination_roles.v3_held(e.template_version)
    except (DocumentError, ValidationError, OSError): raise ValidationError(v3_mapping.GENERATION_SOURCE_REFUSAL) from None
    if held:
        raise ValidationError(destination_roles.GENERATION_HELD_REFUSAL.format(
            labels=', '.join(v3_mapping.label_of(f) for f in e.template_version.fields if f['key'] in held)))
    plan = b.plan_for(e, base_config)
    if b.digest(plan) != authorization['plan_sha256'] or plan['maximum_charge'] != authorization['maximum_charge']:
        b.refuse('The complete form or charge changed after the quote.')
    batch = GenerationBatch.objects.create(encounter=e, user=user, admission_key=admission, revision=e.revision,
        plan=plan, plan_sha256=b.digest(plan), maximum_charge=Decimal(plan['maximum_charge']))
    children = []
    for item in plan['parts']:
        ordinal = item['ordinal']
        snapshot = {**base_config, 'generation_part': {'batch_id':str(batch.pk), 'ordinal':ordinal,
                                                     'plan_sha256':batch.plan_sha256}}
        job = Job.objects.create(encounter=e, user=user, kind='generation_part', revision=e.revision,
            request_key=f'generation_part:{batch.pk}:{ordinal}', config=snapshot)
        GenerationBatchPart.objects.create(batch=batch,job=job,ordinal=ordinal,field_ids=item['field_ids'],
            request_sha256=item['request_sha256'], maximum_charge=Decimal(item['maximum_charge']))
        children.append(job)
    # All child rows and all wallet holds commit together. None is visible to a
    # worker until this outer transaction succeeds. reserve retains sorted locks.
    payers = set()
    for job, item in zip(children, plan['parts']):
        reserve(job, charge_limit=Decimal(item['maximum_charge']))
        job.refresh_from_db(fields=['payer']); payers.add(job.payer)
    held = sum(Reservation.objects.filter(job__in=children,state='held').values_list('amount',flat=True),Decimal(0))
    if len(payers) != 1 or held != batch.maximum_charge:
        b.refuse('The payer or complete reservation changed during admission.')
    event(batch,'admitted',details={'charge_limit':str(held),'parts':len(children),'plan_sha256':batch.plan_sha256})
    audit(user,'generation_batch.admitted',batch.pk,department=e.department,
          parts=len(children),plan_sha256=batch.plan_sha256,charge_limit=str(held))
    return children[0]


def current_plan(batch):
    from .disposition_execution import require_access
    require_access(batch.encounter_id)
    plan = batch.plan
    if b.digest(plan) != batch.plan_sha256:
        raise ValidationError('Batch plan integrity failed.')
    if plan['config'] != g.configuration():
        raise ValidationError('The model, mode, price or generation contract changed; no further part may be sent.')
    b.require_config(plan['config'])
    e = Encounter.objects.select_related('template_version__template').get(pk=batch.encounter_id)
    membership(batch.user, e.department)
    from .views import clinician_decided
    if (e.revision != batch.revision or e.status == 'finalized' or clinician_decided(e)
            or e.notes != plan['notes'] or str(e.template_version_id) != plan['mapping_version_id']
            or b.digest(e.template_version.fields) != plan['mapping_sha256']):
        raise ValidationError('The source or clinician decisions changed; no further part may be sent.')
    if refusal := v3_mapping.generation_refusal(e.template_version): raise ValidationError(refusal)
    if b.plan_constraints(e.template_version, plan['config'], live=plan['config']['mode']=='live') != plan['constraints']:
        raise ValidationError('The form-wide rules changed; no further part may be sent.')
    if list(g.source_units(plan['notes'],plan['asked'],context_labels=plan['context_labels'])[0]) != plan['units']:
        raise ValidationError('The source-unit reader changed; no part may reinterpret stored source IDs.')
    return plan


def fixture_response(plan, part):
    """Deterministic labelled fixture only; never portrayed as Sonnet evidence."""
    picks = g.fixture(plan['notes'],plan['asked'],context_labels=plan['context_labels'])
    selected = {p.key:p.quotes for p in picks.fields}
    body = {'fields':[{'key':key,'unit_ids':[u['id'] for u in plan['units'] if u['quote'] in selected[key]],
                      'conflict':False} for key in part.field_ids]}
    if plan['history_targets']:
        # No invented semantic partitions in the deterministic fixture.
        body['history_context'] = [{'key':key,'units':[{'unit_id':u['id'],'relation':'unresolved'}
                for u in plan['units']]} for key in plan['history_targets'] if key in part.field_ids]
    return {'id':'fixture_'+str(part.pk),'model':plan['config']['model'],'stop_reason':'end_turn',
            'content':[{'type':'text','text':json.dumps(body)}], 'synthetic_source':'deterministic-batch-fixture'}


def store_response(batch, part, raw, receipt, *, request_id=''):
    """Financial facts first; private result is exclusive-created and hash-bound."""
    # HTTP request identity is not included by SDK model_dump. Keep it even
    # when metering is unreadable and no financial receipt can yet be issued.
    request_id=receipt['provider_request_id'] if receipt is not None else request_id
    payload = json.dumps({'provider_output':raw,'provider_request_id':request_id},ensure_ascii=False).encode()
    path = f'receipts/{secrets.token_hex(24)}.json'; sha = hashlib.sha256(payload).hexdigest()
    with transaction.atomic():
        # The provider runs outside our locks. A stale-attempt closeout can have
        # released this hold while its one request was still returning. Record
        # that newly arrived evidence and its accounting state in one commit.
        # Keep the parent terminal: a replacement batch may already be active.
        locked=GenerationBatch.objects.select_for_update().get(pk=batch.pk)
        job=Job.objects.select_for_update().get(pk=part.job_id)
        if job.state in ('failed','cancelled') and not Usage.objects.filter(job=job).exists():
            job.state='reconciliation';job.finished_at=None
            job.error='Late provider evidence requires financial reconciliation; this attempt cannot run again.'
            job.save(update_fields=['state','finished_at','error'])
            event(locked,'late_response_recorded',part=part,details={'sha256':sha,'metering_known':receipt is not None})
        if receipt is not None:
            ProviderReceipt.objects.create(job=job,**receipt,result_path=path,result_sha256=sha)
            job.provider=receipt['provider'];job.provider_request_id=receipt['provider_request_id']
            job.provider_resource_id=receipt['provider_resource_id']
            job.result_path=path;job.result_sha256=sha
            job.save(update_fields=['provider','provider_request_id','provider_resource_id','result_path','result_sha256'])
    destination = private_path(path); destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with destination.open('xb') as out:
        destination.chmod(0o600);out.write(payload);out.flush();os.fsync(out.fileno())
    if hashlib.sha256(destination.read_bytes()).hexdigest() != sha:
        raise ValidationError('Recorded batch response integrity failed.')
    with transaction.atomic():
        GenerationBatchResponse.objects.create(part=part,result_path=path,result_sha256=sha,
            model=str(raw.get('model','')),stop_reason=str(raw.get('stop_reason','')),
            provider_resource_id=str(raw.get('id','')))
        if receipt is None:
            job.provider=f"anthropic:{batch.plan['config']['model']}";job.provider_request_id=request_id
            job.provider_resource_id=str(raw.get('id',''))
            job.result_path=path;job.result_sha256=sha
            job.save(update_fields=['provider','provider_request_id','provider_resource_id','result_path','result_sha256'])
        event(batch,'response_recorded',part=part,details={'sha256':sha})


def read_response(part):
    response = part.response
    data = private_path(response.result_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != response.result_sha256:
        raise ValidationError('Stored response hash mismatch; no answers adopted.')
    raw = json.loads(data)['provider_output']
    if (response.result_path != part.job.result_path or response.result_sha256 != part.job.result_sha256
            or raw.get('model') != response.model or raw.get('stop_reason') != response.stop_reason
            or str(raw.get('id','')) != response.provider_resource_id):
        raise ValidationError('Stored child response identity mismatch.')
    return raw


@transaction.atomic
def stop(batch_id, reason, *, uncertain_part=None, user_declined=False):
    batch=GenerationBatch.objects.select_for_update().get(pk=batch_id)
    if batch.state in ('succeeded','cancelled','failed','not_adopted'):return
    parts=list(batch.parts.select_related('job').order_by('ordinal'))
    for part in parts:
        job=Job.objects.select_for_update().get(pk=part.job_id)
        # A send intent with durable proof that its request was never transmitted (MONEY-2) is not a send.
        sent=(part.events.filter(kind='send_intent').exists()
              and not part.events.filter(kind='not_transmitted').exists())
        known=Usage.objects.filter(job=job).exists()
        if job.state=='succeeded':continue
        # Explicitly resolved attempts stay consumed. Their immutable evidence
        # remains, but absence of Usage is valid for no-cost/platform-only
        # closeout. A late receipt explicitly reopens the child above instead.
        if job.state=='failed' and part.events.filter(kind='financially_resolved').exists():continue
        if (uncertain_part==part.pk or (sent and not known)):
            job.state='reconciliation';job.error='Batch request outcome requires reconciliation; it will not be sent again.'
        else:
            job.state='failed' if sent else 'cancelled'
            job.error=('not_adopted: ' if user_declined else 'platform_failure: ')+reason if sent else 'Batch stopped before this part was sent.'
            job.finished_at=timezone.now()
            if not sent:release(job)
        job.save(update_fields=['state','error','finished_at'])
        if known and job.state=='failed' and not user_declined:absorb_failed_job(job)
        event(batch,'stopped',part=part,details={'state':job.state,'sent':sent})
    unresolved=Job.objects.filter(generation_part__batch=batch,state='reconciliation').exists()
    batch.state='reconciliation' if unresolved else 'not_adopted' if user_declined else 'failed'
    batch.error=reason[:250];batch.finished_at=None if unresolved else timezone.now()
    batch.save(update_fields=['state','error','finished_at'])
    event(batch,'stopped',details={'state':batch.state})


def finish(batch_id):
    from .disposition import require_processing
    require_processing()
    batch=GenerationBatch.objects.get(pk=batch_id)
    from .disposition_execution import require_access
    require_access(batch.encounter_id)
    parts=list(batch.parts.select_related('job','response').order_by('ordinal'))
    if len(parts)!=len(batch.plan['parts']) or any(p.job.state!='staged' for p in parts):return False
    # Complete clinical validation precedes user-declined billing classification.
    try:
        if b.digest(batch.plan)!=batch.plan_sha256:raise ValidationError('Batch plan integrity failed.')
        if any(not Usage.objects.filter(job=p.job).exists() for p in parts):
            raise ValidationError('Every child settlement must be recorded before adoption.')
        # The original is checked before every send and once more before the
        # whole result becomes a draft; an intact last request is not proof of
        # the original at adoption time.
        if refusal := v3_mapping.generation_refusal(batch.encounter.template_version):
            raise ValidationError(refusal)
        answers,review=b.assemble(batch.plan,[read_response(p) for p in parts],
                                  read_options=b.option_reader(batch.encounter.template_version))
    except Exception:
        stop(batch.pk,'The complete form failed validation; no partial answers were adopted.')
        return True
    declined=reconfigured=False
    with transaction.atomic():
        e=Encounter.objects.select_for_update().get(pk=batch.encounter_id)
        batch=GenerationBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.state not in ('running','validating'):return True
        # QuillMD's own configuration is judged FIRST and is never the user's decision (MONEY-1). A flag, rate, profile
        # or mode change cannot activate a staged contract after withdrawal, so the complete output is discarded; that
        # discard is ours, so it is a platform failure and every settled part is absorbed, exactly as the same change
        # one step earlier (current_plan, between parts) already is. It also wins over a simultaneous user-side change:
        # our change alone made the output unusable, and our own change is never billed.
        reconfigured=batch.plan['config']!=g.configuration()
        if not reconfigured:
            from .views import clinician_decided
            try:membership(batch.user,e.department)
            except PermissionDenied:declined=True
            declined=declined or e.status=='finalized' or e.revision!=batch.revision or clinician_decided(e)
            declined=declined or e.notes!=batch.plan['notes'] or str(e.template_version_id)!=batch.plan['mapping_version_id']
            if not declined:
                e.answers=answers;e.template_review=review;e.status='review';e.save(update_fields=['answers','template_review','status'])
                batch.state='succeeded';batch.finished_at=timezone.now();batch.save(update_fields=['state','finished_at'])
                Job.objects.filter(generation_part__batch=batch,state='staged').update(state='succeeded',finished_at=timezone.now())
                event(batch,'adopted',details={'answers_sha256':b.digest(answers),'revision':e.revision})
                audit(batch.user,'generation_batch.adopted',batch.pk,department=e.department,parts=len(parts))
    if reconfigured:stop(batch.pk,'The model, mode, price or generation configuration changed; the complete output was not adopted.')
    elif declined:stop(batch.pk,'The source, authorization or clinical decisions changed; the complete output was not adopted.',user_declined=True)
    return True


def run_one():
    from .disposition import require_processing
    require_processing()
    with transaction.atomic():
        batch=GenerationBatch.objects.select_for_update(skip_locked=True).filter(state__in=['queued','running','validating']).order_by('created_at').first()
        if not batch:return False
        from .disposition_execution import require_access
        require_access(batch.encounter_id)
        if batch.parts.filter(job__state='running').exists():return False
        part=batch.parts.select_related('job').filter(job__state='queued').order_by('ordinal').first()
        if part:
            # A later child never overtakes an earlier unresolved/still processing child.
            if batch.parts.filter(ordinal__lt=part.ordinal).exclude(job__state='staged').exists():return False
            job=Job.objects.select_for_update().get(pk=part.job_id)
            job.state='running';job.started_at=timezone.now();job.save(update_fields=['state','started_at'])
            batch.state='running';batch.save(update_fields=['state'])
            event(batch,'claimed',part=part)
        else:
            batch.state='validating';batch.save(update_fields=['state'])
    if not part:return finish(batch.pk)
    sent=False
    try:
        plan=current_plan(batch)
        wire=b.request(plan,part.ordinal)
        if b.digest(wire)!=part.request_sha256:raise ValidationError('Compiled request no longer matches the held request.')
        from .jobs import sandbox_hold
        if sandbox_hold(job):raise ValidationError('The held funds are ineligible for this data mode.')
        held=sum(job.reservations.filter(state='held').values_list('amount',flat=True),Decimal(0))
        if held!=part.maximum_charge:raise ValidationError('The complete child charge is not held.')
        live=plan['config']['mode']=='live'
        if live:
            from anthropic import Anthropic
            client=Anthropic(timeout=plan['config']['request_profile']['timeout_seconds'],max_retries=0)
        with transaction.atomic():
            locked=GenerationBatch.objects.select_for_update().get(pk=batch.pk)
            current=Job.objects.select_for_update().get(pk=job.pk)
            if locked.state!='running' or current.state!='running':raise ValidationError('This child is no longer eligible to send.')
            if part.events.filter(kind='send_intent').exists():raise ValidationError('This provider attempt was already consumed.')
            event(batch,'send_intent',part=part,details={'request_sha256':part.request_sha256})
        sent=True
        if live:
            response=client.messages.create(**wire)
            raw=response.model_dump(mode='json')
            try:
                cost,units,rates=g.anthropic_settlement(response,g.rates(plan['config']),plan['config'])
            except Exception:
                store_response(batch,part,raw,None,request_id=getattr(response,'_request_id',None) or '')
                raise
            receipt={'provider':f"anthropic:{plan['config']['model']}",'provider_request_id':getattr(response,'_request_id',None) or '',
                'provider_resource_id':getattr(response,'id','') or '', 'actual_cost':cost,'units':units,'rates':rates,'simulated':False}
        else:
            raw=fixture_response(plan,part)
            receipt={'provider':'synthetic-batch-fixture','provider_request_id':'','provider_resource_id':'',
                     'actual_cost':Decimal(0),'units':{},'rates':{},'simulated':True}
        store_response(batch,part,raw,receipt)
        settle(job,receipt['actual_cost'],receipt['units'],receipt['rates'],receipt['provider'],
               receipt['provider_request_id'],receipt['simulated'],provider_resource_id=receipt['provider_resource_id'])
        b.parse_part(plan,part.ordinal,raw)
        with transaction.atomic():
            locked=GenerationBatch.objects.select_for_update().get(pk=batch.pk)
            current=Job.objects.select_for_update().get(pk=job.pk)
            if locked.state!='running':raise ValidationError('The batch stopped before this response could be staged.')
            current.state='staged';current.save(update_fields=['state'])
            event(batch,'staged',part=part,details={'result_sha256':current.result_sha256})
    except Exception as error:
        event(batch,'part_failed',part=part,details={'error_class':type(error).__name__})
        known=Usage.objects.filter(job=job).exists()
        from .jobs import never_transmitted
        untransmitted=sent and not known and never_transmitted(error)
        if untransmitted:
            # The send intent is consumed, but the SDK refused while BUILDING the request (no credential): nothing
            # left (MONEY-2). The durable evidence makes stop() treat this child as unsent: cancelled, hold released.
            event(batch,'not_transmitted',part=part,details={'error_class':type(error).__name__,
                                                            'proof':'provider SDK request build'})
        stop(batch.pk,'A batch part failed or needs reconciliation; no partial form was adopted.',
             uncertain_part=part.pk if sent and not known and not untransmitted else None)
    return True


def mark_stale():
    for part in GenerationBatchPart.objects.filter(job__state='running',job__started_at__lt=timezone.now()-timedelta(minutes=5)):
        if part.batch.parts.filter(response__isnull=True).exists() is False:
            # Every request returned durably. Hold for an explicit local-only
            # recovery; do not discard evidence or automatically adopt it.
            with transaction.atomic():
                batch=GenerationBatch.objects.select_for_update().get(pk=part.batch_id)
                job=Job.objects.select_for_update().get(pk=part.job_id)
                if job.state!='running':continue
                job.state='reconciliation';job.error='All responses are recorded; an administrator must verify local recovery.'
                job.save(update_fields=['state','error'])
                batch.state='reconciliation';batch.error=job.error;batch.save(update_fields=['state','error'])
                event(batch,'local_recovery_required',part=part)
            continue
        stop(part.batch_id,'An interrupted batch requires reconciliation; no request is automatically repeated.',
             uncertain_part=part.pk if part.events.filter(kind='send_intent').exists() else None)


@transaction.atomic
def cancel_child(job,user):
    from .jobs import CancellationRefused
    part=GenerationBatchPart.objects.get(job_id=job.pk)
    batch=GenerationBatch.objects.select_for_update().get(pk=part.batch_id)
    membership(user,batch.department,roles=None if batch.user_id==user.pk else ['owner','clinician'])
    if batch.events.filter(kind='send_intent').exists() or batch.state!='queued':
        raise CancellationRefused('This complete-form request has started; resolve its outcome before another request.')
    stop(batch.pk,'Cancelled before any batch part was sent.')
    batch.refresh_from_db();batch.state='cancelled';batch.save(update_fields=['state'])
    event(batch,'cancelled')


def require_admin(user):
    from .retention import custodian
    custodian(user)


def resolve_view(request,job_id):
    """Explicit financial closeout; consumed identities remain consumed forever."""
    from django.http import HttpResponse
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages
    from .forms import JobResolutionForm
    from .models import PlatformCost
    require_admin(request.user)
    part=get_object_or_404(GenerationBatchPart,job_id=job_id)
    form=JobResolutionForm(request.POST)
    if not form.is_valid():raise ValidationError('A complete provider-evidence resolution is required.')
    data=form.cleaned_data
    with transaction.atomic():
        batch=GenerationBatch.objects.select_for_update().get(pk=part.batch_id)
        job=Job.objects.select_for_update().get(pk=part.job_id)
        if job.state!='reconciliation':return HttpResponse('Only unresolved batch attempts may be reconciled.',status=409)
        receipt=ProviderReceipt.objects.filter(job=job).first()
        if receipt and not Usage.objects.filter(job=job).exists():
            if job.reservations.filter(state='held').exists():
                # An administrator settles the held attempt (then absorbs it below): the one settlement of a job that is
                # not running (core.billing.SETTLEABLE_STATES), named here.
                settle(job,receipt.actual_cost,receipt.units,receipt.rates,receipt.provider,
                       receipt.provider_request_id,receipt.simulated,provider_resource_id=receipt.provider_resource_id,
                       allowed_states=('reconciliation',))
            else:
                # Never recreate a released grant or debit a replacement hold.
                # The original receipt remains authoritative; this separate
                # platform expense carries no fabricated customer Usage row.
                cost,created=PlatformCost.objects.get_or_create(job=job,kind='absorbed_failure',defaults={
                    'amount':receipt.actual_cost,'description':'Late provider receipt after released authorization',
                    'evidence_reference':f'receipt:{receipt.pk} '+data['evidence_note'][:180],
                    'recorded_by':request.user})
                if cost.amount!=receipt.actual_cost:
                    raise ValidationError('Late provider evidence conflicts with the previously recorded platform cost; independent financial reconciliation is required.')
        release(job)
        job.state='failed';job.error='platform_failure: Batch attempt resolved by an administrator; no request was repeated.'
        job.finished_at=timezone.now();job.save(update_fields=['state','error','finished_at'])
        if Usage.objects.filter(job=job).exists():
            absorb_failed_job(job,actor=request.user,note=data['evidence_note'])
        elif data['outcome']=='absorb_platform_failure' and receipt is None:
            cost,created=PlatformCost.objects.get_or_create(job=job,kind='absorbed_failure',defaults={
                'amount':data['actual_cost'],'description':'Uncertain batch outcome resolved as platform cost',
                'evidence_reference':data['evidence_note'],'recorded_by':request.user})
            if cost.amount!=data['actual_cost']:
                raise ValidationError('New evidence conflicts with the previously recorded platform cost; independent financial reconciliation is required.')
        late=part.events.filter(kind='late_response_recorded').exists()
        event(batch,'late_financially_resolved' if late else 'financially_resolved',part=part,
              details={'outcome':data['outcome'],'actor':str(request.user.pk),
                       'evidence_note':data['evidence_note'],'receipt_id':str(receipt.pk) if receipt else None})
        # A financial closeout abandons the entire clinical result. Close/refund
        # prior staged children too; retain every unknown sibling for its own
        # explicit evidence resolution. stop never revives a terminal parent.
        stop(batch.pk,'An administrator resolved a failed batch; no partial form was adopted.')
        audit(request.user,'generation_batch.reconciled',batch.pk,department=batch.department,part=part.ordinal)
    messages.success(request,'Provider evidence recorded and held funds resolved. This attempt cannot be sent again.')
    return redirect('/console/#jobs')


def recover_recorded(batch_id,user):
    """Explicit administrator recovery of ALL durable responses, never network I/O.

    Partial/unknown attempts and already absorbed outcomes cannot be revived. The
    original per-request records, source, rates and ceilings remain authoritative.
    """
    from .disposition import require_processing
    require_processing()
    require_admin(user)
    with transaction.atomic():
        batch=GenerationBatch.objects.select_for_update().get(pk=batch_id)
        if batch.state!='reconciliation':raise ValidationError('Only an interrupted recorded batch needs recovery.')
        current_plan(batch)
        parts=list(batch.parts.select_related('job','response').order_by('ordinal'))
        if (len(parts)!=len(batch.plan['parts']) or any(p.job.state not in ('staged','reconciliation','running') for p in parts)
                or any(not hasattr(p,'response') for p in parts)):
            raise ValidationError('This batch contains an unknown, cancelled or consumed failure; no recovery is possible.')
        # Validate every file and the complete result before touching any hold.
        b.assemble(batch.plan,[read_response(p) for p in parts],
                   read_options=b.option_reader(batch.encounter.template_version))
        for part in parts:
            job=Job.objects.select_for_update().get(pk=part.job_id)
            receipt=ProviderReceipt.objects.get(job=job)
            # An administrator's explicit recovery of durable responses: the states the check above admits.
            settle(job,receipt.actual_cost,receipt.units,receipt.rates,receipt.provider,
                   receipt.provider_request_id,receipt.simulated,provider_resource_id=receipt.provider_resource_id,
                   allowed_states=('staged','reconciliation','running'))
            job.state='staged';job.save(update_fields=['state'])
            event(batch,'recovered_locally',part=part,details={'actor':str(user.pk)})
        batch.state='validating';batch.error='';batch.save(update_fields=['state','error'])
    return finish(batch.pk)
