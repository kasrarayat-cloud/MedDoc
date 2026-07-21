import { assertExactDatabasePrincipal } from "./exact-database-principal";
import { assertPostgresHostAuthenticationContract } from "./postgres-host-auth";

export const QUILLMD_DATABASE_PRINCIPAL_PROFILE_ENV =
  "QUILLMD_DATABASE_PRINCIPAL_PROFILE" as const;
export const QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE =
  "exact-production-v1" as const;
export const QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE =
  "synthetic-disposable-qa-v1" as const;

export const QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS = Object.freeze({
  "meddoc-pro-app": Object.freeze({
    loginRole: "meddoc_runtime",
    boundaryRole: "quillmd_runtime",
  }),
  "physician-app": Object.freeze({
    loginRole: "meddoc_runtime",
    boundaryRole: "quillmd_runtime",
  }),
  "template-twin-admin-app": Object.freeze({
    loginRole: "meddoc_runtime",
    boundaryRole: "quillmd_runtime",
  }),
  "template-twin-admin-control": Object.freeze({
    loginRole: "meddoc_release_control",
    boundaryRole: "quillmd_release_control",
  }),
  "transcribe-md-worker": Object.freeze({
    loginRole: "meddoc_runtime",
    boundaryRole: "quillmd_runtime",
  }),
  "template-twin-audit-dispatcher": Object.freeze({
    loginRole: "meddoc_audit_dispatcher",
    boundaryRole: "quillmd_audit_dispatcher",
  }),
  "auth-email-dispatcher": Object.freeze({
    loginRole: "meddoc_auth_email_dispatcher",
    boundaryRole: "quillmd_auth_email_dispatcher",
  }),
} as const);

export type QuillmdProductionRuntimeServiceRole =
  keyof typeof QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS;

type ExactPrincipalClient = Parameters<
  typeof assertExactDatabasePrincipal
>[0]["prisma"];

const SYNTHETIC_QA_SERVICE_ROLES = new Set<QuillmdProductionRuntimeServiceRole>(
  ["physician-app", "transcribe-md-worker"],
);

export class ProductionRuntimeDatabasePrincipalError extends Error {
  readonly code = "PRODUCTION_RUNTIME_DATABASE_PRINCIPAL_INVALID";

  constructor() {
    super(
      "The production runtime database-principal configuration is invalid.",
    );
    this.name = "ProductionRuntimeDatabasePrincipalError";
  }
}

function productionRuntimeServiceRole(
  environment: Readonly<Record<string, string | undefined>>,
): QuillmdProductionRuntimeServiceRole {
  const role = environment.QUILLMD_SERVICE_ROLE ?? "";
  if (
    !Object.prototype.hasOwnProperty.call(
      QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS,
      role,
    )
  ) {
    throw new ProductionRuntimeDatabasePrincipalError();
  }
  return role as QuillmdProductionRuntimeServiceRole;
}

/**
 * Production startup gate for every reviewed QuillMD database login. Exact
 * mode proves the PostgreSQL login/boundary graph. The disposable synthetic QA
 * app/worker pair uses the same exact database proof and is admitted only after
 * its caller has also evaluated the complete synthetic resource boundary.
 */
export async function assertProductionRuntimeDatabasePrincipal(input: {
  prisma: ExactPrincipalClient;
  environment: Readonly<Record<string, string | undefined>>;
  syntheticQaResourceBoundaryAllowed: boolean;
}): Promise<void> {
  const profile = input.environment[QUILLMD_DATABASE_PRINCIPAL_PROFILE_ENV];
  const configuredServiceRole = input.environment.QUILLMD_SERVICE_ROLE;
  if (
    input.environment.NODE_ENV?.trim().toLowerCase() !== "production" &&
    profile === undefined &&
    (configuredServiceRole === undefined || configuredServiceRole.length === 0)
  ) {
    return;
  }

  if (input.environment.NODE_ENV !== "production") {
    throw new ProductionRuntimeDatabasePrincipalError();
  }

  const role = productionRuntimeServiceRole(input.environment);
  if (profile === QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE) {
    try {
      await assertPostgresHostAuthenticationContract({ prisma: input.prisma });
      await assertExactDatabasePrincipal({
        prisma: input.prisma,
        ...QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS[role],
      });
    } catch {
      throw new ProductionRuntimeDatabasePrincipalError();
    }
    return;
  }
  if (
    profile === QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE &&
    SYNTHETIC_QA_SERVICE_ROLES.has(role) &&
    input.syntheticQaResourceBoundaryAllowed
  ) {
    try {
      await assertPostgresHostAuthenticationContract({ prisma: input.prisma });
      await assertExactDatabasePrincipal({
        prisma: input.prisma,
        ...QUILLMD_PRODUCTION_RUNTIME_DATABASE_PRINCIPALS[role],
      });
    } catch {
      throw new ProductionRuntimeDatabasePrincipalError();
    }
    return;
  }
  throw new ProductionRuntimeDatabasePrincipalError();
}
