import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

const db = vi.hoisted(() => ({ queryRaw: vi.fn() }));

vi.mock("@meddoc/db", () => ({
  default: { $queryRaw: db.queryRaw },
}));

import {
  runTemplateTwinOwnedModelComplete,
  runTemplateTwinOwnedModelCompleteText,
  runTemplateTwinOwnedTranscribe,
} from "../provider-ownership";

const IDENTITY = {
  practiceId: "practice-ordinary-authority",
  userId: "doctor-ordinary-authority",
  visitId: "visit-ordinary-authority",
} as const;

const CURRENT_ACTOR = {
  id: IDENTITY.userId,
  practiceId: IDENTITY.practiceId,
  email: "synthetic-physician@example.test",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ordinary visit provider current-authority fence", () => {
  it("revalidates immediately before every structured-output attempt and after success", async () => {
    db.queryRaw.mockResolvedValue([CURRENT_ACTOR]);
    let externalAttempts = 0;
    const complete = vi.fn(async (args) => {
      await args.beforeProviderAttempt?.();
      externalAttempts += 1;
      await args.afterProviderAttempt?.();
      await args.beforeProviderAttempt?.();
      externalAttempts += 1;
      await args.afterProviderAttempt?.();
      return { value: "synthetic-safe-result" };
    });

    await expect(
      runTemplateTwinOwnedModelComplete({
        operation: "L3_EXTRACT_ENTITIES",
        operationVersion: "ordinary-authority-test-v1",
        client: { complete: complete as never },
        args: {
          ...IDENTITY,
          purpose: "tm_entities",
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: "synthetic input",
          schema: z.object({ value: z.string() }),
        },
      }),
    ).resolves.toEqual({ value: "synthetic-safe-result" });

    expect(externalAttempts).toBe(2);
    expect(db.queryRaw).toHaveBeenCalledTimes(5);
  });

  it("prevents a later retry after current authority is revoked", async () => {
    db.queryRaw
      .mockResolvedValueOnce([CURRENT_ACTOR])
      .mockResolvedValueOnce([CURRENT_ACTOR])
      .mockResolvedValueOnce([]);
    let externalAttempts = 0;
    const complete = vi.fn(async (args) => {
      await args.beforeProviderAttempt?.();
      externalAttempts += 1;
      await args.afterProviderAttempt?.();
      await args.beforeProviderAttempt?.();
      externalAttempts += 1;
      return { value: "must-not-be-returned" };
    });

    await expect(
      runTemplateTwinOwnedModelComplete({
        operation: "L3_EXTRACT_ENTITIES",
        operationVersion: "ordinary-authority-test-v1",
        client: { complete: complete as never },
        args: {
          ...IDENTITY,
          purpose: "tm_entities",
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: "synthetic input",
          schema: z.object({ value: z.string() }),
        },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED",
    });

    expect(externalAttempts).toBe(1);
    expect(db.queryRaw).toHaveBeenCalledTimes(3);
  });

  it("discards a completed text result when authority changes in flight", async () => {
    db.queryRaw
      .mockResolvedValueOnce([CURRENT_ACTOR])
      .mockResolvedValueOnce([]);
    const completeText = vi.fn(async (args) => {
      await args.beforeProviderAttempt?.();
      await args.afterProviderAttempt?.();
      return {
        text: "must not be accepted",
        inputTokens: 1,
        outputTokens: 1,
      };
    });

    await expect(
      runTemplateTwinOwnedModelCompleteText({
        operation: "L4_GENERATE_SOAP",
        operationVersion: "ordinary-authority-test-v1",
        client: { completeText },
        args: {
          ...IDENTITY,
          purpose: "tm_soap_draft",
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: "synthetic input",
        },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED",
    });

    expect(completeText).toHaveBeenCalledOnce();
    expect(db.queryRaw).toHaveBeenCalledTimes(2);
  });

  it("binds every transcription attempt and its returned transcript", async () => {
    db.queryRaw.mockResolvedValue([CURRENT_ACTOR]);
    const transcriber = vi.fn(async (args) => {
      await args.beforeProviderAttempt?.();
      await args.afterProviderAttempt?.();
      return {
        provider: "deepgram-batch" as const,
        transcript: "bounded synthetic transcript",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram" as const, data: {} as never },
      };
    });

    await expect(
      runTemplateTwinOwnedTranscribe({
        operation: "L1_TRANSCRIBE",
        operationVersion: "ordinary-authority-test-v1",
        audioIdentity: {
          objectKey: "synthetic/audio.webm",
          objectEtag: "synthetic-etag",
          sizeBytes: 16,
          lastModifiedIso: null,
        },
        transcriber,
        args: {
          ...IDENTITY,
          purpose: "tm_transcribe",
          audio: Buffer.from("synthetic audio"),
          mimeType: "audio/webm",
        },
      }),
    ).resolves.toMatchObject({ transcript: "bounded synthetic transcript" });

    expect(transcriber).toHaveBeenCalledOnce();
    expect(db.queryRaw).toHaveBeenCalledTimes(3);
  });

  it("fails a visit-bound call closed when the current actor identity is absent", async () => {
    const completeText = vi.fn();

    await expect(
      runTemplateTwinOwnedModelCompleteText({
        operation: "L4_GENERATE_SOAP",
        operationVersion: "ordinary-authority-test-v1",
        client: { completeText },
        args: {
          practiceId: IDENTITY.practiceId,
          visitId: IDENTITY.visitId,
          userId: null,
          purpose: "tm_soap_draft",
          provider: "anthropic",
          model: "synthetic-model",
          system: "synthetic system",
          user: "synthetic input",
        },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED",
    });

    expect(completeText).not.toHaveBeenCalled();
    expect(db.queryRaw).not.toHaveBeenCalled();
  });
});
