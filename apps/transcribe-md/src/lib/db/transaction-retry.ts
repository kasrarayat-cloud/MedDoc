import { Prisma } from "@prisma/client";

import { log } from "@/lib/log";

export const DATABASE_TRANSACTION_MAX_ATTEMPTS = 3;
const BASE_BACKOFF_MS = 25;
const MAX_BACKOFF_MS = 200;

export type RetriableDatabaseCode = "40P01" | "40001" | "P2034";

export interface TransactionHost {
  $transaction<T>(
    callback: (tx: Prisma.TransactionClient) => Promise<T>,
    options?: { isolationLevel?: Prisma.TransactionIsolationLevel },
  ): Promise<T>;
}

export interface TransactionRetrySafeContext {
  visitId?: string;
  practiceId?: string;
  runId?: string;
  manifestId?: string;
}

export interface TransactionRetryMetricSnapshot {
  attempts: number;
  retries: number;
  exhausted: number;
  deadlocks: number;
  serializationFailures: number;
}

const retryMetrics: TransactionRetryMetricSnapshot = {
  attempts: 0,
  retries: 0,
  exhausted: 0,
  deadlocks: 0,
  serializationFailures: 0,
};

export class DatabaseTransactionRetryExhaustedError extends Error {
  readonly code = "DATABASE_TRANSACTION_RETRY_EXHAUSTED" as const;

  constructor(
    readonly operation: string,
    readonly databaseCode: RetriableDatabaseCode,
    readonly attempts: number,
    cause: unknown,
  ) {
    super(
      `Database transaction could not complete after ${attempts} bounded attempts.`,
      { cause },
    );
    this.name = "DatabaseTransactionRetryExhaustedError";
  }
}

function candidateCodes(error: unknown): unknown[] {
  if (!error || typeof error !== "object") return [];
  const record = error as Record<string, unknown>;
  const meta =
    record.meta && typeof record.meta === "object"
      ? (record.meta as Record<string, unknown>)
      : null;
  return [
    record.code,
    record.sqlState,
    record.sqlstate,
    record.originalCode,
    meta?.code,
    meta?.sqlState,
    meta?.sqlstate,
    meta?.originalCode,
  ];
}

export function retriableDatabaseCode(
  error: unknown,
): RetriableDatabaseCode | null {
  const seen = new Set<unknown>();
  const pending: Array<{ value: unknown; depth: number }> = [
    { value: error, depth: 0 },
  ];
  while (pending.length > 0 && seen.size < 32) {
    const current = pending.shift();
    if (!current) break;
    const cursor = current.value;
    if (!cursor || seen.has(cursor)) continue;
    seen.add(cursor);
    for (const code of candidateCodes(cursor)) {
      if (code === "40P01" || code === "40001" || code === "P2034") {
        return code;
      }
    }
    if (
      current.depth >= 5 ||
      typeof cursor !== "object" ||
      cursor === null
    ) {
      continue;
    }
    const record = cursor as Record<string, unknown>;
    for (const key of [
      "cause",
      "meta",
      "driverAdapterError",
      "originalError",
      "error",
    ]) {
      const child = record[key];
      if (child && typeof child === "object") {
        pending.push({ value: child, depth: current.depth + 1 });
      }
    }
  }
  return null;
}

function backoffMs(attempt: number, random: () => number): number {
  const ceiling = Math.min(BASE_BACKOFF_MS * 2 ** (attempt - 1), MAX_BACKOFF_MS);
  return Math.max(1, Math.round(ceiling / 2 + random() * (ceiling / 2)));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function recordFailure(code: RetriableDatabaseCode): void {
  if (code === "40P01") retryMetrics.deadlocks += 1;
  else retryMetrics.serializationFailures += 1;
}

/**
 * Retries one complete SERIALIZABLE transaction after PostgreSQL deadlock or
 * serialization abort. The callback must contain database work only and be
 * idempotent: provider calls, object writes, email, and other irreversible
 * side effects belong outside this boundary.
 */
export async function runSerializableTransactionWithRetry<T>(input: {
  prisma: TransactionHost;
  operation: string;
  context?: TransactionRetrySafeContext;
  maxAttempts?: number;
  isolationLevel?: Prisma.TransactionIsolationLevel;
  transaction: (
    tx: Prisma.TransactionClient,
    attempt: number,
  ) => Promise<T>;
  /** Test-only deterministic hooks; production callers must omit these. */
  retryHooks?: {
    sleep?: (ms: number) => Promise<void>;
    random?: () => number;
    onRetry?: (input: {
      attempt: number;
      code: RetriableDatabaseCode;
      delayMs: number;
    }) => void;
  };
}): Promise<T> {
  const maxAttempts = Math.max(
    1,
    Math.min(input.maxAttempts ?? DATABASE_TRANSACTION_MAX_ATTEMPTS, 5),
  );
  const wait = input.retryHooks?.sleep ?? sleep;
  const random = input.retryHooks?.random ?? Math.random;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    retryMetrics.attempts += 1;
    try {
      return await input.prisma.$transaction(
        (tx) => input.transaction(tx, attempt),
        {
          isolationLevel:
            input.isolationLevel ??
            Prisma.TransactionIsolationLevel.Serializable,
        },
      );
    } catch (error) {
      const code = retriableDatabaseCode(error);
      if (!code) throw error;
      recordFailure(code);
      if (attempt >= maxAttempts) {
        retryMetrics.exhausted += 1;
        log.error("database-transaction-retry", "bounded retry exhausted", {
          operation: input.operation,
          databaseCode: code,
          attempts: attempt,
          ...input.context,
        });
        throw new DatabaseTransactionRetryExhaustedError(
          input.operation,
          code,
          attempt,
          error,
        );
      }
      retryMetrics.retries += 1;
      const delayMs = backoffMs(attempt, random);
      log.warn("database-transaction-retry", "retrying complete transaction", {
        operation: input.operation,
        databaseCode: code,
        attempt,
        maxAttempts,
        delayMs,
        ...input.context,
      });
      input.retryHooks?.onRetry?.({ attempt, code, delayMs });
      await wait(delayMs);
    }
  }
  throw new Error("Unreachable transaction retry state.");
}

export function getDatabaseTransactionRetryMetrics(): Readonly<TransactionRetryMetricSnapshot> {
  return { ...retryMetrics };
}

export function resetDatabaseTransactionRetryMetricsForTest(): void {
  retryMetrics.attempts = 0;
  retryMetrics.retries = 0;
  retryMetrics.exhausted = 0;
  retryMetrics.deadlocks = 0;
  retryMetrics.serializationFailures = 0;
}
