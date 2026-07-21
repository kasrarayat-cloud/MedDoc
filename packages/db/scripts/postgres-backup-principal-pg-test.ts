#!/usr/bin/env tsx

// Isolated actual-PostgreSQL 16 proof for the MedDoc backup principal.
// The two containers use --network none, fixed synthetic rows, and explicit
// names owned by this process. No production target or ambient DATABASE_URL is
// accepted, and cleanup never enumerates/removes unrelated containers.

import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import {
  chmod,
  mkdtemp,
  mkdir,
  readFile,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const POSTGRES_IMAGE =
  "pgvector/pgvector:pg16@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff";
const BACKUP_IMAGE =
  "prodrigestivill/postgres-backup-local@sha256:a0103fbce0c48ccc7693ddbb2a2bfa733048db845354f635efef9e4566de185d";
const BACKUP_OPTIONS =
  "--format=custom --compress=6 --no-owner --create --large-objects --lock-wait-timeout=60s";
const V9_MIGRATION_SHA256 =
  "8d2c4fe1075490085b34397cdecde3d8c6e50b3e21c778ac9d491da071faf404";
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const v9MigrationPath = join(
  repoRoot,
  "packages/db/prisma/migrations/20260720213000_exact_database_principal_closure_v9/migration.sql",
);
const provisionerPath = join(
  repoRoot,
  "infra/postgres/provision-postgres-backup-principal.sh",
);
const hookPath = join(
  repoRoot,
  "infra/postgres-backup/hooks/10-principal-preflight",
);

interface CommandResult {
  readonly code: number;
  readonly stdout: string;
  readonly stderr: string;
}

const sensitiveValues: string[] = [];

function redact(value: string): string {
  return sensitiveValues.reduce(
    (redacted, secret) => redacted.split(secret).join("[redacted]"),
    value,
  );
}

function assertSecretFree(result: CommandResult, label: string): void {
  const output = `${result.stdout}\n${result.stderr}`;
  for (const secret of sensitiveValues) {
    assert.equal(output.includes(secret), false, `${label} exposed a secret`);
  }
}

async function command(
  executable: string,
  args: readonly string[],
): Promise<CommandResult> {
  const child = spawn(executable, args, {
    cwd: repoRoot,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
  child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
  const code = await new Promise<number>((done, reject) => {
    child.once("error", reject);
    child.once("close", (status) => done(status ?? 1));
  });
  const result = {
    code,
    stdout: Buffer.concat(stdout).toString("utf8"),
    stderr: Buffer.concat(stderr).toString("utf8"),
  };
  assertSecretFree(result, executable);
  return result;
}

async function mustRun(
  executable: string,
  args: readonly string[],
  label: string,
): Promise<CommandResult> {
  const result = await command(executable, args);
  if (result.code !== 0) {
    throw new Error(
      `${label} failed (${result.code}): ${redact(result.stderr).trim().slice(-1200)}`,
    );
  }
  return result;
}

async function docker(
  args: readonly string[],
  label: string,
): Promise<CommandResult> {
  return mustRun("docker", args, label);
}

function execArgs(container: string, environment: readonly string[] = []) {
  return [
    "exec",
    ...environment.flatMap((entry) => ["--env", entry]),
    container,
  ];
}

async function waitForPostgres(container: string, database: string) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const ready = await command("docker", [
      "exec",
      container,
      "psql",
      "-X",
      "--quiet",
      "--username",
      "postgres",
      "--dbname",
      database,
      "--command",
      "SELECT 1",
    ]);
    if (ready.code === 0) return;
    await new Promise((done) => setTimeout(done, 100));
  }
  throw new Error("Disposable PostgreSQL did not become ready");
}

async function adminSql(
  container: string,
  database: string,
  sql: string,
): Promise<string> {
  const result = await docker(
    [
      ...execArgs(container),
      "psql",
      "-X",
      "--quiet",
      "--tuples-only",
      "--no-align",
      "--set",
      "ON_ERROR_STOP=1",
      "--username",
      "postgres",
      "--dbname",
      database,
      "--command",
      sql,
    ],
    "administrator SQL",
  );
  return result.stdout.trim();
}

async function setSyntheticRolePassword(input: {
  container: string;
  database: string;
  password: string;
}): Promise<void> {
  const child = spawn(
    "docker",
    [
      "exec",
      "--interactive",
      input.container,
      "psql",
      "-X",
      "--quiet",
      "--set",
      "ON_ERROR_STOP=1",
      "--username",
      "postgres",
      "--dbname",
      input.database,
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
  child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
  child.stdin.end(
    `\\set ECHO none\nSET password_encryption = 'scram-sha-256';\n\\password meddoc_backup\n${input.password}\n${input.password}\n\\q\n`,
  );
  const code = await new Promise<number>((done, reject) => {
    child.once("error", reject);
    child.once("close", (status) => done(status ?? 1));
  });
  const result = {
    code,
    stdout: Buffer.concat(stdout).toString("utf8"),
    stderr: Buffer.concat(stderr).toString("utf8"),
  };
  assertSecretFree(result, "hidden synthetic password restoration");
  assert.equal(code, 0, "hidden synthetic password restoration must pass");
}

async function startReleaseLockHolder(
  container: string,
  database: string,
  applicationName: string,
): Promise<{
  readonly completion: Promise<CommandResult>;
  readonly release: () => void;
}> {
  assert.match(applicationName, /^[a-z0-9_]+$/u);
  const child = spawn(
    "docker",
    [
      "exec",
      "--interactive",
      "--env",
      `PGAPPNAME=${applicationName}`,
      container,
      "psql",
      "-X",
      "--quiet",
      "--set",
      "ON_ERROR_STOP=1",
      "--username",
      "postgres",
      "--dbname",
      database,
    ],
    {
      cwd: repoRoot,
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
  child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
  const completion = new Promise<CommandResult>((done, reject) => {
    child.once("error", reject);
    child.once("close", (status) => {
      const result = {
        code: status ?? 1,
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
      };
      assertSecretFree(result, "release-lock holder");
      done(result);
    });
  });
  child.stdin.write("SELECT pg_catalog.pg_advisory_lock(73119, 2026072001);\n");

  for (let attempt = 0; attempt < 50; attempt += 1) {
    const heldByAnotherSession = await adminSql(
      container,
      database,
      `SELECT CASE
         WHEN pg_catalog.pg_try_advisory_lock(73119, 2026072001)
         THEN pg_catalog.pg_advisory_unlock(73119, 2026072001) AND FALSE
         ELSE TRUE
       END;`,
    );
    if (heldByAnotherSession === "t") {
      return {
        completion,
        release: () => {
          child.stdin.end("\\q\n");
        },
      };
    }
    await new Promise((done) => setTimeout(done, 100));
  }
  throw new Error("Disposable release-lock holder did not become ready");
}

async function backupSql(
  container: string,
  database: string,
  pgpassPath: string,
  sql: string,
): Promise<CommandResult> {
  return command("docker", [
    ...execArgs(container, [`PGPASSFILE=${pgpassPath}`]),
    "psql",
    "-X",
    "--quiet",
    "--tuples-only",
    "--no-align",
    "--set",
    "ON_ERROR_STOP=1",
    "--host",
    "127.0.0.1",
    "--port",
    "5432",
    "--username",
    "meddoc_backup",
    "--dbname",
    database,
    "--command",
    sql,
  ]);
}

async function expectBackupSqlRejected(
  container: string,
  database: string,
  pgpassPath: string,
  sql: string,
  label: string,
) {
  const result = await backupSql(container, database, pgpassPath, sql);
  assert.notEqual(result.code, 0, `${label} must be rejected`);
}

async function provision(
  container: string,
  database: string,
  secretPath: string,
  executable = "/opt/quillmd/provision-backup-principal",
  options: {
    expectedSystemIdentifier?: string;
    additionalEnvironment?: readonly string[];
  } = {},
): Promise<CommandResult> {
  const expectedSystemIdentifier =
    options.expectedSystemIdentifier ??
    (await adminSql(
      container,
      database,
      "SELECT system_identifier FROM pg_catalog.pg_control_system();",
    ));
  return command("docker", [
    ...execArgs(container, [
      `DB_BACKUP_PASSWORD_FILE=${secretPath}`,
      `DB_EXPECTED_SYSTEM_IDENTIFIER=${expectedSystemIdentifier}`,
      "POSTGRES_USER=postgres",
      `POSTGRES_DB=${database}`,
      ...(options.additionalEnvironment ?? []),
    ]),
    executable,
  ]);
}

async function assertProvisionPass(result: CommandResult): Promise<void> {
  assert.equal(
    result.code,
    0,
    `provisioner must pass with fixed output: ${redact(result.stderr).trim()}`,
  );
  assert.equal(result.stdout, "postgres-backup-principal: PASS\n");
  assert.equal(result.stderr, "");
}

async function preflight(
  container: string,
  database: string,
  secretPath: string,
  pgpassPath: string,
  host = "127.0.0.1",
): Promise<CommandResult> {
  return command("docker", [
    ...execArgs(container, [
      `POSTGRES_HOST=${host}`,
      "POSTGRES_PORT=5432",
      `POSTGRES_DB=${database}`,
      "POSTGRES_USER=meddoc_backup",
      `POSTGRES_PASSWORD_FILE=${secretPath}`,
      `PGPASSFILE=${pgpassPath}`,
    ]),
    "/opt/quillmd/backup-preflight",
    "pre-backup",
  ]);
}

async function assertPreflightPass(result: CommandResult): Promise<void> {
  assert.equal(
    result.code,
    0,
    `preflight must pass with fixed output: ${redact(result.stderr).trim()}`,
  );
  assert.equal(result.stdout, "postgres-backup-preflight: PASS\n");
  assert.equal(result.stderr, "");
}

async function assertPreflightFail(result: CommandResult): Promise<void> {
  assert.notEqual(result.code, 0);
  assert.equal(result.stdout, "");
  assert.equal(result.stderr, "postgres-backup-preflight: FAIL\n");
}

const boundaryRoleSql = `
DO $roles$
DECLARE role_name TEXT;
BEGIN
  FOREACH role_name IN ARRAY ARRAY[
    'quillmd_runtime',
    'quillmd_release_control',
    'quillmd_release_security',
    'quillmd_audit_dispatcher',
    'quillmd_auth_email_dispatcher',
    'quillmd_backup'
  ] LOOP
    EXECUTE format(
      'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
      role_name
    );
  END LOOP;
END
$roles$;
CREATE ROLE meddoc_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  INHERIT NOREPLICATION NOBYPASSRLS;
CREATE ROLE meddoc_release_control LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  INHERIT NOREPLICATION NOBYPASSRLS;
CREATE ROLE meddoc_audit_dispatcher LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  INHERIT NOREPLICATION NOBYPASSRLS;
CREATE ROLE meddoc_auth_email_dispatcher LOGIN NOSUPERUSER NOCREATEDB
  NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS;
GRANT quillmd_runtime TO meddoc_runtime
  WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT quillmd_release_control TO meddoc_release_control
  WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT quillmd_audit_dispatcher TO meddoc_audit_dispatcher
  WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
GRANT quillmd_auth_email_dispatcher TO meddoc_auth_email_dispatcher
  WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`;

const migrationLedgerSql = `
CREATE TABLE public."_prisma_migrations" (
  id VARCHAR(36) PRIMARY KEY,
  checksum VARCHAR(64) NOT NULL,
  finished_at TIMESTAMPTZ,
  migration_name VARCHAR(255) NOT NULL,
  logs TEXT,
  rolled_back_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_steps_count INTEGER NOT NULL DEFAULT 0
);`;

const fixtureAfterBoundarySql = `
${migrationLedgerSql}
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA clinical AUTHORIZATION postgres;
REVOKE CREATE ON SCHEMA clinical FROM PUBLIC;
CREATE SEQUENCE clinical.synthetic_record_sequence START 40;
CREATE TABLE clinical.synthetic_patient_records (
  id BIGINT PRIMARY KEY DEFAULT nextval('clinical.synthetic_record_sequence'),
  practice_key TEXT NOT NULL,
  synthetic_value TEXT NOT NULL
);
ALTER TABLE clinical.synthetic_patient_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical.synthetic_patient_records FORCE ROW LEVEL SECURITY;
CREATE POLICY synthetic_practice_policy
  ON clinical.synthetic_patient_records
  USING (practice_key = current_setting('app.synthetic_practice', TRUE));
INSERT INTO clinical.synthetic_patient_records (practice_key, synthetic_value)
VALUES ('synthetic-a', 'alpha'), ('synthetic-b', 'beta');
CREATE VIEW clinical.synthetic_record_view AS
  SELECT id, practice_key FROM clinical.synthetic_patient_records;
CREATE MATERIALIZED VIEW clinical.synthetic_record_rollup AS
  SELECT practice_key, COUNT(*) AS record_count
  FROM clinical.synthetic_patient_records GROUP BY practice_key;
CREATE FUNCTION clinical.synthetic_owner_count()
RETURNS BIGINT
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, clinical
AS 'SELECT COUNT(*) FROM clinical.synthetic_patient_records';
REVOKE ALL ON FUNCTION clinical.synthetic_owner_count() FROM PUBLIC;
GRANT SELECT ON clinical.synthetic_patient_records
  TO quillmd_audit_dispatcher;
GRANT INSERT, UPDATE ON clinical.synthetic_patient_records
  TO quillmd_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA clinical
  GRANT SELECT ON TABLES TO quillmd_audit_dispatcher;`;

const exactBoundaryPasswordFunctionSql = `CREATE FUNCTION public.quillmd_boundary_password_is_null(boundary_name TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $password_null$
  SELECT CASE
    WHEN boundary_name IN (
      'quillmd_runtime',
      'quillmd_release_control',
      'quillmd_release_security',
      'quillmd_audit_dispatcher',
      'quillmd_auth_email_dispatcher',
      'quillmd_backup'
    ) THEN EXISTS (
      SELECT 1
      FROM pg_catalog.pg_authid authentication
      WHERE authentication.rolname = boundary_name
        AND authentication.rolcanlogin = FALSE
        AND authentication.rolpassword IS NULL
    )
    WHEN boundary_name IN (
      'meddoc_runtime',
      'meddoc_release_control',
      'meddoc_release_security',
      'meddoc_audit_dispatcher',
      'meddoc_auth_email_dispatcher',
      'meddoc_backup'
    ) THEN EXISTS (
      SELECT 1
      FROM pg_catalog.pg_authid authentication
      WHERE authentication.rolname = boundary_name
        AND authentication.rolcanlogin = TRUE
        AND authentication.rolpassword LIKE 'SCRAM-SHA-256$4096:%'
    )
    ELSE FALSE
  END;
$password_null$;
REVOKE ALL ON FUNCTION
  public.quillmd_boundary_password_is_null(TEXT)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
  public.quillmd_boundary_password_is_null(TEXT)
TO
  quillmd_runtime,
  quillmd_release_control,
  quillmd_release_security,
  quillmd_audit_dispatcher,
  quillmd_auth_email_dispatcher,
  quillmd_backup;`;

const exactBoundaryPasswordHelperSql = `
INSERT INTO public."_prisma_migrations" (
  id, checksum, finished_at, migration_name, applied_steps_count
) VALUES (
  '00000000-0000-0000-0000-000000000009',
  '${V9_MIGRATION_SHA256}',
  CURRENT_TIMESTAMP,
  '20260720213000_exact_database_principal_closure_v9',
  1
);
${exactBoundaryPasswordFunctionSql}`;

const exactStateSql = `
WITH role_state AS (
  SELECT 'role|' || rolname || '|' || rolcanlogin || '|' || rolsuper || '|' ||
    rolcreatedb || '|' || rolcreaterole || '|' || rolinherit || '|' ||
    rolreplication || '|' || rolbypassrls || '|' || rolconnlimit || '|' ||
    COALESCE(array_to_string(rolconfig, ','), '-') || '|' ||
    COALESCE(rolvaliduntil::TEXT, '-') AS item
  FROM pg_catalog.pg_roles
  WHERE rolname IN (
    'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
  )
), password_state AS (
  SELECT 'password|' || rolname || '|' || COALESCE(rolpassword, '-') AS item
  FROM pg_catalog.pg_authid
  WHERE rolname IN (
    'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
  )
), membership_state AS (
  SELECT 'member|' || member_role.rolname || '|' || granted_role.rolname || '|' ||
    membership.admin_option || '|' || membership.inherit_option || '|' ||
    membership.set_option || '|' || grantor_role.rolname AS item
  FROM pg_catalog.pg_auth_members membership
  JOIN pg_catalog.pg_roles member_role ON member_role.oid = membership.member
  JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = membership.roleid
  JOIN pg_catalog.pg_roles grantor_role ON grantor_role.oid = membership.grantor
  WHERE member_role.rolname IN (
    'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
  ) OR granted_role.rolname IN (
    'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
  ) OR grantor_role.rolname IN (
    'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
  )
), database_acl_state AS (
  SELECT 'dbacl|' || database_object.datname || '|' || privilege.grantee || '|' ||
    privilege.grantor || '|' || privilege.privilege_type || '|' ||
    privilege.is_grantable AS item
  FROM pg_catalog.pg_database database_object
  CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
), lo_acl_state AS (
  SELECT 'loacl|' || routine.oid::regprocedure::text || '|' ||
    COALESCE(routine.proacl::text, '<default>') AS item
  FROM pg_catalog.pg_proc routine
  WHERE routine.pronamespace = 'pg_catalog'::pg_catalog.regnamespace
    AND routine.proname IN (
      'lo_creat', 'lo_create', 'lo_from_bytea', 'lo_open', 'lo_put',
      'lo_truncate', 'lo_truncate64', 'lo_unlink', 'lowrite',
      'lo_import', 'lo_export'
    )
), all_state AS (
  SELECT item FROM role_state UNION ALL
  SELECT item FROM password_state UNION ALL
  SELECT item FROM membership_state UNION ALL
  SELECT item FROM database_acl_state UNION ALL
  SELECT item FROM lo_acl_state
)
SELECT string_agg(item, E'\\n' ORDER BY item) FROM all_state;`;

const applicationAclSql = `
WITH acl_state AS (
  SELECT 'database|' || database_object.datname || '|' ||
    CASE WHEN privilege.grantee = 0 THEN 'PUBLIC'
      ELSE pg_catalog.pg_get_userbyid(privilege.grantee) END || '|' ||
    pg_catalog.pg_get_userbyid(privilege.grantor) || '|' ||
    privilege.privilege_type || '|' ||
    privilege.is_grantable AS item
  FROM pg_catalog.pg_database database_object
  CROSS JOIN LATERAL pg_catalog.aclexplode(database_object.datacl) privilege
  WHERE database_object.datname = current_database()
    AND privilege.grantee <> database_object.datdba
  UNION ALL
  SELECT 'schema|' || namespace_object.nspname || '|' ||
    CASE WHEN privilege.grantee = 0 THEN 'PUBLIC'
      ELSE pg_catalog.pg_get_userbyid(privilege.grantee) END || '|' ||
    pg_catalog.pg_get_userbyid(privilege.grantor) || '|' ||
    privilege.privilege_type || '|' ||
    privilege.is_grantable
  FROM pg_catalog.pg_namespace namespace_object
  CROSS JOIN LATERAL pg_catalog.aclexplode(namespace_object.nspacl) privilege
  WHERE namespace_object.nspname IN ('public', 'clinical')
    AND privilege.grantee <> namespace_object.nspowner
  UNION ALL
  SELECT 'relation|' || namespace_object.nspname || '.' || relation.relname ||
    '|' || CASE WHEN privilege.grantee = 0 THEN 'PUBLIC'
      ELSE pg_catalog.pg_get_userbyid(privilege.grantee) END || '|' ||
    pg_catalog.pg_get_userbyid(privilege.grantor) || '|' ||
    privilege.privilege_type || '|' || privilege.is_grantable
  FROM pg_catalog.pg_class relation
  JOIN pg_catalog.pg_namespace namespace_object
    ON namespace_object.oid = relation.relnamespace
  CROSS JOIN LATERAL pg_catalog.aclexplode(relation.relacl) privilege
  WHERE namespace_object.nspname = 'clinical'
    AND privilege.grantee <> relation.relowner
  UNION ALL
  SELECT 'routine|' || routine.oid::regprocedure::text || '|' ||
    CASE WHEN privilege.grantee = 0 THEN 'PUBLIC'
      ELSE pg_catalog.pg_get_userbyid(privilege.grantee) END || '|' ||
    pg_catalog.pg_get_userbyid(privilege.grantor) || '|' ||
    privilege.privilege_type || '|' || privilege.is_grantable
  FROM pg_catalog.pg_proc routine
  JOIN pg_catalog.pg_namespace namespace_object
    ON namespace_object.oid = routine.pronamespace
  CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) privilege
  WHERE namespace_object.nspname = 'clinical'
    AND privilege.grantee <> routine.proowner
  UNION ALL
  SELECT 'default|' || default_acl.defaclobjtype::TEXT || '|' ||
    CASE WHEN privilege.grantee = 0 THEN 'PUBLIC'
      ELSE pg_catalog.pg_get_userbyid(privilege.grantee) END || '|' ||
    pg_catalog.pg_get_userbyid(privilege.grantor) || '|' ||
    privilege.privilege_type || '|' || privilege.is_grantable
  FROM pg_catalog.pg_default_acl default_acl
  CROSS JOIN LATERAL pg_catalog.aclexplode(default_acl.defaclacl) privilege
  WHERE default_acl.defaclnamespace = 'clinical'::pg_catalog.regnamespace
    AND privilege.grantee <> default_acl.defaclrole
)
SELECT string_agg(item, E'\\n' ORDER BY item) FROM acl_state;`;

async function startContainer(input: {
  name: string;
  database: string;
  adminSecret: string;
  backupSecret: string;
  nextBackupSecret: string;
  invalidBackupSecret: string;
  weakBackupSecret: string;
  backupPgpass: string;
  nextBackupPgpass: string;
  injectedProvisioner: string;
}) {
  await docker(
    [
      "run",
      "--detach",
      "--name",
      input.name,
      "--network",
      "none",
      "--env",
      "POSTGRES_PASSWORD_FILE=/run/secrets/postgres_admin_password",
      "--env",
      "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=trust",
      "--env",
      `POSTGRES_DB=${input.database}`,
      "--mount",
      `type=bind,src=${input.adminSecret},dst=/run/secrets/postgres_admin_password,readonly`,
      "--mount",
      `type=bind,src=${input.backupSecret},dst=/run/secrets/backup_password,readonly`,
      "--mount",
      `type=bind,src=${input.nextBackupSecret},dst=/run/secrets/backup_password_next,readonly`,
      "--mount",
      `type=bind,src=${input.invalidBackupSecret},dst=/run/secrets/backup_password_nul,readonly`,
      "--mount",
      `type=bind,src=${input.weakBackupSecret},dst=/run/secrets/backup_password_weak,readonly`,
      "--mount",
      `type=bind,src=${input.backupPgpass},dst=/run/secrets/backup_pgpass,readonly`,
      "--mount",
      `type=bind,src=${input.nextBackupPgpass},dst=/run/secrets/backup_pgpass_next,readonly`,
      "--mount",
      `type=bind,src=${provisionerPath},dst=/opt/quillmd/provision-backup-principal,readonly`,
      "--mount",
      `type=bind,src=${input.injectedProvisioner},dst=/opt/quillmd/provision-backup-principal-induced-failure,readonly`,
      "--mount",
      `type=bind,src=${hookPath},dst=/opt/quillmd/backup-preflight,readonly`,
      POSTGRES_IMAGE,
    ],
    "start disposable PostgreSQL",
  );
  await waitForPostgres(input.name, input.database);
  const version = await adminSql(
    input.name,
    input.database,
    "SHOW server_version;",
  );
  assert.match(version, /^16\./u, "test requires PostgreSQL 16");
}

async function main() {
  const frozenV9Migration = await readFile(v9MigrationPath, "utf8");
  assert.equal(
    createHash("sha256").update(frozenV9Migration).digest("hex"),
    V9_MIGRATION_SHA256,
    "backup admission must remain pinned to the frozen v9 migration bytes",
  );
  const helperStart =
    "CREATE FUNCTION public.quillmd_boundary_password_is_null(boundary_name TEXT)";
  const helperEnd = "\n  quillmd_backup;";
  const helperStartOffset = frozenV9Migration.indexOf(helperStart);
  const helperEndOffset = frozenV9Migration.indexOf(
    helperEnd,
    helperStartOffset,
  );
  assert.ok(helperStartOffset >= 0 && helperEndOffset > helperStartOffset);
  assert.equal(
    frozenV9Migration.lastIndexOf(helperStart),
    helperStartOffset,
    "frozen v9 must contain exactly one canonical backup helper block",
  );
  assert.equal(
    frozenV9Migration.slice(
      helperStartOffset,
      helperEndOffset + helperEnd.length,
    ),
    exactBoundaryPasswordFunctionSql,
    "actual-PG helper fixture must exactly match frozen v9 source",
  );

  assert.equal(
    process.env.DATABASE_URL,
    undefined,
    "ambient DATABASE_URL must be absent for the isolated backup test",
  );

  const suffix = `${process.pid}-${randomBytes(4).toString("hex")}`;
  const sourceContainer = `meddoc-backup-source-${suffix}`;
  const restoreContainer = `meddoc-backup-restore-${suffix}`;
  const sourceDatabase = `meddoc_backup_pg_test_${suffix.replaceAll("-", "_")}`;
  const graphProbeRole = `synthetic_backup_graph_${suffix.replaceAll("-", "_")}`;
  const readClosureProbeRole =
    `synthetic_backup_read_closure_${suffix.replaceAll("-", "_")}`;
  const releaseLockApplication = `synthetic_backup_lock_${suffix.replaceAll("-", "_")}`;
  assert.match(graphProbeRole, /^[a-z0-9_]+$/u);
  assert.match(readClosureProbeRole, /^[a-z0-9_]+$/u);
  assert.match(releaseLockApplication, /^[a-z0-9_]+$/u);
  const tempDirectory = await mkdtemp(
    join(tmpdir(), "meddoc-backup-principal-pg-test-"),
  );
  const createdContainers: string[] = [];

  const adminPassword = randomBytes(32).toString("base64url");
  const backupPassword = randomBytes(32).toString("base64url");
  const nextBackupPassword = randomBytes(32).toString("base64url");
  assert.notEqual(backupPassword, nextBackupPassword);
  sensitiveValues.push(adminPassword, backupPassword, nextBackupPassword);

  const adminSecret = join(tempDirectory, "admin-password");
  const backupSecret = join(tempDirectory, "backup-password");
  const nextBackupSecret = join(tempDirectory, "backup-password-next");
  const invalidBackupSecret = join(tempDirectory, "backup-password-nul");
  const weakBackupSecret = join(tempDirectory, "backup-password-weak");
  const backupPgpass = join(tempDirectory, "backup.pgpass");
  const nextBackupPgpass = join(tempDirectory, "backup-next.pgpass");
  const injectedProvisioner = join(
    tempDirectory,
    "provision-backup-principal-induced-failure",
  );
  const backupOutputDirectory = join(tempDirectory, "image-backups");

  const provisionerSource = await readFile(provisionerPath, "utf8");
  const commitMarker = "COMMIT;\nSQL";
  assert.equal(
    provisionerSource.split(commitMarker).length,
    2,
    "provisioner must have one transaction commit marker",
  );
  const injectedSource = provisionerSource.replace(
    commitMarker,
    "SELECT 1 / 0;\nCOMMIT;\nSQL",
  );

  await Promise.all([
    mkdir(backupOutputDirectory, { mode: 0o755 }),
    writeFile(adminSecret, adminPassword, { mode: 0o600 }),
    writeFile(backupSecret, backupPassword, { mode: 0o444 }),
    writeFile(nextBackupSecret, nextBackupPassword, { mode: 0o444 }),
    writeFile(
      invalidBackupSecret,
      Buffer.concat([
        Buffer.from("a".repeat(21), "utf8"),
        Buffer.from([0x00]),
        Buffer.from("b".repeat(21), "utf8"),
      ]),
      { mode: 0o444 },
    ),
    writeFile(weakBackupSecret, "synthetic-short-secret", { mode: 0o444 }),
    writeFile(
      backupPgpass,
      `127.0.0.1:5432:*:meddoc_backup:${backupPassword}`,
      { mode: 0o600 },
    ),
    writeFile(
      nextBackupPgpass,
      `127.0.0.1:5432:*:meddoc_backup:${nextBackupPassword}`,
      { mode: 0o600 },
    ),
    writeFile(injectedProvisioner, injectedSource, { mode: 0o700 }),
  ]);
  await chmod(injectedProvisioner, 0o700);
  await docker(
    [
      "run",
      "--rm",
      "--network",
      "none",
      "--mount",
      `type=bind,src=${backupOutputDirectory},dst=/target`,
      "--entrypoint",
      "chown",
      POSTGRES_IMAGE,
      "999:999",
      "/target",
    ],
    "prepare synthetic non-root backup volume",
  );

  const containerInput = {
    adminSecret,
    backupSecret,
    nextBackupSecret,
    invalidBackupSecret,
    weakBackupSecret,
    backupPgpass,
    nextBackupPgpass,
    injectedProvisioner,
  };

  try {
    createdContainers.push(sourceContainer);
    await startContainer({
      ...containerInput,
      name: sourceContainer,
      database: sourceDatabase,
    });
    await adminSql(sourceContainer, sourceDatabase, boundaryRoleSql);

    // Fresh-cluster provisioning precedes Prisma's ledger creation. Exercise
    // that catalog-absent branch twice and prove the post-migration archive
    // hook still refuses to run until the exact durable ledger exists.
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    await adminSql(sourceContainer, sourceDatabase, fixtureAfterBoundarySql);
    await adminSql(
      sourceContainer,
      sourceDatabase,
      "ALTER SYSTEM SET log_statement = 'all';",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      "SELECT pg_catalog.pg_reload_conf();",
    );
    assert.equal(
      await adminSql(sourceContainer, sourceDatabase, "SHOW log_statement;"),
      "all",
    );

    const wrongClusterFailure = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
      "/opt/quillmd/provision-backup-principal",
      { expectedSystemIdentifier: "1" },
    );
    assert.notEqual(wrongClusterFailure.code, 0);
    assert.equal(wrongClusterFailure.stdout, "");
    assert.equal(
      wrongClusterFailure.stderr,
      "postgres-backup-principal: FAIL\n",
    );

    const ambientRouteFailure = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
      "/opt/quillmd/provision-backup-principal",
      { additionalEnvironment: ["PGHOST=synthetic-unapproved-target"] },
    );
    assert.notEqual(ambientRouteFailure.code, 0);
    assert.equal(ambientRouteFailure.stdout, "");
    assert.equal(
      ambientRouteFailure.stderr,
      "postgres-backup-principal: FAIL\n",
    );

    const weakSecretFailure = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password_weak",
    );
    assert.notEqual(weakSecretFailure.code, 0);
    assert.equal(weakSecretFailure.stdout, "");
    assert.equal(weakSecretFailure.stderr, "postgres-backup-principal: FAIL\n");

    const invalidSecretFailure = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password_nul",
    );
    assert.notEqual(invalidSecretFailure.code, 0);
    assert.equal(invalidSecretFailure.stdout, "");
    assert.equal(
      invalidSecretFailure.stderr,
      "postgres-backup-principal: FAIL\n",
    );

    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    const backupVerifier = await adminSql(
      sourceContainer,
      sourceDatabase,
      "SELECT rolpassword FROM pg_catalog.pg_authid WHERE rolname = 'meddoc_backup';",
    );
    assert.match(backupVerifier, /^SCRAM-SHA-256\$/u);
    const statementLogs = await docker(
      ["logs", sourceContainer],
      "inspect synthetic PostgreSQL statement-log redaction",
    );
    assert.equal(
      `${statementLogs.stdout}\n${statementLogs.stderr}`.includes(
        "SCRAM-SHA-256$",
      ),
      false,
      "statement log must not expose a password verifier",
    );

    // Cluster-role provisioning is intentionally available before Prisma v9,
    // and remains idempotent there. The archive hook is post-migration only,
    // so it must fail until the durable v9 marker and helper both exist.
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    // v9 adds exactly one shared dependency for the backup boundary: EXECUTE
    // on the frozen password-null helper.  The provisioner must remain
    // idempotent after that migration, while rejecting any helper drift or a
    // second function capability granted to the same boundary.
    await adminSql(
      sourceContainer,
      sourceDatabase,
      exactBoundaryPasswordHelperSql,
    );
    const helperDependencyCount = await adminSql(
      sourceContainer,
      sourceDatabase,
      `SELECT COUNT(*)
       FROM pg_catalog.pg_shdepend dependency
       WHERE dependency.dbid = (
           SELECT oid FROM pg_catalog.pg_database
           WHERE datname = pg_catalog.current_database()
         )
         AND dependency.classid =
           'pg_catalog.pg_proc'::pg_catalog.regclass
         AND dependency.objid = pg_catalog.to_regprocedure(
           'public.quillmd_boundary_password_is_null(text)'
         )
         AND dependency.objsubid = 0
         AND dependency.refclassid =
           'pg_catalog.pg_authid'::pg_catalog.regclass
         AND dependency.refobjid =
           'quillmd_backup'::pg_catalog.regrole
         AND dependency.deptype = 'a';`,
    );
    assert.equal(helperDependencyCount, "1");
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `UPDATE public."_prisma_migrations"
       SET checksum = '${"f".repeat(64)}'
       WHERE migration_name =
         '20260720213000_exact_database_principal_closure_v9';`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const wrongV9ChecksumProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(wrongV9ChecksumProvision.code, 0);
    assert.equal(wrongV9ChecksumProvision.stdout, "");
    assert.equal(
      wrongV9ChecksumProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `UPDATE public."_prisma_migrations"
       SET checksum = '${V9_MIGRATION_SHA256}'
       WHERE migration_name =
         '20260720213000_exact_database_principal_closure_v9';`,
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    const stateBeforeReleaseLockContention = await adminSql(
      sourceContainer,
      sourceDatabase,
      exactStateSql,
    );
    const releaseLockHolder = await startReleaseLockHolder(
      sourceContainer,
      sourceDatabase,
      releaseLockApplication,
    );
    let releaseLockHolderStopped = false;
    try {
      const hookContentionStartedAt = Date.now();
      await assertPreflightFail(
        await preflight(
          sourceContainer,
          sourceDatabase,
          "/run/secrets/backup_password",
          "/run/secrets/backup_pgpass",
        ),
      );
      assert.ok(
        Date.now() - hookContentionStartedAt < 10_000,
        "preflight lock contention must fail promptly",
      );

      const provisionContentionStartedAt = Date.now();
      const provisionDuringReleaseLock = await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      );
      assert.notEqual(provisionDuringReleaseLock.code, 0);
      assert.equal(provisionDuringReleaseLock.stdout, "");
      assert.equal(
        provisionDuringReleaseLock.stderr,
        "postgres-backup-principal: FAIL\n",
      );
      assert.ok(
        Date.now() - provisionContentionStartedAt < 10_000,
        "provisioner lock contention must fail promptly",
      );
      assert.equal(
        await adminSql(sourceContainer, sourceDatabase, exactStateSql),
        stateBeforeReleaseLockContention,
        "release-lock contention must leave the principal graph unchanged",
      );
    } finally {
      releaseLockHolder.release();
      releaseLockHolderStopped = true;
    }
    assert.equal(releaseLockHolderStopped, true);
    const lockHolderResult = await releaseLockHolder.completion;
    assert.equal(lockHolderResult.code, 0);
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE INDEX synthetic_unreviewed_migration_marker_index
       ON public."_prisma_migrations" (migration_name);`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const unreviewedLedgerIndexProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(unreviewedLedgerIndexProvision.code, 0);
    assert.equal(unreviewedLedgerIndexProvision.stdout, "");
    assert.equal(
      unreviewedLedgerIndexProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      "DROP INDEX public.synthetic_unreviewed_migration_marker_index;",
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `ALTER TABLE public."_prisma_migrations"
         ALTER COLUMN checksum TYPE TEXT;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const malformedLedgerProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(malformedLedgerProvision.code, 0);
    assert.equal(malformedLedgerProvision.stdout, "");
    assert.equal(
      malformedLedgerProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `ALTER TABLE public."_prisma_migrations"
         ALTER COLUMN checksum TYPE VARCHAR(64)
         USING checksum::VARCHAR(64);`,
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `UPDATE public."_prisma_migrations"
       SET rolled_back_at = CURRENT_TIMESTAMP
       WHERE migration_name =
         '20260720213000_exact_database_principal_closure_v9';`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const rolledBackMarkerProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(rolledBackMarkerProvision.code, 0);
    assert.equal(rolledBackMarkerProvision.stdout, "");
    assert.equal(
      rolledBackMarkerProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `UPDATE public."_prisma_migrations"
       SET rolled_back_at = NULL
       WHERE migration_name =
         '20260720213000_exact_database_principal_closure_v9';`,
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    // A structural mismatch must stop at the psql protocol boundary.  The
    // drifted SECURITY DEFINER body has a benign observable side effect so
    // this proves the archive hook and provisioner do not invoke unverified
    // privileged code while deciding to fail closed.
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE TABLE public.synthetic_helper_invocation_marker (
         invoked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
       );
       CREATE OR REPLACE FUNCTION
         public.quillmd_boundary_password_is_null(boundary_name TEXT)
       RETURNS BOOLEAN
       LANGUAGE plpgsql
       VOLATILE
       SECURITY DEFINER
       SET search_path = pg_catalog, public, pg_temp
       AS $observable_drift$
       BEGIN
         INSERT INTO public.synthetic_helper_invocation_marker DEFAULT VALUES;
         RETURN TRUE;
       END
       $observable_drift$;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const sourceDriftProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(sourceDriftProvision.code, 0);
    assert.equal(sourceDriftProvision.stdout, "");
    assert.equal(
      sourceDriftProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    assert.equal(
      await adminSql(
        sourceContainer,
        sourceDatabase,
        "SELECT COUNT(*) FROM public.synthetic_helper_invocation_marker;",
      ),
      "0",
      "unverified SECURITY DEFINER helper body must never be invoked",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      exactBoundaryPasswordFunctionSql.replace(
        "CREATE FUNCTION",
        "CREATE OR REPLACE FUNCTION",
      ),
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      "DROP TABLE public.synthetic_helper_invocation_marker;",
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    for (const boundary of ["quillmd_backup", "quillmd_runtime"] as const) {
      await adminSql(
        sourceContainer,
        sourceDatabase,
        `DO $password_drift$
         BEGIN
           EXECUTE pg_catalog.format(
             'ALTER ROLE %I PASSWORD %L',
             '${boundary}',
             pg_catalog.md5(
               pg_catalog.clock_timestamp()::TEXT ||
               pg_catalog.random()::TEXT
             )
           );
         END
         $password_drift$;`,
      );
      await assertPreflightFail(
        await preflight(
          sourceContainer,
          sourceDatabase,
          "/run/secrets/backup_password",
          "/run/secrets/backup_pgpass",
        ),
      );
      await adminSql(
        sourceContainer,
        sourceDatabase,
        `ALTER ROLE ${boundary} PASSWORD NULL;`,
      );
    }
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE EXECUTE ON FUNCTION
         public.quillmd_boundary_password_is_null(TEXT)
       FROM quillmd_backup;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const missingExpectedHelperGrant = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(missingExpectedHelperGrant.code, 0);
    assert.equal(missingExpectedHelperGrant.stdout, "");
    assert.equal(
      missingExpectedHelperGrant.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `GRANT EXECUTE ON FUNCTION
         public.quillmd_boundary_password_is_null(TEXT)
       TO quillmd_backup;`,
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `DROP FUNCTION public.quillmd_boundary_password_is_null(TEXT);`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const missingPostV9Helper = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(missingPostV9Helper.code, 0);
    assert.equal(missingPostV9Helper.stdout, "");
    assert.equal(
      missingPostV9Helper.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      exactBoundaryPasswordFunctionSql,
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `INSERT INTO public."_prisma_migrations" (
         id, checksum, finished_at, migration_name, applied_steps_count
       ) VALUES (
         '00000000-0000-0000-0000-000000000019',
         '${"1".repeat(64)}',
         CURRENT_TIMESTAMP,
         '20260720213000_exact_database_principal_closure_v9',
         1
       );`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const ambiguousV9Marker = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(ambiguousV9Marker.code, 0);
    assert.equal(ambiguousV9Marker.stdout, "");
    assert.equal(ambiguousV9Marker.stderr, "postgres-backup-principal: FAIL\n");
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `DELETE FROM public."_prisma_migrations"
       WHERE id = '00000000-0000-0000-0000-000000000019';`,
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `GRANT EXECUTE ON FUNCTION
         public.quillmd_boundary_password_is_null(TEXT) TO PUBLIC;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const helperAclDrift = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(helperAclDrift.code, 0);
    assert.equal(helperAclDrift.stdout, "");
    assert.equal(helperAclDrift.stderr, "postgres-backup-principal: FAIL\n");
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE EXECUTE ON FUNCTION
         public.quillmd_boundary_password_is_null(TEXT) FROM PUBLIC;`,
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE FUNCTION public.synthetic_unreviewed_backup_capability()
       RETURNS BOOLEAN LANGUAGE sql STABLE
       SET search_path = pg_catalog AS 'SELECT TRUE';
       REVOKE ALL ON FUNCTION
         public.synthetic_unreviewed_backup_capability() FROM PUBLIC;
       GRANT EXECUTE ON FUNCTION
         public.synthetic_unreviewed_backup_capability() TO quillmd_backup;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const additionalFunctionDependency = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(additionalFunctionDependency.code, 0);
    assert.equal(additionalFunctionDependency.stdout, "");
    assert.equal(
      additionalFunctionDependency.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE EXECUTE ON FUNCTION
         public.synthetic_unreviewed_backup_capability() FROM quillmd_backup;
       DROP FUNCTION public.synthetic_unreviewed_backup_capability();`,
    );
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_nul",
        "/run/secrets/backup_pgpass",
      ),
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_weak",
        "/run/secrets/backup_pgpass",
      ),
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE ROLE ${readClosureProbeRole} NOLOGIN;
       GRANT ${readClosureProbeRole} TO pg_read_all_data
         WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const readClosureProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(readClosureProvision.code, 0);
    assert.equal(readClosureProvision.stdout, "");
    assert.equal(
      readClosureProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE ${readClosureProbeRole} FROM pg_read_all_data;
       DROP ROLE ${readClosureProbeRole};`,
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `ALTER ROLE meddoc_backup
       PASSWORD 'md500000000000000000000000000000000';`,
    );
    assert.equal(
      await adminSql(
        sourceContainer,
        sourceDatabase,
        `SELECT public.quillmd_boundary_password_is_null('meddoc_backup');`,
      ),
      "f",
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
        "/var/run/postgresql",
      ),
    );
    const downgradedVerifierProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(downgradedVerifierProvision.code, 0);
    assert.equal(downgradedVerifierProvision.stdout, "");
    assert.equal(
      downgradedVerifierProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await setSyntheticRolePassword({
      container: sourceContainer,
      database: sourceDatabase,
      password: backupPassword,
    });
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    const graph = await adminSql(
      sourceContainer,
      sourceDatabase,
      `SELECT member_role.rolname || '>' || granted_role.rolname || '|' ||
          membership.admin_option || '|' || membership.inherit_option || '|' ||
          membership.set_option || '|' || grantor_role.rolsuper
       FROM pg_catalog.pg_auth_members membership
       JOIN pg_catalog.pg_roles member_role ON member_role.oid = membership.member
       JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = membership.roleid
       JOIN pg_catalog.pg_roles grantor_role ON grantor_role.oid = membership.grantor
       WHERE member_role.rolname IN (
         'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
       ) OR granted_role.rolname IN (
         'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
       ) OR grantor_role.rolname IN (
         'meddoc_backup', 'quillmd_backup', 'pg_read_all_data'
       )
       ORDER BY 1;`,
    );
    assert.equal(
      graph,
      [
        "meddoc_backup>quillmd_backup|false|true|false|true",
        "quillmd_backup>pg_read_all_data|false|true|false|true",
      ].join("\n"),
    );
    const clusterDatabaseDrift = await adminSql(
      sourceContainer,
      sourceDatabase,
      `SELECT COUNT(*)
       FROM pg_catalog.pg_database database_object
       WHERE pg_catalog.has_database_privilege(
         'meddoc_backup', database_object.oid, 'CONNECT'
       ) IS DISTINCT FROM (
         database_object.datname = pg_catalog.current_database()
       )
       OR pg_catalog.has_database_privilege(
         'meddoc_backup', database_object.oid, 'CREATE'
       )
       OR pg_catalog.has_database_privilege(
         'meddoc_backup', database_object.oid, 'TEMPORARY'
       );`,
    );
    assert.equal(clusterDatabaseDrift, "0");

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE ROLE ${graphProbeRole} NOLOGIN;
       GRANT ${graphProbeRole} TO meddoc_runtime
         WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const graphDriftProvision = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password",
    );
    assert.notEqual(graphDriftProvision.code, 0);
    assert.equal(graphDriftProvision.stdout, "");
    assert.equal(
      graphDriftProvision.stderr,
      "postgres-backup-principal: FAIL\n",
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE ${graphProbeRole} FROM meddoc_runtime;
       GRANT meddoc_runtime TO ${graphProbeRole}
         WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE meddoc_runtime FROM ${graphProbeRole};
       GRANT quillmd_runtime TO ${graphProbeRole}
         WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `REVOKE quillmd_runtime FROM ${graphProbeRole};
       DROP ROLE ${graphProbeRole};`,
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE ROLE meddoc_release_security LOGIN NOSUPERUSER NOCREATEDB
         NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS;
       GRANT quillmd_release_security TO meddoc_release_security
         WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;`,
    );
    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
      ),
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );

    const rlsRead = await backupSql(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass",
      `SELECT COUNT(*) || '|' || string_agg(synthetic_value, ',' ORDER BY synthetic_value)
       FROM clinical.synthetic_patient_records;`,
    );
    assert.equal(rlsRead.code, 0);
    assert.equal(rlsRead.stdout.trim(), "2|alpha,beta");
    const sequenceRead = await backupSql(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass",
      "SELECT last_value >= 41 FROM clinical.synthetic_record_sequence;",
    );
    assert.equal(sequenceRead.code, 0);
    assert.equal(sequenceRead.stdout.trim(), "t");

    for (const [label, sql] of [
      [
        "insert",
        "INSERT INTO clinical.synthetic_patient_records(practice_key, synthetic_value) VALUES ('synthetic-c','gamma')",
      ],
      [
        "update",
        "UPDATE clinical.synthetic_patient_records SET synthetic_value='changed'",
      ],
      ["delete", "DELETE FROM clinical.synthetic_patient_records"],
      ["truncate", "TRUNCATE clinical.synthetic_patient_records"],
      ["DDL", "CREATE TABLE clinical.synthetic_forbidden(id INTEGER)"],
      ["temporary DDL", "CREATE TEMP TABLE synthetic_forbidden(id INTEGER)"],
      ["boundary SET ROLE", "SET ROLE quillmd_backup"],
      ["predefined SET ROLE", "SET ROLE pg_read_all_data"],
      ["large-object create", "SELECT pg_catalog.lo_create(910001::oid)"],
      [
        "large-object from bytea",
        "SELECT pg_catalog.lo_from_bytea(0::oid, decode('00','hex'))",
      ],
      ["large-object unlink", "SELECT pg_catalog.lo_unlink(910001::oid)"],
    ] as const) {
      await expectBackupSqlRejected(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_pgpass",
        sql,
        label,
      );
    }
    await expectBackupSqlRejected(
      sourceContainer,
      "postgres",
      "/run/secrets/backup_pgpass",
      "SELECT 1",
      "non-application database CONNECT",
    );

    // Make three distinct changes that the provisioner repairs, then inject a
    // failure after every SQL postcondition but before COMMIT. Exact state,
    // including the old SCRAM verifier, must be restored atomically.
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `GRANT CONNECT ON DATABASE postgres TO PUBLIC;
       GRANT TEMPORARY ON DATABASE ${sourceDatabase} TO PUBLIC;
       GRANT EXECUTE ON FUNCTION pg_catalog.lo_create(OID) TO PUBLIC;
       REVOKE pg_read_all_data FROM quillmd_backup;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password",
        "/run/secrets/backup_pgpass",
      ),
    );
    const stateBeforeInjectedFailure = await adminSql(
      sourceContainer,
      sourceDatabase,
      exactStateSql,
    );
    const inducedFailure = await provision(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_password_next",
      "/opt/quillmd/provision-backup-principal-induced-failure",
    );
    assert.notEqual(inducedFailure.code, 0);
    assert.equal(inducedFailure.stdout, "");
    assert.equal(inducedFailure.stderr, "postgres-backup-principal: FAIL\n");
    const stateAfterInjectedFailure = await adminSql(
      sourceContainer,
      sourceDatabase,
      exactStateSql,
    );
    assert.equal(stateAfterInjectedFailure, stateBeforeInjectedFailure);

    const oldPasswordStillWorks = await backupSql(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass",
      "SELECT 1",
    );
    assert.equal(oldPasswordStillWorks.code, 0);
    await expectBackupSqlRejected(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass_next",
      "SELECT 1",
      "rolled-back backup password",
    );

    await assertProvisionPass(
      await provision(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
      ),
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
        "/run/secrets/backup_pgpass_next",
      ),
    );
    await expectBackupSqlRejected(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass",
      "SELECT 1",
      "rotated backup password",
    );

    const heldBackupConnection = backupSql(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass_next",
      "SELECT pg_sleep(3)",
    );
    let heldConnectionObserved = false;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const activeCount = await adminSql(
        sourceContainer,
        sourceDatabase,
        `SELECT COUNT(*) FROM pg_catalog.pg_stat_activity
         WHERE usename = 'meddoc_backup'
           AND state = 'active'
           AND query LIKE '%pg_sleep(3)%';`,
      );
      if (activeCount === "1") {
        heldConnectionObserved = true;
        break;
      }
      await new Promise((done) => setTimeout(done, 100));
    }
    assert(heldConnectionObserved, "held backup connection must be observed");
    await expectBackupSqlRejected(
      sourceContainer,
      sourceDatabase,
      "/run/secrets/backup_pgpass_next",
      "SELECT 1",
      "backup connection-limit second session",
    );
    const heldConnectionResult = await heldBackupConnection;
    assert.equal(heldConnectionResult.code, 0);

    await adminSql(
      sourceContainer,
      sourceDatabase,
      `CREATE FOREIGN DATA WRAPPER synthetic_backup_fdw NO HANDLER;
       CREATE SERVER synthetic_backup_server
         FOREIGN DATA WRAPPER synthetic_backup_fdw;
       CREATE FOREIGN TABLE clinical.synthetic_external_record(id INTEGER)
         SERVER synthetic_backup_server;`,
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
        "/run/secrets/backup_pgpass_next",
      ),
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      `DROP FOREIGN TABLE clinical.synthetic_external_record;
       DROP SERVER synthetic_backup_server;
       DROP FOREIGN DATA WRAPPER synthetic_backup_fdw;`,
    );

    await adminSql(
      sourceContainer,
      sourceDatabase,
      "SELECT pg_catalog.lo_create(920001::oid);",
    );
    await assertPreflightFail(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
        "/run/secrets/backup_pgpass_next",
      ),
    );
    await adminSql(
      sourceContainer,
      sourceDatabase,
      "SELECT pg_catalog.lo_unlink(920001::oid);",
    );
    await assertPreflightPass(
      await preflight(
        sourceContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
        "/run/secrets/backup_pgpass_next",
      ),
    );

    const sourceAcl = await adminSql(
      sourceContainer,
      sourceDatabase,
      applicationAclSql,
    );
    await docker(
      [
        "run",
        "--rm",
        "--network",
        `container:${sourceContainer}`,
        "--user",
        "999:999",
        "--cap-drop",
        "ALL",
        "--env",
        "POSTGRES_HOST=127.0.0.1",
        "--env",
        "POSTGRES_PORT=5432",
        "--env",
        `POSTGRES_DB=${sourceDatabase}`,
        "--env",
        "POSTGRES_USER=meddoc_backup",
        "--env",
        "POSTGRES_PASSWORD_FILE=/run/secrets/backup_password",
        "--env",
        "PGAPPNAME=meddoc-postgres-backup",
        "--env",
        `POSTGRES_EXTRA_OPTS=${BACKUP_OPTIONS}`,
        "--env",
        "BACKUP_SUFFIX=.dump",
        "--env",
        "BACKUP_DIR=/backups",
        "--mount",
        `type=bind,src=${nextBackupSecret},dst=/run/secrets/backup_password,readonly`,
        "--mount",
        `type=bind,src=${join(repoRoot, "infra/postgres-backup/hooks")},dst=/hooks,readonly`,
        "--mount",
        `type=bind,src=${backupOutputDirectory},dst=/backups`,
        BACKUP_IMAGE,
        "/backup.sh",
      ],
      "pinned backup image custom archive",
    );
    const archivePath = await realpath(
      join(backupOutputDirectory, "last", `${sourceDatabase}-latest.dump`),
    );
    const archiveHeader = await readFile(archivePath);
    assert.equal(
      archiveHeader.subarray(0, 5).toString("ascii"),
      "PGDMP",
      "pinned backup image must emit a custom-format .dump archive",
    );

    createdContainers.push(restoreContainer);
    await startContainer({
      ...containerInput,
      name: restoreContainer,
      database: "postgres",
    });
    await adminSql(restoreContainer, "postgres", boundaryRoleSql);
    await docker(
      ["cp", archivePath, `${restoreContainer}:/tmp/meddoc-backup-test.dump`],
      "copy archive into disposable restore",
    );
    await docker(
      [
        ...execArgs(restoreContainer),
        "pg_restore",
        "--exit-on-error",
        "--no-owner",
        "--create",
        "--username",
        "postgres",
        "--dbname",
        "postgres",
        "/tmp/meddoc-backup-test.dump",
      ],
      "disposable no-egress restore",
    );
    const restoredAcl = await adminSql(
      restoreContainer,
      sourceDatabase,
      applicationAclSql,
    );
    assert.equal(
      restoredAcl,
      sourceAcl,
      "application ACLs must survive restore",
    );
    const restoredRows = await adminSql(
      restoreContainer,
      sourceDatabase,
      `SET row_security = off;
       SELECT COUNT(*) || '|' || string_agg(synthetic_value, ',' ORDER BY synthetic_value)
       FROM clinical.synthetic_patient_records;`,
    );
    assert.equal(restoredRows, "2|alpha,beta");

    // Role membership and pg_catalog LO ACLs are cluster/bootstrap state, not
    // application-dump state. Reapply the same privileged provisioner before
    // the restored backup service is allowed to run.
    await assertProvisionPass(
      await provision(
        restoreContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
      ),
    );
    await assertPreflightPass(
      await preflight(
        restoreContainer,
        sourceDatabase,
        "/run/secrets/backup_password_next",
        "/run/secrets/backup_pgpass_next",
      ),
    );

    printfPass();
  } finally {
    for (const container of createdContainers.reverse()) {
      await command("docker", ["rm", "--force", container]);
    }
    await command("docker", [
      "run",
      "--rm",
      "--network",
      "none",
      "--mount",
      `type=bind,src=${tempDirectory},dst=/target`,
      "--entrypoint",
      "chown",
      POSTGRES_IMAGE,
      "-R",
      `${process.getuid()}:${process.getgid()}`,
      "/target",
    ]);
    await rm(tempDirectory, { recursive: true, force: true });
  }
}

function printfPass(): void {
  process.stdout.write("postgres-backup-principal-pg-test: PASS\n");
}

main().catch((error: unknown) => {
  const message =
    error instanceof Error ? (error.stack ?? error.message) : "unknown failure";
  process.stderr.write(
    `postgres-backup-principal-pg-test: FAIL: ${redact(message)}\n`,
  );
  process.exitCode = 1;
});
