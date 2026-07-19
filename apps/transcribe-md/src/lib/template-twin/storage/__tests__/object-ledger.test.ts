import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  TemplateTwinObjectLedgerConflictError,
  beginTemplateTwinObjectWrite,
  claimTemplateTwinObject,
  markTemplateTwinObjectWritten,
  reconcileTemplateTwinObjectLedgers,
} from "../object-ledger";
import type { TemplateTwinObjectLedgerClient } from "../object-ledger";

const findUnique = vi.fn();
const findMany = vi.fn();
const create = vi.fn();
const update = vi.fn();
const updateMany = vi.fn();
const db = {
  templateTwinObjectLedger: {
    findUnique,
    findMany,
    create,
    update,
    updateMany,
  },
};
const ledgerDb = db as unknown as TemplateTwinObjectLedgerClient;

const intent = {
  id: "ledger-1",
  practiceId: "practice-1",
  objectKey:
    "practices/practice-1/template-twin/outputs/visit-1/" +
    `${"a".repeat(64)}/artifact-1/${"b".repeat(64)}.docx`,
  objectVersionId: null,
  objectEtag: null,
  sha256: "b".repeat(64),
  sizeBytes: 128,
  kind: "output",
  state: "INTENT",
  claimType: null,
  claimId: null,
  attemptCount: 0,
  nextAttemptAt: null,
  retentionUntil: null,
  lastErrorCode: null,
  createdAt: new Date("2026-07-15T20:00:00.000Z"),
  updatedAt: new Date("2026-07-15T20:00:00.000Z"),
};

beforeEach(() => {
  vi.clearAllMocks();
  findUnique.mockResolvedValue(null);
  findMany.mockResolvedValue([]);
  create.mockResolvedValue(intent);
  update.mockResolvedValue(intent);
  updateMany.mockResolvedValue({ count: 1 });
});

describe("Template Twin durable object ledger", () => {
  it("persists an INTENT before storage and accepts an identical retry", async () => {
    await beginTemplateTwinObjectWrite(ledgerDb, intent);
    expect(create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        objectKey: intent.objectKey,
        state: "INTENT",
      }),
    });

    findUnique.mockResolvedValue(intent);
    await expect(
      beginTemplateTwinObjectWrite(ledgerDb, intent),
    ).resolves.toEqual(intent);
    expect(create).toHaveBeenCalledTimes(1);
  });

  it("rejects a colliding retry with different bytes or tenant", async () => {
    findUnique.mockResolvedValue(intent);
    await expect(
      beginTemplateTwinObjectWrite(ledgerDb, {
        ...intent,
        sha256: "c".repeat(64),
      }),
    ).rejects.toBeInstanceOf(TemplateTwinObjectLedgerConflictError);
  });

  it("marks a verified write, then atomically claims it for the owning row", async () => {
    await markTemplateTwinObjectWritten(ledgerDb, {
      objectKey: intent.objectKey,
      practiceId: intent.practiceId,
      objectVersionId: "provider-version-1",
      objectEtag: "provider-etag-1",
      retentionUntil: new Date("2026-07-16T20:00:00.000Z"),
    });
    expect(updateMany).toHaveBeenCalledWith({
      where: {
        objectKey: intent.objectKey,
        practiceId: intent.practiceId,
        OR: [
          {
            state: "INTENT",
            objectVersionId: null,
            objectEtag: null,
          },
          {
            state: "WRITTEN_UNCLAIMED",
            objectVersionId: "provider-version-1",
            objectEtag: "provider-etag-1",
          },
        ],
      },
      data: expect.objectContaining({
        state: "WRITTEN_UNCLAIMED",
        objectVersionId: "provider-version-1",
        objectEtag: "provider-etag-1",
      }),
    });

    await claimTemplateTwinObject(ledgerDb, {
      objectKey: intent.objectKey,
      practiceId: intent.practiceId,
      claimType: "fill_manifest",
      claimId: "fill-1",
    });
    expect(updateMany).toHaveBeenLastCalledWith({
      where: {
        objectKey: intent.objectKey,
        practiceId: intent.practiceId,
        state: { in: ["WRITTEN_UNCLAIMED", "CLAIMED"] },
      },
      data: {
        state: "CLAIMED",
        claimType: "fill_manifest",
        claimId: "fill-1",
        nextAttemptAt: null,
        lastErrorCode: null,
      },
    });
  });

  it("recovers a crash after PUT, ages the orphan, and purges idempotently", async () => {
    const now = new Date("2026-07-15T20:10:00.000Z");
    const statObject = vi.fn().mockResolvedValue({
      exists: true,
      objectVersionId: "provider-version-crash-recovery",
      objectEtag: "provider-etag-crash-recovery",
      sha256: intent.sha256,
      sizeBytes: intent.sizeBytes,
    });
    const deleteObject = vi.fn().mockResolvedValue(undefined);

    findMany.mockResolvedValueOnce([intent]);
    await expect(
      reconcileTemplateTwinObjectLedgers({
        prisma: ledgerDb,
        objectAdmin: { statObject, deleteObject },
        now,
        orphanRetentionMs: 60_000,
        purgeApproved: true,
      }),
    ).resolves.toEqual({ recovered: 1, scheduled: 0, purged: 0, failed: 0 });
    expect(update).toHaveBeenLastCalledWith({
      where: { id: intent.id },
      data: {
        state: "WRITTEN_UNCLAIMED",
        objectVersionId: "provider-version-crash-recovery",
        objectEtag: "provider-etag-crash-recovery",
        retentionUntil: new Date("2026-07-15T20:11:00.000Z"),
        nextAttemptAt: null,
        lastErrorCode: null,
      },
    });

    findMany.mockResolvedValueOnce([
      { ...intent, state: "WRITTEN_UNCLAIMED", retentionUntil: now },
    ]);
    await reconcileTemplateTwinObjectLedgers({
      prisma: ledgerDb,
      objectAdmin: { statObject, deleteObject },
      now,
      orphanRetentionMs: 60_000,
      purgeApproved: true,
    });
    expect(update).toHaveBeenLastCalledWith({
      where: { id: intent.id },
      data: {
        state: "PURGE_PENDING",
        nextAttemptAt: now,
        lastErrorCode: null,
      },
    });

    findMany.mockResolvedValueOnce([
      {
        ...intent,
        state: "PURGE_PENDING",
        objectVersionId: "provider-version-crash-recovery",
        objectEtag: "provider-etag-crash-recovery",
      },
    ]);
    await expect(
      reconcileTemplateTwinObjectLedgers({
        prisma: ledgerDb,
        objectAdmin: { statObject, deleteObject },
        now,
        orphanRetentionMs: 60_000,
        purgeApproved: true,
      }),
    ).resolves.toEqual({ recovered: 0, scheduled: 0, purged: 1, failed: 0 });
    expect(deleteObject).toHaveBeenCalledWith(
      intent.objectKey,
      "provider-version-crash-recovery",
    );
    expect(update).toHaveBeenLastCalledWith({
      where: { id: intent.id },
      data: {
        state: "PURGED",
        nextAttemptAt: null,
        lastErrorCode: null,
      },
    });
  });

  it("fails closed on a stored object whose bytes do not match the ledger", async () => {
    findMany.mockResolvedValueOnce([intent]);
    const deleteObject = vi.fn();
    await expect(
      reconcileTemplateTwinObjectLedgers({
        prisma: ledgerDb,
        objectAdmin: {
          statObject: vi.fn().mockResolvedValue({
            exists: true,
            objectVersionId: "provider-version-mismatch",
            objectEtag: "provider-etag-mismatch",
            sha256: "c".repeat(64),
            sizeBytes: intent.sizeBytes,
          }),
          deleteObject,
        },
        now: new Date("2026-07-15T20:10:00.000Z"),
        orphanRetentionMs: 60_000,
        purgeApproved: true,
      }),
    ).resolves.toEqual({ recovered: 0, scheduled: 0, purged: 0, failed: 1 });
    expect(deleteObject).not.toHaveBeenCalled();
    expect(update).toHaveBeenLastCalledWith({
      where: { id: intent.id },
      data: expect.objectContaining({
        state: "FAILED",
        lastErrorCode: "OBJECT_INTEGRITY_MISMATCH",
      }),
    });
  });

  it("retains expired unclaimed objects until purge is explicitly approved", async () => {
    const now = new Date("2026-07-15T20:10:00.000Z");
    const deleteObject = vi.fn();
    findMany.mockResolvedValueOnce([
      { ...intent, state: "WRITTEN_UNCLAIMED", retentionUntil: now },
    ]);

    await expect(
      reconcileTemplateTwinObjectLedgers({
        prisma: ledgerDb,
        objectAdmin: { statObject: vi.fn(), deleteObject },
        now,
        orphanRetentionMs: 60_000,
        purgeApproved: false,
      }),
    ).resolves.toEqual({ recovered: 0, scheduled: 0, purged: 0, failed: 0 });
    expect(deleteObject).not.toHaveBeenCalled();
    expect(update).toHaveBeenCalledWith({
      where: { id: intent.id },
      data: {
        state: "RETAINED",
        nextAttemptAt: null,
        lastErrorCode: "PURGE_APPROVAL_REQUIRED",
      },
    });
  });
});
