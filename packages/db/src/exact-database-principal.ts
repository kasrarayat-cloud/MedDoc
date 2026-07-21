import type { Prisma } from "@prisma/client";

import {
  type ExactPrincipalCatalogRow,
  exactDatabasePrincipalCatalogQuery,
} from "./exact-database-principal-query";

interface PrincipalQueryClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

/** PostgreSQL 16 catalog contract derived from two isolated, pinned-image
 * clusters and frozen by additive migration v9. */
export const EXACT_DATABASE_PRINCIPAL_CONTRACT = {
  postgresMajor: 16,
  applicationAclCount: 4_141,
  applicationAclSha256:
    "17af3f8af88bf594576f30c2cfa9bd6b1ee78b7e1447a9064ca657b71c1cfdd6",
  applicationPublicAclCount: 504,
  applicationPublicAclSha256:
    "d5e24c7cd5c7b20491973623e3f2387eb72dd2461f78a931897345b5cfd8ad16",
  systemPublicAclCount: 4_046,
  systemPublicAclSha256:
    "b2bf14053b1e8d8a0f135bd315f1c2c79a97f6957ab6a718fbed67c4aaf69746",
  futureDefaultAclCount: 0,
  futureDefaultAclSha256:
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  boundaries: {
    quillmd_runtime: {
      loginBypassRls: false,
      loginConnectionLimit: -1,
      boundaryMemberships: [] as string[],
      count: 260,
      sha256:
        "9a57516235a2bf6e05d78ece57b36a8181b0940517dbac327b2ec38fecb08491",
    },
    quillmd_release_control: {
      loginBypassRls: false,
      loginConnectionLimit: -1,
      boundaryMemberships: [] as string[],
      count: 53,
      sha256:
        "1b19ff4639456ed2198b33093733743bf844ff1b0ea535cd96fae987401eb9d2",
    },
    quillmd_release_security: {
      loginBypassRls: false,
      loginConnectionLimit: -1,
      boundaryMemberships: [] as string[],
      count: 3,
      sha256:
        "08d8966d88162b49e4a19e8e0054a8d507a1d6830bedefc7a6267d852a83974d",
    },
    quillmd_audit_dispatcher: {
      loginBypassRls: false,
      loginConnectionLimit: -1,
      boundaryMemberships: [] as string[],
      count: 7,
      sha256:
        "3bcd5b8e7e9a2a11004d05e262a44dcbfccc4cd835e9ac8db844cb76425205ca",
    },
    quillmd_auth_email_dispatcher: {
      loginBypassRls: false,
      loginConnectionLimit: -1,
      boundaryMemberships: [] as string[],
      count: 10,
      sha256:
        "dc350422fa6da53ea697ba61956de992022ed3daad93f80227698d361be6e9a3",
    },
    quillmd_backup: {
      loginBypassRls: true,
      loginConnectionLimit: 1,
      boundaryMemberships: ["pg_read_all_data"] as string[],
      count: 2,
      sha256:
        "e059a6bf37ca30b019ce585d518ae8d8441ec09aa864a3a1e323065b31a58fe5",
    },
  },
} as const;

export const EXACT_BOUNDARY_ACL_SHA256 = Object.fromEntries(
  Object.entries(EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries).map(
    ([role, value]) => [role, value.sha256],
  ),
) as Record<keyof typeof EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries, string>;

export async function assertExactDatabasePrincipal(input: {
  prisma: PrincipalQueryClient;
  loginRole: string;
  boundaryRole: string;
}): Promise<void> {
  const expected =
    EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries[
      input.boundaryRole as keyof typeof EXACT_DATABASE_PRINCIPAL_CONTRACT.boundaries
    ];
  if (
    !expected ||
    expected.count < 0 ||
    expected.sha256.startsWith("PENDING_") ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationAclCount < 0 ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationAclSha256.startsWith(
      "PENDING_",
    ) ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationPublicAclCount < 0 ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationPublicAclSha256.startsWith(
      "PENDING_",
    ) ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.systemPublicAclCount < 0 ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.systemPublicAclSha256.startsWith(
      "PENDING_",
    ) ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.futureDefaultAclCount < 0 ||
    EXACT_DATABASE_PRINCIPAL_CONTRACT.futureDefaultAclSha256.startsWith(
      "PENDING_",
    )
  ) {
    throw new Error("Exact database principal is required.");
  }

  const rows = await input.prisma.$queryRaw<ExactPrincipalCatalogRow[]>(
    exactDatabasePrincipalCatalogQuery(input),
  );
  const principal = rows[0];
  if (
    rows.length !== 1 ||
    !principal ||
    Math.trunc(principal.serverVersionNumber / 10_000) !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.postgresMajor ||
    principal.sessionRole !== input.loginRole ||
    principal.sessionSearchPath !== "pg_catalog,public" ||
    principal.loginRole !== input.loginRole ||
    principal.loginCanLogin !== true ||
    principal.loginSuperuser !== false ||
    principal.loginCreateDb !== false ||
    principal.loginCreateRole !== false ||
    principal.loginInherits !== true ||
    principal.loginReplication !== false ||
    principal.loginBypassRls !== expected.loginBypassRls ||
    principal.loginConnectionLimit !== expected.loginConnectionLimit ||
    principal.loginValidUntil !== null ||
    principal.loginHasExactVerifier !== true ||
    principal.loginHasAdminMembership !== false ||
    principal.loginHasNonInheritedMembership !== false ||
    principal.loginHasSetMembership !== false ||
    principal.loginHasNonSuperuserGrantor !== false ||
    !Array.isArray(principal.loginMemberships) ||
    principal.loginMemberships.length !== 1 ||
    principal.loginMemberships[0] !== input.boundaryRole ||
    !Array.isArray(principal.loginMembers) ||
    principal.loginMembers.length !== 0 ||
    principal.loginHasDirectAuthority !== false ||
    principal.boundaryRole !== input.boundaryRole ||
    principal.boundaryCanLogin !== false ||
    principal.boundarySuperuser !== false ||
    principal.boundaryCreateDb !== false ||
    principal.boundaryCreateRole !== false ||
    principal.boundaryInherits !== false ||
    principal.boundaryReplication !== false ||
    principal.boundaryBypassRls !== false ||
    principal.boundaryConnectionLimit !== -1 ||
    principal.boundaryValidUntil !== null ||
    principal.boundaryHasAdminMember !== false ||
    principal.boundaryHasNonInheritedMember !== false ||
    principal.boundaryHasSetMember !== false ||
    principal.boundaryHasNonSuperuserGrantor !== false ||
    !Array.isArray(principal.boundaryMembers) ||
    principal.boundaryMembers.length !== 1 ||
    principal.boundaryMembers[0] !== input.loginRole ||
    !Array.isArray(principal.boundaryMemberships) ||
    principal.boundaryMemberships.length !==
      expected.boundaryMemberships.length ||
    principal.boundaryMemberships.some(
      (membership, index) => membership !== expected.boundaryMemberships[index],
    ) ||
    principal.readAllDataClosureIsExact !== true ||
    principal.boundaryHasPassword !== false ||
    principal.boundaryAclCount !== expected.count ||
    principal.boundaryAclSha256 !== expected.sha256 ||
    principal.applicationAclCount !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationAclCount ||
    principal.applicationAclSha256 !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationAclSha256 ||
    principal.applicationPublicAclCount !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationPublicAclCount ||
    principal.applicationPublicAclSha256 !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.applicationPublicAclSha256 ||
    principal.systemPublicAclCount !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.systemPublicAclCount ||
    principal.systemPublicAclSha256 !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.systemPublicAclSha256 ||
    principal.futureDefaultAclCount !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.futureDefaultAclCount ||
    principal.futureDefaultAclSha256 !==
      EXACT_DATABASE_PRINCIPAL_CONTRACT.futureDefaultAclSha256 ||
    principal.boundaryHasUnexpectedDependency !== false ||
    principal.graphHasForbiddenGrantor !== false ||
    principal.databaseHasGlobalRoleSettings !== false ||
    principal.hasApplicablePolicy !== false ||
    principal.hasPublicUserMapping !== false ||
    principal.hasBoundaryUserMapping !== false ||
    principal.hasForeignDataAuthority !== false ||
    principal.hasWritableApplicationSchema !== false ||
    principal.hasUnapprovedApplicationAuthority !== false ||
    principal.hasUnsafeExecutableCapability !== false ||
    principal.hasForbiddenLargeObjectFunctionAuthority !== false ||
    principal.hasLargeObjects !== false ||
    principal.loginCanConnectCurrentDatabase !== true ||
    principal.boundaryCanConnectCurrentDatabase !== true ||
    principal.hasForbiddenDatabaseAuthority !== false
  ) {
    throw new Error("Exact database principal is required.");
  }
}
