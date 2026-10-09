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
    # The charge rule audit_billing checks: 1.5 x cost, capped at the approved limit the settled holds record, and anything above
    # the cap present, exactly, as one absorbed_over_limit platform cost. Rows without a hold keep the plain 1.5 x cost.
    'usage_multiplier': '''SELECT count(*) FROM core_usage u WHERE u.charged_cost < 0 OR u.charged_cost <> LEAST(u.actual_cost*1.5,
        COALESCE((SELECT sum(r.amount) FROM core_reservation r WHERE r.job_id=u.job_id AND r.state='settled' HAVING sum(r.amount)>0), u.actual_cost*1.5))
        OR COALESCE((SELECT sum(p.amount) FROM core_platformcost p WHERE p.job_id=u.job_id AND p.kind='absorbed_over_limit'),0) <> u.actual_cost*1.5-u.charged_cost''',
    'encounter_scope': '''SELECT count(*) FROM core_encounter e JOIN core_patient p ON p.id=e.patient_id
        JOIN core_templateversion v ON v.id=e.template_version_id JOIN core_template t ON t.id=v.template_id
        WHERE e.department_id<>p.department_id OR e.department_id<>t.department_id''',
    'held_reservations': '''SELECT count(*) FROM core_wallet w WHERE w.reserved<>
        COALESCE((SELECT sum(r.amount) FROM core_reservation r WHERE r.wallet_id=w.id AND r.state='held'),0)''',
}

# Backup qualification is historical: use the immutable grant captured on the
# request, not today's activation settings or account membership. Keep the old
# multiplier query intact for pre-0024 restores and every non-sponsored row.
_STANDING_USAGE_VALID = r"""
    jsonb_typeof(j.config)='object'
    AND j.config ?& ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose','testing_quote_usd']
    AND NOT (j.config ?| ARRAY['campaign','campaign_scope_sha256','campaign_actor_scope_sha256','campaign_quote_usd'])
    AND j.config->>'testing_authority_mode'='standing_authority'
    AND j.config->>'testing_authority_id'='quillmd-standing-testing-20261009-v1'
    AND j.config->>'testing_authority_sha256'='eb04bade3d212ebdc06dfc44095f0ba56fecfacd0d3d1dbcec97279865d0a7a5'
    AND ((j.kind='generation' AND j.config->>'testing_purpose'='typed-or-reviewed-voice-generation')
      OR (j.kind='transcription' AND j.config->>'testing_purpose'='reviewed-synthetic-voice-transcription'))
    AND j.config->>'mode' IN ('live','fixture')
    AND j.config->>'provider' IN ('anthropic','openai')
    AND jsonb_typeof(j.config->'model')='string' AND length(j.config->>'model') BETWEEN 1 AND 100
    AND CASE WHEN jsonb_typeof(j.config->'testing_quote_usd')='string'
      AND j.config->>'testing_quote_usd' ~ '^[0-9]+([.][0-9]{1,12})?$'
      AND length(split_part(j.config->>'testing_quote_usd','.',1))<=12
      THEN r.quoted_provider_cost=(j.config->>'testing_quote_usd')::numeric
      ELSE false END
    AND r.authority_id='quillmd-standing-testing-20261009-v1' AND r.state='settled'
    AND r.quoted_provider_cost>=0
    AND ((j.user_id='71dc60e3-ca1e-40c7-ad49-4a2612ed8d1a' AND e.department_id='d41ad441-987c-4e68-bb0e-b885ec4b642a')
      OR (j.user_id='2247e403-a830-4807-9a34-6903b95a0f50' AND e.department_id='46a5abdd-36f1-41f0-968f-8c09c39d9daa'))
    AND u.user_id=j.user_id AND e.created_by_id=j.user_id
    AND u.department_id=e.department_id AND u.organization_id=d.organization_id
    AND j.payer='standing:quillmd-standing-testing-20261009-v1' AND u.payer=j.payer
    AND u.actual_cost>=0 AND u.actual_cost<'Infinity'::numeric AND u.charged_cost=0
    AND p.provider=u.provider AND p.provider_request_id=u.provider_request_id AND p.provider_resource_id=u.provider_resource_id
    AND p.units=u.units AND p.rates=u.rates AND p.actual_cost=u.actual_cost AND p.simulated=u.simulated
    AND u.provider ~ '[^[:space:]]'
    AND jsonb_typeof(u.units)='object' AND jsonb_typeof(u.rates)='object'
    AND (u.simulated OR (
      ((j.kind='generation' AND u.provider ~ '^(anthropic|openai):[^[:space:]]'
        AND u.units ?& ARRAY['input_tokens','output_tokens']
        AND u.rates ?& ARRAY['input_per_million','output_per_million'])
       OR (j.kind='transcription' AND u.provider ~ '^deepgram:[^[:space:]]'
        AND u.units ? 'duration_seconds' AND u.rates ? 'usd_per_minute'))
      AND NOT EXISTS(SELECT 1 FROM jsonb_each(CASE WHEN jsonb_typeof(u.units)='object' THEN u.units ELSE '{}'::jsonb END) meter
        WHERE j.kind='generation' AND meter.key IN ('input_tokens','output_tokens','cached_input_tokens','cache_creation_tokens')
          AND (jsonb_typeof(meter.value) IN ('number','string')
            AND length(meter.value#>>'{}') BETWEEN 1 AND 20
            AND meter.value#>>'{}' ~ '^[+]?[0-9]+$') IS NOT TRUE)
      AND NOT EXISTS(SELECT 1 FROM (
          SELECT meter.value FROM jsonb_each(CASE WHEN jsonb_typeof(u.rates)='object' THEN u.rates ELSE '{}'::jsonb END) meter
            WHERE (j.kind='generation' AND meter.key IN ('input_per_million','output_per_million','cached_per_million'))
               OR (j.kind='transcription' AND meter.key='usd_per_minute')
          UNION ALL
          SELECT u.units->'duration_seconds' WHERE j.kind='transcription'
        ) meter WHERE (CASE WHEN jsonb_typeof(meter.value) IN ('number','string')
          AND length(meter.value#>>'{}') BETWEEN 1 AND 100
          AND meter.value#>>'{}' ~ '^[+-]?[0-9]+([.][0-9]+)?([eE][+-]?[0-9]{1,3})?$'
          THEN (meter.value#>>'{}')::numeric>=0 ELSE false END) IS NOT TRUE)
    ))
    AND u.simulated=(j.config->>'mode'='fixture')
    AND (NOT u.simulated OR (u.actual_cost=0 AND r.quoted_provider_cost=0))
    AND NOT EXISTS(SELECT 1 FROM core_reservation w WHERE w.job_id=u.job_id)
    AND NOT EXISTS(SELECT 1 FROM core_ledgerentry l WHERE l.job_id=u.job_id)
    AND (c.id IS NULL OR (c.reconciled_cost>=0 AND c.reconciled_cost<'Infinity'::numeric
      AND c.provider_credit_applied>=0 AND c.provider_credit_applied<'Infinity'::numeric
      AND c.discount_applied>=0 AND c.discount_applied<'Infinity'::numeric
      AND c.evidence_kind IN ('unclassified','provider_report','invoice') AND c.evidence_reference ~ '[^[:space:]]'
      AND c.charge_delta=0 AND c.over_limit_delta=0
      AND (c.ledger_status='applied' OR (c.ledger_status='absorbed'
        AND EXISTS(SELECT 1 FROM core_platformcost a WHERE a.job_id=u.job_id AND a.kind='absorbed_failure')))))
    AND (NOT EXISTS(SELECT 1 FROM core_platformcost a WHERE a.job_id=u.job_id)
      OR (j.state='failed' AND j.error LIKE 'platform_failure:%' AND NOT u.simulated
        AND (SELECT count(*) FROM core_platformcost a WHERE a.job_id=u.job_id)=1
        AND EXISTS(SELECT 1 FROM core_platformcost a
          CROSS JOIN LATERAL (SELECT left('usage:'||u.id::text||
            CASE WHEN c.created_at<a.created_at THEN ' reconciliation:'||c.evidence_reference ELSE '' END,240) AS prefix) evidence
          WHERE a.job_id=u.job_id
          AND a.kind='absorbed_failure' AND a.created_at>=u.created_at
          AND a.amount=CASE WHEN c.created_at<a.created_at THEN c.reconciled_cost ELSE u.actual_cost END
          AND (a.evidence_reference=evidence.prefix
            OR left(a.evidence_reference,length(evidence.prefix)+6)=evidence.prefix||' note:'))))
"""
_STANDING_USAGE_INVARIANT = '''SELECT count(*) FROM core_usage u
    LEFT JOIN core_job j ON j.id=u.job_id
    LEFT JOIN core_encounter e ON e.id=j.encounter_id
    LEFT JOIN core_department d ON d.id=e.department_id
    LEFT JOIN core_testingreservation r ON r.job_id=u.job_id
    LEFT JOIN core_providerreceipt p ON p.job_id=u.job_id
    LEFT JOIN core_costreconciliation c ON c.usage_id=u.id
    WHERE CASE WHEN j.config ?| ARRAY['testing_authority_mode','testing_authority_id','testing_authority_sha256','testing_purpose','testing_quote_usd']
        OR j.payer LIKE 'standing:%' OR u.payer LIKE 'standing:%' OR r.id IS NOT NULL
      THEN (''' + _STANDING_USAGE_VALID + ''') IS NOT TRUE
      ELSE ''' + INVARIANTS['usage_multiplier'].split(' WHERE ', 1)[1] + ''' END'''


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
    statements = dict(INVARIANTS)
    if query("SELECT to_regclass('public.core_testingreservation')")[0][0] is not None:
        statements['usage_multiplier'] = _STANDING_USAGE_INVARIANT
    result = {name: query(statement)[0][0] for name, statement in statements.items()}
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
            # The dump is captured in memory and encrypted there. A temporary file would put an unencrypted copy of every row
            # on the plain root filesystem (/tmp), outside the encrypted volume.
            env = dict(os.environ, PGPASSWORD=opts['password'])
            plain = run(['docker', 'exec', '-e', 'PGPASSWORD', SOURCE_CONTAINER, 'pg_dump',
                         '-h', '127.0.0.1', '-U', opts['user'], '-d', SOURCE_DATABASE,
                         '--format=custom', '--no-owner', '--no-privileges', '--snapshot=' + snapshot], env=env)
            require(len(plain) <= MAX_OBJECT_BYTES, 'Database dump exceeds bounded encrypted-object size.')
            encrypted = cipher.encrypt(plain)
            write_private(destination / 'database.dump.fernet', encrypted)
            manifest['dump'] = {'sha256': digest(plain), 'size': len(plain), 'cipher_sha256': digest(encrypted)}
            del plain
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


READY_MARKER = b'PostgreSQL init process complete; ready for start up.'


def restore_ready(container, runner=subprocess.run):
    """True only once the real server is up.

    The postgres entrypoint runs a TEMPORARY server on the socket while it applies initdb, and `pg_isready` answers for it.
    A restore that starts then meets the shutdown between the temporary server and the real one. That is exactly how the
    2026-09-18T11:09Z restore failed: the container started, pg_isready answered, and pg_restore hit the handover 2 s later.
    So readiness needs the entrypoint's own completion marker, and then a statement the real server answers."""
    logs = runner(['docker', 'logs', container], capture_output=True)
    if READY_MARKER not in (logs.stdout or b'') + (logs.stderr or b''):
        return False
    if runner(['docker', 'exec', container, 'pg_isready', '-U', 'restore_owner', '-d', 'quillmd_restore'],
              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        return False
    probe = runner(['docker', 'exec', container, 'psql', '-X', '-q', '-t', '-A', '-U', 'restore_owner',
                    '-d', 'quillmd_restore', '-c', 'SELECT 1'], capture_output=True)
    return probe.returncode == 0 and (probe.stdout or b'').strip() == b'1'


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
    # The record is opened BEFORE the first step that can fail. Reading the key, loading the backup and creating the
    # output directory all used to run before `result` existed, so a refusal there wrote no verification.json at all and
    # surfaced only as the generic "refused or failed" message — the operator was left with nothing that named the stage.
    run_id = secrets.token_hex(8)
    name = 'quillmd-restore-' + run_id
    result = {'run_id': run_id, 'container': name, 'complete': False,
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'provider_actions': 0,
              'stage': 'opening_the_backup'}
    restored = None
    try:
        cipher = key_at(args.key_file)
        backup_path, manifest = load_backup(args.backup, cipher)
        output = private_dir(args.output, create=True)
        restored = output / ('restore-' + run_id)
        restored.mkdir(mode=0o700)
    except BaseException as failure:
        result['failed_stage'] = result['stage']
        result['error_class'] = type(failure).__name__
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        # There may be no directory to write into yet; say what happened on the way out rather than swallow it.
        print(json.dumps({'restore_directory': None, **result}))
        raise
    created = False
    result['stage'] = 'authenticating_the_backup'
    try:
        # Recovery uses the reviewed local image recorded in the manifest.
        # Inspect never pulls; --pull=never also closes removal races before run.
        image_id = run(['docker', 'image', 'inspect', '--format', '{{.Id}}',
                        manifest['image_id']]).decode().strip()
        require(image_id == manifest['image_id'], 'Reviewed PostgreSQL restore image is unavailable locally.')
        # Authenticate and verify every object before starting the isolated DB.
        dump = decrypt_checked(backup_path / 'database.dump.fernet', manifest['dump'], cipher)
        # decrypt_checked verifies size and SHA-256 of every decrypted document in memory.
        # Nothing decrypted is written to disk: the restore host's root filesystem is not
        # the encrypted volume, and a proof must not leave plaintext copies behind.
        verified_files = 0
        for row in manifest['files']:
            decrypt_checked(backup_path / row['object'], row, cipher)
            verified_files += 1
        require(verified_files == len(manifest['files']), 'Not every backed-up document was verified.')
        # Set before the step it names: it used to be set after, so a container that would not start was recorded as an
        # authentication failure and this label could never appear at all.
        result['stage'] = 'starting_the_isolated_database'
        run(['docker', 'run', '--pull=never', '--detach', '--name', name, '--label', LABEL + '=' + run_id,
             '--network', 'none', '--read-only', '--memory', '768m', '--memory-swap', '768m', '--cpus', '1',
             '--tmpfs', '/var/lib/postgresql/data:rw,size=512m,mode=0700',
             '--tmpfs', '/var/run/postgresql:rw,mode=0777', '--tmpfs', '/tmp:rw,mode=1777',
             '--env', 'POSTGRES_USER=restore_owner', '--env', 'POSTGRES_DB=quillmd_restore',
             '--env', 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=trust',
             '--env', 'POSTGRES_PASSWORD', manifest['image_id']],
            env=dict(os.environ, POSTGRES_PASSWORD=secrets.token_urlsafe(48)))
        created = True
        result['stage'] = 'waiting_for_the_restored_database'
        for _ in range(120):
            if restore_ready(name):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Isolated restore database did not become ready.')
        result['stage'] = 'restoring_the_dump'
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
        metadata = inspect_container(name)
        host_config = metadata['HostConfig']
        # --tmpfs mounts are listed under HostConfig.Tmpfs, not Mounts: check both, so this cannot pass on an empty list.
        on_tmpfs_without_swap = ('/var/lib/postgresql/data' in (host_config.get('Tmpfs') or {}) and not metadata['Mounts']
                                 and host_config.get('ReadonlyRootfs') is True and host_config.get('Memory', 0) > 0
                                 and host_config.get('MemorySwap') == host_config.get('Memory'))
        require(host_config['NetworkMode'] == 'none' and not host_config['PortBindings'] and on_tmpfs_without_swap,
                'Restore isolation was not maintained.')
        result['stage'] = 'complete'
        result.update(complete=True, table_count=len(tables), row_count=sum(t['rows'] for t in tables.values()),
                      file_count=len(manifest['files']), all_table_hashes_match=True, all_file_hashes_match=True,
                      decrypted_files_written=0, restore_database_on_tmpfs_without_swap=on_tmpfs_without_swap,
                      invariants=invariants, enabled_custom_triggers=triggers, network='none', published_ports=0,
                      workers_started=0, provider_credentials_copied=False, backup_run_id=manifest['run_id'])
    except BaseException as failure:
        # The stage and the failure's class, never the failing command's output: a database error can quote row data.
        result['failed_stage'] = result.get('stage')
        result['error_class'] = type(failure).__name__
        raise
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['container_retained'] = created and args.keep_container
        # Cleanup runs first but may not destroy the record: a failure here used to replace the original exception AND
        # discard the whole result, so the reason the restore failed was lost exactly when something else also went wrong.
        if created and not args.keep_container:
            try:
                remove_owned_restore(name, run_id)
            except BaseException as cleanup_failure:
                result['cleanup_failed'] = True
                result['cleanup_error_class'] = type(cleanup_failure).__name__
                result['container_retained'] = True  # it may still be running; say so rather than imply it was removed
                if result['complete']:
                    result.update(data_verification_complete=True, complete=False,
                                  stage='cleaning_the_isolated_database',
                                  failed_stage='cleaning_the_isolated_database')
        write_private(restored / 'verification.json', json.dumps(result, indent=2).encode() + b'\n')
    # A clean comparison with a retained plaintext DB is not a completed drill.
    # This follows the finally block so an earlier failure keeps its original
    # exception and failed_stage while both failures remain in the report.
    require(not result.get('cleanup_failed'), 'Isolated restore cleanup failed; inspect the protected verification record.')
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
