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

from .models import (AuditEvent, Department, Encounter, Organization, Patient, PreservedFile, PreservedRecord, RetentionHold,
                     RetentionHoldRelease, User)
from .security import audit, private_path

LOCK_KEY=716849203517
SCOPES={'organization':Organization,'department':Department,'patient':Patient,'encounter':Encounter}

# ⚠️ ONE GLOBAL LOCK ORDER. LOCK_KEY is a single advisory lock that every preserved clinical write takes implicitly
# (the 0025/0026/0030 triggers: UPDATE/DELETE of an encounter, patient, template, department, job or code suggestion,
# INSERT of an encounter, a hold, a release or a tombstone), so it is held by most clinical transactions until commit.
# A transaction that holds a row lock another one needs while waiting for LOCK_KEY deadlocks. The order is:
#
#   1. source/scope rows    account (User), organization, department, patient, encounter, template, generation batch
#   2. job rows             Job
#   3. the preservation lock (lock_preservation(), or any trigger above)
#   4. money rows           Reservation, then Wallet (sorted by pk)
#   5. commit               deferred foreign-key checks take FOR KEY SHARE on every row a new row references
#
# Levels may be skipped, never reversed. Billing's job-scoped entry points (reserve, release, settle, absorb_failed_job)
# take level 3 themselves before any money row, so no caller can reach a wallet lock ahead of a later job.save() (RF-1).
# Level 5 comes last by construction, and every transaction reaches it holding the locks of levels 3-4, so a row lock
# held while waiting for a later level (LOCK_KEY or a money row) must not conflict with FOR KEY SHARE: such a row is
# locked FOR NO KEY UPDATE, never FOR UPDATE. create_hold's scope row (RF-2); welcome_credit's account row and the
# clinic acceptance's, held while it locks the promotional wallet that the account's own requests hold before their
# commit-time FOR KEY SHARE on that account (RF-R1); an organization top-up's owner-membership check, whose join also
# locks the owner's account and department while its payment waits for the organization's wallet, and a held
# reconciliation charge's row, locked of=('self',) so its select_related department is not (RF-R1's class); the
# department a payer change updates, whose trigger then waits for LOCK_KEY (RF-R2). A bare select_for_update() over a
# join locks every joined row: name the rows with of=, or use no_key=True.


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
        # FOR NO KEY UPDATE, not FOR UPDATE (the global lock order above, level 5): the in-flight clinical write this
        # waits for (at lock_preservation) re-checks its new rows' foreign keys at commit with FOR KEY SHARE on this
        # very row, which FOR UPDATE refused, so neither could finish (RF-2). This mode still excludes deletion,
        # key changes and every concurrent update of the scope row, and a second hold on it.
        try:row=SCOPES[scope].objects.select_for_update(no_key=True).get(pk=target)
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


def scoped_holds(*,encounter_id=None,department_id=None):
    holds=RetentionHold.objects.all()
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


def active_holds(**scope):
    return scoped_holds(**scope).filter(release__isnull=True)


@transaction.atomic
def begin_private_file(path):
    """Record creation intent BEFORE bytes exist, serialized with hold release.

    A later cleanup may exclude only releases already committed at this boundary.
    This does not trust filesystem times, which copying or touching can change.
    Unknown older files have no such exemption. Random storage keys are never reused.
    """
    root=settings.MEDIA_ROOT.resolve();candidate=Path(path)
    if not candidate.is_absolute():candidate=root/candidate
    try:relative=str(candidate.relative_to(root))
    except ValueError:raise ValidationError('Invalid private creation location.')
    if private_path(relative)!=candidate or candidate.exists() or candidate.is_symlink():
        raise ValidationError('Private storage keys cannot be reused.')
    lock_preservation()
    if AuditEvent.objects.filter(action='retention.file_creation',target=relative).exists():
        raise ValidationError('Private storage keys cannot be reused.')
    audit(None,'retention.file_creation',relative,
          released_hold_ids=[str(pk) for pk in RetentionHoldRelease.objects.order_by('hold_id').values_list('hold_id',flat=True)])


def cleanup_file(path,*,encounter_id=None,department_id=None):
    from .disposition import quarantined
    if quarantined():return False
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
    # Release stops future capture; it is not permission to destroy evidence that
    # existed during the hold. Only our pre-creation ledger can prove a file began
    # after a release. Missing or ambiguous creation evidence stays conservative.
    births=list(AuditEvent.objects.filter(action='retention.file_creation',target=relative).values_list('details',flat=True)[:2])
    exempt=[]
    if len(births)==1 and isinstance(births[0],dict):
        candidate_ids=births[0].get('released_hold_ids')
        if isinstance(candidate_ids,list):
            try:exempt=[uuid.UUID(value) for value in candidate_ids]
            except (ValueError,TypeError,AttributeError):exempt=[]
    hold_ids=set(str(pk) for pk in scoped_holds(encounter_id=encounter_id,department_id=department_id)
                 .exclude(pk__in=exempt).values_list('pk',flat=True))
    # A prior immutable row is a durable file reference even when the current row
    # has changed scope or points at a replacement file.
    archives=PreservedRecord.objects.filter(
        Q(prior_record__input_path=relative)|Q(prior_record__result_path=relative)
        |Q(prior_record__original_path=relative)|Q(prior_record__export_path=relative))
    for ids in archives.values_list('hold_ids',flat=True):hold_ids.update(ids)
    if hold_ids:
        if validated.is_file():
            digest=hashlib.sha256();size=0
            with validated.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(block);size+=len(block)
            PreservedFile.objects.create(storage_key=relative,sha256=digest.hexdigest(),byte_count=size,hold_ids=sorted(hold_ids))
        return False
    # An active durable reference is never a transient cleanup candidate.
    from .models import Job,ProviderReceipt,Template,GenerationBatchResponse
    if (Job.objects.filter(Q(input_path=relative)|Q(result_path=relative)).exists()
            or ProviderReceipt.objects.filter(result_path=relative).exists()
            or GenerationBatchResponse.objects.filter(result_path=relative).exists()
            or Template.objects.filter(original_path=relative).exists()
            or Encounter.objects.filter(export_path=relative).exists()):return False
    existed=validated.is_file()
    validated.unlink(missing_ok=True)
    return existed
