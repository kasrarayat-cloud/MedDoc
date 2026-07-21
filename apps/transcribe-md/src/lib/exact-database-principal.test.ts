import { beforeEach, describe, expect, it, vi } from "vitest";

import { EXACT_DATABASE_PRINCIPAL_CONTRACT } from "@meddoc/db/exact-database-principal";

import { assertExactDatabasePrincipal } from "./exact-database-principal";

function principal(overrides: Record<string, unknown> = {}) {
  return {
    serverVersionNumber: 160_013,
    sessionRole: "meddoc_audit_dispatcher",
    sessionSearchPath: "pg_catalog,public",
    loginRole: "meddoc_audit_dispatcher",
    loginCanLogin: true,
    loginSuperuser: false,
    loginCreateDb: false,
    loginCreateRole: false,
    loginInherits: true,
    loginReplication: false,
    loginBypassRls: false,
    loginConnectionLimit: -1,
    loginValidUntil: null,
    loginHasExactVerifier: true,
    loginMemberships: ["quillmd_audit_dispatcher"],
    loginHasAdminMembership: false,
    loginHasNonInheritedMembership: false,
    loginHasSetMembership: false,
    loginHasNonSuperuserGrantor: false,
    loginMembers: [],
    loginHasDirectAuthority: false,
    boundaryRole: "quillmd_audit_dispatcher",
    boundaryCanLogin: false,
    boundarySuperuser: false,
    boundaryCreateDb: false,
    boundaryCreateRole: false,
    boundaryInherits: false,
    boundaryReplication: false,
    boundaryBypassRls: false,
    boundaryConnectionLimit: -1,
    boundaryValidUntil: null,
    boundaryMembers: ["meddoc_audit_dispatcher"],
    boundaryHasAdminMember: false,
    boundaryHasNonInheritedMember: false,
    boundaryHasSetMember: false,
    boundaryHasNonSuperuserGrantor: false,
    boundaryMemberships: [],
    readAllDataClosureIsExact: true,
    boundaryHasPassword: false,
    boundaryAclCount: 5,
    boundaryAclSha256: "synthetic-audit-boundary-sha256",
    applicationAclCount: 1_337,
    applicationAclSha256: "synthetic-application-sha256",
    applicationPublicAclCount: 506,
    applicationPublicAclSha256: "synthetic-public-sha256",
    systemPublicAclCount: 4_096,
    systemPublicAclSha256: "synthetic-system-public-sha256",
    futureDefaultAclCount: 0,
    futureDefaultAclSha256: "synthetic-default-sha256",
    boundaryHasUnexpectedDependency: false,
    graphHasForbiddenGrantor: false,
    databaseHasGlobalRoleSettings: false,
    hasApplicablePolicy: false,
    hasPublicUserMapping: false,
    hasBoundaryUserMapping: false,
    hasForeignDataAuthority: false,
    hasWritableApplicationSchema: false,
    hasUnapprovedApplicationAuthority: false,
    hasUnsafeExecutableCapability: false,
    hasForbiddenLargeObjectFunctionAuthority: false,
    hasLargeObjects: false,
    loginCanConnectCurrentDatabase: true,
    boundaryCanConnectCurrentDatabase: true,
    hasForbiddenDatabaseAuthority: false,
    ...overrides,
  };
}

function client(row: Record<string, unknown>) {
  return {
    $queryRaw: vi.fn().mockResolvedValue([row]),
  };
}

const expectedFalseFields = [
  "loginSuperuser",
  "loginCreateDb",
  "loginCreateRole",
  "loginReplication",
  "loginBypassRls",
  "loginHasAdminMembership",
  "loginHasNonInheritedMembership",
  "loginHasSetMembership",
  "loginHasNonSuperuserGrantor",
  "loginHasDirectAuthority",
  "boundaryCanLogin",
  "boundarySuperuser",
  "boundaryCreateDb",
  "boundaryCreateRole",
  "boundaryInherits",
  "boundaryReplication",
  "boundaryBypassRls",
  "boundaryHasAdminMember",
  "boundaryHasNonInheritedMember",
  "boundaryHasSetMember",
  "boundaryHasNonSuperuserGrantor",
  "boundaryHasPassword",
  "boundaryHasUnexpectedDependency",
  "graphHasForbiddenGrantor",
  "databaseHasGlobalRoleSettings",
  "hasApplicablePolicy",
  "hasPublicUserMapping",
  "hasBoundaryUserMapping",
  "hasForeignDataAuthority",
  "hasWritableApplicationSchema",
  "hasUnapprovedApplicationAuthority",
  "hasUnsafeExecutableCapability",
  "hasForbiddenLargeObjectFunctionAuthority",
  "hasLargeObjects",
  "hasForbiddenDatabaseAuthority",
] as const;

describe("exact dispatcher PostgreSQL principal", () => {
  beforeEach(() => {
    Object.assign(EXACT_DATABASE_PRINCIPAL_CONTRACT, {
      applicationAclCount: 1_337,
      applicationAclSha256: "synthetic-application-sha256",
      applicationPublicAclCount: 506,
      applicationPublicAclSha256: "synthetic-public-sha256",
      systemPublicAclCount: 4_096,
      systemPublicAclSha256: "synthetic-system-public-sha256",
      futureDefaultAclCount: 0,
      futureDefaultAclSha256: "synthetic-default-sha256",
    });
    Object.assign(
      EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries.quillmd_audit_dispatcher,
      { count: 5, sha256: "synthetic-audit-boundary-sha256" },
    );
  });

  it("accepts only the exact login to boundary graph", async () => {
    await expect(
      assertExactDatabasePrincipal({
        prisma: client(principal()),
        loginRole: "meddoc_audit_dispatcher",
        boundaryRole: "quillmd_audit_dispatcher",
      }),
    ).resolves.toBeUndefined();
  });

  it.each([
    [
      "nested boundary membership",
      { boundaryMemberships: ["pg_read_all_data"] },
    ],
    [
      "unexpected boundary member",
      { boundaryMembers: ["meddoc_audit_dispatcher", "other_login"] },
    ],
    ["admin-option edge", { boundaryHasAdminMember: true }],
    [
      "predefined read role closure drift",
      { readAllDataClosureIsExact: false },
    ],
    ["non-inheriting edge", { loginHasNonInheritedMembership: true }],
    ["set-role edge", { loginHasSetMembership: true }],
    ["different authenticated role", { sessionRole: "database_owner" }],
    ["login verifier downgrade", { loginHasExactVerifier: false }],
    ["unsafe session search path", { sessionSearchPath: '"$user", public' }],
    [
      "extra login membership",
      { loginMemberships: ["quillmd_audit_dispatcher", "other_role"] },
    ],
    ["unexpected member of login", { loginMembers: ["other_login"] }],
    ["direct object authority", { loginHasDirectAuthority: true }],
    ["non-superuser membership grantor", { loginHasNonSuperuserGrantor: true }],
    ["boundary ACL digest drift", { boundaryAclSha256: "different" }],
    ["application ACL drift", { applicationAclCount: 1_338 }],
    ["NOLOGIN boundary verifier", { boundaryHasPassword: true }],
    [
      "unapproved application authority",
      { hasUnapprovedApplicationAuthority: true },
    ],
    ["PUBLIC authority drift", { applicationPublicAclCount: 507 }],
    ["system PUBLIC authority drift", { systemPublicAclCount: 4_097 }],
    ["default ACL drift", { futureDefaultAclCount: 1 }],
    [
      "unexpected boundary dependency",
      { boundaryHasUnexpectedDependency: true },
    ],
    ["forbidden membership grantor", { graphHasForbiddenGrantor: true }],
    ["database-wide role setting", { databaseHasGlobalRoleSettings: true }],
    ["PUBLIC policy", { hasApplicablePolicy: true }],
    ["PUBLIC user mapping", { hasPublicUserMapping: true }],
    ["foreign-data authority", { hasForeignDataAuthority: true }],
    ["writable application schema", { hasWritableApplicationSchema: true }],
    ["unsafe executable", { hasUnsafeExecutableCapability: true }],
    [
      "large-object mutation function authority",
      { hasForbiddenLargeObjectFunctionAuthority: true },
    ],
    ["large-object data", { hasLargeObjects: true }],
    ["cross-database authority", { hasForbiddenDatabaseAuthority: true }],
    ["missing current connect", { loginCanConnectCurrentDatabase: false }],
    ["privileged boundary", { boundaryBypassRls: true }],
    ["bounded runtime connections", { loginConnectionLimit: 4 }],
    ["expiring runtime credential", { loginValidUntil: new Date(0) }],
    ["bounded NOLOGIN boundary", { boundaryConnectionLimit: 4 }],
    ["expiring NOLOGIN boundary", { boundaryValidUntil: new Date(0) }],
  ])("rejects %s", async (_label, overrides) => {
    await expect(
      assertExactDatabasePrincipal({
        prisma: client(principal(overrides)),
        loginRole: "meddoc_audit_dispatcher",
        boundaryRole: "quillmd_audit_dispatcher",
      }),
    ).rejects.toThrow("Exact database principal is required");
  });

  it.each(
    expectedFalseFields.flatMap((field) =>
      ([undefined, null] as const).map((missing) => [field, missing] as const),
    ),
  )("rejects missing expected-false %s (%s)", async (field, missing) => {
    await expect(
      assertExactDatabasePrincipal({
        prisma: client(principal({ [field]: missing })),
        loginRole: "meddoc_audit_dispatcher",
        boundaryRole: "quillmd_audit_dispatcher",
      }),
    ).rejects.toThrow("Exact database principal is required");
  });

  it.each(
    ["loginHasExactVerifier", "readAllDataClosureIsExact"].flatMap((field) =>
      ([undefined, null] as const).map((missing) => [field, missing] as const),
    ),
  )("rejects missing expected-true %s (%s)", async (field, missing) => {
    await expect(
      assertExactDatabasePrincipal({
        prisma: client(principal({ [field]: missing })),
        loginRole: "meddoc_audit_dispatcher",
        boundaryRole: "quillmd_audit_dispatcher",
      }),
    ).rejects.toThrow("Exact database principal is required");
  });

  it.each(
    [
      "loginMemberships",
      "loginMembers",
      "boundaryMembers",
      "boundaryMemberships",
    ].flatMap((field) =>
      ([undefined, null] as const).map((missing) => [field, missing] as const),
    ),
  )(
    "rejects missing array %s (%s) with the fixed error",
    async (field, missing) => {
      await expect(
        assertExactDatabasePrincipal({
          prisma: client(principal({ [field]: missing })),
          loginRole: "meddoc_audit_dispatcher",
          boundaryRole: "quillmd_audit_dispatcher",
        }),
      ).rejects.toThrow("Exact database principal is required");
    },
  );
});
