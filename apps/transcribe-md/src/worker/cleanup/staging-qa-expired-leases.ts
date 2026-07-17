import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";

import { reconcileExpiredTemplateTwinSyntheticQaWorkerClaim } from "@/worker/synthetic-qa-provider";

export const TEMPLATE_TWIN_STAGING_QA_LEASE_SCAN_INTERVAL_MS = 15_000;
export const TEMPLATE_TWIN_STAGING_QA_LEASE_SCAN_LIMIT = 25;
const MAX_SCAN_LIMIT = 100;

interface ExpiredSyntheticQaLeaseCandidate {
  id: string;
  visitId: string;
  doctorId: string;
  attempt: number;
  workerLeaseExpiresAt: Date;
}

export interface TemplateTwinSyntheticQaLeaseScanCursor {
  workerLeaseExpiresAt: Date;
  id: string;
}

export interface TemplateTwinSyntheticQaLeaseScanResult {
  scanned: number;
  reconciled: number;
  failed: number;
  nextCursor: TemplateTwinSyntheticQaLeaseScanCursor | null;
}

interface TemplateTwinSyntheticQaLeaseScanDependencies {
  listExpired(input: {
    now: Date;
    limit: number;
    cursor: TemplateTwinSyntheticQaLeaseScanCursor | null;
  }): Promise<readonly ExpiredSyntheticQaLeaseCandidate[]>;
  reconcile(input: {
    runId: string;
    visitId: string;
    userId: string;
    attempt: number;
    now: Date;
  }): Promise<boolean>;
}

const leaseScanDatabase = prisma as {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
};

const defaultDependencies: TemplateTwinSyntheticQaLeaseScanDependencies = {
  // Use the database clock so container clock skew cannot strand an expired
  // owner or prematurely revoke a live one. This query is projection-only,
  // bounded, and contains no document or encounter content.
  listExpired: ({ limit, cursor }) => {
    const projection = Prisma.sql`
      SELECT "id", "visitId", "doctorId", "attempt", "workerLeaseExpiresAt"
      FROM "template_twin_synthetic_qa_runs"
      WHERE "status" = 'PROCESSING'
        AND "workerClaimId" IS NOT NULL
        AND "workerLeaseExpiresAt" <= clock_timestamp()
    `;
    return cursor
      ? leaseScanDatabase.$queryRaw<ExpiredSyntheticQaLeaseCandidate[]>(
          Prisma.sql`
            ${projection}
            ORDER BY
              CASE WHEN ("workerLeaseExpiresAt", "id") >
                (${cursor.workerLeaseExpiresAt}, ${cursor.id})
                THEN 0 ELSE 1 END,
              "workerLeaseExpiresAt" ASC, "id" ASC
            LIMIT ${limit}
          `,
        )
      : leaseScanDatabase.$queryRaw<ExpiredSyntheticQaLeaseCandidate[]>(
          Prisma.sql`
            ${projection}
            ORDER BY "workerLeaseExpiresAt" ASC, "id" ASC
            LIMIT ${limit}
          `,
        );
  },
  // The durable reconciler independently reads database time inside its
  // transaction. The scan timestamp is only a deterministic test seam.
  reconcile: (input) =>
    reconcileExpiredTemplateTwinSyntheticQaWorkerClaim({
      runId: input.runId,
      visitId: input.visitId,
      userId: input.userId,
      attempt: input.attempt,
    }),
};

/**
 * Bounded, idempotent recovery for PROCESSING attempts whose BullMQ failed
 * event was lost or whose one-shot handler encountered a transient database
 * failure. Multiple worker replicas may scan the same row: the reconciler's
 * transactional conditional update and deterministic audit key permit exactly
 * one clinical transition.
 */
export async function scanExpiredTemplateTwinSyntheticQaWorkerClaims(input?: {
  now?: Date;
  limit?: number;
  cursor?: TemplateTwinSyntheticQaLeaseScanCursor | null;
  dependencies?: Partial<TemplateTwinSyntheticQaLeaseScanDependencies>;
}): Promise<TemplateTwinSyntheticQaLeaseScanResult> {
  const now = input?.now ?? new Date();
  const limit = input?.limit ?? TEMPLATE_TWIN_STAGING_QA_LEASE_SCAN_LIMIT;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > MAX_SCAN_LIMIT) {
    throw new Error("Template Twin synthetic QA lease scan limit is invalid.");
  }
  const dependencies = { ...defaultDependencies, ...input?.dependencies };
  const candidates = await dependencies.listExpired({
    now,
    limit,
    cursor: input?.cursor ?? null,
  });
  let reconciled = 0;
  let failed = 0;
  for (const candidate of candidates) {
    try {
      if (
        await dependencies.reconcile({
          runId: candidate.id,
          visitId: candidate.visitId,
          userId: candidate.doctorId,
          attempt: candidate.attempt,
          now,
        })
      ) {
        reconciled += 1;
      }
    } catch {
      // A malformed/contended row must not starve later expired attempts.
      // Only an aggregate count leaves this module; no identifier, database
      // message, document text, or encounter content is logged.
      failed += 1;
    }
  }
  const last = candidates.at(-1);
  return {
    scanned: candidates.length,
    reconciled,
    failed,
    nextCursor: last
      ? { workerLeaseExpiresAt: last.workerLeaseExpiresAt, id: last.id }
      : null,
  };
}

export interface TemplateTwinSyntheticQaLeaseReconciler {
  runNow(): Promise<TemplateTwinSyntheticQaLeaseScanResult | null>;
  stop(): void;
}

/**
 * Worker-lifecycle scheduler. It runs immediately, retries after transient
 * failures, never overlaps itself, and stops with the BullMQ worker. Errors are
 * surfaced only through a caller-provided aggregate callback; no job payload,
 * encounter text, object key, or database error message is emitted here.
 */
export function startTemplateTwinSyntheticQaExpiredLeaseReconciler(input: {
  enabled: boolean;
  intervalMs?: number;
  scan?: (
    cursor: TemplateTwinSyntheticQaLeaseScanCursor | null,
  ) => Promise<TemplateTwinSyntheticQaLeaseScanResult>;
  onError?: () => void;
  onResult?: (result: TemplateTwinSyntheticQaLeaseScanResult) => void;
}): TemplateTwinSyntheticQaLeaseReconciler {
  const intervalMs =
    input.intervalMs ?? TEMPLATE_TWIN_STAGING_QA_LEASE_SCAN_INTERVAL_MS;
  if (!Number.isSafeInteger(intervalMs) || intervalMs < 1_000) {
    throw new Error(
      "Template Twin synthetic QA lease scan interval is invalid.",
    );
  }
  const scan =
    input.scan ??
    ((cursor: TemplateTwinSyntheticQaLeaseScanCursor | null) =>
      scanExpiredTemplateTwinSyntheticQaWorkerClaims({ cursor }));
  let stopped = !input.enabled;
  let cursor: TemplateTwinSyntheticQaLeaseScanCursor | null = null;
  let inFlight: Promise<TemplateTwinSyntheticQaLeaseScanResult | null> | null =
    null;

  const runNow = (): Promise<TemplateTwinSyntheticQaLeaseScanResult | null> => {
    if (stopped) return Promise.resolve(null);
    if (inFlight) return inFlight;
    inFlight = scan(cursor)
      .then((result) => {
        // Advance even when every candidate failed. A fixed oldest-first page
        // lets permanent poison rows starve the queue; this cyclic cursor
        // visits the next page on the following tick and wraps at the end.
        cursor = result.nextCursor;
        input.onResult?.(result);
        return result;
      })
      .catch(() => {
        input.onError?.();
        return null;
      })
      .finally(() => {
        inFlight = null;
      });
    return inFlight;
  };

  const timer = input.enabled
    ? setInterval(() => {
        void runNow();
      }, intervalMs)
    : null;
  timer?.unref?.();
  if (input.enabled) void runNow();

  return {
    runNow,
    stop() {
      if (stopped) return;
      stopped = true;
      if (timer) clearInterval(timer);
    },
  };
}
