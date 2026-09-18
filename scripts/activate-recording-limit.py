#!/usr/bin/env python3
"""Cited private activation of the binding recording charge limit: reviewed code plus migration 0013; default is read-only.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B <worktree>/scripts/activate-recording-limit.py \
        --target FULL_MERGE_SHA --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/recording-limit-activation-<label>.json [--execute]

The executing form runs only through scripts/run-ruled-mutation.sh with the committed declaration.

Migration 0013 creates no table and no model, so Django's post-migrate bookkeeping (content types, permissions) has nothing
to add. Its whole database delta is: one new NOT NULL numeric column on the empty reconciliation table, the platform-cost
kind check widened by one kind, the usage check relaxed from "charged = 1.5 x cost" to "charged <= 1.5 x cost", one partial
unique index, and one migration-history row. Every other row, column, constraint and index must be identical.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
HERE = Path(__file__).resolve().parent
BASELINE = '3eac783a55b6b771016da258ab2b57e0a06bdb38'
DECL = 'docs/foundation/mutations/20260918-quillmd-recording-limit.md'
SELF = 'scripts/activate-recording-limit.py'
PREVIOUS_MIGRATION = '0012_billing_policy'
MIGRATION = '0013_recording_charge_limit'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
MIGRATION_SHA256 = '424b7b1255b98f4b86fac89d6b1ea604027a534b58d13aebd2084beadb26789e'
TABLE_COUNT = 35
# Every tracked path that may differ between the running release and the target, so the activation judges the whole tree.
ALLOWED = {
    # PR #1195 — milestone close-out documentation
    'docs/rebuild/CHECKPOINT.md', 'docs/rebuild/external-verification-runbook.md', 'docs/rebuild/owner-actions.md',
    'docs/rebuild/patient-data-release-requirements.md', 'docs/rebuild/storage-encryption.md',
    # plaintext recovery-and-reap act (scripts, tests and its declaration only)
    'scripts/verify-and-reap-fresh-plaintext.py', 'scripts/migrate-fresh-storage.py', 'rebuild/ops/test_plaintext_reap.py',
    'rebuild/ops/test_storage_migration.py', 'docs/foundation/mutations/20260918-quillmd-plaintext-recovery-reap.md',
    # binding recording charge limit
    'docs/rebuild/cost-definition.md', 'rebuild/core/audio.py', 'rebuild/core/billing.py', 'rebuild/core/jobs.py',
    'rebuild/core/management/commands/audit_billing.py', MIGRATION_PATH, 'rebuild/core/models.py', 'rebuild/core/views.py',
    'rebuild/quillmd/urls.py', 'rebuild/templates/billing.html', 'rebuild/templates/encounter_detail.html',
    'rebuild/templates/voice_limit.html', 'rebuild/private-beta-browser.mjs', 'rebuild/verify-private-release.mjs',
    'rebuild/core/tests/audio_fixtures.py', 'rebuild/core/tests/test_billing_boundary.py',
    'rebuild/core/tests/test_billing_boundary_regressions.py', 'rebuild/core/tests/test_billing_policy.py',
    'rebuild/core/tests/test_encounter_snapshot.py', 'rebuild/core/tests/test_recording_limit.py',
    'rebuild/core/tests/test_refutation.py', 'rebuild/core/tests/test_wm_workflow.py',
    *('rebuild/core/tests/fixtures/audio/' + name for name in ('tone-3s.wav', 'tone-3s.mp3', 'tone-3s.m4a', 'tone-3s-fragmented.m4a',
                                                              'tone-3s.webm', 'tone-3s-live.webm')),
    # its refutation fixes: every reader of the old exact-1.5x rule, the worker's upload reaper and the consent wording
    'rebuild/ops/backup_restore.py', 'rebuild/core/management/commands/worker.py', 'rebuild/core/forms.py', 'rebuild/README.md',
    'docs/rebuild/backup-restore.md', 'docs/rebuild/security-readiness.md',
    'rebuild/ops/test_billing_activation.py', 'rebuild/ops/test_recording_limit_activation.py', SELF, DECL,
}
# The operations Django generated, in order: (operation, model, name). The file itself is pinned by SHA-256 above.
OPERATIONS = [('RemoveConstraint', 'platformcost', 'platform_cost_kind_known'), ('RemoveConstraint', 'usage', 'exact_usage_multiplier'),
              ('AddField', 'costreconciliation', 'over_limit_delta'), ('AlterField', 'platformcost', 'kind'),
              ('AddConstraint', 'platformcost', 'one_over_limit_absorption_per_job'), ('AddConstraint', 'platformcost', 'platform_cost_kind_known'),
              ('AddConstraint', 'usage', 'usage_charge_at_most_multiplier')]
# pg_get_constraintdef / pg_indexes.indexdef as PostgreSQL 17 renders them, measured on the live database (before) and on a
# database migrated to 0013 by the test runner (after).
DEFINITIONS_BEFORE = {
    ('core_platformcost', 'platform_cost_kind_known'):
        "CHECK (((kind)::text = ANY ((ARRAY['fixed_overhead'::character varying, 'absorbed_failure'::character varying])::text[])))",
    ('core_usage', 'exact_usage_multiplier'):
        'CHECK (((actual_cost >= (0)::numeric) AND (charged_cost >= (0)::numeric) AND (charged_cost = (actual_cost * 1.5))))',
}
DEFINITIONS_AFTER = {
    ('core_platformcost', 'platform_cost_kind_known'):
        "CHECK (((kind)::text = ANY ((ARRAY['fixed_overhead'::character varying, 'absorbed_failure'::character varying, "
        "'absorbed_over_limit'::character varying])::text[])))",
    ('core_usage', 'usage_charge_at_most_multiplier'):
        'CHECK (((actual_cost >= (0)::numeric) AND (charged_cost >= (0)::numeric) AND (charged_cost <= (actual_cost * 1.5))))',
}
NEW_INDEX = ('core_platformcost', 'one_over_limit_absorption_per_job',
             "CREATE UNIQUE INDEX one_over_limit_absorption_per_job ON public.core_platformcost USING btree (job_id) "
             "WHERE ((kind)::text = 'absorbed_over_limit'::text)")
NEW_COLUMN = {'table_name': 'core_costreconciliation', 'column_name': 'over_limit_delta', 'data_type': 'numeric', 'udt_name': 'numeric',
              'is_nullable': 'NO', 'column_default': None, 'numeric_precision': 24, 'numeric_scale': 12}
UNITS = ['quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker')]
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.run(command, check=True, **kwargs)


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_migration(source):
    """The generated migration exactly: pinned bytes, one Migration class depending on 0012, the seven operations in order."""
    data = source if isinstance(source, bytes) else source.encode()
    require(sha(data) == MIGRATION_SHA256, 'Migration differs from the reviewed bytes.')
    tree = ast.parse(data)
    require(all(isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef)) for node in tree.body)
            and [node.name for node in tree.body if isinstance(node, ast.ClassDef)] == ['Migration'],
            'Migration module contains statements beyond imports and the Migration class.')
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assigns = {node.targets[0].id: node.value for node in klass.body if isinstance(node, ast.Assign)}
    require(list(assigns) == ['dependencies', 'operations'] and len(klass.body) == 2, 'Migration declares unexpected attributes.')
    require(ast.literal_eval(assigns['dependencies']) == [('core', PREVIOUS_MIGRATION)], 'Migration must depend on core 0012 only.')
    found = []
    for call in assigns['operations'].elts:
        require(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                and call.func.value.id == 'migrations', 'Migration operation is not a django migrations call.')
        keywords = {k.arg: k.value for k in call.keywords}
        if 'constraint' in keywords:  # AddConstraint names its constraint inside the constraint constructor
            inner = {k.arg: k.value for k in keywords['constraint'].keywords}
            name = ast.literal_eval(inner['name'])
        else:
            name = ast.literal_eval(keywords['name'])
        found.append((call.func.attr, ast.literal_eval(keywords['model_name']), name))
    require(found == OPERATIONS, 'Migration operations differ from the reviewed list.')


def schema():
    sql = """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') FROM
      (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,numeric_precision,numeric_scale
       FROM information_schema.columns WHERE table_schema='public') c"""
    return json.loads(output(PSQL + [sql]))


def tables():
    names = output(PSQL + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"]).splitlines()
    require(all(re.fullmatch('[a-z_][a-z_0-9]*', name) for name in names), 'Unexpected table name.')
    return names


def fingerprints(names, *, comparable):
    """Row fingerprints per table. comparable=True drops exactly what the migration adds (its history row and the new column)
    so the result can be compared with the fingerprints taken before it."""
    rows = {}
    for table in names:
        value = '(to_jsonb(t))'
        where = ''
        if comparable and table == 'core_costreconciliation':
            value = "(to_jsonb(t) - 'over_limit_delta')"
        if comparable and table == 'django_migrations':
            where = " WHERE NOT (app='core' AND name='" + MIGRATION + "')"
        data = subprocess.check_output(PSQL + [f'COPY (SELECT {value}::text AS value FROM "{table}" t{where} ORDER BY value) TO STDOUT'], timeout=600)
        rows[table] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return rows


def constraints():
    sql = """SELECT coalesce(jsonb_agg(jsonb_build_array(c.conrelid::regclass::text, c.conname, c.contype::text, c.confrelid::regclass::text,
                 pg_get_constraintdef(c.oid)) ORDER BY c.conrelid::regclass::text, c.conname),'[]')
             FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'"""
    return [tuple(row) for row in json.loads(output(PSQL + [sql]))]


def indexes():
    return [tuple(row) for row in json.loads(output(PSQL + [
        "SELECT coalesce(jsonb_agg(jsonb_build_array(tablename,indexname,indexdef) ORDER BY tablename,indexname),'[]') FROM pg_indexes WHERE schemaname='public'"]))]


def check_before(constraints_before):
    by_name = {(row[0], row[1]): row[4] for row in constraints_before}
    for key, definition in DEFINITIONS_BEFORE.items():
        require(by_name.get(key) == definition, 'Current constraint differs from the recorded running release: ' + '.'.join(key))
    require(('core_usage', 'usage_charge_at_most_multiplier') not in by_name, 'The relaxed usage check already exists; do not reapply.')


def check_catalog(constraints_before, constraints_after, indexes_before, indexes_after):
    changed = set(DEFINITIONS_BEFORE) | set(DEFINITIONS_AFTER)
    require([row for row in constraints_after if (row[0], row[1]) not in changed] == [row for row in constraints_before if (row[0], row[1]) not in changed],
            'Constraints outside the declared change differ.')
    after = {(row[0], row[1]): row for row in constraints_after if (row[0], row[1]) in changed}
    require(set(after) == set(DEFINITIONS_AFTER), 'The replaced constraints are not exactly the declared ones.')
    for key, definition in DEFINITIONS_AFTER.items():
        require(after[key][2] == 'c' and after[key][4] == definition, 'Constraint definition differs from the reviewed migration: ' + '.'.join(key))
    require([row for row in indexes_after if row[:2] != NEW_INDEX[:2]] == indexes_before, 'Indexes outside the declared one differ.')
    require([row for row in indexes_after if row[:2] == NEW_INDEX[:2]] == [NEW_INDEX], 'The new partial unique index differs from the reviewed migration.')


def check_schema(before, after):
    key = (NEW_COLUMN['table_name'], NEW_COLUMN['column_name'])
    require(not [row for row in before if (row['table_name'], row['column_name']) == key], 'The new column already exists; do not reapply.')
    added = [row for row in after if (row['table_name'], row['column_name']) == key]
    require(len(added) == 1 and {k: added[0][k] for k in NEW_COLUMN} == NEW_COLUMN, 'New column differs from the reviewed migration.')
    require([row for row in after if (row['table_name'], row['column_name']) != key] == before, 'Existing columns changed beyond the declared one.')


def retained_unchanged(before, now):
    """Reports retained before the act are unchanged; reports other sessions add meanwhile are allowed."""
    return all(now.get(name) == row for name, row in before.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    require(output(['git', 'branch', '--show-current']) == 'main'
            and output(['git', 'rev-parse', 'HEAD']) == BASELINE
            and output(['git', 'rev-parse', 'origin/main']) == args.target, 'Unexpected source release.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target])
    changed = set(output(['git', 'diff', '--name-only', BASELINE, args.target]).splitlines())
    require(changed <= ALLOWED and MIGRATION_PATH in changed and 'rebuild/core/audio.py' in changed,
            'Target changes paths outside the declared set: ' + ', '.join(sorted(changed - ALLOWED)))
    require(output(['git', 'diff', '--name-only', BASELINE, args.target, '--', 'rebuild/core/migrations']) == MIGRATION_PATH,
            'Exactly one new migration is declared.')
    validate_migration(subprocess.check_output(['git', 'show', args.target + ':' + MIGRATION_PATH]))
    require(subprocess.check_output(['git', 'show', args.target + ':' + SELF]) == (HERE.parent / SELF).read_bytes(),
            'Activator differs from the reviewed target.')
    require(output(['git', 'diff', '--name-only', BASELINE, args.target, '--', 'rebuild/deploy', 'rebuild/documents', 'rebuild/ops/private_storage.py',
                    'rebuild/ops/service_launcher.py', 'rebuild/requirements.txt']) == '',
            'Units, document sandbox, launcher, storage helpers and dependencies are outside this activation.')
    helpers = {'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py', 'previous': 'scripts/update-private-beta.py',
               'storage': 'rebuild/ops/private_storage.py', 'billing': 'scripts/activate-billing-policy.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(), 'Existing qualified helper changed.')
        modules[name] = load('recording_limit_' + name, relative)
    word, identity, previous, storage, billing = (modules[k] for k in ('word', 'identity', 'previous', 'storage', 'billing'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    health = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
    require(all(h.get('release') == BASELINE and h.get('data_mode') == 'synthetic-only' for h in health), 'The private services must run the baseline, synthetic-only.')
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('decrypted_files_written') == 0 and backup.get('restore_database_on_tmpfs_without_swap') is True,
            'The restore proof must come from the plaintext-free restore check.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unresolved jobs require inspection; never replay a provider request.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + PREVIOUS_MIGRATION + "'"]) == '1'
            and output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '0',
            'Expected fresh schema through core 0012 only.')
    names = tables()
    require(len(names) == TABLE_COUNT, 'Expected the current tables.')
    live_rows = sum(int(output(PSQL + [f'SELECT count(*) FROM "{t}"'])) for t in names)
    require(live_rows == backup.get('row_count'), 'The restore proof does not cover the current rows; take a fresh backup first.')
    # The migration's new checks must already hold on every existing row, or it would fail half-applied.
    require(output(PSQL + ["SELECT count(*) FROM core_usage WHERE NOT (charged_cost <= actual_cost * 1.5 AND charged_cost >= 0 AND actual_cost >= 0)"]) == '0'
            and output(PSQL + ["SELECT count(*) FROM core_platformcost WHERE kind NOT IN ('fixed_overhead','absorbed_failure','absorbed_over_limit')"]) == '0',
            'Existing rows would violate the new checks.')
    check_before(constraints())
    protected = previous.protected()
    retained = word.retained_reports()
    env_before = word.checked_file(APP / '.env', private=True)
    old_line = ('QUILLMD_RELEASE_SHA=' + BASELINE).encode()
    require(env_before.splitlines().count(old_line) == 1, 'Expected current private release setting.')
    env_after = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$', ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
    require(env_after != env_before and env_after.count(b'\n') == env_before.count(b'\n'), 'Release replacement did not apply cleanly.')
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper) and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned local helper required.')
    credentials = PRIVATE / 'db-role-secrets/fresh-db-roles.json'
    word.checked_file(credentials, private=True, limit=16384)
    for name in ('files', 'mail'):
        storage.inventory(STATE / name)
    for unit in UNITS:
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Installed service policy differs from reviewed source.')
    identity.verify_live(BASELINE, storage)
    result_path = Path(args.result)
    lock = PRIVATE / '.recording-limit-activation.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'recording-limit-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and not lock.exists() and not lock.is_symlink(), 'Choose unused private operation evidence; a prior lock needs inspection.')
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Recording-limit activation preflight passed: reviewed code, pinned migration 0013, restore proof, no pending jobs.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECL).name
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL])
            == subprocess.check_output(['git', 'show', commit + ':' + DECL]), 'Committed absolute declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target])
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid()})
    result = {'complete': False, 'previous_head': BASELINE, 'target': args.target, 'started_at': datetime.now(timezone.utc).isoformat(),
              'provider_calls': 0, 'migration': MIGRATION, 'backup_report': args.backup_report, 'backup_run_id': backup.get('backup_run_id'),
              'artifact': artifact, 'helper_image': helper, 'retained_reports_before': retained, 'stage': 'stopping_private_services'}
    try:
        word.systemd('stop', helper)
        for unit in UNITS:
            require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Service did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Job appeared before stop.')
        old_tables = tables()
        require(old_tables == names, 'Tables changed before the migration.')
        result['schema_before'] = schema()
        result['constraints_before'], result['indexes_before'] = constraints(), indexes()
        check_before(result['constraints_before'])
        result['database_before'] = fingerprints(old_tables, comparable=True)
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed.')
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        result['stage'] = 'applying_migration_0013'
        migrate = [str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'), '--credentials', str(credentials),
                   '--source', str(APP), '--role', 'migrator', '--', 'migrate', 'core', MIGRATION]
        plan = output(migrate + ['--plan'], cwd=APP)
        require(re.findall(r'^[a-zA-Z_][a-zA-Z_0-9]*\.[a-zA-Z_0-9]+$', plan, re.MULTILINE) == ['core.' + MIGRATION],
                'Migration plan contains an undeclared operation.')
        run(migrate + ['--noinput'], cwd=APP)
        result['schema_after'] = schema()
        check_schema(result['schema_before'], result['schema_after'])
        result['constraints_after'], result['indexes_after'] = constraints(), indexes()
        check_catalog(result['constraints_before'], result['constraints_after'], result['indexes_before'], result['indexes_after'])
        require(tables() == old_tables, 'The migration created or dropped a table.')
        require(fingerprints(old_tables, comparable=True) == result['database_before'], 'Existing rows changed during the migration.')
        require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '1', 'Exactly one schema-history row is required.')
        require(output(PSQL + ['SELECT count(*) FROM core_costreconciliation WHERE over_limit_delta <> 0']) == '0', 'The new column must start at zero.')
        result['database_after_all_rows'] = fingerprints(tables(), comparable=False)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_permissions'] = word.static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('recording-limit-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment differs from release-only update.')
        result['stage'] = 'starting_and_verifying'
        word.systemd('start', helper)
        for attempt in range(60):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
                if all(h.get('release') == args.target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Release health failed.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        require(fingerprints(old_tables, comparable=True) == result['database_before'], 'Startup changed existing application data.')
        require(fingerprints(tables(), comparable=False) == result['database_after_all_rows'], 'Startup changed rows or migration history.')
        require(schema() == result['schema_after'] and constraints() == result['constraints_after'] and indexes() == result['indexes_after'],
                'Schema, constraints or indexes changed after startup.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private bytes changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs) == artifact,
                'Word runtime changed.')
        require(retained_unchanged(retained, word.retained_reports()) and previous.protected() == protected, 'Retained or shared resources changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Unit policy changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_existing_rows_identical=True, only_declared_schema_delta=True,
                      all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after),
                      finished_at=datetime.now(timezone.utc).isoformat())
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400], finished_at=datetime.now(timezone.utc).isoformat())
        # Fail closed, as the billing activation does: services stay stopped until the recorded state is inspected.
        try:
            word.systemd('stop', helper)
            result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False
            result['stop_failure_kind'] = type(stop_error).__name__
        if not result_path.exists():
            identity.private_write(result_path, result)
        else:
            identity.private_write(result_path.with_name(result_path.stem + '-publication-failure.json'), result)
        raise
    print('Recording-limit activation completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
