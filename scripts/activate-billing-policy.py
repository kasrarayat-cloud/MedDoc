#!/usr/bin/env python3
"""Cited private billing-policy activation: reviewed code plus exactly two new tables; default is read-only preflight.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B scripts/activate-billing-policy.py \
        --target FULL_MERGE_SHA --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/billing-policy-activation-<label>.json [--execute]

The executing form runs only through scripts/run-ruled-mutation.sh with the committed declaration.
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
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
BASELINE = '8f8a6763b80d345e432074df64b907c2db50be2a'
SDK_RELEASE = '429283dfb71aa389bccef48976ee0dce2936e0bc'
PIN = '2a2ab5e1ba63e041dfd087e7f2c205999ccf8ff6bc41f9409cfd1d99e4537680'
DECL = 'docs/foundation/mutations/20260917-quillmd-billing-policy.md'
MIGRATION = '0012_billing_policy'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
BACKUP_RUN = '20260917T234313Z-56be2efa'
NEW_TABLES = {
    'core_costreconciliation': {'id', 'created_at', 'reconciled_cost', 'provider_credit_applied', 'discount_applied',
                                'evidence_reference', 'evidence_sha256', 'note', 'charge_delta', 'ledger_status',
                                'recorded_by_id', 'usage_id'},
    'core_platformcost': {'id', 'created_at', 'kind', 'amount', 'description', 'period_start', 'period_end',
                          'evidence_reference', 'job_id', 'recorded_by_id'},
}
# Every tracked path that may differ between the running release and the target. The docs and runner
# pull requests that landed on main between them are named here so the deploy judges the whole tree.
ALLOWED = {
    # PR #1186 — fresh live Word run record, acceptance checklist, release requirements
    'docs/rebuild/CHECKPOINT.md', 'docs/rebuild/owner-actions.md', 'docs/rebuild/patient-data-release-requirements.md',
    'docs/rebuild/pentest-scope.md', 'docs/rebuild/word-acceptance-checklist.md', 'rebuild/wm-live-fresh.mjs',
    'scripts/ops/reviewer-tunnel-access.sh',
    # PR #1187 — credential-gated external verification runners (scripts and a runbook only)
    'docs/rebuild/external-verification-runbook.md', 'rebuild/email-delivery-verify.py', 'rebuild/stripe-sandbox-verify.mjs',
    # billing policy
    'docs/rebuild/cost-definition.md', 'rebuild/core/billing.py', 'rebuild/core/forms.py', 'rebuild/core/generation.py',
    'rebuild/core/jobs.py', 'rebuild/core/management/commands/audit_billing.py', MIGRATION_PATH, 'rebuild/core/models.py',
    'rebuild/core/tests/test_billing_policy.py', 'rebuild/core/views.py', 'rebuild/quillmd/urls.py',
    'rebuild/templates/admin_dashboard.html', 'rebuild/templates/base.html', 'rebuild/templates/billing.html',
    'rebuild/ops/test_billing_activation.py', 'scripts/activate-billing-policy.py', DECL,
}
UNITS = ['quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker')]
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


# Exactly the constructs Django's writer emits for these two models: no other callable is reachable.
ALLOWED_CALLS = {('migrations', 'CreateModel'), ('models', 'UUIDField'), ('models', 'DateTimeField'), ('models', 'DecimalField'),
                 ('models', 'CharField'), ('models', 'DateField'), ('models', 'ForeignKey'), ('models', 'OneToOneField'),
                 ('models', 'CheckConstraint'), ('models', 'UniqueConstraint'), ('models', 'Q')}
ALLOWED_CHAINS = {('django', 'db', 'models', 'deletion', 'PROTECT'), ('uuid', 'uuid4'), ('settings', 'AUTH_USER_MODEL')}


def attribute_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    require(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load), 'Migration attribute chain must start at an imported name.')
    return (node.id, *reversed(parts))


def check_expression(node):
    """Literal data, the exact reference chains and the exact field/constraint constructors the generated migration uses; nothing else."""
    if isinstance(node, ast.Constant):
        require(node.value is None or isinstance(node.value, (str, int, bool)), 'Migration literal of an unexpected type.')
    elif isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            check_expression(element)
    elif isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            require(isinstance(key, ast.Constant) and isinstance(key.value, str), 'Migration dict keys must be string literals.')
            check_expression(value)
    elif isinstance(node, ast.Call):
        require(not node.args or all(isinstance(argument, (ast.Constant, ast.List, ast.Tuple)) for argument in node.args), 'Migration positional arguments must be literals.')
        chain = attribute_chain(node.func)
        require(chain in ALLOWED_CALLS, 'Migration calls a constructor outside the generated form: ' + '.'.join(chain))
        for argument in node.args:
            check_expression(argument)
        for keyword in node.keywords:
            require(keyword.arg is not None and keyword.arg.isidentifier(), 'Migration keyword splat is not permitted.')
            check_expression(keyword.value)
    elif isinstance(node, (ast.Attribute, ast.Name)):
        require(attribute_chain(node) in ALLOWED_CHAINS, 'Migration references a name outside the generated form.')
    else:
        require(False, 'Migration expression uses a construct outside the generated form: ' + type(node).__name__)


def validate_migration(source):
    """Exactly two CreateModel operations for the declared tables, depending on core0011; no other code can run on import."""
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    require(len(classes) == 1 and classes[0].name == 'Migration'
            and all(isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef)) for node in tree.body),
            'Migration module contains statements beyond imports and the Migration class.')
    # Pin the names, not just the identifiers: 'migrations' and 'models' must be django.db's, with no aliases.
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend((alias.name, None, alias.asname) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.extend((node.module, alias.name, alias.asname) for alias in node.names)
    require(all(asname is None for _, _, asname in imports) and set(imports) == {
        ('django.db.models.deletion', None, None), ('uuid', None, None), ('django.conf', 'settings', None),
        ('django.db', 'migrations', None), ('django.db', 'models', None)}, 'Migration imports differ from the reviewed generated form.')
    klass = classes[0]
    require(not klass.decorator_list and not klass.keywords and len(klass.bases) == 1 and isinstance(klass.bases[0], ast.Attribute)
            and isinstance(klass.bases[0].value, ast.Name) and klass.bases[0].value.id == 'migrations'
            and klass.bases[0].attr == 'Migration', 'Migration class must be an undecorated subclass of django.db.migrations.Migration.')
    require(len(klass.body) == 2 and all(isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                                         for node in klass.body), 'Migration class body must be exactly the two generated assignments.')
    assigns = {node.targets[0].id: node.value for node in klass.body}
    require(list(assigns) == ['dependencies', 'operations'], 'Migration declares unexpected attributes.')
    require(ast.literal_eval(assigns['dependencies']) == [('core', '0011_template_clinical_review')],
            'Migration must depend on core0011 only.')
    operations = assigns['operations']
    check_expression(operations)
    require(isinstance(operations, ast.List) and len(operations.elts) == 2, 'Exactly two migration operations are declared.')
    names = []
    for call in operations.elts:
        require(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == 'migrations'
                and call.func.attr == 'CreateModel' and not call.args, 'Only CreateModel operations are permitted.')
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        require(set(keywords) == {'name', 'fields', 'options'}, 'CreateModel carries unexpected arguments.')
        names.append(ast.literal_eval(keywords['name']))
        for source_node in ast.walk(call):
            require(not (isinstance(source_node, ast.Call) and isinstance(source_node.func, ast.Attribute)
                         and source_node.func.attr in ('RunSQL', 'RunPython', 'AlterField', 'RemoveField', 'DeleteModel',
                                                       'AddField', 'RenameModel', 'RenameField', 'AlterModelTable', 'SeparateDatabaseAndState')),
                    'Migration must not touch existing tables.')
    require(names == ['CostReconciliation', 'PlatformCost'], 'Migration creates unexpected models.')


def schema():
    sql = """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') FROM
      (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default
       FROM information_schema.columns WHERE table_schema='public') c"""
    return json.loads(output(PSQL + [sql]))


def tables():
    names = output(PSQL + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"]).splitlines()
    require(all(re.fullmatch('[a-z_][a-z_0-9]*', name) for name in names), 'Unexpected table name.')
    return names


def fingerprints(names, *, exclude_new_migration):
    rows = {}
    for table in names:
        where = (" WHERE NOT (app='core' AND name='" + MIGRATION + "')") if exclude_new_migration and table == 'django_migrations' else ''
        data = subprocess.check_output(PSQL + [f'COPY (SELECT (to_jsonb(t))::text AS value FROM "{table}" t{where} ORDER BY value) TO STDOUT'])
        rows[table] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return rows


def check_schema(before, after):
    old_tables = {row['table_name'] for row in before}
    require(not old_tables & set(NEW_TABLES), 'Declared tables already exist; do not reapply this activation.')
    require([row for row in after if row['table_name'] not in NEW_TABLES] == before,
            'Existing columns changed beyond the two declared new tables.')
    for table, columns in NEW_TABLES.items():
        require({row['column_name'] for row in after if row['table_name'] == table} == columns,
                'New table columns differ from the reviewed migration: ' + table)
    require({row['table_name'] for row in after} - old_tables == set(NEW_TABLES), 'Unexpected new table.')


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
    require(changed <= ALLOWED and MIGRATION_PATH in changed and 'rebuild/core/billing.py' in changed,
            'Target changes paths outside the declared billing-policy, docs and runner set: ' + ', '.join(sorted(changed - ALLOWED)))
    require(output(['git', 'diff', '--name-only', BASELINE, args.target, '--', 'rebuild/core/migrations']) == MIGRATION_PATH,
            'Exactly one new migration is declared.')
    validate_migration(subprocess.check_output(['git', 'show', args.target + ':' + MIGRATION_PATH]))
    require(subprocess.check_output(['git', 'show', args.target + ':scripts/activate-billing-policy.py'])
            == Path(__file__).read_bytes(), 'Activator differs from the reviewed target.')
    require(output(['git', 'diff', '--name-only', BASELINE, args.target, '--', 'rebuild/deploy', 'rebuild/documents', 'rebuild/ops/private_storage.py']) == '',
            'Units, document sandbox and storage helpers are outside this activation.')
    helpers = {'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
               'previous': 'scripts/update-private-beta.py', 'storage': 'rebuild/ops/private_storage.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative])
                == (ROOT / relative).read_bytes(), 'Existing qualified helper changed.')
        modules[name] = load('billing_activation_' + name, relative)
    word, identity, previous, storage = (modules[k] for k in ('word', 'identity', 'previous', 'storage'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('backup_run_id') == BACKUP_RUN, 'Use the restored post-fresh-run snapshot.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unresolved jobs require inspection; never replay a provider request.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='0011_template_clinical_review'"]) == '1'
            and output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '0',
            'Expected fresh schema through core0011 only.')
    require(len(tables()) == 33 and not set(tables()) & set(NEW_TABLES), 'Expected all33 current tables and no declared table yet.')
    protected = previous.protected()
    retained = word.retained_reports()
    env_before = word.checked_file(APP / '.env', private=True)
    old_line = ('QUILLMD_RELEASE_SHA=' + BASELINE).encode()
    require(env_before.splitlines().count(old_line) == 1, 'Expected current private release setting.')
    env_after = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$', ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
    require(env_after != env_before and env_after.count(b'\n') == env_before.count(b'\n'), 'Release replacement did not apply cleanly.')
    installed = APP / '.word-sdk' / SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', PIN, inputs)
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
    lock = PRIVATE / '.billing-policy-activation.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'billing-policy-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and not lock.exists() and not lock.is_symlink(), 'Choose unused private operation evidence; a prior lock needs inspection.')
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Billing-policy activation preflight passed: reviewed code, one validated two-table migration, restore proof, no pending jobs.', flush=True)
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
              'provider_calls': 0, 'migration': MIGRATION, 'backup_report': args.backup_report, 'artifact': artifact,
              'helper_image': helper, 'retained_reports_before': retained, 'stage': 'stopping_private_services'}
    try:
        word.systemd('stop', helper)
        for unit in UNITS:
            require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Service did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Job appeared before stop.')
        old_tables = tables()
        require(len(old_tables) == 33, 'Expected all33 current tables.')
        result['schema_before'] = schema()
        result['database_before'] = fingerprints(old_tables, exclude_new_migration=True)
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed.')
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        result['stage'] = 'applying_two_new_tables'
        migrate = [str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'), '--credentials', str(credentials),
                   '--source', str(APP), '--role', 'migrator', '--', 'migrate', 'core', MIGRATION]
        plan = output(migrate + ['--plan'], cwd=APP)
        require(re.findall(r'^[a-zA-Z_][a-zA-Z_0-9]*\.[a-zA-Z_0-9]+$', plan, re.MULTILINE) == ['core.' + MIGRATION],
                'Migration plan contains an undeclared operation.')
        run(migrate + ['--noinput'], cwd=APP)
        result['schema_after'] = schema()
        check_schema(result['schema_before'], result['schema_after'])
        require(fingerprints(old_tables, exclude_new_migration=True) == result['database_before'], 'Existing rows changed during schema addition.')
        require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '1', 'Exactly one schema-history row is required.')
        for table in NEW_TABLES:
            require(output(PSQL + [f'SELECT count(*) FROM {table}']) == '0', 'New table must be empty at activation.')
        result['database_after_all_rows'] = fingerprints(tables(), exclude_new_migration=False)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_permissions'] = word.static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('billing-policy-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment differs from release-only update.')
        result['stage'] = 'starting_and_verifying'
        word.systemd('start', helper)
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
                if all(h.get('release') == args.target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Release health failed.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        require(fingerprints(old_tables, exclude_new_migration=True) == result['database_before'], 'Startup changed existing application data.')
        require(fingerprints(tables(), exclude_new_migration=False) == result['database_after_all_rows'], 'Startup changed new tables or migration history.')
        require(schema() == result['schema_after'], 'Schema changed after startup.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private bytes changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', PIN, inputs) == artifact, 'Word runtime changed.')
        require(word.retained_reports() == retained and previous.protected() == protected, 'Retained or shared resources changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Unit policy changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_existing_rows_and_columns_identical=True,
                      exactly_two_empty_new_tables=True, all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after))
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
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
    print('Billing-policy activation completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
