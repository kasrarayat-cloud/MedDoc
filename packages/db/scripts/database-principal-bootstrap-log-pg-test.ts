#!/usr/bin/env tsx

// Pinned-PostgreSQL proof that principal bootstrap credentials never enter
// argv, SQL files, activity text, or maximally enabled statement/duration
// logs. All generated containers and files are disposable and synthetic.

import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const repositoryRoot = resolve(import.meta.dirname, "../../..");
const initScript = resolve(
  repositoryRoot,
  "infra/postgres/init-template-twin-roles.sh",
);
const releaseSecurityScript = resolve(
  repositoryRoot,
  "infra/postgres/provision-template-twin-release-security.sh",
);
const image =
  "pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff";
const suffix = randomBytes(8).toString("hex");
const container = `meddoc-principal-log-test-${suffix}`;
const database = `meddoc_principal_log_test_${suffix}`;
const scratch = mkdtempSync(`${tmpdir()}/meddoc-principal-log-test-`);

type CommandResult = ReturnType<typeof spawnSync>;

function run(
  command: string,
  args: string[],
  timeout = 120_000,
): CommandResult {
  return spawnSync(command, args, {
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
    timeout,
    env: {
      PATH: process.env.PATH,
      DOCKER_HOST: process.env.DOCKER_HOST,
    },
  });
}

function requireSuccess(result: CommandResult, label: string): void {
  if (
    result.status !== 0 &&
    process.env.DATABASE_PRINCIPAL_BOOTSTRAP_TEST_DEBUG === "true"
  ) {
    const output = combinedOutput(result);
    assertNoCredentialEvidence(output);
    process.stderr.write(`${label}: ${output.slice(0, 2_000)}\n`);
  }
  assert.equal(result.status, 0, `${label} must succeed`);
  assert.equal(result.signal, null, `${label} must not time out`);
}

function secret(): string {
  const value = randomBytes(32).toString("base64url");
  assert.match(value, /^[A-Za-z0-9_-]{43}$/u);
  return value;
}

const secrets = {
  postgres: secret(),
  runtime: secret(),
  releaseControl: secret(),
  releaseSecurity: secret(),
  audit: secret(),
  authEmail: secret(),
  backup: secret(),
};

function writePrivate(path: string, body: string): void {
  writeFileSync(path, body, { encoding: "utf8", mode: 0o600 });
  chmodSync(path, 0o600);
}

function writeMountedSecret(path: string, body: string): void {
  writeFileSync(path, body, { encoding: "utf8", mode: 0o400 });
  // The pinned image executes init hooks as its unprivileged postgres UID;
  // read-only bind mounts do not remap the host owner.
  chmodSync(path, 0o444);
}

function environmentFile(input: {
  path: string;
  systemIdentifier?: string;
  runtimeSecret?: string;
  backupFile?: string;
}): void {
  const lines = [
    `POSTGRES_USER=meddoc`,
    `POSTGRES_DB=${database}`,
    `POSTGRES_PASSWORD=${secrets.postgres}`,
    `DB_RUNTIME_PASSWORD=${input.runtimeSecret ?? secrets.runtime}`,
    `DB_RELEASE_CONTROL_PASSWORD=${secrets.releaseControl}`,
    `DB_RELEASE_SECURITY_PASSWORD=${secrets.releaseSecurity}`,
    `DB_AUDIT_DISPATCHER_PASSWORD=${secrets.audit}`,
    `DB_AUTH_EMAIL_DISPATCHER_PASSWORD=${secrets.authEmail}`,
    `DB_BACKUP_PASSWORD_FILE=${input.backupFile ?? "/run/secrets/backup_password"}`,
  ];
  if (input.systemIdentifier) {
    lines.push(`DB_EXPECTED_SYSTEM_IDENTIFIER=${input.systemIdentifier}`);
  }
  writePrivate(input.path, `${lines.join("\n")}\n`);
}

function combinedOutput(result: CommandResult): string {
  return `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
}

function assertNoCredentialEvidence(text: string): void {
  for (const value of Object.values(secrets)) {
    assert(!text.includes(value), "credential plaintext must be absent");
    assert(
      !text.includes(Buffer.from(value, "utf8").toString("base64")),
      "reversible credential encoding must be absent",
    );
  }
  assert(!/SCRAM-SHA-256\$4096:/u.test(text), "SCRAM verifier must be absent");
}

async function waitForDatabase(): Promise<void> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const logs = run("docker", ["logs", container], 5_000);
    const initComplete = combinedOutput(logs).includes(
      "PostgreSQL init process complete; ready for start up.",
    );
    const ready = run(
      "docker",
      ["exec", container, "pg_isready", "-U", "meddoc", "-d", database, "-q"],
      5_000,
    );
    if (initComplete && ready.status === 0) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error("Pinned PostgreSQL did not become ready");
}

async function main(): Promise<void> {
  const backupFile = `${scratch}/backup-password`;
  const invalidBackupFile = `${scratch}/invalid-backup-password`;
  const initialEnvironment = `${scratch}/initial.env`;
  const invalidEnvironment = `${scratch}/invalid.env`;
  const releaseEnvironment = `${scratch}/release.env`;
  const wrongTargetEnvironment = `${scratch}/wrong-target.env`;
  writeMountedSecret(backupFile, secrets.backup);
  // A legacy generic 43-byte value must not cross the generated-base64url
  // boundary shared by fresh init and the backup sidecar.
  writeMountedSecret(invalidBackupFile, `${"A".repeat(42)}+`);
  environmentFile({ path: initialEnvironment });

  const start = run("docker", [
    "run",
    "--detach",
    "--name",
    container,
    "--env-file",
    initialEnvironment,
    "--mount",
    `type=bind,src=${backupFile},dst=/run/secrets/backup_password,readonly`,
    "--mount",
    `type=bind,src=${invalidBackupFile},dst=/run/secrets/invalid_backup_password,readonly`,
    "--mount",
    `type=bind,src=${initScript},dst=/docker-entrypoint-initdb.d/20-template-twin-roles.sh,readonly`,
    "--mount",
    `type=bind,src=${releaseSecurityScript},dst=/usr/local/bin/provision-release-security,readonly`,
    image,
    "-c",
    "log_statement=all",
    "-c",
    "log_duration=on",
    "-c",
    "log_min_duration_statement=0",
    "-c",
    "log_min_error_statement=debug5",
    "-c",
    "log_connections=on",
    "-c",
    "log_disconnections=on",
  ]);
  requireSuccess(start, "pinned PostgreSQL start");
  assertNoCredentialEvidence(combinedOutput(start));
  await waitForDatabase();

  const systemIdentifierResult = run("docker", [
    "exec",
    container,
    "psql",
    "-X",
    "-U",
    "meddoc",
    "-d",
    database,
    "-Atqc",
    "SELECT system_identifier::TEXT FROM pg_catalog.pg_control_system()",
  ]);
  requireSuccess(systemIdentifierResult, "system identifier read");
  const systemIdentifier = String(systemIdentifierResult.stdout).trim();
  assert.match(systemIdentifier, /^[0-9]+$/u);

  environmentFile({
    path: releaseEnvironment,
    systemIdentifier,
  });
  const release = run("docker", [
    "exec",
    "--env-file",
    releaseEnvironment,
    container,
    "/usr/local/bin/provision-release-security",
  ]);
  requireSuccess(release, "release-security provisioner");
  assertNoCredentialEvidence(combinedOutput(release));

  const verifierProof = run("docker", [
    "exec",
    container,
    "psql",
    "-X",
    "-U",
    "meddoc",
    "-d",
    database,
    "-Atqc",
    `SELECT
       count(*) FILTER (
         WHERE rolname LIKE 'meddoc_%'
           AND rolpassword LIKE 'SCRAM-SHA-256$%'
       ) = 6
       AND count(*) FILTER (
         WHERE rolname LIKE 'quillmd_%'
           AND rolcanlogin = FALSE
           AND rolpassword IS NULL
       ) = 6
     FROM pg_catalog.pg_authid
     WHERE rolname LIKE 'meddoc_%' OR rolname LIKE 'quillmd_%'`,
  ]);
  requireSuccess(verifierProof, "catalog verifier proof");
  assert.equal(String(verifierProof.stdout).trim(), "t");

  environmentFile({
    path: invalidEnvironment,
    runtimeSecret: `${"A".repeat(42)}+`,
    backupFile: "/run/secrets/invalid_backup_password",
  });
  const invalidRuntime = run("docker", [
    "exec",
    "--env-file",
    invalidEnvironment,
    container,
    "/docker-entrypoint-initdb.d/20-template-twin-roles.sh",
  ]);
  assert.notEqual(invalidRuntime.status, 0);
  assertNoCredentialEvidence(combinedOutput(invalidRuntime));

  environmentFile({
    path: invalidEnvironment,
    backupFile: "/run/secrets/invalid_backup_password",
  });
  const invalidBackup = run("docker", [
    "exec",
    "--env-file",
    invalidEnvironment,
    container,
    "/docker-entrypoint-initdb.d/20-template-twin-roles.sh",
  ]);
  assert.notEqual(invalidBackup.status, 0);
  assertNoCredentialEvidence(combinedOutput(invalidBackup));

  const wrongSystemIdentifier = `${systemIdentifier.slice(0, -1)}${
    systemIdentifier.endsWith("0") ? "1" : "0"
  }`;
  environmentFile({
    path: wrongTargetEnvironment,
    systemIdentifier: wrongSystemIdentifier,
  });
  const wrongTarget = run("docker", [
    "exec",
    "--env-file",
    wrongTargetEnvironment,
    container,
    "/usr/local/bin/provision-release-security",
  ]);
  assert.notEqual(wrongTarget.status, 0);
  assertNoCredentialEvidence(combinedOutput(wrongTarget));

  const logs = run("docker", ["logs", container]);
  requireSuccess(logs, "PostgreSQL log collection");
  assertNoCredentialEvidence(combinedOutput(logs));

  const runningCommandLines = run("docker", [
    "top",
    container,
    "-eo",
    "pid,args",
  ]);
  requireSuccess(runningCommandLines, "container command-line proof");
  assertNoCredentialEvidence(combinedOutput(runningCommandLines));

  process.stdout.write("DATABASE_PRINCIPAL_BOOTSTRAP_LOG_PG_TEST_PASS\n");
}

void main()
  .catch((error: unknown) => {
    process.stderr.write("DATABASE_PRINCIPAL_BOOTSTRAP_LOG_PG_TEST_FAIL\n");
    if (process.env.DATABASE_PRINCIPAL_BOOTSTRAP_TEST_DEBUG === "true") {
      process.stderr.write(
        `${error instanceof Error ? error.message : "unknown failure"}\n`,
      );
      const debugLogs = run("docker", ["logs", container]);
      const debugOutput = combinedOutput(debugLogs);
      assertNoCredentialEvidence(debugOutput);
      process.stderr.write(`${debugOutput.slice(-4_000)}\n`);
    }
    process.exitCode = 1;
  })
  .finally(() => {
    run("docker", ["rm", "--force", container], 30_000);
    rmSync(scratch, { recursive: true, force: true });
  });
