from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import secrets
import os
import httpx
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Job, Encounter, Usage, ProviderReceipt, CodeSuggestion
from .security import membership,audit,private_path
from .billing import reserve,settle,release
from . import generation

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
    path=private_path(job.input_path)
    raw=path.read_bytes()
    if len(raw)>15*1024*1024: raise ValidationError('Recording too large.')
    key=os.getenv('DEEPGRAM_API_KEY')
    if not key: raise ValidationError('Transcription provider is not connected.')
    response=httpx.post('https://api.deepgram.com/v1/listen',params={'model':'nova-3-medical','smart_format':'false'},headers={'Authorization':f'Token {key}','Content-Type':'application/octet-stream'},content=raw,timeout=90)
    response.raise_for_status()
    data=response.json()
    try:transcript=data['results']['channels'][0]['alternatives'][0]['transcript']
    except (KeyError,IndexError,TypeError):transcript=None
    duration=Decimal(str(data['metadata']['duration']))
    config=job.config or generation.configuration()
    rate=Decimal(config['voice_rate_minute'] or str(Decimal(config['voice_rate_second'])*60))
    if not duration.is_finite() or duration<0 or not rate.is_finite() or rate<0: raise ValidationError('Invalid provider usage.')
    cost=(duration*rate/60).quantize(Decimal('0.0000000001'))
    return transcript,cost,{'duration_seconds':str(duration)},{'usd_per_minute':str(rate),'cost_quantum_usd':'0.0000000001','rounding':'half_even'},'deepgram:nova-3-medical',data['metadata']['request_id'],False

def run_one():
    with transaction.atomic():
        job=Job.objects.select_for_update(skip_locked=True).filter(state='queued').order_by('created_at').first()
        if not job: return False
        try: membership(job.user,job.encounter.department)
        except Exception:
            job.state='failed'; job.error='Access was revoked before processing.'; job.finished_at=timezone.now(); job.save();release(job); return True
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
            membership(job.user,e.department)
            if e.status=='finalized' or e.revision!=job.revision: raise ValidationError('Source changed while this job ran; output was not adopted.')
            if job.kind=='generation':
                e.answers=generation.validated(result); e.status='review'
            else:
                if not isinstance(result,str):raise ValidationError('Provider supplied no usable transcript; its metered cost was retained.')
                if len(e.notes)+len(result)+2>50000: raise ValidationError('Transcription exceeds note limit. It was not truncated; reconciliation required.')
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
        job.state='failed' if known or fixture else 'reconciliation'
        job.error='Output could not be adopted; review required.' if known else 'Provider outcome is uncertain; reconcile before retrying.' if not fixture else 'Generation failed validation.'
        job.finished_at=timezone.now(); job.save(update_fields=['state','error','finished_at'])
        if fixture: release(job)
        audit(job.user,'job.'+job.state,job.pk,department=job.encounter.department,error_class=type(exc).__name__)
    return True

def mark_stale():
    for job in Job.objects.filter(state='running',started_at__lt=timezone.now()-timedelta(minutes=5)):
        with transaction.atomic():
            locked=Job.objects.select_for_update().get(pk=job.pk)
            if locked.state!='running':continue
            locked.state='reconciliation';locked.error='Worker stopped with an unknown provider outcome. Automatic retry is disabled.';locked.save(update_fields=['state','error'])
            audit(locked.user,'job.reconciliation',locked.pk)
