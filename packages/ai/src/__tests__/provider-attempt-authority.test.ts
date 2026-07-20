import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

process.env.ANTHROPIC_API_KEY = "synthetic-test-key";

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
}));

vi.mock("@anthropic-ai/sdk", () => ({
  default: class {
    messages = { create: mocks.create };
  },
}));
vi.mock("../log", () => ({ logAiCall: vi.fn() }));
vi.mock("../api-usage", () => ({
  logApiUsage: vi.fn(),
  buildAnthropicUsage: vi.fn(() => ({})),
}));

import { modelClient } from "../model-client";

const Schema = z.object({ value: z.string() });
const BASE_ARGS = {
  practiceId: "practice-provider-attempt",
  visitId: "visit-provider-attempt",
  userId: "doctor-provider-attempt",
  purpose: "tm_entities" as const,
  provider: "anthropic" as const,
  model: "synthetic-model",
  system: "synthetic system",
  user: "synthetic input",
  schema: Schema,
};

const USAGE = {
  input_tokens: 1,
  output_tokens: 1,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  process.env.MOCK_AI_CALLS = "false";
});

describe("model provider attempt authority", () => {
  it("runs the guard before every schema-retry provider attempt", async () => {
    mocks.create
      .mockResolvedValueOnce({
        content: [{ type: "text", text: "not valid json" }],
        usage: USAGE,
        stop_reason: "end_turn",
      })
      .mockResolvedValueOnce({
        content: [{ type: "text", text: '{"value":"synthetic-safe"}' }],
        usage: USAGE,
        stop_reason: "end_turn",
      });
    const beforeProviderAttempt = vi.fn(async () => undefined);
    const afterProviderAttempt = vi.fn(async () => undefined);

    await expect(
      modelClient.complete({
        ...BASE_ARGS,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).resolves.toEqual({ value: "synthetic-safe" });

    expect(beforeProviderAttempt).toHaveBeenCalledTimes(2);
    expect(afterProviderAttempt).toHaveBeenCalledTimes(2);
    expect(mocks.create).toHaveBeenCalledTimes(2);
    expect(mocks.create.mock.calls[0]?.[1]).toMatchObject({ maxRetries: 0 });
    expect(mocks.create.mock.calls[1]?.[1]).toMatchObject({ maxRetries: 0 });
    expect(beforeProviderAttempt.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.create.mock.invocationCallOrder[0]!,
    );
    expect(beforeProviderAttempt.mock.invocationCallOrder[1]).toBeLessThan(
      mocks.create.mock.invocationCallOrder[1]!,
    );
    expect(mocks.create.mock.invocationCallOrder[0]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[0]!,
    );
    expect(mocks.create.mock.invocationCallOrder[1]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[1]!,
    );
  });

  it("stops before a retry when the guard denies current authority", async () => {
    mocks.create.mockResolvedValueOnce({
      content: [{ type: "text", text: "not valid json" }],
      usage: USAGE,
      stop_reason: "end_turn",
    });
    const beforeProviderAttempt = vi
      .fn<() => Promise<void>>()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("current authority revoked"));
    const afterProviderAttempt = vi.fn(async () => undefined);

    await expect(
      modelClient.complete({
        ...BASE_ARGS,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).rejects.toThrow("current authority revoked");

    expect(beforeProviderAttempt).toHaveBeenCalledTimes(2);
    expect(afterProviderAttempt).toHaveBeenCalledOnce();
    expect(mocks.create).toHaveBeenCalledOnce();
    expect(mocks.create.mock.calls[0]?.[1]).toMatchObject({ maxRetries: 0 });
  });

  it("stops after a malformed attempt when post-attempt authority is revoked", async () => {
    mocks.create.mockResolvedValueOnce({
      content: [{ type: "text", text: "not valid json" }],
      usage: USAGE,
      stop_reason: "end_turn",
    });
    const beforeProviderAttempt = vi.fn(async () => undefined);
    const afterProviderAttempt = vi.fn(async () => {
      throw new Error("post-attempt authority revoked");
    });

    await expect(
      modelClient.complete({
        ...BASE_ARGS,
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).rejects.toThrow("post-attempt authority revoked");

    expect(beforeProviderAttempt).toHaveBeenCalledOnce();
    expect(afterProviderAttempt).toHaveBeenCalledOnce();
    expect(mocks.create).toHaveBeenCalledOnce();
  });

  it("runs the guard before a plain-text provider request", async () => {
    mocks.create.mockResolvedValueOnce({
      content: [{ type: "text", text: "synthetic safe text" }],
      usage: USAGE,
      stop_reason: "end_turn",
    });
    const beforeProviderAttempt = vi.fn(async () => undefined);
    const afterProviderAttempt = vi.fn(async () => undefined);

    await expect(
      modelClient.completeText({
        ...BASE_ARGS,
        purpose: "tm_soap_draft",
        beforeProviderAttempt,
        afterProviderAttempt,
      }),
    ).resolves.toMatchObject({ text: "synthetic safe text" });

    expect(beforeProviderAttempt).toHaveBeenCalledOnce();
    expect(afterProviderAttempt).toHaveBeenCalledOnce();
    expect(mocks.create).toHaveBeenCalledOnce();
    expect(mocks.create.mock.calls[0]?.[1]).toMatchObject({ maxRetries: 0 });
    expect(beforeProviderAttempt.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.create.mock.invocationCallOrder[0]!,
    );
    expect(mocks.create.mock.invocationCallOrder[0]).toBeLessThan(
      afterProviderAttempt.mock.invocationCallOrder[0]!,
    );
  });
});
