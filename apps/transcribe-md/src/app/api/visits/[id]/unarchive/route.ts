// ============================================================================
// POST /api/visits/[id]/unarchive (T-M17.3 Phase 4 Commit 6)
// ----------------------------------------------------------------------------
// Symmetric counterpart to /api/visits/[id]/archive. Clears archivedAt
// so the visit reappears in the default dashboard. SIGNED status is
// preserved (archive never changed status; unarchive doesn't either).
//
//   Not archived      → 200 idempotent (alreadyActive)
//   Trashed            → 400 VISIT_DELETED (handle via /restore first)
// ============================================================================

import { NextResponse } from "next/server";

import prisma from "@meddoc/db";

import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { log } from "@/lib/log";
import { logAudit } from "@/lib/audit";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const POST = withApiHandler<{ id: string }>(
  "api:visits:unarchive",
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        deletedAt: true,
        archivedAt: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);

    if (visit.deletedAt !== null) {
      return NextResponse.json(
        {
          error: "Trashed visits must be restored first.",
          code: "VISIT_DELETED",
        },
        { status: 400 },
      );
    }

    if (visit.archivedAt === null) {
      return NextResponse.json({ ok: true, alreadyActive: true });
    }

    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { archivedAt: null },
    });
    log.info("api:visits:unarchive", "unarchived", { userId, visitId });
    void logAudit({
      action: "VISIT_UNARCHIVED",
      targetType: "TranscribeVisit",
      targetId: visitId,
    });
    return NextResponse.json({ ok: true });
  },
);
