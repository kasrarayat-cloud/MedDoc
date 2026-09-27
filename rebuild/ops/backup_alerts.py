#!/usr/bin/env python3
"""Private, nonclinical recovery-stage alerts. No database access or backup mutation."""
import argparse
from contextlib import contextmanager
import copy
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
import tempfile
import time
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
#: Between the FIRST notices of successive incidents: a condition flapping between healthy and
#: unhealthy opens a new incident every flap, and this is what stops that becoming a storm.
COOLDOWN_SECONDS = 24 * 3600
#: Inside one open incident, a still-open incident is re-announced this long after its last notice.
REMINDER_SECONDS = 24 * 3600
#: Inside one open incident, the least time between a notice and a change to a condition not yet
#: announced that is no more severe than that notice. A condition MORE severe than the LAST notice
#: is not held by it (see plan_notice for why that cannot loop).
ESCALATION_SPACING_SECONDS = 3600
NOTICES = ('initial', 'escalation', 'reminder')
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
IN_PROGRESS = {'backup_in_progress', 'offsite_in_progress', 'offsite_renewal_in_progress'}
#: A check in one of these closes the open incident.
QUIET = {'healthy', 'offsite_policy_expiring'}
#: A check in one of these keeps the incident open and announces nothing.
UNANNOUNCED = {'backup_in_progress', 'offsite_in_progress', 'offsite_pending_configuration',
               'offsite_renewal_in_progress'}
ANNOUNCEABLE = set(ERRORS) - QUIET - UNANNOUNCED - {'authorized_nonclinical_test'}
SEVERITY_RANK = {'warning': 1, 'failure': 2}


def severity(condition):
    """The one severity rule: report() and the escalation decision both read this."""
    return ('warning' if condition in WARNINGS else 'healthy' if condition == 'healthy'
            else 'in_progress' if condition in IN_PROGRESS else 'failure')


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


def closed_incident():
    """Every per-incident key, closed. `last_attempt_at` is deliberately NOT here: it outlives
    the incident because the cooldown between incidents is measured from it."""
    return {'incident_id': None, 'incident_attempt': None, 'incident_opened_at': None,
            'incident_attempt_condition': None, 'incident_attempt_notice': None,
            'incident_attempt_count': 0, 'incident_conditions_announced': []}


#: ⚠️ status.json IS FORMAT 1, EXACTLY THESE SIX KEYS, FOREVER. Every release reads it, including
#: the one a rollback restores, and that one refuses any other key set. `incident_attempt` names
#: the incident's LATEST notice; its first notice keeps the incident's own identity, exactly as the
#: previous release names it, and a previous release replays whichever receipt it names.
STATUS_KEYS = ('format', 'last_check_at', 'condition', 'incident_id', 'incident_attempt', 'last_attempt_at')
#: The extension lives in a sidecar the previous release never opens. Named `incident-*` so every
#: release's lost-state guard (status.json missing while incident evidence remains) covers it.
NOTICES_FILE = 'incident-notices.json'
RECORD_KEYS = tuple(closed_incident())

#: ⚠️ FAIL CLOSED MEANS ALERT, NOT SILENCE: the lead's design rule for this monitor, 2026-09-27.
#: A state this release cannot validate or recover must never leave the monitor refusing forever
#: with no email. At most once per RESTART_INTERVAL_SECONDS it sends an operator notice saying it
#: could not read its own state (one of these labels, never any content), what the backup condition
#: is now, and that it has restarted its incident record from now; then it continues from a fresh,
#: valid state. A possible duplicate email is acceptable; permanent silence is not.
UNREADABLE = ('state_missing',            # status.json is absent while incident records remain
              'state_invalid',            # status.json is unsafe, unparseable or malformed
              'ledger_invalid',           # incident-notices.json is unsafe, unparseable or malformed
              'notice_record_missing',    # a notice the state names has no request record
              'notice_record_invalid',    # a notice's request record is unsafe or malformed
              'notice_record_mismatch',   # a request record and the state disagree about a notice
              'incident_record_invalid')  # the incident record breaks its own invariants
RESTART_INTERVAL_SECONDS = 24 * 3600
#: One per restart, reserved before anything is changed. Named so that no release's lost-state
#: guard (`incident-*`) reads it, and nothing but the once-a-day limit ever does.
RESTART_MARKER = re.compile(r'monitor-restart-([a-f0-9]{32})\.json')


class Unreadable(Exception):
    """A monitor state this release cannot validate or recover, and which of UNREADABLE it is."""

    def __init__(self, reason):
        backup.require(reason in UNREADABLE, 'Unknown monitor state failure.')
        super().__init__(reason)
        self.reason = reason


@contextmanager
def unreadable(reason):
    """Any failure inside is this one; a more specific one raised deeper keeps its own label."""
    try:
        yield
    except Unreadable:
        raise
    except Exception:
        raise Unreadable(reason) from None


def no_announcements():
    return {level: None for level in SEVERITY_RANK}


def initial_state():
    return {'format': 1, 'last_check_at': None, 'condition': 'monitoring_stale', 'last_attempt_at': None,
            **closed_incident(), 'announced_at': no_announcements()}


def validate_incident(value):
    """The incident invariants, over a ledger record or the state it is merged into."""
    for key in ('incident_id', 'incident_attempt'):
        backup.require(value[key] is None or isinstance(value[key], str)
                       and re.fullmatch(r'[a-f0-9]{32}', value[key]), 'Invalid incident identity.')
    if value['incident_opened_at'] is not None:
        timestamp(value['incident_opened_at'])
    announced, count = value['incident_conditions_announced'], value['incident_attempt_count']
    backup.require(type(announced) is list and len(set(announced)) == len(announced)
                   and all(isinstance(item, str) and item in ANNOUNCEABLE for item in announced)
                   and type(count) is int and 0 <= count <= 100000 and len(announced) <= count
                   and value['incident_attempt_notice'] in (None, *NOTICES)
                   and value['incident_attempt_condition'] in (None, *announced), 'Invalid incident record.')
    if value['incident_attempt'] is None:
        # No notice yet: nothing announced, and an open incident still knows when it opened.
        backup.require(count == 0 and value['incident_attempt_notice'] is None
                       and value['incident_attempt_condition'] is None
                       and (value['incident_opened_at'] is None) == (value['incident_id'] is None),
                       'Invalid incident record.')
    else:
        backup.require(value['incident_id'] is not None and value['incident_opened_at'] is not None
                       and count >= 1 and value['incident_attempt_condition'] is not None
                       and (value['incident_attempt_notice'] == 'initial') == (count == 1)
                       and (value['incident_attempt_notice'] != 'initial'
                            or value['incident_attempt'] == value['incident_id']),
                       'Invalid incident record.')


def validate_status(value):
    """status.json's own invariants: format 1 and exactly its six keys, as every release reads it."""
    backup.require(type(value) is dict and set(value) == set(STATUS_KEYS)
                   and type(value['format']) is int and value['format'] == 1
                   and value['condition'] in ERRORS
                   and (value['incident_id'] is not None or value['incident_attempt'] is None),
                   'Invalid monitor state.')
    for key in ('last_check_at', 'last_attempt_at'):
        if value[key] is not None:
            timestamp(value[key])
    for key in ('incident_id', 'incident_attempt'):
        backup.require(value[key] is None or isinstance(value[key], str)
                       and re.fullmatch(r'[a-f0-9]{32}', value[key]), 'Invalid incident identity.')


def validate_layer(value):
    """One layer of the ledger: the incident record it describes (None once closed) and its stamps."""
    backup.require(type(value['announced_at']) is dict and set(value['announced_at']) == set(SEVERITY_RANK)
                   and (value['incident'] is None
                        or type(value['incident']) is dict and set(value['incident']) == set(RECORD_KEYS)),
                   'Invalid incident notices.')
    for when in value['announced_at'].values():
        if when is not None:
            timestamp(when)
    if value['incident'] is not None:
        validate_incident(value['incident'])


def layer(state):
    return {'incident': {key: state[key] for key in RECORD_KEYS} if state['incident_id'] else None,
            'announced_at': dict(state['announced_at'])}


def superseded(state):
    """What a notice's ledger write keeps until status.json commits the notice: the exact status.json
    the check began from, and the ledger layer that described it."""
    return copy.deepcopy({'status': {key: state[key] for key in STATUS_KEYS}, **layer(state)})


def read_notices():
    """The sidecar ledger, or None where no release that keeps one has written it yet."""
    path = DIRECTORY / NOTICES_FILE
    if not path.exists() and not path.is_symlink():
        return None
    value = json.loads(backup.read_private(path, 65536))
    backup.require(type(value) is dict and set(value) == {'format', 'incident', 'announced_at', 'committed'}
                   and type(value['format']) is int and value['format'] == 1, 'Invalid incident notices.')
    validate_layer(value)
    committed = value['committed']
    if committed is not None:
        # Only a notice keeps what it superseded, and a notice names its incident and itself.
        backup.require(type(committed) is dict and set(committed) == {'status', 'incident', 'announced_at'}
                       and value['incident'] is not None and value['incident']['incident_attempt'] is not None,
                       'Invalid incident notices.')
        validate_status(committed['status'])
        validate_layer(committed)
    return value


def requested(prefix):
    """Whether any request record exists for this identity: a pending or result file, or either one's
    name taken by anything at all. Existence is the evidence; its content is read elsewhere."""
    return any((DIRECTORY / (prefix + suffix)).exists() or (DIRECTORY / (prefix + suffix)).is_symlink()
               for suffix in ('-pending.json', '-result.json'))


def notice_time(notices):
    """When the ledger's newest notice was made: a notice stamps its own severity with the very
    instant status.json records as its last_attempt_at, and nothing later rewrites the layer that
    still keeps what it superseded."""
    record = notices['incident']
    return notices['announced_at'][severity(record['incident_attempt_condition'])]


def committed_by(notices, status):
    """Whether status.json records the ledger's newest notice: its incident, itself, and its time."""
    record = notices['incident']
    return ((status['incident_id'], status['incident_attempt'], status['last_attempt_at'])
            == (record['incident_id'], record['incident_attempt'], notice_time(notices)))


def layer_in_force(notices, status):
    """⚠️ WHICH LEDGER LAYER DESCRIBES status.json. The ledger may have run ahead of it.

    A notice's first write lands the ledger with the layer it supersedes kept beside it, and only
    then is status.json (the commit point) written. A request only ever begins after both. So the
    newer layer is read only if status.json records THAT notice (its incident, its own identity and
    its time), or its own request record shows it began and status.json has been rewritten since by
    a release that keeps no ledger. Otherwise the notice never began, and the kept layer is read.

    ⚠️ status.json IS NOT REQUIRED TO BE BYTE-FOR-BYTE WHAT THE CRASHED CHECK BEGAN FROM (F1, round
    2). The previous release, run after a rollback, rewrites status.json without opening the ledger:
    its check time and condition on every check, and a first notice or a close of its own. Requiring
    equality dropped the kept layer the moment that happened, and the monitor refused forever.

    ⚠️ AND A REQUEST RECORD UNDER THE SAME NAME IS NOT PROOF THAT THIS NOTICE BEGAN. A first notice
    is named by its incident, and the previous release names its own first notice for the same
    incident the same way; that record announces its own condition at its own time. Only a record
    of this notice (its condition, at its time) says it began.
    """
    committed = notices['committed']
    if committed is None or committed_by(notices, status):
        return notices
    record, when = notices['incident'], notice_time(notices)
    prefix = 'incident-' + record['incident_attempt']
    if requested(prefix):
        with unreadable('notice_record_invalid'):
            began = attempt_record(prefix)
        if (began['condition'], began['attempted_at']) == (record['incident_attempt_condition'], when):
            return notices
    return committed


def read_state():
    """The merged state: status.json, the ledger layer in force, and what a first notice the previous
    release made announced. ⚠️ Raises Unreadable, with its label, for ANY state this release cannot
    validate or recover: check() then restarts the record and says so (FAIL CLOSED MEANS ALERT)."""
    try:
        return merged_state()
    except Unreadable:
        raise
    except Exception:
        raise Unreadable('incident_record_invalid') from None


def merged_state():
    path = DIRECTORY / 'status.json'
    if not path.exists() and not path.is_symlink():
        # Partial recovery may lose mutable state while retaining a durable
        # request record. Do not invent a fresh incident and send again.
        pristine = initial_state()
        evidence = list(DIRECTORY.glob('incident-*'))
        if evidence == [DIRECTORY / NOTICES_FILE]:
            # ...with one exception that is provably no loss: a fresh monitor's very first notice
            # whose ledger landed and whose status.json never did. The ledger kept the pristine
            # state that check began from, and no request record exists (the only file is the ledger).
            with unreadable('ledger_invalid'):
                notices = read_notices()
            if (notices['committed'] is None
                    or notices['committed']['status'] != {key: pristine[key] for key in STATUS_KEYS}):
                raise Unreadable('state_missing')
        elif evidence:
            raise Unreadable('state_missing')
        return pristine
    with unreadable('state_invalid'):
        value = json.loads(backup.read_private(path, 65536))
        validate_status(value)
    with unreadable('ledger_invalid'):
        notices = read_notices() or {'incident': None, 'announced_at': no_announcements(), 'committed': None}
    notices = layer_in_force(notices, value)
    # ⚠️ A STAMP COUNTS ONLY IF status.json RECORDS A REQUEST NO EARLIER THAN IT. Every notice
    # stamps its severity with the very instant status.json then records as last_attempt_at. A
    # stamp later than that (or any stamp before status.json records a request at all) was written
    # by a check that died between the ledger and status.json: no request ever began for it, and a
    # notice nobody received must never hold the one that is owed. It is read as not sent.
    backed = timestamp(value['last_attempt_at']) if value['last_attempt_at'] else None
    announced_at = {level: when if when is not None and backed is not None and timestamp(when) <= backed
                    else None for level, when in notices['announced_at'].items()}
    state = dict(value, **closed_incident(), announced_at=announced_at)
    record = notices['incident']
    if value['incident_id'] is None:
        pass    # A closed incident: any older record describes an incident that is over.
    elif record and (record['incident_id'], record['incident_attempt']) == (value['incident_id'],
                                                                            value['incident_attempt']):
        state.update(record)
    else:
        # status.json names an incident the ledger (the layer in force) does not describe: the
        # previous release opened it or made its first notice. It can only be that shape: at most
        # a first notice, named by the incident itself (anything else fails the invariants below).
        # What that notice announced is read from its own durable record rather than assumed.
        same = record is not None and record['incident_id'] == value['incident_id']
        state.update(incident_id=value['incident_id'],
                     incident_opened_at=record['incident_opened_at'] if same else value['last_check_at'])
        if value['incident_attempt']:
            prefix = 'incident-' + value['incident_attempt']
            with unreadable('notice_record_invalid' if requested(prefix) else 'notice_record_missing'):
                first = attempt_record(prefix)
            state.update(incident_attempt=value['incident_attempt'], incident_attempt_notice='initial',
                         incident_attempt_condition=first['condition'], incident_attempt_count=1,
                         incident_conditions_announced=[first['condition']])
            if not same:
                state['incident_opened_at'] = first['attempted_at']
            level = severity(first['condition'])
            known = state['announced_at'].get(level)
            if level in SEVERITY_RANK and (known is None or timestamp(known) < timestamp(first['attempted_at'])):
                state['announced_at'][level] = first['attempted_at']
    with unreadable('incident_record_invalid'):
        validate_incident(state)
        backup.require(state['incident_attempt'] is None or state['last_attempt_at'] is not None,
                       'Invalid incident record.')
    return state


def named_notice(state):
    """The durable request record of the notice the state names (None if it names none), held to
    what the state says it announced."""
    if not state['incident_attempt']:
        return None
    prefix = 'incident-' + state['incident_attempt']
    with unreadable('notice_record_invalid'):
        exists = requested(prefix)
    with unreadable('notice_record_invalid' if exists else 'notice_record_missing'):
        record = attempt_record(prefix)
    if record['condition'] != state['incident_attempt_condition']:
        raise Unreadable('notice_record_mismatch')
    return record


def restart_held_until(at):
    """When the next restart notice may be sent, if one was sent in the RESTART_INTERVAL before
    `at`; None if it may be sent now.

    A restart counts once a request record for its notice exists: a restart that stopped before its
    request began sent nothing and holds nothing. A marker that cannot be read holds nothing either,
    and a time later than now (a clock that ran fast) is not within the interval: each can cost a
    duplicate at most, never a day of silence more.
    """
    latest = None
    for path in DIRECTORY.glob('monitor-restart-*.json'):
        match = RESTART_MARKER.fullmatch(path.name)
        if not match or not requested('incident-' + match[1]):
            continue
        try:
            marker = json.loads(backup.read_private(path, 4096))
            backup.require(type(marker) is dict and set(marker) == {'format', 'reason', 'reserved_at'}
                           and type(marker['format']) is int and marker['format'] == 1
                           and marker['reason'] in UNREADABLE, 'Invalid restart marker.')
            when = timestamp(marker['reserved_at'])
        except Exception:
            continue
        if 0 <= (at - when).total_seconds() < RESTART_INTERVAL_SECONDS and (latest is None or when > latest):
            latest = when
    return latest + timedelta(seconds=RESTART_INTERVAL_SECONDS) if latest else None


def replace_status(value):
    """status.json replaced atomically WITHOUT reading what it replaces, which may be unreadable."""
    fd, temporary = tempfile.mkstemp(prefix='.status-', dir=DIRECTORY)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, DIRECTORY / 'status.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restart_record(identity, reason, at):
    """⚠️ RESTART THE INCIDENT RECORD FROM NOW, KEEPING EVERYTHING THAT COULD NOT BE READ.

    1. Reserve the restart under its notice's identity (its marker counts once a request exists).
    2. Keep status.json and the ledger for diagnosis under names nothing reads. Hard links, so
       status.json is never missing: the previous release refuses a directory without one.
    3. Replace status.json with the pristine state and drop the ledger's name. Request records are
       immutable evidence and are never touched; nothing names the unreadable ones any more.
    """
    backup.write_private(DIRECTORY / f'monitor-restart-{identity}.json',
                         json.dumps({'format': 1, 'reason': reason, 'reserved_at': at.isoformat()},
                                    sort_keys=True).encode() + b'\n')
    status, ledger = DIRECTORY / 'status.json', DIRECTORY / NOTICES_FILE
    for path in (status, ledger):
        if path.exists() or path.is_symlink():
            kept = DIRECTORY / f'monitor-restart-{identity}-{path.name}'
            try:
                os.link(path, kept, follow_symlinks=False)
            except OSError:
                os.rename(path, kept)             # not linkable (a directory, say): moved instead
    pristine = initial_state()
    replace_status({key: pristine[key] for key in STATUS_KEYS})
    if ledger.exists() or ledger.is_symlink():
        os.unlink(ledger)


def write_state(state, supersedes=None):
    """Two files and one rule: status.json is the commit point, and the ledger describes it.

    While an incident is open the ledger is written FIRST. A write that makes a NOTICE passes what
    it supersedes (the exact status.json the check began from and the ledger layer describing it),
    and the ledger keeps that until the check's next write. So a crash between the two files leaves
    a status.json that does not record the notice (as the check found it, or as a release without
    the ledger has rewritten it since), and read_state reads the kept layer (layer_in_force): the
    notice is discarded, provably unsent, because a request only begins after both writes. Any
    other write in an open incident changes nothing status.json names, so the ledger's
    record still matches it. When the incident is closed status.json goes first, so the ledger's
    older record is inert from the moment it lands. The ledger is created on first need: a monitor
    that has never announced anything has no ledger.

    The state is held to the same invariants on the way OUT as on the way in: an inconsistent
    incident is refused here (and the check fails closed) rather than persisted for the next
    check to trip over, or for a stale key to be silently dropped.
    """
    validate_incident(state)
    backup.require(supersedes is None or state['incident_id'] and state['incident_attempt'],
                   'Only a notice supersedes a ledger layer.')
    status = {key: state[key] for key in STATUS_KEYS}
    ledger = DIRECTORY / NOTICES_FILE
    notices = {'format': 1, **layer(state), 'committed': supersedes}
    if state['incident_id']:
        scheduled.atomic_status(ledger, notices)
        scheduled.atomic_status(DIRECTORY / 'status.json', status)
    else:
        scheduled.atomic_status(DIRECTORY / 'status.json', status)
        if ledger.exists() or ledger.is_symlink() or any(state['announced_at'].values()):
            scheduled.atomic_status(ledger, notices)


#: ⚠️ status() holds the monitor lock SHARED while it reads the state files, for milliseconds. A
#: check that meets such a reader waits this long rather than refusing as though it met a parallel
#: check: the publisher's status() and this check run on independent five-minute timers, and a
#: reader must never turn a tick into monitoring_state_unavailable. A parallel CHECK holds the lock
#: for its whole run and is still refused once this bound passes.
LOCK_WAIT_SECONDS = 2
#: How long status() waits for a running check to finish writing before it reads.
READ_WAIT_SECONDS = 30


def hold(fd, operation, seconds):
    deadline = time.monotonic() + seconds
    while True:
        try:
            fcntl.flock(fd, operation | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def lock_file(fd):
    info = os.fstat(fd)
    backup.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                   and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
                   'Invalid monitor lock.')


@contextmanager
def locked():
    backup.private_dir(DIRECTORY)
    fd = os.open(DIRECTORY / 'monitor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        lock_file(fd)
        hold(fd, fcntl.LOCK_EX, LOCK_WAIT_SECONDS)
        yield
    finally:
        os.close(fd)


@contextmanager
def reading():
    """A consistent read of what check() writes: the same lock, held SHARED.

    ⚠️ OPENED READ-ONLY AND NEVER CREATED. The publisher calls status() from a unit whose
    ProtectSystem=strict sandbox grants no write to this directory, so an O_CREAT or O_RDWR open
    here would fail there on every tick. flock needs no write access. With no lock file no check
    has ever run in this directory, so there is no writer to be consistent with.
    """
    try:
        fd = os.open(DIRECTORY / 'monitor.lock', os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        fd = None
    try:
        if fd is not None:
            lock_file(fd)
            hold(fd, fcntl.LOCK_SH, READ_WAIT_SECONDS)
        yield
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def configured_transport(values):
    # Operations run outside Django's application initialization, with the
    # established transport only. Explicit minimal settings exclude app secrets.
    from django.conf import settings
    from django.test.utils import override_settings
    if not settings.configured:
        settings.configure(DEFAULT_CHARSET='utf-8')
    # Once per process: an unconditional insert grew sys.path by one entry per check in any
    # long-lived process, and a spawned child inherits the whole list.
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
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


def duration(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 3600} hours {seconds % 3600 // 60} minutes'


def notice_message(condition, at, prefix, *, test=False, notice='initial', incident=None):
    """Subject and body. Fixed vocabulary, timestamps and a random reference only: no secret,
    provider response or patient information can reach either."""
    footer = ('\n\nNo patient information or credentials are included. '
              'This message confirms neither offsite recovery nor outside-host monitoring.\n')
    lines = f'UTC check: {at.isoformat()}\nReference: {prefix}\n' + ERRORS[condition] + footer
    header = 'QuillMD private synthetic environment: operational backup notification.\n'
    if not test and incident and incident.get('restart'):
        # FAIL CLOSED MEANS ALERT. The reason is a fixed label: nothing read from the state reaches here.
        backup.require(incident['restart'] in UNREADABLE and notice == 'initial', 'Unknown restart notice.')
        return ('[QuillMD operations] MONITOR RESTARTED: the backup monitor could not read its own state',
                header + 'MONITOR RESTARTED: the backup monitor could not read its own incident state '
                + f'(reason: {incident["restart"]}), so it has restarted its incident record from this check. '
                + 'Notices sent before this one are not carried forward, so this may repeat one you already '
                + 'hold. The unreadable files are kept beside the new record for diagnosis.\n'
                + f'Condition: {condition}\nSeverity: {severity(condition)}\n' + lines)
    if test or notice == 'initial':
        subject = ('[QuillMD operations] ESCALATION: a more severe backup incident opened'
                   if incident and incident.get('lifted_over') else
                   '[QuillMD NONCLINICAL TEST] Simulated backup failure' if test
                   else '[QuillMD operations] Backup recovery requires attention')
        lifted = ''
        if incident and incident.get('lifted_over'):
            earlier = {rank: level for level, rank in SEVERITY_RANK.items()}[incident['lifted_over']]
            lifted = (f'ESCALATION: a new incident, sent inside the 24-hour interval between incidents because '
                      f'it is more severe ({severity(condition)}) than every notice in the last 24 hours '
                      f'(highest: {earlier}).\n')
        return subject, (header + ('AUTHORIZED SIMULATED FAILURE; NO BACKUP WAS INTERRUPTED.\n' if test else '')
                         + lifted + f'Condition: {condition}\n' + lines)
    opened = timestamp(incident['opened_at'])
    open_for = (f'Incident open for at least {duration((at - opened).total_seconds())}, '
                f'open since no later than {opened.isoformat()}. This is notice {incident["count"]} for this incident.\n')
    if notice == 'escalation':
        previous = incident['previous']
        movement = SEVERITY_RANK[severity(condition)] - SEVERITY_RANK[severity(previous)]
        return ('[QuillMD operations] ESCALATION: backup recovery condition changed',
                header + 'ESCALATION: an open incident changed condition since its last notice.\n'
                + f'Condition: {condition}\nSeverity: {severity(condition)} '
                + f'(last notice announced {previous}, {severity(previous)}; severity '
                + ('increased' if movement > 0 else 'unchanged' if movement == 0 else 'decreased') + ')\n'
                + open_for + lines)
    backup.require(notice == 'reminder', 'Unknown notice.')
    return ('[QuillMD operations] REMINDER: backup recovery incident still open',
            header + 'REMINDER: this incident is still open; no healthy check has closed it.\n'
            + f'Condition: {condition}\nSeverity: {severity(condition)}\n' + open_for + lines)


def attempt_alert(values, condition, identity, at, *, test=False, notice='initial', incident=None):
    prefix = 'test-' + TEST_AUTHORIZATION if test else 'incident-' + identity
    pending = DIRECTORY / (prefix + '-pending.json')
    result_path = DIRECTORY / (prefix + '-result.json')
    # Exclusive create BEFORE the request prevents a crash/restart or parallel
    # command from sending an uncertain attempt again. Existing evidence stays.
    # A result is independent evidence of a request even when a damaged or
    # incomplete recovery lost its pending marker. Never send before inspecting
    # either artifact; malformed/unsafe artifacts also suppress a new request.
    if requested(prefix):
        return receipt(prefix)
    record = {'format': 1, 'kind': 'authorized_test' if test else 'operational',
              'condition': condition, 'attempted_at': at.isoformat(), 'outcome': 'pending',
              'provider_message_id': None, 'provider_accepted': False,
              'delivery_confirmed': False, 'inbox_receipt_confirmed': False}
    # Composed before the reservation and without I/O: a message that cannot be composed raises
    # here, leaves no request record, and the already-persisted identity then fails closed.
    subject, body = notice_message(condition, at, prefix, test=test, notice=notice, incident=incident)
    backup.write_private(pending, json.dumps(record, sort_keys=True).encode() + b'\n')
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
    return public_receipt(attempt_record(prefix))


def public_receipt(value):
    # Return a fixed set, never unexpected fields supplied by a malformed file.
    return {key: value[key] for key in ('outcome', 'provider_message_id', 'provider_accepted',
                                      'delivery_confirmed', 'inbox_receipt_confirmed')}


def attempt_record(prefix):
    """The validated durable record of one attempt, including what it announced and when."""
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
    return value


def report(condition, *, checked_at=None, alert=None, recovery=None, local_capture=None, external=None,
           incident=None):
    return {'format': 1, 'condition': condition, 'action': ERRORS[condition],
            'checked_at': checked_at, 'healthy': condition in {'healthy', 'backup_in_progress', 'offsite_in_progress'},
            'severity': severity(condition),
            'alert': alert, 'offsite_recovery_verified': bool(recovery and recovery.get('last_isolated_restore')),
            'local_capture': local_capture, 'offsite': recovery,
            'external_monitor': external, 'incident': incident,
            'outside_host_failure_detection': False, 'clinical_content_included': False}


def incident_summary(state, at, *, latest_confirmed, deferred_until=None):
    """Nonsecret incident facts for the operator: no identity, provider data or content."""
    if not state['incident_id']:
        return None
    reminder = None
    if state['incident_attempt'] and latest_confirmed:
        reminder = (timestamp(state['last_attempt_at']) + timedelta(seconds=REMINDER_SECONDS)).isoformat()
    return {'opened_at': state['incident_opened_at'],
            'open_seconds': int((at - timestamp(state['incident_opened_at'])).total_seconds()),
            'notices_attempted': state['incident_attempt_count'],
            'last_notice': state['incident_attempt_notice'],
            'last_notice_condition': state['incident_attempt_condition'],
            'conditions_announced': list(state['incident_conditions_announced']),
            'next_reminder_at': reminder,
            'escalation_deferred_until': deferred_until.isoformat() if deferred_until else None}


def recent_severity_rank(state, at):
    """The highest severity announced in the COOLDOWN_SECONDS before `at`, across incidents.

    ⚠️ A notice status.json records that the ledger does not (the previous release made it, or the
    ledger was new) counts as a FAILURE: an unknown notice can hold the cooldown, never lift it.
    The converse never reaches here: a stamp the ledger holds that status.json records no request
    for was dropped by read_state, because a notice nobody received must hold nothing.
    """
    def recent(when):
        return when is not None and (at - timestamp(when)).total_seconds() < COOLDOWN_SECONDS
    rank = max([SEVERITY_RANK[level] for level, when in state['announced_at'].items() if recent(when)], default=0)
    if recent(state['last_attempt_at']) and state['last_attempt_at'] not in state['announced_at'].values():
        rank = SEVERITY_RANK['failure']
    return rank


def not_after(state, at):
    """⚠️ A RECORDED TIME LATER THAN NOW IS READ AS NOW, AND KEPT THAT WAY.

    A clock that ran fast and was then corrected leaves notice, stamp and opening times in the
    future. Measured as they stand, the reminder, the escalation spacing and the interval between
    incidents would each wait out the whole error (three days fast: a reminder after four), and an
    incident would report a negative age. Each such time becomes the moment it is first seen in the
    future, and check() persists that, so every interval restarts from the correction rather than
    from a time that has not happened. It can only bring a notice forward, never hold one back.
    """
    def clamp(value):
        return at.isoformat() if value is not None and timestamp(value) > at else value
    state.update(last_attempt_at=clamp(state['last_attempt_at']),
                 incident_opened_at=clamp(state['incident_opened_at']),
                 announced_at={level: clamp(when) for level, when in state['announced_at'].items()})
    return state


#: The conditions check() plans a notice for. `alert_configuration_unavailable` is recorded only by
#: the check that could not read its configuration, and that check returns before planning.
PLANNED = ANNOUNCEABLE - {'alert_configuration_unavailable'}


def plan_notice(state, condition, at):
    """What an open incident whose latest notice was ACCEPTED owes now: (notice, deferred_until).

    1. A condition MORE SEVERE than the incident's LAST notice is announced at once, announced
       before or not. The operator's newest email is the one they act on: a failure that returns
       after a notice said the severity decreased must not stand on "decreased" until a reminder.
    2. Any other condition the incident has not announced waits ESCALATION_SPACING_SECONDS
       after the last notice.
    3. Anything else, the reminder, REMINDER_SECONDS after the last notice.

    ⚠️ WHY (1) CANNOT LOOP. It compares with the LAST notice, so once that notice is the failure,
    flapping between conditions already announced sends nothing until the reminder. A rise needs a
    notice at a lower severity first, and such a notice is itself bounded: either a newly announced
    condition, an hour after the previous notice and once per condition, or the daily reminder.
    """
    last = timestamp(state['last_attempt_at'])
    elapsed = (at - last).total_seconds()
    if SEVERITY_RANK[severity(condition)] > SEVERITY_RANK[severity(state['incident_attempt_condition'])]:
        return 'escalation', None
    if condition not in state['incident_conditions_announced']:
        if elapsed >= ESCALATION_SPACING_SECONDS:
            return 'escalation', None
        return None, last + timedelta(seconds=ESCALATION_SPACING_SECONDS)
    if elapsed >= REMINDER_SECONDS:
        return 'reminder', None
    return None, None


def _record_recovery_failure(error):
    """Durable, bounded, non-clinical. It must never raise: a recorder that can fail the caller
    reintroduces the very problem the `except` above exists to avoid."""
    try:
        record = {'at_utc': now().isoformat(), 'event': 'publication_recovery_failed',
                  'error_class': type(error).__name__,
                  'errno': getattr(error, 'errno', None),
                  # The message, not the traceback, and bounded: this is an operations ledger,
                  # not a crash dump, and an unbounded string is how a ledger becomes unreadable.
                  'detail': str(error)[:300]}
        DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(DIRECTORY / 'recovery-failures.jsonl', 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, sort_keys=True) + '\n')
        os.chmod(DIRECTORY / 'recovery-failures.jsonl', 0o600)
    except Exception:
        # Nothing further is available, and raising here would defeat the whole point.
        pass


def check(at=None):
    at = at or now()
    # ⚠️ THE INDEPENDENT RECOVERY PATH, AND IT LIVES HERE FOR A REASON. An activation pauses the
    # publisher timer and restores it in a `finally` — but a `finally` does not run after SIGKILL
    # or a host failure, and a paused publisher cannot recover itself because it is not running.
    # This check runs on its OWN five-minute timer, which keeps ticking throughout, so it is the
    # one thing positioned to pay that debt. It is a no-op unless a pause is actually owed, and it
    # refuses while an activation still holds exclusion, so it can never interrupt a live act.
    try:
        #: ⚠️ THE SIBLING IMPORT FORM, BECAUSE THIS FILE IS RUN AS A SCRIPT, NOT AS A PACKAGE.
        #: Its unit is `python -B /opt/meddoc-pro/rebuild/ops/backup_alerts.py check`, which puts
        #: `rebuild/ops` on `sys.path` and NOT `rebuild` — so `from ops import …` raises
        #: ModuleNotFoundError every tick. It shipped that way in `52b28b36`, inside the bare
        #: `except: pass`, so the independent recovery hook was INERT from the moment it landed
        #: and said nothing about it. The recorder added below is what surfaced it, on its first
        #: two ticks, in production. Every other sibling in this file already uses this form
        #: (see `scheduled_backup`, line 22) — this one line did not.
        try:
            from . import activation_exclusion as _exclusion
        except ImportError:
            import activation_exclusion as _exclusion
        _exclusion.recover_publication()
    except Exception as error:
        # Recovery is best-effort and must never turn the alert check itself into a failure:
        # a monitor that dies trying to fix something monitors nothing.
        #
        # ⚠️ BUT BEST-EFFORT IS NOT SILENT, AND THIS `except` IS DISABLED FOR EXACTLY THE CASE
        # IT EXISTS TO HANDLE. On 2026-09-22 the shipped exclusion lock sat on a path this unit's
        # `ProtectSystem=strict` sandbox makes read-only, so any `_open_lock()` here raises EROFS
        # and the bare `pass` would swallow it.
        #
        # ⚠️ STATED PRECISELY, BECAUSE THE FIRST VERSION OF THIS COMMENT OVERCLAIMED: it did NOT
        # fire during that outage. `recover_publication()` returns at `pause_owed()` before it
        # ever opens the lock, and no pause was owed — so the swallow was never reached. What was
        # broken is the path that pays a pause DEBT, which is the one thing this hook is for: the
        # day an activation dies mid-act, recovery would fail here and say nothing.
        #
        # ⚠️ AND THE RECORD CANNOT GO TO THE DEFERRAL LEDGER, BECAUSE THAT LEDGER IS THE THING
        # THAT MAY BE UNWRITABLE. A failure record written to the path whose unwritability IS
        # the failure is not a record. It goes in OUR OWN directory, which is this unit's
        # `ReadWritePaths` grant and is therefore writable exactly when recovery is not.
        _record_recovery_failure(error)
    try:
        with locked():
            # ⚠️ FAIL CLOSED MEANS ALERT. A state this release cannot validate or recover is not a
            # reason to refuse for ever: it is restarted, and the restart is announced (at most once
            # a day). Until the notice is actually sent, nothing about the unreadable state changes.
            try:
                state = read_state()
                latest = named_notice(state)
                unreadable_state = None
            except Unreadable as failure:
                state, latest, unreadable_state = initial_state(), None, failure.reason
            began = superseded(state)
            not_after(state, at)
            try:
                values = read_configuration()
            except Exception:
                if unreadable_state:
                    # Nothing can be sent, so nothing is restarted: the state stays exactly as found.
                    return state_unavailable(unreadable_state, at), 1
                state.update(last_check_at=at.isoformat(), condition='alert_configuration_unavailable')
                write_state(state)
                return report(state['condition'], checked_at=state['last_check_at']), 1
            restart = None
            if unreadable_state:
                held_until = restart_held_until(at)
                if held_until:
                    # One restart notice a day: inside that day, refuse (and say why) without a change.
                    return state_unavailable(unreadable_state, at, held_until=held_until), 1
                restart = secrets.token_hex(16)
            condition = backup_condition(at)
            recovery = recovery_status(at)
            local_capture = local_capture_status(at)
            if condition == 'healthy':
                condition = recovery['condition']
            external = external_heartbeat(at, healthy=condition == 'healthy' or condition in WARNINGS, execute=True)
            if (condition == 'healthy' or condition in WARNINGS) and external['outcome'] in {'configuration_or_state_invalid', 'pending', 'uncertain_no_retry'}:
                condition = 'external_monitor_unconfirmed'
            if restart:
                restart_record(restart, unreadable_state, at)
            state.update(last_check_at=at.isoformat(), condition=condition)
            alert = deferred_until = None
            lifted = False
            if condition in QUIET:
                state.update(closed_incident())
            elif condition not in UNANNOUNCED:
                if not state['incident_id']:
                    # A restart's incident is named by the restart, so its notice is the incident's first.
                    state.update(incident_id=restart or secrets.token_hex(16), incident_opened_at=at.isoformat())
                notice = None
                if state['incident_attempt']:
                    alert = public_receipt(latest)
                    # ⚠️ NEVER FOLLOW AN UNCONFIRMED NOTICE. A pending or uncertain request keeps
                    # the incident at alert_delivery_unconfirmed for operator review; a later
                    # accepted reminder must not replace that receipt and read as confirmation.
                    if alert['outcome'] == 'provider_accepted':
                        notice, deferred_until = plan_notice(state, condition, at)
                elif (state['last_attempt_at'] is None or
                      (at - timestamp(state['last_attempt_at'])).total_seconds() >= COOLDOWN_SECONDS):
                    notice = 'initial'
                elif SEVERITY_RANK[severity(condition)] > recent_severity_rank(state, at):
                    # A NEW incident more severe than everything announced in the last 24 hours is
                    # not held by the cooldown between incidents. Only a strict increase lifts it,
                    # so flapping at the same or a lower severity still sends nothing extra.
                    notice, lifted = 'initial', True
                else:
                    alert = {'outcome': 'cooldown_suppressed', 'provider_accepted': False}
                if notice:
                    announced = state['incident_conditions_announced']
                    context = {'opened_at': state['incident_opened_at'], 'previous': state['incident_attempt_condition'],
                               'count': state['incident_attempt_count'] + 1,
                               'lifted_over': recent_severity_rank(state, at) if lifted else None,
                               'restart': unreadable_state if restart else None}
                    # The first notice keeps the incident's identity (the receipt name every release uses);
                    # every later notice is a new request with its own identity and receipt.
                    identity = state['incident_id'] if notice == 'initial' else secrets.token_hex(16)
                    state.update(incident_attempt=identity, last_attempt_at=at.isoformat(),
                                 incident_attempt_condition=condition, incident_attempt_notice=notice,
                                 incident_attempt_count=context['count'],
                                 incident_conditions_announced=(announced if condition in announced
                                                                else announced + [condition]))
                    state['announced_at'][severity(condition)] = at.isoformat()
                    # Persist the identity before sending: a crash between state and pending receipt
                    # leaves a notice with no request record, which the next check restarts from and
                    # announces. A crash between the ledger and status.json leaves `began` to be read.
                    write_state(state, supersedes=began)
                    alert = attempt_alert(values, condition, identity, at, notice=notice, incident=context)
            if restart and state['incident_attempt'] != restart:
                # Nothing to announce as an incident (healthy, or in progress): the restart is still
                # announced, on its own. Sent before the record is written, which already reads fresh.
                alert = attempt_alert(values, condition, restart, at, incident={'restart': unreadable_state})
            write_state(state)
            incident = incident_summary(state, at, deferred_until=deferred_until,
                                        latest_confirmed=bool(alert and alert['outcome'] == 'provider_accepted'))
            if alert and alert['outcome'] in {'pending', 'uncertain_no_retry'}:
                result = report('alert_delivery_unconfirmed', checked_at=state['last_check_at'], alert=alert,
                                recovery=recovery, local_capture=local_capture, external=external,
                                incident=incident)
            else:
                result = report(condition, checked_at=state['last_check_at'], alert=alert,
                                recovery=recovery, local_capture=local_capture, external=external,
                                incident=incident)
            if restart:
                result.update(state_unreadable=unreadable_state, state_restarted=True)
                return result, 1
            if result['condition'] == 'alert_delivery_unconfirmed':
                return result, 1
            return result, 0 if result['healthy'] or condition in WARNINGS | {'offsite_renewal_in_progress'} else 1
    except Exception:
        return report('monitoring_state_unavailable'), 1


def state_unavailable(reason, at, *, held_until=None):
    """The report of a check that could not read its state and did not restart it: why (a label),
    and when the next restart notice may be sent (None where nothing can be sent at all)."""
    result = report('monitoring_state_unavailable', checked_at=at.isoformat())
    result.update(state_unreadable=reason, state_restarted=False,
                  next_state_notice_at=held_until.isoformat() if held_until else None)
    return result


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
        with reading():
            state = read_state()
            latest = named_notice(state)
        alert = public_receipt(latest) if latest else None
        try:
            read_configuration()
        except Exception:
            return report('alert_configuration_unavailable', checked_at=state['last_check_at']), 1
        age = (at - timestamp(state['last_check_at'])).total_seconds() if state['last_check_at'] else None
        condition = 'monitoring_stale' if age is None or not 0 <= age <= STALE_SECONDS else state['condition']
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
        # The escalation the last check deferred, if any: the same rule over the same persisted
        # inputs at the same moment, so status() and check() cannot disagree about it.
        deferred_until = None
        if (state['incident_attempt'] and alert and alert['outcome'] == 'provider_accepted'
                and state['condition'] in PLANNED and state['last_check_at']):
            deferred_until = plan_notice(state, state['condition'], timestamp(state['last_check_at']))[1]
        not_after(state, at)
        incident = incident_summary(state, at, deferred_until=deferred_until,
                                    latest_confirmed=bool(alert and alert['provider_accepted']))
        result = report(condition, checked_at=state['last_check_at'], alert=alert,
                        recovery=recovery, local_capture=local_capture_status(at), external=external,
                        incident=incident)
        result.update(monitor_age_seconds=int(age) if age is not None else None,
                      stale_after_seconds=STALE_SECONDS)
        return result, 0 if result['healthy'] or condition in WARNINGS | {'offsite_renewal_in_progress'} else 1
    except Unreadable as failure:
        # Read-only: the next check restarts the record and announces it (FAIL CLOSED MEANS ALERT).
        result = report('monitoring_state_unavailable')
        result['state_unreadable'] = failure.reason
        return result, 1
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
