import type {
  VisitAutomationLayerRequirement,
  VisitAutomationLayerStatus,
} from "@prisma/client";

import { retriableDatabaseCode } from "@/lib/db/transaction-retry";

export const VISIT_AUTOMATION_POLICY_VERSION =
  "visit-automation-policy-v1" as const;
export const VISIT_AUTOMATION_SOURCE_VERSION = "soap-final-v1" as const;

export const VISIT_AUTOMATION_LAYER_IDS = [
  "icd_coding",
  "cpt_coding",
  "rx_drafting",
  "referrals",
  "patient_summary",
  "em_mdm_prewarm",
] as const;

export type VisitAutomationLayerId =
  (typeof VISIT_AUTOMATION_LAYER_IDS)[number];

export const VISIT_AUTOMATION_LAYER_VERSION: Record<
  VisitAutomationLayerId,
  string
> = {
  icd_coding: "l7a-v1",
  cpt_coding: "l7b-v1",
  rx_drafting: "l7c-v1",
  referrals: "l7d-v1",
  patient_summary: "l7e-v1",
  em_mdm_prewarm: "em-mdm-prewarm-v1",
};

export interface VisitAutomationLayerPolicy {
  layerId: VisitAutomationLayerId;
  layerVersion: string;
  requirement: VisitAutomationLayerRequirement;
  initialStatus: VisitAutomationLayerStatus;
}

/**
 * Shared clinical policy:
 *
 * - The existing ordinary-visit contract intentionally treats every L7
 *   automation result as optional. A rejected coding, prescription-drafting,
 *   referral, or summary provider must remain visible and durable, but it did
 *   not historically make the clinician's SOAP unavailable for review. This
 *   manifest must not silently redefine those product semantics.
 * - Synthetic staging exercises the complete five-layer worker boundary, so
 *   all enabled L7 layers are required there.
 * - The durable worker fanout marks E/M cache prewarm N/A in both workflows.
 *   On-demand E/M remains available, but the legacy prewarm's internal retry
 *   and Redis side effect cannot satisfy the provider-execution contract.
 * - A disabled or specialty-inapplicable layer is explicit NOT_APPLICABLE;
 *   it never disappears from the manifest.
 */
export function buildVisitAutomationPolicy(input: {
  staging: boolean;
  enabled: Record<VisitAutomationLayerId, boolean>;
}): VisitAutomationLayerPolicy[] {
  return VISIT_AUTOMATION_LAYER_IDS.map((layerId) => {
    const enabled = input.enabled[layerId];
    if (!enabled) {
      return {
        layerId,
        layerVersion: VISIT_AUTOMATION_LAYER_VERSION[layerId],
        requirement: "NOT_APPLICABLE",
        initialStatus: "NOT_APPLICABLE",
      };
    }
    const required = input.staging && layerId !== "em_mdm_prewarm";
    return {
      layerId,
      layerVersion: VISIT_AUTOMATION_LAYER_VERSION[layerId],
      requirement: required ? "REQUIRED" : "OPTIONAL",
      initialStatus: "PENDING",
    };
  });
}

export type VisitAutomationFailureCode =
  | "DATABASE_CONTENTION"
  | "PROVIDER_FAILURE"
  | "OUTPUT_VALIDATION_FAILED"
  | "LAYER_FAILED";

/** Sanitized failure taxonomy: never persists an exception message. */
export function classifyVisitAutomationFailure(
  error: unknown,
): VisitAutomationFailureCode {
  if (retriableDatabaseCode(error)) return "DATABASE_CONTENTION";
  if (
    error instanceof Error &&
    /(?:zod|schema|validation|parse|invalid output)/iu.test(error.name)
  ) {
    return "OUTPUT_VALIDATION_FAILED";
  }
  if (
    error instanceof Error &&
    /(?:provider|anthropic|deepgram|model|timeout|rate)/iu.test(error.name)
  ) {
    return "PROVIDER_FAILURE";
  }
  return "LAYER_FAILED";
}

export function automationIncompleteReviewReason(
  layerIds: readonly string[],
): string {
  const count = layerIds.length;
  return `${count} required automation layer${count === 1 ? " is" : "s are"} incomplete. Retry processing before review or signing.`;
}
