#!/usr/bin/env python3
"""Encrypted fresh-database backup and isolated, networkless restore verification."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import tempfile
import time

from cryptography.fernet import Fernet, InvalidToken
from dotenv import dotenv_values
import psycopg
from psycopg import sql

SOURCE_CONTAINER = 'quillmd-fresh-postgres'
SOURCE_DATABASE = 'quillmd_fresh'
MAX_OBJECT_BYTES = 256 * 1024 * 1024
LABEL = 'quillmd.restore-run'
FILE_QUERIES = [
    ('original', 'SELECT original_path,sha256 FROM core_template'),
    ('export', "SELECT export_path,export_sha256 FROM core_encounter WHERE export_path<>''"),
    ('audio', "SELECT input_path,'' FROM core_job WHERE input_path<>''"),
    ('receipt', "SELECT result_path,result_sha256 FROM core_job WHERE result_path<>''"),
    ('receipt', "SELECT result_path,result_sha256 FROM core_providerreceipt WHERE result_path<>''"),
]
INVARIANTS = {
    'wallet_bounds': 'SELECT count(*) FROM core_wallet WHERE balance<0 OR reserved<0 OR reserved>balance',
    'usage_multiplier': 'SELECT count(*) FROM core_usage WHERE charged_cost<>actual_cost*1.5',
    'encounter_scope': '''SELECT count(*) FROM core_encounter e JOIN core_patient p ON p.id=e.patient_id
        JOIN core_templateversion v ON v.id=e.template_version_id JOIN core_template t ON t.id=v.template_id
        WHERE e.department_id<>p.department_id OR e.department_id<>t.department_id''',
    'held_reservations': '''SELECT count(*) FROM core_wallet w WHERE w.reserved<>
        COALESCE((SELECT sum(r.amount) FROM core_reservation r WHERE r.wallet_id=w.id AND r.state='held'),0)''',
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def private_dir(path, create=False):
    path = Path(path).absolute()
    require(path.resolve() == path, 'Private directory cannot contain symlinks.')
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    s = path.stat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid()
            and stat.S_IMODE(s.st_mode) == 0o700, 'Private directory must be owned by this user and mode 0700.')
    return path


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def read_private(path, limit=MAX_OBJECT_BYTES):
    path = Path(path).absolute()
    require(path.resolve() == path, 'Private file cannot be a symlink.')
    s = path.stat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid()
            and stat.S_IMODE(s.st_mode) == 0o600, 'Private file must be owned and mode 0600.')
    require(s.st_size <= limit, 'Object exceeds bounded backup size; use a qualified streaming backup tool.')
    return path.read_bytes()


def key_at(path):
    return Fernet(read_private(path, 128).strip())


def run(args, *, data=None, output=None, env=None):
    p = subprocess.run(args, input=data, stdout=output or subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env)
    require(p.returncode == 0, 'Operational command failed; no raw database/provider output was emitted.')
    return p.stdout


def inspect_container(name):
    return json.loads(run(['docker', 'inspect', name]))[0]


def safe_relative(value):
    p = PurePosixPath(value)
    require(value and not p.is_absolute() and '..' not in p.parts
            and str(p) == value and '\\' not in value and '\x00' not in value,
            'Unsafe backup file path.')
    return p


def file_data(root, relative):
    safe_relative(relative)
    if root == Path('/var/lib/quillmd/files'):
        # The application identity owns 0600 files. The operator's bounded
        # read-only helper has no network, keys, extra groups or capabilities.
        try:
            from .private_storage import read_file
        except ImportError:
            from private_storage import read_file
        return read_file(root, relative)
    p = root / relative
    require(p.resolve() == p and p.is_relative_to(root), 'Symlink or out-of-root file rejected.')
    before = p.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_OBJECT_BYTES, 'Invalid/oversized private file.')
    data = p.read_bytes()
    after = p.stat()
    require((before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns), 'File changed while being copied; retry backup.')
    return data


def table_queries(query):
    rows = query('''SELECT c.relname,a.attname,k.ord FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_index i ON i.indrelid=c.oid AND i.indisprimary
        JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord) ON true
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname,k.ord''')
    tables = {}
    for table, column, _ in rows:
        tables.setdefault(table, []).append(column)
    count = query("SELECT count(*) FROM pg_tables WHERE schemaname='public'")[0][0]
    require(len(tables) == count, 'Every backed-up public table needs a primary key for deterministic verification.')
    return tables


def fingerprint(query, copy_hash):
    result = {}
    for table, columns in table_queries(query).items():
        select = sql.SQL('SELECT * FROM public.{} ORDER BY {}').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns))).as_string()
        count = query(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)).as_string())[0][0]
        result[table] = {'rows': count, 'sha256': copy_hash(f'COPY ({select}) TO STDOUT')}
    return result


def invariant_counts(query):
    result = {name: query(statement)[0][0] for name, statement in INVARIANTS.items()}
    require(not any(result.values()), 'Database invariants failed; backup/restore qualification stopped.')
    return result


def source_options(source, credentials=None):
    values = dotenv_values(source / '.env')
    opts = {'dbname': values.get('QUILLMD_DB_NAME', SOURCE_DATABASE),
            'user': values.get('QUILLMD_DB_USER', SOURCE_DATABASE),
            'password': values['QUILLMD_DB_PASSWORD'],
            'host': values.get('QUILLMD_DB_HOST', '127.0.0.1'),
            'port': values.get('QUILLMD_DB_PORT', '55438')}
    require(opts['dbname'] == SOURCE_DATABASE and opts['host'] == '127.0.0.1'
            and str(opts['port']) == '55438', 'Only the existing fresh loopback database is supported.')
    if credentials:
        data = json.loads(read_private(credentials, 16384))
        require(data['database'] == SOURCE_DATABASE and data['roles']['backup']['name'] == 'quillmd_backup'
                and data['container_id'] == inspect_container(SOURCE_CONTAINER)['Id'], 'Backup role belongs to another target.')
        opts.update(user='quillmd_backup', password=data['roles']['backup']['password'])
    return opts


def backup(args):
    source = Path(args.source).absolute()
    require(source.resolve() == source and (source / 'core/models.py').is_file(), 'Invalid fresh source root.')
    runtime = private_dir(source / '.runtime')
    try:
        from .private_storage import state_root, inventory
    except ImportError:
        from private_storage import state_root, inventory
    media = state_root(source) / 'files'
    if media == Path('/var/lib/quillmd/files'):
        inventory(media)  # Verify pinned ownership and the bounded mount first.
    else:
        require(media.is_dir() and media.resolve() == media, 'Protected source media directory is invalid.')
    parent = private_dir(args.output, create=True)
    key_path = Path(args.key_file).absolute()
    require(not key_path.is_relative_to(parent), 'Keep the encryption key outside the backup destination.')
    cipher = key_at(key_path)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
    destination = parent / run_id
    destination.mkdir(mode=0o700)
    (destination / 'objects').mkdir(mode=0o700)
    opts = source_options(source, getattr(args, 'database_credentials', None))
    metadata = inspect_container(SOURCE_CONTAINER)
    ports = metadata['HostConfig']['PortBindings']
    require(metadata['State']['Running'] and ports == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]},
            'Fresh database container identity/exposure differs.')
    manifest = {'format': 1, 'run_id': run_id, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'database': SOURCE_DATABASE, 'container_id': metadata['Id'], 'image_id': metadata['Image'],
                'source_commit': run(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip(),
                'files': [], 'complete': False}
    try:
        with psycopg.connect(**opts, autocommit=True) as conn:
            conn.execute("SET timezone='UTC'")
            conn.execute("SET datestyle='ISO, MDY'")
            conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            snapshot = conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
            query = lambda text: conn.execute(text).fetchall()
            def copy_hash(text):
                h = hashlib.sha256()
                with conn.cursor().copy(text) as stream:
                    for data in stream:
                        h.update(data)
                return h.hexdigest()
            manifest['tables'] = fingerprint(query, copy_hash)
            manifest['invariants'] = invariant_counts(query)
            references = {}
            for kind, statement in FILE_QUERIES:
                for relative, expected in query(statement):
                    safe_relative(relative)
                    old = references.setdefault(relative, {'kinds': [], 'expected_sha256': expected})
                    require(not (old['expected_sha256'] and expected and old['expected_sha256'] != expected),
                            'Conflicting database file hashes.')
                    old['kinds'].append(kind)
                    if expected:
                        old['expected_sha256'] = expected
            # Copy files referenced by this exact DB snapshot. New uncommitted or
            # unreferenced scratch files are deliberately outside the backup.
            for relative, reference in sorted(references.items()):
                data = file_data(media, relative)
                h = digest(data)
                require(not reference['expected_sha256'] or reference['expected_sha256'] == h,
                        'Referenced file differs from its database integrity hash.')
                object_name = 'objects/' + digest(relative.encode()) + '.fernet'
                payload = cipher.encrypt(data)
                write_private(destination / object_name, payload)
                manifest['files'].append({'path': relative, 'size': len(data), 'sha256': h,
                                          'object': object_name, 'cipher_sha256': digest(payload),
                                          'kinds': reference['kinds']})
            with tempfile.TemporaryFile() as dump:
                os.fchmod(dump.fileno(), 0o600)
                env = dict(os.environ, PGPASSWORD=opts['password'])
                run(['docker', 'exec', '-e', 'PGPASSWORD', SOURCE_CONTAINER, 'pg_dump',
                     '-h', '127.0.0.1', '-U', opts['user'], '-d', SOURCE_DATABASE,
                     '--format=custom', '--no-owner', '--no-privileges', '--snapshot=' + snapshot],
                    output=dump, env=env)
                require(dump.tell() <= MAX_OBJECT_BYTES, 'Database dump exceeds bounded encrypted-object size.')
                dump.seek(0)
                plain = dump.read()
                encrypted = cipher.encrypt(plain)
                write_private(destination / 'database.dump.fernet', encrypted)
                manifest['dump'] = {'sha256': digest(plain), 'size': len(plain), 'cipher_sha256': digest(encrypted)}
            for row in manifest['files']:
                require(digest(file_data(media, row['path'])) == row['sha256'],
                        'Referenced file changed during snapshot; backup is incomplete.')
            conn.execute('COMMIT')
        manifest['complete'] = True
        write_private(destination / 'manifest.json.fernet', cipher.encrypt(json.dumps(manifest, sort_keys=True).encode()))
        summary = {'complete': True, 'run_id': run_id, 'database': SOURCE_DATABASE,
                   'table_count': len(manifest['tables']), 'row_count': sum(t['rows'] for t in manifest['tables'].values()),
                   'file_count': len(manifest['files']), 'file_bytes': sum(f['size'] for f in manifest['files']),
                   'source_commit': manifest['source_commit'], 'encrypted': True,
                   'manifest_cipher_sha256': digest((destination / 'manifest.json.fernet').read_bytes())}
        write_private(destination / 'summary.json', json.dumps(summary, indent=2).encode() + b'\n')
        print(json.dumps({'backup_directory': str(destination), **summary}))
    except Exception:
        write_private(destination / 'INCOMPLETE', b'Backup failed; do not restore this directory.\n')
        raise


def psql(container, statement, binary=False):
    out = run(['docker', 'exec', '-i', container, 'psql', '-X', '-q', '-A', '-t',
               '-v', 'ON_ERROR_STOP=1', '-U', 'restore_owner', '-d', 'quillmd_restore'],
              data=("SET timezone='UTC'; SET datestyle='ISO, MDY';\n" + statement + ';\n').encode())
    return out if binary else json.loads(out)


def restore_query(container, statement):
    return psql(container, 'SELECT COALESCE(json_agg(row_to_json(r)),\'[]\'::json) FROM (' + statement + ') r')


def load_backup(path, cipher):
    root = private_dir(path)
    require(not (root / 'INCOMPLETE').exists(), 'Incomplete backup rejected.')
    manifest = json.loads(cipher.decrypt(read_private(root / 'manifest.json.fernet')))
    require(manifest.get('format') == 1 and manifest.get('complete') is True
            and manifest.get('database') == SOURCE_DATABASE, 'Not a complete fresh backup.')
    paths = [f['path'] for f in manifest['files']]
    require(len(paths) == len(set(paths)), 'Duplicate restored file paths.')
    for row in manifest['files']:
        safe_relative(row['path'])
        require(re.fullmatch(r'objects/[a-f0-9]{64}\.fernet', row['object']), 'Invalid encrypted-object path.')
    require(re.fullmatch(r'sha256:[a-f0-9]{64}', manifest['image_id']), 'Invalid pinned PostgreSQL image.')
    return root, manifest


def decrypt_checked(path, expected, cipher):
    payload = read_private(path, MAX_OBJECT_BYTES * 2)
    require(digest(payload) == expected['cipher_sha256'], 'Ciphertext integrity check failed.')
    plain = cipher.decrypt(payload)
    require(len(plain) == expected['size'] and digest(plain) == expected['sha256'], 'Restored object hash/size differs.')
    return plain


def remove_owned_restore(name, run_id):
    row = inspect_container(name)
    require(row['Config']['Labels'].get(LABEL) == run_id and row['HostConfig']['NetworkMode'] == 'none'
            and not row['HostConfig']['PortBindings'], 'Restore cleanup ownership check failed.')
    run(['docker', 'rm', '--force', name])


def restore(args):
    cipher = key_at(args.key_file)
    backup_path, manifest = load_backup(args.backup, cipher)
    output = private_dir(args.output, create=True)
    run_id = secrets.token_hex(8)
    restored = output / ('restore-' + run_id)
    restored.mkdir(mode=0o700)
    (restored / 'files').mkdir(mode=0o700)
    name = 'quillmd-restore-' + run_id
    result = {'run_id': run_id, 'container': name, 'complete': False,
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'provider_actions': 0}
    created = False
    try:
        # Authenticate and verify every object before starting the isolated DB.
        dump = decrypt_checked(backup_path / 'database.dump.fernet', manifest['dump'], cipher)
        for row in manifest['files']:
            data = decrypt_checked(backup_path / row['object'], row, cipher)
            target = restored / 'files' / row['path']
            target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            write_private(target, data)
        run(['docker', 'run', '--detach', '--name', name, '--label', LABEL + '=' + run_id,
             '--network', 'none', '--read-only', '--memory', '768m', '--cpus', '1',
             '--tmpfs', '/var/lib/postgresql/data:rw,size=512m,mode=0700',
             '--tmpfs', '/var/run/postgresql:rw,mode=0777', '--tmpfs', '/tmp:rw,mode=1777',
             '--env', 'POSTGRES_USER=restore_owner', '--env', 'POSTGRES_DB=quillmd_restore',
             '--env', 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=trust',
             '--env', 'POSTGRES_PASSWORD', manifest['image_id']],
            env=dict(os.environ, POSTGRES_PASSWORD=secrets.token_urlsafe(48)))
        created = True
        for _ in range(60):
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'restore_owner',
                                    '-d', 'quillmd_restore'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Isolated restore database did not become ready.')
        run(['docker', 'exec', '-i', name, 'pg_restore', '--exit-on-error', '--single-transaction',
             '--no-owner', '--no-privileges', '-U', 'restore_owner', '-d', 'quillmd_restore'], data=dump)
        def query(statement):
            return [tuple(row.values()) for row in restore_query(name, statement)]
        tables = fingerprint(query, lambda statement: digest(psql(name, statement, binary=True)))
        require(tables == manifest['tables'], 'Restored table count/hash comparison failed.')
        invariants = invariant_counts(query)
        require(invariants == manifest['invariants'], 'Restored invariants differ.')
        triggers = query("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O'")[0][0]
        require(triggers >= 6, 'Fresh immutable-record/scope triggers are missing.')
        for row in manifest['files']:
            require(digest(file_data(restored / 'files', row['path'])) == row['sha256'], 'Restored file differs.')
        metadata = inspect_container(name)
        require(metadata['HostConfig']['NetworkMode'] == 'none' and not metadata['HostConfig']['PortBindings']
                and all(m['Type'] == 'tmpfs' for m in metadata['Mounts']), 'Restore isolation was not maintained.')
        result.update(complete=True, table_count=len(tables), row_count=sum(t['rows'] for t in tables.values()),
                      file_count=len(manifest['files']), all_table_hashes_match=True, all_file_hashes_match=True,
                      invariants=invariants, enabled_custom_triggers=triggers, network='none', published_ports=0,
                      workers_started=0, provider_credentials_copied=False, backup_run_id=manifest['run_id'])
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['container_retained'] = created and args.keep_container
        if created and not args.keep_container:
            remove_owned_restore(name, run_id)
        write_private(restored / 'verification.json', json.dumps(result, indent=2).encode() + b'\n')
    print(json.dumps({'restore_directory': str(restored), **result}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    keygen = sub.add_parser('keygen')
    keygen.add_argument('--key-file', required=True)
    b = sub.add_parser('backup')
    b.add_argument('--source', default='/opt/meddoc-pro/rebuild')
    b.add_argument('--output', required=True)
    b.add_argument('--key-file', required=True)
    b.add_argument('--database-credentials', help='Private role file; selects its read-only backup login.')
    r = sub.add_parser('restore-check')
    r.add_argument('--backup', required=True)
    r.add_argument('--key-file', required=True)
    r.add_argument('--output', required=True)
    r.add_argument('--keep-container', action='store_true')
    args = parser.parse_args()
    if args.action == 'keygen':
        private_dir(Path(args.key_file).absolute().parent, create=True)
        write_private(args.key_file, Fernet.generate_key() + b'\n')
        print('Created private backup key; no key material emitted.')
    elif args.action == 'backup':
        backup(args)
    else:
        restore(args)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, InvalidToken, psycopg.Error):
        raise SystemExit('Backup/restore refused or failed. Inspect protected status evidence; no sensitive output emitted.')
