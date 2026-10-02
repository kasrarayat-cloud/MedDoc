"""Offline backup exposure ledger: which recovery points may still contain a disposed or redacted document.

A disposition or redaction acts on the live database and files. Every recovery point taken BEFORE that act (a database
backup, a volume snapshot, an offsite copy) still holds the content until that recovery point itself expires. Those
copies are offline and immutable by design, so nothing deletes from them; what is owed is a record of the exposure and
the guarantee that restoring one of them re-applies the act.

- The acts come from the verified independent journal (core.disposition_journal), proved complete against a fresh
  independent checkpoint: it is outside the clinical backup, so a restore cannot roll it back. Disposition instructions
  and redactions are the acts; holds and releases add preservation and are not exposures.
- The recovery points come from the backup system's own inventory, never from QuillMD: an operator export (JSON) and/or
  the local encrypted backup run directories (ops/backup_restore.py, run ids '<UTC stamp>-<hex>', complete only). A
  recovery point's expiry is whatever that system records; QuillMD sets, infers and shortens none (no retention period
  exists here, and absence of an expiry means the copy is kept).
- Restoring any recovery point re-applies every journaled act: disposition_execution.replay imports each instruction's
  tombstone and each redaction, in journal order, and restore_admission refuses until they are all applied. The ledger's
  per-recovery-point 'contains' list is what that replay will re-apply for a restore of that point.

The ledger holds identities, timestamps and counts only: no clinical text, patient name, storage path or file bytes.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from . import disposition_journal as journal, disposition_policy as p

CONTRACT = 'backup-exposure-ledger-v1'
RUN_ID = re.compile(r'^(\d{8}T\d{6}Z)-[0-9a-f]{8}$')
MAX_POINTS = 100000
# An act's time is its journal signature, which PRECEDES its database commit, and the commit can come much later (a
# failed commit retried an hour on keeps the first signature: refutation F3 of dc33e094). Until the database's own
# tombstone shows the commit, every later recovery point may still hold the content. The tombstone's creation time is
# inside its transaction, so points up to this long after it are still listed as possibly exposed. A technical tolerance
# for one transaction, not a retention period; restoring any point re-applies every journaled act either way.
COMMIT_TOLERANCE = timedelta(minutes=5)


def commit_evidence():
    """{act id: when the content the act removes was last in THIS database or on this volume}: a disposition's by its
    instruction id, a redaction's by its tombstone id (the journal entry's id). An act missing here counts as uncommitted:
    every later recovery point may still hold its content.

    A tombstone alone is not that evidence (refutation round 2 of 4cfa4301):
    - a disposition counts only once the document's row is gone: replay imports the tombstone of a disposition into an
      older restore and keeps a restored row whose content conflicts (X1), and later backups then hold that row;
    - a redaction counts only while none of its bytes is left on this volume, and from the later of its tombstone and the
      last removal of its bytes, by its sweep ('redaction.swept' with files removed) or by the worker's reaper of an
      unapproved dictation ('voice.over_limit_upload_removed', refutation R4S-2 of b3d8111d: the reaper can remove it first,
      and only the sweep's removals were read): a failed unlink leaves the recording after the commit, and volume snapshots
      taken meanwhile hold it (X2)."""
    from .models import AuditEvent, DispositionTombstone, Encounter, RedactionTombstone
    from . import redaction
    found = {}
    disposed = list(DispositionTombstone.objects.values_list('instruction_id', 'created_at', 'target_id'))
    present = set(Encounter.objects.filter(pk__in=[target for _i, _m, target in disposed]).values_list('pk', flat=True))
    for ident, moment, target in disposed:
        if target not in present:
            found[str(ident)] = moment
    removed = {}
    targets = [str(target) for target in RedactionTombstone.objects.values_list('target_id', flat=True)]
    for action, target, moment, details in AuditEvent.objects.filter(
            action__in=('redaction.swept', 'voice.over_limit_upload_removed'), target__in=targets).values_list(
            'action', 'target', 'created_at', 'details'):
        if action == 'redaction.swept' and not (details or {}).get('removed'):
            continue
        removed[target] = max(moment, removed.get(target, moment))
    for ident, moment, target in RedactionTombstone.objects.values_list('id', 'created_at', 'target_id'):
        if not redaction.files_left(target):
            found[str(ident)] = max(moment, removed.get(str(target), moment))
    return {ident: moment.astimezone(dt_timezone.utc) for ident, moment in found.items()}


def _instant(value, label):
    try:
        moment = p.timestamp(value)
    except ValidationError:
        raise ValidationError(f'The recovery point inventory has an invalid {label}.') from None
    return moment.astimezone(dt_timezone.utc)


def inventory(data):
    """Validate an operator's recovery point export: {"recovery_points": [{"id", "created_at", "expires_at"?,
    "location"?}]}. Ids are unique; timestamps carry a timezone; an absent or null expiry means kept."""
    points = data.get('recovery_points') if isinstance(data, dict) else None
    if not isinstance(points, list) or len(points) > MAX_POINTS:
        raise ValidationError('The recovery point inventory is invalid.')
    seen = set(); result = []
    for point in points:
        if not isinstance(point, dict) or set(point) - {'id', 'created_at', 'expires_at', 'location'}:
            raise ValidationError('The recovery point inventory is invalid.')
        ident = point.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9:/._-]{1,200}', ident) or ident in seen:
            raise ValidationError('Recovery point ids must be unique plain identifiers.')
        seen.add(ident)
        expires = point.get('expires_at')
        location = point.get('location', '')
        if not isinstance(location, str) or len(location) > 80:
            raise ValidationError('The recovery point inventory is invalid.')
        result.append({'id': ident, 'created_at': _instant(point.get('created_at'), 'creation time'),
                       'expires_at': None if expires is None else _instant(expires, 'expiry'), 'location': location})
    return result


def local_backups(root):
    """Complete local backup runs under `root` (ops/backup_restore.py): the run id names its UTC start, which is no
    later than its database snapshot. An incomplete run is not a recovery point."""
    root = Path(root)
    if not root.is_dir():
        raise ValidationError('The backup root is not a directory.')
    points = []
    for child in sorted(root.iterdir()):
        match = RUN_ID.match(child.name)
        if not match or not child.is_dir() or child.is_symlink() or (child / 'INCOMPLETE').exists():
            continue
        try:
            summary = json.loads((child / 'summary.json').read_text())
        except (OSError, ValueError):
            continue
        if summary.get('complete') is not True or summary.get('run_id') != child.name:
            continue
        created = datetime.strptime(match.group(1), '%Y%m%dT%H%M%SZ').replace(tzinfo=dt_timezone.utc)
        points.append({'id': child.name, 'created_at': created, 'expires_at': None, 'location': 'local'})
    return points


def acts(entries):
    """Journaled disposition instructions and redactions, in journal order: what a recovery point older than each still
    contains."""
    found = []
    for entry in entries:
        kind = journal.kind(entry)
        if kind == 'instruction':
            body = entry['body']['instruction']; ident, target = body['id'], body['target_id']
        elif kind == 'redaction':
            body = entry['body']['redaction']; ident, target = body['id'], body['target_id']
        else:
            continue
        found.append({'kind': kind, 'id': ident, 'target_id': target,
                      'acted_at': p.timestamp(entry['body']['written_at']).astimezone(dt_timezone.utc),
                      'entry_sha256': p.digest(entry)})
    return found


def ledger(entries, points, now, committed):
    """Every act with the unexpired recovery points taken at or before its journal signature (exposed), and those taken
    after it but before its database commit plus COMMIT_TOLERANCE (possibly exposed; every later point when `committed`,
    from commit_evidence(), has no tombstone for it), and every recovery point with the acts a restore of it re-applies."""
    listed = acts(entries)
    live = [point for point in points if point['expires_at'] is None or point['expires_at'] > now]
    def until(act):
        moment = committed.get(act['id'])
        return None if moment is None else max(moment, act['acted_at']) + COMMIT_TOLERANCE
    def may_hold(point, act):
        bound = until(act)
        return bound is None or point['created_at'] <= bound
    rows = []
    for act in listed:
        exposed = sorted(point['id'] for point in live if point['created_at'] <= act['acted_at'])
        possibly = sorted(point['id'] for point in live if act['acted_at'] < point['created_at'] and may_hold(point, act))
        moment = committed.get(act['id'])
        rows.append({'kind': act['kind'], 'id': act['id'], 'target_id': act['target_id'],
                     'acted_at': act['acted_at'].isoformat(), 'entry_sha256': act['entry_sha256'],
                     'committed_at': moment.isoformat() if moment else None,
                     'exposed_recovery_points': exposed, 'possibly_exposed_recovery_points': possibly,
                     'reapplied_by': 'journal_replay_then_restore_admission'})
    recovery = []
    for point in sorted(live, key=lambda point: (point['created_at'], point['id'])):
        contains = [act['id'] for act in listed if point['created_at'] <= act['acted_at'] or may_hold(point, act)]
        recovery.append({'id': point['id'], 'location': point['location'], 'created_at': point['created_at'].isoformat(),
                         'expires_at': point['expires_at'].isoformat() if point['expires_at'] else None,
                         'contains': contains})
    head = p.digest(entries[-1]) if entries else p.ZERO
    return {'contract': CONTRACT, 'generated_at': now.isoformat(),
            'journal': {'sequence': len(entries), 'head_sha256': head},
            'acts': rows, 'recovery_points': recovery,
            'counts': {'acts': len(rows), 'exposed_acts': sum(bool(row['exposed_recovery_points']) for row in rows),
                       'recovery_points': len(recovery), 'expired_recovery_points_omitted': len(points) - len(live),
                       'recovery_points_with_exposure': sum(bool(row['contains']) for row in recovery)}}


def write_private(path, value):
    """Write the ledger once, 0600, outside the clinical state root (it must survive the restore it describes)."""
    target = Path(path)
    if not target.is_absolute() or any(target.resolve().is_relative_to(Path(root).resolve())
                                       for root in (settings.STATE_DIR, settings.MEDIA_ROOT)):
        raise ValidationError('The exposure ledger must be written outside the clinical state root.')
    data = json.dumps(value, sort_keys=True, indent=1).encode() + b'\n'
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError:
        raise ValidationError('The exposure ledger path exists or cannot be created.') from None
    with os.fdopen(descriptor, 'wb') as file:
        file.write(data); file.flush(); os.fsync(file.fileno())
    return p.digest(value)
