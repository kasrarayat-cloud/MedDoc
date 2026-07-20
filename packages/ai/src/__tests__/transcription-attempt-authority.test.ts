import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../log", () => ({ logAiCall: vi.fn() }));
vi.mock("../api-usage", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api-usage")>();
  return { ...actual, logApiUsage: vi.fn() };
});

import { deepgramBatchTranscribe } from "../deepgram-batch";
import {
  __setOpenAIClientForTests,
  whisperBatchTranscribe,
} from "../whisper-batch";

const CONTEXT = {
  practiceId: "practice-transcription-authority",
  visitId: "visit-transcription-authority",
  userId: "doctor-transcription-authority",
  purpose: "tm_transcribe" as const,
  audio: Buffer.from("bounded synthetic audio"),
  mimeType: "audio/webm",
};

function deepgramResponse(status = 200): Response {
  if (status !== 200) {
    return new Response("synthetic provider failure", {
      status,
      statusText: "Synthetic Failure",
    });
  }
  return new Response(
    JSON.stringify({
      metadata: { duration: 1 },
      results: {
        channels: [
          { alternatives: [{ transcript: "bounded synthetic transcript" }] },
        ],
        utterances: [],
      },
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(Math, "random").mockReturnValue(0);
  process.env.MOCK_AI_CALLS = "false";
  process.env.DEEPGRAM_API_KEY = "synthetic-test-key";
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  __setOpenAIClientForTests(null);
});

describe("transcription provider attempt authority", () => {
  it("runs the guard before every Deepgram retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(deepgramResponse(503))
      .mockResolvedValueOnce(deepgramResponse());
    vi.stubGlobal("fetch", fetchMock);
    const beforeProviderAttempt = vi.fn(async () => undefined);
    const afterProviderAttempt = vi.fn(async () => undefined);

    await expect(
      deepgramBatchTranscribe({
        ...CONTEXT,
        maxAttempts: 2,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).resolves.toMatchObject({ transcript: "bounded synthetic transcript" });

    expect(beforeProviderAttempt).toHaveBeenCalledTimes(2);
    expect(afterProviderAttempt).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(beforeProviderAttempt.mock.invocationCallOrder[0]).toBeLessThan(
      fetchMock.mock.invocationCallOrder[0]!,
    );
    expect(beforeProviderAttempt.mock.invocationCallOrder[1]).toBeLessThan(
      fetchMock.mock.invocationCallOrder[1]!,
    );
    expect(fetchMock.mock.invocationCallOrder[0]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[0]!,
    );
    expect(fetchMock.mock.invocationCallOrder[1]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[1]!,
    );
  });

  it("prevents a Deepgram retry after authority is revoked", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(deepgramResponse(503));
    vi.stubGlobal("fetch", fetchMock);
    const beforeProviderAttempt = vi
      .fn<() => Promise<void>>()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("current authority revoked"));
    const afterProviderAttempt = vi.fn(async () => undefined);

    await expect(
      deepgramBatchTranscribe({
        ...CONTEXT,
        maxAttempts: 2,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).rejects.toThrow("current authority revoked");

    expect(beforeProviderAttempt).toHaveBeenCalledTimes(2);
    expect(afterProviderAttempt).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("prevents a Deepgram retry when post-attempt authority is revoked", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(deepgramResponse(503));
    vi.stubGlobal("fetch", fetchMock);
    const beforeProviderAttempt = vi.fn(async () => undefined);
    const afterProviderAttempt = vi.fn(async () => {
      throw new Error("post-attempt authority revoked");
    });

    await expect(
      deepgramBatchTranscribe({
        ...CONTEXT,
        maxAttempts: 2,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).rejects.toThrow("post-attempt authority revoked");

    expect(beforeProviderAttempt).toHaveBeenCalledOnce();
    expect(afterProviderAttempt).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("runs the guard before every Whisper retry", async () => {
    const create = vi
      .fn()
      .mockRejectedValueOnce(
        Object.assign(new Error("synthetic 503"), { status: 503 }),
      )
      .mockResolvedValueOnce({
        text: "bounded synthetic transcript",
        duration: 1,
        language: "en",
        segments: [],
      });
    __setOpenAIClientForTests({
      audio: { transcriptions: { create } },
    } as never);
    const beforeProviderAttempt = vi.fn(async () => undefined);
    const afterProviderAttempt = vi.fn(async () => undefined);

    await expect(
      whisperBatchTranscribe({
        ...CONTEXT,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).resolves.toMatchObject({ transcript: "bounded synthetic transcript" });

    expect(beforeProviderAttempt).toHaveBeenCalledTimes(2);
    expect(afterProviderAttempt).toHaveBeenCalledTimes(2);
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[0]?.[1]).toMatchObject({ maxRetries: 0 });
    expect(create.mock.calls[1]?.[1]).toMatchObject({ maxRetries: 0 });
    expect(beforeProviderAttempt.mock.invocationCallOrder[0]).toBeLessThan(
      create.mock.invocationCallOrder[0]!,
    );
    expect(beforeProviderAttempt.mock.invocationCallOrder[1]).toBeLessThan(
      create.mock.invocationCallOrder[1]!,
    );
    expect(create.mock.invocationCallOrder[0]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[0]!,
    );
    expect(create.mock.invocationCallOrder[1]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[1]!,
    );
  });
});
