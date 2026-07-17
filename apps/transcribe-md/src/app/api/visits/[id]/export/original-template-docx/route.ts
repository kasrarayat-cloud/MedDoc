import { NextResponse } from "next/server";
import { randomUUID } from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { apiError, withApiHandler } from "@/lib/api-error";
import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";
import { logDelivery } from "@/lib/deliveries";
import { log } from "@/lib/log";
import { auth } from "@/lib/nextauth";
import {
  assessTemplateTwinSigning,
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
} from "@/lib/template-twin/signing-gate";
import {
  createTemplateTwinArtifactStore,
  TemplateTwinArtifactIntegrityError,
  TemplateTwinStorageUnavailableError,
} from "@/lib/template-twin/storage/artifact-store";
import { DOCX_MIME_TYPE } from "@/lib/template-twin/storage/keys";
import { TemplateTwinArtifactNotFoundError } from "@/lib/template-twin/storage/ownership";
import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  templateTwinRolloutAuditMetadata,
  TemplateTwinRolloutError,
  type TemplateTwinRolloutToken,
} from "@/lib/template-twin/rollout";
import { TemplateTwinStagingQaDisabledError } from "@/lib/template-twin/staging-qa-gate";
import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaOperation,
  TemplateTwinStagingQaVisitGuardError,
} from "@/lib/template-twin/staging-qa-visit-guard";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

/**
 * Delivers the already-rendered clone of the physician's immutable source
 * template. This route never regenerates a document. It authorizes visit
 * ownership, re-runs the signing-readiness proof, then verifies object key,
 * tenant, size, metadata, and SHA-256 while reading the immutable bytes.
 */
export const GET = withApiHandler<{ id: string }>(
  "api:visits:export:original-template-docx",
  async (_request, { params }) => {
    const { id: visitId } = await params;
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    let practiceId: string;
    let rolloutToken: TemplateTwinRolloutToken;
    try {
      practiceId = (await requireFreshDoctorIdentity(userId)).practiceId;
    } catch (error) {
      if (error instanceof AuthError) {
        return apiError("physician role required", 403, {
          code: "DOCTOR_ROLE_REQUIRED",
          retry: false,
        });
      }
      throw error;
    }
    try {
      rolloutToken = await pinTemplateTwinRollout({ practiceId });
    } catch (error) {
      if (!(error instanceof TemplateTwinRolloutError)) throw error;
      return apiError(error.message, 409, {
        code: error.code,
        retry: true,
      });
    }

    const visit = await prisma.transcribeVisit.findFirst({
      where: {
        id: visitId,
        userId,
        status: TranscribeVisitStatus.SIGNED,
        deletedAt: null,
      },
      select: {
        id: true,
        status: true,
        ...TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
      },
    });
    if (!visit) return apiError("not found", 404);
    let stagingQaRunId: string | null = null;
    let stagingQaAttempt: number | null = null;
    try {
      const stagingAdmission = assertTemplateTwinStagingQaVisitGuard({
        run: visit.templateTwinSyntheticQaRun,
        actor: { userId, practiceId },
        currentRolloutToken: rolloutToken,
      });
      stagingQaRunId = stagingAdmission.applies ? stagingAdmission.runId : null;
      stagingQaAttempt = stagingAdmission.applies
        ? visit.templateTwinSyntheticQaRun!.attempt
        : null;
    } catch (error) {
      if (
        error instanceof TemplateTwinStagingQaDisabledError ||
        (error instanceof TemplateTwinStagingQaVisitGuardError &&
          error.code === "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND")
      ) {
        return apiError("not found", 404);
      }
      if (error instanceof TemplateTwinStagingQaVisitGuardError) {
        return apiError(error.message, 409, {
          code: error.code,
          retry: false,
        });
      }
      throw error;
    }

    const assessment = assessTemplateTwinSigning({
      visitId: visit.id,
      practiceId,
      visitStatus: visit.status,
      soapFinal: visit.soapFinal,
      soapVersion: visit.soapVersion,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      noteTemplate: visit.noteTemplate,
      templateTwinFill: visit.templateTwinFill,
    });
    if (!assessment.applies) return apiError("not found", 404);
    if (!assessment.ready || !assessment.claim || !visit.templateTwinFill) {
      log.warn(
        "api:visits:export:original-template-docx",
        "verified output unavailable",
        {
          userId,
          visitId,
          blockerCodes: assessment.blockerCodes,
          blockerCount: assessment.blockerCodes.length,
        },
      );
      try {
        await enqueueTemplateTwinAudit(prisma, {
          eventKey: `template-twin-export-blocked:${visitId}:${randomUUID()}`,
          practiceId,
          actorId: userId,
          actorEmailSnapshot: session.user.email ?? null,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TranscribeVisit",
          targetId: visitId,
          metadata: {
            reasonCode: "TEMPLATE_TWIN_OUTPUT_UNVERIFIED",
            blockerCodes: [...assessment.blockerCodes],
            blockerCount: assessment.blockerCodes.length,
            compiledVersionId: assessment.compiledVersionId,
            fillManifestId: assessment.fillManifestId,
          },
        });
      } catch {
        return apiError(
          "The export safety decision could not be recorded. Try again.",
          503,
          { code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE", retry: true },
        );
      }
      return NextResponse.json(
        {
          ok: false,
          error: "The verified Original Template DOCX is not available.",
          code: "TEMPLATE_TWIN_OUTPUT_UNVERIFIED",
        },
        { status: 409 },
      );
    }

    const fill = visit.templateTwinFill;
    if (
      fill.pinnedGlobalRolloutGeneration !== rolloutToken.globalGeneration ||
      fill.pinnedPracticeRolloutGeneration !==
        rolloutToken.practiceGeneration ||
      fill.signedGlobalRolloutGeneration !== rolloutToken.globalGeneration ||
      fill.signedPracticeRolloutGeneration !== rolloutToken.practiceGeneration
    ) {
      try {
        await enqueueTemplateTwinAudit(prisma, {
          eventKey: `template-twin-export-rollout-stale:${visitId}:${randomUUID()}`,
          practiceId,
          actorId: userId,
          actorEmailSnapshot: session.user.email ?? null,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TranscribeVisit",
          targetId: visitId,
          metadata: {
            reasonCode: "TEMPLATE_TWIN_OUTPUT_ROLLOUT_STALE",
            fillManifestId: fill.id,
            currentGlobalGeneration: rolloutToken.globalGeneration.toString(),
            currentPracticeGeneration:
              rolloutToken.practiceGeneration.toString(),
          },
        });
      } catch {
        return apiError(
          "The export safety decision could not be recorded. Try again.",
          503,
          { code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE", retry: true },
        );
      }
      return apiError(
        "The Original Template DOCX was generated before rollout changed. Regenerate and sign it again.",
        409,
        { code: "TEMPLATE_TWIN_OUTPUT_ROLLOUT_STALE", retry: true },
      );
    }
    // These columns are proven non-null by assessTemplateTwinSigning. Keep the
    // guard explicit so a future refactor cannot weaken that invariant.
    if (
      !fill.outputObjectKey ||
      !fill.outputVersionId ||
      !fill.outputEtag ||
      !fill.outputSha256 ||
      !fill.outputSizeBytes
    ) {
      return apiError("verified output unavailable", 409);
    }

    let document: Buffer;
    try {
      document = await createTemplateTwinArtifactStore().readOutputArtifact({
        practiceId,
        objectKey: fill.outputObjectKey,
        expectedObjectVersionId: fill.outputVersionId,
        expectedObjectEtag: fill.outputEtag,
        expectedSha256: fill.outputSha256,
        expectedSizeBytes: fill.outputSizeBytes,
      });
    } catch (error) {
      const unavailable = error instanceof TemplateTwinStorageUnavailableError;
      const integrityFailure =
        error instanceof TemplateTwinArtifactIntegrityError ||
        error instanceof TemplateTwinArtifactNotFoundError;
      log.warn(
        "api:visits:export:original-template-docx",
        "artifact read failed",
        {
          userId,
          visitId,
          errorCode: unavailable
            ? "TEMPLATE_TWIN_STORAGE_UNAVAILABLE"
            : integrityFailure
              ? "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED"
              : "TEMPLATE_TWIN_OUTPUT_READ_FAILED",
        },
      );
      const reasonCode = unavailable
        ? "TEMPLATE_TWIN_STORAGE_UNAVAILABLE"
        : "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED";
      try {
        await enqueueTemplateTwinAudit(prisma, {
          eventKey: `template-twin-export-blocked:${visitId}:${randomUUID()}`,
          practiceId,
          actorId: userId,
          actorEmailSnapshot: session.user.email ?? null,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TranscribeVisit",
          targetId: visitId,
          metadata: {
            reasonCode,
            compiledVersionId: assessment.compiledVersionId,
            fillManifestId: assessment.fillManifestId,
          },
        });
      } catch {
        return apiError(
          "The export safety decision could not be recorded. Try again.",
          503,
          { code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE", retry: true },
        );
      }
      return NextResponse.json(
        {
          ok: false,
          error: unavailable
            ? "Original Template DOCX storage is temporarily unavailable."
            : "The Original Template DOCX failed integrity verification.",
          code: unavailable
            ? "TEMPLATE_TWIN_STORAGE_UNAVAILABLE"
            : "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED",
        },
        { status: unavailable ? 503 : 409 },
      );
    }

    let finalAuthorization:
      | { allowed: true }
      | { allowed: false; code: string; reason: string };
    try {
      finalAuthorization = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
            tx,
            practiceId,
            pinnedToken: rolloutToken,
          });
          if (!finalRollout.allowed) {
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin-export-rollout-blocked:${visitId}:${randomUUID()}`,
              practiceId,
              actorId: userId,
              actorEmailSnapshot: session.user.email ?? null,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TranscribeVisit",
              targetId: visitId,
              metadata: {
                reasonCode: finalRollout.code,
                operation: "download_final_authorization",
                fillManifestId: fill.id,
                ...templateTwinRolloutAuditMetadata(
                  rolloutToken,
                  finalRollout.currentToken,
                ),
              },
            });
            return {
              allowed: false as const,
              code: finalRollout.code,
              reason: finalRollout.reason,
            };
          }
          if (stagingQaRunId) {
            try {
              if (stagingQaAttempt === null) {
                throw new TemplateTwinStagingQaVisitGuardError(
                  "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
                  "Synthetic QA attempt identity is unavailable.",
                );
              }
              await lockAndAssertTemplateTwinStagingQaOperation({
                tx,
                runId: stagingQaRunId,
                expectedAttempt: stagingQaAttempt,
                actor: { userId, practiceId },
                currentRolloutToken: finalRollout.token,
                allowedStatuses: ["COMPLETED"],
              });
            } catch (error) {
              if (
                error instanceof TemplateTwinStagingQaDisabledError ||
                error instanceof TemplateTwinStagingQaVisitGuardError
              ) {
                const code = error.code;
                await enqueueTemplateTwinAudit(tx, {
                  eventKey: `template-twin-export-staging-blocked:${visitId}:${code}`,
                  practiceId,
                  actorId: userId,
                  actorEmailSnapshot: session.user.email ?? null,
                  action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
                  targetType: "TranscribeVisit",
                  targetId: visitId,
                  metadata: {
                    reasonCode: code,
                    operation: "staging_download_final_authorization",
                    stagingQaRunId,
                    fillManifestId: fill.id,
                  },
                });
                return {
                  allowed: false as const,
                  code,
                  reason:
                    "Synthetic QA authorization changed before download. Create a new run.",
                };
              }
              throw error;
            }
          }

          const currentFill = await tx.templateTwinFillManifest.findUnique({
            where: { id: fill.id },
            select: {
              status: true,
              signedDecisionAt: true,
              outputObjectKey: true,
              outputVersionId: true,
              outputEtag: true,
              outputSha256: true,
              outputSizeBytes: true,
              pinnedGlobalRolloutGeneration: true,
              pinnedPracticeRolloutGeneration: true,
              signedGlobalRolloutGeneration: true,
              signedPracticeRolloutGeneration: true,
            },
          });
          if (
            !currentFill ||
            currentFill.status !== "SIGNED" ||
            currentFill.signedDecisionAt === null ||
            currentFill.outputObjectKey !== fill.outputObjectKey ||
            currentFill.outputVersionId !== fill.outputVersionId ||
            currentFill.outputEtag !== fill.outputEtag ||
            currentFill.outputSha256 !== fill.outputSha256 ||
            currentFill.outputSizeBytes !== fill.outputSizeBytes ||
            currentFill.pinnedGlobalRolloutGeneration !==
              rolloutToken.globalGeneration ||
            currentFill.pinnedPracticeRolloutGeneration !==
              rolloutToken.practiceGeneration ||
            currentFill.signedGlobalRolloutGeneration !==
              rolloutToken.globalGeneration ||
            currentFill.signedPracticeRolloutGeneration !==
              rolloutToken.practiceGeneration
          ) {
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin-export-claim-stale:${visitId}:${randomUUID()}`,
              practiceId,
              actorId: userId,
              actorEmailSnapshot: session.user.email ?? null,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TranscribeVisit",
              targetId: visitId,
              metadata: {
                reasonCode: "TEMPLATE_TWIN_OUTPUT_CLAIM_STALE",
                operation: "download_final_authorization",
                fillManifestId: fill.id,
              },
            });
            return {
              allowed: false as const,
              code: "TEMPLATE_TWIN_OUTPUT_CLAIM_STALE",
              reason:
                "The Original Template DOCX changed before download authorization. Refresh and try again.",
            };
          }

          await enqueueTemplateTwinAudit(tx, {
            eventKey: `template-twin-exported:${visitId}:${randomUUID()}`,
            practiceId,
            actorId: userId,
            actorEmailSnapshot: session.user.email ?? null,
            action: "EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED",
            targetType: "TranscribeVisit",
            targetId: visitId,
            metadata: {
              sizeBytes: document.byteLength,
              compiledVersionId: assessment.compiledVersionId,
              fillManifestId: assessment.fillManifestId,
              noteTemplateVersion: visit.noteTemplateVersion,
              rolloutGlobalGeneration: rolloutToken.globalGeneration.toString(),
              rolloutPracticeGeneration:
                rolloutToken.practiceGeneration.toString(),
            },
          });
          return { allowed: true as const };
        },
      );
    } catch {
      return apiError("The export could not be recorded. Try again.", 503, {
        code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE",
        retry: true,
      });
    }
    if (!finalAuthorization.allowed) {
      return apiError(finalAuthorization.reason, 409, {
        code: finalAuthorization.code,
        retry: true,
      });
    }
    logDelivery({
      visitId,
      channel: "docx_original_template",
      sizeBytes: document.byteLength,
    });

    return new NextResponse(document as unknown as BodyInit, {
      status: 200,
      headers: {
        "Content-Type": DOCX_MIME_TYPE,
        "Content-Length": String(document.byteLength),
        "Content-Disposition": `attachment; filename="quillmd-original-template-${visitId}.docx"`,
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
);
