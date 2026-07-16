import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import prisma from "@meddoc/db";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import { TemplateTwinFillManifestSchema } from "./ir";
import {
  assertTemplateTwinRollout,
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  templateTwinRolloutAuditMetadata,
  TemplateTwinRolloutError,
  type TemplateTwinRolloutCode,
  type TemplateTwinRolloutToken,
} from "./rollout";
import { canonicalSoapSha256 } from "./soap-binding";

export interface TemplateTwinReviewAcknowledgementActor {
  userId: string;
  userEmail: string;
  practiceId: string;
}

export class TemplateTwinReviewAcknowledgementError extends Error {
  constructor(
    readonly code:
      | "NOT_FOUND"
      | "NOT_READY"
      | "MANIFEST_INVALID"
      | "SOAP_BINDING_STALE"
      | "OPTIMISTIC_CONFLICT"
      | TemplateTwinRolloutCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinReviewAcknowledgementError";
  }
}

export async function acknowledgeTemplateTwinReview(input: {
  visitId: string;
  expectedManifestVersion: number;
  expectedManifestSha256: string;
  actor: TemplateTwinReviewAcknowledgementActor;
  now?: Date;
}): Promise<{
  fillManifestId: string;
  manifestVersion: number;
  reviewedAt: string;
}> {
  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      id: input.visitId,
      userId: input.actor.userId,
      user: { practiceId: input.actor.practiceId },
    },
    select: {
      status: true,
      soapVersion: true,
      soapFinal: true,
      user: {
        select: { practice: { select: { templateTwinEnabled: true } } },
      },
      templateTwinFill: {
        select: {
          id: true,
          practiceId: true,
          status: true,
          signedDecisionAt: true,
          manifestVersion: true,
          manifestSha256: true,
          fillManifest: true,
          soapVersion: true,
          soapSha256: true,
          needsReviewCount: true,
          conflictCount: true,
          criticalUnresolvedCount: true,
          roundTripVerified: true,
          reviewedAt: true,
          reviewedById: true,
          reviewedManifestVersion: true,
          reviewedManifestSha256: true,
          pinnedGlobalRolloutGeneration: true,
          pinnedPracticeRolloutGeneration: true,
        },
      },
    },
  });
  if (!visit) {
    throw new TemplateTwinReviewAcknowledgementError(
      "NOT_FOUND",
      "The Template Twin visit was not found.",
    );
  }
  assertTemplateTwinRollout({
    practiceEnabled: visit.user.practice.templateTwinEnabled,
  });
  let rolloutToken: TemplateTwinRolloutToken;
  try {
    rolloutToken = await pinTemplateTwinRollout({
      practiceId: input.actor.practiceId,
    });
  } catch (error) {
    if (error instanceof TemplateTwinRolloutError) {
      throw new TemplateTwinReviewAcknowledgementError(
        error.code,
        error.message,
      );
    }
    throw error;
  }

  const fill = visit.templateTwinFill;
  if (
    !fill ||
    fill.practiceId !== input.actor.practiceId ||
    visit.status !== TranscribeVisitStatus.READY ||
    fill.status !== "VERIFIED" ||
    fill.signedDecisionAt !== null ||
    !fill.roundTripVerified ||
    fill.needsReviewCount !== 0 ||
    fill.conflictCount !== 0 ||
    fill.criticalUnresolvedCount !== 0
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "NOT_READY",
      "Resolve and regenerate every required Template Twin field before confirming review.",
    );
  }
  if (fill.pinnedGlobalRolloutGeneration !== rolloutToken.globalGeneration) {
    throw new TemplateTwinReviewAcknowledgementError(
      "TEMPLATE_TWIN_GLOBAL_GENERATION_STALE",
      "Template Twin was disabled or reconfigured globally after this document was generated. Regenerate it before confirming review.",
    );
  }
  if (
    fill.pinnedPracticeRolloutGeneration !== rolloutToken.practiceGeneration
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
      "Template Twin was disabled or reconfigured for this practice after this document was generated. Regenerate it before confirming review.",
    );
  }
  if (
    fill.manifestVersion !== input.expectedManifestVersion ||
    fill.manifestSha256 !== input.expectedManifestSha256
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "OPTIMISTIC_CONFLICT",
      "The Template Twin changed. Review the latest generated document before confirming.",
    );
  }

  const parsedManifest = TemplateTwinFillManifestSchema.safeParse(
    fill.fillManifest,
  );
  if (
    !parsedManifest.success ||
    canonicalSha256(parsedManifest.data) !== fill.manifestSha256
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "MANIFEST_INVALID",
      "The Template Twin manifest could not be verified.",
    );
  }
  if (
    typeof visit.soapFinal !== "string" ||
    fill.soapVersion !== visit.soapVersion ||
    fill.soapSha256 !== canonicalSoapSha256(visit.soapFinal) ||
    parsedManifest.data.soapVersion !== visit.soapVersion ||
    parsedManifest.data.soapSha256 !== fill.soapSha256
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "SOAP_BINDING_STALE",
      "The SOAP note changed. Regenerate and review the Original Template DOCX.",
    );
  }

  if (
    fill.reviewedAt !== null &&
    fill.reviewedById === input.actor.userId &&
    fill.reviewedManifestVersion === fill.manifestVersion &&
    fill.reviewedManifestSha256 === fill.manifestSha256
  ) {
    return {
      fillManifestId: fill.id,
      manifestVersion: fill.manifestVersion,
      reviewedAt: fill.reviewedAt.toISOString(),
    };
  }

  const reviewedAt = input.now ?? new Date();
  const applied = await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: rolloutToken,
      });
      if (!finalRollout.allowed) {
        await enqueueTemplateTwinAudit(tx, {
          eventKey:
            `template-twin:manifest-review-rollout-blocked:${fill.id}:` +
            `${fill.manifestVersion}:${finalRollout.code}:` +
            `${rolloutToken.globalGeneration.toString()}:` +
            rolloutToken.practiceGeneration.toString(),
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TemplateTwinFillManifest",
          targetId: fill.id,
          metadata: {
            reasonCode: finalRollout.code,
            operation: "whole_manifest_review_final_claim",
            visitId: input.visitId,
            manifestVersion: fill.manifestVersion,
            ...templateTwinRolloutAuditMetadata(
              rolloutToken,
              finalRollout.currentToken,
            ),
          },
        });
        return { applied: false as const, rolloutRejected: finalRollout };
      }
      const updated = await tx.templateTwinFillManifest.updateMany({
        where: {
          id: fill.id,
          practiceId: input.actor.practiceId,
          status: "VERIFIED",
          signedDecisionAt: null,
          manifestVersion: fill.manifestVersion,
          manifestSha256: input.expectedManifestSha256,
          soapVersion: fill.soapVersion,
          soapSha256: fill.soapSha256,
          roundTripVerified: true,
          needsReviewCount: 0,
          conflictCount: 0,
          criticalUnresolvedCount: 0,
          pinnedGlobalRolloutGeneration: rolloutToken.globalGeneration,
          pinnedPracticeRolloutGeneration: rolloutToken.practiceGeneration,
          reviewedAt: null,
          practice: {
            is: {
              id: input.actor.practiceId,
              templateTwinEnabled: true,
            },
          },
          visit: {
            is: {
              id: input.visitId,
              userId: input.actor.userId,
              status: TranscribeVisitStatus.READY,
              soapVersion: visit.soapVersion,
              soapFinal: visit.soapFinal,
            },
          },
        },
        data: {
          reviewedAt,
          reviewedById: input.actor.userId,
          reviewedManifestVersion: fill.manifestVersion,
          reviewedManifestSha256: input.expectedManifestSha256,
        },
      });
      if (updated.count !== 1) {
        return { applied: false as const, rolloutRejected: null };
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:manifest-reviewed:${fill.id}:${fill.manifestVersion}:${fill.manifestSha256}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_FIELD_REVIEWED",
        targetType: "TemplateTwinFillManifest",
        targetId: fill.id,
        metadata: {
          reviewKind: "whole_manifest_acknowledgement",
          visitId: input.visitId,
          manifestVersion: fill.manifestVersion,
          manifestSha256: fill.manifestSha256,
          soapVersion: fill.soapVersion,
          soapSha256: fill.soapSha256,
          rolloutGlobalGeneration: rolloutToken.globalGeneration.toString(),
          rolloutPracticeGeneration: rolloutToken.practiceGeneration.toString(),
        },
      });
      return { applied: true as const, rolloutRejected: null };
    },
    { isolationLevel: "Serializable" },
  );
  if (applied.rolloutRejected) {
    throw new TemplateTwinReviewAcknowledgementError(
      applied.rolloutRejected.code,
      applied.rolloutRejected.reason,
    );
  }
  if (!applied.applied) {
    throw new TemplateTwinReviewAcknowledgementError(
      "OPTIMISTIC_CONFLICT",
      "The Template Twin changed. Review the latest generated document before confirming.",
    );
  }

  return {
    fillManifestId: fill.id,
    manifestVersion: fill.manifestVersion,
    reviewedAt: reviewedAt.toISOString(),
  };
}
