"""Aggregate retention preparation only. No deletion, file inventory or eligibility decision.

The catalog is explicit: new models/routes require review, never automatic aging or
an inferred retention rule. A policy declaration is not verified legal authority.
"""
import hashlib
import json
from datetime import timedelta
from typing import Annotated, Literal
from django.apps import apps
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION='retention-readiness-v1'
MAX_POLICY_BYTES=65536

# class: (model label, optional fixed filter, permitted explicitly chosen review anchors,
#         immutable/protected-for-this-tool). A count is rows/references, never verified files.
CATALOG={
 'disposition_policy_admissions':('core.DispositionPolicyAdmission',{},('created_at',),True),
 'disposition_instructions':('core.DispositionInstruction',{},('created_at',),True),
 'disposition_approvals':('core.DispositionApproval',{},('created_at',),True),
 'disposition_tombstones':('core.DispositionTombstone',{},('created_at',),True),
 'disposition_completions':('core.DispositionCompletion',{},('created_at',),True),
 'disposition_requests':('core.DispositionRequest',{},('created_at',),True),
 'disposition_plans':('core.DispositionPlan',{},('created_at',),True),
 'disposition_reviews':('core.DispositionReview',{},('created_at',),True),
 'restore_preparations':('core.RestorePreparation',{},('created_at',),True),
 'restore_admissions':('core.RestoreAdmission',{},('created_at',),True),
 'retention_hold_replays':('core.RetentionHoldReplay',{},('created_at',),True),
 'redaction_requests':('core.RedactionRequest',{},('created_at',),True),
 'redaction_tombstones':('core.RedactionTombstone',{},('created_at',),True),
 'retention_holds':('core.RetentionHold',{},('created_at',),True),
 'retention_hold_releases':('core.RetentionHoldRelease',{},('created_at',),True),
 'preserved_clinical_rows':('core.PreservedRecord',{},('created_at',),True),
 'preserved_file_references':('core.PreservedFile',{},('created_at',),True),
 'accounts':('core.User',{},('date_joined',),False),
 'organizations':('core.Organization',{},('created_at',),False),
 'departments':('core.Department',{},('created_at',),False),
 'memberships':('core.Membership',{},('created_at',),False),
 'department_invitations':('core.Invitation',{},('created_at','expires_at'),False),
 'clinic_invitations':('core.ClinicInvitation',{},('created_at','expires_at'),False),
 'verification_tokens':('core.Verification',{},('created_at','expires_at'),False),
 'sessions':('sessions.Session',{},('expire_date',),False),
 'mfa_devices':('otp_totp.TOTPDevice',{},(),False),
 'login_throttles':('core.LoginAttempt',{},('created_at','window_start'),False),
 'patient_identity':('core.Patient',{},('created_at',),False),
 'template_original_references':('core.Template',{'original_path__gt':''},('created_at',),True),
 'mapping_versions':('core.TemplateVersion',{},('created_at',),True),
 'mapping_confirmations':('core.MappingConfirmation',{},('created_at',),True),
 'draft_clinical_records':('core.Encounter',{'status':'draft'},('created_at',),False),
 'finalized_clinical_records':('core.Encounter',{'status':'finalized'},('finalized_at',),True),
 'clinical_records_other_status':('core.Encounter',{'exclude_status':['draft','finalized']},('created_at',),False),
 'final_export_references':('core.Encounter',{'export_path__gt':''},('finalized_at',),True),
 'jobs':('core.Job',{},('created_at','finished_at'),True),
 'generation_batches':('core.GenerationBatch',{},('created_at','finished_at'),True),
 'generation_parts':('core.GenerationBatchPart',{},('created_at',),True),
 'generation_attempt_events':('core.GenerationBatchEvent',{},('created_at',),True),
 'generation_response_references':('core.GenerationBatchResponse',{},('created_at',),True),
 'recording_references':('core.Job',{'input_path__gt':''},('created_at','finished_at'),False),
 'job_result_references':('core.Job',{'result_path__gt':''},('created_at','finished_at'),True),
 'receipt_result_references':('core.ProviderReceipt',{'result_path__gt':''},('created_at',),True),
 'code_suggestions':('core.CodeSuggestion',{},('created_at',),False),
 'wallets':('core.Wallet',{},('created_at',),True),
 'ledger':('core.LedgerEntry',{},('created_at',),True),
 'reservations':('core.Reservation',{},('created_at',),True),
 'usage':('core.Usage',{},('created_at',),True),
 'payments':('core.Payment',{},('created_at',),True),
 'payment_events':('core.WebhookEvent',{},('created_at',),True),
 'refunds':('core.Refund',{},('created_at',),True),
 'provider_receipts':('core.ProviderReceipt',{},('created_at',),True),
 'reconciliations':('core.CostReconciliation',{},('created_at',),True),
 'platform_costs':('core.PlatformCost',{},('created_at',),True),
 'audit':('core.AuditEvent',{},('created_at',),True),
 'service_status':('core.ServiceHealth',{},('created_at',),False),
 'terminology_releases':('core.CodeSet',{},('created_at',),True),
 'terminology_codes':('core.Code',{},('created_at',),True),
}
EXTERNAL=('legal_hold_registry','state_file_inventory','rds_pitr','aws_backup_rds','aws_backup_ebs',
 'cross_account_locked_copies','legacy_encrypted_offsite','anthropic_account','deepgram_account',
 'invitation_recovery_email','stripe_records','host_ssm_security_logs','downloaded_exports')

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class Rule(Strict):
    mode:Literal['unresolved','review_window','preserve']
    anchor:str|None
    days:Annotated[int,Field(ge=1,le=365000)]|None

    @model_validator(mode='after')
    def coherent(self):
        if self.mode=='review_window':
            if self.anchor is None or self.days is None:raise ValueError('incomplete_rule')
        elif self.anchor is not None or self.days is not None:raise ValueError('unexpected_window')
        return self

class Policy(Strict):
    contract:Literal['retention-readiness-v1']
    schedule_document_sha256:Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]|None
    coverage:dict[str,Literal['unresolved','declared_for_review']]
    classes:dict[str,Rule]

    @model_validator(mode='after')
    def complete(self):
        if set(self.classes)!=set(CATALOG) or set(self.coverage)!=set(EXTERNAL):raise ValueError('incomplete_catalog')
        for name,rule in self.classes.items():
            _,_,anchors,protected=CATALOG[name]
            if rule.mode=='review_window' and (protected or rule.anchor not in anchors):raise ValueError('unsupported_window')
        if any(rule.mode=='review_window' for rule in self.classes.values()) and self.schedule_document_sha256 is None:
            raise ValueError('missing_schedule_reference')
        return self

class PolicyError(ValueError):
    """Fixed error messages only: never return untrusted policy values or paths."""

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'))

def unresolved_policy():
    return {'contract':VERSION,'schedule_document_sha256':None,
            'coverage':{name:'unresolved' for name in EXTERNAL},
            'classes':{name:{'mode':'unresolved','anchor':None,'days':None} for name in CATALOG}}

def policy_schema():
    """Publish the same closed catalog; the command remains the authority for validation."""
    schema=Policy.model_json_schema()
    schema['$schema']='https://json-schema.org/draft/2020-12/schema'
    schema['description']='Review declarations only. Shape validation never grants deletion authority.'
    schema['properties']['coverage']={'type':'object','additionalProperties':False,'required':list(EXTERNAL),
        'properties':{name:{'enum':['unresolved','declared_for_review']} for name in EXTERNAL}}
    rules={};windows=[]
    for name,(_,_,anchors,protected) in CATALOG.items():
        variants=[{'type':'object','additionalProperties':False,'required':['mode','anchor','days'],
                   'properties':{'mode':{'const':mode},'anchor':{'type':'null'},'days':{'type':'null'}}}
                  for mode in ('unresolved','preserve')]
        if anchors and not protected:
            variants.append({'type':'object','additionalProperties':False,'required':['mode','anchor','days'],
                'properties':{'mode':{'const':'review_window'},'anchor':{'enum':list(anchors)},
                              'days':{'type':'integer','minimum':1,'maximum':365000}}})
            windows.append({'properties':{name:{'properties':{'mode':{'const':'review_window'}}}},'required':[name]})
        rules[name]={'oneOf':variants}
    schema['properties']['classes']={'type':'object','additionalProperties':False,'required':list(CATALOG),'properties':rules}
    schema['allOf']=[{'if':{'properties':{'classes':{'anyOf':windows}}},
                     'then':{'properties':{'schedule_document_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}}}}]
    return schema

def parse_policy(raw):
    if not isinstance(raw,bytes) or len(raw)>MAX_POLICY_BYTES:raise PolicyError('policy_size_refused')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise PolicyError('duplicate_policy_member')
            result[key]=value
        return result
    try:
        value=json.loads(raw,object_pairs_hook=unique)
        return Policy.model_validate(value)
    except (ValueError,TypeError,RecursionError,UnicodeError):
        raise PolicyError('policy_invalid_or_incomplete') from None

def count_class(name,rule,now):
    model_label,filters,_,protected=CATALOG[name]
    query=apps.get_model(model_label).objects.all()
    filters=dict(filters)
    excluded=filters.pop('exclude_status',None)
    if excluded:query=query.exclude(status__in=excluded)
    query=query.filter(**filters)
    counters={'records':Count('pk')}
    if rule.mode=='review_window':
        cutoff=now-timedelta(days=rule.days)
        counters['at_or_before_review_cutoff']=Count('pk',filter=Q(**{rule.anchor+'__lte':cutoff}))
        counters['missing_review_anchor']=Count('pk',filter=Q(**{rule.anchor+'__isnull':True}))
    counted=query.aggregate(**counters)
    return {'class':name,'count_unit':'database_reference_rows' if name.endswith('_references') else 'database_rows',
            **counted,'at_or_before_review_cutoff':counted.get('at_or_before_review_cutoff'),
            'missing_review_anchor':counted.get('missing_review_anchor'),
            'policy_mode':rule.mode,'protected_by_this_tool':protected,'deletion_eligible_count':None}

def report(policy,now=None):
    """PostgreSQL enforces read-only on the exact transaction containing every count."""
    if not isinstance(policy,Policy):raise PolicyError('validated_policy_required')
    policy=Policy.model_validate(policy.model_dump())
    if connection.vendor!='postgresql' or connection.in_atomic_block:
        raise PolicyError('standalone_postgresql_read_only_transaction_required')
    now=now or timezone.now()
    if timezone.is_naive(now):raise PolicyError('aware_timestamp_required')
    blockers=['tombstone_and_deletion_workflow_not_implemented','legal_hold_external_and_restore_reconciliation_unverified',
              'external_policy_authority_not_verified','purge_unavailable']
    if any(rule.mode=='unresolved' for rule in policy.classes.values()):blockers.append('schedule_incomplete')
    if any(state=='unresolved' for state in policy.coverage.values()):blockers.append('external_coverage_unresolved')
    with transaction.atomic(durable=True):
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute('SHOW transaction_read_only')
            if cursor.fetchone()!=('on',):raise PolicyError('read_only_not_enforced')
        rows=[count_class(name,policy.classes[name],now) for name in CATALOG]
    return {'contract':VERSION,'status':'blocked','purpose':'aggregate_review_only',
            'as_of':now.isoformat(),'policy_sha256':hashlib.sha256(canonical(policy.model_dump()).encode()).hexdigest(),
            'policy_authority_verified':False,'purge_available':False,'deletion_eligibility_assessed':False,
            'database_transaction':'repeatable_read_read_only','file_contents_read':False,
            'file_existence_or_integrity_checked':False,'external_accounts_checked':False,
            'blockers':blockers,'rows':rows,
            'external_inventory':[{'class':name,'declaration':policy.coverage[name],'verified':False} for name in EXTERNAL]}
