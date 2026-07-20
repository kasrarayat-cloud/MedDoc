import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  legacyVisitUpdateMany: vi.fn(),
  txVisitUpdateMany: vi.fn(),
  txFillUpdateMany: vi.fn(),
  txQueryRaw: vi.fn(),
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
  pinRollout: vi.fn(),
  finalRollout: vi.fn(),
  verifyEvidence: vi.fn(),
  authorizeDelivery: vi.fn(),
  logDelivery: vi.fn(),
  captureEditPattern: vi.fn(),
  computeDisplayedEmCode: vi.fn(),
  sendVisitPdfEmail: vi.fn(),
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
vi.mock("@meddoc/ai", () => ({
  redactPhi: (value: unknown) => value,
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION:
    "template-twin-staging-safe-docx/1.0.0",
}));
vi.mock("@/lib/visit-export", () => ({ formatVisitDate: () => "2026-07-15" }));
vi.mock("@/lib/visit-export-server", () => ({
  loadVisitExportData: mocks.loadVisitExportData,
}));
vi.mock("@/lib/ehr-formatters", () => ({ formatForEhr: () => "formatted" }));
vi.mock("@/lib/pdf-generator", () => ({
  generateVisitPdf: vi.fn(async () => Buffer.from("pdf")),
}));
vi.mock("@/lib/email", () => ({
  sendVisitPdfEmail: mocks.sendVisitPdfEmail,
}));
vi.mock("@/lib/deliveries", () => ({ logDelivery: mocks.logDelivery }));
vi.mock("@/lib/edit-tracking", () => ({
  captureEditPattern: mocks.captureEditPattern,
}));
vi.mock("@/lib/rx-warnings", () => ({
  criticalWarningRefs: mocks.criticalWarningRefs,
}));
vi.mock("@/lib/em-coding/displayed-level", () => ({
  computeDisplayedEmCode: mocks.computeDisplayedEmCode,
}));
vi.mock("@/lib/template-twin/signing-gate", () => ({
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT: {},
  assessTemplateTwinSigning: mocks.assess,
}));
vi.mock("@/lib/template-twin/delivery-authorization", () => ({
  TemplateTwinDeliveryAuthorizationError: class TemplateTwinDeliveryAuthorizationError extends Error {
    constructor(
      public readonly code: string,
      public readonly status: number,
    ) {
      super("Template Twin delivery authorization changed.");
    }
  },
  authorizeVisitDeliveryFinalClaim: mocks.authorizeDelivery,
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
vi.mock("@/worker/automation-finalization", () => ({
  assessVisitAutomationProof: () => ({ ready: true, blockerCodes: [] }),
  lockAndAssertVisitAutomationProof: vi.fn().mockResolvedValue({}),
  VisitAutomationIncompleteError: class VisitAutomationIncompleteError extends Error {},
}));
vi.mock("@/worker/automation-locks", () => ({
  runVisitAutomationTransaction: async (input: {
    transaction: (tx: unknown, visit: unknown) => Promise<unknown>;
  }) =>
    mocks.transaction((tx: unknown) =>
      input.transaction(tx, {
        id: "visit-1",
        userId: "doctor-1",
        status: "READY",
        soapVersion: 7,
        soapFinal: "Synthetic SOAP note.",
        reviewReason: null,
        deletedAt: null,
        archivedAt: null,
      }),
    ),
}));
vi.mock("@/lib/template-twin/fill-engine", () => ({
  lockCurrentTemplateTwinVisit: async (tx: {
    $queryRaw: () => Promise<unknown[]>;
  }) => (await tx.$queryRaw())[0] ?? null,
}));
vi.mock("@/lib/template-twin/encounter-evidence-verification", () => ({
  persistedTemplateTwinEncounterEvidenceIsValid: mocks.verifyEvidence,
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

import type { NextRequest } from "next/server";
import { TranscribeVisitStatus } from "@prisma/client";
import { AuthError } from "@/lib/auth";
import { TemplateTwinStorageUnavailableError } from "@/lib/template-twin/storage";
import { TemplateTwinDeliveryAuthorizationError } from "@/lib/template-twin/delivery-authorization";

import { POST } from "../route";

const VISIT_ID = "visit-1";
const CLAIM_UPDATED_AT = new Date("2026-07-15T12:00:00.000Z");

function visitRow(overrides: Record<string, unknown> = {}) {
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
    user: { practiceId: "practice-1" },
    automationManifest: null,
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
    ...overrides,
  };
}

function stagingRun() {
  const requestSha256 = "d".repeat(64);
  const payloadSha256 = "e".repeat(64);
  return {
    id: "staging-run-1",
    admissionId: "staging-admission-1",
    visitId: VISIT_ID,
    practiceId: "practice-1",
    doctorId: "doctor-1",
    noteTemplateId: "template-1",
    noteTemplateVersion: 1,
    requestSha256,
    payloadSha256,
    mode: "typed",
    status: "COMPLETED",
    fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
    attempt: 1,
    pinnedGlobalRolloutGeneration: BigInt(1),
    pinnedPracticeRolloutGeneration: BigInt(1),
    admission: {
      id: "staging-admission-1",
      practiceId: "practice-1",
      actorId: "doctor-1",
      parentAdmissionId: "staging-root-admission-1",
      sourceSha256:
        "9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4",
      sourceSizeBytes: 4_686,
      fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
      providerMode: "SYNTHETIC_TYPED",
      purpose: "VISIT",
      phase: "REVIEW_READY",
      requestSha256,
      payloadSha256,
      pinnedGlobalRolloutGeneration: BigInt(1),
      pinnedPracticeRolloutGeneration: BigInt(1),
      sourceArtifactId: "source-artifact-1",
      noteTemplateId: "template-1",
      noteTemplateVersion: 1,
      certificationId: "certification-1",
      mappingSha256: "f".repeat(64),
      visitId: VISIT_ID,
      attempt: 1,
      expiresAt: new Date("2099-07-15T12:00:00.000Z"),
      failedAt: null,
      revokedAt: null,
      consumedAt: null,
    },
  };
}

function call(
  destinations: string[] = [],
  headers: Record<string, string> = {
    origin: "https://app.example.test",
    host: "app.example.test",
    "sec-fetch-site": "same-origin",
  },
  emailTo?: string,
) {
  const request = new Request(
    `https://app.example.test/api/visits/${VISIT_ID}/sign`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...headers,
      },
      body: JSON.stringify({
        destinations,
        ...(emailTo !== undefined ? { emailTo } : {}),
      }),
    },
  ) as unknown as NextRequest;
  return POST(request, { params: Promise.resolve({ id: VISIT_ID }) });
}

function deterministicBarrier() {
  let signalEntered!: () => void;
  let release!: () => void;
  const entered = new Promise<void>((resolve) => {
    signalEntered = resolve;
  });
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  return {
    entered,
    release,
    async stop() {
      signalEntered();
      await released;
    },
  };
}

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.stubEnv("TEMPLATE_TWIN_STAGING_QA_ENABLED", "false");
  vi.clearAllMocks();
  for (const mock of [
    mocks.findUnique,
    mocks.transaction,
    mocks.txQueryRaw,
    mocks.txFillUpdateMany,
    mocks.txVisitUpdateMany,
    mocks.assess,
    mocks.finalRollout,
    mocks.enqueueAudit,
    mocks.verifyEvidence,
  ]) {
    mock.mockReset();
  }
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
  mocks.authorizeDelivery.mockResolvedValue({
    templateTwin: true,
    currentPhysicianEmail: "current-doctor@example.test",
  });
  mocks.computeDisplayedEmCode.mockResolvedValue("99213");
  mocks.sendVisitPdfEmail.mockResolvedValue({ id: "message-1" });
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
      providerOwnershipEvidence: { synthetic: "provider-receipt" },
      providerOwnershipSha256: "d".repeat(64),
      updatedAt: CLAIM_UPDATED_AT,
    },
  });
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.enqueueAudit.mockResolvedValue(undefined);
  mocks.verifyEvidence.mockReturnValue(true);
  mocks.pinRollout.mockResolvedValue({
    practiceId: "practice-1",
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: {
      practiceId: "practice-1",
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(1),
    },
  });
  mocks.txFillUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txVisitUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txQueryRaw
    .mockResolvedValueOnce([
      {
        id: "doctor-1",
        practiceId: "practice-1",
        role: "DOCTOR",
        isActive: true,
      },
    ])
    .mockResolvedValueOnce([
      { id: "doctor-1", email: "current-doctor@example.test" },
    ])
    .mockResolvedValue([
      {
        id: VISIT_ID,
        userId: "doctor-1",
        status: TranscribeVisitStatus.READY,
        deletedAt: null,
        archivedAt: null,
        soapVersion: 7,
        soapFinal: "Synthetic SOAP note.",
        noteTemplateId: "template-1",
        noteTemplateVersion: 1,
        inputMode: "text_notes",
      },
    ]);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        templateTwinFillManifest: {
          updateMany: mocks.txFillUpdateMany,
        },
        transcribeVisit: { updateMany: mocks.txVisitUpdateMany },
        templateTwinSyntheticQaAdmission: {
          updateMany: vi.fn().mockResolvedValue({ count: 1 }),
        },
        $queryRaw: mocks.txQueryRaw,
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
  it("rejects a cross-site Template Twin signing mutation before any clinical claim", async () => {
    const response = await call([], {
      origin: "https://cross-site.synthetic.test",
      host: "app.example.test",
      "sec-fetch-site": "cross-site",
    });

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_CROSS_SITE_MUTATION",
      retry: false,
    });
    expect(mocks.assess).not.toHaveBeenCalled();
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it.each(["email", "pdf", "docx", "clipboard_epic", "clipboard_generic"])(
    "blocks the %s destination for a synthetic QA visit",
    async (destination) => {
      for (const [key, value] of Object.entries({
        TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
        TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
        TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION:
          "isolated-disposable-qa-v1",
        TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
        MOCK_AI_CALLS: "true",
        MOCK_TEMPLATE_TWIN_E2E: "true",
        DATABASE_URL:
          "postgresql://synthetic:synthetic@localhost/template_twin_test",
        REDIS_URL: "redis://redis:6379/15",
        MINIO_ENDPOINT: "minio:9000",
        MINIO_USE_SSL: "false",
        TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
        TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
      })) {
        vi.stubEnv(key, value);
      }
      mocks.findUnique.mockReset();
      mocks.findUnique.mockResolvedValueOnce({
        ...visitRow(),
        templateTwinSyntheticQaRun: stagingRun(),
      });

      const response = await call([destination]);

      expect(response.status).toBe(403);
      await expect(response.json()).resolves.toMatchObject({
        code: "TEMPLATE_TWIN_STAGING_QA_DESTINATION_BLOCKED",
        retry: false,
      });
      expect(mocks.readTemplateTwinOutput).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
    },
  );

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
        cptCodes: { em: { code: "99213" } },
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
    expect(mocks.txVisitUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.computeDisplayedEmCode).toHaveBeenCalledTimes(1);
    expect(mocks.captureEditPattern).toHaveBeenCalledWith({
      visitId: VISIT_ID,
      doctorId: "doctor-1",
    });
  });

  it("never calls generic E/M or edit-pattern providers while signing a live Twin", async () => {
    mocks.findUnique.mockReset();
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ cptCodes: { em: { code: "99214" } } }))
      .mockResolvedValue({
        signedAt: new Date("2026-07-15T12:05:00.000Z"),
        status: TranscribeVisitStatus.SIGNED,
      });

    const response = await call();

    expect(response.status).toBe(200);
    expect(mocks.computeDisplayedEmCode).not.toHaveBeenCalled();
    expect(mocks.captureEditPattern).not.toHaveBeenCalled();
    expect(mocks.txVisitUpdateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          cptCodes: expect.objectContaining({
            em: expect.objectContaining({ signedCode: "99214" }),
          }),
        }),
      }),
    );
  });

  it("keeps fill-only durable Twin provenance out of ordinary sign providers", async () => {
    mocks.findUnique.mockReset();
    mocks.findUnique
      .mockResolvedValueOnce(
        visitRow({
          noteTemplate: { templateKind: "structured" },
          cptCodes: { em: { code: "99214" } },
        }),
      )
      .mockResolvedValue({
        signedAt: new Date("2026-07-15T12:05:00.000Z"),
        status: TranscribeVisitStatus.SIGNED,
      });
    mocks.assess.mockReturnValue({
      applies: true,
      ready: false,
      blockerCodes: ["TEMPLATE_PROVENANCE_UNAVAILABLE"],
      compiledVersionId: null,
      fillManifestId: "fill-1",
      claim: null,
    });

    const response = await call();

    expect(response.status).toBe(422);
    expect(mocks.freshDoctor).toHaveBeenCalledWith("doctor-1");
    expect(mocks.computeDisplayedEmCode).not.toHaveBeenCalled();
    expect(mocks.captureEditPattern).not.toHaveBeenCalled();
  });

  it("uses the newest locked physician email when it changes before Twin delivery", async () => {
    vi.stubEnv("RESEND_API_KEY", "synthetic-test-key");
    mocks.authorizeDelivery
      .mockResolvedValueOnce({
        templateTwin: true,
        currentPhysicianEmail: "before-update@example.test",
      })
      .mockResolvedValueOnce({
        templateTwin: true,
        currentPhysicianEmail: "after-update@example.test",
      });

    const response = await call(["email"]);

    expect(response.status).toBe(200);
    expect(mocks.authorizeDelivery).toHaveBeenLastCalledWith({
      visitId: VISIT_ID,
      actorUserId: "doctor-1",
      allowSyntheticOriginalTemplate: false,
      emailDelivery: {},
    });
    expect(mocks.sendVisitPdfEmail).toHaveBeenCalledWith(
      expect.objectContaining({ toEmail: "after-update@example.test" }),
    );
    expect(mocks.sendVisitPdfEmail).not.toHaveBeenCalledWith(
      expect.objectContaining({ toEmail: "doctor@example.test" }),
    );
  });

  it("rejects an explicit stale-session Twin email before the signed claim", async () => {
    vi.stubEnv("RESEND_API_KEY", "synthetic-test-key");

    const response = await call(
      ["email"],
      {
        origin: "https://app.example.test",
        host: "app.example.test",
        "sec-fetch-site": "same-origin",
      },
      "doctor@example.test",
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "INVALID_DESTINATION",
      retry: false,
    });
    expect(mocks.txFillUpdateMany).not.toHaveBeenCalled();
    expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.sendVisitPdfEmail).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        actorEmailSnapshot: "current-doctor@example.test",
        metadata: expect.objectContaining({
          reasonCode: "EMAIL_TARGET_MISMATCH",
        }),
      }),
    );
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
        providerOwnershipEvidence: {
          equals: { synthetic: "provider-receipt" },
        },
        providerOwnershipSha256: "d".repeat(64),
        roundTripVerified: true,
        needsReviewCount: 0,
        conflictCount: 0,
        criticalUnresolvedCount: 0,
        pinnedGlobalRolloutGeneration: BigInt(1),
        pinnedPracticeRolloutGeneration: BigInt(1),
        signedDecisionAt: null,
        updatedAt: CLAIM_UPDATED_AT,
      },
      data: {
        status: "SIGNED",
        signedDecisionAt: expect.any(Date),
        signedGlobalRolloutGeneration: BigInt(1),
        signedPracticeRolloutGeneration: BigInt(1),
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

  it("rechecks authorization before every destination and stops on revocation", async () => {
    mocks.authorizeDelivery
      .mockResolvedValueOnce({ templateTwin: true })
      .mockResolvedValueOnce({ templateTwin: true })
      .mockRejectedValueOnce(
        new TemplateTwinDeliveryAuthorizationError(
          "TEMPLATE_TWIN_DELIVERY_BLOCKED",
          409,
        ),
      );

    const response = await call(["clipboard_generic", "pdf"]);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
      retry: false,
    });
    expect(mocks.authorizeDelivery).toHaveBeenCalledTimes(3);
    expect(mocks.authorizeDelivery).toHaveBeenNthCalledWith(2, {
      visitId: VISIT_ID,
      actorUserId: "doctor-1",
      allowSyntheticOriginalTemplate: false,
    });
    expect(mocks.authorizeDelivery).toHaveBeenNthCalledWith(3, {
      visitId: VISIT_ID,
      actorUserId: "doctor-1",
      allowSyntheticOriginalTemplate: false,
    });
    expect(mocks.logDelivery).toHaveBeenCalledTimes(1);
    expect(mocks.logDelivery).toHaveBeenCalledWith(
      expect.objectContaining({ channel: "clipboard_generic" }),
    );
  });

  it("never returns a destination collaborator error verbatim", async () => {
    mocks.logDelivery.mockImplementationOnce(() => {
      throw new Error(
        "synthetic patient and provider receipt detail must not escape",
      );
    });

    const response = await call(["pdf"]);
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.deliveryErrors).toEqual({ pdf: "delivery failed" });
    expect(JSON.stringify(body)).not.toMatch(/patient|provider receipt/i);
  });

  it("blocks signing when encounter evidence changes before the final claim", async () => {
    mocks.verifyEvidence.mockReturnValue(false);
    mocks.findUnique.mockReset();
    mocks.findUnique.mockResolvedValueOnce(visitRow()).mockResolvedValue({
      signedAt: null,
      status: TranscribeVisitStatus.READY,
    });

    const response = await call([]);

    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({
      code: "TEMPLATE_TWIN_ENCOUNTER_EVIDENCE_STALE",
    });
    expect(mocks.txFillUpdateMany).not.toHaveBeenCalled();
    expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
  });

  it("rolls back both clinical transitions when durable audit enqueue fails", async () => {
    const clinicalState: {
      fillStatus: string;
      visitStatus: TranscribeVisitStatus;
    } = {
      fillStatus: "VERIFIED",
      visitStatus: TranscribeVisitStatus.READY,
    };
    mocks.txFillUpdateMany.mockImplementation(async () => {
      clinicalState.fillStatus = "SIGNED";
      return { count: 1 };
    });
    mocks.txVisitUpdateMany.mockImplementation(async () => {
      clinicalState.visitStatus = TranscribeVisitStatus.SIGNED;
      return { count: 1 };
    });
    mocks.enqueueAudit.mockImplementation(async (_tx, input) => {
      if ((input as { action?: string }).action === "VISIT_SIGNED") {
        throw new Error("synthetic transactional outbox failure");
      }
    });
    mocks.transaction.mockImplementation(async (callback) => {
      const before = { ...clinicalState };
      try {
        return await callback({
          templateTwinFillManifest: {
            updateMany: mocks.txFillUpdateMany,
          },
          transcribeVisit: { updateMany: mocks.txVisitUpdateMany },
          $queryRaw: mocks.txQueryRaw,
        });
      } catch (error) {
        Object.assign(clinicalState, before);
        throw error;
      }
    });

    const response = await call([]);

    expect(response.status).toBe(500);
    expect(clinicalState).toEqual({
      fillStatus: "VERIFIED",
      visitStatus: TranscribeVisitStatus.READY,
    });
    expect(mocks.txFillUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.txVisitUpdateMany).toHaveBeenCalledTimes(1);
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

  it("blocks a suspension race at the final signed claim", async () => {
    mocks.txQueryRaw
      .mockReset()
      .mockResolvedValueOnce([
        {
          id: "doctor-1",
          practiceId: "practice-1",
          role: "DOCTOR",
          isActive: true,
        },
      ])
      .mockResolvedValueOnce([]);

    const response = await call([]);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
      retry: false,
    });
    expect(mocks.txFillUpdateMany).not.toHaveBeenCalled();
    expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
  });

  it.each([
    [
      "practice",
      "TEMPLATE_TWIN_PRACTICE_DISABLED",
      "Template Twin was disabled for this practice.",
    ],
    [
      "global",
      "TEMPLATE_TWIN_GLOBAL_DISABLED",
      "Template Twin is temporarily unavailable.",
    ],
  ] as const)(
    "rejects the SIGNED transition when %s rollout is revoked after sign admission",
    async (_scope, code, reason) => {
      const barrier = deterministicBarrier();
      mocks.readTemplateTwinOutput.mockImplementation(async () => {
        await barrier.stop();
        return Buffer.from("synthetic verified DOCX bytes");
      });
      const operation = call([]);

      await barrier.entered;
      mocks.finalRollout.mockResolvedValue({
        allowed: false,
        code,
        reason,
        currentToken: {
          practiceId: "practice-1",
          globalGeneration: BigInt(2),
          practiceGeneration: BigInt(2),
        },
      });
      barrier.release();

      const response = await operation;
      expect(response.status).toBe(409);
      expect(await response.json()).toMatchObject({ code, retry: true });
      expect(mocks.txFillUpdateMany).not.toHaveBeenCalled();
      expect(mocks.txVisitUpdateMany).not.toHaveBeenCalled();
      expect(mocks.enqueueAudit).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          action: "TEMPLATE_TWIN_SIGN_BLOCKED",
          metadata: expect.objectContaining({
            reasonCode: code,
            operation: "sign_final_claim",
          }),
        }),
      );
    },
  );

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
