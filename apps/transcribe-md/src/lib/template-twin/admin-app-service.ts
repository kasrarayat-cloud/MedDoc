import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";

export const TEMPLATE_TWIN_ADMIN_APP_SERVICE_ROLE =
  "template-twin-admin-app" as const;
export const TEMPLATE_TWIN_ADMIN_CONTROL_SERVICE_ROLE =
  "template-twin-admin-control" as const;
export const TRANSCRIBE_MD_PHYSICIAN_APP_SERVICE_ROLE =
  "physician-app" as const;

export const TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH =
  "/settings/note-format/static-assets" as const;
export const TEMPLATE_TWIN_STATIC_ASSET_ADMIN_API_PATH =
  "/api/note-templates/template-twin/static-assets" as const;
export const TEMPLATE_TWIN_ADMIN_APP_HEALTH_PATH =
  "/api/health/template-twin-admin-app" as const;
export const TEMPLATE_TWIN_RELEASE_CONTROL_PATH =
  "/admin/template-twin-release" as const;
export const TEMPLATE_TWIN_RELEASE_CONTROL_API_PATH =
  "/api/admin/template-twin/releases" as const;
export const TEMPLATE_TWIN_RELEASE_METRICS_API_PATH =
  "/api/admin/template-twin/release-metrics" as const;
export const TEMPLATE_TWIN_RELEASE_CONTROL_HEALTH_PATH =
  "/api/admin/template-twin/control-health" as const;
export const TEMPLATE_TWIN_ROLLBACK_API_PATH =
  "/api/admin/template-twin/rollback" as const;
export const TEMPLATE_TWIN_ADMIN_MFA_PATH =
  "/settings/security/mfa?reason=super_admin_required" as const;

const ADMIN_APP_EXACT_PATHS = new Set<string>([
  "/login",
  "/forgot-password",
  "/reset-password",
  "/check-email",
  "/settings/security/mfa",
  "/api/mfa/enroll",
  "/api/mfa/verify-enrollment",
  "/api/mfa/recovery-codes/rotate",
  TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH,
  TEMPLATE_TWIN_STATIC_ASSET_ADMIN_API_PATH,
  TEMPLATE_TWIN_ADMIN_APP_HEALTH_PATH,
  TEMPLATE_TWIN_ROLLBACK_API_PATH,
  "/favicon.ico",
  "/favicon.svg",
  "/robots.txt",
  "/manifest.webmanifest",
]);

const ADMIN_CONTROL_EXACT_PATHS = new Set<string>([
  TEMPLATE_TWIN_RELEASE_CONTROL_PATH,
  TEMPLATE_TWIN_RELEASE_CONTROL_API_PATH,
  TEMPLATE_TWIN_RELEASE_METRICS_API_PATH,
  TEMPLATE_TWIN_RELEASE_CONTROL_HEALTH_PATH,
]);

interface AdminAppAccessCandidate {
  readonly role: string;
  readonly products: readonly string[];
  readonly mfaEnabled?: boolean;
  readonly mfaSecret?: string | null;
  readonly mfaVerifiedAt?: Date | null;
}

type ServiceEnvironment = Readonly<Record<string, string | undefined>>;

/**
 * The ordinary TranscribeMD process remains physician-only. Administrative
 * cookies are minted and refreshed only by the separately routed admin app
 * process, whose protected routes still perform their narrower current-state
 * SUPER_ADMIN or practice-admin checks.
 */
export function isTemplateTwinAdminAppService(
  environment: ServiceEnvironment = process.env,
): boolean {
  return (
    environment.QUILLMD_SERVICE_ROLE === TEMPLATE_TWIN_ADMIN_APP_SERVICE_ROLE
  );
}

export function isTranscribeMdPhysicianAppService(
  environment: ServiceEnvironment = process.env,
): boolean {
  return (
    environment.QUILLMD_SERVICE_ROLE ===
    TRANSCRIBE_MD_PHYSICIAN_APP_SERVICE_ROLE
  );
}

export function isTemplateTwinAdminControlService(
  environment: ServiceEnvironment = process.env,
): boolean {
  return (
    environment.QUILLMD_SERVICE_ROLE ===
    TEMPLATE_TWIN_ADMIN_CONTROL_SERVICE_ROLE
  );
}

/** Exact process-level route surface. Caddy is not the only boundary: a
 * direct container request or future proxy mistake receives the same 404. */
export function isTemplateTwinAdminAppPathAllowed(pathname: string): boolean {
  return (
    ADMIN_APP_EXACT_PATHS.has(pathname) ||
    pathname === "/api/auth" ||
    pathname.startsWith("/api/auth/") ||
    pathname.startsWith("/_next/static/")
  );
}

/** The privileged release-control process serves only its reviewed control
 * surface, even when reached without Caddy. Same-image physician, practice
 * admin, authentication, and unreviewed control routes remain unreachable. */
export function isTemplateTwinAdminControlPathAllowed(
  pathname: string,
): boolean {
  return (
    ADMIN_CONTROL_EXACT_PATHS.has(pathname) ||
    pathname.startsWith(`${TEMPLATE_TWIN_RELEASE_CONTROL_PATH}/`) ||
    pathname.startsWith(`${TEMPLATE_TWIN_RELEASE_CONTROL_API_PATH}/`) ||
    pathname.startsWith(`${TEMPLATE_TWIN_RELEASE_METRICS_API_PATH}/`) ||
    pathname.startsWith("/_next/static/")
  );
}

export function isTranscribeMdPhysicianProxyPath(pathname: string): boolean {
  return ["/dashboard", "/visits", "/settings"].some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/**
 * Platform administrators are product-authorized in the existing schema and
 * may retain a clinical role. Practice static-asset administrators require
 * both a practice-admin role and the TranscribeMD product.
 */
export function hasTemplateTwinAdminAppAccess(
  candidate: AdminAppAccessCandidate,
): boolean {
  return (
    candidate.products.includes("SUPER_ADMIN") ||
    ((candidate.role === "ADMIN" || candidate.role === "SUPER_ADMIN") &&
      candidate.products.includes("TRANSCRIBE_MD"))
  );
}

export function templateTwinAdminLandingPath(
  candidate: AdminAppAccessCandidate,
):
  | typeof TEMPLATE_TWIN_RELEASE_CONTROL_PATH
  | typeof TEMPLATE_TWIN_ADMIN_MFA_PATH
  | typeof TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH
  | null {
  // The ordinary `/admin` upstream still applies the physician process's
  // DOCTOR + TRANSCRIBE_MD raw-session policy. Keep platform operators on
  // controlled MFA enrollment/repair until every enrollment field is current,
  // then cross into the isolated release-control process.
  if (candidate.products.includes("SUPER_ADMIN")) {
    return hasCompleteMfaEnrollment(candidate)
      ? TEMPLATE_TWIN_RELEASE_CONTROL_PATH
      : TEMPLATE_TWIN_ADMIN_MFA_PATH;
  }
  if (hasTemplateTwinAdminAppAccess(candidate)) {
    return TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH;
  }
  return null;
}

export const TEMPLATE_TWIN_ADMIN_APP_SESSION_POLICY = {
  anyOf: [
    {
      allowedRoles: ["ADMIN", "SUPER_ADMIN"],
      requiredProducts: ["TRANSCRIBE_MD"],
    },
    { requiredProducts: ["SUPER_ADMIN"] },
  ],
} as const;

export const TRANSCRIBE_MD_PHYSICIAN_SESSION_POLICY = {
  allowedRoles: ["DOCTOR"],
  requiredProducts: ["TRANSCRIBE_MD"],
} as const;

/** Missing, misspelled, worker, or privileged control identities never inherit
 * physician session authority. The production control process uses its narrow
 * SQL session verifier after JWT claim parsing and does not consume this grant. */
export const TRANSCRIBE_MD_DENY_SESSION_POLICY = {
  anyOf: [],
} as const;

export function transcribeMdSessionPolicyForService(
  environment: ServiceEnvironment = process.env,
) {
  if (isTemplateTwinAdminAppService(environment)) {
    return TEMPLATE_TWIN_ADMIN_APP_SESSION_POLICY;
  }
  if (isTranscribeMdPhysicianAppService(environment)) {
    return TRANSCRIBE_MD_PHYSICIAN_SESSION_POLICY;
  }
  return TRANSCRIBE_MD_DENY_SESSION_POLICY;
}
