// ============================================================================
// POST /api/visits/[id]/archive (T-M17.3 Phase 2 Commit 2)
// ----------------------------------------------------------------------------
// Archive only applies to SIGNED visits. HIPAA retention forbids hard-
// delete of signed clinical notes; archiving hides them from the
// dashboard's default view while preserving the row indefinitely.
//
// Non-SIGNED visits → 400 (code: VISIT_NOT_SIGNED). The UI routes
// those through /api/visits/[id]/delete instead.
//
// Already-archived → 200 idempotent.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { getSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const POST = withApiHandler<{ id: string }>(
  'api:visits:archive',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        status: true,
        archivedAt: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    if (visit.status !== TranscribeVisitStatus.SIGNED) {
      return NextResponse.json(
        {
          error:
            'Only signed visits can be archived. Use Delete for draft or in-progress visits.',
          code: 'VISIT_NOT_SIGNED',
        },
        { status: 400 }
      );
    }

    if (visit.archivedAt !== null) {
      return NextResponse.json({ ok: true, alreadyArchived: true });
    }

    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { archivedAt: new Date() },
    });
    log.info('api:visits:archive', 'archived', { userId, visitId });
    void logAudit({
      action: 'VISIT_ARCHIVED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
    });
    return NextResponse.json({ ok: true });
  }
);
