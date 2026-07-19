import { AsyncLocalStorage } from "node:async_hooks";
import { createHash } from "node:crypto";

import type { AiLogContext } from "./types";

/**
 * Synthetic provider execution is deliberately narrower than the existing
 * process-wide MOCK_AI_CALLS test harness. A persisted, per-visit staging run
 * admits one worker attempt into this context; every provider call must then
 * match that exact visit and practice.
 */
export const TEMPLATE_TWIN_SYNTHETIC_QA_MODE =
  "template_twin_staging_qa_v1" as const;
export const TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION =
  "template-twin-staging-safe-docx/1.0.0" as const;
export const TEMPLATE_TWIN_SYNTHETIC_QA_RESERVED_DATE = "2099-07-16" as const;
export const TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT =
  "Chief concern is synthetic wrist discomfort. Synthetic wrist discomfort began on 2099-07-16 with Moderate severity and context Explicit synthetic detail. Smoking status is Current. Respiratory review confirms synthetic cough. Encounter category is Follow-up. Medication Syntheticmed documented. Plan use synthetic brace. Plan detail is synthetic brace at night. Additional synthetic detail is synthetic follow-up tolerated well." as const;
export const TEMPLATE_TWIN_SYNTHETIC_QA_EVIDENCE = Object.freeze({
  chief_complaint: "Chief concern is synthetic wrist discomfort.",
  hpi: "Synthetic wrist discomfort began on 2099-07-16 with Moderate severity and context Explicit synthetic detail.",
  smoking: "Smoking status is Current.",
  respiratory_review: "Respiratory review confirms synthetic cough.",
  encounter_category: "Encounter category is Follow-up.",
  medication: "Medication Syntheticmed documented.",
  plan: "Plan use synthetic brace.",
  plan_detail: "Plan detail is synthetic brace at night.",
  additional_detail:
    "Additional synthetic detail is synthetic follow-up tolerated well.",
} as const);
export type TemplateTwinSyntheticQaEvidenceClaim =
  keyof typeof TEMPLATE_TWIN_SYNTHETIC_QA_EVIDENCE;
export const TEMPLATE_TWIN_SYNTHETIC_QA_ALL_EVIDENCE_CLAIMS = Object.freeze(
  Object.keys(
    TEMPLATE_TWIN_SYNTHETIC_QA_EVIDENCE,
  ) as TemplateTwinSyntheticQaEvidenceClaim[],
);

/**
 * Parse the staging evidence as an exact subset of the reviewed fixture
 * sentences, in canonical order. This is intentionally a closed grammar: a
 * synthetic marker cannot bless arbitrary free text, names, or identifiers.
 */
export function parseTemplateTwinSyntheticQaEvidenceClaims(
  evidenceText: string,
): readonly TemplateTwinSyntheticQaEvidenceClaim[] | null {
  const text = evidenceText.trim();
  if (!text) return null;

  const claims: TemplateTwinSyntheticQaEvidenceClaim[] = [];
  let cursor = 0;
  let minimumOrdinal = 0;
  while (cursor < text.length) {
    let matched = false;
    for (
      let ordinal = minimumOrdinal;
      ordinal < TEMPLATE_TWIN_SYNTHETIC_QA_ALL_EVIDENCE_CLAIMS.length;
      ordinal += 1
    ) {
      const claim = TEMPLATE_TWIN_SYNTHETIC_QA_ALL_EVIDENCE_CLAIMS[ordinal];
      const sentence = TEMPLATE_TWIN_SYNTHETIC_QA_EVIDENCE[claim];
      if (!text.startsWith(sentence, cursor)) continue;
      claims.push(claim);
      cursor += sentence.length;
      minimumOrdinal = ordinal + 1;
      if (cursor < text.length) {
        if (text[cursor] !== " ") return null;
        cursor += 1;
      }
      matched = true;
      break;
    }
    if (!matched) return null;
  }
  return claims.length > 0 ? Object.freeze(claims) : null;
}

/**
 * Return a provider/privacy-scan projection only for reviewed evidence. The
 * exact reserved future date is replaced before the generic PHI detector; no
 * other date, text, or identifier receives an exception.
 */
export function templateTwinSyntheticQaPrivacyScanText(
  evidenceText: string,
): string | null {
  if (!parseTemplateTwinSyntheticQaEvidenceClaims(evidenceText)) return null;
  return evidenceText
    .trim()
    .replaceAll(
      TEMPLATE_TWIN_SYNTHETIC_QA_RESERVED_DATE,
      "[reserved synthetic date]",
    );
}

/**
 * The staging mock recognizes only complete, reviewed fixture sentences.
 * Unrelated, partial, or merely similar text yields no claim instead of a
 * best-effort clinical inference. This is deliberately narrow synthetic QA
 * behavior, not a substitute for the production extraction provider.
 */
export function deriveTemplateTwinSyntheticQaEvidenceClaims(
  evidenceText: string,
): readonly TemplateTwinSyntheticQaEvidenceClaim[] {
  return parseTemplateTwinSyntheticQaEvidenceClaims(evidenceText) ?? [];
}
export const SYNTHETIC_QA_PROVIDER_CONTEXT_VERSION =
  "synthetic-qa-provider-context-v4" as const;
export const TEMPLATE_TWIN_SYNTHETIC_QA_RESOURCE_ATTESTATION =
  "isolated-disposable-qa-v1" as const;

export type TemplateTwinSyntheticQaMode =
  typeof TEMPLATE_TWIN_SYNTHETIC_QA_MODE;
export type TemplateTwinSyntheticQaFixtureVersion =
  typeof TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION;

export type SyntheticQaProviderErrorCode =
  | "SYNTHETIC_QA_DISABLED"
  | "SYNTHETIC_QA_ENVIRONMENT_UNSAFE"
  | "SYNTHETIC_QA_DATABASE_UNSAFE"
  | "SYNTHETIC_QA_RESOURCE_ATTESTATION_UNSAFE"
  | "SYNTHETIC_QA_REDIS_UNSAFE"
  | "SYNTHETIC_QA_OBJECT_STORAGE_UNSAFE"
  | "SYNTHETIC_QA_MOCK_PROVIDER_DISABLED"
  | "SYNTHETIC_QA_CONTEXT_INVALID"
  | "SYNTHETIC_QA_CONTEXT_NESTED"
  | "SYNTHETIC_QA_CONTEXT_CLOSED"
  | "SYNTHETIC_QA_WORKER_LEASE_UNHEALTHY"
  | "SYNTHETIC_QA_VISIT_MISMATCH"
  | "SYNTHETIC_QA_PRACTICE_MISMATCH";

export class SyntheticQaProviderContextError extends Error {
  readonly code: SyntheticQaProviderErrorCode;

  constructor(code: SyntheticQaProviderErrorCode, message: string) {
    super(message);
    this.name = "SyntheticQaProviderContextError";
    this.code = code;
  }
}

export interface SyntheticQaProviderEnvironment {
  readonly [key: string]: string | undefined;
}

export interface TemplateTwinSyntheticQaProviderContextInput {
  readonly mode: TemplateTwinSyntheticQaMode;
  readonly fixtureVersion: TemplateTwinSyntheticQaFixtureVersion;
  /** PostgreSQL-verified capability that authorized this provider context. */
  readonly admissionId: string;
  readonly runId: string;
  readonly visitId: string;
  readonly practiceId: string;
  readonly requestSha256: string;
  readonly attempt: number;
  readonly workerClaimId: string;
  readonly pinnedGlobalGeneration: bigint;
  readonly pinnedPracticeGeneration: bigint;
  /**
   * Admitted synthetic visit evidence. Validation immediately projects it to
   * exact claim keys plus a digest; raw text is never retained in the context.
   */
  readonly evidenceText: string;
}

export type TemplateTwinSyntheticQaProviderContext = Omit<
  TemplateTwinSyntheticQaProviderContextInput,
  "evidenceText"
> & {
  readonly contractVersion: typeof SYNTHETIC_QA_PROVIDER_CONTEXT_VERSION;
  readonly evidenceClaims: readonly TemplateTwinSyntheticQaEvidenceClaim[];
  readonly evidenceSha256: string;
};

interface SyntheticQaProviderContextState {
  readonly context: TemplateTwinSyntheticQaProviderContext;
  active: boolean;
  workerLeaseHealthy: boolean;
}

const providerContext =
  new AsyncLocalStorage<SyntheticQaProviderContextState>();
const SAFE_STAGING_ENVIRONMENTS = new Set(["qa", "test", "synthetic"]);
const SAFE_DATABASE_TOKEN = /(?:^|[_-])(?:qa|test|synthetic)(?:[_-]|$)/iu;
const SAFE_RESOURCE_HOST_TOKEN = /(?:^|[.-])(?:qa|test|synthetic)(?:[.-]|$)/iu;
const SAFE_BUCKET_TOKEN = /(?:^|-)(?:qa|test|synthetic)(?:-|$)/iu;
const SHA256 = /^[a-f0-9]{64}$/u;
const PRODUCTION_PROFILE_KEYS = [
  "APP_ENV",
  "APPLICATION_ENV",
  "DEPLOYMENT_ENV",
  "ENVIRONMENT",
  "SENTRY_ENVIRONMENT",
  "NEXT_PUBLIC_SENTRY_ENVIRONMENT",
  "TEMPLATE_TWIN_STORAGE_PROFILE",
] as const;

function unsafe(message: string): SyntheticQaProviderContextError {
  return new SyntheticQaProviderContextError(
    "SYNTHETIC_QA_ENVIRONMENT_UNSAFE",
    message,
  );
}

function databaseName(databaseUrl: string | undefined): string | null {
  if (!databaseUrl) return null;
  try {
    const parsed = new URL(databaseUrl);
    if (parsed.protocol !== "postgres:" && parsed.protocol !== "postgresql:") {
      return null;
    }
    const name = decodeURIComponent(parsed.pathname.replace(/^\/+/, ""));
    return name.length > 0 && !name.includes("/") ? name : null;
  } catch {
    return null;
  }
}

function isLocalOrSafeResourceHost(
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
    SAFE_RESOURCE_HOST_TOKEN.test(normalized)
  );
}

function hasIsolatedRedisIdentity(redisUrl: string | undefined): boolean {
  if (!redisUrl) return false;
  try {
    const parsed = new URL(redisUrl);
    if (parsed.protocol !== "redis:" && parsed.protocol !== "rediss:") {
      return false;
    }
    if (
      !isLocalOrSafeResourceHost(parsed.hostname, "redis") ||
      parsed.search ||
      parsed.hash
    ) {
      return false;
    }
    const namespace = parsed.pathname.replace(/^\/+/, "");
    return /^[1-9]$|^1[0-5]$/u.test(namespace);
  } catch {
    return false;
  }
}

function hasSafeBucketName(value: string | undefined): boolean {
  const bucket = value?.trim() ?? "";
  return (
    bucket.length >= 3 &&
    bucket.length <= 63 &&
    /^[a-z0-9][a-z0-9.-]*[a-z0-9]$/u.test(bucket) &&
    SAFE_BUCKET_TOKEN.test(bucket)
  );
}

function hasIsolatedObjectStorageIdentity(
  env: SyntheticQaProviderEnvironment,
): boolean {
  const rawEndpoint = env.MINIO_ENDPOINT?.trim();
  if (!rawEndpoint || rawEndpoint.includes("://")) return false;
  let hostname: string;
  try {
    const endpoint = new URL(`http://${rawEndpoint}`);
    if (
      endpoint.username ||
      endpoint.password ||
      endpoint.pathname !== "/" ||
      endpoint.search ||
      endpoint.hash ||
      !isLocalOrSafeResourceHost(endpoint.hostname, "minio")
    ) {
      return false;
    }
    hostname = endpoint.hostname.toLowerCase();
  } catch {
    return false;
  }

  const audioBucket = env.TRANSCRIBE_MD_MINIO_BUCKET?.trim();
  const templateBucket = env.TRANSCRIBE_MD_TEMPLATE_BUCKET?.trim();
  if (
    !hasSafeBucketName(audioBucket) ||
    !hasSafeBucketName(templateBucket) ||
    audioBucket === templateBucket
  ) {
    return false;
  }

  const internalPlaintextHost =
    hostname === "minio" ||
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "[::1]" ||
    hostname === "::1";
  return env.MINIO_USE_SSL === (internalPlaintextHost ? "false" : "true");
}

/**
 * Validate the immutable runtime boundary before creating a synthetic context.
 * NODE_ENV is intentionally not used as the deployment boundary: optimized QA
 * images run with NODE_ENV=production. Instead, the dedicated environment must
 * positively identify qa/test/synthetic, while any explicit production profile
 * still wins and rejects admission.
 */
export function assertTemplateTwinSyntheticQaProviderEnvironment(
  env: SyntheticQaProviderEnvironment = process.env,
): void {
  if (env.TEMPLATE_TWIN_STAGING_QA_ENABLED !== "true") {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_DISABLED",
      "Template Twin synthetic QA provider execution is disabled.",
    );
  }

  const environment = env.TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT;
  if (!environment || !SAFE_STAGING_ENVIRONMENTS.has(environment)) {
    throw unsafe(
      "Template Twin synthetic QA requires an explicit qa, test, or synthetic environment.",
    );
  }

  for (const key of PRODUCTION_PROFILE_KEYS) {
    const value = env[key]?.trim().toLowerCase();
    if (value === "production" || value === "prod") {
      throw unsafe(
        "Template Twin synthetic QA is forbidden by an explicit production profile.",
      );
    }
  }

  const name = databaseName(env.DATABASE_URL);
  if (!name || !SAFE_DATABASE_TOKEN.test(name)) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_DATABASE_UNSAFE",
      "Template Twin synthetic QA requires a database named for qa, test, or synthetic use.",
    );
  }
  if (
    env.TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION !==
    TEMPLATE_TWIN_SYNTHETIC_QA_RESOURCE_ATTESTATION
  ) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_RESOURCE_ATTESTATION_UNSAFE",
      "Template Twin synthetic QA requires the disposable-resource attestation.",
    );
  }
  if (!hasIsolatedRedisIdentity(env.REDIS_URL)) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_REDIS_UNSAFE",
      "Template Twin synthetic QA requires an isolated Redis namespace.",
    );
  }
  if (!hasIsolatedObjectStorageIdentity(env)) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_OBJECT_STORAGE_UNSAFE",
      "Template Twin synthetic QA requires isolated object storage.",
    );
  }
  if (env.MOCK_AI_CALLS !== "true" || env.MOCK_TEMPLATE_TWIN_E2E !== "true") {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_MOCK_PROVIDER_DISABLED",
      "Template Twin synthetic QA requires deterministic provider fixtures.",
    );
  }
}

function assertIdentifier(value: string, label: string): void {
  if (!value.trim() || value.length > 200) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      `Template Twin synthetic QA ${label} is invalid.`,
    );
  }
}

function validateContextInput(
  input: TemplateTwinSyntheticQaProviderContextInput,
): TemplateTwinSyntheticQaProviderContext {
  if (
    input.mode !== TEMPLATE_TWIN_SYNTHETIC_QA_MODE ||
    input.fixtureVersion !== TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION
  ) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA mode or fixture version is unsupported.",
    );
  }
  assertIdentifier(input.admissionId, "admission identifier");
  assertIdentifier(input.runId, "run identifier");
  assertIdentifier(input.visitId, "visit identifier");
  assertIdentifier(input.practiceId, "practice identifier");
  if (!SHA256.test(input.requestSha256)) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA request digest is invalid.",
    );
  }
  if (!Number.isSafeInteger(input.attempt) || input.attempt < 1) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA worker attempt is invalid.",
    );
  }
  if (
    !/^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/u.test(
      input.workerClaimId,
    )
  ) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA worker claim is invalid.",
    );
  }
  if (
    input.pinnedGlobalGeneration < BigInt(1) ||
    input.pinnedPracticeGeneration < BigInt(1)
  ) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA rollout generation is invalid.",
    );
  }

  const evidenceText = input.evidenceText;
  if (
    typeof evidenceText !== "string" ||
    evidenceText.trim().length === 0 ||
    evidenceText.length > 5_000
  ) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA evidence admission is invalid.",
    );
  }
  const evidenceClaims =
    deriveTemplateTwinSyntheticQaEvidenceClaims(evidenceText);
  if (evidenceClaims.length === 0) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_INVALID",
      "Template Twin synthetic QA evidence is outside the reviewed fixture grammar.",
    );
  }
  const { evidenceText: _discardedEvidenceText, ...safeInput } = input;
  void _discardedEvidenceText;

  return Object.freeze({
    ...safeInput,
    evidenceClaims,
    evidenceSha256: createHash("sha256")
      .update(evidenceText, "utf8")
      .digest("hex"),
    contractVersion: SYNTHETIC_QA_PROVIDER_CONTEXT_VERSION,
  });
}

/**
 * Run one worker attempt with a visit-bound synthetic provider. The active bit
 * closes over detached async resources when the callback settles, so work that
 * escapes the awaited worker attempt cannot keep using the mock provider.
 */
export async function runWithTemplateTwinSyntheticQaProviderContext<T>(
  input: TemplateTwinSyntheticQaProviderContextInput,
  callback: () => Promise<T> | T,
  env: SyntheticQaProviderEnvironment = process.env,
): Promise<T> {
  assertTemplateTwinSyntheticQaProviderEnvironment(env);
  if (providerContext.getStore()) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_NESTED",
      "Nested Template Twin synthetic QA provider contexts are forbidden.",
    );
  }
  const context = validateContextInput(input);
  const state: SyntheticQaProviderContextState = {
    context,
    active: true,
    workerLeaseHealthy: true,
  };
  return providerContext.run(state, async () => {
    try {
      return await callback();
    } finally {
      state.active = false;
    }
  });
}

export function getTemplateTwinSyntheticQaProviderContext(): TemplateTwinSyntheticQaProviderContext | null {
  const state = providerContext.getStore();
  if (!state) return null;
  if (!state.active) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_CONTEXT_CLOSED",
      "Template Twin synthetic QA provider context is closed.",
    );
  }
  return state.context;
}

/** Mark a failed durable lease renewal inside the current worker context. */
export function markTemplateTwinSyntheticQaWorkerLeaseUnhealthy(): void {
  const state = providerContext.getStore();
  if (!state || !state.active) return;
  state.workerLeaseHealthy = false;
}

/** Fail a terminal worker claim once any renewal in this context failed. */
export function assertTemplateTwinSyntheticQaWorkerLeaseHealthy(): void {
  const state = providerContext.getStore();
  if (!state) return;
  if (!state.active || !state.workerLeaseHealthy) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_WORKER_LEASE_UNHEALTHY",
      "Template Twin synthetic QA worker lease renewal failed.",
    );
  }
}

/**
 * Provider-boundary admission check. A mismatch throws rather than silently
 * falling back to a live provider, which prevents a synthetic worker attempt
 * from leaking a call for another visit or tenant.
 */
export function syntheticQaFixtureForProviderCall(
  call: Pick<AiLogContext, "visitId" | "practiceId">,
): TemplateTwinSyntheticQaFixtureVersion | null {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (!context) return null;
  if (!call.visitId || call.visitId !== context.visitId) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_VISIT_MISMATCH",
      "Synthetic QA provider call does not match the admitted visit.",
    );
  }
  if (call.practiceId !== context.practiceId) {
    throw new SyntheticQaProviderContextError(
      "SYNTHETIC_QA_PRACTICE_MISMATCH",
      "Synthetic QA provider call does not match the admitted practice.",
    );
  }
  return context.fixtureVersion;
}
