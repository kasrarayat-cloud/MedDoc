"""Bounded independent API calls with durable request, raw response and cost evidence."""
from decimal import Decimal, ROUND_CEILING
from contextlib import contextmanager
import hashlib
import json
import os
import secrets
from django.core.exceptions import ValidationError
from django.db import transaction,DatabaseError
from django.utils import timezone
from . import generation
from .models import AIStageReceipt, Job, TemplateDefinitionPreparation
from .security import audit, membership, private_path

PROTOCOL='quillmd-ai-stages-v1'
MAX_REQUEST_BYTES=512000
MAX_OUTPUT_TOKENS=4000
GENERATION_CAPACITY_PROFILE='bounded-output-16k-v1'
GENERATION_MAX_OUTPUT_TOKENS=16000
GENERATION_TIMEOUT_SECONDS=120
MAX_CALLS=5
DEFINITION_MAX_OUTPUT_TOKENS=16000
STAGES={'extractor':1,'assigner':2,'checker':2,'definition_proposer':1,'definition_checker':1,'revalidation_checker':1}

class StageFailure(ValidationError):
    """A known result failed processing; its provider accounting remains retained."""

class StageUnknown(ValidationError):
    """A send may be chargeable; keep reservations and require reconciliation."""

class StageNotSent(ValidationError):
    """The current stage was refused before its provider send."""


def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def quote(config,input_bytes=MAX_REQUEST_BYTES,output_tokens=MAX_OUTPUT_TOKENS):
    if config.get('mode')!='live':return Decimal('0')
    rates=generation.rates(config)
    input_rate=max(rates['input_per_million']*Decimal('1.25'),rates['cached_per_million'])
    bound=(Decimal(input_bytes+12000)*input_rate+Decimal(output_tokens)*rates['output_per_million'])/1000000
    return (bound*(1-generation.discount_rate(config))).quantize(generation.COST_QUANTUM,rounding=ROUND_CEILING)


def generation_limits(config):
    """Absent means historical; an explicit invalid profile never falls back."""
    if 'semantic_capacity_profile' not in config:
        if 'semantic_timeout_seconds' in config:
            raise StageNotSent('The generation timeout has no capacity profile.')
        return MAX_OUTPUT_TOKENS,60
    if config['semantic_capacity_profile']!=GENERATION_CAPACITY_PROFILE:
        raise StageNotSent('Unknown generation capacity profile; nothing was sent.')
    if (type(config.get('semantic_output_token_limit')) is not int
        or config['semantic_output_token_limit']!=GENERATION_MAX_OUTPUT_TOKENS
        or type(config.get('semantic_timeout_seconds')) is not int
        or config['semantic_timeout_seconds']!=GENERATION_TIMEOUT_SECONDS):
        raise StageNotSent('The generation limits differ from their capacity profile.')
    return GENERATION_MAX_OUTPUT_TOKENS,GENERATION_TIMEOUT_SECONDS


def pipeline_config(config):
    prospective={**config,'semantic_contract':'semantic-facts-v1','semantic_stage_protocol':PROTOCOL,
            'semantic_max_calls':MAX_CALLS,'semantic_request_byte_limit':MAX_REQUEST_BYTES,
            'semantic_capacity_profile':GENERATION_CAPACITY_PROFILE,
            'semantic_timeout_seconds':GENERATION_TIMEOUT_SECONDS,
            'semantic_output_token_limit':GENERATION_MAX_OUTPUT_TOKENS}
    return {**prospective,'semantic_maximum_cost':str(maximum_cost(prospective))}


def definition_pipeline_config(config):
    return {**config,'definition_stage_protocol':PROTOCOL,'definition_max_calls':2,
            'definition_request_byte_limit':MAX_REQUEST_BYTES,
            'definition_output_token_limit':DEFINITION_MAX_OUTPUT_TOKENS,
            'definition_maximum_cost':str(quote(config,output_tokens=DEFINITION_MAX_OUTPUT_TOKENS)*2)}


def call_limit(config):
    if 'semantic_revalidation_contract' not in config:
        return MAX_CALLS
    from .semantic_revalidation import CONTRACT
    if config['semantic_revalidation_contract'] != CONTRACT:
        raise StageNotSent('Unknown retained revalidation contract; nothing was sent.')
    return 1


def revalidation_config(config):
    from .semantic_revalidation import CONTRACT
    prospective=pipeline_config(config)
    prospective.update(semantic_revalidation_contract=CONTRACT,semantic_max_calls=1)
    prospective['semantic_maximum_cost']=str(maximum_cost(prospective))
    return prospective


def maximum_cost(config):
    output_limit,_=generation_limits(config)
    return quote(config,output_tokens=output_limit)*call_limit(config)


def retain(value):
    relative=f'receipts/{secrets.token_hex(24)}.json'
    path=private_path(relative);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    raw=encode(value)
    with path.open('xb') as stream:
        path.chmod(0o600);stream.write(raw)
    return relative,hashlib.sha256(raw).hexdigest()


def parent_context(job,definition_preparation,config):
    if (job is None)==(definition_preparation is None):raise StageNotSent('AI stage requires exactly one authorized parent.')
    if job is not None:
        job.refresh_from_db(fields=['state','config'])
        parent=job;actor=job.user;department=job.encounter.department
        if job.kind!='generation' or job.state!='running':raise StageNotSent('Generation is not running.')
    else:
        parent=definition_preparation;parent.refresh_from_db(fields=['state','config'])
        actor=parent.requested_by;department=parent.source_version.template.department
        if parent.state not in ('proposer','checker'):raise StageNotSent('Definition preparation is not running.')
    if parent.config!=config:raise StageNotSent('The stage configuration differs from its authorized request.')
    membership(actor,department,roles=None if job is not None else ['owner','clinician'])
    from . import testing_authority
    if testing_authority.identity(config):
        if job is not None:testing_authority.admit_job_send(job)
        else:
            testing_authority.validate_config(config,'preparation')
            testing_authority.admit_actor(actor,department.pk,config)
    return parent,actor,department


def _response(payload,schema,instructions,config,max_output_tokens,timeout_seconds,on_response):
    schema=schema.model_json_schema() if hasattr(schema,'model_json_schema') else schema
    if config['provider']=='anthropic':
        from anthropic import Anthropic,transform_schema
        response=Anthropic(timeout=timeout_seconds,max_retries=0).messages.create(
            model=config['model'],max_tokens=max_output_tokens,system=instructions,
            messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
            output_config={'format':{'type':'json_schema','schema':transform_schema(schema)}})
        on_response(response)
        usage=response.usage
        cached=getattr(usage,'cache_read_input_tokens',0) or 0
        written=getattr(usage,'cache_creation_input_tokens',0) or 0
        units={'input_tokens':usage.input_tokens,'cached_input_tokens':cached,
               'cache_creation_tokens':written,'output_tokens':usage.output_tokens}
        r=generation.rates(config)
        list_cost=(usage.input_tokens*r['input_per_million']+cached*r['cached_per_million']+
                   written*r['input_per_million']*Decimal('1.25')+usage.output_tokens*r['output_per_million'])/1000000
        text=''.join(block.text for block in response.content if block.type=='text')
        complete=response.stop_reason=='end_turn'
    else:
        from openai import OpenAI
        response=OpenAI(timeout=timeout_seconds,max_retries=0).responses.create(
            model=config['model'],store=False,service_tier='default',truncation='disabled',
            max_output_tokens=max_output_tokens,instructions=instructions,input=json.dumps(payload,ensure_ascii=False),
            text={'format':{'type':'json_schema','name':'quillmd_stage','schema':schema,'strict':True}})
        on_response(response)
        usage=response.usage
        if usage is None:return response,None,None,None,None,False
        cached=getattr(usage.input_tokens_details,'cached_tokens',0) or 0
        units={'input_tokens':usage.input_tokens,'cached_input_tokens':cached,'output_tokens':usage.output_tokens}
        r=generation.rates(config)
        list_cost=((usage.input_tokens-cached)*r['input_per_million']+cached*r['cached_per_million']+usage.output_tokens*r['output_per_million'])/1000000
        text=response.output_text;complete=response.status=='completed'
    if (any(type(v) is not int or v<0 for v in units.values()) or (config['provider']=='openai' and units['cached_input_tokens']>units['input_tokens'])):return response,None,None,None,None,False
    discount=generation.discount_rate(config)
    return response,generation.discounted_cost(list_cost,discount),units,generation.cost_rates(r,list_cost,discount),text,complete


@contextmanager
def stage_slot(receipt,config):
    from .preparation_campaign import provider_slot
    try:
        with provider_slot(config):yield
    except Exception as exc:
        receipt.refresh_from_db()
        if receipt.state=='reserved':
            receipt.actual_cost=Decimal('0');receipt.state='failed';receipt.error_code='not_sent'
            receipt.finished_at=timezone.now();receipt.save(update_fields=['actual_cost','state','error_code','finished_at'])
            raise StageNotSent('The stage was refused before any provider request.') from exc
        raise


def execute_stage(*,job=None,definition_preparation=None,stage,payload,schema,instructions,config,
                  max_output_tokens=None,timeout_seconds=None,attempt=1,fixture_output=None):
    if stage not in STAGES or type(attempt) is not int or not 1<=attempt<=STAGES[stage]:
        raise StageNotSent('This stage is outside the bounded workflow.')
    if (job is None)!=stage.startswith('definition_'):raise StageNotSent('The stage does not match its parent.')
    output_limit,default_timeout=((DEFINITION_MAX_OUTPUT_TOKENS,120) if stage.startswith('definition_')
                                  else generation_limits(config))
    if max_output_tokens is None:max_output_tokens=output_limit
    if timeout_seconds is None:timeout_seconds=default_timeout
    if (type(max_output_tokens) is not int or not 1<=max_output_tokens<=output_limit
        or type(timeout_seconds) not in (int,float) or not 0<timeout_seconds<=120):
        raise StageNotSent('The stage exceeds its output or time limit.')
    parent,actor,department=parent_context(job,definition_preparation,config)
    if job is not None:
        limit=call_limit(config)
        if limit==1:
            if stage!='revalidation_checker' or attempt!=1:
                raise StageNotSent('Retained revalidation permits only its one independent checker.')
            from .semantic_revalidation import validate_stage_parent
            validate_stage_parent(job,payload,schema,instructions)
        elif stage=='revalidation_checker':
            raise StageNotSent('This checker requires an explicit retained revalidation contract.')
    schema_json=schema.model_json_schema() if hasattr(schema,'model_json_schema') else schema
    envelope={'protocol':PROTOCOL,'stage':stage,'attempt':attempt,'payload':payload,
              'schema':schema_json,'instructions':instructions,'max_output_tokens':max_output_tokens}
    if job is not None and 'semantic_capacity_profile' in config:
        envelope['timeout_seconds']=timeout_seconds
    raw=encode(envelope)
    if len(raw)>MAX_REQUEST_BYTES:raise StageNotSent('The complete stage request exceeds its limit; nothing was truncated or sent.')
    if config.get('mode') not in ('live','fixture'):raise StageNotSent('Unknown provider execution mode; nothing was sent.')
    live=config.get('mode')=='live'
    if live and fixture_output is not None:raise StageNotSent('Simulated output cannot be used for a live request.')
    if live and (config.get('provider') not in ('anthropic','openai') or not os.getenv('ANTHROPIC_API_KEY' if config['provider']=='anthropic' else 'OPENAI_API_KEY')):
        raise StageNotSent('The configured generation provider is unavailable; nothing was sent.')
    assert_installed_guards()
    cap=quote(config,len(raw),max_output_tokens)
    relation={'job':job} if job is not None else {'definition_preparation':definition_preparation}
    with transaction.atomic():
        model=Job if job is not None else TemplateDefinitionPreparation
        model.objects.select_for_update().get(pk=parent.pk)
        previous=AIStageReceipt.objects.filter(**relation)
        if previous.filter(stage=stage,attempt=attempt).exists():raise StageNotSent('This stage already has a retained attempt; it cannot be resent.')
        if previous.exclude(state='succeeded').exists():raise StageUnknown('An earlier stage remains unresolved; no new request was sent.')
        if previous.count()>=(call_limit(config) if job is not None else 2):raise StageNotSent('The bounded workflow has no further provider requests.')
        if job is not None and (config.get('semantic_stage_protocol')!=PROTOCOL or config.get('semantic_max_calls')!=call_limit(config) or config.get('semantic_request_byte_limit')!=MAX_REQUEST_BYTES or config.get('semantic_output_token_limit')!=output_limit):
            raise StageNotSent('The immutable generation quote does not cover this workflow.')
        if job is not None:
            if Decimal(config.get('semantic_maximum_cost','-1'))!=maximum_cost(config):raise StageNotSent('The pipeline quote differs from its authorized configuration.')
            if sum((row.actual_cost or Decimal('0') for row in previous),Decimal('0'))+cap>maximum_cost(config):
                raise StageNotSent('Recorded provider costs exhausted the whole-pipeline estimate; no further request was sent.')
        else:
            expected=definition_pipeline_config(config)
            if any(config.get(k)!=expected[k] for k in ('definition_stage_protocol','definition_max_calls','definition_request_byte_limit','definition_output_token_limit','definition_maximum_cost')):
                raise StageNotSent('The immutable definition quote does not cover this workflow.')
        predecessor=({'assigner':('extractor',1) if attempt==1 else ('checker',1),'checker':('assigner',attempt)}.get(stage)
            if job is not None else (('definition_proposer',1) if stage=='definition_checker' else None))
        if predecessor and not previous.filter(stage=predecessor[0],attempt=predecessor[1],state='succeeded').exists():
            raise StageNotSent('The required preceding independent stage has not completed.')
        request_path,request_sha=retain(envelope)
        receipt=AIStageReceipt.objects.create(**relation,stage=stage,attempt=attempt,config=config,
            request_path=request_path,request_sha256=request_sha,provider=config['provider'],
            requested_model=config['model'],quote_maximum=cap,simulated=not live)
    with stage_slot(receipt,config):
        parent_context(job,definition_preparation,config)
        receipt.state='sending';receipt.started_at=timezone.now();receipt.save(update_fields=['state','started_at'])
        try:
            if live:
                def on_response(response):
                    path,sha=retain({'provider_output':response.model_dump(mode='json'),
                        'provider_request_id':getattr(response,'_request_id',None) or '',
                        'provider_resource_id':getattr(response,'id','') or '',
                        'returned_model':getattr(response,'model','') or ''})
                    receipt.result_path=path;receipt.result_sha256=sha
                    receipt.provider_request_id=getattr(response,'_request_id',None) or ''
                    receipt.provider_resource_id=getattr(response,'id','') or ''
                    receipt.returned_model=getattr(response,'model','') or ''
                    try:
                        with transaction.atomic():
                            receipt.save(update_fields=['result_path','result_sha256','provider_request_id','provider_resource_id','returned_model'])
                    except DatabaseError as exc:
                        # Replayed provider IDs cannot identify a second valid
                        # stage. Keep this raw response and its original IDs in
                        # the retained wrapper, then require reconciliation.
                        receipt.provider_request_id='';receipt.provider_resource_id=''
                        receipt.save(update_fields=['result_path','result_sha256','returned_model'])
                        raise RuntimeError('Provider evidence identity collision requires reconciliation.') from exc
                response,cost,units,rates,text,complete=_response(payload,schema,instructions,config,max_output_tokens,timeout_seconds,on_response)
                request_id=getattr(response,'_request_id',None) or '';resource_id=getattr(response,'id','') or ''
                returned_model=getattr(response,'model','') or ''
            else:
                if fixture_output is None:
                    if job is not None:
                        from .semantic_generation import fixture_stage
                    else:
                        from .semantic_preparation import fixture_stage
                    parsed=fixture_stage(stage,payload)
                else:parsed=fixture_output
                cost=Decimal('0');units={};rates={};text=json.dumps(parsed);complete=True
                retained={'simulated':True,'output':parsed};request_id=resource_id=returned_model=''
            if not live:
                result_path,result_sha=retain(retained)
                receipt.result_path=result_path;receipt.result_sha256=result_sha
            receipt.provider_request_id=request_id;receipt.provider_resource_id=resource_id;receipt.returned_model=returned_model
            receipt.actual_cost=cost;receipt.usage=units or {};receipt.rates=rates or {}
            if cost is None:
                receipt.state='unknown';receipt.error_code='usage_unavailable';receipt.finished_at=timezone.now();receipt.save()
                raise StageUnknown('Provider usage is unavailable; reconciliation is required before any new request.')
            receipt.state='received';receipt.save()
            audit(actor,'ai.stage_received',receipt.pk,department=department,stage=stage,attempt=attempt,
                  calculated_provider_cost=str(cost),provider_request_id=request_id,provider_resource_id=resource_id,simulated=not live)
            try:
                if not complete:raise ValueError('incomplete')
                parsed=json.loads(text)
                if hasattr(schema,'model_validate'):schema.model_validate(parsed)
            except Exception as exc:
                receipt.state='failed';receipt.error_code='invalid_response';receipt.finished_at=timezone.now();receipt.save(update_fields=['state','error_code','finished_at'])
                raise StageFailure('The provider stage response was retained but could not be validated.') from exc
            receipt.state='succeeded';receipt.finished_at=timezone.now();receipt.save(update_fields=['state','finished_at'])
            return parsed
        except (StageUnknown,StageFailure):raise
        except Exception as exc:
            receipt.refresh_from_db()
            if receipt.state=='received':
                receipt.state='failed';receipt.error_code='processing_failure';receipt.finished_at=timezone.now();receipt.save(update_fields=['state','error_code','finished_at'])
                raise StageFailure('The retained stage could not be processed; its provider cost remains recorded.') from exc
            if receipt.state=='sending':
                receipt.state='unknown';receipt.error_code='provider_unknown';receipt.finished_at=timezone.now();receipt.save(update_fields=['state','error_code','finished_at'])
            raise StageUnknown('The provider outcome is uncertain; reconciliation is required before any new request.') from exc


def aggregate(job):
    rows=list(job.ai_stage_receipts.order_by('created_at','pk'))
    if not rows or any(row.actual_cost is None or row.state not in ('succeeded','failed') for row in rows):
        raise StageUnknown('The independent provider stages are not all reconciled.')
    stages=[{'id':str(row.pk),'stage':row.stage,'attempt':row.attempt,'provider':row.provider,
             'state':row.state,'error_code':row.error_code,'started_at':row.started_at.isoformat() if row.started_at else None,
             'request_id':row.provider_request_id,'resource_id':row.provider_resource_id,
             'actual_cost':str(row.actual_cost),'usage':row.usage,'rates':row.rates,
             'result_sha256':row.result_sha256,'request_sha256':row.request_sha256,
             'requested_model':row.requested_model,'returned_model':row.returned_model,
             'config_sha256':hashlib.sha256(encode(row.config)).hexdigest(),'simulated':row.simulated} for row in rows]
    return sum((row.actual_cost for row in rows),Decimal('0')),{'protocol':PROTOCOL,'stages':stages},{'aggregation':'sum_of_independently_rounded_stage_costs'},'quillmd:semantic-stages','',all(row.simulated for row in rows)


def stage_progress(job):
    labels={'extractor':'Extracting source facts','assigner':'Assigning facts to approved fields',
            'checker':'Independently checking answers','revalidation_checker':'Independently rechecking retained answers'}
    rows=list(job.ai_stage_receipts.order_by('created_at','pk'))
    return [{'stage':row.stage,'label':labels[row.stage], 'attempt':row.attempt,
        'state':row.state,'maximum_calls':call_limit(job.config),'completed_calls':sum(r.state=='succeeded' for r in rows)}
        for row in rows if row.stage in labels and row.state in ('reserved','sending','received','succeeded','failed','unknown')]


def assert_installed_guards():
    """Refuse sends when prospective immutable stage/approval controls differ."""
    import importlib,re
    from django.db import connection
    module=importlib.import_module('core.migrations.0026_semantic_stage_receipts')
    bodies=dict(re.findall(r'CREATE FUNCTION (quillmd_[a-z_]+)\([^)]*\) RETURNS [^$]*?AS \$\$(.*?)\$\$;',module.SEMANTIC_SQL,re.S))
    recovery=importlib.import_module('core.migrations.0030_retained_semantic_revalidation')
    bodies.update(dict(re.findall(r'CREATE OR REPLACE FUNCTION (quillmd_[a-z_]+)\([^)]*\) RETURNS [^$]*?AS \$\$(.*?)\$\$;',recovery.REVALIDATION_SQL,re.S)))
    triggers={name:(f'CREATE TRIGGER {name} BEFORE {events} ON public.{table} FOR EACH ROW EXECUTE FUNCTION {function}()')
        for name,table,events,function in (
            ('definition_preparation_guard','core_templatedefinitionpreparation','INSERT OR DELETE OR UPDATE','quillmd_definition_preparation_guard'),
            ('semantic_version_guard','core_templateversion','INSERT','quillmd_semantic_version_guard'),
            ('ai_stage_guard','core_aistagereceipt','INSERT OR DELETE OR UPDATE','quillmd_ai_stage_guard'))}
    with connection.cursor() as cursor:
        cursor.execute('SELECT tgname,tgenabled,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND NOT tgisinternal AND tgname=ANY(%s)',['public',list(triggers)])
        rows=cursor.fetchall()
        if len(rows)!=3 or any(enabled!='O' or definition!=triggers.get(name) for name,enabled,definition in rows):
            raise StageNotSent('Installed semantic database controls differ; no provider request was sent.')
        cursor.execute('SELECT proname,prosrc,prosecdef FROM pg_proc JOIN pg_namespace n ON n.oid=pronamespace WHERE n.nspname=%s AND proname=ANY(%s)',['public',list(bodies)])
        rows=cursor.fetchall()
        if len(bodies)!=3 or len(rows)!=3 or any(body!=bodies.get(name) or definer for name,body,definer in rows):
            raise StageNotSent('Installed semantic database function controls differ; no provider request was sent.')
