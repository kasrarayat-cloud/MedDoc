#!/bin/sh
set -eu

: "${DB_RELEASE_SECURITY_PASSWORD:?DB_RELEASE_SECURITY_PASSWORD is required}"

# Run only after the production-control migrations have completed. Migration
# v2 deliberately verifies the original three login principals before v3 makes
# this fourth, procedure-only security principal operational.
psql --quiet --set ON_ERROR_STOP=1 \
  --set release_security_password="$DB_RELEASE_SECURITY_PASSWORD" <<'SQL'
DO $preexisting_role_guard$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'quillmd_release_security'
      AND rolcanlogin = FALSE AND rolsuper = FALSE
      AND rolcreatedb = FALSE AND rolcreaterole = FALSE
      AND rolinherit = FALSE AND rolreplication = FALSE
      AND rolbypassrls = FALSE
  ) OR EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'meddoc_release_security' AND (
      rolcanlogin = FALSE OR rolsuper OR rolcreatedb OR rolcreaterole
      OR rolinherit = FALSE OR rolreplication OR rolbypassrls
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles granted ON granted.oid = membership.roleid
    WHERE member.rolname = 'meddoc_release_security'
      AND granted.rolname <> 'quillmd_release_security'
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

SELECT format(
  'CREATE ROLE meddoc_release_security LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS',
  :'release_security_password'
) WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'meddoc_release_security'
) \gexec

SELECT format(
  'ALTER ROLE meddoc_release_security PASSWORD %L',
  :'release_security_password'
) \gexec

GRANT quillmd_release_security TO meddoc_release_security;

DO $postcondition$
BEGIN
  IF (
    SELECT COUNT(*) FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles granted ON granted.oid = membership.roleid
    WHERE member.rolname = 'meddoc_release_security'
      AND granted.rolname = 'quillmd_release_security'
  ) <> 1 OR (
    SELECT COUNT(*) FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    WHERE member.rolname = 'meddoc_release_security'
  ) <> 1 THEN
    RAISE EXCEPTION 'Template Twin release-security membership is not exact';
  END IF;
END
$postcondition$;
SQL
