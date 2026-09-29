"""Template-scoped mapping queue using the existing wallet, receipt and ledger lifecycle."""
import hashlib
import json
import secrets
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from . import generation, mapping_assistance as mapping
from .billing import reserve, release, settle, sandbox_hold, absorb_failed_job
from .models import Job, Template, TemplateVersion, ProviderReceipt, Usage
from .security import private_path, membership, audit

def enabled():
    return bool(getattr(settings,'QUILLMD_MAPPING_ASSISTANCE',False))

def permission(config,*,queued=False):
    from .jobs import NoProviderRequest
    if not enabled():raise NoProviderRequest('Mapping assistance is disabled.')
    # This must precede the current compiler: old queued contracts are never replayed
    # through a new schema and reservations must be released as definitely unsent.
    if queued and config.get('mapping_contract')!=mapping.VERSION:
        raise NoProviderRequest('Mapping contract changed. Review a fresh quote; nothing was sent.')
    mapping.request_profile(config)
    generation.refuse_switched_mode(config)
    current=generation.configuration()
    if config.get('pricing_version')!=current['pricing_version']:
        raise NoProviderRequest('Mapping profile or pricing changed. Review a fresh quote.')
    if config['mode']=='live' and not getattr(settings,'QUILLMD_MAPPING_ASSISTANCE_LIVE',False):
        raise NoProviderRequest('Live mapping has not been admitted. No provider request was made.')

@transaction.atomic
def enqueue(version,user,config,request_sha256):
    permission(config)
    template=Template.objects.select_for_update().get(pk=version.template_id)
    membership(user,template.department,roles=['owner','clinician','manager'])
    if template.versions.order_by('-number').first().pk!=version.pk:
        raise ValidationError('Mapping version changed. Review the current version first.')
    compiled=mapping.compile_request(version,config)
    if compiled['request_sha256']!=request_sha256:raise ValidationError('The quoted blank-source request changed.')
    key=f'mapping:{version.pk}:{compiled["request_sha256"]}'
    old=Job.objects.filter(request_key=key).first()
    if old:return old
    if Job.objects.filter(mapping_version__template=template,state__in=['queued','running','reconciliation']).exists():
        raise ValidationError('This template already has a pending mapping operation.')
    config={**config,'source_sha256':template.sha256,'department_id':str(template.department_id),
            'mapping_version_id':str(version.pk),'mapping_contract':mapping.VERSION,
            'mapping_request_profile':compiled['profile'],'mapping_profile_sha256':compiled['profile_sha256'],
            'request_sha256':compiled['request_sha256'],'input_token_bound':compiled['input_token_bound'],
            'mapping_maximum_cost':compiled['maximum_cost']}
    job=Job.objects.create(mapping_version=version,user=user,kind='mapping',request_key=key,config=config)
    reserve(job,Decimal(compiled['maximum_cost']) if config['mode']=='live' else Decimal(0))
    audit(user,'mapping.queued',job.pk,department=template.department,version=str(version.pk),request_sha256=compiled['request_sha256'])
    return job

def send(compiled,config):
    """One native request, no retries. Called only after runtime/profile/hold admission."""
    if config['mode']!='live':
        payload=json.loads(compiled['request']['messages'][0]['content'])
        # The fixture makes no semantic judgement. Every unmapped place stays visibly unresolved.
        body=mapping.wire.fixture(payload)
        return body,Decimal(0),{}, {},'synthetic-mapping-fixture','','',True
    from .jobs import NoProviderRequest
    try:
        from anthropic import Anthropic
        profile=mapping.request_profile(config)
        client=Anthropic(timeout=profile['timeout_seconds'],max_retries=0)
    except Exception as exc:
        # No transport call exists before this boundary. A definite local failure
        # must not strand a reservation as an unknown provider outcome.
        raise NoProviderRequest('Mapping request setup failed before submission.') from exc
    # Exceptions from create itself remain unknown: the provider may have received it.
    response=client.messages.create(**compiled['request'])
    rates=generation.rates(config);provider=f"anthropic:{config['model']}"
    cost,units,recorded=generation.anthropic_settlement(response,rates,config)
    units['response_model']=getattr(response,'model','')
    return response,cost,units,recorded,provider,getattr(response,'_request_id','') or '',getattr(response,'id','') or '',False

def parse_response(raw,simulated):
    if simulated:return raw
    if getattr(raw,'model',None)!=generation.SONNET_5 or getattr(raw,'stop_reason',None)!='end_turn':
        raise ValidationError('Mapping response model differs, was refused or was incomplete.')
    if any(getattr(block,'type','')=='refusal' for block in raw.content):
        raise ValidationError('Provider refused mapping assistance.')
    texts=[block.text for block in raw.content if getattr(block,'type','')=='text']
    if len(texts)!=1:raise ValidationError('Mapping response needs exactly one complete JSON text block.')
    def unique_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValidationError('Mapping response contains duplicate JSON members.')
            result[key]=value
        return result
    return json.loads(texts[0],object_pairs_hook=unique_pairs)

def run_one():
    from .disposition import require_processing
    require_processing()
    from .jobs import NoProviderRequest, NotAdoptedByUser
    with transaction.atomic():
        job=Job.objects.select_for_update(skip_locked=True).filter(kind='mapping',state='queued').order_by('created_at').first()
        if not job:return False
        job.state='running';job.started_at=timezone.now();job.save(update_fields=['state','started_at'])
    sent=False;returned=False;settling=False;carrier=None
    try:
        permission(job.config,queued=True)
        try:membership(job.user,job.department,roles=['owner','clinician','manager'])
        except PermissionDenied as exc:raise NoProviderRequest('Access revoked before mapping.') from exc
        if sandbox_hold(job):raise NoProviderRequest('Sandbox funds cannot fund real-mode mapping.')
        version=job.mapping_version
        compiled=mapping.compile_request(version,job.config)
        if compiled['request_sha256']!=job.config['request_sha256']:
            raise NoProviderRequest('Mapping source, compiler or request changed after quotation.')
        if version.template.versions.order_by('-number').first().pk!=version.pk:
            raise NoProviderRequest('Mapping was edited before the request began.')
        sent=job.config['mode']=='live'
        raw,cost,units,rates,provider,request_id,resource_id,simulated=send(compiled,job.config)
        returned=True
        with transaction.atomic():
            ProviderReceipt.objects.create(job=job,provider=provider,provider_request_id=request_id,provider_resource_id=resource_id,
                actual_cost=cost,units=units,rates=rates,simulated=simulated)
            job.provider=provider;job.provider_request_id=request_id;job.provider_resource_id=resource_id
            job.save(update_fields=['provider','provider_request_id','provider_resource_id'])
        payload=json.dumps(raw if simulated else raw.model_dump(mode='json'),ensure_ascii=False).encode()
        relative=f'receipts/{secrets.token_hex(24)}.json';path=private_path(relative)
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with path.open('xb') as stream:path.chmod(0o600);stream.write(payload)
        job.result_path=relative;job.result_sha256=hashlib.sha256(payload).hexdigest()
        job.save(update_fields=['result_path','result_sha256'])
        # The connection that will carry settlement's COMMIT, kept to tell afterwards whether it was lost (as core.jobs, RS-1).
        connection.ensure_connection();carrier=connection.connection;settling=True
        settle(job,cost,units,rates,provider,request_id,simulated,provider_resource_id=resource_id)
        settling=False
        proposal=mapping.validate_proposal(version,compiled,parse_response(raw,simulated))
        with transaction.atomic():
            template=Template.objects.select_for_update().get(pk=version.template_id)
            try:membership(job.user,template.department,roles=['owner','clinician','manager'])
            except PermissionDenied as exc:raise NotAdoptedByUser('Access revoked before mapping adoption.') from exc
            if template.versions.order_by('-number').first().pk!=version.pk:
                raise NotAdoptedByUser('Mapping was edited while the request ran.')
            new=TemplateVersion.objects.create(template=template,number=version.number+1,fields=proposal['fields'],
                contract='v3',review_requirements=version.review_requirements,created_by=job.user,
                assistance={**proposal['review'],'job_id':str(job.pk),'base_version':str(version.pk),'simulated':simulated})
            job.state='succeeded';job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
            audit(job.user,'mapping.review_ready',job.pk,department=template.department,version=str(new.pk),
                  unresolved=len(proposal['review']['unresolved']),simulated=simulated)
    except Exception as exc:
        # A request the SDK refused to build never left: it is the pre-send refusal it is (MONEY-2).
        from .jobs import OUTCOME_UNRECORDED, PROVIDER_NOT_CONNECTED, commit_in_doubt, hold_for_reconciliation, never_transmitted, usable_connection
        if not returned and never_transmitted(exc): exc=NoProviderRequest(PROVIDER_NOT_CONNECTED)
        # Read before anything reconnects: whether settle()'s COMMIT went out and its answer was lost (as core.jobs, RS-1).
        in_doubt=settling and commit_in_doubt(exc,carrier)
        usable_connection()
        try:end_failed_job(job,exc,returned,sent,in_doubt)
        except DatabaseError:
            # The handler's own read or write failed (as core.jobs, RS-2): hold the job for an administrator, asserting nothing.
            usable_connection()
            hold_for_reconciliation(job,exc,OUTCOME_UNRECORDED,action='mapping.reconciliation')
    return True

def end_failed_job(job,exc,returned,sent,in_doubt):
    """Record how a running mapping job that raised ended, from what is committed, under its row lock.

    ⚠️ THE SAME GUARD AS core.jobs.end_failed_job (RR2-M1, docs/rebuild/v1/residuals-assessment-20260929.md). This handler
    used to read Usage.exists() without the job's lock and write afterwards: when the ADOPTION's COMMIT answer was lost
    after it committed (the new mapping version on the template, the job 'succeeded', the charge standing), it decided
    'known and not declined' and overwrote the committed success as a platform failure, reversing the charge. Now the
    decision and the write happen under the job's row lock, where the committed record is final (a transaction whose COMMIT
    answer was lost holds that lock until it ends), and an outcome a committed transaction recorded is never overwritten.
    An in-doubt settlement COMMIT asserts nothing and holds the job with its request key."""
    from .jobs import (ABSORPTION_FAILED, SETTLEMENT_UNKNOWN, NoProviderRequest, NotAdoptedByUser, ended_key,
                       hold_for_reconciliation, outcome_already_recorded)
    if in_doubt:return hold_for_reconciliation(job,exc,SETTLEMENT_UNKNOWN,action='mapping.reconciliation')
    absorbing=False
    try:
        with transaction.atomic():
            state=Job.objects.select_for_update().get(pk=job.pk).state
            if state!='running':return outcome_already_recorded(job,exc,state)
            known=Usage.objects.filter(job=job).exists()
            declined=known and isinstance(exc,NotAdoptedByUser)
            unsent=not returned and (not sent or isinstance(exc,NoProviderRequest))
            job.state='failed' if known or unsent else 'reconciliation'
            job.error=('not_adopted: Source or permission changed; output was not adopted.' if declined else
                       'platform_failure: Mapping output could not be adopted.' if known else
                       'not_processed: Mapping refused before submission; held funds released.' if unsent else
                       'Provider outcome or settlement is uncertain; reconcile before retrying.')
            job.finished_at=timezone.now()
            if job.state=='failed':job.request_key=ended_key(job,'failed')
            job.save(update_fields=['state','error','finished_at','request_key'])
            if unsent:release(job)
            # ⚠️ In the same transaction as the failed state (RS-3, as core.jobs): a reversal that fails never leaves a
            # 'failed' job charged with its request key freed, which let the same mapping be bought again.
            if known and not declined:absorbing=True;absorb_failed_job(job);absorbing=False
            audit(job.user,'mapping.'+job.state,job.pk,department=job.department,error_class=type(exc).__name__)
    except Exception as absorb_error:
        if not absorbing:raise
        hold_for_reconciliation(job,exc,ABSORPTION_FAILED,billing='platform_failure',absorb_error=absorb_error,
                                action='mapping.reconciliation')
