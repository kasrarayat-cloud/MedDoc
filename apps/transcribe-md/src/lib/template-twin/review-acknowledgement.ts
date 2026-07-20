import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import prisma from "@meddoc/db";

import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import {
  assessVisitAutomationProof,
  lockAndAssertVisitAutomationProof,
  VisitAutomationIncompleteError,
} from "@/worker/automation-finalization";
import { VISIT_AUTOMATION_MANIFEST_SELECT } from "@/worker/automation-manifest";

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
import { lockCurrentTemplateTwinVisit } from "./fill-engine";
import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaActor,
  lockAndAssertTemplateTwinStagingQaOperation,
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
} from "./staging-qa-visit-guard";
import {
  assessTemplateTwinEncounterEvidence,
  persistedTemplateTwinEncounterEvidenceIsValid,
} from "./encounter-evidence-verification";
import {
  lockAndAssertCurrentTemplateTwinPatient,
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "./final-claim-authority";
import {
  isTemplateTwinLiveProviderCompilationOwned,
  isTemplateTwinStagingProviderCompilationOwned,
  isTemplateTwinVisitProviderReceiptOwned,
} from "./live-provider-ownership";

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
      | "ENCOUNTER_EVIDENCE_INVALID"
      | "SOAP_BINDING_STALE"
      | "PROVIDER_OWNERSHIP_INVALID"
      | "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED"
      | "OPTIMISTIC_CONFLICT"
      | "VISIT_AUTOMATION_INCOMPLETE"
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
      AND: [
        currentClinicalVisitActorWhere(input.actor.userId),
        {
          userId: input.actor.userId,
          user: { is: { practiceId: input.actor.practiceId } },
          patient: { is: { practiceId: input.actor.practiceId } },
        },
      ],
    },
    select: {
      patientId: true,
      status: true,
      soapVersion: true,
      manualRetryCount: true,
      soapFinal: true,
      inputMode: true,
      rawTextInput: true,
      transcriptText: true,
      transcriptRaw: true,
      speakerMap: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      noteTemplate: {
        select: {
          id: true,
          doctorId: true,
          version: true,
          templateKind: true,
          templateTwinCompiledVersion: {
            select: {
              id: true,
              providerOwnershipEvidence: true,
              providerOwnershipSha256: true,
              sourceArtifact: {
                select: {
                  id: true,
                  lineageId: true,
                  lineageVersion: true,
                  sha256: true,
                  providerOwnershipEvidence: true,
                  providerOwnershipSha256: true,
                },
              },
            },
          },
        },
      },
      automationManifest: { select: VISIT_AUTOMATION_MANIFEST_SELECT },
      templateTwinSyntheticQaRun: {
        select: TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
      },
      user: {
        select: { practice: { select: { templateTwinEnabled: true } } },
      },
      templateTwinFill: {
        select: {
          id: true,
          practiceId: true,
          compiledVersionId: true,
          noteTemplateId: true,
          noteTemplateVersion: true,
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
          providerOwnershipEvidence: true,
          providerOwnershipSha256: true,
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
  const stagingAdmission = assertTemplateTwinStagingQaVisitGuard({
    run: visit.templateTwinSyntheticQaRun,
    actor: input.actor,
    currentRolloutToken: rolloutToken,
    allowedAdmissionPhases: ["REVIEW_READY"],
  });
  const stagingQaClaim = stagingAdmission.applies
    ? {
        runId: stagingAdmission.runId,
        attempt: visit.templateTwinSyntheticQaRun!.attempt,
      }
    : null;

  const automationProof = assessVisitAutomationProof({
    visitId: input.visitId,
    practiceId: input.actor.practiceId,
    soapVersion: visit.soapVersion,
    soapFinal: visit.soapFinal,
    manifest: visit.automationManifest,
    staging: visit.templateTwinSyntheticQaRun
      ? {
          admissionId: visit.templateTwinSyntheticQaRun.admissionId ?? "",
          runId: visit.templateTwinSyntheticQaRun.id,
          globalGeneration:
            visit.templateTwinSyntheticQaRun.pinnedGlobalRolloutGeneration,
          practiceGeneration:
            visit.templateTwinSyntheticQaRun.pinnedPracticeRolloutGeneration,
        }
      : null,
  });
  if (!automationProof.ready) {
    throw new TemplateTwinReviewAcknowledgementError(
      "VISIT_AUTOMATION_INCOMPLETE",
      "Required visit automation is incomplete. Retry processing before confirming review.",
    );
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
  const template = visit.noteTemplate;
  const compiled = template?.templateTwinCompiledVersion;
  const compilationIdentity =
    template && compiled
      ? {
          practiceId: input.actor.practiceId,
          actorUserId: template.doctorId,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
          compiledVersionId: compiled.id,
          sourceArtifactId: compiled.sourceArtifact.id,
          sourceLineageId: compiled.sourceArtifact.lineageId,
          sourceLineageVersion: compiled.sourceArtifact.lineageVersion,
          sourceSha256: compiled.sourceArtifact.sha256,
          sourceProviderOwnershipEvidence:
            compiled.sourceArtifact.providerOwnershipEvidence,
          sourceProviderOwnershipSha256:
            compiled.sourceArtifact.providerOwnershipSha256,
          compiledProviderOwnershipEvidence: compiled.providerOwnershipEvidence,
          compiledProviderOwnershipSha256: compiled.providerOwnershipSha256,
        }
      : null;
  const expectedSyntheticSourceAdmissionId = visit.templateTwinSyntheticQaRun
    ? (visit.templateTwinSyntheticQaRun.admission?.parentAdmissionId ?? null)
    : null;
  const compilationOwned =
    compilationIdentity &&
    (visit.templateTwinSyntheticQaRun
      ? Boolean(
          expectedSyntheticSourceAdmissionId &&
          isTemplateTwinStagingProviderCompilationOwned({
            ...compilationIdentity,
            expectedSyntheticAdmissionId: expectedSyntheticSourceAdmissionId,
          }),
        )
      : isTemplateTwinLiveProviderCompilationOwned(compilationIdentity));
  const visitInputMode =
    visit.inputMode === "audio_upload" ||
    visit.inputMode === "voice_dictation" ||
    visit.inputMode === "text_notes"
      ? visit.inputMode
      : null;
  const fillProviderOwned = Boolean(
    compilationIdentity &&
    visitInputMode &&
    Number.isSafeInteger(visit.manualRetryCount) &&
    visit.manualRetryCount >= 0 &&
    isTemplateTwinVisitProviderReceiptOwned({
      evidence: fill.providerOwnershipEvidence,
      evidenceSha256: fill.providerOwnershipSha256,
      practiceId: input.actor.practiceId,
      actorUserId: input.actor.userId,
      visitId: input.visitId,
      visitInputMode,
      sourceArtifactId: compilationIdentity.sourceArtifactId,
      compiledVersionId: compilationIdentity.compiledVersionId,
      noteTemplateId: compilationIdentity.noteTemplateId,
      noteTemplateVersion: compilationIdentity.noteTemplateVersion,
      sourceLineageId: compilationIdentity.sourceLineageId,
      sourceLineageVersion: compilationIdentity.sourceLineageVersion,
      sourceSha256: compilationIdentity.sourceSha256,
      logicalAttempt: visit.manualRetryCount + 1,
      providerMode: visit.templateTwinSyntheticQaRun ? "SYNTHETIC_QA" : "LIVE",
      syntheticAdmissionId: visit.templateTwinSyntheticQaRun
        ? (visit.templateTwinSyntheticQaRun.admissionId ?? null)
        : null,
      pinnedGlobalRolloutGeneration: fill.pinnedGlobalRolloutGeneration,
      pinnedPracticeRolloutGeneration: fill.pinnedPracticeRolloutGeneration,
    }),
  );
  if (
    template?.templateKind !== "template_twin_docx" ||
    template.doctorId !== input.actor.userId ||
    visit.noteTemplateId !== template.id ||
    visit.noteTemplateVersion !== template.version ||
    fill.compiledVersionId !== compiled?.id ||
    fill.noteTemplateId !== template.id ||
    fill.noteTemplateVersion !== template.version ||
    !compilationOwned ||
    !fillProviderOwned
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "PROVIDER_OWNERSHIP_INVALID",
      "The Template Twin provider proof could not be verified. Regenerate it before confirming review.",
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
    !assessTemplateTwinEncounterEvidence({
      visit,
      manifest: parsedManifest.data,
    }).valid
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "ENCOUNTER_EVIDENCE_INVALID",
      "The encounter evidence no longer matches this Template Twin. Regenerate it before confirming review.",
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

  const alreadyReviewed =
    fill.reviewedAt !== null &&
    fill.reviewedById === input.actor.userId &&
    fill.reviewedManifestVersion === fill.manifestVersion &&
    fill.reviewedManifestSha256 === fill.manifestSha256;

  const reviewedAt = fill.reviewedAt ?? input.now ?? new Date();
  const applied = await runSerializableTransactionWithRetry({
    prisma,
    operation: "template_twin_review_acknowledgement",
    context: {
      visitId: input.visitId,
      practiceId: input.actor.practiceId,
      runId: stagingQaClaim?.runId,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
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
      const lockedStagingRun = stagingQaClaim
        ? await lockAndAssertTemplateTwinStagingQaOperation({
            tx,
            runId: stagingQaClaim.runId,
            expectedAttempt: stagingQaClaim.attempt,
            actor: input.actor,
            currentRolloutToken: finalRollout.token,
            allowedStatuses: ["COMPLETED"],
            allowedAdmissionPhases: ["REVIEW_READY"],
          })
        : null;
      if (!lockedStagingRun) {
        await lockAndAssertTemplateTwinStagingQaActor({
          tx,
          actor: {
            userId: input.actor.userId,
            practiceId: input.actor.practiceId,
          },
        });
      }
      await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: {
          userId: input.actor.userId,
          practiceId: input.actor.practiceId,
        },
      });
      await lockAndAssertCurrentTemplateTwinPatient({
        tx,
        patientId: visit.patientId,
        practiceId: input.actor.practiceId,
      });
      const lockedVisit = await lockCurrentTemplateTwinVisit(tx, input.visitId);
      const currentRetry = await tx.transcribeVisit.findUnique({
        where: { id: input.visitId },
        select: { manualRetryCount: true },
      });
      if (
        !lockedVisit ||
        lockedVisit.userId !== input.actor.userId ||
        lockedVisit.patientId !== visit.patientId ||
        lockedVisit.status !== TranscribeVisitStatus.READY ||
        lockedVisit.deletedAt !== null ||
        lockedVisit.archivedAt !== null ||
        lockedVisit.soapVersion !== visit.soapVersion ||
        lockedVisit.soapFinal !== visit.soapFinal ||
        lockedVisit.inputMode !== visit.inputMode ||
        currentRetry?.manualRetryCount !== visit.manualRetryCount
      ) {
        return { applied: false as const, rolloutRejected: null };
      }
      if (
        !persistedTemplateTwinEncounterEvidenceIsValid({
          visit: lockedVisit,
          manifest: fill.fillManifest,
        })
      ) {
        await enqueueTemplateTwinAudit(tx, {
          eventKey:
            `template-twin:manifest-review-evidence-stale:${fill.id}:` +
            `${fill.manifestVersion}:${fill.manifestSha256}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TemplateTwinFillManifest",
          targetId: fill.id,
          metadata: {
            reasonCode: "ENCOUNTER_EVIDENCE_INVALID",
            operation: "whole_manifest_review_final_claim",
            visitId: input.visitId,
            manifestVersion: fill.manifestVersion,
          },
        });
        return {
          applied: false as const,
          rolloutRejected: null,
          encounterEvidenceRejected: true as const,
        };
      }
      await lockAndAssertVisitAutomationProof({
        tx,
        visitId: input.visitId,
        practiceId: input.actor.practiceId,
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
      if (alreadyReviewed) {
        const current = await tx.templateTwinFillManifest.findFirst({
          where: {
            id: fill.id,
            practiceId: input.actor.practiceId,
            visitId: input.visitId,
            compiledVersionId: fill.compiledVersionId,
            noteTemplateId: fill.noteTemplateId,
            noteTemplateVersion: fill.noteTemplateVersion,
            status: "VERIFIED",
            signedDecisionAt: null,
            manifestVersion: fill.manifestVersion,
            manifestSha256: fill.manifestSha256,
            soapVersion: fill.soapVersion,
            soapSha256: fill.soapSha256,
            providerOwnershipEvidence: {
              equals: fill.providerOwnershipEvidence as Prisma.InputJsonValue,
            },
            providerOwnershipSha256: fill.providerOwnershipSha256,
            reviewedAt,
            reviewedById: input.actor.userId,
            reviewedManifestVersion: fill.manifestVersion,
            reviewedManifestSha256: fill.manifestSha256,
            pinnedGlobalRolloutGeneration: rolloutToken.globalGeneration,
            pinnedPracticeRolloutGeneration: rolloutToken.practiceGeneration,
          },
          select: { id: true },
        });
        return {
          applied: current?.id === fill.id,
          rolloutRejected: null,
        };
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
          providerOwnershipEvidence: {
            equals: fill.providerOwnershipEvidence as Prisma.InputJsonValue,
          },
          providerOwnershipSha256: fill.providerOwnershipSha256,
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
  }).catch((error: unknown) => {
    if (error instanceof TemplateTwinCurrentPhysicianAuthorityError) {
      throw new TemplateTwinReviewAcknowledgementError(
        error.code,
        "Current physician authorization is required for Template Twin.",
      );
    }
    if (error instanceof VisitAutomationIncompleteError) {
      throw new TemplateTwinReviewAcknowledgementError(
        "VISIT_AUTOMATION_INCOMPLETE",
        "Required visit automation changed before review confirmation. Retry processing.",
      );
    }
    throw error;
  });
  if (applied.rolloutRejected) {
    throw new TemplateTwinReviewAcknowledgementError(
      applied.rolloutRejected.code,
      applied.rolloutRejected.reason,
    );
  }
  if (
    "encounterEvidenceRejected" in applied &&
    applied.encounterEvidenceRejected
  ) {
    throw new TemplateTwinReviewAcknowledgementError(
      "ENCOUNTER_EVIDENCE_INVALID",
      "The encounter evidence changed before review confirmation. Regenerate and review the document.",
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
