#!/bin/sh
set -eu

: "${DB_RUNTIME_PASSWORD:?DB_RUNTIME_PASSWORD is required}"
: "${DB_RELEASE_CONTROL_PASSWORD:?DB_RELEASE_CONTROL_PASSWORD is required}"
: "${DB_AUDIT_DISPATCHER_PASSWORD:?DB_AUDIT_DISPATCHER_PASSWORD is required}"
: "${DB_AUTH_EMAIL_DISPATCHER_PASSWORD:?DB_AUTH_EMAIL_DISPATCHER_PASSWORD is required}"

# Fresh-database bootstrap only. Existing production databases use the
# reviewed role-provisioning block in the release runbook. Quiet mode and
# psql variables keep credentials out of command lines and logs.
psql --quiet --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set runtime_password="$DB_RUNTIME_PASSWORD" \
  --set release_control_password="$DB_RELEASE_CONTROL_PASSWORD" \
  --set audit_dispatcher_password="$DB_AUDIT_DISPATCHER_PASSWORD" \
  --set auth_email_dispatcher_password="$DB_AUTH_EMAIL_DISPATCHER_PASSWORD" <<'SQL'
DO $roles$
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
END
$roles$;

DO $preexisting_role_guard$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_roles role
    WHERE role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
      'quillmd_audit_dispatcher', 'quillmd_auth_email_dispatcher'
    ) AND (
      role.rolcanlogin OR role.rolsuper OR role.rolcreatedb
      OR role.rolcreaterole OR role.rolinherit OR role.rolreplication
      OR role.rolbypassrls
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_roles role
    WHERE role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher'
    )
      AND (
        NOT role.rolcanlogin OR role.rolsuper OR role.rolcreatedb
        OR role.rolcreaterole OR NOT role.rolinherit OR role.rolreplication
        OR role.rolbypassrls
      )
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members membership
    JOIN pg_roles member_role ON member_role.oid = membership.member
    JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
    WHERE (
      member_role.rolname = 'meddoc_runtime'
      AND granted_role.rolname <> 'quillmd_runtime'
    ) OR (
      member_role.rolname = 'meddoc_release_control'
      AND granted_role.rolname <> 'quillmd_release_control'
    ) OR (
      member_role.rolname = 'meddoc_audit_dispatcher'
      AND granted_role.rolname <> 'quillmd_audit_dispatcher'
    ) OR (
      member_role.rolname = 'meddoc_auth_email_dispatcher'
      AND granted_role.rolname <> 'quillmd_auth_email_dispatcher'
    ) OR (
      member_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_audit_dispatcher', 'meddoc_auth_email_dispatcher'
      ) AND membership.admin_option
    ) OR member_role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
      'quillmd_audit_dispatcher', 'quillmd_auth_email_dispatcher'
    )
  ) THEN
    RAISE EXCEPTION 'Refusing to reuse a non-exact Template Twin database principal';
  END IF;
END
$preexisting_role_guard$;

SELECT format(
  'CREATE ROLE meddoc_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS',
  :'runtime_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_runtime') \gexec

SELECT format(
  'CREATE ROLE meddoc_release_control LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS',
  :'release_control_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_release_control') \gexec

SELECT format(
  'CREATE ROLE meddoc_audit_dispatcher LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS',
  :'audit_dispatcher_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_audit_dispatcher') \gexec

SELECT format(
  'CREATE ROLE meddoc_auth_email_dispatcher LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS',
  :'auth_email_dispatcher_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_auth_email_dispatcher') \gexec

SELECT format('ALTER ROLE meddoc_runtime PASSWORD %L', :'runtime_password') \gexec
SELECT format(
  'ALTER ROLE meddoc_release_control PASSWORD %L', :'release_control_password'
) \gexec
SELECT format(
  'ALTER ROLE meddoc_audit_dispatcher PASSWORD %L', :'audit_dispatcher_password'
) \gexec
SELECT format(
  'ALTER ROLE meddoc_auth_email_dispatcher PASSWORD %L',
  :'auth_email_dispatcher_password'
) \gexec

GRANT quillmd_runtime TO meddoc_runtime;
GRANT quillmd_release_control TO meddoc_release_control;
GRANT quillmd_audit_dispatcher TO meddoc_audit_dispatcher;
GRANT quillmd_auth_email_dispatcher TO meddoc_auth_email_dispatcher;
SQL
