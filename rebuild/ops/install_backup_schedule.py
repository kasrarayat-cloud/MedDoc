#!/usr/bin/env python3
"""Plan/install/activate only the two new, reviewed QuillMD backup units. No deletion."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
SYSTEMD = Path('/etc/systemd/system')
MONITOR = APP / '.runtime/backup-monitor'
EVIDENCE = APP / '.runtime/overnight-completion-20260920'
DECLARATION = 'docs/foundation/mutations/20260920-quillmd-overnight-completion.md'
INSTALLER = 'rebuild/ops/install_backup_schedule.py'
IMAGE = 'sha256:9b84b0c75adf7a34fb1b00b406a50dc9f7bebd3bfbe3e7fd9ff168a6f9d0dfb9'
SERVICE = 'quillmd-fresh-backup.service'
TIMER = 'quillmd-fresh-backup.timer'
UNITS = (SERVICE, TIMER)
LINK = 'timers.target.wants/' + TIMER
SOURCES = (INSTALLER, 'rebuild/ops/scheduled_backup.py', 'rebuild/ops/backup_restore.py',
           'rebuild/ops/private_storage.py', DECLARATION, *(f'rebuild/deploy/{u}' for u in UNITS))
PROTECTED = (APP / '.env', APP / '.runtime/db-role-secrets/fresh-db-roles.json',
             APP / '.runtime/backup-secrets/fresh-backup-current-20260917.key')
FRESH = tuple('quillmd-fresh-' + name + '.service' for name in ('doctor', 'admin', 'worker', 'database'))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def command(argv, timeout=40):
    result = subprocess.run(argv, capture_output=True, timeout=timeout,
                            env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C'})
    require(result.returncode == 0, 'Command refused or failed; raw output suppressed.')
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(path):
    info = path.lstat()
    result = {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):
        result['link'] = os.readlink(path)
    elif stat.S_ISREG(info.st_mode):
        result['sha256'] = digest(path)
    elif stat.S_ISDIR(info.st_mode):
        result['directory'] = True
    else:
        raise RuntimeError('Unexpected configuration object.')
    return result


def private_directory(path, create=False):
    require(path.is_absolute() and path.resolve() == path, 'Private path must be fixed without symlinks.')
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    value = metadata(path)
    require(value == {'uid': pwd.getpwnam('claude').pw_uid, 'gid': pwd.getpwnam('claude').pw_gid,
                      'mode': 0o700, 'directory': True}, 'Expected claude0700 directory.')


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def read_private(path):
    value = metadata(path)
    require(path.resolve() == path and value.get('uid') == os.getuid()
            and value.get('mode') == 0o600 and 'sha256' in value and path.stat().st_size < 262144,
            'Unsafe installation receipt.')
    return json.loads(path.read_bytes())


def reviewed_source(commit, mutation=False):
    require(re.fullmatch('[a-f0-9]{40}', commit), 'Full reviewed commit required.')
    git = ['git', '-c', 'safe.directory=' + str(ROOT), '-C', str(ROOT)]
    require(command(git + ['rev-parse', 'HEAD']).strip().decode() == commit
            and command(git + ['branch', '--show-current']).strip() == b'main',
            'Use the exact reviewed permanent main revision.')
    hashes = {}
    for relative in SOURCES:
        path = ROOT / relative
        require(path.resolve() == path and path.is_file(), 'Source symlink or missing source.')
        require(command(git + ['show', commit + ':' + relative]) == path.read_bytes(),
                'Source differs from the reviewed commit.')
        hashes[relative] = digest(path)
    if mutation:
        declared = os.environ.get('RULED_MUTATION_DECLARATION', '')
        require((ROOT / declared).absolute() == ROOT / DECLARATION,
                'Use the committed overnight ruled-mutation declaration.')
        declared_commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
        require(re.fullmatch('[a-f0-9]{40}', declared_commit), 'Committed declaration identity required.')
        require(command(git + ['log', '-1', '--format=%H', '--', DECLARATION]).strip().decode()
                == declared_commit, 'Declaration commit differs.')
        require(command(git + ['show', declared_commit + ':' + DECLARATION]) == (ROOT / DECLARATION).read_bytes(),
                'Declaration differs from its recorded commit.')
    command(['systemd-analyze', 'verify', *(str(APP / 'deploy' / name) for name in UNITS)])
    require(command(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}']).strip().decode() == IMAGE,
            'Pinned local helper image unavailable; do not pull an image.')
    return hashes


def baseline():
    require(SYSTEMD.resolve() == SYSTEMD and metadata(SYSTEMD) ==
            {'uid': 0, 'gid': 0, 'mode': 0o755, 'directory': True}, 'Unexpected systemd directory.')
    units = {str(path.relative_to(SYSTEMD)): metadata(path) for path in SYSTEMD.rglob('*')}
    configuration = {}
    for path in PROTECTED:
        value = metadata(path)
        require(path.resolve() == path and value.get('uid') == pwd.getpwnam('claude').pw_uid
                and value.get('mode') == 0o600 and 'sha256' in value, 'Unsafe protected configuration.')
        configuration[str(path)] = value
    processes = {}
    for name in FRESH:
        raw = command(['systemctl', 'show', name, '--property=ActiveState,MainPID']).decode()
        value = dict(line.split('=', 1) for line in raw.splitlines())
        require(value.get('ActiveState') == 'active', 'Existing private service must already be active.')
        processes[name] = value
    return {'units': units, 'configuration': configuration, 'processes': processes}


def require_absent(before):
    for name in UNITS:
        require(name not in before['units'] and not any(p.startswith(name + '.d') for p in before['units']),
                'New backup units must be absent, including overrides.')
        require(command(['systemctl', 'show', name, '--property=LoadState', '--value']).strip() == b'not-found',
                'Backup unit already resolved by systemd.')
    require(LINK not in before['units'], 'Backup timer authorization already exists.')


def require_installed(hashes):
    for name in UNITS:
        path = SYSTEMD / name
        require(metadata(path) == {'uid': 0, 'gid': 0, 'mode': 0o644,
                                  'sha256': hashes['rebuild/deploy/' + name]}, 'Installed unit changed.')
        require(not (SYSTEMD / (name + '.d')).exists(), 'Unexpected backup unit override.')
        fragment = command(['systemctl', 'show', name, '--property=FragmentPath', '--value']).strip().decode()
        require(fragment == str(path), 'Unexpected effective backup unit path.')
        require(command(['systemctl', 'show', name, '--property=DropInPaths', '--value']).strip() == b'',
                'Unexpected effective backup unit override.')


def compare_baseline(before, after, hashes, activate):
    require(before['configuration'] == after['configuration'] and before['processes'] == after['processes'],
            'Protected configuration or existing service changed.')
    allowed = set(UNITS) | ({LINK, 'timers.target.wants'} if activate else set())
    require({k: v for k, v in before['units'].items() if k not in allowed}
            == {k: v for k, v in after['units'].items() if k not in allowed},
            'Unrelated systemd configuration changed.')
    for name in UNITS:
        require(after['units'].get(name) == {'uid': 0, 'gid': 0, 'mode': 0o644,
                                            'sha256': hashes['rebuild/deploy/' + name]}, 'Unit readback failed.')
    if activate:
        require(after['units'].get(LINK) == {'uid': 0, 'gid': 0, 'mode': 0o777,
                                           'link': str(SYSTEMD / TIMER)}, 'Timer enablement differs.')
        expected_parent = before['units'].get('timers.target.wants',
                                             {'uid': 0, 'gid': 0, 'mode': 0o755, 'directory': True})
        require(after['units'].get('timers.target.wants') == expected_parent, 'Timer parent differs.')


def root_action(payload):
    """Called only inside the fixed, reviewed root helper; no caller-supplied paths."""
    require(os.getuid() == 0 and set(payload) == {'action', 'hashes', 'baseline', 'commit'}, 'Invalid helper input.')
    require(payload['action'] in ('install', 'activate') and set(payload['hashes']) == set(SOURCES),
            'Invalid helper scope.')
    require(re.fullmatch('[a-f0-9]{40}', payload['commit']), 'Invalid reviewed revision.')
    hashes = payload['hashes']
    for relative, expected in hashes.items():
        require((ROOT / relative).resolve() == ROOT / relative and digest(ROOT / relative) == expected, 'Source drift.')
    require(baseline() == payload['baseline'], 'Host changed after the baseline.')
    private_directory(MONITOR)
    result = {'action': payload['action'], 'success': False, 'commit': payload['commit'], 'hashes': hashes,
              'started_at': datetime.now(timezone.utc).isoformat(), 'new_units_only': True}
    try:
        if payload['action'] == 'install':
            require_absent(payload['baseline'])
            for name in UNITS:
                fd = os.open(SYSTEMD / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
                with os.fdopen(fd, 'wb') as stream:
                    os.fchmod(stream.fileno(), 0o644)
                    os.fchown(stream.fileno(), 0, 0)
                    stream.write((APP / 'deploy' / name).read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
            command(['systemctl', 'daemon-reload'])
            require_installed(hashes)
        else:
            require_installed(hashes)
            require(command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip() == b'inactive',
                    'Timer must be inactive before the bounded capture.')
            require(LINK not in payload['baseline']['units'], 'Timer must not already be enabled.')
            prior = {path.name for path in MONITOR.glob('20*.json')}
            command(['systemctl', 'start', SERVICE], timeout=620)
            state = command(['systemctl', 'show', SERVICE, '--property=Result,ExecMainStatus']).decode()
            require(dict(line.split('=', 1) for line in state.splitlines()) ==
                    {'Result': 'success', 'ExecMainStatus': '0'}, 'Backup service did not complete successfully.')
            new = {path.name for path in MONITOR.glob('20*.json')} - prior
            require(len(new) == 1, 'Expected exactly one new backup attempt.')
            attempt_path = MONITOR / next(iter(new))
            info = metadata(attempt_path)
            require(info.get('uid') == pwd.getpwnam('claude').pw_uid and info.get('mode') == 0o600
                    and 'sha256' in info and attempt_path.stat().st_size <= 65536, 'Unsafe backup attempt.')
            attempt = json.loads(attempt_path.read_bytes())
            require(attempt.get('outcome') == 'complete' and attempt.get('summary', {}).get('complete') is True
                    and attempt['summary'].get('source_commit') == payload['commit'], 'Capture evidence incomplete or stale.')
            result['capture_attempt'] = attempt_path.name
            result['capture_attempt_sha256'] = info['sha256']
            result['capture_summary'] = attempt['summary']
            # Enable after the demonstrated capture; start the timer separately from the service.
            command(['systemctl', 'enable', TIMER])
            command(['systemctl', 'start', TIMER])
            require(command(['systemctl', 'is-active', TIMER]).strip() == b'active', 'Timer not active.')
            require(command(['systemctl', 'is-enabled', TIMER]).strip() == b'enabled', 'Timer not enabled.')
            require({path.name for path in MONITOR.glob('20*.json')} - prior == new,
                    'Timer unexpectedly initiated an additional capture.')
        after = baseline()
        compare_baseline(payload['baseline'], after, hashes, payload['action'] == 'activate')
        result.update(success=True, baseline_preserved=True, after=after)
    except Exception:
        result['error'] = 'Scoped backup installation or verification failed; inspect retained evidence.'
        if payload['action'] == 'activate':
            try:
                command(['systemctl', 'disable', '--now', TIMER])
                result['timer_stopped_disabled'] = True
            except Exception:
                result['timer_stopped_disabled'] = False
        # Retain partial units and capture history. Never alter existing services or delete backups.
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    return result


def helper_command():
    return ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none', '--pid=host',
            '--mount', 'type=bind,src=/,dst=/host,readonly',
            '--mount', 'type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system', IMAGE, 'python', '-']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--action', choices=('install', 'activate'), default='install')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(os.getuid() == pwd.getpwnam('claude').pw_uid, 'Run as claude, using the reviewed root helper.')
    os.umask(0o077)
    hashes = reviewed_source(args.expected_commit, mutation=args.execute)
    before = baseline()
    if args.action == 'install':
        require_absent(before)
        require(not (MONITOR / 'installation.json').exists() and not (MONITOR / 'installation.json').is_symlink(),
                'Installation receipt already exists; do not overwrite evidence.')
    else:
        receipt = read_private(MONITOR / 'installation.json')
        require(receipt.get('success') is True and receipt.get('action') == 'install'
                and receipt.get('commit') == args.expected_commit and receipt.get('hashes') == hashes,
                'Successful exact-revision installation receipt required.')
        require_installed(hashes)
    if not args.execute:
        print(json.dumps({'plan_verified': True, 'action': args.action, 'commit': args.expected_commit,
                          'unit_hashes': {u: hashes['rebuild/deploy/' + u] for u in UNITS},
                          'helper_image': IMAGE, 'host_mutation': False}))
        return 0
    private_directory(EVIDENCE)
    private_directory(APP / '.runtime')
    private_directory(MONITOR, create=True)
    name = 'backup-schedule-' + args.action + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
    payload = {'action': args.action, 'hashes': hashes, 'baseline': before, 'commit': args.expected_commit}
    write_private(EVIDENCE / (name + '-before.json'), payload)
    # Load all standard-library imports before chroot; no host Python packages or secrets are inherited.
    source = (ROOT / INSTALLER).read_bytes()
    body = ('import argparse,datetime,hashlib,json,os,pathlib,pwd,re,secrets,stat,subprocess\n'
            'os.chroot("/host");os.chdir("/")\n'
            'source=pathlib.Path(' + repr(str(ROOT / INSTALLER)) + ').read_bytes()\n'
            'assert hashlib.sha256(source).hexdigest()==' + repr(hashes[INSTALLER]) + '\n'
            'namespace={"__name__":"reviewed_backup_helper"}\n'
            'exec(compile(source,' + repr(str(ROOT / INSTALLER)) + ',"exec"),namespace)\n'
            'print(json.dumps(namespace["root_action"](' + repr(payload) + '),sort_keys=True))\n')
    require(hashlib.sha256(source).hexdigest() == hashes[INSTALLER], 'Installer drift.')
    try:
        child = subprocess.run(helper_command(), input=body.encode(), capture_output=True, timeout=900,
                               env={'PATH': '/usr/local/bin:/usr/bin:/bin'})
    except subprocess.TimeoutExpired:
        result = {'success': False, 'error': 'Helper deadline exceeded; completion and timer state unverified.'}
        write_private(EVIDENCE / (name + '-result.json'), result)
        print(json.dumps({'success': False, 'evidence': str(EVIDENCE / (name + '-result.json'))}))
        return 1
    if child.returncode == 0:
        try:
            result = json.loads(child.stdout)
        except Exception:
            result = {'success': False, 'error': 'Invalid helper result.'}
    else:
        result = {'success': False, 'error': 'Helper failed; no raw output emitted.', 'exit_code': child.returncode}
    write_private(EVIDENCE / (name + '-result.json'), result)
    if result.get('success') and args.action == 'install':
        write_private(MONITOR / 'installation.json', result)
    print(json.dumps({'success': result.get('success') is True, 'action': args.action,
                      'evidence': str(EVIDENCE / (name + '-result.json'))}))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    raise SystemExit(main())
