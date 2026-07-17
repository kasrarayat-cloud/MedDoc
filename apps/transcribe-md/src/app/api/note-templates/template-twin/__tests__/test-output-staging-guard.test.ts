import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  session: vi.fn(),
  findTemplate: vi.fn(),
  readOutput: vi.fn(),
  finality: vi.fn(),
  lifecycleGuard: vi.fn(async (input: { operation: () => unknown }) =>
    input.operation(),
  ),
}));

vi.mock("next/server", () => {
  class FakeNextResponse {
    status: number;
    headers: Headers;
    private readonly payload: unknown;

    constructor(payload: unknown, init?: ResponseInit) {
      this.payload = payload;
      this.status = init?.status ?? 200;
      this.headers = new Headers(init?.headers);
    }

    async json() {
      return this.payload;
    }

    static json(payload: unknown, init?: ResponseInit) {
      return new FakeNextResponse(payload, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireDoctorSession: mocks.session,
}));
vi.mock("@meddoc/db", () => ({
  default: { noteTemplate: { findFirst: mocks.findTemplate } },
}));
vi.mock("@/lib/template-twin/storage", () => ({
  DOCX_MIME_TYPE:
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  createTemplateTwinArtifactStore: () => ({
    readOutputArtifact: mocks.readOutput,
  }),
}));
vi.mock("@/lib/template-twin/staging-qa-lifecycle-guard", () => ({
  TemplateTwinStagingQaLifecycleGuardError: class TemplateTwinStagingQaLifecycleGuardError extends Error {},
  runWithTemplateTwinStagingQaLifecycleGuard: mocks.lifecycleGuard,
  assertTemplateTwinStagingQaLifecycleFinality: mocks.finality,
}));

import { GET } from "../[id]/test-output/route";
import { TemplateTwinStagingQaLifecycleGuardError } from "@/lib/template-twin/staging-qa-lifecycle-guard";

const TOKEN = {
  practiceId: "practice-download-synthetic",
  globalGeneration: BigInt(4),
  practiceGeneration: BigInt(9),
};

describe("generic synthetic-test output staging finality", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.lifecycleGuard.mockImplementation(
      async (input: { operation: () => unknown }) => input.operation(),
    );
    mocks.session.mockResolvedValue({
      templateTwinRolloutToken: TOKEN,
      user: {
        id: "doctor-download@synthetic.test",
        practiceId: TOKEN.practiceId,
      },
    });
    mocks.findTemplate.mockResolvedValue({
      name: "Synthetic QA Template",
      templateTwinCompiledVersion: {
        latestTestOutputObjectKey: "synthetic/output.docx",
        latestTestOutputVersionId: "version-synthetic",
        latestTestOutputEtag: "etag-synthetic",
        latestTestOutputSha256: "a".repeat(64),
        latestTestVerifiedAt: new Date("2026-07-17T00:00:00.000Z"),
        latestTestRoundTrip: { verified: true },
        sourceArtifact: { practiceId: TOKEN.practiceId },
      },
    });
    mocks.readOutput.mockResolvedValue(Buffer.from("synthetic-docx"));
    mocks.finality.mockResolvedValue(undefined);
  });

  it("returns no bytes when rollout or staging admission is revoked at the final response boundary", async () => {
    mocks.finality.mockRejectedValue(
      new TemplateTwinStagingQaLifecycleGuardError(),
    );

    const response = await GET(new Request("https://app.synthetic.test"), {
      params: Promise.resolve({ id: "template-download-synthetic" }),
    });

    expect(response.status).toBe(404);
    expect(mocks.readOutput).toHaveBeenCalledTimes(1);
    expect(mocks.finality).toHaveBeenCalledWith({
      noteTemplateId: "template-download-synthetic",
      actor: {
        userId: "doctor-download@synthetic.test",
        practiceId: TOKEN.practiceId,
        rolloutToken: TOKEN,
      },
    });
    expect(response.headers.get("content-type")).not.toBe(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
  });

  it("authorizes a verified output only after final staging and rollout revalidation", async () => {
    const response = await GET(new Request("https://app.synthetic.test"), {
      params: Promise.resolve({ id: "template-download-synthetic" }),
    });

    expect(response.status).toBe(200);
    expect(mocks.finality).toHaveBeenCalledTimes(1);
    expect(response.headers.get("content-type")).toBe(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(response.headers.get("cache-control")).toBe("no-store, private");
  });
});
