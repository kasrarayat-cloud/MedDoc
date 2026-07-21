import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  assertExactDatabasePrincipal: vi.fn(),
}));

vi.mock("./exact-database-principal", () => ({
  assertExactDatabasePrincipal: mocks.assertExactDatabasePrincipal,
}));

import {
  ProductionRuntimeDatabasePrincipalError,
  QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS,
  assertProductionRuntimeDatabasePrincipal,
} from "./production-runtime-principal";

const prisma = { $queryRaw: vi.fn() };

function environment(
  overrides: Readonly<Record<string, string | undefined>> = {},
) {
  return {
    NODE_ENV: "production",
    QUILLMD_SERVICE_ROLE: "physician-app",
    QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.assertExactDatabasePrincipal.mockResolvedValue(undefined);
});

describe("production runtime database-principal profile", () => {
  it("defines the exact reviewed service-role to login/boundary mapping", () => {
    expect(QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS).toEqual({
      "meddoc-pro-app": {
        loginRole: "meddoc_runtime",
        boundaryRole: "quillmd_runtime",
      },
      "physician-app": {
        loginRole: "meddoc_runtime",
        boundaryRole: "quillmd_runtime",
      },
      "template-twin-admin-app": {
        loginRole: "meddoc_runtime",
        boundaryRole: "quillmd_runtime",
      },
      "template-twin-admin-control": {
        loginRole: "meddoc_release_control",
        boundaryRole: "quillmd_release_control",
      },
      "transcribe-md-worker": {
        loginRole: "meddoc_runtime",
        boundaryRole: "quillmd_runtime",
      },
      "template-twin-audit-dispatcher": {
        loginRole: "meddoc_audit_dispatcher",
        boundaryRole: "quillmd_audit_dispatcher",
      },
      "auth-email-dispatcher": {
        loginRole: "meddoc_auth_email_dispatcher",
        boundaryRole: "quillmd_auth_email_dispatcher",
      },
    });
  });

  it.each(Object.entries(QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS))(
    "proves the exact principal for %s",
    async (role, principal) => {
      await expect(
        assertProductionRuntimeDatabasePrincipal({
          prisma,
          environment: environment({ QUILLMD_SERVICE_ROLE: role }),
          syntheticQaResourceBoundaryAllowed: false,
        }),
      ).resolves.toBeUndefined();
      expect(mocks.assertExactDatabasePrincipal).toHaveBeenCalledWith({
        prisma,
        ...principal,
      });
    },
  );

  it("normalizes database proof failures without retaining credentials", async () => {
    mocks.assertExactDatabasePrincipal.mockRejectedValueOnce(
      new Error("postgresql://user:secret@db/private-clinical-value"),
    );
    const rejection = assertProductionRuntimeDatabasePrincipal({
      prisma,
      environment: environment(),
      syntheticQaResourceBoundaryAllowed: false,
    });
    await expect(rejection).rejects.toBeInstanceOf(
      ProductionRuntimeDatabasePrincipalError,
    );
    await expect(rejection).rejects.not.toThrow(/secret|clinical|postgresql/u);
  });

  it.each([
    ["missing role", { QUILLMD_SERVICE_ROLE: undefined }],
    ["unknown role", { QUILLMD_SERVICE_ROLE: "unreviewed-service" }],
    ["non-exact role", { QUILLMD_SERVICE_ROLE: " physician-app " }],
    ["missing profile", { QUILLMD_DATABASE_PRINCIPAL_PROFILE: undefined }],
    [
      "unknown profile",
      { QUILLMD_DATABASE_PRINCIPAL_PROFILE: "legacy-principal-bypass" },
    ],
  ] as const)("fails closed for %s", async (_label, overrides) => {
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: environment(overrides),
        syntheticQaResourceBoundaryAllowed: false,
      }),
    ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
    expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
  });

  it.each(["physician-app", "transcribe-md-worker"] as const)(
    "admits %s in the synthetic profile only after the complete QA resource boundary",
    async (role) => {
      const qaEnvironment = environment({
        QUILLMD_SERVICE_ROLE: role,
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
      });
      await expect(
        assertProductionRuntimeDatabasePrincipal({
          prisma,
          environment: qaEnvironment,
          syntheticQaResourceBoundaryAllowed: false,
        }),
      ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
      await expect(
        assertProductionRuntimeDatabasePrincipal({
          prisma,
          environment: qaEnvironment,
          syntheticQaResourceBoundaryAllowed: true,
        }),
      ).resolves.toBeUndefined();
      expect(mocks.assertExactDatabasePrincipal).toHaveBeenCalledWith({
        prisma,
        ...QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS[role],
      });
    },
  );

  it("normalizes synthetic-QA exact-principal proof failure", async () => {
    mocks.assertExactDatabasePrincipal.mockRejectedValueOnce(
      new Error("synthetic database detail that must not escape"),
    );
    const rejection = assertProductionRuntimeDatabasePrincipal({
      prisma,
      environment: environment({
        QUILLMD_SERVICE_ROLE: "physician-app",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
      }),
      syntheticQaResourceBoundaryAllowed: true,
    });
    await expect(rejection).rejects.toBeInstanceOf(
      ProductionRuntimeDatabasePrincipalError,
    );
    await expect(rejection).rejects.not.toThrow(/synthetic database detail/u);
  });

  it("never admits an administrative or MedDoc Pro service into the synthetic profile", async () => {
    for (const role of [
      "meddoc-pro-app",
      "template-twin-admin-app",
      "template-twin-admin-control",
      "template-twin-audit-dispatcher",
      "auth-email-dispatcher",
    ]) {
      await expect(
        assertProductionRuntimeDatabasePrincipal({
          prisma,
          environment: environment({
            QUILLMD_SERVICE_ROLE: role,
            QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
          }),
          syntheticQaResourceBoundaryAllowed: true,
        }),
      ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
    }
  });

  it("does not impose a production principal profile on local unit processes", async () => {
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: { NODE_ENV: "test" },
        syntheticQaResourceBoundaryAllowed: false,
      }),
    ).resolves.toBeUndefined();
    expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
  });

  it.each([
    ["recognized", "physician-app"],
    ["unknown", "unreviewed-service"],
    ["non-exact", " physician-app "],
  ] as const)(
    "does not let a non-production NODE_ENV suppress a %s configured service role",
    async (_label, role) => {
      await expect(
        assertProductionRuntimeDatabasePrincipal({
          prisma,
          environment: {
            NODE_ENV: "development",
            QUILLMD_SERVICE_ROLE: role,
          },
          syntheticQaResourceBoundaryAllowed: false,
        }),
      ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
      expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
    },
  );

  it("still permits a truly empty local service role when no profile is configured", async () => {
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: {
          NODE_ENV: "test",
          QUILLMD_SERVICE_ROLE: "",
        },
        syntheticQaResourceBoundaryAllowed: false,
      }),
    ).resolves.toBeUndefined();
    expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
  });

  it("rejects an explicitly configured exact profile outside NODE_ENV production", async () => {
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: environment({ NODE_ENV: "development" }),
        syntheticQaResourceBoundaryAllowed: false,
      }),
    ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
    expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
  });

  it("rejects an explicitly configured synthetic profile outside NODE_ENV production", async () => {
    const qaEnvironment = environment({
      NODE_ENV: "development",
      QUILLMD_SERVICE_ROLE: "transcribe-md-worker",
      QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
    });
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: qaEnvironment,
        syntheticQaResourceBoundaryAllowed: false,
      }),
    ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: qaEnvironment,
        syntheticQaResourceBoundaryAllowed: true,
      }),
    ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
    expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
  });

  it("rejects an explicitly configured unknown profile outside NODE_ENV production", async () => {
    await expect(
      assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: environment({
          NODE_ENV: "test",
          QUILLMD_DATABASE_PRINCIPAL_PROFILE: "unreviewed-profile",
        }),
        syntheticQaResourceBoundaryAllowed: false,
      }),
    ).rejects.toBeInstanceOf(ProductionRuntimeDatabasePrincipalError);
    expect(mocks.assertExactDatabasePrincipal).not.toHaveBeenCalled();
  });
});
