#!/usr/bin/env tsx

/**
 * Disposable PostgreSQL proof for the rollout-generation migration lock bound.
 *
 * The harness uses the real Prisma migration runner twice: once while a
 * deterministic conflicting table lock is held, and once after Prisma marks
 * that failed attempt rolled back. It never accepts an external database URL.
 * All identities and database names are synthetic and the container is removed
 * in finally.
 */

import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  cpSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";

import { Client } from "pg";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(SCRIPT_DIR, "../../..");
const DB_PACKAGE = path.join(ROOT, "packages/db");
const MIGRATIONS = path.join(DB_PACKAGE, "prisma/migrations");
const TARGET = "20260716113000_template_twin_rollout_generations";
const TARGET_SOURCE = path.join(MIGRATIONS, TARGET);
const PRISMA = path.join(ROOT, "node_modules/.bin/prisma");
const IMAGE =
  process.env.TEMPLATE_TWIN_ROLLOUT_LOCK_POSTGRES_IMAGE ??
  "pgvector/pgvector:pg16";
const CONTAINER = `meddoc-rollout-migration-lock-${process.pid}`;
const SYNTHETIC_PASSWORD = "synthetic-rollout-migration-lock-only";
const EVIDENCE_PATH =
  process.env.TEMPLATE_TWIN_ROLLOUT_LOCK_EVIDENCE_PATH ??
  "/tmp/template-twin-rollout-migration-lock-evidence.json";

interface CommandResult {
  status: number;
  stdout: string;
  stderr: string;
  durationMs: number;
}

interface AbsentShape {
  practiceGenerationColumnCount: number;
  rolloutControlTableCount: number;
  fillGenerationColumnCount: number;
  rolloutFunctionCount: number;
  rolloutTriggerCount: number;
  rolloutConstraintCount: number;
}

interface InstalledShape extends AbsentShape {
  globalEnabled: boolean;
  globalGeneration: string;
  practiceEnabled: boolean;
  practiceGeneration: string;
}

interface ScenarioEvidence {
  scenario: "early_practice_lock" | "late_fill_manifest_lock";
  blockedTable: "practices" | "template_twin_fill_manifests";
  blockerLockMode: "ACCESS SHARE";
  blockerLockGrantedBeforeDeploy: boolean;
  failedDeployDurationMs: number;
  failedDeployExitCode: number;
  prismaReportedP3018: boolean;
  prismaReportedAbortedTransaction: boolean;
  postgresReportedLockTimeout: boolean;
  failedMigrationRowPresent: boolean;
  failedMigrationUnfinished: boolean;
  failedMigrationNotPretendedSuccessful: boolean;
  rollbackWasAtomic: boolean;
  syntheticPracticeUnchangedAfterTimeout: boolean;
  resolveRolledBackExitCode: number;
  retryDeployExitCode: number;
  noPendingRetryExitCode: number;
  retryInstalledCompleteContract: boolean;
  syntheticPracticeUnchangedAfterRetry: boolean;
  failedAttemptMarkedRolledBack: boolean;
  successfulAttemptRecorded: boolean;
}

function progress(message: string): void {
  process.stderr.write(`[rollout-migration-lock-test] ${message}\n`);
}

function run(
  command: string,
  args: string[],
  options: { cwd?: string; env?: NodeJS.ProcessEnv } = {},
): CommandResult {
  const started = performance.now();
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? ROOT,
    env: options.env ?? process.env,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  return {
    status: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
    durationMs: performance.now() - started,
  };
}

function checked(command: string, args: string[]): string {
  const result = run(command, args);
  if (result.status !== 0) {
    throw new Error(
      `Disposable command failed (${path.basename(command)} exit ${result.status}).`,
    );
  }
  return result.stdout.trim();
}

function waitForPostgres(): void {
  const waitBuffer = new Int32Array(new SharedArrayBuffer(4));
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const logs = run("docker", ["logs", CONTAINER]);
    const initializationComplete = `${logs.stdout}\n${logs.stderr}`.includes(
      "PostgreSQL init process complete; ready for start up.",
    );
    const ready = run("docker", [
      "exec",
      CONTAINER,
      "pg_isready",
      "-U",
      "postgres",
      "-d",
      "postgres",
    ]);
    if (initializationComplete && ready.status === 0) return;
    Atomics.wait(waitBuffer, 0, 0, 100);
  }
  throw new Error("Disposable PostgreSQL did not become ready.");
}

function preparePrismaWorkspace(scenario: string): string {
  const workspace = mkdtempSync(
    path.join(tmpdir(), `template-twin-rollout-lock-${scenario}-`),
  );
  const prismaDir = path.join(workspace, "prisma");
  const migrationDir = path.join(prismaDir, "migrations");
  mkdirSync(migrationDir, { recursive: true });
  copyFileSync(
    path.join(DB_PACKAGE, "prisma/schema.prisma"),
    path.join(prismaDir, "schema.prisma"),
  );
  copyFileSync(
    path.join(DB_PACKAGE, "prisma.config.ts"),
    path.join(workspace, "prisma.config.ts"),
  );
  copyFileSync(
    path.join(MIGRATIONS, "migration_lock.toml"),
    path.join(migrationDir, "migration_lock.toml"),
  );
  for (const entry of readdirSync(MIGRATIONS, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name >= TARGET) continue;
    cpSync(
      path.join(MIGRATIONS, entry.name),
      path.join(migrationDir, entry.name),
      { recursive: true },
    );
  }
  symlinkSync(
    path.join(ROOT, "node_modules"),
    path.join(workspace, "node_modules"),
  );
  return workspace;
}

function addTargetMigration(workspace: string): void {
  cpSync(TARGET_SOURCE, path.join(workspace, "prisma/migrations", TARGET), {
    recursive: true,
  });
}

function prisma(
  workspace: string,
  databaseUrl: string,
  args: string[],
): CommandResult {
  return run(
    PRISMA,
    [...args, "--config", path.join(workspace, "prisma.config.ts")],
    {
      cwd: workspace,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
      },
    },
  );
}

async function readAbsentShape(client: Client): Promise<AbsentShape> {
  const result = await client.query<AbsentShape>(`
    SELECT
      (SELECT count(*)::int
         FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'practices'
          AND column_name = 'templateTwinRolloutGeneration')
        AS "practiceGenerationColumnCount",
      (SELECT count(*)::int
         FROM pg_class c
         JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = 'template_twin_rollout_controls'
          AND c.relkind = 'r') AS "rolloutControlTableCount",
      (SELECT count(*)::int
         FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'template_twin_fill_manifests'
          AND column_name IN (
            'pinnedGlobalRolloutGeneration',
            'pinnedPracticeRolloutGeneration',
            'signedGlobalRolloutGeneration',
            'signedPracticeRolloutGeneration'
          )) AS "fillGenerationColumnCount",
      (SELECT count(*)::int
         FROM pg_proc p
         JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN (
            'template_twin_guard_global_rollout_generation',
            'template_twin_guard_practice_rollout_generation'
          )) AS "rolloutFunctionCount",
      (SELECT count(*)::int
         FROM pg_trigger
        WHERE NOT tgisinternal
          AND tgname IN (
            'template_twin_global_rollout_generation_guard',
            'template_twin_practice_rollout_generation_guard'
          )) AS "rolloutTriggerCount",
      (SELECT count(*)::int
         FROM pg_constraint
        WHERE conname IN (
          'practices_template_twin_rollout_generation_positive',
          'template_twin_rollout_generation_positive',
          'template_twin_rollout_singleton',
          'template_twin_fill_pinned_rollout_pair',
          'template_twin_fill_signed_rollout_pair',
          'template_twin_fill_signed_rollout_matches_pinned'
        )) AS "rolloutConstraintCount"
  `);
  return result.rows[0]!;
}

function shapeIsAbsent(shape: AbsentShape): boolean {
  return Object.values(shape).every((value) => value === 0);
}

async function readInstalledShape(client: Client): Promise<InstalledShape> {
  const shape = await readAbsentShape(client);
  const global = await client.query<{
    enabled: boolean;
    generation: string;
  }>(`
    SELECT enabled, generation::text AS generation
      FROM template_twin_rollout_controls
     WHERE id = 'global'
  `);
  const practice = await client.query<{
    templateTwinEnabled: boolean;
    templateTwinRolloutGeneration: string;
  }>(`
    SELECT "templateTwinEnabled",
           "templateTwinRolloutGeneration"::text
             AS "templateTwinRolloutGeneration"
      FROM practices
     WHERE id = 'synthetic_rollout_lock_practice'
  `);
  return {
    ...shape,
    globalEnabled: global.rows[0]!.enabled,
    globalGeneration: global.rows[0]!.generation,
    practiceEnabled: practice.rows[0]!.templateTwinEnabled,
    practiceGeneration: practice.rows[0]!.templateTwinRolloutGeneration,
  };
}

function shapeIsComplete(shape: InstalledShape): boolean {
  return (
    shape.practiceGenerationColumnCount === 1 &&
    shape.rolloutControlTableCount === 1 &&
    shape.fillGenerationColumnCount === 4 &&
    shape.rolloutFunctionCount === 2 &&
    shape.rolloutTriggerCount === 2 &&
    shape.rolloutConstraintCount === 6 &&
    shape.globalEnabled === false &&
    shape.globalGeneration === "1" &&
    shape.practiceEnabled === false &&
    shape.practiceGeneration === "1"
  );
}

async function syntheticPracticeIsUnchanged(client: Client): Promise<boolean> {
  const result = await client.query<{
    name: string;
    slug: string;
    enabled: boolean;
  }>(`
    SELECT name, slug, "templateTwinEnabled" AS enabled
      FROM practices
     WHERE id = 'synthetic_rollout_lock_practice'
  `);
  const row = result.rows[0];
  return (
    result.rowCount === 1 &&
    row?.name === "Synthetic rollout migration lock practice" &&
    row.slug === "synthetic-rollout-migration-lock" &&
    row.enabled === false
  );
}

async function runScenario(input: {
  adminUrl: string;
  scenario: ScenarioEvidence["scenario"];
  blockedTable: ScenarioEvidence["blockedTable"];
}): Promise<ScenarioEvidence> {
  progress(`${input.scenario}: create disposable database`);
  const database = `rollout_lock_${input.scenario}`;
  const admin = new Client({ connectionString: input.adminUrl });
  await admin.connect();
  await admin.query(`CREATE DATABASE ${database}`);
  await admin.end();

  const url = new URL(input.adminUrl);
  url.pathname = `/${database}`;
  const databaseUrl = url.toString();
  const workspace = preparePrismaWorkspace(input.scenario);
  const observer = new Client({ connectionString: databaseUrl });
  const locker = new Client({ connectionString: databaseUrl });
  let observerConnected = false;
  let lockerConnected = false;

  try {
    progress(`${input.scenario}: apply 70-migration baseline`);
    const baseline = prisma(workspace, databaseUrl, ["migrate", "deploy"]);
    if (baseline.status !== 0) {
      const diagnostic = `${baseline.stdout}\n${baseline.stderr}`
        .replaceAll(SYNTHETIC_PASSWORD, "[synthetic-password-redacted]")
        .slice(-4_000);
      throw new Error(
        `Baseline migration failed for ${input.scenario} ` +
          `(exit ${baseline.status}): ${diagnostic}`,
      );
    }
    await observer.connect();
    observerConnected = true;
    await locker.connect();
    lockerConnected = true;
    progress(`${input.scenario}: seed synthetic baseline row`);
    await observer.query(`
      INSERT INTO practices (
        id, name, slug, "templateTwinEnabled", "createdAt", "updatedAt"
      ) VALUES (
        'synthetic_rollout_lock_practice',
        'Synthetic rollout migration lock practice',
        'synthetic-rollout-migration-lock',
        false,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
      )
    `);
    if (!shapeIsAbsent(await readAbsentShape(observer))) {
      throw new Error(
        "Target rollout schema existed before the target migration.",
      );
    }

    addTargetMigration(workspace);
    await locker.query("BEGIN");
    await locker.query(
      `LOCK TABLE "${input.blockedTable}" IN ACCESS SHARE MODE`,
    );
    const blocker = await locker.query<{ granted: boolean }>(
      `
      SELECT bool_and(granted) AS granted
        FROM pg_locks
       WHERE pid = pg_backend_pid()
         AND relation = $1::regclass
         AND mode = 'AccessShareLock'
    `,
      [input.blockedTable],
    );
    const blockerLockGrantedBeforeDeploy = blocker.rows[0]?.granted === true;
    if (!blockerLockGrantedBeforeDeploy) {
      throw new Error(
        "Deterministic blocker lock was not granted before deploy.",
      );
    }

    progress(`${input.scenario}: blocker granted; run target migration`);
    const failedDeploy = prisma(workspace, databaseUrl, ["migrate", "deploy"]);
    const diagnostic = `${failedDeploy.stdout}\n${failedDeploy.stderr}`;
    const prismaReportedP3018 = /P3018/.test(diagnostic);
    const prismaReportedAbortedTransaction =
      /current transaction is aborted/i.test(diagnostic);
    const postgresLogs = run("docker", ["logs", CONTAINER]);
    const postgresDiagnostic = `${postgresLogs.stdout}\n${postgresLogs.stderr}`;
    const postgresReportedLockTimeout =
      /55P03|lock timeout|canceling statement due to lock timeout/i.test(
        `${diagnostic}\n${postgresDiagnostic}`,
      );
    if (
      failedDeploy.status === 0 ||
      (!prismaReportedP3018 && !prismaReportedAbortedTransaction) ||
      !postgresReportedLockTimeout ||
      failedDeploy.durationMs < 1_500 ||
      failedDeploy.durationMs > 15_000
    ) {
      const failureDiagnostic = diagnostic
        .replaceAll(SYNTHETIC_PASSWORD, "[synthetic-password-redacted]")
        .slice(-4_000);
      throw new Error(
        `Expected bounded Prisma lock failure was not observed for ${input.scenario} ` +
          `(exit=${failedDeploy.status}, durationMs=${failedDeploy.durationMs.toFixed(3)}, ` +
          `P3018=${prismaReportedP3018}, aborted=${prismaReportedAbortedTransaction}, ` +
          `lockTimeout=${postgresReportedLockTimeout}): ` +
          failureDiagnostic,
      );
    }

    progress(`${input.scenario}: bounded timeout observed; verify rollback`);

    const failedRows = await observer.query<{
      finished: boolean;
      rolledBack: boolean;
    }>(
      `
      SELECT "finished_at" IS NOT NULL AS finished,
             "rolled_back_at" IS NOT NULL AS "rolledBack"
        FROM _prisma_migrations
       WHERE migration_name = $1
       ORDER BY started_at
    `,
      [TARGET],
    );
    const failed = failedRows.rows[0];
    const failedMigrationRowPresent = failedRows.rowCount === 1;
    const failedMigrationUnfinished = failed?.finished === false;
    const failedMigrationNotPretendedSuccessful =
      failed?.finished === false && failed.rolledBack === false;
    const rollbackWasAtomic = shapeIsAbsent(await readAbsentShape(observer));
    const syntheticPracticeUnchangedAfterTimeout =
      await syntheticPracticeIsUnchanged(observer);
    if (
      !failedMigrationRowPresent ||
      !failedMigrationUnfinished ||
      !failedMigrationNotPretendedSuccessful ||
      !rollbackWasAtomic ||
      !syntheticPracticeUnchangedAfterTimeout
    ) {
      throw new Error(
        `Lock timeout left inconsistent migration evidence for ${input.scenario} ` +
          `(row=${failedMigrationRowPresent}, unfinished=${failedMigrationUnfinished}, ` +
          `failed=${failedMigrationNotPretendedSuccessful}, atomic=${rollbackWasAtomic}, ` +
          `data=${syntheticPracticeUnchangedAfterTimeout}, ` +
          `shape=${JSON.stringify(await readAbsentShape(observer))}).`,
      );
    }

    await locker.query("ROLLBACK");
    progress(`${input.scenario}: blocker released; resolve and retry`);
    const resolved = prisma(workspace, databaseUrl, [
      "migrate",
      "resolve",
      "--rolled-back",
      TARGET,
    ]);
    if (resolved.status !== 0) {
      throw new Error(
        `Prisma rollback resolution failed for ${input.scenario}.`,
      );
    }
    const retry = prisma(workspace, databaseUrl, ["migrate", "deploy"]);
    if (retry.status !== 0) {
      throw new Error(`Prisma migration retry failed for ${input.scenario}.`);
    }
    const noPending = prisma(workspace, databaseUrl, ["migrate", "deploy"]);
    if (
      noPending.status !== 0 ||
      !/No pending migrations/i.test(noPending.stdout)
    ) {
      throw new Error(
        `Idempotent no-pending deploy failed for ${input.scenario}.`,
      );
    }

    const installed = await readInstalledShape(observer);
    const retryInstalledCompleteContract = shapeIsComplete(installed);
    const syntheticPracticeUnchangedAfterRetry =
      await syntheticPracticeIsUnchanged(observer);
    const attempts = await observer.query<{
      finished: boolean;
      rolledBack: boolean;
    }>(
      `
      SELECT "finished_at" IS NOT NULL AS finished,
             "rolled_back_at" IS NOT NULL AS "rolledBack"
        FROM _prisma_migrations
       WHERE migration_name = $1
       ORDER BY started_at
    `,
      [TARGET],
    );
    const failedAttemptMarkedRolledBack =
      attempts.rowCount === 2 && attempts.rows[0]?.rolledBack === true;
    const successfulAttemptRecorded =
      attempts.rowCount === 2 &&
      attempts.rows[1]?.finished === true &&
      attempts.rows[1]?.rolledBack === false;
    if (
      !retryInstalledCompleteContract ||
      !syntheticPracticeUnchangedAfterRetry ||
      !failedAttemptMarkedRolledBack ||
      !successfulAttemptRecorded
    ) {
      throw new Error(`Retry proof was incomplete for ${input.scenario}.`);
    }

    progress(`${input.scenario}: retry and no-pending deploy passed`);

    return {
      scenario: input.scenario,
      blockedTable: input.blockedTable,
      blockerLockMode: "ACCESS SHARE",
      blockerLockGrantedBeforeDeploy,
      failedDeployDurationMs: Number(failedDeploy.durationMs.toFixed(3)),
      failedDeployExitCode: failedDeploy.status,
      prismaReportedP3018,
      prismaReportedAbortedTransaction,
      postgresReportedLockTimeout,
      failedMigrationRowPresent,
      failedMigrationUnfinished,
      failedMigrationNotPretendedSuccessful,
      rollbackWasAtomic,
      syntheticPracticeUnchangedAfterTimeout,
      resolveRolledBackExitCode: resolved.status,
      retryDeployExitCode: retry.status,
      noPendingRetryExitCode: noPending.status,
      retryInstalledCompleteContract,
      syntheticPracticeUnchangedAfterRetry,
      failedAttemptMarkedRolledBack,
      successfulAttemptRecorded,
    };
  } finally {
    if (lockerConnected) {
      try {
        await locker.query("ROLLBACK");
      } catch {}
      await locker.end().catch(() => undefined);
    }
    if (observerConnected) await observer.end().catch(() => undefined);
    rmSync(workspace, { recursive: true, force: true });
  }
}

async function main(): Promise<void> {
  const migrationSql = await import("node:fs/promises").then((fs) =>
    fs.readFile(path.join(TARGET_SOURCE, "migration.sql"), "utf8"),
  );
  const begin = migrationSql.indexOf("BEGIN;");
  const lockTimeout = migrationSql.indexOf("SET LOCAL lock_timeout = '2s';");
  const statementTimeout = migrationSql.indexOf(
    "SET LOCAL statement_timeout = '30s';",
  );
  const firstLockingDdl = migrationSql.search(/ALTER TABLE|CREATE TABLE/);
  const commit = migrationSql.lastIndexOf("COMMIT;");
  if (
    begin < 0 ||
    lockTimeout < begin ||
    statementTimeout < lockTimeout ||
    firstLockingDdl < statementTimeout ||
    commit < firstLockingDdl ||
    migrationSql.slice(commit + "COMMIT;".length).trim() !== ""
  ) {
    throw new Error(
      "Rollout migration does not have one complete transaction-local timeout envelope.",
    );
  }

  checked("docker", [
    "run",
    "--detach",
    "--rm",
    "--name",
    CONTAINER,
    "--publish",
    "127.0.0.1::5432",
    "--env",
    `POSTGRES_PASSWORD=${SYNTHETIC_PASSWORD}`,
    "--env",
    "POSTGRES_USER=postgres",
    "--env",
    "POSTGRES_DB=postgres",
    IMAGE,
  ]);

  try {
    progress(`container ${CONTAINER}: wait for disposable PostgreSQL`);
    waitForPostgres();
    const mapped = checked("docker", ["port", CONTAINER, "5432/tcp"]);
    const match = mapped.match(/127\.0\.0\.1:(\d+)/);
    if (!match)
      throw new Error("Could not determine disposable PostgreSQL port.");
    const adminUrl =
      `postgresql://postgres:${SYNTHETIC_PASSWORD}` +
      `@127.0.0.1:${match[1]}/postgres`;
    const bootstrap = new Client({ connectionString: adminUrl });
    await bootstrap.connect();
    await bootstrap.query("CREATE ROLE meddoc NOLOGIN");
    await bootstrap.end();
    progress("disposable cluster bootstrap complete");
    const scenarios = [
      await runScenario({
        adminUrl,
        scenario: "early_practice_lock",
        blockedTable: "practices",
      }),
      await runScenario({
        adminUrl,
        scenario: "late_fill_manifest_lock",
        blockedTable: "template_twin_fill_manifests",
      }),
    ];
    const evidence = {
      profile: "template-twin-rollout-generation-migration-lock-v1",
      auditedMigration: TARGET,
      synthetic: true,
      disposablePostgresImage: IMAGE,
      prismaRunner: "real prisma migrate deploy/resolve",
      lockTimeout: "2s transaction-local",
      statementTimeout: "30s transaction-local",
      timeoutEnvelopeCoversCompleteMigration: true,
      scenarios,
      productionDatabaseUsed: false,
    };
    writeFileSync(EVIDENCE_PATH, `${JSON.stringify(evidence, null, 2)}\n`, {
      mode: 0o600,
    });
    process.stdout.write(`${JSON.stringify(evidence)}\n`);
  } finally {
    run("docker", ["rm", "--force", CONTAINER]);
  }
}

void main().catch((error: unknown) => {
  process.stderr.write(
    `${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
  );
  process.exitCode = 1;
});
