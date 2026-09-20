#!/usr/bin/env python3
"""Scoped installation of offsite units; activation requires a fresh capacity policy and verified service run."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess

try:
    from . import install_backup_schedule as base
except ImportError:
    import install_backup_schedule as base

INSTALLER = 'rebuild/ops/install_offsite_schedule.py'
DECLARATION = 'docs/foundation/mutations/20260920-quillmd-automatic-offsite.md'
SERVICE = 'quillmd-fresh-offsite.service'
TIMER = 'quillmd-fresh-offsite.timer'
CONFIG = base.APP / '.runtime/backup-secrets/b2-offsite.json'


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
    base.EVIDENCE = base.APP / '.runtime/automatic-offsite-20260920'
    base.SOURCES = (INSTALLER, 'rebuild/ops/install_backup_schedule.py',
                    'rebuild/ops/automatic_offsite.py', 'rebuild/ops/offsite_backup.py',
                    'rebuild/ops/backup_restore.py', 'rebuild/ops/private_storage.py',
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


def root_action(payload):
    base.require(os.getuid() == 0 and set(payload) == {'action', 'hashes', 'baseline', 'commit'},
                 'Invalid helper input.')
    base.require(payload['action'] in ('install', 'activate', 'disable')
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
        elif payload['action'] == 'activate':
            base.require_installed(payload['hashes'])
            base.require(base.LINK not in payload['baseline']['units'], 'Timer already enabled.')
            result['eligibility'] = eligibility()
            base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Timer must be inactive before controlled run.')
            prior = set(base.MONITOR.glob('20*.json'))
            base.command(['systemctl', 'start', SERVICE], timeout=980)
            state = base.command(['systemctl', 'show', SERVICE, '--property=Result,ExecMainStatus']).decode()
            base.require(dict(x.split('=', 1) for x in state.splitlines()) ==
                         {'Result': 'success', 'ExecMainStatus': '0'}, 'Controlled offsite run failed.')
            result['controlled_run'] = verified_attempt(prior)
            result['eligibility_after_run'] = eligibility()
            base.command(['systemctl', 'enable', TIMER])
            base.command(['systemctl', 'start', TIMER])
            base.require(base.command(['systemctl', 'is-active', TIMER]).strip() == b'active'
                         and base.command(['systemctl', 'is-enabled', TIMER]).strip() == b'enabled',
                         'Offsite timer activation failed.')
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
            base.compare_baseline(payload['baseline'], after, payload['hashes'], payload['action'] == 'activate')
        result.update(success=True, baseline_preserved=True, after=after)
    except Exception:
        result['error'] = 'Scoped offsite installation failed; retained evidence requires diagnosis.'
        if payload['action'] == 'activate':
            try:
                base.command(['systemctl', 'disable', '--now', TIMER])
                base.command(['systemctl', 'stop', SERVICE])
                result['timer_disabled'] = True
            except Exception:
                result['timer_disabled'] = False
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    return result


def main():
    scope()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--action', choices=('install', 'activate', 'disable'), default='install')
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
        if args.action == 'activate':
            configuration()
        base.require_installed(hashes)
        receipt = base.read_private(base.MONITOR / 'installation.json')
        base.require(receipt.get('success') and receipt.get('commit') == args.expected_commit
                     and receipt.get('hashes') == hashes, 'Exact reviewed installation receipt required.')
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
    body = ('import argparse,datetime,hashlib,json,os,pathlib,pwd,re,secrets,stat,subprocess,sys\n'
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
    result['backup_records_unchanged'] = backups == unchanged_backups()
    result['b2_configuration_checked'] = args.action != 'disable'
    result['b2_configuration_unchanged'] = (config_before == base.metadata(CONFIG)
                                             if args.action != 'disable' else None)
    result['success'] = (result.get('success') is True and result['backup_records_unchanged']
                         and (args.action == 'disable' or result['b2_configuration_unchanged']))
    base.write_private(base.EVIDENCE / (name + '-result.json'), result)
    if result['success'] and args.action == 'install':
        base.write_private(base.MONITOR / 'installation.json', result)
    print(json.dumps({'success': result['success'], 'action': args.action,
                      'evidence': str(base.EVIDENCE / (name + '-result.json'))}))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
