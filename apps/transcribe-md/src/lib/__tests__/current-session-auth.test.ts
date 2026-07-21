import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  headers: vi.fn(),
  validateSession: vi.fn(),
}));

vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: vi.fn() } },
}));
vi.mock("@meddoc/auth", async (importOriginal) => {
  const actual = (await importOriginal()) as typeof import("@meddoc/auth");
  return { ...actual, validateSession: mocks.validateSession };
});

import { getSession } from "../auth";

function rawSession(overrides: Record<string, unknown> = {}) {
  return {
    user: {
      id: "doctor-current",
      email: "stale-doctor@synthetic.test",
      name: "Stale Synthetic Doctor",
      role: "STAFF",
      practiceId: "practice-current",
      sessionId: "session-current",
      ...overrides,
    },
  };
}

function currentValidation() {
  return {
    id: "session-row-current",
    userId: "doctor-current",
    createdAt: new Date("2026-07-20T10:00:00.000Z"),
    expiresAt: new Date("2026-07-21T10:00:00.000Z"),
    user: {
      id: "doctor-current",
      email: "current-doctor@synthetic.test",
      name: "Current Synthetic Doctor",
      role: "DOCTOR",
      practiceId: "practice-current",
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("ADMIN_PUBLIC_HOST", "admin.quillmd.com");
  vi.stubEnv("PHYSICIAN_PUBLIC_HOST", "app.quillmd.com");
  vi.stubEnv("AUTH_COOKIE_DOMAIN", "");
  vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
  mocks.headers.mockResolvedValue(new Headers({ host: "app.quillmd.com" }));
  mocks.auth.mockResolvedValue(rawSession());
  mocks.validateSession.mockResolvedValue(currentValidation());
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("TranscribeMD current session wrapper", () => {
  it("denies the administrative service before reading a clinical session", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");

    await expect(getSession()).resolves.toBeNull();
    expect(mocks.headers).not.toHaveBeenCalled();
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.validateSession).not.toHaveBeenCalled();
  });

  it("denies an admin-host request handled by the ordinary process", async () => {
    mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));

    await expect(getSession()).resolves.toBeNull();
    expect(mocks.headers).toHaveBeenCalledTimes(1);
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.validateSession).not.toHaveBeenCalled();
  });

  it("returns only the current database identity, including updated email", async () => {
    await expect(getSession()).resolves.toEqual({
      user: {
        id: "doctor-current",
        email: "current-doctor@synthetic.test",
        fullName: "Current Synthetic Doctor",
        role: "DOCTOR",
        practiceId: "practice-current",
      },
    });
    expect(mocks.validateSession).toHaveBeenCalledWith({
      sessionToken: "session-current",
      expectedUserId: "doctor-current",
      expectedPracticeId: "practice-current",
      allowedRoles: ["DOCTOR"],
      requiredProducts: ["TRANSCRIBE_MD"],
    });
  });

  it("denies a raw fixture without the required session binding", async () => {
    mocks.auth.mockResolvedValue(rawSession({ sessionId: undefined }));

    await expect(getSession()).resolves.toBeNull();
    expect(mocks.validateSession).not.toHaveBeenCalled();
  });

  it("fails closed when validation errors or rejects current authority", async () => {
    mocks.validateSession.mockRejectedValueOnce(
      new Error("synthetic validator outage"),
    );
    await expect(getSession()).resolves.toBeNull();

    mocks.validateSession.mockResolvedValueOnce(null);
    await expect(getSession()).resolves.toBeNull();
  });
});
