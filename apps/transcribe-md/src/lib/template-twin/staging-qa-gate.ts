import {
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION as SHARED_RESOURCE_ATTESTATION,
  evaluateSyntheticQaResourceBoundary,
  type SyntheticQaResourceBoundaryCode,
  type SyntheticQaResourceBoundaryDecision,
} from "@meddoc/auth/synthetic-qa-runtime-profile";

export const TEMPLATE_TWIN_STAGING_QA_ENABLED_ENV =
  "TEMPLATE_TWIN_STAGING_QA_ENABLED" as const;
export const TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT_ENV =
  "TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT" as const;
export const TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION_ENV =
  "TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION" as const;
export const TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION =
  SHARED_RESOURCE_ATTESTATION;

export type TemplateTwinStagingQaResourceBoundaryCode =
  SyntheticQaResourceBoundaryCode;

export type TemplateTwinStagingQaGateCode =
  | "STAGING_QA_DISABLED"
  | TemplateTwinStagingQaResourceBoundaryCode
  | "STAGING_QA_MOCK_PROVIDER_DISABLED";

export type TemplateTwinStagingQaResourceBoundaryDecision =
  SyntheticQaResourceBoundaryDecision;

export type TemplateTwinStagingQaGateDecision =
  | Extract<TemplateTwinStagingQaResourceBoundaryDecision, { allowed: true }>
  | { allowed: false; code: TemplateTwinStagingQaGateCode };

function explicitlyTrue(value: string | undefined): boolean {
  return value === "true";
}

/**
 * The synthetic-only boundary is requested by one exact, case-sensitive flag.
 * This intentionally does not depend on the rest of the staging readiness
 * checks: a partially configured staging process must still fence ordinary
 * Template Twin entry points instead of falling back to production behavior.
 */
export function isTemplateTwinStagingQaRequested(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  return env[TEMPLATE_TWIN_STAGING_QA_ENABLED_ENV] === "true";
}

/**
 * Exact disposable-resource boundary shared by synthetic staging admission and
 * production startup checks for deterministic provider flags. It deliberately
 * excludes both the staging feature switch and provider flags: an optimized QA
 * image may use the reviewed mock provider while its staging UI remains off.
 */
export function evaluateTemplateTwinStagingQaResourceBoundary(
  env: Readonly<Record<string, string | undefined>> = process.env,
): TemplateTwinStagingQaResourceBoundaryDecision {
  return evaluateSyntheticQaResourceBoundary(env);
}

/**
 * Process-level staging boundary. This intentionally does not use NODE_ENV:
 * the isolated QA stack runs a production Next build. Admission instead needs
 * an explicit feature opt-in, the complete disposable-resource boundary, and
 * the deterministic mock provider. Every missing/unknown value fails closed.
 */
export function evaluateTemplateTwinStagingQaGate(
  env: Readonly<Record<string, string | undefined>> = process.env,
): TemplateTwinStagingQaGateDecision {
  if (!isTemplateTwinStagingQaRequested(env)) {
    return { allowed: false, code: "STAGING_QA_DISABLED" };
  }
  const resourceBoundary = evaluateTemplateTwinStagingQaResourceBoundary(env);
  if (!resourceBoundary.allowed) return resourceBoundary;
  // Pre-admission privacy inspection runs before a visit-bound worker context
  // exists, so the app process must also positively disable live model calls.
  if (
    !explicitlyTrue(env.MOCK_AI_CALLS) ||
    !explicitlyTrue(env.MOCK_TEMPLATE_TWIN_E2E)
  ) {
    return { allowed: false, code: "STAGING_QA_MOCK_PROVIDER_DISABLED" };
  }
  return resourceBoundary;
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
