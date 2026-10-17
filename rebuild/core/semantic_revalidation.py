"""One append-only independent check of an explicitly admitted retained generation.

The original extractor, assignments, checks, receipts and failure are immutable.
This is a new proposal under a prospective local rule, never a replayed approval.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import ai_stages, generation, semantic_generation as semantic, testing_authority
from .models import CodingRun, Encounter, Job, Usage
from .security import audit, membership, private_path

CONTRACT = 'retained-facts-independent-check-v1'
STAGE = 'revalidation_checker'
SALT = 'quillmd-retained-generation-revalidation-v1'
INSTRUCTIONS = (
    ' This is one new independent check of retained source facts and field assignments after a local '
    'validation-rule correction. Inspect the complete original notes and approved definitions independently. '
    'The prior checker findings are historical evidence, not passing findings. The new local proposal is not '
    'a clinician decision. Verify every proposed field and fact, including omitted, negative, uncertain and '
    'wrong-person content. Return a hold for any unresolved issue; never pass merely because the local rule changed.')
SEQUENCE = (('extractor',1),('assigner',1),('checker',1),('assigner',2),('checker',2))


def _fail(message):
    raise ValidationError(message)


def _read(path, expected):
    if not path or not expected:
        _fail('Retained revalidation evidence is incomplete.')
    raw = private_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        _fail('Retained revalidation evidence failed its integrity check.')
    return json.loads(raw)


def _output(wrapper):
    if wrapper.get('simulated') is True:
        return deepcopy(wrapper['output'])
    response = wrapper.get('provider_output', {})
    if isinstance(response.get('content'), list):
        text = ''.join(b.get('text','') for b in response['content'] if b.get('type') == 'text')
    else:
        text = ''.join(c.get('text','') for item in response.get('output', [])
                       for c in item.get('content', []) if c.get('type') == 'output_text')
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        _fail('The original provider response cannot be read without another inference call.')


def _retained(parent):
    result = _read(parent.result_path, parent.result_sha256)
    rows = list(parent.ai_stage_receipts.order_by('created_at','pk'))
    if (tuple((r.stage,r.attempt) for r in rows) != SEQUENCE
            or any(r.state != 'succeeded' or r.actual_cost is None or r.config != parent.config for r in rows)
            or result.get('contract') != semantic.CONTRACT
            or result.get('stages') != [str(r.pk) for r in rows]):
        _fail('Recovery requires the complete original five-stage evidence, unchanged.')
    requests, outputs, manifest = [], [], []
    for row in rows:
        request = _read(row.request_path,row.request_sha256)
        raw = _read(row.result_path,row.result_sha256)
        if (request.get('protocol') != ai_stages.PROTOCOL or request.get('stage') != row.stage
                or request.get('attempt') != row.attempt):
            _fail('An original request does not match its retained stage.')
        requests.append(request); outputs.append(_output(raw))
        manifest.append({'id':str(row.pk),'stage':row.stage,'attempt':row.attempt,
            'request_sha256':row.request_sha256,'result_sha256':row.result_sha256,
            'config_sha256':semantic.digest(row.config),'actual_cost':str(row.actual_cost),
            'provider_request_id':row.provider_request_id,'provider_resource_id':row.provider_resource_id})
    return result, requests, outputs, manifest


def prepare(notes, fields, definitions, requests, outputs, original_answers, original_config):
    """Pure deterministic proposal. No provider call and no old verdict promoted."""
    if len(requests) != 5 or len(outputs) != 5:
        _fail('The complete original stage chain is required.')
    counter = 0
    def replay(role, attempt, payload, schema, instructions):
        nonlocal counter
        index=counter; counter+=1
        if (role,attempt) != SEQUENCE[index]:
            _fail('The original generation stage sequence changed.')
        request=requests[index]
        if (request.get('payload') != payload or request.get('schema') != schema
                or request.get('instructions') != instructions):
            _fail('The retained original generation request cannot be reconstructed exactly.')
        return deepcopy(outputs[index])
    historical=semantic.run(notes,fields,definitions,replay,
        reference_contract=original_config['semantic_fact_reference_contract'],
        scope_contract=original_config['semantic_fact_scope_contract'])
    if counter != 5 or historical != original_answers:
        _fail('The original answers do not match the original checks and source.')
    units,_=generation.source_units(notes,fields)
    facts=semantic.validate_facts(notes,units,semantic.resolve_source_references(notes,units,outputs[0],
        reference_contract=original_config['semantic_fact_reference_contract']),
        scope_contract=semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT,
        timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
    semantic._validate_current_subjects(notes,units,facts)
    final={r['key']:deepcopy(r) for r in outputs[1]['fields']}
    # Only the recorded repair destinations may replace original assignments.
    repair=requests[3]['payload'].get('repair_keys')
    if set(r['key'] for r in outputs[3]['fields']) != set(repair or []):
        _fail('The retained assignment repair differs from its recorded destinations.')
    final.update({r['key']:deepcopy(r) for r in outputs[3]['fields']})
    for row in final.values():
        row['status']='supported' if row['fact_ids'] else 'missing'
    answers=semantic._assign(notes,fields,definitions,facts,{'fields':list(final.values())},
        scope_contract=semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT,
        timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
    if any(a['status'] not in ('supported','missing') for a in answers.values()):
        _fail('A deterministic source or assignment issue remains; no new checker may be sent.')
    payload=deepcopy(requests[4]['payload'])
    payload.update(fact_scope_contract=semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT,
                   facts=list(facts.values()),proposed_answers=semantic._answer_preview(answers))
    payload['retained_revalidation']={'contract':CONTRACT,
        'original_scope_contract':original_config['semantic_fact_scope_contract'],
        'original_checks':[deepcopy(outputs[2]),deepcopy(outputs[4])],
        'original_assignments':[deepcopy(outputs[1]),deepcopy(outputs[3])],
        'proposal_basis':'Original selected fact IDs and separators, revalidated under the explicit prospective local rule.'}
    return {'answers':answers,'facts':facts,'payload':payload,
            'schema':semantic.CHECK_SCHEMA,'instructions':requests[4]['instructions']+INSTRUCTIONS}


def _origin(encounter, user, parent_id=None, *, require_current=True, admitted=True):
    membership(user,encounter.department,roles=['owner','clinician'])
    if admitted:
        if not settings.SYNTHETIC_ONLY:
            _fail('Retained revalidation is available only in the authorized synthetic workflow.')
        ids=getattr(settings,'SEMANTIC_REVALIDATION_ORIGIN_JOB_IDS',())
    else:
        ids=[parent_id]
    query=Job.objects.filter(pk__in=ids,encounter=encounter,user=user,kind='generation',state='succeeded')
    if parent_id:query=query.filter(pk=parent_id)
    parents=list(query)
    if len(parents)!=1:
        _fail('This encounter has no uniquely admitted retained generation recovery.')
    parent=parents[0]
    from .word_contract import require_generation
    definitions=require_generation(encounter.template_version)
    if (parent.revision != encounter.revision or 'semantic_revalidation_contract' in parent.config
            or parent.config.get('semantic_source_sha256') != hashlib.sha256(encounter.notes.encode()).hexdigest()
            or parent.config.get('semantic_definitions_sha256') != semantic.digest(definitions)
            or parent.config.get('semantic_template_version') != str(encounter.template_version_id)):
        _fail('Source, patient revision or approved definitions changed after the original generation.')
    result,requests,outputs,manifest=_retained(parent)
    if require_current and (encounter.status != 'review' or encounter.answers != result['answers']
                            or encounter.template_review):
        _fail('Saved clinical edits or review decisions changed; recovery cannot overwrite them.')
    proposal=prepare(encounter.notes,encounter.template_version.fields,definitions,requests,outputs,
                     result['answers'],parent.config)
    return parent,result,manifest,proposal,definitions


def _binding(encounter,user,parent,result,manifest,parent_run_id):
    return {'parent_job_id':str(parent.pk),'parent_run_id':str(parent_run_id),
        'parent_answers_sha256':semantic.digest(result['answers']),
        'source_sha256':hashlib.sha256(encounter.notes.encode()).hexdigest(),
        'definitions_sha256':parent.config['semantic_definitions_sha256'],
        'template_version_id':str(encounter.template_version_id),'encounter_id':str(encounter.pk),
        'patient_id':str(encounter.patient_id),'revision':encounter.revision,
        'parent_result_sha256':parent.result_sha256,'parent_receipts_digest':semantic.digest(manifest),
        'target_scope_contract':semantic.OBJECTIVE_NEGATION_SCOPE_CONTRACT,'actor_id':str(user.pk)}


def _new_config(encounter,user,binding):
    config=testing_authority.active_config(generation.configuration(),'generation')
    if not testing_authority.identity(config):
        _fail('A new standing synthetic testing authority is required; old allowances cannot be reused.')
    testing_authority.admit_encounter(user,encounter)
    config=ai_stages.revalidation_config(config)
    config.update(semantic_revalidation=binding,semantic_template_version=binding['template_version_id'],
        semantic_source_sha256=binding['source_sha256'],semantic_definitions_sha256=binding['definitions_sha256'],
        semantic_fact_scope_contract=binding['target_scope_contract'],
        semantic_fact_reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
    config=testing_authority.job_config(config,'generation',user,encounter.department_id,ai_stages.maximum_cost(config))
    config['testing_quote_usd']=format(Decimal(config['testing_quote_usd']),'f')
    return config


def _key(parent_id):
    return f'semantic-revalidation:{parent_id}:{CONTRACT}'


def _prior(parent_id):
    # Other worker refusal paths may release the active request key. The immutable
    # config binding still identifies the consumed recovery and cannot buy a retry.
    return Job.objects.filter(config__semantic_revalidation_contract=CONTRACT,
        config__semantic_revalidation__parent_job_id=str(parent_id)).order_by('created_at','pk').first()


def _coding_source(encounter,user,parent_run_id,*,completed=False):
    from . import coding_recovery,coding_service
    try:source=CodingRun.objects.get(pk=parent_run_id,encounter=encounter,user=user)
    except (CodingRun.DoesNotExist,ValueError):
        _fail('The original coding snapshot is unavailable.')
    coding_recovery.live_receipt(source)
    inputs,context,releases,key=coding_service.input_snapshot(encounter)
    stable=lambda row:{k:v for k,v in row.items() if k not in ('answers','documented_patient_name_evidence')}
    if ((stable(source.inputs)!=stable(inputs) if completed else source.inputs!=inputs or source.input_digest!=key)
            or source.context!=context or source.releases!=releases):
        _fail('The retained prediction belongs to different source, patient, date, context or references.')
    return source


def _offer(encounter,user):
    parent,result,manifest,proposal,definitions=_origin(encounter,user)
    prior=_prior(parent.pk)
    if prior:
        return {'available':False,'reason':'The one independent recheck already has a retained attempt.',
                'prior_job_id':str(prior.pk),'prior_job_state':prior.state,'provider_calls':0}
    if Job.objects.filter(encounter=encounter,state__in=['queued','running','reconciliation']).exists():
        _fail('Another request is still pending for this encounter.')
    runs=list(CodingRun.objects.filter(encounter=encounter,user=user,config__provider='corti',config__mode='live').exclude(
        state__in=['queued','running','unknown','failed']))
    if len(runs)!=1:
        _fail('The retained Corti prediction must have one unambiguous completed source run.')
    run=_coding_source(encounter,user,runs[0].pk)
    if run.inputs.get('answers')!=result['answers'] or run.inputs.get('notes')!=encounter.notes:
        _fail('The retained coding prediction belongs to different source answers.')
    binding=_binding(encounter,user,parent,result,manifest,run.pk)
    config=_new_config(encounter,user,binding)
    quoted=str(ai_stages.maximum_cost(config))
    token=signing.dumps({'binding':binding,'config_digest':semantic.digest(config)},salt=SALT,compress=True)
    return {'available':True,'reason':'One new independent check of unchanged retained facts; no extraction or coding call.',
        'display_token':token,'revision':encounter.revision,'parent_job_id':str(parent.pk),
        'parent_run_id':str(run.pk),'quote_usd':quoted,'provider_calls':1,'stage':STAGE}


def offer(encounter,user):
    try:return _offer(encounter,user)
    except (PermissionDenied,ValidationError,OSError,ValueError,KeyError) as exc:
        return {'available':False,'reason':'; '.join(exc.messages) if isinstance(exc,ValidationError) else
                'The retained source evidence is unavailable or incomplete.','provider_calls':0}


@transaction.atomic
def enqueue(encounter,user,display_token,expected_revision):
    try:shown=signing.loads(display_token,salt=SALT,max_age=3600)
    except signing.BadSignature:_fail('The recovery quote expired or changed. Reload before requesting the one check.')
    e=Encounter.objects.select_for_update().get(pk=encounter.pk)
    membership(user,e.department,roles=['owner','clinician'])
    binding=shown.get('binding',{})
    if (binding.get('encounter_id')!=str(e.pk) or binding.get('actor_id')!=str(user.pk)
            or type(expected_revision) is not int or e.revision!=expected_revision):
        _fail('The recovery quote belongs to a different actor, encounter or revision.')
    old=_prior(binding.get('parent_job_id'))
    if old:
        old.reused=True;return old
    parent,result,manifest,proposal,definitions=_origin(e,user,binding.get('parent_job_id'))
    if binding!=_binding(e,user,parent,result,manifest,binding.get('parent_run_id')):
        _fail('The retained recovery evidence changed after the quote.')
    current=_offer(e,user)
    if not current['available'] or current['parent_run_id']!=binding.get('parent_run_id'):
        _fail('This recovery is no longer eligible.')
    config=_new_config(e,user,binding)
    if semantic.digest(config)!=shown.get('config_digest'):
        _fail('The independent-check configuration or estimate changed. Reload before requesting it.')
    config['queued_release_sha']=settings.RELEASE_SHA
    job=Job.objects.create(encounter=e,user=user,kind='generation',revision=e.revision,
                           request_key=_key(parent.pk),config=config)
    from .billing import reserve
    reserve(job,ai_stages.maximum_cost(config))
    audit(user,'semantic.revalidation_queued',job.pk,department=e.department,parent_job_id=str(parent.pk),
          parent_run_id=binding['parent_run_id'],provider_calls=1,automatic_retries=0)
    job.refresh_from_db()
    job.reused=False
    return job


def _bound_proposal(job,*,completed=False):
    job.encounter=Encounter.objects.get(pk=job.encounter_id)
    if job.config.get('semantic_revalidation_contract')!=CONTRACT:
        _fail('Unknown retained revalidation contract.')
    binding=job.config.get('semantic_revalidation',{})
    parent,result,manifest,proposal,definitions=_origin(job.encounter,job.user,binding.get('parent_job_id'),
        require_current=not completed,admitted=not completed)
    if (binding!=_binding(job.encounter,job.user,parent,result,manifest,binding.get('parent_run_id'))
            or job.revision!=binding['revision'] or job.request_key!=_key(parent.pk)
            or job.config.get('semantic_fact_scope_contract')!=binding['target_scope_contract']):
        _fail('The independent check no longer matches its immutable parent and source.')
    _coding_source(job.encounter,job.user,binding.get('parent_run_id'),completed=completed)
    proposal['payload']['retained_revalidation']['binding']=deepcopy(binding)
    return proposal,definitions


def validate_stage_parent(job,payload,schema,instructions):
    proposal,_=_bound_proposal(job)
    testing_authority.validate_config(job.config,'generation')
    if (payload!=proposal['payload'] or schema!=proposal['schema'] or instructions!=proposal['instructions']):
        _fail('The one checker must receive the complete unchanged source and exact retained proposal.')


def _finish(encounter,proposal,definitions,check):
    checks,bad=semantic._check(encounter.template_version.fields,proposal['facts'],check)
    answers=semantic._apply_check(deepcopy(proposal['answers']),checks,bad)
    semantic._validate_current_numeric_answers(encounter.notes,encounter.template_version.fields,
                                              definitions,proposal['facts'],answers)
    for field in encounter.template_version.fields:
        semantic.validate_stored_answer(encounter.notes,field,definitions[field['key']],answers[field['key']])
    return answers


def validate_completed(job,answers):
    """Read-only proof revalidation for a derived coding run or Word export."""
    if job.state!='succeeded':_fail('The retained recheck did not complete successfully.')
    proposal,definitions=_bound_proposal(job,completed=True)
    rows=list(job.ai_stage_receipts.all())
    if len(rows)!=1 or rows[0].stage!=STAGE or rows[0].attempt!=1 or rows[0].state!='succeeded':
        _fail('A completed recovery requires exactly one successful independent checker receipt.')
    row=rows[0]
    envelope=_read(row.request_path,row.request_sha256)
    if (row.config!=job.config or row.actual_cost is None
            or envelope!={'protocol':ai_stages.PROTOCOL,'stage':STAGE,'attempt':1,
                'payload':proposal['payload'],'schema':proposal['schema'],'instructions':proposal['instructions'],
                'max_output_tokens':ai_stages.GENERATION_MAX_OUTPUT_TOKENS,
                'timeout_seconds':ai_stages.GENERATION_TIMEOUT_SECONDS}):
        _fail('The independent checker receipt does not bind its exact retained proposal.')
    checked=_finish(job.encounter,proposal,definitions,_output(_read(row.result_path,row.result_sha256)))
    retained=_read(job.result_path,job.result_sha256)
    if (checked!=answers or any(a['status'] not in ('supported','missing') for a in checked.values())
            or retained!={'contract':semantic.CONTRACT,'answers':checked,'stages':[str(row.pk)],
                          'revalidation':deepcopy(job.config['semantic_revalidation'])}):
        _fail('The saved recovery answers do not match their independent checker and source proof.')
    return True


def run(job):
    from .jobs import settle_semantic_stages
    from .billing import release
    try:
        proposal,definitions=_bound_proposal(job)
        check=ai_stages.execute_stage(job=job,stage=STAGE,attempt=1,payload=proposal['payload'],
            schema=proposal['schema'],instructions=proposal['instructions'],config=job.config)
        answers=_finish(job.encounter,proposal,definitions,check)
        path,sha=ai_stages.retain({'contract':semantic.CONTRACT,'answers':answers,
            'stages':[str(pk) for pk in job.ai_stage_receipts.values_list('pk',flat=True)],
            'revalidation':deepcopy(job.config['semantic_revalidation'])})
        job.result_path=path;job.result_sha256=sha;job.save(update_fields=['result_path','result_sha256'])
        settle_semantic_stages(job)
        if any(a['status'] not in ('supported','missing') for a in answers.values()):
            _fail('The independent checker retained unresolved findings. Original answers were preserved; no further inference was scheduled.')
        with transaction.atomic():
            e=Encounter.objects.select_for_update().get(pk=job.encounter_id)
            job.encounter=e
            _bound_proposal(job)
            e.answers=answers;e.template_review={};e.status='review';e.save()
            job.state='succeeded';job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
            validate_completed(job,answers)
            from .coding_recovery import derive
            derived=derive(e,job,job.config['semantic_revalidation']['parent_run_id'])
            audit(job.user,'semantic.revalidation_adopted',job.pk,department=e.department,
                  parent_job_id=job.config['semantic_revalidation']['parent_job_id'],
                  coding_run_id=str(derived.pk),provider_calls=1,clinician_approval=False)
    except Exception as exc:
        rows=list(job.ai_stage_receipts.all())
        sent=any(row.started_at is not None for row in rows)
        unresolved=any(row.actual_cost is None or row.state not in ('succeeded','failed') for row in rows)
        if sent and not unresolved and not Usage.objects.filter(job=job).exists():
            try:settle_semantic_stages(job)
            except Exception:unresolved=True
        known=Usage.objects.filter(job=job).exists()
        job.state='failed' if known or not sent and not unresolved else 'reconciliation'
        job.error=('The single retained-source check did not adopt answers. Original evidence is preserved; '
                   'do not resubmit. '+type(exc).__name__)[:250]
        job.finished_at=timezone.now()
        # Never release or replace the parent-bound request key, even after failure.
        with transaction.atomic():
            job.save(update_fields=['state','error','finished_at'])
            if not sent and not unresolved:release(job)
        audit(job.user,'semantic.revalidation_'+job.state,job.pk,department=job.encounter.department,
              error_class=type(exc).__name__,provider_calls=len(rows),automatic_retries=0)
    return True
