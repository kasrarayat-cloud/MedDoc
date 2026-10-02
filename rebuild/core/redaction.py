"""Redaction tombstones: remove one unfinalized document's clinical content while its accounting skeleton stays.

A document with jobs, a generation batch or code suggestions cannot be deleted (every reference to an encounter is
PROTECT), and its jobs, reservations, ledger entries, usage, receipts and audit rows must keep their ids and amounts.
Redaction keeps every one of those rows and removes the content instead:

- the document's notes, answers and review state become empty and its status 'redacted';
- its code suggestions (diagnosis codes and their quoted evidence are clinical content) are deleted;
- the bytes of the private files its rows reference (the recording, provider results) are removed after the commit,
  unless another record references the same key (round 2: not 'only while they have the journaled digest'). The rows
  keep their storage keys as accounting evidence; backups and the restore drill no longer expect those bytes
  (ops.backup_restore.FILE_QUERIES).

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
from django.db.models import Count, Q

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
    """{storage_key: recorded sha256 or ''} for every private file this document's own rows reference, and every dictation
    an over-limit quote stored for it (refutation R3R-T19 of 75d11c09: until a doctor approves it, an over-limit upload is
    referenced only by its 'voice.over_limit_quoted' audit row, so a redaction left it on the volume, uncounted, until the
    reaper removed it 40 minutes later). Swept, counted and refused-if-shared like the rest; never fingerprinted (content)."""
    keys = own_files(encounter_id)
    for key in pending_uploads(encounter_id):
        keys.setdefault(key, '')
    return keys


def pending_uploads(encounter_id):
    """The dictations an over-limit quote stored for this document, which no row references until a doctor approves them.
    The audit read is narrowed by the document's department (an indexed column; refutation R4S-4 of b3d8111d: the action and
    target filter alone scanned the whole audit table for every redacted document, every minute)."""
    return [key for key in (str((details or {}).get('path') or '') for details in quote_events(encounter_id).values_list(
        'details', flat=True)) if key]


def quote_events(encounter_id):
    """This document's over-limit quote rows, narrowed by its department (a document's department never changes)."""
    department = m.Encounter.objects.filter(pk=encounter_id).values_list('department_id', flat=True).first()
    events = m.AuditEvent.objects.filter(action='voice.over_limit_quoted', target=str(encounter_id))
    return events.filter(department_id=department) if department else events


def own_files(encounter_id):
    """{storage_key: recorded sha256 or ''} for every private file this document's own rows reference: what its content
    fingerprint covers. ⚠️ NOT a pending over-limit dictation (refutation R4S-1 of b3d8111d): the worker's reaper deletes that
    file on its own 40-minute timer, so with it in the fingerprint a requested redaction's execute, or a journaled one's
    exact retry, was refused ('content changed') for good once the reaper had run. The dictation is a system-managed upload
    that the redaction sweeps anyway; the custodians approve the content the document's rows hold."""
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
    files = [file_record(key) for key in sorted(own_files(encounter.pk))]
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
    if unjournaled_releases(encounter.pk):
        found.add('hold_release_not_journaled')
    jobs = m.Job.objects.filter(encounter=encounter)
    if (jobs.filter(state__in=ACTIVE_JOB_STATES).exists()
            or m.GenerationBatch.objects.filter(encounter=encounter, state__in=ACTIVE_BATCH_STATES).exists()):
        found.add('work_unresolved')
    # ⚠️ A GENERATION BATCH KEEPS THE NOTES (refutation F1 of dc33e094): its plan holds the full notes and quoted units,
    # and 0027 makes the row immutable, so blanking the document would leave the content there. Refused, never redacted
    # around; the database refuses the tombstone too (0033).
    if m.GenerationBatch.objects.filter(encounter=encounter).exists():
        found.add('generation_batch_content')
    # An append-only transcript review retains clinical text independently of notes and provider result files.
    # Never claim redaction while that text survives: it needs its own qualified disposal adapter.
    if m.TranscriptReview.objects.filter(encounter=encounter).exists():
        found.add('transcript_review_content')
    if m.Reservation.objects.filter(job__encounter=encounter, state='held').exists(): found.add('funds_held')
    for receipt in m.ProviderReceipt.objects.filter(job__encounter=encounter).values('job_id', 'actual_cost'):
        if not (m.Usage.objects.filter(job_id=receipt['job_id']).exists() or m.PlatformCost.objects.filter(
                job_id=receipt['job_id'], kind='absorbed_failure', amount=receipt['actual_cost']).exists()):
            found.add('receipt_accounting_unresolved')
    if m.CostReconciliation.objects.filter(usage__job__encounter=encounter, ledger_status='pending_funds').exists():
        found.add('financial_history_unresolved')
    if m.PreservedRecord.objects.filter(Q(source_id=encounter.pk) | Q(prior_record__encounter_id=str(encounter.pk))).exists():
        found.add('preserved_evidence')
    if shared_keys(referenced_files(encounter.pk), encounter.pk):
        found.add('shared_or_preserved_file')
    return sorted(found)


PRIOR_FILE_FIELDS = ('input_path', 'result_path', 'original_path', 'export_path')


def shared_keys(keys, encounter_id):
    """The keys, among `keys`, that a record other than this document's own rows references: another job, receipt or
    batch response, a template's original, another document's export, preserved evidence. Execution refuses while any
    exists; and a sweep never removes their bytes, which are that record's (round 2, R2D-R1)."""
    keys = set(keys)
    if not keys:
        return set()
    own_jobs = list(m.Job.objects.filter(encounter_id=encounter_id).values_list('pk', flat=True))
    found = set(m.PreservedFile.objects.filter(storage_key__in=keys).values_list('storage_key', flat=True))
    for row in m.Job.objects.filter(Q(input_path__in=keys) | Q(result_path__in=keys)).exclude(pk__in=own_jobs).values(
            'input_path', 'result_path'):
        found |= {row['input_path'], row['result_path']} & keys
    found |= set(m.ProviderReceipt.objects.filter(result_path__in=keys).exclude(job_id__in=own_jobs).values_list(
        'result_path', flat=True))
    found |= set(m.GenerationBatchResponse.objects.filter(result_path__in=keys).exclude(part__job_id__in=own_jobs).values_list(
        'result_path', flat=True))
    found |= set(m.Template.objects.filter(original_path__in=keys).values_list('original_path', flat=True))
    found |= set(m.Encounter.objects.filter(export_path__in=keys).exclude(pk=encounter_id).values_list('export_path', flat=True))
    for prior in m.PreservedRecord.objects.filter(Q(prior_record__input_path__in=keys) | Q(prior_record__result_path__in=keys)
            | Q(prior_record__original_path__in=keys) | Q(prior_record__export_path__in=keys)).values_list('prior_record', flat=True):
        found |= {prior.get(field) for field in PRIOR_FILE_FIELDS if isinstance(prior, dict)} & keys
    return found


def journal_only_holds(encounter_id):
    """Journaled holds in this document's scope with no journaled release: as binding as committed ones."""
    if not retention.journal_configured(): return set()
    records = journal.journaled_holds()
    scoped = retention.journal_hold_ids(encounter_id=encounter_id)
    return {hold_id for hold_id in scoped if records.get(hold_id, {}).get('release') is None}


def journal_pending_releases(actor, encounter_id):
    """Clear 'hold_release_not_journaled' for one document: every hold in its scope released here whose release the journal
    lacks is journaled from its own recorded evidence (retention.journal_committed_release), by any active verified
    custodian. Returns how many were journaled."""
    retention.custodian(actor)
    # ⚠️ AN UNKNOWN DOCUMENT IS REFUSED (refutation R5F-12 of a0bc4fd8): scoped_holds answers an unknown or unparseable id
    # with EVERY hold (unknown ownership never proves a disposal safe), which is right for a refusal and wrong for choosing
    # what to act on: a mistyped id journaled every pending release in the database, across organizations.
    try:
        known = m.Encounter.objects.filter(pk=encounter_id).exists()
    except (ValueError, ValidationError):
        known = False
    if not known:
        raise ValidationError('Unknown document.')
    pending = unjournaled_releases(encounter_id)
    for hold_id in sorted(pending):
        retention.journal_committed_release(actor, hold_id)
    return len(pending)


def unjournaled_releases(encounter_id):
    """Holds in this document's scope released in THIS database for which the independent journal holds no release (the
    copy is pending: retention._journal_release_after_commit logs it; any active custodian journals it, R4F-A). A
    restore older than that release keeps the hold active, and a redaction journaled before any release of the hold would
    then replay into a held document and be refused for good: every recovery point taken under the hold stayed
    quarantined (refutation R3R-T3 of 75d11c09). So the redaction waits until a release of the hold precedes it in the
    journal (any journaled release ends the hold at replay, as F8's stale-marker case shows)."""
    if not retention.journal_configured(): return set()
    records = journal.journaled_holds()
    return {str(hold_id) for hold_id in m.RetentionHoldRelease.objects.filter(
                hold__in=retention.scoped_holds(encounter_id=encounter_id)).values_list('hold_id', flat=True)
            if not (records.get(str(hold_id)) or {}).get('release')}


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
    files = journaled_files(row.pk, encounter.pk, files)
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


def journaled_files(request_id, encounter_id, own):
    """The file list a redaction journals: the files its fingerprint covers AND every dictation an over-limit quote stored
    for the document. ⚠️ THE JOURNAL IS THE ONLY RECORD OF A REDACTION'S KEYS OUTSIDE THE CLINICAL BACKUP (refutation R5R-1
    of a0bc4fd8): R4S-1 took the dictation out of the fingerprint and, with it, out of this list, so a restore pairing a
    database from before the quote with a volume snapshot from after it (ops/production_restore_check.py) replayed, left the
    redacted dictation on the volume, admitted it, and dated the exposure as ended; nothing referenced the key again. The
    dictation stays out of the fingerprint and in this list, whether or not its bytes are still there (the reaper may have
    removed them live; a restored volume may hold them).

    An exact retry of a redaction already journaled (its commit failed) journals the identical body, so it takes this list
    from that entry: the reaper may have removed the dictation in between, and its digest now would differ."""
    for entry in journal.redaction_entries(journal.verified()):
        body = entry['body']['redaction']
        if body['request_id'] == str(request_id):
            return body['files']
    listed = {record['storage_key'] for record in own}
    pending = [file_record(key) for key in dict.fromkeys(pending_uploads(encounter_id)) if key not in listed]
    return sorted(own + pending, key=lambda record: record['storage_key'])


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


def remove_files(files, target_id):
    """How many of these files' bytes were removed (removal(): the whole outcome)."""
    return removal(files, target_id)[0]


def removal(files, target_id):
    """Remove the bytes of each file of the redacted document `target_id`, whatever they hold now, except a key another
    record references (shared_keys): those bytes are that record's.

    ⚠️ NOT ONLY WHILE THEY HAVE THE JOURNALED DIGEST (refutation R2D-R1 of 4cfa4301): a recording missing when the
    redaction ran is journaled as empty (sha256 of nothing, 0 bytes), so after a restore of an older recovery point its
    bytes never matched, every sweep logged 'digest changed' and kept the redacted recording, and the restore could never
    be admitted. A redacted document's storage keys are its own (a key is never reused: retention.file_creation), so the
    bytes at them are its content, journaled or not. Never raises: the redaction is committed. Returns (removed, retryable,
    refused): bytes a failed unlink left (retryable: the worker's next sweep, the exact retry or the next replay tries
    again) and keys refused for good (another record references them, or a symbolic link sits on the way: an operator's
    matter, said once, never promised away; refutation R4S-6 of b3d8111d). Both keep restore admission refused."""
    log = logging.getLogger(__name__)
    keys = [record['storage_key'] for record in files]
    try:
        shared = shared_keys(keys, target_id)
    except Exception:  # noqa: BLE001 - unknown sharing removes nothing; the worker's next sweep tries again
        log.error('Whether a redacted file is shared could not be read; nothing was removed.')
        return 0, len(keys), 0
    removed = retryable = refused = 0
    root = settings.MEDIA_ROOT.resolve()
    for key in keys:
        if key in shared:
            log.error('A redacted file is referenced by another record and was kept.')
            refused += 1
            continue
        try:
            # ⚠️ THE LINK ITSELF, NOT WHAT IT POINTS TO (refutation R3R-T1 of 75d11c09): private_path() resolves, so a check
            # of its result never saw a symbolic link, and the sweep unlinked the link's TARGET, another record's file
            # (a template's original), leaving the link. As retention._cleanup_file does: refuse a link at the key, and a
            # key whose resolved path is not the key itself (a linked directory on the way).
            candidate = root / key
            if candidate.is_symlink() or private_path(key) != candidate:
                log.error('A redacted key reaches its bytes through a symbolic link; nothing was removed. An operator must '
                          'remove the link: what it points to may be another record\'s.')
                refused += 1
                continue
            if not candidate.exists():continue
            candidate.unlink(); removed += 1
        except (OSError, ValidationError):
            log.error('A redacted file was not removed; the worker\'s next sweep, the exact retry or the next replay '
                      'removes it.')
            retryable += 1
    return removed, retryable, refused


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
    """Remove the bytes of every file of a redacted document (after its commit, at a retry, at every replay, and by the
    worker while a retryable failure is outstanding). Returns how many were removed. Its outcome is audited as
    'redaction.swept' (counts, no path) whenever it differs from the last one recorded: a removal's time is when those bytes
    left this volume (core.exposure.commit_evidence), and the last outcome tells the worker whether to come back
    (sweep_left)."""
    # Counted BEFORE the files are read: a quote that lands after this count is revisited by the worker, never missed.
    quotes = quote_events(target_id).count()
    removed, retryable, refused = removal(redacted_files(target_id), target_id)
    outcome = {'removed': removed, 'retryable': retryable, 'refused': refused, 'quotes': quotes}
    last = latest_outcomes(m.AuditEvent.objects.filter(action='redaction.swept', target=str(target_id))).get(str(target_id))
    # Recorded when bytes were removed, and when what is left changed: a retry that removed nothing and left the same is
    # not, or a failure the worker retries every minute would add an append-only audit row every minute.
    if removed or any((last or {}).get(key) != outcome[key] for key in ('retryable', 'refused', 'quotes')):
        audit(None, 'redaction.swept', target_id, **outcome, sequence=((last or {}).get('sequence') or 0) + 1)
    return removed


def latest_outcomes(events):
    """{target: the details of its latest 'redaction.swept'}: the latest by the sweep's own sequence number, the time only
    between equal ones. By time alone, two sweeps sharing a timestamp (a coarse or a stepped-back clock) made 'the latest'
    either of them, and a document whose newest sweep left bytes retryable could be read as clean and never retried."""
    latest, order = {}, {}
    for target, details, created in events.values_list('target', 'details', 'created_at'):
        details = details or {}
        rank = (details.get('sequence') or 0, created)
        if target not in order or rank > order[target]:
            latest[target], order[target] = details, rank
    return latest


def withheld(encounter_id):
    """Whether provider output for this document must not be stored: this database has its redaction tombstone, or the
    independent journal holds its redaction (refutation R2D-L1 of 4cfa4301: while a journaled redaction waits for its
    retried commit, a late result wrote the quoted notes to receipts, and the new file changed the content so the exact
    retry could never commit).

    ⚠️ A JOURNAL THAT CANNOT BE READ NOW DOES NOT DISCARD THE OUTPUT (refutation R3R-T2 of 75d11c09): this runs after the
    provider returned and its receipt committed, and raising here parked the job and lost the paid output of a document
    nobody redacted. The database's answer stands and the fault is logged; the output is stored, referenced by its job, so
    a redaction that commits later still sweeps it. The residual, recorded: a redaction that is ONLY journaled (its commit
    failed) while the journal is also unreadable lets this output be written; its exact retry then refuses with
    CONTENT_CHANGED, as before R2D-L1."""
    if not encounter_id:
        return False
    if m.RedactionTombstone.objects.filter(target_id=encounter_id).exists():
        return True
    if getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''):
        try:
            entries = journal.redaction_entries(journal.verified())
        except (ValidationError, OSError):
            logging.getLogger(__name__).error('The independent journal could not be read while storing a provider result; '
                                              'the database shows no redaction, so the result is stored.')
            return False
        return any(entry['body']['redaction']['target_id'] == str(encounter_id) for entry in entries)
    return False


def sweep_left():
    """The automatic retry of a failed removal (refutation R3R-T5 of 75d11c09): the worker runs this every minute. A
    redaction whose bytes a failed unlink left on a SERVING instance no longer quarantines it (R2D-Q1), and a redaction
    applied there by replay has no request row for an exact retry, nor a replay once admitted; so every redacted document
    whose last sweep left a retryable failure, or that was never swept here, is swept again. Returns how many files were
    removed.

    ⚠️ THE STEADY STATE COSTS THREE QUERIES, HOWEVER MANY REDACTIONS EXIST (refutation R4S-4 of b3d8111d: every tombstone's
    files were re-read every minute, about 14 queries each and an audit-table scan among them, 6 s a pass at 100 redactions).
    A document whose last sweep left nothing retryable, and saw every over-limit quote its document has, is not visited
    again; one whose bytes were refused for good (a symbolic link, another record's key) is an operator's matter and is not
    retried, so it is not logged every minute either."""
    tombstones = dict(m.RedactionTombstone.objects.values_list('target_id', 'department_id'))
    if not tombstones:
        return 0
    last = latest_outcomes(m.AuditEvent.objects.filter(action='redaction.swept'))
    quoted = {}
    for target, department, count in m.AuditEvent.objects.filter(
            action='voice.over_limit_quoted', target__in=[str(target_id) for target_id in tombstones]).order_by().values(
            'target', 'department_id').annotate(count=Count('pk')).values_list('target', 'department_id', 'count'):
        quoted[(target, department)] = count
    removed = 0
    for target_id, department in tombstones.items():
        outcome = last.get(str(target_id))
        # ⚠️ AND ONE WITH A QUOTE ITS LAST SWEEP DID NOT SEE (refutation R5R-2 of a0bc4fd8): views.voice stores the upload,
        # enqueue refuses over the limit and releases the document's lock, and only then is the quote audited; a redaction
        # committing in between swept clean, and the dictation then waited 40 minutes for the reaper. Counts, not times:
        # the quote and the sweep may share a timestamp, and they come from different processes' clocks.
        unseen = quoted.get((str(target_id), department), 0) != (outcome or {}).get('quotes', 0)
        if outcome is not None and not (outcome or {}).get('retryable') and not unseen:
            continue
        try:
            removed += sweep(target_id)
        except Exception:  # noqa: BLE001 - one unreadable record never stops the worker; the next pass tries again
            logging.getLogger(__name__).error('A redacted document could not be swept; the next pass tries again.')
    return removed


def files_left(target_id, listed=()):
    """How many files of a redacted document still have bytes on this volume: the tombstone's (or `listed`, a journaled
    list) and those its rows reference, never one another record references (those bytes are that record's)."""
    keys = {record['storage_key'] for record in redacted_files(target_id)} | set(listed)
    keys -= shared_keys(keys, target_id)
    return sum(private_path(key).exists() for key in keys)


def redacted_targets():
    """Every document this database or the independent journal records as redacted. A journaled redaction whose
    database commit failed keeps its document unavailable, as a journaled disposition instruction does."""
    targets = {str(pk) for pk in m.RedactionTombstone.objects.values_list('target_id', flat=True)}
    if getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''):
        targets |= {e['body']['redaction']['target_id'] for e in journal.redaction_entries(journal.verified())}
    return targets


def unapplied(entries, volume=True):
    """Journaled redactions this database (and, with `volume`, its volume) does not reflect: no exact tombstone, the
    document still holds content, or a file of it still has bytes here.

    Restore admission counts the bytes (refutation F6 of dc33e094: remove_files logs a failure and admission passed with
    them on the restored volume). The serving gate of an admitted instance does NOT (volume=False, disposition
    .journal_accounted): one failed unlink quarantined every doctor's processing there, and the replay it pointed to
    could not lift it (refutation R2D-Q1 of 4cfa4301). Those bytes are logged, keep the exposure ledger open
    (core.exposure), and are removed by the exact retry."""
    missing = 0
    for entry in journal.redaction_entries(entries):
        body = entry['body']['redaction']
        tomb = m.RedactionTombstone.objects.filter(target_id=body['target_id']).values_list('entry_sha256', flat=True).first()
        content_left = m.Encounter.objects.filter(pk=body['target_id']).exclude(
            status='redacted', notes='', answers={}, template_review={}).exists()
        codes_left = m.CodeSuggestion.objects.filter(encounter_id=body['target_id']).exists()
        bytes_left = volume and files_left(body['target_id'], [record['storage_key'] for record in body['files']])
        missing += bool(tomb != p.digest(entry) or content_left or codes_left or bytes_left)
    return missing
