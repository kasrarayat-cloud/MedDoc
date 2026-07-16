import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  freshDoctor: vi.fn(),
  findFirst: vi.fn(),
  assess: vi.fn(),
  readOutput: vi.fn(),
  enqueueAudit: vi.fn(),
  logDelivery: vi.fn(),
  pinRollout: vi.fn(),
  finalRollout: vi.fn(),
  transaction: vi.fn(),
  findFill: vi.fn(),
}));

vi.mock("next/server", () => {
  class FakeNextResponse {
    status: number;
    headers: Map<string, string>;
    private readonly body: unknown;

    constructor(
      body: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      this.body = body;
      this.status = init?.status ?? 200;
      this.headers = new Map(Object.entries(init?.headers ?? {}));
    }

    async json() {
      return this.body;
    }

    static json(body: unknown, init?: { status?: number }) {
      return new FakeNextResponse(body, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findFirst: mocks.findFirst },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: mocks.freshDoctor,
}));
vi.mock("@/lib/template-twin/signing-gate", () => ({
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT: {},
  assessTemplateTwinSigning: mocks.assess,
}));
vi.mock("@/lib/template-twin/storage/artifact-store", () => ({
  TemplateTwinArtifactIntegrityError: class TemplateTwinArtifactIntegrityError extends Error {},
  TemplateTwinStorageUnavailableError: class TemplateTwinStorageUnavailableError extends Error {},
  createTemplateTwinArtifactStore: () => ({
    readOutputArtifact: mocks.readOutput,
  }),
}));
vi.mock("@/lib/template-twin/storage/ownership", () => ({
  TemplateTwinArtifactNotFoundError: class TemplateTwinArtifactNotFoundError extends Error {},
}));
vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));
vi.mock("@/lib/template-twin/rollout", () => ({
  TemplateTwinRolloutError: class TemplateTwinRolloutError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  pinTemplateTwinRollout: mocks.pinRollout,
  lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  templateTwinRolloutAuditMetadata: () => ({
    pinnedGlobalGeneration: "1",
    pinnedPracticeGeneration: "1",
    currentGlobalGeneration: "1",
    currentPracticeGeneration: "1",
  }),
}));
vi.mock("@/lib/deliveries", () => ({ logDelivery: mocks.logDelivery }));
vi.mock("@/lib/log", () => ({
  log: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));

import type { NextRequest } from "next/server";
import { TranscribeVisitStatus } from "@prisma/client";
import { TemplateTwinArtifactIntegrityError } from "@/lib/template-twin/storage/artifact-store";
import { GET } from "../route";

const VISIT_ID = "synthetic-visit-1";
const OUTPUT_KEY =
  `practices/synthetic-practice-1/template-twin/outputs/${VISIT_ID}/` +
  `${"a".repeat(64)}/synthetic-artifact/${"b".repeat(64)}.docx`;

function call() {
  return GET({} as NextRequest, {
    params: Promise.resolve({ id: VISIT_ID }),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: {
      id: "synthetic-doctor-1",
      email: "doctor@synthetic.test",
    },
  });
  mocks.freshDoctor.mockResolvedValue({
    practiceId: "synthetic-practice-1",
    role: "DOCTOR",
  });
  mocks.findFirst.mockResolvedValue({
    id: VISIT_ID,
    status: TranscribeVisitStatus.SIGNED,
    soapFinal: "Synthetic note.",
    soapVersion: 2,
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    noteTemplate: { templateKind: "template_twin_docx" },
    templateTwinFill: {
      id: "synthetic-fill-1",
      outputObjectKey: OUTPUT_KEY,
      outputVersionId: "provider-output-version-synthetic",
      outputEtag: "provider-output-etag-synthetic",
      outputSha256: "b".repeat(64),
      outputSizeBytes: 128,
      pinnedGlobalRolloutGeneration: BigInt(1),
      pinnedPracticeRolloutGeneration: BigInt(1),
      signedGlobalRolloutGeneration: BigInt(1),
      signedPracticeRolloutGeneration: BigInt(1),
    },
  });
  mocks.assess.mockReturnValue({
    applies: true,
    ready: true,
    blockerCodes: [],
    compiledVersionId: "synthetic-compiled-1",
    fillManifestId: "synthetic-fill-1",
    claim: { id: "synthetic-fill-1" },
  });
  mocks.readOutput.mockResolvedValue(Buffer.from("synthetic DOCX bytes"));
  mocks.enqueueAudit.mockResolvedValue(undefined);
  mocks.pinRollout.mockResolvedValue({
    practiceId: "synthetic-practice-1",
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: {
      practiceId: "synthetic-practice-1",
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(1),
    },
  });
  mocks.findFill.mockResolvedValue({
    status: "SIGNED",
    signedDecisionAt: new Date("2026-07-15T12:00:00.000Z"),
    outputObjectKey: OUTPUT_KEY,
    outputVersionId: "provider-output-version-synthetic",
    outputEtag: "provider-output-etag-synthetic",
    outputSha256: "b".repeat(64),
    outputSizeBytes: 128,
    pinnedGlobalRolloutGeneration: BigInt(1),
    pinnedPracticeRolloutGeneration: BigInt(1),
    signedGlobalRolloutGeneration: BigInt(1),
    signedPracticeRolloutGeneration: BigInt(1),
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        templateTwinFillManifest: { findUnique: mocks.findFill },
      }),
  );
});

describe("Original Template DOCX export durable audit gate", () => {
  it("durably enqueues the export audit before returning verified bytes", async () => {
    const response = await call();

    expect(response.status).toBe(200);
    expect(mocks.readOutput).toHaveBeenCalledWith({
      practiceId: "synthetic-practice-1",
      objectKey: OUTPUT_KEY,
      expectedObjectVersionId: "provider-output-version-synthetic",
      expectedObjectEtag: "provider-output-etag-synthetic",
      expectedSha256: "b".repeat(64),
      expectedSizeBytes: 128,
    });
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        action: "EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED",
        targetId: VISIT_ID,
        practiceId: "synthetic-practice-1",
      }),
    );
    expect(mocks.logDelivery).toHaveBeenCalledTimes(1);
  });

  it("fails closed without recording a delivery when durable audit enqueue fails", async () => {
    mocks.enqueueAudit.mockRejectedValue(new Error("synthetic outbox outage"));

    const response = await call();

    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({
      code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE",
    });
    expect(mocks.logDelivery).not.toHaveBeenCalled();
  });

  it("durably records an unverified-output safety block", async () => {
    mocks.assess.mockReturnValue({
      applies: true,
      ready: false,
      blockerCodes: ["SOAP_BINDING_MISMATCH"],
      compiledVersionId: "synthetic-compiled-1",
      fillManifestId: "synthetic-fill-1",
      claim: null,
    });

    const response = await call();

    expect(response.status).toBe(409);
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        metadata: expect.objectContaining({
          reasonCode: "TEMPLATE_TWIN_OUTPUT_UNVERIFIED",
          blockerCodes: ["SOAP_BINDING_MISMATCH"],
        }),
      }),
    );
    expect(mocks.readOutput).not.toHaveBeenCalled();
  });

  it("blocks corrupted stored bytes and durably records the integrity reason", async () => {
    mocks.readOutput.mockRejectedValue(
      new TemplateTwinArtifactIntegrityError("synthetic corruption"),
    );

    const response = await call();

    expect(response.status).toBe(409);
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        metadata: expect.objectContaining({
          reasonCode: "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED",
        }),
      }),
    );
  });
});
