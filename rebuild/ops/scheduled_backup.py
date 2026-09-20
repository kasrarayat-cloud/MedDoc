#!/usr/bin/env python3
"""Bounded local encrypted capture and redacted operator status. No deletion or offsite traffic."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import tempfile

try:
    from . import backup_restore as backup
except ImportError:
    import backup_restore as backup

SOURCE = Path('/opt/meddoc-pro/rebuild')
RUNTIME = SOURCE / '.runtime'
MONITOR = RUNTIME / 'backup-monitor'
KEY = RUNTIME / 'backup-secrets/fresh-backup-current-20260917.key'
ROLES = RUNTIME / 'db-role-secrets/fresh-db-roles.json'
DESTINATION = RUNTIME / 'new-system-backups'
RUN_PATTERN = re.compile(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}')
MAX_AGE_SECONDS = 30 * 3600
TIMEOUT_SECONDS = 540
MIN_FREE_BYTES = 2 * 1024 ** 3
SUMMARY_KEYS = {'complete', 'run_id', 'database', 'table_count', 'row_count', 'file_count',
                'file_bytes', 'source_commit', 'encrypted', 'manifest_cipher_sha256'}
ERRORS = {'capture_already_running', 'insufficient_free_space', 'backup_command_failed',
          'backup_timeout', 'validation_or_capture_failed'}


def now():
    return datetime.now(timezone.utc)


def atomic_status(path, value):
    if path.exists() or path.is_symlink():
        backup.read_private(path, 65536)
    fd, temporary = tempfile.mkstemp(prefix='.status-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def previous():
    path = MONITOR / 'latest.json'
    item = json.loads(backup.read_private(path, 65536)) if path.exists() or path.is_symlink() else {}
    backup.require(isinstance(item, dict) and item.get('outcome') in (None, 'running', 'complete', 'failed')
                   and item.get('error') in ERRORS | {None}, 'Invalid backup status.')
    if item.get('last_success_at') is not None:
        parsed = datetime.fromisoformat(item['last_success_at'])
        backup.require(parsed.tzinfo is not None and RUN_PATTERN.fullmatch(item['last_success_run_id']),
                       'Invalid last-success identity.')
    return item


def validate_summary(raw):
    value = json.loads(raw)
    backup.require(set(value) == SUMMARY_KEYS | {'backup_directory'}, 'Unexpected backup result.')
    backup.require(value['complete'] is True and value['encrypted'] is True
                   and value['database'] == 'quillmd_fresh'
                   and isinstance(value['run_id'], str) and RUN_PATTERN.fullmatch(value['run_id'])
                   and value['backup_directory'] == str(DESTINATION / value['run_id']), 'Invalid backup identity.')
    backup.require(all(type(value[key]) is int and value[key] >= 0
                       for key in ('table_count', 'row_count', 'file_count', 'file_bytes'))
                   and value['table_count'] > 0, 'Invalid backup totals.')
    backup.require(re.fullmatch(r'[a-f0-9]{40}', value['source_commit'])
                   and re.fullmatch(r'[a-f0-9]{64}', value['manifest_cipher_sha256']), 'Invalid backup hashes.')
    destination = backup.private_dir(DESTINATION / value['run_id'])
    backup.require(not (destination / 'INCOMPLETE').exists(), 'Incomplete backup.')
    stored = json.loads(backup.read_private(destination / 'summary.json', 65536))
    safe = {key: value[key] for key in SUMMARY_KEYS}
    backup.require(stored == safe, 'Backup summary differs.')
    backup.require(backup.digest(backup.read_private(destination / 'manifest.json.fernet'))
                   == safe['manifest_cipher_sha256'], 'Encrypted manifest differs.')
    return safe


def run_capture():
    """Exactly one invocation, with immutable attempt records and no automatic retry."""
    backup.private_dir(RUNTIME)
    backup.private_dir(MONITOR, create=True)
    attempt = now().strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
    record = {'format': 1, 'attempt': attempt, 'started_at': now().isoformat(),
              'outcome': 'running', 'scope': 'local encrypted backup only',
              'offsite_verified': False, 'restore_performed': False, 'provider_calls': 0}
    lock = None
    acquired = False
    try:
        lock = os.open(MONITOR / 'capture.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(lock)
        backup.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                       and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'Invalid capture lock.')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            record.update(outcome='skipped', error='capture_already_running', finished_at=now().isoformat())
            return record, 0
        prior = previous()
        for key in ('last_success_at', 'last_success_run_id'):
            if key in prior:
                record[key] = prior[key]
        atomic_status(MONITOR / 'latest.json', record)
        backup.private_dir(DESTINATION, create=True)
        backup.key_at(KEY)
        backup.read_private(ROLES, 65536)  # The backup tool separately verifies the pinned database/role.
        if shutil.disk_usage(DESTINATION).free < MIN_FREE_BYTES:
            record.update(outcome='failed', error='insufficient_free_space')
        else:
            # No .env is loaded into this supervisor. Only the existing audited backup
            # process opens the application config/read-only role file, without logging it.
            command = [str(SOURCE / '.venv/bin/python'), str(SOURCE / 'ops/backup_restore.py'), 'backup',
                       '--source', str(SOURCE), '--database-credentials', str(ROLES),
                       '--key-file', str(KEY), '--output', str(DESTINATION)]
            child = subprocess.run(command, capture_output=True, timeout=TIMEOUT_SECONDS,
                                   env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'})
            if child.returncode:
                record.update(outcome='failed', error='backup_command_failed', exit_code=child.returncode)
            else:
                backup.require(len(child.stdout) <= 65536, 'Oversized backup result.')
                summary = validate_summary(child.stdout)
                record.update(outcome='complete', summary=summary, last_success_at=now().isoformat(),
                              last_success_run_id=summary['run_id'])
    except subprocess.TimeoutExpired:
        record.update(outcome='failed', error='backup_timeout')
    except Exception:
        # Never propagate an exception message, child stderr, credential or database row.
        record.update(outcome='failed', error='validation_or_capture_failed')
    finally:
        try:
            record['finished_at'] = now().isoformat()
            backup.write_private(MONITOR / (attempt + '.json'), json.dumps(record).encode() + b'\n')
            # Only the lock holder replaces shared state. Even an unsafe/unopenable
            # lock leaves an immutable failed attempt; status reads those too, so
            # an older success cannot hide this failure or a racing capture.
            if acquired:
                atomic_status(MONITOR / 'latest.json', record)
        finally:
            if lock is not None:
                os.close(lock)
    return record, 0 if record['outcome'] == 'complete' else 1


def status(at=None):
    """Local operator status only; no clinical fields or remote monitoring claim."""
    at = at or now()
    try:
        backup.private_dir(MONITOR)
        item = previous()
        # Failures before lock acquisition must stay visible even after an operator
        # repairs the lock. A subsequent successful capture closes that failure.
        attempts = list(MONITOR.glob('*.json'))
        backup.require(len(attempts) <= 10000, 'Oversized backup status history.')
        latest = item
        latest_time = datetime.fromisoformat(item['finished_at']) if item.get('finished_at') else None
        for path in attempts:
            if not RUN_PATTERN.fullmatch(path.stem):
                continue
            attempt = json.loads(backup.read_private(path, 65536))
            backup.require(attempt.get('outcome') in ('complete', 'failed', 'skipped')
                           and attempt.get('error') in ERRORS | {None}, 'Invalid attempt history.')
            finished = datetime.fromisoformat(attempt['finished_at'])
            backup.require(finished.tzinfo is not None, 'Invalid attempt time.')
            if attempt['outcome'] != 'skipped' and (latest_time is None or finished > latest_time):
                latest, latest_time = attempt, finished
        success = datetime.fromisoformat(item['last_success_at']) if item.get('last_success_at') else None
        age = (at - success).total_seconds() if success else None
        lock = MONITOR / 'capture.lock'
        info = lock.lstat()
        backup.require(lock.resolve() == lock and stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                       and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'Invalid capture lock.')
        # An active attempt takes precedence over an older completed history row.
        outcome = 'running' if item.get('outcome') == 'running' else latest.get('outcome', 'missing')
        healthy = outcome == 'complete' and age is not None and 0 <= age <= MAX_AGE_SECONDS
        return {'format': 1, 'healthy': healthy, 'latest_outcome': outcome,
                'last_success_at': item.get('last_success_at'), 'last_success_run_id': item.get('last_success_run_id'),
                'last_success_age_seconds': int(age) if age is not None else None,
                'stale_after_seconds': MAX_AGE_SECONDS, 'last_error': latest.get('error'),
                'offsite_verified': False, 'alert_delivery_verified': False}
    except Exception:
        return {'format': 1, 'healthy': False, 'latest_outcome': 'missing_or_invalid',
                'offsite_verified': False, 'alert_delivery_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'status'))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action == 'status':
            result = status()
            code = 0 if result['healthy'] else 1
        else:
            result, code = run_capture()
    except Exception:
        result, code = {'outcome': 'failed', 'error': 'status_directory_or_lock_unavailable'}, 1
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
