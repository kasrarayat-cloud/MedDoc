import { createHash } from "node:crypto";

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  type TranscribeArgs,
  type TranscribeResult,
} from "@meddoc/ai";
import { runWithTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai/internal/synthetic-qa-context";
import { z } from "zod";

import {
  buildTemplateTwinProviderOwnershipReceipt,
  runTemplateTwinOwnedModelComplete,
  runTemplateTwinOwnedModelCompleteText,
  runTemplateTwinOwnedProvider,
  runTemplateTwinOwnedTranscribe,
  runWithTemplateTwinProviderOwnershipContext as runWithTemplateTwinProviderOwnershipContextRaw,
  TemplateTwinProviderOwnershipError,
  type TemplateTwinProviderOwnershipContext,
} from "../provider-ownership";
import { runWithTemplateTwinProviderCensus } from "../provider-census";
import { TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT } from "../staging-qa-fixtures";

interface StoredRow extends Record<string, unknown> {
  id: string;
  ownershipKey: string;
  idempotencyKey: string;
  status: string;
  invocationCount: number;
  claimId: string | null;
  resultPayload: unknown;
  resultSha256: string | null;
  resultVersion: string | null;
}

function whereMatches(row: StoredRow, where: Record<string, unknown>): boolean {
  return Object.entries(where).every(([key, value]) => row[key] === value);
}

class MemoryProviderDatabase {
  readonly rows = new Map<string, StoredRow>();
  throwAfterSuccessfulCompletion = false;

  readonly templateTwinProviderExecution = {
    create: async (raw: unknown): Promise<StoredRow> => {
      const args = raw as { data: Record<string, unknown> };
      const duplicate = [...this.rows.values()].find(
        (row) =>
          row.ownershipKey === args.data.ownershipKey ||
          row.idempotencyKey === args.data.idempotencyKey,
      );
      if (duplicate) {
        throw Object.assign(new Error("synthetic unique conflict"), {
          code: "P2002",
        });
      }
      const row = {
        ...args.data,
        status: "RESERVED",
        invocationCount: 0,
        claimId: null,
        resultPayload: null,
        resultSha256: null,
        resultVersion: null,
      } as StoredRow;
      this.rows.set(row.id, row);
      return { ...row };
    },
    findUnique: async (raw: unknown): Promise<StoredRow | null> => {
      const args = raw as { where: Record<string, unknown> };
      const row = [...this.rows.values()].find((candidate) =>
        whereMatches(candidate, args.where),
      );
      return row ? { ...row } : null;
    },
    updateMany: async (raw: unknown): Promise<{ count: number }> => {
      const args = raw as {
        where: Record<string, unknown>;
        data: Record<string, unknown>;
      };
      const row = [...this.rows.values()].find((candidate) =>
        whereMatches(candidate, args.where),
      );
      if (!row) return { count: 0 };
      Object.assign(row, args.data);
      return { count: 1 };
    },
  };

  async $queryRaw<T>(): Promise<T> {
    return [] as T;
  }

  async $transaction<T>(
    callback: (tx: MemoryProviderDatabase) => Promise<T>,
  ): Promise<T> {
    const result = await callback(this);
    if (
      this.throwAfterSuccessfulCompletion &&
      [...this.rows.values()].some((row) => row.status === "SUCCEEDED")
    ) {
      this.throwAfterSuccessfulCompletion = false;
      throw new Error("synthetic commit acknowledgement lost");
    }
    return result;
  }
}

const CONTEXT: TemplateTwinProviderOwnershipContext = {
  practiceId: "practice-provider-owner",
  actorUserId: "doctor-provider-owner",
  visitId: "visit-provider-owner",
  visitInputMode: "text_notes",
  scope: "VISIT_PIPELINE",
  logicalAttempt: 1,
  subjectId: "visit-provider-owner",
  subjectSha256: "1".repeat(64),
  sourceArtifactId: "source-provider-owner",
  compiledVersionId: "compiled-provider-owner",
  noteTemplateId: "template-provider-owner",
  noteTemplateVersion: 4,
  sourceLineageId: "lineage-provider-owner",
  sourceLineageVersion: 2,
  sourceSha256: "2".repeat(64),
  syntheticAdmissionId: null,
  rolloutToken: {
    practiceId: "practice-provider-owner",
    globalGeneration: BigInt(7),
    practiceGeneration: BigInt(9),
    releaseId: "77777777-7777-4777-8777-777777777777",
    releaseIdentitySha256: "3".repeat(64),
    runtimeManifestSha256: "4".repeat(64),
    runtimeInstanceId: "worker-provider-owner-1",
  },
};

const SYNTHETIC_AUDIO = Buffer.from("bounded synthetic voice audio", "utf8");
const SYNTHETIC_AUDIO_SHA256 = createHash("sha256")
  .update(SYNTHETIC_AUDIO)
  .digest("hex");
const SYNTHETIC_VOICE_CONTEXT: TemplateTwinProviderOwnershipContext = {
  ...CONTEXT,
  visitInputMode: "audio_upload",
  scope: "SYNTHETIC_EVIDENCE",
  subjectId: "synthetic-voice-admission-1",
  subjectSha256: "5".repeat(64),
  syntheticAdmissionId: "synthetic-voice-admission-1",
  rolloutToken: {
    practiceId: CONTEXT.practiceId,
    globalGeneration: BigInt(7),
    practiceGeneration: BigInt(9),
  },
};

const SAFE_SYNTHETIC_ENV = {
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
} as const;

function runWithSyntheticVoiceProviderOwnershipContext<T>(
  context: TemplateTwinProviderOwnershipContext,
  callback: () => Promise<T>,
): Promise<T> {
  return runWithTemplateTwinSyntheticQaProviderContext(
    {
      mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      admissionId: SYNTHETIC_VOICE_CONTEXT.syntheticAdmissionId!,
      runId: SYNTHETIC_VOICE_CONTEXT.syntheticAdmissionId!,
      visitId: SYNTHETIC_VOICE_CONTEXT.visitId!,
      practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
      requestSha256: "7".repeat(64),
      attempt: 1,
      workerClaimId: "11111111-1111-4111-8111-111111111111",
      pinnedGlobalGeneration:
        SYNTHETIC_VOICE_CONTEXT.rolloutToken.globalGeneration,
      pinnedPracticeGeneration:
        SYNTHETIC_VOICE_CONTEXT.rolloutToken.practiceGeneration,
      evidenceText: TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
    },
    () => runWithTemplateTwinProviderOwnershipContextRaw(context, callback),
    SAFE_SYNTHETIC_ENV,
  );
}

function syntheticVoiceTranscribeInput(
  transcriber: (args: TranscribeArgs) => Promise<TranscribeResult>,
) {
  return {
    operation: "SYNTHETIC_EVIDENCE_TRANSCRIPTION" as const,
    operationVersion: "synthetic-evidence-transcription-v1",
    audioIdentity: {
      objectKey: "template-twin-synthetic-voice/exact-audio",
      objectEtag: SYNTHETIC_AUDIO_SHA256,
      sha256: SYNTHETIC_AUDIO_SHA256,
      sizeBytes: SYNTHETIC_AUDIO.byteLength,
      lastModifiedIso: "2026-07-19T17:20:00.000Z",
    },
    transcriber,
    args: {
      practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
      userId: SYNTHETIC_VOICE_CONTEXT.actorUserId,
      visitId: SYNTHETIC_VOICE_CONTEXT.visitId!,
      purpose: "tm_transcribe" as const,
      audio: SYNTHETIC_AUDIO,
      mimeType: "audio/webm",
      allowCrossProviderFallback: false,
      deepgram: { maxAttempts: 1 as const },
    },
  };
}

function runWithTemplateTwinProviderOwnershipContext<T>(
  context: TemplateTwinProviderOwnershipContext,
  callback: () => Promise<T>,
): Promise<T> {
  if (context.scope !== "VISIT_PIPELINE") {
    return runWithTemplateTwinProviderOwnershipContextRaw(context, callback);
  }
  return runWithTemplateTwinProviderCensus(
    {
      classification: "TEMPLATE_TWIN",
      templateId: context.noteTemplateId!,
      templateVersion: context.noteTemplateVersion!,
    },
    () => runWithTemplateTwinProviderOwnershipContextRaw(context, callback),
  );
}

let sequence = 0;

function dependencies(
  database: MemoryProviderDatabase,
  input: {
    mode?: "LIVE" | "DETERMINISTIC_MOCK" | "SYNTHETIC_QA";
    rolloutCurrent?: boolean;
    authorityCurrent?: boolean | (() => boolean);
  } = {},
): NonNullable<Parameters<typeof runTemplateTwinOwnedProvider>[1]> {
  return {
    db: database,
    providerMode: () => input.mode ?? "DETERMINISTIC_MOCK",
    lockRollout: async () => input.rolloutCurrent ?? true,
    currentAuthority: async () =>
      typeof input.authorityCurrent === "function"
        ? input.authorityCurrent()
        : (input.authorityCurrent ?? true),
    executionId: () => `provider-execution-${++sequence}`,
    claimId: () => `${sequence.toString(16).padStart(64, "0")}`,
    now: () => new Date("2026-07-19T17:20:00.000Z"),
    sleep: (milliseconds: number) =>
      new Promise((resolve) => setTimeout(resolve, milliseconds)),
    terminalWaitMs: 250,
    pollMs: 1,
  } as unknown as NonNullable<
    Parameters<typeof runTemplateTwinOwnedProvider>[1]
  >;
}

function providerInput(invoke: () => Promise<{ facts: string[] }>) {
  return {
    operation: "L3_EXTRACT_ENTITIES" as const,
    operationVersion: "l3-provider-owner-v1",
    provider: "anthropic",
    model: "claude-synthetic-1",
    providerConfiguration: { temperature: 0, maxTokens: 512 },
    inputIdentity: {
      purpose: "tm_entities",
      evidence: "private synthetic input must never enter the receipt",
    },
    invoke,
    validate: (output: unknown) => {
      if (
        !output ||
        typeof output !== "object" ||
        !Array.isArray((output as { facts?: unknown }).facts)
      ) {
        throw new Error("invalid synthetic provider result");
      }
      return output as { facts: string[] };
    },
  };
}

async function errorCode(promise: Promise<unknown>): Promise<string | null> {
  try {
    await promise;
    return null;
  } catch (error) {
    return error instanceof TemplateTwinProviderOwnershipError
      ? error.code
      : "UNEXPECTED";
  }
}

beforeEach(() => {
  sequence = 0;
});

describe("Template Twin exact provider ownership runtime", () => {
  it("rejects synthetic-evidence transcription without an exact ownership context before egress", async () => {
    const transcriber = vi.fn(
      async (): Promise<TranscribeResult> => ({
        provider: "deepgram-batch",
        transcript: "must not egress",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram", data: {} as never },
      }),
    );

    await expect(
      runTemplateTwinOwnedTranscribe(
        syntheticVoiceTranscribeInput(transcriber),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    expect(transcriber).not.toHaveBeenCalled();
  });

  it("rejects every inexact synthetic voice scope, audio, and replay control before egress", async () => {
    const transcriber = vi.fn(
      async (): Promise<TranscribeResult> => ({
        provider: "deepgram-batch",
        transcript: "must not egress",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram", data: {} as never },
      }),
    );
    const cases = [
      {
        context: {
          ...SYNTHETIC_VOICE_CONTEXT,
          scope: "CUSTOM_EXAMPLE" as const,
        },
      },
      {
        context: {
          ...SYNTHETIC_VOICE_CONTEXT,
          visitInputMode: "text_notes",
        },
      },
      {
        context: { ...SYNTHETIC_VOICE_CONTEXT, logicalAttempt: 2 },
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          audioIdentity: { ...value.audioIdentity, sha256: "6".repeat(64) },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          audioIdentity: {
            ...value.audioIdentity,
            sizeBytes: value.audioIdentity.sizeBytes + 1,
          },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          args: { ...value.args, audio: "not-a-buffer" as never },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          args: { ...value.args, allowCrossProviderFallback: true },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          args: { ...value.args, deepgram: { maxAttempts: 2 as const } },
        }),
      },
    ];

    for (const item of cases) {
      const exact = syntheticVoiceTranscribeInput(transcriber);
      const candidate = item.mutate ? item.mutate(exact) : exact;
      await expect(
        runWithSyntheticVoiceProviderOwnershipContext(item.context, () =>
          runTemplateTwinOwnedTranscribe(candidate),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
      });
    }
    expect(transcriber).not.toHaveBeenCalled();
  });

  it("permits one exact synthetic mock transcription and rejects non-Deepgram or fallback results", async () => {
    const exactResult: TranscribeResult = {
      provider: "deepgram-batch",
      transcript: "exact synthetic voice transcript",
      durationSec: 1,
      language: "en",
      costCents: 0,
      fallbackUsed: false,
      raw: { kind: "deepgram", data: {} as never },
    };
    const database = new MemoryProviderDatabase();
    const transcriber = vi.fn(async (args: TranscribeArgs) => {
      void args;
      return exactResult;
    });

    await expect(
      runWithSyntheticVoiceProviderOwnershipContext(
        SYNTHETIC_VOICE_CONTEXT,
        () =>
          runTemplateTwinOwnedTranscribe({
            ...syntheticVoiceTranscribeInput(transcriber),
            dependencies: dependencies(database, { mode: "SYNTHETIC_QA" }),
          }),
      ),
    ).resolves.toEqual(exactResult);
    expect(transcriber).toHaveBeenCalledOnce();
    expect(transcriber.mock.calls[0]?.[0]).toMatchObject({
      allowCrossProviderFallback: false,
      deepgram: { maxAttempts: 1 },
    });

    for (const invalid of [
      { ...exactResult, provider: "whisper" },
      { ...exactResult, fallbackUsed: true },
      { ...exactResult, raw: { kind: "whisper", data: {} } },
    ] as TranscribeResult[]) {
      const invalidDatabase = new MemoryProviderDatabase();
      const invalidTranscriber = vi.fn(async () => invalid);
      await expect(
        runWithSyntheticVoiceProviderOwnershipContext(
          SYNTHETIC_VOICE_CONTEXT,
          () =>
            runTemplateTwinOwnedTranscribe({
              ...syntheticVoiceTranscribeInput(invalidTranscriber),
              dependencies: dependencies(invalidDatabase, {
                mode: "SYNTHETIC_QA",
              }),
            }),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED",
      });
      expect(invalidTranscriber).toHaveBeenCalledOnce();
      expect([...invalidDatabase.rows.values()][0]).toMatchObject({
        status: "FAILED",
        resultPayload: null,
      });
    }
  });

  it("rejects synthetic-evidence transcription in LIVE or deterministic mode before egress", async () => {
    for (const mode of ["LIVE", "DETERMINISTIC_MOCK"] as const) {
      const database = new MemoryProviderDatabase();
      const transcriber = vi.fn(
        async (): Promise<TranscribeResult> => ({
          provider: "deepgram-batch",
          transcript: "must not egress",
          durationSec: 1,
          language: "en",
          costCents: 0,
          fallbackUsed: false,
          raw: { kind: "deepgram", data: {} as never },
        }),
      );
      await expect(
        runWithSyntheticVoiceProviderOwnershipContext(
          SYNTHETIC_VOICE_CONTEXT,
          () =>
            runTemplateTwinOwnedTranscribe({
              ...syntheticVoiceTranscribeInput(transcriber),
              dependencies: dependencies(database, { mode }),
            }),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
      });
      expect(transcriber).not.toHaveBeenCalled();
      expect(database.rows.size).toBe(0);
    }
  });

  it("leaves an ordinary provider call unchanged when no Twin context exists", async () => {
    const invoke = vi.fn(async (claim: { idempotencyKey?: string }) => ({
      facts: [claim.idempotencyKey ?? "ordinary"],
    }));

    const result = await runTemplateTwinOwnedProvider({
      ...providerInput(() => invoke({})),
      invoke,
    });

    expect(result).toEqual({ facts: ["ordinary"] });
    expect(invoke).toHaveBeenCalledOnce();
    expect(invoke).toHaveBeenCalledWith({});
  });

  it("blocks every direct wrapper when the pre-L1 census requires a Twin owner", async () => {
    const genericInvoke = vi.fn(async () => ({ facts: ["must not egress"] }));
    const completeText = vi.fn(async () => ({
      text: "must not egress",
      inputTokens: 1,
      outputTokens: 1,
    }));
    const complete = vi.fn(async () => ({ value: "must not egress" }));
    const transcriber = vi.fn(
      async (): Promise<TranscribeResult> => ({
        provider: "deepgram-batch",
        transcript: "must not egress",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram", data: {} as never },
      }),
    );

    await runWithTemplateTwinProviderCensus(
      {
        classification: "TEMPLATE_TWIN",
        templateId: CONTEXT.noteTemplateId!,
        templateVersion: CONTEXT.noteTemplateVersion!,
      },
      async () => {
        await expect(
          runTemplateTwinOwnedProvider(providerInput(genericInvoke)),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
        await expect(
          runTemplateTwinOwnedModelComplete({
            operation: "SYNTHETIC_EVIDENCE_EXTRACTION",
            operationVersion: "synthetic-direct-wrapper-v1",
            args: {
              practiceId: CONTEXT.practiceId,
              userId: CONTEXT.actorUserId,
              visitId: CONTEXT.visitId,
              purpose: "tm_entities",
              provider: "anthropic",
              model: "claude-synthetic-1",
              system: "synthetic",
              user: "synthetic",
              schema: z.object({ value: z.string() }),
            },
            client: { complete: complete as never },
          }),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
        await expect(
          runTemplateTwinOwnedModelCompleteText({
            operation: "SYNTHETIC_EVIDENCE_EXTRACTION",
            operationVersion: "synthetic-direct-wrapper-v1",
            args: {
              practiceId: CONTEXT.practiceId,
              userId: CONTEXT.actorUserId,
              visitId: CONTEXT.visitId,
              purpose: "tm_template_synthetic_phi_scan",
              provider: "anthropic",
              model: "claude-synthetic-1",
              system: "synthetic",
              user: "synthetic",
            },
            client: { completeText },
          }),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
        await expect(
          runTemplateTwinOwnedTranscribe({
            operation: "L1_TRANSCRIBE",
            operationVersion: "synthetic-direct-wrapper-v1",
            audioIdentity: {
              objectKey: "synthetic/audio.webm",
              objectEtag: "synthetic-etag",
              sizeBytes: 32,
              lastModifiedIso: null,
            },
            args: {
              practiceId: CONTEXT.practiceId,
              userId: CONTEXT.actorUserId,
              visitId: CONTEXT.visitId,
              purpose: "tm_transcribe",
              audio: Buffer.alloc(32),
              mimeType: "audio/webm",
            },
            transcriber,
          }),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
      },
    );

    expect(genericInvoke).not.toHaveBeenCalled();
    expect(complete).not.toHaveBeenCalled();
    expect(completeText).not.toHaveBeenCalled();
    expect(transcriber).not.toHaveBeenCalled();
  });

  it("rejects a wrong Twin census context and any ownership context under an ordinary census", async () => {
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));
    await expect(
      runWithTemplateTwinProviderCensus(
        {
          classification: "TEMPLATE_TWIN",
          templateId: "different-template",
          templateVersion: CONTEXT.noteTemplateVersion!,
        },
        () =>
          runWithTemplateTwinProviderOwnershipContextRaw(CONTEXT, () =>
            runTemplateTwinOwnedProvider(providerInput(invoke)),
          ),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    await expect(
      runWithTemplateTwinProviderCensus(
        {
          classification: "ORDINARY",
          templateId: CONTEXT.noteTemplateId!,
          templateVersion: CONTEXT.noteTemplateVersion!,
        },
        () =>
          runWithTemplateTwinProviderOwnershipContextRaw(CONTEXT, () =>
            runTemplateTwinOwnedProvider(providerInput(invoke)),
          ),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("rejects a VISIT_PIPELINE ownership context when no pre-L1 census exists", async () => {
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));
    await expect(
      runWithTemplateTwinProviderOwnershipContextRaw(CONTEXT, () =>
        runTemplateTwinOwnedProvider(providerInput(invoke)),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("admits exactly one concurrent provider invocation and reuses its committed result", async () => {
    const database = new MemoryProviderDatabase();
    let release!: () => void;
    let started!: () => void;
    const providerStarted = new Promise<void>((resolve) => {
      started = resolve;
    });
    const providerReleased = new Promise<void>((resolve) => {
      release = resolve;
    });
    const invoke = vi.fn(async () => {
      started();
      await providerReleased;
      return { facts: ["synthetic fact"] };
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
      );

    const first = run();
    await providerStarted;
    const second = run();
    await new Promise((resolve) => setTimeout(resolve, 5));
    release();

    await expect(Promise.all([first, second])).resolves.toEqual([
      { facts: ["synthetic fact"] },
      { facts: ["synthetic fact"] },
    ]);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()]).toHaveLength(1);
    expect([...database.rows.values()][0]).toMatchObject({
      status: "SUCCEEDED",
      invocationCount: 1,
    });
  });

  it("treats a provider or runtime swap as an identity mismatch, not a new call", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    const swappedInvoke = vi.fn(async () => ({ facts: ["second"] }));
    const swapped = providerInput(swappedInvoke);

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          { ...swapped, provider: "different-provider" },
          dependencies(database, { mode: "LIVE" }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(swappedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("collides input drift with the same logical owner before a second egress", async () => {
    const database = new MemoryProviderDatabase();
    let release!: () => void;
    let started!: () => void;
    const providerStarted = new Promise<void>((resolve) => {
      started = resolve;
    });
    const providerReleased = new Promise<void>((resolve) => {
      release = resolve;
    });
    const firstInvoke = vi.fn(async () => {
      started();
      await providerReleased;
      return { facts: ["first"] };
    });
    const first = runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    await providerStarted;
    const driftedInvoke = vi.fn(async () => ({ facts: ["drifted"] }));
    const drifted = providerInput(driftedInvoke);
    const driftCode = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          {
            ...drifted,
            inputIdentity: { ...drifted.inputIdentity, evidence: "changed" },
          },
          dependencies(database),
        ),
      ),
    );
    release();

    await expect(first).resolves.toEqual({ facts: ["first"] });
    expect(driftCode).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(driftedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("collides operation-version drift with the same logical owner", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    const driftedInvoke = vi.fn(async () => ({ facts: ["drifted"] }));
    const drifted = providerInput(driftedInvoke);

    const driftCode = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          { ...drifted, operationVersion: "l3-provider-owner-v2" },
          dependencies(database),
        ),
      ),
    );

    expect(driftCode).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(driftedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("collides a persisted visit input-mode drift with the same logical owner", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(
        { ...CONTEXT, visitInputMode: "voice_dictation" },
        () =>
          runTemplateTwinOwnedProvider(
            providerInput(invoke),
            dependencies(database),
          ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(invoke).toHaveBeenCalledOnce();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("permits explicitly distinct deterministic operation instances", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    const secondInvoke = vi.fn(async () => ({ facts: ["second"] }));

    const results = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      async () => [
        await runTemplateTwinOwnedProvider(
          {
            ...providerInput(firstInvoke),
            operationInstance: "ensemble-pass-1",
          },
          dependencies(database),
        ),
        await runTemplateTwinOwnedProvider(
          {
            ...providerInput(secondInvoke),
            operationInstance: "ensemble-pass-2",
          },
          dependencies(database),
        ),
      ],
    );

    expect(results).toEqual([{ facts: ["first"] }, { facts: ["second"] }]);
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(secondInvoke).toHaveBeenCalledOnce();
    expect(database.rows).toHaveProperty("size", 2);
  });

  it("makes an ambiguous live provider failure terminal and blocks replay", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => {
      throw new Error("synthetic network acknowledgement lost");
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { mode: "LIVE" }),
        ),
      );

    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "UNKNOWN_OUTCOME",
      invocationCount: 1,
    });
  });

  it("terminalizes an ambiguous live outcome despite concurrent authority revocation and never replays it", async () => {
    const database = new MemoryProviderDatabase();
    let authorityCurrent = true;
    const invoke = vi.fn(async () => {
      authorityCurrent = false;
      throw new Error(
        "synthetic provider acknowledgement lost during revocation",
      );
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, {
            mode: "LIVE",
            authorityCurrent: () => authorityCurrent,
          }),
        ),
      );

    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect([...database.rows.values()][0]).toMatchObject({
      status: "UNKNOWN_OUTCOME",
      invocationCount: 1,
      resultPayload: null,
      resultSha256: null,
    });
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED",
    );
    authorityCurrent = true;
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("recovers an exact committed result when the commit acknowledgement is lost", async () => {
    const database = new MemoryProviderDatabase();
    database.throwAfterSuccessfulCompletion = true;
    const invoke = vi.fn(async () => ({ facts: ["committed once"] }));

    const result = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
    );

    expect(result).toEqual({ facts: ["committed once"] });
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]?.status).toBe("SUCCEEDED");
  });

  it("does not return an ambiguously committed success after authority is revoked", async () => {
    const database = new MemoryProviderDatabase();
    database.throwAfterSuccessfulCompletion = true;
    const invoke = vi.fn(async () => ({ facts: ["committed once"] }));
    let authorityChecks = 0;

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, {
            authorityCurrent: () => ++authorityChecks < 3,
          }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(authorityChecks).toBe(3);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]?.status).toBe("SUCCEEDED");
  });

  it.each([
    "actor deactivation",
    "actor suspension",
    "actor product removal",
    "visit deletion",
    "visit reassignment",
    "visit input-mode drift",
    "artifact lineage drift",
    "synthetic admission revocation",
  ])("blocks %s before provider egress", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { authorityCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(invoke).not.toHaveBeenCalled();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "FAILED",
      invocationCount: 0,
      failureCode: "AUTHORITY_REVOKED_BEFORE_PROVIDER",
    });
  });

  it.each([
    "actor deactivation",
    "actor suspension",
    "actor product removal",
    "visit deletion",
    "visit reassignment",
    "visit input-mode drift",
    "artifact lineage drift",
    "synthetic admission revocation",
  ])("rejects %s after provider return before success admission", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["unadmitted result"] }));
    let authorityChecks = 0;

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, {
            authorityCurrent: () => ++authorityChecks === 1,
          }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(authorityChecks).toBe(2);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "FAILED",
      invocationCount: 1,
      failureCode: "AUTHORITY_REVOKED_AFTER_PROVIDER",
      resultPayload: null,
      resultSha256: null,
    });
  });

  it("rejects a tampered committed result before it can be reused", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["exact"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );
    const row = [...database.rows.values()][0];
    if (!row) throw new Error("synthetic row missing");
    row.resultSha256 = "f".repeat(64);

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("rejects a committed result after current actor authority is revoked without new egress", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["exact"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { authorityCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("builds a minimal canonical receipt without provider inputs or claim tokens", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["receipt"] }));

    const receipt = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: CONTEXT.visitId,
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          expectedExecutionPlan: [
            { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
          ],
        });
      },
    );
    const serialized = JSON.stringify(receipt);

    expect(receipt.sha256).toMatch(/^[a-f0-9]{64}$/u);
    expect(receipt.evidence).toMatchObject({
      contractVersion: "template-twin-provider-ownership-receipt-v2",
      actorUserId: CONTEXT.actorUserId,
      providerMode: "DETERMINISTIC_MOCK",
      syntheticAdmissionId: null,
    });
    expect(receipt.evidence.executions).toHaveLength(1);
    expect(serialized).not.toContain("private synthetic input");
    expect(serialized).not.toContain("idempotency");
    expect(serialized).not.toContain("claimId");
    expect(serialized).not.toContain("resultPayload");
  });

  it("rejects a receipt projection that does not exactly match its provider context", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["receipt"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: "different-visit",
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          expectedExecutionPlan: [
            { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
          ],
        });
      }),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("taints the whole chain when a caught provider failure would otherwise be omitted", async () => {
    const database = new MemoryProviderDatabase();
    const l3 = vi.fn(async () => ({ facts: ["successful evidence"] }));
    const verifier = vi.fn(async () => {
      throw new Error("synthetic verifier failure");
    });
    const afterFailure = vi.fn(async () => ({ facts: ["must not egress"] }));
    let afterFailureCode: string | null = null;

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(l3),
          dependencies(database),
        );
        try {
          await runTemplateTwinOwnedProvider(
            {
              ...providerInput(verifier),
              operation: "L4_ANCHOR_VERIFY",
              operationVersion: "anchor-verifier-v1",
            },
            dependencies(database),
          );
        } catch {
          // Production verifier call sites may conservatively fall back. The
          // artifact receipt must still remember that provider ownership was
          // incomplete instead of silently certifying the partial chain.
        }
        afterFailureCode = await errorCode(
          runTemplateTwinOwnedProvider(
            {
              ...providerInput(afterFailure),
              operation: "L5_SELF_CRITIQUE",
              operationVersion: "post-failure-v1",
            },
            dependencies(database),
          ),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: CONTEXT.visitId,
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          expectedExecutionPlan: [
            { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
          ],
        });
      }),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
    expect(afterFailureCode).toBe("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
    expect(l3).toHaveBeenCalledOnce();
    expect(verifier).toHaveBeenCalledOnce();
    expect(afterFailure).not.toHaveBeenCalled();
  });

  it("fails a reserved execution closed when rollout authority is revoked", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["must not run"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { rolloutCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
    expect(invoke).not.toHaveBeenCalled();
    expect([...database.rows.values()][0]?.status).toBe("FAILED");
  });

  it.each([
    ["practice", { practiceId: "different-practice" }],
    ["actor", { userId: "different-doctor" }],
    ["visit", { visitId: "different-visit" }],
  ] as const)(
    "rejects cross-%s complete-text and transcription identities before egress",
    async (_label, identityOverride) => {
      const completeText = vi.fn(async () => ({
        text: "must not run",
        inputTokens: 1,
        outputTokens: 1,
      }));
      const transcriber = vi.fn(
        async () =>
          ({
            provider: "deepgram-batch",
            transcript: "must not run",
            durationSec: 1,
            language: "en",
            costCents: 0,
            fallbackUsed: false,
            raw: { kind: "deepgram", data: {} },
          }) as TranscribeResult,
      );
      const providerIdentity = {
        practiceId: CONTEXT.practiceId,
        userId: CONTEXT.actorUserId,
        visitId: CONTEXT.visitId,
        ...identityOverride,
      };

      const completeTextCode = await errorCode(
        runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
          runTemplateTwinOwnedModelCompleteText({
            operation: "L6_POLISH",
            operationVersion: "l6-provider-owner-v1",
            client: { completeText },
            args: {
              ...providerIdentity,
              purpose: "tm_polish",
              provider: "anthropic",
              model: "claude-synthetic-1",
              system: "synthetic system",
              user: "synthetic input",
            },
          }),
        ),
      );
      const transcriptionCode = await errorCode(
        runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
          runTemplateTwinOwnedTranscribe({
            operation: "L1_TRANSCRIBE",
            operationVersion: "l1-provider-owner-v1",
            audioIdentity: {
              objectKey: "private/provider-owner/audio.webm",
              objectEtag: "synthetic-etag",
              sizeBytes: 16,
              lastModifiedIso: "2026-07-19T17:20:00.000Z",
            },
            transcriber,
            args: {
              ...providerIdentity,
              purpose: "tm_transcribe",
              audio: Buffer.from("synthetic audio"),
              mimeType: "audio/webm",
            },
          }),
        ),
      );

      expect(completeTextCode).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
      expect(transcriptionCode).toBe(
        "TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH",
      );
      expect(completeText).not.toHaveBeenCalled();
      expect(transcriber).not.toHaveBeenCalled();
    },
  );
});
