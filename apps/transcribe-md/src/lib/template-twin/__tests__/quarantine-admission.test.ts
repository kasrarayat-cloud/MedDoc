import { createHash } from "node:crypto";

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  quarantineCreate: vi.fn(),
  quarantineUpdateMany: vi.fn(),
  ledgerUpdateMany: vi.fn(),
  ledgerFindUnique: vi.fn(),
  outboxCreate: vi.fn(),
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

import {
  beginTemplateTwinQuarantine,
  scanTemplateTwinQuarantine,
} from "../quarantine-admission";
import {
  TemplateTwinMalwareRejectedError,
  TemplateTwinMalwareScanUnavailableError,
  TEMPLATE_TWIN_MALWARE_SCAN_PROFILE,
  type TemplateTwinMalwareScanEvidence,
  type TemplateTwinMalwareScanner,
} from "../malware-scan";
import type { TemplateTwinArtifactStore } from "../storage";

const SOURCE = Buffer.from("synthetic raw DOCX intake bytes", "utf8");
const ACTOR = {
  userId: "doctor_synthetic_1",
  userEmail: "doctor@synthetic.test",
  practiceId: "practice_synthetic_1",
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
        metadata: expect.objectContaining({ verdict: "clean" }),
      }),
    });
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
