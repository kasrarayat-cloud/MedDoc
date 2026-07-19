import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  inspect: vi.fn(),
  create: vi.fn(),
  freeze: vi.fn(),
  approval: vi.fn(),
  activate: vi.fn(),
  metrics: vi.fn(),
  pass: vi.fn(),
  revoke: vi.fn(),
}));

vi.mock("@/lib/admin-api-gate", () => ({
  adminApi:
    (_routeKey: string, handler: (...args: unknown[]) => unknown) =>
    (request: NextRequest) =>
      handler(request, {
        session: {
          user: {
            id: "synthetic-admin",
            email: "admin@synthetic.test",
            practiceId: "synthetic-practice",
          },
        },
        verifiedSessionId: "synthetic-live-session",
        routeKey: "template-twin:releases:test",
      }),
}));

vi.mock("@/lib/template-twin/release-control", () => ({
  inspectTemplateTwinReleaseControl: mocks.inspect,
  createTemplateTwinReleaseCandidate: mocks.create,
  freezeTemplateTwinReleaseCandidate: mocks.freeze,
  recordTemplateTwinReleaseApproval: mocks.approval,
  activateTemplateTwinReleaseCheckpoint: mocks.activate,
  recordTemplateTwinReleaseMetricSnapshot: mocks.metrics,
  passTemplateTwinReleaseCheckpoint: mocks.pass,
  revokeTemplateTwinRelease: mocks.revoke,
  TemplateTwinReleaseControlError: class extends Error {},
}));

import { GET, POST } from "../route";

const exactEvidence = {
  sourceCommitSha: "a".repeat(40),
  baseCommitSha: "b".repeat(40),
  appImageDigest: `sha256:${"c".repeat(64)}`,
  workerImageDigest: `sha256:${"d".repeat(64)}`,
  migratorImageDigest: `sha256:${"e".repeat(64)}`,
  testCensusEvidenceSha256: "1".repeat(64),
  independentReviewEvidenceSha256: "2".repeat(64),
  securityEvidenceSha256: "3".repeat(64),
  migrationRestoreEvidenceSha256: "4".repeat(64),
  officeWordEvidenceSha256: "5".repeat(64),
};
const runtimeInstances = [
  {
    instanceId: "app-1",
    component: "APP",
    imageDigest: exactEvidence.appImageDigest,
  },
  {
    instanceId: "worker-1",
    component: "WORKER",
    imageDigest: exactEvidence.workerImageDigest,
  },
] as const;

function request(
  body: unknown,
  overrides: Record<string, string> = {},
): NextRequest {
  return new NextRequest(
    "https://admin.quillmd.com/api/admin/template-twin/releases",
    {
      method: "POST",
      headers: {
        host: "admin.quillmd.com",
        origin: "https://admin.quillmd.com",
        "x-forwarded-proto": "https",
        "content-type": "application/json",
        ...overrides,
      },
      body: JSON.stringify(body),
    },
  );
}

async function json(response: Response): Promise<Record<string, unknown>> {
  return (await response.json()) as Record<string, unknown>;
}

describe("Template Twin release admin API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.inspect.mockResolvedValue({ global: {}, release: null });
    mocks.create.mockResolvedValue({ releaseId: "synthetic-release" });
  });

  it("rejects cross-origin mutations before parsing or service invocation", async () => {
    const response = (await POST(
      request({ action: "create" }, { origin: "https://app.quillmd.com" }),
    )) as NextResponse;

    expect(response.status).toBe(403);
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("rejects unsupported top-level and nested fields", async () => {
    const base = {
      action: "create",
      confirmation: "CREATE EXACT RELEASE",
      evidence: exactEvidence,
      guardrailPolicy: {},
      authorizedPracticeIds: ["synthetic-practice-1"],
      canaryPracticeIds: ["synthetic-practice-1"],
      runtimeInstances,
    };
    const topLevel = (await POST(
      request({ ...base, unsupported: "reject" }),
    )) as NextResponse;
    const nested = (await POST(
      request({
        ...base,
        evidence: { ...exactEvidence, unsupported: "reject" },
      }),
    )) as NextResponse;

    expect(topLevel.status).toBe(400);
    expect(nested.status).toBe(400);
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("enforces the declared request ceiling", async () => {
    const response = (await POST(
      request(
        { action: "create" },
        { "content-length": String(256 * 1024 + 1) },
      ),
    )) as NextResponse;

    expect(response.status).toBe(400);
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("binds valid creation to the verified live session and typed phrase", async () => {
    const response = (await POST(
      request({
        action: "create",
        confirmation: "CREATE EXACT RELEASE",
        evidence: exactEvidence,
        guardrailPolicy: {},
        authorizedPracticeIds: ["synthetic-practice-1"],
        canaryPracticeIds: ["synthetic-practice-1"],
        runtimeInstances,
      }),
    )) as NextResponse;

    expect(response.status).toBe(200);
    expect(await json(response)).toMatchObject({ ok: true });
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        actor: {
          userId: "synthetic-admin",
          sessionId: "synthetic-live-session",
        },
        confirmation: "CREATE EXACT RELEASE",
        evidence: exactEvidence,
        runtimeInstances,
      }),
    );
  });

  it("scopes inspection authority to the freshly verified operator", async () => {
    const response = (await GET(
      new NextRequest(
        "https://admin.quillmd.com/api/admin/template-twin/releases",
        { headers: { host: "admin.quillmd.com" } },
      ),
    )) as NextResponse;

    expect(response.status).toBe(200);
    expect(mocks.inspect).toHaveBeenCalledWith({
      releaseId: undefined,
      operatorUserId: "synthetic-admin",
    });
  });
});
