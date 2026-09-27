#!/usr/bin/env python3
"""Inspect/apply the fresh PostgreSQL role policy; live apply requires the mutation gate."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

from psycopg import sql, Error as DatabaseError
try:
    from .backup_restore import inspect_container, private_dir, read_private, require, run, write_private, LABEL
except ImportError:
    from backup_restore import inspect_container, private_dir, read_private, require, run, write_private, LABEL

ROLES = {'owner': 'quillmd_owner', 'runtime': 'quillmd_runtime',
         'migrator': 'quillmd_migrator', 'backup': 'quillmd_backup'}
MARKER = 'QuillMD fresh role policy v1'


def statement(template, *identifiers):
    return sql.SQL(template).format(*[sql.Identifier(x) for x in identifiers]).as_string()


def execute_sql(container, database, user, body, password=None, expect_success=True):
    command = ['docker', 'exec', '-i']
    env = None
    if password is not None:
        command += ['-e', 'PGPASSWORD']
        env = dict(os.environ, PGPASSWORD=password)
    command += [container, 'psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-U', user, '-d', database]
    if password is not None:
        command += ['-h', '127.0.0.1']
    result = subprocess.run(command, input=body.encode(), capture_output=True, env=env)
    if expect_success:
        require(result.returncode == 0, 'Role SQL failed; raw SQL/passwords/results are not emitted.')
    return result


def query(container, database, user, body, password=None):
    wrapped = "SELECT COALESCE(json_agg(row_to_json(r)),'[]'::json) FROM (" + body + ') r;'
    return json.loads(execute_sql(container, database, user, wrapped, password).stdout)


def target(args):
    metadata = inspect_container(args.container)
    if args.container == 'quillmd-fresh-postgres':
        require(args.database == 'quillmd_fresh' and args.admin_user == 'quillmd_fresh', 'Live target identity mismatch.')
        require(args.expected_container_id == metadata['Id'], 'Pin the exact current live container ID.')
        require(metadata['HostConfig']['PortBindings'] ==
                {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]}, 'Live database exposure changed.')
    else:
        require(re.fullmatch(r'quillmd-restore-[a-f0-9]{16}', args.container)
                and args.database == 'quillmd_restore' and args.admin_user == 'restore_owner', 'Unowned restore target.')
        require(metadata['Config']['Labels'].get(LABEL) == args.container.removeprefix('quillmd-restore-')
                and metadata['HostConfig']['NetworkMode'] == 'none'
                and not metadata['HostConfig']['PortBindings'], 'Restore isolation/ownership mismatch.')
    require(metadata['State']['Running'], 'Target must be running.')
    state = query(args.container, args.database, args.admin_user,
                  'SELECT current_database() AS database,current_user AS role,rolsuper FROM pg_roles WHERE rolname=current_user')[0]
    require(state['database'] == args.database and state['role'] == args.admin_user and state['rolsuper'],
            'Verified maintenance connection is required and must remain available.')
    return metadata


def role_credentials(path, metadata, database, create=False):
    path = Path(path).absolute()
    if not path.exists() and create:
        private_dir(path.parent, create=True)
        payload = {'policy': MARKER, 'container_id': metadata['Id'], 'database': database,
                   'roles': {kind: {'name': name, 'password': secrets.token_urlsafe(48)}
                             for kind, name in ROLES.items() if kind != 'owner'}}
        write_private(path, json.dumps(payload, indent=2).encode() + b'\n')
    data = json.loads(read_private(path, 16384))
    require(data['policy'] == MARKER and data['container_id'] == metadata['Id'] and data['database'] == database,
            'Private credentials belong to a different target/policy.')
    require(set(data['roles']) == {'runtime', 'migrator', 'backup'}
            and all(row['name'] == ROLES[kind] and len(row['password']) >= 40
                    for kind, row in data['roles'].items()), 'Invalid private role credential shape.')
    return data


def inspect_policy(args):
    metadata = target(args)
    roles = query(args.container, args.database, args.admin_user, '''SELECT rolname,rolsuper,rolcreatedb,
        rolcreaterole,rolreplication,rolbypassrls,rolcanlogin FROM pg_roles
        WHERE rolname IN ('quillmd_fresh','restore_owner','quillmd_owner','quillmd_runtime','quillmd_migrator','quillmd_backup')
        ORDER BY rolname''')
    database = query(args.container, args.database, args.admin_user, '''SELECT datname,pg_get_userbyid(datdba) AS owner,
        has_database_privilege('public',oid,'CONNECT') AS public_connect FROM pg_database WHERE datname=current_database()''')[0]
    return {'container_id': metadata['Id'], 'database': database, 'roles': roles,
            'network': metadata['HostConfig']['NetworkMode'], 'ports': metadata['HostConfig']['PortBindings']}


def apply(args):
    metadata = target(args)
    if args.container == 'quillmd-fresh-postgres':
        require(os.environ.get('RULED_MUTATION_DECLARATION') and
                re.fullmatch('[a-f0-9]{40}', os.environ.get('RULED_MUTATION_DECL_COMMIT', '')),
                'Live role changes require a coordinated, committed mutation declaration.')
    before = inspect_policy(args)
    credentials = role_credentials(args.credentials, metadata, args.database, create=True)
    existing = query(args.container, args.database, args.admin_user, '''SELECT rolname,shobj_description(oid,'pg_authid') AS marker
        FROM pg_roles WHERE rolname IN ('quillmd_owner','quillmd_runtime','quillmd_migrator','quillmd_backup')''')
    require(all(row['marker'] == MARKER for row in existing), 'A role name already belongs to another policy; refuse.')
    present = {row['rolname'] for row in existing}
    commands = ['BEGIN;', "SET lock_timeout='5s';", "SET statement_timeout='30s';"]
    for kind, name in ROLES.items():
        if name not in present:
            commands.append(statement('CREATE ROLE {};', name))
        commands.append(statement('ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;', name))
        if kind == 'owner':
            commands.append(statement('ALTER ROLE {} NOLOGIN;', name))
        else:
            commands.append(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {};').format(
                sql.Identifier(name), sql.Literal(credentials['roles'][kind]['password'])).as_string())
        commands.append(sql.SQL('COMMENT ON ROLE {} IS {};').format(sql.Identifier(name), sql.Literal(MARKER)).as_string())
    commands += [statement('GRANT {} TO {} WITH INHERIT FALSE, SET TRUE;', ROLES['owner'], ROLES['migrator']),
                 statement('REVOKE {} FROM {},{};', ROLES['owner'], ROLES['runtime'], ROLES['backup']),
                 statement('ALTER DATABASE {} OWNER TO {};', args.database, ROLES['owner']),
                 statement('REVOKE ALL ON DATABASE {} FROM PUBLIC;', args.database)]
    for kind in ['runtime', 'migrator', 'backup']:
        commands.append(statement('GRANT CONNECT ON DATABASE {} TO {};', args.database, ROLES[kind]))
    commands += [statement('ALTER SCHEMA public OWNER TO {};', ROLES['owner']),
                 'REVOKE ALL ON SCHEMA public FROM PUBLIC;']
    for kind in ['runtime', 'migrator', 'backup']:
        commands.append(statement('GRANT USAGE ON SCHEMA public TO {};', ROLES[kind]))
    objects = query(args.container, args.database, args.admin_user, '''SELECT c.relname,c.relkind FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','S','v','m')
        ORDER BY CASE WHEN c.relkind='S' THEN 1 ELSE 0 END,c.relname''')
    for row in objects:
        kind = {'r': 'TABLE', 'S': 'SEQUENCE', 'v': 'VIEW', 'm': 'MATERIALIZED VIEW'}[row['relkind']]
        commands.append(statement(f'ALTER {kind} public.{{}} OWNER TO {{}};', row['relname'], ROLES['owner']))
    functions = query(args.container, args.database, args.admin_user, '''SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS args
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ''')
    for row in functions:
        require(row['proname'].startswith('quillmd_') and row['args'] == '', 'Unknown public function requires review.')
        commands.append(statement('ALTER FUNCTION public.{}() OWNER TO {};', row['proname'], ROLES['owner']))
    commands += ['REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;',
                 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;',
                 'REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;']
    commands += [statement('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {};', ROLES['runtime']),
                 statement('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {};', ROLES['runtime']),
                 statement('GRANT SELECT ON ALL TABLES IN SCHEMA public TO {};', ROLES['backup']),
                 statement('GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {};', ROLES['backup']),
                 statement('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {};', ROLES['owner'], ROLES['runtime']),
                 statement('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO {};', ROLES['owner'], ROLES['runtime']),
                 statement('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT ON TABLES TO {};', ROLES['owner'], ROLES['backup']),
                 statement('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT ON SEQUENCES TO {};', ROLES['owner'], ROLES['backup']),
                 statement('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;', ROLES['owner']),
                 'COMMIT;']
    execute_sql(args.container, args.database, args.admin_user, '\n'.join(commands))
    after = inspect_policy(args)  # Proves the bootstrap maintenance connection still works.
    require(after['database']['owner'] == ROLES['owner'] and not after['database']['public_connect'], 'Role policy did not apply.')
    evidence = {'applied_at_utc': datetime.now(timezone.utc).isoformat(), 'before': before, 'after': after,
                'maintenance_connection_preserved': True, 'live': args.container == 'quillmd-fresh-postgres'}
    output = Path(args.credentials).with_suffix('.applied.json')
    # Atomic evidence replacement supports an explicitly idempotent repeat.
    temp = output.with_name(output.name + '.' + secrets.token_hex(4))
    write_private(temp, json.dumps(evidence, indent=2).encode() + b'\n')
    os.replace(temp, output)
    print(json.dumps({'applied': True, 'container': args.container, 'database': args.database,
                      'runtime_superuser': False, 'owner_login': False, 'public_connect': False,
                      'maintenance_connection_preserved': True, 'evidence': str(output)}))


def verify(args):
    metadata = target(args)
    require(args.container != 'quillmd-fresh-postgres', 'Mutation proofs run only on isolated restoration.')
    credentials = role_credentials(args.credentials, metadata, args.database)
    checks = {}
    policy = inspect_policy(args)
    managed = [row for row in policy['roles'] if row['rolname'] in ROLES.values()]
    require(len(managed) == 4 and all(not row[flag] for row in managed
            for flag in ('rolsuper', 'rolcreatedb', 'rolcreaterole', 'rolreplication', 'rolbypassrls')),
            'A managed role retains a privileged flag.')
    require(next(row for row in managed if row['rolname'] == ROLES['owner'])['rolcanlogin'] is False
            and policy['database']['public_connect'] is False, 'Owner/public-connect policy differs.')
    checks['all_managed_roles_unprivileged'] = True
    checks['nonlogin_owner_public_connect_revoked'] = True
    def as_role(kind, body, succeeds):
        row = credentials['roles'][kind]
        result = execute_sql(args.container, args.database, row['name'], body, row['password'], expect_success=False)
        require((result.returncode == 0) == succeeds, f'Isolated {kind} permission assertion failed.')
    runtime = credentials['roles']['runtime']
    bad = execute_sql(args.container, args.database, runtime['name'], 'SELECT 1;',
                      'deliberately-wrong-private-test-password', expect_success=False)
    require(bad.returncode != 0, 'Password authentication was not enforced.')
    checks['wrong_password_rejected'] = True
    as_role('runtime', 'SELECT count(*) FROM core_template;', True)
    as_role('runtime', "BEGIN; INSERT INTO core_organization(id,created_at,name) VALUES ('00000000-0000-4000-8000-000000000099',now(),'Synthetic role probe'); ROLLBACK;", True)
    checks['runtime_read_and_rolled_back_dml'] = True
    for name, body in {
        'runtime_create_denied': 'CREATE TABLE public.quillmd_forbidden(id integer);',
        'runtime_trigger_disable_denied': 'ALTER TABLE core_ledgerentry DISABLE TRIGGER USER;',
        'runtime_truncate_denied': 'TRUNCATE core_auditevent;',
        'ledger_update_rejected': 'UPDATE core_ledgerentry SET description=description;',
        'audit_delete_rejected': 'DELETE FROM core_auditevent;',
        'usage_update_rejected': 'UPDATE core_usage SET provider=provider;',
        'mapping_update_rejected': 'UPDATE core_templateversion SET number=number;',
        'receipt_update_rejected': 'UPDATE core_providerreceipt SET provider=provider;',
        'owner_escalation_denied': 'SET ROLE quillmd_owner;',
    }.items():
        as_role('runtime', 'BEGIN; ' + body + ' ROLLBACK;', False)
        checks[name] = True
    as_role('backup', 'SELECT count(*) FROM core_user;', True)
    as_role('backup', "INSERT INTO core_organization(id,created_at,name) VALUES ('00000000-0000-4000-8000-000000000098',now(),'Forbidden');", False)
    checks['backup_read_only'] = True
    as_role('migrator', 'CREATE TABLE public.quillmd_forbidden(id integer);', False)
    as_role('migrator', '''BEGIN; SET ROLE quillmd_owner;
        CREATE TABLE public.quillmd_permission_probe(id bigserial PRIMARY KEY);
        DO $$ BEGIN IF NOT has_table_privilege('quillmd_runtime','public.quillmd_permission_probe','SELECT')
          OR NOT has_table_privilege('quillmd_runtime','public.quillmd_permission_probe','INSERT')
          OR NOT has_table_privilege('quillmd_runtime','public.quillmd_permission_probe','UPDATE')
          OR NOT has_table_privilege('quillmd_runtime','public.quillmd_permission_probe','DELETE')
          OR has_table_privilege('quillmd_runtime','public.quillmd_permission_probe','TRUNCATE')
          OR NOT has_sequence_privilege('quillmd_runtime','public.quillmd_permission_probe_id_seq','USAGE')
          OR has_sequence_privilege('quillmd_runtime','public.quillmd_permission_probe_id_seq','UPDATE')
          OR NOT has_table_privilege('quillmd_backup','public.quillmd_permission_probe','SELECT')
          THEN RAISE EXCEPTION 'default grants missing'; END IF; END $$; ROLLBACK;''', True)
    checks['migrator_requires_explicit_owner_role'] = True
    checks['new_table_default_grants'] = True
    backup_role = credentials['roles']['backup']
    run(['docker', 'exec', '-e', 'PGPASSWORD', args.container, 'pg_dump', '-h', '127.0.0.1',
         '-U', backup_role['name'], '-d', args.database, '--no-owner', '--no-privileges', '--file=/dev/null'],
        env=dict(os.environ, PGPASSWORD=backup_role['password']))
    checks['backup_role_pg_dump'] = True
    result = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'container': args.container,
              'checks': checks, 'checks_passed': len(checks), 'live_mutations': 0, 'provider_actions': 0}
    output = Path(args.credentials).with_suffix('.verified.json')
    temp = output.with_name(output.name + '.' + secrets.token_hex(4))
    write_private(temp, json.dumps(result, indent=2).encode() + b'\n')
    os.replace(temp, output)
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'apply', 'verify'])
    parser.add_argument('--profile', choices=['private', 'production'], default='private')
    parser.add_argument('--container')
    parser.add_argument('--database')
    parser.add_argument('--admin-user')
    parser.add_argument('--expected-container-id', default='')
    parser.add_argument('--credentials')
    args = parser.parse_args()
    if args.profile == 'production':
        require(not any((args.container, args.database, args.admin_user, args.expected_container_id, args.credentials)),
                'Production target and private credential paths come only from the reviewed profile.')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ops.production_database_roles import run as production_run
        production_run(args)
        return
    require(args.container and args.database and args.admin_user, 'Private target arguments required.')
    if args.action == 'inspect':
        print(json.dumps(inspect_policy(args)))
    else:
        require(args.credentials, 'Private credential destination required.')
        (apply if args.action == 'apply' else verify)(args)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.SubprocessError, DatabaseError):
        raise SystemExit('Role operation refused or failed; no secrets/SQL contents emitted.')
