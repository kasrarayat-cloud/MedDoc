#!/usr/bin/env python3
"""Scoped installation of offsite units; activation requires a fresh capacity policy and verified service run."""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess

try:
    from . import install_backup_schedule as base
except ImportError:
    import install_backup_schedule as base

INSTALLER = 'rebuild/ops/install_offsite_schedule.py'
DECLARATION = 'docs/foundation/mutations/20260920-quillmd-offsite-activation.md'
SERVICE = 'quillmd-fresh-offsite.service'
TIMER = 'quillmd-fresh-offsite.timer'
CONFIG = base.APP / '.runtime/backup-secrets/b2-offsite.json'
RESUME_COMMIT = '53571ce789426590c65939e8f6dc925176dcd4fa'
RESUME_FAILURE = 'offsite-units-activate-20260920T212053Z-331be21a-result.json'
RESUME_FAILURE_SHA256 = '50c80ff8b454d66612597fd20fffad27ece47dcff80e8177c94e6328c196e752'
RESUME_BASELINE = 'offsite-units-activate-20260920T212053Z-331be21a-before.json'
RESUME_BASELINE_SHA256 = '87dd5383cf50030b225c8299e5cd68023878aed6dab0c6f1d11ebcd53c760e4c'
RESUME_CONTEXT = 'timer-resume-context.json'
RESUME_CONTEXT_SHA256 = '473d642d91b9309a64cd919f53dcd887abcdf7fbfd0a0c3af020b268ff0588ed'


def eligibility():
    """The actual service identity validates the protected policy; no provider requests."""
    raw = base.command(['/usr/sbin/runuser', '-u', 'claude', '--',
                        str(base.APP / '.venv/bin/python'), '-B',
                        str(base.APP / 'ops/automatic_offsite.py'), 'inspect'])
    result = json.loads(raw)
    base.require(result.get('eligible') is True and result.get('provider_calls') == 0,
                 'Current approved operating envelope required before activation.')
    return {k: result[k] for k in ('policy_expires_at', 'scope_ceiling_bytes',
                                  'daily_download_budget_bytes', 'daily_request_budget')}


def first_run_coverage(limits, *, actual=False, at=None):
    """The reviewed daily calendar and its entire bounded run must fit the evidence.

    An inactive timer has no NextElapseUSecRealtime. Check the exact reviewed
    calendar before any provider work, then recheck systemd's actual schedule.
    """
    at = at or datetime.now(timezone.utc)
    base.require(at.tzinfo is not None, 'UTC-aware activation time required.')
    at = at.astimezone(timezone.utc)
    calendar = (base.APP / 'deploy' / TIMER).read_text().splitlines()
    base.require([line for line in calendar if line.startswith('OnCalendar=')]
                 == ['OnCalendar=*-*-* 05:00:00 UTC']
                 and 'RandomizedDelaySec=0' in calendar and 'Persistent=true' in calendar,
                 'Only the reviewed daily UTC calendar is supported.')
    expected = at.replace(hour=5, minute=0, second=0, microsecond=0)
    if expected <= at:
        expected += timedelta(days=1)
    scheduled = expected
    if actual:
        raw = base.command(['/usr/bin/env', 'TZ=UTC', 'systemctl', 'show', TIMER,
                            '--property=NextElapseUSecRealtime', '--value']).decode().strip()
        # strptime lazily imports _strptime, unavailable after the pinned helper
        # chroots into the host. The expected instant is already known; require
        # systemd's exact UTC rendering instead of parsing another datetime.
        base.require(raw == expected.strftime('%a %Y-%m-%d %H:%M:%S UTC'),
                     'Actual offsite timer differs from the reviewed next run.')
    expires = datetime.fromisoformat(limits['policy_expires_at'])
    # Timer accuracy defaults to one minute; allow it as well as the 900-second job.
    deadline = scheduled + timedelta(seconds=960)
    base.require(expires.tzinfo is not None and at < scheduled and deadline < expires,
                 'Policy must remain valid through the first scheduled run and timer accuracy window.')
    return {'next_run_at': scheduled.isoformat(), 'latest_completion_at': deadline.isoformat(),
            'policy_expires_at': expires.isoformat(), 'actual_systemd_schedule': actual}


def service_identity():
    properties = {'User': 'claude', 'Group': 'claude', 'WorkingDirectory': str(base.APP),
                  'KillMode': 'control-group', 'NoNewPrivileges': 'yes', 'ProtectSystem': 'strict',
                  'PrivateTmp': 'yes', 'MemoryMax': '1073741824', 'MemorySwapMax': '0',
                  'TimeoutStartUSec': '16min', 'Environment': '', 'EnvironmentFiles': '',
                  'ReadWritePaths': str(base.MONITOR)}
    raw = base.command(['systemctl', 'show', SERVICE, '--all',
                        '--property=' + ','.join(properties)]).decode()
    actual = dict(line.split('=', 1) for line in raw.splitlines())
    # This systemd omits EnvironmentFiles when the unit has none, even with --all.
    actual.setdefault('EnvironmentFiles', '')
    base.require(actual == properties, 'Effective offsite service identity or containment differs.')
    return actual


def adoption_receipt(commit):
    return base.MONITOR / ('installation-' + commit + '.json')


def installation_receipt(commit, hashes, *, adopt=False):
    """Preserve the original receipt; adoption can change source revision, never units."""
    path = base.MONITOR / 'installation.json' if adopt else adoption_receipt(commit)
    if not adopt and not path.exists() and not path.is_symlink():
        path = base.MONITOR / 'installation.json'
    receipt = base.read_private(path)
    base.require(path.stat().st_nlink == 1 and receipt.get('success') is True
                 and re.fullmatch('[a-f0-9]{40}', receipt.get('commit', '')),
                 'Successful protected installation receipt required.')
    if adopt:
        base.require(all(receipt.get('hashes', {}).get('rebuild/deploy/' + name)
                         == hashes['rebuild/deploy/' + name] for name in (SERVICE, TIMER)),
                     'Adoption cannot change the originally reviewed unit bytes.')
    else:
        base.require(receipt['commit'] == commit and receipt.get('hashes') == hashes,
                     'Exact reviewed installation receipt required.')
    return {'path': str(path), 'sha256': base.digest(path), 'commit': receipt['commit']}


def verified_attempt(prior):
    paths = set(base.MONITOR.glob('20*.json')) - prior
    base.require(len(paths) == 1, 'Expected exactly one immutable offsite attempt.')
    path = paths.pop()
    info = base.metadata(path)
    base.require(path.resolve() == path and path.stat().st_nlink == 1
                 and info.get('uid') == pwd.getpwnam('claude').pw_uid
                 and info.get('mode') == 0o600 and path.stat().st_size < 262144,
                 'Unsafe offsite attempt.')
    value = json.loads(path.read_bytes())
    evidence = value.get('result', {})
    remote, readback = value.get('last_remote_complete', {}), value.get('last_verified_readback', {})
    base.require(value.get('state') == 'complete' and value.get('reason_code') is None
                 and value.get('provider_calls_permitted') is True
                 and evidence.get('authenticated') is True and evidence.get('ciphertext_sha256_verified') is True
                 and not evidence.get('no_new_local_backup'),
                 'Controlled offsite run did not prove completion and readback.')
    identity_fields = ('run_id', 'manifest_cipher_sha256', 'object_count', 'cipher_bytes')
    base.require(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', evidence.get('run_id', ''))
                 and re.fullmatch(r'[a-f0-9]{64}', evidence.get('manifest_cipher_sha256', ''))
                 and type(evidence.get('object_count')) is int and evidence['object_count'] > 1
                 and type(evidence.get('cipher_bytes')) is int and evidence['cipher_bytes'] > 0
                 and all(evidence.get(key) == remote.get(key) == readback.get(key) for key in identity_fields),
                 'Controlled readback identity differs from uploaded snapshot.')
    times = [datetime.fromisoformat(raw) for raw in
             (value.get('started_at', ''), remote.get('completed_at', ''),
              readback.get('verified_at', ''), value.get('finished_at', ''))]
    base.require(all(moment.tzinfo is not None for moment in times)
                 and times[0] <= times[1] <= times[2] <= times[3],
                 'Controlled readback must occur within this service attempt.')
    return {'path': str(path), 'sha256': info['sha256'], 'record': value}


def scope():
    """Reuse the reviewed filesystem/systemd guards with explicit, narrower unit names."""
    base.INSTALLER = INSTALLER
    base.DECLARATION = DECLARATION
    base.SERVICE, base.TIMER, base.UNITS = SERVICE, TIMER, (SERVICE, TIMER)
    base.LINK = 'timers.target.wants/' + TIMER
    base.MONITOR = base.APP / '.runtime/automatic-offsite'
    base.EVIDENCE = base.APP / '.runtime/offsite-activation-20260920'
    base.SOURCES = (INSTALLER, 'rebuild/ops/install_backup_schedule.py',
                    'rebuild/ops/automatic_offsite.py', 'rebuild/ops/offsite_backup.py',
                    'rebuild/ops/backup_restore.py', 'rebuild/ops/private_storage.py',
                    'rebuild/ops/offsite_allocation.py',
                    'rebuild/ops/offsite_operator.py',
                    'rebuild/ops/install_offsite_policy.py',
                    'rebuild/ops/backup_alerts.py', 'rebuild/ops/recovery_kit.py',
                    DECLARATION, *(f'rebuild/deploy/{u}' for u in base.UNITS))


def unchanged_backups():
    """Content identity of existing backup monitor records; no new capture is part of this act."""
    folder = base.APP / '.runtime/backup-monitor'
    base.private_directory(folder)
    return {p.name: base.metadata(p) for p in folder.iterdir()}


def configuration():
    value = base.metadata(CONFIG)
    base.require(CONFIG.resolve() == CONFIG and CONFIG.stat().st_nlink == 1
                 and value.get('uid') == pwd.getpwnam('claude').pw_uid
                 and value.get('mode') == 0o600 and 'sha256' in value,
                 'Installed protected B2 configuration required.')


def operator_bytes(path, expected=None):
    """Read claude-owned records inside the root helper without relaxing metadata."""
    base.require(path.resolve() == path, 'Unsafe resume evidence path.')
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        base.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                     and info.st_uid == pwd.getpwnam('claude').pw_uid
                     and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size < 4 * 1024 * 1024,
                     'Unsafe resume evidence metadata.')
        raw = stream.read(4 * 1024 * 1024)
    base.require(expected is None or hashlib.sha256(raw).hexdigest() == expected,
                 'Pinned resume evidence changed.')
    return raw


def resume_snapshot(context):
    """This fixed observation is a current-state pin, not a retroactive secret hash."""
    paths = {'b2_configuration': CONFIG,
             'policy': base.APP / '.runtime/backup-secrets/offsite-policy.json',
             'allocation': base.APP / '.runtime/backup-secrets/offsite-allocation.json',
             **{name: base.MONITOR / (name + '.json') for name in ('budget', 'status', 'active')}}
    base.require(set(context['protected_files']) == set(paths), 'Unexpected resume state scope.')
    values = {}
    for name, path in paths.items():
        expected = context['protected_files'][name]
        base.require(expected['path'] == str(path), 'Resume state path differs.')
        raw = operator_bytes(path, expected['sha256'])
        base.require(base.metadata(path) == {**expected['metadata'], 'sha256': expected['sha256']},
                     'Resume state metadata changed.')
        if name in {'policy', 'status', 'active', 'budget'}:
            values[name] = json.loads(raw)
    actual = {path.name: hashlib.sha256(operator_bytes(path)).hexdigest()
              for path in base.MONITOR.glob('20*.json')}
    base.require(actual == context['attempt_files'], 'Offsite attempt history changed after qualification.')
    return values


def resume_qualification(payload):
    """Resume only the one authenticated run whose local timer parser failed.

    The hash-pinned failure and its immutable successful readback must survive;
    an arbitrary historical backup or a no-op can never take this path.
    """
    failure = json.loads(operator_bytes(base.EVIDENCE / RESUME_FAILURE, RESUME_FAILURE_SHA256))
    before = json.loads(operator_bytes(base.EVIDENCE / RESUME_BASELINE, RESUME_BASELINE_SHA256))
    context = json.loads(operator_bytes(base.EVIDENCE / RESUME_CONTEXT, RESUME_CONTEXT_SHA256))
    base.require(failure['action'] == before['action'] == 'activate'
                 and failure['commit'] == before['commit'] == context['prior_commit'] == RESUME_COMMIT
                 and failure['success'] is False and failure['timer_disabled'] is True
                 and failure['backup_records_unchanged'] is True and failure['b2_configuration_unchanged'] is True
                 and context['original_baseline_identical_after_failure'] is True
                 and context['inspection_does_not_retroactively_measure_pre_failure_config'] is True
                 and context['provider_calls'] == 0
                 and context['failed_report_sha256'] == RESUME_FAILURE_SHA256
                 and context['before_payload_sha256'] == RESUME_BASELINE_SHA256,
                 'The exact failed timer qualification is required.')
    base.require(before['baseline'] == payload['baseline'], 'Original controlled-run host baseline changed.')
    old_hashes = before['hashes']
    base.require(failure['hashes'] == old_hashes and set(old_hashes) == set(payload['hashes'])
                 and all(old_hashes[name] == current for name, current in payload['hashes'].items()
                         if name not in {INSTALLER, DECLARATION}),
                 'Resume permits only the reviewed timer verifier and declaration repair.')
    values = resume_snapshot(context)
    path = Path(context['controlled_attempt'])
    base.require(path.parent == base.MONITOR and path.name in context['attempt_files'],
                 'Controlled attempt is outside the pinned history.')
    attempts = set(base.MONITOR.glob('20*.json'))
    controlled = verified_attempt(attempts - {path})
    base.require(controlled == failure['controlled_run']
                 and controlled['sha256'] == context['controlled_attempt_sha256']
                 and values['status'] == controlled['record'] and values['budget'] == context['budget'],
                 'Current status does not match the retained authenticated run.')
    active, record = values['active'], controlled['record']
    base.require(active.get('complete') is True and active.get('pending') is None
                 and all(active.get(key) == record['result'][key]
                         for key in ('run_id', 'manifest_cipher_sha256')),
                 'Partial or different remote publication cannot qualify the timer.')
    at = datetime.now(timezone.utc)
    times = [datetime.fromisoformat(raw) for raw in
             (values['policy']['observed_at'], record['started_at'], record['finished_at'],
              failure['finished_at'], context['at'], values['policy']['valid_until'])]
    base.require(all(moment.tzinfo is not None for moment in times)
                 and times[0] <= times[1] <= times[2] <= times[3] <= times[4] <= at < times[5],
                 'Retained qualification is outside its original evidence interval.')
    limits = eligibility()
    base.require(limits == failure['eligibility'] == failure['eligibility_after_run']
                 and first_run_coverage(limits) == failure['first_run_coverage_before_enable'],
                 'The original qualification envelope or next calendar run changed.')
    return context, controlled, limits


def resume_activation(payload, result):
    """Hold the existing provider-work lock; change only timer enablement, never start its service."""
    # The existing privileged helper mounts the project read-only. Linux flock
    # permits an exclusive lock on a read-only descriptor; no state write is needed.
    fd = os.open(base.MONITOR / 'execution.lock', os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        base.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                     and info.st_uid == pwd.getpwnam('claude').pw_uid
                     and stat.S_IMODE(info.st_mode) == 0o600, 'Unsafe shared offsite lock.')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_path = os.stat(base.MONITOR / 'execution.lock', follow_symlinks=False)
        base.require((info.st_dev, info.st_ino) == (lock_path.st_dev, lock_path.st_ino),
                     'Shared offsite lock changed while being acquired.')
        context, controlled, limits = resume_qualification(payload)
        result.update(controlled_run=controlled, retained_failed_receipt=RESUME_FAILURE,
                      retained_failed_receipt_sha256=RESUME_FAILURE_SHA256,
                      resume_context_sha256=RESUME_CONTEXT_SHA256)
        raw = base.command(['systemctl', 'show', SERVICE, '--property=ActiveState,Result,ExecMainStatus']).decode()
        base.require(dict(line.split('=', 1) for line in raw.splitlines()) ==
                     {'ActiveState': 'inactive', 'Result': 'success', 'ExecMainStatus': '0'},
                     'Retained controlled service must remain successfully completed and inactive.')
        base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                     == b'inactive' and base.LINK not in payload['baseline']['units'],
                     'Resume requires the verified disabled timer.')
        identity = service_identity()
        coverage = first_run_coverage(limits)
        result['timer_enable_attempted'] = True
        base.command(['systemctl', 'enable', TIMER])
        base.command(['systemctl', 'start', TIMER])
        base.require(base.command(['systemctl', 'is-active', TIMER]).strip() == b'active'
                     and base.command(['systemctl', 'is-enabled', TIMER]).strip() == b'enabled',
                     'Offsite timer resume failed.')
        actual = first_run_coverage(eligibility(), actual=True)
        lock_path = os.stat(base.MONITOR / 'execution.lock', follow_symlinks=False)
        base.require((info.st_dev, info.st_ino) == (lock_path.st_dev, lock_path.st_ino),
                     'Shared offsite lock changed during timer resume.')
        resume_snapshot(context)  # No request, reservation, attempt, configuration or evidence mutation.
        return {'controlled_run': controlled, 'retained_failed_receipt': RESUME_FAILURE,
                'retained_failed_receipt_sha256': RESUME_FAILURE_SHA256,
                'resume_context_sha256': RESUME_CONTEXT_SHA256, 'service_identity': identity,
                'first_run_coverage_before_enable': coverage, 'first_run_coverage_actual': actual,
                'new_service_start': False, 'provider_calls': 0, 'shared_journal_unchanged': True}
    except Exception:
        if result.get('timer_enable_attempted'):
            # Contain only our timer while still holding the provider-work lock.
            # A pre-lock or proof refusal must not interrupt another consumer.
            try:
                base.command(['systemctl', 'disable', '--now', TIMER])
                result['timer_disabled'] = (
                    base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                    == b'inactive' and base.LINK not in base.baseline()['units'])
            except Exception:
                result['timer_disabled'] = False
        raise
    finally:
        os.close(fd)


def root_action(payload):
    base.require(os.getuid() == 0 and set(payload) == {'action', 'hashes', 'baseline', 'commit'},
                 'Invalid helper input.')
    base.require(payload['action'] in ('install', 'adopt', 'activate', 'resume', 'disable')
                 and set(payload['hashes']) == set(base.SOURCES), 'Invalid helper scope.')
    for relative, expected in payload['hashes'].items():
        path = base.ROOT / relative
        base.require(path.resolve() == path and base.digest(path) == expected, 'Reviewed source drift.')
    base.require(base.baseline() == payload['baseline'], 'Host changed after baseline.')
    result = {'action': payload['action'], 'success': False, 'commit': payload['commit'],
              'started_at': datetime.now(timezone.utc).isoformat(), 'new_offsite_units_only': True}
    try:
        if payload['action'] == 'install':
            base.require_absent(payload['baseline'])
            for name in base.UNITS:
                fd = os.open(base.SYSTEMD / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
                with os.fdopen(fd, 'wb') as stream:
                    os.fchmod(stream.fileno(), 0o644)
                    os.fchown(stream.fileno(), 0, 0)
                    stream.write((base.APP / 'deploy' / name).read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
            base.command(['systemctl', 'daemon-reload'])
            base.require_installed(payload['hashes'])
        elif payload['action'] == 'adopt':
            base.require_installed(payload['hashes'])
            base.require(base.LINK not in payload['baseline']['units'], 'Adoption requires an inactive timer.')
            base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Adoption requires an inactive timer.')
            result['service_identity'] = service_identity()
            result['unit_files_changed'] = False
        elif payload['action'] == 'activate':
            base.require_installed(payload['hashes'])
            base.require(base.LINK not in payload['baseline']['units'], 'Timer already enabled.')
            result['eligibility'] = eligibility()
            result['first_run_coverage_before'] = first_run_coverage(result['eligibility'])
            result['service_identity'] = service_identity()
            base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Timer must be inactive before controlled run.')
            prior = set(base.MONITOR.glob('20*.json'))
            base.command(['systemctl', 'start', SERVICE], timeout=980)
            state = base.command(['systemctl', 'show', SERVICE, '--property=Result,ExecMainStatus']).decode()
            base.require(dict(x.split('=', 1) for x in state.splitlines()) ==
                         {'Result': 'success', 'ExecMainStatus': '0'}, 'Controlled offsite run failed.')
            result['controlled_run'] = verified_attempt(prior)
            result['eligibility_after_run'] = eligibility()
            result['first_run_coverage_before_enable'] = first_run_coverage(result['eligibility_after_run'])
            base.command(['systemctl', 'enable', TIMER])
            base.command(['systemctl', 'start', TIMER])
            base.require(base.command(['systemctl', 'is-active', TIMER]).strip() == b'active'
                         and base.command(['systemctl', 'is-enabled', TIMER]).strip() == b'enabled',
                         'Offsite timer activation failed.')
            result['first_run_coverage_actual'] = first_run_coverage(eligibility(), actual=True)
        elif payload['action'] == 'resume':
            base.require_installed(payload['hashes'])
            result.update(resume_activation(payload, result))
        else:
            base.require_installed(payload['hashes'])
            base.command(['systemctl', 'disable', '--now', TIMER])
            base.command(['systemctl', 'stop', SERVICE])
            base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Offsite timer rollback failed.')
            base.require(base.command(['systemctl', 'show', SERVICE, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Offsite process rollback failed; preserve uncertain upload evidence.')
        after = base.baseline()
        if payload['action'] == 'disable':
            # Disabling removes only this timer's enablement link, retaining all evidence/units.
            prior = dict(payload['baseline'], units=dict(payload['baseline']['units']))
            prior['units'].pop(base.LINK, None)
            base.compare_baseline(prior, after, payload['hashes'], False)
            base.require(base.LINK not in after['units'], 'Timer enablement survived rollback.')
        else:
            base.compare_baseline(payload['baseline'], after, payload['hashes'], payload['action'] in ('activate', 'resume'))
        result.update(success=True, baseline_preserved=True, after=after)
    except Exception:
        result['error'] = 'Scoped offsite installation failed; retained evidence requires diagnosis.'
        if payload['action'] == 'activate':
            try:
                base.command(['systemctl', 'disable', '--now', TIMER])
                base.command(['systemctl', 'stop', SERVICE])
                result['timer_disabled'] = (
                    base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                    == b'inactive' and base.LINK not in base.baseline()['units'])
            except Exception:
                result['timer_disabled'] = False
        elif payload['action'] == 'resume' and result.get('timer_enable_attempted') and not result.get('timer_disabled'):
            # A post-return host-baseline failure still contains our timer, but
            # must never interrupt a separate provider consumer's service.
            try:
                base.command(['systemctl', 'disable', '--now', TIMER])
                result['timer_disabled'] = (
                    base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                    == b'inactive' and base.LINK not in base.baseline()['units'])
            except Exception:
                result['timer_disabled'] = False
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    return result


def main():
    scope()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--action', choices=('install', 'adopt', 'activate', 'resume', 'disable'), default='install')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    base.require(os.getuid() == pwd.getpwnam('claude').pw_uid, 'Use the authorized project operator.')
    os.umask(0o077)
    hashes = base.reviewed_source(args.expected_commit, mutation=args.execute)
    before, backups = base.baseline(), unchanged_backups()
    if args.action == 'install':
        base.require_absent(before)
        configuration()
    else:
        if args.action in ('activate', 'resume'):
            configuration()
        base.require_installed(hashes)
        prior_receipt = installation_receipt(args.expected_commit, hashes, adopt=args.action == 'adopt')
        if args.action == 'adopt':
            base.require(not adoption_receipt(args.expected_commit).exists(), 'Revision already adopted.')
    if not args.execute:
        print(json.dumps({'plan_verified': True, 'action': args.action, 'commit': args.expected_commit,
                          'host_mutation': False, 'application_restart': False}))
        return 0
    base.private_directory(base.EVIDENCE)
    if args.action == 'install':
        base.private_directory(base.MONITOR, create=True)
    # Containment must work after the B2 credential disappears or becomes unsafe.
    # Disable still checks reviewed units, installation and shared-host baseline,
    # but never opens configuration/policy or starts provider work.
    if args.action != 'disable':
        configuration()
        config_before = base.metadata(CONFIG)
    name = 'offsite-units-' + args.action + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
    payload = {'action': args.action, 'hashes': hashes, 'baseline': before, 'commit': args.expected_commit}
    base.write_private(base.EVIDENCE / (name + '-before.json'), payload)
    body = ('import argparse,datetime,fcntl,hashlib,json,os,pathlib,pwd,re,secrets,stat,subprocess,sys\n'
            'os.chroot("/host");os.chdir("/")\n'
            'sys.path.insert(0,' + repr(str(base.APP / 'ops')) + ')\n'
            'files=' + repr(hashes) + '\n'
            'assert all(hashlib.sha256((pathlib.Path(' + repr(str(base.ROOT)) + ')/p).read_bytes()).hexdigest()==h for p,h in files.items())\n'
            'sys.dont_write_bytecode=True\n'
            'import install_offsite_schedule as operation\n'
            'operation.scope()\n'
            'print(json.dumps(operation.root_action(' + repr(payload) + '),sort_keys=True))\n')
    try:
        child = subprocess.run(base.helper_command(), input=body.encode(), capture_output=True, timeout=1050,
                               env={'PATH': '/usr/local/bin:/usr/bin:/bin'})
        result = json.loads(child.stdout) if child.returncode == 0 else {'success': False, 'error': 'helper_failed'}
    except Exception:
        result = {'success': False, 'error': 'helper_outcome_unconfirmed'}
    result['hashes'] = hashes
    if args.action != 'install':
        result['prior_installation_receipt'] = prior_receipt
    result['backup_records_unchanged'] = backups == unchanged_backups()
    result['b2_configuration_checked'] = args.action != 'disable'
    result['b2_configuration_unchanged'] = (config_before == base.metadata(CONFIG)
                                             if args.action != 'disable' else None)
    result['success'] = (result.get('success') is True and result['backup_records_unchanged']
                         and (args.action == 'disable' or result['b2_configuration_unchanged']))
    base.write_private(base.EVIDENCE / (name + '-result.json'), result)
    if result['success'] and args.action == 'install':
        base.write_private(base.MONITOR / 'installation.json', result)
    elif result['success'] and args.action == 'adopt':
        base.write_private(adoption_receipt(args.expected_commit), result)
    print(json.dumps({'success': result['success'], 'action': args.action,
                      'evidence': str(base.EVIDENCE / (name + '-result.json'))}))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
