"""Redaction tombstones: remove one unfinalized document's clinical content while its accounting skeleton stays.

A document with jobs, a generation batch or code suggestions cannot be deleted (every reference to an encounter is
PROTECT), and its jobs, reservations, ledger entries, usage, receipts and audit rows must keep their ids and amounts.
Redaction keeps every one of those rows and removes the content instead:

- the document's notes, answers and review state become empty and its status 'redacted';
- its code suggestions (diagnosis codes and their quoted evidence are clinical content) are deleted;
- the bytes of the private files its rows reference (the recording, provider results) are removed after the commit,
  each only if it still has the digest the journal recorded. The rows keep their storage keys as accounting evidence;
  backups and the restore drill no longer expect those bytes (ops.backup_restore.FILE_QUERIES).

Who, when and why: a verified custodian requests it, naming the exact content by its digest and the reason by a
SHA-256 of the authority document (never prose); a second, distinct custodian executes it while the content still has
that digest. The signed entry naming both, the reason hash and the removed files is appended to the independent journal
and fsynced BEFORE the database rows commit, against a current independent checkpoint, and kept verbatim in the
append-only tombstone (0033 guards it). The journal is outside the clinical backup: a restore of an older recovery
point re-applies every journaled redaction (disposition_execution.replay) and is not admitted until it has
(restore_admission), and the offline exposure ledger (core.exposure) reads it.

Refused: while any retention hold applies (a committed unreleased hold, or a journaled one with no journaled release),
while preserved evidence or a file shared with another record exists, while work or money is unresolved, for a
finalized document, while restore quarantine is on, without DISPOSITION_ENABLED and a configured journal. No retention
period, schedule or deletion authority is inferred anywhere: redaction is an explicit, per-document, two-person act.
"""
import hashlib
import logging
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from . import disposition as d, disposition_journal as journal, disposition_policy as p, models as m, retention
from .security import audit, private_path

TOMBSTONE_IDS = uuid.UUID('1b0b7f2e-6c3a-4f0d-9a51-3d2f8e6b7c41')
UNFINALIZED = ('draft', 'review')
ACTIVE_JOB_STATES = ('queued', 'running', 'staged', 'validating', 'reconciliation')
ACTIVE_BATCH_STATES = ('queued', 'running', 'validating', 'reconciliation')
CONTENT_CHANGED = 'The document content changed since this redaction was requested; a new request is required.'


def tombstone_id(request_id):
    """One tombstone id per request, so an interrupted execution's retry signs the identical journal body."""
    return str(uuid.uuid5(TOMBSTONE_IDS, str(request_id)))


def referenced_files(encounter_id):
    """{storage_key: recorded sha256 or ''} for every private file this document's own rows reference."""
    jobs = m.Job.objects.filter(encounter_id=encounter_id)
    keys = {}
    def add(path, sha=''):
        if path:
            keys[path] = keys.get(path) or sha
    for row in jobs.values('input_path', 'result_path', 'result_sha256'):
        add(row['input_path']); add(row['result_path'], row['result_sha256'])
    for row in m.ProviderReceipt.objects.filter(job__encounter_id=encounter_id).values('result_path', 'result_sha256'):
        add(row['result_path'], row['result_sha256'])
    for row in m.GenerationBatchResponse.objects.filter(part__batch__encounter_id=encounter_id).values('result_path', 'result_sha256'):
        add(row['result_path'], row['result_sha256'])
    row = m.Encounter.objects.filter(pk=encounter_id).values('export_path', 'export_sha256').first()
    if row: add(row['export_path'], row['export_sha256'])
    return keys


def file_record(storage_key):
    """The bytes as they are now: their digest and size. A missing file is recorded as such (sha256 of nothing, 0)."""
    path = private_path(storage_key)
    digest = hashlib.sha256(); size = 0
    try:
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block); size += len(block)
    except FileNotFoundError:
        pass
    return {'storage_key': storage_key, 'sha256': digest.hexdigest(), 'byte_count': size}


def content(encounter):
    """The exact clinical content redaction removes, as digests: never stored, only hashed."""
    codes = sorted(m.CodeSuggestion.objects.filter(encounter=encounter).values_list(
        'terminology_id', 'explanation', 'evidence', 'accepted_by_id'), key=lambda row: str(row[0]))
    files = [file_record(key) for key in sorted(referenced_files(encounter.pk))]
    batches = sorted(m.GenerationBatch.objects.filter(encounter=encounter).values_list('plan_sha256', flat=True))
    value = {'notes': encounter.notes, 'answers': encounter.answers, 'template_review': encounter.template_review,
             'revision': encounter.revision, 'status': encounter.status,
             'codes': [[str(a), b, c, str(e) if e else None] for a, b, c, e in codes], 'files': files, 'batches': batches}
    return p.digest(value), files


def refusals(encounter):
    """Fixed labels, never row content. Empty when this document's content may be redacted now."""
    found = set()
    if encounter.status not in UNFINALIZED: found.add('not_an_unfinalized_document')
    if m.RedactionTombstone.objects.filter(target_id=encounter.pk).exists(): found.add('already_redacted')
    if m.DispositionTombstone.objects.filter(target_id=encounter.pk).exists(): found.add('disposed_target')
    if retention.active_holds(encounter_id=encounter.pk).exists() or journal_only_holds(encounter.pk):
        found.add('active_hold')
    jobs = m.Job.objects.filter(encounter=encounter)
    if (jobs.filter(state__in=ACTIVE_JOB_STATES).exists()
            or m.GenerationBatch.objects.filter(encounter=encounter, state__in=ACTIVE_BATCH_STATES).exists()):
        found.add('work_unresolved')
    # ⚠️ A GENERATION BATCH KEEPS THE NOTES (refutation F1 of dc33e094): its plan holds the full notes and quoted units,
    # and 0027 makes the row immutable, so blanking the document would leave the content there. Refused, never redacted
    # around; the database refuses the tombstone too (0033).
    if m.GenerationBatch.objects.filter(encounter=encounter).exists():
        found.add('generation_batch_content')
    if m.Reservation.objects.filter(job__encounter=encounter, state='held').exists(): found.add('funds_held')
    for receipt in m.ProviderReceipt.objects.filter(job__encounter=encounter).values('job_id', 'actual_cost'):
        if not (m.Usage.objects.filter(job_id=receipt['job_id']).exists() or m.PlatformCost.objects.filter(
                job_id=receipt['job_id'], kind='absorbed_failure', amount=receipt['actual_cost']).exists()):
            found.add('receipt_accounting_unresolved')
    if m.CostReconciliation.objects.filter(usage__job__encounter=encounter, ledger_status='pending_funds').exists():
        found.add('financial_history_unresolved')
    if m.PreservedRecord.objects.filter(Q(source_id=encounter.pk) | Q(prior_record__encounter_id=str(encounter.pk))).exists():
        found.add('preserved_evidence')
    keys = list(referenced_files(encounter.pk))
    if keys:
        own_jobs = list(jobs.values_list('pk', flat=True))
        if (m.PreservedFile.objects.filter(storage_key__in=keys).exists()
                or m.Job.objects.filter(Q(input_path__in=keys) | Q(result_path__in=keys)).exclude(pk__in=own_jobs).exists()
                or m.ProviderReceipt.objects.filter(result_path__in=keys).exclude(job_id__in=own_jobs).exists()
                or m.GenerationBatchResponse.objects.filter(result_path__in=keys).exclude(part__job_id__in=own_jobs).exists()
                or m.Template.objects.filter(original_path__in=keys).exists()
                or m.Encounter.objects.filter(export_path__in=keys).exclude(pk=encounter.pk).exists()
                or m.PreservedRecord.objects.filter(Q(prior_record__input_path__in=keys) | Q(prior_record__result_path__in=keys)
                    | Q(prior_record__original_path__in=keys) | Q(prior_record__export_path__in=keys)).exists()):
            found.add('shared_or_preserved_file')
    return sorted(found)


def journal_only_holds(encounter_id):
    """Journaled holds in this document's scope with no journaled release: as binding as committed ones."""
    if not retention.journal_configured(): return set()
    records = journal.journaled_holds()
    scoped = retention.journal_hold_ids(encounter_id=encounter_id)
    return {hold_id for hold_id in scoped if records.get(hold_id, {}).get('release') is None}


def require_configured():
    from .disposition_execution import enabled
    enabled()
    if not retention.journal_configured():
        raise ValidationError('Redaction requires the independent journal: a restore must be able to re-apply it.')


@transaction.atomic
def request(actor, encounter_id, reason_sha256, request_key):
    require_configured(); d.require_processing(); retention.custodian(actor)
    reason = retention.authority_hash(reason_sha256)
    try:key = uuid.UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):raise ValidationError('Invalid redaction request key.') from None
    encounter = m.Encounter.objects.select_for_update().filter(pk=encounter_id).first()
    if encounter is None:raise ValidationError('Unknown document.')
    retention.lock_preservation()
    old = m.RedactionRequest.objects.filter(request_key=key).first()
    if old:
        if (old.created_by_id, old.encounter_id, old.reason_sha256) != (actor.pk, encounter.pk, reason):
            raise ValidationError('This request key belongs to another redaction request.')
        return old
    blocked = refusals(encounter)
    if blocked:raise ValidationError('Redaction is unavailable: ' + ', '.join(blocked) + '.')
    fingerprint, _ = content(encounter)
    row = m.RedactionRequest.objects.create(encounter=encounter, department=encounter.department, reason_sha256=reason,
                                            content_sha256=fingerprint, request_key=key, created_by=actor)
    audit(actor, 'redaction.requested', row.pk, department=encounter.department, content_sha256=fingerprint)
    return row


@transaction.atomic
def execute(actor, request_id, checkpoint_envelope):
    """Journal, then tombstone and blank, in one transaction; remove the file bytes after the commit. An exact retry of a
    completed redaction returns its tombstone and removes any bytes an earlier attempt left."""
    require_configured(); d.require_processing(); retention.custodian(actor)
    try:row = m.RedactionRequest.objects.select_related('created_by').get(pk=request_id)
    except (m.RedactionRequest.DoesNotExist, ValueError, ValidationError):raise ValidationError('Unknown redaction request.') from None
    if actor.pk == row.created_by_id:raise PermissionDenied('A second custodian must execute a redaction.')
    retention.custodian(row.created_by)
    encounter = m.Encounter.objects.select_for_update().get(pk=row.encounter_id)
    retention.lock_preservation()
    done = m.RedactionTombstone.objects.filter(request_id=row.pk).first()
    if done:
        if done.journal_entry['body']['redaction']['approved_by'] != str(actor.pk):
            raise ValidationError('This redaction was already executed by another custodian.')
        transaction.on_commit(lambda: sweep(done.target_id))
        return done
    blocked = refusals(encounter)
    if blocked:raise ValidationError('Redaction is unavailable: ' + ', '.join(blocked) + '.')
    fingerprint, files = content(encounter)
    if fingerprint != row.content_sha256:raise ValidationError(CONTENT_CHANGED)
    body = {'id': tombstone_id(row.pk), 'request_id': str(row.pk), 'target_id': str(encounter.pk),
            'department_id': str(encounter.department_id), 'content_sha256': fingerprint, 'reason_sha256': row.reason_sha256,
            'files': files, 'requested_by': str(row.created_by_id), 'requested_at': row.created_at.isoformat(),
            'approved_by': str(actor.pk)}
    entry = journal.append_redaction(body, checkpoint_envelope)  # signed and fsynced before anything below commits
    tombstone, codes = apply(entry)
    audit(actor, 'redaction.executed', row.pk, department=encounter.department, journal_sha256=tombstone.entry_sha256,
          files=len(files), code_suggestions=codes)
    transaction.on_commit(lambda: sweep(tombstone.target_id))
    return tombstone


def apply(entry):
    """Record the tombstone from its verified journal entry and remove the content from this database. Used by execute
    and by restore replay; an existing tombstone must be this exact entry. Returns (tombstone, code suggestions
    deleted)."""
    body = entry['body']['redaction']; digest = p.digest(entry)
    old = m.RedactionTombstone.objects.filter(target_id=body['target_id']).first()
    if old:
        if old.entry_sha256 != digest or old.journal_entry != entry:
            raise ValidationError('The restored redaction conflicts with the independent journal.')
        tombstone = old
    else:
        tombstone = m.RedactionTombstone.objects.create(id=uuid.UUID(body['id']), target_id=uuid.UUID(body['target_id']),
            department_id=uuid.UUID(body['department_id']), request_id=uuid.UUID(body['request_id']),
            content_sha256=body['content_sha256'], files=body['files'], journal_entry=entry, entry_sha256=digest)
    deleted, _ = m.CodeSuggestion.objects.filter(encounter_id=body['target_id']).delete()
    m.Encounter.objects.filter(pk=body['target_id']).exclude(status='redacted', notes='', answers={}, template_review={}).update(
        notes='', answers={}, template_review={}, status='redacted')
    return tombstone, deleted


def remove_files(files):
    """Remove each recorded file's bytes, only while they still have the digest recorded for them (a record without one
    is removed as it is). Never raises: the redaction is committed; bytes left behind are logged (no path, no content),
    keep restore admission refused (unapplied) and are removed by the exact retry or the next replay."""
    removed = 0
    for record in files:
        try:
            path = private_path(record['storage_key'])
            if path.is_symlink():raise ValidationError('symbolic link')
            if not path.exists():continue
            if record.get('sha256') and file_record(record['storage_key'])['sha256'] != record['sha256']:
                raise ValidationError('digest changed')
            path.unlink(); removed += 1
        except (OSError, ValidationError):
            logging.getLogger(__name__).error('A redacted file was not removed; the exact retry removes it.')
    return removed


def redacted_files(target_id):
    """Every file a redacted document's bytes may live in: the tombstone's journaled list, and every file its rows reference
    now (refutation F2 of dc33e094: a provider result arriving after the redaction, written before it was refused, is
    referenced by the job and listed nowhere). Records {storage_key, sha256 or ''}."""
    records = {}
    tomb = m.RedactionTombstone.objects.filter(target_id=target_id).values_list('files', flat=True).first() or []
    for record in tomb:
        records[record['storage_key']] = record['sha256']
    for key, sha in referenced_files(target_id).items():
        records.setdefault(key, sha)
    return [{'storage_key': key, 'sha256': sha} for key, sha in sorted(records.items())]


def sweep(target_id):
    """Remove the bytes of every file of a redacted document (after its commit, at a retry, at every replay, and after a
    late provider result was written). Returns how many were removed."""
    return remove_files(redacted_files(target_id))


def withheld(encounter_id):
    """Whether provider output for this document must not be stored: it has a redaction tombstone here."""
    return bool(encounter_id) and m.RedactionTombstone.objects.filter(target_id=encounter_id).exists()


def files_left(target_id):
    """How many of a redacted document's files still have bytes on this volume."""
    return sum(private_path(record['storage_key']).exists() for record in redacted_files(target_id))


def redacted_targets():
    """Every document this database or the independent journal records as redacted. A journaled redaction whose
    database commit failed keeps its document unavailable, as a journaled disposition instruction does."""
    targets = {str(pk) for pk in m.RedactionTombstone.objects.values_list('target_id', flat=True)}
    if getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''):
        targets |= {e['body']['redaction']['target_id'] for e in journal.redaction_entries(journal.verified())}
    return targets


def unapplied(entries):
    """Journaled redactions this database or its volume does not reflect: no exact tombstone, the document still holds
    content, or a file of it still has bytes here (refutation F6 of dc33e094: remove_files logs a failure and admission
    passed with the bytes on the restored volume)."""
    missing = 0
    for entry in journal.redaction_entries(entries):
        body = entry['body']['redaction']
        tomb = m.RedactionTombstone.objects.filter(target_id=body['target_id']).values_list('entry_sha256', flat=True).first()
        content_left = m.Encounter.objects.filter(pk=body['target_id']).exclude(
            status='redacted', notes='', answers={}, template_review={}).exists()
        codes_left = m.CodeSuggestion.objects.filter(encounter_id=body['target_id']).exists()
        listed = {record['storage_key'] for record in body['files']}
        bytes_left = files_left(body['target_id']) or any(private_path(key).exists() for key in listed)
        missing += bool(tomb != p.digest(entry) or content_left or codes_left or bytes_left)
    return missing
