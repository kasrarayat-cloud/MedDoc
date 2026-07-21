#!/usr/bin/env tsx

// Pinned PostgreSQL 16 proof for the immutable host-authentication image.
// The harness owns its random image/container/volume and synthetic credential,
// emits no child output, and always removes only those exact resources.

import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const POSTGRES_DOCKERFILE = "infra/postgres/Dockerfile";
const POSTGRES_BUILD_CONTEXT = "infra/postgres";
const HBA_CONTAINER_PATH = "/etc/postgresql/quillmd-pg_hba.conf";
const VERIFIER_CONTAINER_PATH = "/opt/quillmd/verify-quillmd-host-auth.sh";
const TEST_PASSWORD_PATH = "/run/quillmd-test/postgres-password";
const WEAK_HBA_PATH = "/run/quillmd-test/weak-pg_hba.conf";
const POSTGRES_TMPFS =
  "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=3777";
const GENERAL_TMPFS = "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777";
const HBA_SHA256 =
  "8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0";
const repositoryRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

interface CommandResult {
  status: number | null;
  signal: NodeJS.Signals | null;
  stdout: string;
  stderr: string;
}

type DockerResourceKind = "container" | "image" | "volume";

function docker(args: string[], timeout = 30_000): CommandResult {
  const result = spawnSync("docker", args, {
    encoding: "utf8",
    timeout,
    maxBuffer: 4 * 1024 * 1024,
    env: process.env,
  });
  return {
    status: result.status,
    signal: result.signal,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

function requireSuccess(label: string, args: string[], timeout?: number): void {
  const result = docker(args, timeout);
  if (result.status !== 0 || result.signal !== null) {
    throw new Error(label);
  }
}

function requireFailure(
  label: string,
  args: string[],
  expectedMessage?: string,
): void {
  const result = docker(args);
  if ((result.status ?? 0) === 0) throw new Error(`${label}_SUCCEEDED`);
  if (result.signal !== null) throw new Error(`${label}_SIGNALLED`);
  if (
    expectedMessage !== undefined &&
    !result.stderr.includes(expectedMessage)
  ) {
    throw new Error(`${label}_MESSAGE_INEXACT`);
  }
}

function requireExactOutput(
  label: string,
  args: string[],
  expected: string,
): void {
  const result = docker(args);
  if (
    result.status !== 0 ||
    result.signal !== null ||
    result.stdout.trim() !== expected
  ) {
    throw new Error(label);
  }
}

function isOwnedResource(
  kind: DockerResourceKind,
  name: string,
  ownershipLabel: string,
): boolean {
  const result = docker([kind, "inspect", name]);
  if (result.status !== 0 || result.signal !== null) return false;
  try {
    const rows = JSON.parse(result.stdout) as Array<{
      Config?: { Labels?: Record<string, string> };
      Labels?: Record<string, string>;
    }>;
    const labels =
      kind === "volume" ? rows[0]?.Labels : rows[0]?.Config?.Labels;
    return labels?.["com.quillmd.synthetic-test-owner"] === ownershipLabel;
  } catch {
    return false;
  }
}

function waitForVerifier(containerName: string): void {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const result = docker([
      "exec",
      containerName,
      "/bin/sh",
      VERIFIER_CONTAINER_PATH,
    ]);
    if (result.status === 0 && result.signal === null) return;
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 250);
  }
  const diagnostic = docker([
    "exec",
    containerName,
    "psql",
    "-X",
    "--no-psqlrc",
    "--quiet",
    "--tuples-only",
    "--no-align",
    "--field-separator",
    "|",
    "--username",
    "meddoc",
    "--dbname",
    "meddoc_hba_contract_test",
    "--command",
    `SELECT
       pg_catalog.current_setting('server_version_num')::INTEGER
         BETWEEN 160000 AND 169999,
       pg_catalog.current_setting('hba_file') = '${HBA_CONTAINER_PATH}',
       pg_catalog.current_setting('password_encryption') = 'scram-sha-256',
       pg_catalog.current_setting('quillmd.hba_contract_sha256', TRUE) =
         '${HBA_SHA256}',
       pg_catalog.inet_client_addr() IS NULL,
       pg_catalog.pg_conf_load_time() <=
         pg_catalog.pg_postmaster_start_time(),
       (SELECT COUNT(*) = 6 AND pg_catalog.bool_and(error IS NULL)
          FROM pg_catalog.pg_hba_file_rules)`,
  ]);
  if (diagnostic.status !== 0 || diagnostic.signal !== null) {
    throw new Error("POSTGRES_HOST_AUTH_STARTUP_DATABASE_UNAVAILABLE");
  }
  const predicates = diagnostic.stdout.trim().split("|");
  const failed = predicates.findIndex((value) => value !== "t");
  if (failed >= 0) {
    throw new Error(`POSTGRES_HOST_AUTH_STARTUP_PREDICATE_${failed + 1}`);
  }
  throw new Error("POSTGRES_HOST_AUTH_STARTUP_RULES_INEXACT");
}

function tcpPsqlArgs(
  containerName: string,
  host: string,
  user: string,
  passwordExpression: string,
): string[] {
  return [
    "exec",
    containerName,
    "/bin/sh",
    "-ec",
    `PGPASSWORD=${passwordExpression} exec psql -X --no-psqlrc --quiet --tuples-only --no-align --set ON_ERROR_STOP=1 --host '${host}' --port 5432 --username '${user}' --dbname meddoc_hba_contract_test --command 'SELECT 1'`,
  ];
}

async function main(): Promise<void> {
  const root = mkdtempSync(join(tmpdir(), "quillmd-hba-pg-"));
  chmodSync(root, 0o700);
  const suffix = `${process.pid}-${randomBytes(6).toString("hex")}`;
  const containerName = `quillmd-hba-contract-${suffix}`;
  const weakContainerName = `quillmd-hba-weak-${suffix}`;
  const volumeName = `quillmd-hba-pgdata-${suffix}`;
  const imageTag = `quillmd-postgres-hba-test:${suffix}`;
  const ownershipLabel = `postgres-host-auth-${suffix}`;
  const passwordPath = join(root, "postgres-password");
  const weakHbaPath = join(root, "weak-pg_hba.conf");
  const environmentPath = join(root, "postgres.env");
  const password = randomBytes(32).toString("base64url");
  // The 0700 parent protects these host files. The container's unprivileged
  // postgres UID still needs read access through each exact read-only bind.
  writeFileSync(passwordPath, `${password}\n`, { mode: 0o444 });
  writeFileSync(
    weakHbaPath,
    ["local all all trust", "host all all all trust", ""].join("\n"),
    { mode: 0o444 },
  );
  writeFileSync(
    environmentPath,
    [
      "POSTGRES_USER=meddoc",
      "POSTGRES_DB=meddoc_hba_contract_test",
      `POSTGRES_PASSWORD=${password}`,
      "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=trust",
      "",
    ].join("\n"),
    { mode: 0o600 },
  );

  try {
    requireSuccess(
      "POSTGRES_HOST_AUTH_IMAGE_BUILD_FAILED",
      [
        "build",
        "--file",
        resolve(repositoryRoot, POSTGRES_DOCKERFILE),
        "--tag",
        imageTag,
        "--label",
        `com.quillmd.synthetic-test-owner=${ownershipLabel}`,
        resolve(repositoryRoot, POSTGRES_BUILD_CONTEXT),
      ],
      120_000,
    );

    // The image wrapper must reject an otherwise runnable server invocation
    // that attempts to select weaker startup bytes after image verification.
    requireFailure(
      "POSTGRES_HOST_AUTH_WEAK_START_ADMITTED",
      [
        "run",
        "--rm",
        "--name",
        weakContainerName,
        "--label",
        `com.quillmd.synthetic-test-owner=${ownershipLabel}`,
        "--read-only",
        "--user",
        "999:999",
        "--cap-drop",
        "ALL",
        "--tmpfs",
        GENERAL_TMPFS,
        "--tmpfs",
        POSTGRES_TMPFS,
        "--env-file",
        environmentPath,
        "--mount",
        `type=bind,source=${weakHbaPath},target=${WEAK_HBA_PATH},readonly`,
        imageTag,
        "postgres",
        "-c",
        `hba_file=${WEAK_HBA_PATH}`,
        "-c",
        "password_encryption=scram-sha-256",
        "-c",
        `quillmd.hba_contract_path=${WEAK_HBA_PATH}`,
        "-c",
        `quillmd.hba_contract_sha256=${HBA_SHA256}`,
      ],
      "QUILLMD_POSTGRES_IMAGE_CONTRACT_FAIL",
    );

    // A direct runtime mount can shadow an image path even on a read-only
    // root filesystem. The pre-entrypoint byte proof must reject that case
    // while the exact default argv remains otherwise unchanged.
    requireFailure(
      "POSTGRES_HOST_AUTH_WEAK_BYTES_START_ADMITTED",
      [
        "run",
        "--rm",
        "--name",
        weakContainerName,
        "--label",
        `com.quillmd.synthetic-test-owner=${ownershipLabel}`,
        "--read-only",
        "--user",
        "999:999",
        "--cap-drop",
        "ALL",
        "--tmpfs",
        GENERAL_TMPFS,
        "--tmpfs",
        POSTGRES_TMPFS,
        "--env-file",
        environmentPath,
        "--mount",
        `type=bind,source=${weakHbaPath},target=${HBA_CONTAINER_PATH},readonly`,
        imageTag,
      ],
      "QUILLMD_POSTGRES_IMAGE_CONTRACT_FAIL",
    );

    requireSuccess("POSTGRES_HOST_AUTH_VOLUME_CREATE_FAILED", [
      "volume",
      "create",
      "--label",
      `com.quillmd.synthetic-test-owner=${ownershipLabel}`,
      volumeName,
    ]);
    requireSuccess("POSTGRES_HOST_AUTH_CONTAINER_START_FAILED", [
      "run",
      "--detach",
      "--name",
      containerName,
      "--label",
      `com.quillmd.synthetic-test-owner=${ownershipLabel}`,
      "--read-only",
      "--user",
      "999:999",
      "--cap-drop",
      "ALL",
      "--tmpfs",
      GENERAL_TMPFS,
      "--tmpfs",
      POSTGRES_TMPFS,
      "--env-file",
      environmentPath,
      "--mount",
      `type=volume,source=${volumeName},target=/var/lib/postgresql/data`,
      "--mount",
      `type=bind,source=${passwordPath},target=${TEST_PASSWORD_PATH},readonly`,
      imageTag,
    ]);
    waitForVerifier(containerName);

    requireExactOutput(
      "POSTGRES_HOST_AUTH_ROOTFS_NOT_READ_ONLY",
      ["inspect", "--format", "{{.HostConfig.ReadonlyRootfs}}", containerName],
      "true",
    );
    requireFailure("POSTGRES_HOST_AUTH_ROOTFS_MUTATION_ADMITTED", [
      "exec",
      "--user",
      "0:0",
      containerName,
      "/bin/sh",
      "-ec",
      "printf '%s\\n' unreviewed > /etc/postgresql/quillmd-unreviewed.conf",
    ]);
    requireSuccess("POSTGRES_HOST_AUTH_EMBEDDED_BYTES_DRIFT", [
      "exec",
      containerName,
      "/bin/sh",
      "-ec",
      `test "$(sha256sum '${HBA_CONTAINER_PATH}' | cut -d ' ' -f 1)" = '${HBA_SHA256}'`,
    ]);

    const passwordFromFile = `"$(cat '${TEST_PASSWORD_PATH}')"`;
    requireSuccess(
      "POSTGRES_HOST_AUTH_IPV4_OWNER_REJECTED",
      tcpPsqlArgs(containerName, "127.0.0.1", "meddoc", passwordFromFile),
    );
    requireSuccess(
      "POSTGRES_HOST_AUTH_IPV6_OWNER_REJECTED",
      tcpPsqlArgs(containerName, "::1", "meddoc", passwordFromFile),
    );
    requireFailure(
      "POSTGRES_HOST_AUTH_WRONG_PASSWORD_ADMITTED",
      tcpPsqlArgs(containerName, "127.0.0.1", "meddoc", "synthetic-wrong"),
      "password authentication failed",
    );
    requireFailure(
      "POSTGRES_HOST_AUTH_UNKNOWN_LOGIN_ADMITTED",
      tcpPsqlArgs(
        containerName,
        "127.0.0.1",
        "quillmd_unknown_test",
        "synthetic-wrong",
      ),
      "pg_hba.conf rejects connection",
    );
    requireFailure(
      "POSTGRES_HOST_AUTH_REPLICATION_ADMITTED",
      [
        "exec",
        containerName,
        "/bin/sh",
        "-ec",
        `PGPASSWORD=${passwordFromFile} exec psql -X --no-psqlrc --quiet --set ON_ERROR_STOP=1 'host=127.0.0.1 port=5432 user=meddoc dbname=replication replication=database' --command 'IDENTIFY_SYSTEM'`,
      ],
      "replication",
    );

    // The embedded bytes cannot change, but any post-start configuration
    // reload invalidates the startup-generation proof until an exact restart.
    requireSuccess("POSTGRES_HOST_AUTH_RELOAD_FAILED", [
      "exec",
      containerName,
      "psql",
      "-X",
      "--no-psqlrc",
      "--quiet",
      "--username",
      "meddoc",
      "--dbname",
      "meddoc_hba_contract_test",
      "--command",
      "SELECT pg_catalog.pg_reload_conf()",
    ]);
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const loaded = docker([
        "exec",
        containerName,
        "psql",
        "-X",
        "--no-psqlrc",
        "--quiet",
        "--tuples-only",
        "--no-align",
        "--username",
        "meddoc",
        "--dbname",
        "meddoc_hba_contract_test",
        "--command",
        "SELECT pg_catalog.pg_conf_load_time() > pg_catalog.pg_postmaster_start_time()",
      ]);
      if (loaded.status === 0 && loaded.stdout.trim() === "t") break;
      if (attempt === 39) throw new Error("POSTGRES_HOST_AUTH_RELOAD_UNPROVEN");
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
    }
    requireFailure(
      "POSTGRES_HOST_AUTH_RELOAD_ADMITTED",
      ["exec", containerName, "/bin/sh", VERIFIER_CONTAINER_PATH],
      "QUILLMD_POSTGRES_HOST_AUTH_FAIL",
    );

    requireSuccess("POSTGRES_HOST_AUTH_RESTART_FAILED", [
      "restart",
      containerName,
    ]);
    waitForVerifier(containerName);
    process.stdout.write("POSTGRES_HOST_AUTH_PG_TEST_PASS\n");
  } finally {
    if (isOwnedResource("container", weakContainerName, ownershipLabel)) {
      docker(["container", "rm", "--force", weakContainerName]);
    }
    if (isOwnedResource("container", containerName, ownershipLabel)) {
      docker(["container", "rm", "--force", containerName]);
    }
    if (isOwnedResource("volume", volumeName, ownershipLabel)) {
      docker(["volume", "rm", "--force", volumeName]);
    }
    if (isOwnedResource("image", imageTag, ownershipLabel)) {
      docker(["image", "rm", "--force", imageTag]);
    }
    rmSync(root, { recursive: true, force: true });
  }
}

void main().catch((error: unknown) => {
  const code =
    error instanceof Error &&
    /^POSTGRES_HOST_AUTH_[A-Z0-9_]{2,80}$/u.test(error.message)
      ? error.message
      : "POSTGRES_HOST_AUTH_PG_TEST_FAIL";
  process.stderr.write(`${code}\n`);
  process.exitCode = 1;
});
