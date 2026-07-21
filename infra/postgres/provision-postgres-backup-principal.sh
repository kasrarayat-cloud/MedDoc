#!/bin/sh
set -eu
set +x
umask 077

# Data-bearing and fresh-install provisioner for the dedicated PostgreSQL
# backup login. The caller supplies only a Docker/Kubernetes-style secret-file
# path; the credential is never accepted as a command-line argument.

fail() {
  printf '%s\n' 'postgres-backup-principal: FAIL' >&2
  exit 1
}

cleanup() {
  unset DB_BACKUP_PASSWORD secret_size stripped_size
}
trap cleanup EXIT HUP INT TERM

[ -n "${DB_BACKUP_PASSWORD_FILE:-}" ] || fail
[ -n "${POSTGRES_USER:-}" ] || fail
[ -n "${POSTGRES_DB:-}" ] || fail
[ -n "${DB_EXPECTED_SYSTEM_IDENTIFIER:-}" ] || fail
case "$DB_EXPECTED_SYSTEM_IDENTIFIER" in
  ''|*[!0-9]*) fail ;;
esac

# The data-bearing provisioner is local-cluster-only. Refuse ambient libpq
# routing or session overrides instead of allowing an operator shell to select
# a different server with the same database and role names.
[ -z "${PGHOST:-}" ] || fail
[ -z "${PGHOSTADDR:-}" ] || fail
[ -z "${PGPORT:-}" ] || fail
[ -z "${PGDATABASE:-}" ] || fail
[ -z "${PGUSER:-}" ] || fail
[ -z "${PGSERVICE:-}" ] || fail
[ -z "${PGSERVICEFILE:-}" ] || fail
[ -z "${PGOPTIONS:-}" ] || fail

[ -f "$DB_BACKUP_PASSWORD_FILE" ] || fail
[ -r "$DB_BACKUP_PASSWORD_FILE" ] || fail

secret_size=$(wc -c 2>/dev/null < "$DB_BACKUP_PASSWORD_FILE") || fail
secret_size=$(printf '%s' "$secret_size" | tr -d '[:space:]')
case "$secret_size" in
  ''|*[!0-9]*) fail ;;
esac
[ "$secret_size" -ge 43 ] || fail
[ "$secret_size" -le 128 ] || fail
LC_ALL=C grep -Eq '^[A-Za-z0-9_-]{43,128}$' \
  "$DB_BACKUP_PASSWORD_FILE" 2>/dev/null || fail

# Docker secret files used for database passwords must contain exactly the
# password bytes. POSIX environment variables cannot preserve NUL, and command
# substitution strips trailing newlines, so reject NUL/CR/LF before reading.
stripped_size=$(LC_ALL=C tr -d '\000\r\n' 2>/dev/null < "$DB_BACKUP_PASSWORD_FILE" | wc -c) || fail
stripped_size=$(printf '%s' "$stripped_size" | tr -d '[:space:]')
[ "$stripped_size" = "$secret_size" ] || fail

DB_BACKUP_PASSWORD=$(cat "$DB_BACKUP_PASSWORD_FILE" 2>/dev/null) || fail

if ! {
  printf '%s\n%s\n' "$DB_BACKUP_PASSWORD" "$DB_BACKUP_PASSWORD"
} | psql -X --no-psqlrc --quiet --set ON_ERROR_STOP=1 \
  --host /var/run/postgresql --port 5432 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set expected_owner="$POSTGRES_USER" \
  --set expected_system_identifier="$DB_EXPECTED_SYSTEM_IDENTIFIER" \
  --file=/dev/fd/3 >/dev/null 2>&1 3<<'SQL'
\set ECHO none
BEGIN;
SET LOCAL search_path = pg_catalog;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '180s';
SET LOCAL password_encryption = 'scram-sha-256';
-- psql's client-side password command sends only a SCRAM verifier. Keep that
-- verifier out of statement/error/duration and installed pgaudit logs; the
-- transaction's fixed PASS/FAIL result and postcondition hashes are the audit
-- evidence for this narrowly scoped bootstrap operation.
SET LOCAL log_statement = 'none';
SET LOCAL log_min_duration_statement = -1;
SET LOCAL log_duration = FALSE;
SET LOCAL log_min_error_statement = 'panic';
SET LOCAL pgaudit.log = 'none';
SET LOCAL track_activities = FALSE;
SELECT pg_catalog.set_config(
  'quillmd.expected_system_identifier', :'expected_system_identifier', TRUE
);
SELECT pg_catalog.set_config('quillmd.expected_owner', :'expected_owner', TRUE);
SELECT pg_catalog.pg_try_advisory_xact_lock(73119, 2026072001)
  AS release_lock_acquired \gset
\if :release_lock_acquired
\else
  DO $release_lock_required$
  BEGIN
    RAISE EXCEPTION 'Database-principal release lock is unavailable';
  END
  $release_lock_required$;
\endif

CREATE OR REPLACE FUNCTION pg_temp.quillmd_application_role_graph_is_exact()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = pg_catalog
AS $application_role_graph$
  WITH expected(member_name, boundary_name, required) AS (
    VALUES
      ('meddoc_runtime', 'quillmd_runtime', TRUE),
      ('meddoc_release_control', 'quillmd_release_control', TRUE),
      ('meddoc_audit_dispatcher', 'quillmd_audit_dispatcher', TRUE),
      ('meddoc_auth_email_dispatcher', 'quillmd_auth_email_dispatcher', TRUE),
      ('meddoc_release_security', 'quillmd_release_security', FALSE)
  ), expected_present AS (
    SELECT expected.*
    FROM expected
    WHERE expected.required OR EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles role
      WHERE role.rolname = expected.member_name
    )
  )
  SELECT NOT EXISTS (
    SELECT 1
    FROM expected
    LEFT JOIN pg_catalog.pg_roles boundary_role
      ON boundary_role.rolname = expected.boundary_name
    WHERE boundary_role.oid IS NULL
       OR boundary_role.rolcanlogin
       OR boundary_role.rolsuper
       OR boundary_role.rolcreatedb
       OR boundary_role.rolcreaterole
       OR boundary_role.rolinherit
       OR boundary_role.rolreplication
       OR boundary_role.rolbypassrls
       OR boundary_role.rolconnlimit <> -1
       OR boundary_role.rolconfig IS NOT NULL
       OR boundary_role.rolvaliduntil IS NOT NULL
       OR EXISTS (
         SELECT 1 FROM pg_catalog.pg_authid authentication
         WHERE authentication.oid = boundary_role.oid
           AND authentication.rolpassword IS NOT NULL
       )
  ) AND NOT EXISTS (
    SELECT 1
    FROM expected_present
    LEFT JOIN pg_catalog.pg_roles login_role
      ON login_role.rolname = expected_present.member_name
    WHERE login_role.oid IS NULL
       OR login_role.rolcanlogin = FALSE
       OR login_role.rolsuper
       OR login_role.rolcreatedb
       OR login_role.rolcreaterole
       OR login_role.rolinherit = FALSE
       OR login_role.rolreplication
       OR login_role.rolbypassrls
       OR login_role.rolconnlimit <> -1
       OR login_role.rolconfig IS NOT NULL
       OR login_role.rolvaliduntil IS NOT NULL
  ) AND NOT EXISTS (
    SELECT 1
    FROM expected_present
    JOIN pg_catalog.pg_roles login_role
      ON login_role.rolname = expected_present.member_name
    WHERE EXISTS (
      SELECT 1 FROM pg_catalog.pg_db_role_setting setting
      WHERE setting.setrole = login_role.oid
    ) OR EXISTS (
      SELECT 1 FROM pg_catalog.pg_shdepend dependency
      WHERE dependency.refclassid =
          'pg_catalog.pg_authid'::pg_catalog.regclass
        AND dependency.refobjid = login_role.oid
    )
  ) AND NOT EXISTS (
    SELECT 1
    FROM expected_present
    WHERE (
      SELECT COUNT(*)
      FROM pg_catalog.pg_auth_members membership
      JOIN pg_catalog.pg_roles member_role
        ON member_role.oid = membership.member
      JOIN pg_catalog.pg_roles granted_role
        ON granted_role.oid = membership.roleid
      JOIN pg_catalog.pg_roles grantor_role
        ON grantor_role.oid = membership.grantor
      WHERE member_role.rolname = expected_present.member_name
        AND granted_role.rolname = expected_present.boundary_name
        AND membership.admin_option = FALSE
        AND membership.inherit_option = TRUE
        AND membership.set_option = FALSE
        AND grantor_role.rolsuper
    ) <> 1
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role
      ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor_role
      ON grantor_role.oid = membership.grantor
    WHERE (
      member_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher', 'quillmd_runtime',
        'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher', 'quillmd_auth_email_dispatcher'
      ) OR granted_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher', 'quillmd_runtime',
        'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher', 'quillmd_auth_email_dispatcher'
      ) OR grantor_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher', 'quillmd_runtime',
        'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher', 'quillmd_auth_email_dispatcher'
      )
    ) AND NOT EXISTS (
      SELECT 1 FROM expected_present
      WHERE expected_present.member_name = member_role.rolname
        AND expected_present.boundary_name = granted_role.rolname
        AND membership.admin_option = FALSE
        AND membership.inherit_option = TRUE
        AND membership.set_option = FALSE
        AND grantor_role.rolsuper
    )
  );
$application_role_graph$;

-- Exact v9 installations grant the backup boundary EXECUTE on one narrowly
-- scoped fixed-role credential helper. That function never returns a verifier,
-- and its ACL creates a pg_shdepend row
-- for quillmd_backup.  Treat it as reviewed only while the complete helper
-- definition, owner, configuration, and ACL remain frozen; an absent helper
-- is valid before v9, but no dependency is then allowlisted.
CREATE OR REPLACE FUNCTION pg_temp.quillmd_backup_password_helper_is_exact()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = pg_catalog
AS $backup_password_helper$
  WITH selected AS (
    SELECT database_object.oid AS database_oid,
      database_object.datdba AS database_owner_oid
    FROM pg_catalog.pg_database database_object
    WHERE database_object.datname = pg_catalog.current_database()
  ), helper AS (
    SELECT routine.*, namespace_object.nspname, language_object.lanname,
      selected.database_oid, selected.database_owner_oid
    FROM selected
    JOIN pg_catalog.pg_proc routine
      ON routine.oid = pg_catalog.to_regprocedure(
        'public.quillmd_boundary_password_is_null(text)'
      )
    JOIN pg_catalog.pg_namespace namespace_object
      ON namespace_object.oid = routine.pronamespace
    JOIN pg_catalog.pg_language language_object
      ON language_object.oid = routine.prolang
  ), helper_acl AS (
    SELECT privilege.*
    FROM helper
    CROSS JOIN LATERAL pg_catalog.aclexplode(helper.proacl) privilege
  ), expected_grantees AS (
    SELECT role.oid
    FROM pg_catalog.pg_roles role
    WHERE role.rolname IN (
      'quillmd_runtime',
      'quillmd_release_control',
      'quillmd_release_security',
      'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher',
      'quillmd_backup'
    )
    UNION
    SELECT selected.database_owner_oid FROM selected
  )
  SELECT
    (SELECT pg_catalog.count(*) FROM helper) = 1
    AND NOT EXISTS (
      SELECT 1
      FROM helper
      WHERE helper.nspname <> 'public'
         OR helper.proname <> 'quillmd_boundary_password_is_null'
         OR helper.proowner <> helper.database_owner_oid
         OR NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_roles database_owner
              WHERE database_owner.oid = helper.database_owner_oid
                AND database_owner.rolsuper
            )
         OR helper.lanname <> 'sql'
         OR helper.prokind <> 'f'
         OR helper.prosecdef = FALSE
         OR helper.proleakproof
         OR helper.proisstrict
         OR helper.proretset
         OR helper.provolatile <> 's'
         OR helper.proparallel <> 'u'
         OR helper.procost <> 100
         OR helper.prorows <> 0
         OR helper.prosupport <> 0
         OR helper.provariadic <> 0
         OR helper.prorettype <> 'pg_catalog.bool'::pg_catalog.regtype
         OR helper.pronargs <> 1
         OR helper.pronargdefaults <> 0
         OR helper.proargdefaults IS NOT NULL
         OR helper.proargtypes <> '25'::pg_catalog.oidvector
         OR helper.proallargtypes IS NOT NULL
         OR helper.proargmodes IS NOT NULL
         OR helper.proargnames IS DISTINCT FROM ARRAY['boundary_name']::TEXT[]
         OR helper.protrftypes IS NOT NULL
         OR helper.proconfig IS DISTINCT FROM
              ARRAY['search_path=pg_catalog, public, pg_temp']::TEXT[]
         OR helper.proacl IS NULL
         OR helper.probin IS NOT NULL
         OR helper.prosqlbody IS NOT NULL
         OR pg_catalog.pg_get_function_identity_arguments(helper.oid)
              <> 'boundary_name text'
         OR pg_catalog.pg_get_function_arguments(helper.oid)
              <> 'boundary_name text'
         OR pg_catalog.pg_get_function_result(helper.oid) <> 'boolean'
         OR pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
              helper.prosrc, 'UTF8'
            )), 'hex') <>
              '4e96e14b9bd337559df5a178a83d76490fa6cba73aed3ced3b2c4a4da644ee01'
         OR EXISTS (
              SELECT 1
              FROM pg_catalog.pg_depend dependency
              WHERE dependency.classid =
                  'pg_catalog.pg_proc'::pg_catalog.regclass
                AND dependency.objid = helper.oid
                AND dependency.refclassid =
                  'pg_catalog.pg_extension'::pg_catalog.regclass
                AND dependency.deptype = 'e'
            )
    )
    AND (SELECT pg_catalog.count(*) FROM expected_grantees) = 7
    AND (SELECT pg_catalog.count(*) FROM helper_acl) = 7
    AND NOT EXISTS (
      SELECT 1
      FROM helper_acl
      CROSS JOIN selected
      WHERE helper_acl.grantor <> selected.database_owner_oid
         OR helper_acl.privilege_type <> 'EXECUTE'
         OR helper_acl.is_grantable
         OR NOT EXISTS (
              SELECT 1 FROM expected_grantees
              WHERE expected_grantees.oid = helper_acl.grantee
            )
    )
    AND NOT EXISTS (
      SELECT 1
      FROM expected_grantees
      WHERE NOT EXISTS (
        SELECT 1 FROM helper_acl
        WHERE helper_acl.grantee = expected_grantees.oid
      )
    );
$backup_password_helper$;

CREATE OR REPLACE FUNCTION pg_temp.quillmd_exact_principal_v9_stage()
RETURNS TEXT
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog
AS $v9_stage$
DECLARE
  migration_relation_oid OID := pg_catalog.to_regclass(
    'public._prisma_migrations'
  );
  marker_count BIGINT := 0;
  exact_marker_count BIGINT := 0;
  relation_is_exact BOOLEAN := FALSE;
BEGIN
  -- Fresh bootstrap provisions the cluster role before Prisma creates its
  -- migration ledger. That is the only accepted ledger-absent state.
  IF migration_relation_oid IS NULL THEN
    RETURN 'pre-v9';
  END IF;

  WITH expected_attribute(
    attnum, attname, atttypid, atttypmod, attnotnull, atthasdef,
    attcollation
  ) AS (
    VALUES
      (1, 'id', 'pg_catalog.varchar'::pg_catalog.regtype, 40, TRUE, FALSE,
        pg_catalog.to_regcollation('pg_catalog."default"')),
      (2, 'checksum', 'pg_catalog.varchar'::pg_catalog.regtype, 68, TRUE,
        FALSE, pg_catalog.to_regcollation('pg_catalog."default"')),
      (3, 'finished_at', 'pg_catalog.timestamptz'::pg_catalog.regtype, -1,
        FALSE, FALSE, 0::pg_catalog.oid),
      (4, 'migration_name', 'pg_catalog.varchar'::pg_catalog.regtype, 259,
        TRUE, FALSE, pg_catalog.to_regcollation('pg_catalog."default"')),
      (5, 'logs', 'pg_catalog.text'::pg_catalog.regtype, -1, FALSE, FALSE,
        pg_catalog.to_regcollation('pg_catalog."default"')),
      (6, 'rolled_back_at', 'pg_catalog.timestamptz'::pg_catalog.regtype, -1,
        FALSE, FALSE, 0::pg_catalog.oid),
      (7, 'started_at', 'pg_catalog.timestamptz'::pg_catalog.regtype, -1,
        TRUE, TRUE, 0::pg_catalog.oid),
      (8, 'applied_steps_count', 'pg_catalog.int4'::pg_catalog.regtype, -1,
        TRUE, TRUE, 0::pg_catalog.oid)
  )
  SELECT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_class relation
    JOIN pg_catalog.pg_namespace namespace_object
      ON namespace_object.oid = relation.relnamespace
    JOIN pg_catalog.pg_database database_object
      ON database_object.datname = pg_catalog.current_database()
    JOIN pg_catalog.pg_am access_method
      ON access_method.oid = relation.relam
    WHERE relation.oid = migration_relation_oid
      AND namespace_object.nspname = 'public'
      AND relation.relname = '_prisma_migrations'
      AND relation.relkind = 'r'
      AND relation.relpersistence = 'p'
      AND relation.relowner = database_object.datdba
      AND access_method.amname = 'heap'
      AND relation.relrowsecurity = FALSE
      AND relation.relforcerowsecurity = FALSE
      AND relation.relhasrules = FALSE
      AND relation.relhastriggers = FALSE
      AND relation.relhassubclass = FALSE
      AND relation.relispartition = FALSE
      AND relation.relpartbound IS NULL
      AND relation.reloftype = 0
      AND relation.reloptions IS NULL
      AND relation.relreplident = 'd'
  )
  AND (
    SELECT pg_catalog.count(*)
    FROM pg_catalog.pg_attribute attribute
    WHERE attribute.attrelid = migration_relation_oid
      AND attribute.attnum > 0
      AND attribute.attisdropped = FALSE
  ) = 8
  AND NOT EXISTS (
    SELECT 1
    FROM expected_attribute expected
    WHERE NOT EXISTS (
      SELECT 1
      FROM pg_catalog.pg_attribute attribute
      WHERE attribute.attrelid = migration_relation_oid
        AND attribute.attnum = expected.attnum
        AND attribute.attname = expected.attname
        AND attribute.atttypid = expected.atttypid
        AND attribute.atttypmod = expected.atttypmod
        AND attribute.attnotnull = expected.attnotnull
        AND attribute.atthasdef = expected.atthasdef
        AND attribute.attcollation = expected.attcollation
        AND attribute.attisdropped = FALSE
        AND attribute.attislocal
        AND attribute.attinhcount = 0
        AND attribute.attidentity = ''
        AND attribute.attgenerated = ''
        AND attribute.atthasmissing = FALSE
        AND attribute.attacl IS NULL
        AND attribute.attoptions IS NULL
        AND attribute.attfdwoptions IS NULL
    )
  )
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_trigger trigger_object
    WHERE trigger_object.tgrelid = migration_relation_oid
  )
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_rewrite rule
    WHERE rule.ev_class = migration_relation_oid
  )
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_policy policy
    WHERE policy.polrelid = migration_relation_oid
  )
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_inherits inheritance
    WHERE inheritance.inhrelid = migration_relation_oid
       OR inheritance.inhparent = migration_relation_oid
  )
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_partitioned_table partitioned
    WHERE partitioned.partrelid = migration_relation_oid
  )
  AND (
    SELECT pg_catalog.count(*) FROM pg_catalog.pg_index index_object
    WHERE index_object.indrelid = migration_relation_oid
  ) = 1
  AND (
    SELECT pg_catalog.count(*) FROM pg_catalog.pg_constraint constraint_object
    WHERE constraint_object.conrelid = migration_relation_oid
  ) = 1
  AND EXISTS (
    SELECT 1
    FROM pg_catalog.pg_index index_object
    JOIN pg_catalog.pg_class index_relation
      ON index_relation.oid = index_object.indexrelid
    JOIN pg_catalog.pg_namespace index_namespace
      ON index_namespace.oid = index_relation.relnamespace
    JOIN pg_catalog.pg_am index_access_method
      ON index_access_method.oid = index_relation.relam
    JOIN pg_catalog.pg_opclass operator_class
      ON operator_class.oid = index_object.indclass[0]
    JOIN pg_catalog.pg_namespace operator_namespace
      ON operator_namespace.oid = operator_class.opcnamespace
    JOIN pg_catalog.pg_database database_object
      ON database_object.datname = pg_catalog.current_database()
    JOIN pg_catalog.pg_constraint constraint_object
      ON constraint_object.conrelid = migration_relation_oid
     AND constraint_object.conindid = index_relation.oid
    WHERE index_object.indrelid = migration_relation_oid
      AND index_relation.relname = '_prisma_migrations_pkey'
      AND index_namespace.nspname = 'public'
      AND index_relation.relowner = database_object.datdba
      AND index_relation.relkind = 'i'
      AND index_relation.relpersistence = 'p'
      AND index_relation.relispartition = FALSE
      AND index_relation.reloptions IS NULL
      AND index_access_method.amname = 'btree'
      AND index_object.indisunique
      AND index_object.indisprimary
      AND index_object.indisvalid
      AND index_object.indisready
      AND index_object.indislive
      AND index_object.indisreplident = FALSE
      AND index_object.indimmediate
      AND index_object.indisclustered = FALSE
      AND index_object.indcheckxmin = FALSE
      AND index_object.indnatts = 1
      AND index_object.indnkeyatts = 1
      AND index_object.indkey::TEXT = '1'
      AND index_object.indcollation[0] =
        pg_catalog.to_regcollation('pg_catalog."default"')
      AND operator_namespace.nspname = 'pg_catalog'
      AND operator_class.opcname = 'text_ops'
      AND index_object.indoption[0] = 0
      AND index_object.indexprs IS NULL
      AND index_object.indpred IS NULL
      AND constraint_object.conname = '_prisma_migrations_pkey'
      AND constraint_object.contype = 'p'
      AND constraint_object.condeferrable = FALSE
      AND constraint_object.condeferred = FALSE
      AND constraint_object.convalidated
      AND constraint_object.connoinherit
      AND constraint_object.conislocal
      AND constraint_object.coninhcount = 0
      AND constraint_object.conparentid = 0
      AND constraint_object.confrelid = 0
      AND constraint_object.conkey = ARRAY[1]::SMALLINT[]
      AND constraint_object.conbin IS NULL
  ) INTO relation_is_exact;
  IF relation_is_exact IS DISTINCT FROM TRUE THEN
    RETURN 'invalid';
  END IF;

  EXECUTE $marker$
    SELECT pg_catalog.count(*),
      pg_catalog.count(*) FILTER (
        WHERE checksum =
            '8d2c4fe1075490085b34397cdecde3d8c6e50b3e21c778ac9d491da071faf404'
          AND started_at IS NOT NULL
          AND finished_at IS NOT NULL
          AND finished_at >= started_at
          AND rolled_back_at IS NULL
          AND logs IS NULL
          AND applied_steps_count = 1
      )
    FROM public."_prisma_migrations"
    WHERE migration_name =
      '20260720213000_exact_database_principal_closure_v9'
  $marker$ INTO marker_count, exact_marker_count;

  IF marker_count = 0 THEN
    RETURN 'pre-v9';
  END IF;
  IF marker_count = 1 AND exact_marker_count = 1 THEN
    RETURN 'post-v9';
  END IF;
  RETURN 'invalid';
END;
$v9_stage$;

CREATE OR REPLACE FUNCTION
  pg_temp.quillmd_backup_password_helper_dependency_count()
RETURNS BIGINT
LANGUAGE sql
STABLE
SET search_path = pg_catalog
AS $helper_dependency_count$
  SELECT pg_catalog.count(*)
  FROM pg_catalog.pg_shdepend dependency
  JOIN pg_catalog.pg_roles backup_boundary
    ON backup_boundary.oid = dependency.refobjid
   AND backup_boundary.rolname = 'quillmd_backup'
  JOIN pg_catalog.pg_database database_object
    ON database_object.datname = pg_catalog.current_database()
  WHERE dependency.dbid = database_object.oid
    AND dependency.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
    AND dependency.objid = pg_catalog.to_regprocedure(
      'public.quillmd_boundary_password_is_null(text)'
    )
    AND dependency.objsubid = 0
    AND dependency.refclassid =
      'pg_catalog.pg_authid'::pg_catalog.regclass
    AND dependency.deptype = 'a';
$helper_dependency_count$;

CREATE OR REPLACE FUNCTION
  pg_temp.quillmd_backup_password_helper_stage_is_exact()
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog
AS $helper_stage$
DECLARE
  migration_stage TEXT := pg_temp.quillmd_exact_principal_v9_stage();
  boundary_result BOOLEAN := FALSE;
  login_result BOOLEAN := FALSE;
BEGIN
  IF migration_stage = 'pre-v9' THEN
    RETURN pg_catalog.to_regprocedure(
        'public.quillmd_boundary_password_is_null(text)'
      ) IS NULL
      AND pg_temp.quillmd_backup_password_helper_dependency_count() = 0;
  END IF;
  IF migration_stage <> 'post-v9'
     OR NOT pg_temp.quillmd_backup_password_helper_is_exact()
     OR pg_temp.quillmd_backup_password_helper_dependency_count() <> 1
  THEN
    RETURN FALSE;
  END IF;
  EXECUTE $call_helper$
    SELECT public.quillmd_boundary_password_is_null('quillmd_backup')
  $call_helper$ INTO boundary_result;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.rolname = 'meddoc_backup'
  ) THEN
    EXECUTE $call_helper$
      SELECT public.quillmd_boundary_password_is_null('meddoc_backup')
    $call_helper$ INTO login_result;
  ELSE
    -- Cluster roles are not contained in a database archive. A restored v9
    -- database can therefore carry the frozen helper before this provisioner
    -- recreates the fixed backup login and installs its SCRAM verifier.
    login_result := TRUE;
  END IF;
  RETURN boundary_result IS TRUE AND login_result IS TRUE;
END;
$helper_stage$;

DO $precondition$
DECLARE
  backup_database_oid OID := (
    SELECT oid FROM pg_catalog.pg_database
    WHERE datname = pg_catalog.current_database()
  );
BEGIN
  IF pg_catalog.pg_is_in_recovery() THEN
    RAISE EXCEPTION 'Backup-principal provisioning requires the primary';
  END IF;

  IF NOT pg_temp.quillmd_backup_password_helper_stage_is_exact() THEN
    RAISE EXCEPTION 'Backup helper migration stage is not exact';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.rolname = CURRENT_USER
      AND role.rolname = SESSION_USER
      AND role.rolname = pg_catalog.current_setting(
        'quillmd.expected_owner', FALSE
      )
      AND role.rolsuper
  ) THEN
    RAISE EXCEPTION 'Backup-principal provisioning requires a superuser';
  END IF;

  IF (
    SELECT system_identifier::pg_catalog.text
    FROM pg_catalog.pg_control_system()
  ) <> pg_catalog.current_setting(
    'quillmd.expected_system_identifier', FALSE
  ) THEN
    RAISE EXCEPTION 'Backup-principal target cluster is not approved';
  END IF;

  IF (
    SELECT COUNT(*)
    FROM pg_catalog.pg_roles role
    WHERE role.rolname IN (
      'quillmd_runtime',
      'quillmd_release_control',
      'quillmd_release_security',
      'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher'
    )
      AND role.rolcanlogin = FALSE
      AND role.rolsuper = FALSE
      AND role.rolcreatedb = FALSE
      AND role.rolcreaterole = FALSE
      AND role.rolinherit = FALSE
      AND role.rolreplication = FALSE
      AND role.rolbypassrls = FALSE
  ) <> 5 THEN
    RAISE EXCEPTION 'Required database-principal boundaries are not exact';
  END IF;

  IF NOT pg_temp.quillmd_application_role_graph_is_exact() THEN
    RAISE EXCEPTION 'Application database-principal graph is not exact';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_stat_activity activity
    WHERE activity.pid <> pg_catalog.pg_backend_pid()
      AND activity.usename IN (
        'meddoc_runtime',
        'meddoc_release_control',
        'meddoc_release_security',
        'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher',
        'meddoc_backup'
      )
  ) THEN
    RAISE EXCEPTION 'Trusted login sessions must be drained before cluster ACL provisioning';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.rolname = 'quillmd_backup'
      AND (
        role.rolcanlogin OR role.rolsuper OR role.rolcreatedb
        OR role.rolcreaterole OR role.rolinherit OR role.rolreplication
        OR role.rolbypassrls OR role.rolconnlimit <> -1
        OR role.rolconfig IS NOT NULL OR role.rolvaliduntil IS NOT NULL
        OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_authid authentication
          WHERE authentication.oid = role.oid
            AND authentication.rolpassword IS NOT NULL
        )
      )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.rolname = 'meddoc_backup'
      AND (
        role.rolcanlogin = FALSE OR role.rolsuper OR role.rolcreatedb
        OR role.rolcreaterole OR role.rolinherit = FALSE
        OR role.rolreplication OR role.rolbypassrls = FALSE
        OR role.rolconnlimit <> 1 OR role.rolconfig IS NOT NULL
        OR role.rolvaliduntil IS NOT NULL
      )
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
  ) THEN
    RAISE EXCEPTION 'Refusing to reuse a non-exact backup principal';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role
      ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor_role
      ON grantor_role.oid = membership.grantor
    WHERE (
      member_role.rolname IN (
        'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
      ) OR granted_role.rolname IN (
        'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
      ) OR grantor_role.rolname IN (
        'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
      )
    ) AND NOT (
      membership.admin_option = FALSE
      AND membership.inherit_option = TRUE
      AND membership.set_option = FALSE
      AND grantor_role.rolsuper
      AND (
        (
          member_role.rolname = 'meddoc_backup'
          AND granted_role.rolname = 'quillmd_backup'
        ) OR (
          member_role.rolname = 'quillmd_backup'
          AND granted_role.rolname = 'pg_read_all_data'
        )
      )
    )
  ) THEN
    RAISE EXCEPTION 'Refusing a non-exact backup role graph';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname = 'meddoc_backup'
      AND (
        EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = login_role.oid
        ) OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = login_role.oid
        )
      )
  ) THEN
    RAISE EXCEPTION 'Backup login has direct database authority';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles boundary_role
    WHERE boundary_role.rolname = 'quillmd_backup'
      AND (
        EXISTS (
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          WHERE setting.setrole = boundary_role.oid
        ) OR EXISTS (
          SELECT 1 FROM pg_catalog.pg_shdepend dependency
          WHERE dependency.refclassid =
              'pg_catalog.pg_authid'::pg_catalog.regclass
            AND dependency.refobjid = boundary_role.oid
            AND NOT (
              dependency.deptype = 'a'
              AND dependency.objsubid = 0
              AND (
                (
                  dependency.dbid = 0
                  AND dependency.classid =
                    'pg_catalog.pg_database'::pg_catalog.regclass
                  AND dependency.objid = backup_database_oid
                ) OR (
                  dependency.dbid = backup_database_oid
                  AND dependency.classid =
                    'pg_catalog.pg_proc'::pg_catalog.regclass
                  AND dependency.objid = pg_catalog.to_regprocedure(
                    'public.quillmd_boundary_password_is_null(text)'
                  )
                  AND pg_temp.quillmd_backup_password_helper_is_exact()
                )
              )
            )
        )
      )
  ) THEN
    RAISE EXCEPTION 'Backup boundary has authority outside its database ACL';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_database database_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
    JOIN pg_catalog.pg_roles grantor_role
      ON grantor_role.oid = privilege.grantor
    WHERE grantor_role.rolname IN ('meddoc_backup', 'quillmd_backup')
  ) THEN
    RAISE EXCEPTION 'Backup principal cannot grant database privileges';
  END IF;
END
$precondition$;

SELECT 'CREATE ROLE quillmd_backup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'quillmd_backup'
) \gexec

SELECT 'CREATE ROLE meddoc_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION BYPASSRLS CONNECTION LIMIT 1'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'meddoc_backup'
) \gexec

\password meddoc_backup
ALTER ROLE meddoc_backup NOSUPERUSER NOCREATEDB NOCREATEROLE
  INHERIT NOREPLICATION BYPASSRLS CONNECTION LIMIT 1;

SELECT 'GRANT quillmd_backup TO meddoc_backup WITH ADMIN FALSE, INHERIT TRUE, SET FALSE'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_auth_members membership
  WHERE membership.member = 'meddoc_backup'::pg_catalog.regrole
    AND membership.roleid = 'quillmd_backup'::pg_catalog.regrole
) \gexec

SELECT 'GRANT pg_read_all_data TO quillmd_backup WITH ADMIN FALSE, INHERIT TRUE, SET FALSE'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_auth_members membership
  WHERE membership.member = 'quillmd_backup'::pg_catalog.regrole
    AND membership.roleid = 'pg_read_all_data'::pg_catalog.regrole
) \gexec

SELECT pg_catalog.format(
  'REVOKE CONNECT, CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC, quillmd_runtime, quillmd_release_control, quillmd_release_security, quillmd_audit_dispatcher, quillmd_auth_email_dispatcher, quillmd_backup',
  database_object.datname
)
FROM pg_catalog.pg_database database_object
ORDER BY database_object.oid
\gexec

SELECT pg_catalog.format(
  'GRANT CONNECT ON DATABASE %I TO quillmd_runtime, quillmd_release_control, quillmd_release_security, quillmd_audit_dispatcher, quillmd_auth_email_dispatcher, quillmd_backup',
  pg_catalog.current_database()
) \gexec

-- Large objects are outside the released MedDoc storage contract. PostgreSQL
-- grants these pg_catalog entrypoints to PUBLIC by default, which would let a
-- read-only backup credential create or mutate LOs. Keep owner-only access;
-- lo_import/lo_export are already owner-only in the stock PostgreSQL 16 ACL.
REVOKE EXECUTE ON FUNCTION
  pg_catalog.lo_creat(INTEGER),
  pg_catalog.lo_create(OID),
  pg_catalog.lo_from_bytea(OID, BYTEA),
  pg_catalog.lo_open(OID, INTEGER),
  pg_catalog.lo_put(OID, BIGINT, BYTEA),
  pg_catalog.lo_truncate(INTEGER, INTEGER),
  pg_catalog.lo_truncate64(INTEGER, BIGINT),
  pg_catalog.lo_unlink(OID),
  pg_catalog.lowrite(INTEGER, BYTEA)
FROM PUBLIC;

DO $postcondition$
DECLARE
  backup_database_oid OID := (
    SELECT oid FROM pg_catalog.pg_database
    WHERE datname = pg_catalog.current_database()
  );
BEGIN
  IF NOT pg_temp.quillmd_backup_password_helper_stage_is_exact() THEN
    RAISE EXCEPTION 'Backup helper migration stage changed during provisioning';
  END IF;

  IF NOT pg_temp.quillmd_application_role_graph_is_exact() THEN
    RAISE EXCEPTION 'Application database-principal graph changed during provisioning';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_stat_activity activity
    WHERE activity.pid <> pg_catalog.pg_backend_pid()
      AND activity.usename IN (
        'meddoc_runtime',
        'meddoc_release_control',
        'meddoc_release_security',
        'meddoc_audit_dispatcher',
        'meddoc_auth_email_dispatcher',
        'meddoc_backup'
      )
  ) THEN
    RAISE EXCEPTION 'Trusted login session appeared during cluster ACL provisioning';
  END IF;

  IF (
    SELECT COUNT(*) FROM pg_catalog.pg_roles role
    WHERE role.rolname = 'meddoc_backup'
      AND role.rolcanlogin AND role.rolsuper = FALSE
      AND role.rolcreatedb = FALSE AND role.rolcreaterole = FALSE
      AND role.rolinherit AND role.rolreplication = FALSE
      AND role.rolbypassrls AND role.rolconnlimit = 1
      AND role.rolconfig IS NULL AND role.rolvaliduntil IS NULL
      AND EXISTS (
        SELECT 1 FROM pg_catalog.pg_authid authentication
        WHERE authentication.oid = role.oid
          AND authentication.rolpassword LIKE 'SCRAM-SHA-256$4096:%'
      )
  ) <> 1 OR (
    SELECT COUNT(*) FROM pg_catalog.pg_roles role
    WHERE role.rolname = 'quillmd_backup'
      AND role.rolcanlogin = FALSE AND role.rolsuper = FALSE
      AND role.rolcreatedb = FALSE AND role.rolcreaterole = FALSE
      AND role.rolinherit = FALSE AND role.rolreplication = FALSE
      AND role.rolbypassrls = FALSE AND role.rolconnlimit = -1
      AND role.rolconfig IS NULL AND role.rolvaliduntil IS NULL
      AND EXISTS (
        SELECT 1 FROM pg_catalog.pg_authid authentication
        WHERE authentication.oid = role.oid
          AND authentication.rolpassword IS NULL
      )
  ) <> 1 OR (
    SELECT COUNT(*)
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
  ) <> 1 THEN
    RAISE EXCEPTION 'Backup role attributes are not exact';
  END IF;

  IF (
    SELECT COUNT(*)
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role
      ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor_role
      ON grantor_role.oid = membership.grantor
    WHERE (
      member_role.rolname IN (
        'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
      ) OR granted_role.rolname IN (
        'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
      ) OR grantor_role.rolname IN (
        'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
      )
    )
      AND membership.admin_option = FALSE
      AND membership.inherit_option = TRUE
      AND membership.set_option = FALSE
      AND grantor_role.rolsuper
      AND (
        (
          member_role.rolname = 'meddoc_backup'
          AND granted_role.rolname = 'quillmd_backup'
        ) OR (
          member_role.rolname = 'quillmd_backup'
          AND granted_role.rolname = 'pg_read_all_data'
        )
      )
  ) <> 2 OR (
    SELECT COUNT(*)
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role
      ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor_role
      ON grantor_role.oid = membership.grantor
    WHERE member_role.rolname IN (
      'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
    ) OR granted_role.rolname IN (
      'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
    ) OR grantor_role.rolname IN (
      'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
    )
  ) <> 2 THEN
    RAISE EXCEPTION 'Backup role graph is not exact';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_db_role_setting setting
    WHERE setting.setrole IN (
      'meddoc_backup'::pg_catalog.regrole,
      'quillmd_backup'::pg_catalog.regrole
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_shdepend dependency
    WHERE dependency.refclassid =
        'pg_catalog.pg_authid'::pg_catalog.regclass
      AND dependency.refobjid = 'meddoc_backup'::pg_catalog.regrole
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_shdepend dependency
    WHERE dependency.refclassid =
        'pg_catalog.pg_authid'::pg_catalog.regclass
      AND dependency.refobjid = 'quillmd_backup'::pg_catalog.regrole
      AND NOT (
        dependency.deptype = 'a'
        AND dependency.objsubid = 0
        AND (
          (
            dependency.dbid = 0
            AND dependency.classid =
              'pg_catalog.pg_database'::pg_catalog.regclass
            AND dependency.objid = backup_database_oid
          ) OR (
            dependency.dbid = backup_database_oid
            AND dependency.classid =
              'pg_catalog.pg_proc'::pg_catalog.regclass
            AND dependency.objid = pg_catalog.to_regprocedure(
              'public.quillmd_boundary_password_is_null(text)'
            )
            AND pg_temp.quillmd_backup_password_helper_is_exact()
          )
        )
      )
  ) THEN
    RAISE EXCEPTION 'Backup principal has direct authority';
  END IF;

  IF (
    SELECT COUNT(*)
    FROM pg_catalog.pg_database database_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
    JOIN pg_catalog.pg_roles grantee_role
      ON grantee_role.oid = privilege.grantee
    WHERE grantee_role.rolname IN (
      'quillmd_runtime',
      'quillmd_release_control',
      'quillmd_release_security',
      'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher',
      'quillmd_backup'
    )
      AND database_object.oid = backup_database_oid
      AND privilege.privilege_type = 'CONNECT'
      AND privilege.is_grantable = FALSE
      AND EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles grantor_role
        WHERE grantor_role.oid = privilege.grantor
          AND grantor_role.rolsuper
      )
  ) <> 6 OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_database database_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
    JOIN pg_catalog.pg_roles grantee_role
      ON grantee_role.oid = privilege.grantee
    WHERE grantee_role.rolname IN (
      'quillmd_runtime',
      'quillmd_release_control',
      'quillmd_release_security',
      'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher',
      'quillmd_backup'
    )
      AND NOT (
        database_object.oid = backup_database_oid
        AND privilege.privilege_type = 'CONNECT'
        AND privilege.is_grantable = FALSE
        AND EXISTS (
          SELECT 1 FROM pg_catalog.pg_roles grantor_role
          WHERE grantor_role.oid = privilege.grantor
            AND grantor_role.rolsuper
        )
      )
  ) OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_database database_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
    JOIN pg_catalog.pg_roles grantor_role
      ON grantor_role.oid = privilege.grantor
    WHERE grantor_role.rolname IN ('meddoc_backup', 'quillmd_backup')
  ) OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_database database_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
    WHERE privilege.grantee = 'meddoc_backup'::pg_catalog.regrole
  ) THEN
    RAISE EXCEPTION 'Backup database ACL is not current-CONNECT-only';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_database database_object
    WHERE pg_catalog.has_database_privilege(
        'meddoc_backup', database_object.oid, 'CONNECT'
      ) IS DISTINCT FROM (database_object.oid = backup_database_oid)
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_database database_object
    WHERE (
        pg_catalog.has_database_privilege(
          'meddoc_backup', database_object.oid, 'CREATE'
        ) OR pg_catalog.has_database_privilege(
          'meddoc_backup', database_object.oid, 'TEMPORARY'
        )
      )
  ) OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_database database_object
    CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
    WHERE privilege.grantee = 0
      AND privilege.privilege_type IN ('CONNECT', 'CREATE', 'TEMPORARY')
  ) THEN
    RAISE EXCEPTION 'Backup database privileges are not fail-closed';
  END IF;

  IF (
    SELECT COUNT(*)
    FROM (
      VALUES
        ('pg_catalog.lo_creat(integer)'),
        ('pg_catalog.lo_create(oid)'),
        ('pg_catalog.lo_from_bytea(oid,bytea)'),
        ('pg_catalog.lo_open(oid,integer)'),
        ('pg_catalog.lo_put(oid,bigint,bytea)'),
        ('pg_catalog.lo_truncate(integer,integer)'),
        ('pg_catalog.lo_truncate64(integer,bigint)'),
        ('pg_catalog.lo_unlink(oid)'),
        ('pg_catalog.lowrite(integer,bytea)'),
        ('pg_catalog.lo_import(text)'),
        ('pg_catalog.lo_import(text,oid)'),
        ('pg_catalog.lo_export(oid,text)')
    ) AS expected(signature)
    WHERE pg_catalog.to_regprocedure(expected.signature) IS NOT NULL
  ) <> 12 OR EXISTS (
    SELECT 1
    FROM (
      VALUES
        ('pg_catalog.lo_creat(integer)'),
        ('pg_catalog.lo_create(oid)'),
        ('pg_catalog.lo_from_bytea(oid,bytea)'),
        ('pg_catalog.lo_open(oid,integer)'),
        ('pg_catalog.lo_put(oid,bigint,bytea)'),
        ('pg_catalog.lo_truncate(integer,integer)'),
        ('pg_catalog.lo_truncate64(integer,bigint)'),
        ('pg_catalog.lo_unlink(oid)'),
        ('pg_catalog.lowrite(integer,bytea)'),
        ('pg_catalog.lo_import(text)'),
        ('pg_catalog.lo_import(text,oid)'),
        ('pg_catalog.lo_export(oid,text)')
    ) AS expected(signature)
    WHERE pg_catalog.has_function_privilege(
      'meddoc_backup',
      pg_catalog.to_regprocedure(expected.signature),
      'EXECUTE'
    )
  ) THEN
    RAISE EXCEPTION 'PostgreSQL large-object capability is not fail-closed';
  END IF;
END
$postcondition$;
COMMIT;
SQL
then
  fail
fi

unset DB_BACKUP_PASSWORD
trap - EXIT HUP INT TERM
printf '%s\n' 'postgres-backup-principal: PASS'
