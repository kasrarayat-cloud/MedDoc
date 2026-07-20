import { randomUUID } from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";
import {
  claimCurrentOrdinaryVisitDeliveryActor,
  currentClinicalVisitActorWhere,
} from "@/lib/clinical-visit-authority";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import {
  lockAndAssertVisitAutomationProof,
  VisitAutomationIncompleteError,
} from "@/worker/automation-finalization";

import { canonicalSha256 } from "./canonical";
import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "./durable-visit-exclusion";
import { persistedTemplateTwinEncounterEvidenceIsValid } from "./encounter-evidence-verification";
import {
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "./final-claim-authority";
import { lockCurrentTemplateTwinVisit } from "./fill-engine";
import {
  lockTemplateTwinRolloutForFinalClaim,
  TemplateTwinRolloutError,
} from "./rollout";
import {
  assessTemplateTwinSigning,
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
} from "./signing-gate";
import { TemplateTwinStagingQaDisabledError } from "./staging-qa-gate";
import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaOperation,
  TemplateTwinStagingQaVisitGuardError,
} from "./staging-qa-visit-guard";
import {
  requireTemplateTwinVisitReadAuthority,
  type TemplateTwinVisitReadDecision,
  TemplateTwinVisitReadAuthorityError,
} from "./read-authority";
import {
  requireTemplateTwinSyntheticReadAdmission,
  type TemplateTwinSyntheticReadAdmission,
  TemplateTwinSyntheticReadAdmissionError,
} from "./synthetic-read-admission";

export type TemplateTwinDeliveryAuthorizationCode =
  | "NOT_FOUND"
  | "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED"
  | "TEMPLATE_TWIN_DELIVERY_BLOCKED";

/** Stable, PHI-free boundary error. Receipt/provider details are never exposed. */
export class TemplateTwinDeliveryAuthorizationError extends Error {
  constructor(
    readonly code: TemplateTwinDeliveryAuthorizationCode,
    readonly status: 403 | 404 | 409,
  ) {
    super(
      code === "NOT_FOUND"
        ? "not found"
        : code === "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED"
          ? "Current physician authorization is required for Template Twin."
          : "Template Twin delivery authorization changed. Refresh and try again.",
    );
    this.name = "TemplateTwinDeliveryAuthorizationError";
  }
}

function blocked(): never {
  throw new TemplateTwinDeliveryAuthorizationError(
    "TEMPLATE_TWIN_DELIVERY_BLOCKED",
    409,
  );
}

function normalizedEmail(email: string): string {
  return email.trim().toLowerCase();
}

export type TemplateTwinDeliveryFinalClaim =
  | { templateTwin: false; currentPhysicianEmail: string }
  | { templateTwin: true; currentPhysicianEmail: string };

interface TemplateTwinDeliveryReadBoundaryClaim {
  decision: TemplateTwinVisitReadDecision;
  syntheticAdmission: TemplateTwinSyntheticReadAdmission | null;
}

async function requireDeliveryReadBoundary(input: {
  visitId: string;
  actorUserId: string;
  allowSyntheticOriginalTemplate: boolean;
  expected?: TemplateTwinDeliveryReadBoundaryClaim;
}): Promise<TemplateTwinDeliveryReadBoundaryClaim> {
  let decision: TemplateTwinVisitReadDecision;
  try {
    decision = await requireTemplateTwinVisitReadAuthority({
      db: prisma,
      visitId: input.visitId,
      actorUserId: input.actorUserId,
    });
  } catch (error) {
    if (error instanceof TemplateTwinVisitReadAuthorityError) {
      throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
    }
    throw error;
  }

  if (
    input.expected &&
    (decision.visitId !== input.expected.decision.visitId ||
      decision.isTemplateTwin !== input.expected.decision.isTemplateTwin ||
      decision.isSyntheticTemplateTwin !==
        input.expected.decision.isSyntheticTemplateTwin ||
      decision.practiceId !== input.expected.decision.practiceId)
  ) {
    throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
  }

  if (!decision.isSyntheticTemplateTwin) {
    if (input.expected?.syntheticAdmission) {
      throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
    }
    return { decision, syntheticAdmission: null };
  }
  if (
    input.allowSyntheticOriginalTemplate !== true ||
    (input.expected !== undefined && !input.expected.syntheticAdmission)
  ) {
    throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
  }

  try {
    const syntheticAdmission = await requireTemplateTwinSyntheticReadAdmission({
      visitId: input.visitId,
      actorUserId: input.actorUserId,
      readDecision: decision,
      ...(input.expected?.syntheticAdmission
        ? { expected: input.expected.syntheticAdmission }
        : {}),
    });
    if (!syntheticAdmission) {
      throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
    }
    return { decision, syntheticAdmission };
  } catch (error) {
    if (error instanceof TemplateTwinSyntheticReadAdmissionError) {
      throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
    }
    throw error;
  }
}

/**
 * Final authorization claim for every generic visit delivery surface.
 * Ordinary visits retain their prior behavior. A Template Twin delivery must
 * be SIGNED and retain the exact current review, rollout, automation, source,
 * provider-receipt, and fill identities. Synthetic visits remain limited to
 * the stored Original Template DOCX path.
 */
export async function authorizeVisitDeliveryFinalClaim(input: {
  visitId: string;
  actorUserId: string;
  allowSyntheticOriginalTemplate?: boolean;
  /**
   * Present only for an email side effect. An explicit target is compared to
   * the current locked users.email value. When omitted, the locked address is
   * the target; a stale session/JWT email is never used for a Twin delivery.
   */
  emailDelivery?: { targetEmail?: string };
}): Promise<TemplateTwinDeliveryFinalClaim> {
  // This classifier reads only identifiers and provenance. It must run before
  // TEMPLATE_TWIN_SIGNING_VISIT_SELECT projects SOAP/transcript/evidence into
  // application memory. Ordinary owned visits retain their existing path.
  const initialReadClaim = await requireDeliveryReadBoundary({
    visitId: input.visitId,
    actorUserId: input.actorUserId,
    allowSyntheticOriginalTemplate:
      input.allowSyntheticOriginalTemplate === true,
  });
  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      id: input.visitId,
      ...currentClinicalVisitActorWhere(input.actorUserId),
      ...(initialReadClaim.decision.isTemplateTwin
        ? {}
        : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
    },
    select: {
      id: true,
      userId: true,
      status: true,
      deletedAt: true,
      archivedAt: true,
      user: { select: { practiceId: true } },
      ...TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
    },
  });
  if (!visit || visit.userId !== input.actorUserId) {
    throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
  }

  // Rebind the identifier/provenance claim immediately after the clinical
  // projection. Synthetic run/admission, tenant, and template transitions may
  // never survive into a returned or delivered payload.
  const projectedReadClaim = await requireDeliveryReadBoundary({
    visitId: input.visitId,
    actorUserId: input.actorUserId,
    allowSyntheticOriginalTemplate:
      input.allowSyntheticOriginalTemplate === true,
    expected: initialReadClaim,
  });

  const isTwin = visit.noteTemplate?.templateKind === "template_twin_docx";
  if (!isTwin) {
    // A fill attached to a non-Twin template is inconsistent clinical state,
    // not an ordinary visit that may inherit the legacy delivery behavior.
    if (visit.templateTwinFill) blocked();
    const currentActor = await claimCurrentOrdinaryVisitDeliveryActor({
      visitId: input.visitId,
      actorUserId: input.actorUserId,
    });
    if (!currentActor) {
      throw new TemplateTwinDeliveryAuthorizationError(
        "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
        403,
      );
    }
    if (visit.user.practiceId !== currentActor.practiceId) blocked();
    return {
      templateTwin: false,
      currentPhysicianEmail: currentActor.email,
    };
  }
  if (
    visit.templateTwinSyntheticQaRun &&
    input.allowSyntheticOriginalTemplate !== true
  ) {
    throw new TemplateTwinDeliveryAuthorizationError("NOT_FOUND", 404);
  }
  if (
    visit.status !== TranscribeVisitStatus.SIGNED ||
    visit.deletedAt !== null ||
    visit.archivedAt !== null
  ) {
    blocked();
  }

  let identity: Awaited<ReturnType<typeof requireFreshDoctorIdentity>>;
  try {
    identity = await requireFreshDoctorIdentity(input.actorUserId);
  } catch (error) {
    if (error instanceof AuthError) {
      throw new TemplateTwinDeliveryAuthorizationError(
        "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
        403,
      );
    }
    throw error;
  }
  const practiceId = identity.practiceId;
  if (visit.user.practiceId !== practiceId) blocked();
  const rolloutToken = identity.rolloutToken;

  let stagingClaim: { runId: string; attempt: number } | null = null;
  try {
    const staging = assertTemplateTwinStagingQaVisitGuard({
      run: visit.templateTwinSyntheticQaRun,
      actor: { userId: input.actorUserId, practiceId },
      currentRolloutToken: rolloutToken,
      allowedAdmissionPhases: ["SIGNED"],
    });
    stagingClaim = staging.applies
      ? {
          runId: staging.runId,
          attempt: visit.templateTwinSyntheticQaRun!.attempt,
        }
      : null;
  } catch (error) {
    if (
      error instanceof TemplateTwinStagingQaDisabledError ||
      error instanceof TemplateTwinStagingQaVisitGuardError
    ) {
      blocked();
    }
    throw error;
  }

  const assessment = assessTemplateTwinSigning({
    visitId: visit.id,
    practiceId,
    actorUserId: input.actorUserId,
    visitStatus: visit.status,
    soapFinal: visit.soapFinal,
    soapVersion: visit.soapVersion,
    manualRetryCount: visit.manualRetryCount,
    inputMode: visit.inputMode,
    rawTextInput: visit.rawTextInput,
    transcriptText: visit.transcriptText,
    transcriptRaw: visit.transcriptRaw,
    speakerMap: visit.speakerMap,
    templateTwinSyntheticQaRun: visit.templateTwinSyntheticQaRun,
    noteTemplateId: visit.noteTemplateId,
    noteTemplateVersion: visit.noteTemplateVersion,
    noteTemplate: visit.noteTemplate,
    templateTwinFill: visit.templateTwinFill,
  });
  const claim = assessment.claim;
  const fill = visit.templateTwinFill;
  if (
    !assessment.applies ||
    !assessment.ready ||
    !claim ||
    !fill ||
    fill.pinnedGlobalRolloutGeneration !== rolloutToken.globalGeneration ||
    fill.pinnedPracticeRolloutGeneration !== rolloutToken.practiceGeneration ||
    fill.signedGlobalRolloutGeneration !== rolloutToken.globalGeneration ||
    fill.signedPracticeRolloutGeneration !== rolloutToken.practiceGeneration
  ) {
    blocked();
  }

  try {
    const decision = await runSerializableTransactionWithRetry({
      prisma,
      operation: "template_twin_delivery_final_claim",
      context: {
        visitId: input.visitId,
        practiceId,
        runId: stagingClaim?.runId,
      },
      transaction: async (tx: Prisma.TransactionClient) => {
        const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
          tx,
          practiceId,
          pinnedToken: rolloutToken,
        });
        if (!finalRollout.allowed) return false;

        const lockedStagingRun = stagingClaim
          ? await lockAndAssertTemplateTwinStagingQaOperation({
              tx,
              runId: stagingClaim.runId,
              expectedAttempt: stagingClaim.attempt,
              actor: { userId: input.actorUserId, practiceId },
              currentRolloutToken: finalRollout.token,
              allowedStatuses: ["COMPLETED"],
              allowedAdmissionPhases: ["SIGNED"],
            })
          : null;
        const currentPhysician =
          await lockAndAssertCurrentTemplateTwinPhysician({
            tx,
            actor: { userId: input.actorUserId, practiceId },
          });
        if (
          input.emailDelivery?.targetEmail !== undefined &&
          normalizedEmail(input.emailDelivery.targetEmail) !==
            normalizedEmail(currentPhysician.email)
        ) {
          await enqueueTemplateTwinAudit(tx, {
            eventKey: `template-twin-email-delivery-blocked:${input.visitId}:${randomUUID()}`,
            practiceId,
            actorId: input.actorUserId,
            actorEmailSnapshot: currentPhysician.email,
            action: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
            targetType: "TranscribeVisit",
            targetId: input.visitId,
            metadata: {
              reasonCode: "EMAIL_TARGET_MISMATCH",
              operation: "email_delivery_final_claim",
            },
          });
          return {
            allowed: false,
            emailTargetRejected: true,
            currentPhysicianEmail: currentPhysician.email,
          };
        }

        const lockedVisit = await lockCurrentTemplateTwinVisit(
          tx,
          input.visitId,
        );
        const currentRetry = await tx.transcribeVisit.findUnique({
          where: { id: input.visitId },
          select: { manualRetryCount: true },
        });
        if (
          !lockedVisit ||
          lockedVisit.userId !== input.actorUserId ||
          lockedVisit.status !== TranscribeVisitStatus.SIGNED ||
          lockedVisit.deletedAt !== null ||
          lockedVisit.archivedAt !== null ||
          lockedVisit.soapVersion !== visit.soapVersion ||
          lockedVisit.soapFinal !== visit.soapFinal ||
          lockedVisit.inputMode !== visit.inputMode ||
          currentRetry?.manualRetryCount !== visit.manualRetryCount ||
          lockedVisit.noteTemplateId !== visit.noteTemplateId ||
          lockedVisit.noteTemplateVersion !== visit.noteTemplateVersion
        ) {
          return false;
        }
        if (
          !persistedTemplateTwinEncounterEvidenceIsValid({
            visit: lockedVisit,
            manifest: fill.fillManifest,
          })
        ) {
          return false;
        }
        await lockAndAssertVisitAutomationProof({
          tx,
          visitId: input.visitId,
          practiceId,
          soapVersion: lockedVisit.soapVersion,
          soapFinal: lockedVisit.soapFinal,
          staging: lockedStagingRun
            ? {
                admissionId: lockedStagingRun.admissionId ?? "",
                runId: lockedStagingRun.id,
                globalGeneration: finalRollout.token.globalGeneration,
                practiceGeneration: finalRollout.token.practiceGeneration,
              }
            : null,
        });

        const currentFill = await tx.templateTwinFillManifest.findUnique({
          where: { id: claim.id },
          select: {
            practiceId: true,
            visitId: true,
            compiledVersionId: true,
            noteTemplateId: true,
            noteTemplateVersion: true,
            status: true,
            manifestVersion: true,
            manifestSha256: true,
            soapVersion: true,
            soapSha256: true,
            reviewedAt: true,
            reviewedById: true,
            reviewedManifestVersion: true,
            reviewedManifestSha256: true,
            signedDecisionAt: true,
            outputObjectKey: true,
            outputVersionId: true,
            outputEtag: true,
            outputSha256: true,
            outputSizeBytes: true,
            providerOwnershipEvidence: true,
            providerOwnershipSha256: true,
            pinnedGlobalRolloutGeneration: true,
            pinnedPracticeRolloutGeneration: true,
            signedGlobalRolloutGeneration: true,
            signedPracticeRolloutGeneration: true,
            updatedAt: true,
          },
        });
        const allowed = Boolean(
          currentFill &&
          currentFill.practiceId === practiceId &&
          currentFill.visitId === input.visitId &&
          currentFill.compiledVersionId === fill.compiledVersionId &&
          currentFill.noteTemplateId === fill.noteTemplateId &&
          currentFill.noteTemplateVersion === fill.noteTemplateVersion &&
          currentFill.status === "SIGNED" &&
          currentFill.manifestVersion === claim.manifestVersion &&
          currentFill.manifestSha256 === claim.manifestSha256 &&
          currentFill.soapVersion === claim.soapVersion &&
          currentFill.soapSha256 === claim.soapSha256 &&
          currentFill.reviewedAt?.getTime() === claim.reviewedAt.getTime() &&
          currentFill.reviewedById === claim.reviewedById &&
          currentFill.reviewedManifestVersion === claim.manifestVersion &&
          currentFill.reviewedManifestSha256 === claim.manifestSha256 &&
          currentFill.signedDecisionAt !== null &&
          currentFill.outputObjectKey === claim.outputObjectKey &&
          currentFill.outputVersionId === claim.outputVersionId &&
          currentFill.outputEtag === claim.outputEtag &&
          currentFill.outputSha256 === claim.outputSha256 &&
          currentFill.outputSizeBytes === claim.outputSizeBytes &&
          currentFill.providerOwnershipSha256 ===
            claim.providerOwnershipSha256 &&
          canonicalSha256(currentFill.providerOwnershipEvidence) ===
            canonicalSha256(claim.providerOwnershipEvidence) &&
          currentFill.pinnedGlobalRolloutGeneration ===
            rolloutToken.globalGeneration &&
          currentFill.pinnedPracticeRolloutGeneration ===
            rolloutToken.practiceGeneration &&
          currentFill.signedGlobalRolloutGeneration ===
            rolloutToken.globalGeneration &&
          currentFill.signedPracticeRolloutGeneration ===
            rolloutToken.practiceGeneration &&
          currentFill.updatedAt.getTime() === claim.updatedAt.getTime(),
        );
        if (allowed && input.emailDelivery) {
          await enqueueTemplateTwinAudit(tx, {
            eventKey: `template-twin-email-delivery-authorized:${input.visitId}:${randomUUID()}`,
            practiceId,
            actorId: input.actorUserId,
            actorEmailSnapshot: currentPhysician.email,
            action: "TEMPLATE_TWIN_DELIVERY_AUTHORIZED",
            targetType: "TranscribeVisit",
            targetId: input.visitId,
            metadata: {
              operation: "email_delivery_final_claim",
              explicitTarget: input.emailDelivery.targetEmail !== undefined,
            },
          });
        }
        return {
          allowed,
          emailTargetRejected: false,
          currentPhysicianEmail: currentPhysician.email,
        };
      },
    });
    if (decision === false || decision.allowed !== true) blocked();
    await requireDeliveryReadBoundary({
      visitId: input.visitId,
      actorUserId: input.actorUserId,
      allowSyntheticOriginalTemplate:
        input.allowSyntheticOriginalTemplate === true,
      expected: projectedReadClaim,
    });
    return {
      templateTwin: true,
      currentPhysicianEmail: decision.currentPhysicianEmail,
    };
  } catch (error) {
    if (error instanceof TemplateTwinDeliveryAuthorizationError) throw error;
    if (error instanceof TemplateTwinCurrentPhysicianAuthorityError) {
      throw new TemplateTwinDeliveryAuthorizationError(
        "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
        403,
      );
    }
    if (
      error instanceof TemplateTwinRolloutError ||
      error instanceof TemplateTwinStagingQaDisabledError ||
      error instanceof TemplateTwinStagingQaVisitGuardError ||
      error instanceof VisitAutomationIncompleteError
    ) {
      blocked();
    }
    throw error;
  }
}
