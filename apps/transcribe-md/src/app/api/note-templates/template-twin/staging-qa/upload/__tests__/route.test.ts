// @vitest-environment node

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireDoctor: vi.fn(),
  createDraft: vi.fn(),
  uploadProvider: vi.fn(),
  rateLimit: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireDoctorSession: mocks.requireDoctor,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { UPLOAD: {} },
  rateLimitOr429: mocks.rateLimit,
}));
vi.mock("@/lib/template-twin/create-draft", () => ({
  TemplateTwinDraftError: class TemplateTwinDraftError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  createTemplateTwinDraft: mocks.createDraft,
}));
vi.mock("@/lib/template-twin/staging-qa-upload-provider", () => ({
  TemplateTwinStagingQaUploadProviderError: class TemplateTwinStagingQaUploadProviderError extends Error {},
  runWithTemplateTwinStagingQaUploadProvider: mocks.uploadProvider,
}));

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_FILENAME,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_MIME,
  TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE,
  TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME,
  TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION,
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  templateTwinStagingQaFixtureDescriptor,
} from "@/lib/template-twin/staging-qa-fixtures";
import { AuthError } from "@/lib/auth";

import { POST } from "../route";

const ENDPOINT =
  "https://app.synthetic.test/api/note-templates/template-twin/staging-qa/upload";
const ENV_KEYS = [
  "TEMPLATE_TWIN_STAGING_QA_ENABLED",
  "TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT",
  "TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION",
  "TEMPLATE_TWIN_STORAGE_PROFILE",
  "MOCK_AI_CALLS",
  "MOCK_TEMPLATE_TWIN_E2E",
  "DATABASE_URL",
  "REDIS_URL",
  "MINIO_ENDPOINT",
  "MINIO_USE_SSL",
  "TRANSCRIBE_MD_MINIO_BUCKET",
  "TRANSCRIBE_MD_TEMPLATE_BUCKET",
  "TEMPLATE_TWIN_KILL_SWITCH",
] as const;
const originalEnv = Object.fromEntries(
  ENV_KEYS.map((key) => [key, process.env[key]]),
);

function safeEnvironment(): void {
  process.env.TEMPLATE_TWIN_STAGING_QA_ENABLED = "true";
  process.env.TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT = "test";
  process.env.TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION =
    "isolated-disposable-qa-v1";
  process.env.TEMPLATE_TWIN_STORAGE_PROFILE = "qa";
  process.env.MOCK_AI_CALLS = "true";
  process.env.MOCK_TEMPLATE_TWIN_E2E = "true";
  process.env.DATABASE_URL = "postgresql:///meddoc_synthetic_test";
  process.env.REDIS_URL = "redis://redis:6379/15";
  process.env.MINIO_ENDPOINT = "minio:9000";
  process.env.MINIO_USE_SSL = "false";
  process.env.TRANSCRIBE_MD_MINIO_BUCKET = "transcribe-md-audio-qa";
  process.env.TRANSCRIBE_MD_TEMPLATE_BUCKET =
    "transcribe-md-template-artifacts-qa";
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
}

async function uploadRequest(
  input: {
    bytes?: Uint8Array;
    filename?: string;
    mimeType?: string;
    fixtureVersion?: string;
    origin?: string;
    contentLength?: string;
  } = {},
): Promise<Request> {
  const fixture = await templateTwinStagingQaFixtureDescriptor();
  const fileBytes = Buffer.from(input.bytes ?? fixture.bytes);
  const fileBuffer = fileBytes.buffer.slice(
    fileBytes.byteOffset,
    fileBytes.byteOffset + fileBytes.byteLength,
  ) as ArrayBuffer;
  const form = new FormData();
  form.set(
    "file",
    new File([fileBuffer], input.filename ?? fixture.filename, {
      type: input.mimeType ?? fixture.mimeType,
    }),
  );
  form.set("templateName", TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME);
  form.set("encounterScope", TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE);
  form.set("versionDescription", TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION);
  form.set("fixtureVersion", input.fixtureVersion ?? fixture.fixtureVersion);
  return new Request(ENDPOINT, {
    method: "POST",
    headers: {
      origin: input.origin ?? "https://app.synthetic.test",
      "sec-fetch-site": input.origin ? "cross-site" : "same-origin",
      ...(input.contentLength ? { "content-length": input.contentLength } : {}),
    },
    body: form,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  safeEnvironment();
  mocks.rateLimit.mockReturnValue(null);
  mocks.uploadProvider.mockImplementation(
    (input: { operation: (providerVisitId: string) => unknown }) =>
      input.operation("template-twin-staging-upload-visit:synthetic"),
  );
  mocks.requireDoctor.mockResolvedValue({
    user: {
      id: "doctor-synthetic-1",
      email: "doctor@synthetic.test",
      practiceId: "practice-synthetic-1",
    },
    templateTwinRolloutToken: {
      practiceId: "practice-synthetic-1",
      globalGeneration: BigInt(2),
      practiceGeneration: BigInt(3),
    },
  });
  mocks.createDraft.mockResolvedValue({
    noteTemplateId: "template-synthetic-1",
    sourceSha256: "a".repeat(64),
    compilerVersion: "synthetic-compiler/1",
    fieldCount: 8,
    blockingUnsupportedCount: 0,
  });
});

afterEach(() => {
  for (const key of ENV_KEYS) {
    const value = originalEnv[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

describe("synthetic staging fixture upload route", () => {
  it("admits only the independently byte-verified fixture through the real draft service", async () => {
    const response = await POST(await uploadRequest());
    expect(response.status).toBe(201);
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      noteTemplateId: "template-synthetic-1",
      certificationUrl: "/settings/note-format/template-synthetic-1/certify",
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    });
    expect(mocks.createDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        source: expect.any(Uint8Array),
        providerVisitId: "template-twin-staging-upload-visit:synthetic",
        actor: expect.objectContaining({
          practiceId: "practice-synthetic-1",
        }),
      }),
    );
    expect(mocks.uploadProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        source: expect.objectContaining({
          sha256: expect.stringMatching(/^[a-f0-9]{64}$/u),
        }),
        actor: expect.objectContaining({
          practiceId: "practice-synthetic-1",
        }),
        operation: expect.any(Function),
      }),
    );
  });

  it("treats browser MIME as untrusted and admits only matching allowlisted bytes", async () => {
    const response = await POST(await uploadRequest({ mimeType: "text/html" }));
    expect(response.status).toBe(201);
    expect(mocks.createDraft).toHaveBeenCalledTimes(1);
  });

  it("accepts a renamed local copy when its version and bytes are exact", async () => {
    const response = await POST(
      await uploadRequest({ filename: "renamed-synthetic-copy.docx" }),
    );
    expect(response.status).toBe(201);
    expect(mocks.createDraft).toHaveBeenCalledTimes(1);
  });

  it.each([
    [
      "changed bytes regardless of MIME",
      { bytes: Uint8Array.from([1, 2, 3]), mimeType: "text/html" },
    ],
    ["stale version", { fixtureVersion: "synthetic-fixture/old" }],
  ])("rejects %s before draft creation", async (_label, patch) => {
    const response = await POST(await uploadRequest(patch));
    expect(response.status).toBe(422);
    expect(mocks.createDraft).not.toHaveBeenCalled();
  });

  it("rejects arbitrary upload metadata before draft creation", async () => {
    const request = await uploadRequest();
    const form = await request.formData();
    form.set("templateName", "Arbitrary staging template");
    const response = await POST(
      new Request(ENDPOINT, {
        method: "POST",
        headers: {
          origin: "https://app.synthetic.test",
          "sec-fetch-site": "same-origin",
        },
        body: form,
      }),
    );

    expect(response.status).toBe(400);
    expect(mocks.createDraft).not.toHaveBeenCalled();
  });

  it("rejects cross-site, disabled, and non-doctor requests without draft creation", async () => {
    expect(
      (await POST(await uploadRequest({ origin: "https://evil.example.test" })))
        .status,
    ).toBe(404);

    process.env.TEMPLATE_TWIN_STAGING_QA_ENABLED = "false";
    expect((await POST(await uploadRequest())).status).toBe(404);

    safeEnvironment();
    mocks.requireDoctor.mockRejectedValue(
      new AuthError("FORBIDDEN", "not a doctor"),
    );
    expect((await POST(await uploadRequest())).status).toBe(404);
    expect(mocks.createDraft).not.toHaveBeenCalled();
  });

  it("uses a hard actual-byte multipart cap with absent or lying length metadata", async () => {
    expect(
      (await POST(await uploadRequest({ contentLength: "1" }))).status,
    ).toBe(201);
    const response = await POST(
      await uploadRequest({ bytes: new Uint8Array(1024 * 1024 + 1) }),
    );
    expect(response.status).toBe(413);
    expect(mocks.createDraft).toHaveBeenCalledTimes(1);
  });

  it("pins exact public fixture identity constants", () => {
    expect(TEMPLATE_TWIN_STAGING_QA_FIXTURE_FILENAME).toBe(
      "template-twin-synthetic-qa-v1.docx",
    );
    expect(TEMPLATE_TWIN_STAGING_QA_FIXTURE_MIME).toContain(
      "wordprocessingml.document",
    );
  });
});
