#!/usr/bin/env python3
"""Move the QuillMD fresh database and state onto a LUKS2 encrypted volume; default is read-only preflight.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B scripts/migrate-fresh-storage.py \
        --target FULL_MERGE_SHA --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/fresh-storage-migration-<label>.json [--execute | --rollback]

Design (see docs/rebuild/storage-encryption.md): a sparse loop file under /opt/meddoc-pro/secrets holds a
LUKS2 container whose ext4 filesystem carries `postgres/` and `state/`. quillmd-fresh-volume.service opens
it before docker and bind-mounts those roots over the docker named-volume directory and /var/lib/quillmd,
so the PostgreSQL container keeps its identity and the application keeps its paths. When the volume is
closed, both bind targets are empty, root-owned, immutable directories. Root steps run through the fixed
local python helper image with the host root bound read-only plus the few writable paths each step needs;
every mount/unmount/luks operation is executed by the host's systemd (systemd-run / systemctl) so it lands
in the host mount namespace. The executing form runs only through scripts/run-ruled-mutation.sh.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
BASELINE = '19d46ad3d51a3d8b548b4b53073f91664ca30946'
DECL = 'docs/foundation/mutations/20260918-quillmd-fresh-storage-encryption.md'
APP_UNITS = ['quillmd-fresh-' + s + '.service' for s in ('doctor', 'admin', 'worker')]
NEW_UNITS = ['quillmd-fresh-volume.service', 'quillmd-fresh-database.service']
VOLUME_SCRIPT = 'rebuild/deploy/quillmd-fresh-volume.sh'
VOLUME_SCRIPT_TARGET = '/usr/local/bin/quillmd-fresh-volume'
ALLOWED = {'rebuild/deploy/' + u for u in APP_UNITS + NEW_UNITS} | {
    VOLUME_SCRIPT, 'scripts/migrate-fresh-storage.py', 'scripts/verify-post-reboot.sh',
    'rebuild/ops/test_storage_migration.py', 'docs/rebuild/storage-encryption.md',
    'docs/rebuild/patient-data-release-requirements.md', 'docs/rebuild/security-readiness.md',
    'docs/rebuild/CHECKPOINT.md', 'docs/rebuild/owner-actions.md', DECL}  # the last two landed with PR #1191 between the baseline and this target
CONTAINER = 'quillmd-fresh-postgres'
IMAGE = '/opt/meddoc-pro/secrets/quillmd-fresh.luks'
KEY = '/etc/quillmd/quillmd-fresh-luks.key'
RECOVERY = '/etc/quillmd/quillmd-fresh-luks.recovery-passphrase'
MAPPER = 'quillmd-fresh-encrypted'
MOUNT = '/mnt/quillmd-fresh-encrypted'
PG_DATA = '/var/lib/docker/volumes/quillmd_fresh_pg/_data'
ROLLBACK = '/var/lib/quillmd-rollback-20260918'
IMAGE_BYTES = 16 * 2 ** 30
PSQL = ['docker', 'exec', CONTAINER, 'psql', '-U', 'quillmd_fresh', '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helper_image():
    image = output(['docker', 'image', 'inspect', 'python:3-slim', '--format', '{{.Id}}'])
    require(re.fullmatch('sha256:[a-f0-9]{64}', image), 'The fixed local helper image must already exist.')
    return image


def root(code, params, image, *, writable=(), ipc=False, timeout=1800):
    """Run a root step: host root bound read-only plus explicit writable binds; result is the last JSON line."""
    args = ['docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--pid=host',
            '--security-opt', 'apparmor=unconfined', '--mount', 'type=bind,src=/,dst=/host,readonly']
    if ipc:
        args.append('--ipc=host')
    for path in writable:
        args += ['--mount', f'type=bind,src={path},dst=/host{path}']
    args += [image, 'python', '-B', '-']
    source = "import os,sys,json,subprocess,stat,hashlib,time\nos.chroot('/host');os.chdir('/');os.umask(0o077)\nP=json.loads(sys.stdin.readline())\n" + code
    result = subprocess.run(args, input=json.dumps(params) + '\n' + source, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    require(result.returncode == 0 and lines, 'Root step failed: ' + result.stderr[-1500:])
    return json.loads(lines[-1])


ROOT_PREFLIGHT = r'''
def st(p):
    try:
        s=os.lstat(p); return {'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid,'dev':s.st_dev,'ino':s.st_ino,'type':'dir' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'other'}
    except FileNotFoundError: return None
mounted=set()
for line in open('/proc/1/mountinfo'):
    mounted.add(line.split(' ')[4])
free=os.statvfs('/opt/meddoc-pro/secrets'); free_bytes=free.f_bavail*free.f_frsize
report={'pg_data':st(P['pg_data']),'state':st(str(P['state'])),'state_children':{n:st(str(P['state'])+'/'+n) for n in ('files','mail','proofs')},
        'image':st(P['image']),'key':st(P['key']),'mount':st(P['mount']),'rollback':st(P['rollback']),
        'pg_data_mounted':P['pg_data'] in mounted,'state_mounted':str(P['state']) in mounted,'mount_mounted':P['mount'] in mounted,
        'mapper_present':os.path.exists('/dev/mapper/'+P['mapper']),'free_bytes':free_bytes,
        'tools':{t:os.access(t,os.X_OK) for t in ('/usr/sbin/cryptsetup','/usr/sbin/mkfs.ext4','/usr/bin/rsync','/usr/bin/chattr','/usr/bin/systemd-run','/usr/bin/mountpoint','/usr/bin/findmnt')},
        'volume_script_installed':os.path.exists(P['volume_script_target']),
        'units_installed':{u:os.path.exists('/etc/systemd/system/'+u) for u in P['new_units']}}
print(json.dumps(report))
'''

ROOT_PREPARE = r'''
def host(*cmd, timeout=900):
    r=subprocess.run(['systemd-run','--wait','--pipe','--collect','--quiet','--property=Type=oneshot',*cmd],capture_output=True,text=True,timeout=timeout)
    if r.returncode!=0: raise RuntimeError('host command failed: '+' '.join(cmd)+' :: '+r.stderr[-800:])
    return r.stdout
if os.path.exists(P['key']) or os.path.exists(P['image']) or os.path.exists(P['recovery']): raise RuntimeError('key, recovery passphrase or image already exists')
fd=os.open(P['key'],os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'wb') as f: f.write(os.urandom(64)); f.flush(); os.fsync(f.fileno())
import secrets
phrase=secrets.token_urlsafe(36)
fd=os.open(P['recovery'],os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'w') as f: f.write(phrase+'\n'); f.flush(); os.fsync(f.fileno())
fd=os.open(P['image'],os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
os.ftruncate(fd,P['image_bytes']); os.close(fd)
os.makedirs(P['mount'],mode=0o700,exist_ok=False)
host('/usr/sbin/cryptsetup','-q','--type','luks2','--key-file',P['key'],'luksFormat',P['image'])
host('/usr/sbin/cryptsetup','open','--key-file',P['key'],P['image'],P['mapper'])
host('/usr/sbin/cryptsetup','luksAddKey','--key-file',P['key'],P['image'],P['recovery'])
host('/usr/sbin/mkfs.ext4','-q','-L','quillmd-fresh','/dev/mapper/'+P['mapper'])
host('/bin/mount','-o','nodev,nosuid','/dev/mapper/'+P['mapper'],P['mount'])
dump=host('/usr/sbin/cryptsetup','luksDump',P['image'])
slots=[l for l in dump.splitlines() if l.strip().startswith(('0:','1:')) and 'luks2' in l]
print(json.dumps({'formatted':True,'key_slots':len(slots),'cipher':next((l.strip() for l in dump.splitlines() if 'Cipher:' in l),''),'image_sha256_header':hashlib.sha256(open(P['image'],'rb').read(4096)).hexdigest()}))
'''

ROOT_COPY = r'''
def sh(*cmd, timeout=1800):
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if r.returncode!=0: raise RuntimeError(' '.join(cmd[:3])+' failed: '+r.stderr[-800:])
    return r.stdout
M=P['mount']
mounted={line.split(' ')[4] for line in open('/proc/1/mountinfo')}
if M not in mounted: raise RuntimeError('encrypted volume is not mounted in the host namespace')
if os.path.exists(P['rollback']): raise RuntimeError('rollback directory already exists')
os.mkdir(M+'/postgres',0o700); os.mkdir(M+'/state',0o710)
sh('/usr/bin/rsync','-aHAX','--numeric-ids',P['pg_data']+'/',M+'/postgres/')
sh('/usr/bin/rsync','-aHAX','--numeric-ids',str(P['state'])+'/',M+'/state/')
diff_pg=sh('/usr/bin/rsync','-aHAXn','--numeric-ids','--checksum','--delete','--itemize-changes',P['pg_data']+'/',M+'/postgres/')
diff_state=sh('/usr/bin/rsync','-aHAXn','--numeric-ids','--checksum','--delete','--itemize-changes',str(P['state'])+'/',M+'/state/')
if diff_pg.strip() or diff_state.strip(): raise RuntimeError('copy verification reported differences')
def census(root):
    files=0;size=0;h=hashlib.sha256()
    for d,dirs,fs in os.walk(root):
        dirs.sort(); fs.sort()
        for f in fs:
            p=os.path.join(d,f); s=os.lstat(p)
            if stat.S_ISREG(s.st_mode):
                files+=1; size+=s.st_size
                with open(p,'rb') as fh:
                    for chunk in iter(lambda: fh.read(1<<20), b''): h.update(chunk)
    return {'files':files,'bytes':size,'content_sha256':h.hexdigest()}
pg_before=census(P['pg_data']); pg_after=census(M+'/postgres')
st_before=census(str(P['state'])); st_after=census(M+'/state')
if pg_before!=pg_after or st_before!=st_after: raise RuntimeError('census differs after copy')
uid,gid=P['uid'],P['gid']
os.mkdir(M+'/state/tmp',0o700); os.chown(M+'/state/tmp',uid,gid)
os.chown(M+'/state',0,gid); os.chmod(M+'/state',0o710)
fd=os.open(M+'/.quillmd-fresh-volume',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'w') as f: json.dump({'created':P['now'],'source_commit':P['target'],'roots':['postgres','state']},f); f.flush(); os.fsync(f.fileno())
os.mkdir(P['rollback'],0o700)
os.rename(P['pg_data'],P['rollback']+'/pg_data'); os.mkdir(P['pg_data'],0o700)
os.rename(str(P['state']),P['rollback']+'/state'); os.mkdir(str(P['state']),0o710); os.chown(str(P['state']),0,gid)
sh('/usr/bin/chattr','+i',P['pg_data']); sh('/usr/bin/chattr','+i',str(P['state']))
ident={n:{'device':os.stat(M+'/state/'+n).st_dev,'inode':os.stat(M+'/state/'+n).st_ino} for n in ('files','mail','proofs')}
print(json.dumps({'copied':True,'pg':pg_after,'state':st_after,'identity':ident,'tmp_owner':[uid,gid]}))
'''

ROOT_INSTALL = r'''
def host(*cmd, timeout=600):
    r=subprocess.run(['systemd-run','--wait','--pipe','--collect','--quiet','--property=Type=oneshot',*cmd],capture_output=True,text=True,timeout=timeout)
    if r.returncode!=0: raise RuntimeError('host command failed: '+' '.join(cmd)+' :: '+r.stderr[-800:])
    return r.stdout
mounted={line.split(' ')[4] for line in open('/proc/1/mountinfo')}
if P['mount'] in mounted: host('/bin/umount',P['mount'])
if os.path.exists('/dev/mapper/'+P['mapper']): host('/usr/sbin/cryptsetup','close',P['mapper'])
def install(source_bytes, target, mode):
    t=target; tmp=t+'.pending'
    if os.path.lexists(tmp): os.unlink(tmp)
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f: f.write(source_bytes); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp,mode); os.rename(tmp,t)
    if hashlib.sha256(open(t,'rb').read()).hexdigest()!=hashlib.sha256(source_bytes).hexdigest(): raise RuntimeError('install readback differs: '+t)
install(bytes.fromhex(P['volume_script_hex']),P['volume_script_target'],0o755)
for unit,hexdata in P['units'].items():
    install(bytes.fromhex(hexdata),'/etc/systemd/system/'+unit,0o644)
r=subprocess.run(['systemd-analyze','verify',*['/etc/systemd/system/'+u for u in P['units']]],capture_output=True,text=True)
if r.returncode!=0: raise RuntimeError('systemd-analyze verify failed: '+r.stderr[-800:])
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable',*P['new_units']],check=True,capture_output=True)
print(json.dumps({'installed':sorted(P['units']),'enabled':P['new_units'],'analyze_warnings':r.stderr.strip()[-400:]}))
'''

ROOT_STATE = r'''
mounted={line.split(' ')[4]:line for line in open('/proc/1/mountinfo')}
def attrs(p):
    r=subprocess.run(['/usr/bin/lsattr','-d',p],capture_output=True,text=True); return r.stdout.split()[0] if r.returncode==0 else ''
def listing(p):
    try: return sorted(os.listdir(p))
    except Exception as e: return ['ERR:'+type(e).__name__]
rep={'mount_mounted':P['mount'] in mounted,'pg_bound':P['pg_data'] in mounted,'state_bound':str(P['state']) in mounted,
     'mapper_present':os.path.exists('/dev/mapper/'+P['mapper']),'marker':os.path.exists(P['mount']+'/.quillmd-fresh-volume') if P['mount'] in mounted else None,
     'pg_data_listing':listing(P['pg_data'])[:5],'state_listing':listing(str(P['state'])),
     'pg_data_attrs':attrs(P['pg_data']),'state_attrs':attrs(str(P['state'])),
     'rollback_present':os.path.isdir(P['rollback']),'units_active':{u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip() for u in P['all_units']},
     'units_enabled':{u:subprocess.run(['systemctl','is-enabled',u],capture_output=True,text=True).stdout.strip() for u in P['new_units']},
     'key_mode':oct(stat.S_IMODE(os.stat(P['key']).st_mode)) if os.path.exists(P['key']) else None,'recovery_present':os.path.exists(P['recovery'])}
if rep['state_bound']:
    rep['state_identity']={n:{'device':os.stat(str(P['state'])+'/'+n).st_dev,'inode':os.stat(str(P['state'])+'/'+n).st_ino} for n in ('files','mail','proofs')}
    s=os.stat(str(P['state'])); rep['state_root']={'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid}
    t=os.stat(str(P['state'])+'/tmp'); rep['tmp']={'mode':oct(stat.S_IMODE(t.st_mode)),'uid':t.st_uid,'gid':t.st_gid}
print(json.dumps(rep))
'''

ROOT_WRITE_PROBE = r'''
# Prove the closed state cannot receive plaintext: creating a file in either target must fail.
res={}
for p in (P['pg_data'],str(P['state'])):
    try:
        fd=os.open(p+'/.plaintext-probe',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd); os.unlink(p+'/.plaintext-probe'); res[p]='WRITABLE'
    except PermissionError: res[p]='refused'
    except Exception as e: res[p]='refused:'+type(e).__name__
print(json.dumps(res))
'''

ROOT_ROLLBACK = r'''
def sh(*cmd, timeout=600):
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if r.returncode!=0: raise RuntimeError(' '.join(cmd[:3])+' failed: '+r.stderr[-800:])
    return r.stdout
mounted={line.split(' ')[4] for line in open('/proc/1/mountinfo')}
for p in (P['pg_data'],str(P['state']),P['mount']):
    if p in mounted: raise RuntimeError('still mounted: '+p)
for p in (P['pg_data'],str(P['state'])):
    sh('/usr/bin/chattr','-i',p)
    if os.listdir(p): raise RuntimeError('bind target is not empty: '+p)
    os.rmdir(p)
os.rename(P['rollback']+'/pg_data',P['pg_data']); os.rename(P['rollback']+'/state',str(P['state']))
for unit,hexdata in P['units'].items():
    t='/etc/systemd/system/'+unit; tmp=t+'.pending'
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,'wb') as f: f.write(bytes.fromhex(hexdata)); f.flush(); os.fsync(f.fileno())
    os.rename(tmp,t)
subprocess.run(['systemctl','disable',*P['new_units']],capture_output=True)
for u in P['new_units']:
    if os.path.exists('/etc/systemd/system/'+u): os.unlink('/etc/systemd/system/'+u)
if os.path.exists(P['volume_script_target']): os.unlink(P['volume_script_target'])
subprocess.run(['systemctl','daemon-reload'],check=True)
print(json.dumps({'restored':True}))
'''


def systemctl_units(action, units, image):
    require(action in ('start', 'stop') and all(re.fullmatch(r'quillmd-fresh-[a-z]+\.service', u) for u in units), 'Only the private QuillMD units may be controlled.')
    code = "subprocess.run(['systemctl'," + repr(action) + ",*" + repr(units) + "],check=True)\nprint(json.dumps({'done':True}))\n"
    return root(code, {}, image, timeout=400)


def unit_states(units):
    return {u: output(['systemctl', 'show', u, '--property=ActiveState', '--value']) for u in units}


def health(target, attempts=60):
    for _ in range(attempts):
        try:
            rows = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
            if all(r.get('release') == target and r.get('data_mode') == 'synthetic-only' for r in rows):
                return rows
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError('Private health did not identify the reviewed synthetic release.')


def container_running():
    return output(['docker', 'inspect', CONTAINER, '--format', '{{.State.Running}}']) == 'true'


def fingerprints(billing):
    return billing.fingerprints(billing.tables(), exclude_new_migration=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    require(not (args.execute and args.rollback), 'Choose --execute or --rollback.')
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    head = output(['git', 'rev-parse', 'HEAD'])
    require(output(['git', 'branch', '--show-current']) == 'main' and output(['git', 'rev-parse', 'origin/main']) == args.target, 'Unexpected origin release.')
    require(head == (args.target if args.rollback else BASELINE), 'Unexpected permanent HEAD for this mode.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target])
    changed = set(output(['git', 'diff', '--name-only', BASELINE, args.target]).splitlines())
    require(changed <= ALLOWED and VOLUME_SCRIPT in changed and 'scripts/migrate-fresh-storage.py' in changed,
            'Target changes paths outside the declared storage set: ' + ', '.join(sorted(changed - ALLOWED)))
    require(subprocess.check_output(['git', 'show', args.target + ':scripts/migrate-fresh-storage.py']) == Path(__file__).read_bytes(), 'Migration script differs from the reviewed target.')
    helpers = {'billing': 'scripts/activate-billing-policy.py', 'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
               'previous': 'scripts/update-private-beta.py', 'storage': 'rebuild/ops/private_storage.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(), 'Reviewed helper changed: ' + relative)
        modules[name] = load('storage_' + name, relative)
    billing, word, identity, previous, storage = (modules[k] for k in ('billing', 'word', 'identity', 'previous', 'storage'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    image = helper_image()
    units = {u: subprocess.check_output(['git', 'show', args.target + ':rebuild/deploy/' + u]) for u in APP_UNITS + NEW_UNITS}
    volume_script = subprocess.check_output(['git', 'show', args.target + ':' + VOLUME_SCRIPT])
    for u in APP_UNITS:
        require(b'Requires=quillmd-fresh-database.service' in units[u] and b'TMPDIR=/var/lib/quillmd/tmp' in units[u]
                and b'InaccessiblePaths=/run/docker.sock' in units[u] and b'User=quillmd-app\n' in units[u], 'Amended app unit lacks the reviewed policy: ' + u)
    require(b'Before=docker.service' in units['quillmd-fresh-volume.service'] and b'BindsTo=quillmd-fresh-volume.service' in units['quillmd-fresh-database.service'], 'New units lack the reviewed ordering.')
    require(volume_script.startswith(b'#!/usr/bin/env bash') and b'set -euo pipefail' in volume_script, 'Volume helper script is not the reviewed form.')
    inspect = json.loads(output(['docker', 'inspect', CONTAINER]))[0]
    mounts = [(m.get('Type'), m.get('Name'), m.get('Source'), m.get('Destination')) for m in inspect['Mounts']]
    require(mounts == [('volume', 'quillmd_fresh_pg', PG_DATA, '/var/lib/postgresql/data')] and inspect['Config']['Image'].startswith('postgres:17')
            and inspect['HostConfig']['PortBindings'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]}, 'Database container identity differs from the recorded one.')
    result_path = Path(args.result)
    lock = PRIVATE / '.fresh-storage-migration.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'fresh-storage-(migration|rollback)-[a-zA-Z0-9_-]+\.json', result_path.name) and not result_path.exists()
            and not result_path.is_symlink() and not lock.exists() and not lock.is_symlink(), 'Choose unused private evidence; a prior lock needs inspection.')
    probe = root(ROOT_PREFLIGHT, {'pg_data': PG_DATA, 'state': str(STATE), 'image': IMAGE, 'key': KEY, 'mount': MOUNT, 'rollback': ROLLBACK,
                                  'mapper': MAPPER, 'volume_script_target': VOLUME_SCRIPT_TARGET, 'new_units': NEW_UNITS}, image)
    require(all(probe['tools'].values()), 'Required host tools are missing: ' + json.dumps(probe['tools']))
    if not args.rollback:
        require(probe['image'] is None and probe['key'] is None and probe['mount'] is None and probe['rollback'] is None and not probe['mapper_present']
                and not probe['pg_data_mounted'] and not probe['state_mounted'] and not probe['volume_script_installed'] and not any(probe['units_installed'].values()),
                'The encrypted volume, its key, mount or units already exist; inspect before continuing.')
        require(probe['pg_data'] and probe['pg_data']['type'] == 'dir' and probe['state'] and probe['state']['mode'] == '0o710'
                and all(v and v['uid'] == 996 and v['gid'] == 988 for v in probe['state_children'].values()), 'Current data directories differ from the recorded layout.')
        require(probe['free_bytes'] >= 24 * 2 ** 30, 'At least 24 GiB free space is required beside the sparse image.')
    else:
        require(probe['rollback'] and probe['rollback']['type'] == 'dir', 'No rollback material is present.')
    backup = previous.validate_restore_report(args.backup_report)
    require(re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}', backup.get('backup_run_id', '')), 'A validated restore proof is required.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Unresolved jobs require inspection.')
    protected = previous.protected()
    retained = word.retained_reports()
    for u in APP_UNITS:
        require((APP / 'deploy' / u).read_bytes() == (Path('/etc/systemd/system') / u).read_bytes(), 'Installed service policy differs from the tree: ' + u)
    env_before = word.checked_file(APP / '.env', private=True)
    release_line = ('QUILLMD_RELEASE_SHA=' + (args.target if args.rollback else BASELINE)).encode()
    require(env_before.splitlines().count(release_line) == 1, 'Expected the environment to name the current release.')
    env_after = re.sub(rb'(?m)^' + re.escape(release_line) + rb'$', ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs)
    identity.verify_live(BASELINE if not args.rollback else args.target, storage)
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Fresh-storage preflight passed: reviewed units and helper, recorded layout, restore proof, no pending jobs, host tools present.', flush=True)
    if not (args.execute or args.rollback):
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECL).name and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL]) == subprocess.check_output(['git', 'show', commit + ':' + DECL]),
            'Committed absolute declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target])
    identity.private_write(lock, {'target': args.target, 'mode': 'rollback' if args.rollback else 'migrate', 'pid': os.getpid()})
    now = datetime.now(timezone.utc).isoformat()
    result = {'complete': False, 'mode': 'rollback' if args.rollback else 'migrate', 'previous_head': head, 'target': args.target, 'started_at': now,
              'provider_calls': 0, 'migration_commands': 0, 'backup_report': args.backup_report, 'helper_image': image, 'stage': 'stopping_private_services'}
    all_units = APP_UNITS + list(reversed(NEW_UNITS))
    try:
        result['database_before'] = fingerprints(billing)
        result['schema_before'] = billing.schema()
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        systemctl_units('stop', APP_UNITS, image)
        require(all(v == 'inactive' for v in unit_states(APP_UNITS).values()), 'Private services did not stop.')
        if args.rollback:
            result['stage'] = 'rollback'
            systemctl_units('stop', ['quillmd-fresh-database.service'], image)
            systemctl_units('stop', ['quillmd-fresh-volume.service'], image)
            require(not container_running(), 'Database container still running.')
            baseline_units = {u: subprocess.check_output(['git', 'show', BASELINE + ':rebuild/deploy/' + u]).hex() for u in APP_UNITS}
            result['rollback'] = root(ROOT_ROLLBACK, {'pg_data': PG_DATA, 'state': str(STATE), 'mount': MOUNT, 'rollback': ROLLBACK, 'units': baseline_units,
                                                     'new_units': NEW_UNITS, 'volume_script_target': VOLUME_SCRIPT_TARGET}, image,
                                     writable=['/var/lib', '/etc/systemd/system', '/usr/local/bin'])
            previous_identity = PRIVATE / 'state-identity.pre-encryption-20260918.json'
            require(previous_identity.is_file(), 'Pre-encryption identity pin missing.')
            (PRIVATE / 'state-identity.json').write_bytes(previous_identity.read_bytes())
            run(['docker', 'update', '--restart=unless-stopped', CONTAINER], stdout=subprocess.DEVNULL)
            run(['docker', 'start', CONTAINER], stdout=subprocess.DEVNULL)
            for _ in range(90):
                if subprocess.run(['docker', 'exec', CONTAINER, 'pg_isready', '-U', 'quillmd_fresh', '-d', 'quillmd_fresh'], capture_output=True).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Database did not become ready after rollback.')
            require(fingerprints(billing) == result['database_before'], 'Rows changed across rollback.')
            systemctl_units('start', APP_UNITS, image)
            result['health'] = health(args.target)
            result['note'] = 'Rolled back to plaintext storage; the encrypted image, key and recovery passphrase were left in place for inspection. Main and the release stamp remain at the target.'
            result.update(complete=True, stage='complete')
            identity.private_write(result_path, result)
            lock.unlink()
            print('Fresh-storage rollback completed: ' + str(result_path), flush=True)
            return
        result['stage'] = 'stopping_database_container'
        run(['docker', 'stop', '-t', '90', CONTAINER], stdout=subprocess.DEVNULL)
        require(not container_running(), 'Database container did not stop.')
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        result['stage'] = 'formatting_encrypted_volume'
        result['prepare'] = root(ROOT_PREPARE, {'key': KEY, 'recovery': RECOVERY, 'image': IMAGE, 'image_bytes': IMAGE_BYTES, 'mount': MOUNT, 'mapper': MAPPER}, image,
                                writable=['/etc/quillmd', '/opt/meddoc-pro/secrets', '/mnt'])
        require(result['prepare']['formatted'] and result['prepare']['key_slots'] == 2, 'LUKS format or key slots differ from the declaration.')
        result['stage'] = 'copying_and_verifying_data'
        result['copy'] = root(ROOT_COPY, {'mount': MOUNT, 'pg_data': PG_DATA, 'state': str(STATE), 'rollback': ROLLBACK, 'uid': 996, 'gid': 988, 'now': now, 'target': args.target}, image,
                             writable=['/mnt', '/var/lib'])
        result['stage'] = 'installing_units_and_helper'
        result['install'] = root(ROOT_INSTALL, {'mount': MOUNT, 'mapper': MAPPER, 'volume_script_hex': volume_script.hex(), 'volume_script_target': VOLUME_SCRIPT_TARGET,
                                                'units': {u: b.hex() for u, b in units.items()}, 'new_units': NEW_UNITS}, image,
                                writable=['/usr/local/bin', '/etc/systemd/system', '/mnt'])
        for u in APP_UNITS + NEW_UNITS:
            require((Path('/etc/systemd/system') / u).read_bytes() == units[u], 'Installed unit readback differs: ' + u)
        run(['docker', 'update', '--restart=no', CONTAINER], stdout=subprocess.DEVNULL)
        result['stage'] = 'repinning_state_identity'
        old_identity = json.loads(word.checked_file(PRIVATE / 'state-identity.json', private=True))
        identity.private_write(PRIVATE / 'state-identity.pre-encryption-20260918.json', old_identity)
        new_identity = dict(old_identity)
        new_identity['roots'] = {f'/var/lib/quillmd/{name}': result['copy']['identity'][name] for name in ('files', 'mail', 'proofs')}
        (PRIVATE / 'state-identity.json').unlink()
        identity.private_write(PRIVATE / 'state-identity.json', new_identity)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('fresh-storage-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        result['stage'] = 'opening_volume_and_database'
        systemctl_units('start', ['quillmd-fresh-volume.service'], image)
        systemctl_units('start', ['quillmd-fresh-database.service'], image)
        state = root(ROOT_STATE, {'mount': MOUNT, 'pg_data': PG_DATA, 'state': str(STATE), 'mapper': MAPPER, 'rollback': ROLLBACK, 'key': KEY, 'recovery': RECOVERY,
                                  'all_units': all_units, 'new_units': NEW_UNITS}, image)
        require(state['mount_mounted'] and state['pg_bound'] and state['state_bound'] and state['marker'] and state['rollback_present']
                and state['state_identity'] == result['copy']['identity'] and state['state_root'] == {'mode': '0o710', 'uid': 0, 'gid': 988}
                and state['tmp'] == {'mode': '0o700', 'uid': 996, 'gid': 988} and state['key_mode'] == '0o400', 'Opened volume state differs from the declaration.')
        result['open_state'] = state
        require(container_running(), 'Database container is not running on the encrypted volume.')
        require(fingerprints(billing) == result['database_before'] and billing.schema() == result['schema_before'], 'Database rows or schema differ after the move.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private files or mail differ after the move.')
        result['stage'] = 'starting_and_verifying_private_services'
        systemctl_units('start', APP_UNITS, image)
        result['health'] = health(args.target)
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        run(['bash', 'scripts/check-cotenants.sh'])
        require(previous.protected() == protected, 'Protected container population changed.')
        result['stage'] = 'unavailability_drill'
        systemctl_units('stop', ['quillmd-fresh-volume.service'], image)
        time.sleep(3)
        closed = root(ROOT_STATE, {'mount': MOUNT, 'pg_data': PG_DATA, 'state': str(STATE), 'mapper': MAPPER, 'rollback': ROLLBACK, 'key': KEY, 'recovery': RECOVERY,
                                   'all_units': all_units, 'new_units': NEW_UNITS}, image)
        require(not closed['mount_mounted'] and not closed['pg_bound'] and not closed['state_bound'] and not closed['mapper_present']
                and all(v == 'inactive' for v in closed['units_active'].values()) and closed['pg_data_listing'] == [] and closed['state_listing'] == []
                and 'i' in closed['pg_data_attrs'] and 'i' in closed['state_attrs'], 'Closed-volume state is not fail-closed: ' + json.dumps(closed))
        require(not container_running(), 'Database container kept running without its volume.')
        result['closed_state'] = closed
        result['closed_write_probe'] = root(ROOT_WRITE_PROBE, {'pg_data': PG_DATA, 'state': str(STATE)}, image, writable=['/var/lib'])
        require(all(v.startswith('refused') for v in result['closed_write_probe'].values()), 'Plaintext write probe succeeded while closed.')
        try:
            output(['curl', '--fail', '--silent', '--max-time', '5', 'http://127.0.0.1:9130/health/'])
            raise RuntimeError('Doctor listener answered while the volume was closed.')
        except subprocess.CalledProcessError:
            pass
        subprocess.run(['docker', 'start', CONTAINER], capture_output=True)
        time.sleep(8)
        probe_after_start = root(ROOT_STATE, {'mount': MOUNT, 'pg_data': PG_DATA, 'state': str(STATE), 'mapper': MAPPER, 'rollback': ROLLBACK, 'key': KEY, 'recovery': RECOVERY,
                                              'all_units': all_units, 'new_units': NEW_UNITS}, image)
        require(probe_after_start['pg_data_listing'] == [], 'A manual container start wrote into the closed database directory.')
        subprocess.run(['docker', 'stop', '-t', '30', CONTAINER], capture_output=True)
        result['manual_container_start_while_closed'] = {'running_after_8s': container_running(), 'pg_data_listing': probe_after_start['pg_data_listing']}
        result['stage'] = 'recovery_after_drill'
        systemctl_units('start', ['quillmd-fresh-volume.service'], image)
        systemctl_units('start', ['quillmd-fresh-database.service'], image)
        systemctl_units('start', APP_UNITS, image)
        result['health_after_recovery'] = health(args.target)
        require(fingerprints(billing) == result['database_before'], 'Rows differ after the recovery drill.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private files differ after the recovery drill.')
        result['proofs_after_recovery'] = identity.verify_live(args.target, storage)
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs) == artifact, 'Word runtime changed.')
        require(word.retained_reports() == retained and previous.protected() == protected, 'Retained or shared resources changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', all_rows_identical=True, all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after),
                      custody={'key': KEY + ' (root 0400, same host; escrow required)', 'recovery_passphrase': RECOVERY + ' (root 0400; move to the owner vault, then shred here)',
                               'image': IMAGE, 'rollback_material': ROLLBACK})
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
        try:
            systemctl_units('stop', APP_UNITS, image)
            result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False
            result['stop_failure_kind'] = type(stop_error).__name__
        if not result_path.exists():
            identity.private_write(result_path, result)
        else:
            identity.private_write(result_path.with_name(result_path.stem + '-publication-failure.json'), result)
        raise
    print('Fresh-storage migration completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
