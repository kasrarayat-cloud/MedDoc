#!/usr/bin/env python3
"""Run the pinned project-only host SSH fixture through existing administrative access.

Default is read-only validation. --execute is for the already authorized synthetic
host exercise, not external reviewer activation. No app/shared SSH restart.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/opt/meddoc-pro')
EVIDENCE = ROOT / 'rebuild/.runtime/reviewer-host-20260919'
HARNESS_REL = 'scripts/ops/qualify-reviewer-host.py'
WORKTREE = ROOT / '.worktrees/reviewer-host-qualification'


def invoke(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--execute', action='store_true')
    args = ap.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.commit) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{5,32}', args.run_id):
        ap.error('Exact commit and project run slug required')
    source = WORKTREE / HARNESS_REL
    pinned = subprocess.check_output(['git', '-C', str(WORKTREE), 'show', args.commit + ':' + HARNESS_REL])
    actual = source.read_bytes()
    if actual != pinned or source.is_symlink():
        raise RuntimeError('Host harness differs from committed regular file')
    helper = WORKTREE / 'scripts/ops/reviewer-tunnel-access.sh'
    helper_pin = subprocess.check_output(['git', '-C', str(WORKTREE), 'show', args.commit + ':scripts/ops/reviewer-tunnel-access.sh'])
    if helper.is_symlink() or helper.read_bytes() != helper_pin:
        raise RuntimeError('Prepared policy source differs from committed file')
    image = invoke(['docker', 'image', 'inspect', 'python:3-slim', '--format', '{{.Id}}']).stdout.strip()
    if not re.fullmatch('sha256:[a-f0-9]{64}', image):
        raise RuntimeError('Existing administrative helper image not pinned')
    spec = {'source': str(source), 'source_sha256': hashlib.sha256(actual).hexdigest(),
            'helper': str(helper), 'helper_sha256': hashlib.sha256(helper_pin).hexdigest(),
            'commit': args.commit, 'run_id': args.run_id, 'image': image,
            'evidence': str(EVIDENCE / args.run_id), 'supervisor': 'quillmd-reviewer-qual-supervisor-' + args.run_id}
    if not args.execute:
        print(json.dumps({'validated': spec, 'executed': False}, indent=2))
        return
    EVIDENCE.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = Path(spec['evidence'])
    target.mkdir(mode=0o700)  # A previous attempt is evidence, never overwritten.
    (target / 'launch.json').write_text(json.dumps(spec, indent=2) + '\n')
    os.chmod(target / 'launch.json', 0o600)
    # The existing root-management bridge needs D-Bus access. This option applies
    # to this short-lived administrator container only; no host profile, shared
    # SSH service or application sandbox is modified. All host writes are made
    # by the pinned, narrowly scoped fixture, via its transient host supervisor.
    body = r'''
import os,sys,json,pathlib,subprocess,hashlib
P=json.loads(sys.stdin.readline())
os.chroot('/host');os.chdir('/')
for field in ('source','helper'):
 p=pathlib.Path(P[field])
 if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=P[field+'_sha256']:
  raise RuntimeError('Pinned program changed')
r=subprocess.run(['systemd-run','--wait','--pipe','--collect','--quiet',
  '--unit='+P['supervisor'],'--property=Type=exec','--property=RuntimeMaxSec=240',
  '--property=TimeoutStopSec=15','--property=KillMode=control-group',
  '/usr/bin/python3','-B',P['source'],'--evidence',P['evidence'],'--run-id',P['run_id']],
 capture_output=True,text=True,timeout=270)
print(json.dumps({'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))
'''
    try:
        proc = subprocess.run(['docker','run','--rm','-i','--pull=never','--network=none','--pid=host',
                               '--security-opt','apparmor=unconfined','--mount','type=bind,src=/,dst=/host,readonly',
                               image,'python','-B','-c',body], input=json.dumps(spec)+'\n',capture_output=True,text=True,timeout=290)
        result = {'bridge_exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}
    except subprocess.TimeoutExpired as exc:
        def decoded(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')
        result = {'bridge_timed_out':True, 'cleanup_verified':False,
                  'stdout':decoded(exc.stdout), 'stderr':decoded(exc.stderr)}
        (target/'launcher-result.json').write_text(json.dumps(result,indent=2)+'\n')
        os.chmod(target/'launcher-result.json',0o600)
        raise RuntimeError('Administrative bridge timed out; evidence preserved; verify the exact supervisor, fixture units and identities before proceeding') from exc
    (target/'launcher-result.json').write_text(json.dumps(result,indent=2)+'\n')
    os.chmod(target/'launcher-result.json',0o600)
    if proc.returncode != 0:
        raise RuntimeError('Administrative bridge failed; inspect private launcher-result.json; preserve attempt and verify scoped cleanup')
    host = json.loads(proc.stdout)
    print(json.dumps({'evidence':str(target),'host_exit_code':host['exit_code'],'executed':True}))
    if host['exit_code'] != 0:
        raise SystemExit(host['exit_code'])


if __name__ == '__main__':
    main()
