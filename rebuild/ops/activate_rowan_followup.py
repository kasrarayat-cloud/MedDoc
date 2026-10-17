"""Inert, declared Rowan recovery installation; never runs recovery/provider work.

The first Rowan installer is a consumed activation. This controller reuses only
its reviewed publication/snapshot primitives, with a new exact release boundary.
It admits one guard migration and one origin-job setting, not another activation.
"""
import argparse
import ast
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

from dotenv import dotenv_values
from . import activate_rowan_corti as prior

BASE = 'bb8a185dc76cec8bff35820155e9416b24c087ea'
SOURCE = Path(__file__).resolve().parents[2]
MIGRATION = '0030_retained_semantic_revalidation'
FUNCTION = 'quillmd_ai_stage_guard'
ORIGIN = '1e56aac0-69ae-4927-bd75-168beb8b4a95'
ENV_KEY = 'QUILLMD_SEMANTIC_REVALIDATION_ORIGIN_JOB_IDS'
FORMAT = 'quillmd-rowan-recovery-native-install-v1'
require, Refusal = prior.require, prior.Refusal


@contextmanager
def bound_primitives(static):
    """Bind pure historical primitives without invoking their consumed lifecycle."""
    saved = {k: getattr(prior, k) for k in ('BASE', 'SOURCE', 'STATIC')}
    prior.BASE, prior.SOURCE, prior.STATIC = BASE, SOURCE, frozenset(static)
    try:
        yield prior
    finally:
        for name, value in saved.items():
            setattr(prior, name, value)


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'source_sha256',
        'source_worktree', 'evidence_directory', 'environment_before_sha256', 'environment',
        'guard_before_md5', 'guard_after_md5', 'static'}, 'closed_followup_plan')
    require(plan['format'] == FORMAT and plan['base'] == BASE
            and re.fullmatch('[a-f0-9]{40}', plan['candidate']) and plan['candidate'] != BASE, 'exact_followup_revision')
    require(plan['environment'] == {ENV_KEY: ORIGIN}, 'one_exact_recovery_origin')
    require(all(re.fullmatch('[a-f0-9]{32}', plan[k]) for k in ('guard_before_md5', 'guard_after_md5'))
            and plan['guard_before_md5'] != plan['guard_after_md5'], 'exact_guard_body_delta')
    require(re.fullmatch('[a-f0-9]{64}', plan['environment_before_sha256']), 'environment_pin')
    paths = plan['source_sha256']
    require(type(paths) is dict and 0 < len(paths) <= 100, 'finite_source_manifest')
    for name, digest in paths.items():
        path = PurePosixPath(name)
        require(name == str(path) and not path.is_absolute() and len(name) <= 240
                and not any(p.startswith('.') or p in {'node_modules', 'uploads', 'backups'} for p in path.parts)
                and name.startswith(('rebuild/', 'docs/', 'scripts/'))
                and (path.suffix in {'.py', '.html', '.md', '.json', '.js', '.css', '.sh', '.cjs'}
                     or name == 'rebuild/core/tests/fixtures/rowan/source.txt')
                and re.fullmatch('[a-f0-9]{64}', digest), 'public_exact_source_path')
        if '/migrations/' in name:
            require(name == 'rebuild/core/migrations/' + MIGRATION + '.py', 'one_exact_migration')
    require('rebuild/core/migrations/' + MIGRATION + '.py' in paths, 'migration_bound')
    static = plan['static']
    require(type(static) is list and static == sorted(set(static))
            and set(static) <= {'encounter-live.js', 'coding.js', 'coding.css'}, 'bounded_public_static')
    require(sorted('rebuild/static/' + n for n in static)
            == sorted(n for n in paths if n.startswith('rebuild/static/')), 'exact_changed_static')
    out = Path(plan['evidence_directory']); source = Path(plan['source_worktree'])
    require(out.is_absolute() and out.parent.resolve() == out.parent and not out.exists()
            and out.parent.stat().st_uid == os.getuid() and stat.S_IMODE(out.parent.stat().st_mode) == 0o700,
            'exclusive_private_output')
    require(source.is_absolute() and source.resolve() == source and source == SOURCE, 'exact_operator_worktree')


def render_environment(original, revision):
    values = dotenv_values(stream=io.StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == BASE and values.get('QUILLMD_CODING_PROVIDER', 'existing') == 'existing'
            and values.get('QUILLMD_CORTI_CODING_MODE') == 'live'
            and values.get('QUILLMD_CORTI_CREDENTIALS_FILE') == str(prior.CREDENTIAL_TARGET), 'installed_activation_required')
    require(ENV_KEY not in values, 'recovery_admission_not_reused')
    replacements = {'QUILLMD_RELEASE_SHA': revision, ENV_KEY: ORIGIN}
    lines, found = [], set()
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', line)
        key = match[1].decode() if match else ''
        if key in replacements:
            require(key not in found, 'duplicate_environment_key'); found.add(key)
            lines.append((key + '="' + replacements[key] + '"\n').encode())
        else:
            lines.append(line)
    require('QUILLMD_RELEASE_SHA' in found, 'release_assignment_found')
    if lines and not lines[-1].endswith(b'\n'):
        lines.append(b'\n')
    lines.append((ENV_KEY + '="' + ORIGIN + '"\n').encode())
    result = b''.join(lines)
    after = dotenv_values(stream=io.StringIO(result.decode()), interpolate=False)
    require(after == {**values, **replacements}, 'only_release_and_recovery_setting_changed')
    return result


def snapshot(original):
    """Keep exact old migration rows too, including their timestamps and IDs."""
    import psycopg
    result = prior.database_snapshot(original)
    with psycopg.connect(**prior.database_options(original)) as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        connection.execute("SET LOCAL statement_timeout='10s'")
        result['migration_ledger'] = [[str(v) for v in row] for row in connection.execute(
            'SELECT id,app,name,applied FROM django_migrations ORDER BY id')]
    return result


def validate_migration_source(plan, root):
    """Admit only two literal SQL strings and one exact RunSQL operation.

    The catalog snapshot is not a universal DDL detector. This source boundary
    prevents an unwatched ALTER, RunPython, import or extra SQL statement from
    entering the migration at all. A trigger body is installed, never invoked.
    """
    relative = 'rebuild/core/migrations/' + MIGRATION + '.py'
    raw = (root / relative).read_bytes()
    require(prior.sha(raw) == plan['source_sha256'].get(relative), 'migration_source_pin')
    tree = ast.parse(raw)
    nodes = list(tree.body)
    if nodes and isinstance(nodes[0], ast.Expr) and isinstance(nodes[0].value, ast.Constant) \
            and isinstance(nodes[0].value.value, str):
        nodes.pop(0)
    require(len(nodes) == 4 and isinstance(nodes[1], ast.Assign) and isinstance(nodes[2], ast.Assign),
            'literal_migration_module')
    for node, name in zip(nodes[1:3], ('REVALIDATION_SQL', 'REVALIDATION_REVERSE')):
        require(len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str), 'literal_migration_sql')
        sql = node.value.value
        require(sql.count('$$') == 2 and re.fullmatch(r'\s*CREATE OR REPLACE FUNCTION '
            r'quillmd_ai_stage_guard\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$.*\$\$;\s*', sql, re.S),
            'sole_guard_function_statement')
        node.value = ast.Constant(value='SQL')
    expected = ast.parse("""from django.db import migrations
REVALIDATION_SQL = 'SQL'
REVALIDATION_REVERSE = 'SQL'
class Migration(migrations.Migration):
    dependencies = [('core', '0029_bounded_output_decision')]
    operations = [migrations.RunSQL(REVALIDATION_SQL, REVALIDATION_REVERSE)]
""")
    require(ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)
            == ast.dump(expected, include_attributes=False), 'sole_runsql_migration_shape')
    return dict(source_sha256=prior.sha(raw), operation='one_literal_RunSQL', function=FUNCTION,
                table_ddl=False, row_dml=False, runpython=False)


def verify_migration(before, after, plan):
    require(set(before) == set(after), 'same_snapshot_scope')
    require(set(after['tables']) == set(before['tables']), 'no_new_or_removed_tables')
    require(all(after['tables'][n] == row for n, row in before['tables'].items() if n != 'django_migrations'),
            'all_existing_database_rows_preserved')
    require(after['tables']['django_migrations'][0] == before['tables']['django_migrations'][0] + 1
            and after['migration_ledger'][:-1] == before['migration_ledger']
            and after['migration_ledger'][-1][1:3] == ['core', MIGRATION]
            and sorted(after['migrations']) == sorted(before['migrations'] + [['core', MIGRATION]]), 'one_appended_migration_row')
    for name in ('schema', 'triggers', 'constraints', 'indexes', 'latest_enrolled_encounter'):
        require(after[name] == before[name], 'unchanged_' + name)
    old = [r for r in before['functions'] if r[:2] == [FUNCTION, '']]
    new = [r for r in after['functions'] if r[:2] == [FUNCTION, '']]
    require(len(old) == len(new) == 1 and old[0][2] == plan['guard_before_md5']
            and new[0] == [*old[0][:2], plan['guard_after_md5'], *old[0][3:]], 'exact_guard_replacement')
    require([r for r in after['functions'] if r[:2] != [FUNCTION, '']]
            == [r for r in before['functions'] if r[:2] != [FUNCTION, '']], 'other_functions_unchanged')
    require(set(after['sequences']) == set(before['sequences']), 'same_sequence_population')
    for name, value in before['sequences'].items():
        expected = [value[0] + (1 if value[1] else 0), True] if name == 'django_migrations_id_seq' else value
        require(after['sequences'][name] == expected, 'only_exact_migration_sequence_advance')
    require(after['pending'] == before['pending'] and not any(after['pending'].values()), 'no_provider_work_during_install')


def migrate(original):
    # Same owner-role transport, exact-one forward plan, and no post_migrate signals.
    code = prior.migration_source().replace(prior.MIGRATION, MIGRATION).replace(
        'rowan_additive_migration_committed', 'rowan_recovery_migration_committed')
    opts = prior.database_options(original, owner=True)
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'HOME', 'USER'}}
    env.update({k: v for k, v in dotenv_values(stream=io.StringIO(original.decode()), interpolate=False).items()
                if isinstance(v, str)})
    env.update(QUILLMD_ENV_MANAGED='1', QUILLMD_DB_USER=opts['user'], QUILLMD_DB_PASSWORD=opts['password'],
               PGOPTIONS=opts['options'], PYTHONDONTWRITEBYTECODE='1')
    raw = prior.command([str(prior.APP / '.venv/bin/python'), '-B', '-c', code], cwd=prior.APP, env=env, timeout=90)
    require(raw.strip() == b'rowan_recovery_migration_committed', 'migration_receipt')


def execute(plan, digest):
    validate_plan(plan)
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.is_file() and re.fullmatch('[a-f0-9]{40}', commit), 'ruled_declaration_required')
    text = declaration.read_bytes()
    require(all(x.encode() in text for x in (digest, plan['candidate'], FORMAT)), 'declaration_exact_plan')
    repo = Path(prior.command(['git', '-C', str(declaration.parent), 'rev-parse', '--show-toplevel']).decode().strip())
    require(prior.command(['git', '-C', str(repo), 'show', commit + ':' + declaration.relative_to(repo).as_posix()])
            == text, 'committed_declaration_bytes')
    original = prior.backup_restore.read_private(prior.APP / '.env', 65536)
    require(prior.sha(original) == plan['environment_before_sha256'], 'environment_before_pin')
    active = render_environment(original, plan['candidate'])
    guard = prior.source_guard(); prepared = prior.source_plan(plan, guard)
    migration_admission = validate_migration_source(plan, SOURCE)
    prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory']); out.mkdir(mode=0o700)
    prior.write_new(out / 'plan.json', plan)
    prior.write_new(out / 'migration-source-admission.json', migration_admission)
    cipher = prior.backup_restore.key_at(prior.legacy.KEY)
    prior.write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    prior.write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    primitives = prior.legacy.static_primitives(); primitives.static_delta = prior.static_delta
    if plan['static']:
        stage, static_before, staged = prior.stage_static(plan, out, primitives)
    else:
        static_before = primitives.static_inventory(prior.APP / 'staticfiles')
    host = prior.legacy.Host(prior.managed_helper)
    prior.activation_exclusion.bind_runtime(prior.APP / '.runtime')
    stopped = resumed = False
    stage_name = 'prepared'
    with prior.legacy.operation_locks(), prior.activation_exclusion.hold('rowan-recovery:' + plan['candidate'][:12], timeout=30):
        try:
            baseline = dict(configuration=host.configuration(), services=prior.foreign_services(), database=snapshot(original),
                files=prior.private_storage.inventory(Path('/var/lib/quillmd/files')))
            require(not any(baseline['database']['pending'].values()), 'pending_work_before_stop')
            require(['core', MIGRATION] not in baseline['database']['migrations'], 'migration_not_already_attempted')
            require([r for r in baseline['database']['functions'] if r[:2] == [FUNCTION, '']][0][2]
                    == plan['guard_before_md5'], 'original_guard_pin')
            prior.write_new(out / 'baseline.json', baseline)
            stage_name = 'stop_owned_services'; stopped = True
            for unit in prior.UNITS:
                host.service('stop', unit)
            require(all(host.state(u)['ActiveState'] == 'inactive' and host.state(u)['MainPID'] == '0'
                        for u in prior.UNITS), 'owned_units_drained')
            before = snapshot(original)
            require(before == baseline['database'], 'no_pre_stop_database_race')
            stage_name = 'source_publication'; prior.publish_source(plan, guard, prepared)
            stage_name = 'one_guard_migration'
            require(validate_migration_source(plan, prior.ROOT) == migration_admission, 'installed_migration_matches_admission')
            migrate(original)
            after = snapshot(original); verify_migration(before, after, plan)
            prior.write_new(out / 'migration-preservation.json', after)
            stage_name = 'static_publication'
            if plan['static']:
                static_after = primitives.install_static(prior.APP / 'staticfiles', stage, static_before, staged)
            else:
                static_after = primitives.static_inventory(prior.APP / 'staticfiles')
                require(static_after == static_before, 'static_bytes_unchanged')
            stage_name = 'environment_publication'
            require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = prior.APP / '.rowan-recovery-env-pending'
            prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
            require(snapshot(active) == after, 'database_preserved_until_resume')
            require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'], 'all_clinical_files_preserved')
            require(host.configuration() == baseline['configuration'] and prior.foreign_services() == baseline['services'],
                    'unrelated_configuration_services_preserved')
            prior.write_new(out / 'pre-resume-preservation.json', dict(old_rows_preserved=True, files_preserved=True,
                only_declared_guard_changed=True, static_inventory=static_after, provider_calls=0))
            stage_name = 'resume_owned_services'; resumed = True
            for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                host.service('start', unit)
            health = prior.await_health(plan['candidate'])
            require(all(host.state(u)['ActiveState'] == 'active' for u in prior.UNITS), 'owned_units_active')
            require(host.configuration() == baseline['configuration'] and prior.foreign_services() == baseline['services'],
                    'foreign_services_after_resume')
            result = dict(format=FORMAT, installed_revision=plan['candidate'], complete=True, health=health,
                migration=MIGRATION, provider_calls=0, clinician_decisions_created=0, recovery_executed=False,
                strict_preservation_ends_before_resume=True)
            prior.write_new(out / 'installation-complete.json', result)
            return result
        except BaseException as error:
            prior.write_new(out / 'failure.json', dict(format=FORMAT, complete=False, stage=stage_name,
                failure_type=type(error).__name__, reason=str(error) if isinstance(error, Refusal) else 'protected_operational_failure',
                stopped=stopped, resumed=resumed, provider_calls=0, automatic_retry=False))
            if stopped and not resumed and prior.git('rev-parse', 'HEAD').decode().strip() == BASE:
                for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                    host.service('start', unit)
                prior.write_new(out / 'original-release-resumed.json', {'release': BASE})
            raise Refusal('installation_failed_inspect_retained_evidence') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--plan'); parser.add_argument('--plan-sha256')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(dict(inert=True, database_queries=0, provider_calls=0, service_actions=0))); return
    os.umask(0o077); sys.dont_write_bytecode = True
    plan, digest = prior.private_json(Path(args.plan))
    require(digest == args.plan_sha256, 'private_plan_hash')
    validate_plan(plan)
    with bound_primitives(plan['static']):
        print(json.dumps(execute(plan, digest), sort_keys=True))


if __name__ == '__main__':
    main()
