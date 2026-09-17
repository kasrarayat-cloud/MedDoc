#!/usr/bin/env python3
"""One-shot, reviewed private Word beta activation; default is read-only preflight."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
RUNTIME = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
BASELINE = '688837471efb8b11c57a89e76d585e0ba352e937'
DECLARATION = '20260917-quillmd-word-beta.md'
MIGRATION = '0011_template_clinical_review'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
UNITS = ['quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker')]
NEW_COLUMNS = {'core_templateversion': {'review_requirements': [], 'document_backend': {}},
               'core_encounter': {'template_review': {}}}
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']
ENV_KEYS = ('QUILLMD_WORD_RUNTIME', 'QUILLMD_WORD_MANIFEST', 'QUILLMD_WORD_MANIFEST_SHA256')
EXPECTED_MIGRATION = '''from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [('core', '0010_canonical_provider_settlement')]
    operations = [
        migrations.AddField(model_name='templateversion', name='review_requirements', field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name='templateversion', name='document_backend', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='encounter', name='template_review', field=models.JSONField(blank=True, default=dict)),
    ]
'''


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(path, *, private=False, limit=384 * 1024 * 1024):
    info = path.lstat()
    require(path.is_absolute() and path.resolve() == path and stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid() and info.st_nlink == 1 and 0 < info.st_size <= limit
            and not info.st_mode & 0o022, 'Expected a bounded, unlinked operator-owned artifact.')
    if private:
        require(stat.S_IMODE(info.st_mode) == 0o600, 'Expected a private0600 artifact.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(limit + 1)
        after = os.fstat(fd)
        attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        require(all(getattr(info, key) == getattr(before, key) == getattr(after, key) for key in attrs)
                and len(data) == info.st_size, 'Artifact changed while being verified.')
        return data
    finally:
        os.close(fd)


def unique_json(data):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'Duplicate artifact metadata key.')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def relative(name):
    require(isinstance(name, str) and name and '\\' not in name and '\x00' not in name,
            'Invalid artifact path.')
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and '..' not in path.parts
            and len(path.parts) <= 16, 'Artifact path escapes its runtime.')
    return name


def retained_reports():
    """Inventory only the historical untracked reports retained by prior releases."""
    paths = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z']).split(b'\0')
    result, total = {}, 0
    for raw in paths:
        if not raw:
            continue
        name = raw.decode('utf-8')
        allowed = re.fullmatch(r'docs/preflight-reports/preflight-\d{8}T\d{6}Z\.md', name)
        allowed = allowed or name in ('docs/preflight-reports/storage-census-20260907.txt',
                                      'docs/preflight-reports/storage-reap-20260907.txt')
        require(allowed and len(result) < 200, 'Untracked resource is outside the explicitly retained report scope.')
        path = ROOT / name
        before = path.lstat()
        require(path.resolve() == path and stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= 4 * 1024 * 1024, 'Retained report is linked, nonregular or oversized.')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with os.fdopen(os.dup(fd), 'rb') as stream:
                data = stream.read(4 * 1024 * 1024 + 1)
            after = os.fstat(fd)
            require(all(getattr(before, key) == getattr(after, key) for key in
                        ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
                    and len(data) == before.st_size, 'Retained report changed during inspection.')
        finally:
            os.close(fd)
        total += len(data)
        require(total <= 128 * 1024 * 1024, 'Retained report population exceeds its bounded size.')
        result[name] = {'sha256': sha(data), 'size': len(data), 'mode': stat.S_IMODE(before.st_mode)}
    return result


def expected_inputs(target):
    names = output(['git', 'ls-tree', '-r', '--name-only', target, '--', 'rebuild/documents/sdk_word']).splitlines()
    names = [name for name in names if (Path(name).suffix in ('.cs', '.csproj')
             or Path(name).name in ('packages.lock.json', 'global.json', 'build_word.py'))
             and not {'bin', 'obj'} & set(Path(name).parts)]
    require(names and 'rebuild/documents/sdk_word/WordHost/Program.cs' in names
            and 'rebuild/documents/sdk_word/Adapter/SdkSeccompGate.cs' in names,
            'Reviewed build source population is incomplete.')
    return {name: sha(subprocess.check_output(['git', 'show', target + ':' + name])) for name in names}


def verify_artifact(runtime, manifest, proof_path, pin, target_inputs):
    require(runtime.is_absolute() and runtime.resolve() == runtime and runtime.is_dir()
            and runtime.stat().st_uid == os.getuid() and not runtime.stat().st_mode & 0o022,
            'Runtime must be a real operator-owned directory.')
    require(re.fullmatch('[a-f0-9]{64}', pin), 'A complete runtime manifest SHA256 is required.')
    manifest_bytes = checked_file(manifest, limit=1024 * 1024)
    require(sha(manifest_bytes) == pin, 'Runtime manifest differs from its trusted pin.')
    metadata = unique_json(manifest_bytes)
    require(set(metadata) == {'format', 'runtime', 'executable', 'files'} and metadata['format'] == 1
            and metadata['runtime'] == 'dotnet8-self-contained-linux-x64'
            and metadata['executable'] == 'WordHost' and isinstance(metadata['files'], dict)
            and 0 < len(metadata['files']) <= 1000, 'Unexpected self-contained Word manifest.')
    files = metadata['files']
    require({'WordHost', 'libcoreclr.so', 'System.Private.CoreLib.dll', 'WordHost.runtimeconfig.json'} <= files.keys(),
            'Self-contained runtime is incomplete.')
    actual, total = {}, 0
    for path in sorted(runtime.rglob('*')):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode) and info.st_uid == os.getuid()
                and not info.st_mode & 0o022, 'Runtime ownership or link policy failed.')
        if stat.S_ISDIR(info.st_mode):
            continue
        name = relative(str(path.relative_to(runtime)))
        data = checked_file(path)
        total += len(data)
        require(total <= 384 * 1024 * 1024 and len(actual) < 1000, 'Runtime exceeds its bounded size.')
        actual[name] = sha(data)
    require(all(relative(name) and isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest)
                for name, digest in files.items()) and actual == files, 'Runtime files differ from the exact manifest population.')
    config = unique_json((runtime / 'WordHost.runtimeconfig.json').read_bytes())
    frameworks = config.get('runtimeOptions', {}).get('includedFrameworks', [])
    require(frameworks and all(row.get('version') == '8.0.31' for row in frameworks), 'Runtime version differs from the approved pin.')
    proof_bytes = checked_file(proof_path, limit=1024 * 1024)
    proof = unique_json(proof_bytes)
    require(proof.get('format') == 1 and proof.get('sdk_version') == '8.0.425'
            and proof.get('runtime_version') == '8.0.31' and proof.get('runtime_identifier') == 'linux-x64'
            and proof.get('runtime_executable') == 'WordHost' and proof.get('restored_locked') is True
            and proof.get('self_contained') is True
            and proof.get('ambient_scm_metadata') is False
            and proof.get('source_revision_id') == '' and proof.get('repository_commit') == ''
            and proof.get('runtime_manifest_sha256') == pin
            and proof.get('build_inputs') == target_inputs
            and re.fullmatch('[a-f0-9]{64}', proof.get('sdk_executable_sha256', ''))
            and proof.get('dependencies') == {'Aspose.Words.FOSS': '26.3.0'} and proof.get('license') == 'MIT',
            'Build proof does not identify the exact reviewed source and locked toolchain.')
    return {'files': actual, 'bytes': total, 'manifest_sha256': pin,
            'build_proof_sha256': sha(proof_bytes), 'build_inputs': target_inputs}


def validate_migration(source):
    require(ast.dump(ast.parse(source), include_attributes=False)
            == ast.dump(ast.parse(EXPECTED_MIGRATION), include_attributes=False),
            'This activation permits only the three reviewed JSONField additions.')


def schema():
    sql = """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') FROM
      (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default
       FROM information_schema.columns WHERE table_schema='public') c"""
    return json.loads(output(PSQL + [sql]))


def check_schema(before, after):
    expected = {(table, column) for table, columns in NEW_COLUMNS.items() for column in columns}
    require(not any((row['table_name'], row['column_name']) in expected for row in before),
            'Word schema additions are already present; do not reapply this activation.')
    old = [row for row in after if (row['table_name'], row['column_name']) not in expected]
    additions = [row for row in after if (row['table_name'], row['column_name']) in expected]
    require(old == before and {(row['table_name'], row['column_name']) for row in additions} == expected
            and len(additions) == 3, 'Schema differs beyond the three declared new columns.')
    for row in additions:
        old_count = max(item['ordinal_position'] for item in before if item['table_name'] == row['table_name'])
        offset = list(NEW_COLUMNS[row['table_name']]).index(row['column_name']) + 1
        require(row['data_type'] == row['udt_name'] == 'jsonb' and row['is_nullable'] == 'NO'
                and row['column_default'] is None and row['ordinal_position'] == old_count + offset,
                'Added column type, nullability, default or position differs from the reviewed migration.')


def fingerprints(*, normalized=True):
    tables = output(PSQL + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"]).splitlines()
    require(len(tables) == 33 and all(re.fullmatch('[a-z_][a-z_0-9]*', table) for table in tables),
            'Expected all33 new-system public tables.')
    rows = {}
    for table in tables:
        expression = 'to_jsonb(t)'
        if normalized:
            expression += ''.join("-'" + name + "'" for name in NEW_COLUMNS.get(table, {}))
        where = (" WHERE NOT (app='core' AND name='" + MIGRATION + "')") if normalized and table == 'django_migrations' else ''
        data = subprocess.check_output(PSQL + [f'COPY (SELECT ({expression})::text AS value FROM "{table}" t{where} ORDER BY value) TO STDOUT'])
        rows[table] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return rows


def check_new_defaults():
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '1',
            'Exactly one declared schema-history row is required.')
    for table, columns in NEW_COLUMNS.items():
        for column, value in columns.items():
            literal = json.dumps(value, separators=(',', ':'))
            require(output(PSQL + [f"SELECT count(*) FROM {table} WHERE {column} IS DISTINCT FROM '{literal}'::jsonb"]) == '0',
                    'New JSON column contains unexpected application data.')


def systemd(action, helper_image):
    require(action in ('start', 'stop') and re.fullmatch('sha256:[a-f0-9]{64}', helper_image),
            'Only fixed private service operations with a locally pinned image are permitted.')
    code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\n"
    code += 'subprocess.run(' + repr(['systemctl', action, *UNITS]) + ',check=True)\n'
    result = subprocess.run(['docker', 'run', '--rm', '-i', '--pull=never', '--network=none', '--pid=host',
                             '--mount', 'type=bind,src=/,dst=/host,readonly', helper_image, 'python', '-B', '-'],
                            input=code, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=200)
    require(result.returncode == 0, 'Fixed private service operation failed; helper stderr withheld.')


def install_artifact(target, runtime, manifest, proof, verified):
    root = APP / '.word-sdk'
    if not root.exists():
        root.mkdir(mode=0o755)
        root.chmod(0o755)
    info = root.lstat()
    require(root.resolve() == root and stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o755, 'Permanent SDK root must be operator-owned0755.')
    destination = root / target
    destination.mkdir(mode=0o755)  # Exclusive: prior release artifacts are never overwritten.
    out = destination / 'runtime'
    out.mkdir(mode=0o755)
    for name, digest in verified['files'].items():
        source = runtime / name
        data = checked_file(source)
        require(sha(data) == digest, 'Source runtime changed before installation.')
        target_file = out / name
        target_file.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        fd = os.open(target_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                     0o755 if name == 'WordHost' else 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    for source, name, digest in ((manifest, 'runtime-manifest.json', verified['manifest_sha256']),
                                  (proof, 'build-proof.json', verified['build_proof_sha256'])):
        data = checked_file(source, limit=1024 * 1024)
        require(sha(data) == digest, 'Artifact metadata changed before installation.')
        fd = os.open(destination / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    # Enforce exact public-read modes despite the caller's private umask. These
    # are reviewed executables/metadata, never credentials or uploaded documents.
    for path in [destination, *destination.rglob('*')]:
        os.chmod(path, 0o755 if path.is_dir() or path == out / 'WordHost' else 0o644)
    verify_artifact(out, destination / 'runtime-manifest.json', destination / 'build-proof.json',
                    verified['manifest_sha256'], verified['build_inputs'])
    return out, destination / 'runtime-manifest.json'


def updated_environment(original, target, runtime, manifest, pin):
    lines = original.decode().splitlines()
    require(not any(line.startswith(key + '=') for key in ENV_KEYS for line in lines),
            'Word processor configuration already exists; inspect instead of replacing it.')
    require(sum(line.startswith('QUILLMD_RELEASE_SHA=') for line in lines) == 1
            and 'QUILLMD_RELEASE_SHA=' + BASELINE in lines
            and 'QUILLMD_STATE_DIR=/var/lib/quillmd' in lines
            and not any(line.startswith('QUILLMD_WORD_QUALIFICATION=') for line in lines),
            'Expected private identity release and state configuration without qualification bypass.')
    retained = [line for line in lines if not line.startswith('QUILLMD_RELEASE_SHA=')]
    result = retained + ['QUILLMD_RELEASE_SHA=' + target,
                         ENV_KEYS[0] + '=' + str(runtime), ENV_KEYS[1] + '=' + str(manifest), ENV_KEYS[2] + '=' + pin]
    return ('\n'.join(result) + '\n').encode()


def static_permissions():
    """Keep earlier hashed public assets; verify current public-read policy."""
    root = APP / 'staticfiles'
    require(root.resolve() == root, 'Static output root is not canonical.')
    counts = {'files': 0, 'directories': 0}
    for path in [root, *root.rglob('*')]:
        info = path.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        require((directory or stat.S_ISREG(info.st_mode)) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == (0o755 if directory else 0o644)
                and (directory or info.st_nlink == 1), 'Collected public assets violate read-only application access policy.')
        counts['directories' if directory else 'files'] += 1
        require(sum(counts.values()) <= 10000, 'Static output exceeds its bounded population.')
    counts['manifest_sha256'] = sha((root / 'staticfiles.json').read_bytes())
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target', 'backup-report', 'runtime', 'manifest', 'manifest-sha256', 'build-proof', 'result'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Run from the permanent shared main directory.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'A full reviewed merge SHA is required.')
    require(output(['git', 'branch', '--show-current']) == 'main'
            and output(['git', 'rev-parse', 'HEAD']) == BASELINE, 'Expected shared main at the OS identity release.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    reports_before = retained_reports()
    require(output(['git', 'rev-parse', 'origin/main']) == args.target
            and output(['git', 'remote', 'get-url', 'origin']) == 'https://github.com/kasrarayat-cloud/MedDoc.git',
            'Expected the reviewed current origin/main target.')
    run(['git', 'merge-base', '--is-ancestor', 'HEAD', args.target])
    require(subprocess.check_output(['git', 'show', args.target + ':scripts/activate-word-beta.py']) == Path(__file__).read_bytes(),
            'Activator bytes differ from reviewed target.')
    for path in ('scripts/update-private-beta.py', 'scripts/activate-os-identity.py', 'rebuild/ops/private_storage.py'):
        require(subprocess.check_output(['git', 'show', args.target + ':' + path]) == (ROOT / path).read_bytes(),
                'Previously reviewed activation helper changed in this target.')
    require(output(['git', 'diff', '--name-only', 'HEAD', args.target, '--', 'rebuild/deploy']) == '', 'Unit changes are outside this activation.')
    require(output(['git', 'diff', '--name-only', 'HEAD', args.target, '--', 'rebuild/core/migrations']) == MIGRATION_PATH,
            'Unexpected schema change in target.')
    validate_migration(subprocess.check_output(['git', 'show', args.target + ':' + MIGRATION_PATH]))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(row.get('merged_at') and row.get('merge_commit_sha') == args.target
                and row.get('base', {}).get('ref') == 'main' for row in pulls), 'A merged PR into main is required.')
    result_path = Path(args.result)
    require(result_path.is_absolute() and result_path.parent == RUNTIME and result_path.resolve() == result_path
            and re.fullmatch(r'word-beta-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists(), 'Choose a unique permanent private activation evidence path.')
    lock = RUNTIME / '.word-beta-activation.lock'
    require(not lock.exists() and not lock.is_symlink() and not (APP / '.word-sdk' / args.target).exists(),
            'A prior activation or artifact needs inspection; never repeat automatically.')
    require(RUNTIME.resolve() == RUNTIME and RUNTIME.stat().st_uid == os.getuid()
            and stat.S_IMODE(RUNTIME.stat().st_mode) == 0o700, 'Operator runtime must remain private.')
    previous = module_at('word_previous_updater', ROOT / 'scripts/update-private-beta.py')
    identity = module_at('word_identity_verifier', ROOT / 'scripts/activate-os-identity.py')
    storage = module_at('word_private_storage', APP / 'ops/private_storage.py')
    previous.validate_restore_report(args.backup_report)
    baseline_protected = previous.protected()
    identity.verify_live(BASELINE, storage)
    helper = output(['docker', 'image', 'inspect', 'python:3-slim', '--format', '{{.Id}}'])
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper), 'The fixed local helper image must already exist.')
    for unit in UNITS:
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                'Installed service policy differs from reviewed source.')
    source_runtime, source_manifest, proof = map(Path, (args.runtime, args.manifest, args.build_proof))
    verified = verify_artifact(source_runtime, source_manifest, proof, args.manifest_sha256, expected_inputs(args.target))
    future = APP / '.word-sdk' / args.target
    env_before = checked_file(APP / '.env', private=True)
    env_after = updated_environment(env_before, args.target, future / 'runtime', future / 'runtime-manifest.json', args.manifest_sha256)
    credentials = RUNTIME / 'db-role-secrets/fresh-db-roles.json'
    checked_file(credentials, private=True, limit=16384)
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running')"]) == '0', 'Pending jobs must finish before activation; no provider retry is performed.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='0010_canonical_provider_settlement'"]) == '1'
            and output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '0',
            'Expected fresh schema through core0010 only.')
    for name in ('files', 'mail'):
        storage.inventory(STATE / name)
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Verified cited Word candidate, exact build inputs, preserved private state and encrypted restore proof.', flush=True)
    if not args.execute:
        return
    require(Path(os.environ.get('RULED_MUTATION_DECLARATION', '')).name == DECLARATION
            and re.fullmatch('[a-f0-9]{40}', os.environ.get('RULED_MUTATION_DECL_COMMIT', '')),
            'Use the committed Word activation declaration through the ruled-mutation runner.')
    identity.private_write(lock, {'pid': os.getpid(), 'target': args.target})
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'previous_head': BASELINE,
              'target': args.target, 'complete': False, 'provider_calls': 0, 'helper_image': helper,
              'artifact': verified, 'retained_reports_before': reports_before, 'stage': 'stopping_services'}
    try:
        systemd('stop', helper)
        require(all(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive' for unit in UNITS),
                'Private services did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running')"]) == '0', 'A job remains pending after service stop.')
        result['schema_before'] = schema()
        require(not any(row['column_name'] in NEW_COLUMNS.get(row['table_name'], {}) for row in result['schema_before']), 'Declared columns already exist.')
        result['database_before'] = fingerprints()
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        result['stage'] = 'installing_verified_word_runtime'
        install_artifact(args.target, source_runtime, source_manifest, proof, verified)
        result['stage'] = 'applying_three_json_columns'
        migrate = [str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'), '--credentials', str(credentials),
                   '--source', str(APP), '--role', 'migrator', '--', 'migrate', 'core', MIGRATION]
        plan = output(migrate + ['--plan'], cwd=APP)
        require(re.findall(r'^[a-zA-Z_][a-zA-Z_0-9]*\.[a-zA-Z_0-9]+$', plan, re.MULTILINE)
                == ['core.' + MIGRATION], 'Migration plan contains an undeclared operation.')
        run(migrate + ['--noinput'], cwd=APP)
        result['schema_after'] = schema()
        check_schema(result['schema_before'], result['schema_after'])
        check_new_defaults()
        require(fingerprints() == result['database_before'], 'Existing application rows or columns changed during schema addition.')
        result['database_after_all_columns'] = fingerprints(normalized=False)
        run([str(APP / '.venv/bin/python'), 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_permissions'] = static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        require(checked_file(APP / '.env', private=True) == env_before, 'Private environment changed concurrently.')
        pending = RUNTIME / ('word-beta-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(checked_file(APP / '.env', private=True) == env_before, 'Private environment changed before replacement.')
        pending.replace(APP / '.env')
        require(checked_file(APP / '.env', private=True) == env_after, 'Private environment replacement differs.')
        result['stage'] = 'starting_and_verifying_private_services'
        systemd('start', helper)
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{port}/health/'])) for port in (9130, 9131)]
                if all(row.get('release') == args.target and row.get('data_mode') == 'synthetic-only' for row in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Private health did not identify the reviewed synthetic release.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        require(fingerprints() == result['database_before'], 'Startup changed existing application data.')
        check_new_defaults()
        require(fingerprints(normalized=False) == result['database_after_all_columns'], 'Startup changed new schema defaults or migration history.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Application originals, exports, receipts or mail changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Service policy changed during activation.')
        run(['bash', 'scripts/check-cotenants.sh'])
        require(previous.protected() == baseline_protected, 'Protected service population changed.')
        result['retained_reports_after'] = retained_reports()
        require(result['retained_reports_after'] == reports_before, 'Retained historical reports changed.')
        result.update(complete=True, stage='complete', health=health, all_old_rows_and_columns_identical=True,
                      all_files_and_mail_identical=True, exactly_three_empty_json_columns=True, public_maintenance=True)
    except BaseException as error:
        result['failure_kind'] = type(error).__name__
        try:
            systemd('stop', helper)
            result['failure_services_stopped'] = True
        except BaseException:
            result['failure_services_stopped'] = False
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        identity.private_write(result_path, result)
        if result['complete']:
            lock.unlink()
        print('Private Word activation evidence: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
