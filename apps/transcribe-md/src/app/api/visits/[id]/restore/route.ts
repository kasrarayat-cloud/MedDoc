// ============================================================================
// POST /api/visits/[id]/restore (T-M17.3 Phase 2 Commit 2)
// ----------------------------------------------------------------------------
// Pulls a soft-deleted visit back into the default view. Only works
// when `deletedAt IS NOT NULL AND archivedAt IS NULL` — archived
// visits are a separate concern (SIGNED visits reached archive via
// a deliberate click, not a delete, so they don't restore via this
// route).
//
//   Not deleted  → 400 VISIT_NOT_IN_TRASH
//   Archived     → 400 VISIT_ARCHIVED (use an unarchive flow once we
//                  ship one; not in T-M17.3 scope)
//   Already active in a concurrent request → still return 200 so a
//                  double-click races cleanly.
// ============================================================================

import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { log } from "@/lib/log";
import { logAudit } from "@/lib/audit";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { hasDurableTemplateTwinClinicalMutationProvenance } from "@/lib/template-twin/visit-mutation-authority";
import {
  enqueueTemplateTwinDataLifecycleMutationAudit,
  lockAndAssertOrdinaryDataLifecycleMutation,
  lockAndAssertTemplateTwinDataLifecycleMutation,
  pinTemplateTwinDataLifecycleMutation,
  TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT,
  TemplateTwinDataLifecycleAuthorizationError,
  type TemplateTwinDataLifecycleClaim,
} from "@/lib/template-twin/visit-lifecycle-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const POST = withApiHandler<{ id: string }>(
  "api:visits:restore",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    const authorityTarget = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        updatedAt: true,
        ...TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT,
      },
    });
    if (!authorityTarget || authorityTarget.userId !== userId) {
      return apiError("not found", 404);
    }

    let templateTwinLifecycleClaim: TemplateTwinDataLifecycleClaim | null =
      null;
    try {
      templateTwinLifecycleClaim =
        await pinTemplateTwinDataLifecycleMutation({
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
    if (
      templateTwinLifecycleClaim &&
      !isSameOriginTemplateTwinMutation(req)
    ) {
      return apiError("not found", 404);
    }

    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: visitId,
        userId,
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

    if (visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error:
            "Archived visits cannot be restored via this route. Unarchive it first.",
          code: "VISIT_ARCHIVED",
        },
        { status: 400 },
      );
    }

    if (visit.deletedAt === null) {
      return NextResponse.json({ ok: true, alreadyActive: true });
    }

    if (templateTwinLifecycleClaim) {
      try {
        const applied = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            const locked =
              await lockAndAssertTemplateTwinDataLifecycleMutation({
                tx,
                claim: templateTwinLifecycleClaim,
              });
            if (
              locked.archivedAt !== null ||
              locked.status !== visit.status ||
              locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
              locked.deletedAt?.getTime() !== visit.deletedAt?.getTime()
            ) {
              return false;
            }
            await tx.transcribeVisit.update({
              where: { id: visit.id },
              data: { deletedAt: null },
            });
            await enqueueTemplateTwinDataLifecycleMutationAudit({
              tx,
              claim: templateTwinLifecycleClaim,
              operation: "restore",
              action: "VISIT_RESTORED",
              admittedVisitUpdatedAtEpochMs: visit.updatedAt.getTime(),
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
            data: { deletedAt: null },
          });
        });
      } catch (error) {
        if (error instanceof TemplateTwinDataLifecycleAuthorizationError) {
          return apiError("The visit changed. Reload and retry.", 409);
        }
        throw error;
      }
    }
    log.info("api:visits:restore", "restored", { userId, visitId });
    void logAudit({
      action: "VISIT_RESTORED",
      targetType: "TranscribeVisit",
      targetId: visitId,
    });
    return NextResponse.json({ ok: true });
  },
);
