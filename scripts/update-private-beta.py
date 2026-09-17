#!/usr/bin/env python3
"""Preserve new data while updating the three private QuillMD services from a cited PR."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
UNITS = ['quillmd-fresh-' + name + '.service' for name in ('doctor', 'admin', 'worker')]
NEW_COLUMNS = {'core_job':['provider_resource_id'], 'core_usage':['provider_resource_id'],
               'core_providerreceipt':['provider_resource_id'],
               'core_payment':['request_key','checkout_url'],
               'core_webhookevent':['attempts','error','object_data','processed_at','semantic_hash','status']}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def output(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def protected():
    baseline = json.loads((ROOT / 'docs/rebuild/activation-baseline.json').read_text())
    rows = json.loads(output(['docker', 'inspect', *[r['name'].lstrip('/') for r in baseline['containers']]]))
    for want, got in zip(baseline['containers'], rows):
        require(want['id'] == got['Id'] and want['image'] == got['Image'] and want['running'] == got['State']['Running'], 'A protected container identity/state changed.')
        require(want['mounts'] == [{'source': m['Source'], 'destination': m['Destination']} for m in got['Mounts']], 'A protected mount changed.')
    return len(rows)


def systemd(action):
    require(action in ('stop', 'start'), 'Unsupported service operation.')
    # No writable host mount, network, provider credentials or arbitrary unit names.
    code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\n"
    code += 'subprocess.run(' + repr(['systemctl', action, *UNITS]) + ',check=True)\n'
    run(['docker','run','--rm','-i','--network','none','--pid=host','--mount','type=bind,src=/,dst=/host,readonly','python:3-slim','python','-'], input=code, text=True)


def database_fingerprints():
    command = ['docker','exec','quillmd-fresh-postgres','psql','-U','quillmd_fresh','-d','quillmd_fresh','-X','-At','-v','ON_ERROR_STOP=1','-c']
    tables = output(command+["SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'django_migrations' ORDER BY tablename"]).splitlines()
    require(tables and all(re.fullmatch('[a-z_][a-z_0-9]*',table) for table in tables), 'Cannot enumerate fresh application tables.')
    result = {}
    for table in tables:
        # Only fields declared as additions may differ across this release.
        expression = 'to_jsonb(t)' + ''.join("-'"+field+"'" for field in NEW_COLUMNS.get(table,[]))
        data = subprocess.check_output(command+[f'COPY (SELECT ({expression})::text AS value FROM {table} t ORDER BY value) TO STDOUT'])
        result[table] = {'sha256': hashlib.sha256(data).hexdigest(), 'rows': len(data.splitlines())}
    return result


def validate_restore_report(report_path):
    from cryptography.fernet import Fernet
    report_path = Path(report_path).absolute()
    require(report_path.resolve() == report_path and report_path.parent == APP/'.runtime/restore-checks', 'Use the permanent private new-system restore report.')
    def read_private(path):
        require(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o777 == 0o600, 'Backup evidence/key must be a private regular0600 file.')
        return path.read_bytes()
    report = json.loads(read_private(report_path))
    for flag in ('complete','all_table_hashes_match','all_file_hashes_match','encrypted_backup_preserved','transfer_all_hashes_match'):
        require(report.get(flag) is True, 'Verified encrypted backup and restore comparison required.')
    require(report.get('network') == 'none' and report.get('published_ports') == 0 and report.get('workers_started') == 0 and report.get('provider_actions') == 0 and report.get('provider_credentials_copied') is False, 'Restore isolation evidence is incomplete.')
    require(report.get('invariants') and all(value == 0 for value in report['invariants'].values()), 'Restore invariant proof failed.')
    run_id = report.get('backup_run_id','')
    require(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',run_id), 'Invalid backup identity.')
    backup_path = APP/'.runtime/new-system-backups'/run_id
    require(str(backup_path) == report.get('backup_directory') and backup_path.resolve() == backup_path, 'Backup directory ownership mismatch.')
    key_path = Path(report.get('key_file',''))
    require(key_path.is_absolute() and key_path.parent == APP/'.runtime/backup-secrets' and key_path.resolve() == key_path, 'Backup key must remain separate and protected.')
    summary = json.loads(read_private(backup_path/'summary.json'))
    cipher = read_private(backup_path/'manifest.json.fernet')
    require(summary.get('encrypted') is True and summary.get('complete') is True and summary.get('database') == 'quillmd_fresh' and summary.get('run_id') == run_id, 'Not a completed fresh-system encrypted backup.')
    require(hashlib.sha256(cipher).hexdigest() == summary.get('manifest_cipher_sha256'), 'Backup manifest changed after verification.')
    manifest = json.loads(Fernet(read_private(key_path).strip()).decrypt(cipher))
    require(manifest.get('database') == 'quillmd_fresh' and manifest.get('run_id') == run_id and manifest.get('complete') is True, 'Authenticated backup manifest mismatch.')
    require(manifest.get('source_commit') == summary.get('source_commit'), 'Backup source evidence mismatch.')
    for count in ('table_count','row_count','file_count'):
        require(type(report.get(count)) is int and report[count] > 0 and report[count] == summary.get(count), 'Restore population does not match backup.')
    require(manifest.get('container_id') == output(['docker','inspect','--format','{{.Id}}','quillmd-fresh-postgres']), 'Backup belongs to another database container.')
    for item in [dict(manifest['dump'],object='database.dump.fernet'), *manifest['files']]:
        obj = backup_path/item['object']
        require(obj.resolve() == obj and obj.is_relative_to(backup_path), 'Invalid encrypted backup object path.')
        encrypted = read_private(obj)
        require(hashlib.sha256(encrypted).hexdigest() == item['cipher_sha256'], 'Encrypted backup object changed since restore.')
    return report


def files():
    root = APP / '.runtime/files'
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Private storage contains a symlink.')
        if path.is_file():
            require(path.stat().st_mode & 0o777 == 0o600, 'Private file permission differs from 0600.')
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def stamp_release(sha):
    env = APP / '.env'
    require(env.is_file() and not env.is_symlink() and env.stat().st_mode & 0o777 == 0o600, 'Private environment must be a regular0600 file.')
    lines = [x for x in env.read_text().splitlines() if not x.startswith('QUILLMD_RELEASE_SHA=')]
    tmp = APP / '.runtime/release-env.pending'
    with tmp.open('x') as f:
        tmp.chmod(0o600)
        f.write('\n'.join(lines) + '\nQUILLMD_RELEASE_SHA=' + sha + '\n')
        f.flush(); os.fsync(f.fileno())
    tmp.replace(env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Run from the shared main directory.')
    require(re.fullmatch(r'[a-f0-9]{40}', args.target), 'Target must be a full commit SHA.')
    require(output(['git','branch','--show-current']) == 'main', 'Shared tree must stay on main.')
    run(['git','diff','--exit-code','HEAD','--','.'])
    require(output(['git','show', args.target + ':scripts/update-private-beta.py']) == Path(__file__).read_text().strip(), 'Updater bytes do not match the reviewed target.')
    run(['git','merge-base','--is-ancestor','HEAD',args.target])
    require(output(['git','rev-parse','origin/main']) == args.target, 'Target must be the current origin/main PR merge.')
    require((APP/'.runtime').resolve() == APP/'.runtime', 'Runtime root must not be a symlink.')
    validate_restore_report(args.backup_report)
    protected()
    print('Verified cited target candidate, preserved runtime, protected services and restore evidence.', flush=True)
    if not args.execute:
        return
    require(Path(os.environ.get('RULED_MUTATION_DECLARATION', '')).name == '20260917-quillmd-private-beta-update.md', 'Committed update declaration required.')
    run(['bash','scripts/check-citation.sh',args.target])
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'previous_head': output(['git','rev-parse','HEAD']), 'head': args.target, 'complete': False}
    result_path = APP/'.runtime/private-beta-activation.json'
    try:
        print('Gracefully stopping private request handlers and worker before changing code.', flush=True)
        systemd('stop')
        for unit in UNITS:
            require(output(['systemctl','show',unit,'--property=ActiveState','--value']) == 'inactive', 'Private unit has not stopped cleanly.')
        states = output(['docker','exec','quillmd-fresh-postgres','psql','-U','quillmd_fresh','-d','quillmd_fresh','-X','-At','-c',"SELECT count(*) FROM core_job WHERE state IN ('running','queued')"])
        require(states == '0', 'Unfinished jobs require reconciliation before update; no provider retry attempted.')
        before_db, before_files = database_fingerprints(), files()
        result['before_database'] = before_db
        result['file_count'] = len(before_files)
        run(['git','merge','--ff-only',args.target])
        credentials = APP/'.runtime/db-role-secrets/fresh-db-roles.json'
        if credentials.exists():
            run([str(APP/'.venv/bin/python'),str(APP/'ops/with_db_role.py'),'--credentials',str(credentials),'--source',str(APP),'--role','migrator','--','migrate','--noinput'], cwd=APP)
        else:
            run([str(APP/'.venv/bin/python'),'manage.py','migrate','--noinput'], cwd=APP)
        run([str(APP/'.venv/bin/python'),'manage.py','check'], cwd=APP)
        run([str(APP/'.venv/bin/python'),'manage.py','collectstatic','--noinput'], cwd=APP)
        require(database_fingerprints() == before_db, 'New application data changed unexpectedly during schema update.')
        require(files() == before_files, 'New originals/exports/provider files changed during update.')
        stamp_release(args.target)
        run([str(APP/'.venv/bin/python'),str(APP/'ops/install_unit_policy.py'),'--expected-commit',args.target,'--execute'], cwd=APP)
        systemd('start')
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl','--fail','--silent',f'http://127.0.0.1:{port}/health/'])) for port in (9130,9131)]
                if all(h.get('release') == args.target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Private listener release/readiness proof failed.')
        require(all(output(['systemctl','is-active',x]) == 'active' for x in UNITS), 'A private unit is not active.')
        run(['bash','scripts/check-cotenants.sh'])
        result.update(complete=True, preserved_database=True, preserved_files=True, protected_containers=protected(), health=health)
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        fd = os.open(result_path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(fd,'w') as f:
            json.dump(result,f,indent=2)
        print('Private update evidence: '+str(result_path), flush=True)
    print('Private application update verified. Public routes remain in maintenance.', flush=True)


if __name__ == '__main__':
    main()
