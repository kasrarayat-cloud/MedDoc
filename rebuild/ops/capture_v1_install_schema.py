#!/usr/bin/env python3
"""Capture the actual 0018→0038 PostgreSQL contract on ONE empty owned QA DB.

Run only after the lead grants the serialized QA slot, through the existing
protected QA launcher. No credentials are accepted, read or printed here. This
command refuses installed, production, shared QA, populated or redirected DBs.
It performs no provider/service/offsite/restore operation.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
# Prospective capture only. The normal installer keeps its separately reviewed
# 0037/nineteen pin until this new raw PostgreSQL contract is actually validated.
SCHEMA = 'docs/rebuild/v1/private-synthetic-install-preparation-20261004/schema-contract-0038.PREPARED.json'
SCHEMA_SHA256 = '47e45ec7ff94ce89cfa3ce8f3fbc514fa05eddb5e88e480d1ed58fa26706da96'
LEAF = '0038_reinspection_confirmation_guard'
FORWARD_MIGRATIONS = 20
DATABASE = 'quillmd_qa_sol_installcontract38_1004'
OWNED_OUTPUT = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations')


def require_declared_core_leaf(graph, leaf):
    """A final migrate-all must never apply an undeclared newer core migration."""
    if [node for node in graph.leaf_nodes() if node[0] == 'core'] != [('core', leaf)]:
        raise ValueError('Actual core migration leaf differs from the reviewed capture contract.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    require_source = ROOT.resolve() == ROOT and ROOT.is_relative_to(Path('/opt/meddoc-pro/.worktrees'))
    if not require_source or os.path.lexists(ROOT / 'rebuild/.env'):
        raise SystemExit('Capture requires an isolated source worktree without an environment file.')
    sys.path.insert(0, str(ROOT / 'rebuild'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.core.management import call_command
    from ops import backup_restore, integrity_contract, v1_install_catalog
    from ops import v1_private_install_adapter as a
    from ops import v1_private_install_preparation as p
    target = Path(args.output)
    p.require(target.is_absolute() and target.resolve() == target and target.parent.is_relative_to(OWNED_OUTPUT)
              and not target.exists(), 'Unused owned operations evidence path required.')
    db = connection.settings_dict
    p.require(db['NAME'] == DATABASE and db['HOST'] == '127.0.0.1' and str(db['PORT']) == '55731'
              and db['USER'] == 'quillmd_qa' and settings.QUILLMD_DATA_MODE == 'synthetic',
              'Only the explicitly owned synthetic QA database/role is eligible.')
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
        p.require(cursor.fetchone()[0] == 0, 'Contract capture requires an empty new QA database; no downgrade is allowed.')
        cursor.execute('SELECT current_user')
        owner = cursor.fetchone()[0]
        p.require(owner == db['USER'], 'Unexpected QA schema owner/role.')
    schema_bytes = (ROOT / SCHEMA).read_bytes()
    p.require(p.sha(schema_bytes) == SCHEMA_SHA256, 'Reviewed prospective capture graph changed.')
    schema = json.loads(schema_bytes)
    p.require((schema['baseline_core_migration'], schema['candidate_core_migration']) == (p.BASELINE_NODE, LEAF)
              and len(schema['forward_migration_sha256']) == FORWARD_MIGRATIONS,
              'Exact twenty-member prospective capture graph required.')
    sources = a.CATALOG_SOURCES | {'rebuild/core/migrations/' + name + '.py'
        for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
    before_sources = {path: p.sha((ROOT / path).read_bytes()) for path in sources}
    for name, expected in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}.items():
        p.require(before_sources['rebuild/core/migrations/' + name + '.py'] == expected,
                  'Reviewed baseline or forward migration source changed.')
    p.require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT),
              'Freeze and commit capture source before the QA run.')
    def snapshot(before=None):
        with connection.cursor() as cursor:
            cursor.execute("SET timezone='UTC'; SET datestyle='ISO, MDY'")
        def query(statement):
            with connection.cursor() as cursor:
                cursor.execute(statement)
                return cursor.fetchall()
        def copy_hash(statement):
            with connection.connection.cursor().copy(statement) as stream:
                return v1_install_catalog.stream_hash(stream)
        return v1_install_catalog.read(query, copy_hash, before=before)
    executor = MigrationExecutor(connection)
    require_declared_core_leaf(executor.loader.graph, LEAF)
    noncore = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'core']
    executor.migrate(noncore + [('core', p.BASELINE_NODE)])
    call_command('migrate', 'core', p.BASELINE_NODE, interactive=False, verbosity=0)
    # Reproduce the already reviewed database_roles.py function-execution
    # envelope within THIS owned database. Never modify shared/global roles.
    # The known QA owner spelling is normalized to the private owner afterwards.
    with connection.cursor() as cursor:
        cursor.execute('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC')
        cursor.execute('ALTER DEFAULT PRIVILEGES FOR ROLE quillmd_qa IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC')
    before = snapshot()
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan([('core', LEAF)])
    p.require({migration.name for migration, backward in plan if not backward} == set(schema['forward_migration_sha256'])
              and not any(backward for migration, backward in plan), 'Exact twenty forward migrations required.')
    call_command('migrate', 'core', LEAF, interactive=False, verbosity=0)
    call_command('migrate', interactive=False, verbosity=0)
    after = snapshot(before)
    record = {'format': 'quillmd-v1-postgresql-upgrade-contract-v1', 'baseline': p.BASELINE,
        'source_sha256': before_sources, 'schema_sha256': p.sha(schema_bytes),
        'before': a.schema_catalog(before, owner=owner), 'after': a.schema_catalog(after, owner=owner),
        'new_permissions': after['new_noncore_rows']['auth_permission'],
        'new_content_types': after['new_noncore_rows']['django_content_type']}
    p.require({path: p.sha((ROOT / path).read_bytes()) for path in sources} == before_sources, 'Capture source changed.')
    p.require(after['old_rows'] == before['rows'], 'Baseline metadata changed during the synthetic contract capture.')
    p.require({name: fields for name, fields in before['columns'].items() if name.startswith('core_')}
              == schema['baseline_core_columns']
              and {name: fields for name, fields in after['columns'].items() if name.startswith('core_')}
              == schema['candidate_core_columns'], 'Actual baseline/candidate core columns differ from the reviewed source.')
    with connection.cursor() as cursor:
        cursor.execute(integrity_contract.CATALOG); guards = cursor.fetchall()
        cursor.execute(integrity_contract.CONTEXT); context = cursor.fetchall()
    integrity = integrity_contract.assess(guards, context, len(integrity_contract.GUARDS))
    p.require(integrity['passed'] and len(guards) == 111
              and len(after['catalog']['functions']) == 28,
              'Actual source-bound PostgreSQL integrity definitions differ.')
    raw = (json.dumps(record, indent=2, sort_keys=True) + '\n').encode()
    a.validate_catalog_contract(raw, {path: (ROOT / path).read_bytes() for path in sources}, schema_bytes)
    backup_restore.private_dir(target.parent, create=True)
    backup_restore.write_private(target, raw)
    print(json.dumps({'complete': True, 'contract_sha256': p.sha(raw), 'database': DATABASE,
                      'before_tables': len(before['tables']), 'after_tables': len(after['tables']),
                      'before_core_tables': len(schema['baseline_core_columns']),
                      'after_core_tables': len(schema['candidate_core_columns']),
                      'after_functions': len(after['catalog']['functions']), 'after_triggers': len(guards),
                      'forward_migrations': FORWARD_MIGRATIONS, 'provider_calls': 0, 'installed_mutation_performed': False}))


if __name__ == '__main__':
    main()
