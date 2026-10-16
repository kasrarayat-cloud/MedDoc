"""One declared native Rowan/Corti installation. No action without --execute.

This composes the installed service/locking/static publication primitives. The
plan binds a reviewed merge, the complete source delta, one additive migration,
three public assets and narrowly named environment values. It never invokes a
provider or submits a clinician decision. Existing output directories refuse.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat
import subprocess
import sys
import time

from dotenv import dotenv_values
import dotenv
from . import activation_exclusion, backup_restore, legacy_model_activation as legacy
from . import managed_helper, private_storage

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
SOURCE = Path(__file__).resolve().parents[2]
BASE = 'd7c6dee0496f43f9917c09feed2a58c527b45b0b'
MIGRATION = '0029_bounded_output_decision'
NEW_TABLE = 'core_codingoutputdecision'
STATIC = frozenset({'coding.js', 'coding.css', 'encounter-live.js'})
CREDENTIAL_SOURCE = Path('/etc/quillmd-corti-test/credentials.env')
CREDENTIAL_TARGET = Path('/var/lib/quillmd/provider-secrets/corti/credentials.env')
FORMAT = 'quillmd-rowan-corti-native-install-v1'
ENVIRONMENT_KEYS = frozenset({'QUILLMD_CORTI_CODING_MODE', 'QUILLMD_CORTI_CREDENTIALS_FILE',
    'QUILLMD_CORTI_NEW_ENCOUNTERS_SINCE', 'QUILLMD_CORTI_NEW_ENCOUNTER_ACTORS',
    'QUILLMD_CORTI_OUTPUT_REFERENCE_FILE', 'QUILLMD_CORTI_OUTPUT_REFERENCE_SHA256'})
GUARD = APP / '.runtime/standing-testing-authority-20261009/native-review-v1/source_publication_guard_standing_v3.py'
GUARD_SHA = '13be30775df7ae6f0fc0266e8c1b148ef2bd8aabac8fc954e26b8fdc18b00300'
UNITS = legacy.UNITS


class Refusal(RuntimeError):
    """Only fixed, non-sensitive labels may escape the operational boundary."""


def require(value, label):
    if not value:
        raise Refusal(label)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def command(argv, *, cwd=None, env=None, timeout=60, data=None, umask=None):
    options = {} if umask is None else {'umask': umask}
    result = subprocess.run(argv, cwd=cwd, env=env, input=data, capture_output=True, timeout=timeout, **options)
    require(result.returncode == 0, 'bounded_command_failed')
    return result.stdout


def git(*arguments, repo=ROOT, publication=False):
    return command(['git', '-C', str(repo), *arguments], umask=0o022 if publication else None)


def write_new(path, value):
    raw = value if isinstance(value, bytes) else encode(value) + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno())


def private_json(path):
    raw = backup_restore.read_private(path, 2 * 1024**2)
    return json.loads(raw), sha(raw)


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'source_sha256',
        'environment', 'evidence_directory', 'source_worktree', 'environment_before_sha256'}, 'closed_plan')
    require(plan['format'] == FORMAT and plan['base'] == BASE
            and re.fullmatch('[a-f0-9]{40}', plan['candidate']) and plan['candidate'] != BASE, 'exact_revision')
    paths = plan['source_sha256']
    require(type(paths) is dict and 0 < len(paths) <= 180, 'finite_source_manifest')
    for name, digest in paths.items():
        path = PurePosixPath(name)
        require(name == str(path) and not path.is_absolute() and len(name) <= 240
                and not any(p.startswith('.') or p in {'node_modules', 'uploads', 'backups'} for p in path.parts)
                and name.startswith(('rebuild/', 'docs/', 'scripts/'))
                and (path.suffix in {'.py', '.html', '.md', '.json', '.cjs', '.mjs', '.js', '.css', '.sh'}
                     or name in {'rebuild/core/tests/fixtures/rowan/source.txt', 'rebuild/core/tests/fixtures/corti/README.txt'})
                and re.fullmatch('[a-f0-9]{64}', digest), 'public_exact_source_path')
        if '/migrations/' in name:
            require(name == 'rebuild/core/migrations/' + MIGRATION + '.py', 'one_additive_migration')
    require('rebuild/core/migrations/' + MIGRATION + '.py' in paths, 'migration_bound')
    require(all('rebuild/static/' + n in paths for n in STATIC), 'static_sources_bound')
    env = plan['environment']
    require(type(env) is dict and set(env) == ENVIRONMENT_KEYS, 'closed_environment_delta')
    require(env['QUILLMD_CORTI_CODING_MODE'] == 'live'
            and env['QUILLMD_CORTI_CREDENTIALS_FILE'] == str(CREDENTIAL_TARGET), 'direct_synthetic_mode')
    require(all(type(v) is str and v and '\n' not in v and '\r' not in v and '"' not in v
                and '\\' not in v and '\x00' not in v for v in env.values()), 'safe_environment_values')
    cutoff = datetime.fromisoformat(env['QUILLMD_CORTI_NEW_ENCOUNTERS_SINCE'])
    require(cutoff.tzinfo is not None, 'prospective_cutoff_timezone')
    require(env['QUILLMD_CORTI_NEW_ENCOUNTER_ACTORS'] == '5f4d1a3d-eeb6-4207-b1df-4597dc696e82', 'one_existing_synthetic_actor')
    reference = Path(env['QUILLMD_CORTI_OUTPUT_REFERENCE_FILE'])
    require(reference == APP / 'ops/fixtures/corti_rowan_output_reference.json', 'committed_reference_path')
    relative = reference.relative_to(ROOT).as_posix()
    require(paths.get(relative) == env['QUILLMD_CORTI_OUTPUT_REFERENCE_SHA256'], 'reference_source_binding')
    require(re.fullmatch('[a-f0-9]{64}', plan['environment_before_sha256']), 'environment_pin')
    out = Path(plan['evidence_directory']); source = Path(plan['source_worktree'])
    require(out.is_absolute() and out.parent.resolve() == out.parent and not out.exists()
            and out.parent.stat().st_uid == os.getuid() and stat.S_IMODE(out.parent.stat().st_mode) == 0o700,
            'exclusive_private_output')
    require(source.is_absolute() and source.resolve() == source and source == SOURCE, 'exact_operator_worktree')
    return plan


def render_environment(original, values, revision):
    parsed = dotenv_values(stream=io.StringIO(original.decode()), interpolate=False)
    require(parsed.get('QUILLMD_RELEASE_SHA') == BASE and parsed.get('QUILLMD_CODING_PROVIDER', 'existing') == 'existing',
            'original_provider_and_release')
    require(all(k not in parsed for k in ENVIRONMENT_KEYS), 'new_activation_not_reused')
    replacements = {'QUILLMD_RELEASE_SHA': revision, **values}
    lines, found = [], set()
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', line)
        key = match[1].decode() if match else ''
        if key in replacements:
            require(key not in found, 'duplicate_environment_key'); found.add(key)
            lines.append((key + '="' + replacements[key] + '"\n').encode())
        else:
            lines.append(line)
    if lines and not lines[-1].endswith(b'\n'):
        lines.append(b'\n')
    lines.extend((k + '="' + replacements[k] + '"\n').encode() for k in sorted(set(replacements) - found))
    after = b''.join(lines)
    new = dotenv_values(stream=io.StringIO(after.decode()), interpolate=False)
    require({k: v for k, v in parsed.items() if k not in replacements}
            == {k: v for k, v in new.items() if k not in replacements}, 'unrelated_environment_preserved')
    require(all(new[k] == v for k, v in replacements.items()), 'environment_roundtrip')
    return after


def source_guard():
    raw = GUARD.read_bytes(); require(sha(raw) == GUARD_SHA, 'existing_source_guard_pin')
    spec = importlib.util.spec_from_loader('_rowan_source_guard', loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(GUARD), 'exec'), mod.__dict__)
    return mod


def source_plan(plan, guard):
    paths = sorted(plan['source_sha256'])
    require(git('branch', '--show-current').strip() == b'main'
            and git('rev-parse', 'HEAD').decode().strip() == BASE
            and not git('status', '--porcelain', '--untracked-files=no').strip(), 'clean_installed_main')
    require(git('rev-parse', 'origin/main').decode().strip() == plan['candidate'], 'merged_origin_main')
    git('merge-base', '--is-ancestor', BASE, plan['candidate'])
    actual = git('diff', '--name-only', '--no-renames', BASE, plan['candidate']).decode().splitlines()
    require(sorted(actual) == paths, 'exact_complete_source_delta')
    require(git('rev-parse', 'HEAD', repo=SOURCE).decode().strip() == plan['candidate']
            and not git('status', '--porcelain', '--untracked-files=no', repo=SOURCE).strip(), 'clean_candidate')
    status = git('diff', '--name-status', '--no-renames', BASE, plan['candidate']).decode().splitlines()
    require(all(x.split('\t')[0] in {'A', 'M'} for x in status), 'no_source_deletion')
    account = pwd.getpwnam('quillmd-app')
    binding = {'base': BASE, 'owner_uid': os.getuid(), 'owner_gid': os.getgid(),
               'service_identity': {'uid': account.pw_uid, 'gids': [account.pw_gid]}}
    before = guard.tree_entries(ROOT, BASE, paths); after = guard.tree_entries(ROOT, plan['candidate'], paths)
    require({k: v['sha256'] for k, v in after.items()} == plan['source_sha256'], 'committed_source_hashes')
    for name, entry in before.items():
        guard.file_proof(ROOT, name, entry, binding, revision=BASE)
    for name, entry in after.items():
        require(sha((SOURCE / name).read_bytes()) == entry['sha256'], 'candidate_disk_bytes')
        if name not in before:
            require(not (ROOT / name).exists(), 'new_path_absent')
    return {'binding': binding, 'before': before, 'after': after}


def publish_source(plan, guard, prepared):
    require(git('rev-parse', 'HEAD').decode().strip() == BASE
            and not git('status', '--porcelain', '--untracked-files=no').strip(), 'source_prepublication_identity')
    hook = Path(git('rev-parse', '--git-path', 'hooks/post-merge').decode().strip())
    if not hook.is_absolute():
        hook = ROOT / hook
    require(not hook.exists() and not hook.is_symlink(), 'no_post_merge_hook')
    for name, entry in prepared['before'].items():
        guard.file_proof(ROOT, name, entry, prepared['binding'], revision=BASE)
    git('merge', '--ff-only', plan['candidate'], publication=True)
    require(guard.current_umask() == 0o077, 'private_operator_umask_preserved')
    for name, entry in prepared['after'].items():
        guard.file_proof(ROOT, name, entry, prepared['binding'], revision=plan['candidate'])
    require(not git('status', '--porcelain', '--untracked-files=no').strip(), 'published_clean')


def static_delta(before, staged):
    replaceable = {'staticfiles.json'} | {n + suffix for n in STATIC for suffix in ('', '.gz')}
    changed = {}
    for name, row in staged.items():
        if row['kind'] == 'directory':
            require(name == '.', 'flat_static_stage'); continue
        old = before.get(name)
        if old is not None and all(old.get(k) == row[k] for k in ('kind', 'mode', 'size', 'sha256')):
            continue
        require(old is None or name in replaceable, 'immutable_static_preserved')
        changed[name] = row
    return changed


def stage_static(plan, directory, primitives):
    root = APP / 'staticfiles'; before = primitives.static_inventory(root)
    require(not any(n + '.br' in before for n in STATIC), 'unexpected_brotli_alias_requires_review')
    manifest = json.loads((root / 'staticfiles.json').read_bytes())
    stage = directory / 'static-stage'; primitives.create_static_stage(stage)
    original_paths = dict(manifest['paths'])
    for name in sorted(STATIC):
        raw = (SOURCE / 'rebuild/static' / name).read_bytes()
        require(sha(raw) == plan['source_sha256']['rebuild/static/' + name], 'static_source_hash')
        suffix = Path(name).suffix
        hashed = name[:-len(suffix)] + '.' + hashlib.md5(raw).hexdigest()[:12] + suffix
        manifest['paths'][name] = hashed
        for target, content in ((name, raw), (hashed, raw), (name + '.gz', gzip.compress(raw, mtime=0)),
                                (hashed + '.gz', gzip.compress(raw, mtime=0))):
            (stage / target).write_bytes(content); (stage / target).chmod(0o644)
    require(all(manifest['paths'][n] == v for n, v in original_paths.items() if n not in STATIC), 'other_static_routes_unchanged')
    manifest['hash'] = hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12]
    (stage / 'staticfiles.json').write_text(json.dumps(manifest)); (stage / 'staticfiles.json').chmod(0o644)
    staged = primitives.static_inventory(stage)
    static_delta(before, staged)
    primitives.retain_static(root, directory / 'static-before.tar', before)
    return stage, before, staged


def database_options(original, owner=False):
    values = dotenv_values(stream=io.StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_DB_NAME') == 'quillmd_fresh'
            and values.get('QUILLMD_DB_USER') == 'quillmd_runtime'
            and values.get('QUILLMD_DB_HOST', '127.0.0.1') == '127.0.0.1'
            and values.get('QUILLMD_DB_PORT', '55438') == '55438', 'fixed_native_database')
    result = dict(dbname='quillmd_fresh', user='quillmd_runtime', password=values['QUILLMD_DB_PASSWORD'],
                  host='127.0.0.1', port=55438, connect_timeout=5)
    if owner:
        roles = json.loads(backup_restore.read_private(legacy.ROLES, 16384))
        require(roles['database'] == 'quillmd_fresh' and roles['container_id'] ==
                backup_restore.inspect_container('quillmd-fresh-postgres')['Id'], 'migrator_container_binding')
        role = roles['roles']['migrator']; require(role['name'] == 'quillmd_migrator', 'migrator_role')
        result.update(user=role['name'], password=role['password'], options='-c role=quillmd_owner')
    return result


def database_snapshot(original):
    import psycopg
    from psycopg import sql
    with psycopg.connect(**database_options(original)) as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        require(connection.execute("SELECT current_database(),current_user,current_setting('transaction_read_only')").fetchone()
                == ('quillmd_fresh', 'quillmd_runtime', 'on'), 'readonly_snapshot')
        connection.execute("SET LOCAL statement_timeout='90s'")
        tables = [x[0] for x in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        rows = {}
        for name in tables:
            query = sql.SQL("SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,'|' ORDER BY to_jsonb(t)::text),'')) FROM {} t").format(sql.Identifier(name))
            rows[name] = list(connection.execute(query).fetchone())
        migration_rows = [list(x) for x in connection.execute('SELECT app,name FROM django_migrations ORDER BY app,name')]
        pending = {}
        for table, states in [('core_job', ('queued','running')), ('core_codingrun', ('queued','running')),
                ('core_aistagereceipt', ('reserved','sending','received')),
                ('core_templatepreparation', ('queued','inventory','proposer','checker')),
                ('core_templatedefinitionpreparation', ('queued','inventory','proposer','checker'))]:
            pending[table] = connection.execute(sql.SQL('SELECT count(*) FROM {} WHERE state=ANY(%s)').format(sql.Identifier(table)), (list(states),)).fetchone()[0]
        schema = [list(x) for x in connection.execute("""SELECT c.relname,pg_get_userbyid(c.relowner),c.relacl::text,
            a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
            WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""")]
        triggers = [list(x) for x in connection.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""")]
        constraints = [list(x) for x in connection.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid)
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' ORDER BY c.relname,k.conname""")]
        indexes = [list(x) for x in connection.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname")]
        functions = [list(x) for x in connection.execute("""SELECT p.proname,pg_get_function_identity_arguments(p.oid),
            md5(pg_get_functiondef(p.oid)),pg_get_userbyid(p.proowner),p.proacl::text
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind='f'
            ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)""")]
        sequences = {}
        for (name,) in connection.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"):
            sequences[name] = list(connection.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(name))).fetchone())
        return dict(tables=rows, migrations=migration_rows, schema=schema, triggers=triggers,
                    constraints=constraints, indexes=indexes, functions=functions, sequences=sequences, pending=pending,
                    latest_enrolled_encounter=str(connection.execute("SELECT max(created_at) FROM core_encounter WHERE created_by_id='5f4d1a3d-eeb6-4207-b1df-4597dc696e82'").fetchone()[0]))


def verify_migration(before, after):
    require(set(after['tables']) == set(before['tables']) | {NEW_TABLE} and NEW_TABLE not in before['tables'], 'one_new_table')
    require(after['tables'][NEW_TABLE][0] == 0, 'empty_new_decisions')
    require(all(after['tables'][name] == row for name, row in before['tables'].items() if name != 'django_migrations'),
            'all_existing_database_rows_preserved')
    require(sorted(after['migrations']) == sorted(before['migrations'] + [['core', MIGRATION]]), 'exact_migration_row')
    require([x for x in after['schema'] if x[0] != NEW_TABLE] == before['schema'], 'old_schema_unchanged')
    new = [x for x in after['schema'] if x[0] == NEW_TABLE]
    require(new and all(x[1] == 'quillmd_owner' and 'quillmd_runtime=arwd/' in (x[2] or '') for x in new), 'new_owner_runtime_privileges')
    require([x for x in after['triggers'] if x[0] != NEW_TABLE] == before['triggers'], 'old_guards_unchanged')
    added = [x for x in after['triggers'] if x[0] == NEW_TABLE]
    require(len(added) == 1 and added[0][1] == 'coding_output_decision_append_only'
            and 'BEFORE DELETE OR UPDATE' in added[0][2]
            and 'quillmd_append_only()' in added[0][2] and added[0][3] == 'O', 'new_append_only_guard')
    for name in ('constraints', 'indexes'):
        require([x for x in after[name] if x[0] != NEW_TABLE] == before[name], 'old_' + name + '_unchanged')
    require(after['functions'] == before['functions'], 'old_guard_functions_unchanged')
    require(set(after['sequences']) == set(before['sequences']), 'same_sequence_population')
    for name, value in before['sequences'].items():
        expected = [value[0] + (1 if value[1] else 0), True] if name == 'django_migrations_id_seq' else value
        require(after['sequences'][name] == expected, 'only_exact_migration_sequence_advance')
    require(not any(after['pending'].values()), 'no_provider_work_during_install')


def migration_source():
    return '''import os,django
os.environ['DJANGO_SETTINGS_MODULE']='quillmd.settings'
django.setup()
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
with connection.cursor() as c:
 c.execute('SELECT current_database(),current_user')
 assert c.fetchone()==('quillmd_fresh','quillmd_owner')
e=MigrationExecutor(connection);target=[('core','0029_bounded_output_decision')]
assert [(m.app_label,m.name,b)for m,b in e.migration_plan(target)]==[('core','0029_bounded_output_decision',False)]
with transaction.atomic():e.migrate(target)
print('rowan_additive_migration_committed')
'''


def migrate(original):
    opts = database_options(original, owner=True)
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'HOME', 'USER'}}
    env.update({k: v for k, v in dotenv_values(stream=io.StringIO(original.decode()), interpolate=False).items() if isinstance(v, str)})
    env.update(QUILLMD_ENV_MANAGED='1', QUILLMD_DB_USER=opts['user'], QUILLMD_DB_PASSWORD=opts['password'],
               PGOPTIONS=opts['options'], PYTHONDONTWRITEBYTECODE='1')
    result = command([str(APP / '.venv/bin/python'), '-B', '-c', migration_source()], cwd=APP, env=env, timeout=90)
    require(result.strip() == b'rowan_additive_migration_committed', 'migration_receipt')


def credential_source_checks():
    # Reuse the installed pure-Python dotenv parser inside a read-only host mount;
    # exported assignments are data, never sourced or interpolated. No credential
    # value or credential-derived digest leaves the helper.
    library = '/host' + str(Path(dotenv.__file__).resolve().parents[1])
    return '''import pathlib,os,pwd,stat,sys,io
sys.path.insert(0,''' + repr(library) + ''')
from dotenv import dotenv_values
source=pathlib.Path('/host/etc/quillmd-corti-test/credentials.env')
assert all(not p.is_symlink() for p in (source,*source.parents))
info=source.stat();parent=source.parent.stat()
assert stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600
assert parent.st_uid==0 and stat.S_IMODE(parent.st_mode)==0o700
original=source.read_bytes();assert 0<len(original)<32000
values=dotenv_values(stream=io.StringIO(original.decode()),interpolate=False)
assert all(isinstance(values.get(k),str) and values[k].strip() for k in ('CORTI_CLIENT_ID','CORTI_CLIENT_SECRET'))
assert values.get('CORTI_ENVIRONMENT')=='us' and values.get('CORTI_TENANT_NAME')=='base'
root=pathlib.Path('/host/var/lib/quillmd/provider-secrets')
assert not root.exists() and not root.is_symlink()
assert all(not p.is_symlink() for p in root.parents)
'''


def preflight_credential(directory):
    code = credential_source_checks() + "print('protected_credential_preflight_complete')\n"
    argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network=none', '--read-only',
        '--mount', 'type=bind,src=/,dst=/host,readonly', managed_helper.IMAGE, 'python', '-B', '-']
    result = managed_helper.run_helper(argv, input=code.encode(), timeout=30, failure_directory=directory)
    require(result.stdout.strip() == b'protected_credential_preflight_complete', 'credential_preflight_result')
    return {'protected_source_valid': True, 'dotenv_keys_valid': True, 'environment': 'us', 'tenant': 'base',
            'target_absent': True, 'provider_calls': 0, 'secret_values_recorded': False}


def copy_credential(directory):
    # Secret bytes stay in the no-log root helper. This copy is a service secret,
    # never a report artifact. Root original content and permissions are retained.
    code = credential_source_checks() + '''account=pwd.getpwnam('quillmd-app')
root.mkdir(mode=0o700);os.chown(root,account.pw_uid,account.pw_gid)
folder=root/'corti';folder.mkdir(mode=0o700);os.chown(folder,account.pw_uid,account.pw_gid)
fd=os.open(folder/'credentials.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb')as out:out.write(original);out.flush();os.fsync(out.fileno())
os.chown(folder/'credentials.env',account.pw_uid,account.pw_gid)
assert (folder/'credentials.env').read_bytes()==source.read_bytes()==original
os.setgroups([]);os.setgid(account.pw_gid);os.setuid(account.pw_uid)
assert (folder/'credentials.env').read_bytes()==original
print('protected_service_copy_complete')
'''
    # Resolve host account before chroot; container /etc/passwd does not own it.
    code = code.replace("account=pwd.getpwnam('quillmd-app')", "account=type('A',(),{'pw_uid':" + str(pwd.getpwnam('quillmd-app').pw_uid) + ",'pw_gid':" + str(pwd.getpwnam('quillmd-app').pw_gid) + "})()")
    argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network=none',
        '--mount', 'type=bind,src=/,dst=/host,readonly',
        '--mount', 'type=bind,src=/var/lib/quillmd,dst=/host/var/lib/quillmd',
        managed_helper.IMAGE, 'python', '-B', '-']
    result = managed_helper.run_helper(argv, input=code.encode(), timeout=30, failure_directory=directory)
    require(result.stdout.strip() == b'protected_service_copy_complete', 'credential_copy_result')


def foreign_services():
    raw = command(['systemctl', 'list-units', '--type=service', '--state=running', '--no-legend', '--plain']).decode()
    result = {}
    for line in raw.splitlines():
        unit = line.split()[0]
        if unit in UNITS:
            continue
        data = command(['systemctl', 'show', unit, '-p', 'Type', '-p', 'MainPID', '-p', 'InvocationID', '-p', 'FragmentPath']).decode()
        if 'Type=oneshot\n' not in data:
            result[unit] = data
    return result


def await_health(revision):
    import httpx
    deadline = time.monotonic() + 45
    while True:
        try:
            value = httpx.get('https://app.quillmd.com/health/', timeout=3).json()
            if value == {'status': 'ok', 'data_mode': 'synthetic-only', 'surface': 'doctor', 'release': revision}:
                return value
        except (OSError, ValueError, httpx.HTTPError):
            pass
        require(time.monotonic() < deadline, 'normal_https_readiness_deadline')
        time.sleep(.25)


def execute(plan, plan_sha):
    validate_plan(plan)
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    declared_commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.is_file() and re.fullmatch('[a-f0-9]{40}', declared_commit), 'ruled_declaration_required')
    text = declaration.read_bytes()
    require(plan_sha.encode() in text and plan['candidate'].encode() in text and FORMAT.encode() in text, 'declaration_exact_plan')
    relative = declaration.relative_to(Path(command(['git', '-C', str(declaration.parent), 'rev-parse', '--show-toplevel']).decode().strip()))
    require(command(['git', '-C', str(declaration.parent), 'show', declared_commit + ':' + relative.as_posix()]) == text, 'committed_declaration_bytes')
    original = backup_restore.read_private(APP / '.env', 65536)
    require(sha(original) == plan['environment_before_sha256'], 'environment_before_pin')
    active = render_environment(original, plan['environment'], plan['candidate'])
    guard = source_guard(); prepared = source_plan(plan, guard)
    command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory']); out.mkdir(mode=0o700)
    write_new(out / 'plan.json', plan)
    cipher = backup_restore.key_at(legacy.KEY)
    write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    primitives = legacy.static_primitives(); primitives.static_delta = static_delta
    stage, static_before, staged = stage_static(plan, out, primitives)
    host = legacy.Host(managed_helper)
    activation_exclusion.bind_runtime(APP / '.runtime')
    stopped = resumed = False
    stage_name = 'prepared'
    with legacy.operation_locks(), activation_exclusion.hold('rowan-corti:' + plan['candidate'][:12], timeout=30):
        try:
            stage_name = 'credential_preflight'
            write_new(out / 'credential-preflight.json', preflight_credential(out))
            baseline = dict(configuration=host.configuration(), services=foreign_services(),
                database=database_snapshot(original), files=private_storage.inventory(Path('/var/lib/quillmd/files')))
            require(not any(baseline['database']['pending'].values()), 'pending_work_before_stop')
            require(NEW_TABLE not in baseline['database']['tables'], 'migration_not_already_attempted')
            latest = baseline['database']['latest_enrolled_encounter']
            require(latest == 'None' or datetime.fromisoformat(plan['environment']['QUILLMD_CORTI_NEW_ENCOUNTERS_SINCE'])
                    > datetime.fromisoformat(latest), 'cutoff_preserves_every_existing_enrolled_encounter')
            write_new(out / 'baseline.json', baseline)
            stage_name = 'stop_owned_services'
            stopped = True  # A failed second stop still requires recovery of the first.
            for unit in UNITS:
                host.service('stop', unit)
            require(all(host.state(u)['ActiveState'] == 'inactive' and host.state(u)['MainPID'] == '0' for u in UNITS), 'owned_units_drained')
            before = database_snapshot(original)
            require(before == baseline['database'], 'no_pre_stop_database_race')
            stage_name = 'source_publication'; publish_source(plan, guard, prepared)
            stage_name = 'additive_migration'; migrate(original)
            after = database_snapshot(original); verify_migration(before, after)
            write_new(out / 'migration-preservation.json', after)
            stage_name = 'static_publication'
            static_after = primitives.install_static(APP / 'staticfiles', stage, static_before, staged)
            stage_name = 'credential_publication'; copy_credential(out)
            stage_name = 'environment_publication'
            require((APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = APP / '.rowan-env-pending'
            write_new(temporary, active); temporary.replace(APP / '.env')
            require(database_snapshot(active) == after, 'database_preserved_until_resume')
            require(private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'], 'all_clinical_files_preserved')
            require(host.configuration() == baseline['configuration'] and foreign_services() == baseline['services'], 'unrelated_configuration_services_preserved')
            write_new(out / 'pre-resume-preservation.json', {'old_rows_preserved': True, 'files_preserved': True,
                'old_guards_preserved': True, 'static_inventory': static_after, 'new_decisions': 0, 'provider_calls': 0})
            stage_name = 'resume_owned_services'; resumed = True
            for unit in (UNITS[2], *UNITS[:2]):
                host.service('start', unit)
            health = await_health(plan['candidate'])
            require(all(host.state(u)['ActiveState'] == 'active' for u in UNITS), 'owned_units_active')
            require(host.configuration() == baseline['configuration'] and foreign_services() == baseline['services'], 'foreign_services_after_resume')
            receipt = dict(format=FORMAT, installed_revision=plan['candidate'], health=health,
                complete=True, new_table=NEW_TABLE, migration=MIGRATION, provider_calls=0,
                clinician_decisions_created=0, global_coding_provider='existing', source_delta=len(plan['source_sha256']),
                strict_preservation_ends_before_resume=True)
            write_new(out / 'installation-complete.json', receipt)
            return receipt
        except BaseException as error:
            # Never retry a sent migration/provider operation or restart a worker
            # after resume. Retain first failure for explicit bounded recovery.
            failure = dict(format=FORMAT, complete=False, stage=stage_name, failure_type=type(error).__name__,
                reason=str(error) if isinstance(error, Refusal) else 'protected_operational_failure',
                stopped=stopped, resumed=resumed, provider_calls=0, automatic_retry=False)
            write_new(out / 'failure.json', failure)
            if stopped and not resumed and git('rev-parse', 'HEAD').decode().strip() == BASE:
                for unit in (UNITS[2], *UNITS[:2]):
                    host.service('start', unit)
                write_new(out / 'original-release-resumed.json', {'release': BASE})
            raise Refusal('installation_failed_inspect_retained_evidence') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--plan'); parser.add_argument('--plan-sha256')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'inert': True, 'database_queries': 0, 'provider_calls': 0, 'service_actions': 0})); return
    os.umask(0o077); sys.dont_write_bytecode = True
    plan, digest = private_json(Path(args.plan))
    require(digest == args.plan_sha256, 'private_plan_hash')
    print(json.dumps(execute(plan, digest), sort_keys=True))


if __name__ == '__main__':
    main()
