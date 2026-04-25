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

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { deleteAudioObject } from '@/lib/minio';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const POST = withApiHandler<{ id: string }>(
  'api:visits:delete',
  async (req, { params }) => {
    const { id: visitId } = await params;
    const permanent = new URL(req.url).searchParams.get('permanent') === '1';

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
        status: true,
        deletedAt: true,
        archivedAt: true,
        audioKey: true,
        dictationAudioKey: true,
        rawTextInput: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    if (visit.status === TranscribeVisitStatus.SIGNED) {
      return NextResponse.json(
        {
          error: 'Signed visits cannot be deleted. Archive it instead.',
          code: 'VISIT_SIGNED',
        },
        { status: 400 }
      );
    }

    // ── Already-trashed + ?permanent=1 → HARD purge now ──
    if (visit.deletedAt !== null && permanent) {
      try {
        await prisma.$transaction(async (tx: typeof prisma) => {
          await tx.aiCall.deleteMany({ where: { visitId } });
          await tx.transcribeVisit.delete({ where: { id: visitId } });
        });
      } catch (err) {
        console.error(
          '[api:visits:delete] permanent-purge tx failed:',
          redactPhi(err instanceof Error ? err.message : err)
        );
        return apiError('Could not delete permanently. Try again.', 500);
      }
      await Promise.all(
        [visit.audioKey, visit.dictationAudioKey].map(async (key) => {
          if (!key) return;
          try {
            await deleteAudioObject(key);
          } catch (err) {
            console.warn(
              `[api:visits:delete] minio cleanup failed key=${key}:`,
              redactPhi(err instanceof Error ? err.message : err)
            );
          }
        })
      );
      log.info('api:visits:delete', 'permanent-purged', {
        userId,
        visitId,
        prevStatus: visit.status,
      });
      void logAudit({
        action: 'VISIT_DELETED',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        metadata: { mode: 'permanent', prevStatus: visit.status },
      });
      return NextResponse.json({ ok: true, mode: 'permanent' });
    }

    if (visit.deletedAt !== null) {
      return NextResponse.json({ ok: true, alreadyDeleted: true });
    }

    // HARD delete path — QUEUED visit that never received input.
    const noInput =
      visit.audioKey === null &&
      visit.dictationAudioKey === null &&
      (visit.rawTextInput === null || visit.rawTextInput.length === 0);

    if (
      visit.status === TranscribeVisitStatus.QUEUED &&
      noInput
    ) {
      // Transaction: clear AiCall rows first (no FK cascade because
      // AiCall.visitId is a loose nullable pointer), then the visit.
      // If either step fails, both roll back and the row stays visible
      // — the doctor can retry the click.
      try {
        await prisma.$transaction(async (tx: typeof prisma) => {
          await tx.aiCall.deleteMany({ where: { visitId } });
          await tx.transcribeVisit.delete({ where: { id: visitId } });
        });
      } catch (err) {
        console.error(
          '[api:visits:delete] hard-delete tx failed:',
          redactPhi(err instanceof Error ? err.message : err)
        );
        return apiError('Could not delete visit. Try again.', 500);
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
              redactPhi(err instanceof Error ? err.message : err)
            );
          }
        })
      );

      log.info('api:visits:delete', 'hard-deleted', {
        userId,
        visitId,
        prevStatus: visit.status,
      });
      void logAudit({
        action: 'VISIT_DELETED',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        metadata: { mode: 'hard', prevStatus: visit.status },
      });
      return NextResponse.json({ ok: true, mode: 'hard' });
    }

    // SOFT delete path — everything else (PROCESSING / REVIEW / READY,
    // or QUEUED-with-input).
    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { deletedAt: new Date() },
    });
    log.info('api:visits:delete', 'soft-deleted', {
      userId,
      visitId,
      prevStatus: visit.status,
    });
    void logAudit({
      action: 'VISIT_DELETED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
      metadata: { mode: 'soft', prevStatus: visit.status },
    });
    return NextResponse.json({ ok: true, mode: 'soft' });
  }
);
