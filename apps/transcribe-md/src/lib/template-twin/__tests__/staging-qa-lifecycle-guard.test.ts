import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  getTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixtures";
import {
  assertTemplateTwinStagingQaLifecycleFinality,
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "../staging-qa-lifecycle-guard";

const mocks = vi.hoisted(() => ({
  findAdmission: vi.fn(),
  pinRollout: vi.fn(),
  certifyAdmission: vi.fn(),
  markAdmissionFailed: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    templateTwinSyntheticQaAdmission: { findFirst: mocks.findAdmission },
  },
}));
vi.mock("../rollout", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../rollout")>()),
  pinTemplateTwinRollout: mocks.pinRollout,
}));
vi.mock("../staging-qa-admission", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../staging-qa-admission")>()),
  certifyTemplateTwinStagingQaAdmission: mocks.certifyAdmission,
  markTemplateTwinStagingQaAdmissionFailed: mocks.markAdmissionFailed,
}));

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
  TEMPLATE_TWIN_KILL_SWITCH: "false",
};

const TOKEN = {
  practiceId: "practice-lifecycle-synthetic",
  globalGeneration: BigInt(5),
  practiceGeneration: BigInt(8),
};

const ACTOR = {
  userId: "doctor-lifecycle@synthetic.test",
  practiceId: TOKEN.practiceId,
  rolloutToken: TOKEN,
};

const EXACT_SOURCE = {
  sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
};

function admission() {
  return {
    id: "admission-lifecycle-synthetic",
    practiceId: TOKEN.practiceId,
    actorId: ACTOR.userId,
    parentAdmissionId: null,
    sourceSha256: EXACT_SOURCE.sha256,
    sourceSizeBytes: EXACT_SOURCE.sizeBytes,
    fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
    providerMode: "SYNTHETIC_LIFECYCLE",
    purpose: "UPLOAD",
    phase: "TEMPLATE_LINKED",
    requestSha256: "a".repeat(64),
    payloadSha256: null,
    pinnedGlobalRolloutGeneration: TOKEN.globalGeneration,
    pinnedPracticeRolloutGeneration: TOKEN.practiceGeneration,
    sourceArtifactId: "source-lifecycle-synthetic",
    noteTemplateId: "template-lifecycle-synthetic",
    noteTemplateVersion: 1,
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

function stagingInspect(
  source: { sha256: string; sizeBytes: number } = EXACT_SOURCE,
) {
  return vi.fn().mockResolvedValue({
    stagingQa: true,
    source,
    admission: admission(),
  });
}

function matchingPin() {
  return vi.fn().mockResolvedValue(TOKEN);
}

beforeEach(() => {
  mocks.findAdmission.mockReset().mockResolvedValue(admission());
  mocks.pinRollout.mockReset().mockResolvedValue(TOKEN);
  mocks.certifyAdmission.mockReset().mockResolvedValue(undefined);
  mocks.markAdmissionFailed.mockReset().mockResolvedValue(undefined);
});

describe("generic staging lifecycle guard", () => {
  it("rejects exact staging source provenance without a durable root admission", async () => {
    const operation = vi.fn();
    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "workspace-read",
        operation,
        dependencies: {
          inspect: vi.fn().mockResolvedValue({
            stagingQa: true,
            source: EXACT_SOURCE,
            admission: null,
          }),
          pinRollout: matchingPin(),
          env: SAFE_ENV,
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaLifecycleGuardError);
    expect(operation).not.toHaveBeenCalled();
  });

  it("rejects exact persisted staging provenance before any callback after process revocation", async () => {
    const operation = vi.fn();
    const pinRollout = matchingPin();

    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "mapping-update",
        operation,
        dependencies: {
          inspect: stagingInspect(),
          pinRollout,
          env: { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENABLED: "false" },
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaLifecycleGuardError);

    expect(pinRollout).not.toHaveBeenCalled();
    expect(operation).not.toHaveBeenCalled();
  });

  it("rejects a copied admission when the persisted source is not the fixture", async () => {
    const operation = vi.fn(() => {
      const context = getTemplateTwinSyntheticQaProviderContext();
      expect(context?.practiceId).toBe(ACTOR.practiceId);
      return context?.visitId;
    });
    const overbroadClassifier = vi.fn(() => true);

    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "workspace-read",
        operation,
        isExpectedBusinessError: overbroadClassifier,
        dependencies: {
          inspect: stagingInspect({
            sha256: "f".repeat(64),
            sizeBytes: 7_777,
          }),
          pinRollout: matchingPin(),
          env: SAFE_ENV,
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaLifecycleGuardError);
    expect(operation).not.toHaveBeenCalled();
    expect(overbroadClassifier).not.toHaveBeenCalled();
    expect(mocks.markAdmissionFailed).not.toHaveBeenCalled();
  });

  it("keeps the deterministic provider context active if flags are revoked during an admitted callback", async () => {
    const mutableEnv = { ...SAFE_ENV };
    const result = await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: "template-lifecycle-synthetic",
      actor: ACTOR,
      purpose: "custom-example-run",
      evidenceText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
      operation: (providerVisitId) => {
        mutableEnv.TEMPLATE_TWIN_STAGING_QA_ENABLED = "false";
        mutableEnv.MOCK_AI_CALLS = "false";
        mutableEnv.MOCK_TEMPLATE_TWIN_E2E = "false";
        const context = getTemplateTwinSyntheticQaProviderContext();
        expect(context?.visitId).toBe(providerVisitId);
        expect(context?.practiceId).toBe(ACTOR.practiceId);
        return context?.fixtureVersion;
      },
      dependencies: {
        inspect: stagingInspect(),
        pinRollout: matchingPin(),
        env: mutableEnv,
      },
    });

    expect(result).toBe("template-twin-staging-safe-docx/1.0.0");
    expect(getTemplateTwinSyntheticQaProviderContext()).toBeNull();
  });

  it("rejects stale generations before a certification or download operation", async () => {
    const operation = vi.fn();
    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "certification-activation",
        operation,
        dependencies: {
          inspect: stagingInspect(),
          pinRollout: vi.fn().mockResolvedValue({
            ...TOKEN,
            practiceGeneration: TOKEN.practiceGeneration + BigInt(2),
          }),
          env: SAFE_ENV,
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaLifecycleGuardError);
    expect(operation).not.toHaveBeenCalled();
  });

  it("preserves an expected certification conflict without failing or certifying the admission", async () => {
    class ExpectedCertificationConflict extends Error {}
    const conflict = new ExpectedCertificationConflict(
      "The mapping version changed before certification.",
    );
    const isExpectedBusinessError = vi.fn(
      (error: unknown) => error instanceof ExpectedCertificationConflict,
    );

    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "certification-activation",
        operation: () => {
          throw conflict;
        },
        isExpectedBusinessError,
        dependencies: {
          inspect: stagingInspect(),
          pinRollout: matchingPin(),
          env: SAFE_ENV,
        },
      }),
    ).rejects.toBe(conflict);

    expect(isExpectedBusinessError).toHaveBeenCalledOnce();
    expect(isExpectedBusinessError).toHaveBeenCalledWith(conflict);
    expect(mocks.markAdmissionFailed).not.toHaveBeenCalled();
    expect(mocks.certifyAdmission).not.toHaveBeenCalled();
  });

  it("fails the admission for an unexpected certification operation error", async () => {
    const failure = new Error("Unexpected persistence failure.");

    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "certification-activation",
        operation: () => {
          throw failure;
        },
        isExpectedBusinessError: () => false,
        dependencies: {
          inspect: stagingInspect(),
          pinRollout: matchingPin(),
          env: SAFE_ENV,
        },
      }),
    ).rejects.toBe(failure);

    expect(mocks.markAdmissionFailed).toHaveBeenCalledWith({
      admissionId: admission().id,
      actor: {
        userId: ACTOR.userId,
        practiceId: ACTOR.practiceId,
      },
      failureCode: "TEMPLATE_TWIN_STAGING_QA_LIFECYCLE_PROVIDER_FAILED",
    });
    expect(mocks.certifyAdmission).not.toHaveBeenCalled();
  });

  it("advances certification admission only after the operation succeeds", async () => {
    const operation = vi.fn().mockResolvedValue("certified-workspace");

    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-lifecycle-synthetic",
        actor: ACTOR,
        purpose: "certification-activation",
        operation,
        isExpectedBusinessError: () => false,
        dependencies: {
          inspect: stagingInspect(),
          pinRollout: matchingPin(),
          env: SAFE_ENV,
        },
      }),
    ).resolves.toBe("certified-workspace");

    expect(mocks.certifyAdmission).toHaveBeenCalledWith({
      admissionId: admission().id,
      actor: ACTOR,
      noteTemplateId: "template-lifecycle-synthetic",
      env: SAFE_ENV,
    });
    expect(operation.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.certifyAdmission.mock.invocationCallOrder[0]!,
    );
    expect(mocks.markAdmissionFailed).not.toHaveBeenCalled();
  });

  it("preserves the ordinary Template Twin lifecycle path without a synthetic provider context", async () => {
    const operation = vi.fn((providerVisitId: string | null) => {
      expect(getTemplateTwinSyntheticQaProviderContext()).toBeNull();
      return providerVisitId;
    });
    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-ordinary",
        actor: ACTOR,
        purpose: "mapping-update",
        operation,
        dependencies: {
          inspect: vi.fn().mockResolvedValue({
            stagingQa: false,
            source: { sha256: "e".repeat(64), sizeBytes: 9_999 },
          }),
          env: { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENABLED: "false" },
        },
      }),
    ).resolves.toBeNull();
    expect(operation).toHaveBeenCalledWith(null);
  });

  it("rejects an ordinary Template Twin before its lifecycle callback in synthetic-only staging", async () => {
    const operation = vi.fn();

    await expect(
      runWithTemplateTwinStagingQaLifecycleGuard({
        noteTemplateId: "template-ordinary-staging-bypass",
        actor: ACTOR,
        purpose: "mapping-update",
        operation,
        dependencies: {
          inspect: vi.fn().mockResolvedValue({
            stagingQa: false,
            source: { sha256: "d".repeat(64), sizeBytes: 8_888 },
          }),
          env: SAFE_ENV,
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaLifecycleGuardError);
    expect(operation).not.toHaveBeenCalled();
  });

  it("rejects ordinary Template Twin response finality before any database lock in synthetic-only staging", async () => {
    const lockFinal = vi.fn();

    await expect(
      assertTemplateTwinStagingQaLifecycleFinality({
        noteTemplateId: "template-ordinary-staging-download",
        actor: ACTOR,
        dependencies: {
          inspect: vi.fn().mockResolvedValue({
            stagingQa: false,
            source: { sha256: "c".repeat(64), sizeBytes: 7_777 },
          }),
          env: SAFE_ENV,
          lockFinal,
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaLifecycleGuardError);
    expect(lockFinal).not.toHaveBeenCalled();
  });
});
