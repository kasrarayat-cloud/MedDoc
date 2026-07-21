#!/usr/bin/env tsx

// Disposable, synthetic main-schema -> online lineage upgrade harness.
// It starts its own PostgreSQL container, never accepts production data, and
// records only sanitized counts/timing/lock evidence. Default scale is 1M rows.

import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import { Pool } from "pg";

import {
  backfillLineageBatch,
  contractLineageNotNull,
  readLineageMigrationProgress,
  readLineageMigrationStatus,
  type TransactionalRawSqlClient,
} from "../src/template-twin-lineage-online";
import { acquireLineageOperatorSessionLock } from "../src/template-twin-lineage-session-lock";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "../../..");
const BASE_SHA =
  process.env.TEMPLATE_TWIN_SCALE_BASE_SHA ??
  "1be101912f01293de3b8fddae722c823ecc86f29";
const ROW_COUNT = Number(process.env.TEMPLATE_TWIN_SCALE_ROWS ?? "1000000");
const EVIDENCE_PATH =
  process.env.TEMPLATE_TWIN_SCALE_EVIDENCE_PATH ??
  "/tmp/template-twin-lineage-scale-evidence.json";
const IMAGE =
  process.env.TEMPLATE_TWIN_SCALE_POSTGRES_IMAGE ??
  "pgvector/pgvector:pg16@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff";
const KEEP_FAILED_INFRA =
  process.env.TEMPLATE_TWIN_SCALE_KEEP_FAILED_INFRA === "true";
const CONTAINER = `meddoc-lineage-scale-${process.pid}`;
const DATABASE = "meddoc_lineage_scale_test";
const SYNTHETIC_PASSWORD = "synthetic-lineage-scale-only";

interface CommandResult {
  code: number;
  stdout: string;
  stderr: string;
  durationMs: number;
}

interface WorkloadMetrics {
  reads: number;
  inserts: number;
  updates: number;
  readFailures: number;
  insertFailures: number;
  updateFailures: number;
  readsOver250Ms: number;
  writesOver250Ms: number;
  maxReadMs: number;
  maxInsertMs: number;
  maxUpdateMs: number;
  maxObservedDatabaseLockWaitMs: number;
  failureCodes: Record<string, number>;
}

function summarizeDiff(sql: string) {
  return {
    sha256: createHash("sha256").update(sql).digest("hex"),
    bytes: Buffer.byteLength(sql),
    lines: sql === "" ? 0 : sql.split("\n").length,
    requiresLineageSetNotNull:
      /ALTER TABLE\s+"note_templates"[\s\S]*?ALTER COLUMN\s+"lineageId"\s+SET NOT NULL/i.test(
        sql,
      ),
    requiresLineageUniqueIndex: sql.includes(
      "note_templates_lineageId_version_key",
    ),
  };
}

function summarizeBatchDurations(stdout: string) {
  const durations = stdout
    .split("\n")
    .filter(Boolean)
    .flatMap((line) => {
      try {
        const value = JSON.parse(line) as {
          event?: string;
          durationMs?: number;
        };
        return value.event === "batch" && typeof value.durationMs === "number"
          ? [value.durationMs]
          : [];
      } catch {
        return [];
      }
    })
    .sort((left, right) => left - right);
  const percentile = (fraction: number) =>
    durations.length === 0
      ? null
      : durations[
          Math.min(
            durations.length - 1,
            Math.ceil(durations.length * fraction) - 1,
          )
        ]!;
  return {
    samples: durations.length,
    p50Ms: percentile(0.5),
    p95Ms: percentile(0.95),
    maxMs: durations.at(-1) ?? null,
  };
}

async function prismaDiff(
  configPath: string,
  databaseUrl: string,
  sourceArgs: string[],
) {
  const result = await checked(
    "npx",
    [
      "--no-install",
      "prisma",
      "migrate",
      "diff",
      "--config",
      configPath,
      ...sourceArgs,
      "--to-schema",
      path.join(ROOT, "packages/db/prisma/schema.prisma"),
      "--script",
    ],
    { cwd: ROOT, env: { ...process.env, DATABASE_URL: databaseUrl } },
  );
  return { durationMs: result.durationMs, ...summarizeDiff(result.stdout) };
}

function requireSafeScale(): void {
  if (
    !Number.isInteger(ROW_COUNT) ||
    ROW_COUNT < 10_000 ||
    ROW_COUNT > 5_000_000
  ) {
    throw new Error(
      "TEMPLATE_TWIN_SCALE_ROWS must be an integer from 10,000 to 5,000,000",
    );
  }
  if (!path.isAbsolute(EVIDENCE_PATH) || !EVIDENCE_PATH.startsWith("/tmp/")) {
    throw new Error("Scale evidence must be written beneath /tmp");
  }
}

function runCommand(
  command: string,
  args: string[],
  options: { cwd?: string; env?: NodeJS.ProcessEnv; input?: string } = {},
): Promise<CommandResult> {
  const started = performance.now();
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd ?? ROOT,
      env: options.env ?? process.env,
      stdio: [options.input === undefined ? "ignore" : "pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.once("error", reject);
    child.once("close", (code) => {
      resolve({
        code: code ?? 1,
        stdout,
        stderr,
        durationMs: Math.round((performance.now() - started) * 100) / 100,
      });
    });
    if (options.input !== undefined) child.stdin.end(options.input);
  });
}

async function checked(
  command: string,
  args: string[],
  options: { cwd?: string; env?: NodeJS.ProcessEnv; input?: string } = {},
): Promise<CommandResult> {
  const result = await runCommand(command, args, options);
  if (result.code !== 0) {
    // No connection string is included in command arguments. Limit captured
    // diagnostics so a synthetic load failure cannot create an unbounded log.
    const diagnostic = result.stderr
      .slice(-2_000)
      .replaceAll(SYNTHETIC_PASSWORD, "[redacted]");
    throw new Error(`${command} failed (${result.code}): ${diagnostic}`);
  }
  return result;
}

function makeClient(
  databaseUrl: string,
  applicationName: string,
): TransactionalRawSqlClient & {
  $disconnect(): Promise<void>;
} {
  const url = new URL(databaseUrl);
  url.searchParams.set(
    "options",
    `-c lock_timeout=2s -c statement_timeout=15min -c application_name=${applicationName}`,
  );
  const adapter = new PrismaPg({
    connectionString: url.toString(),
    max: 4,
    connectionTimeoutMillis: 10_000,
  });
  return new PrismaClient({
    adapter,
  }) as unknown as TransactionalRawSqlClient & {
    $disconnect(): Promise<void>;
  };
}

function safeCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = String((error as { code?: unknown }).code ?? "UNKNOWN");
    if (/^[A-Z0-9_]{2,32}$/.test(code)) return code;
  }
  const message = error instanceof Error ? error.message : "";
  const stable = message.match(/LINEAGE_MIGRATION_[A-Z0-9_]+/)?.[0];
  return stable ?? "OTHER_SYNTHETIC_WORKLOAD_FAILURE";
}

async function waitForPostgres(): Promise<void> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const result = await runCommand("docker", [
      "exec",
      CONTAINER,
      "psql",
      "-X",
      "-A",
      "-t",
      "-q",
      "-U",
      "meddoc",
      "-d",
      DATABASE,
      "-c",
      "SELECT 1",
    ]);
    if (result.code === 0 && result.stdout.trim() === "1") return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("Disposable PostgreSQL did not become ready");
}

async function dockerPsql(sql: string): Promise<CommandResult> {
  return checked(
    "docker",
    [
      "exec",
      "-i",
      CONTAINER,
      "psql",
      "-X",
      "-v",
      "ON_ERROR_STOP=1",
      "-U",
      "meddoc",
      "-d",
      DATABASE,
    ],
    { input: sql },
  );
}

async function startWorkload(
  databaseUrl: string,
  expanded: { value: boolean },
): Promise<{ stop: () => Promise<void>; metrics: WorkloadMetrics }> {
  const client = makeClient(databaseUrl, "lineage_scale_workload");
  const sampler = makeClient(databaseUrl, "lineage_scale_lock_sampler");
  let running = true;
  let sequence = 0;
  const metrics: WorkloadMetrics = {
    reads: 0,
    inserts: 0,
    updates: 0,
    readFailures: 0,
    insertFailures: 0,
    updateFailures: 0,
    readsOver250Ms: 0,
    writesOver250Ms: 0,
    maxReadMs: 0,
    maxInsertMs: 0,
    maxUpdateMs: 0,
    maxObservedDatabaseLockWaitMs: 0,
    failureCodes: {},
  };

  const recordFailure = (error: unknown) => {
    const code = safeCode(error);
    metrics.failureCodes[code] = (metrics.failureCodes[code] ?? 0) + 1;
  };
  const timed = async (
    kind: "read" | "insert" | "update",
    operation: () => Promise<unknown>,
  ) => {
    const started = performance.now();
    try {
      await operation();
      metrics[`${kind}s` as "reads" | "inserts" | "updates"] += 1;
    } catch (error) {
      metrics[
        `${kind}Failures` as
          | "readFailures"
          | "insertFailures"
          | "updateFailures"
      ] += 1;
      recordFailure(error);
    } finally {
      const duration = performance.now() - started;
      const maxKey = `max${kind[0]!.toUpperCase()}${kind.slice(1)}Ms` as
        | "maxReadMs"
        | "maxInsertMs"
        | "maxUpdateMs";
      metrics[maxKey] = Math.max(metrics[maxKey], duration);
      if (duration > 250) {
        if (kind === "read") metrics.readsOver250Ms += 1;
        else metrics.writesOver250Ms += 1;
      }
    }
  };

  const workload = (async () => {
    while (running) {
      sequence += 1;
      const id = `live_${String(sequence).padStart(12, "0")}`;
      const updateId = `scale_${String((sequence % ROW_COUNT) + 1).padStart(12, "0")}`;
      await Promise.all([
        timed("read", () =>
          client.$queryRawUnsafe(
            `SELECT "id", "name", "status" FROM "note_templates"
             WHERE "id" >= $1 ORDER BY "id" LIMIT 25`,
            updateId,
          ),
        ),
        timed("update", () =>
          client.$executeRawUnsafe(
            `UPDATE "note_templates" SET "updatedAt" = CURRENT_TIMESTAMP
             WHERE "id" = $1`,
            updateId,
          ),
        ),
        timed("insert", () =>
          expanded.value
            ? client.$executeRawUnsafe(
                `INSERT INTO "note_templates" (
                   "id", "doctorId", "name", "sections", "version", "status",
                   "isSystemDefault", "lineageId", "createdAt", "updatedAt"
                 ) VALUES ($1, NULL, 'Synthetic live template', '[]'::jsonb, 1,
                           'draft', false, $1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)`,
                id,
              )
            : client.$executeRawUnsafe(
                `INSERT INTO "note_templates" (
                   "id", "doctorId", "name", "sections", "version", "status",
                   "isSystemDefault", "createdAt", "updatedAt"
                 ) VALUES ($1, NULL, 'Synthetic live template', '[]'::jsonb, 1,
                           'draft', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)`,
                id,
              ),
        ),
      ]);
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
  })();

  const lockSampling = (async () => {
    while (running) {
      try {
        const rows = await sampler.$queryRawUnsafe<
          Array<{ waitMs: number | string }>
        >(
          `SELECT COALESCE(MAX(
             EXTRACT(EPOCH FROM (clock_timestamp() - query_start)) * 1000
           ), 0)::float8 AS "waitMs"
           FROM pg_stat_activity
           WHERE wait_event_type = 'Lock'
             AND application_name IN (
               'lineage_scale_workload',
               'quillmd_template_twin_lineage_online_v1'
             )`,
        );
        metrics.maxObservedDatabaseLockWaitMs = Math.max(
          metrics.maxObservedDatabaseLockWaitMs,
          Number(rows[0]?.waitMs ?? 0),
        );
      } catch (error) {
        recordFailure(error);
      }
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  })();

  return {
    metrics,
    stop: async () => {
      running = false;
      await Promise.all([workload, lockSampling]);
      await Promise.all([client.$disconnect(), sampler.$disconnect()]);
      for (const key of [
        "maxReadMs",
        "maxInsertMs",
        "maxUpdateMs",
        "maxObservedDatabaseLockWaitMs",
      ] as const) {
        metrics[key] = Math.round(metrics[key] * 100) / 100;
      }
    },
  };
}

function operatorEnv(databaseUrl: string): NodeJS.ProcessEnv {
  return {
    ...process.env,
    DATABASE_URL: databaseUrl,
    NODE_ENV: "test",
  };
}

async function runOperator(
  databaseUrl: string,
  phase: string,
  extraArgs: string[] = [],
  extraEnv: NodeJS.ProcessEnv = {},
): Promise<CommandResult> {
  const approvedFingerprint = await operatorFingerprint(databaseUrl, phase);
  return checked(
    "npx",
    [
      "--no-install",
      "tsx",
      "scripts/template-twin-lineage-online.ts",
      "--phase",
      phase,
      ...extraArgs,
    ],
    {
      cwd: path.join(ROOT, "packages/db"),
      env: {
        ...operatorEnv(databaseUrl),
        ...extraEnv,
        TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT: approvedFingerprint,
      },
    },
  );
}

async function operatorFingerprint(
  databaseUrl: string,
  phase: string,
): Promise<string> {
  const status = await checked(
    "npx",
    [
      "--no-install",
      "tsx",
      "scripts/template-twin-lineage-online.ts",
      "--phase",
      "status",
    ],
    {
      cwd: path.join(ROOT, "packages/db"),
      env: operatorEnv(databaseUrl),
    },
  );
  const line = status.stdout
    .split("\n")
    .map((value) => value.trim())
    .find(Boolean);
  let fingerprint: unknown;
  try {
    const parsed = JSON.parse(line ?? "") as {
      targetFingerprints?: Record<string, unknown>;
    };
    fingerprint = parsed.targetFingerprints?.[phase];
  } catch {
    throw new Error("Lineage status did not return a fingerprint challenge");
  }
  if (typeof fingerprint !== "string" || !/^[a-f0-9]{64}$/u.test(fingerprint)) {
    throw new Error("Lineage status returned an invalid fingerprint challenge");
  }
  return fingerprint;
}

async function interruptBackfill(databaseUrl: string) {
  const approvedFingerprint = await operatorFingerprint(
    databaseUrl,
    "backfill",
  );
  const barrierClient = makeClient(
    databaseUrl,
    "lineage_scale_interrupt_barrier",
  );
  const child = spawn(
    path.join(ROOT, "node_modules/.bin/tsx"),
    [
      "scripts/template-twin-lineage-online.ts",
      "--phase",
      "backfill",
      "--batch-size",
      "100",
      "--batch-delay-ms",
      "100",
    ],
    {
      cwd: path.join(ROOT, "packages/db"),
      env: {
        ...operatorEnv(databaseUrl),
        TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT: approvedFingerprint,
      },
      stdio: ["ignore", "ignore", "pipe"],
      // tsx may use a child process. A dedicated process group lets the
      // harness simulate a real operator crash instead of killing only its
      // launcher and allowing an orphan to finish the backfill.
      detached: true,
    },
  );
  let stderr = "";
  child.stderr.on("data", (chunk) => {
    stderr += String(chunk);
  });
  const closed = new Promise<number | null>((resolve) =>
    child.once("close", resolve),
  );
  const killOperatorGroup = () => {
    if (child.pid === undefined) return;
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      child.kill("SIGKILL");
    }
  };

  const deadline = Date.now() + 60_000;
  let beforeKill = await readLineageMigrationProgress(barrierClient);
  while (Date.now() < deadline) {
    beforeKill = await readLineageMigrationProgress(barrierClient);
    if (beforeKill.batchCount >= 5 && beforeKill.phase === "BACKFILLING") break;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  if (beforeKill.batchCount < 5 || beforeKill.phase !== "BACKFILLING") {
    killOperatorGroup();
    await barrierClient.$disconnect();
    throw new Error(
      `Backfill did not reach interruption barrier: ${stderr.slice(-500)}`,
    );
  }
  killOperatorGroup();
  const exit = await closed;
  const afterKill = await readLineageMigrationProgress(barrierClient);
  await barrierClient.$disconnect();
  if (afterKill.phase !== "BACKFILLING" || afterKill.rowsProcessed < 1) {
    throw new Error(
      "Killed backfill did not retain a resumable committed cursor",
    );
  }
  return { exit, beforeKill, afterKill };
}

async function main(): Promise<void> {
  requireSafeScale();
  mkdirSync(path.dirname(EVIDENCE_PATH), { recursive: true });
  const temporary = mkdtempSync(
    path.join(tmpdir(), "template-twin-lineage-scale-"),
  );
  const evidence: Record<string, unknown> = {
    generatedAt: new Date().toISOString(),
    syntheticOnly: true,
    baseSha: BASE_SHA,
    requestedRows: ROW_COUNT,
    scaleClassification:
      ROW_COUNT >= 1_000_000
        ? "million_row_synthetic"
        : "sub_million_synthetic",
    postgresImage: IMAGE,
  };
  let workload: Awaited<ReturnType<typeof startWorkload>> | null = null;
  let client: ReturnType<typeof makeClient> | null = null;
  let succeeded = false;

  try {
    await checked("git", ["cat-file", "-e", `${BASE_SHA}^{commit}`], {
      cwd: ROOT,
    });
    await checked("docker", [
      "run",
      "--rm",
      "-d",
      "--name",
      CONTAINER,
      "-e",
      "POSTGRES_USER=meddoc",
      "-e",
      `POSTGRES_PASSWORD=${SYNTHETIC_PASSWORD}`,
      "-e",
      `POSTGRES_DB=${DATABASE}`,
      "-P",
      IMAGE,
    ]);
    await waitForPostgres();
    const portResult = await checked("docker", ["port", CONTAINER, "5432/tcp"]);
    const port = portResult.stdout.trim().match(/:(\d+)$/)?.[1];
    if (!port) throw new Error("Could not resolve disposable PostgreSQL port");
    const databaseUrl = `postgresql://meddoc:${SYNTHETIC_PASSWORD}@127.0.0.1:${port}/${DATABASE}?schema=public`;
    const shadowDatabase = "meddoc_lineage_shadow_test";
    await checked("docker", [
      "exec",
      CONTAINER,
      "psql",
      "-X",
      "-v",
      "ON_ERROR_STOP=1",
      "-U",
      "meddoc",
      "-d",
      "postgres",
      "-c",
      `CREATE DATABASE ${shadowDatabase}`,
    ]);
    const shadowUrl = `postgresql://meddoc:${SYNTHETIC_PASSWORD}@127.0.0.1:${port}/${shadowDatabase}?schema=public`;

    const archive = path.join(temporary, "base-prisma.tar");
    await checked(
      "git",
      [
        "archive",
        "--format=tar",
        "-o",
        archive,
        BASE_SHA,
        "packages/db/prisma",
      ],
      { cwd: ROOT },
    );
    await checked("tar", ["-xf", archive, "-C", temporary]);
    const tempPrisma = path.join(temporary, "packages/db/prisma");
    cpSync(
      path.join(
        ROOT,
        "packages/db/prisma/migrations/20260715162000_template_twin_docx_v1",
      ),
      path.join(tempPrisma, "migrations/20260715162000_template_twin_docx_v1"),
      { recursive: true },
    );
    const configPath = path.join(temporary, "prisma.config.js");
    const prismaConfigModule = path.join(ROOT, "node_modules/prisma/config.js");
    writeFileSync(
      configPath,
      `const { defineConfig } = require(${JSON.stringify(prismaConfigModule)});\n` +
        `module.exports = defineConfig({\n` +
        `  schema: ${JSON.stringify(path.join(tempPrisma, "schema.prisma"))},\n` +
        `  migrations: { path: ${JSON.stringify(path.join(tempPrisma, "migrations"))} },\n` +
        `  datasource: { url: process.env.DATABASE_URL, shadowDatabaseUrl: ${JSON.stringify(shadowUrl)} },\n` +
        `});\n`,
      { mode: 0o600 },
    );

    const migrationEnv = { ...process.env, DATABASE_URL: databaseUrl };
    // Apply main only, seed the populated table, then introduce only the expand
    // migration to make the before/after lock evidence attributable.
    const expandDir = path.join(
      tempPrisma,
      "migrations/20260715162000_template_twin_docx_v1",
    );
    const heldExpandDir = path.join(temporary, "held-expand-migration");
    cpSync(expandDir, heldExpandDir, { recursive: true });
    rmSync(expandDir, { recursive: true, force: true });
    const mainMigrate = await checked(
      "npx",
      ["--no-install", "prisma", "migrate", "deploy", "--config", configPath],
      { cwd: ROOT, env: migrationEnv },
    );
    evidence.mainMigrationDurationMs = mainMigrate.durationMs;

    const seed = await dockerPsql(
      `\\set ON_ERROR_STOP on\n` +
        `INSERT INTO "note_templates" (\n` +
        `  "id", "doctorId", "name", "encounterType", "specialtyBaseline",\n` +
        `  "sections", "styleProfile", "version", "status", "isSystemDefault",\n` +
        `  "createdAt", "updatedAt"\n` +
        `)\n` +
        `SELECT 'scale_' || lpad(g::text, 12, '0'), NULL,\n` +
        `       'Synthetic generic template ' || g, NULL, NULL, '[]'::jsonb, NULL,\n` +
        `       1, 'draft', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP\n` +
        `FROM generate_series(1, ${ROW_COUNT}) AS g;\n`,
    );
    evidence.seedDurationMs = seed.durationMs;

    const expanded = { value: false };
    workload = await startWorkload(databaseUrl, expanded);
    cpSync(heldExpandDir, expandDir, { recursive: true });
    const expand = await checked(
      "npx",
      ["--no-install", "prisma", "migrate", "deploy", "--config", configPath],
      { cwd: ROOT, env: migrationEnv },
    );
    expanded.value = true;
    evidence.expandMigrationDurationMs = expand.durationMs;

    client = makeClient(databaseUrl, "lineage_scale_controller");
    const afterExpand = await readLineageMigrationStatus(client);
    evidence.afterExpand = afterExpand;
    if (afterExpand.nullRows < ROW_COUNT || afterExpand.phase !== "EXPANDED") {
      throw new Error(
        "Expand unexpectedly backfilled or advanced existing rows",
      );
    }

    const lockPoolA = new Pool({ connectionString: databaseUrl, max: 1 });
    const lockPoolB = new Pool({ connectionString: databaseUrl, max: 1 });
    const firstOperatorLock =
      await acquireLineageOperatorSessionLock(lockPoolA);
    let opposingOperatorCode = "NO_FAILURE";
    try {
      await acquireLineageOperatorSessionLock(lockPoolB);
    } catch (error) {
      opposingOperatorCode = safeCode(error);
    }
    await firstOperatorLock.release();
    const secondOperatorLock =
      await acquireLineageOperatorSessionLock(lockPoolB);
    await secondOperatorLock.release();
    await Promise.all([lockPoolA.end(), lockPoolB.end()]);
    evidence.opposingOperatorSerialization = {
      whileFirstHeld: opposingOperatorCode,
      secondAcquiredAfterRelease: true,
    };
    if (opposingOperatorCode !== "LINEAGE_MIGRATION_OPERATOR_BUSY") {
      throw new Error("Opposing lineage operators were not session-serialized");
    }
    evidence.prismaDiffFromMigrationHistory = await prismaDiff(
      configPath,
      databaseUrl,
      ["--from-migrations", path.join(tempPrisma, "migrations")],
    );
    evidence.prismaDiffBeforeOperatorContract = await prismaDiff(
      configPath,
      databaseUrl,
      ["--from-config-datasource"],
    );

    const guard = await runOperator(databaseUrl, "guard-index");
    evidence.guardIndexDurationMs = guard.durationMs;

    let prematureContractCode = "NO_FAILURE";
    try {
      await contractLineageNotNull(client);
    } catch (error) {
      prematureContractCode = safeCode(error);
    }
    evidence.prematureContractCode = prematureContractCode;
    if (
      prematureContractCode !== "LINEAGE_MIGRATION_CONTRACT_REQUIRES_VALIDATION"
    ) {
      throw new Error("Premature contract did not fail closed");
    }

    const interrupted = await interruptBackfill(databaseUrl);
    evidence.interruptedBackfill = {
      exit: interrupted.exit,
      beforeKillRows: interrupted.beforeKill.rowsProcessed,
      afterKillRows: interrupted.afterKill.rowsProcessed,
      durableCursor: interrupted.afterKill.lastProcessedId,
      phase: interrupted.afterKill.phase,
    };

    const resume = await runOperator(databaseUrl, "backfill", [
      "--batch-size",
      "10000",
      "--batch-delay-ms",
      "0",
    ]);
    evidence.resumeDurationMs = resume.durationMs;
    evidence.batchDurations = summarizeBatchDurations(resume.stdout);
    const afterResume = await readLineageMigrationStatus(client);
    evidence.afterResume = afterResume;
    if (afterResume.phase !== "BACKFILLED" || afterResume.nullRows !== 0) {
      throw new Error("Resumed backfill did not complete");
    }

    const idempotent = await backfillLineageBatch(client, 10_000);
    evidence.idempotentBackfill = idempotent;
    if (!idempotent.complete || idempotent.batchRows !== 0) {
      throw new Error("Completed backfill was not idempotent");
    }

    const indexes = await runOperator(databaseUrl, "indexes");
    evidence.finalIndexDurationMs = indexes.durationMs;
    const validate = await runOperator(databaseUrl, "validate");
    evidence.validationDurationMs = validate.durationMs;
    const blockedContractFingerprint = await operatorFingerprint(
      databaseUrl,
      "contract",
    );

    // Deterministic lock-contention proof: an open read transaction holds
    // ACCESS SHARE while the contract needs ACCESS EXCLUSIVE. The contract's
    // two-second lock timeout must fail without advancing VALIDATED.
    const blocker = makeClient(databaseUrl, "lineage_scale_contract_blocker");
    let releaseBlock!: () => void;
    let signalLocked!: () => void;
    const releasePromise = new Promise<void>((resolve) => {
      releaseBlock = resolve;
    });
    const lockedPromise = new Promise<void>((resolve) => {
      signalLocked = resolve;
    });
    const heldRead = blocker.$transaction(
      async (tx) => {
        await tx.$queryRawUnsafe(
          `SELECT "id" FROM "note_templates" ORDER BY "id" LIMIT 1`,
        );
        signalLocked();
        await releasePromise;
      },
      { timeout: 30_000, maxWait: 5_000 },
    );
    await lockedPromise;
    const blockedContractStarted = performance.now();
    const blockedContract = await runCommand(
      "npx",
      [
        "--no-install",
        "tsx",
        "scripts/template-twin-lineage-online.ts",
        "--phase",
        "contract",
      ],
      {
        cwd: path.join(ROOT, "packages/db"),
        env: {
          ...operatorEnv(databaseUrl),
          TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT:
            blockedContractFingerprint,
          TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK: `note_templates_lineage_v1:${DATABASE}`,
        },
      },
    );
    const blockedContractDurationMs =
      Math.round((performance.now() - blockedContractStarted) * 100) / 100;
    const afterBlockedContract = await readLineageMigrationStatus(client);
    releaseBlock();
    await heldRead;
    await blocker.$disconnect();
    evidence.contractLockContention = {
      exitCode: blockedContract.code,
      durationMs: blockedContractDurationMs,
      stableErrorCode: blockedContract.stderr.trim().split("\n").at(-1) ?? null,
      phaseAfterFailure: afterBlockedContract.phase,
      columnNotNullAfterFailure: afterBlockedContract.columnNotNull,
    };
    if (
      blockedContract.code === 0 ||
      !blockedContract.stderr.includes("LOCK_TIMEOUT") ||
      afterBlockedContract.phase !== "VALIDATED" ||
      afterBlockedContract.columnNotNull
    ) {
      throw new Error("Contended contract did not fail closed at VALIDATED");
    }

    const contract = await runOperator(databaseUrl, "contract", [], {
      TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK: `note_templates_lineage_v1:${DATABASE}`,
    });
    evidence.contractDurationMs = contract.durationMs;

    await workload.stop();
    evidence.concurrentWorkload = workload.metrics;
    workload = null;

    const finalStatus = await readLineageMigrationStatus(client);
    evidence.finalStatus = finalStatus;
    evidence.prismaDiffAfterOperatorContract = await prismaDiff(
      configPath,
      databaseUrl,
      ["--from-config-datasource"],
    );
    const genericRows = await client.$queryRawUnsafe<
      Array<{ total: bigint; liveRows: bigint; readableRows: bigint }>
    >(
      `SELECT COUNT(*)::bigint AS "total",
              COUNT(*) FILTER (WHERE "id" LIKE 'live_%')::bigint AS "liveRows",
              COUNT(*) FILTER (WHERE "sections" = '[]'::jsonb)::bigint AS "readableRows"
       FROM "note_templates"`,
    );
    const totals = genericRows[0]!;
    evidence.genericTemplateProof = {
      total: Number(totals.total),
      liveRows: Number(totals.liveRows),
      readableRows: Number(totals.readableRows),
    };
    if (
      finalStatus.phase !== "CONTRACTED" ||
      !finalStatus.columnNotNull ||
      finalStatus.nullRows !== 0 ||
      finalStatus.duplicateLineageVersions !== 0 ||
      finalStatus.transitionTriggerPresent
    ) {
      throw new Error("Final lineage contract proof failed");
    }

    let contractedProgressMutationRejected = false;
    try {
      await client.$executeRawUnsafe(
        `UPDATE "template_twin_lineage_migration_progress"
         SET "phase" = 'VALIDATED', "updatedAt" = CURRENT_TIMESTAMP
         WHERE "operationKey" = $1`,
        "note_templates_lineage_v1",
      );
    } catch {
      contractedProgressMutationRejected = true;
    }
    evidence.contractedProgressMutationRejected =
      contractedProgressMutationRejected;
    if (!contractedProgressMutationRejected) {
      throw new Error(
        "Contracted progress record accepted a terminal-state mutation",
      );
    }

    let omittedLineageRejected = false;
    try {
      await client.$executeRawUnsafe(
        `INSERT INTO "note_templates" (
           "id", "doctorId", "name", "sections", "version", "status",
           "isSystemDefault", "createdAt", "updatedAt"
         ) VALUES ('post_contract_omitted', NULL, 'Synthetic omitted lineage',
                   '[]'::jsonb, 1, 'draft', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)`,
      );
    } catch {
      omittedLineageRejected = true;
    }
    evidence.omittedLineageRejectedAfterContract = omittedLineageRejected;
    if (!omittedLineageRejected)
      throw new Error("NOT NULL contract accepted an omitted lineage");

    await client.$executeRawUnsafe(
      `INSERT INTO "note_templates" (
         "id", "doctorId", "name", "sections", "version", "status",
         "isSystemDefault", "lineageId", "createdAt", "updatedAt"
       ) VALUES ('post_contract_explicit', NULL, 'Synthetic explicit lineage',
                 '[]'::jsonb, 1, 'draft', false, 'post_contract_explicit',
                 CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)`,
    );
    evidence.explicitLineageAcceptedAfterContract = true;

    const head = await checked("git", ["rev-parse", "HEAD"], { cwd: ROOT });
    evidence.branchHead = head.stdout.trim();
    evidence.completedAt = new Date().toISOString();
    writeFileSync(EVIDENCE_PATH, `${JSON.stringify(evidence, null, 2)}\n`, {
      mode: 0o600,
    });
    succeeded = true;
    process.stdout.write(`${EVIDENCE_PATH}\n`);
  } finally {
    if (workload) await workload.stop().catch(() => undefined);
    if (client) await client.$disconnect().catch(() => undefined);
    if (succeeded || !KEEP_FAILED_INFRA) {
      await runCommand("docker", ["rm", "-f", CONTAINER]).catch(
        () => undefined,
      );
      if (existsSync(temporary))
        rmSync(temporary, { recursive: true, force: true });
    } else {
      process.stderr.write(
        `Preserved synthetic debug container ${CONTAINER}\n`,
      );
      process.stderr.write(`Preserved synthetic debug files ${temporary}\n`);
    }
  }
}

void main().catch((error) => {
  const message =
    error instanceof Error ? error.message : "Unknown scale-test failure";
  process.stderr.write(
    `${message.replaceAll(SYNTHETIC_PASSWORD, "[redacted]")}\n`,
  );
  process.exitCode = 1;
});
