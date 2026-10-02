"""Admit a quarantined restored target into service. Quarantine lifts only against the record written here.

Admission never replays, repairs or deletes anything. It refuses unless, on the quarantined target whose instance id
the operator selected:

- the complete independent journal verifies against a fresh (unexpired, trusted, exact-head) checkpoint;
- every journaled disposition instruction has its exact tombstone here (disposition_execution.replay);
- every journaled hold, and each release after its hold, has its replay marker and the row that marker states;
- every journaled redaction has its exact tombstone here and its document holds no clinical content (core.redaction);
- (after admission) quarantine lifts only while this database still accounts for every journaled hold and release
  (disposition.restore_admitted): a journal that grows past it quarantines the target again until replay imports it;
- no journal target is visible: no document row for one lacks its tombstone, and the application filter shows none;
- the release-bound production restore check passes, including the journaled-hold section.

The report carries counts, fixed labels and hashes only; no clinical text, path or row content.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from . import disposition as d, disposition_execution as x, disposition_journal as journal, disposition_policy as p
from . import models as m, retention
from .security import audit

CONTRACT = 'restore-admission-v1'


def _query(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def selected_instance(instance_id):
    try:
        instance = uuid.UUID(str(instance_id)); selected = uuid.UUID(str(getattr(settings, 'RESTORE_INSTANCE_ID', '')))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('An independently selected restore target is required.') from None
    if not d.quarantined() or instance != selected:
        raise ValidationError('Restore admission runs only on the quarantined restore target it names.')
    return str(instance)


def _hold_state(record):
    """(missing, unreplayed) for one journaled hold and its release, judged by the same readers replay uses."""
    hold = record['hold']
    marker = m.RetentionHoldReplay.objects.filter(entry_sha256=p.digest(record['hold_entry'])).first()
    if marker is None: return 0, 1
    row = m.RetentionHold.objects.filter(pk=hold['id']).first()
    missing = not retention.hold_marker_consistent(marker, row, hold)
    unreplayed = 0
    if record['release'] is not None:
        released = m.RetentionHoldReplay.objects.filter(entry_sha256=p.digest(record['release_entry'])).first()
        if released is None: unreplayed = 1
        else:
            actual = m.RetentionHoldRelease.objects.filter(hold_id=hold['id']).first()
            missing = missing or not retention.release_marker_consistent(released, marker.outcome, actual, record['release'])
    return int(missing), unreplayed


def assess(instance_id, checkpoint_envelope, expected_triggers):
    """Every admission condition, as counts. Raises only when the target or the journal itself cannot be trusted."""
    instance = selected_instance(instance_id)
    entries = journal.verified(checkpoint_envelope)  # trusted signer, unexpired, the complete journal's exact head
    head = p.digest(entries[-1]) if entries else p.ZERO
    instructions = journal.instruction_entries(entries)
    records = journal.retention_records(entries)
    tombstoned = {str(target): digest for target, digest in m.DispositionTombstone.objects.values_list('target_id', 'entry_sha256')}
    targets = [e['body']['instruction']['target_id'] for e in instructions]
    tombstones_missing = sum(tombstoned.get(e['body']['instruction']['target_id']) != p.digest(e) for e in instructions)
    missing_holds = unreplayed_holds = unreplayed_releases = 0
    for record in records.values():
        missing, unreplayed = _hold_state(record)
        marker = m.RetentionHoldReplay.objects.filter(entry_sha256=p.digest(record['hold_entry'])).exists()
        missing_holds += missing or not marker
        unreplayed_holds += not marker
        unreplayed_releases += unreplayed
    # A restored row for a disposed target is suppressed here only by its tombstone; the journal filter hides it too.
    untombstoned_rows = m.Encounter.objects.filter(pk__in=targets).exclude(
        pk__in=m.DispositionTombstone.objects.values('target_id')).count() if targets else 0
    visible_rows = x.available(m.Encounter.objects.filter(pk__in=targets)).count() if targets else 0
    from ops import production_restore_check  # the release-bound drill check, run here on the target's own database
    check = production_restore_check.check(_query, None, expected_triggers, journal_holds=list(records),
                                           files_root=settings.MEDIA_ROOT)
    from . import redaction
    redactions_unapplied = redaction.unapplied(entries)
    unreplayed = tombstones_missing + unreplayed_holds + unreplayed_releases + redactions_unapplied
    blockers = sorted(label for label, failed in (
        ('restore_check_failed', not check['passed']), ('tombstone_replay_incomplete', tombstones_missing),
        ('hold_replay_incomplete', unreplayed_holds or missing_holds), ('release_replay_incomplete', unreplayed_releases),
        ('redaction_replay_incomplete', redactions_unapplied),
        ('journal_target_visible', untombstoned_rows or visible_rows)) if failed)
    return {'contract': CONTRACT, 'instance_id': instance,
            'journal': {'sequence': len(entries), 'head_sha256': head, 'instructions': len(instructions),
                        'holds': len(records), 'releases': sum(r['release'] is not None for r in records.values())},
            'checkpoint_sha256': p.digest(checkpoint_envelope),
            'tombstones_missing': tombstones_missing, 'unreplayed_holds': unreplayed_holds,
            'unreplayed_releases': unreplayed_releases, 'redactions_unapplied': redactions_unapplied,
            'unreplayed': unreplayed, 'missing_holds': missing_holds,
            'visible_targets': untombstoned_rows + visible_rows, 'restore_check': check,
            'blockers': blockers, 'admissible': not blockers}


@transaction.atomic
def admit(actor, instance_id, checkpoint_envelope, expected_triggers):
    """Write the one append-only admission record for this quarantined instance, or refuse with fixed labels."""
    retention.custodian(actor)
    instance = selected_instance(instance_id)
    # Serialize with replay, hold and release writers; the quarantined target runs no clinical work.
    retention.lock_preservation()
    old = m.RestoreAdmission.objects.filter(instance_id=instance).first()
    if old: return old
    report = assess(instance, checkpoint_envelope, expected_triggers)
    if not report['admissible']:
        raise ValidationError('Restore admission refused: ' + ', '.join(report['blockers']) + '.')
    row = m.RestoreAdmission.objects.create(instance_id=instance, checkpoint=checkpoint_envelope,
        journal_sequence=report['journal']['sequence'], journal_head_sha256=report['journal']['head_sha256'],
        report=report, report_sha256=p.digest(report), created_by=actor)
    audit(actor, 'restore.admitted', row.pk, instance_id=instance, journal_sha256=row.journal_head_sha256,
          report_sha256=row.report_sha256)
    return row
