// ============================================================================
// POST /api/visits/[id]/delete (T-M17.3 Phase 2 Commit 2)
// ----------------------------------------------------------------------------
// Delete strategy is status-aware:
//
//   SIGNED           → 400. Signed visits cannot be deleted; the UI
//                      offers an Archive button instead.
//   QUEUED + no input → HARD delete. Row has no clinical value and the
//                      doctor probably mis-created it (mode-tile click
//                      without committing content). AiCall rows for the
//                      visit are cascaded via a transaction; MinIO
//                      objects are swept best-effort afterward.
//   Already trashed + ?permanent=1 → HARD delete now (user clicked
//                      "Delete permanently" from the trash banner). Full
//                      MinIO sweep of audioKey + dictationAudioKey so
//                      the cleanup cron doesn't have to wait.
//   Anything else    → SOFT delete (deletedAt = now()). The 15-day
//                      cleanup cron hard-deletes later; the doctor can
//                      restore in the meantime via /api/visits/[id]/restore.
//
// Already-deleted visits without ?permanent=1 return 200 idempotently
// so a double-click or a flaky network replay can't flip UI state into
// an error.
// 404 on wrong owner (anti-enumeration — same pattern as /retry).
// ============================================================================

import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { deleteAudioObject } from "@/lib/minio";
import { redactPhi } from "@meddoc/ai";
import { log } from "@/lib/log";
import { logAudit } from "@/lib/audit";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import {
  enqueueTemplateTwinDataLifecycleMutationAudit,
  lockAndAssertOrdinaryDataLifecycleMutation,
  lockAndAssertTemplateTwinDataLifecycleMutation,
  pinTemplateTwinDataLifecycleMutation,
  TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT,
  TemplateTwinDataLifecycleAuthorizationError,
  type TemplateTwinDataLifecycleClaim,
} from "@/lib/template-twin/visit-lifecycle-authority";
import {
  hasDurableTemplateTwinClinicalMutationProvenance,
  loadTemplateTwinClinicalMutationAdmissionTarget,
} from "@/lib/template-twin/visit-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const POST = withApiHandler<{ id: string }>(
  "api:visits:delete",
  async (req, { params }) => {
    const { id: visitId } = await params;
    const permanent = new URL(req.url).searchParams.get("permanent") === "1";

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    // Establish current lifecycle authority from immutable identifiers before
    // selecting audio keys or typed clinical input used by delete strategy.
    const authorityTarget =
      await loadTemplateTwinClinicalMutationAdmissionTarget({
        visitId,
        actorUserId: userId,
      });
    if (!authorityTarget || authorityTarget.userId !== userId) {
      return apiError("not found", 404);
    }
    let templateTwinLifecycleClaim: TemplateTwinDataLifecycleClaim | null =
      null;
    try {
      templateTwinLifecycleClaim = await pinTemplateTwinDataLifecycleMutation({
        visitId,
        actorUserId: userId,
        provenance: authorityTarget,
      });
    } catch (error) {
      if (error instanceof TemplateTwinDataLifecycleAuthorizationError) {
        return apiError("not found", 404);
      }
      throw error;
    }
    if (templateTwinLifecycleClaim && !isSameOriginTemplateTwinMutation(req)) {
      return apiError("not found", 404);
    }

    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: visitId,
        ...currentClinicalVisitActorWhere(userId),
        updatedAt: authorityTarget.updatedAt,
        ...(templateTwinLifecycleClaim
          ? {}
          : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      },
      select: {
        id: true,
        userId: true,
        status: true,
        updatedAt: true,
        deletedAt: true,
        archivedAt: true,
        audioKey: true,
        dictationAudioKey: true,
        rawTextInput: true,
        ...TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT,
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);
    if (
      Boolean(templateTwinLifecycleClaim) !==
      hasDurableTemplateTwinClinicalMutationProvenance(visit)
    ) {
      return apiError("The visit changed. Reload and retry.", 409);
    }

    if (visit.status === TranscribeVisitStatus.SIGNED) {
      return NextResponse.json(
        {
          error: "Signed visits cannot be deleted. Archive it instead.",
          code: "VISIT_SIGNED",
        },
        { status: 400 },
      );
    }

    // ── Already-trashed + ?permanent=1 → HARD purge now ──
    if (visit.deletedAt !== null && permanent) {
      if (
        templateTwinLifecycleClaim?.fillManifestId ||
        templateTwinLifecycleClaim?.providerExecutionIds.length
      ) {
        return apiError(
          "Immutable Template Twin evidence must be retained.",
          409,
          { code: "TEMPLATE_TWIN_IMMUTABLE_EVIDENCE_RETAINED" },
        );
      }
      try {
        const applied = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            if (templateTwinLifecycleClaim) {
              const locked =
                await lockAndAssertTemplateTwinDataLifecycleMutation({
                  tx,
                  claim: templateTwinLifecycleClaim,
                });
              if (
                locked.status !== visit.status ||
                locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
                locked.deletedAt?.getTime() !== visit.deletedAt?.getTime() ||
                locked.audioKey !== visit.audioKey ||
                locked.dictationAudioKey !== visit.dictationAudioKey ||
                locked.templateTwinFill !== null ||
                locked.templateTwinProviderExecutions.length !== 0
              ) {
                return false;
              }
            } else {
              await lockAndAssertOrdinaryDataLifecycleMutation({
                tx,
                visitId,
                actorUserId: userId,
                admittedVisitUpdatedAt: visit.updatedAt,
                admittedPatientId: visit.patientId,
                admittedNoteTemplateId: visit.noteTemplateId,
              });
            }
            await tx.aiCall.deleteMany({ where: { visitId } });
            await tx.transcribeVisit.delete({ where: { id: visitId } });
            if (templateTwinLifecycleClaim) {
              await enqueueTemplateTwinDataLifecycleMutationAudit({
                tx,
                claim: templateTwinLifecycleClaim,
                operation: "hard_delete",
                action: "VISIT_DELETED",
                admittedVisitUpdatedAtEpochMs: visit.updatedAt.getTime(),
                metadata: { deleteMode: "permanent" },
              });
            }
            return true;
          },
        );
        if (!applied) {
          return apiError("The visit changed. Reload and retry.", 409);
        }
      } catch (err) {
        if (err instanceof TemplateTwinDataLifecycleAuthorizationError) {
          return templateTwinLifecycleClaim
            ? apiError("not found", 404)
            : apiError("The visit changed. Reload and retry.", 409);
        }
        console.error(
          "[api:visits:delete] permanent-purge tx failed:",
          redactPhi(err instanceof Error ? err.message : err),
        );
        return apiError("Could not delete permanently. Try again.", 500);
      }
      await Promise.all(
        [visit.audioKey, visit.dictationAudioKey].map(async (key) => {
          if (!key) return;
          try {
            await deleteAudioObject(key);
          } catch (err) {
            console.warn(
              `[api:visits:delete] minio cleanup failed key=${key}:`,
              redactPhi(err instanceof Error ? err.message : err),
            );
          }
        }),
      );
      log.info("api:visits:delete", "permanent-purged", {
        userId,
        visitId,
        prevStatus: visit.status,
      });
      void logAudit({
        action: "VISIT_DELETED",
        targetType: "TranscribeVisit",
        targetId: visitId,
        metadata: { mode: "permanent", prevStatus: visit.status },
      });
      return NextResponse.json({ ok: true, mode: "permanent" });
    }

    if (visit.deletedAt !== null) {
      return NextResponse.json({ ok: true, alreadyDeleted: true });
    }

    // HARD delete path — QUEUED visit that never received input.
    const noInput =
      visit.audioKey === null &&
      visit.dictationAudioKey === null &&
      (visit.rawTextInput === null || visit.rawTextInput.length === 0);

    if (visit.status === TranscribeVisitStatus.QUEUED && noInput) {
      if (
        templateTwinLifecycleClaim?.fillManifestId ||
        templateTwinLifecycleClaim?.providerExecutionIds.length
      ) {
        return apiError(
          "Immutable Template Twin evidence must be retained.",
          409,
          { code: "TEMPLATE_TWIN_IMMUTABLE_EVIDENCE_RETAINED" },
        );
      }
      // Transaction: clear AiCall rows first (no FK cascade because
      // AiCall.visitId is a loose nullable pointer), then the visit.
      // If either step fails, both roll back and the row stays visible
      // — the doctor can retry the click.
      try {
        const applied = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            if (templateTwinLifecycleClaim) {
              const locked =
                await lockAndAssertTemplateTwinDataLifecycleMutation({
                  tx,
                  claim: templateTwinLifecycleClaim,
                });
              if (
                locked.status !== TranscribeVisitStatus.QUEUED ||
                locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
                locked.deletedAt !== null ||
                locked.audioKey !== null ||
                locked.dictationAudioKey !== null ||
                Boolean(locked.rawTextInput?.length) ||
                locked.templateTwinFill !== null ||
                locked.templateTwinProviderExecutions.length !== 0
              ) {
                return false;
              }
            } else {
              await lockAndAssertOrdinaryDataLifecycleMutation({
                tx,
                visitId,
                actorUserId: userId,
                admittedVisitUpdatedAt: visit.updatedAt,
                admittedPatientId: visit.patientId,
                admittedNoteTemplateId: visit.noteTemplateId,
              });
            }
            await tx.aiCall.deleteMany({ where: { visitId } });
            await tx.transcribeVisit.delete({ where: { id: visitId } });
            if (templateTwinLifecycleClaim) {
              await enqueueTemplateTwinDataLifecycleMutationAudit({
                tx,
                claim: templateTwinLifecycleClaim,
                operation: "hard_delete",
                action: "VISIT_DELETED",
                admittedVisitUpdatedAtEpochMs: visit.updatedAt.getTime(),
                metadata: { deleteMode: "hard" },
              });
            }
            return true;
          },
        );
        if (!applied) {
          return apiError("The visit changed. Reload and retry.", 409);
        }
      } catch (err) {
        if (err instanceof TemplateTwinDataLifecycleAuthorizationError) {
          return templateTwinLifecycleClaim
            ? apiError("not found", 404)
            : apiError("The visit changed. Reload and retry.", 409);
        }
        console.error(
          "[api:visits:delete] hard-delete tx failed:",
          redactPhi(err instanceof Error ? err.message : err),
        );
        return apiError("Could not delete visit. Try again.", 500);
      }

      // Best-effort MinIO sweep. The visit had no audioKey /
      // dictationAudioKey but a half-uploaded multipart could have
      // left junk under the conventional prefix — T-M12 sweep picks
      // up anything we miss here.
      await Promise.all(
        [visit.audioKey, visit.dictationAudioKey].map(async (key) => {
          if (!key) return;
          try {
            await deleteAudioObject(key);
          } catch (err) {
            console.warn(
              `[api:visits:delete] minio cleanup failed key=${key}:`,
              redactPhi(err instanceof Error ? err.message : err),
            );
          }
        }),
      );

      log.info("api:visits:delete", "hard-deleted", {
        userId,
        visitId,
        prevStatus: visit.status,
      });
      void logAudit({
        action: "VISIT_DELETED",
        targetType: "TranscribeVisit",
        targetId: visitId,
        metadata: { mode: "hard", prevStatus: visit.status },
      });
      return NextResponse.json({ ok: true, mode: "hard" });
    }

    // SOFT delete path — everything else (PROCESSING / REVIEW / READY,
    // or QUEUED-with-input).
    const deletedAt = new Date();
    if (templateTwinLifecycleClaim) {
      try {
        const applied = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            const locked = await lockAndAssertTemplateTwinDataLifecycleMutation(
              {
                tx,
                claim: templateTwinLifecycleClaim,
              },
            );
            if (
              locked.status !== visit.status ||
              locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
              locked.deletedAt !== null ||
              locked.archivedAt?.getTime() !== visit.archivedAt?.getTime() ||
              locked.audioKey !== visit.audioKey ||
              locked.dictationAudioKey !== visit.dictationAudioKey ||
              locked.rawTextInput !== visit.rawTextInput
            ) {
              return false;
            }
            await tx.transcribeVisit.update({
              where: { id: visit.id },
              data: { deletedAt },
            });
            await enqueueTemplateTwinDataLifecycleMutationAudit({
              tx,
              claim: templateTwinLifecycleClaim,
              operation: "soft_delete",
              action: "VISIT_DELETED",
              admittedVisitUpdatedAtEpochMs: visit.updatedAt.getTime(),
              metadata: { deleteMode: "soft" },
            });
            return true;
          },
        );
        if (!applied) {
          return apiError("The visit changed. Reload and retry.", 409);
        }
      } catch (error) {
        if (error instanceof TemplateTwinDataLifecycleAuthorizationError) {
          return apiError("not found", 404);
        }
        throw error;
      }
    } else {
      try {
        await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
          await lockAndAssertOrdinaryDataLifecycleMutation({
            tx,
            visitId: visit.id,
            actorUserId: userId,
            admittedVisitUpdatedAt: visit.updatedAt,
            admittedPatientId: visit.patientId,
            admittedNoteTemplateId: visit.noteTemplateId,
          });
          await tx.transcribeVisit.update({
            where: { id: visit.id },
            data: { deletedAt },
          });
        });
      } catch (error) {
        if (error instanceof TemplateTwinDataLifecycleAuthorizationError) {
          return apiError("The visit changed. Reload and retry.", 409);
        }
        throw error;
      }
    }
    log.info("api:visits:delete", "soft-deleted", {
      userId,
      visitId,
      prevStatus: visit.status,
    });
    void logAudit({
      action: "VISIT_DELETED",
      targetType: "TranscribeVisit",
      targetId: visitId,
      metadata: { mode: "soft", prevStatus: visit.status },
    });
    return NextResponse.json({ ok: true, mode: "soft" });
  },
);
