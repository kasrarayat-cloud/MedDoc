const PRODUCTION_ADMIN_HOST = "admin.quillmd.com";
const PRODUCTION_PHYSICIAN_HOST = "app.quillmd.com";
export const ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION =
  "accepted-isolated-synthetic-qa-shared-host";

type HostEnvironment = Partial<
  Pick<
    NodeJS.ProcessEnv,
    | "ADMIN_PUBLIC_HOST"
    | "PHYSICIAN_PUBLIC_HOST"
    | "AUTH_COOKIE_DOMAIN"
    | "ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION"
    | "TEMPLATE_TWIN_STORAGE_PROFILE"
    | "NODE_ENV"
  >
>;

function normalizeHost(value: string | null | undefined): string | null {
  const raw = value?.trim().toLowerCase().replace(/\.$/u, "");
  if (!raw || raw.includes("/") || raw.includes("\\") || raw.includes("@")) {
    return null;
  }

  if (raw.startsWith("[")) {
    const closingBracket = raw.indexOf("]");
    if (closingBracket < 0) return null;
    const suffix = raw.slice(closingBracket + 1);
    if (suffix && !/^:\d+$/u.test(suffix)) return null;
    return raw.slice(0, closingBracket + 1);
  }

  const colon = raw.lastIndexOf(":");
  if (colon >= 0) {
    const port = raw.slice(colon + 1);
    if (!/^\d+$/u.test(port)) return null;
    return raw.slice(0, colon);
  }
  return raw;
}

function configuredAdminHostUnchecked(
  environment: HostEnvironment = process.env,
): string | null {
  const configured = normalizeHost(environment.ADMIN_PUBLIC_HOST);
  if (environment.ADMIN_PUBLIC_HOST !== undefined) return configured;
  return environment.NODE_ENV === "production" ? PRODUCTION_ADMIN_HOST : null;
}

function configuredPhysicianHost(
  environment: HostEnvironment = process.env,
): string | null {
  const configured = normalizeHost(environment.PHYSICIAN_PUBLIC_HOST);
  if (environment.PHYSICIAN_PUBLIC_HOST !== undefined) return configured;
  return environment.NODE_ENV === "production"
    ? PRODUCTION_PHYSICIAN_HOST
    : null;
}

/**
 * Exact physician-origin boundary for request-scoped clinical authorization.
 * Production and explicitly configured environments require the reviewed
 * physician hostname. Local development without a physician hostname remains
 * usable, but an explicitly configured admin hostname is still excluded.
 */
export function isPhysicianRequestHost(
  headers: Pick<Headers, "get">,
  environment: HostEnvironment = process.env,
): boolean {
  if (adminSurfaceConfigurationError(environment)) return false;
  const expected = configuredPhysicianHost(environment);
  if (environment.PHYSICIAN_PUBLIC_HOST !== undefined && !expected) {
    return false;
  }
  const actual = normalizeHost(headers.get("host"));
  if (expected) return actual === expected;
  if (environment.NODE_ENV === "production") return false;
  const adminHost = configuredAdminHostUnchecked(environment);
  return actual !== null && (!adminHost || actual !== adminHost);
}

function permitsSyntheticQaSharedHost(environment: HostEnvironment): boolean {
  return (
    environment.TEMPLATE_TWIN_STORAGE_PROFILE === "qa" &&
    environment.ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION ===
      ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION
  );
}

/**
 * Returns a fixed, credential-free reason when runtime configuration would
 * collapse the physician/admin origin boundary. Production accepts only the
 * reviewed admin hostname. The one shared-host exception is explicit and
 * limited to the isolated synthetic QA profile.
 */
export function adminSurfaceConfigurationError(
  environment: HostEnvironment = process.env,
): string | null {
  const adminHost = configuredAdminHostUnchecked(environment);
  const physicianHost = configuredPhysicianHost(environment);
  if (environment.ADMIN_PUBLIC_HOST !== undefined && !adminHost) {
    return "ADMIN_PUBLIC_HOST_INVALID";
  }
  if (environment.PHYSICIAN_PUBLIC_HOST !== undefined && !physicianHost) {
    return "PHYSICIAN_PUBLIC_HOST_INVALID";
  }
  if (environment.AUTH_COOKIE_DOMAIN?.trim()) {
    return "ADMIN_COOKIE_MUST_BE_HOST_ONLY";
  }

  const qaSharedHost =
    permitsSyntheticQaSharedHost(environment) &&
    adminHost !== null &&
    adminHost === physicianHost;
  if (
    environment.NODE_ENV === "production" &&
    adminHost !== PRODUCTION_ADMIN_HOST &&
    !qaSharedHost
  ) {
    return "PRODUCTION_ADMIN_HOST_NOT_REVIEWED";
  }
  if (
    environment.NODE_ENV === "production" &&
    physicianHost !== PRODUCTION_PHYSICIAN_HOST &&
    !qaSharedHost
  ) {
    return "PRODUCTION_PHYSICIAN_HOST_NOT_REVIEWED";
  }
  if (
    adminHost &&
    physicianHost &&
    adminHost === physicianHost &&
    !qaSharedHost
  ) {
    return "ADMIN_PHYSICIAN_HOST_COLLISION";
  }
  return null;
}

export function configuredAdminHost(
  environment: HostEnvironment = process.env,
): string | null {
  if (adminSurfaceConfigurationError(environment)) return null;
  return configuredAdminHostUnchecked(environment);
}

/** Production-server startup gate, invoked by instrumentation.ts. */
export function assertAdminSurfaceRuntimeConfiguration(
  environment: HostEnvironment = process.env,
): void {
  const error = adminSurfaceConfigurationError(environment);
  if (error) {
    throw new Error(`Unsafe admin surface runtime configuration: ${error}`);
  }
}

/**
 * Administrative routes are served by the same Next.js process as the
 * physician application. The edge proxy is the first host boundary; this is
 * the application-layer boundary for direct-container and proxy-misroute
 * defense. Development/test environments opt in by setting ADMIN_PUBLIC_HOST.
 */
export function isAdminRequestHost(
  headers: Pick<Headers, "get">,
  environment: HostEnvironment = process.env,
): boolean {
  if (adminSurfaceConfigurationError(environment)) return false;
  const expected = configuredAdminHost(environment);
  if (environment.ADMIN_PUBLIC_HOST !== undefined && !expected) return false;
  if (!expected) return environment.NODE_ENV !== "production";

  // Caddy overwrites Host with the accepted virtual host. Do not prefer a
  // caller-controlled X-Forwarded-Host value here.
  return normalizeHost(headers.get("host")) === expected;
}
