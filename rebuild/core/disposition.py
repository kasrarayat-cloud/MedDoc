"""Bounded review proposals. Nothing in this module grants destruction authority."""
import hashlib
import json
import os
import uuid
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from . import models as m, retention
from .security import audit
from .disposition_catalog import EDGES, COLUMNS

VERSION = 'disposition-review-v1'
LIMIT = 2000
# Restore administration records carry no patient, document or file reference: RestoreAdmission names an instance.
PREPARATION = {'DispositionRequest','DispositionPlan','DispositionReview','RestorePreparation','RestoreAdmission'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

def check_catalog():
    # Closed capability: a new model, column or relationship requires an explicit
    # graph adapter. Batch events and responses are included even after termination.
    actual = {model.__name__: sorted([f.name,f.related_model._meta.label_lower]
              for f in model._meta.get_fields() if f.is_relation and not f.auto_created)
              for model in apps.get_app_config('core').get_models() if model.__name__ not in PREPARATION}
    columns = {model.__name__: sorted([f.name,f.get_internal_type()] for f in model._meta.get_fields() if not f.auto_created or f.concrete)
               for model in apps.get_app_config('core').get_models() if model.__name__ not in PREPARATION}
    if actual != EDGES or columns != COLUMNS:
        raise ValidationError('The reference catalogue changed; a reviewed graph adapter is required.')

def scoped_target(department_id, scope, target_id, *, lock=False):
    if scope not in ('patient','encounter'):raise ValidationError('Only patient or document proposals are supported.')
    model = m.Patient if scope == 'patient' else m.Encounter
    query = model.objects.select_for_update() if lock else model.objects
    try:return query.get(pk=target_id,department_id=department_id)
    except (model.DoesNotExist,ValueError,ValidationError):raise ValidationError('The target does not belong to this department.') from None

def graph(request):
    """Private row identities/hashes, never clinical bodies or deletion eligibility.

    Complete only for this explicit root/edge capability. External copy ownership
    and policy remain unresolved even when all database queries succeed.
    """
    check_catalog()
    scoped_target(request.department_id,request.scope,request.target_id)
    rows = {}; paths = set(); blockers = {'policy_unset','external_copies_unverified','deletion_unavailable'}
    total = 0
    def collect(name, query):
        nonlocal total
        records = list(query.order_by('pk').values()[:LIMIT-total+1])
        total += len(records)
        if total > LIMIT:raise ValidationError('The complete graph exceeds the review limit; no partial plan was recorded.')
        rows[name] = [{'id':str(v['id']), 'sha256':digest(v)} for v in records]
        for record in records:
            for key in ('input_path','result_path','original_path','export_path','storage_key'):
                if record.get(key):paths.add(record[key])
        return records
    patients = m.Patient.objects.filter(pk=request.target_id) if request.scope=='patient' else m.Patient.objects.filter(encounter__pk=request.target_id)
    patient_rows=collect('Patient',patients); patient_ids=[v['id'] for v in patient_rows]
    encounters=m.Encounter.objects.filter(patient_id__in=patient_ids)
    if request.scope=='encounter':encounters=encounters.filter(pk=request.target_id)
    es=collect('Encounter',encounters); eids=[v['id'] for v in es]; vids={v['template_version_id'] for v in es}
    versions=collect('TemplateVersion',m.TemplateVersion.objects.filter(pk__in=vids))
    tids={v['template_id'] for v in versions}
    collect('Template',m.Template.objects.filter(pk__in=tids))
    collect('MappingConfirmation',m.MappingConfirmation.objects.filter(version_id__in=vids))
    batches=collect('GenerationBatch',m.GenerationBatch.objects.filter(encounter_id__in=eids))
    batch_ids=[v['id'] for v in batches]
    parts=collect('GenerationBatchPart',m.GenerationBatchPart.objects.filter(batch_id__in=batch_ids))
    part_ids=[v['id'] for v in parts]
    collect('GenerationBatchEvent',m.GenerationBatchEvent.objects.filter(batch_id__in=batch_ids))
    collect('GenerationBatchResponse',m.GenerationBatchResponse.objects.filter(part_id__in=part_ids))
    if any(v['state'] in ('queued','running','validating','reconciliation') for v in batches):
        blockers.add('work_or_finance_unresolved')
    js=collect('Job',m.Job.objects.filter(Q(encounter_id__in=eids)|Q(mapping_version_id__in=vids)))
    jids=[v['id'] for v in js]
    if any(v['state'] in ('queued','running','staged','validating','reconciliation') for v in js):blockers.add('work_or_finance_unresolved')
    collect('CodeSuggestion',m.CodeSuggestion.objects.filter(encounter_id__in=eids))
    reservations=collect('Reservation',m.Reservation.objects.filter(job_id__in=jids))
    if any(v['state']=='held' for v in reservations):blockers.add('funds_held')
    usage=collect('Usage',m.Usage.objects.filter(job_id__in=jids))
    receipts=collect('ProviderReceipt',m.ProviderReceipt.objects.filter(job_id__in=jids))
    costs=collect('PlatformCost',m.PlatformCost.objects.filter(job_id__in=jids))
    for receipt in receipts:
        if not any(v['job_id']==receipt['job_id'] for v in usage) and not any(
                v['job_id']==receipt['job_id'] and v['kind']=='absorbed_failure' and v['amount']==receipt['actual_cost'] for v in costs):
            blockers.add('receipt_accounting_unresolved')
    ledger=collect('LedgerEntry',m.LedgerEntry.objects.filter(job_id__in=jids))
    wallets={v['wallet_id'] for v in reservations+ledger}
    collect('Wallet',m.Wallet.objects.filter(pk__in=wallets))
    payments=collect('Payment',m.Payment.objects.filter(wallet_id__in=wallets))
    refunds=collect('Refund',m.Refund.objects.filter(payment_id__in=[v['id'] for v in payments]))
    reconciliations=collect('CostReconciliation',m.CostReconciliation.objects.filter(usage_id__in=[v['id'] for v in usage]))
    if (any(v['status'] not in ('paid','failed','expired') for v in payments)
        or any(v['status'] not in ('succeeded','failed','canceled') for v in refunds)
        or any(v['ledger_status']=='pending_funds' for v in reconciliations)):
        blockers.add('financial_history_unresolved')
    collect('Department',m.Department.objects.filter(pk=request.department_id))
    dept=m.Department.objects.get(pk=request.department_id)
    collect('Organization',m.Organization.objects.filter(pk=dept.organization_id))
    collect('DispositionPolicyAdmission',m.DispositionPolicyAdmission.objects.filter(department_id=request.department_id))
    instruction_scope=Q(target_id__in=eids)
    if request.scope=='patient':
        # The empty row may already be gone. Its immutable preparation snapshot
        # retains the patient identity; deletion cannot erase review history.
        instruction_scope |= Q(source_snapshot__patient_id=str(request.target_id))
    instructions=collect('DispositionInstruction',m.DispositionInstruction.objects.filter(instruction_scope))
    instruction_ids=[v['id'] for v in instructions]
    collect('DispositionApproval',m.DispositionApproval.objects.filter(instruction_id__in=instruction_ids))
    tombstones=collect('DispositionTombstone',m.DispositionTombstone.objects.filter(Q(target_id__in=eids)|Q(instruction_id__in=instruction_ids)))
    collect('DispositionCompletion',m.DispositionCompletion.objects.filter(tombstone_id__in=[v['id'] for v in tombstones]))
    if tombstones:blockers.add('disposed_target')
    holds=collect('RetentionHold',m.RetentionHold.objects.filter(Q(scope='global')|Q(organization_id=dept.organization_id)|Q(department_id=dept.pk)|Q(patient_id__in=patient_ids)|Q(encounter_id__in=eids)))
    releases=collect('RetentionHoldRelease',m.RetentionHoldRelease.objects.filter(hold_id__in=[v['id'] for v in holds]))
    collect('RetentionHoldReplay',m.RetentionHoldReplay.objects.filter(hold_id__in=[v['id'] for v in holds]))
    if holds:blockers.add('historical_preservation')
    if any(v['id'] not in {x['hold_id'] for x in releases} for v in holds):blockers.add('active_hold')
    source_ids=[v['id'] for values in rows.values() for v in values]
    archives=collect('PreservedRecord',m.PreservedRecord.objects.filter(source_id__in=source_ids))
    for record in archives:
        for key in ('input_path','result_path','original_path','export_path'):
            if record['prior_record'].get(key):paths.add(record['prior_record'][key])
    preserved=collect('PreservedFile',m.PreservedFile.objects.filter(storage_key__in=paths))
    if archives or preserved:blockers.add('preserved_evidence')
    collect('FileCreationEvidence',m.AuditEvent.objects.filter(action='retention.file_creation',target__in=paths))
    shared = [
        ('SharedEncounter',m.Encounter.objects.filter(Q(template_version_id__in=vids)|Q(export_path__in=paths)).exclude(pk__in=eids)),
        ('SharedJob',m.Job.objects.filter(Q(input_path__in=paths)|Q(result_path__in=paths)).exclude(pk__in=jids)),
        ('SharedReceipt',m.ProviderReceipt.objects.filter(result_path__in=paths).exclude(job_id__in=jids)),
        ('SharedBatchResponse',m.GenerationBatchResponse.objects.filter(result_path__in=paths).exclude(part_id__in=part_ids)),
        ('SharedTemplate',m.Template.objects.filter(original_path__in=paths).exclude(pk__in=tids)),
        ('SharedArchive',m.PreservedRecord.objects.filter(Q(prior_record__input_path__in=paths)|Q(prior_record__result_path__in=paths)
            |Q(prior_record__original_path__in=paths)|Q(prior_record__export_path__in=paths)).exclude(source_id__in=source_ids)),
    ]
    for label,query in shared:
        if collect(label,query):blockers.add('shared_reference')
    if paths:blockers.add('file_bytes_unverified')
    if versions or ledger or usage or receipts or any(v['status']=='finalized' for v in es):blockers.add('immutable_evidence')
    # Accounts/access, audit bodies, provider copies and terminology have no
    # disposal adapter in this narrow root contract. Do not label it a purge graph.
    return {'contract':VERSION,'scope':request.scope,'target_id':str(request.target_id),
            'department_id':str(request.department_id),'nodes':rows,'storage_keys':sorted(paths),
            'blockers':sorted(blockers),'deletion_authorized':False,
            'coverage':'review_dependencies_only','batch_capability':'batch-v1'}

@transaction.atomic
def submit(actor,department_id,scope,target_id,authority,request_key):
    retention.custodian(actor);retention.authority_hash(authority)
    target=scoped_target(department_id,scope,target_id,lock=True)
    try:key=uuid.UUID(str(request_key))
    except (ValueError,TypeError,AttributeError):raise ValidationError('Invalid request key.') from None
    old=m.DispositionRequest.objects.filter(request_key=key).first()
    if old:
        if (old.created_by_id,old.department_id,old.scope,old.target_id,old.authority_sha256)!=(actor.pk,target.department_id,scope,target.pk,authority):
            raise ValidationError('This request key belongs to another proposal.')
        return old
    row=m.DispositionRequest.objects.create(department_id=target.department_id,scope=scope,target_id=target.pk,
        authority_sha256=authority,request_key=key,created_by=actor)
    audit(actor,'disposition.requested',row.pk,department=target.department)
    return row

@transaction.atomic
def prepare(actor,request_id):
    retention.custodian(actor)
    request=m.DispositionRequest.objects.select_for_update().get(pk=request_id)
    value=graph(request)
    row=m.DispositionPlan.objects.create(request=request,graph=value,graph_sha256=digest(value),created_by=actor)
    audit(actor,'disposition.planned',row.pk,department=request.department)
    return row

@transaction.atomic
def review(actor,plan_id,expected_digest,decision,evidence):
    retention.custodian(actor);retention.authority_hash(evidence)
    plan=m.DispositionPlan.objects.select_for_update().select_related('request').get(pk=plan_id)
    if actor.pk in (plan.created_by_id,plan.request.created_by_id):raise PermissionDenied('A distinct administrator must review this proposal.')
    if decision not in ('reviewed','rejected'):raise ValidationError('Invalid review decision.')
    if expected_digest!=plan.graph_sha256 or digest(plan.graph)!=plan.graph_sha256 or digest(graph(plan.request))!=expected_digest:
        raise ValidationError('The graph changed; prepare a new plan before review.')
    old=m.DispositionReview.objects.filter(plan=plan).first()
    if old:
        if (old.created_by_id,old.decision,old.evidence_sha256)!=(actor.pk,decision,evidence):raise ValidationError('This plan already has another review.')
        return old
    row=m.DispositionReview.objects.create(plan=plan,decision=decision,graph_sha256=expected_digest,evidence_sha256=evidence,created_by=actor)
    audit(actor,'disposition.reviewed',row.pk,department=plan.request.department,decision=decision)
    return row

_ADMITTED=set()
_ACCOUNTED={}

def quarantined():
    """Quarantine lifts only against a RestoreAdmission record for the selected restore instance, and only while this
    database still accounts for everything the independent journal preserves.

    QUILLMD_RESTORE_QUARANTINE=1 always quarantines. With it off, a configured QUILLMD_RESTORE_INSTANCE_ID still
    quarantines until core.restore_admission has recorded that instance's admission; an unreadable id or database is
    quarantined. Nothing in a restored database marks it as restored, so the operator keeps the instance id configured
    (cutover plan). A found record is cached: admission records are append-only."""
    if getattr(settings,'RESTORE_QUARANTINE',False):return True
    instance=getattr(settings,'RESTORE_INSTANCE_ID','')
    if not instance:return False
    return not restore_admitted(instance)

def restore_admitted(instance):
    try:key=str(uuid.UUID(str(instance)))
    except (ValueError,TypeError,AttributeError):return False
    if key not in _ADMITTED:
        try:found=m.RestoreAdmission.objects.filter(instance_id=key).exists()
        except DatabaseError:return False
        if not found:return False
        _ADMITTED.add(key)
    return journal_accounted(key)

def journal_accounted(key):
    """Admission is not a one-time latch: the journal can grow after it (another host's hold, a release, a hold whose
    commit failed here). The admitted target serves only while every journaled hold and release is in this database
    or recorded by a replay marker (retention.unaccounted_journal_records); otherwise it is quarantined again until the
    replay, which runs while quarantined, imports it. A missing, unconfigured or unverifiable journal is quarantined.

    Re-checked whenever the journal file changes (it is append-only; any change of identity, size or time re-reads
    it). A hold being committed on this host is journaled first, under the preservation lock: outside a transaction
    the check waits for that lock before it believes a hold is missing, so a concurrent request is not quarantined by
    this host's own hold. Inside a transaction it does not wait (it could invert the global lock order) and answers
    quarantined until the hold commits."""
    path=getattr(settings,'DISPOSITION_JOURNAL_PATH','')
    if not path:return False
    try:meta=os.stat(path)
    except OSError:return False
    identity=(key,str(path),meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns)
    if _ACCOUNTED.get(key)==identity:return True
    try:
        missing=retention.unaccounted_journal_records()
        if missing and not connection.in_atomic_block:
            with transaction.atomic():
                retention.lock_preservation()
                missing=retention.unaccounted_journal_records()
    except (ValidationError,DatabaseError):return False
    if missing:return False
    _ACCOUNTED[key]=identity
    return True

def require_processing():
    if quarantined():raise ValidationError('This restored target is quarantined; processing is unavailable.')

@transaction.atomic
def prepare_restore(actor,instance_id,backup_sha256):
    retention.custodian(actor);retention.authority_hash(backup_sha256)
    try:instance=uuid.UUID(str(instance_id));selected=uuid.UUID(str(getattr(settings,'RESTORE_INSTANCE_ID','')))
    except (ValueError,TypeError,AttributeError):raise ValidationError('An independently selected restore target is required.') from None
    if not quarantined() or instance!=selected:raise ValidationError('The restore target does not match quarantine configuration.')
    db=settings.DATABASES['default']
    target={'instance_id':str(instance),'database_host':str(db['HOST']),'database_port':str(db['PORT']),
            'database_name':str(db['NAME']),'state_root':str(settings.MEDIA_ROOT.resolve())}
    if not all(target.values()):raise ValidationError('The restore target is incomplete.')
    report={'contract':'restore-preparation-v1','target':target,'backup_sha256':backup_sha256,
            'quarantined':True,'admission_available':False,'journal_freshness_verified':False,
            'blockers':['independent_journal_unverified','journal_replay_pending','restore_admission_pending']}
    row=m.RestorePreparation.objects.create(instance_id=instance,target=target,backup_sha256=backup_sha256,
        report=report,report_sha256=digest(report),created_by=actor)
    audit(actor,'disposition.restore_prepared',row.pk)
    return row

class RestoreQuarantineMiddleware:
    SAFE = frozenset(('/health/','/login/','/logout/','/mfa/','/preview/sign-in/','/preview/sign-out/',
                      '/console/disposition/','/console/restore-preparation/','/console/disposition-execution/'))
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        # On PATH_INFO, the path Django resolves: the full path carries a client SCRIPT_NAME, and SCRIPT_NAME '/login' with
        # PATH_INFO '/' spelled the safe '/login/' while the dashboard was served (refutation round 2, the R1 sibling).
        path=request.path_info
        if quarantined() and path not in self.SAFE and not path.startswith('/static/'):
            from django.http import HttpResponse
            return HttpResponse('Restored target quarantined. Clinical access and processing are unavailable.',status=503)
        return self.get_response(request)
