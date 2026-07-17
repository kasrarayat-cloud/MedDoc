import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { deepgramBatchTranscribe } from "../deepgram-batch";
import { modelClient } from "../model-client";
import {
  __setOpenAIClientForTests,
  whisperBatchTranscribe,
} from "../whisper-batch";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  assertTemplateTwinSyntheticQaProviderEnvironment,
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  deriveTemplateTwinSyntheticQaEvidenceClaims,
  getTemplateTwinSyntheticQaProviderContext,
  markTemplateTwinSyntheticQaWorkerLeaseUnhealthy,
  runWithTemplateTwinSyntheticQaProviderContext,
  syntheticQaFixtureForProviderCall,
  type SyntheticQaProviderEnvironment,
  type TemplateTwinSyntheticQaProviderContextInput,
} from "../synthetic-qa-context";

vi.mock("@meddoc/db", () => ({ default: {}, prisma: {} }));

const ORIGINAL_ENV = { ...process.env };
const SAFE_ENV: SyntheticQaProviderEnvironment = {
  NODE_ENV: "production",
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
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
};

const EntitySchema = z.object({
  chief_complaint: z
    .object({ statement: z.string(), evidence_quote: z.string() })
    .nullable(),
  hpi: z
    .object({
      onset: z.string().optional(),
      severity: z.string().optional(),
      context: z.string().optional(),
      evidence_quote: z.string(),
    })
    .nullable(),
  medications: z
    .array(z.object({ name: z.string(), evidence_quote: z.string() }))
    .default([]),
  social_history: z
    .object({
      smoking: z
        .object({ status: z.string(), evidence_quote: z.string() })
        .optional(),
    })
    .default({}),
  plan_discussed: z
    .array(z.object({ item: z.string(), evidence_quote: z.string() }))
    .default([]),
  assessment_discussed: z
    .array(z.object({ finding: z.string(), evidence_quote: z.string() }))
    .default([]),
});

function context(
  overrides: Partial<TemplateTwinSyntheticQaProviderContextInput> = {},
): TemplateTwinSyntheticQaProviderContextInput {
  return {
    mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    runId: "synthetic-run-1",
    visitId: "synthetic-visit-1",
    practiceId: "synthetic-practice-1",
    requestSha256: "a".repeat(64),
    attempt: 1,
    workerClaimId: "11111111-1111-4111-8111-111111111111",
    pinnedGlobalGeneration: BigInt(3),
    pinnedPracticeGeneration: BigInt(7),
    evidenceText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
    ...overrides,
  };
}

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
  delete process.env.MOCK_AI_CALLS;
  delete process.env.MOCK_TEMPLATE_TWIN_E2E;
});

afterEach(() => {
  __setOpenAIClientForTests(null);
  vi.unstubAllGlobals();
  process.env = { ...ORIGINAL_ENV };
});

describe("Template Twin synthetic QA provider environment", () => {
  it("admits an optimized QA image only with every explicit safe boundary", () => {
    expect(() =>
      assertTemplateTwinSyntheticQaProviderEnvironment(SAFE_ENV),
    ).not.toThrow();
  });

  it.each([
    [
      "missing enable flag",
      { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENABLED: undefined },
      "SYNTHETIC_QA_DISABLED",
    ],
    [
      "non-exact enable flag",
      { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENABLED: "TRUE" },
      "SYNTHETIC_QA_DISABLED",
    ],
    [
      "missing staging environment",
      { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: undefined },
      "SYNTHETIC_QA_ENVIRONMENT_UNSAFE",
    ],
    [
      "production staging environment",
      { ...SAFE_ENV, TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "production" },
      "SYNTHETIC_QA_ENVIRONMENT_UNSAFE",
    ],
    [
      "explicit production storage profile",
      { ...SAFE_ENV, TEMPLATE_TWIN_STORAGE_PROFILE: "production" },
      "SYNTHETIC_QA_ENVIRONMENT_UNSAFE",
    ],
    [
      "production database",
      { ...SAFE_ENV, DATABASE_URL: "postgresql:///meddoc" },
      "SYNTHETIC_QA_DATABASE_UNSAFE",
    ],
    [
      "safe token only in username",
      { ...SAFE_ENV, DATABASE_URL: "postgresql://qa@db/meddoc" },
      "SYNTHETIC_QA_DATABASE_UNSAFE",
    ],
    [
      "non-PostgreSQL database URL",
      { ...SAFE_ENV, DATABASE_URL: "file:///meddoc_synthetic_test" },
      "SYNTHETIC_QA_DATABASE_UNSAFE",
    ],
    [
      "missing disposable-resource attestation",
      {
        ...SAFE_ENV,
        TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: undefined,
      },
      "SYNTHETIC_QA_RESOURCE_ATTESTATION_UNSAFE",
    ],
    [
      "shared Redis database zero",
      { ...SAFE_ENV, REDIS_URL: "redis://redis:6379/0" },
      "SYNTHETIC_QA_REDIS_UNSAFE",
    ],
    [
      "production-named Redis endpoint",
      { ...SAFE_ENV, REDIS_URL: "redis://cache.internal:6379/15" },
      "SYNTHETIC_QA_REDIS_UNSAFE",
    ],
    [
      "unmarked audio bucket",
      { ...SAFE_ENV, TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio" },
      "SYNTHETIC_QA_OBJECT_STORAGE_UNSAFE",
    ],
    [
      "remote object store without TLS",
      {
        ...SAFE_ENV,
        MINIO_ENDPOINT: "minio-qa.synthetic.test:9000",
        MINIO_USE_SSL: "false",
      },
      "SYNTHETIC_QA_OBJECT_STORAGE_UNSAFE",
    ],
    [
      "live provider fallback enabled",
      { ...SAFE_ENV, MOCK_AI_CALLS: "false" },
      "SYNTHETIC_QA_MOCK_PROVIDER_DISABLED",
    ],
  ])("fails closed for %s", (_label, env, code) => {
    expect(() =>
      assertTemplateTwinSyntheticQaProviderEnvironment(env),
    ).toThrowError(expect.objectContaining({ code }));
  });
});

describe("AsyncLocalStorage-scoped provider selection", () => {
  it("does not mutate process environment and closes after the callback", async () => {
    const before = { ...process.env };
    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      async () => {
        expect(getTemplateTwinSyntheticQaProviderContext()).toMatchObject({
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });
      },
      SAFE_ENV,
    );

    expect(process.env).toEqual(before);
    expect(getTemplateTwinSyntheticQaProviderContext()).toBeNull();
  });

  it("fences terminal work after a durable worker lease renewal failure", async () => {
    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      async () => {
        expect(() =>
          assertTemplateTwinSyntheticQaWorkerLeaseHealthy(),
        ).not.toThrow();
        markTemplateTwinSyntheticQaWorkerLeaseUnhealthy();
        expect(() =>
          assertTemplateTwinSyntheticQaWorkerLeaseHealthy(),
        ).toThrowError(
          expect.objectContaining({
            code: "SYNTHETIC_QA_WORKER_LEASE_UNHEALTHY",
          }),
        );
      },
      SAFE_ENV,
    );

    // The fence is visit-context scoped and never affects ordinary work.
    expect(() =>
      assertTemplateTwinSyntheticQaWorkerLeaseHealthy(),
    ).not.toThrow();
  });

  it("isolates concurrent visits without process-global toggles", async () => {
    let arrivals = 0;
    let release!: () => void;
    const barrier = new Promise<void>((resolve) => {
      release = resolve;
    });

    async function run(visitId: string): Promise<string> {
      return runWithTemplateTwinSyntheticQaProviderContext(
        context({ runId: `run-${visitId}`, visitId }),
        async () => {
          arrivals += 1;
          if (arrivals === 2) release();
          await barrier;
          await Promise.resolve();
          return getTemplateTwinSyntheticQaProviderContext()?.visitId ?? "";
        },
        SAFE_ENV,
      );
    }

    await expect(
      Promise.all([run("synthetic-visit-a"), run("synthetic-visit-b")]),
    ).resolves.toEqual(["synthetic-visit-a", "synthetic-visit-b"]);
  });

  it("rejects nested contexts", async () => {
    await expect(
      runWithTemplateTwinSyntheticQaProviderContext(
        context(),
        () =>
          runWithTemplateTwinSyntheticQaProviderContext(
            context({ runId: "nested-run" }),
            () => undefined,
            SAFE_ENV,
          ),
        SAFE_ENV,
      ),
    ).rejects.toMatchObject({ code: "SYNTHETIC_QA_CONTEXT_NESTED" });
  });

  it("closes detached async resources after the admitted attempt settles", async () => {
    let inspectDetached!: () => void;
    const detached = new Promise<unknown>((resolve) => {
      inspectDetached = () => {
        try {
          resolve(getTemplateTwinSyntheticQaProviderContext());
        } catch (error) {
          resolve(error);
        }
      };
    });

    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      () => {
        setImmediate(inspectDetached);
      },
      SAFE_ENV,
    );

    await expect(detached).resolves.toMatchObject({
      code: "SYNTHETIC_QA_CONTEXT_CLOSED",
    });
  });

  it("throws instead of falling back live for another visit or practice", async () => {
    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      () => {
        expect(() =>
          syntheticQaFixtureForProviderCall({
            visitId: "normal-visit",
            practiceId: "synthetic-practice-1",
          }),
        ).toThrowError(
          expect.objectContaining({ code: "SYNTHETIC_QA_VISIT_MISMATCH" }),
        );
        expect(() =>
          syntheticQaFixtureForProviderCall({
            visitId: "synthetic-visit-1",
            practiceId: "other-practice",
          }),
        ).toThrowError(
          expect.objectContaining({ code: "SYNTHETIC_QA_PRACTICE_MISMATCH" }),
        );
      },
      SAFE_ENV,
    );
  });

  it("rejects unsupported fixture metadata before entering the callback", async () => {
    let called = false;
    await expect(
      runWithTemplateTwinSyntheticQaProviderContext(
        {
          ...context(),
          fixtureVersion:
            "future-fixture" as TemplateTwinSyntheticQaProviderContextInput["fixtureVersion"],
        },
        () => {
          called = true;
        },
        SAFE_ENV,
      ),
    ).rejects.toMatchObject({ code: "SYNTHETIC_QA_CONTEXT_INVALID" });
    expect(called).toBe(false);
  });

  it("rejects empty or oversized evidence admission without retaining raw text", async () => {
    for (const evidenceText of ["", "x".repeat(5_001)]) {
      await expect(
        runWithTemplateTwinSyntheticQaProviderContext(
          context({ evidenceText }),
          () => undefined,
          SAFE_ENV,
        ),
      ).rejects.toMatchObject({ code: "SYNTHETIC_QA_CONTEXT_INVALID" });
    }

    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      () => {
        const admitted = getTemplateTwinSyntheticQaProviderContext();
        expect(admitted).not.toHaveProperty("evidenceText");
        expect(admitted?.evidenceSha256).toMatch(/^[a-f0-9]{64}$/u);
      },
      SAFE_ENV,
    );
  });
});

describe("exact synthetic evidence projection", () => {
  it("returns no claims for unrelated or merely partial typed text", () => {
    expect(
      deriveTemplateTwinSyntheticQaEvidenceClaims(
        "Unrelated synthetic follow-up text with no reviewed sentence.",
      ),
    ).toEqual([]);
    expect(
      deriveTemplateTwinSyntheticQaEvidenceClaims(
        "Medication Syntheticmed docu",
      ),
    ).toEqual([]);
  });

  it("projects only complete exact evidence sentences", () => {
    expect(
      deriveTemplateTwinSyntheticQaEvidenceClaims(
        "Chief concern is synthetic wrist discomfort. Plan use synthetic brace.",
      ),
    ).toEqual(["chief_complaint", "plan"]);
    expect(
      deriveTemplateTwinSyntheticQaEvidenceClaims(
        "Chief concern is synthetic wrist discomfort. Plan use synthetic brace. Extra synthetic text.",
      ),
    ).toEqual([]);
  });
});

describe("modelClient and Deepgram integration", () => {
  it("selects evidence-bearing structured and text fixtures only in the admitted visit context", async () => {
    // Deliberately make the legacy global seam ineligible. The explicit
    // AsyncLocal fixture still wins without changing process environment.
    process.env.MOCK_AI_CALLS = "false";
    process.env.MOCK_TEMPLATE_TWIN_E2E = "true";
    process.env.DATABASE_URL = "postgresql:///meddoc";
    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      async () => {
        const entities = await modelClient.complete({
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
          schema: EntitySchema,
          purpose: "tm_entities",
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });
        const soap = await modelClient.completeText({
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
          purpose: "tm_soap_draft",
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });

        expect(entities.medications).toEqual([
          expect.objectContaining({ name: "Syntheticmed" }),
        ]);
        expect(entities.hpi).toMatchObject({
          onset: "2099-07-16",
          severity: "Moderate",
          context: "Explicit synthetic detail",
        });
        expect(entities.assessment_discussed).toEqual([
          expect.objectContaining({ finding: "Follow-up" }),
        ]);
        expect(soap.text).toContain("Syntheticmed");
      },
      SAFE_ENV,
    );
  });

  it("rejects unrelated typed evidence before any provider fixture can run", async () => {
    let providerCalled = false;
    await expect(
      runWithTemplateTwinSyntheticQaProviderContext(
        context({
          evidenceText:
            "Unrelated synthetic encounter text with no reviewed evidence sentence.",
        }),
        () => {
          providerCalled = true;
        },
        SAFE_ENV,
      ),
    ).rejects.toMatchObject({ code: "SYNTHETIC_QA_CONTEXT_INVALID" });
    expect(providerCalled).toBe(false);
  });

  it("emits only claims admitted by complete partial typed evidence", async () => {
    await runWithTemplateTwinSyntheticQaProviderContext(
      context({ evidenceText: "Chief concern is synthetic wrist discomfort." }),
      async () => {
        const entities = await modelClient.complete({
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: "Chief concern is synthetic wrist discomfort.",
          schema: EntitySchema,
          purpose: "tm_entities",
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });
        const soap = await modelClient.completeText({
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: "Chief concern is synthetic wrist discomfort.",
          purpose: "tm_soap_draft",
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });

        expect(entities.chief_complaint).toMatchObject({
          statement: "synthetic wrist discomfort",
        });
        expect(entities.medications).toEqual([]);
        expect(soap.text).toContain(
          "Chief concern is synthetic wrist discomfort.",
        );
        expect(soap.text).not.toContain("Syntheticmed");
        expect(soap.text).not.toContain("Follow-up");
      },
      SAFE_ENV,
    );
  });

  it("uses the existing Deepgram entrypoint without reading audio or making a network call", async () => {
    const fetchSpy = vi.fn().mockRejectedValue(new Error("must not be called"));
    vi.stubGlobal("fetch", fetchSpy);
    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      async () => {
        const result = await deepgramBatchTranscribe({
          audio: Buffer.from("synthetic-audio-placeholder"),
          mimeType: "audio/wav",
          purpose: "tm_transcribe",
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });

        expect(result.transcript).toContain("Syntheticmed");
        expect(result.raw.metadata?.request_id).toBe(
          "mock-template-twin-deepgram-request",
        );
      },
      SAFE_ENV,
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("keeps the Whisper fallback boundary synthetic with zero OpenAI calls", async () => {
    const create = vi.fn().mockRejectedValue(new Error("must not be called"));
    __setOpenAIClientForTests({
      audio: { transcriptions: { create } },
    } as never);

    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      async () => {
        const result = await whisperBatchTranscribe({
          audio: Buffer.from("synthetic-audio-placeholder"),
          mimeType: "audio/wav",
          purpose: "tm_transcribe",
          visitId: "synthetic-visit-1",
          practiceId: "synthetic-practice-1",
        });
        expect(result.transcript).toBe(TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT);
        expect(result.costCents).toBe(0);
      },
      SAFE_ENV,
    );
    expect(create).not.toHaveBeenCalled();
  });

  it("blocks mismatched Deepgram and Whisper calls before either network boundary", async () => {
    const fetchSpy = vi.fn().mockRejectedValue(new Error("must not be called"));
    const create = vi.fn().mockRejectedValue(new Error("must not be called"));
    vi.stubGlobal("fetch", fetchSpy);
    __setOpenAIClientForTests({
      audio: { transcriptions: { create } },
    } as never);

    await runWithTemplateTwinSyntheticQaProviderContext(
      context(),
      async () => {
        await expect(
          deepgramBatchTranscribe({
            audio: Buffer.from("synthetic-audio-placeholder"),
            mimeType: "audio/wav",
            purpose: "tm_transcribe",
            visitId: "other-visit",
            practiceId: "synthetic-practice-1",
          }),
        ).rejects.toMatchObject({ code: "SYNTHETIC_QA_VISIT_MISMATCH" });
        await expect(
          whisperBatchTranscribe({
            audio: Buffer.from("synthetic-audio-placeholder"),
            mimeType: "audio/wav",
            purpose: "tm_transcribe",
            visitId: "synthetic-visit-1",
            practiceId: "other-practice",
          }),
        ).rejects.toMatchObject({ code: "SYNTHETIC_QA_PRACTICE_MISMATCH" });
      },
      SAFE_ENV,
    );

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(create).not.toHaveBeenCalled();
  });

  it("keeps a normal visit on the generic mock fixture, never the staging fixture", async () => {
    process.env.MOCK_AI_CALLS = "true";
    process.env.MOCK_TEMPLATE_TWIN_E2E = "true";
    process.env.DATABASE_URL = "postgresql:///meddoc_synthetic_test";

    const entities = await modelClient.complete({
      provider: "anthropic",
      model: "synthetic-model",
      system: "synthetic system",
      user: "synthetic encounter",
      schema: EntitySchema,
      purpose: "tm_entities",
      visitId: "normal-visit",
      practiceId: "normal-practice",
    });
    const transcription = await deepgramBatchTranscribe({
      audio: Buffer.from("synthetic-audio-placeholder"),
      mimeType: "audio/wav",
      purpose: "tm_transcribe",
      visitId: "normal-visit",
      practiceId: "normal-practice",
    });

    expect(entities.medications).toEqual([]);
    expect(transcription.transcript).toContain("head has been aching");
    expect(transcription.transcript).not.toContain("Syntheticmed");
  });

  it("fails closed at the provider boundary when a normal visit is called inside the context", async () => {
    await expect(
      runWithTemplateTwinSyntheticQaProviderContext(
        context(),
        () =>
          modelClient.complete({
            provider: "anthropic",
            model: "synthetic-model",
            system: "synthetic system",
            user: "synthetic encounter",
            schema: EntitySchema,
            purpose: "tm_entities",
            visitId: "normal-visit",
            practiceId: "synthetic-practice-1",
          }),
        SAFE_ENV,
      ),
    ).rejects.toMatchObject({ code: "SYNTHETIC_QA_VISIT_MISMATCH" });
  });
});
