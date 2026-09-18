#!/usr/bin/env python3
"""Cited private activation of date-of-service code selection: reviewed code plus migration 0014; default is read-only.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B <worktree>/scripts/activate-service-date.py \
        --target FULL_MERGE_SHA --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/service-date-activation-<label>.json [--execute]

The executing form runs only through scripts/run-ruled-mutation.sh with the committed declaration.

Migration 0014 adds one NOT NULL date column to core_encounter, backfills it from each row's own created_at in UTC (the migration spells UTC out rather than reading TIME_ZONE),
and adds one migration-history row. It creates no model, so Django's post-migrate bookkeeping has nothing to add. No
constraint and no index changes. Every other row, column, constraint and index must be identical, and every encounter
must end with a service date equal to the UTC date it was recorded on.
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
BASELINE = '475a59259203b04072e35cb9270f39a3b0005906'   # the tree's HEAD
# ⚠️ THE TREE'S HEAD AND THE RUNNING RELEASE ARE DIFFERENT FACTS, and the refused attempt proved it. It advanced
# permanent main to BASELINE and then died in the migration, BEFORE it reached the line that rewrites the release in
# the environment file. So the tree says 475a5925, the services' release line still says 5f673a3b, and they are
# stopped. An activator that assumes those three move together cannot describe the state it is asked to repair.
RUNNING_RELEASE = '5f673a3b2cc5c99d68f08f34fba43b4883403583'
DECL = 'docs/foundation/mutations/20260918-quillmd-service-date-retry.md'
SELF = 'scripts/activate-service-date.py'
PREVIOUS_MIGRATION = '0013_recording_charge_limit'
MIGRATION = '0014_encounter_service_date'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
MIGRATION_SHA256 = '2119a159682ea0da03523f80e6dd38f7ac0aab16733101ea6d2a60eb3deda01c'
TABLE_COUNT = 35
EXPECTED_ENCOUNTERS = 11
# Every tracked path that may differ between the running release and the target, so the activation judges the whole tree.
ALLOWED = {
    # main already carries the rest of this work: the first attempt advanced it before the migration refused.
    MIGRATION_PATH, 'rebuild/core/tests/test_code_release_dates.py', 'rebuild/ops/test_service_date_activation.py',
    'docs/rebuild/CHECKPOINT.md', 'docs/rebuild/terminology.md', SELF, DECL,
}
# The operations Django generated, in order. The file itself is pinned by SHA-256 above.
OPERATIONS = [('AddField', 'encounter', 'service_date'), ('RunPython', None, 'adopt_recorded_date'),
              ('AlterField', 'encounter', 'service_date')]
NEW_COLUMN = {'table_name': 'core_encounter', 'column_name': 'service_date', 'data_type': 'date', 'udt_name': 'date',
              'is_nullable': 'NO', 'column_default': None, 'numeric_precision': None, 'numeric_scale': None}
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


def operation_name(call):
    """(kind, model, name) for each migration operation, whether it names things by keyword or position."""
    keywords = {k.arg: k.value for k in call.keywords}
    kind = call.func.attr
    if kind == 'RunPython':
        forwards = keywords.get('code') or call.args[0]
        require(isinstance(forwards, ast.Name), 'RunPython must name a module-level function.')
        return kind, None, forwards.id
    model = ast.literal_eval(keywords['model_name'])
    return kind, model, ast.literal_eval(keywords['name'])


def validate_migration(source):
    """The reviewed migration exactly: pinned bytes, a docstring, the two backfill functions, three operations in order.

    ⚠️ The STRUCTURE is checked independently of the byte pin; what the backfill WRITES is not. A
    mutated body that writes today's date, or a fixed date, parses to the same three operations and
    is caught only by the pin and afterwards by check_backfill(). Do not read this function as
    proof that the values are right — that proof is check_backfill's.
    """
    data = source if isinstance(source, bytes) else source.encode()
    require(sha(data) == MIGRATION_SHA256, 'Migration differs from the reviewed bytes.')
    tree = ast.parse(data)
    kinds = [type(node) for node in tree.body]
    require(kinds[0] is ast.Expr and isinstance(tree.body[0].value, ast.Constant), 'Migration must open with its docstring.')
    require(all(isinstance(node, (ast.Expr, ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)) for node in tree.body),
            'Migration module contains statements beyond its docstring, imports, functions and the Migration class.')
    require([node.name for node in tree.body if isinstance(node, ast.FunctionDef)] == ['adopt_recorded_date', 'keep_the_dates'],
            'Migration declares unexpected module-level functions.')
    require([node.name for node in tree.body if isinstance(node, ast.ClassDef)] == ['Migration'], 'Expected exactly one Migration class.')
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assigns = {node.targets[0].id: node.value for node in klass.body if isinstance(node, ast.Assign)}
    require(list(assigns) == ['dependencies', 'operations'] and len(klass.body) == 2, 'Migration declares unexpected attributes.')
    require(ast.literal_eval(assigns['dependencies']) == [('core', PREVIOUS_MIGRATION)], 'Migration must depend on core 0013 only.')
    found = []
    for call in assigns['operations'].elts:
        require(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                and call.func.value.id == 'migrations', 'Migration operation is not a django migrations call.')
        found.append(operation_name(call))
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
    """Row fingerprints per table. comparable=True drops exactly what the migration adds (its history row and the new
    column) so the result can be compared with the fingerprints taken before it."""
    rows = {}
    for table in names:
        value = '(to_jsonb(t))'
        where = ''
        if comparable and table == NEW_COLUMN['table_name']:
            value = "(to_jsonb(t) - '" + NEW_COLUMN['column_name'] + "')"
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


def check_schema(before, after):
    key = (NEW_COLUMN['table_name'], NEW_COLUMN['column_name'])
    require(not [row for row in before if (row['table_name'], row['column_name']) == key], 'The new column already exists; do not reapply.')
    added = [row for row in after if (row['table_name'], row['column_name']) == key]
    require(len(added) == 1 and {k: added[0][k] for k in NEW_COLUMN} == NEW_COLUMN, 'New column differs from the reviewed migration.')
    require([row for row in after if (row['table_name'], row['column_name']) != key] == before, 'Existing columns changed beyond the declared one.')


def guard_enabled():
    """'O' = enabled. The migration suspends `encounter_scope` for the backfill statement; if it ever failed to restore
    it, every finalized clinical document on this system would silently become editable."""
    return output(PSQL + ["SELECT tgenabled FROM pg_trigger WHERE tgrelid='core_encounter'::regclass "
                          "AND tgname='encounter_scope'"])


def check_backfill():
    """Every encounter keeps the date it was recorded on, in UTC, and none is left without one."""
    require(output(PSQL + ['SELECT count(*) FROM core_encounter']) == str(EXPECTED_ENCOUNTERS), 'The encounter count changed.')
    require(output(PSQL + ['SELECT count(*) FROM core_encounter WHERE service_date IS NULL']) == '0', 'An encounter has no service date.')
    require(output(PSQL + ["SELECT count(*) FROM core_encounter WHERE service_date <> (created_at AT TIME ZONE 'UTC')::date"]) == '0',
            'A service date differs from the UTC date the encounter was recorded on.')
    require(guard_enabled() == 'O', 'The finalized-document guard was not restored after the backfill.')


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
    require(changed <= ALLOWED and MIGRATION_PATH in changed and DECL in changed,
            'Target changes paths outside the declared set: ' + ', '.join(sorted(changed - ALLOWED)))
    require(output(['git', 'diff', '--name-only', BASELINE, args.target, '--', 'rebuild/core/migrations']) == MIGRATION_PATH,
            'Exactly one new migration is declared.')
    validate_migration(subprocess.check_output(['git', 'show', args.target + ':' + MIGRATION_PATH]))
    require(subprocess.check_output(['git', 'show', args.target + ':' + SELF]) == (HERE.parent / SELF).read_bytes(),
            'Activator differs from the reviewed target.')
    require(output(['git', 'diff', '--name-only', BASELINE, args.target, '--', 'rebuild/deploy', 'rebuild/documents',
                    'rebuild/ops/private_storage.py', 'rebuild/ops/service_launcher.py', 'rebuild/requirements.txt']) == '',
            'Units, document sandbox, launcher, storage helpers and dependencies are outside this activation.')
    helpers = {'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
               'previous': 'scripts/update-private-beta.py', 'storage': 'rebuild/ops/private_storage.py',
               'billing': 'scripts/activate-billing-policy.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(),
                'Existing qualified helper changed.')
        modules[name] = load('service_date_' + name, relative)
    word, identity, previous, storage, billing = (modules[k] for k in ('word', 'identity', 'previous', 'storage', 'billing'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    # The services are expected to be DOWN here: the refused act stopped them and fails closed by design. If they are
    # up, they must be the release the environment file still names — never something unexplained.
    health = []
    for port in (9130, 9131):
        try:
            health.append(json.loads(output(['curl', '--fail', '--silent', '--max-time', '5',
                                             f'http://127.0.0.1:{port}/health/'])))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            health.append(None)
    require(all(answer is None or (answer.get('release') == RUNNING_RELEASE
                                   and answer.get('data_mode') == 'synthetic-only') for answer in health),
            'A private service is answering as something other than the recorded running release.')
    # Both up, or both down. `any(is None) or all(is not None)` — which is what this said first — is true for every
    # possible input, including the one it was meant to catch.
    require(all(answer is None for answer in health) or all(answer is not None for answer in health),
            'The two surfaces disagree about whether they are running.')
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('decrypted_files_written') == 0 and backup.get('restore_database_on_tmpfs_without_swap') is True,
            'The restore proof must come from the plaintext-free restore check.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unresolved jobs require inspection; never replay a provider request.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + PREVIOUS_MIGRATION + "'"]) == '1'
            and output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '0',
            'Expected fresh schema through core 0013 only.')
    names = tables()
    require(len(names) == TABLE_COUNT, 'Expected the current tables.')
    live_rows = sum(int(output(PSQL + [f'SELECT count(*) FROM "{t}"'])) for t in names)
    require(live_rows == backup.get('row_count'), 'The restore proof does not cover the current rows; take a fresh backup first.')
    # The column is NOT NULL with no default, so a row the backfill misses fails the ALTER and rolls
    # the whole migration back. `created_at` is auto_now_add and NOT NULL, so a check for nulls there
    # could not fail and is deliberately not written: a control that cannot fail proves nothing.
    require(output(PSQL + ['SELECT count(*) FROM core_encounter']) == str(EXPECTED_ENCOUNTERS), 'Unexpected encounter count.')
    protected = previous.protected()
    retained = word.retained_reports()
    env_before = word.checked_file(APP / '.env', private=True)
    old_line = ('QUILLMD_RELEASE_SHA=' + RUNNING_RELEASE).encode()
    require(env_before.splitlines().count(old_line) == 1, 'Expected current private release setting.')
    env_after = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$', ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
    require(env_after != env_before and env_after.count(b'\n') == env_before.count(b'\n'), 'Release replacement did not apply cleanly.')
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE) == word.expected_inputs(RUNNING_RELEASE),
            'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json',
                                    billing.PIN, inputs)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper) and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned local helper required.')
    credentials = PRIVATE / 'db-role-secrets/fresh-db-roles.json'
    word.checked_file(credentials, private=True, limit=16384)
    for name in ('files', 'mail'):
        storage.inventory(STATE / name)
    for unit in UNITS:
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                'Installed service policy differs from reviewed source.')
    if all(answer is not None for answer in health):
        identity.verify_live(RUNNING_RELEASE, storage)
    result_path = Path(args.result)
    lock = PRIVATE / '.service-date-activation.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'service-date-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and not lock.exists() and not lock.is_symlink(), 'Choose unused private operation evidence; a prior lock needs inspection.')
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Service-date activation preflight passed: reviewed code, pinned migration 0014, restore proof, no pending jobs.', flush=True)
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
    result = {'complete': False, 'previous_head': BASELINE, 'running_release_before': RUNNING_RELEASE,
              'services_up_before': [answer is not None for answer in health], 'target': args.target,
              'started_at': datetime.now(timezone.utc).isoformat(), 'provider_calls': 0, 'migration': MIGRATION,
              'backup_report': args.backup_report, 'backup_run_id': backup.get('backup_run_id'), 'artifact': artifact,
              'helper_image': helper, 'retained_reports_before': retained, 'stage': 'stopping_private_services'}
    try:
        word.systemd('stop', helper)   # idempotent: they are already stopped after the refused act
        for unit in UNITS:
            require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Service did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
                'Job appeared before stop.')
        old_tables = tables()
        require(old_tables == names, 'Tables changed before the migration.')
        result['guard_before'] = guard_enabled()
        require(result['guard_before'] == 'O', 'The finalized-document guard is not enabled before the act.')
        result['schema_before'] = schema()
        result['constraints_before'], result['indexes_before'] = constraints(), indexes()
        result['database_before'] = fingerprints(old_tables, comparable=True)
        result['encounter_recorded_dates'] = output(PSQL + [
            "SELECT string_agg(d||'='||n,',' ORDER BY d) FROM (SELECT (created_at AT TIME ZONE 'UTC')::date::text d, count(*)::text n "
            "FROM core_encounter GROUP BY 1) s"])
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed.')
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        result['stage'] = 'applying_migration_0014'
        migrate = [str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'), '--credentials', str(credentials),
                   '--source', str(APP), '--role', 'migrator', '--', 'migrate', 'core', MIGRATION]
        plan = output(migrate + ['--plan'], cwd=APP)
        require(re.findall(r'^[a-zA-Z_][a-zA-Z_0-9]*\.[a-zA-Z_0-9]+$', plan, re.MULTILINE) == ['core.' + MIGRATION],
                'Migration plan contains an undeclared operation.')
        run(migrate + ['--noinput'], cwd=APP)
        result['schema_after'] = schema()
        check_schema(result['schema_before'], result['schema_after'])
        result['constraints_after'], result['indexes_after'] = constraints(), indexes()
        require(result['constraints_after'] == result['constraints_before'], 'Constraints changed; this migration declares none.')
        require(result['indexes_after'] == result['indexes_before'], 'Indexes changed; this migration declares none.')
        require(tables() == old_tables, 'The migration created or dropped a table.')
        require(fingerprints(old_tables, comparable=True) == result['database_before'],
                'Existing rows changed during the migration, beyond the new column.')
        require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '1',
                'Exactly one schema-history row is required.')
        check_backfill()
        result['guard_after'] = guard_enabled()
        require(result['guard_after'] == result['guard_before'], 'The finalized-document guard changed state.')
        result['service_dates'] = output(PSQL + [
            "SELECT string_agg(d||'='||n,',' ORDER BY d) FROM (SELECT service_date::text d, count(*)::text n "
            "FROM core_encounter GROUP BY 1) s"])
        require(result['service_dates'] == result['encounter_recorded_dates'],
                'The backfilled service dates differ from the dates the encounters were recorded on.')
        result['database_after_all_rows'] = fingerprints(tables(), comparable=False)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_permissions'] = word.static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('service-date-env-' + args.target + '.pending')
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
        require(fingerprints(tables(), comparable=False) == result['database_after_all_rows'],
                'Startup changed rows or migration history.')
        require(schema() == result['schema_after'] and constraints() == result['constraints_after'] and indexes() == result['indexes_after'],
                'Schema, constraints or indexes changed after startup.')
        check_backfill()
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private bytes changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json',
                                     billing.PIN, inputs) == artifact, 'Word runtime changed.')
        require(retained_unchanged(retained, word.retained_reports()) and previous.protected() == protected,
                'Retained or shared resources changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Unit policy changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_existing_rows_identical=True,
                      only_declared_schema_delta=True, all_private_files_and_mail_identical=True,
                      every_encounter_kept_its_recorded_date=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after),
                      finished_at=datetime.now(timezone.utc).isoformat())
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400],
                      finished_at=datetime.now(timezone.utc).isoformat())
        # Fail closed, as the billing and recording-limit activations do: services stay stopped until the recorded state is inspected.
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
    print('Service-date activation completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
