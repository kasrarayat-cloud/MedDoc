import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ record: vi.fn() }));

vi.mock("@/lib/template-twin/release-control", () => ({
  recordTemplateTwinReleaseMetricSnapshot: mocks.record,
  TemplateTwinReleaseControlError: class extends Error {},
}));

import { TEMPLATE_TWIN_METRIC_DEFINITIONS } from "@/lib/template-twin/release-control-contracts";
import { POST } from "../route";

const originalAdminHost = process.env.ADMIN_PUBLIC_HOST;

function payload() {
  return {
    releaseId: "67c8c5fb-5c34-4671-9aec-10d1fb189b90",
    stage: "CANARY",
    expectedReleaseGeneration: "7",
    expectedGlobalGeneration: "9",
    sampleCount: 25,
    observationStartedAt: "2026-07-19T14:00:00.000Z",
    observationEndedAt: "2026-07-19T14:05:00.000Z",
    metrics: Object.fromEntries(
      Object.keys(TEMPLATE_TWIN_METRIC_DEFINITIONS).map((key) => [key, "0"]),
    ),
    attestation: {
      version: "template-twin-metric-attestation-v1",
      keyId: "synthetic-monitoring-v1",
      nonce: "ae018731-b071-431d-9825-cce7e07760eb",
      issuedAtEpochSeconds: 1_784_470_000,
      signature: "a".repeat(64),
    },
  };
}

function request(
  body: unknown,
  headers: Record<string, string> = {},
): NextRequest {
  return new NextRequest(
    "https://admin.quillmd.com/api/admin/template-twin/release-metrics",
    {
      method: "POST",
      headers: {
        host: "admin.quillmd.com",
        "content-type": "application/json",
        ...headers,
      },
      body: JSON.stringify(body),
    },
  );
}

describe("Template Twin signed metric ingestion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.ADMIN_PUBLIC_HOST = "admin.quillmd.com";
    mocks.record.mockResolvedValue({ evaluation: "PASS" });
  });

  afterEach(() => {
    if (originalAdminHost === undefined) delete process.env.ADMIN_PUBLIC_HOST;
    else process.env.ADMIN_PUBLIC_HOST = originalAdminHost;
  });

  it("rejects non-admin hosts before reading monitoring input", async () => {
    const response = await POST(
      request(payload(), { host: "app.quillmd.com" }),
    );

    expect(response.status).toBe(404);
    expect(mocks.record).not.toHaveBeenCalled();
  });

  it("rejects numeric aggregates, missing metrics, and extra fields", async () => {
    const numeric = payload();
    numeric.metrics.failed_upload_rate = 0 as never;
    const missing = payload();
    delete missing.metrics.failed_upload_rate;
    const extra = { ...payload(), patientId: "must-not-cross-boundary" };

    for (const candidate of [numeric, missing, extra]) {
      const response = await POST(request(candidate));
      expect(response.status).toBe(400);
    }
    expect(mocks.record).not.toHaveBeenCalled();
  });

  it("passes only exact aggregate strings and the signed envelope", async () => {
    const input = payload();
    const response = await POST(request(input));

    expect(response.status).toBe(200);
    expect(mocks.record).toHaveBeenCalledWith({
      ...input,
      observationStartedAt: new Date(input.observationStartedAt),
      observationEndedAt: new Date(input.observationEndedAt),
    });
  });
});
