#!/bin/sh
set -eu
set +x

clear_release_security_password() {
  DB_RELEASE_SECURITY_PASSWORD=''
  unset DB_RELEASE_SECURITY_PASSWORD
}
trap clear_release_security_password EXIT
trap 'clear_release_security_password; trap - EXIT HUP INT TERM; exit 1' HUP INT TERM

: "${DB_RELEASE_SECURITY_PASSWORD:?DB_RELEASE_SECURITY_PASSWORD is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${DB_EXPECTED_SYSTEM_IDENTIFIER:?DB_EXPECTED_SYSTEM_IDENTIFIER is required}"

case "$DB_EXPECTED_SYSTEM_IDENTIFIER" in
  ''|*[!0-9]*)
    printf '%s\n' 'Release-security target identity is invalid.' >&2
    exit 1
    ;;
esac

# Refuse ambient libpq routing and session overrides. This provisioner is
# local-cluster-only and binds the target again inside its transaction.
if [ -n "${PGHOST:-}" ] || [ -n "${PGHOSTADDR:-}" ] ||
   [ -n "${PGPORT:-}" ] || [ -n "${PGDATABASE:-}" ] ||
   [ -n "${PGUSER:-}" ] || [ -n "${PGSERVICE:-}" ] ||
   [ -n "${PGSERVICEFILE:-}" ] || [ -n "${PGOPTIONS:-}" ] ||
   [ -n "${PGPASSWORD:-}" ] || [ -n "${PGPASSFILE:-}" ]; then
  printf '%s\n' 'Release-security provisioner refuses ambient libpq routing.' >&2
  exit 1
fi

release_security_password_size=$(
  printf '%s' "$DB_RELEASE_SECURITY_PASSWORD" | wc -c | tr -d ' '
)
release_security_password_without_forbidden_bytes=$(
  printf '%s' "$DB_RELEASE_SECURITY_PASSWORD" | LC_ALL=C tr -d '\r\n' |
    wc -c | tr -d ' '
)
case "$release_security_password_size" in
  ''|*[!0-9]*)
    printf '%s\n' 'Release-security database secret is invalid.' >&2
    exit 1
    ;;
esac
case "$DB_RELEASE_SECURITY_PASSWORD" in
  *[!A-Za-z0-9_-]*)
    printf '%s\n' 'Release-security database secret is invalid.' >&2
    exit 1
    ;;
esac
if [ "$release_security_password_size" -lt 43 ] ||
   [ "$release_security_password_size" -gt 128 ] ||
   [ "$release_security_password_size" -ne \
     "$release_security_password_without_forbidden_bytes" ]; then
  printf '%s\n' 'Release-security database secret must be an approved generated base64url value.' >&2
  exit 1
fi
unset release_security_password_size
unset release_security_password_without_forbidden_bytes

# Run only after the production-control migrations have completed. Migration
# v2 deliberately verifies the original three login principals before v3 makes
# this fourth, procedure-only security principal operational.
{
  printf '%s\n%s\n' \
    "$DB_RELEASE_SECURITY_PASSWORD" "$DB_RELEASE_SECURITY_PASSWORD"
} | psql -X --quiet --set ON_ERROR_STOP=1 \
  --no-psqlrc --host /var/run/postgresql --port 5432 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set expected_owner="$POSTGRES_USER" \
  --set expected_database="$POSTGRES_DB" \
  --set expected_system_identifier="$DB_EXPECTED_SYSTEM_IDENTIFIER" \
  --file=/dev/fd/3 3<<'SQL'
\set ECHO none
BEGIN;
SET LOCAL search_path = pg_catalog;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '180s';
SET LOCAL password_encryption = 'scram-sha-256';
SELECT pg_catalog.pg_advisory_xact_lock(73119, 2026072001);
SET LOCAL log_statement = 'none';
SET LOCAL log_min_duration_statement = -1;
SET LOCAL log_duration = FALSE;
SET LOCAL log_statement_stats = FALSE;
SET LOCAL log_min_error_statement = 'panic';
SET LOCAL track_activities = FALSE;
SET LOCAL pgaudit.log = 'none';
SET LOCAL pgaudit.log_parameter = FALSE;

SELECT pg_catalog.set_config(
  'quillmd.expected_owner', :'expected_owner', TRUE
);
SELECT pg_catalog.set_config(
  'quillmd.expected_database', :'expected_database', TRUE
);
SELECT pg_catalog.set_config(
  'quillmd.expected_system_identifier',
  :'expected_system_identifier',
  TRUE
);

DO $target_guard$
DECLARE
  expected_owner TEXT := pg_catalog.current_setting(
    'quillmd.expected_owner'
  );
  expected_database TEXT := pg_catalog.current_setting(
    'quillmd.expected_database'
  );
  expected_system_identifier TEXT := pg_catalog.current_setting(
    'quillmd.expected_system_identifier'
  );
BEGIN
  IF pg_catalog.current_setting('server_version_num')::integer
       NOT BETWEEN 160000 AND 169999
    OR pg_catalog.current_database() <> expected_database
    OR session_user::TEXT <> expected_owner
    OR current_user::TEXT <> expected_owner
    OR NOT EXISTS (
      SELECT 1
      FROM pg_catalog.pg_database database
      JOIN pg_catalog.pg_roles owner ON owner.oid = database.datdba
      WHERE database.datname = pg_catalog.current_database()
        AND owner.rolname = expected_owner
        AND owner.rolsuper
    )
    OR (
      SELECT control.system_identifier::TEXT
      FROM pg_catalog.pg_control_system() control
    ) <> expected_system_identifier
  THEN
    RAISE EXCEPTION 'Release-security target identity mismatch';
  END IF;
END
$target_guard$;

DO $preexisting_role_guard$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'quillmd_release_security'
      AND rolcanlogin = FALSE AND rolsuper = FALSE
      AND rolcreatedb = FALSE AND rolcreaterole = FALSE
      AND rolinherit = FALSE AND rolreplication = FALSE
      AND rolbypassrls = FALSE AND rolconnlimit = -1
      AND rolvaliduntil IS NULL AND rolconfig IS NULL
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_authid authentication
    WHERE authentication.rolname = 'quillmd_release_security'
      AND authentication.rolpassword IS NOT NULL
  ) OR EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'meddoc_release_security' AND (
      rolcanlogin = FALSE OR rolsuper OR rolcreatedb OR rolcreaterole
      OR rolinherit = FALSE OR rolreplication OR rolbypassrls
      OR rolconnlimit <> -1 OR rolvaliduntil IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname = 'meddoc_release_security'
      AND (
        login_role.rolconfig IS NOT NULL
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = login_role.oid
        )
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = login_role.oid
        )
      )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles boundary_role
    WHERE boundary_role.rolname = 'quillmd_release_security'
      AND (
        boundary_role.rolconfig IS NOT NULL
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = boundary_role.oid
        )
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = boundary_role.oid
            AND dependency.deptype <> 'a'
        )
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_user_mapping mapping
          WHERE mapping.umuser = boundary_role.oid
        )
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_policy policy
          WHERE boundary_role.oid = ANY(policy.polroles)
        )
      )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname = 'meddoc_release_security'
      AND (
        SELECT COUNT(*)
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles boundary
          ON boundary.oid = membership.roleid
        JOIN pg_catalog.pg_roles grantor
          ON grantor.oid = membership.grantor
        WHERE membership.member = login_role.oid
          AND boundary.rolname = 'quillmd_release_security'
          AND membership.admin_option = FALSE
          AND membership.inherit_option = TRUE
          AND membership.set_option = FALSE
          AND grantor.rolsuper = TRUE
      ) <> 1
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles granted ON granted.oid = membership.roleid
    JOIN pg_roles grantor ON grantor.oid = membership.grantor
    WHERE (
      member.rolname IN (
        'meddoc_release_security', 'quillmd_release_security'
      ) OR granted.rolname IN (
        'meddoc_release_security', 'quillmd_release_security'
      )
    ) AND (
      membership.admin_option OR NOT membership.inherit_option
      OR membership.set_option OR NOT grantor.rolsuper OR NOT (
        member.rolname = 'meddoc_release_security'
        AND granted.rolname = 'quillmd_release_security'
      )
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_class object
    JOIN pg_roles owner_role ON owner_role.oid = object.relowner
    WHERE owner_role.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_namespace object
    JOIN pg_roles owner_role ON owner_role.oid = object.nspowner
    WHERE owner_role.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_proc object
    JOIN pg_roles owner_role ON owner_role.oid = object.proowner
    WHERE owner_role.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_database object
    JOIN pg_roles owner_role ON owner_role.oid = object.datdba
    WHERE owner_role.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_class object
    CROSS JOIN LATERAL aclexplode(object.relacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_namespace object
    CROSS JOIN LATERAL aclexplode(object.nspacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_proc object
    CROSS JOIN LATERAL aclexplode(object.proacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1 FROM pg_database object
    CROSS JOIN LATERAL aclexplode(object.datacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname = 'meddoc_release_security'
  ) THEN
    RAISE EXCEPTION 'Refusing to reuse a non-exact Template Twin release-security principal';
  END IF;
END
$preexisting_role_guard$;

SELECT 'CREATE ROLE meddoc_release_security LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_release_security'
) \gexec

-- SQL stays on fd 3 while stdin supplies the two hidden fixed-role prompts.
-- Server statement/error/duration/pgaudit/activity paths are disabled above.
\password meddoc_release_security

SELECT 'GRANT quillmd_release_security TO meddoc_release_security WITH ADMIN FALSE, INHERIT TRUE, SET FALSE'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_auth_members membership
  WHERE membership.member = 'meddoc_release_security'::pg_catalog.regrole
    AND membership.roleid = 'quillmd_release_security'::pg_catalog.regrole
) \gexec

DO $postcondition$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles boundary_role
    WHERE boundary_role.rolname = 'quillmd_release_security'
      AND boundary_role.rolcanlogin = FALSE
      AND boundary_role.rolsuper = FALSE
      AND boundary_role.rolcreatedb = FALSE
      AND boundary_role.rolcreaterole = FALSE
      AND boundary_role.rolinherit = FALSE
      AND boundary_role.rolreplication = FALSE
      AND boundary_role.rolbypassrls = FALSE
      AND boundary_role.rolconnlimit = -1
      AND boundary_role.rolvaliduntil IS NULL
      AND boundary_role.rolconfig IS NULL
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_authid authentication
    WHERE authentication.rolname = 'quillmd_release_security'
      AND authentication.rolpassword IS NOT NULL
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname = 'meddoc_release_security'
      AND login_role.rolcanlogin
      AND login_role.rolsuper = FALSE
      AND login_role.rolcreatedb = FALSE
      AND login_role.rolcreaterole = FALSE
      AND login_role.rolinherit
      AND login_role.rolreplication = FALSE
      AND login_role.rolbypassrls = FALSE
      AND login_role.rolconnlimit = -1
      AND login_role.rolvaliduntil IS NULL
      AND login_role.rolconfig IS NULL
  ) OR (
    SELECT COUNT(*) FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles granted ON granted.oid = membership.roleid
    JOIN pg_roles grantor ON grantor.oid = membership.grantor
    WHERE member.rolname = 'meddoc_release_security'
      AND granted.rolname = 'quillmd_release_security'
      AND membership.admin_option = FALSE
      AND membership.inherit_option = TRUE
      AND membership.set_option = FALSE
      AND grantor.rolsuper = TRUE
  ) <> 1 OR (
    SELECT COUNT(*) FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles granted ON granted.oid = membership.roleid
    WHERE member.rolname IN (
      'meddoc_release_security', 'quillmd_release_security'
    ) OR granted.rolname IN (
      'meddoc_release_security', 'quillmd_release_security'
    )
  ) <> 1 OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_authid login_role
    WHERE login_role.rolname = 'meddoc_release_security'
      AND COALESCE(login_role.rolpassword, '') NOT LIKE 'SCRAM-SHA-256$4096:%'
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname = 'meddoc_release_security'
      AND (
        login_role.rolconfig IS NOT NULL
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = login_role.oid
        )
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = login_role.oid
        )
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin release-security membership is not exact';
  END IF;
END
$postcondition$;
COMMIT;
SQL

trap - EXIT HUP INT TERM
clear_release_security_password
