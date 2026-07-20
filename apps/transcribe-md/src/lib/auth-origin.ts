import { ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION } from "@/lib/admin-host";
import { isExactSyntheticQaRuntimeProfile } from "@meddoc/auth";

export const PHYSICIAN_PRODUCTION_ORIGIN = "https://app.quillmd.com" as const;
export const ADMIN_PRODUCTION_ORIGIN = "https://admin.quillmd.com" as const;
export const SYNTHETIC_QA_PHYSICIAN_ORIGIN = "http://localhost:9020" as const;

type OriginEnvironment = Partial<
  Pick<
    NodeJS.ProcessEnv,
    | "NODE_ENV"
    | "QUILLMD_SERVICE_ROLE"
    | "AUTH_URL"
    | "NEXTAUTH_URL"
    | "ADMIN_PUBLIC_HOST"
    | "PHYSICIAN_PUBLIC_HOST"
    | "TEMPLATE_TWIN_STORAGE_PROFILE"
    | "ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION"
  >
>;

export type AuthOriginConfigurationError =
  | "AUTH_SERVICE_ROLE_NOT_REVIEWED"
  | "AUTH_URL_NOT_REVIEWED"
  | "NEXTAUTH_URL_NOT_REVIEWED"
  | "PHYSICIAN_APP_URL_NOT_REVIEWED";

function isExactSyntheticQaOriginProfile(
  environment: OriginEnvironment,
  compiledPhysicianAppUrl: string,
): boolean {
  return (
    isExactSyntheticQaRuntimeProfile(environment) &&
    environment.ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION ===
      ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION &&
    compiledPhysicianAppUrl === SYNTHETIC_QA_PHYSICIAN_ORIGIN
  );
}

/**
 * Fixed-code production origin census. Exact string equality intentionally
 * rejects credentials, alternate ports, plaintext production URLs, trailing
 * paths, query strings, fragments, and normalization-dependent variants.
 */
export function authOriginConfigurationError(
  environment: OriginEnvironment,
  compiledPhysicianAppUrl: string,
): AuthOriginConfigurationError | null {
  if (environment.NODE_ENV !== "production") return null;
  if (isExactSyntheticQaOriginProfile(environment, compiledPhysicianAppUrl)) {
    return null;
  }

  const expectedAuthOrigin =
    environment.QUILLMD_SERVICE_ROLE === "physician-app"
      ? PHYSICIAN_PRODUCTION_ORIGIN
      : environment.QUILLMD_SERVICE_ROLE === "template-twin-admin-app" ||
          environment.QUILLMD_SERVICE_ROLE === "template-twin-admin-control"
        ? ADMIN_PRODUCTION_ORIGIN
        : null;
  if (!expectedAuthOrigin) return "AUTH_SERVICE_ROLE_NOT_REVIEWED";
  if (environment.AUTH_URL !== expectedAuthOrigin) {
    return "AUTH_URL_NOT_REVIEWED";
  }
  if (environment.NEXTAUTH_URL !== expectedAuthOrigin) {
    return "NEXTAUTH_URL_NOT_REVIEWED";
  }
  if (compiledPhysicianAppUrl !== PHYSICIAN_PRODUCTION_ORIGIN) {
    return "PHYSICIAN_APP_URL_NOT_REVIEWED";
  }
  return null;
}

export function assertAuthOriginRuntimeConfiguration(
  environment: OriginEnvironment,
  compiledPhysicianAppUrl: string,
): void {
  const error = authOriginConfigurationError(
    environment,
    compiledPhysicianAppUrl,
  );
  if (error) {
    throw new Error(`Unsafe authentication origin configuration: ${error}`);
  }
}
