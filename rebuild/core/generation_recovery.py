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
from django.core.exceptions import PermissionDenied, ValidationError
from .models import AuditEvent, Job, Usage, ProviderReceipt, TestingReservation, Reservation
from .security import private_path
from . import anthropic_request_policy as request_policy
from . import clinical_schema_transport as clinical_transport
from .provider_schema import ANTHROPIC_SCHEMA_TRANSPORT

CONTRACT='rejected-generation-successor-v1'
CONTRACT_V2='rejected-generation-successor-v2'
CONTRACT_METERED='metered-thinking-budget-successor-v1'
CONTRACT_PROFILE='rejected-request-profile-successor-v1'
CONTRACT_CARRIER='invalid-generation-carrier-successor-v1'
CONTRACT_TRUNCATED='truncated-json-output-successor-v1'
METERED_SUCCESSOR_TRANSPORTS=(clinical_transport.TRANSPORT,
    clinical_transport.EVIDENCE_TRANSPORT,clinical_transport.CURRENT_TRANSPORT,
    clinical_transport.JSON_TRANSPORT,clinical_transport.DIRECT_TRANSPORT)
CARRIER_SUCCESSOR_TRANSPORTS=(clinical_transport.JSON_TRANSPORT,clinical_transport.DIRECT_TRANSPORT)
SALT='rejected-generation-successor'
TRANSPORT_KEY='semantic_schema_transport'
RECOVERY_KEY='semantic_recovery'
CONFIG_KEYS=('provider','model','mode','prompt_version','pricing_version','input_rate','cached_rate',
    'output_rate','discount_rate','semantic_contract','semantic_stage_protocol','semantic_max_calls',
    'semantic_request_byte_limit','semantic_capacity_profile','semantic_timeout_seconds',
    'semantic_output_token_limit','semantic_maximum_cost',TRANSPORT_KEY,request_policy.CONFIG_KEY)
CHANGED_KEYS=frozenset({TRANSPORT_KEY,'queued_release_sha',RECOVERY_KEY})
MAX_FAMILY_CALLS=5
V2_FAMILY_MAX_CALLS=8
PER_BATCH_MAX_CALLS=5
# A rejected first extractor has no reusable output: its successor must still
# complete extractor, assigner and checker under the original family limit.
MIN_SUCCESSOR_CALLS=3


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


def _v2_bounds(config):
    """Server-selected technical batch bounds, never new funding or credits."""
    from . import testing_authority
    if testing_authority.identity(config) is None:return None
    if (config['testing_purpose']!=testing_authority.PURPOSES['generation']
        or type(config.get('semantic_max_calls'))is not int
        or config['semantic_max_calls']!=PER_BATCH_MAX_CALLS
        or type(config.get('semantic_maximum_cost'))is not str):raise ValueError('recovery authority or batch bounds')
    _cost(Decimal(config['semantic_maximum_cost']))
    return {'per_batch_max_calls':PER_BATCH_MAX_CALLS,'family_max_calls':V2_FAMILY_MAX_CALLS,
        'family_cost_ceiling':config['semantic_maximum_cost'],
        **{key:config[key]for key in testing_authority.KEYS}}


def _family_limit(config):
    value=config.get(RECOVERY_KEY)
    limit=config.get('semantic_max_calls')
    if type(limit)is not int or not 1<=limit<=MAX_FAMILY_CALLS:raise ValueError('per-job recovery bound')
    if type(value)is not dict:raise ValueError('recovery contract')
    from . import clinical_call_authority as scoped
    if scoped.selected(config):
        grant=scoped.record(value['grant_id'])
        if value.get('grant_sha256')!=scoped._digest(grant):raise ValueError('scoped recovery authority')
        return scoped.FAMILY_CALLS
    if value.get('contract')==CONTRACT:return limit
    if value.get('contract')not in(CONTRACT_V2,CONTRACT_METERED,CONTRACT_PROFILE,CONTRACT_CARRIER,CONTRACT_TRUNCATED):raise ValueError('recovery contract')
    bounds=_v2_bounds(config)
    if bounds is None and value['contract']==CONTRACT_PROFILE:return limit
    if bounds is None or any(not _same(value.get(k),v)for k,v in bounds.items()):raise ValueError('recovery batch bounds')
    return V2_FAMILY_MAX_CALLS


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


def _local_paid_failure(job,*,carrier=False,truncated=False):
    """Authenticate a settled first extractor and its exact retained failure.

    This is an additional request, not reconciliation or a rewrite of the paid
    failure. Both its metered cost and conservative quote remain in the family.
    """
    try:
        from . import ai_stages, generation
        if carrier and truncated:return None
        explicit_profile=carrier or truncated
        if (job.kind!='generation' or job.state!='failed' or job.finished_at is None
            or job.result_path or job.result_sha256 or not job.error.startswith('platform_failure:')
            or type(job.config)is not dict or job.config.get('mode')!='live'
            or job.config.get('provider')!='anthropic' or job.config.get('model')!='claude-sonnet-5-5'
            or (job.config.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE
                if explicit_profile else request_policy.CONFIG_KEY in job.config)
            or not re.fullmatch('[a-f0-9]{40}',job.config.get('queued_release_sha',''))):return None
        old_transport=(clinical_transport.marker(job.config)if clinical_transport.selected(job.config)
                       else ANTHROPIC_SCHEMA_TRANSPORT)
        if carrier and old_transport!=clinical_transport.CURRENT_TRANSPORT:return None
        if truncated and old_transport!=clinical_transport.JSON_TRANSPORT:return None
        rows=list(job.ai_stage_receipts.all()[:2])
        if len(rows)!=1:return None
        stage=rows[0]
        if (stage.stage!='extractor' or type(stage.attempt)is not int or stage.attempt!=1
            or stage.state!='failed' or stage.error_code!='invalid_response' or stage.simulated is not False
            or _cost(stage.actual_cost)<=0 or stage.started_at is None or stage.finished_at is None
            or not stage.started_at<=stage.finished_at<=job.finished_at
            or not _same(stage.config,job.config) or stage.provider!='anthropic'
            or stage.requested_model!=job.config['model'] or stage.returned_model!=job.config['model']
            or not re.fullmatch(r'req_[A-Za-z0-9]+',stage.provider_request_id or'')
            or not re.fullmatch(r'msg_[A-Za-z0-9]+',stage.provider_resource_id or'')):return None
        request=_retained(stage.request_path,stage.request_sha256)
        payload=request['payload'];identity=payload['identity']
        expected_identity={**job.config['semantic_encounter_binding'],'generation_job_id':str(job.pk)}
        if (request['protocol']!=job.config['semantic_stage_protocol'] or request['stage']!='extractor'
            or type(request['attempt'])is not int or request['attempt']!=1
            or type(request['max_output_tokens'])is not int
            or request['max_output_tokens']<=0 or request['max_output_tokens']!=job.config['semantic_output_token_limit']
            or request['timeout_seconds']!=job.config['semantic_timeout_seconds']
            or request.get('schema_transport',ANTHROPIC_SCHEMA_TRANSPORT)!=old_transport
            or (not _same(request.get(request_policy.ENVELOPE_KEY),request_policy.parameters(job.config))
                if explicit_profile else request_policy.ENVELOPE_KEY in request)
            or not _same(identity,expected_identity) or identity['encounter_id']!=str(job.encounter_id)
            or hashlib.sha256(payload['notes'].encode()).hexdigest()!=job.config['semantic_source_sha256']
            or _digest(payload['approved_definitions'])!=job.config['semantic_definitions_sha256']):return None
        result=_retained(stage.result_path,stage.result_sha256)
        output=result['provider_output'];usage=output['usage']
        if (set(result)!={'provider_output','provider_request_id','provider_resource_id','returned_model'}
            or result['provider_request_id']!=stage.provider_request_id
            or result['provider_resource_id']!=stage.provider_resource_id
            or result['returned_model']!=stage.returned_model
            or output.get('id')!=stage.provider_resource_id or output.get('model')!=stage.returned_model
            or output.get('type')!='message' or output.get('role')!='assistant'
            or output.get('stop_reason')!=('end_turn' if carrier else 'max_tokens')
            or type(output.get('content'))is not list or not output['content']
            or any(type(block)is not dict or block.get('type')!=('text'if explicit_profile else'thinking')
                   for block in output['content'])):return None
        if truncated and output.get('stop_details')is not None:return None
        counters={'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],
            'cached_input_tokens':usage.get('cache_read_input_tokens',0),
            'cache_creation_tokens':usage.get('cache_creation_input_tokens',0)}
        if (any(type(v)is not int or v<0 for v in counters.values()) or counters['input_tokens']<=0
            or (not 0<counters['output_tokens']<=request['max_output_tokens'] if carrier
                else counters['output_tokens']!=request['max_output_tokens'])
            or type(usage.get('output_tokens_details'))is not dict
            or type(usage['output_tokens_details'].get('thinking_tokens'))is not int
            or usage['output_tokens_details']['thinking_tokens']!=(0 if explicit_profile else counters['output_tokens'])
            or not _same(stage.usage,counters)):return None
        if explicit_profile:
            from . import source_assertion_graph
            if (not _same(request['schema'],source_assertion_graph.extraction_schema())
                or type(request.get('transmitted_schema'))is not str
                or not _same(clinical_transport.strict_loads(request['transmitted_schema']),
                    clinical_transport.transmitted_schema(request['schema'],old_transport))
                or any(type(block.get('text'))is not str for block in output['content'])):return None
            text=''.join(block['text']for block in output['content'])
            if not text.strip():return None
            if carrier:
                try:
                    clinical_transport.response_value(text,request,config=job.config,
                        provider='anthropic',simulated=False)
                except clinical_transport.TransportError:
                    pass
                else:
                    # A complete canonical graph with clinically unsafe assertions
                    # is not a carrier failure and gains no recovery permission.
                    return None
            # max_tokens never certifies a complete response, even if a prefix
            # happens to parse. Do not decode, adopt or salvage its text here.
        rates=generation.rates(job.config);discount=generation.discount_rate(job.config)
        list_cost=(counters['input_tokens']*rates['input_per_million']
            +counters['cached_input_tokens']*rates['cached_per_million']
            +counters['cache_creation_tokens']*rates['input_per_million']*Decimal('1.25')
            +counters['output_tokens']*rates['output_per_million'])/1000000
        cost=generation.discounted_cost(list_cost,discount)
        if cost!=stage.actual_cost or not _same(stage.rates,generation.cost_rates(rates,list_cost,discount)):return None
        events=list(AuditEvent.objects.filter(action='ai.stage_received',target=str(stage.pk),
            actor_id=job.user_id,department_id=job.encounter.department_id)[:2])
        details={'stage':'extractor','attempt':1,'calculated_provider_cost':str(cost),
            'provider_request_id':stage.provider_request_id,'provider_resource_id':stage.provider_resource_id,'simulated':False}
        if (len(events)!=1 or not stage.started_at<=events[0].created_at<=stage.finished_at
            or not _same(events[0].details,details)):return None
        receipts=list(ProviderReceipt.objects.filter(job=job)[:2]);usages=list(Usage.objects.filter(job=job)[:2])
        if len(receipts)!=1 or len(usages)!=1:return None
        total,units,aggregate_rates,provider,_,simulated=ai_stages.aggregate(job)
        for row in [receipts[0],usages[0]]:
            if (row.actual_cost!=total or row.provider!=provider or row.simulated is not False
                or row.provider_request_id or row.provider_resource_id
                or not _same(row.units,units) or not _same(row.rates,aggregate_rates)
                or not stage.finished_at<=row.created_at<=job.finished_at):return None
        if (total!=cost or simulated is not False or usages[0].user_id!=job.user_id
            or usages[0].department_id!=job.encounter.department_id):return None
        settlement={}
        if truncated:
            from . import testing_authority
            authority=testing_authority.identity(job.config)
            held=list(TestingReservation.objects.filter(job=job)[:2])
            settled=list(AuditEvent.objects.filter(action='testing.settle',target=str(job.pk),
                actor_id=job.user_id,department_id=job.encounter.department_id)[:2])
            if (authority is None or len(held)!=1 or held[0].state!='settled'
                or held[0].authority_id!=authority or job.payer!='standing:'+authority
                or held[0].quoted_provider_cost!=testing_authority.quote(job.config.get('testing_quote_usd'))
                or Reservation.objects.filter(job=job).exists()
                or usages[0].payer!=job.payer or usages[0].charged_cost!=Decimal('0')
                or len(settled)!=1 or not stage.finished_at<=settled[0].created_at<=job.finished_at
                or not _same(settled[0].details,{'authority_id':authority,'calculated_provider_cost':str(total),
                    'confirmed_provider_charge':None,'user_charge':'0','simulated':False})):return None
            settlement={'settled_reservation':str(held[0].pk),'settlement_audit':str(settled[0].pk)}
        return {'job':str(job.pk),'stage':str(stage.pk),'request_sha256':stage.request_sha256,
            'result_sha256':stage.result_sha256,'received_audit':str(events[0].pk),
            'metered_usage':str(usages[0].pk),'metered_receipt':str(receipts[0].pk),
            'metered_cost':str(stage.actual_cost),
            **({'truncated_transport':old_transport,**settlement}if truncated else
               {'invalid_carrier':old_transport}if carrier else{'old_request_profile':None}),
            'old_transport':old_transport,'prior_calls':1,
            'prior_quote':str(max(_cost(stage.quote_maximum),cost)),
            'old_config_sha256':_digest(job.config)}
    except (AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):
        return None


def _local_metered_exhaustion(job):
    """Historical paid max-token/thinking-only evidence remains unchanged."""
    return _local_paid_failure(job)


def _local_invalid_carrier(job):
    """A paid, complete text response failed its original v3 carrier/schema."""
    return _local_paid_failure(job,carrier=True)


def _local_truncated_json(job):
    """A settled v4 first extractor exhausted its budget on text, never a result."""
    return _local_paid_failure(job,truncated=True)


def _local_failure(job):
    return (_local_metered_exhaustion(job)or _local_invalid_carrier(job)or _local_truncated_json(job))if job.state=='failed'else _local_rejection(job)


def _changed_keys(contract):
    return CHANGED_KEYS|{request_policy.CONFIG_KEY} if contract in(CONTRACT_METERED,CONTRACT_PROFILE)else CHANGED_KEYS


def _edge(predecessor,successor,proof):
    from . import clinical_call_authority as scoped
    if scoped.selected(successor.config):return scoped.edge(predecessor,successor,proof)
    value=successor.config.get(RECOVERY_KEY)
    keys={'contract',*proof,'encounter','actor','revision','new_transport','accepted_release','new_configuration_sha256'}
    if type(value)is not dict:return False
    metered=value.get('contract')==CONTRACT_METERED
    carrier=value.get('contract')==CONTRACT_CARRIER
    truncated=value.get('contract')==CONTRACT_TRUNCATED
    profile_changed=value.get('contract')in(CONTRACT_METERED,CONTRACT_PROFILE)
    if metered!=('old_request_profile'in proof):return False
    if carrier!=('invalid_carrier'in proof):return False
    if truncated!=('truncated_transport'in proof):return False
    if profile_changed:keys.add('new_request_profile')
    if value.get('contract')==CONTRACT:
        # Raising the traversal bound must never broaden a historical v1 edge.
        limit=predecessor.config.get('semantic_max_calls')
        if (type(limit)is not int or not 1<=limit<=MAX_FAMILY_CALLS
            or type(proof.get('prior_calls'))is not int or not 1<=proof['prior_calls']<limit):return False
    elif value.get('contract')in(CONTRACT_V2,CONTRACT_METERED,CONTRACT_PROFILE,CONTRACT_CARRIER,CONTRACT_TRUNCATED):
        try:bounds=_v2_bounds(successor.config)
        except (KeyError,TypeError,ValueError,InvalidOperation,ValidationError):return False
        if bounds is None:
            if value['contract']!=CONTRACT_PROFILE:return False
            family_limit=successor.config.get('semantic_max_calls')
            if type(family_limit)is not int or not 1<=family_limit<=MAX_FAMILY_CALLS:return False
        else:
            if any(not _same(value.get(k),v)for k,v in bounds.items()):return False
            keys.update(bounds);family_limit=V2_FAMILY_MAX_CALLS
        if (type(proof.get('prior_calls'))is not int
            or proof['prior_calls']<1 or family_limit-proof['prior_calls']<MIN_SUCCESSOR_CALLS):return False
    else:return False
    if set(value)!=keys:return False
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
        or (not metered and value['new_transport']==proof['old_transport'])
        or (metered and (proof['old_request_profile']is not None
            or value['new_transport']not in METERED_SUCCESSOR_TRANSPORTS))
        or (carrier and (proof['invalid_carrier']!=clinical_transport.CURRENT_TRANSPORT
            or value['new_transport']not in CARRIER_SUCCESSOR_TRANSPORTS
            or predecessor.config.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE
            or successor.config.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE))
        or (truncated and (proof['truncated_transport']!=clinical_transport.JSON_TRANSPORT
            or value['new_transport']!=clinical_transport.DIRECT_TRANSPORT
            or predecessor.config.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE
            or successor.config.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE))
        or (profile_changed and (request_policy.CONFIG_KEY in predecessor.config
            or value.get('new_request_profile')!=request_policy.PROFILE
            or successor.config.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE))
        or _digest({k:successor.config[k]for k in CONFIG_KEYS if k in successor.config})!=value.get('new_configuration_sha256')
        or not _same({k:v for k,v in successor.config.items()if k not in _changed_keys(value['contract'])},
                     {k:v for k,v in predecessor.config.items()if k not in _changed_keys(value['contract'])})
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
        if str(identifier)!=value['job'] or identifier in seen or len(nodes)>=V2_FAMILY_MAX_CALLS:
            raise ValueError('cyclic or excessive recovery family')
        manager=Job.objects.select_for_update()if lock else Job.objects
        parent=manager.get(pk=identifier)
        if (parent.encounter_id!=job.encounter_id or parent.user_id!=job.user_id
            or parent.revision!=job.revision):raise ValueError('recovery family identity')
        seen.add(identifier);nodes.append(parent)
    nodes.reverse();exposure=Decimal('0');transports=set()
    if (len(nodes)>MAX_FAMILY_CALLS
        and job.config.get(RECOVERY_KEY,{}).get('contract')not in(CONTRACT_V2,CONTRACT_METERED,CONTRACT_PROFILE,CONTRACT_CARRIER,CONTRACT_TRUNCATED,'scoped-clinical-call-grant-successor-v1')):
        raise ValueError('historical recovery family bound')
    for index,(parent,child)in enumerate(zip(nodes,nodes[1:])):
        proof=_local_failure(parent)
        if not proof:raise ValueError('unproved recovery ancestor')
        exposure+=Decimal(proof['prior_quote'])
        proof={**proof,'prior_calls':index+1,'prior_quote':str(exposure)}
        if not _edge(parent,child,proof):raise ValueError('unauthenticated recovery edge')
        transports.add(proof['old_transport'])
        transport=child.config.get(TRANSPORT_KEY)
        if transport in transports and child.config[RECOVERY_KEY]['contract']!=CONTRACT_METERED:
            raise ValueError('repeated recovery transport')
    return nodes,exposure,transports


def rejection(job):
    """Authenticate the complete rejected family and count every prior call."""
    try:
        nodes,exposure,_=_lineage(job)
        proof=_local_failure(job)
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
    from . import clinical_call_authority as scoped
    value=scoped.proposal(job,encounter,user,config)
    if value is not None:return value
    proof=rejection(job)
    if not proof or job.user_id!=user.pk or encounter.status=='finalized' or encounter.answers:return None
    metered='old_request_profile'in proof
    carrier='invalid_carrier'in proof
    truncated='truncated_transport'in proof
    profile_changed=(request_policy.CONFIG_KEY not in job.config and config.get(request_policy.CONFIG_KEY)==request_policy.PROFILE)
    contract=CONTRACT_TRUNCATED if truncated else CONTRACT_CARRIER if carrier else CONTRACT_METERED if metered else CONTRACT_PROFILE if profile_changed else None
    changed=_changed_keys(contract)
    if not _source_matches(job,encounter):return None
    _,_,transports=_lineage(job)
    children=_children(job)
    if children and (len(children)!=1 or not linked(job,children[0])):return None
    limit=job.config.get('semantic_max_calls')
    if type(limit)is not int or not 1<=limit<=MAX_FAMILY_CALLS:return None
    try:
        bounds=_v2_bounds(job.config)
        if bounds is not None:
            from . import testing_authority
            # The page's price quote is deliberately not a queued job config.
            # Apply the same prospective authority/enrollment admission as the
            # enqueue path, without copying authority from a historical job.
            authorized=testing_authority.active_config(config,'generation')
            authorized=testing_authority.bind_actor_config(authorized,user,encounter.department_id)
            testing_authority.validate_config(authorized,'generation')
            testing_authority.admit_encounter(user,encounter)
            if (not _same(_v2_bounds(authorized),bounds)
                or not _same(authorized.get(testing_authority.ACTOR_ENROLLMENT_KEY),
                             job.config.get(testing_authority.ACTOR_ENROLLMENT_KEY))
                or any(key not in job.config or not _same(value,job.config[key])
                       for key,value in config.items()if key not in changed)):return None
    except (AttributeError,KeyError,TypeError,ValueError,InvalidOperation,PermissionDenied,ValidationError):return None
    family_limit=V2_FAMILY_MAX_CALLS if bounds is not None else limit
    if (metered or carrier or truncated)and bounds is None:return None
    if family_limit-proof['prior_calls']<MIN_SUCCESSOR_CALLS:return None
    prospective={k:config[k]for k in CONFIG_KEYS if k in config}
    original={k:job.config[k]for k in CONFIG_KEYS if k in job.config}
    new_transport=prospective.pop(TRANSPORT_KEY,None);original.pop(TRANSPORT_KEY,None)
    if carrier and (proof['invalid_carrier']!=clinical_transport.CURRENT_TRANSPORT
        or new_transport not in CARRIER_SUCCESSOR_TRANSPORTS
        or original.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE):return None
    if truncated and (proof['truncated_transport']!=clinical_transport.JSON_TRANSPORT
        or new_transport!=clinical_transport.DIRECT_TRANSPORT
        or original.get(request_policy.CONFIG_KEY)!=request_policy.PROFILE):return None
    if metered or profile_changed:
        profile=prospective.pop(request_policy.CONFIG_KEY,None)
        if request_policy.CONFIG_KEY in original or profile!=request_policy.PROFILE:return None
    release=settings.RELEASE_SHA
    if (not _same(prospective,original) or type(new_transport)is not str or not new_transport
        or (new_transport not in METERED_SUCCESSOR_TRANSPORTS
            if metered else new_transport in transports|{proof['old_transport']})
        or not re.fullmatch('[a-f0-9]{40}',release)
        or release==job.config['queued_release_sha']):return None
    return {'contract':contract or(CONTRACT_V2 if bounds is not None else CONTRACT),**(bounds or {}),
        **({'new_request_profile':request_policy.PROFILE}if metered or profile_changed else {}),
        **proof,'encounter':str(encounter.pk),'actor':str(user.pk),
        'revision':encounter.revision,'new_transport':new_transport,'accepted_release':release,
        'new_configuration_sha256':_digest({k:config[k]for k in CONFIG_KEYS if k in config})}


def offer(encounter,user,config):
    """Read-only offer; a GET neither authorizes nor reserves a successor."""
    jobs=list(Job.objects.filter(encounter=encounter,state__in=['queued','running','reconciliation']).order_by('-created_at','-pk')[:V2_FAMILY_MAX_CALLS+1])
    ended_rows=list(Job.objects.filter(encounter=encounter,kind='generation',revision=encounter.revision,state='failed').order_by('-created_at','-pk')[:V2_FAMILY_MAX_CALLS+1])
    for ended in ended_rows:
        # Keep the complete bounded attempt universe. An opaque or genuine
        # clinical failure must not reveal an older, convenient recovery tip.
        if _local_failure(ended)is None:return None
        jobs.append(ended)
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
        if (type(value)is not dict or value.get('contract')not in(CONTRACT,CONTRACT_V2,CONTRACT_METERED,CONTRACT_PROFILE,CONTRACT_CARRIER,CONTRACT_TRUNCATED,'scoped-clinical-call-grant-successor-v1')
            or value.get('actor')!=str(user.pk) or value.get('encounter')!=str(encounter.pk)):raise ValueError()
        job=Job.objects.select_for_update().get(pk=value['job'],encounter=encounter,user=user)
        return job,value
    except (signing.BadSignature,Job.DoesNotExist,KeyError,TypeError,ValueError):
        raise ValidationError('The repaired-generation offer expired or changed. Reload this document; nothing was queued.') from None


def bind(job,value,encounter,user,config):
    expected=_proposal(job,encounter,user,config)
    if expected is None or not _same(value,expected):
        raise ValidationError('The rejection evidence, source or repaired configuration changed. Nothing was queued.')
    changed=_changed_keys(value['contract'])
    if not _same({k:v for k,v in config.items()if k not in changed},
                 {k:v for k,v in job.config.items()if k not in changed}):
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
    for _ in range(V2_FAMILY_MAX_CALLS-1):
        child=successor(job)
        if child is None or child.pk in seen:return job
        seen.add(child.pk);job=child
    return job


def pending_jobs(jobs):
    """Financially unresolved original rejection stops being operationally busy only after its successor exists."""
    return any(job.state in ('queued','running') or (job.state=='reconciliation' and successor(job)is None) for job in jobs)


def enforce_stage_budget(job,previous,cap,*,stage=None,attempt=None):
    """Called under the stage's parent-row lock; prior unknown exposure is counted."""
    if RECOVERY_KEY not in job.config:return
    from .ai_stages import StageNotSent,maximum_cost
    try:
        from . import clinical_call_authority as scoped
        if scoped.selected(job.config):
            scoped.enforce(job,previous,cap,stage,attempt)
            return
        nodes,prior_exposure,_=_lineage(job,lock=True);rows=list(previous)
        limit=job.config['semantic_max_calls']
        family_limit=_family_limit(job.config)
        if (len(nodes)<2 or type(limit)is not int or not 1<=limit<=MAX_FAMILY_CALLS
            or len(rows)>=limit or len(nodes)-1+len(rows)>=family_limit):raise ValueError()
        exposure=prior_exposure+sum((max(_cost(row.quote_maximum),_cost(row.actual_cost)if row.actual_cost is not None else Decimal('0'))for row in rows),Decimal('0'))+_cost(cap)
        ceiling=_cost(maximum_cost(job.config))
        if (job.config[RECOVERY_KEY]['contract']in(CONTRACT_V2,CONTRACT_METERED,CONTRACT_PROFILE,CONTRACT_CARRIER,CONTRACT_TRUNCATED)
            and _v2_bounds(job.config)is not None
            and Decimal(job.config[RECOVERY_KEY]['family_cost_ceiling'])!=ceiling):raise ValueError()
        if exposure>ceiling:raise ValueError()
    except (Job.DoesNotExist,AttributeError,KeyError,TypeError,ValueError,OSError,InvalidOperation,ValidationError):
        raise StageNotSent('The repaired workflow has exhausted or lost its original bounded-call and cost evidence; nothing was sent.') from None
