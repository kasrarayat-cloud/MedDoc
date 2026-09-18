#!/usr/bin/env python3
"""Verify encrypted recovery of the fresh QuillMD storage, then remove its redundant plaintext copies; default is read-only.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B <worktree>/scripts/verify-and-reap-fresh-plaintext.py \
        --target FULL_MERGE_SHA --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/plaintext-recovery-reap-<label>.json [--execute]

Read-only preflight, then (with --execute, only through scripts/run-ruled-mutation.sh and the committed declaration):

1. Active storage: the database directory and WAL, documents, mail, proofs and service temporary files resolve to the
   encrypted mapper; PostgreSQL has no tablespace or WAL outside its data directory; the services' private /tmp is empty.
2. Keys: slot 0 opens with the key file, slot 1 with the recovery passphrase file and as typed. Nothing is printed.
3. Backup: a fresh encrypted backup restored in isolation with no decrypted file written, covering every live row.
4. Recovery drill: close the encrypted volume (database and services stop with it, nothing can write plaintext), reopen it,
   and confirm health, identity proofs, rows and files are unchanged.
5. Accounting, again, immediately before removal: every file in each plaintext copy is byte-identical to a file at the
   same path in the live encrypted store, and the rollback database is the snapshot the storage act proved identical.
6. Removal of exactly the declared paths (shred each file, check, then remove the empty directories), recorded file by file.

It never touches live storage, backups, credentials, evidence, the Word review package or any original-application data.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
HERE = Path(__file__).resolve().parent
DECL = 'docs/foundation/mutations/20260918-quillmd-plaintext-recovery-reap.md'
SELF = 'scripts/verify-and-reap-fresh-plaintext.py'
MIGRATE = 'scripts/migrate-fresh-storage.py'
STORAGE_ACT_RESULT = PRIVATE / 'fresh-storage-migrate-20260918b.json'
ROLLBACK = '/var/lib/quillmd-rollback-20260918'
LIVE = {'files': '/var/lib/quillmd/files', 'mail': '/var/lib/quillmd/mail'}
# Restore checks made before the plaintext-free restore mode wrote each restored document to disk: run -> (backup, source commit).
RESTORE_COPIES = {'3cb2094861b0221f': ('20260917T174418Z-220e52ba', '66acbba70e7f', 21, 927150),
                  '8ff86eb5e74a79c6': ('20260917T190612Z-48741b09', '688837471efb', 22, 963799),
                  '082a2b3c778bf220': ('20260917T211935Z-6f919769', '5d43d3d62c6d', 25, 1064574),
                  'c5846e432dececd0': ('20260917T214244Z-c2b7f69c', '8f8a6763b80d', 26, 1111178),
                  'd56b7fa1af209561': ('20260917T234313Z-56be2efa', '8f8a6763b80d', 28, 1169128),
                  'd74d8e2b0746dd01': ('20260918T015725Z-f9fb8a56', '19d46ad3d51a', 28, 1169128)}
# Exactly the plaintext copies this act may remove, each with where it came from and how its content is accounted for.
# File and byte counts are the declaration's; any difference refuses the act before removal.
TARGETS = ([{'path': ROLLBACK, 'kind': 'rollback', 'files': 2499 + 44, 'bytes': 143248132 + 1176723,
             'origin': 'pre-migration snapshot of release 19d46ad3 (database directory and state), moved aside by the storage act (target 3eac783a)'},
            {'path': str(PRIVATE / 'files'), 'kind': 'state', 'live': 'files', 'files': 27, 'bytes': 927320,
             'origin': 'document root of releases up to 66acbba7, superseded by /var/lib/quillmd at the OS-identity cutover (2026-09-17 17:42Z)'},
            {'path': str(PRIVATE / 'mail'), 'kind': 'state', 'live': 'mail', 'files': 2, 'bytes': 1227,
             'origin': 'private outbox of releases up to 66acbba7, superseded by /var/lib/quillmd at the OS-identity cutover'}]
           + [{'path': str(PRIVATE / 'restore-checks' / ('restore-' + run) / 'files'), 'kind': 'state', 'live': 'files', 'files': files, 'bytes': size,
               'origin': f'documents decrypted by the restore check of backup {backup} (source {commit}); its verification.json is kept'}
              for run, (backup, commit, files, size) in sorted(RESTORE_COPIES.items())])
# Never inside a target, and never a target itself.
PROTECTED = ['/var/lib/quillmd', '/var/lib/docker', '/var/lib/quillmd-encrypted', '/etc/quillmd', '/opt/meddoc-pro/backups',
             str(PRIVATE / 'new-system-backups'), str(PRIVATE / 'backup-secrets'), str(PRIVATE / 'db-role-secrets'),
             str(PRIVATE / 'word-review-package'), str(PRIVATE / 'terminology')]
TREE_HELPERS = {'billing': 'scripts/activate-billing-policy.py', 'word': 'scripts/activate-word-beta.py',
                'identity': 'scripts/activate-os-identity.py', 'previous': 'scripts/update-private-beta.py'}
ACTIVE_PATHS = ['/var/lib/quillmd', '/var/lib/quillmd/files', '/var/lib/quillmd/mail', '/var/lib/quillmd/proofs', '/var/lib/quillmd/tmp',
                '/var/lib/docker/volumes/quillmd_fresh_pg/_data', '/var/lib/docker/volumes/quillmd_fresh_pg/_data/pg_wal']


class Terminated(BaseException):
    pass


def _terminate(signum, frame):
    raise Terminated('signal %d' % signum)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.run(command, check=True, **kwargs)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT_VERIFY_STORAGE = r'''
def source(path):
    r=host('/usr/bin/findmnt','-no','SOURCE','-T',path,check=False)
    return r.stdout.strip() if r.returncode==0 else 'ERROR'
private={}
for base in ('/tmp','/var/tmp'):
    for name in sorted(os.listdir(base)):
        if name.startswith('systemd-private-') and '-quillmd-fresh-' in name:
            private[base+':'+name.split('-quillmd-fresh-')[1].split('.service')[0]]=sum(len(fs) for _,_,fs in os.walk(base+'/'+name))
wal=os.lstat(P['pg_data']+'/pg_wal')
emit({'sources':{p:source(p) for p in P['paths']},'private_tmp_files':private,'pg_wal_is_directory':stat.S_ISDIR(wal.st_mode)})
'''

ROOT_KEYS = r'''
dump=host('/usr/sbin/cryptsetup','luksDump',P['image']).stdout
lines=[' '.join(l.split()) for l in dump.splitlines()]
slot0=host('/usr/sbin/cryptsetup','open','--test-passphrase','--key-slot','0','--key-file',P['key'],P['image'],check=False).returncode
slot1=host('/usr/sbin/cryptsetup','open','--test-passphrase','--key-slot','1','--key-file',P['recovery'],P['image'],check=False).returncode
with open(P['recovery']) as f: phrase=f.read()
typed=host('/usr/sbin/cryptsetup','open','--test-passphrase','--key-slot','1',P['image'],stdin=phrase+'\n',check=False).returncode
del phrase
def mode(p):
    s=os.stat(p); return {'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid}
emit({'slots':[l for l in lines if l.endswith(': luks2') and l.split(':')[0].isdigit()],'keyfile_opens_slot0':slot0==0,'recovery_file_opens_slot1':slot1==0,
      'typed_recovery_opens_slot1':typed==0,'key':mode(P['key']),'recovery':mode(P['recovery'])})
'''

ROOT_ACCOUNT = r'''
def hashes(root):
    out={}
    for d,ds,fs in os.walk(root):
        ds.sort()
        for f in sorted(fs):
            p=os.path.join(d,f); s=os.lstat(p)
            if stat.S_ISREG(s.st_mode):
                h=hashlib.sha256()
                with open(p,'rb') as fh:
                    for chunk in iter(lambda: fh.read(1<<20), b''): h.update(chunk)
                out[os.path.relpath(p,root)]={'sha256':h.hexdigest(),'bytes':s.st_size}
            elif not stat.S_ISDIR(s.st_mode): out[os.path.relpath(p,root)]={'sha256':None,'bytes':0,'special':True}
    return out
live={name:hashes(root) for name,root in P['live'].items()}
report=[]
for t in P['targets']:
    path=t['path']
    if not os.path.lexists(path): report.append({'path':path,'present':False}); continue
    if os.path.islink(path) or os.path.realpath(path)!=path: raise RuntimeError('target is not a resolved directory: '+path)
    entry={'path':path,'present':True,'kind':t['kind'],'origin':t['origin']}
    if t['kind']=='state':
        entry['files']=hashes(path)
        entry['unaccounted']=sorted(r for r,v in entry['files'].items() if live[t['live']].get(r,{}).get('sha256')!=v['sha256'])
    else:
        entry['state']={name:hashes(path+'/state/'+name) for name in sorted(os.listdir(path+'/state'))} if os.path.isdir(path+'/state') else {}
        entry['unaccounted']=sorted(name+'/'+r for name in ('files','mail') for r,v in entry['state'].get(name,{}).items() if live[name].get(r,{}).get('sha256')!=v['sha256'])
        entry['unexpected_state']=sorted(set(entry['state'])-{'files','mail','proofs'})
        entry['top_level']=sorted(os.listdir(path))
        entry['census']={name:census(path+'/'+name) for name in ('pg_data','state') if os.path.isdir(path+'/'+name)}
        entry['pg_data_files']=hashes(path+'/pg_data') if os.path.isdir(path+'/pg_data') else {}
    report.append(entry)
emit({'live_counts':{k:len(v) for k,v in live.items()},'targets':report})
'''

ROOT_REAP = r'''
done=[]
for path in P['paths']:
    if not os.path.lexists(path): done.append({'path':path,'removed':False,'reason':'absent'}); continue
    if os.path.islink(path) or os.path.realpath(path)!=path: raise RuntimeError('refusing unresolved path: '+path)
    shredded=host('/usr/bin/find',path,'-xdev','-type','f','-exec','/usr/bin/shred','-u','-n','3','-z','{}','+',check=False,timeout=1800)
    left=[os.path.join(d,f) for d,_,fs in os.walk(path) for f in fs if not os.path.islink(os.path.join(d,f))]
    if shredded.returncode!=0 or left:
        raise RuntimeError('shred did not complete for '+path+' ('+str(len(left))+' files left); nothing further removed')
    host('/usr/bin/find',path,'-xdev','-type','l','-delete')
    host('/usr/bin/find',path,'-xdev','-depth','-type','d','-empty','-delete')
    if os.path.lexists(path): raise RuntimeError('directory remains after shredding: '+path)
    done.append({'path':path,'removed':True})
emit({'reaped':done})
'''


def main():
    signal.signal(signal.SIGTERM, _terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    require(output(['git', 'branch', '--show-current']) == 'main', 'Shared tree must stay on main.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    running = output(['git', 'rev-parse', 'HEAD'])
    run(['git', 'merge-base', '--is-ancestor', running, args.target])
    for relative in (SELF, MIGRATE):
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (HERE.parent / relative).read_bytes(),
                'Script differs from the reviewed target: ' + relative)
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target and p.get('base', {}).get('ref') == 'main' for p in pulls),
            'A merged PR is required.')
    m = load('fresh_storage_act', HERE.parent / MIGRATE)
    modules = {}
    for name, relative in TREE_HELPERS.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(), 'Reviewed helper changed: ' + relative)
        modules[name] = load('reap_' + name, ROOT / relative)
    billing, word, identity, previous = (modules[k] for k in ('billing', 'word', 'identity', 'previous'))
    storage = load('reap_storage', ROOT / 'rebuild/ops/private_storage.py')
    image = m.helper_image()
    common = m.params_common()
    health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
    release = health[0].get('release')
    require(release == running and all(h.get('release') == running and h.get('data_mode') == 'synthetic-only' for h in health),
            'The private services must run the permanent release, synthetic-only.')
    # Every target is a resolved path outside everything protected, and nothing protected lies inside a target.
    for target in TARGETS:
        path = target['path']
        require(Path(path).is_absolute() and os.path.normpath(path) == path, 'Unresolved target: ' + path)
        for protected in PROTECTED:
            require(not (path == protected or path.startswith(protected + '/') or protected.startswith(path + '/')), 'Target touches a protected path: ' + path)
    # The storage act that made the rollback snapshot completed and proved every row and file identical on the encrypted volume.
    act = json.loads(word.checked_file(STORAGE_ACT_RESULT, private=True))
    require(act.get('complete') is True and act.get('all_rows_identical') is True and act.get('all_private_files_and_mail_identical') is True,
            'The storage act result does not prove the rollback snapshot redundant.')
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('decrypted_files_written') == 0 and backup.get('restore_database_on_tmpfs_without_swap') is True,
            'The restore proof must come from the plaintext-free restore check.')
    live_rows = sum(int(output(m.PSQL + [f'SELECT count(*) FROM "{t}"'])) for t in billing.tables())
    require(live_rows == backup.get('row_count'), 'The restore proof does not cover the current rows; take a fresh backup first.')
    require(output(m.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Unresolved jobs require inspection.')
    verified = verify(m, image, common, release, identity, storage)
    accounting = account(m, image, act['copy'])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Plaintext recovery-and-reap preflight passed.', flush=True)
    if not args.execute:
        print(json.dumps({'verified': verified, 'accounting': summary(accounting)}, indent=1), flush=True)
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECL).name and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL]) == subprocess.check_output(['git', 'show', commit + ':' + DECL]),
            'Committed absolute declaration required.')
    result_path = Path(args.result)
    lock = PRIVATE / '.plaintext-recovery-reap.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and re.fullmatch(r'plaintext-recovery-reap-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not lock.exists(), 'Choose unused private evidence; a prior lock needs inspection.')
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid()})
    result = {'complete': False, 'target': args.target, 'release': release, 'started_at': datetime.now(timezone.utc).isoformat(),
              'backup_report': args.backup_report, 'backup_run_id': backup.get('backup_run_id'), 'preflight': verified}
    try:
        before = billing.fingerprints(billing.tables(), exclude_new_migration=False)
        files_before = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        result['stage'] = 'recovery_drill'
        result['drill'] = drill(m, image, common, release)
        require(billing.fingerprints(billing.tables(), exclude_new_migration=False) == before, 'Rows changed across the recovery drill.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == files_before, 'Files changed across the recovery drill.')
        result['after_drill'] = verify(m, image, common, release, identity, storage)
        result['stage'] = 'accounting_before_removal'
        accounting = account(m, image, act['copy'])
        result['removal_manifest'] = accounting
        result['stage'] = 'removing_redundant_plaintext'
        result['reaped'] = m.root(ROOT_REAP, {'paths': [t['path'] for t in TARGETS]}, image, timeout=2400)
        result['stage'] = 'final_checks'
        after = m.root(ROOT_ACCOUNT, {'targets': TARGETS, 'live': LIVE}, image)
        require(all(not entry['present'] for entry in after['targets']), 'A declared plaintext copy is still present.')
        require(billing.fingerprints(billing.tables(), exclude_new_migration=False) == before, 'Rows changed.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == files_before, 'Live files changed.')
        require(previous.validate_restore_report(args.backup_report).get('backup_run_id') == backup.get('backup_run_id'), 'The encrypted backup is no longer intact.')
        result['final'] = verify(m, image, common, release, identity, storage)
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', finished_at=datetime.now(timezone.utc).isoformat())
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400], finished_at=datetime.now(timezone.utc).isoformat())
        result['services_restarted'] = restart_best_effort(m, image)
        identity.private_write(result_path if not result_path.exists() else result_path.with_name(result_path.stem + '-failure.json'), result)
        raise
    print('Plaintext recovery-and-reap completed: ' + str(result_path), flush=True)


def verify(m, image, common, release, identity, storage):
    """Active storage on the encrypted mapper, WAL inside the data directory, no tablespace elsewhere, service temp on the volume."""
    state = m.root(m.ROOT_STATE, common, image)
    require(state['mount_mounted'] and state['pg_bound'] and state['state_bound'] and state['marker'] and state['device_matches_mapper'],
            'Encrypted volume is not fully open and bound.')
    storage_view = m.root(ROOT_VERIFY_STORAGE, dict(common, paths=ACTIVE_PATHS), image)
    require(all(source.startswith('/dev/mapper/' + m.MAPPER) for source in storage_view['sources'].values()),
            'An active path is not on the encrypted mapper: ' + json.dumps(storage_view['sources']))
    require(storage_view['pg_wal_is_directory'], 'WAL must be a directory inside the encrypted data directory, not a link elsewhere.')
    require(all(count == 0 for count in storage_view['private_tmp_files'].values()), 'Service private /tmp holds files: ' + json.dumps(storage_view['private_tmp_files']))
    require(output(m.PSQL + ['SHOW data_directory']) == '/var/lib/postgresql/data', 'Unexpected PostgreSQL data directory.')
    require(output(m.PSQL + ["SELECT count(*) FROM pg_tablespace WHERE spcname NOT IN ('pg_default','pg_global')"]) == '0', 'A tablespace lives outside the data directory.')
    proofs = identity.verify_live(release, storage)
    for surface, proof in proofs.items():
        require(proof['checks'].get('temporary_directory', {}).get('path') == '/var/lib/quillmd/tmp'
                and proof['checks'].get('state_tmp', {}).get('read_write_delete') is True, 'Service temporary files are not on the encrypted state: ' + surface)
    keys = m.root(ROOT_KEYS, common, image)
    require(keys['slots'] == ['0: luks2', '1: luks2'] and keys['keyfile_opens_slot0'] and keys['recovery_file_opens_slot1'] and keys['typed_recovery_opens_slot1']
            and keys['key'] == {'mode': '0o400', 'uid': 0} and keys['recovery'] == {'mode': '0o400', 'uid': 0}, 'Key slots are not both usable: ' + json.dumps(keys))
    return {'sources': storage_view['sources'], 'private_tmp_files': storage_view['private_tmp_files'], 'keys': keys,
            'service_temporary_directory': {s: p['checks']['temporary_directory'] for s, p in proofs.items()}}


def account(m, image, copied):
    view = m.root(ROOT_ACCOUNT, {'targets': TARGETS, 'live': LIVE}, image, timeout=1200)
    require([e['path'] for e in view['targets']] == [t['path'] for t in TARGETS], 'Accounting did not cover exactly the declared paths.')
    for entry, declared in zip(view['targets'], TARGETS):
        require(entry['present'], 'A declared plaintext copy is missing before removal: ' + entry['path'])
        if entry['kind'] == 'state':
            measured = (len(entry['files']), sum(v['bytes'] for v in entry['files'].values()))
        else:
            measured = (sum(c['files'] for c in entry['census'].values()), sum(c['bytes'] for c in entry['census'].values()))
        require(measured == (declared['files'], declared['bytes']), 'Measured files and bytes differ from the declaration: ' + entry['path'] + ' ' + str(measured))
        require(not entry['unaccounted'], 'Plaintext copy holds content not in the live encrypted store: ' + entry['path'] + ' ' + json.dumps(entry['unaccounted'][:5]))
        if entry['kind'] == 'rollback':
            require(entry['top_level'] == ['pg_data', 'state'] and not entry['unexpected_state'], 'Rollback snapshot layout differs from the one the storage act made.')
            # The storage act copied these trees onto the encrypted volume with the services and database stopped, proved the
            # copy's census equal to this source, and proved every row identical once the database ran from the copy.
            require(entry['census'] == {'pg_data': copied['pg'], 'state': copied['state']},
                    'The rollback snapshot is not byte-identical to what the storage act copied onto the encrypted volume.')
        else:
            require(entry['files'] and not any(v.get('special') for v in entry['files'].values()), 'Unexpected content in ' + entry['path'])
    return view


def summary(view):
    return [{'path': e['path'], 'files': len(e.get('files', {})) if e['kind'] == 'state' else {'pg_data': e['census']['pg_data']['files'],
             **{k: len(v) for k, v in e['state'].items()}}} for e in view['targets']]


def drill(m, image, common, release):
    """Close the encrypted volume, prove nothing runs or writes, reopen it and prove the service recovered."""
    m.systemctl('stop', ['quillmd-fresh-volume.service'], image)
    time.sleep(3)
    closed = m.root(m.ROOT_STATE, common, image)
    require(not closed['mount_mounted'] and not closed['pg_bound'] and not closed['state_bound'] and not closed['mapper_present']
            and all(v in ('inactive', 'failed') for v in closed['units_active'].values()) and closed['pg_data_listing'] == [] and closed['state_listing'] == []
            and 'i' in closed['pg_data_attrs'] and 'i' in closed['state_attrs'], 'Closed volume is not fail-closed: ' + json.dumps(closed))
    require(not m.container_running() and not m.listener_answers(), 'A service kept running without its volume.')
    probe = m.root(m.ROOT_WRITE_PROBE, common, image)
    require(all(v == 'refused' for v in probe.values()), 'A plaintext write succeeded while the volume was closed.')
    manual = subprocess.run(['docker', 'start', m.CONTAINER], capture_output=True, text=True, timeout=120)
    time.sleep(8)
    after_manual = m.root(m.ROOT_STATE, common, image)
    running_after = m.container_running()
    if running_after:
        subprocess.run(['docker', 'stop', '-t', '30', m.CONTAINER], capture_output=True, timeout=90)
    require(after_manual['pg_data_listing'] == [], 'A manual container start wrote into the closed database directory.')
    m.systemctl('start', ['quillmd-fresh-volume.service'], image)
    m.systemctl('start', ['quillmd-fresh-database.service'], image)
    m.wait_database()
    m.systemctl('start', m.APP_UNITS, image)
    reopened = m.root(m.ROOT_STATE, common, image)
    require(reopened['mount_mounted'] and reopened['pg_bound'] and reopened['state_bound'] and reopened['marker'] and reopened['device_matches_mapper'],
            'Reopened volume state differs.')
    return {'closed': closed, 'write_probe': probe, 'reopened_units': reopened['units_active'], 'health': m.health(release),
            'manual_container_start_while_closed': {'docker_start_exit': manual.returncode, 'running_after_8s': running_after,
                                                    'pg_data_listing': after_manual['pg_data_listing']}}


def restart_best_effort(m, image):
    try:
        for unit in (['quillmd-fresh-volume.service'], ['quillmd-fresh-database.service'], m.APP_UNITS):
            m.systemctl('start', unit, image)
        return True
    except BaseException:
        return False


if __name__ == '__main__':
    main()
