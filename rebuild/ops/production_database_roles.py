"""Production-only role bootstrap. Private container tooling is unchanged.

Uses the activated profile, a committed target/release declaration, AWS RDS
identity and verify-full TLS. `inspect` is read-only; `apply` changes only roles,
public-schema/database ownership and grants. `verify` is read-only: destructive
permission proofs belong on an independently pinned restore drill.
"""
import json
from pathlib import Path
import secrets
from psycopg import sql
from . import deployment_profile as profiles
from .production_operator import authority, connection, describe_target, private_json, require

POLICY = 'QuillMD production role policy v1'
FLAGS = ('rolsuper', 'rolcreatedb', 'rolcreaterole', 'rolreplication', 'rolbypassrls')


def roles_state(conn, profile):
    return conn.execute('''SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,
        rolreplication,rolbypassrls,shobj_description(oid,'pg_authid') AS marker
        FROM pg_roles WHERE rolname = ANY(%s) ORDER BY rolname''', (list(profile.roles.values()),)).fetchall()


def check_roles(rows, profile, complete=False):
    require(not complete or len(rows) == 4, 'role_count')
    require(all(not row[key] for row in rows for key in FLAGS), 'role_privilege')
    require(all(row['marker'] == POLICY for row in rows), 'role_policy')
    require(all(row['rolcanlogin'] == (row['rolname'] != profile.roles['owner']) for row in rows), 'role_login')


def verify_policy(conn, profile):
    check_roles(roles_state(conn, profile), profile, complete=True)
    row = conn.execute('''SELECT pg_get_userbyid(datdba) AS owner,
        has_database_privilege('public',oid,'CONNECT') AS public_connect
        FROM pg_database WHERE datname=current_database()''').fetchone()
    require(row['owner'] == profile.roles['owner'] and not row['public_connect'], 'database_policy')
    memberships = conn.execute('''SELECT parent.rolname AS parent,child.rolname AS child,
        m.admin_option,m.inherit_option,m.set_option FROM pg_auth_members m
        JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member
        WHERE child.rolname=ANY(%s)''', (list(profile.roles.values()),)).fetchall()
    require(len(memberships) == 1 and memberships[0] == {
        'parent': profile.roles['owner'], 'child': profile.roles['migrator'],
        'admin_option': False, 'inherit_option': False, 'set_option': True}, 'role_membership')
    owner = conn.execute("SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname='public'").fetchone()
    require(owner['owner'] == profile.roles['owner'], 'schema_owner')
    privileges = conn.execute('''SELECT count(*) AS count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p') AND (
        has_table_privilege(%s,c.oid,'TRUNCATE') OR has_table_privilege(%s,c.oid,'TRIGGER') OR
        has_table_privilege(%s,c.oid,'INSERT') OR has_table_privilege(%s,c.oid,'UPDATE') OR
        has_table_privilege(%s,c.oid,'DELETE') OR has_table_privilege(%s,c.oid,'TRUNCATE'))''',
        (profile.roles['runtime'], profile.roles['runtime'], *([profile.roles['backup']] * 4))).fetchone()
    require(privileges['count'] == 0, 'excess_table_privilege')
    for kind, required in (('runtime', ('SELECT', 'INSERT', 'UPDATE', 'DELETE')), ('backup', ('SELECT',))):
        for permission in required:
            missing = conn.execute('''SELECT count(*) AS count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m')
                AND NOT has_table_privilege(%s,c.oid,%s)''', (profile.roles[kind], permission)).fetchone()
            require(missing['count'] == 0, 'required_table_privilege')
    for kind, required in (('runtime', ('USAGE', 'SELECT')), ('backup', ('SELECT',))):
        for permission in required:
            missing = conn.execute('''SELECT count(*) AS count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND CASE WHEN c.relkind='S'
                THEN NOT has_sequence_privilege(%s,c.oid,%s) ELSE false END''', (profile.roles[kind], permission)).fetchone()
            require(missing['count'] == 0, 'required_sequence_privilege')
    for kind in ('runtime', 'backup', 'migrator'):
        access = conn.execute("SELECT has_schema_privilege(%s,'public','USAGE') AS usage,"
                              "has_schema_privilege(%s,'public','CREATE') AS create",
                              (profile.roles[kind], profile.roles[kind])).fetchone()
        require(access == {'usage': True, 'create': False}, 'required_schema_privilege')
    verify_defaults(conn, profile)
    return {'roles': 4, 'unprivileged': True, 'owner_login': False, 'public_connect': False,
            'migrator_explicit_owner': True}


def verify_defaults(conn, profile):
    """Global defaults plus schema additions determine future access (they union).

    A schema-local REVOKE cannot remove global PUBLIC EXECUTE. Include PostgreSQL's
    implicit acldefault when the owner's global ACL row is absent.
    """
    required = {'r': {'runtime': {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}, 'backup': {'SELECT'}},
                'S': {'runtime': {'USAGE', 'SELECT'}, 'backup': {'SELECT'}}, 'f': {}}
    for kind, expected in required.items():
        entries = conn.execute('''WITH owner AS (SELECT oid FROM pg_roles WHERE rolname=%s),
            grants AS (
              SELECT x.* FROM owner o CROSS JOIN LATERAL aclexplode(COALESCE(
                (SELECT defaclacl FROM pg_default_acl WHERE defaclrole=o.oid AND defaclnamespace=0 AND defaclobjtype=%s),
                acldefault(%s::"char",o.oid))) x
              UNION ALL
              SELECT x.* FROM owner o JOIN pg_default_acl d ON d.defaclrole=o.oid
                CROSS JOIN LATERAL aclexplode(d.defaclacl) x
              WHERE d.defaclnamespace='public'::regnamespace AND d.defaclobjtype=%s)
            SELECT COALESCE(r.rolname,'PUBLIC') AS recipient,g.privilege_type,g.is_grantable
            FROM grants g LEFT JOIN pg_roles r ON r.oid=g.grantee''',
            (profile.roles['owner'], kind, kind, kind)).fetchall()
        require(not any(row['recipient'] == 'PUBLIC' for row in entries), 'public_default_privilege')
        for role_kind in ('runtime', 'backup', 'migrator'):
            grants = [row for row in entries if row['recipient'] == profile.roles[role_kind]]
            require({row['privilege_type'] for row in grants} == expected.get(role_kind, set())
                    and not any(row['is_grantable'] for row in grants), 'required_default_privilege')


def apply_policy(conn, profile, admin, credentials):
    conn.execute("SET LOCAL lock_timeout='5s'")
    conn.execute("SET LOCAL statement_timeout='30s'")
    conn.execute("SELECT pg_advisory_xact_lock(748413910341)")
    rows = roles_state(conn, profile)
    check_roles(rows, profile)
    existing = {row['rolname'] for row in rows}
    objects = conn.execute('''SELECT count(*) AS count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','S','v','m','p') AND pg_get_userbyid(c.relowner)<>%s''',
                           (profile.roles['owner'],)).fetchone()
    require(objects['count'] == 0, 'unexpected_object_owner')
    for kind, name in profile.roles.items():
        if name not in existing:
            conn.execute(sql.SQL('CREATE ROLE {} {}').format(sql.Identifier(name), sql.SQL('NOLOGIN' if kind == 'owner' else 'LOGIN')))
            conn.execute(sql.SQL('COMMENT ON ROLE {} IS {}').format(sql.Identifier(name), sql.Literal(POLICY)))
            if kind != 'owner':
                conn.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(name), sql.Literal(credentials['roles'][kind]['password'])))
    # RDS master is NOSUPERUSER. Its explicit owner membership is retained for
    # recovery; application runtime/backup never receive it.
    conn.execute(sql.SQL('GRANT {} TO {} WITH INHERIT TRUE, SET TRUE').format(
        sql.Identifier(profile.roles['owner']), sql.Identifier(admin)))
    conn.execute(sql.SQL('GRANT {} TO {} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE').format(
        sql.Identifier(profile.roles['owner']), sql.Identifier(profile.roles['migrator'])))
    for kind in ('runtime', 'backup'):
        conn.execute(sql.SQL('REVOKE {} FROM {}').format(sql.Identifier(profile.roles['owner']), sql.Identifier(profile.roles[kind])))
    conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(profile.database_name), sql.Identifier(admin)))
    conn.execute(sql.SQL('ALTER DATABASE {} OWNER TO {}').format(sql.Identifier(profile.database_name), sql.Identifier(profile.roles['owner'])))
    conn.execute(sql.SQL('ALTER SCHEMA public OWNER TO {}').format(sql.Identifier(profile.roles['owner'])))
    conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(profile.roles['owner'])))
    conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(profile.database_name)))
    conn.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
    for kind in ('runtime', 'migrator', 'backup'):
        role = sql.Identifier(profile.roles[kind])
        conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(profile.database_name), role))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(role))
    for kind, table, sequence in (('runtime', 'SELECT,INSERT,UPDATE,DELETE', 'USAGE,SELECT'), ('backup', 'SELECT', 'SELECT')):
        role = sql.Identifier(profile.roles[kind])
        for object_type, permissions in (('TABLES', table), ('SEQUENCES', sequence)):
            conn.execute(sql.SQL('GRANT ' + permissions + ' ON ALL ' + object_type + ' IN SCHEMA public TO {}').format(role))
            conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ' + permissions + ' ON ' + object_type + ' TO {}').format(role))
    conn.execute('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC')
    conn.execute('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC')
    conn.execute('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC')
    conn.execute('ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC')
    conn.execute('RESET ROLE')
    return verify_policy(conn, profile)


def role_credentials(profile, declaration, *, create=False):
    from .backup_restore import write_private
    destination = profile.operator_directory / 'role-bootstrap.json'
    if not destination.exists():
        require(create, 'credential_file_missing')
        data = {'profile': 'production', 'profile_sha256': profile.sha256, 'database': profile.database_name,
                'database_resource_id': declaration['database_resource_id'], 'policy': POLICY,
                'roles': {kind: {'name': name, 'password': secrets.token_urlsafe(48)}
                          for kind, name in profile.roles.items() if kind != 'owner'}}
        write_private(destination, json.dumps(data).encode())
    data = private_json(destination)
    require(data.get('profile') == 'production' and data.get('profile_sha256') == profile.sha256
            and data.get('database') == profile.database_name and data.get('policy') == POLICY
            and data.get('database_resource_id') == declaration['database_resource_id'], 'credential_target')
    require(set(data.get('roles', {})) == {'runtime', 'migrator', 'backup'} and all(
        data['roles'][kind]['name'] == profile.roles[kind] and len(data['roles'][kind]['password']) >= 40
        for kind in data['roles']), 'credential_roles')
    return data


def verify_credentials(profile, credentials):
    """Authentication and role-boundary checks only; no live DML/DDL proof."""
    for kind in ('runtime', 'migrator', 'backup'):
        role = credentials['roles'][kind]
        with connection(profile, {'username': role['name'], 'password': role['password']}) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            row = conn.execute('''SELECT current_database() AS database,current_user AS role,
                current_setting('session_replication_role') AS replication,
                has_schema_privilege(current_user,'public','CREATE') AS can_create,
                pg_has_role(current_user,%s,'SET') AS can_set_owner,
                (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls''',
                (profile.roles['owner'],)).fetchone()
            require(row == {'database': profile.database_name, 'role': role['name'], 'replication': 'origin',
                            'can_create': False, 'can_set_owner': kind == 'migrator', 'tls': True}, 'role_authentication')


def run(args):
    profile = profiles.load_production()
    declaration = authority(profile, 'database_roles')
    require(args.action in declaration.get('actions', []), 'declaration_action')
    target = describe_target(profile, declaration)
    admin = private_json(profile.operator_directory / 'rds-master.json')
    require(admin.get('username') == target.get('MasterUsername'), 'maintenance_identity')
    with connection(profile, admin) as conn:
        if args.action != 'apply':
            conn.execute('SET TRANSACTION READ ONLY')
        identity = conn.execute('''SELECT current_database() AS database,current_user AS role,
            pg_has_role(current_user,'rds_superuser','MEMBER') AS rds_admin,
            current_setting('session_replication_role') AS replication,
            (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS tls''').fetchone()
        require(identity == {'database': profile.database_name, 'role': admin['username'],
                             'rds_admin': True, 'replication': 'origin', 'tls': True}, 'maintenance_connection')
        if args.action == 'apply':
            credentials = role_credentials(profile, declaration, create=True)
            result = apply_policy(conn, profile, admin['username'], credentials)
        else:
            result = verify_policy(conn, profile) if args.action == 'verify' else {'roles_present': len(roles_state(conn, profile))}
    if args.action == 'apply':
        verify_credentials(profile, credentials)
        from .backup_restore import write_private
        wrapper = dict(credentials, roles={kind: credentials['roles'][kind] for kind in ('migrator', 'backup')})
        destination = profile.operator_directory / 'database-roles.json'
        if destination.exists():
            require(private_json(destination) == wrapper, 'wrapper_credentials_differ')
        else:
            write_private(destination, json.dumps(wrapper).encode())
    elif args.action == 'verify':
        credentials = role_credentials(profile, declaration)
        verify_credentials(profile, credentials)
    print(json.dumps({'action': args.action, 'profile_sha256': profile.sha256,
                      'release_sha': declaration['release_sha'], 'checks': result}))
