import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  legacyVisitUpdateMany: vi.fn(),
  txVisitUpdateMany: vi.fn(),
  txFillUpdateMany: vi.fn(),
  transaction: vi.fn(),
  rxOverrideFindMany: vi.fn(),
  auth: vi.fn(),
  freshDoctor: vi.fn(),
  readTemplateTwinOutput: vi.fn(),
  assess: vi.fn(),
  logAudit: vi.fn(),
  logWarn: vi.fn(),
  loadVisitExportData: vi.fn(),
  criticalWarningRefs: vi.fn(),
  enqueueAudit: vi.fn(),
}));

vi.mock("next/server", () => {
  class FakeNextResponse {
    status: number;
    headers = new Map<string, string>();
    private body: unknown;

    constructor(body: unknown, init?: { status?: number }) {
      this.body = body;
      this.status = init?.status ?? 200;
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

vi.mock("@meddoc/db", () => {
  const prisma = {
    transcribeVisit: {
      findUnique: mocks.findUnique,
      updateMany: mocks.legacyVisitUpdateMany,
    },
    rxWarningOverride: { findMany: mocks.rxOverrideFindMany },
    $transaction: mocks.transaction,
  };
  return { default: prisma, prisma };
});
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: "UNAUTHENTICATED" | "FORBIDDEN",
      message: string,
    ) {
      super(message);
    }
  },
  requireFreshDoctorIdentity: mocks.freshDoctor,
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/log", () => ({
  log: { warn: mocks.logWarn, info: vi.fn(), error: vi.fn() },
}));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));
vi.mock("@/lib/visit-export", () => ({ formatVisitDate: () => "2026-07-15" }));
vi.mock("@/lib/visit-export-server", () => ({
  loadVisitExportData: mocks.loadVisitExportData,
}));
vi.mock("@/lib/ehr-formatters", () => ({ formatForEhr: () => "formatted" }));
vi.mock("@/lib/pdf-generator", () => ({
  generateVisitPdf: vi.fn(async () => Buffer.from("pdf")),
}));
vi.mock("@/lib/email", () => ({ sendVisitPdfEmail: vi.fn() }));
vi.mock("@/lib/deliveries", () => ({ logDelivery: vi.fn() }));
vi.mock("@/lib/edit-tracking", () => ({ captureEditPattern: vi.fn() }));
vi.mock("@/lib/rx-warnings", () => ({
  criticalWarningRefs: mocks.criticalWarningRefs,
}));
vi.mock("@/lib/em-coding/displayed-level", () => ({
  computeDisplayedEmCode: vi.fn(),
}));
vi.mock("@/lib/template-twin/signing-gate", () => ({
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT: {},
  assessTemplateTwinSigning: mocks.assess,
}));
vi.mock("@/lib/template-twin/storage", () => ({
  TemplateTwinStorageUnavailableError: class TemplateTwinStorageUnavailableError extends Error {},
  createTemplateTwinArtifactStore: () => ({
    readOutputArtifact: mocks.readTemplateTwinOutput,
  }),
}));
vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));

import type { NextRequest } from "next/server";
import { TranscribeVisitStatus } from "@prisma/client";
import { AuthError } from "@/lib/auth";
import { TemplateTwinStorageUnavailableError } from "@/lib/template-twin/storage";

import { POST } from "../route";

const VISIT_ID = "visit-1";
const CLAIM_UPDATED_AT = new Date("2026-07-15T12:00:00.000Z");

function visitRow() {
  return {
    id: VISIT_ID,
    userId: "doctor-1",
    status: TranscribeVisitStatus.READY,
    soapFinal: "Synthetic SOAP note.",
    soapVersion: 7,
    icdCodes: null,
    rxDrafts: null,
    cptCodes: null,
    signedAt: null,
    deletedAt: null,
    archivedAt: null,
    emPendingChange: null,
    noteTemplateId: "template-1",
    noteTemplateVersion: 1,
    noteTemplate: { templateKind: "template_twin_docx" },
    templateTwinFill: {
      id: "fill-1",
      outputObjectKey:
        `practices/practice-1/template-twin/outputs/${VISIT_ID}/` +
        `${"a".repeat(64)}/artifact-1/${"b".repeat(64)}.docx`,
      outputVersionId: "provider-output-version-synthetic",
      outputEtag: "provider-output-etag-synthetic",
      outputSha256: "b".repeat(64),
      outputSizeBytes: 4096,
    },
  };
}

function call(destinations: string[] = []) {
  const request = {
    json: async () => ({ destinations }),
  } as unknown as NextRequest;
  return POST(request, { params: Promise.resolve({ id: VISIT_ID }) });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: {
      id: "doctor-1",
      email: "doctor@example.test",
      practiceId: "practice-1",
    },
  });
  mocks.freshDoctor.mockResolvedValue({
    role: "DOCTOR",
    practiceId: "practice-1",
  });
  mocks.readTemplateTwinOutput.mockResolvedValue(
    Buffer.from("synthetic verified DOCX bytes"),
  );
  mocks.findUnique.mockResolvedValueOnce(visitRow()).mockResolvedValue({
    signedAt: new Date("2026-07-15T12:05:00.000Z"),
    status: TranscribeVisitStatus.SIGNED,
  });
  mocks.assess.mockReturnValue({
    applies: true,
    ready: true,
    blockerCodes: [],
    compiledVersionId: "compiled-1",
    fillManifestId: "fill-1",
    claim: {
      id: "fill-1",
      manifestVersion: 3,
      manifestSha256: "a".repeat(64),
      reviewedAt: new Date("2026-07-15T12:03:00.000Z"),
      reviewedById: "doctor-1",
      soapVersion: 7,
      soapSha256: "c".repeat(64),
      outputObjectKey:
        `practices/practice-1/template-twin/outputs/${VISIT_ID}/` +
        `${"a".repeat(64)}/artifact-1/${"b".repeat(64)}.docx`,
      outputVersionId: "provider-output-version-synthetic",
      outputEtag: "provider-output-etag-synthetic",
      outputSha256: "b".repeat(64),
      outputSizeBytes: 4096,
      updatedAt: CLAIM_UPDATED_AT,
    },
  });
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.enqueueAudit.mockResolvedValue(undefined);
  mocks.txFillUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txVisitUpdateMany.mockResolvedValue({ count: 1 });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        templateTwinFillManifest: {
          updateMany: mocks.txFillUpdateMany,
        },
        transcribeVisit: { updateMany: mocks.txVisitUpdateMany },
      }),
  );
  mocks.loadVisitExportData.mockResolvedValue({
    clinicianName: "Synthetic clinician",
    patientName: "Synthetic patient",
    signedAt: new Date("2026-07-15T12:05:00.000Z"),
    createdAt: new Date("2026-07-15T11:00:00.000Z"),
  });
});

describe("POST /api/visits/[id]/sign — Template Twin server gate", () => {
  it.each(["STAFF", "ADMIN"] as const)(
    "rejects a fresh %s role before assessing or signing a Template Twin visit",
    async (role) => {
      mocks.freshDoctor.mockRejectedValue(
        new AuthError("FORBIDDEN", `Synthetic ${role} is not a physician.`),
      );

      const response = await call();

      expect(response.status).toBe(403);
      expect(mocks.freshDoctor).toHaveBeenCalledWith("doctor-1");
      expect(mocks.assess).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.legacyVisitUpdateMany).not.toHaveBeenCalled();
    },
  );

  it("keeps legacy non-Template-Twin signing outside the fresh role gate", async () => {
    mocks.findUnique.mockReset();
    mocks.findUnique
      .mockResolvedValueOnce({
        ...visitRow(),
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: null,
      })
      .mockResolvedValue({
        signedAt: new Date("2026-07-15T12:05:00.000Z"),
        status: TranscribeVisitStatus.SIGNED,
      });
    mocks.assess.mockReturnValue({
      applies: false,
      ready: true,
      blockerCodes: [],
      compiledVersionId: null,
      fillManifestId: null,
      claim: null,
    });
    mocks.legacyVisitUpdateMany.mockResolvedValue({ count: 1 });

    const response = await call();

    expect(response.status).toBe(200);
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
    expect(mocks.legacyVisitUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("blocks the transition and emits only PHI-safe blocker codes", async () => {
    mocks.assess.mockReturnValue({
      applies: true,
      ready: false,
      blockerCodes: ["CRITICAL_FIELDS_UNRESOLVED", "ROUND_TRIP_UNVERIFIED"],
      compiledVersionId: "compiled-1",
      fillManifestId: "fill-1",
      claim: null,
    });

    const response = await call();

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({
      ok: false,
      error:
        "Review the unresolved Template Twin fields and regenerate the verified document before signing.",
      code: "TEMPLATE_TWIN_SIGN_BLOCKED",
      blockerCodes: ["CRITICAL_FIELDS_UNRESOLVED", "ROUND_TRIP_UNVERIFIED"],
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.legacyVisitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        action: "TEMPLATE_TWIN_SIGN_BLOCKED",
        metadata: expect.objectContaining({
          blockerCodes: ["CRITICAL_FIELDS_UNRESOLVED", "ROUND_TRIP_UNVERIFIED"],
        }),
      }),
    );
  });

  it("returns a physician-readable regeneration reason for a stale SOAP binding", async () => {
    mocks.assess.mockReturnValue({
      applies: true,
      ready: false,
      blockerCodes: ["SOAP_BINDING_MISMATCH"],
      compiledVersionId: "compiled-1",
      fillManifestId: "fill-1",
      claim: null,
    });

    const response = await call([]);

    expect(response.status).toBe(422);
    expect(await response.json()).toMatchObject({
      code: "TEMPLATE_TWIN_SIGN_BLOCKED",
      blockerCodes: ["SOAP_BINDING_MISMATCH"],
      error:
        "The SOAP note changed after the Original Template DOCX was generated. Regenerate and review the document before signing.",
    });
    expect(mocks.readTemplateTwinOutput).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("atomically claims the exact verified manifest and signs the visit", async () => {
    const response = await call(["docx_original_template"]);

    expect(response.status).toBe(200);
    expect(mocks.readTemplateTwinOutput).toHaveBeenCalledWith({
      practiceId: "practice-1",
      objectKey:
        `practices/practice-1/template-twin/outputs/${VISIT_ID}/` +
        `${"a".repeat(64)}/artifact-1/${"b".repeat(64)}.docx`,
      expectedObjectVersionId: "provider-output-version-synthetic",
      expectedObjectEtag: "provider-output-etag-synthetic",
      expectedSha256: "b".repeat(64),
      expectedSizeBytes: 4096,
    });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.txFillUpdateMany).toHaveBeenCalledWith({
      where: {
        id: "fill-1",
        practice: {
          is: {
            id: "practice-1",
            templateTwinEnabled: true,
          },
        },
        status: "VERIFIED",
        manifestVersion: 3,
        manifestSha256: "a".repeat(64),
        reviewedAt: new Date("2026-07-15T12:03:00.000Z"),
        reviewedById: "doctor-1",
        reviewedManifestVersion: 3,
        reviewedManifestSha256: "a".repeat(64),
        outputObjectKey:
          `practices/practice-1/template-twin/outputs/${VISIT_ID}/` +
          `${"a".repeat(64)}/artifact-1/${"b".repeat(64)}.docx`,
        outputVersionId: "provider-output-version-synthetic",
        outputEtag: "provider-output-etag-synthetic",
        outputSha256: "b".repeat(64),
        outputSizeBytes: 4096,
        roundTripVerified: true,
        needsReviewCount: 0,
        conflictCount: 0,
        criticalUnresolvedCount: 0,
        signedDecisionAt: null,
        updatedAt: CLAIM_UPDATED_AT,
      },
      data: {
        status: "SIGNED",
        signedDecisionAt: expect.any(Date),
      },
    });
    expect(mocks.txVisitUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: VISIT_ID,
          status: TranscribeVisitStatus.READY,
          soapVersion: 7,
          soapFinal: "Synthetic SOAP note.",
        },
        data: expect.objectContaining({
          status: TranscribeVisitStatus.SIGNED,
          signedAt: expect.any(Date),
        }),
      }),
    );
    expect(mocks.legacyVisitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        action: "VISIT_SIGNED",
        targetId: VISIT_ID,
        metadata: expect.objectContaining({
          manifestVersion: 3,
          soapVersion: 7,
          soapSha256: "c".repeat(64),
        }),
      }),
    );
    expect((await response.json()).originalTemplateDocxDownloadUrl).toBe(
      `/api/visits/${VISIT_ID}/export/original-template-docx`,
    );
  });

  it("reads and verifies stored bytes before signing when no destination is selected", async () => {
    const response = await call([]);

    expect(response.status).toBe(200);
    expect(mocks.readTemplateTwinOutput).toHaveBeenCalledWith({
      practiceId: "practice-1",
      objectKey:
        `practices/practice-1/template-twin/outputs/${VISIT_ID}/` +
        `${"a".repeat(64)}/artifact-1/${"b".repeat(64)}.docx`,
      expectedObjectVersionId: "provider-output-version-synthetic",
      expectedObjectEtag: "provider-output-etag-synthetic",
      expectedSha256: "b".repeat(64),
      expectedSizeBytes: 4096,
    });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["unavailable", new TemplateTwinStorageUnavailableError(), 503],
    ["integrity failure", new Error("synthetic digest mismatch"), 409],
  ] as const)(
    "does not sign when exact-output delivery preflight reports %s",
    async (_label, failure, status) => {
      mocks.readTemplateTwinOutput.mockRejectedValue(failure);

      const response = await call([]);

      expect(response.status).toBe(status);
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.legacyVisitUpdateMany).not.toHaveBeenCalled();
      expect(mocks.enqueueAudit).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          action: "TEMPLATE_TWIN_SIGN_BLOCKED",
        }),
      );
    },
  );

  it.each(["missing", "corrupt", "truncated", "replaced"])(
    "does not sign when the stored object is %s",
    async (failureMode) => {
      mocks.readTemplateTwinOutput.mockRejectedValue(
        new Error(`synthetic ${failureMode} stored object`),
      );

      const response = await call([]);

      expect(response.status).toBe(409);
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.txFillUpdateMany).not.toHaveBeenCalled();
      expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
    },
  );

  it("loses closed when the manifest changes between assessment and claim", async () => {
    mocks.txFillUpdateMany.mockResolvedValue({ count: 0 });
    mocks.findUnique.mockReset();
    mocks.findUnique.mockResolvedValueOnce(visitRow()).mockResolvedValue({
      signedAt: null,
      status: TranscribeVisitStatus.READY,
    });

    const response = await call();

    expect(response.status).toBe(409);
    expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.legacyVisitUpdateMany).not.toHaveBeenCalled();
  });

  it("loses closed when the provider object identity is replaced after exact-byte verification", async () => {
    mocks.txFillUpdateMany.mockResolvedValue({ count: 0 });
    mocks.findUnique.mockReset();
    mocks.findUnique.mockResolvedValueOnce(visitRow()).mockResolvedValue({
      signedAt: null,
      status: TranscribeVisitStatus.READY,
    });

    const response = await call();

    expect(mocks.readTemplateTwinOutput).toHaveBeenCalledWith(
      expect.objectContaining({
        expectedObjectVersionId: "provider-output-version-synthetic",
        expectedObjectEtag: "provider-output-etag-synthetic",
      }),
    );
    expect(mocks.txFillUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          outputVersionId: "provider-output-version-synthetic",
          outputEtag: "provider-output-etag-synthetic",
        }),
      }),
    );
    expect(response.status).toBe(409);
    expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
  });
});
