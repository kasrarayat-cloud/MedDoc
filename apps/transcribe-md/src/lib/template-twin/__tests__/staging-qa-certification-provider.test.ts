import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  getTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixtures";
import {
  TemplateTwinStagingQaCertificationProviderError,
  runWithTemplateTwinStagingQaCertificationProvider,
} from "../staging-qa-certification-provider";

const mocks = vi.hoisted(() => ({
  findTemplate: vi.fn(),
  findAdmission: vi.fn(),
  pinRollout: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    noteTemplate: { findFirst: mocks.findTemplate },
    templateTwinSyntheticQaAdmission: { findFirst: mocks.findAdmission },
  },
}));
vi.mock("../rollout", async (importOriginal) => ({
  ...((await importOriginal()) as typeof import("../rollout")),
  pinTemplateTwinRollout: mocks.pinRollout,
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
  practiceId: "practice-certification-synthetic",
  globalGeneration: BigInt(7),
  practiceGeneration: BigInt(13),
};

type PinRollout = (input: {
  practiceId: string;
  env?: Readonly<Record<string, string | undefined>>;
}) => Promise<typeof TOKEN>;

function matchingPin() {
  return vi.fn<PinRollout>().mockResolvedValue(TOKEN);
}

function exactSource() {
  return {
    sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
    sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
  };
}

function admission() {
  return {
    id: "admission-certification-synthetic",
    practiceId: TOKEN.practiceId,
    actorId: "doctor-certification-synthetic",
    parentAdmissionId: null,
    sourceSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
    sourceSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    providerMode: "SYNTHETIC_LIFECYCLE",
    purpose: "UPLOAD",
    phase: "TEMPLATE_LINKED",
    requestSha256: "a".repeat(64),
    payloadSha256: null,
    pinnedGlobalRolloutGeneration: TOKEN.globalGeneration,
    pinnedPracticeRolloutGeneration: TOKEN.practiceGeneration,
    sourceArtifactId: "source-certification-synthetic",
    noteTemplateId: "template-certification-synthetic",
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

beforeEach(() => {
  const admitted = admission();
  mocks.pinRollout.mockReset().mockResolvedValue(TOKEN);
  mocks.findAdmission.mockReset().mockResolvedValue(admitted);
  mocks.findTemplate.mockReset().mockResolvedValue({
    templateTwinCompiledVersion: {
      sourceArtifact: {
        practiceId: TOKEN.practiceId,
        ...exactSource(),
      },
    },
    templateTwinSyntheticQaAdmissions: [admitted],
  });
});

function input(
  encounterMode: "text" | "dictation",
  operation: (providerVisitId: string | null) => unknown,
  overrides: {
    env?: SyntheticQaProviderEnvironment;
    pinRollout?: PinRollout;
    confirmMappings?: () => Promise<boolean>;
  } = {},
) {
  return {
    source: exactSource(),
    noteTemplateId: "template-certification-synthetic",
    doctorId: "doctor-certification-synthetic",
    practiceId: TOKEN.practiceId,
    rolloutToken: TOKEN,
    encounterMode,
    evidenceText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
    operation,
    dependencies: {
      env: overrides.env ?? SAFE_ENV,
      pinRollout: overrides.pinRollout ?? matchingPin(),
      confirmMappings:
        overrides.confirmMappings ?? vi.fn().mockResolvedValue(true),
    },
  };
}

describe("staging fixture certification provider boundary", () => {
  it.each(["text", "dictation"] as const)(
    "forces %s certification calls into the exact deterministic provider context",
    async (encounterMode) => {
      const order: string[] = [];
      const pinRollout = vi.fn<PinRollout>().mockImplementation(async () => {
        order.push("rollout-gate");
        return TOKEN;
      });
      const confirmMappings = vi.fn().mockImplementation(async () => {
        order.push("mapping-confirmation");
        return true;
      });
      const result = await runWithTemplateTwinStagingQaCertificationProvider(
        input(
          encounterMode,
          (providerVisitId) => {
            order.push("provider-call");
            expect(providerVisitId).toMatch(
              /^template-twin-staging-admission-visit:/u,
            );
            const context = getTemplateTwinSyntheticQaProviderContext();
            expect(context).toMatchObject({
              visitId: providerVisitId,
              practiceId: TOKEN.practiceId,
              fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
            });
            return context?.fixtureVersion;
          },
          { pinRollout, confirmMappings },
        ),
      );

      expect(result).toBe(TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION);
      expect(order).toEqual([
        "mapping-confirmation",
        "rollout-gate",
        "provider-call",
      ]);
    },
  );

  it("rejects a revoked staging process before typed or voice provider callbacks", async () => {
    const pinRollout = matchingPin();
    const typedProvider = vi.fn();
    const voiceProvider = vi.fn();
    const revokedEnv = {
      ...SAFE_ENV,
      TEMPLATE_TWIN_STAGING_QA_ENABLED: "false",
    };

    await expect(
      runWithTemplateTwinStagingQaCertificationProvider(
        input("text", typedProvider, { env: revokedEnv, pinRollout }),
      ),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaCertificationProviderError);
    await expect(
      runWithTemplateTwinStagingQaCertificationProvider(
        input("dictation", voiceProvider, { env: revokedEnv, pinRollout }),
      ),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaCertificationProviderError);

    expect(pinRollout).not.toHaveBeenCalled();
    expect(typedProvider).not.toHaveBeenCalled();
    expect(voiceProvider).not.toHaveBeenCalled();
  });

  it("rejects incomplete mappings before process, resource, or rollout admission", async () => {
    const provider = vi.fn();
    const pinRollout = matchingPin();
    const confirmMappings = vi.fn().mockResolvedValue(false);

    await expect(
      runWithTemplateTwinStagingQaCertificationProvider(
        input("text", provider, { confirmMappings, pinRollout }),
      ),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaCertificationProviderError);
    expect(confirmMappings).toHaveBeenCalledTimes(1);
    expect(pinRollout).not.toHaveBeenCalled();
    expect(provider).not.toHaveBeenCalled();
  });

  it("rejects a stale rollout generation before invoking the provider", async () => {
    const provider = vi.fn();
    const pinRollout = vi.fn<PinRollout>().mockResolvedValue({
      ...TOKEN,
      practiceGeneration: TOKEN.practiceGeneration + BigInt(1),
    });

    await expect(
      runWithTemplateTwinStagingQaCertificationProvider(
        input("text", provider, { pinRollout }),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_PROVIDER_UNAVAILABLE",
      message: "Template Twin synthetic QA is unavailable.",
    });
    expect(pinRollout).toHaveBeenCalledTimes(1);
    expect(provider).not.toHaveBeenCalled();
  });

  it("cannot fall through to a live provider if process flags change after admission", async () => {
    const mutableEnv = { ...SAFE_ENV };
    const result = await runWithTemplateTwinStagingQaCertificationProvider(
      input(
        "dictation",
        (providerVisitId) => {
          mutableEnv.MOCK_AI_CALLS = "false";
          mutableEnv.MOCK_TEMPLATE_TWIN_E2E = "false";
          mutableEnv.TEMPLATE_TWIN_STAGING_QA_ENABLED = "false";
          const context = getTemplateTwinSyntheticQaProviderContext();
          expect(context).toMatchObject({
            visitId: providerVisitId,
            practiceId: TOKEN.practiceId,
          });
          return context?.fixtureVersion;
        },
        { env: mutableEnv },
      ),
    );

    expect(result).toBe(TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION);
  });

  it("leaves ordinary source artifacts on the existing generic path", async () => {
    const pinRollout = matchingPin();
    const operation = vi.fn().mockResolvedValue("generic");

    await expect(
      runWithTemplateTwinStagingQaCertificationProvider({
        ...input("text", operation, { pinRollout }),
        source: { sha256: "f".repeat(64), sizeBytes: 4_686 },
      }),
    ).resolves.toBe("generic");
    expect(operation).toHaveBeenCalledWith(null);
    expect(pinRollout).not.toHaveBeenCalled();
  });
});
