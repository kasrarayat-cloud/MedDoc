#!/usr/bin/env python3
"""Install exactly the three reviewed private units while stopped; no restart."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from backup_restore import private_dir, require, run, write_private

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
UNITS = ['quillmd-fresh-' + x + '.service' for x in ('doctor', 'admin', 'worker')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(re.fullmatch('[a-f0-9]{40}', args.expected_commit), 'Full reviewed commit required.')
    require(run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip() == args.expected_commit
            and run(['git', '-C', str(ROOT), 'branch', '--show-current']).strip() == b'main',
            'Install only from the reviewed activated main commit.')
    expected = {}
    for unit in UNITS:
        path = APP / 'deploy' / unit
        data = path.read_bytes()
        require(run(['git', '-C', str(ROOT), 'show', args.expected_commit + ':rebuild/deploy/' + unit]) == data,
                'Unit bytes differ from reviewed commit.')
        require(b'InaccessiblePaths=/run/docker.sock' in data
                and b'/opt/meddoc-pro/rebuild/.runtime' in data
                and b'User=quillmd-app\n' in data and b'Group=quillmd-app\n' in data
                and b'CapabilityBoundingSet=\n' in data and b'AmbientCapabilities=\n' in data,
                'Required sandbox policy missing.')
        expected[unit] = hashlib.sha256(data).hexdigest()
    run(['systemd-analyze', 'verify', *[str(APP / 'deploy' / u) for u in UNITS]])
    if not args.execute:
        print('Verified three tracked unit policies; no systemd changes.')
        return
    require(Path(os.environ.get('RULED_MUTATION_DECLARATION', '')).name ==
            '20260917-quillmd-private-beta-update.md'
            and re.fullmatch('[a-f0-9]{40}', os.environ.get('RULED_MUTATION_DECL_COMMIT', '')),
            'Coordinated committed private-beta declaration required.')
    for unit in UNITS:
        require(run(['systemctl', 'show', unit, '--property=ActiveState', '--value']).strip() == b'inactive',
                'Stop all three private services before changing unit policy.')
    for name in ('db-role-secrets', 'backup-secrets', 'new-system-backups', 'restore-checks'):
        private_dir(APP / '.runtime' / name, create=True)
    body = '''import os,pathlib,subprocess,hashlib,json
os.chroot('/host');os.chdir('/')
expected=EXPECTED
for unit,sha in expected.items():
 source=pathlib.Path('/opt/meddoc-pro/rebuild/deploy')/unit
 data=source.read_bytes()
 if hashlib.sha256(data).hexdigest()!=sha:raise RuntimeError('Unit drift')
 target=pathlib.Path('/etc/systemd/system')/unit
 if not target.is_file() or target.is_symlink():raise RuntimeError('Unexpected unit target')
 temp=target.with_name('.'+unit+'.private-beta-pending')
 fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
 with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
 temp.replace(target)
subprocess.run(['systemctl','daemon-reload'],check=True)
'''.replace('EXPECTED', repr(expected))
    run(['docker', 'run', '--rm', '-i', '--network', 'none', '--pid=host',
         '--mount', 'type=bind,src=/,dst=/host,readonly',
         '--mount', 'type=bind,src=/etc/systemd/system,dst=/host/etc/systemd/system',
         'python:3-slim', 'python', '-'], data=body.encode())
    for unit, h in expected.items():
        require(hashlib.sha256((Path('/etc/systemd/system') / unit).read_bytes()).hexdigest() == h,
                'Installed unit readback differs.')
    print(json.dumps({'installed': UNITS, 'exact_unit_hashes': expected, 'daemon_reloaded': True, 'services_started': False}))


if __name__ == '__main__':
    main()
