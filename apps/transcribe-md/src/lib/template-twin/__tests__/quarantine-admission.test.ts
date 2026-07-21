import { createHash } from "node:crypto";

import type { Prisma } from "@prisma/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  quarantineCreate: vi.fn(),
  quarantineUpdateMany: vi.fn(),
  ledgerUpdateMany: vi.fn(),
  ledgerFindUnique: vi.fn(),
  outboxCreate: vi.fn(),
  finalRollout: vi.fn(),
  currentPhysician: vi.fn(),
}));

vi.mock("@meddoc/db", () => {
  const tx = {
    templateTwinQuarantineArtifact: {
      create: mocks.quarantineCreate,
      updateMany: mocks.quarantineUpdateMany,
    },
    templateTwinObjectLedger: {
      updateMany: mocks.ledgerUpdateMany,
      findUnique: mocks.ledgerFindUnique,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
  };
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) => callback(tx),
  );
  return { default: { $transaction: mocks.transaction } };
});

vi.mock("../rollout", async (importOriginal) => ({
  ...((await importOriginal()) as typeof import("../rollout")),
  lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
}));

vi.mock("../final-claim-authority", async (importOriginal) => ({
  ...((await importOriginal()) as typeof import("../final-claim-authority")),
  lockAndAssertCurrentTemplateTwinPhysician: mocks.currentPhysician,
}));

import {
  admitTemplateTwinQuarantine,
  beginTemplateTwinQuarantine,
  isolateCompletedExampleQuarantine,
  rejectTemplateTwinQuarantine,
  scanTemplateTwinQuarantine,
  type TemplateTwinQuarantineReceipt,
} from "../quarantine-admission";
import {
  TemplateTwinMalwareRejectedError,
  TemplateTwinMalwareScanUnavailableError,
  TEMPLATE_TWIN_MALWARE_SCAN_PROFILE,
  type TemplateTwinMalwareScanEvidence,
  type TemplateTwinMalwareScanner,
} from "../malware-scan";
import type { TemplateTwinArtifactStore } from "../storage";
import { TEMPLATE_TWIN_METADATA_PROFILE } from "../source-metadata";
import type { TemplateTwinRolloutToken } from "../rollout";

const SOURCE = Buffer.from("synthetic raw DOCX intake bytes", "utf8");
const ACTOR = {
  userId: "doctor_synthetic_1",
  userEmail: "doctor@synthetic.test",
  practiceId: "practice_synthetic_1",
  rolloutToken: {
    practiceId: "practice_synthetic_1",
    globalGeneration: BigInt(2),
    practiceGeneration: BigInt(3),
  } satisfies TemplateTwinRolloutToken,
};
const SAME_PRACTICE_FOREIGN_ACTOR = {
  ...ACTOR,
  userId: "doctor_synthetic_2",
  userEmail: "foreign-doctor@synthetic.test",
};

function digest(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

function scanEvidence(
  verdict: "clean" | "infected",
): TemplateTwinMalwareScanEvidence {
  const unsigned = {
    profileVersion: TEMPLATE_TWIN_MALWARE_SCAN_PROFILE,
    scanner: "clamav-clamd" as const,
    transport: "unix-domain-socket" as const,
    engineVersion: "1.4.3",
    signatureVersion: "27888",
    sourceSha256: digest(SOURCE),
    sourceSizeBytes: SOURCE.byteLength,
    verdict,
    threatNameSha256:
      verdict === "infected" ? digest("Synthetic-Test-Signature") : null,
    scannedAt: "2026-07-19T00:00:00.000Z",
  };
  return {
    ...unsigned,
    attestationSha256: digest(JSON.stringify(unsigned)),
  };
}

function storage() {
  const storeQuarantineArtifact = vi.fn().mockResolvedValue({
    bucket: "synthetic-private-template-artifacts",
    objectKey: `practices/${ACTOR.practiceId}/template-twin/quarantine/lineage_synthetic/v1/artifact_synthetic/${digest(SOURCE)}.docx`,
    objectVersionId: "provider-quarantine-version-synthetic",
    objectEtag: "provider-quarantine-etag-synthetic",
    sha256: digest(SOURCE),
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    sizeBytes: SOURCE.byteLength,
    created: true,
  });
  return {
    value: { storeQuarantineArtifact } as unknown as TemplateTwinArtifactStore,
    storeQuarantineArtifact,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) =>
      callback({
        templateTwinQuarantineArtifact: {
          create: mocks.quarantineCreate,
          updateMany: mocks.quarantineUpdateMany,
        },
        templateTwinObjectLedger: {
          updateMany: mocks.ledgerUpdateMany,
          findUnique: mocks.ledgerFindUnique,
        },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
      }),
  );
  mocks.quarantineCreate.mockResolvedValue({ id: "quarantine_synthetic_1" });
  mocks.quarantineUpdateMany.mockResolvedValue({ count: 1 });
  mocks.ledgerUpdateMany.mockResolvedValue({ count: 1 });
  mocks.ledgerFindUnique.mockResolvedValue(null);
  mocks.outboxCreate.mockResolvedValue({ id: "outbox_synthetic_1" });
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: ACTOR.rolloutToken,
  });
  mocks.currentPhysician.mockResolvedValue({ email: ACTOR.userEmail });
});

describe("Template Twin raw-quarantine admission", () => {
  it("captures immutable bytes and ledger ownership before any downstream gate", async () => {
    const artifactStore = storage();
    const receipt = await beginTemplateTwinQuarantine({
      source: SOURCE,
      actor: ACTOR,
      intakeMode: "NATIVE_TEMPLATE",
      lineageId: "lineage_synthetic",
      storage: artifactStore.value,
    });

    expect(artifactStore.storeQuarantineArtifact).toHaveBeenCalledWith({
      practiceId: ACTOR.practiceId,
      lineageId: "lineage_synthetic",
      lineageVersion: 1,
      bytes: SOURCE,
    });
    expect(
      artifactStore.storeQuarantineArtifact.mock.invocationCallOrder[0],
    ).toBeLessThan(mocks.quarantineCreate.mock.invocationCallOrder[0]!);
    expect(mocks.finalRollout.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.currentPhysician.mock.invocationCallOrder[0]!,
    );
    expect(mocks.currentPhysician.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.quarantineCreate.mock.invocationCallOrder[0]!,
    );
    expect(mocks.quarantineCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        id: receipt.id,
        intakeMode: "NATIVE_TEMPLATE",
        status: "QUARANTINED",
        sha256: digest(SOURCE),
        objectVersionId: "provider-quarantine-version-synthetic",
        objectEtag: "provider-quarantine-etag-synthetic",
      }),
    });
    expect(mocks.ledgerUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: "CLAIMED",
          claimType: "quarantine_artifact",
          claimId: receipt.id,
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: "TEMPLATE_TWIN_QUARANTINED",
        targetId: receipt.id,
        metadata: expect.objectContaining({
          gateOutcome: "pending_malware_scan",
        }),
      }),
    });
    expect(JSON.stringify(mocks.outboxCreate.mock.calls)).not.toContain(
      SOURCE.toString("utf8"),
    );
  });

  it("leaves newly stored bytes unclaimed when physician authority changes before capture", async () => {
    const artifactStore = storage();
    mocks.currentPhysician.mockRejectedValueOnce(
      new Error("synthetic current-authority revocation"),
    );

    await expect(
      beginTemplateTwinQuarantine({
        source: SOURCE,
        actor: ACTOR,
        intakeMode: "NATIVE_TEMPLATE",
        lineageId: "lineage_synthetic",
        storage: artifactStore.value,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED",
    });

    expect(artifactStore.storeQuarantineArtifact).toHaveBeenCalledTimes(1);
    expect(mocks.quarantineCreate).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdateMany).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("cannot admit or isolate a clean quarantine row after authority revocation", async () => {
    const stored = {
      bucket: "synthetic-private-template-artifacts",
      objectKey: "synthetic/quarantine/object.docx",
      objectVersionId: "provider-quarantine-version-synthetic",
      objectEtag: "provider-quarantine-etag-synthetic",
      sha256: digest(SOURCE),
      mimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const,
      sizeBytes: SOURCE.byteLength,
      created: true,
    };
    const nativeReceipt: TemplateTwinQuarantineReceipt = {
      id: "quarantine_native_synthetic",
      lineageId: "lineage_native_synthetic",
      lineageVersion: 1,
      intakeMode: "NATIVE_TEMPLATE",
      stored,
    };
    const completedReceipt: TemplateTwinQuarantineReceipt = {
      ...nativeReceipt,
      id: "quarantine_completed_synthetic",
      lineageId: "lineage_completed_synthetic",
      intakeMode: "COMPLETED_EXAMPLE",
    };
    const metadataEvidence = {
      profileVersion: TEMPLATE_TWIN_METADATA_PROFILE,
      originalSha256: digest(SOURCE),
      minimizedSha256: "a".repeat(64),
      replacedParts: [] as const,
      zipEntryTimestampsNormalized: true as const,
    };
    const tx = {
      templateTwinQuarantineArtifact: {
        updateMany: mocks.quarantineUpdateMany,
      },
      templateTwinAuditOutbox: { create: mocks.outboxCreate },
    } as unknown as Prisma.TransactionClient;
    mocks.currentPhysician.mockRejectedValue(
      new Error("synthetic current-authority revocation"),
    );

    await expect(
      admitTemplateTwinQuarantine({
        tx,
        receipt: nativeReceipt,
        actor: ACTOR,
        sourceArtifactId: "source_artifact_synthetic",
        metadataEvidence,
      }),
    ).rejects.toThrow("synthetic current-authority revocation");
    await expect(
      isolateCompletedExampleQuarantine({
        tx,
        receipt: completedReceipt,
        actor: ACTOR,
        candidateId: "candidate_synthetic",
        metadataEvidence,
      }),
    ).rejects.toThrow("synthetic current-authority revocation");

    expect(mocks.quarantineUpdateMany).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("binds a clean ClamAV receipt to the quarantine row", async () => {
    const artifactStore = storage();
    const receipt = await beginTemplateTwinQuarantine({
      source: SOURCE,
      actor: ACTOR,
      intakeMode: "NATIVE_TEMPLATE",
      lineageId: "lineage_synthetic",
      storage: artifactStore.value,
    });
    vi.clearAllMocks();
    mocks.transaction.mockImplementation(
      async (callback: (client: unknown) => Promise<unknown>) =>
        callback({
          templateTwinQuarantineArtifact: {
            updateMany: mocks.quarantineUpdateMany,
          },
          templateTwinAuditOutbox: { create: mocks.outboxCreate },
        }),
    );
    mocks.quarantineUpdateMany.mockResolvedValue({ count: 1 });
    const evidence = scanEvidence("clean");
    const scanner: TemplateTwinMalwareScanner = {
      scan: vi.fn().mockResolvedValue(evidence),
    };

    await expect(
      scanTemplateTwinQuarantine({
        source: SOURCE,
        receipt,
        actor: ACTOR,
        scanner,
      }),
    ).resolves.toEqual(evidence);
    expect(mocks.quarantineUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({
        id: receipt.id,
        status: "QUARANTINED",
        sha256: digest(SOURCE),
      }),
      data: expect.objectContaining({
        status: "MALWARE_CLEAN",
        malwareScanEvidence: evidence,
        rejectionCodes: [],
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: "TEMPLATE_TWIN_MALWARE_SCANNED",
        actorEmailSnapshot: null,
        metadata: expect.objectContaining({ verdict: "clean" }),
      }),
    });
  });

  it("never lets a same-practice physician transition another physician's quarantine row", async () => {
    const stored = {
      bucket: "synthetic-private-template-artifacts",
      objectKey: "synthetic/quarantine/foreign-owned.docx",
      objectVersionId: "provider-quarantine-version-synthetic",
      objectEtag: "provider-quarantine-etag-synthetic",
      sha256: digest(SOURCE),
      mimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const,
      sizeBytes: SOURCE.byteLength,
      created: true,
    };
    const nativeReceipt: TemplateTwinQuarantineReceipt = {
      id: "quarantine_owned_by_doctor_1",
      lineageId: "lineage_owned_by_doctor_1",
      lineageVersion: 1,
      intakeMode: "NATIVE_TEMPLATE",
      stored,
    };
    const completedReceipt: TemplateTwinQuarantineReceipt = {
      ...nativeReceipt,
      intakeMode: "COMPLETED_EXAMPLE",
    };
    const metadataEvidence = {
      profileVersion: TEMPLATE_TWIN_METADATA_PROFILE,
      originalSha256: digest(SOURCE),
      minimizedSha256: "a".repeat(64),
      replacedParts: [] as const,
      zipEntryTimestampsNormalized: true as const,
    };
    mocks.quarantineUpdateMany.mockImplementation(
      async (args: { where?: { createdById?: string } }) => ({
        count: args.where?.createdById === ACTOR.userId ? 1 : 0,
      }),
    );
    const scanner: TemplateTwinMalwareScanner = {
      scan: vi.fn().mockResolvedValue(scanEvidence("clean")),
    };
    const tx = {
      templateTwinQuarantineArtifact: {
        updateMany: mocks.quarantineUpdateMany,
      },
      templateTwinAuditOutbox: { create: mocks.outboxCreate },
    } as unknown as Prisma.TransactionClient;

    await expect(
      scanTemplateTwinQuarantine({
        source: SOURCE,
        receipt: nativeReceipt,
        actor: SAME_PRACTICE_FOREIGN_ACTOR,
        scanner,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
    });
    await expect(
      rejectTemplateTwinQuarantine({
        receipt: nativeReceipt,
        actor: SAME_PRACTICE_FOREIGN_ACTOR,
        rejectionCode: "SYNTHETIC_REJECTION",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
    });
    await expect(
      admitTemplateTwinQuarantine({
        tx,
        receipt: nativeReceipt,
        actor: SAME_PRACTICE_FOREIGN_ACTOR,
        sourceArtifactId: "source_artifact_synthetic",
        metadataEvidence,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
    });
    await expect(
      isolateCompletedExampleQuarantine({
        tx,
        receipt: completedReceipt,
        actor: SAME_PRACTICE_FOREIGN_ACTOR,
        candidateId: "candidate_synthetic",
        metadataEvidence,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
    });

    expect(mocks.quarantineUpdateMany).toHaveBeenCalledTimes(4);
    for (const [args] of mocks.quarantineUpdateMany.mock.calls) {
      expect(args.where).toMatchObject({
        practiceId: ACTOR.practiceId,
        createdById: SAME_PRACTICE_FOREIGN_ACTOR.userId,
      });
    }
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("terminally rejects an infected receipt and retains only a threat hash", async () => {
    const artifactStore = storage();
    const receipt = await beginTemplateTwinQuarantine({
      source: SOURCE,
      actor: ACTOR,
      intakeMode: "NATIVE_TEMPLATE",
      lineageId: "lineage_synthetic",
      storage: artifactStore.value,
    });
    vi.clearAllMocks();
    mocks.transaction.mockImplementation(
      async (callback: (client: unknown) => Promise<unknown>) =>
        callback({
          templateTwinQuarantineArtifact: {
            updateMany: mocks.quarantineUpdateMany,
          },
          templateTwinAuditOutbox: { create: mocks.outboxCreate },
        }),
    );
    mocks.quarantineUpdateMany.mockResolvedValue({ count: 1 });
    const evidence = scanEvidence("infected");
    const scanner: TemplateTwinMalwareScanner = {
      scan: vi.fn().mockResolvedValue(evidence),
    };

    await expect(
      scanTemplateTwinQuarantine({
        source: SOURCE,
        receipt,
        actor: ACTOR,
        scanner,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinMalwareRejectedError);
    expect(mocks.quarantineUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({ id: receipt.id, status: "QUARANTINED" }),
      data: expect.objectContaining({
        status: "REJECTED",
        malwareScanEvidence: evidence,
        rejectionCodes: ["TEMPLATE_TWIN_MALWARE_REJECTED"],
      }),
    });
    expect(JSON.stringify(mocks.outboxCreate.mock.calls)).not.toContain(
      "Synthetic-Test-Signature",
    );
  });

  it("stays quarantined when the scanner is unavailable", async () => {
    const artifactStore = storage();
    const receipt = await beginTemplateTwinQuarantine({
      source: SOURCE,
      actor: ACTOR,
      intakeMode: "COMPLETED_EXAMPLE",
      lineageId: "lineage_synthetic",
      storage: artifactStore.value,
    });
    vi.clearAllMocks();
    mocks.transaction.mockImplementation(
      async (callback: (client: unknown) => Promise<unknown>) =>
        callback({
          templateTwinQuarantineArtifact: {
            updateMany: mocks.quarantineUpdateMany,
          },
          templateTwinAuditOutbox: { create: mocks.outboxCreate },
        }),
    );
    mocks.quarantineUpdateMany.mockResolvedValue({ count: 1 });
    const scanner: TemplateTwinMalwareScanner = {
      scan: vi
        .fn()
        .mockRejectedValue(new TemplateTwinMalwareScanUnavailableError()),
    };

    await expect(
      scanTemplateTwinQuarantine({
        source: SOURCE,
        receipt,
        actor: ACTOR,
        scanner,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinMalwareScanUnavailableError);
    expect(mocks.quarantineUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({ id: receipt.id, status: "QUARANTINED" }),
      data: { rejectionCodes: ["TEMPLATE_TWIN_MALWARE_SCAN_UNAVAILABLE"] },
    });
  });
});
