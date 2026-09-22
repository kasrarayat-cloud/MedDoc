#!/usr/bin/env python3
"""Private, nonclinical recovery-stage alerts. No database access or backup mutation."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from urllib.parse import urlsplit

import requests

from dotenv import dotenv_values

try:
    from . import scheduled_backup as scheduled
except ImportError:
    import scheduled_backup as scheduled

backup = scheduled.backup
SOURCE = Path('/opt/meddoc-pro/rebuild')
CONFIG = SOURCE / '.runtime/backup-secrets/backup-alerts.json'
ENV_FILE = SOURCE / '.env'
DIRECTORY = SOURCE / '.runtime/backup-alerts'
OFFSITE_DIRECTORY = SOURCE / '.runtime/automatic-offsite'
EXTERNAL_CONFIG = SOURCE / '.runtime/backup-secrets/external-monitor.json'
HEARTBEAT_INTERVAL_SECONDS = 300
RECIPIENT = 'kasra.rayat@gmail.com'
TEST_AUTHORIZATION = '20260920-operation-recovery'
STALE_SECONDS = 15 * 60
COOLDOWN_SECONDS = 24 * 3600
BACKUP_TIMEOUT_SECONDS = 600
OFFSITE_STALE_SECONDS = 30 * 3600
OFFSITE_TIMEOUT_SECONDS = 1200
OFFSITE_ADMISSION_WINDOW_SECONDS = 960 + 60 + 90
POLICY_WARNING_SECONDS = 6 * 3600
WARNINGS = {'offsite_policy_renewal_due', 'offsite_policy_expiring', 'offsite_capacity_low', 'offsite_renewal_failed', 'offsite_next_run_budget_low'}
ERRORS = {
    'healthy': 'Local capture and offsite completion/readback are current. Isolated-restore and recovery-key custody evidence are reported separately.',
    'backup_in_progress': 'A bounded backup is running; the next monitor check will recheck completion.',
    'backup_failed': 'Inspect scheduled_backup.py status and the private backup-monitor attempt record; repair before retrying capture.',
    'backup_stale': 'Inspect the backup timer and last successful capture; restore the daily schedule and run a verified capture.',
    'backup_status_unavailable': 'Inspect private backup-monitor permissions and status records; do not treat missing evidence as success.',
    'backup_artifacts_unavailable': 'The recorded local capture is missing, altered or incomplete. Inspect its protected summary, manifest and encrypted objects; retain remote recovery sets and do not count capture metadata alone as a current backup.',
    'backup_schedule_unavailable': 'Inspect quillmd-fresh-backup.timer and quillmd-fresh-backup.service; restore the approved schedule.',
    'backup_timeout': 'Inspect quillmd-fresh-backup.service; a running capture exceeded its approved bound.',
    'offsite_in_progress': 'A bounded encrypted upload is running; retain the previous complete set until verified completion.',
    'offsite_status_unavailable': 'Inspect private automatic-offsite status and immutable attempt evidence; missing or malformed evidence does not prove a recoverable remote backup.',
    'offsite_policy_unavailable': 'Install or renew the protected, approved storage, download and request envelope; keep recurrence disabled until all limits are established.',
    'offsite_capacity_refused': 'The approved storage or request allowance is exhausted. Preserve existing versions; obtain a reviewed capacity or retention decision before another upload.',
    'offsite_budget_refused': 'The shared UTC-day request or response reservation budget cannot admit this work. Preserve all reservations, including uncertain attempts; wait for an eligible UTC day or diagnose the recorded refusal without resetting counters.',
    'offsite_next_run_budget_low': 'The next scheduled UTC day lacks reserved headroom for a new backup of the last complete size. This is a forecast, not an executed failure; actual size and pagination may differ. Preserve reservations and inspect that day\'s shared consumers before the run.',
    'offsite_capacity_low': 'The last scoped inventory leaves less room than one backup of the last completed size. Actual future size is unknown; preserve retained versions and arrange a reviewed capacity decision before the next capture. The worker cannot delete versions.',
    'offsite_upload_failed': 'Inspect the redacted automatic-offsite attempt record and authenticated completion manifest; retry through the bounded service after diagnosis, never count a partial upload as complete.',
    'offsite_cleanup_failed': 'The attempt did not complete cleanup. Preserve its private journal and retained resources; verify the bounded process has stopped and repair cleanup before retrying. A prior completed backup remains separately recorded.',
    'offsite_recovery_failed': 'A manual isolated restore failed. Inspect its protected verification and cleanup evidence before retrying through the shared allowance controls; the historical verified restore remains separately recorded.',
    'offsite_policy_renewal_due': 'The next daily run falls outside current account-audit validity. Renew the account-wide evidence through the authenticated desktop and install the reviewed policy before its deadline; the restricted worker cannot refresh account-wide inventory.',
    'offsite_policy_expiring': 'Account evidence is approaching its recorded deadline. Complete the supported renewal before expiry; current backup proof remains separately valid and no allowance is reset.',
    'offsite_policy_expired': 'Account evidence has expired. New offsite work is refused until a supported renewal is installed; retain the last observation, prior backups and shared reservations.',
    'offsite_renewal_failed': 'The latest account-evidence renewal failed; the original observation and deadline remain in force. Inspect the protected renewal result, repair the stated cause and renew before expiry.',
    'offsite_renewal_in_progress': 'A bounded account-evidence import is in progress. The original deadline remains in force until the protected replacement is validated and published.',
    'offsite_decryption_failed': 'Preserve the encrypted set and failure evidence; verify the correct recovery key and object integrity. Do not rotate working keys or overwrite a complete set.',
    'offsite_integrity_failed': 'Preserve the remote objects and failure evidence; inspect readback hashes and completion manifest. The affected set has not passed integrity verification.',
    'offsite_timeout': 'Inspect the bounded automatic-offsite service and its last attempt; determine which objects exist before a controlled retry.',
    'offsite_stale': 'The last complete offsite backup is overdue. Inspect the automatic-offsite timer, capacity policy and last attempt while retaining existing complete sets.',
    'offsite_readback_stale': 'The latest complete offsite backup lacks a current verified readback; inspect its encrypted manifest and readback evidence before relying on it.',
    'offsite_schedule_unavailable': 'Inspect quillmd-fresh-offsite.timer and its approved operating envelope; recurrence remains pending while the timer is disabled.',
    'offsite_pending_configuration': 'Automatic offsite recurrence is prepared but not activated. Establish the approved operating envelope before enabling the timer; earlier manual completion and restore evidence remain separately recorded.',
    'alert_configuration_unavailable': 'Install or repair the protected backup-alerts.json and approved Resend email configuration.',
    'monitoring_state_unavailable': 'Inspect private backup-alerts permissions and immutable attempt records; do not resend an uncertain attempt.',
    'monitoring_stale': 'Inspect quillmd-fresh-backup-alerts.timer and service; the last monitor check is overdue.',
    'alert_delivery_unconfirmed': 'Inspect the private alert receipt and provider evidence; do not automatically resend an uncertain request.',
    'external_monitor_unconfirmed': 'Inspect the protected external-monitor configuration and heartbeat receipt. A successful ping is not a missed-heartbeat alert or human inbox confirmation.',
    'authorized_nonclinical_test': 'This is the single authorized simulated-failure test. Normal backups were not interrupted. Confirm inbox receipt to the QuillMD operator.',
}
SAFE_ENV_FIELDS = (
    'QUILLMD_EMAIL_MODE', 'QUILLMD_EMAIL_FROM', 'QUILLMD_EMAIL_VERIFIED_DOMAIN',
    'QUILLMD_EMAIL_ALLOWED_RECIPIENTS', 'QUILLMD_APP_BASE_URL', 'RESEND_API_KEY',
)


def now():
    return datetime.now(timezone.utc)


def timestamp(value):
    result = datetime.fromisoformat(value)
    backup.require(result.tzinfo is not None, 'Invalid timestamp.')
    return result


def read_configuration():
    value = json.loads(backup.read_private(CONFIG, 16384))
    expected = {'version': 1, 'recipient': RECIPIENT, 'enabled': True,
                'synthetic_only': True, 'test_authorization_id': TEST_AUTHORIZATION}
    backup.require(value == expected and type(value['version']) is int
                   and value['enabled'] is True and value['synthetic_only'] is True,
                   'Invalid approved alert configuration.')
    # Parse without interpolation and retain only the existing email fields. Do
    # not import the application settings, its database, or private-preview login.
    parsed = dotenv_values(stream=io.StringIO(backup.read_private(ENV_FILE, 65536).decode()),
                           interpolate=False)
    values = {key: parsed.get(key, '') for key in SAFE_ENV_FIELDS}
    backup.require(all(isinstance(item, str) and item for item in values.values())
                   and values['QUILLMD_EMAIL_MODE'] == 'resend'
                   and values['QUILLMD_EMAIL_VERIFIED_DOMAIN'] == 'quillmd.com'
                   and values['QUILLMD_EMAIL_ALLOWED_RECIPIENTS'].strip().casefold() == RECIPIENT,
                   'Incomplete approved email configuration.')
    values.update(QUILLMD_RESEND_ENV_FILE='', QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME='',
                  QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD='', ALLOWED_HOSTS=['app.quillmd.com'],
                  DEFAULT_CHARSET='utf-8')
    with configured_transport(values) as transport:
        transport.resend_configuration()
        transport.validate_resend_recipient(RECIPIENT)
    return values


def systemd_state():
    """Return only fixed vocabulary; never include child stdout/stderr in reports."""
    result = {}
    commands = {
        'active': ['systemctl', 'is-active', 'quillmd-fresh-backup.timer'],
        'enabled': ['systemctl', 'is-enabled', 'quillmd-fresh-backup.timer'],
        'service': ['systemctl', 'show', 'quillmd-fresh-backup.service', '--property=Result', '--value'],
    }
    for key, command in commands.items():
        process = subprocess.run(command, capture_output=True, timeout=5,
                                 env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        expected = {'active': b'active', 'enabled': b'enabled', 'service': b'success'}[key]
        result[key] = process.returncode == 0 and process.stdout.strip() == expected
    return result


def backup_condition(at):
    try:
        unit = systemd_state()
        state = scheduled.status(at)
        if not unit['active'] or not unit['enabled']:
            return 'backup_schedule_unavailable'
        if state.get('latest_outcome') == 'running':
            active = scheduled.previous()
            age = (at - timestamp(active['started_at'])).total_seconds()
            return 'backup_in_progress' if 0 <= age <= BACKUP_TIMEOUT_SECONDS else 'backup_timeout'
        if not unit['service']:
            return 'backup_failed'
        if state.get('healthy') is True:
            try:
                current_local_bundle(state)
            except Exception:
                return 'backup_artifacts_unavailable'
            return 'healthy'
        if state.get('latest_outcome') == 'failed':
            return 'backup_failed'
        if state.get('latest_outcome') == 'complete':
            return 'backup_stale'
        return 'backup_status_unavailable'
    except Exception:
        return 'backup_status_unavailable'


def current_local_bundle(state):
    """Check continued presence without reading a key or claiming a new restore.

    Capture metadata alone survives deletion of the backup it names. Recheck
    the nonsecret summary binding and every encrypted member's structural presence;
    full member authentication remains the upload/isolated-restore gate.
    """
    run_id = state.get('last_success_run_id')
    backup.require(isinstance(run_id, str) and scheduled.RUN_PATTERN.fullmatch(run_id), 'Invalid capture identity.')
    root = backup.private_dir(scheduled.DESTINATION / run_id)
    summary = json.loads(backup.read_private(root / 'summary.json', 65536))
    backup.require(type(summary) is dict, 'Invalid capture summary.')
    summary = scheduled.validate_summary(json.dumps(dict(summary, backup_directory=str(root))))
    backup.require(summary['run_id'] == run_id and summary['file_count'] <= 10000, 'Invalid capture identity or size.')
    objects = backup.private_dir(root / 'objects')
    files = [root / 'summary.json', root / 'manifest.json.fernet', root / 'database.dump.fernet']
    count = 0
    for path in objects.iterdir():
        count += 1
        backup.require(count <= 10000 and re.fullmatch(r'[a-f0-9]{64}\.fernet', path.name), 'Invalid encrypted member.')
        files.append(path)
    backup.require(count == summary['file_count'], 'Missing encrypted member.')
    for path in files:
        info = path.lstat()
        backup.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                       and stat.S_IMODE(info.st_mode) == 0o600
                       and 0 < info.st_size <= 2 * backup.MAX_OBJECT_BYTES, 'Unsafe or missing encrypted member.')
    return True


def offsite_systemd_state():
    result = {}
    for field, operation, expected in (('active', 'is-active', b'active'),
                                       ('enabled', 'is-enabled', b'enabled')):
        child = subprocess.run(['systemctl', operation, 'quillmd-fresh-offsite.timer'],
                               capture_output=True, timeout=5,
                               env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        result[field] = child.returncode == 0 and child.stdout.strip() == expected
    return result


def offsite_service_state():
    """Observe unit failures even if the runner died before writing a new journal."""
    child = subprocess.run(['systemctl', 'show', 'quillmd-fresh-offsite.service',
                            '--property=ActiveState,Result'], capture_output=True, timeout=5,
                           env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    backup.require(child.returncode == 0, 'Offsite service status unavailable.')
    value = dict(line.split('=', 1) for line in child.stdout.decode().splitlines())
    backup.require(set(value) == {'ActiveState', 'Result'}
                   and value['ActiveState'] in {'active', 'activating', 'deactivating', 'inactive', 'failed'}
                   and value['Result'] in {'success', 'exit-code', 'signal', 'core-dump', 'timeout',
                                           'watchdog', 'start-limit-hit', 'resources', 'oom-kill', 'protocol'},
                   'Unknown offsite service status.')
    return {'active_state': value['ActiveState'], 'result': value['Result'],
            'failed': value['ActiveState'] == 'failed' or value['Result'] != 'success'}


def safe_stage(value, kind, at):
    """Whitelist stage evidence; neither an unknown field nor its value reaches output."""
    if value is None:
        return None
    required = {'run_id', 'manifest_cipher_sha256',
                'completed_at' if kind == 'remote' else 'verified_at'}
    required |= {'table_count', 'row_count', 'file_count'} if kind == 'restore' else {'object_count', 'cipher_bytes'}
    optional = {'source'} if kind == 'restore' else set()
    backup.require(isinstance(value, dict) and required <= set(value)
                   and set(value) <= required | optional, 'Invalid recovery-stage evidence.')
    backup.require(isinstance(value['run_id'], str) and scheduled.RUN_PATTERN.fullmatch(value['run_id'])
                   and isinstance(value['manifest_cipher_sha256'], str)
                   and re.fullmatch(r'[a-f0-9]{64}', value['manifest_cipher_sha256']), 'Invalid recovery identity.')
    time_key = 'completed_at' if kind == 'remote' else 'verified_at'
    age = (at - timestamp(value[time_key])).total_seconds()
    backup.require(age >= 0, 'Future recovery evidence.')
    for key in required - {'run_id', 'manifest_cipher_sha256', time_key}:
        backup.require(type(value[key]) is int and value[key] >= 0, 'Invalid recovery totals.')
    if kind == 'restore':
        backup.require(value.get('source', 'not_recorded') in
                       {'vps_key', 'independently_retrieved_key', 'not_recorded'}, 'Invalid recovery key source.')
    result = {key: value[key] for key in required}
    result.update(age_seconds=int(age))
    if kind == 'restore':
        result['source'] = value.get('source', 'not_recorded')
    else:
        result['stale'] = age > OFFSITE_STALE_SECONDS
    return result


def latest_offsite_outcome(value, at, reasons):
    """A pre-lock failure cannot be hidden by an older shared success record.

    Concurrency losers intentionally never replace shared state and are ignored;
    the active lock holder owns its running state. Other immutable failures remain
    visible until a later completed attempt, without replacing historic evidence.
    """
    state, reason = value.get('state'), value.get('reason_code')
    boundary = value.get('finished_at') or value.get('started_at')
    boundary = timestamp(boundary) if boundary else None
    latest = None
    paths = list(OFFSITE_DIRECTORY.glob('*.json'))
    backup.require(len(paths) <= 10000, 'Oversized offsite attempt history.')
    for path in paths:
        if not scheduled.RUN_PATTERN.fullmatch(path.stem):
            continue
        attempt = json.loads(backup.read_private(path, 65536))
        backup.require(isinstance(attempt, dict) and type(attempt.get('version')) is int
                       and attempt['version'] == 1 and attempt.get('attempt') == path.stem
                       and attempt.get('state') in {'complete', 'failed', 'refused'}
                       and attempt.get('reason_code') in set(reasons) | {None}, 'Invalid offsite attempt.')
        outcome, code = attempt['state'], attempt.get('reason_code')
        backup.require((outcome == 'complete') == (code is None), 'Contradictory offsite attempt.')
        finished = timestamp(attempt['finished_at'])
        backup.require(finished <= at, 'Future offsite attempt.')
        if code == 'lock_busy':
            continue
        if (boundary is None or finished > boundary) and (latest is None or finished > latest[0]):
            latest = (finished, outcome, code)
    if state != 'running' and latest and latest[1] in {'failed', 'refused'}:
        return latest[1:]
    return state, reason


def capacity_status(value, at):
    """Observed scoped bytes, plus a same-size estimate; never an account-wide total."""
    if value is None:
        return None
    fields = {'observed_at', 'scope_stored_bytes_after', 'scope_ceiling_bytes', 'last_complete_cipher_bytes'}
    backup.require(type(value) is dict and set(value) == fields
                   and all(type(value[name]) is int and value[name] >= 0 for name in fields - {'observed_at'})
                   and value['scope_stored_bytes_after'] <= value['scope_ceiling_bytes'],
                   'Invalid scoped capacity evidence.')
    age = (at - timestamp(value['observed_at'])).total_seconds()
    backup.require(age >= 0, 'Future scoped capacity evidence.')
    headroom = value['scope_ceiling_bytes'] - value['scope_stored_bytes_after']
    size = value['last_complete_cipher_bytes']
    return {**value, 'age_seconds': int(age), 'stale': age > OFFSITE_STALE_SECONDS,
            'remaining_scope_bytes_at_observation': headroom,
            'room_for_same_size_backup_at_observation': headroom >= size,
            'estimated_additional_daily_backups_of_same_size': headroom // size if size else None,
            'estimate_assumptions': 'One new retained set per day at the last complete size; no deletion, retries, other writes or growth. Inventory pagination and daily request limits can refuse sooner.',
            'future_backup_size_known': False, 'account_wide_usage_measurement': False}


def manual_operation_status(at, reasons):
    path = OFFSITE_DIRECTORY / 'manual-status.json'
    if not path.exists() and not path.is_symlink():
        return None
    value = json.loads(backup.read_private(path, 16384))
    fields = {'version', 'action', 'attempt', 'state', 'reason_code', 'started_at',
              'run_id', 'manifest_cipher_sha256', 'restore_verified', 'shared_accounting'}
    backup.require(type(value) is dict and fields <= set(value) <= fields | {'finished_at'}
                   and type(value['version']) is int and value['version'] == 1
                   and value['action'] == 'isolated_restore'
                   and value['state'] in {'running', 'complete', 'failed', 'refused'}
                   and value['reason_code'] in set(reasons) | {None}
                   and type(value['restore_verified']) is bool and value['shared_accounting'] is True
                   and isinstance(value['attempt'], str) and scheduled.RUN_PATTERN.fullmatch(value['attempt'])
                   and isinstance(value['run_id'], str) and scheduled.RUN_PATTERN.fullmatch(value['run_id'])
                   and isinstance(value['manifest_cipher_sha256'], str)
                   and re.fullmatch('[a-f0-9]{64}', value['manifest_cipher_sha256']),
                   'Invalid manual operation status.')
    started = timestamp(value['started_at'])
    backup.require(started <= at, 'Future manual operation status.')
    if value['state'] == 'running':
        backup.require('finished_at' not in value and value['reason_code'] is None
                       and value['restore_verified'] is False, 'Invalid running manual operation.')
        condition = 'offsite_in_progress' if (at - started).total_seconds() <= 945 else 'offsite_timeout'
    else:
        backup.require('finished_at' in value and started <= timestamp(value['finished_at']) <= at,
                       'Invalid manual completion time.')
        if value['state'] == 'complete':
            backup.require(value['reason_code'] is None and value['restore_verified'] is True,
                           'Unverified manual completion.')
            condition = None
        else:
            backup.require(value['reason_code'] is not None, 'Manual failure reason absent.')
            condition = reasons[value['reason_code']]
    return {**value, 'condition': condition}


def offsite_policy_condition(at):
    """Recheck the current approved envelope without authorizing or calling B2."""
    try:
        try:
            from . import automatic_offsite
        except ImportError:
            import automatic_offsite
        automatic_offsite.policy(at=at)
        return None
    except Exception:
        return 'offsite_policy_unavailable'


def allowance_status(at):
    """Expose freshness and local reservations, never infer account-wide usage."""
    result = {'eligible': False, 'reason': 'policy_invalid',
              'eligibility_scope': 'policy and ledger validity; each operation separately reserves its full bounded work',
              'observed_at': None, 'valid_until': None, 'observation_age_seconds': None,
              'local_reservations': None, 'remaining_requests': None,
              'remaining_reserved_response_bytes': None,
              'provider_download_charges_confirmed': False}
    try:
        try:
            from . import automatic_offsite as engine
        except ImportError:
            import automatic_offsite as engine
        limits = engine.policy(at=at)
        allocation = allocation_status(limits, at)
        result.update(eligible=True, reason=None)
    except Exception as failure:
        result.update(eligible=False, reason=getattr(failure, 'code', 'state_invalid'))
        if result['reason'] not in {'policy_missing', 'policy_invalid', 'policy_expired', 'state_invalid'}:
            result['reason'] = 'policy_invalid'
        limits = allocation = None
        if result['reason'] == 'policy_expired':
            # A rejected current policy must not erase the last authenticated
            # observation. Historical validation is display-only, never admission.
            try:
                candidate = json.loads(backup.read_private(engine.POLICY, 16384))
                observed = timestamp(candidate['observed_at'])
                backup.require(observed <= at, 'Future account observation.')
                historical = engine.policy(at=observed)
                backup.require(historical == candidate, 'Policy changed during observation.')
                allocation = allocation_status(historical, observed)
                limits = historical
            except Exception:
                limits = allocation = None
    if limits is not None:
        result.update(observed_at=limits['observed_at'], valid_until=limits['valid_until'],
                      renewal_requires_desktop=allocation['renewal_requires_desktop'],
                      observation_age_seconds=int((at - timestamp(limits['observed_at'])).total_seconds()),
                      seconds_until_expiry=int((timestamp(limits['valid_until']) - at).total_seconds()),
                      daily_request_budget=limits['daily_request_budget'],
                      daily_download_budget_bytes=limits['daily_download_budget_bytes'])
    try:
        value = engine.budget_summary(state=OFFSITE_DIRECTORY, at=at)
        result['local_reservations'] = value
        result['local_reservations']['current_utc_day'] = value['day'] == at.strftime('%Y-%m-%d')
        if limits is not None:
            result.update(remaining_requests=max(0, limits['daily_request_budget'] - value['requests']),
                          remaining_reserved_response_bytes=max(0, limits['daily_download_budget_bytes'] - value['download_bytes']))
    except Exception:
        result.update(eligible=False, reason='state_invalid')
    return result


def next_run_admission(at, next_run, allowance, remote):
    """A local forecast, not a promise about future evidence or provider usage."""
    result = {'scheduled_at': next_run, 'policy_covered': False,
              'admission_status': 'unverified',
              'ledger_day': None, 'remaining_requests': None,
              'remaining_reserved_response_bytes': None,
              'same_size_cycle_estimate': None, 'same_size_cycle_fits': None,
              'future_success_verified': False}
    if not next_run:
        return result
    run_at = timestamp(next_run)
    if run_at <= at:
        result['timer_event_due_or_in_progress'] = True
        return result
    expiry = allowance.get('valid_until')
    result['policy_covered'] = bool(allowance.get('eligible') and expiry
        and run_at + timedelta(seconds=OFFSITE_ADMISSION_WINDOW_SECONDS) < timestamp(expiry))
    try:
        try:
            from . import automatic_offsite as engine
        except ImportError:
            import automatic_offsite as engine
        value = engine.budget_summary(state=OFFSITE_DIRECTORY, at=run_at)
        requests_left = allowance['daily_request_budget'] - value['requests']
        bytes_left = allowance['daily_download_budget_bytes'] - value['download_bytes']
        result.update(ledger_day=value['day'],
                      uses_later_utc_day=value['day'] > at.strftime('%Y-%m-%d'),
                      remaining_requests=max(0, requests_left),
                      remaining_reserved_response_bytes=max(0, bytes_left))
        if remote:
            count = remote['object_count']
            estimate = {'requests': 2 * count + 4,
                        'reserved_response_bytes': remote['cipher_bytes'] + count * (65536 + 131072) + 131072 + 2359296,
                        'extra_inventory_pages_or_retries_included': False,
                        'future_backup_size_known': False}
            result.update(same_size_cycle_estimate=estimate,
                          same_size_cycle_fits=requests_left >= estimate['requests']
                          and bytes_left >= estimate['reserved_response_bytes'])
    except Exception:
        result['budget_forecast_unavailable'] = True
    result['admission_status'] = ('policy_not_covered' if not result['policy_covered'] else
        'estimated_budget_shortfall' if result['same_size_cycle_fits'] is False else
        'conditional_on_runtime_checks' if result['same_size_cycle_fits'] is True else 'budget_forecast_unavailable')
    return result


def allocation_status(limits, at):
    try:
        from . import automatic_offsite as engine, offsite_allocation
    except ImportError:
        import automatic_offsite as engine
        import offsite_allocation
    return offsite_allocation.validate(limits, engine.POLICY, at)


def renewal_status(at):
    """Read only the renewal mechanism's nonsecret operator-facing fields."""
    result = {'state': 'unavailable', 'last_attempt_at': None,
              'last_successful_observation_at': None, 'valid_until': None,
              'reason_code': 'renewal_status_unavailable', 'ticket_id': None,
              'unattended_available': False,
              'required_access': 'separate_account_wide_read_only_audit',
              'failure_does_not_extend_validity': True}
    try:
        try:
            from . import offsite_renewal
        except ImportError:
            import offsite_renewal
        value = offsite_renewal.renewal_status(at)
        backup.require(type(value) is dict and set(value) == set(result)
                       and value['state'] in {'never_requested', 'awaiting_external_audit', 'importing', 'failed', 'installed'}
                       and value['unattended_available'] is False
                       and value['required_access'] == result['required_access']
                       and value['failure_does_not_extend_validity'] is True,
                       'Invalid renewal status.')
        for field in ('last_attempt_at', 'last_successful_observation_at', 'valid_until'):
            if value[field] is not None:
                observed = timestamp(value[field])
                backup.require(field == 'valid_until' or observed <= at, 'Future renewal evidence.')
        backup.require(value['ticket_id'] is None or isinstance(value['ticket_id'], str)
                       and re.fullmatch('[a-f0-9]{32}', value['ticket_id']), 'Invalid renewal ticket.')
        backup.require(value['reason_code'] is None or value['reason_code'] in {
            'audit_access_unavailable', 'audit_failed', 'ticket_expired', 'ticket_invalid',
            'evidence_invalid', 'policy_conflict', 'publication_failed',
            'budget_exhausted', 'state_invalid'},
            'Invalid renewal outcome.')
        if value['state'] == 'importing':
            backup.require(value['last_attempt_at'] is not None, 'Import start is absent.')
            if (at - timestamp(value['last_attempt_at'])).total_seconds() > 300:
                value = dict(value, state='failed', reason_code='state_invalid')
        return {key: value[key] for key in result}
    except Exception:
        return result


def next_timer_run(unit):
    """Only the two permanent calendar timers; never echo arbitrary systemd output."""
    try:
        backup.require(unit in {'quillmd-fresh-backup.timer', 'quillmd-fresh-offsite.timer'}, 'Unknown timer.')
        child = subprocess.run(['systemctl', 'show', unit, '--property=NextElapseUSecRealtime', '--value'],
                               capture_output=True, timeout=5, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TZ': 'UTC'})
        backup.require(child.returncode == 0, 'Timer status unavailable.')
        date = datetime.strptime(child.stdout.decode().strip(), '%a %Y-%m-%d %H:%M:%S UTC')
        return date.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return None


def external_configuration():
    if not EXTERNAL_CONFIG.exists() and not EXTERNAL_CONFIG.is_symlink():
        return None
    backup.private_dir(EXTERNAL_CONFIG.parent)
    backup.require(EXTERNAL_CONFIG.lstat().st_nlink == 1, 'Invalid external-monitor file.')
    value = json.loads(backup.read_private(EXTERNAL_CONFIG, 4096))
    backup.require(type(value) is dict and set(value) == {'version', 'provider', 'check_url',
                   'owner_approval_reference', 'synthetic_only'} and type(value['version']) is int
                   and value['version'] == 1 and value['provider'] == 'healthchecks.io'
                   and value['synthetic_only'] is True
                   and isinstance(value['owner_approval_reference'], str)
                   and 12 <= len(value['owner_approval_reference']) <= 256, 'Invalid approved heartbeat configuration.')
    url = value['check_url']
    parsed = urlsplit(url)
    backup.require(isinstance(url, str) and parsed.scheme == 'https' and parsed.netloc == 'hc-ping.com'
                   and not parsed.query and not parsed.fragment
                   and re.fullmatch(r'/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', parsed.path),
                   'Invalid heartbeat endpoint.')
    return url


def external_heartbeat(at, *, healthy=False, execute=False):
    """Optional success-only heartbeat. No URL, response or exception reaches evidence.

    A durable reservation precedes I/O; manual checks cannot multiply pings. A
    later scheduled period is a new heartbeat, not a retry of uncertain delivery.
    """
    result = {'configured': False, 'outcome': 'not_configured', 'last_attempt_at': None,
              'provider_accepted': False, 'missed_heartbeat_alert_verified': False,
              'human_inbox_confirmed': False}
    try:
        url = external_configuration()
        if url is None:
            return result
        result.update(configured=True, outcome='not_attempted')
        path = DIRECTORY / 'external-heartbeat.json'
        if path.exists() or path.is_symlink():
            saved = json.loads(backup.read_private(path, 4096))
            backup.require(type(saved) is dict and set(saved) == {'version', 'attempted_at', 'outcome'}
                           and type(saved['version']) is int and saved['version'] == 1
                           and saved['outcome'] in {'pending', 'provider_accepted', 'uncertain_no_retry'},
                           'Invalid heartbeat receipt.')
            age = (at - timestamp(saved['attempted_at'])).total_seconds()
            backup.require(age >= 0, 'Future heartbeat receipt.')
            result.update(last_attempt_at=saved['attempted_at'], outcome=saved['outcome'],
                          provider_accepted=saved['outcome'] == 'provider_accepted',
                          stale=age > STALE_SECONDS)
            if age < HEARTBEAT_INTERVAL_SECONDS:
                return result
        if not execute or not healthy:
            return result
        pending = {'version': 1, 'attempted_at': at.isoformat(), 'outcome': 'pending'}
        scheduled.atomic_status(path, pending)
        try:
            with requests.Session() as session:
                session.trust_env = False
                with session.get(url, timeout=(3, 5), allow_redirects=False, stream=True,
                                 headers={'User-Agent': 'QuillMD-private-monitor/1'}) as response:
                    backup.require(response.status_code == 200, 'Heartbeat was not accepted.')
                    # HTTP200 also means "OK (not found)" / rate-limited; accept only exact OK.
                    content = response.raw.read(3, decode_content=False)
                    backup.require(content == b'OK', 'Heartbeat was not accepted.')
            pending['outcome'] = 'provider_accepted'
        except Exception:
            pending['outcome'] = 'uncertain_no_retry'
        scheduled.atomic_status(path, pending)
        result.update(outcome=pending['outcome'], last_attempt_at=pending['attempted_at'],
                      provider_accepted=pending['outcome'] == 'provider_accepted', stale=False)
    except Exception:
        result.update(outcome='configuration_or_state_invalid', provider_accepted=False)
    return result


def recovery_status(at):
    """No provider request: completion, readback and restore stay separate claims."""
    result = {'condition': 'offsite_status_unavailable', 'last_remote_complete': None,
              'last_verified_readback': None, 'last_isolated_restore': None,
              'recurrence_active': False, 'recurrence_enabled': False,
              'independent_key_custody_verified': False,
              'last_successful_scheduled_run': None,
              'scheduled_execution_evidence': 'not_recorded; timer enablement and LastTrigger alone do not prove execution origin',
              'renewal': renewal_status(at),
              'next_permanent_timer_run': next_timer_run('quillmd-fresh-offsite.timer'),
              'allowance': allowance_status(at)}
    try:
        backup.private_dir(OFFSITE_DIRECTORY)
        value = json.loads(backup.read_private(OFFSITE_DIRECTORY / 'status.json', 65536))
        backup.require(isinstance(value, dict) and type(value.get('version')) is int
                       and value['version'] == 1, 'Invalid automatic-offsite status.')
        for key, kind in (('last_remote_complete', 'remote'), ('last_verified_readback', 'readback'),
                          ('last_isolated_restore', 'restore')):
            result[key] = safe_stage(value.get(key), kind, at)
        result['capacity'] = capacity_status(value.get('last_capacity'), at)
        result['current_backup_health'] = 'healthy' if (
            result['last_remote_complete'] and not result['last_remote_complete']['stale']
            and result['last_verified_readback'] and not result['last_verified_readback']['stale']
            and all(result['last_verified_readback'][key] == result['last_remote_complete'][key]
                    for key in ('run_id', 'manifest_cipher_sha256', 'object_count', 'cipher_bytes'))) else 'unverified_or_stale'
        # Custody is a separate owner/off-host gate. A local restore cannot establish it.
        result['independent_key_custody_verified'] = (
            bool(result['last_isolated_restore'])
            and result['last_isolated_restore']['source'] == 'independently_retrieved_key')
        unit = offsite_systemd_state()
        result.update(recurrence_active=unit['active'], recurrence_enabled=unit['enabled'])
        result['service'] = offsite_service_state()
        next_run = result['next_permanent_timer_run']
        expiry = result['allowance'].get('valid_until')
        result['next_run_admission'] = next_run_admission(at, next_run, result['allowance'], result['last_remote_complete'])
        result['next_run_covered_by_policy'] = result['next_run_admission']['policy_covered']
        reasons = {
            'policy_missing': 'offsite_policy_unavailable', 'policy_invalid': 'offsite_policy_unavailable',
            'policy_expired': 'offsite_policy_expired', 'capacity_refused': 'offsite_capacity_refused',
            'budget_exhausted': 'offsite_budget_refused', 'remote_corrupt': 'offsite_integrity_failed',
            'remote_uncertain': 'offsite_integrity_failed',
            'local_authentication_failed': 'offsite_decryption_failed',
            'transport_failed': 'offsite_upload_failed', 'deadline': 'offsite_timeout',
            'cleanup_failed': 'offsite_cleanup_failed',
            'lock_busy': 'offsite_upload_failed',
            'local_backup_stale': 'backup_stale', 'scope_refused': 'offsite_policy_unavailable',
            'state_invalid': 'offsite_status_unavailable',
            'pending_configuration': 'offsite_pending_configuration',
            'recovery_failed': 'offsite_recovery_failed',
        }
        result['manual_operation'] = manual_operation_status(at, reasons)
        state, reason = latest_offsite_outcome(value, at, reasons)
        backup.require(state in {'pending_configuration', 'running', 'complete', 'failed', 'refused'}
                       and reason in set(reasons) | {None}, 'Invalid automatic-offsite outcome.')
        backup.require(state not in {'running', 'complete'} or reason is None,
                       'Contradictory automatic-offsite outcome.')
        execution = {'state': state, 'origin': 'not_recorded', 'scheduled_success_verified': False}
        if 'invocation' in value:
            invocation = value['invocation']
            backup.require(type(invocation) is dict and set(invocation) == {
                'source', 'systemd_invocation_id', 'timer_trigger_verified'}
                and invocation['source'] in {'systemd_environment', 'unclassified'}
                and invocation['timer_trigger_verified'] is False, 'Invalid invocation evidence.')
            identifier = invocation['systemd_invocation_id']
            backup.require((invocation['source'] == 'unclassified' and identifier is None)
                or (invocation['source'] == 'systemd_environment' and isinstance(identifier, str)
                    and re.fullmatch('[a-f0-9]{32}', identifier)), 'Invalid invocation identity.')
            execution.update(origin=invocation['source'], systemd_invocation_id=identifier)
        for field in ('started_at', 'finished_at'):
            if value.get(field) is not None:
                observed = timestamp(value[field])
                backup.require(observed <= at, 'Future execution evidence.')
                execution[field] = observed.isoformat()
        # An immutable newer failure may outrank mutable status. Do not attach
        # the older record's times to that newer outcome.
        if state == value.get('state') and reason == value.get('reason_code'):
            result['latest_execution'] = execution
        if state == 'pending_configuration':
            backup.require(not unit['enabled'] and not unit['active'], 'Pending state with active recurrence.')
            condition = 'offsite_pending_configuration'
        elif state in {'failed', 'refused'}:
            backup.require(reason is not None, 'Missing offsite failure reason.')
            condition = reasons[reason]
        elif state == 'running':
            age = (at - timestamp(value['started_at'])).total_seconds()
            condition = 'offsite_in_progress' if 0 <= age <= OFFSITE_TIMEOUT_SECONDS else 'offsite_timeout'
        elif result['service']['failed']:
            condition = 'offsite_upload_failed'
        elif not result['last_remote_complete'] or result['last_remote_complete']['stale']:
            condition = 'offsite_stale'
        elif (not result['last_verified_readback'] or result['last_verified_readback']['stale']
              or any(result['last_verified_readback'][key] != result['last_remote_complete'][key]
                     for key in ('run_id', 'manifest_cipher_sha256', 'object_count', 'cipher_bytes'))):
            condition = 'offsite_readback_stale'
        elif not unit['enabled'] or not unit['active']:
            condition = 'offsite_schedule_unavailable'
        else:
            condition = offsite_policy_condition(at) or 'healthy'
            if result['allowance'].get('reason') == 'policy_expired':
                condition = 'offsite_policy_expired'
            if condition == 'healthy' and expiry and not result['next_run_covered_by_policy']:
                condition = 'offsite_policy_renewal_due'
            if (condition == 'healthy' and expiry
                    and (timestamp(expiry) - at).total_seconds() <= POLICY_WARNING_SECONDS):
                condition = 'offsite_policy_expiring'
            if (condition == 'healthy' and result['capacity']
                    and not result['capacity']['room_for_same_size_backup_at_observation']):
                condition = 'offsite_capacity_low'
            if condition == 'healthy' and result['next_run_admission']['same_size_cycle_fits'] is False:
                condition = 'offsite_next_run_budget_low'
            if condition == 'healthy' and result['renewal']['state'] == 'failed':
                condition = 'offsite_renewal_failed'
            if condition == 'healthy' and result['renewal']['state'] == 'importing':
                condition = 'offsite_renewal_in_progress'
        if (condition in WARNINGS | {'healthy', 'offsite_pending_configuration', 'offsite_schedule_unavailable', 'offsite_renewal_in_progress'}
                and result['manual_operation'] and result['manual_operation']['condition']):
            condition = result['manual_operation']['condition']
        result['condition'] = condition
        result['disabled_reason'] = condition if not unit['enabled'] or not unit['active'] else None
    except Exception:
        result['condition'] = 'offsite_status_unavailable'
    return result


def local_capture_status(at):
    """Copy only verified, nonclinical last-capture identifiers from the existing monitor."""
    try:
        value = scheduled.status(at)
        run_id, succeeded = value.get('last_success_run_id'), value.get('last_success_at')
        backup.require(isinstance(run_id, str) and scheduled.RUN_PATTERN.fullmatch(run_id), 'Invalid capture.')
        age = (at - timestamp(succeeded)).total_seconds()
        backup.require(age >= 0, 'Invalid capture time.')
        try:
            present = current_local_bundle(value)
        except Exception:
            present = False
        return {'last_success_run_id': run_id, 'last_success_at': succeeded,
                'age_seconds': int(age), 'stale': age > scheduled.MAX_AGE_SECONDS,
                'encrypted_artifacts_present': present,
                'next_permanent_timer_run': next_timer_run('quillmd-fresh-backup.timer')}
    except Exception:
        return None


def initial_state():
    return {'format': 1, 'last_check_at': None, 'condition': 'monitoring_stale',
            'incident_id': None, 'incident_attempt': None, 'last_attempt_at': None}


def read_state():
    path = DIRECTORY / 'status.json'
    if not path.exists() and not path.is_symlink():
        # Partial recovery may lose mutable state while retaining a durable
        # request record. Do not invent a fresh incident and send again.
        backup.require(not any(DIRECTORY.glob('incident-*')), 'Incident state is missing.')
        return initial_state()
    value = json.loads(backup.read_private(path, 65536))
    backup.require(set(value) == set(initial_state()) and value['format'] == 1
                   and value['condition'] in ERRORS, 'Invalid monitor state.')
    for key in ('last_check_at', 'last_attempt_at'):
        if value[key] is not None:
            timestamp(value[key])
    for key in ('incident_id', 'incident_attempt'):
        backup.require(value[key] is None or isinstance(value[key], str)
                       and re.fullmatch(r'[a-f0-9]{32}', value[key]), 'Invalid incident identity.')
    return value


@contextmanager
def locked():
    backup.private_dir(DIRECTORY)
    fd = os.open(DIRECTORY / 'monitor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        backup.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                       and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
                       'Invalid monitor lock.')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


@contextmanager
def configured_transport(values):
    # Operations run outside Django's application initialization, with the
    # established transport only. Explicit minimal settings exclude app secrets.
    from django.conf import settings
    from django.test.utils import override_settings
    if not settings.configured:
        settings.configure(DEFAULT_CHARSET='utf-8')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core import email_backend
    with override_settings(**values):
        yield email_backend


def email_transport(values, subject, body):
    from django.core.mail import EmailMessage
    with configured_transport(values) as transport:
        message = EmailMessage(subject=subject, body=body, to=[RECIPIENT])
        count = transport.ResendEmailBackend(fail_silently=False).send_messages([message])
    identifier = getattr(message, 'provider_message_id', '')
    backup.require(count == 1 and re.fullmatch(r'[A-Za-z0-9_-]{1,200}', identifier),
                   'Provider acceptance not confirmed.')
    return identifier


def attempt_alert(values, condition, identity, at, *, test=False):
    prefix = 'test-' + TEST_AUTHORIZATION if test else 'incident-' + identity
    pending = DIRECTORY / (prefix + '-pending.json')
    result_path = DIRECTORY / (prefix + '-result.json')
    # Exclusive create BEFORE the request prevents a crash/restart or parallel
    # command from sending an uncertain attempt again. Existing evidence stays.
    # A result is independent evidence of a request even when a damaged or
    # incomplete recovery lost its pending marker. Never send before inspecting
    # either artifact; malformed/unsafe artifacts also suppress a new request.
    if (result_path.exists() or result_path.is_symlink()
            or pending.exists() or pending.is_symlink()):
        return receipt(prefix)
    record = {'format': 1, 'kind': 'authorized_test' if test else 'operational',
              'condition': condition, 'attempted_at': at.isoformat(), 'outcome': 'pending',
              'provider_message_id': None, 'provider_accepted': False,
              'delivery_confirmed': False, 'inbox_receipt_confirmed': False}
    backup.write_private(pending, json.dumps(record, sort_keys=True).encode() + b'\n')
    subject = ('[QuillMD NONCLINICAL TEST] Simulated backup failure' if test
               else '[QuillMD operations] Backup recovery requires attention')
    body = ('QuillMD private synthetic environment: operational backup notification.\n'
            + ('AUTHORIZED SIMULATED FAILURE; NO BACKUP WAS INTERRUPTED.\n' if test else '')
            + f'Condition: {condition}\nUTC check: {at.isoformat()}\nReference: {prefix}\n'
            + ERRORS[condition] + '\n\nNo patient information or credentials are included. '
            'This message confirms neither offsite recovery nor outside-host monitoring.\n')
    try:
        provider_id = email_transport(values, subject, body)
        record.update(outcome='provider_accepted', provider_accepted=True,
                      provider_message_id=provider_id)
    except Exception:
        # A transport exception cannot prove non-delivery. No automatic retry,
        # including after the provider's idempotency retention window expires.
        record['outcome'] = 'uncertain_no_retry'
    backup.write_private(result_path, json.dumps(record, sort_keys=True).encode() + b'\n')
    return record


def receipt(prefix):
    path = DIRECTORY / (prefix + '-result.json')
    if not path.exists() and not path.is_symlink():
        path = DIRECTORY / (prefix + '-pending.json')
    value = json.loads(backup.read_private(path, 16384))
    backup.require(set(value) == {'format', 'kind', 'condition', 'attempted_at', 'outcome',
                                  'provider_message_id', 'provider_accepted',
                                  'delivery_confirmed', 'inbox_receipt_confirmed'}
                   and type(value['format']) is int and value['format'] == 1
                   and value['kind'] in {'authorized_test', 'operational'}
                   and value['outcome'] in {'pending', 'provider_accepted', 'uncertain_no_retry'}
                   and value['condition'] in ERRORS
                   and value['provider_accepted'] is (value['outcome'] == 'provider_accepted')
                   and value['delivery_confirmed'] is False and value['inbox_receipt_confirmed'] is False,
                   'Invalid alert receipt.')
    timestamp(value['attempted_at'])
    backup.require((value['kind'] == 'authorized_test') ==
                   (value['condition'] == 'authorized_nonclinical_test')
                   and (value['kind'] == 'authorized_test') == prefix.startswith('test-'),
                   'Invalid receipt kind.')
    identifier = value['provider_message_id']
    backup.require((isinstance(identifier, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}', identifier))
                   if value['provider_accepted'] else identifier is None, 'Invalid provider identifier.')
    # Return a fixed set, never unexpected fields supplied by a malformed file.
    return {key: value[key] for key in ('outcome', 'provider_message_id', 'provider_accepted',
                                      'delivery_confirmed', 'inbox_receipt_confirmed')}


def report(condition, *, checked_at=None, alert=None, recovery=None, local_capture=None, external=None):
    warning = condition in WARNINGS
    in_progress = condition in {'backup_in_progress', 'offsite_in_progress', 'offsite_renewal_in_progress'}
    return {'format': 1, 'condition': condition, 'action': ERRORS[condition],
            'checked_at': checked_at, 'healthy': condition in {'healthy', 'backup_in_progress', 'offsite_in_progress'},
            'severity': 'warning' if warning else 'healthy' if condition == 'healthy' else 'in_progress' if in_progress else 'failure',
            'alert': alert, 'offsite_recovery_verified': bool(recovery and recovery.get('last_isolated_restore')),
            'local_capture': local_capture, 'offsite': recovery,
            'external_monitor': external,
            'outside_host_failure_detection': False, 'clinical_content_included': False}


def check(at=None):
    at = at or now()
    # ⚠️ THE INDEPENDENT RECOVERY PATH, AND IT LIVES HERE FOR A REASON. An activation pauses the
    # publisher timer and restores it in a `finally` — but a `finally` does not run after SIGKILL
    # or a host failure, and a paused publisher cannot recover itself because it is not running.
    # This check runs on its OWN five-minute timer, which keeps ticking throughout, so it is the
    # one thing positioned to pay that debt. It is a no-op unless a pause is actually owed, and it
    # refuses while an activation still holds exclusion, so it can never interrupt a live act.
    try:
        from ops import activation_exclusion as _exclusion
        _exclusion.recover_publication()
    except Exception:
        # Recovery is best-effort and must never turn the alert check itself into a failure:
        # a monitor that dies trying to fix something monitors nothing.
        pass
    try:
        with locked():
            state = read_state()
            try:
                values = read_configuration()
            except Exception:
                state.update(last_check_at=at.isoformat(), condition='alert_configuration_unavailable')
                scheduled.atomic_status(DIRECTORY / 'status.json', state)
                return report(state['condition'], checked_at=state['last_check_at']), 1
            condition = backup_condition(at)
            recovery = recovery_status(at)
            local_capture = local_capture_status(at)
            if condition == 'healthy':
                condition = recovery['condition']
            external = external_heartbeat(at, healthy=condition == 'healthy' or condition in WARNINGS, execute=True)
            if (condition == 'healthy' or condition in WARNINGS) and external['outcome'] in {'configuration_or_state_invalid', 'pending', 'uncertain_no_retry'}:
                condition = 'external_monitor_unconfirmed'
            state.update(last_check_at=at.isoformat(), condition=condition)
            alert = None
            if condition in {'healthy', 'offsite_policy_expiring'}:
                state.update(incident_id=None, incident_attempt=None)
            elif condition not in {'backup_in_progress', 'offsite_in_progress', 'offsite_pending_configuration', 'offsite_renewal_in_progress'}:
                if not state['incident_id']:
                    state['incident_id'] = secrets.token_hex(16)
                if state['incident_attempt']:
                    alert = receipt('incident-' + state['incident_attempt'])
                elif (state['last_attempt_at'] is None or
                      (at - timestamp(state['last_attempt_at'])).total_seconds() >= COOLDOWN_SECONDS):
                    state.update(incident_attempt=state['incident_id'], last_attempt_at=at.isoformat())
                    # Persist the identity before sending: a crash between state
                    # and pending receipt fails closed, requiring operator review.
                    scheduled.atomic_status(DIRECTORY / 'status.json', state)
                    alert = attempt_alert(values, condition, state['incident_id'], at)
                else:
                    alert = {'outcome': 'cooldown_suppressed', 'provider_accepted': False}
            scheduled.atomic_status(DIRECTORY / 'status.json', state)
            if alert and alert['outcome'] in {'pending', 'uncertain_no_retry'}:
                return report('alert_delivery_unconfirmed', checked_at=state['last_check_at'], alert=alert,
                              recovery=recovery, local_capture=local_capture, external=external), 1
            result = report(condition, checked_at=state['last_check_at'], alert=alert,
                            recovery=recovery, local_capture=local_capture, external=external)
            return result, 0 if result['healthy'] or condition in WARNINGS | {'offsite_renewal_in_progress'} else 1
    except Exception:
        return report('monitoring_state_unavailable'), 1


def test_alert(at=None):
    at = at or now()
    try:
        with locked():
            try:
                values = read_configuration()
            except Exception:
                return report('alert_configuration_unavailable'), 1
            alert = attempt_alert(values, 'authorized_nonclinical_test', TEST_AUTHORIZATION, at, test=True)
            result = report('authorized_nonclinical_test', checked_at=at.isoformat(), alert=alert)
            return result, 0 if alert['provider_accepted'] else 1
    except Exception:
        return report('monitoring_state_unavailable'), 1


def status(at=None):
    at = at or now()
    try:
        backup.private_dir(DIRECTORY)
        state = read_state()
        try:
            read_configuration()
        except Exception:
            return report('alert_configuration_unavailable', checked_at=state['last_check_at']), 1
        age = (at - timestamp(state['last_check_at'])).total_seconds() if state['last_check_at'] else None
        condition = 'monitoring_stale' if age is None or not 0 <= age <= STALE_SECONDS else state['condition']
        alert = receipt('incident-' + state['incident_attempt']) if state['incident_attempt'] else None
        if alert and alert['outcome'] in {'pending', 'uncertain_no_retry'} and condition != 'monitoring_stale':
            condition = 'alert_delivery_unconfirmed'
        recovery = recovery_status(at)
        # Status is read-only but still exposes fresh offsite age/configuration;
        # a previous healthy check cannot hide newly stale recovery evidence.
        if condition in {'healthy', 'backup_in_progress', 'offsite_in_progress', 'offsite_pending_configuration',
                         'offsite_policy_renewal_due', 'offsite_policy_expiring', 'offsite_policy_expired',
                         'offsite_renewal_failed', 'offsite_renewal_in_progress', 'offsite_next_run_budget_low'}:
            local_condition = backup_condition(at)
            condition = recovery['condition'] if local_condition == 'healthy' else local_condition
        external = external_heartbeat(at)
        if (condition == 'healthy' or condition in WARNINGS) and external['outcome'] in {'configuration_or_state_invalid', 'pending', 'uncertain_no_retry'}:
            condition = 'external_monitor_unconfirmed'
        result = report(condition, checked_at=state['last_check_at'], alert=alert,
                        recovery=recovery, local_capture=local_capture_status(at), external=external)
        result.update(monitor_age_seconds=int(age) if age is not None else None,
                      stale_after_seconds=STALE_SECONDS)
        return result, 0 if result['healthy'] or condition in WARNINGS | {'offsite_renewal_in_progress'} else 1
    except Exception:
        return report('monitoring_state_unavailable'), 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'status', 'test'))
    action = parser.parse_args().action
    os.umask(0o077)
    result, code = {'check': check, 'status': status, 'test': test_alert}[action]()
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
