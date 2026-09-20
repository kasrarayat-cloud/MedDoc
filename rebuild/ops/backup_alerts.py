#!/usr/bin/env python3
"""Private, nonclinical recovery-stage alerts. No database access or backup mutation."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
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
RECIPIENT = 'kasra.rayat@gmail.com'
TEST_AUTHORIZATION = '20260920-operation-recovery'
STALE_SECONDS = 15 * 60
COOLDOWN_SECONDS = 24 * 3600
BACKUP_TIMEOUT_SECONDS = 600
OFFSITE_STALE_SECONDS = 30 * 3600
OFFSITE_TIMEOUT_SECONDS = 1200
ERRORS = {
    'healthy': 'Local capture and offsite completion/readback are current. Isolated-restore and recovery-key custody evidence are reported separately.',
    'backup_in_progress': 'A bounded backup is running; the next monitor check will recheck completion.',
    'backup_failed': 'Inspect scheduled_backup.py status and the private backup-monitor attempt record; repair before retrying capture.',
    'backup_stale': 'Inspect the backup timer and last successful capture; restore the daily schedule and run a verified capture.',
    'backup_status_unavailable': 'Inspect private backup-monitor permissions and status records; do not treat missing evidence as success.',
    'backup_schedule_unavailable': 'Inspect quillmd-fresh-backup.timer and quillmd-fresh-backup.service; restore the approved schedule.',
    'backup_timeout': 'Inspect quillmd-fresh-backup.service; a running capture exceeded its approved bound.',
    'offsite_in_progress': 'A bounded encrypted upload is running; retain the previous complete set until verified completion.',
    'offsite_status_unavailable': 'Inspect private automatic-offsite status and immutable attempt evidence; missing or malformed evidence does not prove a recoverable remote backup.',
    'offsite_policy_unavailable': 'Install or renew the protected, approved storage, download and request envelope; keep recurrence disabled until all limits are established.',
    'offsite_capacity_refused': 'The approved storage or request allowance is exhausted. Preserve existing versions; obtain a reviewed capacity or retention decision before another upload.',
    'offsite_upload_failed': 'Inspect the redacted automatic-offsite attempt record and authenticated completion manifest; retry through the bounded service after diagnosis, never count a partial upload as complete.',
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
            return 'healthy'
        if state.get('latest_outcome') == 'failed':
            return 'backup_failed'
        if state.get('latest_outcome') == 'complete':
            return 'backup_stale'
        return 'backup_status_unavailable'
    except Exception:
        return 'backup_status_unavailable'


def offsite_systemd_state():
    result = {}
    for field, operation, expected in (('active', 'is-active', b'active'),
                                       ('enabled', 'is-enabled', b'enabled')):
        child = subprocess.run(['systemctl', operation, 'quillmd-fresh-offsite.timer'],
                               capture_output=True, timeout=5,
                               env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        result[field] = child.returncode == 0 and child.stdout.strip() == expected
    return result


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


def recovery_status(at):
    """No provider request: completion, readback and restore stay separate claims."""
    result = {'condition': 'offsite_status_unavailable', 'last_remote_complete': None,
              'last_verified_readback': None, 'last_isolated_restore': None,
              'recurrence_active': False, 'recurrence_enabled': False,
              'independent_key_custody_verified': False}
    try:
        backup.private_dir(OFFSITE_DIRECTORY)
        value = json.loads(backup.read_private(OFFSITE_DIRECTORY / 'status.json', 65536))
        backup.require(isinstance(value, dict) and type(value.get('version')) is int
                       and value['version'] == 1, 'Invalid automatic-offsite status.')
        for key, kind in (('last_remote_complete', 'remote'), ('last_verified_readback', 'readback'),
                          ('last_isolated_restore', 'restore')):
            result[key] = safe_stage(value.get(key), kind, at)
        # Custody is a separate owner/off-host gate. A local restore cannot establish it.
        result['independent_key_custody_verified'] = (
            bool(result['last_isolated_restore'])
            and result['last_isolated_restore']['source'] == 'independently_retrieved_key')
        unit = offsite_systemd_state()
        result.update(recurrence_active=unit['active'], recurrence_enabled=unit['enabled'])
        reasons = {
            'policy_missing': 'offsite_policy_unavailable', 'policy_invalid': 'offsite_policy_unavailable',
            'policy_expired': 'offsite_policy_unavailable', 'capacity_refused': 'offsite_capacity_refused',
            'budget_exhausted': 'offsite_capacity_refused', 'remote_corrupt': 'offsite_integrity_failed',
            'remote_uncertain': 'offsite_integrity_failed',
            'local_authentication_failed': 'offsite_decryption_failed',
            'transport_failed': 'offsite_upload_failed', 'deadline': 'offsite_timeout',
            'lock_busy': 'offsite_upload_failed',
            'local_backup_stale': 'backup_stale', 'scope_refused': 'offsite_policy_unavailable',
            'state_invalid': 'offsite_status_unavailable',
            'pending_configuration': 'offsite_pending_configuration',
        }
        state, reason = latest_offsite_outcome(value, at, reasons)
        backup.require(state in {'pending_configuration', 'running', 'complete', 'failed', 'refused'}
                       and reason in set(reasons) | {None}, 'Invalid automatic-offsite outcome.')
        backup.require(state not in {'running', 'complete'} or reason is None,
                       'Contradictory automatic-offsite outcome.')
        if state == 'pending_configuration':
            backup.require(not unit['enabled'] and not unit['active'], 'Pending state with active recurrence.')
            condition = 'offsite_pending_configuration'
        elif state in {'failed', 'refused'}:
            backup.require(reason is not None, 'Missing offsite failure reason.')
            condition = reasons[reason]
        elif state == 'running':
            age = (at - timestamp(value['started_at'])).total_seconds()
            condition = 'offsite_in_progress' if 0 <= age <= OFFSITE_TIMEOUT_SECONDS else 'offsite_timeout'
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
        result['condition'] = condition
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
        return {'last_success_run_id': run_id, 'last_success_at': succeeded,
                'age_seconds': int(age), 'stale': age > scheduled.MAX_AGE_SECONDS}
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


def report(condition, *, checked_at=None, alert=None, recovery=None, local_capture=None):
    return {'format': 1, 'condition': condition, 'action': ERRORS[condition],
            'checked_at': checked_at, 'healthy': condition in {'healthy', 'backup_in_progress', 'offsite_in_progress'},
            'alert': alert, 'offsite_recovery_verified': bool(recovery and recovery.get('last_isolated_restore')),
            'local_capture': local_capture, 'offsite': recovery,
            'outside_host_failure_detection': False, 'clinical_content_included': False}


def check(at=None):
    at = at or now()
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
            state.update(last_check_at=at.isoformat(), condition=condition)
            alert = None
            if condition == 'healthy':
                state.update(incident_id=None, incident_attempt=None)
            elif condition not in {'backup_in_progress', 'offsite_in_progress', 'offsite_pending_configuration'}:
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
                              recovery=recovery, local_capture=local_capture), 1
            result = report(condition, checked_at=state['last_check_at'], alert=alert,
                            recovery=recovery, local_capture=local_capture)
            return result, 0 if result['healthy'] else 1
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
        if condition in {'healthy', 'offsite_in_progress', 'offsite_pending_configuration'}:
            condition = recovery['condition']
        result = report(condition, checked_at=state['last_check_at'], alert=alert,
                        recovery=recovery, local_capture=local_capture_status(at))
        result.update(monitor_age_seconds=int(age) if age is not None else None,
                      stale_after_seconds=STALE_SECONDS)
        return result, 0 if result['healthy'] else 1
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
