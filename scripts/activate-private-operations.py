#!/usr/bin/env python3
"""Prepare or execute one preserving private QuillMD operations activation.

Run this reviewed file from its committed target worktree. Shared main must still
be the recorded baseline: this script stops the three private units BEFORE its
ff-only source advance. Default is read-only. Execution additionally requires the
committed declaration, exact merged-target CI, current encrypted restore proof,
and an exclusive operation lock. Failure leaves those services stopped; there is
no automatic rollback of code, schema, configuration, or application data.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import time
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
EVIDENCE = PRIVATE / 'overnight-completion-20260920'
SOURCE = Path(__file__).resolve().parents[1]
BASELINE = 'db5f54524a2b3bbda4eaa28a46612e9523966697'
RUNNING_RELEASE = '928897f4e934f1912855f96662617c6d0d9df629'
SELF = 'scripts/activate-private-operations.py'
DECL = 'docs/foundation/mutations/20260920-quillmd-overnight-completion.md'
MIGRATION = '0015_reconciliation_evidence_guard'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
MIGRATION_SHA256 = 'c749bb07a9325059b34a995b77d121ee065f8e07227f029520fa0dcdfec59e62'
FUNCTION = 'quillmd_reconciliation_evidence_guard'
TRIGGER = 'reconciliation_evidence_immutable'
PREVIOUS_MIGRATION = '0014_encounter_service_date'
UNITS = ['quillmd-fresh-' + x + '.service' for x in ('doctor', 'admin', 'worker')]
KEY = PRIVATE / 'backup-secrets/fresh-backup-current-20260917.key'
ROLES = PRIVATE / 'db-role-secrets/fresh-db-roles.json'
HELPERS = {
    'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
    'old': 'scripts/activate-word-export.py', 'previous': 'scripts/update-private-beta.py',
    'storage': 'rebuild/ops/private_storage.py', 'backup': 'rebuild/ops/backup_restore.py',
    'env': 'rebuild/ops/email_activation.py', 'billing': 'scripts/activate-billing-policy.py',
}
RUNTIME_ALLOWED = {
    SELF, MIGRATION_PATH, 'rebuild/core/views.py', 'rebuild/core/billing.py',
    'rebuild/core/admin_queries.py', 'rebuild/quillmd/urls.py',
    'rebuild/documents/engine.py', 'rebuild/documents/tests.py',
    'rebuild/ops/scheduled_backup.py', 'rebuild/ops/test_scheduled_backup.py',
    'rebuild/ops/test_private_operations_activation.py',
    'rebuild/ops/install_backup_schedule.py', 'rebuild/ops/test_install_backup_schedule.py',
    'rebuild/browser-tests.mjs',
    'rebuild/deploy/quillmd-fresh-backup.service', 'rebuild/deploy/quillmd-fresh-backup.timer',
    *('rebuild/templates/' + x + '.html' for x in ('admin_dashboard', 'audit', 'billing',
       'template_detail', 'financial_detail', 'pagination')),
    *('rebuild/core/tests/' + x + '.py' for x in ('test_internal_access_review',
       'test_admin_evidence', 'test_worker_financial_reliability', 'test_billing_policy',
       'test_wm_workflow', 'test_workflow', 'test_reconciliation_and_license_gates')),
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, timeout=600, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, timeout=600, **kwargs)


def git(*args):
    return output(['git', *args], cwd=ROOT)


def blob(target, relative):
    return subprocess.check_output(['git', 'show', target + ':' + relative], cwd=ROOT, timeout=60)


def load(name, relative, target):
    path = ROOT / relative
    data = path.read_bytes()
    require(data == blob(BASELINE, relative) == blob(target, relative), 'A reused qualified helper changed.')
    module = types.ModuleType('private_operations_' + name)
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def validate_changed(changed):
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in changed), 'Changed source path is not canonical.')
    required = {SELF, DECL, MIGRATION_PATH, 'rebuild/core/billing.py', 'rebuild/core/views.py',
                'rebuild/documents/engine.py', 'rebuild/ops/test_private_operations_activation.py'}
    require(required <= changed, 'Target omits required reviewed operation files.')
    require(all(name in RUNTIME_ALLOWED or (name.startswith('docs/rebuild/') and name.endswith('.md'))
                or name == DECL for name in changed), 'Target includes an undeclared source path.')
    require({x for x in changed if x.startswith('rebuild/core/migrations/')} == {MIGRATION_PATH},
            'Only the declared reconciliation guard migration may change.')


def updated_environment(original, target):
    require(re.fullmatch('[a-f0-9]{40}', target) and target != RUNNING_RELEASE, 'Full new target SHA required.')
    pattern = rb'(?m)^(?:export[ \t]+)?QUILLMD_RELEASE_SHA[ \t]*=[^\r\n]*(?:\r?\n|$)'
    matches = list(re.finditer(pattern, original))
    require(len(matches) == 1, 'Exactly one release setting is required.')
    from io import StringIO
    from dotenv import dotenv_values
    before = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    require(before.get('QUILLMD_RELEASE_SHA') == RUNNING_RELEASE, 'Unexpected configured release.')
    found = matches[0]
    ending = b'\r\n' if found[0].endswith(b'\r\n') else b'\n' if found[0].endswith(b'\n') else b''
    updated = original[:found.start()] + b'QUILLMD_RELEASE_SHA="' + target.encode() + b'"' + ending + original[found.end():]
    after = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    require(after.pop('QUILLMD_RELEASE_SHA') == target, 'Release serialization failed.')
    before.pop('QUILLMD_RELEASE_SHA')
    require(before == after, 'An integration or other setting changed.')
    return updated


def verify_migration_plan(plan, *, applied):
    rows = [re.fullmatch(r'\[([X ])\][ \t]+([a-z_][a-z_0-9]*\.[a-z_0-9]+)', line.strip())
            for line in plan.splitlines() if line.strip()]
    require(rows and all(rows), 'Migration plan cannot be parsed completely.')
    names = [row[2] for row in rows]
    require(len(names) == len(set(names)) and 'core.' + PREVIOUS_MIGRATION in names
            and 'core.' + MIGRATION in names, 'Expected migration chain is absent or repeated.')
    require([row[2] for row in rows if row[1] != 'X'] == ([] if applied else ['core.' + MIGRATION]),
            'Migration plan has an unexpected pending operation.')


def validate_migration(source):
    require(sha(source) == MIGRATION_SHA256, 'Migration bytes differ from the reviewed one-function/one-trigger change.')


def retained_source_manifest(archive):
    """Describe exact prior tracked bytes without extracting or trusting tar paths."""
    require(len(archive) <= 64 * 1024 * 1024, 'Rollback source exceeds bounded scope.')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as bundle:
        for member in bundle:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and path.parts[0] == 'rebuild'
                    and '..' not in path.parts and str(path) == member.name.rstrip('/'), 'Unsafe retained source path.')
            if member.isdir():
                continue
            require(member.isfile() and not member.issym() and not member.islnk()
                    and member.name not in files and 0 <= member.size <= 32 * 1024 * 1024
                    and '.env' not in path.parts and '.runtime' not in path.parts,
                    'Retained source has a link, duplicate, secret path or oversized file.')
            data = bundle.extractfile(member).read()
            require(len(data) == member.size, 'Retained source file is incomplete.')
            files[member.name] = {'sha256': sha(data), 'bytes': len(data), 'mode': member.mode}
            require(len(files) <= 2000, 'Retained source file count exceeds scope.')
    require(files and 'rebuild/manage.py' in files, 'Prior application source is absent.')
    return {'commit': BASELINE, 'archive_sha256': sha(archive), 'archive_bytes': len(archive), 'files': files,
            'recovery_policy': ['Keep all three private services stopped after any failed check.',
                'Inspect preserved failure and stopped-state fingerprints before a repair.',
                'Prefer a reviewed forward repair; otherwise prepare a scoped revert PR restoring these exact prior runtime bytes.',
                'Retain any applied 0015 guard, its migration file and history row; do not reverse schema or restore the database.',
                'Do not replace configuration with the saved copy if subsequent settings changed. Preserve those settings and stamp only the exact cited recovery commit.',
                'Activate the cited recovery through a newly scoped declaration and preserving stopped-state checks. Never reset main or claim a stamp alone restores code.']}


def stopped():
    for unit in UNITS:
        require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0',
                'Every private service must be stopped before source changes.')


def catalog(old):
    functions = json.loads(output(old.PSQL + ["""SELECT coalesce(jsonb_agg(jsonb_build_object(
      'name',p.oid::regprocedure::text,'owner',pg_get_userbyid(p.proowner),'language',l.lanname,
      'security_definer',p.prosecdef,'config',p.proconfig,'acl',p.proacl,'body',p.prosrc,
      'definition',pg_get_functiondef(p.oid)) ORDER BY p.oid::regprocedure::text),'[]')
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang
      WHERE n.nspname='public' AND p.prokind='f'"""]))
    triggers = json.loads(output(old.PSQL + ["""SELECT coalesce(jsonb_agg(jsonb_build_object(
      'table',c.relname,'name',t.tgname,'function',p.proname,'type',t.tgtype,'enabled',t.tgenabled,
      'args',encode(t.tgargs,'hex'),'when',pg_get_expr(t.tgqual,t.tgrelid),'definition',pg_get_triggerdef(t.oid))
      ORDER BY c.relname,t.tgname),'[]') FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid
      WHERE n.nspname='public' AND NOT t.tgisinternal"""]))
    return {'functions': functions, 'triggers': triggers}


def check_catalog(before, after, expected_body):
    new_functions = [x for x in after['functions'] if x['name'] == FUNCTION + '()']
    new_triggers = [x for x in after['triggers'] if x['name'] == TRIGGER]
    require(not any(x['name'] == FUNCTION + '()' for x in before['functions'])
            and not any(x['name'] == TRIGGER for x in before['triggers']), 'Guard already exists before activation.')
    require(len(new_functions) == len(new_triggers) == 1, 'Exactly one declared function and trigger must be added.')
    f, t = new_functions[0], new_triggers[0]
    require(f['owner'] == 'quillmd_owner' and f['language'] == 'plpgsql' and not f['security_definer']
            and f['config'] is None and f['acl'] is None and f['body'].strip() == expected_body.strip(),
            'Added function differs from the reviewed guard or privileges.')
    require(t['table'] == 'core_costreconciliation' and t['function'] == FUNCTION and t['type'] == 27
            and t['enabled'] == 'O' and t['args'] == '' and t['when'] is None, 'Added trigger is not the enabled unconditional row guard.')
    require([x for x in after['functions'] if x is not f] == before['functions']
            and [x for x in after['triggers'] if x is not t] == before['triggers'], 'An existing function or trigger changed.')


def rows(old, *, exclude_new=False):
    result = {}
    for name in old.tables():
        where = " WHERE NOT (app='core' AND name='" + MIGRATION + "')" if exclude_new and name == 'django_migrations' else ''
        data = subprocess.check_output(old.PSQL + [f'COPY (SELECT to_jsonb(t)::text AS value FROM "{name}" t{where} ORDER BY value) TO STDOUT'], timeout=600)
        result[name] = {'rows': len(data.splitlines()), 'sha256': sha(data)}
    return result


def unit_files(word):
    result = {}
    for unit in UNITS:
        installed = Path('/etc/systemd/system') / unit
        require(installed.read_bytes() == (APP / 'deploy' / unit).read_bytes(), 'Private unit differs from reviewed source.')
        for path in [installed, *sorted(installed.with_name(unit + '.d').glob('*.conf'))]:
            require(path.resolve() == path and path.is_file() and not path.is_symlink(), 'Unexpected service policy path.')
            result[str(path)] = sha(path.read_bytes())
    return result


def shared_configs(helper_image):
    """Hash protected configuration using the qualified image, without reading it into the operator process."""
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper_image), 'Pinned hash helper required.')
    code = r'''import hashlib,json,pathlib,sys
try:
 roots=(pathlib.Path('/etc/ssh'),pathlib.Path('/etc/nginx'))
 paths=[roots[0]/'sshd_config',roots[1]/'nginx.conf']
 for directory,pattern in (('/etc/ssh/sshd_config.d','*.conf'),('/etc/nginx/conf.d','*.conf'),('/etc/nginx/sites-enabled','*')):
  paths.extend(sorted(pathlib.Path(directory).glob(pattern)))
 result={}
 for path in paths:
  resolved=path.resolve(strict=True)
  assert any(resolved.is_relative_to(root) for root in roots)
  assert path.is_file() and path.stat().st_size<=5*1024*1024
  result[str(path)]={'resolved':str(resolved),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 print(json.dumps(result,sort_keys=True))
except Exception:
 sys.exit(1)
'''
    command = ['docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--read-only',
               '--cap-drop=ALL', '--security-opt=no-new-privileges:true', '--user', '0:0',
               '--pids-limit=32', '--memory=128m', '--mount', 'type=bind,src=/etc/ssh,dst=/etc/ssh,readonly',
               '--mount', 'type=bind,src=/etc/nginx,dst=/etc/nginx,readonly', helper_image, 'python', '-B', '-']
    result = subprocess.run(command, input=code, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(result.returncode == 0, 'Protected configuration hash helper failed; no contents or stderr disclosed.')
    inventory = json.loads(result.stdout)
    require({'/etc/ssh/sshd_config', '/etc/nginx/nginx.conf'} <= inventory.keys()
            and all(set(row) == {'resolved', 'sha256'} and re.fullmatch('[a-f0-9]{64}', row['sha256'])
                    for row in inventory.values()), 'Protected hash inventory is incomplete.')
    return inventory


def backup_evidence(path, modules, current_directory=None):
    word, backup = modules['word'], modules['backup']
    path = Path(path)
    require(path.resolve() == path and path.name == 'verification.json'
            and path.parent.parent == PRIVATE / 'restore-checks', 'Use the authoritative private restore verification report.')
    report = json.loads(word.checked_file(path, private=True))
    for key in ('complete', 'all_table_hashes_match', 'all_file_hashes_match', 'restore_database_on_tmpfs_without_swap'):
        require(report.get(key) is True, 'A complete encrypted restore proof is required.')
    require(report.get('network') == 'none' and report.get('published_ports') == 0
            and report.get('workers_started') == report.get('provider_actions') == report.get('decrypted_files_written') == 0
            and report.get('provider_credentials_copied') is False and report.get('container_retained') is False
            and not report.get('cleanup_failed') and report.get('invariants')
            and all(value == 0 for value in report['invariants'].values()), 'Restore isolation, cleanup or invariants failed.')
    run_id = report.get('backup_run_id', '')
    require(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', run_id), 'Invalid backup identity.')
    from cryptography.fernet import Fernet
    cipher = Fernet(word.checked_file(KEY, private=True, limit=1024).strip())
    destination, manifest = backup.load_backup(PRIVATE / 'new-system-backups' / run_id, cipher)
    summary = json.loads(word.checked_file(destination / 'summary.json', private=True))
    require(manifest['run_id'] == run_id and manifest['source_commit'] == BASELINE
            and summary['manifest_cipher_sha256'] == sha(word.checked_file(destination / 'manifest.json.fernet', private=True)), 'Backup identity/source/authentication mismatch.')
    require(manifest['container_id'] == output(['docker', 'inspect', '--format', '{{.Id}}', 'quillmd-fresh-postgres']), 'Backup belongs to another live database.')
    for key in ('table_count', 'row_count', 'file_count'):
        require(report.get(key) == summary.get(key), 'Restore population does not match its encrypted backup.')
    require(summary.get('complete') is True and summary.get('encrypted') is True
            and report['table_count'] == len(manifest['tables'])
            and report['row_count'] == sum(x['rows'] for x in manifest['tables'].values())
            and report['file_count'] == len(manifest['files']), 'Restore population differs from authenticated manifest.')
    for item in [dict(manifest['dump'], object='database.dump.fernet'), *manifest['files']]:
        require(sha(word.checked_file(destination / item['object'], private=True)) == item['cipher_sha256'], 'Restored encrypted backup object changed.')
    # A final capture may include later audit/session rows. The already completed
    # isolated restore proves this exact source/schema backup mechanism, while the
    # fresh authenticated capture protects the exact stopped state. Keep these
    # distinct: do not describe an un-restored final capture as restored.
    if current_directory:
        current = Path(current_directory)
        require(current.resolve() == current and current.parent == PRIVATE / 'new-system-backups'
                and re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', current.name), 'Use the exact protected final capture directory.')
        destination, latest = backup.load_backup(current, cipher)
        latest_summary = json.loads(word.checked_file(current / 'summary.json', private=True))
        require(latest['source_commit'] == manifest['source_commit'] == BASELINE
                and latest['container_id'] == manifest['container_id']
                and set(latest['tables']) == set(manifest['tables'])
                and latest.get('invariants') == manifest.get('invariants')
                and latest_summary.get('complete') is True and latest_summary.get('encrypted') is True
                and latest_summary.get('run_id') == latest['run_id'] == current.name
                and latest_summary.get('manifest_cipher_sha256') == sha(word.checked_file(current / 'manifest.json.fernet', private=True)), 'Final capture differs from the restored mechanism/schema/source or failed authentication.')
        manifest = latest
    for item in [dict(manifest['dump'], object='database.dump.fernet'), *manifest['files']]:
        require(sha(word.checked_file(destination / item['object'], private=True)) == item['cipher_sha256'], 'Encrypted backup object changed.')
    return report, manifest


def assert_backup_current(manifest, modules, storage):
    backup = modules['backup']
    import psycopg
    with psycopg.connect(**backup.source_options(APP, ROLES), autocommit=True) as conn:
        conn.execute("SET timezone='UTC'")
        conn.execute("SET datestyle='ISO, MDY'")
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        def copy_hash(sql):
            digest = hashlib.sha256()
            with conn.cursor().copy(sql) as stream:
                for data in stream:
                    digest.update(data)
            return digest.hexdigest()
        actual = backup.fingerprint(lambda sql: conn.execute(sql).fetchall(), copy_hash)
        require(actual == manifest['tables'], 'The authenticated backup no longer covers every current row; take a fresh final encrypted capture of the already restored source/schema mechanism.')
        conn.execute('ROLLBACK')
    for item in manifest['files']:
        got = storage.get(item['path'])
        require(got and got.get('sha256') == item['sha256'] and got.get('size') == item['size'], 'A backed-up private file changed.')


def snapshot(modules, helper_image):
    old, storage, identity, word = (modules[k] for k in ('old', 'storage', 'identity', 'word'))
    return {'tables': old.tables(), 'rows': rows(old), 'schema': old.schema(),
            'constraints': old.constraints(), 'indexes': old.indexes(), 'catalog': catalog(old),
            'clinical': old.clinical_counts(),
            'storage': {name: storage.inventory(Path('/var/lib/quillmd') / name) for name in ('files', 'mail')},
            'static': old.static_inventory(identity, word), 'unit_files': unit_files(word), 'shared_configs': shared_configs(helper_image)}


def validate_after(before, after, expected_body):
    for key in before.keys() - {'rows', 'catalog'}:
        require(after[key] == before[key], 'Undeclared stopped-state delta: ' + key)
    require(after['rows'] == before['rows'], 'An existing row changed; no automatic restore or rewrite is allowed.')
    check_catalog(before['catalog'], after['catalog'], expected_body)


def management(*command):
    return [str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'),
            '--credentials', str(ROLES), '--source', str(APP), '--role', 'migrator', '--', *command]


def health(target):
    rows_ = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{port}/health/']))
             for port in (9130, 9131)]
    require(all(row.get('release') == target and row.get('data_mode') == 'synthetic-only' for row in rows_), 'Private health release/gate mismatch.')
    require([row.get('surface') for row in rows_] == ['doctor', 'admin'], 'Private surface mismatch.')
    return rows_


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--backup-directory', help='Optional fresh final capture after the already demonstrated same-source isolated restore.')
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merged target.')
    require(SOURCE.is_relative_to(ROOT / '.worktrees') and SOURCE.resolve() == SOURCE, 'Run the reviewed target file from its retained worktree.')
    require(git('rev-parse', 'HEAD') == BASELINE and git('branch', '--show-current') == 'main'
            and git('rev-parse', 'origin/main') == args.target, 'Shared main must remain at baseline until services stop.')
    require(not git('status', '--porcelain', '--untracked-files=no'), 'Tracked shared main must be clean.')
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target], cwd=ROOT)
    require(not git('diff', '--name-only', RUNNING_RELEASE, BASELINE, '--', 'rebuild'), 'Baseline differs from served runtime.')
    changed = set(git('diff', '--name-only', BASELINE, args.target).splitlines())
    validate_changed(changed)
    require(Path(__file__).read_bytes() == blob(args.target, SELF), 'Activator differs from reviewed target source.')
    validate_migration(blob(args.target, MIGRATION_PATH))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target and p.get('base', {}).get('ref') == 'main' for p in pulls), 'Exact merged PR required.')
    run(['bash', str(ROOT / 'scripts/check-citation.sh'), args.target], cwd=ROOT)
    modules = {name: load(name, relative, args.target) for name, relative in HELPERS.items()}
    old, word, identity, storage, previous = (modules[k] for k in ('old', 'word', 'identity', 'storage', 'previous'))
    original = word.checked_file(APP / '.env', private=True)
    updated = updated_environment(original, args.target)
    report, manifest = backup_evidence(args.backup_report, modules, args.backup_directory)
    require(len(old.tables()) == 35 and output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Unexpected tables or unresolved jobs.')
    require(output(old.PSQL + ["SELECT name FROM django_migrations WHERE app='core' ORDER BY id DESC LIMIT 1"]) == PREVIOUS_MIGRATION, 'Unexpected current migration.')
    before_health = health(RUNNING_RELEASE)
    before_proofs = identity.verify_live(RUNNING_RELEASE, storage)
    worker_before = old.worker_process()
    protected = previous.protected()
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper) and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper, 'Pinned service helper unavailable.')
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Installed Word SDK inputs may not change.')
    installed = APP / '.word-sdk' / modules['billing'].SDK_RELEASE
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', modules['billing'].PIN, inputs)
    baseline = snapshot(modules, helper)
    assert_backup_current(manifest, modules, baseline['storage']['files'])
    result_path = Path(args.result)
    lock = PRIVATE / '.private-operations-activation.lock'
    state = EVIDENCE / ('activation-state-' + args.target[:12])
    require(result_path.is_absolute() and result_path.resolve() == result_path and result_path.parent == EVIDENCE
            and re.fullmatch(r'private-operations-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not any(p.exists() or p.is_symlink() for p in (result_path, lock, state)), 'Unused private result/lock/state required.')
    run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
    print('Read-only activation checks passed; no source, schema, service or integration changed.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration == SOURCE / DECL
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == blob(args.target, DECL) == blob(commit, DECL), 'Committed exact target declaration is required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target], cwd=ROOT)
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid(), 'automatic_rollback': False})
    state.mkdir(mode=0o700)
    result = {'complete': False, 'stage': 'stop_before_source_advance', 'started_at': datetime.now(timezone.utc).isoformat(),
              'baseline': BASELINE, 'served_before': RUNNING_RELEASE, 'target': args.target, 'changed_paths': sorted(changed),
              'backup_report': args.backup_report, 'backup_run_id': manifest['run_id'],
              'restored_backup_run_id': report['backup_run_id'], 'current_capture_restored': manifest['run_id'] == report['backup_run_id'], 'provider_calls': 0,
              'before_health': before_health, 'before_proofs': before_proofs, 'worker_before': worker_before,
              'rollback_policy': 'Stop on failure. Retain prior code/config. Cited forward repair preferred; no automatic code, schema or data rollback.',
              'state_directory': str(state), 'environment_before_sha256': sha(original), 'environment_after_sha256': sha(updated)}
    phase = 0
    def checkpoint(stage):
        nonlocal phase
        result['stage'] = stage
        identity.private_write(state / f'phase-{phase:02d}.json', result)
        phase += 1
    try:
        checkpoint('stop_before_source_advance')
        word.systemd('stop', helper)
        stopped()
        require(git('rev-parse', 'HEAD') == BASELINE and not git('status', '--porcelain', '--untracked-files=no'), 'Shared source changed before stop.')
        require(output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Job appeared during drain.')
        baseline = snapshot(modules, helper)
        result['stopped_before'] = baseline
        assert_backup_current(manifest, modules, baseline['storage']['files'])
        require(word.checked_file(APP / '.env', private=True) == original, 'Environment changed before stopped-state capture.')
        archive = subprocess.check_output(['git', 'archive', '--format=tar', BASELINE, 'rebuild'], cwd=ROOT, timeout=60)
        source_manifest = retained_source_manifest(archive)
        for name, data in (('prior-runtime-source.tar', archive), ('prior-environment.env', original)):
            fd = os.open(state / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        result['retained_source'] = {'commit': BASELINE, 'bytes': len(archive), 'sha256': sha(archive), 'environment_sha256': sha(original)}
        identity.private_write(state / 'prior-runtime-manifest.json', source_manifest)
        checkpoint('advance_stopped_source_ff_only')
        stopped()
        run(['git', 'merge', '--ff-only', args.target], cwd=ROOT, stdout=subprocess.DEVNULL)
        require(git('rev-parse', 'HEAD') == args.target and not git('status', '--porcelain', '--untracked-files=no'), 'Source advance differs from exact target.')
        require(unit_files(word) == baseline['unit_files'], 'Existing service policy changed during source advance.')
        verify_migration_plan(output(management('showmigrations', '--plan'), cwd=APP), applied=False)
        validate_migration((ROOT / MIGRATION_PATH).read_bytes())
        checkpoint('apply_only_declared_reconciliation_guard')
        run(management('migrate', 'core', MIGRATION, '--noinput'), cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        verify_migration_plan(output(management('showmigrations', '--plan'), cwd=APP), applied=True)
        require(output(old.PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '1', 'Exactly one migration history row required.')
        run(management('check'), cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        expected_body = blob(args.target, MIGRATION_PATH).decode().split('AS $$', 1)[1].split('$$;', 1)[0]
        after = snapshot(modules, helper); after['rows'] = rows(old, exclude_new=True)
        validate_after(baseline, after, expected_body)
        result['stopped_after_migration'] = after
        result['source_readability'] = identity.source_readability(helper)
        checkpoint('replace_release_setting_only')
        modules['env'].replace_environment(APP / '.env', original, updated)
        checkpoint('start_and_verify_exact_private_release')
        word.systemd('start', helper)
        for attempt in range(45):
            try:
                live_health = health(args.target)
                break
            except (subprocess.CalledProcessError, json.JSONDecodeError, RuntimeError):
                time.sleep(1)
        else:
            raise RuntimeError('New private release did not become healthy.')
        result['proofs_after'] = identity.verify_live(args.target, storage)
        result['interfaces_after'] = identity.verify_interfaces()
        worker_after = old.worker_process()
        require(worker_after['systemd_start'] != worker_before['systemd_start'] and worker_after['kernel_start_utc'] > worker_before['kernel_start_utc'], 'Worker restart not evidenced.')
        result['worker_after'] = worker_after
        final = snapshot(modules, helper); final['rows'] = rows(old, exclude_new=True)
        validate_after(baseline, final, expected_body)
        require(word.checked_file(APP / '.env', private=True) == updated and previous.protected() == protected, 'Configuration or protected services changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', modules['billing'].PIN, inputs) == artifact, 'Installed Word SDK changed.')
        run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
        result.update(complete=True, stage='complete', health=live_health, existing_rows_unchanged=True,
                      schema_columns_indexes_constraints_unchanged=True, only_new_function_and_trigger=True,
                      private_files_mail_and_static_unchanged=True, backup_units_installed=False,
                      finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint('complete')
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(failure_kind=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
        try:
            word.systemd('stop', helper); stopped(); result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False; result['stop_failure_kind'] = type(stop_error).__name__
        identity.private_write(result_path, result)
        raise RuntimeError('Private activation stopped; inspect private evidence. No automatic rollback or retry.') from None
    print('Private activation verified; evidence: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
