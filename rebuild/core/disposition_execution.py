"""Executable empty-draft adapter; all richer clinical/financial graphs refuse.

The policy and instruction journal are independently signed. New instruction rows
never promote historical review-only proposals. No external copy is removed and
no restored target is released by this module.
"""
import uuid
import json
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, connection
from django.db.models import Q
from django.utils import timezone

from . import disposition as d, disposition_journal as journal, disposition_policy as p
from . import models as m, retention
from .security import audit


def enabled():
    if not getattr(settings, 'DISPOSITION_ENABLED', False):
        raise ValidationError('Executable disposition is unavailable; no approved policy is installed.')


class DocumentUnavailable(ValidationError):
    """The document was disposed of, or has a disposition instruction: the request is refused, never a crash."""


def require_access(target_id, *, own_instruction=None):
    target = str(target_id)
    if m.DispositionTombstone.objects.filter(target_id=target).exists():
        raise DocumentUnavailable('This document has a disposition instruction and is unavailable.')
    if getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''):
        for entry in journal.verified():
            instruction = entry['body']['instruction']
            if instruction['target_id'] == target and instruction['id'] != str(own_instruction):
                raise DocumentUnavailable('This document has a durable disposition instruction and is unavailable.')


def lock_available(target_id):
    """Lock, for writing, a document the caller read earlier in another transaction (a request's page lookup).

    Disposition deletes an exact empty draft, and it may commit between that read and this lock: select_for_update()
    then finds no row. That is a refusal the clinician is told about, never Encounter.DoesNotExist (RF-3). Only
    disposition deletes an encounter (every reference is PROTECT), so a missing row means disposed."""
    row = m.Encounter.objects.select_for_update().filter(pk=target_id).first()
    if row is None:
        raise DocumentUnavailable('This document is no longer available. Nothing was queued, sent or charged.')
    require_access(row.pk)
    return row


def available(query):
    # Configured-but-unreadable journal is an explicit failure, never an empty
    # deny-list. This includes intent persisted before a failed DB transaction.
    return query.exclude(pk__in=m.DispositionTombstone.objects.values('target_id')).exclude(pk__in=journal.pending_targets())


def policy_body(admission, now):
    if p.digest(admission.envelope) != admission.envelope_sha256:
        raise ValidationError('The admitted policy identity changed.')
    body = p.verify_policy(admission.envelope, settings.DISPOSITION_AUTHORITY_KEYS,
                           namespace=journal.namespace(), now=now)
    if (str(admission.policy_id) != body.policy_id or str(admission.department_id) != body.department_id
            or admission.created_at > p.timestamp(body.not_before)):
        raise ValidationError('The admitted policy is not prospective or does not match this scope.')
    return body


def snapshot(target_id):
    # PostgreSQL's own JSON representation also powers the independent DELETE
    # guard. This exact-empty adapter never stores clinical bodies here.
    with connection.cursor() as cursor:
        cursor.execute('SELECT to_jsonb(e) FROM core_encounter e WHERE id=%s', [target_id])
        value = cursor.fetchone()[0]
    return json.loads(value) if isinstance(value, str) else value


@transaction.atomic
def admit(actor, envelope):
    enabled(); d.require_processing(); retention.custodian(actor)
    body = p.verify_policy(envelope, settings.DISPOSITION_AUTHORITY_KEYS,
                           namespace=journal.namespace(), now=timezone.now())
    if p.timestamp(body.not_before) < timezone.now():
        raise ValidationError('A new admission must authorize only a prospective cohort.')
    journal.verified()  # Initialized independent destination, never a hash-only declaration.
    old = m.DispositionPolicyAdmission.objects.filter(policy_id=body.policy_id).first()
    if old:
        if old.envelope != envelope or old.created_by_id != actor.pk:
            raise ValidationError('The policy identity already has another admission.')
        return old
    row = m.DispositionPolicyAdmission.objects.create(policy_id=body.policy_id, department_id=body.department_id,
        envelope=envelope, envelope_sha256=p.digest(envelope), created_by=actor)
    policy_body(row, timezone.now())
    audit(actor, 'disposition.policy_admitted', row.pk, department=row.department,
          policy_sha256=row.envelope_sha256, adapter=p.ADAPTER)
    return row


def eligible(encounter, admission, *, own_instruction=None):
    """Caller locks Encounter before the existing preservation lock, at READ COMMITTED."""
    d.check_catalog(); retention.lock_preservation()
    require_access(encounter.pk, own_instruction=own_instruction)
    now = timezone.now(); policy = policy_body(admission, now)
    if (encounter.department_id != admission.department_id
            or encounter.created_at < p.timestamp(policy.not_before)
            or now < encounter.created_at + timedelta(seconds=policy.minimum_age_seconds)):
        raise ValidationError('This draft is outside the approved prospective retention scope.')
    if (encounter.status != 'draft' or encounter.revision != 0 or encounter.notes != '' or encounter.answers != {}
            or encounter.template_review != {} or encounter.finalized_at is not None or encounter.finalized_by_id is not None
            or encounter.export_path != '' or encounter.export_sha256 != ''):
        raise ValidationError('Only an exactly empty, unreviewed, unfinalized draft is supported.')
    if (m.Job.objects.filter(encounter=encounter).exists() or m.GenerationBatch.objects.filter(encounter=encounter).exists()
            or m.CodeSuggestion.objects.filter(encounter=encounter).exists()
            or retention.scoped_holds(encounter_id=encounter.pk).exists()
            or m.PreservedRecord.objects.filter(Q(source_id=encounter.pk) |
                                               Q(prior_record__encounter_id=str(encounter.pk))).exists()
            or m.AuditEvent.objects.filter(target=str(encounter.pk)).exclude(action__in=['encounter.create', 'encounter.view']).exists()):
        raise ValidationError('Work, review, financial or preservation history makes this adapter unavailable.')
    return p.digest(snapshot(encounter.pk))


@transaction.atomic
def prepare(actor, admission_id, target_id, request_key):
    enabled(); d.require_processing(); retention.custodian(actor)
    admission = m.DispositionPolicyAdmission.objects.get(pk=admission_id)
    encounter = m.Encounter.objects.select_for_update().get(pk=target_id)
    fingerprint = eligible(encounter, admission)
    key = uuid.UUID(p.identity(str(request_key)))
    old = m.DispositionInstruction.objects.filter(request_key=key).first()
    if old:
        if (old.policy_id, old.target_id, old.snapshot_sha256, old.created_by_id) != (
                admission.pk, encounter.pk, fingerprint, actor.pk):
            raise ValidationError('The instruction request key already has another target or body.')
        return old
    row = m.DispositionInstruction.objects.create(policy=admission, target_id=encounter.pk,
        department=encounter.department, snapshot_sha256=fingerprint, source_created_at=encounter.created_at,
        source_snapshot=snapshot(encounter.pk), request_key=key, created_by=actor)
    audit(actor, 'disposition.instruction_prepared', row.pk, department=row.department, snapshot_sha256=fingerprint)
    return row


@transaction.atomic
def approve(actor, instruction_id, expected_digest):
    enabled(); d.require_processing(); retention.custodian(actor)
    instruction = m.DispositionInstruction.objects.select_related('policy').get(pk=instruction_id)
    if actor.pk == instruction.created_by_id:
        raise PermissionDenied('A distinct verified custodian must approve the exact target.')
    encounter = m.Encounter.objects.select_for_update().get(pk=instruction.target_id)
    if expected_digest != instruction.snapshot_sha256 or eligible(encounter, instruction.policy) != expected_digest:
        raise ValidationError('The exact draft changed; a new instruction is required.')
    old = m.DispositionApproval.objects.filter(instruction=instruction).first()
    if old:
        if old.created_by_id != actor.pk: raise ValidationError('This instruction already has another review.')
        return old
    row = m.DispositionApproval.objects.create(instruction=instruction, snapshot_sha256=expected_digest, created_by=actor)
    audit(actor, 'disposition.instruction_approved', instruction.pk, department=instruction.department,
          snapshot_sha256=expected_digest)
    return row


def instruction_body(instruction, approval):
    return {'id': str(instruction.pk), 'department_id': str(instruction.department_id),
            'target_id': str(instruction.target_id), 'snapshot_sha256': instruction.snapshot_sha256,
            'source_created_at': instruction.source_created_at.isoformat(), 'policy': instruction.policy.envelope,
            'policy_admitted_at': instruction.policy.created_at.isoformat(),
            'created_by': str(instruction.created_by_id), 'created_at': instruction.created_at.isoformat(),
            'approved_by': str(approval.created_by_id), 'approved_at': approval.created_at.isoformat()}


def _import_tombstone(entry):
    journal.validate_entry(entry, entry['body']['sequence'], entry['body']['previous_sha256'])
    body = entry['body']; instruction = body['instruction']; fingerprint = p.digest(entry)
    old = m.DispositionTombstone.objects.filter(target_id=instruction['target_id']).first()
    if old:
        if old.entry_sha256 != fingerprint or old.journal_entry != entry:
            raise ValidationError('The restored tombstone conflicts with the independent journal.')
        return old
    return m.DispositionTombstone.objects.create(target_id=instruction['target_id'],
        department_id=instruction['department_id'], instruction_id=instruction['id'],
        journal_entry=entry, entry_sha256=fingerprint)


@transaction.atomic
def execute(actor, instruction_id, checkpoint_envelope):
    enabled(); d.require_processing(); retention.custodian(actor)
    instruction = m.DispositionInstruction.objects.select_related('policy', 'created_by', 'approval__created_by').get(pk=instruction_id)
    completed = m.DispositionCompletion.objects.filter(tombstone__instruction_id=instruction.pk).first()
    if completed: return completed
    approval = instruction.approval
    retention.custodian(instruction.created_by); retention.custodian(approval.created_by)
    if instruction.created_by_id == approval.created_by_id or approval.snapshot_sha256 != instruction.snapshot_sha256:
        raise ValidationError('Distinct exact approval is required.')
    encounter = m.Encounter.objects.select_for_update().get(pk=instruction.target_id)
    if eligible(encounter, instruction.policy, own_instruction=instruction.pk) != instruction.snapshot_sha256:
        raise ValidationError('The exact draft changed; no disposition was performed.')
    entry = journal.append(instruction_body(instruction, approval), checkpoint_envelope)
    tombstone = _import_tombstone(entry)
    # The additive DB guard independently rechecks the empty draft, dependencies
    # and historical holds. No immutable-history guard is disabled or replaced.
    count, detail = m.Encounter.objects.filter(pk=encounter.pk).delete()
    if count != 1 or detail != {'core.Encounter': 1}:
        raise ValidationError('The local disposition outcome is unresolved.')
    result = m.DispositionCompletion.objects.create(tombstone=tombstone, outcome='empty_draft_deleted', created_by=actor)
    audit(actor, 'disposition.empty_draft_deleted', instruction.pk, department=instruction.department,
          journal_sha256=tombstone.entry_sha256)
    return result


@transaction.atomic
def replay(actor, checkpoint_envelope):
    """Import durable suppression only. Conflicting restored content is preserved."""
    retention.custodian(actor)
    if not d.quarantined(): raise ValidationError('Journal replay requires a quarantined restored target.')
    p.identity(getattr(settings, 'RESTORE_INSTANCE_ID', ''))
    entries = journal.verified(checkpoint_envelope)
    # Lock all present source rows before preservation, matching clinical writers.
    targets = [e['body']['instruction']['target_id'] for e in entries]
    list(m.Encounter.objects.select_for_update().filter(pk__in=targets).order_by('pk'))
    retention.lock_preservation()
    for entry in entries: _import_tombstone(entry)
    audit(actor, 'disposition.journal_replayed', settings.RESTORE_INSTANCE_ID, entries=len(entries),
          journal_sha256=p.digest(entries[-1]) if entries else p.ZERO)
    return {'tombstones': len(entries), 'clinical_rows_deleted': 0, 'restore_admission_available': False,
            'external_copy_deletion': False}
