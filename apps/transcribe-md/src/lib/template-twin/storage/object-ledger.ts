import type { Prisma } from "@prisma/client";

type LedgerState =
  | "INTENT"
  | "WRITTEN_UNCLAIMED"
  | "CLAIMED"
  | "RETAINED"
  | "PURGE_PENDING"
  | "PURGED"
  | "FAILED";

interface ObjectLedgerRow {
  id: string;
  practiceId: string;
  objectKey: string;
  objectVersionId: string | null;
  objectEtag: string | null;
  sha256: string;
  sizeBytes: number;
  kind: string;
  state: LedgerState | string;
  claimType: string | null;
  claimId: string | null;
  attemptCount: number;
  nextAttemptAt: Date | null;
  retentionUntil: Date | null;
  lastErrorCode: string | null;
}

export type TemplateTwinObjectLedgerClient = Pick<
  Prisma.TransactionClient,
  "templateTwinObjectLedger"
>;

export interface TemplateTwinObjectWriteInput {
  practiceId: string;
  objectKey: string;
  sha256: string;
  sizeBytes: number;
  kind: "source" | "output" | string;
}

export class TemplateTwinObjectLedgerConflictError extends Error {
  readonly code = "TEMPLATE_TWIN_OBJECT_LEDGER_CONFLICT";

  constructor() {
    super(
      "Template Twin object ledger metadata conflicts with an existing write.",
    );
    this.name = "TemplateTwinObjectLedgerConflictError";
  }
}

function sameWrite(
  row: ObjectLedgerRow,
  input: TemplateTwinObjectWriteInput,
): boolean {
  return (
    row.practiceId === input.practiceId &&
    row.objectKey === input.objectKey &&
    row.sha256 === input.sha256 &&
    row.sizeBytes === input.sizeBytes &&
    row.kind === input.kind &&
    row.state !== "PURGED"
  );
}

export async function beginTemplateTwinObjectWrite(
  prisma: TemplateTwinObjectLedgerClient,
  input: TemplateTwinObjectWriteInput,
): Promise<ObjectLedgerRow> {
  const existing = await prisma.templateTwinObjectLedger.findUnique({
    where: { objectKey: input.objectKey },
  });
  if (existing) {
    if (!sameWrite(existing, input)) {
      throw new TemplateTwinObjectLedgerConflictError();
    }
    return existing;
  }
  try {
    return await prisma.templateTwinObjectLedger.create({
      data: {
        practiceId: input.practiceId,
        objectKey: input.objectKey,
        objectVersionId: null,
        objectEtag: null,
        sha256: input.sha256,
        sizeBytes: input.sizeBytes,
        kind: input.kind,
        state: "INTENT",
        attemptCount: 0,
      },
    });
  } catch (error) {
    const winner = await prisma.templateTwinObjectLedger.findUnique({
      where: { objectKey: input.objectKey },
    });
    if (winner && sameWrite(winner, input)) return winner;
    throw error;
  }
}

export async function markTemplateTwinObjectWritten(
  prisma: TemplateTwinObjectLedgerClient,
  input: {
    objectKey: string;
    practiceId: string;
    objectVersionId: string;
    objectEtag: string;
    retentionUntil: Date;
  },
): Promise<void> {
  if (!input.objectVersionId.trim() || !input.objectEtag.trim()) {
    throw new TemplateTwinObjectLedgerConflictError();
  }
  const result = await prisma.templateTwinObjectLedger.updateMany({
    where: {
      objectKey: input.objectKey,
      practiceId: input.practiceId,
      OR: [
        {
          state: "INTENT",
          objectVersionId: null,
          objectEtag: null,
        },
        {
          state: "WRITTEN_UNCLAIMED",
          objectVersionId: input.objectVersionId,
          objectEtag: input.objectEtag,
        },
      ],
    },
    data: {
      state: "WRITTEN_UNCLAIMED",
      objectVersionId: input.objectVersionId,
      objectEtag: input.objectEtag,
      retentionUntil: input.retentionUntil,
      nextAttemptAt: null,
      lastErrorCode: null,
    },
  });
  if (result.count === 1) return;
  const existing = await prisma.templateTwinObjectLedger.findUnique({
    where: { objectKey: input.objectKey },
  });
  if (
    existing?.practiceId === input.practiceId &&
    existing.objectVersionId === input.objectVersionId &&
    existing.objectEtag === input.objectEtag &&
    ["WRITTEN_UNCLAIMED", "CLAIMED", "RETAINED"].includes(existing.state)
  ) {
    return;
  }
  throw new TemplateTwinObjectLedgerConflictError();
}

export async function claimTemplateTwinObject(
  prisma: TemplateTwinObjectLedgerClient,
  input: {
    objectKey: string;
    practiceId: string;
    claimType: "source_artifact" | "fill_manifest" | string;
    claimId: string;
  },
): Promise<void> {
  const result = await prisma.templateTwinObjectLedger.updateMany({
    where: {
      objectKey: input.objectKey,
      practiceId: input.practiceId,
      state: { in: ["WRITTEN_UNCLAIMED", "CLAIMED"] },
    },
    data: {
      state: "CLAIMED",
      claimType: input.claimType,
      claimId: input.claimId,
      nextAttemptAt: null,
      lastErrorCode: null,
    },
  });
  if (result.count === 1) return;
  const existing = await prisma.templateTwinObjectLedger.findUnique({
    where: { objectKey: input.objectKey },
  });
  if (
    existing?.practiceId === input.practiceId &&
    existing.state === "CLAIMED" &&
    existing.claimType === input.claimType &&
    existing.claimId === input.claimId
  ) {
    return;
  }
  throw new TemplateTwinObjectLedgerConflictError();
}

/**
 * Retains an immutable object that was written successfully but must never be
 * attached to its intended owner. This is the fail-closed side of the
 * write-before-relational-claim protocol: reconciliation may later purge the
 * object under the approved orphan policy, but no fill manifest can expose it.
 */
export async function quarantineTemplateTwinObject(
  prisma: TemplateTwinObjectLedgerClient,
  input: {
    objectKey: string;
    practiceId: string;
    objectVersionId: string;
    objectEtag: string;
    reasonCode: string;
  },
): Promise<void> {
  if (
    !input.objectVersionId.trim() ||
    !input.objectEtag.trim() ||
    !input.reasonCode.trim()
  ) {
    throw new TemplateTwinObjectLedgerConflictError();
  }
  const result = await prisma.templateTwinObjectLedger.updateMany({
    where: {
      objectKey: input.objectKey,
      practiceId: input.practiceId,
      objectVersionId: input.objectVersionId,
      objectEtag: input.objectEtag,
      state: "WRITTEN_UNCLAIMED",
      claimType: null,
      claimId: null,
    },
    data: {
      state: "RETAINED",
      nextAttemptAt: null,
      lastErrorCode: input.reasonCode,
    },
  });
  if (result.count === 1) return;
  const existing = await prisma.templateTwinObjectLedger.findUnique({
    where: { objectKey: input.objectKey },
  });
  if (
    existing?.practiceId === input.practiceId &&
    existing.objectVersionId === input.objectVersionId &&
    existing.objectEtag === input.objectEtag &&
    existing.state === "RETAINED" &&
    existing.claimType === null &&
    existing.claimId === null &&
    existing.lastErrorCode === input.reasonCode
  ) {
    return;
  }
  throw new TemplateTwinObjectLedgerConflictError();
}

export interface TemplateTwinObjectAdmin {
  statObject(objectKey: string): Promise<{
    exists: boolean;
    objectVersionId?: string;
    objectEtag?: string;
    sha256?: string;
    sizeBytes?: number;
  }>;
  deleteObject(objectKey: string, objectVersionId: string): Promise<void>;
}

function nextRetry(now: Date, attemptCount: number): Date {
  return new Date(
    now.getTime() +
      Math.min(60_000 * 2 ** Math.max(0, attemptCount), 3_600_000),
  );
}

export async function reconcileTemplateTwinObjectLedgers(input: {
  prisma: TemplateTwinObjectLedgerClient;
  objectAdmin: TemplateTwinObjectAdmin;
  now?: Date;
  orphanRetentionMs: number;
  /** Purging is a separate operations approval. When false, expired
   * unclaimed objects move to RETAINED and are never deleted. */
  purgeApproved: boolean;
  limit?: number;
}): Promise<{
  recovered: number;
  scheduled: number;
  purged: number;
  failed: number;
}> {
  if (
    !Number.isSafeInteger(input.orphanRetentionMs) ||
    input.orphanRetentionMs < 1
  ) {
    throw new Error(
      "An approved positive orphan retention window is required.",
    );
  }
  const now = input.now ?? new Date();
  const rows = await input.prisma.templateTwinObjectLedger.findMany({
    where: {
      state: {
        in: ["INTENT", "WRITTEN_UNCLAIMED", "RETAINED", "PURGE_PENDING"],
      },
      OR: [{ nextAttemptAt: null }, { nextAttemptAt: { lte: now } }],
    },
    orderBy: { createdAt: "asc" },
    take: Math.max(1, Math.min(input.limit ?? 100, 500)),
  });

  let recovered = 0;
  let scheduled = 0;
  let purged = 0;
  let failed = 0;

  for (const row of rows) {
    if (row.state === "INTENT") {
      try {
        const stat = await input.objectAdmin.statObject(row.objectKey);
        if (!stat.exists) {
          scheduled += 1;
          await input.prisma.templateTwinObjectLedger.update({
            where: { id: row.id },
            data: {
              attemptCount: { increment: 1 },
              nextAttemptAt: nextRetry(now, row.attemptCount),
              lastErrorCode: "OBJECT_NOT_YET_VISIBLE",
            },
          });
          continue;
        }
        if (
          !stat.objectVersionId?.trim() ||
          !stat.objectEtag?.trim() ||
          stat.sha256 !== row.sha256 ||
          stat.sizeBytes !== row.sizeBytes
        ) {
          failed += 1;
          await input.prisma.templateTwinObjectLedger.update({
            where: { id: row.id },
            data: {
              state: "FAILED",
              nextAttemptAt: null,
              lastErrorCode: "OBJECT_INTEGRITY_MISMATCH",
            },
          });
          continue;
        }
        recovered += 1;
        await input.prisma.templateTwinObjectLedger.update({
          where: { id: row.id },
          data: {
            state: "WRITTEN_UNCLAIMED",
            objectVersionId: stat.objectVersionId,
            objectEtag: stat.objectEtag,
            retentionUntil: new Date(now.getTime() + input.orphanRetentionMs),
            nextAttemptAt: null,
            lastErrorCode: null,
          },
        });
      } catch {
        scheduled += 1;
        await input.prisma.templateTwinObjectLedger.update({
          where: { id: row.id },
          data: {
            attemptCount: { increment: 1 },
            nextAttemptAt: nextRetry(now, row.attemptCount),
            lastErrorCode: "OBJECT_STAT_FAILED",
          },
        });
      }
      continue;
    }

    if (row.state === "WRITTEN_UNCLAIMED" || row.state === "RETAINED") {
      if (!row.retentionUntil || row.retentionUntil > now) continue;
      if (!input.purgeApproved) {
        if (row.state !== "RETAINED") {
          await input.prisma.templateTwinObjectLedger.update({
            where: { id: row.id },
            data: {
              state: "RETAINED",
              nextAttemptAt: null,
              lastErrorCode: "PURGE_APPROVAL_REQUIRED",
            },
          });
        }
        continue;
      }
      await input.prisma.templateTwinObjectLedger.update({
        where: { id: row.id },
        data: {
          state: "PURGE_PENDING",
          nextAttemptAt: now,
          lastErrorCode: null,
        },
      });
      continue;
    }

    if (row.state === "PURGE_PENDING") {
      try {
        if (!row.objectVersionId?.trim()) {
          throw new TemplateTwinObjectLedgerConflictError();
        }
        await input.objectAdmin.deleteObject(row.objectKey, row.objectVersionId);
        purged += 1;
        await input.prisma.templateTwinObjectLedger.update({
          where: { id: row.id },
          data: {
            state: "PURGED",
            nextAttemptAt: null,
            lastErrorCode: null,
          },
        });
      } catch {
        failed += 1;
        await input.prisma.templateTwinObjectLedger.update({
          where: { id: row.id },
          data: {
            attemptCount: { increment: 1 },
            nextAttemptAt: nextRetry(now, row.attemptCount),
            lastErrorCode: "OBJECT_PURGE_FAILED",
          },
        });
      }
    }
  }

  return { recovered, scheduled, purged, failed };
}
