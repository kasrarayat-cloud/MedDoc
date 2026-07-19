import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { requireFreshDoctorIdentity } from "@/lib/auth";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import {
  lockCurrentTemplateTwinVisit,
  type LockedTemplateTwinVisit,
} from "./fill-engine";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  TemplateTwinRolloutError,
  type TemplateTwinRolloutCode,
  type TemplateTwinRolloutToken,
} from "./rollout";
import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaOperation,
  type TemplateTwinStagingQaRunGuardRow,
  type TemplateTwinStagingQaVisitGuardCode,
} from "./staging-qa-visit-guard";
import { TEMPLATE_TWIN_STAGING_QA_SOAP_EDIT_SUFFIX } from "./staging-qa-fixtures";
import { isTemplateTwinStagingQaRequested } from "./staging-qa-gate";
export { isTemplateTwinStagingQaCorrectionValueAllowed } from "./staging-qa-values";

export type TemplateTwinStagingQaMutationCode =
  | TemplateTwinRolloutCode
  | TemplateTwinStagingQaVisitGuardCode
  | "TEMPLATE_TWIN_STAGING_QA_MUTATION_STALE"
  | "TEMPLATE_TWIN_STAGING_QA_VALUE_REJECTED";

export class TemplateTwinStagingQaMutationError extends Error {
  constructor(
    readonly code: TemplateTwinStagingQaMutationCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinStagingQaMutationError";
  }
}

export interface TemplateTwinStagingQaMutationClaim {
  readonly runId: string;
  readonly attempt: number;
  readonly visitId: string;
  readonly userId: string;
  readonly practiceId: string;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

/** One deterministic SOAP mutation exists solely to prove stale-output invalidation. */
export function assertTemplateTwinStagingQaSoapEdit(input: {
  currentSoap: string | null;
  nextSoap: string;
}): void {
  if (
    !input.currentSoap ||
    input.currentSoap.endsWith(TEMPLATE_TWIN_STAGING_QA_SOAP_EDIT_SUFFIX) ||
    input.nextSoap !==
      `${input.currentSoap}${TEMPLATE_TWIN_STAGING_QA_SOAP_EDIT_SUFFIX}`
  ) {
    throw new TemplateTwinStagingQaMutationError(
      "TEMPLATE_TWIN_STAGING_QA_VALUE_REJECTED",
      "Synthetic QA accepts only the reviewed SOAP invalidation example.",
    );
  }
}

/**
 * Admission for generic visit mutations that are also reachable from the
 * synthetic staging UI. Ordinary visits intentionally return null and retain
 * their existing auth behavior. Marked visits require a fresh DOCTOR identity,
 * the process gate, and the exact database-backed rollout generation.
 */
export async function pinTemplateTwinStagingQaMutation(input: {
  visitId: string;
  userId: string;
  run: TemplateTwinStagingQaRunGuardRow | null | undefined;
}): Promise<TemplateTwinStagingQaMutationClaim | null> {
  if (!input.run && !isTemplateTwinStagingQaRequested()) return null;
  const identity = await requireFreshDoctorIdentity(input.userId);
  if (input.run && identity.practiceId !== input.run.practiceId) {
    throw new TemplateTwinStagingQaMutationError(
      "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND",
      "Synthetic QA visit not found.",
    );
  }
  let rolloutToken: TemplateTwinRolloutToken;
  try {
    rolloutToken = await pinTemplateTwinRollout({
      practiceId: identity.practiceId,
    });
  } catch (error) {
    if (error instanceof TemplateTwinRolloutError) {
      throw new TemplateTwinStagingQaMutationError(error.code, error.message);
    }
    throw error;
  }
  const admission = assertTemplateTwinStagingQaVisitGuard({
    run: input.run,
    actor: { userId: input.userId, practiceId: identity.practiceId },
    currentRolloutToken: rolloutToken,
    allowedAdmissionPhases: ["REVIEW_READY"],
  });
  if (!admission.applies || input.run?.id !== admission.runId) {
    throw new TemplateTwinStagingQaMutationError(
      "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND",
      "Synthetic QA visit not found.",
    );
  }
  return {
    runId: admission.runId,
    attempt: input.run.attempt,
    visitId: input.visitId,
    userId: input.userId,
    practiceId: identity.practiceId,
    rolloutToken,
  };
}

/**
 * Final linearization boundary for a staging visit mutation. Call inside the
 * same transaction as the clinical update and fill invalidation. Lock order is
 * always global rollout -> practice rollout -> durable admission -> staging
 * run -> actor -> visit -> fill.
 */
export async function lockTemplateTwinStagingQaMutation(input: {
  tx: Prisma.TransactionClient;
  claim: TemplateTwinStagingQaMutationClaim | null;
}): Promise<LockedTemplateTwinVisit | null> {
  if (!input.claim) return null;
  const rollout = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.claim.practiceId,
    pinnedToken: input.claim.rolloutToken,
  });
  if (!rollout.allowed) {
    throw new TemplateTwinStagingQaMutationError(rollout.code, rollout.reason);
  }
  await lockAndAssertTemplateTwinStagingQaOperation({
    tx: input.tx,
    runId: input.claim.runId,
    expectedAttempt: input.claim.attempt,
    actor: {
      userId: input.claim.userId,
      practiceId: input.claim.practiceId,
    },
    currentRolloutToken: rollout.token,
    allowedStatuses: ["COMPLETED"],
    allowedAdmissionPhases: ["REVIEW_READY"],
  });
  const visit = await lockCurrentTemplateTwinVisit(
    input.tx,
    input.claim.visitId,
  );
  if (
    !visit ||
    visit.id !== input.claim.visitId ||
    visit.userId !== input.claim.userId ||
    visit.status !== TranscribeVisitStatus.READY ||
    visit.deletedAt !== null ||
    visit.archivedAt !== null
  ) {
    throw new TemplateTwinStagingQaMutationError(
      "TEMPLATE_TWIN_STAGING_QA_MUTATION_STALE",
      "Synthetic QA visit changed before this update could be saved.",
    );
  }
  return visit;
}

/** Audit is enqueued in the caller's clinical transaction; no text is stored. */
export function enqueueTemplateTwinStagingQaMutationAudit(input: {
  tx: Prisma.TransactionClient;
  claim: TemplateTwinStagingQaMutationClaim | null;
  actorEmail: string;
  operation:
    | "soap_save"
    | "suggestion_adopt"
    | "suggestion_dismiss"
    | "em_additions";
  soapVersion: number;
}): Promise<void> {
  if (!input.claim) return Promise.resolve();
  return enqueueTemplateTwinAudit(input.tx, {
    eventKey:
      `template-twin:staging-mutation:${input.claim.runId}:` +
      `${input.claim.attempt}:${input.operation}:${input.soapVersion}`,
    practiceId: input.claim.practiceId,
    actorId: input.claim.userId,
    actorEmailSnapshot: input.actorEmail,
    action: "TEMPLATE_TWIN_STAGING_QA_SOAP_EDITED",
    targetType: "TranscribeVisit",
    targetId: input.claim.visitId,
    metadata: {
      operation: input.operation,
      stagingQaRunId: input.claim.runId,
      stagingQaAttempt: input.claim.attempt,
      resultingSoapVersion: input.soapVersion,
    },
  });
}
