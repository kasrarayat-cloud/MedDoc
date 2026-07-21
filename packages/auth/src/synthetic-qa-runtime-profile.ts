export const QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE =
  "synthetic-disposable-qa-v1" as const;
export const TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION =
  "isolated-disposable-qa-v1" as const;
export const ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION =
  "accepted-isolated-synthetic-qa-shared-host" as const;

export type SyntheticQaRuntimeEnvironment = Readonly<
  Record<string, string | undefined>
>;

export type SyntheticQaResourceBoundaryCode =
  | "STAGING_QA_ENVIRONMENT_INVALID"
  | "STAGING_QA_DATABASE_NOT_ISOLATED"
  | "STAGING_QA_RESOURCE_ATTESTATION_INVALID"
  | "STAGING_QA_REDIS_NOT_ISOLATED"
  | "STAGING_QA_OBJECT_STORAGE_NOT_ISOLATED"
  | "STAGING_QA_STORAGE_PROFILE_INVALID";

export type SyntheticQaResourceBoundaryDecision =
  | { allowed: true; environment: "qa" | "test" | "synthetic" }
  | { allowed: false; code: SyntheticQaResourceBoundaryCode };

const ISOLATED_RESOURCE_TOKEN = /(?:^|[.-])(?:qa|test|synthetic)(?:[.-]|$)/iu;
const ISOLATED_BUCKET_TOKEN = /(?:^|[-])(?:qa|test|synthetic)(?:[-]|$)/iu;
const BASE64URL_CREDENTIAL = /^[A-Za-z0-9_-]{43,128}$/u;

function isLocalOrIsolatedHost(
  hostname: string,
  localServiceName: "postgres" | "redis" | "minio",
): boolean {
  const normalized = hostname.trim().toLowerCase().replace(/\.$/u, "");
  return (
    normalized === localServiceName ||
    normalized === "localhost" ||
    normalized === "127.0.0.1" ||
    normalized === "[::1]" ||
    normalized === "::1" ||
    ISOLATED_RESOURCE_TOKEN.test(normalized)
  );
}

function isolatedDatabaseIdentity(rawUrl: string | undefined): boolean {
  if (!rawUrl) return false;
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== "postgres:" && parsed.protocol !== "postgresql:") {
      return false;
    }
    if (
      parsed.hostname &&
      !isLocalOrIsolatedHost(parsed.hostname, "postgres")
    ) {
      return false;
    }
    if (parsed.port && parsed.port !== "5432") return false;
    if (parsed.hash) return false;
    const seen = new Set<string>();
    for (const [key, value] of parsed.searchParams) {
      if (seen.has(key)) return false;
      seen.add(key);
      if (key === "schema" && value === "public") continue;
      if (key === "options" && value === "-c search_path=pg_catalog,public") {
        continue;
      }
      return false;
    }
    const name = decodeURIComponent(parsed.pathname.replace(/^\/+/, ""));
    return (
      Boolean(name) &&
      !name.includes("/") &&
      /(?:^|[_-])(?:qa|test|synthetic)(?:[_-]|$)/iu.test(name)
    );
  } catch {
    return false;
  }
}

function exactSyntheticRuntimeDatabaseIdentity(
  rawUrl: string | undefined,
): boolean {
  if (!rawUrl || !isolatedDatabaseIdentity(rawUrl)) return false;
  try {
    const parsed = new URL(rawUrl);
    return (
      decodeURIComponent(parsed.username) === "meddoc_runtime" &&
      BASE64URL_CREDENTIAL.test(decodeURIComponent(parsed.password)) &&
      [...parsed.searchParams].length === 2 &&
      parsed.searchParams.get("schema") === "public" &&
      parsed.searchParams.get("options") === "-c search_path=pg_catalog,public"
    );
  } catch {
    return false;
  }
}

function isolatedRedisIdentity(rawUrl: string | undefined): boolean {
  if (!rawUrl) return false;
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== "redis:" && parsed.protocol !== "rediss:") {
      return false;
    }
    if (!isLocalOrIsolatedHost(parsed.hostname, "redis")) return false;
    if (parsed.search || parsed.hash) return false;
    const namespace = parsed.pathname.replace(/^\/+/, "");
    return /^[1-9]$|^1[0-5]$/u.test(namespace);
  } catch {
    return false;
  }
}

function isolatedBucketName(value: string | undefined): boolean {
  const bucket = value?.trim() ?? "";
  return (
    bucket.length >= 3 &&
    bucket.length <= 63 &&
    /^[a-z0-9][a-z0-9.-]*[a-z0-9]$/u.test(bucket) &&
    ISOLATED_BUCKET_TOKEN.test(bucket)
  );
}

function isolatedObjectStorageIdentity(
  environment: SyntheticQaRuntimeEnvironment,
): boolean {
  const rawEndpoint = environment.MINIO_ENDPOINT?.trim();
  if (!rawEndpoint || rawEndpoint.includes("://")) return false;
  try {
    const endpoint = new URL(`http://${rawEndpoint}`);
    if (
      endpoint.username ||
      endpoint.password ||
      endpoint.pathname !== "/" ||
      endpoint.search ||
      endpoint.hash ||
      !isLocalOrIsolatedHost(endpoint.hostname, "minio")
    ) {
      return false;
    }

    const audioBucket = environment.TRANSCRIBE_MD_MINIO_BUCKET?.trim();
    const templateBucket = environment.TRANSCRIBE_MD_TEMPLATE_BUCKET?.trim();
    if (
      !isolatedBucketName(audioBucket) ||
      !isolatedBucketName(templateBucket) ||
      audioBucket === templateBucket
    ) {
      return false;
    }

    const host = endpoint.hostname.toLowerCase();
    const internalPlaintextHost =
      host === "minio" ||
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "[::1]" ||
      host === "::1";
    return (
      environment.MINIO_USE_SSL === (internalPlaintextHost ? "false" : "true")
    );
  } catch {
    return false;
  }
}

/**
 * Canonical resource boundary for the disposable synthetic QA stack. The
 * predicate is pure and edge-safe so every authentication, provider, and
 * startup gate evaluates the same resources rather than trusting a naming
 * flag or a caller-supplied boolean.
 */
export function evaluateSyntheticQaResourceBoundary(
  environment: SyntheticQaRuntimeEnvironment,
): SyntheticQaResourceBoundaryDecision {
  const qaEnvironment = environment.TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT;
  if (
    qaEnvironment !== "qa" &&
    qaEnvironment !== "test" &&
    qaEnvironment !== "synthetic"
  ) {
    return { allowed: false, code: "STAGING_QA_ENVIRONMENT_INVALID" };
  }
  for (const key of [
    "APP_ENV",
    "APPLICATION_ENV",
    "DEPLOYMENT_ENV",
    "ENVIRONMENT",
    "SENTRY_ENVIRONMENT",
    "NEXT_PUBLIC_SENTRY_ENVIRONMENT",
  ] as const) {
    const value = environment[key]?.trim().toLowerCase();
    if (value === "production" || value === "prod") {
      return { allowed: false, code: "STAGING_QA_ENVIRONMENT_INVALID" };
    }
  }
  if (!isolatedDatabaseIdentity(environment.DATABASE_URL)) {
    return { allowed: false, code: "STAGING_QA_DATABASE_NOT_ISOLATED" };
  }
  if (
    environment.TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION !==
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION
  ) {
    return {
      allowed: false,
      code: "STAGING_QA_RESOURCE_ATTESTATION_INVALID",
    };
  }
  if (!isolatedRedisIdentity(environment.REDIS_URL)) {
    return { allowed: false, code: "STAGING_QA_REDIS_NOT_ISOLATED" };
  }
  if (!isolatedObjectStorageIdentity(environment)) {
    return {
      allowed: false,
      code: "STAGING_QA_OBJECT_STORAGE_NOT_ISOLATED",
    };
  }
  if (environment.TEMPLATE_TWIN_STORAGE_PROFILE !== "qa") {
    return { allowed: false, code: "STAGING_QA_STORAGE_PROFILE_INVALID" };
  }
  return { allowed: true, environment: qaEnvironment };
}

/** Exact profile required before any production-build QA auth bypass fires. */
export function isExactSyntheticQaRuntimeProfile(
  environment: SyntheticQaRuntimeEnvironment,
): boolean {
  return (
    environment.NODE_ENV === "production" &&
    environment.QUILLMD_SERVICE_ROLE === "physician-app" &&
    environment.QUILLMD_DATABASE_PRINCIPAL_PROFILE ===
      QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE &&
    evaluateSyntheticQaResourceBoundary(environment).allowed &&
    exactSyntheticRuntimeDatabaseIdentity(environment.DATABASE_URL) &&
    environment.ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION ===
      ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION &&
    environment.ADMIN_PUBLIC_HOST === "localhost" &&
    environment.PHYSICIAN_PUBLIC_HOST === "localhost" &&
    environment.AUTH_URL === "http://localhost:9020" &&
    environment.NEXTAUTH_URL === "http://localhost:9020"
  );
}
