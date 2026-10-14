#!/usr/bin/env python3
"""Declared additive outpatient-coding installation; inert without --execute.

This is a new schema/static/reference operation, not a rebinding of the previous
code-only operator. The native transport, locks, backup, source publisher, static
publisher and foreign-service observations are the existing hash-pinned ones.
No provider or clinical mutation is part of this operation. An interrupted
mutation is retained for explicit forward recovery; this command never retries
an existing evidence directory or rolls the database back.
"""
from datetime import datetime, timezone
import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import textwrap
import time
from types import FunctionType, SimpleNamespace

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
R = APP / '.runtime/coding-release-20261014'
EVIDENCE = R / 'native-coding-install-v1'
G = APP / '.runtime/gi-preparation-20261013'
BASE = '3db3fd20ccdf134c8de24bbbc8af1306504f24c7'
FORMAT = 'outpatient-coding-install-v1'
MIGRATION = '0028_outpatient_coding'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
MODULE_PATH = 'rebuild/ops/activate_outpatient_coding.py'
NEW_TABLES = frozenset({'core_codingcontext', 'core_codingrun', 'core_codingdecision', 'core_codingrelease'})
NEW_FUNCTION = 'quillmd_coding_run_guard'
NEW_TRIGGERS = frozenset({'core_codingrun:coding_run_immutable_inputs',
                         'core_codingdecision:coding_decision_append_only',
                         'core_codingrelease:coding_reference_immutable'})
STATIC_INPUTS = frozenset({'coding.js', 'coding.css'})
EMPTY_SHA = hashlib.sha256(b'').hexdigest()
LEGACY = G / 'ops-consent-context-code-only-unbound-v1/reviewed-native-consent-context-v1.py'
LEGACY_SHA = '60c71f3c735627378d773f3cadf1cb3ac8d5c4246986f26eb3e04a1c20925723'
BACKUP_SHA = 'b66b52d35c17985107ef72a80e83c2566735a6d3df26d5ad154c82fdf4cb6d0f'
DATABASE_SOURCE_SHA = '9548d15cc1848a8663605b0ef4373553e37bffcd2ce0430ce6e2fe10af433fe0'
REFERENCE_PINS = {
    str(R / 'terminology-review/fy2027-official-reference-manifest-v1.json'):
        'decec02fa1da78a6c8b70f0417457a25bc0d90ab4fe7ab1ed24c4ce76ee5ec97',
    str(R / 'terminology-review/fy2026-april-official-reference-manifest-v1.json'):
        '4d0c1cadc06d644bd35b0604ae002c49ec9fc934f6e1cea8228e2f2ed688ed36',
    str(R / 'terminology-review/fy2026-october-official-reference-manifest-v1.json'):
        'beaea432d6ace4ed20a4c02922f2dda7ac633abb58f1ee0b221414af33a31a9e',
}
ARTIFACT_KEYS = {'schema', 'static', 'histories', 'ci', 'previous_receipt'}
TABLE_METADATA = ('columns', 'old_columns', 'definitions', 'owner_acl', 'privileges')


class Refusal(RuntimeError):
    pass


def need(value, reason):
    if not value:
        raise Refusal(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def equal(a, b):
    return encode(a) == encode(b)


def digest(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def commit(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{40}', value) is not None


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal('nonfinite_json')))


def read_file(path, expected=None, *, private=True, maximum=64 * 1024**2):
    path = Path(path)
    need(path.is_absolute() and path.resolve(strict=True) == path, 'canonical_file')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and before.st_uid == before.st_gid == 1000 and not os.listxattr(path)
         and stat.S_IMODE(before.st_mode) == (0o600 if private else 0o644)
         and 0 < before.st_size <= maximum, 'protected_file_identity')
    if private:
        parent = path.parent.lstat()
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == parent.st_gid == 1000
             and stat.S_IMODE(parent.st_mode) == 0o700 and not os.listxattr(path.parent),
             'protected_parent_identity')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
                          s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    try:
        opened = os.fstat(fd)
        chunks = []; count = 0
        while True:
            block = os.read(fd, min(1024**2, maximum + 1 - count))
            if not block:
                break
            chunks.append(block); count += len(block)
            need(count <= maximum, 'bounded_file')
        after = os.fstat(fd)
    finally:
        os.close(fd)
    raw = b''.join(chunks)
    need(identity(before) == identity(opened) == identity(after) == identity(path.lstat())
         and len(raw) == before.st_size, 'stable_file')
    need(expected is None or (digest(expected) and sha(raw) == expected), 'file_pin')
    return raw


def reference(ref):
    need(type(ref) is dict and set(ref) == {'path', 'sha256'} and digest(ref['sha256']), 'artifact_reference')
    return parse(read_file(ref['path'], ref['sha256']))


def write_new(path, value):
    raw = value if isinstance(value, bytes) else encode(value) + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def load(path, pin, name):
    raw = read_file(path, pin)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def git(repo, *arguments):
    result = subprocess.run(['git', '-C', str(repo), *arguments], capture_output=True, timeout=45)
    need(result.returncode == 0 and len(result.stdout) <= 16 * 1024**2
         and len(result.stderr) <= 65536, 'read_only_git')
    return result.stdout


def scope_digest(plan):
    return sha(encode({k: v for k, v in plan.items() if k != 'execution'}))


def validate_plan(plan):
    need(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'first_commit',
         'module_sha256', 'source_sha256', 'source_worktree', 'execution', 'artifacts',
         'schedule', 'references'}, 'closed_plan')
    need(plan['format'] == FORMAT and plan['base'] == BASE and commit(plan['candidate'])
         and plan['candidate'] != BASE and commit(plan['first_commit']), 'actual_candidate')
    paths = plan['source_sha256']
    need(type(paths) is dict and paths and all(type(k) is str and digest(v) for k, v in paths.items()),
         'source_manifest')
    need({MIGRATION_PATH, MODULE_PATH, 'rebuild/static/coding.js', 'rebuild/static/coding.css'} <= set(paths)
         and plan['module_sha256'] == paths[MODULE_PATH], 'required_source_paths')
    need(not any(p.startswith('rebuild/core/migrations/') and p != MIGRATION_PATH for p in paths)
         and 'rebuild/ops/backup_restore.py' not in paths, 'finite_migration_and_unchanged_backup')
    need(set(plan['artifacts']) == ARTIFACT_KEYS and plan['references'] == REFERENCE_PINS,
         'closed_artifact_population')
    for ref in plan['artifacts'].values():
        need(type(ref) is dict and set(ref) == {'path', 'sha256'} and digest(ref['sha256']), 'artifact_pin')
    ex = plan['execution']
    need(type(ex) is dict and set(ex) == {'worktree', 'path', 'commit', 'sha256'}
         and commit(ex['commit']) and digest(ex['sha256'])
         and re.fullmatch(r'docs/foundation/mutations/[a-z0-9-]+\.md', ex['path']), 'execution_binding')
    for p in (plan['source_worktree'], ex['worktree']):
        need(type(p) is str and Path(p).parent == ROOT / '.worktrees', 'isolated_source_worktree')
    schedule = plan['schedule']
    need(type(schedule) is dict and set(schedule) == {'helper', 'forecast', 'supporting', 'deadline'}
         and type(schedule['supporting']) is list and len(schedule['supporting']) >= 4, 'actual_schedule_chain')
    for ref in [schedule['helper'], schedule['forecast'], *schedule['supporting']]:
        need(type(ref) is dict and set(ref) == {'path', 'sha256'} and digest(ref['sha256']), 'schedule_reference')
    need(len({r['path'] for r in schedule['supporting']}) == len(schedule['supporting']), 'unique_schedule_evidence')
    return plan


def forecast(plan, value, configuration=None, now=None):
    now = now or datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(plan['schedule']['deadline'])
    observed = datetime.fromisoformat(value['observed_at_utc'])
    need(deadline.tzinfo is not None and observed.tzinfo is not None and observed <= now
         and (deadline - now).total_seconds() >= 1200, 'twenty_minute_entry_window')
    need(value.get('read_only') is True and value.get('all_seven_current_hour17_settled_successfully') is True
         and value.get('next_strict_watched_transition_utc') == plan['schedule']['deadline']
         and value.get('watched_foreign_file_population') == 103
         and all(type(value.get(k)) is int and value[k] == 0
                 for k in ('provider_calls', 'service_actions', 'database_queries')), 'settled_full_forecast')
    identities = value.get('actual_exact_unit_source_metadata')
    need(type(identities) is dict and len(identities) == 167, 'full_current_configuration_population')
    if configuration is not None:
        need(all(configuration.get(p) == row for p, row in identities.items()), 'current_forecast_configuration')
    return deadline


def collect_rehearsal(query, source_sha256, prepared_references):
    """Read-only collector for an already migrated ISOLATED owner-role database.

    The caller supplies its isolated connection's SELECT-only query function.
    No connection, native host, environment, service, or provider is constructed.
    prepared_references are the three actual prepare_reference() return values.
    This measures a contract; it does not qualify or authorize an installation.
    """
    from psycopg import sql
    identity = query('SELECT current_database(),current_user')[0]
    need(identity[0] in {'quillmd_coding_fixture', 'test_quillmd_coding_fixture', 'quillmd_coding_reference_rehearsal'}
         and identity[1] == 'quillmd_owner'
         and query('SHOW transaction_read_only')[0][0] == 'on', 'isolated_owner_readonly_rehearsal')
    text = Path(__file__).with_name('word_milestone_delivery.py').read_text()
    tree = ast.parse(text)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeHost')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'schema')
    source = textwrap.dedent('\n'.join(text.splitlines()[fn.lineno-1:fn.end_lineno])) + '\n'
    need(sha(source.encode()) == 'dd1d9699ee684e78f988898b093559efdc70db4ab852fd59b943fb5a6b33e2c4',
         'pinned_read_only_schema_collector')
    namespace = {'require': need}
    exec(compile(source, '<pinned-read-only-catalog>', 'exec'), namespace)
    adapter = load(APP / '.runtime/standing-testing-authority-20261009/native-review-v1/trigger_catalog_adapter_v1.py',
        'a639255c14db65bb22f5b299d889918fb5cd2850d0e306edbf856145219ba432', '_coding_rehearsal_pg17')
    schema = adapter.schema(SimpleNamespace(NativeHost=SimpleNamespace(schema=namespace['schema'])), None, query)
    tables = {}
    for name in sorted(NEW_TABLES):
        columns = query(sql.SQL("SELECT column_name,data_type,is_nullable,column_default,character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name={} ORDER BY ordinal_position").format(sql.Literal(name)).as_string())
        definitions = query(sql.SQL("SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(d.adbin,d.adrelid),a.attidentity::text,a.attgenerated::text,(a.attcollation=0 OR a.attcollation=t.typcollation) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_type t ON t.oid=a.atttypid LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname='public' AND c.relname={} AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum").format(sql.Literal(name)).as_string())
        need(columns and definitions, 'four_rehearsed_tables_present')
        tables[name] = {'columns': [r[0] for r in columns], 'old_columns': columns, 'definitions': definitions}
    references = {}
    for prepared in prepared_references:
        provenance = prepared['provenance']; manifest = provenance['manifest']; reference = prepared['reference']
        release = manifest['release']['id']
        need(release not in references, 'three_distinct_rehearsed_references')
        details = {'release': release, 'version': manifest['release']['version'], 'system': 'ICD-10-CM',
            'digest': prepared['digest'], 'manifest_sha256': provenance['manifest_sha256'],
            'codes': manifest['expected_code_count'], 'index_entries': manifest['expected_index_entry_count'],
            'tabular_diagnoses': manifest['expected_tabular_diagnosis_count']}
        references[release] = {'digest': prepared['digest'], 'index_sha256': sha(encode(reference['index'])),
            'tabular_sha256': sha(encode(reference['tabular'])), 'provenance_sha256': sha(encode(provenance)),
            'manifest_sha256': provenance['manifest_sha256'], 'audit_details': details}
    return {'format': 'outpatient-coding-schema-rehearsal-v1', 'source_sha256': source_sha256,
        'migration': MIGRATION, 'postgresql_server_version_num': query('SHOW server_version_num')[0][0],
        'tables': tables, 'functions': {k: v for k, v in schema['functions'].items() if k == NEW_FUNCTION},
        'triggers': {k: v for k, v in schema['triggers'].items() if k in NEW_TRIGGERS},
        'constraints': {k: v for k, v in schema['constraints'].items() if k.split(':')[0] in NEW_TABLES},
        'indexes': {k: v for k, v in schema['indexes'].items() if k.split(':')[0] in NEW_TABLES},
        'references': references, 'isolated': True, 'provider_calls': 0}


def validate_schema_contract(contract, plan):
    need(type(contract) is dict and set(contract) == {'format', 'source_sha256', 'migration', 'postgresql_server_version_num',
        'tables', 'functions', 'triggers', 'constraints', 'indexes', 'references', 'isolated', 'provider_calls'},
        'closed_schema_rehearsal')
    need(contract['format'] == 'outpatient-coding-schema-rehearsal-v1'
         and contract['source_sha256'] == plan['source_sha256']
         and contract['migration'] == MIGRATION and contract['isolated'] is True
         and type(contract['provider_calls']) is int and contract['provider_calls'] == 0,
         'candidate_isolated_schema_rehearsal')
    need(set(contract['tables']) == NEW_TABLES and set(contract['functions']) == {NEW_FUNCTION}
         and set(contract['triggers']) == NEW_TRIGGERS, 'exact_four_one_three_delta')
    function = contract['functions'][NEW_FUNCTION]
    need(function['owner'] == 'quillmd_owner' and function['acl'] is None
         and function['security_definer'] is False and function['configuration'] is None
         and function['language'] == 'plpgsql' and function['arguments'] == ''
         and function['returns'] == 'trigger', 'new_guard_owner_invoker_only')
    for key, row in contract['triggers'].items():
        expected = NEW_FUNCTION if key.startswith('core_codingrun:') else 'quillmd_append_only'
        need(row['function'] == expected and row['function_schema'] == 'public'
             and row['enabled'] == 'O' and row['type'] == 27 and row['arguments_hex'] == ''
             and row['when'] is None and row['columns'] == '' and row['constraint'] == 0
             and row['deferrable'] is False and row['initially_deferred'] is False,
             'exact_row_before_update_delete_guards')
    for kind in ('constraints', 'indexes'):
        need(contract[kind] and all(k.split(':')[0] in NEW_TABLES for k in contract[kind]), 'new_table_catalog_only')
    need(type(contract['references']) is dict and len(contract['references']) == 3
         and {row['manifest_sha256'] for row in contract['references'].values()} == set(REFERENCE_PINS.values()),
         'exact_three_reference_rehearsals')


def database_preserved(before, after, contract):
    """Compare every old row/catalog entry; admit only the measured additive set."""
    old, new = before['tables'], after['tables']
    need(len(before['schema']['functions']) == 27 and len(before['schema']['triggers']) == 28,
         'exact_original_catalog_population')
    need(len(old) == 41 and not (set(old) & NEW_TABLES) and set(new) == set(old) | NEW_TABLES,
         'exact_public_table_delta')
    need(before['postgresql_server_version_num'] == after['postgresql_server_version_num']
         == contract['postgresql_server_version_num'], 'same_postgresql_version')
    for name, row in old.items():
        observed = new[name]
        need(all(equal(observed[k], row[k]) for k in TABLE_METADATA), 'old_table_metadata_' + name)
        if name in {'django_migrations', 'core_auditevent'}:
            increment = 1 if name == 'django_migrations' else 3
            need(observed['rows'] == row['rows'] + increment and observed['old_rows'] == row['old_rows']
                 and observed['ids'] == row['ids'], 'only_declared_append_' + name)
        else:
            need(observed['rows'] == row['rows'] and observed['sha256'] == row['sha256']
                 and observed['old_rows'] == row['old_rows'], 'all_original_rows_' + name)
    for name in NEW_TABLES:
        row = new[name]; expected = contract['tables'][name]
        need(all(equal(row[k], expected[k]) for k in ('columns', 'old_columns', 'definitions')), 'new_table_definition')
        need(len(row['owner_acl']) == 1 and row['owner_acl'][0][0] == 'quillmd_owner' and equal(row['owner_acl'][0][2:], [False, False, 'r'])
             and equal(row['privileges'], before['expected_new_table_privileges']), 'new_table_owner_acl')
        count = 3 if name == 'core_codingrelease' else 0
        need(row['rows'] == count and (count or row['sha256'] == EMPTY_SHA), 'no_coding_job_or_decision_created')
    need(after['applied_core_migrations'] == before['applied_core_migrations'] + [MIGRATION]
         and before['applied_core_migrations'][-1:] == ['0027_cedar_synthetic_clinician']
         and equal(after['added_migrations'], [['core', MIGRATION]])
         and after['added_content_types'] == [] and after['added_permissions'] == [], 'finite_migration_metadata')
    need(equal(before['invariants'], after['invariants']) and not any(after['invariants'].values())
         and equal(before['referenced_files'], after['referenced_files']), 'all_financial_and_file_invariants')
    a, b = before['schema'], after['schema']
    need(set(a) == set(b), 'same_catalog_categories')
    for category in ('functions', 'triggers', 'constraints', 'indexes'):
        additions = contract[category]
        need(not (set(a[category]) & set(additions)) and set(b[category]) == set(a[category]) | set(additions)
             and all(equal(b[category][k], v) for k, v in a[category].items())
             and all(equal(b[category][k], v) for k, v in additions.items()), 'exact_catalog_' + category)
    for category in set(a) - {'functions', 'triggers', 'constraints', 'indexes', 'sequences'}:
        need(equal(a[category], b[category]), 'unchanged_catalog_' + category)
    need(set(a['sequences']) == set(b['sequences']), 'no_new_sequence')
    for name, row in a['sequences'].items():
        expected = [[row[0][0] + 1, True]] if name == 'django_migrations_id_seq' else row
        need(equal(b['sequences'][name], expected), 'only_migration_sequence_consumed')
    wanted = contract['references']
    actual = after['coding']['references']
    need(set(actual) == set(wanted), 'exact_reference_release_ids')
    for key, row in wanted.items():
        need(equal(actual[key], row), 'official_reference_full_payload')
    audits = after['coding']['new_audits']
    need(len(audits) == 3 and len({a['target'] for a in audits}) == 3, 'three_distinct_reference_audits')
    for audit in audits:
        details = audit['details']; row = wanted.get(details.get('release'))
        need(row is not None and audit['action'] == 'coding.reference_import'
             and audit['actor_id'] is None and audit['organization_id'] is None
             and audit['department_id'] is None and details == row['audit_details']
             and audit['target'] == after['coding']['reference_ids'][details['release']], 'reference_audit_only')
    need(equal(before['coding']['histories'], after['coding']['histories']), 'fresh_named_history_preservation')
    return {'all_original_rows_preserved': True, 'new_tables': 4, 'new_functions': 1,
            'new_triggers': 3, 'reference_imports': 3, 'reference_audits': 3,
            'provider_calls': 0, 'clinical_mutations': 0, 'wallet_mutations': 0}


def post_resume_structure(before, after):
    need(set(before['tables']) == set(after['tables']), 'post_resume_table_population')
    for name, row in before['tables'].items():
        need(all(equal(row[key], after['tables'][name][key]) for key in TABLE_METADATA),
             'post_resume_table_metadata')
    a, b = before['schema'], after['schema']
    need(set(a) == set(b) and all(equal(a[k], b[k]) for k in a if k != 'sequences')
         and set(a['sequences']) == set(b['sequences']), 'post_resume_catalog_identity')
    need(before['applied_core_migrations'] == after['applied_core_migrations']
         and not any(after['invariants'].values()), 'post_resume_migration_invariants')
    # Existing exports and evidence remain referenced; new application work is
    # observed separately and cannot authorize a second worker stop.
    need(all(after['referenced_files'].get(k) == v for k, v in before['referenced_files'].items()),
         'post_resume_original_references')


def validate_static(stage, before, staged, manifest, source_hashes):
    need(type(manifest) is dict and set(manifest) == {'paths', 'version', 'hash'}
         and manifest['version'] == '1.1', 'static_manifest_format')
    need(manifest['hash'] == hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12],
         'static_manifest_digest')
    old_manifest = parse((Path(stage) / 'previous-staticfiles.json').read_bytes())
    need(set(manifest['paths']) == set(old_manifest['paths']) | STATIC_INPUTS
         and all(manifest['paths'][k] == v for k, v in old_manifest['paths'].items()), 'old_static_routes_preserved')
    allowed = {'staticfiles.json'}
    for name in STATIC_INPUTS:
        raw = (Path(stage) / name).read_bytes()
        need(sha(raw) == source_hashes['rebuild/static/' + name], 'static_candidate_source')
        suffix = PurePosixPath(name).suffix
        hashed = name[:-len(suffix)] + '.' + hashlib.md5(raw).hexdigest()[:12] + suffix
        need(manifest['paths'][name] == hashed and (Path(stage) / hashed).read_bytes() == raw, 'static_hashed_candidate')
        allowed.update({name, hashed})
        for path in (name, hashed):
            for ext in ('.gz', '.br'):
                if path + ext in staged:
                    import gzip
                    if ext == '.gz':
                        decoded = gzip.decompress((Path(stage) / (path + ext)).read_bytes())
                    else:
                        import brotli
                        decoded = brotli.decompress((Path(stage) / (path + ext)).read_bytes())
                    need(decoded == raw, 'static_compressed_candidate')
                    allowed.add(path + ext)
    need(set(staged) == allowed | {'.'}, 'only_two_static_sources_and_manifest')
    need(all(row['kind'] == ('directory' if name == '.' else 'file')
             and row['mode'] == (0o755 if name == '.' else 0o644) for name, row in staged.items()),
         'static_public_modes')
    need(sha((Path(stage) / 'previous-staticfiles.json').read_bytes()) == before['staticfiles.json']['sha256'],
         'original_static_manifest_bound')
    return staged


def prestop_preserved(before, after):
    # Preserve the existing narrow session-drain allowance; every other row and
    # all schema/ACL/sequence values remain exact. The quiescent snapshot, not
    # the earlier session population, is the installation preservation baseline.
    a, b = copy.deepcopy(before), copy.deepcopy(after)
    x, y = a['tables']['django_session'], b['tables']['django_session']
    changed = not equal(x, y)
    for key in ('rows', 'sha256', 'old_rows'):
        need(type(y[key]) is int and y[key] >= 0 if key == 'rows' else digest(y[key]),
             'bounded_session_drain_fingerprint')
        y[key] = x[key]
    need(equal(a, b), 'all_non_session_prestop_database_preserved')
    return {'permitted_session_drain_change': changed, 'other_rows_and_entire_schema_unchanged': True}


def coding_pending(query, *, after_resume=False):
    if query("SELECT to_regclass('public.core_codingrun')")[0][0] is None:
        return {'active': 0, 'unresolved': 0}
    active = query("SELECT count(*) FROM core_codingrun WHERE state IN ('queued','running')")[0][0]
    unresolved = query("SELECT count(*) FROM core_codingrun r WHERE r.state='uncertain' OR EXISTS "
        "(SELECT 1 FROM jsonb_array_elements(r.requests) q WHERE q->>'state' IN ('sending','unknown') "
        "OR (q->>'sent'='true' AND (q->'actual_cost' IS NULL OR q->'actual_cost'='null'::jsonb)))")[0][0]
    need(type(active) is int and type(unresolved) is int and active >= 0 and unresolved >= 0, 'coding_activity_counts')
    if not after_resume:
        need(active == unresolved == 0, 'no_pending_or_unresolved_coding_work')
    return {'active': active, 'unresolved': unresolved}


def project_database(w):
    """Exact old reader + semantic files + audit old-ID projection + coding readback.

    This projection does not change the queries or fingerprints for any clinical,
    financial, account, file, or existing schema object.
    """
    original = textwrap.dedent(inspect.getsource(w.NativeHost.database))
    need(sha(original.encode()) == DATABASE_SOURCE_SHA, 'pinned_native_database_reader')
    edits = [
        ('for _,statement in self.backup.FILE_QUERIES:',
         "for _,statement in self.backup.FILE_QUERIES+self.backup.SEMANTIC_FILE_QUERIES:"),
        ("{'auth_permission','django_content_type','django_migrations'}",
         "{'auth_permission','django_content_type','django_migrations','core_auditevent'}"),
        ("[v[0] for v in query(sql.SQL('SELECT id FROM public.{} ORDER BY id')",
         "[str(v[0]) if name=='core_auditevent' else v[0] for v in query(sql.SQL('SELECT id FROM public.{} ORDER BY id')"),
        ("        connection.execute('COMMIT')", "        result['coding']=self.coding_snapshot(query,before)\n        connection.execute('COMMIT')"),
    ]
    expected_counts = (1, 2, 1, 1)
    projected = original
    for (old, new), count in zip(edits, expected_counts):
        need(projected.count(old) == count, 'exact_database_projection_span')
        projected = projected.replace(old, new)
    inverse = projected
    for old, new in reversed(edits):
        inverse = inverse.replace(new, old)
    need(inverse == original, 'database_projection_inverse')
    namespace = dict(w.NativeHost.database.__globals__)
    # Old expected_functions/triggers are not used as acceptance; the measured
    # candidate rehearsal above supplies and checks the complete additive set.
    exec(compile(projected, '<coding-native-read-only-snapshot>', 'exec'), namespace)
    return namespace['database']


class NativeAdapter:
    """Concrete composition of the frozen native transports, never their mains."""
    def __init__(self, plan, artifacts):
        self.plan, self.artifacts = plan, artifacts
        self.legacy = load(LEGACY, LEGACY_SHA, '_coding_previous_native')
        self.prior = load(self.legacy.PRIOR, self.legacy.PRIOR_SHA, '_coding_prior_native')
        self.prior.BASE = BASE; self.prior.D = EVIDENCE
        self.legacy.D = EVIDENCE; self.legacy.BASE = BASE
        self.op = self.prior.load(self.prior.OLD_OPERATOR, self.prior.OLD_OPERATOR_SHA, '_coding_direct_host')
        self.w = w = self.op.w
        self.op.PATHS = frozenset(plan['source_sha256'])
        self.guard = self.prior.load(self.prior.GUARD, self.prior.GUARD_SHA, '_coding_source_guard')
        self.pg = self.prior.load(self.prior.ADAPTER, self.prior.ADAPTER_SHA, '_coding_pg17_catalog')
        self.hourly = load(plan['schedule']['helper']['path'], plan['schedule']['helper']['sha256'], '_coding_hourly')
        need(self.guard.current_umask() == 0o077, 'private_operator_umask')
        self.guard.DECLARED_PATHS = frozenset(plan['source_sha256'])
        self.guard.EXACT_AUTHORITY_DOC_PATHS = frozenset(p for p in plan['source_sha256'] if p.startswith('docs/'))
        self.guard.EXACT_MIGRATION_PATH = MIGRATION_PATH
        self.guard.GROUP_WRITABLE_BASE_PATHS = self.guard.DELETABLE_PATHS = frozenset()
        old_source_path = self.guard.source_path
        def source_path(name):
            if name in {'rebuild/static/' + p for p in STATIC_INPUTS}:
                need(name in self.guard.DECLARED_PATHS, 'declared_coding_static_source')
                return name
            return old_source_path(name)
        self.guard.source_path = source_path
        self.legacy.install_unknown_bridge()
        expected_unknowns = [parse(read_file(p, h))['receipt'] for p, h in
            ((self.legacy.UNKNOWN, self.legacy.UNKNOWN_SHA), (self.legacy.WM_UNKNOWN, self.legacy.WM_UNKNOWN_SHA))]
        expected_failed = self.legacy.qualify_known_failed_wm(
            read_file(self.legacy.KNOWN_FAILED_WM_RESPONSE, self.legacy.KNOWN_FAILED_WM_RESPONSE_SHA),
            read_file(self.legacy.KNOWN_FAILED_WM_METADATA, self.legacy.KNOWN_FAILED_WM_METADATA_SHA))
        database = project_database(w)
        adapter = self
        class CodingHost(self.op.DirectHost):
            resumed = False
            def schema(self, query):
                return adapter.pg.schema(w, self, query)
            def database(self, files, before=None):
                return database(self, files, before)
            def coding_snapshot(self, query, before):
                return adapter.coding_snapshot(query, before)
            def _pending(self, query):
                adapter.legacy.known_failed_wm(query, expected_failed)
                if self.resumed:
                    adapter.legacy.post_resume_pending(query, expected_unknowns)
                else:
                    adapter.legacy.pending(query, expected_unknowns)
                    need(query("SELECT count(*) FROM core_templatedefinitionpreparation WHERE state IN ('queued','inventory','proposer','checker')")[0][0] == 0
                         and query("SELECT count(*) FROM core_aistagereceipt WHERE state IN ('reserved','sending','received','unknown')")[0][0] == 0,
                         'no_pending_semantic_work')
                coding_pending(query, after_resume=self.resumed)
            def validate_static(self, stage):
                return adapter.static_validate(stage)
        self.host = CodingHost(plan['candidate'], EVIDENCE)
        self.host.deadline = min(self.host.deadline, time.monotonic() +
            (datetime.fromisoformat(plan['schedule']['deadline']) - datetime.now(timezone.utc)).total_seconds())
        self.active_environment = self.legacy.environment(self.host.original, plan['candidate'])
        self.source = Path(plan['source_worktree'])
        self.publication = self.guard.make_plan(ROOT, BASE, plan['candidate'], frozenset(plan['source_sha256']),
            owner_uid=1000, owner_gid=1000, service_uid=996, service_gids=[988])
        self.guard.validate_published(self.source, self.publication, plan['candidate'])
        self.private_before = self.op.private_boundary()
        self.static = artifacts['static']
        self.static_preparation = None

    def hold(self):
        return self.op.direct_hold(self.host)

    def coding_snapshot(self, query, before):
        cases = self.artifacts['histories']['cases']
        from psycopg import sql
        histories = {}
        for name, row in cases.items():
            observed = query(sql.SQL('SELECT to_jsonb(e) FROM core_encounter e WHERE id={}::uuid').format(
                sql.Literal(row['encounter_id'])).as_string())
            need(len(observed) == 1, 'named_original_encounter_exists')
            histories[name] = sha(encode(observed[0][0]))
            need(histories[name] == row['encounter_sha256'], 'named_original_encounter_unchanged')
        refs = {}; ids = {}; audits = []
        if query("SELECT to_regclass('public.core_codingrelease')")[0][0] is not None:
            for identifier, release, index, tabular, provenance, fingerprint in query(
                'SELECT id::text,release_id::text,index,tabular,provenance,digest FROM core_codingrelease ORDER BY release_id'):
                manifest = provenance['manifest']
                details = {'release': release, 'version': manifest['release']['version'], 'system': 'ICD-10-CM',
                    'digest': fingerprint, 'manifest_sha256': provenance['manifest_sha256'],
                    'codes': manifest['expected_code_count'], 'index_entries': manifest['expected_index_entry_count'],
                    'tabular_diagnoses': manifest['expected_tabular_diagnosis_count']}
                refs[release] = {'digest': fingerprint, 'index_sha256': sha(encode(index)),
                    'tabular_sha256': sha(encode(tabular)), 'provenance_sha256': sha(encode(provenance)),
                    'manifest_sha256': provenance['manifest_sha256'], 'audit_details': details}
                ids[release] = identifier
            if before:
                old_ids = before['tables']['core_auditevent']['ids']
                condition = sql.SQL('id NOT IN ({})').format(sql.SQL(',').join(map(sql.Literal, old_ids))) if old_ids else sql.SQL('true')
                audits = [row[0] for row in query(sql.SQL('SELECT to_jsonb(a) FROM core_auditevent a WHERE {} ORDER BY id').format(condition).as_string())]
        return {'histories': histories, 'references': refs, 'reference_ids': ids, 'new_audits': audits,
                'activity': coding_pending(query, after_resume=self.host.resumed)}

    def snapshot(self, label, before=None):
        value = self.host.snapshot(before=before)
        context = {u: self.hourly.capture(u, value['configuration']) for u in self.hourly.UNITS}
        context[self.hourly.DORMANT_SERVICE] = self.hourly.capture_dormant(value['configuration'])
        need(all(equal(value['foreign_services'][u], context[u]['service']) for u in self.hourly.OBSERVED_UNITS),
             'coherent_foreign_observation')
        write_new(EVIDENCE / (label + '-snapshot.json'), value)
        write_new(EVIDENCE / (label + '-foreign-context.json'), context)
        return value, context

    def external(self, before, after):
        a, ac = before; b, bc = after
        for category in ('configuration', 'files', 'mail'):
            need(equal(a[category], b[category]), 'unchanged_foreign_' + category)
        population, proof = self.hourly.comparison_population(a['foreign_services'], b['foreign_services'], ac, bc)
        self.w.foreign_service_preservation(population, b['foreign_services'])
        self.same_ingress()
        need(self.op.private_boundary() == self.private_before, 'unchanged_private_boundary')
        return proof

    def same_ingress(self):
        for path in self.op.INGRESS_PATHS:
            raw, metadata = self.op.read_ingress(path)
            need(raw == self.host.ingress_originals[path] and metadata == self.host.ingress_metadata[path],
                 'unchanged_ingress_identity')

    def admission(self, snapshot):
        need(self.host.source_revision() == BASE, 'installed_base')
        self.op.complete_source(BASE)
        need(not git(ROOT, 'status', '--porcelain', '--untracked-files=all').strip(), 'shared_source_clean_all_files')
        previous = self.artifacts['previous_receipt']
        need(previous.get('complete') is True and previous.get('candidate') == BASE
             and previous.get('environment_sha256') == sha(self.host.original), 'previous_install_environment')
        self.w.old.service_boundary(self.host.native, self.host.storage, BASE)
        for unit in self.w.old.OPERATIONS:
            state = self.host.native.state(unit)
            need(state.get('ActiveState') in ('inactive', 'failed') and state.get('MainPID') == '0', 'owned_operations_inactive')
        forecast(self.plan, self.artifacts['forecast'], snapshot['configuration'])
        self.host.no_pending_work(); self.host.space('coding_before_stop')
        self.same_ingress()
        need(sha((APP / 'ops/backup_restore.py').read_bytes()) == BACKUP_SHA
             and sha(git(self.source, 'show', self.plan['candidate'] + ':rebuild/ops/backup_restore.py')) == BACKUP_SHA,
             'unchanged_permanent_backup')
        self.static_validate(Path(self.static['stage']))
        self.static_preparation = {'before': self.static['before'], 'staged': self.static['staged'], 'stage': self.static['stage']}
        need(self.w.old.static_primitives().static_inventory(APP / 'staticfiles') == self.static['before'], 'installed_static_baseline')
        self.w.old.static_primitives().retain_static(APP / 'staticfiles', EVIDENCE / 'public-assets-before.tar', self.static['before'])
        write_new(EVIDENCE / 'environment-before.fernet', self.host.cipher.encrypt(self.host.original))
        write_new(EVIDENCE / 'environment-after.fernet', self.host.cipher.encrypt(self.active_environment))

    def stop(self):
        for unit in self.w.old.UNITS:
            self.host.service('stop', unit)
        self.host.require_stopped(); self.host.no_pending_work()

    def backup(self, before):
        result = self.prior.fresh_backup(self.w, self.host, before)
        write_new(EVIDENCE / 'fresh-backup-complete.json', result)
        return result

    def restore(self, backup):
        return self.legacy.restore_fresh_backup(self.w, self.host, backup)

    def publish_source(self):
        self.host.check_hold(); self.host.require_stopped()
        self.guard.publish_exact_source(ROOT, self.publication)

    def migrate_references(self):
        """One transaction; no post_migrate signal, networking, worker or retry."""
        self.host.check_hold(); self.host.require_stopped()
        roles = parse(self.w.protected(self.w.old.ROLES, 16384))
        need(roles['database'] == 'quillmd_fresh' and roles['container_id'] ==
             self.host.backup.inspect_container('quillmd-fresh-postgres')['Id'], 'exact_owner_database')
        env = self.prior.app_environment(self.w, self.host.original)
        role = roles['roles']['migrator']
        env.update(QUILLMD_DB_NAME='quillmd_fresh', QUILLMD_DB_USER=role['name'],
            QUILLMD_DB_PASSWORD=role['password'], QUILLMD_DB_HOST='127.0.0.1', QUILLMD_DB_PORT='55438',
            PGOPTIONS='-c role=quillmd_owner', PYTHONDONTWRITEBYTECODE='1')
        code = owner_transaction_source(self.plan)
        write_new(EVIDENCE / 'owner-transaction-source.py', code.encode())
        result = subprocess.run([str(APP / '.venv/bin/python'), '-B', '-c', code], cwd=APP,
                                env=env, capture_output=True, timeout=300)
        # Never include credential-bearing errors or command environments in reports.
        write_new(EVIDENCE / 'owner-transaction-result.json', {'returncode': result.returncode,
            'stdout_sha256': sha(result.stdout), 'stderr_sha256': sha(result.stderr), 'retry_authorized': False})
        need(result.returncode == 0 and result.stdout.strip() == b'coding_transaction_committed', 'owner_transaction_outcome')

    def static_validate(self, stage):
        rows = self.w.old.static_primitives().static_inventory(stage)
        # The original manifest is outside the publishable inventory.
        observed = {k: v for k, v in rows.items() if k != 'previous-staticfiles.json'}
        need(equal(observed, self.static['staged']), 'staged_inventory_pin')
        return validate_static(stage, self.static['before'], observed,
            parse((Path(stage) / 'staticfiles.json').read_bytes()), self.plan['source_sha256'])

    def publish_static(self):
        self.host.check_hold(); self.host.require_stopped()
        original = self.w.NativeHost.install_static
        namespace = dict(original.__globals__); namespace['STATIC_INPUTS'] = STATIC_INPUTS
        function = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
        self.static_installed = function(self.host, self.static_preparation)
        return self.static_installed

    def configure(self):
        self.host.check_hold(); self.host.require_stopped()
        self.op.replace_account_environment(self.host, self.host.original, self.active_environment, 'coding-forward')

    def start(self):
        self.host.resumed = True  # No later failure may stop a worker with a sent request.
        for unit in (self.w.old.UNITS[2], *self.w.old.UNITS[:2]):
            self.guard.validate_published(ROOT, self.publication, self.plan['candidate'])
            self.op.checked_account_environment(self.host, self.active_environment)
            self.same_ingress(); self.host.service('start', unit)
        readiness = self.host.readiness(self.plan['candidate'])
        import httpx
        response = httpx.get('https://app.quillmd.com/health/', timeout=20, follow_redirects=False)
        value = response.json()
        need(response.status_code == 200 and value.get('status') == 'ok'
             and value.get('release') == self.plan['candidate'] and value.get('surface') == 'doctor'
             and value.get('data_mode') == 'synthetic-only', 'normal_https_candidate_readiness')
        readiness['normal_https'] = value
        return readiness

    def finish(self):
        self.op.complete_source(self.plan['candidate'])
        need(not git(ROOT, 'status', '--porcelain', '--untracked-files=all').strip(), 'published_source_clean_all_files')
        self.guard.validate_published(ROOT, self.publication, self.plan['candidate'])
        self.op.checked_account_environment(self.host, self.active_environment)
        self.same_ingress()
        need(self.w.old.static_primitives().static_inventory(APP / 'staticfiles') == self.static_installed,
             'complete_published_static_identity')
        need(self.op.private_boundary() == self.private_before, 'complete_private_preservation')
        return {'environment_sha256': sha(self.active_environment), 'private_boundary_unchanged': True}


def owner_transaction_source(plan):
    """Fixed operation only; no caller SQL, arbitrary command, post_migrate or retry."""
    return '''import os, subprocess
os.environ['DJANGO_SETTINGS_MODULE']='quillmd.settings'
import django; django.setup()
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from core.management.commands.import_coding_reference import prepare_reference, save_reference
candidate = CANDIDATE
def require(value):
 if not value: raise RuntimeError('owner_transaction_refused')
require(subprocess.check_output(['git','-C','/opt/meddoc-pro','rev-parse','HEAD']).strip().decode() == candidate)
with connection.cursor() as c:
 c.execute('SELECT current_database(),current_user')
 require(c.fetchone() == ('quillmd_fresh','quillmd_owner'))
prepared = [prepare_reference(path,pin) for path,pin in REFERENCES]
executor = MigrationExecutor(connection)
target = [('core','0028_outpatient_coding')]
require([(m.app_label,m.name,back) for m,back in executor.migration_plan(target)] == [('core','0028_outpatient_coding',False)])
with transaction.atomic():
 executor.migrate(target)
 for item in prepared:
  reference, created = save_reference(item)
  require(created is True)
print('coding_transaction_committed')
'''.replace('CANDIDATE', repr(plan['candidate'])).replace('REFERENCES', repr(sorted(REFERENCE_PINS.items())))


def read_admission(plan):
    validate_plan(plan)
    source = Path(plan['source_worktree']); ex = plan['execution']; private = Path(ex['worktree'])
    need(source.resolve(strict=True) == source and private.resolve(strict=True) == private
         and Path.cwd() == private, 'execution_worktree_and_cwd')
    need(git(source, 'rev-parse', 'HEAD').strip().decode() == plan['candidate']
         and not git(source, 'status', '--porcelain', '--untracked-files=all').strip(), 'clean_candidate_source')
    need(git(private, 'rev-parse', 'HEAD').strip().decode() == ex['commit']
         and not git(private, 'status', '--porcelain', '--untracked-files=all').strip(), 'clean_private_declaration')
    for repo in (source, private):
        common = Path(git(repo, 'rev-parse', '--git-common-dir').strip().decode())
        if not common.is_absolute():
            common = repo / common
        need(common.resolve(strict=True) == ROOT / '.git', 'same_repository')
    for before, after in ((BASE, plan['first_commit']), (plan['first_commit'], plan['candidate']), (plan['candidate'], ex['commit'])):
        git(private, 'merge-base', '--is-ancestor', before, after)
    need(git(private, 'diff', '--no-renames', '--name-status', '-z', plan['candidate'], ex['commit'])
         == b'A\0' + ex['path'].encode() + b'\0', 'execution_only_declaration_commit')
    need(re.fullmatch(b'100644 blob [a-f0-9]{40}\t' + re.escape(ex['path'].encode()) + b'\0',
        git(private, 'ls-tree', '-z', ex['commit'], '--', ex['path'])), 'committed_declaration_mode')
    declaration = read_file(private / ex['path'], ex['sha256'], private=False)
    need(git(private, 'show', ex['commit'] + ':' + ex['path']) == declaration
         and scope_digest(plan).encode() in declaration and plan['candidate'].encode() in declaration
         and b'outpatient-coding-20261014-v1' in declaration, 'prospective_scope_declaration')
    need(os.environ.get('RULED_MUTATION_DECLARATION') == ex['path']
         and os.environ.get('RULED_MUTATION_DECL_COMMIT') == ex['commit'], 'ruled_wrapper_required')
    changed = set(git(source, 'diff', '--name-only', BASE, plan['candidate']).decode().splitlines())
    need(changed == set(plan['source_sha256']), 'exact_candidate_range')
    for path, pin in plan['source_sha256'].items():
        need(sha(git(source, 'show', plan['candidate'] + ':' + path)) == pin
             and sha(git(source, 'show', plan['first_commit'] + ':' + path)) == pin
             and sha((source / path).read_bytes()) == pin, 'first_candidate_disk_source_identity')
    need(sha(Path(__file__).read_bytes()) == plan['module_sha256'], 'executed_module_pin')
    need(git(ROOT, 'rev-parse', 'origin/main').strip().decode() == plan['candidate'], 'actual_main_candidate')
    result = subprocess.run(['bash', str(source / 'scripts/check-citation.sh'), plan['candidate']],
                            cwd=source, capture_output=True, timeout=120)
    need(result.returncode == 0, 'fresh_exact_candidate_citation')
    artifacts = {key: reference(ref) for key, ref in plan['artifacts'].items()}
    validate_schema_contract(artifacts['schema'], plan)
    migration_tree = ast.parse((source / MIGRATION_PATH).read_text())
    guard_sql = next(ast.literal_eval(n.value) for n in migration_tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CODING_GUARDS' for t in n.targets))
    body = re.fullmatch(r'.*CREATE FUNCTION quillmd_coding_run_guard\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$(.*?)\$\$;.*', guard_sql, re.S)
    need(body is not None and artifacts['schema']['functions'][NEW_FUNCTION]['body'] == body[1],
         'rehearsed_function_body_equals_candidate_migration')
    need(artifacts['ci'].get('candidate') == plan['candidate'] and artifacts['ci'].get('passed') is True,
         'retained_exact_ci_citation')
    histories = artifacts['histories']
    need(histories.get('read_only') is True and type(histories.get('provider_calls')) is int and histories['provider_calls'] == 0
         and histories.get('release') == BASE and {'casey_finalized', 'kasra_5'} <= set(histories['cases'])
         and all(re.fullmatch('[a-f0-9-]{36}', row['encounter_id']) and digest(row['encounter_sha256'])
                 for row in histories['cases'].values()), 'fresh_original_finalized_histories')
    artifacts['forecast'] = reference(plan['schedule']['forecast'])
    for ref in plan['schedule']['supporting']:
        read_file(ref['path'], ref['sha256'])
    forecast(plan, artifacts['forecast'])
    for path, pin in REFERENCE_PINS.items():
        read_file(path, pin)
    need(artifacts['static'].get('format') == 'outpatient-coding-static-stage-v1'
         and artifacts['static'].get('candidate') == plan['candidate']
         and artifacts['static'].get('source_sha256') == {k: v for k, v in plan['source_sha256'].items()
             if k.startswith('rebuild/static/')}, 'actual_static_source_stage')
    return artifacts


def execute(plan, adapter, journal):
    """Finite one-attempt lifecycle. After failure, retain the last phase for review."""
    phase = 'admitted'; resumed = False; mutation_started = False
    def mark(name, **values):
        nonlocal phase
        phase = name
        journal(name, {'phase': name, 'candidate': plan['candidate'], 'provider_calls': 0, **values})
    try:
        with adapter.hold():
            before = adapter.snapshot('prestop')
            adapter.admission(before[0]); mark('prestop-admitted')
            mark('stop-attempted'); adapter.stop()
            quiescent = adapter.snapshot('quiescent')
            adapter.external(before, quiescent)
            drain = prestop_preserved(before[0]['database'], quiescent[0]['database'])
            mark('quiescent-qualified', drain=drain)
            backup = adapter.backup(quiescent[0]); mark('backup-qualified', backup_run_id=backup['run_id'])
            restore = adapter.restore(backup); mark('restore-qualified', backup_run_id=backup['run_id'])
            after_backup = adapter.snapshot('after-backup')
            adapter.external(quiescent, after_backup)
            need(equal(quiescent[0]['database'], after_backup[0]['database']), 'quiescent_backup_interval_preserved')
            mark('source-publication-attempted'); mutation_started = True
            adapter.publish_source(); mark('source-published')
            mark('owner-transaction-attempted'); adapter.migrate_references(); mark('owner-transaction-complete')
            changed = adapter.snapshot('post-schema', quiescent[0]['database'])
            proof = database_preserved(quiescent[0]['database'], changed[0]['database'], adapter.artifacts['schema'])
            adapter.external(quiescent, changed); mark('schema-and-originals-qualified', preservation=proof)
            mark('static-publication-attempted'); adapter.publish_static(); mark('static-published')
            mark('environment-publication-attempted'); adapter.configure(); mark('environment-published')
            final = adapter.snapshot('pre-resume', quiescent[0]['database'])
            database_preserved(quiescent[0]['database'], final[0]['database'], adapter.artifacts['schema'])
            adapter.external(quiescent, final); mark('strict-preservation-complete')
            mark('owned-services-resume-attempted'); resumed = True
            readiness = adapter.start()
            post = adapter.snapshot('post-resume')
            post_resume_structure(final[0]['database'], post[0]['database'])
            adapter.external(quiescent, post)
            details = adapter.finish()
            result = {'format': FORMAT, 'complete': True, 'base': BASE, 'candidate': plan['candidate'],
                'native_readiness': readiness, 'preservation': proof, 'fresh_restore': restore,
                'strict_preservation_ends_before_resume': True, 'post_resume_database_is_observation_only': True,
                'provider_calls': 0, 'recovered_forward': False, **details}
            mark('operation-complete', result=result)
            return result
    except BaseException as error:
        # Never infer rollback or repeat a possibly committed transaction. In
        # particular, never stop the worker after it might have sent a request.
        journal('pending-recovery', {'complete': False, 'phase': phase, 'candidate': plan['candidate'],
            'source_or_schema_mutation_attempted': mutation_started, 'services_may_have_resumed': resumed,
            'error_class': type(error).__name__, 'reason': str(error) if isinstance(error, Refusal) else 'bounded_operation_failure',
            'automatic_retry': False, 'destructive_database_rollback': False,
            'worker_stop_after_resume': False, 'provider_calls': 0})
        raise


def render_private_adapter(module_path, module_sha256, input_path, input_sha256):
    """Render a fixed, exclusive private launcher; this function performs no I/O."""
    need(digest(module_sha256) and digest(input_sha256), 'adapter_actual_pins')
    need(Path(module_path).is_absolute() and Path(input_path).is_absolute(), 'adapter_absolute_paths')
    return ("#!/usr/bin/env python3\n# Exact reviewed coding adapter; default inert.\n"
        "import hashlib, importlib.util, pathlib, sys\n"
        f"MODULE = {str(module_path)!r}\nMODULE_SHA = {module_sha256!r}\n"
        f"INPUT = {str(input_path)!r}\nINPUT_SHA = {input_sha256!r}\n"
        "if sys.argv[1:] != ['--execute']:\n print('{\"inert\":true,\"input_loaded\":false}'); raise SystemExit(0)\n"
        "raw = pathlib.Path(MODULE).read_bytes()\nif hashlib.sha256(raw).hexdigest() != MODULE_SHA: raise RuntimeError('module_pin')\n"
        "spec = importlib.util.spec_from_file_location('_reviewed_coding_install', MODULE)\n"
        "module = importlib.util.module_from_spec(spec)\nexec(compile(raw,MODULE,'exec'),module.__dict__)\n"
        "module.main(['--execute','--inputs',INPUT,'--input-sha256',INPUT_SHA])\n").encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--inputs'); parser.add_argument('--input-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'inert': True, 'input_loaded': False, 'service_actions': 0,
                          'database_queries': 0, 'provider_calls': 0}))
        return
    need(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000, 'native_operator_identity')
    need(args.inputs and digest(args.input_sha256), 'actual_protected_inputs')
    raw = read_file(args.inputs, args.input_sha256)
    plan = parse(raw); artifacts = read_admission(plan)
    need(not EVIDENCE.exists(), 'no_implicit_retry_or_evidence_overwrite')
    adapter = NativeAdapter(plan, artifacts)
    EVIDENCE.mkdir(mode=0o700)
    write_new(EVIDENCE / 'execution-inputs.json', raw)
    result = execute(plan, adapter, lambda name, value: write_new(EVIDENCE / (name + '.json'), value))
    write_new(EVIDENCE / 'installation-complete.json', result)
    print(json.dumps({'complete': True, 'candidate': plan['candidate'],
                      'receipt': str(EVIDENCE / 'installation-complete.json')}))


if __name__ == '__main__':
    main()
