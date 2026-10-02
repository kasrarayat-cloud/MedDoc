"""Preserve held clinical evidence without stopping ordinary clinician corrections.

No retention period, legal authority or purge permission is inferred here. The
database captures prior row bodies. File cleanup serializes with hold creation;
unattributed files are preserved while any hold is active. No patient text goes
to ordinary audit rows or API responses.

When the independent journal is configured, every hold is signed and fsynced there
BEFORE its database row commits, and every release only AFTER its row committed. A
journaled hold whose database commit failed is treated as active by file cleanup and
disposition, as a pending disposition instruction is, and a quarantined restore
imports it (replay_journal_holds); a release whose commit failed is never journaled,
so no restore ends preservation on its strength. A journal that cannot take an entry
never refuses a hold or a release: preservation is recorded here and the failure
logged.
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
                     RetentionHoldRelease, RetentionHoldReplay, User)
from .security import audit, private_path

LOCK_KEY=716849203517
SCOPES={'organization':Organization,'department':Department,'patient':Patient,'encounter':Encounter}
# A hold's id follows from its request key, so every attempt under one key names one hold, journaled or not.
HOLD_IDS=uuid.UUID('6f1d8c1e-5a0b-4f53-9c64-2f8a1e7d3b90')

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
# Level 5 comes last by construction, and a transaction reaches it still holding its locks of levels 1-4. So a row that
# OTHER transactions point at from rows they insert without locking it first (an account, organization, department or
# patient: audit, job, usage, payment and membership rows do) is never held FOR UPDATE by a transaction that goes on to
# wait for a later level (LOCK_KEY or a money row). It is locked FOR NO KEY UPDATE, which does not conflict with FOR
# KEY SHARE and still excludes concurrent updates and deletion. Encounter, template and job rows keep FOR UPDATE: every
# row pointing at one is inserted under that row's own lock (jobs, batches, codes and holds under their encounter's;
# versions under their template's; reservations, ledger entries, usage and platform costs under their job's).
# The instances: create_hold's scope row (RF-2); welcome_credit's and the clinic acceptance's account row, held while
# it locks the promotional wallet the account's own requests hold before their commit-time FOR KEY SHARE on it (RF-R1);
# the organization top-up's owner check, whose join also locks the owner's account and department while its payment
# waits for the organization's wallet, and a held reconciliation charge, locked of=('self',) so its select_related
# department is not (RF-R1's class); the department a payer change updates, whose trigger then waits for LOCK_KEY
# (RF-R2). A bare select_for_update() over a join or beside select_related() locks every joined row: name the rows
# with of=, or use no_key=True.


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
        # A hold recorded while the journal could not take it is journaled by its exact retry.
        if journal_configured():_journal_hold(hold_record(existing),retry=True)
        return existing
    hold_id=uuid.uuid5(HOLD_IDS,str(key))
    journaled=False
    if journal_configured():
        # Signed and fsynced before the row below commits. A failed commit leaves a journal-only hold that cleanup and
        # disposition treat as active; this retry (same request key) records the row under the journaled id.
        entry=_journal_hold({'id':str(hold_id),'scope':scope,
            'target_id':None if scope=='global' else str(fields[scope].pk),'authority_sha256':authority,
            'request_key':str(key),'created_by':str(actor.pk)})
        if entry is not None:hold_id=uuid.UUID(entry['body']['hold']['id']);journaled=True
    hold=RetentionHold.objects.create(id=hold_id,scope=scope,authority_sha256=authority,created_by=actor,request_key=key,**fields)
    audit(actor,'retention.hold_created',hold.pk,scope=scope,authority_sha256=authority,journaled=journaled)
    return hold


def _journal_hold(record,retry=False):
    """Append a hold to the independent journal, or return None when the journal cannot take it.

    Preservation first: a journal that is missing, read-only, unverifiable or at its bound never refuses a hold. The
    row is still recorded here (the same id, which follows from its request key) and the failure is logged without
    PHI; its exact retry or its release journals it later. Other evidence under the same request key still refuses a
    new hold; for a hold already recorded here (`retry`) nothing is refused, only logged."""
    from . import disposition_journal as journal
    try:return journal.append_hold(record)
    except journal.RequestConflict:
        if not retry:raise
        logging.getLogger(__name__).error('Preservation hold differs from its independent journal entry.')
        return None
    except ValidationError:
        logging.getLogger(__name__).error('Preservation hold recorded without its independent journal copy.')
        return None


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
        # The exact retry journals a committed release whose journal copy is still pending (appends nothing otherwise).
        _journal_release_after_commit(existing,hold)
        return existing
    row=RetentionHoldRelease.objects.create(id=uuid.uuid4(),hold=hold,authority_sha256=authority,created_by=actor)
    audit(actor,'retention.hold_released',hold.pk,authority_sha256=authority)
    # Journaled only once this row has committed: a release whose commit fails (the application answers "not
    # recorded") is never journaled, so no restore imports it and any second custodian may still release the hold.
    _journal_release_after_commit(row,hold)
    return row


def _journal_release_after_commit(row,hold):
    if not journal_configured():return
    release={'id':str(row.pk),'hold_id':str(hold.pk),'authority_sha256':row.authority_sha256,'created_by':str(row.created_by_id)}
    record=hold_record(hold)
    def append():
        from . import disposition_journal as journal
        try:journal.append_release(release,record)
        except Exception:  # noqa: BLE001 - after the commit, a failure here must never read as "not recorded"
            # The release stands here. Until its copy is journaled a restore older than it keeps the hold active (the
            # conservative side); the custodian's exact retry journals it. A fixed message: no PHI, no row content.
            logging.getLogger(__name__).error('Preservation release recorded; its independent journal copy is pending '
                                              '(any active custodian journals it: retention.journal_committed_release).')
    transaction.on_commit(append)


def journal_committed_release(actor,hold_id):
    """Journal a release this database committed but the independent journal does not hold (its copy failed and is
    pending, or the release predates the journal), from the release row's own evidence: its id, authority hash and
    releasing custodian, exactly what _journal_release_after_commit would have appended (the hold first, if the journal
    lacks it). Any active verified custodian may do it; the entry names the custodian who RELEASED, and this act is audited
    under the custodian who journaled it, so nobody acts as anyone else (refutation R4F-A / R4S-3 of b3d8111d: only the
    releasing custodian's exact retry could journal it, and once that custodian left, every redaction in the hold's scope
    was refused for good). Idempotent: an already journaled release returns its entry and appends nothing."""
    custodian(actor)
    if not journal_configured():raise ValidationError('No independent journal is configured.')
    from . import disposition_journal as journal
    with transaction.atomic():
        lock_preservation()
        try:hold=RetentionHold.objects.get(pk=hold_id)
        except (ValueError,ValidationError,RetentionHold.DoesNotExist):raise ValidationError('Unknown preservation instruction.')
        row=RetentionHoldRelease.objects.filter(hold=hold).first()
        if row is None:raise ValidationError('This preservation instruction has no committed release.')
        release={'id':str(row.pk),'hold_id':str(hold.pk),'authority_sha256':row.authority_sha256,'created_by':str(row.created_by_id)}
        entry=journal.append_release(release,hold_record(hold))
        audit(actor,'retention.release_journaled',hold.pk,release=str(row.pk))
    return entry


def journal_configured():
    return bool(getattr(settings,'DISPOSITION_JOURNAL_PATH',''))


def hold_record(hold):
    """A database hold as its journal record."""
    target=None if hold.scope=='global' else getattr(hold,hold.scope+'_id')
    return {'id':str(hold.pk),'scope':hold.scope,'target_id':None if target is None else str(target),
            'authority_sha256':hold.authority_sha256,'request_key':str(hold.request_key),'created_by':str(hold.created_by_id)}


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


def journal_hold_ids(*,encounter_id=None,department_id=None):
    """Journaled hold ids in the same scope scoped_holds uses, released or not, including a hold whose database commit
    failed after its journal append. Empty when no journal is configured; an unreadable configured journal raises.
    Unknown ownership (an unparseable id, or a row absent from this database) matches every hold, as there."""
    from . import disposition_journal as journal
    holds=[record['hold'] for record in journal.journaled_holds().values()]
    if not holds:return set()
    every={hold['id'] for hold in holds}
    if encounter_id:
        try:encounter_id=uuid.UUID(str(encounter_id))
        except (ValueError,TypeError,AttributeError):return every
        row=Encounter.objects.filter(pk=encounter_id).values('department_id','patient_id','department__organization_id').first()
        if row is None:return every
        keys={('global',None),('organization',str(row['department__organization_id'])),('department',str(row['department_id'])),
              ('patient',str(row['patient_id'])),('encounter',str(encounter_id))}
        return {hold['id'] for hold in holds if (hold['scope'],hold['target_id']) in keys}
    if department_id:
        try:department_id=uuid.UUID(str(department_id))
        except (ValueError,TypeError,AttributeError):return every
        org=Department.objects.filter(pk=department_id).values_list('organization_id',flat=True).first()
        if org is None:return every
        keys={('global',None),('organization',str(org)),('department',str(department_id))}
        def within(hold):
            if (hold['scope'],hold['target_id']) in keys:return True
            if hold['scope'] not in ('patient','encounter'):return False
            owner=SCOPES[hold['scope']].objects.filter(pk=hold['target_id']).values_list('department_id',flat=True).first()
            return owner is None or owner==department_id
        return {hold['id'] for hold in holds if within(hold)}
    return every


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
    # A journaled hold counts even when its database commit failed. An unreadable configured journal keeps the bytes.
    try:journaled=journal_hold_ids(encounter_id=encounter_id,department_id=department_id)
    except ValidationError:
        logging.getLogger(__name__).error('Private cleanup deferred: the independent preservation journal is unavailable.')
        return False
    hold_ids.update(journaled-{str(pk) for pk in exempt})
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


REPLAY_CONFLICT='The restored preservation record conflicts with the independent journal.'


def _hold_target_exists(hold):
    return hold['scope']=='global' or SCOPES[hold['scope']].objects.filter(pk=hold['target_id']).exists()


def _hold_matches(row,hold):
    """Everything but the custodian, which attributed() checks against the replay marker."""
    return {k:v for k,v in hold_record(row).items() if k!='created_by'}=={k:v for k,v in hold.items() if k!='created_by'}


def recorder(journaled,actor_id):
    """Who records a replayed hold or release here: the journaled custodian when that account exists in this database
    (the 0032 guard accepts it inactive through its marker), otherwise the custodian replaying it. The marker keeps the
    signed entry verbatim, so the journaled identity is never lost."""
    return journaled if User.objects.filter(pk=journaled).exists() else str(actor_id)


def attributed(row_created_by,journaled,marker_created_by):
    """A replayed row names its journaled custodian or the custodian who replayed it (recorder(); the 0032 guard
    accepted the second only while the journaled account was absent). Not re-judged against accounts that exist now:
    a user row reconciled later must not turn a consistent replay into a conflict."""
    return str(row_created_by) in (journaled,str(marker_created_by))


def hold_marker_consistent(marker,row,hold):
    """What a hold's replay marker states still holds in this database. ONE reader for replay and admission.

    'imported' and 'present': the journaled hold is here. 'target_absent': its target is still absent and so is the
    hold, or the target has since been reinserted and carries the hold its marker names (quillmd_restore_absent_hold)."""
    if marker.outcome in ('imported','present'):
        return row is not None and _hold_matches(row,hold) and (
            str(row.created_by_id)==hold['created_by'] if marker.outcome=='present'
            else attributed(row.created_by_id,hold['created_by'],marker.created_by_id))
    if marker.outcome=='target_absent':
        if row is None:return not _hold_target_exists(hold)
        return (_hold_matches(row,hold) and _hold_target_exists(hold)
                and attributed(row.created_by_id,hold['created_by'],marker.created_by_id))
    return False


def release_marker_consistent(marker,hold_outcome,row,release):
    """What a release's replay marker states still holds in this database. ONE reader for replay and admission.

    'target_absent' is an absence only while its hold is absent too (NEW-1): once the target is back and carries the
    hold (quillmd_restore_absent_hold), the release must be here as its row, or the hold stays active although the
    source ended it."""
    exact=row is not None and (str(row.pk),row.authority_sha256)==(release['id'],release['authority_sha256'])
    if marker.outcome=='present':
        return exact and str(row.created_by_id)==release['created_by']
    if marker.outcome=='imported':
        return exact and attributed(row.created_by_id,release['created_by'],marker.created_by_id)
    if marker.outcome=='target_absent':
        if hold_outcome!='target_absent':return False
        if row is None:return not RetentionHold.objects.filter(pk=release['hold_id']).exists()
        # A row under the journal's OWN id is the journaled release (replay or quillmd_restore_absent_hold applied it):
        # it must be exactly that release (refutation R2D-F8a of 4cfa4301: other evidence under the signed id was accepted
        # and recorded nowhere).
        if str(row.pk)==release['id']:
            return exact and attributed(row.created_by_id,release['created_by'],marker.created_by_id)
        # F8: a stale absence marker (ac43e379) with the hold since ended HERE by another release under its own id: the
        # journal and this database have both ended the hold, so preservation agrees; replay records the differing evidence.
        return True
    return False


def _replay_marker(actor,event,record_id,hold_id,outcome,entry,digest):
    return RetentionHoldReplay.objects.create(record_id=record_id,hold_id=hold_id,event=event,outcome=outcome,
                                              journal_entry=entry,entry_sha256=digest,created_by=actor)


def _replay_hold(actor,hold,entry):
    from . import disposition_policy as p
    digest=p.digest(entry);row=RetentionHold.objects.filter(pk=hold['id']).first()
    marker=RetentionHoldReplay.objects.filter(entry_sha256=digest).first()
    if marker:
        # Idempotent: an earlier replay into this database recorded it; it must still hold.
        if not hold_marker_consistent(marker,row,hold) or str(marker.record_id)!=hold['id']:raise ValidationError(REPLAY_CONFLICT)
        return marker.outcome
    if row is not None:
        if not _hold_matches(row,hold) or str(row.created_by_id)!=hold['created_by']:raise ValidationError(REPLAY_CONFLICT)
        _replay_marker(actor,'hold',hold['id'],hold['id'],'present',entry,digest)
        return 'present'
    if not _hold_target_exists(hold):
        # The target was created after this backup: nothing here to preserve yet. The marker records the absence, and
        # the database applies the hold if that target is ever reinserted (0032, quillmd_restore_absent_hold).
        _replay_marker(actor,'hold',hold['id'],hold['id'],'target_absent',entry,digest)
        return 'target_absent'
    creator=recorder(hold['created_by'],actor.pk)
    _replay_marker(actor,'hold',hold['id'],hold['id'],'imported',entry,digest)
    fields={} if hold['scope']=='global' else {hold['scope']+'_id':hold['target_id']}
    RetentionHold.objects.create(id=hold['id'],scope=hold['scope'],authority_sha256=hold['authority_sha256'],
                                 created_by_id=creator,request_key=hold['request_key'],**fields)
    audit(actor,'retention.hold_replayed',hold['id'],scope=hold['scope'],authority_sha256=hold['authority_sha256'])
    return 'imported'


def _replay_release(actor,hold,hold_outcome,release,entry):
    from . import disposition_policy as p
    digest=p.digest(entry);row=RetentionHoldRelease.objects.filter(hold_id=hold['id']).first()
    marker=RetentionHoldReplay.objects.filter(entry_sha256=digest).first()
    # What this database holds NOW decides, never the hold marker's outcome alone (NEW-1): a hold recorded
    # 'target_absent' is applied once its target is inserted again, and a release journaled after that must follow it.
    held=RetentionHold.objects.filter(pk=hold['id']).first()
    if marker:
        if str(marker.record_id)!=release['id']:raise ValidationError(REPLAY_CONFLICT)
        if marker.outcome=='target_absent' and row is None and held is not None:
            # Recorded absent before this repair, after the target came back: apply it now from its verbatim marker,
            # exactly as quillmd_restore_absent_hold applies a release recorded before the reinsertion.
            row=RetentionHoldRelease.objects.create(id=release['id'],hold=held,authority_sha256=release['authority_sha256'],
                                                    created_by_id=recorder(release['created_by'],marker.created_by_id))
            audit(actor,'retention.release_replayed',hold['id'],authority_sha256=release['authority_sha256'])
        elif marker.outcome=='target_absent' and row is not None and str(row.pk)!=release['id']:
            # F8 (the refuter's P13): under the stale marker a local custodian ended the hold with other evidence (the
            # journal refused its copy, holding the source's release). Both ended it; the release row is append-only and
            # one per hold, so the divergence is recorded, once, not refused (a refusal quarantined the target for good).
            if not AuditEvent.objects.filter(action='retention.release_evidence_differs',target=str(hold['id'])).exists():
                audit(actor,'retention.release_evidence_differs',hold['id'],journaled_release=release['id'],
                      local_release=str(row.pk),journaled_authority_sha256=release['authority_sha256'],
                      local_authority_sha256=row.authority_sha256)
        if not release_marker_consistent(marker,hold_outcome,row,release):raise ValidationError(REPLAY_CONFLICT)
        return marker.outcome
    if hold_outcome=='target_absent' and held is None:
        _replay_marker(actor,'release',release['id'],hold['id'],'target_absent',entry,digest)
        return 'target_absent'
    if row is not None:
        if (str(row.pk),row.authority_sha256,str(row.created_by_id))!=(release['id'],release['authority_sha256'],release['created_by']):
            raise ValidationError(REPLAY_CONFLICT)
        _replay_marker(actor,'release',release['id'],hold['id'],'present',entry,digest)
        return 'present'
    # Only a committed release is ever journaled (release_hold journals after its commit), so replay imports it: the
    # restored database ends preservation exactly where the source did. The journal chain already proved the second
    # custodian (never the hold's journaled one); when the releaser's account is absent here the replaying custodian
    # records it, and its marker keeps the signed release verbatim.
    if held is None:raise ValidationError(REPLAY_CONFLICT)
    _replay_marker(actor,'release',release['id'],hold['id'],'imported',entry,digest)
    RetentionHoldRelease.objects.create(id=release['id'],hold=held,authority_sha256=release['authority_sha256'],
                                        created_by_id=recorder(release['created_by'],actor.pk))
    audit(actor,'retention.release_replayed',hold['id'],authority_sha256=release['authority_sha256'])
    return 'imported'


def replay_journal_holds(actor,records,*,entries=None,redact=None):
    """Import journaled holds, and each release only after its hold, into a quarantined restored database.

    With `entries` (the verified chain) every hold, release and redaction is replayed in journal order, `redact`
    applying each redaction (core.redaction.apply): the restored database then passes through the source's own sequence,
    so a hold journaled after a redaction never captures the content it removed. Without them, holds in record order.
    The caller (disposition_execution.replay) has verified the complete journal against a fresh checkpoint, and holds
    the scope rows and then the preservation lock. Nothing is deleted here. Returns counts only."""
    counts={'holds':0,'holds_imported':0,'holds_present':0,'holds_target_absent':0,
            'releases':0,'releases_imported':0,'releases_present':0,'releases_target_absent':0}
    from . import disposition_journal as journal
    outcomes={}
    def hold(record):
        outcomes[record['hold']['id']]=outcome=_replay_hold(actor,record['hold'],record['hold_entry'])
        counts['holds']+=1;counts['holds_'+outcome]+=1
    def release(record):
        released=_replay_release(actor,record['hold'],outcomes[record['hold']['id']],record['release'],record['release_entry'])
        counts['releases']+=1;counts['releases_'+released]+=1
    if entries is None:
        for record in records.values():
            hold(record)
            if record['release'] is not None:release(record)
        return counts
    for entry in entries:
        kind=journal.kind(entry)
        if kind=='hold':hold(records[entry['body']['hold']['id']])
        elif kind=='release':release(records[entry['body']['release']['hold_id']])
        elif kind=='redaction':redact(entry)
    return counts


def unaccounted_journal_records():
    """Ids of journaled holds and releases this database does not account for: no row with that id, and no replay
    marker recording its target absent (a marker claiming 'imported' or 'present' counts only through its row). Empty
    when no journal is configured; a configured journal that cannot be verified raises. A restored target serves only
    while this is empty (disposition.restore_admitted)."""
    from . import disposition_journal as journal
    records=journal.journaled_holds()
    holds=set(records)
    releases={record['release']['id'] for record in records.values() if record['release'] is not None}
    if not holds:return set()
    present={str(pk) for pk in RetentionHold.objects.filter(pk__in=holds).values_list('pk',flat=True)}
    released={str(pk) for pk in RetentionHoldRelease.objects.filter(hold_id__in=holds).values_list('hold_id',flat=True)}
    # A release's 'target_absent' marker accounts for it only while its hold is absent here too (NEW-1): once the hold
    # is back, only a release of it here does: its own row, or (F8) a local release with other evidence
    # (release_marker_consistent).
    accounted={str(pk) for pk,hold_id,event in RetentionHoldReplay.objects.filter(
                   record_id__in=holds|releases,outcome='target_absent').values_list('record_id','hold_id','event')
               if event=='hold' or str(hold_id) not in present or str(hold_id) in released}
    accounted|=present
    accounted|={str(pk) for pk in RetentionHoldRelease.objects.filter(pk__in=releases).values_list('pk',flat=True)}
    return (holds|releases)-accounted
