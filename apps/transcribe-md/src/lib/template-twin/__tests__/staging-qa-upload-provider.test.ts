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
import {
  TemplateTwinStagingQaUploadProviderError,
  runWithTemplateTwinStagingQaUploadProvider,
} from "../staging-qa-upload-provider";

const mocks = vi.hoisted(() => ({
  findAdmission: vi.fn(),
  pinRollout: vi.fn(),
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

const SAFE_ENV: SyntheticQaProviderEnvironment = {
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: "postgresql:///meddoc_synthetic_test",
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
  practiceId: "practice-upload-synthetic",
  globalGeneration: BigInt(5),
  practiceGeneration: BigInt(11),
};
function admittedInput<T>(operation: (providerVisitId: string) => T) {
  return {
    admissionId: "admission-upload-synthetic",
    source: {
      sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
      sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
    },
    actor: {
      userId: "doctor-upload-synthetic",
      practiceId: TOKEN.practiceId,
      rolloutToken: TOKEN,
    },
    operation,
    env: SAFE_ENV,
  };
}

function admission() {
  return {
    id: "admission-upload-synthetic",
    practiceId: TOKEN.practiceId,
    actorId: "doctor-upload-synthetic",
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
  mocks.findAdmission.mockReset().mockResolvedValue(admission());
  mocks.pinRollout.mockReset().mockResolvedValue(TOKEN);
});

describe("staging fixture upload provider boundary", () => {
  it("enters deterministic ALS before draft compilation starts", async () => {
    const operation = vi.fn((providerVisitId: string) => {
      expect(providerVisitId).toMatch(
        /^template-twin-staging-admission-visit:/u,
      );
      expect(getTemplateTwinSyntheticQaProviderContext()).toMatchObject({
        visitId: providerVisitId,
        practiceId: TOKEN.practiceId,
        fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
        pinnedGlobalGeneration: TOKEN.globalGeneration,
        pinnedPracticeGeneration: TOKEN.practiceGeneration,
      });
      return providerVisitId;
    });

    await expect(
      runWithTemplateTwinStagingQaUploadProvider(admittedInput(operation)),
    ).resolves.toMatch(/^template-twin-staging-admission-visit:/u);
    expect(operation).toHaveBeenCalledTimes(1);
    expect(getTemplateTwinSyntheticQaProviderContext()).toBeNull();
  });

  it("blocks disabled resources before compilation or provider callbacks", async () => {
    const operation = vi.fn();
    await expect(
      runWithTemplateTwinStagingQaUploadProvider({
        ...admittedInput(operation),
        env: { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENABLED: "false" },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaUploadProviderError);
    expect(mocks.pinRollout).not.toHaveBeenCalled();
    expect(operation).not.toHaveBeenCalled();
  });

  it("rejects a stale session generation before draft compilation", async () => {
    const operation = vi.fn();
    mocks.pinRollout.mockResolvedValue({
      ...TOKEN,
      practiceGeneration: TOKEN.practiceGeneration + BigInt(1),
    });
    await expect(
      runWithTemplateTwinStagingQaUploadProvider({
        ...admittedInput(operation),
        env: SAFE_ENV,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_UNAVAILABLE",
    });
    expect(operation).not.toHaveBeenCalled();
  });

  it("cannot fall through when process flags change after admission", async () => {
    const mutableEnv = { ...SAFE_ENV };
    const result = await runWithTemplateTwinStagingQaUploadProvider({
      ...admittedInput((providerVisitId) => {
        mutableEnv.TEMPLATE_TWIN_STAGING_QA_ENABLED = "false";
        mutableEnv.MOCK_AI_CALLS = "false";
        mutableEnv.MOCK_TEMPLATE_TWIN_E2E = "false";
        expect(getTemplateTwinSyntheticQaProviderContext()?.visitId).toBe(
          providerVisitId,
        );
        return "still-bounded";
      }),
      env: mutableEnv,
    });
    expect(result).toBe("still-bounded");
  });

  it("preserves final-claim revocation from draft creation", async () => {
    const rolloutChanged = Object.assign(
      new Error("Synthetic final rollout generation changed."),
      { code: "ROLLOUT_CHANGED" },
    );
    await expect(
      runWithTemplateTwinStagingQaUploadProvider(
        admittedInput(() => {
          expect(getTemplateTwinSyntheticQaProviderContext()).not.toBeNull();
          throw rolloutChanged;
        }),
      ),
    ).rejects.toBe(rolloutChanged);
  });

  it("never admits an arbitrary source", async () => {
    const operation = vi.fn();
    await expect(
      runWithTemplateTwinStagingQaUploadProvider({
        ...admittedInput(operation),
        source: { sha256: "f".repeat(64), sizeBytes: 4_686 },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaUploadProviderError);
    expect(operation).not.toHaveBeenCalled();
  });
});
