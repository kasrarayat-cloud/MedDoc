"""Explicit successors for evidenced schema rejection; financial history stays held.

An HTTP error is not a meter. Earlier stages, jobs and reservations are never
resolved here. Each signed, changed-transport successor shares its entire
authenticated family's call and exposure limits.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import UUID
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from .models import AuditEvent, Job, Usage, ProviderReceipt
from .security import private_path

CONTRACT='rejected-generation-successor-v1'
SALT='rejected-generation-successor'
TRANSPORT_KEY='semantic_schema_transport'
RECOVERY_KEY='semantic_recovery'
CONFIG_KEYS=('provider','model','mode','prompt_version','pricing_version','input_rate','cached_rate',
    'output_rate','discount_rate','semantic_contract','semantic_stage_protocol','semantic_max_calls',
    'semantic_request_byte_limit','semantic_capacity_profile','semantic_timeout_seconds',
    'semantic_output_token_limit','semantic_maximum_cost',TRANSPORT_KEY)
CHANGED_KEYS=frozenset({TRANSPORT_KEY,'queued_release_sha',RECOVERY_KEY})
MAX_FAMILY_CALLS=5


def _digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _same(one,two):
    # JSON booleans and numbers must not authenticate each other through Python's
    # True == 1 (or 1 == 1.0) comparisons.
    return _digest(one)==_digest(two)


def _cost(value):
    if type(value)is not Decimal or not value.is_finite() or value<0:
        raise ValueError('invalid retained exposure')
    return value


def _retained(path,digest):
    if not isinstance(path,str) or not re.fullmatch(r'receipts/[a-f0-9]{48}\.json',path):raise ValueError('private evidence path')
    if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('evidence hash')
    with private_path(path).open('rb') as stream:raw=stream.read(512001)
    if len(raw)>512000 or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('evidence integrity')
    return json.loads(raw)


def _local_rejection(job):
    """Authenticate this attempt's first-extractor rejection, never cost zero."""
    try:
        if job.kind!='generation' or job.state!='reconciliation' or job.finished_at is None:return None
        if (type(job.config)is not dict or job.result_path or job.result_sha256
            or job.config.get('mode')!='live' or job.config.get('provider')!='anthropic'
            or not re.fullmatch('[a-f0-9]{40}',job.config.get('queued_release_sha',''))):return None
        if Usage.objects.filter(job=job).exists() or ProviderReceipt.objects.filter(job=job).exists():return None
        rows=list(job.ai_stage_receipts.all()[:2])
        if len(rows)!=1:return None
        stage=rows[0]
        if (stage.stage!='extractor' or stage.attempt!=1 or stage.state!='unknown'
            or stage.error_code!='provider_unknown' or stage.simulated or stage.actual_cost is not None
            or stage.started_at is None or stage.finished_at is None or stage.finished_at>job.finished_at
            or not _same(stage.config,job.config) or stage.provider!='anthropic'
            or stage.requested_model!=job.config.get('model') or stage.result_path or stage.result_sha256
            or stage.provider_request_id or stage.provider_resource_id or stage.returned_model
            or stage.usage or stage.rates):return None
        request=_retained(stage.request_path,stage.request_sha256)
        payload=request['payload'];identity=payload['identity']
        expected_identity={**job.config['semantic_encounter_binding'],'generation_job_id':str(job.pk)}
        if (request['protocol']!=job.config['semantic_stage_protocol'] or request['stage']!='extractor'
            or request['attempt']!=1 or request['max_output_tokens']!=job.config['semantic_output_token_limit']
            or request['timeout_seconds']!=job.config['semantic_timeout_seconds']
            or request['schema_transport']!=job.config.get(TRANSPORT_KEY,'anthropic-shared-local-definitions-v1')
            or not _same(identity,expected_identity) or identity['encounter_id']!=str(job.encounter_id)
            or hashlib.sha256(payload['notes'].encode()).hexdigest()!=job.config['semantic_source_sha256']
            or _digest(payload['approved_definitions'])!=job.config['semantic_definitions_sha256']):return None
        events=list(AuditEvent.objects.filter(action='ai.stage_error_retained',target=str(stage.pk),
            actor_id=job.user_id,department_id=job.encounter.department_id)[:2])
        if len(events)!=1:return None
        event=events[0];details=event.details
        if (details.get('contract')!='ai-stage-error-evidence-v1' or details.get('http_status')!=400
            or details.get('exception_class')!='BadRequestError'
            or not stage.finished_at<=event.created_at<=job.finished_at):return None
        error=_retained(details['evidence_path'],details['evidence_sha256'])
        provider_error=error.get('provider_error')
        if (error.get('contract')!='ai-stage-error-evidence-v1' or error.get('provider')!='anthropic'
            or error.get('stage_id')!=str(stage.pk) or error.get('stage')!='extractor' or error.get('attempt')!=1
            or error.get('http_status')!=400 or error.get('exception_class')!='BadRequestError'
            or error.get('body_source')!='cached_http_response' or error.get('body_retention')!='sanitized_error_projection'
            or error.get('sanitized')is not True or error.get('exact_raw_response')is not False
            or error.get('delivery_outcome')!='unknown' or error.get('actual_cost')is not None
            or type(error.get('body_bytes'))is not int or not 0<error['body_bytes']<=65536
            or not isinstance(error.get('body_sha256'),str) or not re.fullmatch('[a-f0-9]{64}',error['body_sha256'])
            or error.get('truncated_fields')!=[] or type(provider_error)is not dict
            or provider_error.get('type')!='invalid_request_error'
            or not re.fullmatch(r'req_[A-Za-z0-9]+',error.get('provider_request_id')or'')):
            return None
        return {'job':str(job.pk),'stage':str(stage.pk),'request_sha256':stage.request_sha256,
            'error_audit':str(event.pk),'error_sha256':details['evidence_sha256'],
            'old_transport':request['schema_transport'],'prior_calls':1,'prior_quote':str(_cost(stage.quote_maximum)),
            'old_config_sha256':_digest(job.config)}
    except (AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):
        return None


def _children(job):
    # Include malformed/cross-encounter pointers. They cannot authenticate an
    # edge, and must not allow choosing a convenient branch of a fork.
    return list(Job.objects.filter(config__semantic_recovery__job=str(job.pk)).order_by('created_at','pk')[:2])


def _edge(predecessor,successor,proof):
    value=successor.config.get(RECOVERY_KEY)
    keys={'contract',*proof,'encounter','actor','revision','new_transport','accepted_release','new_configuration_sha256'}
    if type(value)is not dict or set(value)!=keys or value.get('contract')!=CONTRACT:return False
    if any(not _same(value.get(k),v)for k,v in proof.items()):return False
    if (successor.kind!='generation' or successor.pk==predecessor.pk
        or successor.encounter_id!=predecessor.encounter_id or successor.user_id!=predecessor.user_id
        or successor.revision!=predecessor.revision
        or successor.request_key not in {request_key(predecessor),request_key(predecessor)+':failed:'+successor.pk.hex,request_key(predecessor)+':cancelled:'+successor.pk.hex}
        or value.get('actor')!=str(successor.user_id) or value.get('encounter')!=str(successor.encounter_id)
        or type(value.get('revision'))is not int or value['revision']!=successor.revision
        or successor.config.get('queued_release_sha')!=value.get('accepted_release')
        or not re.fullmatch('[a-f0-9]{40}',value.get('accepted_release')or'')
        or value['accepted_release']==predecessor.config.get('queued_release_sha')
        or type(value.get('new_transport'))is not str or not value['new_transport']
        or successor.config.get(TRANSPORT_KEY)!=value['new_transport']
        or value['new_transport']==proof['old_transport']
        or _digest({k:successor.config[k]for k in CONFIG_KEYS if k in successor.config})!=value.get('new_configuration_sha256')
        or not _same({k:v for k,v in successor.config.items()if k not in CHANGED_KEYS},
                     {k:v for k,v in predecessor.config.items()if k not in CHANGED_KEYS})
        or predecessor.finished_at is None or predecessor.finished_at>successor.created_at):return False
    children=_children(predecessor)
    if len(children)!=1 or children[0].pk!=successor.pk:return False
    events=list(AuditEvent.objects.filter(action='generation.recovery_queued',target=str(successor.pk),
        actor_id=successor.user_id,department_id=successor.encounter.department_id)[:2])
    return (len(events)==1 and events[0].created_at>=successor.created_at
        and _same(events[0].details,{'recovery':value}))


def _lineage(job,*,lock=False):
    """Return a verified root-to-job path and all earlier uncertain exposure.

    Walking is iterative and bounded. Every earlier node must still authenticate
    as a retained rejection and every edge must have one immutable application
    audit and one child. A tip may be queued, successful or rejected.
    """
    nodes=[job];seen={job.pk}
    while RECOVERY_KEY in nodes[-1].config:
        value=nodes[-1].config[RECOVERY_KEY]
        if type(value)is not dict or type(value.get('job'))is not str:raise ValueError('malformed recovery parent')
        identifier=UUID(value['job'])
        if str(identifier)!=value['job'] or identifier in seen or len(nodes)>=MAX_FAMILY_CALLS:
            raise ValueError('cyclic or excessive recovery family')
        manager=Job.objects.select_for_update()if lock else Job.objects
        parent=manager.get(pk=identifier)
        if (parent.encounter_id!=job.encounter_id or parent.user_id!=job.user_id
            or parent.revision!=job.revision):raise ValueError('recovery family identity')
        seen.add(identifier);nodes.append(parent)
    nodes.reverse();exposure=Decimal('0');transports=set()
    for index,(parent,child)in enumerate(zip(nodes,nodes[1:])):
        proof=_local_rejection(parent)
        if not proof:raise ValueError('unproved recovery ancestor')
        exposure+=Decimal(proof['prior_quote'])
        proof={**proof,'prior_calls':index+1,'prior_quote':str(exposure)}
        if not _edge(parent,child,proof):raise ValueError('unauthenticated recovery edge')
        transports.add(proof['old_transport'])
        transport=child.config.get(TRANSPORT_KEY)
        if transport in transports:raise ValueError('repeated recovery transport')
    return nodes,exposure,transports


def rejection(job):
    """Authenticate the complete rejected family and count every prior call."""
    try:
        nodes,exposure,_=_lineage(job)
        proof=_local_rejection(job)
        if proof is None:return None
        return {**proof,'prior_calls':len(nodes),'prior_quote':str(exposure+Decimal(proof['prior_quote']))}
    except (Job.DoesNotExist,AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):
        return None


def family_ids(job):
    """Only authenticated ancestors can be excluded from unrelated busy work."""
    try:return {item.pk for item in _lineage(job)[0]}
    except (Job.DoesNotExist,AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):
        return set()


def _source_matches(job,encounter):
    from .word_contract import require_generation
    from .source_interpretation_store import identity_for
    definitions=require_generation(encounter.template_version)
    identity=identity_for(encounter,definitions,generation_job_id=str(job.pk))
    return (job.encounter_id==encounter.pk and job.revision==encounter.revision
        and hashlib.sha256(encounter.notes.encode()).hexdigest()==job.config.get('semantic_source_sha256')
        and _digest(definitions)==job.config.get('semantic_definitions_sha256')
        and {k:v for k,v in identity.items()if k!='generation_job_id'}==job.config.get('semantic_encounter_binding'))


def _proposal(job,encounter,user,config):
    proof=rejection(job)
    if not proof or job.user_id!=user.pk or encounter.status=='finalized' or encounter.answers:return None
    if not _source_matches(job,encounter):return None
    _,_,transports=_lineage(job)
    children=_children(job)
    if children and (len(children)!=1 or not linked(job,children[0])):return None
    limit=job.config.get('semantic_max_calls')
    if type(limit)is not int or not 1<=limit<=MAX_FAMILY_CALLS or proof['prior_calls']>=limit:return None
    prospective={k:config[k]for k in CONFIG_KEYS if k in config}
    original={k:job.config[k]for k in CONFIG_KEYS if k in job.config}
    new_transport=prospective.pop(TRANSPORT_KEY,None);original.pop(TRANSPORT_KEY,None)
    release=settings.RELEASE_SHA
    if (not _same(prospective,original) or type(new_transport)is not str or not new_transport
        or new_transport in transports|{proof['old_transport']} or not re.fullmatch('[a-f0-9]{40}',release)
        or release==job.config['queued_release_sha']):return None
    return {'contract':CONTRACT,**proof,'encounter':str(encounter.pk),'actor':str(user.pk),
        'revision':encounter.revision,'new_transport':new_transport,'accepted_release':release,
        'new_configuration_sha256':_digest({k:config[k]for k in CONFIG_KEYS if k in config})}


def offer(encounter,user,config):
    """Read-only offer; a GET neither authorizes nor reserves a successor."""
    jobs=list(Job.objects.filter(encounter=encounter,state__in=['queued','running','reconciliation']).order_by('-created_at','-pk')[:MAX_FAMILY_CALLS+1])
    try:
        tips=[job for job in jobs if successor(job)is None]
        if len(tips)!=1:return None
        tip=tips[0]
        if {job.pk for job in jobs}!=family_ids(tip):return None
        value=_proposal(tip,encounter,user,config)
    except (Job.DoesNotExist,AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):return None
    if value is None:return None
    return signing.dumps(value,salt=SALT)


def predecessor(token,encounter,user):
    try:
        value=signing.loads(token,salt=SALT,max_age=600)
        if value.get('contract')!=CONTRACT or value.get('actor')!=str(user.pk) or value.get('encounter')!=str(encounter.pk):raise ValueError()
        job=Job.objects.select_for_update().get(pk=value['job'],encounter=encounter,user=user)
        return job,value
    except (signing.BadSignature,Job.DoesNotExist,KeyError,TypeError,ValueError):
        raise ValidationError('The repaired-generation offer expired or changed. Reload this document; nothing was queued.') from None


def bind(job,value,encounter,user,config):
    expected=_proposal(job,encounter,user,config)
    if expected is None or not _same(value,expected):
        raise ValidationError('The rejection evidence, source or repaired configuration changed. Nothing was queued.')
    if not _same({k:v for k,v in config.items()if k not in CHANGED_KEYS},
                 {k:v for k,v in job.config.items()if k not in CHANGED_KEYS}):
        raise ValidationError('A repaired request must retain the exact original provider, rates, source and authority.')
    return {**config,RECOVERY_KEY:value}


def request_key(job):return f'generation:{job.encounter_id}:{job.revision}:recovery:{job.pk.hex}'


def linked(predecessor,successor):
    """A real immutable successor + append-only audit, not a review or cost override."""
    try:
        nodes,_,_=_lineage(successor)
        return len(nodes)>1 and nodes[-2].pk==predecessor.pk
    except (Job.DoesNotExist,AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):return False


def successor(job):
    children=_children(job)
    return children[0]if len(children)==1 and linked(job,children[0])else None


def latest(job):
    """Idempotent normal submissions resolve to the tip, never buy a new family."""
    seen={job.pk}
    for _ in range(MAX_FAMILY_CALLS-1):
        child=successor(job)
        if child is None or child.pk in seen:return job
        seen.add(child.pk);job=child
    return job


def pending_jobs(jobs):
    """Financially unresolved original rejection stops being operationally busy only after its successor exists."""
    return any(job.state in ('queued','running') or (job.state=='reconciliation' and successor(job)is None) for job in jobs)


def enforce_stage_budget(job,previous,cap):
    """Called under the stage's parent-row lock; prior unknown exposure is counted."""
    if RECOVERY_KEY not in job.config:return
    from .ai_stages import StageNotSent,maximum_cost
    try:
        nodes,prior_exposure,_=_lineage(job,lock=True);rows=list(previous)
        limit=job.config['semantic_max_calls']
        if len(nodes)<2 or type(limit)is not int or not 1<=limit<=MAX_FAMILY_CALLS or len(nodes)-1+len(rows)>=limit:raise ValueError()
        exposure=prior_exposure+sum((max(_cost(row.quote_maximum),_cost(row.actual_cost)if row.actual_cost is not None else Decimal('0'))for row in rows),Decimal('0'))+_cost(cap)
        if exposure>_cost(maximum_cost(job.config)):raise ValueError()
    except (Job.DoesNotExist,AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):
        raise StageNotSent('The repaired workflow has exhausted or lost its original bounded-call and cost evidence; nothing was sent.') from None
