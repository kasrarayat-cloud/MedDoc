import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  headers: vi.fn(),
  findUser: vi.fn(),
  pinRollout: vi.fn(),
}));

vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("next/headers", () => ({ headers: mocks.headers }));
vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: mocks.findUser } },
}));
vi.mock("@/lib/template-twin/rollout", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/template-twin/rollout")>();
  return {
    ...actual,
    pinTemplateTwinRollout: mocks.pinRollout,
  };
});

import { requireDoctorSession } from "../auth";

function currentPhysician(overrides: Record<string, unknown> = {}) {
  return {
    id: "user-synthetic-role",
    email: "current-role-user@synthetic.test",
    name: "Current Synthetic Role User",
    role: "DOCTOR",
    isActive: true,
    practiceId: "practice-current",
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    products: ["TRANSCRIBE_MD"],
    practice: {
      id: "practice-current",
      isActive: true,
      templateTwinEnabled: true,
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("ADMIN_PUBLIC_HOST", "admin.quillmd.com");
  vi.stubEnv("PHYSICIAN_PUBLIC_HOST", "app.quillmd.com");
  vi.stubEnv("AUTH_COOKIE_DOMAIN", "");
  vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");
  vi.stubEnv("TEMPLATE_TWIN_KILL_SWITCH", "false");
  mocks.headers.mockResolvedValue(new Headers({ host: "app.quillmd.com" }));
  mocks.pinRollout.mockResolvedValue({
    practiceId: "practice-current",
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
  mocks.auth.mockResolvedValue({
    user: {
      id: "user-synthetic-role",
      email: "role-user@synthetic.test",
      name: "Synthetic Role User",
      role: "DOCTOR",
      practiceId: "practice-stale-jwt",
      sessionId: "session-current-synthetic",
    },
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("Template Twin fresh physician authorization", () => {
  it("denies the administrative service before reading a physician session", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.headers).not.toHaveBeenCalled();
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
  });

  it("denies an admin-host request handled by the ordinary process", async () => {
    mocks.headers.mockResolvedValue(new Headers({ host: "admin.quillmd.com" }));

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.headers).toHaveBeenCalledTimes(1);
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.findUser).not.toHaveBeenCalled();
  });

  it("rejects a raw auth fixture without a current session binding", async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: "user-synthetic-role",
        email: "role-user@synthetic.test",
        name: "Synthetic Role User",
        role: "DOCTOR",
        practiceId: "practice-current",
      },
    });

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "UNAUTHENTICATED",
    });
    expect(mocks.findUser).not.toHaveBeenCalled();
  });

  it.each(["STAFF", "ADMIN"] as const)(
    "rejects a stale DOCTOR JWT when the current database role is %s",
    async (role) => {
      mocks.findUser.mockResolvedValue(currentPhysician({ role }));

      await expect(requireDoctorSession()).rejects.toMatchObject({
        code: "FORBIDDEN",
      });
      expect(mocks.findUser).toHaveBeenCalledTimes(1);
      expect(mocks.findUser).toHaveBeenCalledWith({
        where: { id: "user-synthetic-role" },
        select: {
          id: true,
          email: true,
          name: true,
          role: true,
          isActive: true,
          practiceId: true,
          deactivatedAt: true,
          suspendedAt: true,
          softDeletedAt: true,
          products: true,
          practice: {
            select: {
              id: true,
              isActive: true,
              templateTwinEnabled: true,
            },
          },
        },
      });
    },
  );

  it("uses fresh physician identity while preserving the exact session tenant", async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: "user-synthetic-role",
        email: "role-user@synthetic.test",
        name: "Synthetic Role User",
        role: "STAFF",
        practiceId: "practice-current",
        sessionId: "session-current-synthetic",
      },
    });
    mocks.findUser.mockResolvedValue(currentPhysician());

    await expect(requireDoctorSession()).resolves.toMatchObject({
      templateTwinRolloutToken: {
        practiceId: "practice-current",
        globalGeneration: BigInt(1),
        practiceGeneration: BigInt(1),
      },
      user: {
        id: "user-synthetic-role",
        email: "current-role-user@synthetic.test",
        fullName: "Current Synthetic Role User",
        role: "DOCTOR",
        practiceId: "practice-current",
      },
    });
    expect(mocks.pinRollout).toHaveBeenCalledWith({
      practiceId: "practice-current",
    });
  });

  it("rejects a practice transfer that races the raw session check", async () => {
    mocks.auth.mockResolvedValue({
      user: {
        id: "user-synthetic-role",
        email: "role-user@synthetic.test",
        name: "Synthetic Role User",
        role: "DOCTOR",
        practiceId: "practice-stale-jwt",
        sessionId: "session-current-synthetic",
      },
    });
    mocks.findUser.mockResolvedValue(currentPhysician());

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
  });

  it("fails closed when fresh database role evidence is unavailable", async () => {
    mocks.findUser.mockRejectedValue(new Error("Synthetic database outage"));

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
  });

  it("rejects an inactive physician", async () => {
    mocks.findUser.mockResolvedValue(currentPhysician({ isActive: false }));

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
  });

  it("rejects a physician whose current practice is inactive", async () => {
    mocks.findUser.mockResolvedValue(
      currentPhysician({
        practice: {
          id: "practice-current",
          isActive: false,
          templateTwinEnabled: true,
        },
      }),
    );

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.pinRollout).not.toHaveBeenCalled();
  });

  it("fails closed when the owning practice rollout flag is disabled", async () => {
    mocks.findUser.mockResolvedValue(
      currentPhysician({
        practice: {
          id: "practice-current",
          isActive: true,
          templateTwinEnabled: false,
        },
      }),
    );

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
      message: "Template Twin is not enabled for this practice.",
    });
  });

  it("fails closed when the global kill switch is not explicitly disabled", async () => {
    delete process.env.TEMPLATE_TWIN_KILL_SWITCH;
    mocks.findUser.mockResolvedValue(currentPhysician());

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
      message: "Template Twin is temporarily unavailable.",
    });
  });

  it.each([
    ["deactivatedAt", new Date("2026-07-20T00:00:00.000Z")],
    ["suspendedAt", new Date("2026-07-20T00:00:00.000Z")],
    ["softDeletedAt", new Date("2026-07-20T00:00:00.000Z")],
  ] as const)(
    "rejects a physician with current %s set",
    async (field, value) => {
      mocks.findUser.mockResolvedValue(currentPhysician({ [field]: value }));

      await expect(requireDoctorSession()).rejects.toMatchObject({
        code: "FORBIDDEN",
      });
      expect(mocks.pinRollout).not.toHaveBeenCalled();
    },
  );

  it("rejects a physician without the Transcribe MD product entitlement", async () => {
    mocks.findUser.mockResolvedValue(currentPhysician({ products: [] }));

    await expect(requireDoctorSession()).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(mocks.pinRollout).not.toHaveBeenCalled();
  });
});
