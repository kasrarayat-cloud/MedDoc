#!/bin/sh
set -eu
set +x

clear_sensitive_environment() {
  DB_RUNTIME_PASSWORD=''
  DB_RELEASE_CONTROL_PASSWORD=''
  DB_AUDIT_DISPATCHER_PASSWORD=''
  DB_AUTH_EMAIL_DISPATCHER_PASSWORD=''
  DB_BACKUP_PASSWORD=''
  unset DB_RUNTIME_PASSWORD DB_RELEASE_CONTROL_PASSWORD
  unset DB_AUDIT_DISPATCHER_PASSWORD DB_AUTH_EMAIL_DISPATCHER_PASSWORD
  unset DB_BACKUP_PASSWORD
}
trap clear_sensitive_environment EXIT
trap 'clear_sensitive_environment; trap - EXIT HUP INT TERM; exit 1' HUP INT TERM

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${DB_RUNTIME_PASSWORD:?DB_RUNTIME_PASSWORD is required}"
: "${DB_RELEASE_CONTROL_PASSWORD:?DB_RELEASE_CONTROL_PASSWORD is required}"
: "${DB_AUDIT_DISPATCHER_PASSWORD:?DB_AUDIT_DISPATCHER_PASSWORD is required}"
: "${DB_AUTH_EMAIL_DISPATCHER_PASSWORD:?DB_AUTH_EMAIL_DISPATCHER_PASSWORD is required}"
: "${DB_BACKUP_PASSWORD_FILE:?DB_BACKUP_PASSWORD_FILE is required}"

validate_environment_secret() {
  secret_value=$1
  secret_size=$(printf '%s' "$secret_value" | wc -c | tr -d ' ')
  secret_without_forbidden_bytes=$(
    printf '%s' "$secret_value" | LC_ALL=C tr -d '\r\n' |
      wc -c | tr -d ' '
  )
  case "$secret_size" in
    ''|*[!0-9]*) return 1 ;;
  esac
  case "$secret_value" in
    *[!A-Za-z0-9_-]*) return 1 ;;
  esac
  [ "$secret_size" -ge 43 ] && [ "$secret_size" -le 128 ] &&
    [ "$secret_size" -eq "$secret_without_forbidden_bytes" ]
}

if ! validate_environment_secret "$DB_RUNTIME_PASSWORD" ||
   ! validate_environment_secret "$DB_RELEASE_CONTROL_PASSWORD" ||
   ! validate_environment_secret "$DB_AUDIT_DISPATCHER_PASSWORD" ||
   ! validate_environment_secret "$DB_AUTH_EMAIL_DISPATCHER_PASSWORD"; then
  printf '%s\n' 'Database login secrets must be approved generated base64url values.' >&2
  exit 1
fi
unset secret_value secret_size secret_without_forbidden_bytes

if [ ! -r "$DB_BACKUP_PASSWORD_FILE" ]; then
  printf '%s\n' 'Database backup password file is not readable.' >&2
  exit 1
fi
backup_password_size=$(wc -c < "$DB_BACKUP_PASSWORD_FILE" | tr -d ' ')
backup_password_without_forbidden_bytes=$(
  LC_ALL=C tr -d '\000\r\n' < "$DB_BACKUP_PASSWORD_FILE" |
    wc -c | tr -d ' '
)
case "$backup_password_size" in
  ''|*[!0-9]*)
    printf '%s\n' 'Database backup password file size is invalid.' >&2
    exit 1
    ;;
esac
if [ "$backup_password_size" -lt 43 ] ||
   [ "$backup_password_size" -gt 128 ] ||
   [ "$backup_password_size" -ne "$backup_password_without_forbidden_bytes" ] ||
   ! LC_ALL=C grep -Eq '^[A-Za-z0-9_-]{43,128}$' \
     "$DB_BACKUP_PASSWORD_FILE" 2>/dev/null; then
  printf '%s\n' 'Database backup password file must be an approved generated base64url secret.' >&2
  exit 1
fi
DB_BACKUP_PASSWORD=''
IFS= read -r DB_BACKUP_PASSWORD < "$DB_BACKUP_PASSWORD_FILE" ||
  [ -n "$DB_BACKUP_PASSWORD" ]
loaded_backup_password_size=$(
  printf '%s' "$DB_BACKUP_PASSWORD" | wc -c | tr -d ' '
)
if [ -z "$DB_BACKUP_PASSWORD" ] ||
   [ "$loaded_backup_password_size" -ne "$backup_password_size" ]; then
  printf '%s\n' 'Database backup password file is empty.' >&2
  exit 1
fi
export DB_BACKUP_PASSWORD

# Fresh-cluster bootstrap only. Existing production clusters use the separate
# reviewed, transactional principal/cluster-ACL provisioner. Passwords enter
# psql only through \getenv and never through argv, generated output, or SQL
# files. Every mutation and every postcondition shares one transaction.
{
  printf '%s\n%s\n' "$DB_RUNTIME_PASSWORD" "$DB_RUNTIME_PASSWORD"
  printf '%s\n%s\n' \
    "$DB_RELEASE_CONTROL_PASSWORD" "$DB_RELEASE_CONTROL_PASSWORD"
  printf '%s\n%s\n' \
    "$DB_AUDIT_DISPATCHER_PASSWORD" "$DB_AUDIT_DISPATCHER_PASSWORD"
  printf '%s\n%s\n' \
    "$DB_AUTH_EMAIL_DISPATCHER_PASSWORD" \
    "$DB_AUTH_EMAIL_DISPATCHER_PASSWORD"
  printf '%s\n%s\n' "$DB_BACKUP_PASSWORD" "$DB_BACKUP_PASSWORD"
} | psql -X --quiet --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file=/dev/fd/3 3<<'SQL'
\set ECHO none
\set VERBOSITY terse
BEGIN;
SET LOCAL search_path = pg_catalog;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '180s';
SET LOCAL password_encryption = 'scram-sha-256';
SELECT pg_catalog.pg_advisory_xact_lock(73119, 2026072001);

-- psql's \password hashes client-side, but its SCRAM verifier is still
-- credential-equivalent. Suppress every server-side query/error/duration/
-- pgaudit path and activity text before those fixed-role commands execute.
-- These transaction-local settings reset when this provisioning transaction
-- commits; the operator emits separate fixed success/failure evidence.
SET LOCAL log_statement = 'none';
SET LOCAL log_min_duration_statement = -1;
SET LOCAL log_duration = FALSE;
SET LOCAL log_statement_stats = FALSE;
SET LOCAL log_min_error_statement = 'panic';
SET LOCAL track_activities = FALSE;
SET LOCAL pgaudit.log = 'none';
SET LOCAL pgaudit.log_parameter = FALSE;

DO $version_guard$
BEGIN
  IF pg_catalog.current_setting('server_version_num')::integer
       NOT BETWEEN 160000 AND 169999 THEN
    RAISE EXCEPTION 'Exact database-principal bootstrap requires PostgreSQL 16';
  END IF;
END
$version_guard$;

DO $boundaries$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_runtime') THEN
    CREATE ROLE quillmd_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_release_control') THEN
    CREATE ROLE quillmd_release_control NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_release_security') THEN
    CREATE ROLE quillmd_release_security NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_audit_dispatcher') THEN
    CREATE ROLE quillmd_audit_dispatcher NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_auth_email_dispatcher') THEN
    CREATE ROLE quillmd_auth_email_dispatcher NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_backup') THEN
    CREATE ROLE quillmd_backup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END
$boundaries$;

CREATE OR REPLACE FUNCTION pg_temp.quillmd_login_has_direct_authority(
  principal_oid OID
)
RETURNS BOOLEAN LANGUAGE sql STABLE
SET search_path = pg_catalog
AS $direct_authority$
  SELECT EXISTS (
    SELECT 1 FROM pg_catalog.pg_shdepend dependency
    WHERE dependency.refclassid =
        'pg_catalog.pg_authid'::pg_catalog.regclass
      AND dependency.refobjid = principal_oid
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_db_role_setting setting
    WHERE setting.setrole = principal_oid
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.oid = principal_oid AND role.rolconfig IS NOT NULL
  );
$direct_authority$;

DO $preexisting_guard$
DECLARE
  current_database_oid OID := (
    SELECT oid FROM pg_catalog.pg_database
    WHERE datname = pg_catalog.current_database()
  );
BEGIN
  IF (
    SELECT count(*) FROM pg_catalog.pg_roles role
    WHERE role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup'
    ) AND role.rolcanlogin = FALSE AND role.rolsuper = FALSE
      AND role.rolcreatedb = FALSE AND role.rolcreaterole = FALSE
      AND role.rolinherit = FALSE AND role.rolreplication = FALSE
      AND role.rolbypassrls = FALSE AND role.rolconnlimit = -1
      AND role.rolvaliduntil IS NULL AND role.rolconfig IS NULL
  ) <> 6 OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_authid authentication
    WHERE authentication.rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup'
    ) AND authentication.rolpassword IS NOT NULL
  ) OR NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles role
    JOIN pg_catalog.pg_authid authentication
      ON authentication.oid = role.oid
    WHERE role.rolname = 'pg_read_all_data'
      AND role.rolcanlogin = FALSE
      AND role.rolsuper = FALSE
      AND role.rolcreatedb = FALSE
      AND role.rolcreaterole = FALSE
      AND role.rolinherit = TRUE
      AND role.rolreplication = FALSE
      AND role.rolbypassrls = FALSE
      AND role.rolconnlimit = -1
      AND role.rolvaliduntil IS NULL
      AND role.rolconfig IS NULL
      AND authentication.rolpassword IS NULL
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher'
    ) AND (
      role.rolcanlogin = FALSE OR role.rolsuper OR role.rolcreatedb
      OR role.rolcreaterole OR role.rolinherit = FALSE OR role.rolreplication
      OR role.rolbypassrls OR role.rolconnlimit <> -1
      OR role.rolvaliduntil IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.rolname = 'meddoc_backup' AND (
      role.rolcanlogin = FALSE OR role.rolsuper OR role.rolcreatedb
      OR role.rolcreaterole OR role.rolinherit = FALSE OR role.rolreplication
      OR role.rolbypassrls = FALSE OR role.rolconnlimit <> 1
      OR role.rolvaliduntil IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher', 'meddoc_backup'
    ) AND pg_temp.quillmd_login_has_direct_authority(login_role.oid)
  ) OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor ON grantor.oid = membership.grantor
    WHERE (
      member_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher', 'meddoc_backup',
        'quillmd_runtime', 'quillmd_release_control',
        'quillmd_release_security', 'quillmd_audit_dispatcher',
        'quillmd_auth_email_dispatcher', 'quillmd_backup',
        'pg_read_all_data'
    ) OR granted_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher', 'meddoc_backup',
        'quillmd_runtime', 'quillmd_release_control',
        'quillmd_release_security', 'quillmd_audit_dispatcher',
        'quillmd_auth_email_dispatcher', 'quillmd_backup',
        'pg_read_all_data'
      ) OR grantor.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher', 'meddoc_backup',
        'quillmd_runtime', 'quillmd_release_control',
        'quillmd_release_security', 'quillmd_audit_dispatcher',
        'quillmd_auth_email_dispatcher', 'quillmd_backup',
        'pg_read_all_data'
      )
    ) AND (
      membership.admin_option OR membership.inherit_option = FALSE
      OR membership.set_option OR grantor.rolsuper = FALSE OR NOT (
        (member_role.rolname = 'meddoc_runtime'
          AND granted_role.rolname = 'quillmd_runtime')
        OR (member_role.rolname = 'meddoc_release_control'
          AND granted_role.rolname = 'quillmd_release_control')
        OR (member_role.rolname = 'meddoc_release_security'
          AND granted_role.rolname = 'quillmd_release_security')
        OR (member_role.rolname = 'meddoc_audit_dispatcher'
          AND granted_role.rolname = 'quillmd_audit_dispatcher')
        OR (member_role.rolname = 'meddoc_auth_email_dispatcher'
          AND granted_role.rolname = 'quillmd_auth_email_dispatcher')
        OR (member_role.rolname = 'meddoc_backup'
          AND granted_role.rolname = 'quillmd_backup')
        OR (member_role.rolname = 'quillmd_backup'
          AND granted_role.rolname = 'pg_read_all_data')
      )
    )
  ) OR EXISTS (
    SELECT 1
    FROM (
      VALUES
        ('meddoc_runtime', 'quillmd_runtime'),
        ('meddoc_release_control', 'quillmd_release_control'),
        ('meddoc_release_security', 'quillmd_release_security'),
        ('meddoc_audit_dispatcher', 'quillmd_audit_dispatcher'),
        ('meddoc_auth_email_dispatcher', 'quillmd_auth_email_dispatcher'),
        ('meddoc_backup', 'quillmd_backup'),
        ('quillmd_backup', 'pg_read_all_data')
    ) expected(member_name, granted_name)
    JOIN pg_catalog.pg_roles member_role
      ON member_role.rolname = expected.member_name
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.rolname = expected.granted_name
    WHERE (
      SELECT count(*) FROM pg_catalog.pg_auth_members membership
      WHERE membership.member = member_role.oid
        AND membership.roleid = granted_role.oid
    ) > 1
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles boundary_role
    WHERE boundary_role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup'
    ) AND (
      EXISTS (
        SELECT 1 FROM pg_catalog.pg_db_role_setting setting
        WHERE setting.setrole = boundary_role.oid
      ) OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_shdepend dependency
        WHERE dependency.refclassid =
            'pg_catalog.pg_authid'::pg_catalog.regclass
          AND dependency.refobjid = boundary_role.oid
          AND NOT (
            dependency.deptype = 'a' AND dependency.dbid = 0
            AND dependency.classid =
                'pg_catalog.pg_database'::pg_catalog.regclass
            AND dependency.objid = current_database_oid
            AND dependency.objsubid = 0
          )
      ) OR (
        SELECT count(*) FROM pg_catalog.pg_shdepend dependency
        WHERE dependency.refclassid =
            'pg_catalog.pg_authid'::pg_catalog.regclass
          AND dependency.refobjid = boundary_role.oid
      ) > 1
    )
  ) THEN
    RAISE EXCEPTION 'Refusing to reuse a non-exact database principal';
  END IF;
END
$preexisting_guard$;

SELECT 'CREATE ROLE meddoc_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_runtime') \gexec
SELECT 'CREATE ROLE meddoc_release_control LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_release_control') \gexec
SELECT 'CREATE ROLE meddoc_audit_dispatcher LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_audit_dispatcher') \gexec
SELECT 'CREATE ROLE meddoc_auth_email_dispatcher LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_auth_email_dispatcher') \gexec
SELECT 'CREATE ROLE meddoc_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION BYPASSRLS CONNECTION LIMIT 1'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_backup') \gexec

-- SQL is read from fd 3, leaving stdin exclusively for two hidden prompts per
-- fixed role. No plaintext, reversible transport, or SCRAM verifier is placed
-- in the SQL file, argv, activity text, or enabled server logs.
\password meddoc_runtime
\password meddoc_release_control
\password meddoc_audit_dispatcher
\password meddoc_auth_email_dispatcher
\password meddoc_backup

SELECT format(
  'GRANT %I TO %I WITH ADMIN FALSE, INHERIT TRUE, SET FALSE',
  expected.granted_name, expected.member_name
)
FROM (
  VALUES
    ('meddoc_runtime', 'quillmd_runtime'),
    ('meddoc_release_control', 'quillmd_release_control'),
    ('meddoc_audit_dispatcher', 'quillmd_audit_dispatcher'),
    ('meddoc_auth_email_dispatcher', 'quillmd_auth_email_dispatcher'),
    ('meddoc_backup', 'quillmd_backup'),
    ('quillmd_backup', 'pg_read_all_data')
) expected(member_name, granted_name)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_auth_members membership
  WHERE membership.member = expected.member_name::pg_catalog.regrole
    AND membership.roleid = expected.granted_name::pg_catalog.regrole
) \gexec

-- No trusted login may escape to postgres/template0/template1/a newly added
-- database through PostgreSQL's implicit PUBLIC CONNECT/TEMPORARY defaults.
-- Normalize databases with datallowconn=false too, so enabling one later
-- cannot activate a latent PUBLIC or trusted-boundary grant.
DO $cluster_database_acl$
DECLARE
  database_name name;
BEGIN
  FOR database_name IN
    SELECT datname FROM pg_catalog.pg_database
    ORDER BY datname COLLATE "C"
  LOOP
    EXECUTE pg_catalog.format(
      'REVOKE CONNECT, CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC',
      database_name
    );
  END LOOP;
  EXECUTE pg_catalog.format(
    'GRANT CONNECT ON DATABASE %I TO quillmd_runtime, quillmd_release_control, quillmd_release_security, quillmd_audit_dispatcher, quillmd_auth_email_dispatcher, quillmd_backup',
    pg_catalog.current_database()
  );
END
$cluster_database_acl$;

REVOKE EXECUTE ON FUNCTION
  pg_catalog.lo_creat(integer),
  pg_catalog.lo_create(oid),
  pg_catalog.lo_from_bytea(oid, bytea),
  pg_catalog.lo_open(oid, integer),
  pg_catalog.lo_put(oid, bigint, bytea),
  pg_catalog.lo_truncate(integer, integer),
  pg_catalog.lo_truncate64(integer, bigint),
  pg_catalog.lo_unlink(oid),
  pg_catalog.lowrite(integer, bytea)
FROM PUBLIC;

DO $postcondition$
DECLARE
  current_database_oid OID := (
    SELECT oid FROM pg_catalog.pg_database
    WHERE datname = pg_catalog.current_database()
  );
BEGIN
  IF (
    SELECT count(*) FROM pg_catalog.pg_roles boundary_role
    WHERE boundary_role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup'
    ) AND boundary_role.rolcanlogin = FALSE
      AND boundary_role.rolsuper = FALSE
      AND boundary_role.rolcreatedb = FALSE
      AND boundary_role.rolcreaterole = FALSE
      AND boundary_role.rolinherit = FALSE
      AND boundary_role.rolreplication = FALSE
      AND boundary_role.rolbypassrls = FALSE
      AND boundary_role.rolconnlimit = -1
      AND boundary_role.rolvaliduntil IS NULL
      AND boundary_role.rolconfig IS NULL
  ) <> 6 OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_authid authentication
    WHERE authentication.rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup'
    ) AND authentication.rolpassword IS NOT NULL
  ) OR NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles role
    JOIN pg_catalog.pg_authid authentication
      ON authentication.oid = role.oid
    WHERE role.rolname = 'pg_read_all_data'
      AND role.rolcanlogin = FALSE
      AND role.rolsuper = FALSE
      AND role.rolcreatedb = FALSE
      AND role.rolcreaterole = FALSE
      AND role.rolinherit = TRUE
      AND role.rolreplication = FALSE
      AND role.rolbypassrls = FALSE
      AND role.rolconnlimit = -1
      AND role.rolvaliduntil IS NULL
      AND role.rolconfig IS NULL
      AND authentication.rolpassword IS NULL
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher'
    ) AND (
      login_role.rolcanlogin = FALSE OR login_role.rolsuper
      OR login_role.rolcreatedb OR login_role.rolcreaterole
      OR login_role.rolinherit = FALSE OR login_role.rolreplication
      OR login_role.rolbypassrls OR login_role.rolconnlimit <> -1
      OR login_role.rolvaliduntil IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname = 'meddoc_backup' AND (
      login_role.rolcanlogin = FALSE OR login_role.rolsuper
      OR login_role.rolcreatedb OR login_role.rolcreaterole
      OR login_role.rolinherit = FALSE OR login_role.rolreplication
      OR login_role.rolbypassrls = FALSE OR login_role.rolconnlimit <> 1
      OR login_role.rolvaliduntil IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1
    FROM (
      VALUES
        ('meddoc_runtime', 'quillmd_runtime'),
        ('meddoc_release_control', 'quillmd_release_control'),
        ('meddoc_audit_dispatcher', 'quillmd_audit_dispatcher'),
        ('meddoc_auth_email_dispatcher', 'quillmd_auth_email_dispatcher'),
        ('meddoc_backup', 'quillmd_backup'),
        ('quillmd_backup', 'pg_read_all_data')
    ) expected(member_name, granted_name)
    JOIN pg_catalog.pg_roles member_role
      ON member_role.rolname = expected.member_name
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.rolname = expected.granted_name
    WHERE (
      SELECT count(*)
      FROM pg_catalog.pg_auth_members membership
      JOIN pg_catalog.pg_roles grantor ON grantor.oid = membership.grantor
      WHERE membership.member = member_role.oid
        AND membership.roleid = granted_role.oid
        AND membership.admin_option = FALSE
        AND membership.inherit_option = TRUE
        AND membership.set_option = FALSE
        AND grantor.rolsuper = TRUE
    ) <> 1
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles optional_login
    WHERE optional_login.rolname = 'meddoc_release_security'
      AND (
        SELECT count(*)
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles grantor ON grantor.oid = membership.grantor
        WHERE membership.member = optional_login.oid
          AND membership.roleid =
              'quillmd_release_security'::pg_catalog.regrole
          AND membership.admin_option = FALSE
          AND membership.inherit_option = TRUE
          AND membership.set_option = FALSE
          AND grantor.rolsuper = TRUE
      ) <> 1
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher', 'meddoc_backup'
    ) AND pg_temp.quillmd_login_has_direct_authority(login_role.oid)
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_authid login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher', 'meddoc_backup'
    ) AND COALESCE(login_role.rolpassword, '') NOT LIKE 'SCRAM-SHA-256$4096:%'
  ) OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor ON grantor.oid = membership.grantor
    WHERE grantor.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher', 'meddoc_backup',
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup',
      'pg_read_all_data'
    ) OR (
      (
        member_role.rolname IN (
          'meddoc_runtime', 'meddoc_release_control',
          'meddoc_release_security', 'meddoc_audit_dispatcher',
          'meddoc_auth_email_dispatcher', 'meddoc_backup',
          'quillmd_runtime', 'quillmd_release_control',
          'quillmd_release_security', 'quillmd_audit_dispatcher',
          'quillmd_auth_email_dispatcher', 'quillmd_backup',
          'pg_read_all_data'
        ) OR granted_role.rolname IN (
          'meddoc_runtime', 'meddoc_release_control',
          'meddoc_release_security', 'meddoc_audit_dispatcher',
          'meddoc_auth_email_dispatcher', 'meddoc_backup',
          'quillmd_runtime', 'quillmd_release_control',
          'quillmd_release_security', 'quillmd_audit_dispatcher',
          'quillmd_auth_email_dispatcher', 'quillmd_backup',
          'pg_read_all_data'
        )
      ) AND (
        membership.admin_option OR membership.inherit_option = FALSE
        OR membership.set_option OR grantor.rolsuper = FALSE OR NOT (
          (member_role.rolname = 'meddoc_runtime'
            AND granted_role.rolname = 'quillmd_runtime')
          OR (member_role.rolname = 'meddoc_release_control'
            AND granted_role.rolname = 'quillmd_release_control')
          OR (member_role.rolname = 'meddoc_release_security'
            AND granted_role.rolname = 'quillmd_release_security')
          OR (member_role.rolname = 'meddoc_audit_dispatcher'
            AND granted_role.rolname = 'quillmd_audit_dispatcher')
          OR (member_role.rolname = 'meddoc_auth_email_dispatcher'
            AND granted_role.rolname = 'quillmd_auth_email_dispatcher')
          OR (member_role.rolname = 'meddoc_backup'
            AND granted_role.rolname = 'quillmd_backup')
          OR (member_role.rolname = 'quillmd_backup'
            AND granted_role.rolname = 'pg_read_all_data')
        )
      )
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles boundary_role
    WHERE boundary_role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher', 'quillmd_backup'
    ) AND (
      (SELECT count(*) FROM pg_catalog.pg_shdepend dependency
       WHERE dependency.refclassid =
           'pg_catalog.pg_authid'::pg_catalog.regclass
         AND dependency.refobjid = boundary_role.oid
         AND dependency.deptype = 'a' AND dependency.dbid = 0
         AND dependency.classid =
             'pg_catalog.pg_database'::pg_catalog.regclass
         AND dependency.objid = current_database_oid
         AND dependency.objsubid = 0) <> 1
      OR (SELECT count(*) FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = boundary_role.oid) <> 1
      OR pg_catalog.has_database_privilege(
           boundary_role.oid, current_database_oid, 'CONNECT'
         ) IS DISTINCT FROM TRUE
      OR pg_catalog.has_database_privilege(
           boundary_role.oid, current_database_oid, 'CREATE'
         ) IS DISTINCT FROM FALSE
      OR pg_catalog.has_database_privilege(
           boundary_role.oid, current_database_oid, 'TEMP'
         ) IS DISTINCT FROM FALSE
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_audit_dispatcher', 'meddoc_auth_email_dispatcher',
      'meddoc_backup'
    ) AND (
      pg_catalog.has_database_privilege(
        login_role.oid, current_database_oid, 'CONNECT'
      ) IS DISTINCT FROM TRUE
      OR pg_catalog.has_database_privilege(
        login_role.oid, current_database_oid, 'CREATE'
      ) IS DISTINCT FROM FALSE
      OR pg_catalog.has_database_privilege(
        login_role.oid, current_database_oid, 'TEMP'
      ) IS DISTINCT FROM FALSE
      OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_database database
        WHERE database.oid <> current_database_oid
          AND pg_catalog.has_database_privilege(
            login_role.oid, database.oid, 'CONNECT'
          ) IS DISTINCT FROM FALSE
      )
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_database database
    CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
      database.datacl,
      pg_catalog.acldefault('d'::"char", database.datdba)
    )) privilege
    WHERE privilege.grantee = 0
      AND privilege.privilege_type IN ('CONNECT', 'CREATE', 'TEMPORARY')
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_database database
    CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
      database.datacl,
      pg_catalog.acldefault('d'::"char", database.datdba)
    )) privilege
    JOIN pg_catalog.pg_roles principal_role
      ON principal_role.oid = privilege.grantee
       OR principal_role.oid = privilege.grantor
    WHERE principal_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher', 'meddoc_backup'
    )
  ) OR EXISTS (
    SELECT 1
    FROM (
      VALUES
        ('quillmd_runtime'),
        ('quillmd_release_control'),
        ('quillmd_release_security'),
        ('quillmd_audit_dispatcher'),
        ('quillmd_auth_email_dispatcher'),
        ('quillmd_backup')
    ) expected(role_name)
    JOIN pg_catalog.pg_roles boundary_role
      ON boundary_role.rolname = expected.role_name
    WHERE (
      SELECT count(*)
      FROM pg_catalog.pg_database database
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        database.datacl,
        pg_catalog.acldefault('d'::"char", database.datdba)
      )) privilege
      WHERE privilege.grantee = boundary_role.oid
         OR privilege.grantor = boundary_role.oid
    ) <> 1 OR NOT EXISTS (
      SELECT 1
      FROM pg_catalog.pg_database database
      CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
        database.datacl,
        pg_catalog.acldefault('d'::"char", database.datdba)
      )) privilege
      JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = privilege.grantor
      WHERE database.oid = current_database_oid
        AND privilege.grantee = boundary_role.oid
        AND privilege.privilege_type = 'CONNECT'
        AND privilege.is_grantable = FALSE
        AND grantor.rolsuper
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc function_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(
      function_object.proacl,
      pg_catalog.acldefault('f'::"char", function_object.proowner)
    )) privilege
    WHERE function_object.oid IN (
      'pg_catalog.lo_creat(integer)'::pg_catalog.regprocedure,
      'pg_catalog.lo_create(oid)'::pg_catalog.regprocedure,
      'pg_catalog.lo_from_bytea(oid,bytea)'::pg_catalog.regprocedure,
      'pg_catalog.lo_open(oid,integer)'::pg_catalog.regprocedure,
      'pg_catalog.lo_put(oid,bigint,bytea)'::pg_catalog.regprocedure,
      'pg_catalog.lo_truncate(integer,integer)'::pg_catalog.regprocedure,
      'pg_catalog.lo_truncate64(integer,bigint)'::pg_catalog.regprocedure,
      'pg_catalog.lo_unlink(oid)'::pg_catalog.regprocedure,
      'pg_catalog.lowrite(integer,bytea)'::pg_catalog.regprocedure
    ) AND privilege.grantee = 0
      AND privilege.privilege_type = 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Database principal bootstrap postcondition failed';
  END IF;
END
$postcondition$;
COMMIT;
SQL

unset DB_BACKUP_PASSWORD
trap - EXIT HUP INT TERM
clear_sensitive_environment
