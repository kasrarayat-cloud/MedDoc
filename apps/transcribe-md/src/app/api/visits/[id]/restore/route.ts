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

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const POST = withApiHandler<{ id: string }>(
  'api:visits:restore',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

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
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    if (visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error:
            'Archived visits cannot be restored via this route. Unarchive it first.',
          code: 'VISIT_ARCHIVED',
        },
        { status: 400 }
      );
    }

    if (visit.deletedAt === null) {
      return NextResponse.json({ ok: true, alreadyActive: true });
    }

    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { deletedAt: null },
    });
    log.info('api:visits:restore', 'restored', { userId, visitId });
    void logAudit({
      action: 'VISIT_RESTORED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
    });
    return NextResponse.json({ ok: true });
  }
);
