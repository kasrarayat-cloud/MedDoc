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
  findCurrentVisit: vi.fn(),
  queryRaw: vi.fn(),
  verifyEvidence: vi.fn(),
  lockVisit: vi.fn(),
  requireRead: vi.fn(),
  requireSyntheticRead: vi.fn(),
  assertStagingRun: vi.fn(),
  lockStagingRun: vi.fn(),
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
vi.mock("@/worker/automation-finalization", () => ({
  assessVisitAutomationProof: () => ({ ready: true, blockerCodes: [] }),
  lockAndAssertVisitAutomationProof: vi.fn().mockResolvedValue({}),
  VisitAutomationIncompleteError: class VisitAutomationIncompleteError extends Error {},
}));
vi.mock("@/lib/template-twin/fill-engine", () => ({
  lockCurrentTemplateTwinVisit: mocks.lockVisit,
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
vi.mock("@/lib/template-twin/read-authority", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/lib/template-twin/read-authority")
  >()),
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));
vi.mock(
  "@/lib/template-twin/synthetic-read-admission",
  async (importOriginal) => ({
    ...(await importOriginal<
      typeof import("@/lib/template-twin/synthetic-read-admission")
    >()),
    requireTemplateTwinSyntheticReadAdmission: mocks.requireSyntheticRead,
  }),
);
vi.mock(
  "@/lib/template-twin/staging-qa-visit-guard",
  async (importOriginal) => ({
    ...(await importOriginal<
      typeof import("@/lib/template-twin/staging-qa-visit-guard")
    >()),
    assertTemplateTwinStagingQaVisitGuard: mocks.assertStagingRun,
    lockAndAssertTemplateTwinStagingQaOperation: mocks.lockStagingRun,
  }),
);
vi.mock("@/lib/deliveries", () => ({ logDelivery: mocks.logDelivery }));
vi.mock("@/lib/log", () => ({
  log: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));

import type { NextRequest } from "next/server";
import { TranscribeVisitStatus } from "@prisma/client";
import { TemplateTwinArtifactIntegrityError } from "@/lib/template-twin/storage/artifact-store";
import { TemplateTwinSyntheticReadAdmissionError } from "@/lib/template-twin/synthetic-read-admission";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { GET } from "../route";

const VISIT_ID = "synthetic-visit-1";
const OUTPUT_KEY =
  `practices/synthetic-practice-1/template-twin/outputs/${VISIT_ID}/` +
  `${"a".repeat(64)}/synthetic-artifact/${"b".repeat(64)}.docx`;
const SYNTHETIC_INPUT = "Synthetic encounter source.";

function lockedVisitRow(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: "synthetic-doctor-1",
    patientId: "synthetic-patient-1",
    status: "SIGNED",
    soapVersion: 2,
    soapFinal: "Synthetic note.",
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    inputMode: "text_notes",
    rawTextInput: SYNTHETIC_INPUT,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
    deletedAt: null,
    archivedAt: null,
    ...overrides,
  };
}

function finalFillRow(overrides: Record<string, unknown> = {}) {
  return {
    practiceId: "synthetic-practice-1",
    visitId: VISIT_ID,
    compiledVersionId: "synthetic-compiled-1",
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    status: "SIGNED",
    signedDecisionAt: new Date("2026-07-15T12:00:00.000Z"),
    outputObjectKey: OUTPUT_KEY,
    outputVersionId: "provider-output-version-synthetic",
    outputEtag: "provider-output-etag-synthetic",
    outputSha256: "b".repeat(64),
    outputSizeBytes: 128,
    providerOwnershipEvidence: { synthetic: "provider-receipt" },
    providerOwnershipSha256: "c".repeat(64),
    pinnedGlobalRolloutGeneration: BigInt(1),
    pinnedPracticeRolloutGeneration: BigInt(1),
    signedGlobalRolloutGeneration: BigInt(1),
    signedPracticeRolloutGeneration: BigInt(1),
    ...overrides,
  };
}

function syntheticRunRow(overrides: Record<string, unknown> = {}) {
  const admission = {
    id: "synthetic-admission-1",
    practiceId: "synthetic-practice-1",
    actorId: "synthetic-doctor-1",
    parentAdmissionId: "synthetic-upload-admission-1",
    sourceSha256: "d".repeat(64),
    sourceSizeBytes: 256,
    fixtureVersion: "synthetic-fixture-v1",
    providerMode: "SYNTHETIC_TYPED",
    purpose: "VISIT",
    phase: "SIGNED",
    requestSha256: "e".repeat(64),
    payloadSha256: "f".repeat(64),
    pinnedGlobalRolloutGeneration: BigInt(1),
    pinnedPracticeRolloutGeneration: BigInt(1),
    sourceArtifactId: "synthetic-source-1",
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    certificationId: "synthetic-certification-1",
    mappingSha256: "1".repeat(64),
    visitId: VISIT_ID,
    attempt: 2,
  };
  return {
    id: "synthetic-run-1",
    admissionId: admission.id,
    visitId: VISIT_ID,
    practiceId: "synthetic-practice-1",
    doctorId: "synthetic-doctor-1",
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    requestSha256: admission.requestSha256,
    payloadSha256: admission.payloadSha256,
    mode: "typed",
    status: "COMPLETED",
    fixtureVersion: admission.fixtureVersion,
    attempt: admission.attempt,
    pinnedGlobalRolloutGeneration: BigInt(1),
    pinnedPracticeRolloutGeneration: BigInt(1),
    admission,
    ...overrides,
  };
}

function syntheticSigningVisitRow(run: ReturnType<typeof syntheticRunRow>) {
  return {
    id: VISIT_ID,
    patientId: "synthetic-patient-1",
    status: TranscribeVisitStatus.SIGNED,
    soapFinal: "Synthetic note.",
    soapVersion: 2,
    manualRetryCount: 0,
    inputMode: "text_notes",
    rawTextInput: SYNTHETIC_INPUT,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
    automationManifest: null,
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    noteTemplate: { templateKind: "template_twin_docx" },
    templateTwinSyntheticQaRun: run,
    templateTwinFill: {
      id: "synthetic-fill-1",
      practiceId: "synthetic-practice-1",
      visitId: VISIT_ID,
      compiledVersionId: "synthetic-compiled-1",
      noteTemplateId: "synthetic-template-1",
      noteTemplateVersion: 3,
      outputObjectKey: OUTPUT_KEY,
      outputVersionId: "provider-output-version-synthetic",
      outputEtag: "provider-output-etag-synthetic",
      outputSha256: "b".repeat(64),
      outputSizeBytes: 128,
      providerOwnershipEvidence: { synthetic: "provider-receipt" },
      providerOwnershipSha256: "c".repeat(64),
      pinnedGlobalRolloutGeneration: BigInt(1),
      pinnedPracticeRolloutGeneration: BigInt(1),
      signedGlobalRolloutGeneration: BigInt(1),
      signedPracticeRolloutGeneration: BigInt(1),
    },
  };
}

function configureSyntheticDownload(
  lockedRun: ReturnType<typeof syntheticRunRow>,
) {
  const initialRun = syntheticRunRow();
  const decision = {
    visitId: VISIT_ID,
    isTemplateTwin: true,
    isSyntheticTemplateTwin: true,
    practiceId: "synthetic-practice-1",
    templateTwinEnabled: true,
  };
  const admission = {
    visitId: VISIT_ID,
    practiceId: "synthetic-practice-1",
    runId: "synthetic-run-1",
    attempt: 2,
  };
  mocks.requireRead.mockResolvedValue(decision);
  mocks.requireSyntheticRead.mockResolvedValue(admission);
  mocks.assertStagingRun.mockReturnValue({
    applies: true,
    runId: admission.runId,
  });
  mocks.lockStagingRun.mockResolvedValue(lockedRun);
  mocks.findFirst.mockResolvedValue(syntheticSigningVisitRow(initialRun));
  return { admission, decision, initialRun };
}

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
  mocks.requireRead.mockResolvedValue({
    visitId: VISIT_ID,
    isTemplateTwin: true,
    isSyntheticTemplateTwin: false,
    practiceId: "synthetic-practice-1",
    templateTwinEnabled: true,
  });
  mocks.requireSyntheticRead.mockResolvedValue(null);
  mocks.assertStagingRun.mockReturnValue({ applies: false });
  mocks.lockStagingRun.mockResolvedValue(undefined);
  mocks.findFirst.mockResolvedValue({
    id: VISIT_ID,
    patientId: "synthetic-patient-1",
    status: TranscribeVisitStatus.SIGNED,
    soapFinal: "Synthetic note.",
    soapVersion: 2,
    manualRetryCount: 0,
    inputMode: "text_notes",
    rawTextInput: SYNTHETIC_INPUT,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
    automationManifest: null,
    noteTemplateId: "synthetic-template-1",
    noteTemplateVersion: 3,
    noteTemplate: { templateKind: "template_twin_docx" },
    templateTwinFill: {
      id: "synthetic-fill-1",
      practiceId: "synthetic-practice-1",
      visitId: VISIT_ID,
      compiledVersionId: "synthetic-compiled-1",
      noteTemplateId: "synthetic-template-1",
      noteTemplateVersion: 3,
      outputObjectKey: OUTPUT_KEY,
      outputVersionId: "provider-output-version-synthetic",
      outputEtag: "provider-output-etag-synthetic",
      outputSha256: "b".repeat(64),
      outputSizeBytes: 128,
      providerOwnershipEvidence: { synthetic: "provider-receipt" },
      providerOwnershipSha256: "c".repeat(64),
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
  mocks.findFill.mockResolvedValue(finalFillRow());
  mocks.findCurrentVisit.mockResolvedValue({ manualRetryCount: 0 });
  mocks.lockVisit.mockResolvedValue(lockedVisitRow());
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        templateTwinFillManifest: { findUnique: mocks.findFill },
        transcribeVisit: { findUnique: mocks.findCurrentVisit },
        $queryRaw: mocks.queryRaw,
      }),
  );
  mocks.queryRaw
    .mockReset()
    .mockImplementation(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join(" ") ?? "";
      if (sql.includes('FROM "transcribe_md_patients" patient')) {
        return [
          {
            id: "synthetic-patient-1",
            practiceId: "synthetic-practice-1",
          },
        ];
      }
      return [
        {
          id: "synthetic-doctor-1",
          email: "doctor@synthetic.test",
        },
      ];
    });
  mocks.verifyEvidence.mockReturnValue(true);
});

describe("Original Template DOCX export durable audit gate", () => {
  it.each(["admission-only", "pre-certification", "reserved-patient orphan"])(
    "denies a %s synthetic visit before clinical projection",
    async () => {
      mocks.requireRead.mockResolvedValue({
        visitId: VISIT_ID,
        isTemplateTwin: true,
        isSyntheticTemplateTwin: true,
        practiceId: "synthetic-practice-1",
        templateTwinEnabled: true,
      });
      mocks.requireSyntheticRead.mockRejectedValue(
        new TemplateTwinSyntheticReadAdmissionError(),
      );

      const response = await call();

      expect(response.status).toBe(404);
      expect(mocks.findFirst).not.toHaveBeenCalled();
      expect(mocks.readOutput).not.toHaveBeenCalled();
    },
  );

  it("denies an ordinary visit before any clinical SELECT", async () => {
    mocks.requireRead.mockResolvedValue({
      visitId: VISIT_ID,
      isTemplateTwin: false,
      isSyntheticTemplateTwin: false,
      practiceId: null,
      templateTwinEnabled: null,
    });
    const response = await call();

    expect(response.status).toBe(404);
    expect(mocks.findFirst).not.toHaveBeenCalled();
    expect(mocks.readOutput).not.toHaveBeenCalled();
  });

  it("preserves a fully admitted synthetic original-template download", async () => {
    const run = syntheticRunRow();
    const decision = {
      visitId: VISIT_ID,
      isTemplateTwin: true,
      isSyntheticTemplateTwin: true,
      practiceId: "synthetic-practice-1",
      templateTwinEnabled: true,
    };
    const admission = {
      visitId: VISIT_ID,
      practiceId: "synthetic-practice-1",
      runId: "synthetic-run-1",
      attempt: 2,
    };
    mocks.requireRead.mockResolvedValue(decision);
    mocks.requireSyntheticRead.mockResolvedValue(admission);
    mocks.assertStagingRun.mockReturnValue({
      applies: true,
      runId: admission.runId,
    });
    mocks.lockStagingRun.mockResolvedValue(run);
    mocks.findFirst.mockResolvedValue({
      id: VISIT_ID,
      patientId: "synthetic-patient-1",
      status: TranscribeVisitStatus.SIGNED,
      soapFinal: "Synthetic note.",
      soapVersion: 2,
      manualRetryCount: 0,
      inputMode: "text_notes",
      rawTextInput: SYNTHETIC_INPUT,
      transcriptText: null,
      transcriptRaw: null,
      speakerMap: null,
      automationManifest: null,
      noteTemplateId: "synthetic-template-1",
      noteTemplateVersion: 3,
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinSyntheticQaRun: run,
      templateTwinFill: {
        id: "synthetic-fill-1",
        practiceId: "synthetic-practice-1",
        visitId: VISIT_ID,
        compiledVersionId: "synthetic-compiled-1",
        noteTemplateId: "synthetic-template-1",
        noteTemplateVersion: 3,
        outputObjectKey: OUTPUT_KEY,
        outputVersionId: "provider-output-version-synthetic",
        outputEtag: "provider-output-etag-synthetic",
        outputSha256: "b".repeat(64),
        outputSizeBytes: 128,
        providerOwnershipEvidence: { synthetic: "provider-receipt" },
        providerOwnershipSha256: "c".repeat(64),
        pinnedGlobalRolloutGeneration: BigInt(1),
        pinnedPracticeRolloutGeneration: BigInt(1),
        signedGlobalRolloutGeneration: BigInt(1),
        signedPracticeRolloutGeneration: BigInt(1),
      },
    });

    const response = await call();

    expect(response.status).toBe(200);
    const where = mocks.findFirst.mock.calls[0]?.[0]?.where;
    expect(where?.AND).toContainEqual(
      currentClinicalVisitActorWhere("synthetic-doctor-1"),
    );
    expect(where?.AND).toContainEqual({
      patient: { is: { practiceId: "synthetic-practice-1" } },
    });
    expect(mocks.requireSyntheticRead).toHaveBeenNthCalledWith(2, {
      visitId: VISIT_ID,
      actorUserId: "synthetic-doctor-1",
      readDecision: decision,
      expected: admission,
    });
    expect(mocks.lockStagingRun).toHaveBeenCalledWith(
      expect.objectContaining({
        runId: admission.runId,
        expectedAdmissionId: "synthetic-admission-1",
        expectedAttempt: admission.attempt,
        allowedAdmissionPhases: ["SIGNED"],
      }),
    );
  });

  it.each([
    ["template identifier", { noteTemplateId: "synthetic-template-replaced" }],
    ["template version", { noteTemplateVersion: 4 }],
    [
      "encounter input identity",
      { rawTextInput: `${SYNTHETIC_INPUT} Changed after assessment.` },
    ],
  ])(
    "blocks a changed visit %s at the final claim",
    async (_label, lockedVisitChange) => {
      mocks.lockVisit.mockResolvedValue(
        lockedVisitRow(lockedVisitChange as Record<string, unknown>),
      );

      const response = await call();

      expect(response.status).toBe(409);
      await expect(response.json()).resolves.toMatchObject({
        code: "VISIT_AUTOMATION_PROOF_STALE",
      });
      expect(mocks.enqueueAudit).not.toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          action: "EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED",
        }),
      );
      expect(mocks.logDelivery).not.toHaveBeenCalled();
    },
  );

  it.each([
    ["practice", { practiceId: "synthetic-practice-replaced" }],
    ["visit", { visitId: "synthetic-visit-replaced" }],
    ["compiled version", { compiledVersionId: "synthetic-compiled-replaced" }],
    ["template identifier", { noteTemplateId: "synthetic-template-replaced" }],
    ["template version", { noteTemplateVersion: 4 }],
  ])(
    "blocks changed fill %s lineage at the final claim",
    async (_label, fillChange) => {
      mocks.findFill.mockResolvedValue(
        finalFillRow(fillChange as Record<string, unknown>),
      );

      const response = await call();

      expect(response.status).toBe(409);
      await expect(response.json()).resolves.toMatchObject({
        code: "TEMPLATE_TWIN_OUTPUT_CLAIM_STALE",
      });
      expect(mocks.enqueueAudit).not.toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          action: "EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED",
        }),
      );
      expect(mocks.logDelivery).not.toHaveBeenCalled();
    },
  );

  it.each([
    ["visit", () => syntheticRunRow({ visitId: "synthetic-visit-replaced" })],
    [
      "admission",
      () => syntheticRunRow({ admissionId: "synthetic-admission-replaced" }),
    ],
    [
      "physician authority",
      () => syntheticRunRow({ doctorId: "synthetic-doctor-replaced" }),
    ],
    [
      "admission source",
      () => {
        const run = syntheticRunRow();
        return {
          ...run,
          admission: {
            ...run.admission,
            sourceArtifactId: "synthetic-source-replaced",
          },
        };
      },
    ],
  ])(
    "blocks changed synthetic run %s linkage at the final claim",
    async (_label, changedRun) => {
      configureSyntheticDownload(changedRun());

      const response = await call();

      expect(response.status).toBe(409);
      await expect(response.json()).resolves.toMatchObject({
        code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
      });
      expect(mocks.enqueueAudit).not.toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          action: "EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED",
        }),
      );
      expect(mocks.logDelivery).not.toHaveBeenCalled();
    },
  );

  it("blocks download when encounter evidence changes before the final claim", async () => {
    mocks.verifyEvidence.mockReturnValue(false);

    const response = await call();

    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({
      code: "TEMPLATE_TWIN_ENCOUNTER_EVIDENCE_STALE",
    });
    expect(mocks.logDelivery).not.toHaveBeenCalled();
  });

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

  it("blocks a suspension race at the final download claim", async () => {
    mocks.queryRaw.mockReset().mockResolvedValue([]);

    const response = await call();

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
      retry: false,
    });
    expect(mocks.enqueueAudit).not.toHaveBeenCalled();
    expect(mocks.logDelivery).not.toHaveBeenCalled();
  });

  it("returns no DOCX when the patient leaves the actor practice before the final download claim", async () => {
    mocks.queryRaw.mockImplementation(
      async (query: { strings?: readonly string[] }) => {
        const sql = query.strings?.join(" ") ?? "";
        if (sql.includes('FROM "transcribe_md_patients" patient')) return [];
        return [
          {
            id: "synthetic-doctor-1",
            email: "doctor@synthetic.test",
          },
        ];
      },
    );

    const response = await call();

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
      retry: false,
    });
    expect(response.headers.get("content-type")).not.toBe(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(mocks.lockVisit).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).not.toHaveBeenCalled();
    expect(mocks.logDelivery).not.toHaveBeenCalled();
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
