import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  getTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixtures";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  findAdmission: vi.fn(),
  pinRollout: vi.fn(),
  lockRollout: vi.fn(),
  enqueueAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: mocks.transaction,
    templateTwinSyntheticQaAdmission: { findFirst: mocks.findAdmission },
  },
}));
vi.mock("../rollout", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../rollout")>()),
  pinTemplateTwinRollout: mocks.pinRollout,
  lockTemplateTwinRolloutForFinalClaim: mocks.lockRollout,
}));
vi.mock("../audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));

import {
  beginTemplateTwinStagingQaUploadAdmission,
  markTemplateTwinStagingQaAdmissionFailed,
  runWithVerifiedTemplateTwinStagingQaAdmissionProvider,
  TemplateTwinStagingQaAdmissionError,
  type TemplateTwinStagingQaAdmissionRow,
} from "../staging-qa-admission";

const SAFE_ENV: SyntheticQaProviderEnvironment = {
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION:
    "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: "postgresql:///meddoc_durable_admission_synthetic_test",
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
  MOCK_AI_CALLS: "true",
  MOCK_TEMPLATE_TWIN_E2E: "true",
  TEMPLATE_TWIN_KILL_SWITCH: "false",
};

const TOKEN = {
  practiceId: "practice-admission-synthetic",
  globalGeneration: BigInt(17),
  practiceGeneration: BigInt(23),
};

const ACTOR = {
  userId: "doctor-admission-synthetic",
  userEmail: "doctor-admission@synthetic.test",
  practiceId: TOKEN.practiceId,
  rolloutToken: TOKEN,
};

function admission(
  overrides: Partial<TemplateTwinStagingQaAdmissionRow> = {},
): TemplateTwinStagingQaAdmissionRow {
  return { ...admissionBase(), ...overrides };
}

function admissionBase(): TemplateTwinStagingQaAdmissionRow {
  return {
    id: "admission-upload-synthetic",
    practiceId: TOKEN.practiceId,
    actorId: ACTOR.userId,
    parentAdmissionId: null,
    sourceSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
    sourceSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    providerMode: "SYNTHETIC_LIFECYCLE",
    purpose: "UPLOAD",
    phase: "ADMITTED",
    requestSha256: "a".repeat(64),
    payloadSha256: null,
    pinnedGlobalRolloutGeneration: TOKEN.globalGeneration,
    pinnedPracticeRolloutGeneration: TOKEN.practiceGeneration,
    sourceArtifactId: null,
    noteTemplateId: null,
    noteTemplateVersion: null,
    certificationId: null,
    mappingSha256: null,
    visitId: null,
    attempt: 1,
    expiresAt: new Date("2099-07-17T00:00:00.000Z"),
    failedAt: null,
    revokedAt: null,
    consumedAt: null,
  };
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.pinRollout.mockResolvedValue(TOKEN);
  mocks.lockRollout.mockResolvedValue({ allowed: true, token: TOKEN });
  mocks.findAdmission.mockResolvedValue(admission());
  mocks.enqueueAudit.mockResolvedValue(undefined);
});

describe("durable synthetic QA admission provider capability", () => {
  it("commits and rereads the admission before the first provider callback", async () => {
    const order: string[] = [];
    let committed: ReturnType<typeof admission> | null = null;
    const created = admission();
    const tx = {
      templateTwinSyntheticQaAdmission: {
        findFirst: vi.fn().mockResolvedValue(null),
        create: vi.fn().mockImplementation(async () => {
          order.push("insert-pending");
          return created;
        }),
      },
    };
    mocks.transaction.mockImplementation(async (callback) => {
      const result = await callback(tx);
      committed = created;
      order.push("commit");
      return result;
    });
    mocks.findAdmission.mockImplementation(async () => {
      order.push("database-reread");
      return committed;
    });

    const createdAdmission = await beginTemplateTwinStagingQaUploadAdmission({
      actor: ACTOR,
      idempotencyKey: "upload-admission-synthetic-0001",
      source: {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
      env: SAFE_ENV,
    });
    await runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
      admissionId: createdAdmission.id,
      actor: ACTOR,
      allowedPhases: ["ADMITTED"],
      expectedProviderMode: "SYNTHETIC_LIFECYCLE",
      operation: () => {
        order.push("provider");
        expect(getTemplateTwinSyntheticQaProviderContext()?.admissionId).toBe(
          createdAdmission.id,
        );
      },
      env: SAFE_ENV,
    });

    expect(order).toEqual([
      "insert-pending",
      "commit",
      "database-reread",
      "provider",
    ]);
  });

  it("does not accept a row that exists only inside an uncommitted transaction", async () => {
    let releaseCommit!: () => void;
    const commitBarrier = new Promise<void>((resolve) => {
      releaseCommit = resolve;
    });
    let inserted!: () => void;
    const insertBarrier = new Promise<void>((resolve) => {
      inserted = resolve;
    });
    let committed: ReturnType<typeof admission> | null = null;
    const created = admission();
    const tx = {
      templateTwinSyntheticQaAdmission: {
        findFirst: vi.fn().mockResolvedValue(null),
        create: vi.fn().mockImplementation(async () => {
          inserted();
          return created;
        }),
      },
    };
    mocks.transaction.mockImplementation(async (callback) => {
      const result = await callback(tx);
      await commitBarrier;
      committed = created;
      return result;
    });
    mocks.findAdmission.mockImplementation(async () => committed);

    const pending = beginTemplateTwinStagingQaUploadAdmission({
      actor: ACTOR,
      idempotencyKey: "upload-admission-synthetic-0002",
      source: {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
      env: SAFE_ENV,
    });
    await insertBarrier;

    await expect(
      runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
        admissionId: created.id,
        actor: ACTOR,
        allowedPhases: ["ADMITTED"],
        expectedProviderMode: "SYNTHETIC_LIFECYCLE",
        operation: vi.fn(),
        env: SAFE_ENV,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_NOT_FOUND",
    });

    releaseCommit();
    await expect(pending).resolves.toMatchObject({ id: created.id });
  });

  it.each([
    ["practice", { practiceId: "practice-other" }],
    ["actor", { actorId: "doctor-other" }],
    ["provider mode", { providerMode: "SYNTHETIC_TYPED" }],
    ["phase", { phase: "FAILED", failedAt: new Date() }],
    ["revocation", { phase: "REVOKED", revokedAt: new Date() }],
    ["consumption replay", { consumedAt: new Date() }],
    ["expiry", { expiresAt: new Date("2020-01-01T00:00:00.000Z") }],
    [
      "global rollout generation",
      { pinnedGlobalRolloutGeneration: TOKEN.globalGeneration + BigInt(1) },
    ],
    [
      "practice rollout generation",
      { pinnedPracticeRolloutGeneration: TOKEN.practiceGeneration + BigInt(1) },
    ],
  ])("rejects a mismatched or stale %s", async (_label, patch) => {
    mocks.findAdmission.mockResolvedValue(admission(patch));
    const operation = vi.fn();
    await expect(
      runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
        admissionId: "admission-upload-synthetic",
        actor: ACTOR,
        allowedPhases: ["ADMITTED"],
        expectedProviderMode: "SYNTHETIC_LIFECYCLE",
        operation,
        env: SAFE_ENV,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaAdmissionError);
    expect(operation).not.toHaveBeenCalled();
  });

  it("rejects a request-local identifier when no durable admission exists", async () => {
    mocks.findAdmission.mockResolvedValue(null);
    const operation = vi.fn();
    await expect(
      runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
        admissionId: "request-local-run-and-visit-identifiers-only",
        actor: ACTOR,
        allowedPhases: ["ADMITTED"],
        expectedProviderMode: "SYNTHETIC_LIFECYCLE",
        operation,
        env: SAFE_ENV,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_NOT_FOUND",
    });
    expect(operation).not.toHaveBeenCalled();
  });

  it("records provider failure as a durable terminal state with an atomic audit event", async () => {
    const update = vi.fn().mockResolvedValue(undefined);
    const tx = {
      templateTwinSyntheticQaAdmission: {
        findFirst: vi.fn().mockResolvedValue({
          id: "admission-upload-synthetic",
          phase: "TEMPLATE_LINKED",
        }),
        update,
      },
    };
    mocks.transaction.mockImplementation(async (callback) => callback(tx));

    await markTemplateTwinStagingQaAdmissionFailed({
      admissionId: "admission-upload-synthetic",
      actor: ACTOR,
      failureCode: "SYNTHETIC_PROVIDER_FAILED",
    });

    expect(update).toHaveBeenCalledWith({
      where: { id: "admission-upload-synthetic" },
      data: {
        phase: "FAILED",
        failedAt: expect.any(Date),
        failureCode: "SYNTHETIC_PROVIDER_FAILED",
      },
    });
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      tx,
      expect.objectContaining({
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_FAILED",
        targetId: "admission-upload-synthetic",
        metadata: {
          phase: "FAILED",
          failureCode: "SYNTHETIC_PROVIDER_FAILED",
        },
      }),
    );
  });
});
