import { describe, expect, it, vi } from "vitest";

import {
  reconcileStaleTemplateTwinQuarantines,
  type TemplateTwinQuarantineReconciliationClient,
} from "./template-twin-quarantine-reconciliation";

const NOW = new Date("2026-07-19T08:00:00.000Z");
const CUTOFF = new Date("2026-07-19T07:00:00.000Z");

function row(status: "QUARANTINED" | "MALWARE_CLEAN", id: string) {
  return {
    id,
    practiceId: "practice-synthetic",
    sha256: (status === "MALWARE_CLEAN" ? "b" : "a").repeat(64),
    intakeMode: "NATIVE_TEMPLATE",
    status,
    createdAt: new Date("2026-07-19T06:00:00.000Z"),
  };
}

function database(input: {
  rows: ReturnType<typeof row>[];
  updateCounts?: number[];
}) {
  const findMany = vi.fn().mockResolvedValue(input.rows);
  const updateMany = vi.fn();
  for (const count of input.updateCounts ?? input.rows.map(() => 1)) {
    updateMany.mockResolvedValueOnce({ count });
  }
  const outboxCreate = vi.fn().mockResolvedValue({ id: "outbox-synthetic" });
  const tx = {
    templateTwinQuarantineArtifact: { updateMany },
    templateTwinAuditOutbox: { create: outboxCreate },
  };
  const transaction = vi.fn(
    async (callback: (value: typeof tx) => Promise<unknown>) => callback(tx),
  );
  return {
    client: {
      templateTwinQuarantineArtifact: { findMany },
      $transaction: transaction,
    } as unknown as TemplateTwinQuarantineReconciliationClient,
    findMany,
    updateMany,
    outboxCreate,
    transaction,
  };
}

describe("stale Template Twin quarantine reconciliation", () => {
  it("terminally rejects pre-scan and post-scan stalls without deleting bytes", async () => {
    const db = database({
      rows: [row("QUARANTINED", "q-1"), row("MALWARE_CLEAN", "q-2")],
    });

    await expect(
      reconcileStaleTemplateTwinQuarantines({
        prisma: db.client,
        now: NOW,
        staleAfterMs: 60 * 60 * 1000,
        limit: 10,
      }),
    ).resolves.toEqual({
      quarantinedRejected: 1,
      malwareCleanRejected: 1,
      contended: 0,
    });

    expect(db.findMany).toHaveBeenCalledWith({
      where: {
        status: { in: ["QUARANTINED", "MALWARE_CLEAN"] },
        admittedAt: null,
        createdAt: { lte: CUTOFF },
      },
      select: {
        id: true,
        practiceId: true,
        sha256: true,
        intakeMode: true,
        status: true,
        createdAt: true,
      },
      orderBy: [{ createdAt: "asc" }, { id: "asc" }],
      take: 10,
    });
    expect(db.updateMany.mock.calls[0]?.[0]).toMatchObject({
      where: { id: "q-1", status: "QUARANTINED", createdAt: { lte: CUTOFF } },
      data: {
        status: "REJECTED",
        rejectionCodes: ["TEMPLATE_TWIN_QUARANTINE_PROCESSING_TIMEOUT"],
      },
    });
    expect(db.updateMany.mock.calls[1]?.[0]).toMatchObject({
      where: { id: "q-2", status: "MALWARE_CLEAN", createdAt: { lte: CUTOFF } },
      data: {
        status: "REJECTED",
        rejectionCodes: ["TEMPLATE_TWIN_POST_SCAN_ADMISSION_TIMEOUT"],
      },
    });
    expect(db.outboxCreate).toHaveBeenCalledTimes(2);
    for (const call of db.outboxCreate.mock.calls) {
      expect(call[0].data).toMatchObject({
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        actorId: null,
        metadata: expect.objectContaining({
          rawObjectDisposition: "retained_by_object_ledger_policy",
          gateOutcome: "terminally_rejected",
        }),
      });
    }
    expect(Object.keys(db.client)).not.toContain("templateTwinObjectLedger");
  });

  it("loses a race to admission without writing a misleading audit event", async () => {
    const db = database({
      rows: [row("MALWARE_CLEAN", "q-raced")],
      updateCounts: [0],
    });

    await expect(
      reconcileStaleTemplateTwinQuarantines({
        prisma: db.client,
        now: NOW,
        staleAfterMs: 60 * 60 * 1000,
      }),
    ).resolves.toEqual({
      quarantinedRejected: 0,
      malwareCleanRejected: 0,
      contended: 1,
    });
    expect(db.outboxCreate).not.toHaveBeenCalled();
  });

  it("rejects an invalid stale interval before querying state", async () => {
    const db = database({ rows: [] });

    await expect(
      reconcileStaleTemplateTwinQuarantines({
        prisma: db.client,
        staleAfterMs: 0,
      }),
    ).rejects.toThrow("stale interval is invalid");
    expect(db.findMany).not.toHaveBeenCalled();
  });
});
