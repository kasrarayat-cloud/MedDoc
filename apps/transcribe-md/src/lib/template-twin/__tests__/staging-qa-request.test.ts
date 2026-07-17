import { describe, expect, it } from "vitest";

import {
  readBoundedTemplateTwinStagingQaJson,
  TemplateTwinStagingQaRequestError,
} from "../staging-qa-request";
import { TemplateTwinStagingQaRetryRequestSchema } from "../staging-qa-service";

function streamedRequest(
  chunks: readonly string[],
  headers: Record<string, string> = {},
): Request {
  const encoder = new TextEncoder();
  return new Request("https://app.example.test/api/synthetic", {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
    duplex: "half",
  } as RequestInit & { duplex: "half" });
}

describe("bounded Template Twin staging QA JSON", () => {
  it("accepts absent Content-Length and chunked JSON under the actual-byte cap", async () => {
    await expect(
      readBoundedTemplateTwinStagingQaJson(
        streamedRequest(['{"mode":', '"mock_voice"}']),
        64,
      ),
    ).resolves.toEqual({ mode: "mock_voice" });
  });

  it("does not trust a lying short Content-Length", async () => {
    await expect(
      readBoundedTemplateTwinStagingQaJson(
        streamedRequest(['{"value":"', "x".repeat(80), '"}'], {
          "content-length": "2",
        }),
        32,
      ),
    ).rejects.toMatchObject({ code: "REQUEST_TOO_LARGE" });
  });

  it("rejects an oversized claimed length before reading", async () => {
    await expect(
      readBoundedTemplateTwinStagingQaJson(
        streamedRequest(["{}"], { "content-length": "9000" }),
        32,
      ),
    ).rejects.toBeInstanceOf(TemplateTwinStagingQaRequestError);
  });

  it("rejects malformed, invalid UTF-8, and wrong media type", async () => {
    await expect(
      readBoundedTemplateTwinStagingQaJson(streamedRequest(["{"]), 32),
    ).rejects.toMatchObject({ code: "INVALID_JSON" });

    const invalidUtf8 = new Request("https://app.example.test/api/synthetic", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: new Uint8Array([0xff]),
    });
    await expect(
      readBoundedTemplateTwinStagingQaJson(invalidUtf8, 32),
    ).rejects.toMatchObject({ code: "INVALID_JSON" });

    await expect(
      readBoundedTemplateTwinStagingQaJson(
        new Request("https://app.example.test/api/synthetic", {
          method: "POST",
          headers: { "content-type": "text/plain" },
          body: "{}",
        }),
        32,
      ),
    ).rejects.toMatchObject({ code: "INVALID_JSON" });
  });
});

describe("Template Twin staging retry request", () => {
  it("requires one exact nonnegative expected attempt", () => {
    expect(
      TemplateTwinStagingQaRetryRequestSchema.parse({ expectedAttempt: 3 }),
    ).toEqual({ expectedAttempt: 3 });
    for (const input of [
      {},
      { expectedAttempt: -1 },
      { expectedAttempt: 1.5 },
      { expectedAttempt: "3" },
      { expectedAttempt: 3, untrusted: true },
    ]) {
      expect(TemplateTwinStagingQaRetryRequestSchema.safeParse(input).success).toBe(
        false,
      );
    }
  });
});
