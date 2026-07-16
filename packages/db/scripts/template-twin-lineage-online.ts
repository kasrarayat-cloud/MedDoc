#!/usr/bin/env tsx

// Online operator for the NoteTemplate lineage transition. This script never
// prints DATABASE_URL or credentials. Mutating phases fail closed unless the
// target is positively QA/test/CI, or an explicit production change-control
// acknowledgement names the target database.

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import { performance } from "node:perf_hooks";
import { Pool } from "pg";

import { assertNonProdDatabase, describeDbTarget } from "../src/db-guard";
import { acquireLineageOperatorSessionLock } from "../src/template-twin-lineage-session-lock";
import {
  backfillLineageBatch,
  buildLineageGuardIndex,
  buildLineageIndexes,
  contractLineageNotNull,
  LINEAGE_OPERATION_KEY,
  readLineageMigrationStatus,
  recordLineageMigrationFailure,
  validateLineageContract,
  type TransactionalRawSqlClient,
} from "../src/template-twin-lineage-online";

type Phase =
  | "status"
  | "guard-index"
  | "backfill"
  | "indexes"
  | "validate"
  | "contract";

interface Options {
  phase: Phase;
  batchSize: number;
  batchDelayMs: number;
  maxBatches: number | null;
}

function parseInteger(value: string, flag: string, minimum: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum) {
    throw new Error(`Invalid ${flag}; expected an integer >= ${minimum}`);
  }
  return parsed;
}

export function parseLineageOperatorArgs(args: string[]): Options {
  let phase: Phase | null = null;
  let batchSize = 1_000;
  let batchDelayMs = 100;
  let maxBatches: number | null = null;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index]!;
    if (arg === "--phase") {
      const value = args[++index] as Phase | undefined;
      if (
        !value ||
        ![
          "status",
          "guard-index",
          "backfill",
          "indexes",
          "validate",
          "contract",
        ].includes(value)
      ) {
        throw new Error(
          "--phase must be status, guard-index, backfill, indexes, validate, or contract",
        );
      }
      phase = value;
    } else if (arg === "--batch-size") {
      batchSize = parseInteger(args[++index] ?? "", arg, 1);
    } else if (arg === "--batch-delay-ms") {
      batchDelayMs = parseInteger(args[++index] ?? "", arg, 0);
    } else if (arg === "--max-batches") {
      maxBatches = parseInteger(args[++index] ?? "", arg, 1);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!phase) throw new Error("--phase is required");
  return { phase, batchSize, batchDelayMs, maxBatches };
}

function withOperatorTimeouts(databaseUrl: string, phase: Phase): string {
  const url = new URL(databaseUrl);
  const existing = url.searchParams.get("options")?.trim() ?? "";
  const statementTimeout =
    phase === "guard-index" || phase === "indexes" ? "15min" : "30s";
  const options = [
    existing,
    "-c lock_timeout=2s",
    `-c statement_timeout=${statementTimeout}`,
    "-c application_name=template_twin_lineage_online_v1",
  ]
    .filter(Boolean)
    .join(" ");
  url.searchParams.set("options", options);
  return url.toString();
}

function assertMutationAuthorized(databaseUrl: string, phase: Phase): void {
  if (phase === "status") return;
  try {
    assertNonProdDatabase(databaseUrl);
  } catch (qaError) {
    const target = describeDbTarget(databaseUrl);
    const productionAllowed =
      process.env.TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION === "true";
    const changeId = process.env.TEMPLATE_TWIN_LINEAGE_PRODUCTION_CHANGE_ID?.trim();
    const ack = process.env.TEMPLATE_TWIN_LINEAGE_PRODUCTION_ACK?.trim();
    if (!productionAllowed || !changeId || ack !== `${target.database}:${phase}`) {
      throw qaError;
    }
  }

  if (phase === "contract") {
    const target = describeDbTarget(databaseUrl);
    const contractAck = process.env.TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK?.trim();
    if (contractAck !== `${LINEAGE_OPERATION_KEY}:${target.database}`) {
      throw new Error(
        "LINEAGE_MIGRATION_CONTRACT_ACK_REQUIRED",
      );
    }
  }
}

function buildClient(databaseUrl: string, phase: Phase): {
  client: TransactionalRawSqlClient & { $disconnect(): Promise<void> };
  pool: Pool;
} {
  const pool = new Pool({
    connectionString: withOperatorTimeouts(databaseUrl, phase),
    max: 2,
    connectionTimeoutMillis: 10_000,
  });
  const adapter = new PrismaPg(pool);
  const client = new PrismaClient({ adapter }) as unknown as TransactionalRawSqlClient & {
    $disconnect(): Promise<void>;
  };
  return { client, pool };
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function printSafeJson(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

async function run(): Promise<void> {
  const options = parseLineageOperatorArgs(process.argv.slice(2));
  const databaseUrl = process.env.DATABASE_URL?.trim();
  if (!databaseUrl) throw new Error("DATABASE_URL is required");
  assertMutationAuthorized(databaseUrl, options.phase);

  const { client, pool } = buildClient(databaseUrl, options.phase);
  let operatorLock: Awaited<ReturnType<typeof acquireLineageOperatorSessionLock>> | null = null;
  let stopping = false;
  const stop = () => {
    stopping = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  try {
    if (options.phase !== "status") {
      operatorLock = await acquireLineageOperatorSessionLock(pool);
    }
    if (options.phase === "status") {
      printSafeJson(await readLineageMigrationStatus(client));
      return;
    }

    if (options.phase === "backfill") {
      let batchesThisRun = 0;
      while (!stopping) {
        const batchStarted = performance.now();
        const result = await backfillLineageBatch(client, options.batchSize);
        const durationMs = Math.round((performance.now() - batchStarted) * 100) / 100;
        if (result.batchRows > 0) batchesThisRun += 1;
        printSafeJson({ event: "batch", durationMs, ...result });
        if (result.complete || stopping) break;
        if (options.maxBatches !== null && batchesThisRun >= options.maxBatches) {
          printSafeJson({ event: "paused", reason: "max_batches", batchesThisRun });
          break;
        }
        if (options.batchDelayMs > 0) await sleep(options.batchDelayMs);
      }
      printSafeJson({ event: "status", ...(await readLineageMigrationStatus(client)) });
      return;
    }

    if (options.phase === "guard-index") await buildLineageGuardIndex(client);
    if (options.phase === "indexes") await buildLineageIndexes(client);
    if (options.phase === "validate") await validateLineageContract(client);
    if (options.phase === "contract") await contractLineageNotNull(client);
    printSafeJson({ event: "status", ...(await readLineageMigrationStatus(client)) });
  } catch (error) {
    let code =
      error instanceof Error && error.message === "LINEAGE_MIGRATION_OPERATOR_BUSY"
        ? error.message
        : "OPERATOR_FAILED_BEFORE_PROGRESS_AVAILABLE";
    if (code !== "LINEAGE_MIGRATION_OPERATOR_BUSY") {
      try {
        code = await recordLineageMigrationFailure(client, error);
      } catch {
        // The expand migration or progress row may not exist. Preserve the
        // original failure without leaking a connection string or query payload.
      }
    }
    process.stderr.write(`${code}\n`);
    process.exitCode = 1;
  } finally {
    if (operatorLock) await operatorLock.release();
    await client.$disconnect();
    await pool.end();
  }
}

if (process.env.VITEST !== "true") {
  void run();
}
