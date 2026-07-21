import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TranscribeVisitStatus } from "@prisma/client";
import { z } from "zod";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  getTemplateTwinSyntheticQaProviderContext,
  modelClient,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
  TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES,
} from "../../lib/template-twin/staging-qa-fixtures";
import { templateTwinStagingQaPayloadSha256 } from "../../lib/template-twin/staging-qa-digest";

import {
  assertSyntheticQaResolvedRolloutToken,
  claimTemplateTwinSyntheticQaWorkerAttempt,
  prepareTemplateTwinSyntheticQaDeliveryRetry,
  reconcileExpiredTemplateTwinSyntheticQaWorkerClaim,
  renewTemplateTwinSyntheticQaWorkerLease,
  runWithWorkerSyntheticQaProviderSelection,
  templateTwinSyntheticQaWorkerFailureCode,
  TEMPLATE_TWIN_SYNTHETIC_QA_JOB_FAILURE_CODE,
  TemplateTwinSyntheticQaWorkerAdmissionError,
  type TemplateTwinSyntheticQaVisitSnapshot,
} from "../synthetic-qa-provider";

const dependencyMocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  pinRollout: vi.fn(),
  lockRollout: vi.fn(),
  lockAttempt: vi.fn(),
  lockOperation: vi.fn(),
  lockAdmissionThenRun: vi.fn(),
  lockVisit: vi.fn(),
  enqueueAudit: vi.fn(),
  claimWorkerAttempt: vi.fn(),
  rootRunFindFirst: vi.fn(),
  runUpdateMany: vi.fn(),
  markManifestFailed: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: dependencyMocks.transaction,
    templateTwinSyntheticQaRun: {
      findFirst: dependencyMocks.rootRunFindFirst,
      updateMany: dependencyMocks.runUpdateMany,
    },
  },
  prisma: {},
}));
vi.mock("@/lib/template-twin/rollout", () => ({
  pinTemplateTwinRollout: dependencyMocks.pinRollout,
  lockTemplateTwinRolloutForFinalClaim: dependencyMocks.lockRollout,
}));
vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueTemplateTwinAudit: dependencyMocks.enqueueAudit,
}));
vi.mock("@/worker/automation-manifest", () => ({
  markVisitAutomationManifestFailed: dependencyMocks.markManifestFailed,
}));

describe("synthetic QA global worker failure telemetry", () => {
  it("preserves only closed-set admission codes", () => {
    expect(
      templateTwinSyntheticQaWorkerFailureCode(
        new TemplateTwinSyntheticQaWorkerAdmissionError(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED",
          "sensitive synthetic document text that must never be logged",
        ),
      ),
    ).toBe("TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED");
  });

  it("collapses arbitrary error messages to one stable non-sensitive code", () => {
    const message =
      "synthetic encounter and provider response that must never be logged";
    const code = templateTwinSyntheticQaWorkerFailureCode(new Error(message));

    expect(code).toBe(TEMPLATE_TWIN_SYNTHETIC_QA_JOB_FAILURE_CODE);
    expect(code).not.toContain(message);
  });
});
vi.mock("@/lib/template-twin/fill-engine", () => ({
  lockCurrentTemplateTwinVisit: dependencyMocks.lockVisit,
}));
vi.mock(
  "@/lib/template-twin/staging-qa-visit-guard",
  async (importOriginal) => ({
    ...((await importOriginal()) as typeof import("../../lib/template-twin/staging-qa-visit-guard")),
    lockAndAssertTemplateTwinStagingQaAttempt: dependencyMocks.lockAttempt,
    lockAndAssertTemplateTwinStagingQaOperation: dependencyMocks.lockOperation,
    lockTemplateTwinStagingQaAdmissionThenRun:
      dependencyMocks.lockAdmissionThenRun,
  }),
);

const SAFE_ENV: SyntheticQaProviderEnvironment = {
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: "postgresql:///meddoc_qa_test",
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
  MOCK_AI_CALLS: "true",
  MOCK_TEMPLATE_TWIN_E2E: "true",
};

beforeEach(() => {
  for (const mock of Object.values(dependencyMocks)) mock.mockReset();
  dependencyMocks.claimWorkerAttempt.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
});

function payloadSha256(
  evidenceText: string,
  mode: "typed" | "mock_voice" = "typed",
): string {
  return templateTwinStagingQaPayloadSha256({
    templateId: "template-synthetic-1",
    expectedTemplateVersion: 4,
    mode,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    evidenceText,
  });
}

function visit(
  overrides: Partial<TemplateTwinSyntheticQaVisitSnapshot> = {},
): TemplateTwinSyntheticQaVisitSnapshot {
  return {
    id: "visit-synthetic-1",
    userId: "doctor-synthetic-1",
    practiceId: "practice-synthetic-1",
    inputMode: "text_notes",
    noteTemplateId: "template-synthetic-1",
    noteTemplateVersion: 4,
    rawTextInput: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
    dictationAudioKey: null,
    audioMimeType: null,
    audioSizeBytes: null,
    templateAdmission: {
      status: "active",
      templateKind: "template_twin_docx",
      certificationStatus: "CERTIFIED",
      hasCertification: true,
      sourceValidationStatus: "accepted",
      sourceArtifactSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
      sourceArtifactSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
    },
    syntheticQaRun: {
      id: "run-synthetic-1",
      admissionId: "admission-visit-synthetic-1",
      visitId: "visit-synthetic-1",
      practiceId: "practice-synthetic-1",
      doctorId: "doctor-synthetic-1",
      noteTemplateId: "template-synthetic-1",
      noteTemplateVersion: 4,
      requestSha256: "a".repeat(64),
      payloadSha256: payloadSha256(TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT),
      mode: "typed",
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      pinnedGlobalRolloutGeneration: BigInt(11),
      pinnedPracticeRolloutGeneration: BigInt(19),
      status: "ENQUEUED",
      attempt: 1,
      enqueuedAt: new Date("2026-07-17T00:00:00.000Z"),
      workerClaimId: null,
      workerClaimedAt: null,
      workerHeartbeatAt: null,
      workerLeaseExpiresAt: null,
      workerDeliveryCount: 0,
      workerRetryReadyAt: null,
      admission: {
        id: "admission-visit-synthetic-1",
        practiceId: "practice-synthetic-1",
        actorId: "doctor-synthetic-1",
        parentAdmissionId: "admission-upload-synthetic-1",
        sourceSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sourceSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
        providerMode: "SYNTHETIC_TYPED",
        purpose: "VISIT",
        phase: "VISIT_LINKED",
        requestSha256: "a".repeat(64),
        payloadSha256: payloadSha256(TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT),
        noteTemplateId: "template-synthetic-1",
        noteTemplateVersion: 4,
        certificationId: "certification-synthetic-1",
        visitId: "visit-synthetic-1",
        attempt: 1,
        expiresAt: new Date("2099-07-17T00:00:00.000Z"),
        failedAt: null,
        revokedAt: null,
        pinnedGlobalRolloutGeneration: BigInt(11),
        pinnedPracticeRolloutGeneration: BigInt(19),
      },
    },
    ...overrides,
  };
}

function typedEvidenceVisit(
  evidenceText: string,
): TemplateTwinSyntheticQaVisitSnapshot {
  const base = visit();
  return visit({
    rawTextInput: evidenceText,
    syntheticQaRun: {
      ...base.syntheticQaRun!,
      payloadSha256: payloadSha256(evidenceText),
      admission: {
        ...base.syntheticQaRun!.admission!,
        payloadSha256: payloadSha256(evidenceText),
      },
    },
  });
}

function mockVoiceVisit(): TemplateTwinSyntheticQaVisitSnapshot {
  const base = visit();
  return visit({
    inputMode: "voice_dictation",
    rawTextInput: null,
    dictationAudioKey:
      "doctor-synthetic-1/visit-synthetic-1/template-twin-synthetic-qa.wav",
    audioMimeType: "audio/wav",
    audioSizeBytes: TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES,
    syntheticQaRun: {
      ...base.syntheticQaRun!,
      mode: "mock_voice",
      payloadSha256: payloadSha256(
        TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
        "mock_voice",
      ),
      admission: {
        ...base.syntheticQaRun!.admission!,
        providerMode: "SYNTHETIC_MOCK_VOICE",
        payloadSha256: payloadSha256(
          TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
          "mock_voice",
        ),
      },
    },
  });
}

function matchingToken() {
  return {
    practiceId: "practice-synthetic-1",
    globalGeneration: BigInt(11),
    practiceGeneration: BigInt(19),
  };
}

function matchingPin() {
  return vi.fn().mockResolvedValue(matchingToken());
}

function admittedDependencies(pinRollout = matchingPin()) {
  return {
    pinRollout,
    claimAttempt: dependencyMocks.claimWorkerAttempt,
    env: SAFE_ENV,
  };
}

function matchingJob(
  overrides: {
    userId?: string;
    syntheticQaRunId?: string;
    syntheticQaAttempt?: number;
    workerDeliveryNumber?: number;
  } = {},
) {
  return {
    userId: "doctor-synthetic-1",
    syntheticQaRunId: "run-synthetic-1",
    syntheticQaAttempt: 1,
    workerClaimId: "11111111-1111-4111-8111-111111111111",
    workerDeliveryNumber: 1,
    ...overrides,
  };
}

describe("worker synthetic QA provider selection", () => {
  it("leaves an ordinary visit outside the synthetic provider context", async () => {
    const pinRollout = matchingPin();
    const result = await runWithWorkerSyntheticQaProviderSelection(
      visit({ syntheticQaRun: null, templateAdmission: null }),
      { userId: "doctor-synthetic-1" },
      () => getTemplateTwinSyntheticQaProviderContext(),
      admittedDependencies(pinRollout),
    );

    expect(result).toBeNull();
    expect(pinRollout).not.toHaveBeenCalled();
  });

  it("scopes the legacy infrastructure fixture to a certified non-staging Template Twin visit", async () => {
    vi.stubEnv("MOCK_AI_CALLS", "true");
    vi.stubEnv("MOCK_TEMPLATE_TWIN_E2E", "true");
    vi.stubEnv("DATABASE_URL", "postgresql:///meddoc_qa_test");
    const base = visit();
    const result = await runWithWorkerSyntheticQaProviderSelection(
      visit({
        syntheticQaRun: null,
        templateAdmission: {
          ...base.templateAdmission!,
          sourceArtifactSha256: "b".repeat(64),
          sourceArtifactSizeBytes: 5_432,
        },
      }),
      { userId: "doctor-synthetic-1" },
      () =>
        modelClient.complete({
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic legacy infrastructure harness",
          user: "synthetic legacy encounter",
          purpose: "tm_entities",
          visitId: "visit-synthetic-1",
          practiceId: "practice-synthetic-1",
          schema: z.object({
            medications: z.array(z.object({ name: z.string() })).default([]),
          }),
        }),
      {
        ...admittedDependencies(),
        env: { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENABLED: undefined },
      },
    );

    expect(result.medications).toEqual([
      expect.objectContaining({ name: "Syntheticmed" }),
    ]);
  });

  it("rejects a certified non-staging Template Twin without durable admission when staging QA is requested", async () => {
    const callback = vi.fn();
    const base = visit();

    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit({
          syntheticQaRun: null,
          templateAdmission: {
            ...base.templateAdmission!,
            sourceArtifactSha256: "b".repeat(64),
            sourceArtifactSizeBytes: 5_432,
          },
        }),
        { userId: "doctor-synthetic-1" },
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
    });
    expect(callback).not.toHaveBeenCalled();
    expect(dependencyMocks.claimWorkerAttempt).not.toHaveBeenCalled();
  });

  it("rejects the allowlisted staging fixture without its durable run", async () => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit({ syntheticQaRun: null }),
        { userId: "doctor-synthetic-1" },
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
    });
    expect(callback).not.toHaveBeenCalled();
  });

  it("enters a visit-bound context only after the persisted generation matches", async () => {
    const pinRollout = matchingPin();
    const result = await runWithWorkerSyntheticQaProviderSelection(
      visit(),
      matchingJob(),
      () => getTemplateTwinSyntheticQaProviderContext(),
      admittedDependencies(pinRollout),
    );

    expect(pinRollout).toHaveBeenCalledWith({
      practiceId: "practice-synthetic-1",
    });
    expect(result).toMatchObject({
      runId: "run-synthetic-1",
      visitId: "visit-synthetic-1",
      practiceId: "practice-synthetic-1",
      pinnedGlobalGeneration: BigInt(11),
      pinnedPracticeGeneration: BigInt(19),
      evidenceClaims: expect.arrayContaining([
        "chief_complaint",
        "medication",
        "plan",
      ]),
    });
    expect(getTemplateTwinSyntheticQaProviderContext()).toBeNull();
  });

  it("rejects an old run after disable/re-enable changes the generation", async () => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit(),
        matchingJob(),
        callback,
        {
          pinRollout: vi.fn().mockResolvedValue({
            practiceId: "practice-synthetic-1",
            globalGeneration: BigInt(13),
            practiceGeneration: BigInt(21),
          }),
          env: SAFE_ENV,
        },
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
    });
    expect(callback).not.toHaveBeenCalled();
  });

  it.each([
    [
      "cross-practice run",
      { practiceId: "other-practice" },
      "TEMPLATE_TWIN_SYNTHETIC_QA_TENANT_MISMATCH",
    ],
    [
      "pending enqueue",
      { status: "PENDING_ENQUEUE", enqueuedAt: null },
      "TEMPLATE_TWIN_SYNTHETIC_QA_NOT_ENQUEUED",
    ],
    [
      "unsupported fixture",
      { fixtureVersion: "future-fixture" },
      "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED",
    ],
    [
      "wrong mode",
      { mode: "mock_voice" },
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
    ],
  ])("rejects %s before provider admission", async (_label, runPatch, code) => {
    const base = visit();
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit({
          syntheticQaRun: { ...base.syntheticQaRun!, ...runPatch },
        }),
        matchingJob(),
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({ code });
    expect(callback).not.toHaveBeenCalled();
  });

  it.each([
    ["artifact digest", { sourceArtifactSha256: "b".repeat(64) }],
    [
      "artifact byte count",
      {
        sourceArtifactSizeBytes:
          TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES + 1,
      },
    ],
    ["certification row", { hasCertification: false }],
    ["active lifecycle", { status: "inactive" }],
  ])(
    "rejects a mismatched reviewed fixture %s before provider work",
    async (_label, patch) => {
      const callback = vi.fn();
      const base = visit();
      await expect(
        runWithWorkerSyntheticQaProviderSelection(
          visit({
            templateAdmission: { ...base.templateAdmission!, ...patch },
          }),
          matchingJob(),
          callback,
          admittedDependencies(),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED",
      });
      expect(callback).not.toHaveBeenCalled();
    },
  );

  it("rejects unrelated typed input before provider admission", async () => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        typedEvidenceVisit(
          "This is an unrelated synthetic sentence with no reviewed fixture evidence.",
        ),
        matchingJob(),
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({ code: "SYNTHETIC_QA_CONTEXT_INVALID" });
    expect(callback).not.toHaveBeenCalled();
  });

  it("rejects partial reviewed sentences instead of silently truncating evidence", async () => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        typedEvidenceVisit(
          "Chief concern is synthetic wrist discomfort. Medication Syntheticmed docu",
        ),
        matchingJob(),
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({ code: "SYNTHETIC_QA_CONTEXT_INVALID" });
    expect(callback).not.toHaveBeenCalled();
  });

  it("admits an exact reviewed sentence subset", async () => {
    const claims = await runWithWorkerSyntheticQaProviderSelection(
      typedEvidenceVisit("Chief concern is synthetic wrist discomfort."),
      matchingJob(),
      () => getTemplateTwinSyntheticQaProviderContext()?.evidenceClaims,
      admittedDependencies(),
    );

    expect(claims).toEqual(["chief_complaint"]);
  });

  it("accepts only mock_voice on a single-speaker voice visit", async () => {
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        mockVoiceVisit(),
        matchingJob(),
        () => getTemplateTwinSyntheticQaProviderContext()?.evidenceClaims,
        {
          ...admittedDependencies(),
          verifyEvidence: vi.fn().mockResolvedValue(undefined),
        },
      ),
    ).resolves.toEqual(
      expect.arrayContaining(["chief_complaint", "medication", "plan"]),
    );
  });

  it("rejects a new rollout token resolved after provider work began", async () => {
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit(),
        matchingJob(),
        () => {
          assertSyntheticQaResolvedRolloutToken({
            practiceId: "practice-synthetic-1",
            globalGeneration: BigInt(12),
            practiceGeneration: BigInt(19),
          });
        },
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
    });
  });

  it("accepts the exact resolved token and keeps final-claim provenance unchanged", async () => {
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit(),
        matchingJob(),
        () => {
          assertSyntheticQaResolvedRolloutToken({
            practiceId: "practice-synthetic-1",
            globalGeneration: BigInt(11),
            practiceGeneration: BigInt(19),
          });
        },
        admittedDependencies(),
      ),
    ).resolves.toBeUndefined();
  });

  it.each([
    ["wrong durable run id", { syntheticQaRunId: "run-synthetic-other" }],
    ["stale attempt", { syntheticQaAttempt: 2 }],
    ["missing run id", { syntheticQaRunId: undefined }],
    ["missing attempt", { syntheticQaAttempt: undefined }],
  ])("rejects a worker payload with %s", async (_label, patch) => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit(),
        matchingJob(patch),
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
    });
    expect(callback).not.toHaveBeenCalled();
  });

  it("rejects a synthetic payload when the durable run does not exist", async () => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit({ syntheticQaRun: null }),
        matchingJob(),
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
    });
    expect(callback).not.toHaveBeenCalled();
  });

  it("rejects a job owner that differs from the visit owner", async () => {
    const callback = vi.fn();
    await expect(
      runWithWorkerSyntheticQaProviderSelection(
        visit(),
        matchingJob({ userId: "doctor-synthetic-other" }),
        callback,
        admittedDependencies(),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_TENANT_MISMATCH",
    });
    expect(callback).not.toHaveBeenCalled();
  });
});

describe("worker synthetic QA attempt ownership", () => {
  it("durably relinquishes a claimed delivery before BullMQ retries it", async () => {
    const tx = {
      templateTwinSyntheticQaRun: {
        updateMany: dependencyMocks.runUpdateMany,
      },
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: true,
      token: matchingToken(),
    });
    dependencyMocks.lockAttempt.mockResolvedValue(undefined);
    dependencyMocks.lockVisit.mockResolvedValue({
      userId: "doctor-synthetic-1",
      status: TranscribeVisitStatus.AUTOMATING,
      deletedAt: null,
      archivedAt: null,
    });
    dependencyMocks.runUpdateMany.mockResolvedValue({ count: 1 });
    dependencyMocks.enqueueAudit.mockResolvedValue(undefined);

    const result = await runWithWorkerSyntheticQaProviderSelection(
      visit(),
      matchingJob(),
      () =>
        prepareTemplateTwinSyntheticQaDeliveryRetry({
          visitId: "visit-synthetic-1",
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          nextWorkerDeliveryNumber: 2,
        }),
      admittedDependencies(),
    );

    expect(result).toBe(true);
    expect(dependencyMocks.runUpdateMany).toHaveBeenCalledWith({
      where: expect.objectContaining({
        status: "PROCESSING",
        workerClaimId: "11111111-1111-4111-8111-111111111111",
        workerDeliveryCount: 1,
        workerRetryReadyAt: null,
      }),
      data: expect.objectContaining({
        status: "RETRY_ENQUEUED",
        workerClaimId: null,
        workerRetryReadyAt: expect.any(Date),
      }),
    });
    expect(dependencyMocks.enqueueAudit).toHaveBeenCalledTimes(1);
  });

  it("claims only the next numbered delivery from RETRY_ENQUEUED", async () => {
    const tx = {
      $queryRaw: vi.fn().mockResolvedValue([{ id: "run-synthetic-1" }]),
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: true,
      token: matchingToken(),
    });
    dependencyMocks.lockOperation.mockResolvedValue({
      status: "RETRY_ENQUEUED",
    });
    dependencyMocks.lockVisit.mockResolvedValue({
      userId: "doctor-synthetic-1",
      status: TranscribeVisitStatus.AUTOMATING,
      deletedAt: null,
      archivedAt: null,
    });
    dependencyMocks.enqueueAudit.mockResolvedValue(undefined);
    const snapshot = visit();

    await expect(
      claimTemplateTwinSyntheticQaWorkerAttempt({
        visit: snapshot,
        run: {
          ...snapshot.syntheticQaRun!,
          status: "RETRY_ENQUEUED",
          workerDeliveryCount: 1,
          workerRetryReadyAt: new Date("2026-07-17T00:00:30.000Z"),
          admission: {
            ...snapshot.syntheticQaRun!.admission!,
            phase: "PROCESSING",
          },
        },
        currentToken: matchingToken(),
        workerClaimId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        workerDeliveryNumber: 2,
      }),
    ).resolves.toBeUndefined();
    expect(dependencyMocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        metadata: expect.objectContaining({
          operation: "bounded_worker_delivery_retry",
          workerDeliveryNumber: 2,
        }),
      }),
    );
  });

  it("rejects a fourth worker delivery before opening a transaction", async () => {
    const snapshot = visit();
    await expect(
      claimTemplateTwinSyntheticQaWorkerAttempt({
        visit: snapshot,
        run: snapshot.syntheticQaRun!,
        currentToken: matchingToken(),
        workerClaimId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        workerDeliveryNumber: 4,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
    });
    expect(dependencyMocks.transaction).not.toHaveBeenCalled();
  });

  it("allows exactly one delivery to claim an ENQUEUED attempt", async () => {
    let available = true;
    const tx = {
      $queryRaw: vi.fn(async () => {
        if (!available) return [];
        available = false;
        return [{ id: "run-synthetic-1" }];
      }),
      templateTwinSyntheticQaAdmission: {
        updateMany: vi.fn().mockResolvedValue({ count: 1 }),
      },
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: true,
      token: {
        practiceId: "practice-synthetic-1",
        globalGeneration: BigInt(11),
        practiceGeneration: BigInt(19),
      },
    });
    dependencyMocks.lockAttempt.mockResolvedValue(undefined);
    dependencyMocks.lockOperation.mockResolvedValue({
      status: "ENQUEUED",
    });
    dependencyMocks.lockVisit.mockResolvedValue({
      userId: "doctor-synthetic-1",
      status: TranscribeVisitStatus.QUEUED,
      deletedAt: null,
      archivedAt: null,
    });
    const snapshot = visit();
    const input = {
      visit: snapshot,
      run: snapshot.syntheticQaRun!,
      currentToken: {
        practiceId: "practice-synthetic-1",
        globalGeneration: BigInt(11),
        practiceGeneration: BigInt(19),
      },
      workerClaimId: "11111111-1111-4111-8111-111111111111",
      workerDeliveryNumber: 1,
    };

    const results = await Promise.allSettled([
      claimTemplateTwinSyntheticQaWorkerAttempt(input),
      claimTemplateTwinSyntheticQaWorkerAttempt(input),
    ]);

    expect(
      results.filter((result) => result.status === "fulfilled"),
    ).toHaveLength(1);
    expect(
      results.filter((result) => result.status === "rejected"),
    ).toHaveLength(1);
    expect(tx.$queryRaw).toHaveBeenCalledTimes(2);
  });

  it("reclaims an expired PROCESSING lease for BullMQ redelivery", async () => {
    const tx = {
      $queryRaw: vi.fn().mockResolvedValue([{ id: "run-synthetic-1" }]),
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: true,
      token: matchingToken(),
    });
    dependencyMocks.lockOperation.mockResolvedValue({ status: "PROCESSING" });
    dependencyMocks.lockVisit.mockResolvedValue({
      userId: "doctor-synthetic-1",
      status: TranscribeVisitStatus.AUTOMATING,
      deletedAt: null,
      archivedAt: null,
    });
    dependencyMocks.enqueueAudit.mockResolvedValue(undefined);
    const snapshot = visit();
    await expect(
      claimTemplateTwinSyntheticQaWorkerAttempt({
        visit: snapshot,
        run: {
          ...snapshot.syntheticQaRun!,
          status: "PROCESSING",
          workerClaimId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
          workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
          workerLeaseExpiresAt: new Date("2026-07-17T00:00:25.000Z"),
          workerDeliveryCount: 1,
        },
        currentToken: matchingToken(),
        workerClaimId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        workerDeliveryNumber: 2,
      }),
    ).resolves.toBeUndefined();

    const claimSql = tx.$queryRaw.mock.calls[0]?.[0] as {
      strings: readonly string[];
    };
    expect(claimSql.strings.join("?")).toContain("clock_timestamp()");
    expect(claimSql.strings.join("?")).toContain(
      '"workerLeaseExpiresAt" <= clock_timestamp()',
    );
    expect(dependencyMocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        metadata: expect.objectContaining({
          operation: "stalled_worker_lease_reclaim",
        }),
      }),
    );
  });

  it("rejects redelivery while the prior claim lease is active", async () => {
    const tx = {
      $queryRaw: vi.fn().mockResolvedValue([]),
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: true,
      token: matchingToken(),
    });
    dependencyMocks.lockOperation.mockResolvedValue({ status: "PROCESSING" });
    dependencyMocks.lockVisit.mockResolvedValue({
      userId: "doctor-synthetic-1",
      status: TranscribeVisitStatus.AUTOMATING,
      deletedAt: null,
      archivedAt: null,
    });
    const snapshot = visit();
    await expect(
      claimTemplateTwinSyntheticQaWorkerAttempt({
        visit: snapshot,
        run: snapshot.syntheticQaRun!,
        currentToken: matchingToken(),
        workerClaimId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        workerDeliveryNumber: 1,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_NOT_ENQUEUED",
    });
    expect(dependencyMocks.enqueueAudit).not.toHaveBeenCalled();
  });

  it("rejects claim or heartbeat after rollout revocation", async () => {
    const tx = {
      $queryRaw: vi.fn(),
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: false,
      reason: "Synthetic rollout generation changed.",
    });
    const snapshot = visit();
    await expect(
      claimTemplateTwinSyntheticQaWorkerAttempt({
        visit: snapshot,
        run: snapshot.syntheticQaRun!,
        currentToken: matchingToken(),
        workerClaimId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        workerDeliveryNumber: 1,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
    });
    expect(tx.$queryRaw).not.toHaveBeenCalled();
  });

  it("renews only the exact current worker claim", async () => {
    const tx = {
      $queryRaw: vi.fn().mockResolvedValue([{ id: "run-synthetic-1" }]),
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({
      allowed: true,
      token: matchingToken(),
    });
    dependencyMocks.lockAttempt.mockResolvedValue(undefined);
    await renewTemplateTwinSyntheticQaWorkerLease({
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      runId: "run-synthetic-1",
      requestSha256: "a".repeat(64),
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      attempt: 1,
      workerClaimId: "11111111-1111-4111-8111-111111111111",
      pinnedGlobalGeneration: BigInt(11),
      pinnedPracticeGeneration: BigInt(19),
    });
    expect(dependencyMocks.lockAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        claim: expect.objectContaining({
          workerClaimId: "11111111-1111-4111-8111-111111111111",
        }),
      }),
    );
    const renewalSql = tx.$queryRaw.mock.calls[0]?.[0] as {
      strings: readonly string[];
    };
    expect(renewalSql.strings.join("?")).toContain(
      '"workerLeaseExpiresAt" > clock_timestamp()',
    );
  });
});

describe("worker synthetic QA crash reconciliation", () => {
  it("turns an expired terminal stalled delivery into an explicit retry state", async () => {
    dependencyMocks.rootRunFindFirst.mockResolvedValue({
      admissionId: "admission-visit-synthetic-1",
      practiceId: "practice-synthetic-1",
      pinnedGlobalRolloutGeneration: BigInt(11),
      pinnedPracticeRolloutGeneration: BigInt(19),
    });
    const tx = {
      templateTwinSyntheticQaRun: {
        update: vi.fn().mockResolvedValue({}),
      },
      templateTwinSyntheticQaAdmission: {
        updateMany: vi.fn().mockResolvedValue({ count: 1 }),
      },
      transcribeVisit: { update: vi.fn().mockResolvedValue({}) },
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({ allowed: false });
    dependencyMocks.lockAdmissionThenRun.mockResolvedValue({
      admissionId: "admission-visit-synthetic-1",
      run: {
        id: "run-synthetic-1",
        admissionId: "admission-visit-synthetic-1",
        visitId: "visit-synthetic-1",
        doctorId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
        attempt: 1,
        status: "PROCESSING",
        workerClaimId: "claim-synthetic-1",
        workerLeaseExpiresAt: new Date("2026-07-17T00:01:00.000Z"),
      },
    });
    dependencyMocks.lockVisit.mockResolvedValue({
      userId: "doctor-synthetic-1",
      status: TranscribeVisitStatus.AUTOMATING,
    });
    dependencyMocks.enqueueAudit.mockResolvedValue(undefined);
    const now = new Date("2026-07-17T00:02:00.000Z");

    await expect(
      reconcileExpiredTemplateTwinSyntheticQaWorkerClaim({
        runId: "run-synthetic-1",
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        attempt: 1,
        now,
      }),
    ).resolves.toBe(true);
    expect(tx.templateTwinSyntheticQaRun.update).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: "run-synthetic-1" },
        data: { status: "PROCESSING_FAILED" },
      }),
    );
    expect(tx.transcribeVisit.update).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ status: TranscribeVisitStatus.FAILED }),
      }),
    );
  });

  it("leaves a live or already-reclaimed claim untouched", async () => {
    dependencyMocks.rootRunFindFirst.mockResolvedValue({
      admissionId: "admission-visit-synthetic-1",
      practiceId: "practice-synthetic-1",
      pinnedGlobalRolloutGeneration: BigInt(11),
      pinnedPracticeRolloutGeneration: BigInt(19),
    });
    const tx = {
      $queryRaw: vi
        .fn()
        .mockResolvedValue([
          { databaseNow: new Date("2026-07-17T00:00:10.000Z") },
        ]),
      templateTwinSyntheticQaRun: {
        update: vi.fn(),
      },
      transcribeVisit: { update: vi.fn() },
    };
    dependencyMocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    dependencyMocks.lockRollout.mockResolvedValue({ allowed: true });
    dependencyMocks.lockAdmissionThenRun.mockResolvedValue({
      admissionId: "admission-visit-synthetic-1",
      run: {
        id: "run-synthetic-1",
        admissionId: "admission-visit-synthetic-1",
        visitId: "visit-synthetic-1",
        doctorId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
        attempt: 1,
        status: "PROCESSING",
        workerClaimId: "claim-synthetic-1",
        workerLeaseExpiresAt: new Date("2026-07-17T00:10:00.000Z"),
      },
    });
    await expect(
      reconcileExpiredTemplateTwinSyntheticQaWorkerClaim({
        runId: "run-synthetic-1",
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        attempt: 1,
      }),
    ).resolves.toBe(false);
    expect(tx.transcribeVisit.update).not.toHaveBeenCalled();
    expect(dependencyMocks.enqueueAudit).not.toHaveBeenCalled();
  });
});
