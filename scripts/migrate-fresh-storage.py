#!/usr/bin/env python3
"""Move the QuillMD fresh database, state and temp files onto a LUKS2 volume; default is read-only preflight.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B scripts/migrate-fresh-storage.py MODE \
        --target FULL_MERGE_SHA --result /opt/meddoc-pro/rebuild/.runtime/fresh-storage-<mode>-<label>.json \
        [--backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json] [--from-result <migration result>] [--execute]

MODE is one of:
  migrate                 copy database and state onto a new encrypted volume, switch, verify, drill, recover
  discard-failed-attempt  after an automatically reverted migrate: remove the partial image, key and mount point
  rollback                after a migrate that reached running services: copy CURRENT data back to plaintext

Without --execute every mode is a read-only preflight. With --execute it runs only through
scripts/run-ruled-mutation.sh with the committed declaration named in DECL.

Design (docs/rebuild/storage-encryption.md). A sparse loop file in a root-only directory holds a LUKS2
container whose ext4 filesystem carries postgres/ and state/. quillmd-fresh-volume.service opens it and
bind-mounts those roots over the docker named-volume directory and /var/lib/quillmd, so the PostgreSQL
container keeps its identity and the application keeps its paths. When the volume is closed both bind
targets are empty, root-owned, immutable directories.

Every privileged action is a HOST process started through systemd-run from the fixed local helper image
(host root bound read-only), so mounts land in the host mount namespace and chattr, rsync and cryptsetup
run with full host capabilities. Until the application starts on the encrypted volume nothing writes to
it, so any failure before that point reverts automatically to the untouched plaintext originals; after
it, failures stop the application and `rollback` copies the current data back.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
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
# Paths that may differ between the running release and the target: the storage change itself, the
# documentation merged since the running release, and the billing-boundary change if it lands first.
STORAGE_PATHS = {'rebuild/deploy/' + u for u in APP_UNITS + NEW_UNITS} | {
    VOLUME_SCRIPT, 'scripts/migrate-fresh-storage.py', 'scripts/verify-post-reboot.sh', 'scripts/ops/unlock-fresh-volume.sh',
    'rebuild/ops/service_launcher.py', 'rebuild/ops/private_storage.py', 'rebuild/ops/backup_restore.py',
    'rebuild/ops/test_storage_migration.py', 'rebuild/ops/test_private_storage.py', 'rebuild/ops/test_service_launcher.py',
    'rebuild/ops/test_backup_restore.py', 'docs/rebuild/storage-encryption.md', DECL}
DOCUMENTATION_PATHS = {'docs/rebuild/CHECKPOINT.md', 'docs/rebuild/owner-actions.md', 'docs/rebuild/patient-data-release-requirements.md',
                       'docs/rebuild/security-readiness.md', 'docs/rebuild/cost-definition.md', 'docs/rebuild/external-verification-runbook.md'}
BILLING_BOUNDARY_PATHS = {'rebuild/core/jobs.py', 'rebuild/core/billing.py', 'rebuild/core/views.py', 'rebuild/quillmd/urls.py',
                          'rebuild/core/management/commands/audit_billing.py', 'rebuild/templates/encounter_detail.html',
                          'rebuild/core/tests/test_billing_boundary.py', 'rebuild/core/tests/test_billing_boundary_regressions.py'}
# The plaintext reap (2026-09-18) removed the pre-migration snapshot after proving it redundant. Its merge is the rollback
# target from then on: rollback copies the current data back from the encrypted volume and never needed the snapshot.
REAP_PATHS = {'scripts/verify-and-reap-fresh-plaintext.py', 'rebuild/ops/test_plaintext_reap.py',
              'docs/foundation/mutations/20260918-quillmd-plaintext-recovery-reap.md', 'rebuild/ops/test_billing_activation.py'}
ALLOWED = STORAGE_PATHS | DOCUMENTATION_PATHS | BILLING_BOUNDARY_PATHS | REAP_PATHS
# The target the completed act migrated (fresh-storage-migrate-20260918b.json).
MIGRATED = '3eac783a55b6b771016da258ab2b57e0a06bdb38'
# Helpers the target changes are materialised from the target commit; the rest must equal the tree.
TARGET_HELPERS = {'storage': 'rebuild/ops/private_storage.py'}
TREE_HELPERS = {'billing': 'scripts/activate-billing-policy.py', 'word': 'scripts/activate-word-beta.py',
                'identity': 'scripts/activate-os-identity.py', 'previous': 'scripts/update-private-beta.py'}
CONTAINER = 'quillmd-fresh-postgres'
IMAGE_DIR = '/var/lib/quillmd-encrypted'
IMAGE = IMAGE_DIR + '/quillmd-fresh.luks'
KEY = '/etc/quillmd/quillmd-fresh-luks.key'
RECOVERY = '/etc/quillmd/quillmd-fresh-luks.recovery-passphrase'
MAPPER = 'quillmd-fresh-encrypted'
MOUNT = '/mnt/quillmd-fresh-encrypted'
PG_DATA = '/var/lib/docker/volumes/quillmd_fresh_pg/_data'
ROLLBACK = '/var/lib/quillmd-rollback-20260918'
IMAGE_BYTES = 16 * 2 ** 30
LUKS_FORMAT = ['--type', 'luks2', '--cipher', 'aes-xts-plain64', '--key-size', '512', '--hash', 'sha256',
               '--pbkdf', 'argon2id', '--pbkdf-memory', '262144', '--iter-time', '2000']
ORIGINAL_MEMORY = (402653184, 805306368)
APP_UID, APP_GID = 996, 988
POST_START_STAGES = ('advancing_reviewed_main', 'starting_private_services_on_encrypted_volume', 'archiving_database_container_log', 'unavailability_drill', 'recovery_after_drill', 'final_checks', 'complete')
PSQL = ['docker', 'exec', CONTAINER, 'psql', '-U', 'quillmd_fresh', '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


class Terminated(BaseException):
    """SIGTERM from the ruled-mutation watchdog: run the failure handler instead of dying silently."""


def _terminate(signum, frame):
    raise Terminated('signal %d' % signum)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


# Every external command is bounded well inside the watchdog ceiling, so a hang surfaces as an ordinary exception that the
# revert handles with time to spare, instead of as the watchdog's SIGTERM followed 15 s later by SIGKILL.
COMMAND_TIMEOUT = 600
PHASE_ONE_BUDGET = 1800
PHASE_ONE_STAGES = ('stopping_private_services', 'capturing_baseline', 'stopping_database_container', 'formatting_encrypted_volume',
                    'copying_and_verifying_data', 'switching_to_immutable_bind_targets', 'installing_units_and_helper',
                    'repinning_state_identity', 'opening_volume_and_database', 'suppressing_statement_logging',
                    'verifying_data_on_encrypted_volume', 'advancing_reviewed_main')
ACT = {'started': None, 'progress': None, 'step': None, 'steps': 0}


def output(command, **kwargs):
    kwargs.setdefault('timeout', COMMAND_TIMEOUT)
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    kwargs.setdefault('timeout', COMMAND_TIMEOUT)
    return subprocess.run(command, check=True, **kwargs)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stage(result, name):
    if name in PHASE_ONE_STAGES and ACT['started'] is not None and time.monotonic() - ACT['started'] > PHASE_ONE_BUDGET:
        raise RuntimeError(f'Phase-one budget of {PHASE_ONE_BUDGET}s exhausted before {name}; reverting while time remains.')
    result['stage'] = name
    result.setdefault('stages', []).append({'stage': name, 'at': datetime.now(timezone.utc).isoformat()})
    print(f"[fresh-storage] {datetime.now(timezone.utc).strftime('%H:%M:%SZ')} stage={name}", flush=True)
    write_progress(result)


def write_progress(result):
    """Record every stage as it starts, so a run killed outright (SIGKILL) still says how far it got."""
    path = ACT['progress']
    if path is None:
        return
    pending = path.with_name(path.name + '.pending')
    fd = os.open(pending, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(result, stream, indent=1, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def migrate_alive(pid):
    """True when the pid recorded in the migrate lock is still this migration (a reused pid running something else is not)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        cmdline = Path(f'/proc/{pid}/cmdline').read_bytes()
    except OSError:
        return False
    return b'migrate-fresh-storage.py' in cmdline


def running_root_steps():
    """Names of root-step containers still running, whichever process started them."""
    listing = subprocess.run(['docker', 'ps', '--filter', 'name=quillmd-fresh-storage-step-', '--format', '{{.Names}}'],
                             capture_output=True, text=True, timeout=60)
    require(listing.returncode == 0, 'Could not list running root-step containers.')
    return [name for name in listing.stdout.split() if name.startswith('quillmd-fresh-storage-step-')]


def settle_root_step(result):
    """A root step's container keeps running when its docker client is killed. Before any revert or rollback touches the host,
    wait for the in-flight step to end, and stop it only if it will not."""
    name = ACT['step']
    if not name:
        return
    state = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', name], capture_output=True, text=True, timeout=60)
    if state.returncode != 0 or state.stdout.strip() != 'true':
        ACT['step'] = None
        return
    try:
        subprocess.run(['docker', 'wait', name], capture_output=True, timeout=300)
        outcome = 'finished'
    except subprocess.TimeoutExpired:
        subprocess.run(['docker', 'kill', name], capture_output=True, timeout=60)
        outcome = 'killed'
    result.setdefault('settled_root_steps', []).append({'container': name, 'outcome': outcome})
    ACT['step'] = None


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialise(target, relative):
    """Write a target helper to a private file so inspect.getsource keeps working, then import it."""
    directory = PRIVATE / 'fresh-storage-helpers'
    if not directory.exists():
        directory.mkdir(mode=0o700)
    require(directory.stat().st_uid == os.getuid() and stat.S_IMODE(directory.stat().st_mode) == 0o700, 'Helper directory must stay private.')
    data = subprocess.check_output(['git', 'show', target + ':' + relative])
    path = directory / (target[:12] + '-' + Path(relative).name)
    if path.exists():
        require(path.read_bytes() == data, 'A materialised helper differs from the target.')
    else:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    return load_file('fresh_storage_target_' + Path(relative).stem, path)


def helper_image():
    image = output(['docker', 'image', 'inspect', 'python:3-slim', '--format', '{{.Id}}'])
    require(re.fullmatch('sha256:[a-f0-9]{64}', image), 'The fixed local helper image must already exist.')
    return image


# Every module a root step uses is imported HERE, before the chroot: afterwards the helper image's standard library is no
# longer on the filesystem, so a late import fails (attempt 1 of the act stopped on exactly that, `import secrets`).
ROOT_LIBRARY = r'''
import os,sys,json,subprocess,stat,hashlib,time,secrets
P=json.loads(sys.stdin.readline())
os.chroot('/host');os.chdir('/');os.umask(0o077)
def host(*cmd, stdin=None, check=True, timeout=600):
    r=subprocess.run(['systemd-run','--wait','--pipe','--collect','--quiet','--property=Type=oneshot',*cmd],input=stdin,capture_output=True,text=True,timeout=timeout)
    if check and r.returncode!=0: raise RuntimeError('host command failed: '+' '.join(cmd[:4])+' :: '+r.stderr[-600:])
    return r
def mounts():
    return {line.split(' ')[4] for line in open('/proc/1/mountinfo')}
def attrs(path):
    r=host('/usr/bin/lsattr','-d',path,check=False); return r.stdout.split()[0] if r.returncode==0 and r.stdout.strip() else ''
def census(root):
    files=0;size=0;h=hashlib.sha256()
    for d,dirs,fs in os.walk(root):
        dirs.sort();fs.sort()
        for f in fs:
            p=os.path.join(d,f);s=os.lstat(p)
            if stat.S_ISREG(s.st_mode):
                files+=1;size+=s.st_size;h.update(os.path.relpath(p,root).encode()+b'\0')
                with open(p,'rb') as fh:
                    for chunk in iter(lambda: fh.read(1<<20), b''): h.update(chunk)
    return {'files':files,'bytes':size,'content_sha256':h.hexdigest()}
def copy_verified(source,destination):
    host('/usr/bin/rsync','-aHAX','--numeric-ids',source+'/',destination+'/')
    diff=host('/usr/bin/rsync','-aHAXn','--numeric-ids','--checksum','--delete','--itemize-changes',source+'/',destination+'/').stdout
    if diff.strip(): raise RuntimeError('copy verification reported differences')
    a,b=census(source),census(destination)
    if a!=b: raise RuntimeError('census differs after copy')
    return b
def state_identity(root):
    return {n:os.stat(root+'/'+n).st_ino for n in ('files','mail','proofs')}
def emit(value): print(json.dumps(value))
'''

ROOT_PROBE = r'''
def st(p):
    try:
        s=os.lstat(p); return {'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid,'type':'dir' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'other'}
    except FileNotFoundError: return None
m=mounts(); free=os.statvfs('/var/lib'); r=host('/usr/bin/id','-u',check=False)
emit({'systemd_run_root':r.returncode==0 and r.stdout.strip()=='0','pg_data':st(P['pg_data']),'state':st(P['state']),
      'state_children':{n:st(P['state']+'/'+n) for n in ('files','mail','proofs','tmp')},
      'image_dir':st(P['image_dir']),'image':st(P['image']),'key':st(P['key']),'recovery':st(P['recovery']),'mount':st(P['mount']),
      'rollback':st(P['rollback']),'pg_data_mounted':P['pg_data'] in m,'state_mounted':P['state'] in m,'mount_mounted':P['mount'] in m,
      'mapper_present':os.path.exists('/dev/mapper/'+P['mapper']),'free_bytes':free.f_bavail*free.f_frsize,
      'pg_data_attrs':attrs(P['pg_data']) if os.path.isdir(P['pg_data']) else '','state_attrs':attrs(P['state']) if os.path.isdir(P['state']) else '',
      'tools':{t:os.access(t,os.X_OK) for t in ('/usr/sbin/cryptsetup','/usr/sbin/mkfs.ext4','/usr/bin/rsync','/usr/bin/chattr','/usr/bin/lsattr','/usr/bin/systemd-run','/usr/bin/mountpoint','/usr/bin/findmnt','/usr/bin/truncate')},
      'volume_script_installed':os.path.exists(P['volume_script_target']),'units_installed':{u:os.path.exists('/etc/systemd/system/'+u) for u in P['new_units']},
      'log_path_bytes':os.path.getsize(P['log_path']) if os.path.exists(P['log_path']) else None})
'''

ROOT_PREPARE = r'''
for p in (P['key'],P['recovery'],P['image'],P['image_dir'],P['mount']):
    if os.path.lexists(p): raise RuntimeError('already exists: '+p)
os.mkdir(P['image_dir'],0o700)
fd=os.open(P['key'],os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'wb') as f: f.write(os.urandom(64)); f.flush(); os.fsync(f.fileno())
phrase=secrets.token_urlsafe(36)
fd=os.open(P['recovery'],os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'w') as f: f.write(phrase); f.flush(); os.fsync(f.fileno())
fd=os.open(P['image'],os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
os.ftruncate(fd,P['image_bytes']); os.close(fd)
os.mkdir(P['mount'],0o700)
host('/usr/sbin/cryptsetup','-q',*P['luks_format'],'--key-file',P['key'],'luksFormat',P['image'])
host('/usr/sbin/cryptsetup','--pbkdf','argon2id','--pbkdf-memory','262144','--key-file',P['key'],'luksAddKey',P['image'],P['recovery'])
typed=host('/usr/sbin/cryptsetup','open','--test-passphrase','--key-slot','1',P['image'],stdin=phrase+'\n',check=False).returncode
wrong=host('/usr/sbin/cryptsetup','open','--test-passphrase','--key-slot','1',P['image'],stdin=phrase+'x\n',check=False).returncode
slot0=host('/usr/sbin/cryptsetup','open','--test-passphrase','--key-slot','0','--key-file',P['key'],P['image'],check=False).returncode
if typed!=0 or wrong==0 or slot0!=0: raise RuntimeError('key slot verification failed')
del phrase
dump=host('/usr/sbin/cryptsetup','luksDump',P['image']).stdout
host('/usr/sbin/cryptsetup','open','--key-file',P['key'],P['image'],P['mapper'])
host('/usr/sbin/mkfs.ext4','-q','-L','quillmd-fresh','/dev/mapper/'+P['mapper'])
host('/bin/mount','-o','nodev,nosuid','/dev/mapper/'+P['mapper'],P['mount'])
os.chmod(P['mount'],0o700)
lines=[' '.join(l.split()) for l in dump.splitlines()]
def picked(prefix): return sorted({l for l in lines if l.startswith(prefix)})
# 'cipher:' (lower case) is the data segment; 'Key:' is the volume key; 'Cipher:'/'Cipher key:' belong to the key slots.
emit({'formatted':True,'slots':[l for l in lines if l in ('0: luks2','1: luks2')],'typed_passphrase_opens_slot1':typed==0,'wrong_passphrase_refused':wrong!=0,
      'keyfile_opens_slot0':slot0==0,'segment_cipher':picked('cipher:'),'volume_key':picked('Key:'),'keyslot_cipher':picked('Cipher:'),
      'keyslot_key':picked('Cipher key:'),'pbkdf':picked('PBKDF:'),'version':picked('Version:')})
'''

ROOT_COPY = r'''
M=P['mount']
if M not in mounts(): raise RuntimeError('encrypted volume is not mounted in the host namespace')
for d in ('postgres','state','archive'):
    if os.path.lexists(M+'/'+d): raise RuntimeError('volume not empty: '+d)
os.mkdir(M+'/postgres',0o700); os.mkdir(M+'/state',0o710); os.mkdir(M+'/archive',0o700)
pg=copy_verified(P['pg_data'],M+'/postgres')
st=copy_verified(P['state'],M+'/state')
if not os.path.isdir(M+'/state/tmp'):
    os.mkdir(M+'/state/tmp',0o700)
os.chown(M+'/state/tmp',P['uid'],P['gid']); os.chmod(M+'/state/tmp',0o700)
s=os.stat(M+'/state')
if (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))!=(0,P['gid'],0o710): raise RuntimeError('state root attributes differ after copy')
fd=os.open(M+'/.quillmd-fresh-volume',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'w') as f: json.dump({'created':P['now'],'source_commit':P['target'],'roots':['postgres','state']},f); f.flush(); os.fsync(f.fileno())
emit({'copied':True,'pg':pg,'state':st,'inodes':state_identity(M+'/state')})
'''

ROOT_ARCHIVE_LOG = r'''
src=P['log_path']; M=P['mount']
if M not in mounts(): raise RuntimeError('encrypted volume is not mounted')
data=open(src,'rb').read() if os.path.exists(src) else b''
dest=M+'/archive/postgres-container-log-'+P['stamp']+'.jsonl'
fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
if hashlib.sha256(open(dest,'rb').read()).hexdigest()!=hashlib.sha256(data).hexdigest(): raise RuntimeError('log archive differs')
if data: host('/usr/bin/truncate','-s','0',src)
emit({'archived_bytes':len(data),'archived_lines':data.count(b'\n'),'statement_lines':data.count(b'STATEMENT:'),'detail_lines':data.count(b'DETAIL:'),
      'archive_sha256':hashlib.sha256(data).hexdigest(),'container_log_bytes_after':os.path.getsize(src) if os.path.exists(src) else None})
'''

ROOT_SWITCH = r'''
if os.path.lexists(P['rollback']): raise RuntimeError('rollback directory already exists')
if P['pg_data'] in mounts() or P['state'] in mounts(): raise RuntimeError('a target is already mounted')
os.mkdir(P['rollback'],0o700)
os.rename(P['pg_data'],P['rollback']+'/pg_data'); os.mkdir(P['pg_data'],0o700)
os.rename(P['state'],P['rollback']+'/state'); os.mkdir(P['state'],0o710); os.chown(P['state'],0,P['gid']); os.chmod(P['state'],0o710)
host('/usr/bin/chattr','+i',P['pg_data']); host('/usr/bin/chattr','+i',P['state'])
emit({'switched':True,'pg_data_attrs':attrs(P['pg_data']),'state_attrs':attrs(P['state']),'pg_data_empty':os.listdir(P['pg_data'])==[],'state_empty':os.listdir(P['state'])==[]})
'''

ROOT_INSTALL = r'''
def install(data, target, mode):
    tmp=target+'.quillmd-pending'
    if os.path.lexists(tmp): raise RuntimeError('pending file exists: '+tmp)
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp,mode); os.rename(tmp,target)
    if open(target,'rb').read()!=data: raise RuntimeError('install readback differs: '+target)
install(bytes.fromhex(P['volume_script_hex']),P['volume_script_target'],0o755)
for unit,hexdata in P['units'].items(): install(bytes.fromhex(hexdata),'/etc/systemd/system/'+unit,0o644)
# On the host: inside this chroot / is read-only and systemd-analyze cannot set up its working directory.
r=host('/usr/bin/systemd-analyze','verify',*['/etc/systemd/system/'+u for u in P['units']],check=False)
if r.returncode!=0: raise RuntimeError('systemd-analyze verify failed: '+r.stderr[-600:])
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable',*P['new_units']],check=True,capture_output=True)
emit({'installed':sorted(P['units']),'enabled':P['new_units']})
'''

ROOT_STATE = r'''
m=mounts()
def listing(p):
    try: return sorted(os.listdir(p))
    except Exception as e: return ['ERR:'+type(e).__name__]
rep={'mount_mounted':P['mount'] in m,'pg_bound':P['pg_data'] in m,'state_bound':P['state'] in m,'mapper_present':os.path.exists('/dev/mapper/'+P['mapper']),
     'marker':os.path.exists(P['mount']+'/.quillmd-fresh-volume') if P['mount'] in m else None,
     'pg_data_listing':listing(P['pg_data'])[:5],'state_listing':listing(P['state']),
     'pg_data_attrs':'' if P['pg_data'] in m else attrs(P['pg_data']),'state_attrs':'' if P['state'] in m else attrs(P['state']),
     'units_active':{u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip() for u in P['all_units']},
     'key_mode':oct(stat.S_IMODE(os.stat(P['key']).st_mode)) if os.path.exists(P['key']) else None,
     'recovery_mode':oct(stat.S_IMODE(os.stat(P['recovery']).st_mode)) if os.path.exists(P['recovery']) else None}
if rep['state_bound']:
    rep['inodes']=state_identity(P['state'])
    s=os.stat(P['state']); rep['state_root']={'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid}
    t=os.stat(P['state']+'/tmp'); rep['tmp']={'mode':oct(stat.S_IMODE(t.st_mode)),'uid':t.st_uid,'gid':t.st_gid}
    rep['device_matches_mapper']=os.stat(P['state']+'/files').st_dev==os.stat('/dev/mapper/'+P['mapper']).st_rdev
emit(rep)
'''

ROOT_WRITE_PROBE = r'''
res={}
for p in (P['pg_data'],P['state']):
    r=host('/usr/bin/touch',p+'/.plaintext-probe',check=False)
    res[p]='refused' if r.returncode!=0 else 'WRITABLE'
    if r.returncode==0: host('/usr/bin/rm','-f',p+'/.plaintext-probe',check=False)
emit(res)
'''

ROOT_REVERT = r'''
# Automatic revert before the application ever ran on the encrypted volume: the originals are untouched.
m=mounts(); done=[]
for p in (P['state'],P['pg_data']):
    if p in m: host('/bin/umount',p); done.append('umount '+p)
if P['mount'] in mounts(): host('/bin/umount',P['mount']); done.append('umount mount')
if os.path.exists('/dev/mapper/'+P['mapper']): host('/usr/sbin/cryptsetup','close',P['mapper']); done.append('close mapper')
for name,target in (('pg_data',P['pg_data']),('state',P['state'])):
    saved=P['rollback']+'/'+name
    if os.path.isdir(saved):
        if os.path.isdir(target):
            host('/usr/bin/chattr','-i',target,check=False)
            if os.listdir(target): raise RuntimeError('target not empty during revert: '+target)
            os.rmdir(target)
        os.rename(saved,target); done.append('restored '+name)
if os.path.isdir(P['rollback']) and not os.listdir(P['rollback']): os.rmdir(P['rollback']); done.append('removed empty rollback dir')
if P['units_installed']:
    for unit,hexdata in P['baseline_units'].items():
        t='/etc/systemd/system/'+unit; tmp=t+'.quillmd-pending'
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
        os.fchmod(fd,0o644)
        with os.fdopen(fd,'wb') as f: f.write(bytes.fromhex(hexdata)); f.flush(); os.fsync(f.fileno())
        os.rename(tmp,t)
    subprocess.run(['systemctl','disable',*P['new_units']],capture_output=True)
    for u in P['new_units']:
        if os.path.exists('/etc/systemd/system/'+u): os.unlink('/etc/systemd/system/'+u)
    if os.path.exists(P['volume_script_target']): os.unlink(P['volume_script_target'])
    subprocess.run(['systemctl','daemon-reload'],check=True); done.append('baseline units restored')
emit({'reverted':True,'actions':done})
'''

ROOT_DISCARD = r'''
if os.path.lexists(P['rollback']): raise RuntimeError('rollback material exists; this is not an automatically reverted attempt')
m=mounts()
for p in (P['pg_data'],P['state']):
    if p in m: raise RuntimeError('a target is still bound: '+p)
if P['mount'] in m: host('/bin/umount',P['mount'])
if os.path.exists('/dev/mapper/'+P['mapper']): host('/usr/sbin/cryptsetup','close',P['mapper'])
removed=[]
for p in (P['image'],P['key'],P['recovery']):
    if os.path.exists(p): host('/usr/bin/shred','-u','-n','1','-z',p) if p!=P['image'] else os.unlink(p); removed.append(p)
for d in (P['mount'],P['image_dir']):
    if os.path.isdir(d): os.rmdir(d); removed.append(d)
emit({'discarded':removed})
'''

ROOT_COPY_BACK = r'''
M=P['mount']; S=P['staging']
if M not in mounts(): raise RuntimeError('encrypted volume is not mounted')
if os.path.lexists(S): raise RuntimeError('staging exists')
os.mkdir(S,0o700); os.mkdir(S+'/pg_data',0o700); os.mkdir(S+'/state',0o710)
pg=copy_verified(M+'/postgres',S+'/pg_data'); st=copy_verified(M+'/state',S+'/state')
emit({'copied_back':True,'pg':pg,'state':st})
'''

ROOT_SWITCH_BACK = r'''
S=P['staging']; m=mounts()
for p in (P['pg_data'],P['state'],P['mount']):
    if p in m: raise RuntimeError('still mounted: '+p)
for name,target in (('pg_data',P['pg_data']),('state',P['state'])):
    host('/usr/bin/chattr','-i',target)
    if os.listdir(target): raise RuntimeError('bind target not empty: '+target)
    os.rmdir(target); os.rename(S+'/'+name,target)
os.rmdir(S)
for unit,hexdata in P['plaintext_units'].items():
    t='/etc/systemd/system/'+unit; tmp=t+'.quillmd-pending'
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
    os.fchmod(fd,0o644)
    with os.fdopen(fd,'wb') as f: f.write(bytes.fromhex(hexdata)); f.flush(); os.fsync(f.fileno())
    os.rename(tmp,t)
subprocess.run(['systemctl','disable',*P['new_units']],capture_output=True)
for u in P['new_units']:
    if os.path.exists('/etc/systemd/system/'+u): os.unlink('/etc/systemd/system/'+u)
if os.path.exists(P['volume_script_target']): os.unlink(P['volume_script_target'])
subprocess.run(['systemctl','daemon-reload'],check=True)
ino={n:{'device':os.stat(P['state']+'/'+n).st_dev,'inode':os.stat(P['state']+'/'+n).st_ino} for n in ('files','mail','proofs')}
emit({'switched_back':True,'identity':ino})
'''


def root(code, params, image, *, writable=(), timeout=900):
    """Run one root step: host root bound read-only plus explicit writable binds; its result is the last JSON line."""
    # The program travels as an argument and the parameters on stdin: with `python -` CPython would read ALL of stdin as the
    # program. Every bind is rslave so a host unmount reaches this container's copy; a private copy would keep the
    # encrypted filesystem mounted here and make the host's `cryptsetup close` fail with "device in use".
    ACT['steps'] += 1
    name = f'quillmd-fresh-storage-step-{os.getpid()}-{ACT["steps"]}'
    args = ['docker', 'run', '--rm', '-i', '--name', name, '--pull=never', '--network=none', '--pid=host',
            '--security-opt', 'apparmor=unconfined', '--mount', 'type=bind,src=/,dst=/host,readonly,bind-propagation=rslave']
    for path in writable:
        args += ['--mount', f'type=bind,src={path},dst=/host{path},bind-propagation=rslave']
    args += [image, 'python', '-B', '-c', ROOT_LIBRARY + code]
    ACT['step'] = name
    result = subprocess.run(args, input=json.dumps(params) + '\n', text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    ACT['step'] = None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    require(result.returncode == 0 and lines, 'Root step failed: ' + result.stderr[-1500:])
    return json.loads(lines[-1])


def systemctl(action, units, image):
    require(action in ('start', 'stop') and all(re.fullmatch(r'quillmd-fresh-[a-z]+\.service', u) for u in units), 'Only the private QuillMD units may be controlled.')
    code = "subprocess.run(['systemctl'," + repr(action) + ",*" + repr(list(units)) + "],check=True)\nemit({'done':True})\n"
    return root(code, {}, image, timeout=600)


def unit_states(units):
    return {u: output(['systemctl', 'show', u, '--property=ActiveState', '--value']) for u in units}


def container_running():
    return output(['docker', 'inspect', CONTAINER, '--format', '{{.State.Running}}']) == 'true'


def wait_database():
    for _ in range(120):
        try:
            if subprocess.run(['docker', 'exec', CONTAINER, 'pg_isready', '-U', 'quillmd_fresh', '-d', 'quillmd_fresh'], capture_output=True, timeout=15).returncode == 0:
                return
        except subprocess.TimeoutExpired:
            pass  # One slow probe on a loaded host is not a failure; keep polling within the loop's bound.
        time.sleep(1)
    raise RuntimeError('Database did not become ready.')


def health(release, attempts=90):
    for _ in range(attempts):
        try:
            rows = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
            if all(r.get('release') == release and r.get('data_mode') == 'synthetic-only' for r in rows):
                return rows
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError('Private health did not identify the expected synthetic release.')


def listener_answers():
    return subprocess.run(['curl', '--silent', '--max-time', '5', 'http://127.0.0.1:9130/health/'], capture_output=True).returncode == 0


def plaintext_units(units):
    """Application units for plaintext operation after a rollback: the target units minus the encrypted-database dependency."""
    result = {}
    for name in APP_UNITS:
        text = units[name].decode()
        require(text.count('\nRequires=quillmd-fresh-database.service\n') == 1 and text.count(' quillmd-fresh-database.service\n') == 1,
                'Unexpected unit shape: ' + name)
        text = text.replace('\nRequires=quillmd-fresh-database.service\n', '\n').replace(' quillmd-fresh-database.service\n', '\n')
        require('quillmd-fresh-database' not in text and 'TMPDIR=/var/lib/quillmd/tmp' in text, 'Plaintext unit transform failed: ' + name)
        result[name] = text.encode()
    return result


def protected_identity(previous):
    """The protected shared population by identity only; the fresh database may be stopped during this act."""
    baseline = json.loads((ROOT / 'docs/rebuild/activation-baseline.json').read_text())
    rows = json.loads(output(['docker', 'inspect', *[r['name'].lstrip('/') for r in baseline['containers']]]))
    for want, got in zip(baseline['containers'], rows):
        require(want['id'] == got['Id'] and want['image'] == got['Image'], 'A protected container identity changed.')
        require(sorted((m['source'], m['destination']) for m in want['mounts']) == sorted((m['Source'], m['Destination']) for m in got['Mounts']),
                'A protected mount changed.')
        if want['name'].lstrip('/') != CONTAINER:
            require(got['State']['Running'], 'A shared protected container stopped.')
    return len(rows)


def write_pin(identity, document):
    path = PRIVATE / 'state-identity.json'
    staging = PRIVATE / 'state-identity.json.fresh-storage-pending'
    if staging.exists():
        staging.unlink()
    identity.private_write(staging, document)
    os.replace(staging, path)
    require(stat.S_IMODE(path.stat().st_mode) == 0o600, 'Identity pin must stay private.')


def retained_unchanged(before):
    """Every report retained before the act is still present and byte-identical. Reports that other sessions add during the
    act (for example a preflight report) are allowed: they cannot have been changed by the act, and must not stop it."""
    for name, row in before.items():
        path = ROOT / name
        try:
            info = path.lstat()
            data = path.read_bytes()
        except OSError:
            return False
        if not stat.S_ISREG(info.st_mode) or sha(data) != row['sha256'] or len(data) != row['size'] or stat.S_IMODE(info.st_mode) != row['mode']:
            return False
    return True


def rollback_source_ok(source, target, contains):
    """The source is a migrate result whose application ran on the encrypted volume, and the rollback target is that
    migration's own target or, for the completed migration, a later reviewed commit that contains it (the reap merge: its
    script no longer needs the removed snapshot, and main may have moved on)."""
    if source.get('mode') != 'migrate' or source.get('stage') not in POST_START_STAGES:
        return False
    if source.get('target') == target:
        return True
    return source.get('target') == MIGRATED and source.get('complete') is True and contains(MIGRATED, target)


def params_common():
    return {'pg_data': PG_DATA, 'state': str(STATE), 'image_dir': IMAGE_DIR, 'image': IMAGE, 'key': KEY, 'recovery': RECOVERY,
            'mount': MOUNT, 'mapper': MAPPER, 'rollback': ROLLBACK, 'volume_script_target': VOLUME_SCRIPT_TARGET,
            'new_units': NEW_UNITS, 'all_units': APP_UNITS + NEW_UNITS}


def main():
    signal.signal(signal.SIGTERM, _terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['migrate', 'revert-interrupted', 'discard-failed-attempt', 'rollback'])
    parser.add_argument('--target', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--backup-report')
    parser.add_argument('--from-result')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    require(output(['git', 'branch', '--show-current']) == 'main', 'Shared tree must stay on main.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    head = output(['git', 'rev-parse', 'HEAD'])
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target])
    if args.mode == 'migrate':
        require(head == BASELINE and output(['git', 'rev-parse', 'origin/main']) == args.target, 'Migrate runs from the running release toward the cited origin target.')
    elif args.mode in ('discard-failed-attempt', 'revert-interrupted'):
        require(head == BASELINE, 'An automatically reverted or interrupted attempt leaves main at the running release.')
    else:
        require(subprocess.run(['git', 'merge-base', '--is-ancestor', args.target, head]).returncode == 0, 'Rollback needs main to contain the target.')
    changed = set(output(['git', 'diff', '--name-only', BASELINE, args.target]).splitlines())
    require(changed <= ALLOWED and VOLUME_SCRIPT in changed and 'scripts/migrate-fresh-storage.py' in changed,
            'Target changes paths outside the declared set: ' + ', '.join(sorted(changed - ALLOWED)))
    require(subprocess.check_output(['git', 'show', args.target + ':scripts/migrate-fresh-storage.py']) == Path(__file__).read_bytes(),
            'Migration script differs from the reviewed target.')
    modules = {}
    for name, relative in TREE_HELPERS.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(), 'Reviewed helper changed: ' + relative)
        modules[name] = load_file('fresh_storage_' + name, ROOT / relative)
    billing, word, identity, previous = (modules[k] for k in ('billing', 'word', 'identity', 'previous'))
    target_storage = materialise(args.target, TARGET_HELPERS['storage'])
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    image = helper_image()
    units = {u: subprocess.check_output(['git', 'show', args.target + ':rebuild/deploy/' + u]) for u in APP_UNITS + NEW_UNITS}
    baseline_units = {u: subprocess.check_output(['git', 'show', BASELINE + ':rebuild/deploy/' + u]) for u in APP_UNITS}
    volume_script = subprocess.check_output(['git', 'show', args.target + ':' + VOLUME_SCRIPT])
    for u in APP_UNITS:
        for needle in (b'Requires=quillmd-fresh-database.service', b'Environment=TMPDIR=/var/lib/quillmd/tmp', b'LimitCORE=0', b'MemorySwapMax=0',
                       b'InaccessiblePaths=/run/docker.sock', b'User=quillmd-app\n', b'/var/lib/quillmd/tmp\n'):
            require(needle in units[u], 'Amended app unit lacks the reviewed policy: ' + u)
    require(b'Before=docker.service' not in units['quillmd-fresh-volume.service'] and b'TimeoutStartSec=' in units['quillmd-fresh-volume.service']
            and b'BindsTo=quillmd-fresh-volume.service' in units['quillmd-fresh-database.service'], 'New units lack the reviewed ordering.')
    require(volume_script.startswith(b'#!/usr/bin/env bash') and b'set -euo pipefail' in volume_script, 'Volume helper is not the reviewed form.')
    inspect = json.loads(output(['docker', 'inspect', CONTAINER]))[0]
    require([(m.get('Type'), m.get('Name'), m.get('Source'), m.get('Destination')) for m in inspect['Mounts']]
            == [('volume', 'quillmd_fresh_pg', PG_DATA, '/var/lib/postgresql/data')] and inspect['Config']['Image'].startswith('postgres:17')
            and inspect['HostConfig']['PortBindings'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]},
            'Database container identity differs from the recorded one.')
    log_path = inspect['LogPath']
    require(re.fullmatch(r'/var/lib/docker/containers/[a-f0-9]{64}/[a-f0-9]{64}-json\.log', log_path), 'Unexpected container log path.')
    result_path = Path(args.result)
    locks = {'migrate': PRIVATE / '.fresh-storage-migration.lock', 'discard-failed-attempt': PRIVATE / '.fresh-storage-discard.lock',
             'rollback': PRIVATE / '.fresh-storage-rollback.lock', 'revert-interrupted': PRIVATE / '.fresh-storage-revert.lock'}
    lock = locks[args.mode]
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'fresh-storage-(migrate|revert|discard|rollback)-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink() and not lock.exists() and not lock.is_symlink(),
            'Choose unused private evidence; a prior lock for this mode needs inspection.')
    common = params_common()
    probe = root(ROOT_PROBE, dict(common, log_path=log_path), image)
    require(probe['systemd_run_root'] and all(probe['tools'].values()), 'Host command execution or tools unavailable: ' + json.dumps(probe['tools']))
    if args.mode == 'migrate':
        require(all(probe[k] is None for k in ('image_dir', 'image', 'key', 'recovery', 'mount', 'rollback')) and not probe['mapper_present']
                and not probe['pg_data_mounted'] and not probe['state_mounted'] and not probe['volume_script_installed']
                and not any(probe['units_installed'].values()) and 'i' not in probe['pg_data_attrs'] and 'i' not in probe['state_attrs'],
                'Encrypted-volume artifacts already exist; inspect or discard them first.')
        require(probe['pg_data'] and probe['pg_data']['type'] == 'dir' and probe['state'] and probe['state']['mode'] == '0o710'
                and all(probe['state_children'][n] and probe['state_children'][n]['uid'] == APP_UID for n in ('files', 'mail', 'proofs')),
                'Current data directories differ from the recorded layout.')
        require(probe['free_bytes'] >= 24 * 2 ** 30, 'At least 24 GiB free space is required beside the sparse image.')
        require(args.backup_report, 'Migrate needs --backup-report.')
        backup = previous.validate_restore_report(args.backup_report)
        require(backup.get('decrypted_files_written') == 0, 'The restore proof must come from the plaintext-free restore check.')
        require(inspect['HostConfig']['Memory'] == ORIGINAL_MEMORY[0] and inspect['HostConfig']['MemorySwap'] == ORIGINAL_MEMORY[1]
                and inspect['HostConfig']['RestartPolicy']['Name'] == 'unless-stopped', 'Database container resource policy differs from the recorded one.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Unresolved jobs require inspection.')
        live_rows = sum(int(output(PSQL + [f'SELECT count(*) FROM "{t}"'])) for t in billing.tables())
        require(live_rows == backup.get('row_count'), 'The restore proof does not cover the current rows; take a fresh backup first.')
        for u in APP_UNITS:
            require((APP / 'deploy' / u).read_bytes() == (Path('/etc/systemd/system') / u).read_bytes() == baseline_units[u], 'Installed unit differs from the running release: ' + u)
        env_before = word.checked_file(APP / '.env', private=True)
        release_line = ('QUILLMD_RELEASE_SHA=' + BASELINE).encode()
        require(env_before.splitlines().count(release_line) == 1, 'Expected the environment to name the running release.')
        identity.verify_live(BASELINE, target_storage)
    elif args.mode == 'revert-interrupted':
        # A migrate killed outright (the watchdog's SIGKILL) before main advanced: its lock remains and its progress file names
        # a phase-one stage. ROOT_REVERT is written to finish a half-done revert from any such state.
        require(args.from_result and locks['migrate'].exists(), 'Revert needs the interrupted migrate lock and --from-result naming its progress file.')
        source = json.loads(word.checked_file(Path(args.from_result), private=True))
        # HEAD == BASELINE is already required above, so a run killed after recording 'advancing_reviewed_main' but before the
        # ref moved is still a phase-one state and is accepted here.
        require(source.get('mode') == 'migrate' and source.get('target') == args.target and not source.get('complete')
                and (source.get('stage') not in POST_START_STAGES or source.get('stage') == 'advancing_reviewed_main'),
                'Revert applies only to a migrate interrupted before main advanced.')
        # Ctrl-C or a hangup at the runner does not stop the act (timeout runs it in its own process group), so the interrupted
        # run may still be alive. Refuse while it or any of its root steps is running.
        owner = json.loads(word.checked_file(locks['migrate'], private=True))
        require(not migrate_alive(owner.get('pid')), 'The interrupted migrate is still running; wait for its result file instead.')
        require(not running_root_steps(), 'A root step container of the interrupted migrate is still running; wait for it to end.')
    elif args.mode == 'discard-failed-attempt':
        require(probe['rollback'] is None and not probe['pg_data_mounted'] and not probe['state_mounted'] and not probe['volume_script_installed']
                and not any(probe['units_installed'].values()) and (probe['image'] or probe['key'] or probe['mount']),
                'Discard applies only to the artifacts of an automatically reverted migrate.')
        identity.verify_live(BASELINE, target_storage)
    else:
        require(args.from_result, 'Rollback needs --from-result naming the migrate result.')
        source = json.loads(word.checked_file(Path(args.from_result), private=True))
        contains = lambda ancestor, commit: subprocess.run(['git', 'merge-base', '--is-ancestor', ancestor, commit], timeout=60).returncode == 0
        require(rollback_source_ok(source, args.target, contains), 'Rollback applies only after the application ran on the encrypted volume.')
        require(probe['image'] and all(probe['units_installed'].values()) and probe['volume_script_installed'], 'Encrypted-volume installation is incomplete.')
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs)
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print(f'Fresh-storage {args.mode} preflight passed.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECL).name and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL]) == subprocess.check_output(['git', 'show', commit + ':' + DECL]),
            'Committed absolute declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target])
    identity.private_write(lock, {'target': args.target, 'mode': args.mode, 'pid': os.getpid()})
    now = datetime.now(timezone.utc)
    ACT['started'] = time.monotonic()
    ACT['progress'] = result_path.with_name(result_path.stem + '-progress.json')
    result = {'complete': False, 'mode': args.mode, 'previous_head': head, 'target': args.target, 'started_at': now.isoformat(),
              'provider_calls': 0, 'schema_migrations': 0, 'helper_image': image, 'maintenance_window_start': now.isoformat()}
    if args.mode == 'revert-interrupted':
        source = json.loads(word.checked_file(Path(args.from_result), private=True))
        if 'database_before' in source:
            result['database_before'] = source['database_before']
        result['interrupted_stage'] = source.get('stage')
        units_installed = any(probe['units_installed'].values()) or probe['volume_script_installed']
        automatic_revert(result, image, common, baseline_units, units_installed, billing, word, identity)
        if result.get('reverted_to_plaintext_service'):
            locks['migrate'].unlink()
            result.update(complete=True, next_step='Run discard-failed-attempt under the same declaration before any new attempt.')
            stage(result, 'complete')
        finish(result, result_path, lock, identity)
        require(result.get('complete'), 'The interrupted revert did not complete; services may be down. Inspect the result before anything else.')
        return
    if args.mode == 'migrate':
        execute_migrate(args, result, lock, result_path, image, common, units, baseline_units, volume_script, log_path,
                        billing, word, identity, previous, target_storage, env_before, installed, inputs, artifact, now)
    elif args.mode == 'discard-failed-attempt':
        try:
            stage(result, 'discarding_failed_attempt_artifacts')
            result['discard'] = root(ROOT_DISCARD, common, image, writable=['/var/lib', '/etc/quillmd', '/mnt'])
            result.update(complete=True, stage='complete')
        finally:
            finish(result, result_path, lock, identity)
    else:
        execute_rollback(args, result, lock, result_path, image, common, units, billing, word, identity, previous, target_storage, installed, inputs, artifact)


def finish(result, result_path, lock, identity):
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['maintenance_window_end'] = result['finished_at']
    if not result_path.exists():
        identity.private_write(result_path, result)
    else:
        identity.private_write(result_path.with_name(result_path.stem + '-publication-failure.json'), result)
    if result.get('complete') or result.get('reverted_to_plaintext_service'):
        lock.unlink()
    print(f"Fresh-storage {result['mode']} {'completed' if result.get('complete') else 'stopped at ' + str(result.get('stage'))}: {result_path}", flush=True)


def automatic_revert(result, image, common, baseline_units, units_installed, billing, word, identity):
    """Before the application ever served from the encrypted volume: put the untouched originals back and restart on plaintext."""
    try:
        settle_root_step(result)
        stage(result, 'automatic_revert_to_plaintext')
        if units_installed:
            for unit in ('quillmd-fresh-database.service', 'quillmd-fresh-volume.service'):
                try:
                    systemctl('stop', [unit], image)
                except BaseException:
                    pass
        if container_running():
            run(['docker', 'stop', '-t', '90', CONTAINER], stdout=subprocess.DEVNULL, timeout=150)
        result['revert'] = root(ROOT_REVERT, dict(common, units_installed=units_installed, baseline_units={u: b.hex() for u, b in baseline_units.items()}), image,
                               writable=['/var/lib', '/etc/systemd/system', '/usr/local/bin'])
        pre = PRIVATE / 'state-identity.pre-encryption-20260918.json'
        if pre.exists() and json.loads(word.checked_file(PRIVATE / 'state-identity.json', private=True)).get('version') == 2:
            write_pin(identity, json.loads(word.checked_file(pre, private=True)))
        run(['docker', 'update', '--restart=unless-stopped', '--memory', str(ORIGINAL_MEMORY[0]), '--memory-swap', str(ORIGINAL_MEMORY[1]), CONTAINER], stdout=subprocess.DEVNULL)
        run(['docker', 'start', CONTAINER], stdout=subprocess.DEVNULL)
        wait_database()
        if 'database_before' in result:
            require(billing.fingerprints(billing.tables(), exclude_new_migration=False) == result['database_before'], 'Rows differ after the automatic revert.')
        systemctl('start', APP_UNITS, image)
        result['health_after_revert'] = health(BASELINE)
        result['reverted_to_plaintext_service'] = True
        result['next_step'] = 'Inspect the failure; run discard-failed-attempt under the same declaration before any new attempt.'
    except BaseException as revert_error:
        result['reverted_to_plaintext_service'] = False
        result['revert_failure_kind'] = type(revert_error).__name__
        result['revert_failure_message'] = str(revert_error)[:400]


def execute_migrate(args, result, lock, result_path, image, common, units, baseline_units, volume_script, log_path,
                    billing, word, identity, previous, target_storage, env_before, installed, inputs, artifact, now):
    try:
        stage(result, 'capturing_protected_population')
        protected = protected_identity(previous)
        retained = word.retained_reports()
    except BaseException as error:
        # Nothing has changed yet; record and stop without touching services.
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400], reverted_to_plaintext_service=True,
                      next_step='Nothing changed. Inspect and rerun.')
        finish(result, result_path, lock, identity)
        raise
    units_installed = False
    try:
        stage(result, 'stopping_private_services')
        systemctl('stop', APP_UNITS, image)
        require(all(v == 'inactive' for v in unit_states(APP_UNITS).values()), 'Private services did not stop.')
        # The baseline is taken only once nothing but this act can write, so a late request cannot fail a correct copy.
        stage(result, 'capturing_baseline')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
                'A job became pending before the services stopped.')
        result['database_before'] = billing.fingerprints(billing.tables(), exclude_new_migration=False)
        result['schema_before'], result['constraints_before'], result['indexes_before'] = billing.schema(), billing.constraints(), billing.indexes()
        result['storage_before'] = {name: target_storage.inventory(STATE / name) for name in ('files', 'mail')}
        stage(result, 'stopping_database_container')
        run(['docker', 'stop', '-t', '90', CONTAINER], stdout=subprocess.DEVNULL, timeout=150)
        require(not container_running(), 'Database container did not stop.')
        stage(result, 'formatting_encrypted_volume')
        result['prepare'] = root(ROOT_PREPARE, dict(common, image_bytes=IMAGE_BYTES, luks_format=LUKS_FORMAT), image,
                                writable=['/var/lib', '/etc/quillmd', '/mnt'])
        prepared = result['prepare']
        require(prepared['slots'] == ['0: luks2', '1: luks2'] and prepared['version'] == ['Version: 2']
                and prepared['segment_cipher'] == ['cipher: aes-xts-plain64'] and prepared['volume_key'] == ['Key: 512 bits']
                and prepared['keyslot_cipher'] == ['Cipher: aes-xts-plain64'] and prepared['keyslot_key'] == ['Cipher key: 512 bits']
                and prepared['pbkdf'] == ['PBKDF: argon2id'] and prepared['typed_passphrase_opens_slot1'] and prepared['wrong_passphrase_refused']
                and prepared['keyfile_opens_slot0'], 'LUKS parameters or key slots differ from the declaration.')
        stage(result, 'copying_and_verifying_data')
        result['copy'] = root(ROOT_COPY, dict(common, uid=APP_UID, gid=APP_GID, now=now.isoformat(), target=args.target), image, writable=['/mnt'])
        stage(result, 'switching_to_immutable_bind_targets')
        result['switch'] = root(ROOT_SWITCH, dict(common, gid=APP_GID), image, writable=['/var/lib'])
        require(result['switch']['pg_data_empty'] and result['switch']['state_empty'] and 'i' in result['switch']['pg_data_attrs']
                and 'i' in result['switch']['state_attrs'], 'Bind targets are not empty and immutable.')
        stage(result, 'installing_units_and_helper')
        units_installed = True
        result['install'] = root(ROOT_INSTALL, dict(common, volume_script_hex=volume_script.hex(), units={u: b.hex() for u, b in units.items()}), image,
                                writable=['/usr/local/bin', '/etc/systemd/system'])
        for u in APP_UNITS + NEW_UNITS:
            require((Path('/etc/systemd/system') / u).read_bytes() == units[u], 'Installed unit readback differs: ' + u)
        run(['docker', 'update', '--restart=no', '--memory', str(ORIGINAL_MEMORY[0]), '--memory-swap', str(ORIGINAL_MEMORY[0]), CONTAINER], stdout=subprocess.DEVNULL)
        stage(result, 'repinning_state_identity')
        old_pin = json.loads(word.checked_file(PRIVATE / 'state-identity.json', private=True))
        require(old_pin.get('version') == 1, 'Expected the plaintext version-1 pin.')
        pre = PRIVATE / 'state-identity.pre-encryption-20260918.json'
        if not pre.exists():
            identity.private_write(pre, old_pin)
        write_pin(identity, {'version': 2, 'account': old_pin['account'], 'device_source': target_storage.DEVICE_SOURCE,
                             'roots': {f'/var/lib/quillmd/{n}': {'inode': result['copy']['inodes'][n]} for n in ('files', 'mail', 'proofs')}})
        stage(result, 'opening_volume_and_database')
        systemctl('start', ['quillmd-fresh-volume.service'], image)
        systemctl('start', ['quillmd-fresh-database.service'], image)
        state = root(ROOT_STATE, common, image)
        require(state['mount_mounted'] and state['pg_bound'] and state['state_bound'] and state['marker'] and state['device_matches_mapper']
                and state['inodes'] == result['copy']['inodes'] and state['state_root'] == {'mode': '0o710', 'uid': 0, 'gid': APP_GID}
                and state['tmp'] == {'mode': '0o700', 'uid': APP_UID, 'gid': APP_GID} and state['key_mode'] == '0o400' and state['recovery_mode'] == '0o400',
                'Opened volume state differs from the declaration: ' + json.dumps(state))
        result['open_state'] = state
        require(container_running(), 'Database container is not running on the encrypted volume.')
        wait_database()
        stage(result, 'suppressing_statement_logging')
        for statement in ("ALTER SYSTEM SET log_min_messages = 'fatal'", "ALTER SYSTEM SET log_min_error_statement = 'panic'", 'SELECT pg_reload_conf()'):
            output(PSQL + [statement])
        time.sleep(2)
        result['logging'] = {'log_min_messages': output(PSQL + ['SHOW log_min_messages']), 'log_min_error_statement': output(PSQL + ['SHOW log_min_error_statement'])}
        require(result['logging'] == {'log_min_messages': 'fatal', 'log_min_error_statement': 'panic'}, 'Statement logging was not suppressed.')
        stage(result, 'verifying_data_on_encrypted_volume')
        require(billing.fingerprints(billing.tables(), exclude_new_migration=False) == result['database_before'], 'Database rows differ after the move.')
        require(billing.schema() == result['schema_before'] and billing.constraints() == result['constraints_before']
                and billing.indexes() == result['indexes_before'], 'Schema or catalog differs after the move.')
        require({name: target_storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private files or mail differ after the move.')
        stage(result, 'advancing_reviewed_main')
        run(['git', 'merge', '--ff-only', args.target])
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400])
        if output(['git', 'rev-parse', 'HEAD']) == BASELINE:
            automatic_revert(result, image, common, baseline_units, units_installed, billing, word, identity)
        else:
            result['reverted_to_plaintext_service'] = False
            result['next_step'] = 'Main advanced but the application never started on the encrypted volume; run rollback with --from-result.'
        finish(result, result_path, lock, identity)
        raise
    env_after = env_before
    try:
        stage(result, 'starting_private_services_on_encrypted_volume')
        env_after = re.sub(rb'(?m)^QUILLMD_RELEASE_SHA=' + BASELINE.encode() + rb'$', ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
        require(env_after != env_before and env_after.count(b'\n') == env_before.count(b'\n'), 'Release replacement did not apply cleanly.')
        pending = PRIVATE / ('fresh-storage-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        systemctl('start', APP_UNITS, image)
        result['health'] = health(args.target)
        result['proofs'] = identity.verify_live(args.target, target_storage)
        for surface, proof in result['proofs'].items():
            require(proof['checks'].get('state_tmp', {}).get('read_write_delete') is True
                    and proof['checks'].get('temporary_directory', {}).get('path') == '/var/lib/quillmd/tmp', 'Temporary directory proof missing: ' + surface)
        run(['bash', 'scripts/check-cotenants.sh'])
        require(protected_identity(previous) == protected, 'Protected container population changed.')
        # Archived only now, after main advanced: an automatic revert or discard can never lose it.
        # Docker appends with O_APPEND, so truncating the live log leaves later lines well formed.
        stage(result, 'archiving_database_container_log')
        result['container_log'] = root(ROOT_ARCHIVE_LOG, dict(common, log_path=log_path, stamp=now.strftime('%Y%m%dT%H%M%SZ')), image, writable=['/mnt'])
        # Recorded, not required: a benign line written between truncate and stat must not stop a running service.
        result['container_log_bytes_after_archive'] = result['container_log']['container_log_bytes_after']
        stage(result, 'unavailability_drill')
        systemctl('stop', ['quillmd-fresh-volume.service'], image)
        time.sleep(3)
        closed = root(ROOT_STATE, common, image)
        require(not closed['mount_mounted'] and not closed['pg_bound'] and not closed['state_bound'] and not closed['mapper_present']
                and all(v in ('inactive', 'failed') for v in closed['units_active'].values()) and closed['pg_data_listing'] == [] and closed['state_listing'] == []
                and 'i' in closed['pg_data_attrs'] and 'i' in closed['state_attrs'], 'Closed-volume state is not fail-closed: ' + json.dumps(closed))
        require(not container_running() and not listener_answers(), 'A service kept running without its volume.')
        result['closed_state'] = closed
        result['closed_write_probe'] = root(ROOT_WRITE_PROBE, common, image)
        require(all(v == 'refused' for v in result['closed_write_probe'].values()), 'Plaintext write probe succeeded while closed.')
        manual = subprocess.run(['docker', 'start', CONTAINER], capture_output=True, text=True, timeout=120)
        time.sleep(8)
        after_manual = root(ROOT_STATE, common, image)
        running_after = container_running()
        if running_after:
            subprocess.run(['docker', 'stop', '-t', '30', CONTAINER], capture_output=True, timeout=90)
        result['manual_container_start_while_closed'] = {'docker_start_exit': manual.returncode, 'running_after_8s': running_after,
                                                         'pg_data_listing': after_manual['pg_data_listing']}
        require(after_manual['pg_data_listing'] == [], 'A manual container start wrote into the closed database directory.')
        stage(result, 'recovery_after_drill')
        systemctl('start', ['quillmd-fresh-volume.service'], image)
        systemctl('start', ['quillmd-fresh-database.service'], image)
        wait_database()
        systemctl('start', APP_UNITS, image)
        result['health_after_recovery'] = health(args.target)
        stage(result, 'final_checks')
        require(billing.fingerprints(billing.tables(), exclude_new_migration=False) == result['database_before'], 'Rows differ after the recovery drill.')
        require({name: target_storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private files differ after the recovery drill.')
        result['proofs_after_recovery'] = identity.verify_live(args.target, target_storage)
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs) == artifact, 'Word runtime changed.')
        require(protected_identity(previous) == protected and previous.protected() == protected, 'Protected population changed.')
        require(retained_unchanged(retained), 'A report retained before the act changed or disappeared.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, all_rows_identical=True, all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after),
                      custody={'key_slot_0': KEY + ' (root 0400, on this host; required for unattended boot)',
                               'recovery_slot_1': RECOVERY + ' (root 0400; owner moves it to the vault, then it is shredded here)',
                               'image': IMAGE, 'rollback_material': ROLLBACK + ' (plaintext pre-migration snapshot; shred after owner acceptance)'})
        stage(result, 'complete')
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400])
        try:
            settle_root_step(result)
        except BaseException:
            pass
        try:
            systemctl('stop', APP_UNITS, image)
            result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False
            result['stop_failure_kind'] = type(stop_error).__name__
        result['next_step'] = 'The application may have run on the encrypted volume. Fix forward, or run rollback under the same declaration with --from-result.'
        finish(result, result_path, lock, identity)
        raise
    finish(result, result_path, lock, identity)


def execute_rollback(args, result, lock, result_path, image, common, units, billing, word, identity, previous, target_storage, installed, inputs, artifact):
    try:
        stage(result, 'stopping_private_services')
        systemctl('stop', APP_UNITS, image)
        stage(result, 'opening_volume_and_database')
        systemctl('start', ['quillmd-fresh-volume.service'], image)
        systemctl('start', ['quillmd-fresh-database.service'], image)
        wait_database()
        result['database_before'] = billing.fingerprints(billing.tables(), exclude_new_migration=False)
        result['storage_before'] = {name: target_storage.inventory(STATE / name) for name in ('files', 'mail')}
        stage(result, 'stopping_database')
        systemctl('stop', ['quillmd-fresh-database.service'], image)
        require(not container_running(), 'Database container did not stop.')
        stage(result, 'copying_current_data_back')
        staging = '/var/lib/quillmd-restore-plaintext-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        result['copy_back'] = root(ROOT_COPY_BACK, dict(common, staging=staging), image, writable=['/var/lib'])
        stage(result, 'closing_volume')
        systemctl('stop', ['quillmd-fresh-volume.service'], image)
        stage(result, 'switching_back_to_plaintext')
        result['switch_back'] = root(ROOT_SWITCH_BACK, dict(common, staging=staging, plaintext_units={u: b.hex() for u, b in plaintext_units(units).items()}), image,
                                    writable=['/var/lib', '/etc/systemd/system', '/usr/local/bin'])
        old_pin = json.loads(word.checked_file(PRIVATE / 'state-identity.json', private=True))
        write_pin(identity, {'version': 1, 'account': old_pin['account'], 'roots': {f'/var/lib/quillmd/{n}': v for n, v in result['switch_back']['identity'].items()}})
        run(['docker', 'update', '--restart=unless-stopped', CONTAINER], stdout=subprocess.DEVNULL)
        run(['docker', 'start', CONTAINER], stdout=subprocess.DEVNULL)
        wait_database()
        require(billing.fingerprints(billing.tables(), exclude_new_migration=False) == result['database_before'], 'Rows differ across rollback.')
        require({name: target_storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private files differ across rollback.')
        stage(result, 'starting_private_services_on_plaintext')
        systemctl('start', APP_UNITS, image)
        release = next(line.split('=', 1)[1] for line in word.checked_file(APP / '.env', private=True).decode().splitlines() if line.startswith('QUILLMD_RELEASE_SHA='))
        result['health'] = health(release)
        result['proofs'] = identity.verify_live(release, target_storage)
        run(['bash', 'scripts/check-cotenants.sh'])
        result['retained'] = {'encrypted_image': IMAGE, 'key': KEY, 'recovery': RECOVERY}
        result.update(complete=True)
        stage(result, 'complete')
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400])
        try:
            settle_root_step(result)
            systemctl('stop', APP_UNITS, image)
        except BaseException:
            pass
        finish(result, result_path, lock, identity)
        raise
    finish(result, result_path, lock, identity)


if __name__ == '__main__':
    main()
