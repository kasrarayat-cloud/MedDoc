import { readFileSync } from "node:fs";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUnique: vi.fn(),
}));

vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: mocks.findUnique } },
}));
vi.mock("next/headers", () => ({ headers: vi.fn() }));

import { getSession } from "@/lib/auth";

const ROOT = path.resolve(__dirname, "../../../..");

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("NODE_ENV", "test");
  vi.stubEnv("AUTH_USE_MOCK", "false");
  mocks.auth.mockResolvedValue(null);
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("MedDoc Pro authentication runtime boundary", () => {
  it("wires current MEDDOC_PRO or SUPER_ADMIN entitlement validation into Auth.js", () => {
    const nextauth = readFileSync(
      path.join(ROOT, "apps/meddoc-pro/src/lib/nextauth.ts"),
      "utf8",
    );
    expect(nextauth).toContain("jwt: createSessionValidationJwtCallback({");
    expect(nextauth).toContain('{ requiredProducts: ["MEDDOC_PRO"] }');
    expect(nextauth).toContain('{ requiredProducts: ["SUPER_ADMIN"] }');
  });

  it("never creates a mock physician session in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("AUTH_USE_MOCK", "true");

    await expect(getSession()).resolves.toBeNull();
    expect(mocks.findUnique).not.toHaveBeenCalled();
  });

  it("retains the explicit mock session only for non-production development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("AUTH_USE_MOCK", "true");

    await expect(getSession()).resolves.toMatchObject({
      user: { id: "mock_user_doctor_01", role: "DOCTOR" },
    });
  });

  it("fails closed when current database identity cannot be read", async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: "synthetic-user",
        email: "synthetic@example.test",
        name: "Synthetic User",
        role: "DOCTOR",
        practiceId: "stale-practice",
      },
    });
    mocks.findUnique.mockRejectedValue(new Error("synthetic outage"));

    await expect(getSession()).resolves.toBeNull();
  });

  it("uses the current database role and tenant instead of stale JWT claims", async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: "synthetic-user",
        email: "synthetic@example.test",
        name: "Synthetic User",
        role: "DOCTOR",
        practiceId: "stale-practice",
      },
    });
    mocks.findUnique.mockResolvedValue({
      role: "STAFF",
      isActive: true,
      practiceId: "current-practice",
    });

    await expect(getSession()).resolves.toMatchObject({
      user: {
        id: "synthetic-user",
        role: "STAFF",
        practiceId: "current-practice",
      },
    });
  });

  it("rejects a deactivated current identity", async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: "synthetic-user",
        role: "DOCTOR",
        practiceId: "current-practice",
      },
    });
    mocks.findUnique.mockResolvedValue({
      role: "DOCTOR",
      isActive: false,
      practiceId: "current-practice",
    });

    await expect(getSession()).resolves.toBeNull();
  });
});
