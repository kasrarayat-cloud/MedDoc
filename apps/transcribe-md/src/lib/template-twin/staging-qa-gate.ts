export const TEMPLATE_TWIN_STAGING_QA_ENABLED_ENV =
  "TEMPLATE_TWIN_STAGING_QA_ENABLED" as const;
export const TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT_ENV =
  "TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT" as const;
export const TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION_ENV =
  "TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION" as const;
export const TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION =
  "isolated-disposable-qa-v1" as const;

export type TemplateTwinStagingQaGateCode =
  | "STAGING_QA_DISABLED"
  | "STAGING_QA_ENVIRONMENT_INVALID"
  | "STAGING_QA_DATABASE_NOT_ISOLATED"
  | "STAGING_QA_RESOURCE_ATTESTATION_INVALID"
  | "STAGING_QA_REDIS_NOT_ISOLATED"
  | "STAGING_QA_OBJECT_STORAGE_NOT_ISOLATED"
  | "STAGING_QA_STORAGE_PROFILE_INVALID"
  | "STAGING_QA_MOCK_PROVIDER_DISABLED";

export type TemplateTwinStagingQaGateDecision =
  | { allowed: true; environment: "qa" | "test" | "synthetic" }
  | { allowed: false; code: TemplateTwinStagingQaGateCode };

function explicitlyTrue(value: string | undefined): boolean {
  return value === "true";
}

function isolatedDatabaseName(rawUrl: string | undefined): boolean {
  if (!rawUrl) return false;
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== "postgres:" && parsed.protocol !== "postgresql:") {
      return false;
    }
    const name = decodeURIComponent(parsed.pathname.replace(/^\/+/, ""));
    if (!name || name.includes("/")) return false;
    return /(?:^|[_-])(?:qa|test|synthetic)(?:[_-]|$)/iu.test(name ?? "");
  } catch {
    return false;
  }
}

const ISOLATED_RESOURCE_TOKEN = /(?:^|[.-])(?:qa|test|synthetic)(?:[.-]|$)/iu;
const ISOLATED_BUCKET_TOKEN = /(?:^|[-])(?:qa|test|synthetic)(?:[-]|$)/iu;

function isLocalOrIsolatedHost(
  hostname: string,
  localServiceName: "redis" | "minio",
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

/**
 * A dedicated non-zero Redis database is required even inside the disposable
 * compose network. This prevents a staging worker from sharing BullMQ keys
 * with another local application process if an endpoint is accidentally
 * reused. Credentials may be present but are never surfaced; query-string
 * overrides are rejected as ambiguous.
 */
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
  env: Readonly<Record<string, string | undefined>>,
): boolean {
  const rawEndpoint = env.MINIO_ENDPOINT?.trim();
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
  } catch {
    return false;
  }

  const audioBucket = env.TRANSCRIBE_MD_MINIO_BUCKET?.trim();
  const templateBucket = env.TRANSCRIBE_MD_TEMPLATE_BUCKET?.trim();
  if (
    !isolatedBucketName(audioBucket) ||
    !isolatedBucketName(templateBucket) ||
    audioBucket === templateBucket
  ) {
    return false;
  }

  // The disposable compose service is an internal network hop. Any other
  // non-loopback endpoint must use TLS, even when its hostname carries a QA
  // marker. The exact flag is required; implicit SDK defaults are rejected.
  const host = new URL(`http://${rawEndpoint}`).hostname.toLowerCase();
  const internalPlaintextHost =
    host === "minio" ||
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "[::1]" ||
    host === "::1";
  return env.MINIO_USE_SSL === (internalPlaintextHost ? "false" : "true");
}

/**
 * Process-level staging boundary. This intentionally does not use NODE_ENV:
 * the isolated QA stack runs a production Next build. Admission instead needs
 * an explicit feature opt-in, a named non-production environment, a positively
 * identified QA/test database, QA storage, and the deterministic mock provider.
 * Every missing/unknown value fails closed.
 */
export function evaluateTemplateTwinStagingQaGate(
  env: Readonly<Record<string, string | undefined>> = process.env,
): TemplateTwinStagingQaGateDecision {
  if (!explicitlyTrue(env[TEMPLATE_TWIN_STAGING_QA_ENABLED_ENV])) {
    return { allowed: false, code: "STAGING_QA_DISABLED" };
  }
  const environment = env[TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT_ENV];
  if (
    environment !== "qa" &&
    environment !== "test" &&
    environment !== "synthetic"
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
    const value = env[key]?.trim().toLowerCase();
    if (value === "production" || value === "prod") {
      return { allowed: false, code: "STAGING_QA_ENVIRONMENT_INVALID" };
    }
  }
  if (!isolatedDatabaseName(env.DATABASE_URL)) {
    return { allowed: false, code: "STAGING_QA_DATABASE_NOT_ISOLATED" };
  }
  if (
    env[TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION_ENV] !==
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION
  ) {
    return {
      allowed: false,
      code: "STAGING_QA_RESOURCE_ATTESTATION_INVALID",
    };
  }
  if (!isolatedRedisIdentity(env.REDIS_URL)) {
    return { allowed: false, code: "STAGING_QA_REDIS_NOT_ISOLATED" };
  }
  if (!isolatedObjectStorageIdentity(env)) {
    return {
      allowed: false,
      code: "STAGING_QA_OBJECT_STORAGE_NOT_ISOLATED",
    };
  }
  if (env.TEMPLATE_TWIN_STORAGE_PROFILE !== "qa") {
    return { allowed: false, code: "STAGING_QA_STORAGE_PROFILE_INVALID" };
  }
  // Pre-admission privacy inspection runs before a visit-bound worker context
  // exists, so the app process must also positively disable live model calls.
  if (
    !explicitlyTrue(env.MOCK_AI_CALLS) ||
    !explicitlyTrue(env.MOCK_TEMPLATE_TWIN_E2E)
  ) {
    return { allowed: false, code: "STAGING_QA_MOCK_PROVIDER_DISABLED" };
  }
  return { allowed: true, environment };
}

export class TemplateTwinStagingQaDisabledError extends Error {
  constructor(readonly code: TemplateTwinStagingQaGateCode) {
    super("Template Twin synthetic QA is unavailable.");
    this.name = "TemplateTwinStagingQaDisabledError";
  }
}

export function assertTemplateTwinStagingQaGate(
  env: Readonly<Record<string, string | undefined>> = process.env,
): "qa" | "test" | "synthetic" {
  const decision = evaluateTemplateTwinStagingQaGate(env);
  if (!decision.allowed) {
    throw new TemplateTwinStagingQaDisabledError(decision.code);
  }
  return decision.environment;
}
