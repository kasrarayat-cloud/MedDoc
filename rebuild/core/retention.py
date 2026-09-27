"""Preserve held clinical evidence without stopping ordinary clinician corrections.

No retention period, legal authority or purge permission is inferred here. The
database captures prior row bodies. File cleanup serializes with hold creation;
unattributed files are preserved while any hold is active. No patient text goes
to ordinary audit rows or API responses.
"""
import hashlib
import logging
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import Q

from .models import (Department, Encounter, Organization, Patient, PreservedFile, RetentionHold,
                     RetentionHoldRelease, User)
from .security import audit, private_path

LOCK_KEY=716849203517
SCOPES={'organization':Organization,'department':Department,'patient':Patient,'encounter':Encounter}


def lock_preservation():
    if connection.vendor!='postgresql' or not connection.in_atomic_block:
        raise ValidationError('Preservation requires an atomic PostgreSQL transaction.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)',[LOCK_KEY])
        cursor.execute('SHOW transaction_isolation')
        if cursor.fetchone()!=('read committed',):
            raise ValidationError('Preservation requires read committed isolation.')


def authority_hash(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
        raise ValidationError('A SHA-256 reference to the preservation authority is required.')
    return value


def custodian(actor):
    # Re-read authorization; a cached user cannot outlive suspension/demotion.
    if not actor or not User.objects.filter(pk=actor.pk,is_active=True,is_staff=True,verified_at__isnull=False).exists():
        raise PermissionDenied('An active verified administrator is required.')


@transaction.atomic
def create_hold(actor,scope,target,authority,request_key):
    custodian(actor);authority=authority_hash(authority)
    if not isinstance(scope,str):raise ValidationError('Invalid preservation scope.')
    try:key=uuid.UUID(str(request_key))
    except (ValueError,TypeError,AttributeError):raise ValidationError('Invalid preservation request key.')
    if scope=='global':
        if target is not None:raise ValidationError('Global preservation has no target.')
        fields={}
    elif scope in SCOPES:
        try:row=SCOPES[scope].objects.select_for_update().get(pk=target)
        except (ValueError,ValidationError,SCOPES[scope].DoesNotExist):raise ValidationError('Invalid preservation scope.')
        fields={scope:row}
    else:raise ValidationError('Invalid preservation scope.')
    lock_preservation()
    existing=RetentionHold.objects.filter(request_key=key).first()
    if existing:
        same=(existing.created_by_id==actor.pk and existing.scope==scope and existing.authority_sha256==authority
              and all(getattr(existing,name+'_id')==getattr(fields.get(name),'pk',None) for name in SCOPES))
        if not same:raise ValidationError('Preservation request key was already used for another instruction.')
        return existing
    hold=RetentionHold.objects.create(scope=scope,authority_sha256=authority,created_by=actor,request_key=key,**fields)
    audit(actor,'retention.hold_created',hold.pk,scope=scope,authority_sha256=authority)
    return hold


@transaction.atomic
def release_hold(actor,hold_id,authority):
    custodian(actor);authority=authority_hash(authority)
    lock_preservation()
    try:hold=RetentionHold.objects.get(pk=hold_id)
    except (ValueError,ValidationError,RetentionHold.DoesNotExist):raise ValidationError('Unknown preservation instruction.')
    if hold.created_by_id==actor.pk:raise PermissionDenied('A second administrator must record release authority.')
    existing=RetentionHoldRelease.objects.filter(hold=hold).first()
    if existing:
        if existing.created_by_id!=actor.pk or existing.authority_sha256!=authority:
            raise ValidationError('This preservation instruction was already released with other evidence.')
        return existing
    row=RetentionHoldRelease.objects.create(hold=hold,authority_sha256=authority,created_by=actor)
    audit(actor,'retention.hold_released',hold.pk,authority_sha256=authority)
    return row


def active_holds(*,encounter_id=None,department_id=None):
    holds=RetentionHold.objects.filter(release__isnull=True)
    if encounter_id:
        try:encounter_id=uuid.UUID(str(encounter_id))
        except (ValueError,TypeError,AttributeError):return holds
        row=Encounter.objects.filter(pk=encounter_id).values('department_id','patient_id','department__organization_id').first()
        if row is None:return holds # Unknown ownership never proves safe disposal.
        return holds.filter(Q(scope='global')|Q(organization_id=row['department__organization_id'])
                            |Q(department_id=row['department_id'])|Q(patient_id=row['patient_id'])|Q(encounter_id=encounter_id))
    if department_id:
        org=Department.objects.filter(pk=department_id).values_list('organization_id',flat=True).first()
        if org is None:return holds
        # The caller knows only the department. Include every narrower hold in it.
        return holds.filter(Q(scope='global')|Q(organization_id=org)|Q(department_id=department_id)
                            |Q(patient__department_id=department_id)|Q(encounter__department_id=department_id))
    return holds


def cleanup_file(path,*,encounter_id=None,department_id=None):
    try:return _cleanup_file(path,encounter_id=encounter_id,department_id=department_id)
    except (DatabaseError,OSError):
        # A completed provider request must still reach settlement if cleanup
        # cannot inspect its preservation register. Keep the bytes, log no PHI.
        logging.getLogger(__name__).error('Private cleanup deferred: preservation database unavailable.')
        return False


@transaction.atomic
def _cleanup_file(path,*,encounter_id=None,department_id=None):
    """One cleanup boundary, returns False when preservation prevents unlink.

    The original storage key is retained; no copy or rename changes historical
    references. Callers must not report a removed file unless this returns True.
    Only private-state paths are accepted and symlinks are refused.
    """
    root=settings.MEDIA_ROOT.resolve()
    candidate=Path(path)
    if not candidate.is_absolute():candidate=root/candidate
    if candidate.is_symlink():raise ValidationError('Preservation refuses a symbolic file link.')
    try:relative=str(candidate.relative_to(root))
    except ValueError:raise ValidationError('Invalid private cleanup location.')
    validated=private_path(relative)
    if validated!=candidate:raise ValidationError('Preservation refuses a symbolic directory link.')
    # Enqueue/approval lock the encounter before publishing the file reference.
    # Reapers use the same order so an approved upload cannot disappear in the
    # reference-check/unlink interval.
    if encounter_id:
        try:scope_id=uuid.UUID(str(encounter_id))
        except (ValueError,TypeError,AttributeError):scope_id=None
        if scope_id:Encounter.objects.select_for_update().filter(pk=scope_id).first()
    lock_preservation()
    if PreservedFile.objects.filter(storage_key=relative).exists():return False
    hold_ids=list(active_holds(encounter_id=encounter_id,department_id=department_id).order_by('pk').values_list('pk',flat=True))
    if hold_ids:
        if validated.is_file():
            digest=hashlib.sha256();size=0
            with validated.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(block);size+=len(block)
            PreservedFile.objects.create(storage_key=relative,sha256=digest.hexdigest(),byte_count=size,hold_ids=[str(pk) for pk in hold_ids])
        return False
    # An active durable reference is never a transient cleanup candidate.
    from .models import Job,ProviderReceipt,Template
    if (Job.objects.filter(Q(input_path=relative)|Q(result_path=relative)).exists()
            or ProviderReceipt.objects.filter(result_path=relative).exists()
            or Template.objects.filter(original_path=relative).exists()
            or Encounter.objects.filter(export_path=relative).exists()):return False
    existed=validated.is_file()
    validated.unlink(missing_ok=True)
    return existed
