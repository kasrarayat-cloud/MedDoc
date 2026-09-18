from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import secrets
import os
import httpx
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Job, Encounter, Usage, ProviderReceipt, CodeSuggestion
from .security import membership,audit,private_path
from .billing import reserve,settle,release,absorb_failed_job
from . import generation


class NotAdoptedByUser(ValidationError):
    """A successful, user-requested generation whose output the user's own state kept from adoption. It stays billable."""


class PlatformFailure(ValidationError):
    """A post-settlement failure QuillMD absorbs. Its message is a fixed, non-clinical string that is safe to display."""


class CancellationRefused(ValidationError):
    """The job is past the point where cancellation is free; the message is the one-line reason."""


class NoProviderRequest(ValidationError):
    """Raised before any provider request is made: nothing billable happened, so the held funds are released."""


# Billing boundary (docs/rebuild/cost-definition.md, "Billing boundary"): a job.error prefix is the billing classification.
NOT_ADOPTED='not_adopted: '
PLATFORM_FAILURE='platform_failure: '
NOT_PROCESSED='Not processed: '
CANCELLED_ERROR='cancelled: before any provider request'
CANCEL_REFUSALS={'running':'Processing already started; the outcome will be billed by result.',
    'succeeded':'This request already completed; its successful generation remains charged.',
    'failed':'This request already ended; nothing is queued to cancel.',
    'reconciliation':'This request is held for reconciliation; an administrator resolves it.',
    'cancelled':'This request was already cancelled.'}


def ended_key(job,label):
    """Free the request key of a job that ended without success so a fresh request for the same revision is accepted; the ended
    row keeps its history under a key only it can hold. Longest key today is transcription (115 chars) + 43 = 158 of 160."""
    return f'{job.request_key}:{label}:{job.pk.hex}'


def public_error(job):
    """What the doctor reads about a job: the billing classification in words, never the internal prefix."""
    error=job.error or ''
    if error.startswith(NOT_ADOPTED): return error[len(NOT_ADOPTED):]
    if error.startswith(PLATFORM_FAILURE): return error[len(PLATFORM_FAILURE):]+' This was a platform failure; it is not charged to you.'
    if error==CANCELLED_ERROR: return 'Cancelled before any provider request; nothing was charged.'
    return error


def billable_outcome(job):
    """A job whose provider usage stands charged: a success, or a success the user's own state kept from adoption."""
    return job.state=='succeeded' or (job.state=='failed' and (job.error or '').startswith(NOT_ADOPTED))


def may_cancel(job,user):
    """Same rule jobs.cancel enforces: the requester, or an owner or clinician of the department."""
    if job.state!='queued': return False
    try: membership(user,job.encounter.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
    except PermissionDenied: return False
    return True


def failure_reason(exc):
    """Display text for a post-settlement failure. Only QuillMD's own fixed messages are shown; any other exception is named by class,
    because provider or validation messages can quote the source text."""
    if isinstance(exc,(NotAdoptedByUser,PlatformFailure,NoProviderRequest)): return '; '.join(exc.messages)
    return f'Output could not be adopted ({type(exc).__name__}); review required.'


@transaction.atomic
def enqueue(encounter,user,kind='generation',input_path='',config=None):
    e=Encounter.objects.select_for_update().get(pk=encounter.pk)
    membership(user,e.department)
    if e.status=='finalized': raise ValidationError('Finalized documents are immutable.')
    fingerprint=hashlib.sha256(private_path(input_path).read_bytes()).hexdigest() if kind=='transcription' else str(e.revision)
    key=f'{kind}:{e.pk}:{fingerprint}'
    old=Job.objects.filter(request_key=key).first()
    if old: return old
    if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists(): raise ValidationError('This encounter already has a pending job.')
    job=Job.objects.create(encounter=e,user=user,kind=kind,revision=e.revision,request_key=key,input_path=input_path,config=config or generation.configuration())
    max_cost=generation.maximum_cost(e.notes,e.template_version.fields,job.config,context_labels=[row['label'] for row in e.template_version.review_requirements]) if kind=='generation' else Decimal(job.config['voice_max_cost'])
    if kind=='transcription' and not (job.config['voice_rate_minute'] or job.config['voice_rate_second']): raise ValidationError('Transcription usage rates have not been configured.')
    reserve(job,max_cost)
    audit(user,'job.queued',job.pk,department=e.department,kind=kind)
    return job

def transcribe(job):
    # Everything before httpx.post raises NoProviderRequest: no provider request was made, so nothing is billable.
    try: raw=private_path(job.input_path).read_bytes()
    except (OSError,ValueError): raise NoProviderRequest('The recording is not available.') from None
    if len(raw)>15*1024*1024: raise NoProviderRequest('Recording too large.')
    key=os.getenv('DEEPGRAM_API_KEY')
    if not key: raise NoProviderRequest('Transcription provider is not connected.')
    response=httpx.post('https://api.deepgram.com/v1/listen',params={'model':'nova-3-medical','smart_format':'false'},headers={'Authorization':f'Token {key}','Content-Type':'application/octet-stream'},content=raw,timeout=90)
    response.raise_for_status()
    data=response.json()
    try:transcript=data['results']['channels'][0]['alternatives'][0]['transcript']
    except (KeyError,IndexError,TypeError):transcript=None
    duration=Decimal(str(data['metadata']['duration']))
    config=job.config or generation.configuration()
    rate=Decimal(config['voice_rate_minute'] or str(Decimal(config['voice_rate_second'])*60))
    if not duration.is_finite() or duration<0 or not rate.is_finite() or rate<0: raise ValidationError('Invalid provider usage.')
    list_cost=(duration*rate/60).quantize(Decimal('0.0000000001'))
    discount=generation.discount_rate(config);cost=generation.discounted_cost(list_cost,discount)
    rates=generation.cost_rates({'usd_per_minute':rate,'cost_quantum_usd':'0.0000000001','rounding':'half_even'},list_cost,discount)
    return transcript,cost,{'duration_seconds':str(duration)},rates,'deepgram:nova-3-medical',data['metadata']['request_id'],False

def run_one():
    with transaction.atomic():
        job=Job.objects.select_for_update(skip_locked=True).filter(state='queued').order_by('created_at').first()
        if not job: return False
        try: membership(job.user,job.encounter.department)
        except Exception:
            job.state='failed'; job.error='Access was revoked before processing.'; job.finished_at=timezone.now(); job.request_key=ended_key(job,'failed'); job.save();release(job); return True
        job.state='running';job.started_at=timezone.now();job.save(update_fields=['state','started_at'])
    provider_returned=False
    try:
        e=job.encounter
        result,cost,units,rates,provider,request_id,simulated=generation.generate(e.notes,e.template_version.fields,job.config,context_labels=[row['label'] for row in e.template_version.review_requirements]) if job.kind=='generation' else transcribe(job)
        provider_returned=True
        response=(result.get('anthropic_response') or result.get('response')) if isinstance(result,dict) else None
        resource_id=getattr(response,'id','') or ''
        # Financial evidence commits before any clinical serialization or file IO.
        with transaction.atomic():
            ProviderReceipt.objects.get_or_create(job=job,defaults={'provider':provider,'provider_request_id':request_id,'provider_resource_id':resource_id,'actual_cost':cost,'units':units,'rates':rates,'simulated':simulated})
            job.provider=provider;job.provider_request_id=request_id;job.provider_resource_id=resource_id;job.save(update_fields=['provider','provider_request_id','provider_resource_id'])
            audit(job.user,'provider.receipt',job.pk,department=e.department,provider=provider,request_id=request_id,resource_id=resource_id,actual_cost=str(cost))
        if job.kind=='transcription': saved={'transcript':result}
        elif isinstance(result,dict) and 'anthropic_response' in result:
            saved={'provider_output':result['anthropic_response'].model_dump(mode='json')}
        elif isinstance(result,dict) and 'response' in result:
            saved={'provider_output':result['response'].model_dump(mode='json')}
        else:saved={'answers':result}
        result_path=f'receipts/{secrets.token_hex(24)}.json'
        path=private_path(result_path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        payload=json.dumps(saved,ensure_ascii=False).encode()
        with path.open('xb') as file:path.chmod(0o600);file.write(payload)
        job.result_path=result_path;job.result_sha256=hashlib.sha256(payload).hexdigest();job.save(update_fields=['result_path','result_sha256'])
        # Settling provider cost is independent of clinical acceptance: invalid answers are never adopted.
        settle(job,cost,units,rates,provider,request_id,simulated,provider_resource_id=resource_id)
        with transaction.atomic():
            e=Encounter.objects.select_for_update().get(pk=e.pk)
            # Output QuillMD cannot use is a platform failure whatever the user did meanwhile, so it is checked first and absorbed.
            if job.kind=='generation': answers=generation.validated(result)
            elif not isinstance(result,str): raise PlatformFailure('Provider supplied no usable transcript.')
            # Usable output that the user's own state (finalized, edited, access revoked) declines is not a platform failure:
            # NotAdoptedByUser keeps the settled charge.
            try: membership(job.user,e.department)
            except PermissionDenied: raise NotAdoptedByUser('Access was revoked before the output could be adopted; its recorded usage stays billed.')
            if e.status=='finalized' or e.revision!=job.revision: raise NotAdoptedByUser('Source changed while this job ran; output was not adopted. Its recorded usage stays billed.')
            if job.kind=='generation':
                e.answers=answers; e.status='review'
            else:
                if len(e.notes)+len(result)+2>50000: raise PlatformFailure('Transcription exceeds the note limit; nothing was truncated.')
                e.notes+='\n\n'+result; e.answers={}; e.status='draft'; e.revision+=1
                CodeSuggestion.objects.filter(encounter=e).delete()
                audit(job.user,'coding.invalidated_by_transcription',e.pk,department=e.department)
            e.template_review={}
            e.save()
            job.state='succeeded';job.provider=provider;job.provider_request_id=request_id;job.finished_at=timezone.now();job.save()
            audit(job.user,'job.succeeded',job.pk,department=e.department,kind=job.kind)
    except Exception as exc:
        # A timeout can be billable. Never retry it or release its reservation as if cost were known.
        known=Usage.objects.filter(job=job).exists()
        fixture=job.kind=='generation' and job.config.get('mode',settings.AI_MODE)!='live'
        declined=known and isinstance(exc,NotAdoptedByUser)
        unsent=not known and not provider_returned and isinstance(exc,NoProviderRequest)
        job.state='failed' if known or fixture or unsent else 'reconciliation'
        # After settlement the error prefix is the billing classification audit_billing reads: not_adopted stays charged, platform_failure is absorbed.
        if known: job.error=((NOT_ADOPTED if declined else PLATFORM_FAILURE)+failure_reason(exc))[:250]
        elif unsent: job.error=(NOT_PROCESSED+failure_reason(exc)+' No provider request was made; nothing was charged and the held funds were released.')[:250]
        elif fixture: job.error='Generation failed validation.'
        elif ProviderReceipt.objects.filter(job=job).exists():
            # The provider completed and its receipt is durable; only settlement failed (for example cost above the held maximum).
            job.error='Provider completed, but settlement needs administrator reconciliation; nothing is charged until it is resolved.'
        else: job.error='Provider outcome is uncertain; reconcile before retrying.'
        job.finished_at=timezone.now()
        fields=['state','error','finished_at']
        if job.state=='failed': job.request_key=ended_key(job,'failed'); fields.append('request_key')
        if fixture or unsent:
            # One transaction: a job never reads 'held funds were released' while its hold is still held. If the release
            # fails, the job stays 'running', mark_stale moves it to reconciliation and the audit lists it as unresolved.
            with transaction.atomic():
                job.save(update_fields=fields); release(job)
        else: job.save(update_fields=fields)
        # Released above (fixture, not processed), or a successful generation the user did not adopt: it remains billable,
        # with no reversal and no platform cost.
        if fixture or unsent or declined: pass
        # Settled provider cost whose output was never adopted is a platform failure: QuillMD absorbs it and reverses the user's charge.
        elif known:
            try: absorb_failed_job(job)
            except Exception as absorb_error:
                # The failed job state is already durable; a failed reversal must never stop the worker. audit_billing flags settled-but-unabsorbed failures.
                audit(job.user,'usage.absorb_failed',job.pk,department=job.encounter.department,error_class=type(absorb_error).__name__)
        audit(job.user,'job.'+job.state,job.pk,department=job.encounter.department,error_class=type(exc).__name__,
              billing='not_adopted' if declined else 'platform_failure' if known and not fixture else 'fixture' if fixture else 'not_processed' if unsent else 'uncertain')
    return True


@transaction.atomic
def cancel(job,user):
    """Cancel a queued request before any provider request. The row lock is the same one run_one takes with skip_locked, so a job
    being picked up is never cancelled and a job being cancelled is never picked up. Held reservations are released; nothing is charged."""
    # Lock the job row only: locking the encounter or department too would invert run_one's encounter-then-job order and deadlock.
    job=Job.objects.select_for_update(of=('self',)).select_related('encounter__department').get(pk=job.pk)
    # The requester may cancel their own queued request; anyone else needs a clinician or owner role in the department.
    membership(user,job.encounter.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
    if job.state!='queued': raise CancellationRefused(CANCEL_REFUSALS.get(job.state,'This request can no longer be cancelled.'))
    job.state='cancelled';job.error=CANCELLED_ERROR;job.finished_at=timezone.now()
    job.request_key=ended_key(job,'cancelled')
    job.save(update_fields=['state','error','finished_at','request_key'])
    release(job)
    audit(user,'job.cancelled',job.pk,department=job.encounter.department,kind=job.kind)
    return job

def mark_stale():
    for job in Job.objects.filter(state='running',started_at__lt=timezone.now()-timedelta(minutes=5)):
        with transaction.atomic():
            locked=Job.objects.select_for_update().get(pk=job.pk)
            if locked.state!='running':continue
            locked.state='reconciliation';locked.error='Worker stopped with an unknown provider outcome. Automatic retry is disabled.';locked.save(update_fields=['state','error'])
            audit(locked.user,'job.reconciliation',locked.pk)
