#!/usr/bin/env python3
"""Scoped installation of backup-alert units; application and backup units stay untouched."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess

try:
    from . import install_backup_schedule as base
except ImportError:
    import install_backup_schedule as base

INSTALLER = 'rebuild/ops/install_backup_alerts.py'
DECLARATION = 'docs/foundation/mutations/20260920-quillmd-operational-recovery.md'
SERVICE = 'quillmd-fresh-backup-alerts.service'
TIMER = 'quillmd-fresh-backup-alerts.timer'
CONFIG = base.APP / '.runtime/backup-secrets/backup-alerts.json'
CONFIGURATION = {'version': 1, 'recipient': 'kasra.rayat@gmail.com', 'enabled': True,
                 'synthetic_only': True, 'test_authorization_id': '20260920-operation-recovery'}


def scope():
    """Reuse the reviewed filesystem/systemd guards with explicit, narrower unit names."""
    base.INSTALLER = INSTALLER
    base.DECLARATION = DECLARATION
    base.SERVICE, base.TIMER, base.UNITS = SERVICE, TIMER, (SERVICE, TIMER)
    base.LINK = 'timers.target.wants/' + TIMER
    base.MONITOR = base.APP / '.runtime/backup-alerts'
    base.EVIDENCE = base.APP / '.runtime/operational-recovery-20260920'
    base.SOURCES = (INSTALLER, 'rebuild/ops/install_backup_schedule.py',
                    'rebuild/ops/backup_alerts.py', 'rebuild/ops/scheduled_backup.py',
                    'rebuild/ops/backup_restore.py', 'rebuild/core/email_backend.py',
                    DECLARATION, *(f'rebuild/deploy/{u}' for u in base.UNITS))


def unchanged_backups():
    """Content identity of existing backup monitor records; no new capture is part of this act."""
    folder = base.APP / '.runtime/backup-monitor'
    base.private_directory(folder)
    return {p.name: base.metadata(p) for p in folder.iterdir()}


def configuration():
    base.require(base.read_private(CONFIG) == CONFIGURATION, 'Alert configuration differs from authorization.')


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
              'started_at': datetime.now(timezone.utc).isoformat(), 'new_alert_units_only': True}
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
            # A healthy check sends no email; the single test is a separate explicit action.
            base.command(['systemctl', 'start', SERVICE], timeout=90)
            state = base.command(['systemctl', 'show', SERVICE, '--property=Result,ExecMainStatus']).decode()
            base.require(dict(x.split('=', 1) for x in state.splitlines()) ==
                         {'Result': 'success', 'ExecMainStatus': '0'}, 'Initial alert monitor check failed.')
            base.command(['systemctl', 'enable', TIMER])
            base.command(['systemctl', 'start', TIMER])
            base.require(base.command(['systemctl', 'is-active', TIMER]).strip() == b'active'
                         and base.command(['systemctl', 'is-enabled', TIMER]).strip() == b'enabled',
                         'Alert timer activation failed.')
        else:
            base.require_installed(payload['hashes'])
            base.command(['systemctl', 'disable', '--now', TIMER])
            base.command(['systemctl', 'stop', SERVICE])
            base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Alert timer rollback failed.')
            base.require(base.command(['systemctl', 'show', SERVICE, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Alert process rollback failed; preserve uncertain send receipt.')
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
        result['error'] = 'Scoped alert installation failed; retained evidence requires diagnosis.'
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
        base.require(not CONFIG.exists() and not CONFIG.is_symlink(), 'Do not overwrite alert configuration.')
        base.require(not base.MONITOR.exists() and not base.MONITOR.is_symlink(), 'Retain existing alert evidence.')
    else:
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
        base.private_directory(CONFIG.parent)
        base.write_private(CONFIG, CONFIGURATION)
        base.private_directory(base.MONITOR, create=True)
    configuration()
    config_before = base.metadata(CONFIG)
    name = 'alert-units-' + args.action + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
    payload = {'action': args.action, 'hashes': hashes, 'baseline': before, 'commit': args.expected_commit}
    base.write_private(base.EVIDENCE / (name + '-before.json'), payload)
    body = ('import argparse,datetime,hashlib,json,os,pathlib,pwd,re,secrets,stat,subprocess,sys\n'
            'os.chroot("/host");os.chdir("/")\n'
            'sys.path.insert(0,' + repr(str(base.APP / 'ops')) + ')\n'
            'files=' + repr(hashes) + '\n'
            'assert all(hashlib.sha256((pathlib.Path(' + repr(str(base.ROOT)) + ')/p).read_bytes()).hexdigest()==h for p,h in files.items())\n'
            'sys.dont_write_bytecode=True\n'
            'import install_backup_alerts as operation\n'
            'operation.scope()\n'
            'print(json.dumps(operation.root_action(' + repr(payload) + '),sort_keys=True))\n')
    try:
        child = subprocess.run(base.helper_command(), input=body.encode(), capture_output=True, timeout=150,
                               env={'PATH': '/usr/local/bin:/usr/bin:/bin'})
        result = json.loads(child.stdout) if child.returncode == 0 else {'success': False, 'error': 'helper_failed'}
    except Exception:
        result = {'success': False, 'error': 'helper_outcome_unconfirmed'}
    result['hashes'] = hashes
    result['backup_records_unchanged'] = backups == unchanged_backups()
    result['alert_configuration_unchanged'] = config_before == base.metadata(CONFIG)
    result['success'] = (result.get('success') is True and result['backup_records_unchanged']
                         and result['alert_configuration_unchanged'])
    base.write_private(base.EVIDENCE / (name + '-result.json'), result)
    if result['success'] and args.action == 'install':
        base.write_private(base.MONITOR / 'installation.json', result)
    print(json.dumps({'success': result['success'], 'action': args.action,
                      'evidence': str(base.EVIDENCE / (name + '-result.json'))}))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
